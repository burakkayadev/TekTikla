"""Arayüz (HTML/JS) ile Python arasındaki köprü; pywebview'e js_api olarak verilir.

JS tarafı metotları `pywebview.api.<ad>()` ile çağırır, olayları `poll()` ile toplar.
Durumun tamamı _ ile başlayan özniteliklerde tutulur ki pywebview onları JS'e açmasın.
"""
from __future__ import annotations

import base64
import ctypes
import io
import itertools
import os
import queue
import re
import subprocess
import threading
import time
import webbrowser
from ctypes import wintypes
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import requests
import webview
from PIL import Image

from . import APP_VERSION, GITHUB_REPO, ai, engine, llm, subtitles, tools, updater
from .config import DEFAULTS, History, Settings, decrypt_secret, encrypt_secret

URL_RE = re.compile(r"^https?://\S+$", re.I)
EXTERNAL_URLS = {
    "anthropic_keys": "https://console.anthropic.com/settings/keys",
    "gemini_keys": "https://aistudio.google.com/apikey",
    "anthropic_billing": "https://console.anthropic.com/settings/billing",
    "releases": f"https://github.com/{GITHUB_REPO}/releases" if GITHUB_REPO else "",
}
BOOL_KEYS = {k for k, v in DEFAULTS.items() if isinstance(v, bool)}
PRIVATE_KEYS = {"api_key_enc", "gemini_key_enc"}
KEY_SETTINGS = {"claude": ("api_key_enc", "ANTHROPIC_API_KEY"), "gemini": ("gemini_key_enc", "GEMINI_API_KEY")}
CHOICES = {"ai_provider": set(llm.PROVIDERS), "whisper_model": {"base", "small"},
           "ai_sub_lang": {c for c, _, _ in subtitles.LANGUAGES} | {"orig"},
           "theme": {"mono", "paper", "violet", "ocean"}}
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

class Api:
    def __init__(self):
        self._settings = Settings()
        self._history = History()
        self._events: queue.Queue = queue.Queue()
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

    # -- iç yardımcılar
    def _emit(self, event_type: str, /, **data) -> None:
        self._events.put({"type": event_type, **data})

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
        """Pencere açıldıktan sonra: bileşen kontrolü, pano izleme, güncelleme kontrolü."""
        if self._started:  # sayfa yeniden yüklenirse iş parçacıkları ikinci kez başlamasın
            return
        self._started = True
        self._check_setup(auto_install=True)
        self._bg(self._watch_clipboard)
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
        }

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
        if key not in DEFAULTS or key in PRIVATE_KEYS:
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
        except Exception:  # noqa: BLE001 - eski Windows'ta desteklenmeyebilir
            pass

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
                    return {"ok": False, "error": f"AI çeviri için Ayarlar > Yapay Zekâ bölümüne {name} anahtarı girin. "
                                                  "Sadece yazıya dökmek için dil olarak 'Orijinal dil'i seçin."}
            req.sub_mode = opts.get("sub_mode") if opts.get("sub_mode") in ("embed", "burn", "file") else "embed"
        return {"ok": True, "id": self._enqueue(req, thumb)}

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
                    item.job = engine.DownloadJob(item.req, dict(self._settings),
                                                  lambda k, it=item, **d: self._on_job(it, k, d))
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
            if item.error:
                self._emit("notify", kind="err", text=item.error.splitlines()[0])
            else:
                self._emit("notify", kind="ok", text=f"İndirildi: {item.req.title}")
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

    # -- AI özeti
    def ai_summary(self, url: str, token: int) -> bool:
        url = (url or "").strip()
        if not URL_RE.match(url):
            return False
        provider, key = self._provider(), self._api_key()

        def work():
            try:
                cached = self._media.get(url)
                info = cached[0].raw if cached and not cached[0].is_playlist else None
                result = ai.summarize(url, dict(self._settings), provider, key, info=info,
                                      on_stage=lambda s: self._emit("ai_stage", token=token, stage=s))
                thumb = cached[1] if cached else _thumb_data(result.get("thumbnail"))
                self._emit("ai_done", token=token, result={**result, "thumb": thumb})
            except ai.AIError as e:
                self._emit("ai_error", token=token, message=str(e))
            except Exception as e:  # noqa: BLE001
                self._emit("ai_error", token=token, message=engine.friendly_error(e))

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
