"""Telefondan kullanım: bilgisayardaki TekTıkla'yı ev ağındaki telefonun tarayıcısında açar (iPhone ve Android).

Telefon QR kodu okutunca aynı arayüz telefonda açılır; indirme, Reels, dönüştürme gibi işleri bilgisayar yapar,
sonuçlar telefona iner. Sunucu yalnızca "Telefondan kullan" açıkken çalışır, yalnızca yerel ağdan (özel IP) gelen
isteklere ve doğru bağlanma koduna cevap verir. Telefondan yalnızca listedeki işlemler çağrılabilir: bilgisayarda
dosya ya da klasör açmak, kayıt klasörünü değiştirmek, güncelleme kurmak gibi işler yapılamaz.
"""
from __future__ import annotations

import io
import ipaddress
import json
import mimetypes
import os
import re
import secrets
import shutil
import socket
import threading
import time
import urllib.parse
from collections import deque
from email.utils import formatdate, parsedate_to_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image

from . import i18n
from .config import APP_DIR, UPLOAD_DIR

WEB_DIR = Path(__file__).resolve().parent / "web"
PORTS = range(8790, 8800)  # telefonda kayıtlı adres değişmesin diye önce hep aynı kapılar denenir
MAX_UPLOAD = 4 * 1024 ** 3  # telefondan gelen tek dosya en fazla 4 GB
KEY_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # birbirine benzeyen 0/O ve 1/I yok
CLIENT_TTL = 600  # bu kadar saniye sessiz kalan telefonun olay kuyruğu silinir (dönünce sayfa yenilenir)
MAX_EVENTS = 4000
LONG_POLL = 20  # yeni olay yoksa telefonun isteği en fazla bu kadar bekletilir (pil ve ağ dostu)
UPLOAD_KEEP_DAYS = 3
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}

# telefondan çağrılabilen Api metotları; listede olmayanlar (dosya/klasör açma, klasör seçme, güncelleme…) reddedilir
ALLOWED = {
    "init", "analyze", "download", "quick", "cancel", "retry", "remove", "clear_finished", "clear_history",
    "similar", "ai_run", "download_thumbnail", "tool_status", "set_setting", "save_api_key", "delete_api_key",
    "save_service_key", "delete_service_key", "support_info", "account_state", "studio_init", "tts_voices", "read_made",
    "watch_list", "watch_add", "watch_set", "watch_move", "watch_remove", "watch_clear", "watch_retry",
    "image_generate", "image_recompose", "reels_analyze", "reels_render", "reels_idea", "dub_start",
    "convert_start", "convert_info", "convert_estimate", "convert_preview", "editor_url", "editor_recent", "editor_save",
}
# yalnızca telefonun kullandığı yardımcılar → Api'deki karşılıkları (masaüstü arayüzüne açılmasınlar diye gizli)
REMOTE_CALLS = {"remote_hello": "_remote_hello", "remote_urls": "_remote_urls", "remote_i18n": "_remote_i18n"}
# bilgisayara özgü ayarlar telefondan değiştirilemez
LOCKED_SETTINGS = {"download_dir", "clipboard_watch", "auto_update_check", "sidebar", "language"}
TYPES = {  # Windows kayıt defterindeki türler yanlış olabiliyor (ör. .js → text/plain; tarayıcı çalıştırmaz)
    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8", ".txt": "text/plain; charset=utf-8", ".svg": "image/svg+xml",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".avif": "image/avif",
    ".gif": "image/gif", ".bmp": "image/bmp", ".ico": "image/x-icon", ".ttf": "font/ttf", ".woff2": "font/woff2",
    ".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm", ".mkv": "video/x-matroska",
    ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".aac": "audio/aac", ".wav": "audio/wav", ".ogg": "audio/ogg",
    ".opus": "audio/ogg", ".flac": "audio/flac", ".pdf": "application/pdf", ".srt": "text/plain; charset=utf-8",
}
MANIFEST = json.dumps({
    "name": "TekTıkla", "short_name": "TekTıkla", "start_url": "/", "scope": "/", "display": "standalone",
    "background_color": "#050505", "theme_color": "#050505",
    "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
              {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"}],
}, ensure_ascii=False).encode("utf-8")
ICONS = {"/apple-touch-icon.png": 180, "/icon-192.png": 192, "/icon-512.png": 512}
HEAD = ('<meta name="apple-mobile-web-app-capable" content="yes">'
        '<meta name="mobile-web-app-capable" content="yes">'
        '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">'
        '<meta name="apple-mobile-web-app-title" content="TekTıkla">'
        '<meta name="theme-color" content="#050505">'
        '<link rel="manifest" href="manifest.webmanifest">'
        '<link rel="apple-touch-icon" href="apple-touch-icon.png">')

_icons: dict[int, bytes] = {}


def new_key() -> str:
    return "".join(secrets.choice(KEY_CHARS) for _ in range(10))


def lan_ips() -> list[str]:
    """Bu bilgisayarın ev ağındaki IPv4 adresleri; varsayılan ağ kartınınki önce."""
    found: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # paket gönderilmez; yalnızca hangi kartın kullanılacağı öğrenilir
            found.append(s.getsockname()[0])
    except OSError:
        pass
    try:
        found += [info[4][0] for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)]
    except OSError:
        pass
    out: list[str] = []
    for ip in found:
        addr = ipaddress.ip_address(ip)
        if ip not in out and addr.is_private and not addr.is_loopback and not addr.is_link_local:
            out.append(ip)
    return out


