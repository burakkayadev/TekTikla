"""Arayüz (HTML/JS) ile Python arasındaki köprü; pywebview'e js_api olarak verilir.

JS tarafı metotları `pywebview.api.<ad>()` ile çağırır, olayları `poll()` ile toplar.
Durumun tamamı _ ile başlayan özniteliklerde tutulur ki pywebview onları JS'e açmasın.
"""
from __future__ import annotations

import base64
import ctypes
import io
import itertools
import json
import os
import queue
import re
import socket
import subprocess
import threading
import time
import webbrowser
from ctypes import wintypes
from dataclasses import asdict, replace
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
import webview
from PIL import Image

from . import APP_NAME, APP_TAGLINE, APP_VERSION, GITHUB_REPO, SUPPORT_DONATE, SUPPORT_GITHUB, WELCOME_URL, ai, engine, i18n, llm, media, qr, remote, subtitles, tools, updater, watchlist, account
from .studio_api import SERVICE_KEYS, SERVICE_URLS, StudioApi
from .config import APP_DIR, DEFAULTS, History, Settings, decrypt_secret, encrypt_secret

URL_RE = re.compile(r"^https?://\S+$", re.I)
EXTERNAL_URLS = {
    "anthropic_keys": "https://console.anthropic.com/settings/keys",
    "gemini_keys": "https://aistudio.google.com/apikey",
    "anthropic_billing": "https://console.anthropic.com/settings/billing",
    "releases": f"https://github.com/{GITHUB_REPO}/releases" if GITHUB_REPO else "",
    **SERVICE_URLS,
    "support_github": SUPPORT_GITHUB,
    "support_donate": SUPPORT_DONATE,
}
BOOL_KEYS = {k for k, v in DEFAULTS.items() if isinstance(v, bool)}
PRIVATE_KEYS = {"api_key_enc", "gemini_key_enc", "account_enc", "remote_key_enc", *SERVICE_KEYS.values()}
INTERNAL_KEYS = {"remote_enabled", "support_seen", "account_user", "account_skipped"}  # kendi metotlarıyla değişir
KEY_SETTINGS = {"claude": ("api_key_enc", "ANTHROPIC_API_KEY"), "gemini": ("gemini_key_enc", "GEMINI_API_KEY")}
CHOICES = {"ai_provider": set(llm.PROVIDERS), "whisper_model": {"base", "small"},
           "ai_sub_lang": {c for c, _, _ in subtitles.LANGUAGES} | {"orig"},
           "theme": {"mono", "paper", "violet", "ocean"}, "font": {"serif", "grotesk", "wide", "soft"},
           "sidebar": {"pinned", "auto"}}
THEME_BARS = {"mono": ("#050505", True), "paper": ("#F3F2EE", False), "violet": ("#0B0A12", True),
              "ocean": ("#04101A", True)}  # başlık çubuğu rengi, koyu mod
FINISHED = ("done", "error", "cancelled")


# ----------------------------------------------------------------------------- yardımcılar

def _thumb_data(url: str | None) -> str | None:
    """Kapak resmini veri URI'sine çevirir (bazı siteler doğrudan gömülen resmi engeller)."""
    if not url:
        return None
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        img.thumbnail((640, 360))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:  # noqa: BLE001 - kapak olmasa da olur
        return None


def _save_thumb(url: str, path: Path) -> bool:
    """Kapak resmini küçültüp dosyaya kaydeder (izleme listesi; YouTube dışı siteler)."""
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        img.thumbnail((480, 270))
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path, "JPEG", quality=85)
        return True
    except Exception:  # noqa: BLE001 - kapak olmasa da olur
        return False


def _safe_name(text: str, limit: int = 100) -> str:
    """Windows'ta dosya ya da klasör adı olarak kullanılabilir hale getirir."""
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", text or "").strip().rstrip(". ")[:limit].strip()


def _media_dict(info: engine.MediaInfo, thumb: str | None) -> dict:
    data = {k: v for k, v in info.__dict__.items() if k != "raw"}
    data["qualities"] = [asdict(q) for q in info.qualities]
    data["subtitles"] = [asdict(s) for s in info.subtitles]
    data["formats"] = [{"label": label, "spec": spec} for label, spec in info.formats]
    data["thumb"] = thumb
    data["duration_text"] = engine.human_time(info.duration)
    return data


class _Clipboard:
    """Panodaki metni Win32 API ile okur (tkinter gerektirmeden)."""

    def __init__(self):
        self.user32, self.kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        self.user32.OpenClipboard.argtypes = [wintypes.HWND]
        self.user32.GetClipboardData.restype = wintypes.HANDLE
        self.kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        self.kernel32.GlobalLock.restype = ctypes.c_void_p
        self.kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]

    def sequence(self) -> int:
        return self.user32.GetClipboardSequenceNumber()

    def text(self) -> str:
        if not self.user32.IsClipboardFormatAvailable(13) or not self.user32.OpenClipboard(None):
            return ""
        try:
            handle = self.user32.GetClipboardData(13)  # CF_UNICODETEXT
            ptr = self.kernel32.GlobalLock(handle) if handle else None
            if not ptr:
                return ""
            try:
                return ctypes.wstring_at(ptr)
            finally:
                self.kernel32.GlobalUnlock(handle)
        finally:
            self.user32.CloseClipboard()


class _Item:
    def __init__(self, item_id: str, req: engine.DownloadRequest, thumb: str | None):
        self.id = item_id
        self.req = req
        self.thumb = thumb
        self.job: engine.DownloadJob | None = None
        self.state = "pending"
        self.stage = "Sırada"
        self.frac: float | None = 0.0
        self.speed = self.eta = self.done_bytes = self.total_bytes = None
        self.files: list[str] = []
        self.error = ""
        self.last_emit = 0.0

    def summary(self) -> str:
        r = self.req
        if isinstance(r, media.StudioTask):
            return r.label
        if r.mode == "audio":
            parts = [f"{r.audio_format.upper()}" + ("" if r.audio_format in ("wav", "flac") else f" {r.audio_quality} kbps")]
        else:
            parts = [f"{r.height}p" if r.height else ("Özel format" if r.format_spec else "En iyi"), r.container.upper()]
        if r.sub_lang or r.external_sub:
            parts.append("altyazılı")
        if r.trim:
            parts.append(f"kesit {engine.human_time(r.trim[0])}–{engine.human_time(r.trim[1])}")
        if r.playlist:
            parts.append("liste")
        return " · ".join(parts)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "title": self.req.title, "url": self.req.url, "thumb": self.thumb,
            "state": self.state, "stage": self.stage, "frac": self.frac, "summary": self.summary(),
            "speed": engine.human_size(self.speed) + "/s" if self.speed else "",
            "eta": engine.human_time(self.eta) if self.eta is not None else "",
            "size": (f"{engine.human_size(self.done_bytes)} / {engine.human_size(self.total_bytes)}"
                     if self.total_bytes else ""),
            "file": os.path.basename(self.files[-1]) if self.files else "",
            "error": self.error,
        }


