"""Arayüz dili. Kaynak dil Türkçedir: çeviri tabloları Türkçe metni anahtar olarak kullanır
(web/i18n/<kod>.json). Tabloda olmayan metin Türkçe görünür. Sayı içeren metinler "{0}" kalıbıyla eşleşir.
"""
from __future__ import annotations

import ctypes
import json
import re
import threading
from contextlib import contextmanager
from pathlib import Path

from .config import APP_DIR

LANGUAGES = [  # (kod, kendi dilindeki adı)
    ("tr", "Türkçe"), ("en", "English"), ("es", "Español"), ("pt", "Português"), ("fr", "Français"),
    ("de", "Deutsch"), ("ru", "Русский"), ("ar", "العربية"), ("hi", "हिन्दी"), ("id", "Bahasa Indonesia"),
    ("zh", "中文"), ("ja", "日本語"), ("ko", "한국어"),
]
NAMES = dict(LANGUAGES)
RTL = {"ar"}
I18N_DIR = APP_DIR / "tektikla" / "web" / "i18n" if (APP_DIR / "tektikla" / "web").exists() \
    else Path(__file__).parent / "web" / "i18n"

_current = "tr"
_table: dict[str, str] = {}
_NUM = re.compile(r"\d+(?:[.,]\d+)?")
_local = threading.local()  # telefondan gelen istek kendi dilinde cevaplanır (tektikla/remote.py)
_cache: dict[str, dict[str, str]] = {}


def table(code: str) -> dict[str, str]:
    if code == "tr":
        return {}
    try:
        return json.loads((I18N_DIR / f"{code}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load(code: str) -> None:
    global _current, _table
    _current = code if code in NAMES else "tr"
    _table = table(_current)


def current() -> str:
    return _current


def language_name(code: str) -> str:
    return NAMES.get(code, code)


@contextmanager
def using(code: str):
    """Bu iş parçacığında t() geçici olarak başka dile çevirir (uygulamanın dili değişmez)."""
    if code not in NAMES:
        yield
        return
    if code not in _cache:
        _cache[code] = table(code)
    prev = getattr(_local, "table", None)
    _local.table = _cache[code]
    try:
        yield
    finally:
        _local.table = prev


def t(text: str, **kw) -> str:
    """Metni geçerli dile çevirir; {ad} yer tutucularını doldurur."""
    tab = getattr(_local, "table", None)
    tab = _table if tab is None else tab
    out = tab.get(text)
    if out is None and tab and _NUM.search(text):
        nums = _NUM.findall(text)
        key = _NUM.sub(lambda m, c=iter(range(99)): "{" + str(next(c)) + "}", text)
        hit = tab.get(key)
        if hit:
            out = re.sub(r"\{(\d+)\}", lambda m: nums[int(m.group(1))] if int(m.group(1)) < len(nums) else m.group(0), hit)
    out = out or text
    return out.format(**kw) if kw else out


def system_language() -> str:
    """Windows'un arayüz dilinden en yakın desteklenen dil."""
    try:
        lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        primary = lcid & 0x3FF
    except (AttributeError, OSError):
        return "en"
    return {0x1F: "tr", 0x09: "en", 0x0A: "es", 0x16: "pt", 0x0C: "fr", 0x07: "de", 0x19: "ru", 0x01: "ar",
            0x39: "hi", 0x21: "id", 0x04: "zh", 0x11: "ja", 0x12: "ko"}.get(primary, "en")
