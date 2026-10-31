"""Ayarlar ve indirme geçmişi (JSON olarak %APPDATA%\\TekTikla altında saklanır)."""
from __future__ import annotations

import base64
import ctypes
import json
import os
import shutil
import sys
import threading
from ctypes import wintypes
from pathlib import Path

# TekTikla.exe olarak çalışırken kaynaklar geçici _MEIPASS klasöründe ve salt okunurdur;
# indirilen araçlar (FFmpeg, yt-dlp güncellemesi) bu yüzden %LOCALAPPDATA%\TekTikla altına yazılır.
FROZEN = getattr(sys, "frozen", False)
APP_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "TekTikla"
LOCAL_DIR = Path(os.environ.get("LOCALAPPDATA", DATA_DIR)) / "TekTikla"
BIN_DIR = LOCAL_DIR / "bin" if FROZEN else APP_DIR / "bin"
LIB_DIR = LOCAL_DIR / "lib"  # exe için güncellenmiş yt-dlp
SETTINGS_FILE = DATA_DIR / "settings.json"
HISTORY_FILE = DATA_DIR / "history.json"
OLD_DATA_DIR = DATA_DIR.with_name("BIM")  # uygulamanın eski adı "BİM" iken kullanılan klasör
OLD_DEFAULT_DOWNLOADS = str(Path.home() / "Downloads" / "BİM")

DEFAULTS = {
    "download_dir": str(Path.home() / "Downloads" / "TekTıkla"),
    "font": "grotesk",  # başlık yazı tipi: "serif" (Instrument Serif) | "grotesk" (Bricolage Grotesque)
    "theme": "mono",  # "mono" (Siyah) | "paper" (Kâğıt) | "violet" (Mor) | "ocean" (Okyanus)
    "clipboard_watch": True,
    "max_parallel": 2,
    "container": "mp4",
    "audio_format": "mp3",
    "audio_quality": "320",
    "embed_thumbnail": True,
    "embed_metadata": True,
    "sponsorblock": False,
    "cookies_browser": "Yok",
    "rate_limit": "",
    "sub_lang_pref": "tr",
    "api_key_enc": "",  # Anthropic API anahtarı, Windows DPAPI ile şifreli (base64)
    "gemini_key_enc": "",  # Google Gemini API anahtarı, aynı şekilde şifreli
    "ai_provider": "gemini",  # "gemini" (ücretsiz anahtar) | "claude"
    "ai_sub_lang": "tr",  # AI altyazı için son seçilen dil
    "whisper_model": "small",  # konuşma tanıma: "base" (hızlı) | "small" (daha doğru)
    "auto_update_check": True,
}

_lock = threading.Lock()


# ----------------------------------------------------------------------------- DPAPI
# Anahtar sadece bu Windows kullanıcısının çözebileceği şekilde şifrelenir; dosya
# başka bir bilgisayara/kullanıcıya kopyalansa da okunamaz.
class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(data: bytes, protect: bool) -> bytes:
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    buf = ctypes.create_string_buffer(data, len(data))
    src = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = _Blob()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    fn.argtypes = [ctypes.POINTER(_Blob), ctypes.c_wchar_p if protect else ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
    fn.restype = wintypes.BOOL
    if not fn(ctypes.byref(src), "TekTikla" if protect else None, None, None, None, 0x1, ctypes.byref(out)):
        raise OSError("DPAPI işlemi başarısız")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


def encrypt_secret(text: str) -> str:
    return base64.b64encode(_dpapi(text.encode("utf-8"), True)).decode("ascii") if text else ""


def decrypt_secret(token: str) -> str:
    if not token:
        return ""
    try:
        return _dpapi(base64.b64decode(token), False).decode("utf-8")
    except (OSError, ValueError):
        return ""


def _read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(path: Path, data) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _migrate_old_data() -> None:
    """Eski "BİM" sürümünün ayarlarını ve geçmişini bir kez yeni klasöre kopyalar."""
    if DATA_DIR.exists() or not OLD_DATA_DIR.is_dir():
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name in (SETTINGS_FILE.name, HISTORY_FILE.name):
        if (OLD_DATA_DIR / name).exists():
            shutil.copy2(OLD_DATA_DIR / name, DATA_DIR / name)


class Settings(dict):
    def __init__(self):
        super().__init__(DEFAULTS)
        _migrate_old_data()
        stored = _read(SETTINGS_FILE, {})
        if isinstance(stored, dict):
            self.update({k: v for k, v in stored.items() if k in DEFAULTS})
        if self["download_dir"] == OLD_DEFAULT_DOWNLOADS:
            self["download_dir"] = DEFAULTS["download_dir"]
        # v2.3 öncesi tema adları: koyu/sistem → Siyah, açık → Kâğıt
        self["theme"] = {"dark": "mono", "system": "mono", "light": "paper"}.get(self["theme"], self["theme"])

    def save(self) -> None:
        with _lock:
            _write(SETTINGS_FILE, dict(self))


class History:
    LIMIT = 500

    def __init__(self):
        data = _read(HISTORY_FILE, [])
        self.items: list[dict] = data if isinstance(data, list) else []

    def add(self, item: dict) -> None:
        with _lock:
            self.items.insert(0, item)
            del self.items[self.LIMIT:]
            _write(HISTORY_FILE, self.items)

    def clear(self) -> None:
        with _lock:
            self.items.clear()
            _write(HISTORY_FILE, self.items)