def device_name(agent: str) -> str:
    a = agent.lower()
    if "iphone" in a:
        return "iPhone"
    if "ipad" in a or ("macintosh" in a and "mobile" in a):
        return "iPad"
    if "android" in a:
        return "Android"
    if "windows" in a:
        return "Windows"
    if "mac os" in a:
        return "Mac"
    return "Tarayıcı"


def _icon(size: int) -> bytes:
    """Ana ekran simgesi (iPhone'da "Ana Ekrana Ekle", Android'de "Ana ekrana ekle")."""
    if size not in _icons:
        img = Image.open(APP_DIR / "assets" / "tektikla.png").convert("RGBA")
        bg = img.getpixel((img.width // 8, img.height // 2))[:3]  # simgenin kendi zemini: köşeler boş kalmasın
        img = img.resize((size, size), Image.LANCZOS)
        canvas = Image.new("RGB", (size, size), bg)
        canvas.paste(img, (0, 0), img)
        buf = io.BytesIO()
        canvas.save(buf, "PNG", optimize=True)
        _icons[size] = buf.getvalue()
    return _icons[size]


def _page() -> bytes:
    """Masaüstündeki arayüzün aynısı; telefon köprüsü (remote.js) ve ana ekran bilgileri eklenir."""
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    html = html.replace("<head>", "<head>" + HEAD, 1)
    html = html.replace('initial-scale=1">', 'initial-scale=1, viewport-fit=cover">', 1)
    html = html.replace("<body>", '<body class="remote">', 1)
    html = html.replace('<script src="app.js"></script>', '<script src="remote.js"></script>\n<script src="app.js"></script>', 1)
    return html.encode("utf-8")


def _ctype(path: str | Path) -> str:
    return TYPES.get(Path(path).suffix.lower()) or mimetypes.guess_type(str(path))[0] or "application/octet-stream"


def _clean_uploads() -> None:
    """Birkaç günden eski telefon yüklemelerini siler (sonuç dosyaları indirme klasöründe kalır)."""
    if not UPLOAD_DIR.is_dir():
        return
    limit = time.time() - UPLOAD_KEEP_DAYS * 86400
    for folder in UPLOAD_DIR.iterdir():
        try:
            if folder.is_dir() and folder.stat().st_mtime < limit:
                shutil.rmtree(folder, ignore_errors=True)
        except OSError:
            pass


class _Client:
    """Bağlı bir telefon sayfası: kendi olay kuyruğu olur, masaüstüyle aynı olayları alır."""
    __slots__ = ("events", "seen", "agent", "ip", "lost")

    def __init__(self, agent: str, ip: str, lost: bool):
        self.events: deque = deque()
        self.seen = time.monotonic()
        self.agent, self.ip = agent, ip
        self.lost = lost  # sunucu bu sayfayı tanımıyordu ya da kuyruk taştı: sayfa yenilenmeli


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "TekTikla"
    sys_version = ""
    _body_done = True

    def log_message(self, *args):  # konsola yazmasın
        pass

    @property
    def remote(self) -> RemoteServer:
        return self.server.remote

    def _send(self, code: int, body: bytes = b"", ctype: str = "text/plain; charset=utf-8",
              headers: dict | None = None, cache: str = "no-store") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        if not self._body_done:  # okunmayan gövde bağlantıda kalıp sonraki isteği bozmasın
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _local(self) -> bool:
        try:
            ip = ipaddress.ip_address(self.client_address[0])
        except ValueError:
            return False
        return ip.is_private or ip.is_loopback

    def _authorized(self) -> bool:
        ip, now = self.client_address[0], time.time()
        recent = [t for t in self.remote.fails.get(ip, []) if now - t < 60]
        if len(recent) >= 20:  # dakikada 20 yanlış koddan sonra o adres bir dakika bekletilir
            return False
        if secrets.compare_digest(self.headers.get("X-TekTikla-Key", "").encode(), self.remote.key.encode()):
            return True
        self.remote.fails[ip] = recent + [now]
        return False

    # -- GET: arayüz, önizlemeler, telefona indirme
    def do_GET(self):
        if not self._local():
            return self._send(403)
        url = urllib.parse.urlsplit(self.path)
        path = url.path
        if path in ("/", "/index.html"):
            return self._send(200, _page(), "text/html; charset=utf-8")
        if path == "/manifest.webmanifest":
            return self._send(200, MANIFEST, "application/manifest+json", cache="no-cache")
        if path in ICONS:
            return self._send(200, _icon(ICONS[path]), "image/png", cache="max-age=86400")
        if path.startswith("/m/"):  # önizlemeler: küçük resimler, videolar
            srv = getattr(self.remote.api, "_media_srv", None)
            return self._file(srv.files.get(path[3:].split("/")[0], "") if srv else "")
        if path.startswith("/f/"):  # telefona indirilecek dosya (?dl=1: kaydet, yoksa tarayıcıda aç)
            file = self.remote.downloads.get(path[3:].split("/")[0], "")
            return self._file(file, attachment="dl" in urllib.parse.parse_qs(url.query))
        return self._static(path)

    do_HEAD = do_GET

    def _static(self, path: str):
        target = (WEB_DIR / urllib.parse.unquote(path).lstrip("/")).resolve()
        if WEB_DIR.resolve() not in target.parents or not target.is_file() or target.name == "auth.html":
            return self._send(404)
        mtime = int(target.stat().st_mtime)
        stamp = formatdate(mtime, usegmt=True)
        try:
            fresh = parsedate_to_datetime(self.headers["If-Modified-Since"]).timestamp() >= mtime
        except (KeyError, TypeError, ValueError):
            fresh = False
        if fresh:  # telefon dosyayı zaten biliyor: yeniden gönderilmez
            self.send_response(304)
            self.send_header("Last-Modified", stamp)
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            return None
        return self._send(200, target.read_bytes(), _ctype(target), {"Last-Modified": stamp}, cache="no-cache")

    def _file(self, path: str, attachment: bool = False):
        """Dosyayı gönderir; video ileri/geri sarılabilsin diye parça (Range) isteklerini de karşılar."""
        if not path or not os.path.isfile(path):
            return self._send(404)
        size = os.path.getsize(path)
        start, end = 0, size - 1
        rng = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", "").strip())
        partial = bool(rng and any(rng.groups()))
        if partial:
            a, b = rng.groups()
            if a:
                start, end = int(a), min(int(b), size - 1) if b else size - 1
            else:
                start = max(0, size - int(b))
            if start > end:
                return self._send(416, headers={"Content-Range": f"bytes */{size}"})
        self.send_response(206 if partial else 200)
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Type", _ctype(path))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Cache-Control", "no-store")
        name = urllib.parse.quote(os.path.basename(path))
        self.send_header("Content-Disposition", f"{'attachment' if attachment else 'inline'}; filename*=UTF-8''{name}")
        self.end_headers()
        if self.command == "HEAD":
            return None
        try:
            with open(path, "rb") as f:
                f.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = f.read(min(1 << 16, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (ConnectionError, OSError):
            self.close_connection = True
        return None

    # -- POST: API çağrıları ve dosya yükleme (bağlanma kodu gerekir)
    def do_POST(self):
        self._body_done = False
        if not self._local():
            return self._send(403)
        if not self._authorized():
            return self._send(401, b'{"error":"key"}', "application/json")
        url = urllib.parse.urlsplit(self.path)
        if url.path == "/upload":
            return self._upload(urllib.parse.parse_qs(url.query).get("name", [""])[0])
        if not url.path.startswith("/api/"):
            return self._send(404)
        length = int(self.headers.get("Content-Length") or 0)
        if length > 8 * 1024 * 1024:
            return self._send(413)
        raw = self.rfile.read(length) if length else b""
        self._body_done = True
        try:
            args = json.loads(raw or b"[]")
        except ValueError:
            return self._send(400)
        if not isinstance(args, list):
            return self._send(400)
        client = re.sub(r"[^A-Za-z0-9_-]", "", self.headers.get("X-TekTikla-Client", ""))[:40] or self.client_address[0]
        try:
            with i18n.using(self.headers.get("X-TekTikla-Lang", "")):  # cevaptaki metinler telefonun dilinde
                result = self.remote.call(url.path[5:], args, client, self.headers.get("User-Agent", "")[:200],
                                          self.client_address[0])
        except PermissionError:
            return self._send(403, b'{"error":"forbidden"}', "application/json")
        except Exception as e:  # noqa: BLE001 - hata telefona iletilir
            return self._send(500, json.dumps({"error": str(e)[:300]}).encode("utf-8"), "application/json")
        body = json.dumps(result, ensure_ascii=False, default=str)
        srv = getattr(self.remote.api, "_media_srv", None)
        if srv:  # önizleme adresleri (127.0.0.1) telefonda bu sunucunun /m/ yolundan açılır
            body = body.replace(f"http://127.0.0.1:{srv.httpd.server_address[1]}/", "/m/")
        return self._send(200, body.encode("utf-8"), "application/json; charset=utf-8")

    def _upload(self, name: str):
        """Telefondan gelen dosyayı (dönüştürme, Reels, dublaj, müzik, altyazı için) bilgisayara kaydeder."""
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_UPLOAD:
            return self._send(413 if length > 0 else 400)
        safe =re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", os.path.basename(name or "")).strip(" .")[:120] or "dosya"
        if safe.split(".")[0].upper() in RESERVED:  # Windows'ta CON, NUL… dosya adı olamaz
            safe = "_" + safe
        folder = UPLOAD_DIR / secrets.token_hex(6)
        dest, left = folder / safe, length
        try:
            folder.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                while left > 0:
                    chunk = self.rfile.read(min(1 << 20, left))
                    if not chunk:
                        break
                    f.write(chunk)
                    left -= len(chunk)
        except OSError:  # ör. disk doldu
            left = left or 1
        self._body_done = left == 0
        if left:
            shutil.rmtree(folder, ignore_errors=True)
            return self._send(400)
        self.remote.uploads.add(str(dest))
        return self._send(200, json.dumps({"path": str(dest)}).encode("utf-8"), "application/json")


class _Http(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False  # Windows'ta başka programın kullandığı kapıya da bağlanır; istemiyoruz

    def __init__(self, addr, remote: RemoteServer):
        self.remote = remote
        super().__init__(addr, _Handler)


class RemoteServer:
    def __init__(self, api, key: str):
        self.api, self.key = api, key
        self.downloads: dict[str, str] = {}  # rastgele anahtar → telefona indirilebilecek dosya
        self.uploads: set[str] = set()  # telefondan gelen dosyalar
        self.clients: dict[str, _Client] = {}
        self.fails: dict[str, list[float]] = {}
        self.cond = threading.Condition()
        self.stopping = False
        _clean_uploads()
        host = os.environ.get("TEKTIKLA_REMOTE_HOST", "0.0.0.0")  # testlerde yalnızca 127.0.0.1
        self.httpd = None
        for port in (*PORTS, 0):
            try:
                self.httpd = _Http((host, port), self)
                break
            except OSError:
                continue
        if self.httpd is None:
            raise OSError("Telefon bağlantısı başlatılamadı.")
        threading.Thread(target=self.httpd.serve_forever, daemon=True, name="telefon").start()

    @property
    def port(self) -> int:
        return self.httpd.server_address[1]

    def call(self, name: str, args: list, client: str, agent: str, ip: str):
        with self.cond:
            c = self.clients.get(client)
            if c is None:  # init ile açılan sayfa yeni durumu zaten alır; başka çağrıyla gelen sayfa eskide kalmıştır
                c = self.clients[client] = _Client(agent, ip, lost=name != "init")
            c.seen = time.monotonic()
            if name == "init":  # sayfa güncel durumu şimdi alıyor: öncesindeki olaylar eskidi
                c.events.clear()
                c.lost = False
        if name == "poll":
            return self.poll(c)
        if name == "remote_link":
            return self.link(*args[:2])
        if name == "remote_uploaded":
            paths = [p for p in (args[1] if len(args) > 1 and isinstance(args[1], list) else []) if p in self.uploads]
            return self.api._remote_uploaded(args[0] if args else "", paths)
        if name in REMOTE_CALLS:
            return getattr(self.api, REMOTE_CALLS[name])(*args)
        if name not in ALLOWED or (name == "set_setting" and (not args or args[0] in LOCKED_SETTINGS)):
            raise PermissionError(name)
        return getattr(self.api, name)(*args)

    def poll(self, c: _Client) -> dict:
        """Yeni olay yoksa bir süre bekler (uzun sorgu): telefon sürekli sormaz, olay olunca hemen alır."""
        with self.cond:
            if not c.events and not c.lost:
                self.cond.wait_for(lambda: c.events or c.lost or self.stopping, timeout=LONG_POLL)
            c.seen = time.monotonic()
            events, c.events = list(c.events), deque()
            fresh, c.lost = c.lost, False
        return {"events": events, "fresh": fresh}

    def broadcast(self, event: dict) -> None:
        with self.cond:
            now = time.monotonic()
            for cid, c in list(self.clients.items()):
                if now - c.seen > CLIENT_TTL:
                    del self.clients[cid]
                elif len(c.events) >= MAX_EVENTS:  # telefon çok uzun süre bakmadı: sayfayı yenilesin
                    c.events.clear()
                    c.lost = True
                else:
                    c.events.append(event)
            self.cond.notify_all()

    def link(self, kind: str, ref) -> str | None:
        """TekTıkla'nın indirdiği ya da ürettiği bir dosya için telefona özel, tahmin edilemez indirme adresi."""
        path = self.api._remote_file(kind, ref)
        if not path:
            return None
        token = secrets.token_urlsafe(16)
        self.downloads[token] = path
        return f"/f/{token}/{urllib.parse.quote(os.path.basename(path))}"

    def connected(self) -> list[dict]:
        """Son birkaç saniyede bağlı olan telefonlar (aynı cihazın yenilenen sayfası bir kez sayılır)."""
        now, seen, out = time.monotonic(), set(), []
        with self.cond:
            clients = sorted(self.clients.values(), key=lambda c: -c.seen)
        for c in clients:
            if now - c.seen < 45 and (c.ip, c.agent) not in seen:
                seen.add((c.ip, c.agent))
                out.append({"name": device_name(c.agent), "ip": c.ip})
        return out

    def stop(self) -> None:
        with self.cond:
            self.stopping = True
            self.cond.notify_all()
        self.httpd.shutdown()
        self.httpd.server_close()