# ----------------------------------------------------------------------------- köprü

class Api(StudioApi):
    def __init__(self):
        self._settings = Settings()
        i18n.load(self._settings.get("language") or "tr")
        self._studio_init()
        self._history = History()
        self._events: queue.Queue = queue.Queue()
        self._remote: remote.RemoteServer | None = None  # telefondan kullanım açıksa ev ağındaki sunucu
        self._remote_lock = threading.Lock()
        self._items: dict[str, _Item] = {}
        self._ids = itertools.count(1)
        self._lock = threading.RLock()
        self._media: dict[str, tuple[engine.MediaInfo, str | None]] = {}
        self._picked_subs: set[str] = set()
        self._window: webview.Window | None = None
        self._ready = threading.Event()
        self._setup_state = "checking"
        self._update: dict | None = None
        self._missing: list[str] = []
        self._started = False
        self._hwnd = 0
        self._thumb_files: set[str] = set()
        self._acct = self._account_load()  # oturum: yenileme anahtarı ve kısa ömürlü kimlik anahtarı
        self._acct_wait: str | None = None  # tarayıcıda Google/GitHub girişi bekleniyor
        self._auth_srv: account.BrowserSignIn | None = None
        self._wl = watchlist.Watchlist()
        self._wl_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="izleme")

    # -- iç yardımcılar
    def _emit(self, event_type: str, /, **data) -> None:
        event = {"type": event_type, **data}
        self._events.put(event)
        if self._remote:  # telefondan bağlı sayfalar da aynı olayları alır
            self._remote.broadcast(event)

    def _bg(self, fn, *args) -> None:
        threading.Thread(target=fn, args=args, daemon=True).start()

    def _public_settings(self) -> dict:
        return {k: v for k, v in self._settings.items() if k not in PRIVATE_KEYS}

    def _provider(self) -> str:
        return self._settings.get("ai_provider") if self._settings.get("ai_provider") in llm.PROVIDERS             else llm.DEFAULT_PROVIDER

    def _api_key(self, provider: str | None = None) -> str:
        setting, env = KEY_SETTINGS[provider or self._provider()]
        return decrypt_secret(self._settings.get(setting, "")) or os.environ.get(env, "")

    def _key_status(self) -> dict:
        return {p: bool(self._api_key(p)) for p in llm.PROVIDERS}

    def _attach(self, window: webview.Window) -> None:
        self._window = window

    def _start_background(self) -> None:
        """Sayfa her yüklendiğinde sürükle-bırak bağlanır; ilk açılışta bileşen kontrolü, pano izleme, güncelleme kontrolü."""
        try:  # F5 ile yenilenen sayfada eski dinleyiciler silinir, her yüklemede yeniden bağlanır
            self._wire_drop()
        except Exception:  # noqa: BLE001 - sürükle-bırak olmasa da dosya seçici çalışır
            pass
        if self._started:  # sayfa yeniden yüklenirse iş parçacıkları ikinci kez başlamasın
            return
        self._started = True
        self._check_setup(auto_install=True)
        self._bg(self._account_check)
        self._bg(self._watch_clipboard)
        if self._settings.get("remote_enabled"):
            self._bg(self._remote_start)
        for item in list(self._wl.items):  # kapanırken bilgisi gelmeyen izleme listesi öğeleri
            if item.get("status") in ("loading", "retry"):
                self._wl_fetch(item["id"])
        if GITHUB_REPO and self._settings.get("auto_update_check", True):
            self._bg(self._check_update, False)

    # -- başlangıç
    def init(self) -> dict:
        return {
            "version": APP_VERSION,
            "repo": GITHUB_REPO,
            "settings": self._public_settings(),
            "keys": self._key_status(),
            "providers": {k: v["name"] for k, v in llm.PROVIDERS.items()},
            "languages": [[c, n] for c, n, _ in subtitles.LANGUAGES],
            "setup": self._setup_state,
            "missing": self._missing,
            "items": [i.to_dict() for i in self._items.values()],
            "history": self._history.items[:300],
            "tools": self.tool_status(),
            "update": self._update,
            "studio": self.studio_init(),
            "lang": self._settings.get("language") or "",
            "system_lang": i18n.system_language(),
            "ui_languages": i18n.LANGUAGES,
            "i18n": i18n.table(i18n.current()),
            "rtl": i18n.current() in i18n.RTL,
            "support": self._settings.get("support_seen") != APP_VERSION,
            "watch": self.watch_list(),
            "account": self._account_state(),
        }

    def _window_title(self) -> str:
        return f"{APP_NAME} — {i18n.t(APP_TAGLINE)}"

    def set_language(self, code: str) -> dict:
        if code not in i18n.NAMES:
            return {"ok": False}
        self._settings["language"] = code
        self._settings.save()
        i18n.load(code)
        if self._window:
            self._window.set_title(self._window_title())
        return {"ok": True, "lang": code, "i18n": i18n.table(code), "rtl": code in i18n.RTL,
                "studio": self.studio_init()}

    def poll(self) -> list[dict]:
        events = []
        try:
            while len(events) < 500:
                events.append(self._events.get_nowait())
        except queue.Empty:
            pass
        return events

    # -- bileşenler (FFmpeg, Deno)
    def _check_setup(self, auto_install: bool) -> None:
        self._missing = tools.missing_components()
        if not self._missing:
            self._setup_state = "ready"
            self._ready.set()
            self._emit("setup", state="ready", tools=self.tool_status())
            self._schedule()
        elif auto_install:
            self.install_components()

    def install_components(self) -> bool:
        if self._setup_state == "installing":
            return False
        self._setup_state = "installing"
        self._emit("setup", state="installing", text="Bileşenler hazırlanıyor…", frac=0)

        def work():
            try:
                tools.install_components(
                    self._missing, lambda text, frac: self._emit("setup", state="installing", text=text, frac=frac))
                self._check_setup(auto_install=False)
            except Exception as e:  # noqa: BLE001
                self._setup_state = "failed"
                self._emit("setup", state="failed", text=f"Kurulum başarısız: {str(e)[:200]}")

        self._bg(work)
        return True

    def tool_status(self) -> dict:
        return {
            "ytdlp": engine.yt_dlp.version.__version__,
            "ffmpeg": bool(tools.find_ffmpeg()),
            "js": ", ".join(tools.js_runtimes()) or "",
        }

    # -- ayarlar
    def set_setting(self, key: str, value) -> dict:
        if key not in DEFAULTS or key in PRIVATE_KEYS or key in INTERNAL_KEYS:
            return self._public_settings()
        if key in BOOL_KEYS:
            value = bool(value)
        elif key == "max_parallel":
            value = max(1, min(4, int(value)))
        elif key in CHOICES:
            if value not in CHOICES[key]:
                return self._public_settings()
        else:
            value = str(value).strip()
        self._settings[key] = value
        self._settings.save()
        if key == "max_parallel":
            self._schedule()
        if key == "theme":
            self._paint_titlebar()
        return self._public_settings()

    def _paint_titlebar(self, window: webview.Window | None = None) -> None:
        """Windows 11 başlık çubuğunu seçili temanın rengine boyar (açık temada açık renk)."""
        color, dark = THEME_BARS.get(self._settings.get("theme"), THEME_BARS["mono"])
        try:
            if window is not None:  # pencere ilk açıldığında; sonraki çağrılar başka iş parçacığından gelir
                self._hwnd = window.native.Handle.ToInt64()
            hwnd = ctypes.c_void_p(self._hwnd)
            dwm = ctypes.windll.dwmapi
            dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(int(dark))), 4)  # koyu mod
            r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
            dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(ctypes.c_int(r | (g << 8) | (b << 16))), 4)
            self._set_window_icon(hwnd)
        except Exception:  # noqa: BLE001 - eski Windows'ta desteklenmeyebilir
            pass

    def _set_window_icon(self, hwnd: ctypes.c_void_p) -> None:
        """Pencere ve görev çubuğu simgesini temanın logosuyla değiştirir (assets/icons/<tema>.ico)."""
        icon = APP_DIR / "assets" / "icons" / f"{self._settings.get('theme', 'mono')}.ico"
        if not icon.exists():
            return
        user32 = ctypes.windll.user32
        user32.LoadImageW.restype = ctypes.c_void_p
        user32.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int,
                                      ctypes.c_uint]
        user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p]
        for which, metric in ((1, 11), (0, 49)):  # ICON_BIG / SM_CXICON, ICON_SMALL / SM_CXSMICON
            px = user32.GetSystemMetrics(metric)
            handle = user32.LoadImageW(None, str(icon), 1, px, px, 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
            if handle:
                user32.SendMessageW(hwnd, 0x80, which, handle)  # WM_SETICON

    def pick_folder(self) -> str | None:
        result = self._window.create_file_dialog(webview.FileDialog.FOLDER,
                                                 directory=self._settings["download_dir"])
        if result:
            path = os.path.normpath(result[0] if isinstance(result, (list, tuple)) else result)
            self.set_setting("download_dir", path)
            return path
        return None

    def pick_subtitle(self) -> str | None:
        result = self._window.create_file_dialog(
            webview.FileDialog.OPEN, file_types=("Altyazı dosyaları (*.srt;*.vtt;*.ass;*.ssa)", "Tüm dosyalar (*.*)"))
        if result:
            path = os.path.normpath(result[0] if isinstance(result, (list, tuple)) else result)
            self._picked_subs.add(path)
            return path
        return None

    def save_api_key(self, provider: str, key: str) -> dict:
        if provider not in KEY_SETTINGS:
            return {"ok": False, "error": "Bilinmeyen servis."}
        key = (key or "").strip()
        problem = llm.valid_key(provider, key)
        if problem:
            return {"ok": False, "error": problem}
        self._settings[KEY_SETTINGS[provider][0]] = encrypt_secret(key)
        self._settings.save()
        return {"ok": True, "keys": self._key_status()}

    def delete_api_key(self, provider: str) -> dict:
        if provider in KEY_SETTINGS:
            self._settings[KEY_SETTINGS[provider][0]] = ""
            self._settings.save()
        return self._key_status()

    def open_url(self, name: str) -> None:
        url = EXTERNAL_URLS.get(name)
        if url:
            webbrowser.open(url)

    # -- destek penceresi: ilk açılışta ve her yeni sürümde bir kez kendiliğinden açılır
    def support_info(self) -> dict:
        def label(key: str, url: str) -> str:
            path = url.split("://", 1)[-1].rstrip("/")
            return "@" + path.rsplit("/", 1)[-1] if key == "github" else path

        links = [("github", SUPPORT_GITHUB), ("donate", SUPPORT_DONATE)]
        return {"links": [{"id": key, "label": label(key, url), "qr": qr.data_uri(url, glyph="coffee" if key == "donate" else "tt")}
                          for key, url in links if url]}

    def support_seen(self) -> None:
        self._settings["support_seen"] = APP_VERSION
        self._settings.save()

    # -- hesap (tektikla/account.py): e-posta, Google, GitHub ile giriş; kayıt olmadan devam
    def _account_load(self) -> dict | None:
        raw = decrypt_secret(self._settings.get("account_enc") or "")
        try:
            data = json.loads(raw) if raw else None
        except ValueError:
            data = None
        return data if isinstance(data, dict) and data.get("refresh_token") else None

    def _account_state(self) -> dict:
        user = self._settings.get("account_user") or None
        return {"configured": account.configured(), "user": user if self._acct else None,
                "skipped": bool(self._settings.get("account_skipped")), "waiting": self._acct_wait}

    def _account_save(self, sess: dict | None, user: dict | None) -> dict:
        """Oturumu saklar (yalnızca yenileme anahtarı, şifreli) ya da sess None ise çıkış yapar."""
        self._acct = sess
        self._settings["account_enc"] = encrypt_secret(json.dumps(
            {"refresh_token": sess["refresh_token"], "provider": sess["provider"]})) if sess else ""
        self._settings["account_user"] = user or {}
        if sess:
            self._settings["account_skipped"] = False
        self._settings.save()
        state = self._account_state()
        self._emit("account", state=state)
        return state

    def _account_check(self) -> None:
        """Açılışta oturumu doğrular ve hesap bilgisini tazeler (ad ya da fotoğraf değişmiş olabilir)."""
        if not self._acct or not account.configured():
            return
        try:
            sess = account.fresh(self._acct)
            user = account.profile(sess["id_token"], sess.get("provider", ""))
        except account.AccountError as e:
            if e.code in account.EXPIRED:  # hesap silinmiş, şifre değişmiş…: çıkış yapılır
                self._account_save(None, None)
                self._emit("notify", kind="err", text=i18n.t(str(e)))
            return  # internet yoksa oturum olduğu gibi kalır
        self._account_save(sess, user)

    def _focus_window(self) -> None:
        try:
            self._window.restore()
            self._window.on_top = True  # tarayıcıdan dönünce pencere öne gelsin
            self._window.on_top = False
        except Exception:  # noqa: BLE001
            pass

    def account_state(self) -> dict:
        return self._account_state()

    def account_email(self, mode: str, email: str, password: str, name: str = "") -> dict:
        email = (email or "").strip()
        try:
            if mode == "signup":
                sess, user = account.sign_up(email, password or "", (name or "").strip()[:60])
            else:
                sess, user = account.sign_in(email, password or "")
        except account.AccountError as e:
            return {"ok": False, "error": i18n.t(str(e))}
        if mode == "signup":
            self._bg(self._send_welcome, sess)
        return {"ok": True, "state": self._account_save(sess, user)}

    def _send_welcome(self, sess: dict) -> None:
        """Yeni üyeye hoş geldin e-postası (server/welcome: anahtar orada doğrulanır, üye başına bir kez gider)."""
        if not WELCOME_URL:
            return
        try:
            requests.post(WELCOME_URL, json={"idToken": account.fresh(sess)["id_token"], "lang": i18n.current()},
                          timeout=30)
        except Exception:  # noqa: BLE001 - e-posta gitmese de hesap açıldı
            pass

    def account_provider(self, provider: str) -> dict:
        if provider not in ("google", "github"):
            return {"ok": False}
        if not account.configured():
            return {"ok": False, "error": i18n.t("Hesap sistemi henüz kurulmadı.")}
        if self._auth_srv is None:
            self._auth_srv = account.BrowserSignIn(Path(account.__file__).parent / "web" / "auth.html",
                                                   self._account_browser_done)
        self._acct_wait = provider
        webbrowser.open(self._auth_srv.start(provider))
        return {"ok": True, "state": self._account_state()}

    def _account_browser_done(self, data: dict) -> None:
        self._acct_wait = None
        try:
            sess, user = account.from_browser(data)
        except account.AccountError as e:
            self._emit("account", state=self._account_state())
            self._emit("account_error", message=i18n.t(str(e)))
            return
        self._account_save(sess, user)
        if data.get("isNewUser"):
            self._bg(self._send_welcome, sess)
        self._emit("notify", kind="ok", text=i18n.t("Hoş geldin, {name}!", name=user["name"]))
        self._focus_window()

    def account_cancel(self) -> dict:
        if self._auth_srv:
            self._auth_srv.cancel()
        self._acct_wait = None
        return self._account_state()

    def account_reset(self, email: str) -> dict:
        try:
            account.send_reset((email or "").strip())
        except account.AccountError as e:
            return {"ok": False, "error": i18n.t(str(e))}
        return {"ok": True}

    def account_verify(self) -> dict:
        if not self._acct:
            return {"ok": False}
        try:
            account.send_verify(self._acct)
        except account.AccountError as e:
            return {"ok": False, "error": i18n.t(str(e))}
        return {"ok": True}

    def account_signout(self) -> dict:
        return self._account_save(None, None)

    def account_delete(self) -> dict:
        """Hesabı Firebase'den kalıcı olarak siler (kişisel verilerin silinmesi hakkı)."""
        if not self._acct:
            return {"ok": False}
        try:
            account.delete(self._acct)
        except account.AccountError as e:
            return {"ok": False, "error": i18n.t(str(e))}
        return {"ok": True, "state": self._account_save(None, None)}

    def account_skip(self) -> dict:
        self._settings["account_skipped"] = True
        self._settings.save()
        return self._account_state()

    # -- izleme listesi: sonra izlenecekler (tektikla/watchlist.py); uygulama kapansa da kalır
    def _wl_view(self, item: dict) -> dict:
        view = {k: v for k, v in item.items() if k != "thumb_file"}
        if item.get("thumb_file"):
            view["thumb"] = self._media_urls([item["thumb_file"]]).get(item["thumb_file"]) or view.get("thumb")
        view["duration_text"] = engine.human_time(item["duration"]) if item.get("duration") else ""
        return view

    def _wl_changed(self) -> list[dict]:
        items = self.watch_list()
        self._emit("watch", items=items)
        return items

    def _wl_forget(self, item: dict) -> None:
        path = item.get("thumb_file")
        if path and Path(path).parent == watchlist.THUMB_DIR:
            Path(path).unlink(missing_ok=True)

    def _wl_fetch(self, item_id: str) -> None:
        """Başlık, kanal, süre ve kapağı arka planda doldurur; oynatma listesini videolarına açar."""
        def work():
            self._ready.wait()  # yt-dlp ve JavaScript çalışma ortamı hazır olmadan sitelere gidilmez
            item = self._wl.get(item_id)
            if not item:
                return
            try:
                info = engine.analyze(item["url"], dict(self._settings))
            except Exception as e:  # noqa: BLE001
                # yalnızca anlaşılır kısım; yt-dlp'nin teknik ayrıntısı satıra sığmaz
                message = engine.friendly_error(e).split("\n\n")[0]
                low = str(e).lower()
                if watchlist.is_youtube_private_list(item["url"]) and ("does not exist" in low or "sign in" in low):
                    # oturum yokken YouTube kişisel listeler için "liste yok" der
                    message = i18n.t("YouTube listene ulaşılamadı. YouTube'a giriş yaptığın tarayıcıyı Ayarlar > "
                                     "Tarayıcı çerezleri'nden seç (Firefox önerilir).")
                self._wl.update(item_id, status="error", error=message)
            else:
                if info.is_playlist:
                    self._wl.replace(item_id, [{"url": e["url"], "title": e["title"], "channel": e["channel"],
                                                "duration": e.get("seconds"), "thumb": e["thumb"], "site": info.site}
                                               for e in info.entries if e.get("available")])
                else:
                    fields = {"title": info.title, "channel": info.uploader, "duration": info.duration,
                              "site": info.site, "status": "ready", "error": None}
                    if not watchlist.youtube_id(item["url"]) and info.thumbnail:
                        path = watchlist.THUMB_DIR / f"{item_id}.jpg"
                        if _save_thumb(info.thumbnail, path):
                            fields["thumb_file"] = str(path)
                    self._wl.update(item_id, **fields)
            self._wl_changed()

        self._wl_pool.submit(work)

    def watch_list(self) -> list[dict]:
        return [self._wl_view(i) for i in self._wl.items]

    def watch_add(self, text: str, entries: list | None = None) -> dict:
        """Yapıştırılan linkleri ya da oynatma listesi kartında seçilen videoları (bilgileriyle) sona ekler."""
        added = dupes = 0
        if entries:
            for e in entries[:watchlist.LIMIT]:
                url = str(e.get("url") or "") if isinstance(e, dict) else ""
                if not url.startswith(("http://", "https://")):
                    continue
                thumb = str(e.get("thumb") or "")
                seconds = e.get("seconds")
                item = self._wl.add(url, title=e.get("title"), channel=e.get("channel"),
                                    duration=seconds if isinstance(seconds, (int, float)) else None,
                                    thumb=thumb if thumb.startswith("https://") else None,
                                    status="ready" if e.get("title") else "loading")
                if not item:
                    dupes += 1
                    continue
                added += 1
                if item["status"] == "loading":
                    self._wl_fetch(item["id"])
        else:
            for url in watchlist.links(text):
                item = self._wl.add(url)
                if item:
                    added += 1
                    self._wl_fetch(item["id"])
                else:
                    dupes += 1
        return {"added": added, "dupes": dupes, "items": self._wl_changed() if added else self.watch_list()}

    def watch_set(self, item_id: str, watched: bool) -> list[dict]:
        self._wl.update(item_id, watched=bool(watched))
        return self._wl_changed()

    def watch_move(self, item_id: str, index: int) -> list[dict]:
        self._wl.move(item_id, int(index))
        return self._wl_changed()

    def watch_remove(self, item_id: str) -> list[dict]:
        item = self._wl.remove(item_id)
        if item:
            self._wl_forget(item)
        return self._wl_changed()

    def watch_clear(self) -> list[dict]:
        for item in self._wl.clear_watched():
            self._wl_forget(item)
        return self._wl_changed()

    def watch_retry(self, item_id: str) -> list[dict]:
        if self._wl.update(item_id, status="loading", error=None):
            self._wl_fetch(item_id)
        return self._wl_changed()

    def watch_open(self, item_id: str) -> bool:
        item = self._wl.get(item_id)
        if not item or not item["url"].startswith(("http://", "https://")):
            return False
        webbrowser.open(item["url"])
        return True

    # -- telefondan kullanım (tektikla/remote.py): aynı Wi-Fi'deki telefon QR kodu okutup bağlanır
    def _remote_key(self) -> str:
        key = decrypt_secret(self._settings.get("remote_key_enc") or "")
        if not key:
            key = remote.new_key()
            self._settings["remote_key_enc"] = encrypt_secret(key)
            self._settings.save()
        return key

    def _remote_start(self) -> bool:
        with self._remote_lock:
            if not self._remote:
                try:
                    self._remote = remote.RemoteServer(self, self._remote_key())
                except OSError:
                    return False
        return True

    def _remote_stop(self) -> None:
        with self._remote_lock:
            srv, self._remote = self._remote, None
        if srv:
            srv.stop()

    def remote_info(self) -> dict:
        """Masaüstündeki "Telefondan kullan" penceresi: QR kod, adres, bağlanma kodu, bağlı telefonlar."""
        srv = self._remote
        if not srv:
            return {"on": False}
        host = srv.httpd.server_address[0]  # testte yalnızca 127.0.0.1'e bağlanır
        urls = [f"http://{ip}:{srv.port}" for ip in (remote.lan_ips() if host == "0.0.0.0" else [host])]
        if not urls:
            return {"on": True, "offline": True}
        return {"on": True, "url": urls[0], "others": urls[1:4], "code": f"{srv.key[:5]}-{srv.key[5:]}",
                "qr": qr.data_uri(f"{urls[0]}/#k={srv.key}"), "devices": srv.connected(), "apk": self._apk_qr()}

    def _apk_qr(self) -> str:
        """Android uygulamasının (GitHub'daki son sürüm) indirme bağlantısının QR kodu."""
        if not GITHUB_REPO:
            return ""
        if not getattr(self, "_apk_qr_cache", ""):
            self._apk_qr_cache = qr.data_uri(f"https://github.com/{GITHUB_REPO}/releases/latest/download/TekTikla-Android.apk")
        return self._apk_qr_cache

    def remote_set(self, on: bool) -> dict:
        if on and not self._remote_start():
            return {"on": False, "error": i18n.t("Telefon bağlantısı başlatılamadı.")}
        if not on:
            self._remote_stop()
        self._settings["remote_enabled"] = bool(on)
        self._settings.save()
        return self.remote_info()

    def remote_reset(self) -> dict:
        """Yeni bağlanma kodu: eski kodla bağlanan telefonlar QR kodu yeniden okutmalı."""
        key = remote.new_key()
        self._settings["remote_key_enc"] = encrypt_secret(key)
        self._settings.save()
        srv = self._remote
        if srv:
            srv.key = key
            srv.downloads.clear()
            with srv.cond:
                srv.clients.clear()
        return self.remote_info()

    def _remote_hello(self) -> dict:
        return {"ok": True, "pc": socket.gethostname()}

    def _remote_urls(self) -> dict:
        return {k: v for k, v in EXTERNAL_URLS.items() if v}

    def _remote_i18n(self, code: str) -> dict:
        """Telefonun kendi dili; bilgisayardaki uygulamanın dili değişmez."""
        if code not in i18n.NAMES:
            return {"ok": False}
        with i18n.using(code):
            return {"ok": True, "lang": code, "i18n": i18n.table(code), "rtl": code in i18n.RTL,
                    "studio": self.studio_init()}

    def _remote_file(self, kind: str, ref) -> str | None:
        """Telefona indirilebilecek dosya: yalnızca TekTıkla'nın indirdiği ya da ürettiği dosyalar."""
        path = ""
        if kind == "item":
            item = self._items.get(str(ref))
            path = item.files[-1] if item and item.files else ""
        elif kind == "history" and isinstance(ref, int) and 0 <= ref < len(self._history.items):
            path = self._history.items[ref].get("path", "")
        elif kind == "made" and ref in self._made_files:
            path = ref
        elif kind == "file" and ref in self._thumb_files:
            path = ref
        return path if path and os.path.isfile(path) else None

    def _remote_uploaded(self, kind: str, paths: list[str]):
        """Telefondan yüklenen dosyalar, masaüstünde dosya seçilmiş gibi kullanılır."""
        if kind == "convert":
            items = self._convert_add(paths)
            return {"items": items, "skipped": len(paths) - len(items)}
        if not paths:
            return None
        if kind == "subtitle":
            self._picked_subs.add(paths[0])
        elif kind in ("video", "audio", "image"):
            self._picked_media.add(paths[0])
        else:
            return None
        return paths[0]

    # -- analiz
    def analyze(self, url: str, token: int) -> bool:
        url = (url or "").strip()
        if not URL_RE.match(url):
            return False

        def work():
            if not self._ready.is_set():
                self._emit("analyze_wait", token=token)
                self._ready.wait()
            try:
                info = engine.analyze(url, dict(self._settings))
                thumb = _thumb_data(info.thumbnail)
                self._media[url] = (info, thumb)
                self._media[info.url] = (info, thumb)
                self._emit("analyzed", token=token, info=_media_dict(info, thumb), url=url)
            except Exception as e:  # noqa: BLE001
                self._emit("analyze_error", token=token, message=engine.friendly_error(e))

        self._bg(work)
        return True

    # -- indirme
    def _base_request(self, url: str, title: str) -> engine.DownloadRequest:
        s = self._settings
        return engine.DownloadRequest(
            url=url, title=title, out_dir=s["download_dir"], container=s["container"],
            audio_format=s["audio_format"], audio_quality=s["audio_quality"],
            embed_thumbnail=s["embed_thumbnail"], embed_metadata=s["embed_metadata"],
            sponsorblock=s["sponsorblock"],
        )

    def download(self, opts: dict) -> dict:
        source = opts.get("source_url", "")
        cached = self._media.get(source)
        if not cached:
            return {"ok": False, "error": "Önce linki analiz edin."}
        info, thumb = cached
        req = self._base_request(info.url, info.title)
        req.playlist = bool(opts.get("playlist")) or info.is_playlist
        if req.playlist and not info.is_playlist:
            req.url = source  # liste parametresi orijinal linkte

        try:
            start = engine.parse_timestamp(opts.get("trim_start") or "") if opts.get("trim") else None
            end = engine.parse_timestamp(opts.get("trim_end") or "") if opts.get("trim") else None
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        if opts.get("trim"):
            start = start or 0
            end = end if end is not None else info.duration
            if not end or end <= start:
                return {"ok": False, "error": "Bitiş zamanı başlangıçtan büyük olmalı."}
            req.trim = (start, end)

        if opts.get("mode") == "audio":
            req.mode = "audio"
            req.audio_format = opts.get("audio_format") if opts.get("audio_format") in engine.AUDIO_FORMATS else "mp3"
            req.audio_quality = opts.get("audio_quality") if opts.get("audio_quality") in engine.AUDIO_QUALITIES else "320"
        else:
            req.container = opts.get("container") if opts.get("container") in engine.CONTAINERS else "mp4"
            specs = {f[1] for f in info.formats}
            if opts.get("format_spec") in specs:
                req.format_spec = opts["format_spec"]
            else:
                heights = {q.height for q in info.qualities}
                req.height = opts.get("height") if opts.get("height") in heights else None
            idx = opts.get("sub_index")
            if isinstance(idx, int) and 0 <= idx < len(info.subtitles):
                req.sub_lang, req.sub_auto = info.subtitles[idx].lang, info.subtitles[idx].auto
            ext = opts.get("external_sub")
            req.external_sub = ext if ext in self._picked_subs else None
            ai_sub = opts.get("ai_sub")
            if ai_sub in CHOICES["ai_sub_lang"]:
                req.ai_sub, req.sub_lang, req.external_sub = ai_sub, None, None  # AI altyazı diğerlerinin yerine
                req.ai_provider, req.ai_key = self._provider(), self._api_key()
                req.whisper_model = self._settings.get("whisper_model", "small")
                if ai_sub != "orig" and not req.ai_key:
                    name = llm.PROVIDERS[req.ai_provider]["name"]
                    return {"ok": False, "error": i18n.t("AI çeviri için Ayarlar > Yapay Zekâ bölümüne {name} anahtarı girin. Sadece yazıya dökmek için dil olarak 'Orijinal dil'i seçin.", name=name)}
            req.sub_mode = opts.get("sub_mode") if opts.get("sub_mode") in ("embed", "burn", "file") else "embed"
        if info.is_playlist:
            return self._enqueue_playlist(info, req, opts.get("items"))
        return {"ok": True, "id": self._enqueue(req, thumb)}

    def _enqueue_playlist(self, info: engine.MediaInfo, req: engine.DownloadRequest, picked) -> dict:
        """Listeden seçilen (ya da tüm) videoları ayrı ayrı sıraya koyar; her biri kendi ilerlemesini gösterir."""
        if isinstance(picked, list):
            wanted = {i for i in picked if isinstance(i, int)}
            chosen = [e for e in info.entries if e["index"] in wanted]
        else:
            chosen = [e for e in info.entries if e["available"]]
        if not chosen:
            return {"ok": False, "error": "En az bir video seçin."}
        folder = Path(req.out_dir) / (_safe_name(info.title) or "Oynatma listesi")
        width = max(2, len(str(chosen[-1]["index"])))
        ids = [self._enqueue(replace(req, url=e["url"], title=e["title"] or e["url"], out_dir=str(folder),
                                     playlist=False, trim=None, external_sub=None,
                                     name_prefix=f"{e['index']:0{width}d} - "),
                             e["thumb"])
               for e in chosen]
        return {"ok": True, "id": ids[0], "count": len(ids)}

    def quick(self, url: str, mode: str) -> dict:
        url = (url or "").strip()
        if not URL_RE.match(url):
            return {"ok": False, "error": "Geçerli bir link girin."}
        cached = self._media.get(url)
        req = self._base_request(url, cached[0].title if cached else url)
        if mode == "audio":
            req.mode = "audio"
        return {"ok": True, "id": self._enqueue(req, cached[1] if cached else None)}

    def _enqueue(self, req: engine.DownloadRequest, thumb: str | None) -> str:
        Path(req.out_dir).mkdir(parents=True, exist_ok=True)
        item = _Item(str(next(self._ids)), req, thumb)
        with self._lock:
            self._items[item.id] = item
        self._emit("item", item=item.to_dict())
        self._schedule()
        return item.id

    def _schedule(self) -> None:
        if not self._ready.is_set():
            return
        with self._lock:
            running = sum(1 for i in self._items.values() if i.state == "running")
            for item in self._items.values():
                if running >= int(self._settings["max_parallel"]):
                    break
                if item.state == "pending":
                    item.state, item.stage, item.frac = "running", "Başlıyor…", None
                    callback = (lambda k, it=item, **d: self._on_job(it, k, d))
                    if isinstance(item.req, media.StudioTask):
                        item.job = item.req.make_job(self._studio_settings(), callback)
                    else:
                        item.job = engine.DownloadJob(item.req, dict(self._settings), callback)
                    self._bg(item.job.run)
                    self._emit("item", item=item.to_dict())
                    running += 1

    def _on_job(self, item: _Item, kind: str, data: dict) -> None:
        if kind == "progress":
            stage_changed = data.get("stage") != item.stage
            if data.get("title") and item.req.title.startswith("http"):
                item.req.title = data["title"]
            item.stage = data.get("stage", item.stage)
            item.frac = data.get("frac")
            item.speed, item.eta = data.get("speed"), data.get("eta")
            item.done_bytes, item.total_bytes = data.get("done_bytes"), data.get("total_bytes")
            now = time.monotonic()
            if not stage_changed and now - item.last_emit < 0.15:
                return
            item.last_emit = now
        elif kind == "done":
            item.state, item.stage, item.frac = "done", "Tamamlandı", 1
            item.files = [f for f in data.get("files", []) if f]
            self._history.add({
                "title": item.req.title, "url": item.req.url, "kind": item.summary(),
                "path": item.files[-1] if item.files else item.req.out_dir,
                "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            })
            self._emit("history", history=self._history.items[:300])
            item.error = data.get("warning", "")  # ör. video indi ama AI altyazı eklenemedi
            if isinstance(item.req, media.StudioTask):
                # uyarı olsa da üretilen dosyalar kullanılabilir (ör. beş resimden biri bozuktu)
                self._made_files.update(item.files)
                self._emit("notify", kind="err" if item.error else "ok",
                           text=item.error.splitlines()[0] if item.error else item.req.done_text)
                self._emit("studio_done", kind=item.req.kind, id=item.id, files=item.files,
                           urls=self._media_urls(item.files))
            elif item.error:
                self._emit("notify", kind="err", text=item.error.splitlines()[0])
            else:
                self._emit("notify", kind="ok", text=i18n.t("İndirildi: {title}", title=item.req.title))
        else:
            item.state = kind
            item.stage = "Hata" if kind == "error" else "İptal edildi"
            item.error = data.get("message", "")
            item.frac = 0
        self._emit("item", item=item.to_dict())
        if kind != "progress":
            self._schedule()

    def cancel(self, item_id: str) -> None:
        item = self._items.get(item_id)
        if not item:
            return
        if item.state == "running" and item.job:
            item.job.cancel()
            item.stage = "İptal ediliyor…"
            self._emit("item", item=item.to_dict())
        elif item.state == "pending":
            self._on_job(item, "cancelled", {})

    def retry(self, item_id: str) -> None:
        item = self._items.get(item_id)
        if item and item.state in ("error", "cancelled"):
            self.remove(item_id)
            self._enqueue(item.req, item.thumb)

    def remove(self, item_id: str) -> None:
        with self._lock:
            item = self._items.get(item_id)
            if item and item.state in FINISHED:
                del self._items[item_id]
                self._emit("removed", id=item_id)

    def clear_finished(self) -> None:
        for item_id in [i.id for i in self._items.values() if i.state in FINISHED]:
            self.remove(item_id)

    def cancel_all(self) -> int:
        running = [i for i in self._items.values() if i.state in ("running", "pending")]
        for item in running:
            self.cancel(item.id)
        return len(running)

    def running_count(self) -> int:
        return sum(1 for i in self._items.values() if i.state in ("running", "pending"))

    # -- dosya açma (yalnızca TekTıkla'nın indirdiği dosyalar)
    def open_item(self, item_id: str) -> None:
        item = self._items.get(item_id)
        if item and item.files and os.path.exists(item.files[-1]):
            os.startfile(item.files[-1])

    def reveal_item(self, item_id: str) -> None:
        item = self._items.get(item_id)
        if item:
            self._reveal(item.files[-1] if item.files else item.req.out_dir)

    def open_history(self, index: int) -> None:
        if 0 <= index < len(self._history.items):
            path = self._history.items[index].get("path", "")
            if os.path.isfile(path):
                os.startfile(path)

    def reveal_history(self, index: int) -> None:
        if 0 <= index < len(self._history.items):
            self._reveal(self._history.items[index].get("path", ""))

    def open_download_dir(self) -> None:
        path = self._settings["download_dir"]
        Path(path).mkdir(parents=True, exist_ok=True)
        os.startfile(path)

    @staticmethod
    def _reveal(path: str) -> None:
        if os.path.isfile(path):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        elif os.path.isdir(path):
            os.startfile(path)
        elif os.path.isdir(os.path.dirname(path)):
            os.startfile(os.path.dirname(path))

    def clear_history(self) -> list:
        self._history.clear()
        return []

    # -- yapay zekâ: video özeti, yorum özeti, video fikirleri
    def ai_run(self, mode: str, text: str, token: int) -> bool:
        text = (text or "").strip()
        is_url = bool(URL_RE.match(text))
        if mode not in ("summary", "comments", "ideas") or not text or (mode != "ideas" and not is_url):
            return False
        provider, key = self._provider(), self._api_key()
        settings = dict(self._settings)
        stage = lambda s: self._emit("ai_stage", token=token, stage=s)  # noqa: E731

        def work():
            try:
                cached = self._media.get(text) if is_url else None
                info = cached[0].raw if cached and not cached[0].is_playlist else None
                if mode == "summary":
                    result = ai.summarize(text, settings, provider, key, info=info, on_stage=stage)
                elif mode == "comments":
                    result = ai.summarize_comments(text, settings, provider, key, on_stage=stage)
                else:
                    result = ai.video_ideas(text, settings, provider, key, info=info, on_stage=stage)
                thumb = cached[1] if cached else _thumb_data(result.get("thumbnail"))
                self._emit("ai_done", token=token, result={**result, "thumb": thumb, "mode": mode})
            except ai.AIError as e:
                self._emit("ai_error", token=token, message=str(e))
            except Exception as e:  # noqa: BLE001
                self._emit("ai_error", token=token, message=engine.friendly_error(e))

        self._bg(work)
        return True

    # -- kapak fotoğrafı
    def download_thumbnail(self, source_url: str) -> dict:
        cached = self._media.get(source_url)
        if not cached:
            return {"ok": False, "error": "Önce linki analiz edin."}
        info = cached[0]
        thumbs = [t for t in (info.raw or {}).get("thumbnails") or [] if t.get("url")]
        best = max(thumbs, key=lambda t: ((t.get("width") or 0) * (t.get("height") or 0), t.get("preference") or 0),
                   default=None)
        url = best["url"] if best else info.thumbnail
        if not url:
            return {"ok": False, "error": "Bu videonun kapak fotoğrafı yok."}
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
        except Exception:  # noqa: BLE001
            return {"ok": False, "error": "Kapak fotoğrafı indirilemedi."}
        out_dir = Path(self._settings["download_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        name = _safe_name(info.title, 150) or "kapak"
        path = out_dir / f"{name} (kapak).jpg"
        img.save(path, "JPEG", quality=95)
        self._thumb_files.add(str(path))
        return {"ok": True, "path": str(path), "size": f"{img.width}×{img.height}"}

    def reveal_file(self, path: str) -> None:
        if path in self._thumb_files:  # yalnızca TekTıkla'nın kaydettiği dosyalar
            self._reveal(path)

    # -- benzer videolar
    def similar(self, source_url: str, token: int) -> bool:
        cached = self._media.get(source_url)
        if not cached:
            return False
        info = cached[0]
        query = re.sub(r"#\S+|[|•–—\-_:()\[\]]+", " ", info.title)
        query = " ".join(query.split()[:10]) or info.title
        settings = dict(self._settings)

        def work():
            try:
                opts = engine.base_opts(settings) | {"skip_download": True, "extract_flat": "in_playlist"}
                with engine.yt_dlp.YoutubeDL(opts) as ydl:
                    result = ydl.extract_info(f"ytsearch13:{query}", download=False)
                items = []
                for e in result.get("entries") or []:
                    if not e.get("url") or e.get("id") == (info.raw or {}).get("id"):
                        continue
                    thumbs = e.get("thumbnails") or []
                    items.append({
                        "url": e["url"], "title": e.get("title") or "",
                        "channel": (e.get("channel") or e.get("uploader") or "").split("•")[0].strip()[:60],
                        "duration": engine.human_time(e.get("duration")),
                        "thumb": thumbs[-1]["url"] if thumbs else None,
                    })
                items = items[:12]
                with ThreadPoolExecutor(6) as pool:  # kapakları veri URI'sine çevir (siteler doğrudan gömmeyi engelleyebilir)
                    for it, data in zip(items, pool.map(_thumb_data, [it["thumb"] for it in items])):
                        it["thumb"] = data
                self._emit("similar", token=token, items=items)
            except Exception as e:  # noqa: BLE001
                self._emit("similar", token=token, items=[], error=engine.friendly_error(e))

        self._bg(work)
        return True

    # -- güncellemeler
    def update_ytdlp(self) -> None:
        def work():
            try:
                msg = tools.update_ytdlp()
                if "Successfully" in msg:
                    msg = msg.replace("Successfully installed", "Güncellendi:") + " — etkin olması için TekTıkla'yı yeniden açın."
            except Exception as e:  # noqa: BLE001
                msg = f"Güncellenemedi: {str(e)[:200]}"
            self._emit("ytdlp", message=msg)

        self._bg(work)

    def _check_update(self, manual: bool) -> None:
        try:
            self._update = updater.check()
            self._emit("app_update", update=self._update, manual=manual)
        except Exception as e:  # noqa: BLE001
            if manual:
                self._emit("app_update", update=None, manual=True, error=str(e)[:200])

    def check_update(self) -> None:
        self._bg(self._check_update, True)

    def install_update(self) -> None:
        if not self._update:
            return

        def work():
            try:
                updater.apply(self._update, lambda f: self._emit("update_progress", frac=f))
                self.cancel_all()
                time.sleep(1)
                self._window.destroy()
            except updater.UpdateError as e:
                self._emit("update_progress", error=str(e), page=True)
            except Exception as e:  # noqa: BLE001
                self._emit("update_progress", error=f"Güncelleme başarısız: {str(e)[:200]}", page=True)

        self._bg(work)

    # -- pano izleme
    def _watch_clipboard(self) -> None:
        clip = _Clipboard()
        last_seq = clip.sequence()
        last_text = ""
        while True:
            time.sleep(0.8)
            seq = clip.sequence()
            if seq == last_seq:
                continue
            last_seq = seq
            if not self._settings.get("clipboard_watch"):
                continue
            try:
                text = clip.text().strip()
            except OSError:
                continue
            if text != last_text and URL_RE.match(text):
                last_text = text
                self._emit("clipboard", url=text)
