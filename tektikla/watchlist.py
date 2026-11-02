"""İzleme listesi: sonra izlenecek videolar sırayla durur; %APPDATA%\\TekTikla\\watchlist.json içinde kalıcıdır.

Link eklenince öğe hemen listeye girer (YouTube'da kapak da hemen görünür); başlık, kanal ve süre arka planda
yt-dlp ile doldurulur (api.py). Oynatma listesi linki, listedeki her video ayrı bir öğe olacak şekilde açılır.
"""
from __future__ import annotations

import re
import secrets
import threading
import time
from pathlib import Path

from .config import DATA_DIR, _read, _write

WATCHLIST_FILE = DATA_DIR / "watchlist.json"
THUMB_DIR = DATA_DIR / "watchlist"  # YouTube dışı sitelerin kapakları (bazı siteler doğrudan gömmeyi engeller)
LIMIT = 3000
FIELDS = ("title", "channel", "duration", "thumb", "thumb_file", "site", "status", "error", "url")

_YT = re.compile(r"(?:youtube\.com/(?:watch\?(?:[^#\s]*&)?v=|shorts/|live/|embed/)|youtu\.be/)([\w-]{11})")
_URL = re.compile(r"https?://[^\s<>\"']+")


def youtube_id(url: str) -> str | None:
    m = _YT.search(url or "")
    return m.group(1) if m else None


def canonical(url: str) -> str:
    """Aynı videonun farklı yazımları (youtu.be, shorts, &t=…) tek bir adrese iner; tekrar eklemeyi önler."""
    vid = youtube_id(url)
    return f"https://www.youtube.com/watch?v={vid}" if vid else (url or "").strip().rstrip("/")


def youtube_thumb(url: str) -> str | None:
    vid = youtube_id(url)
    return f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg" if vid else None


def links(text: str) -> list[str]:
    """Yapıştırılan metindeki linkler; sırası korunur, aynı video iki kez sayılmaz."""
    seen, out = set(), []
    for url in _URL.findall(text or ""):
        url = url.rstrip(").,;]>'\"")
        key = canonical(url)
        if key not in seen:
            seen.add(key)
            out.append(url)
    return out


def _clean(value, limit: int = 300):
    return value.strip()[:limit] if isinstance(value, str) else value


class Watchlist:
    def __init__(self, path: Path = WATCHLIST_FILE):
        self.path = path
        data = _read(path, [])
        self.items: list[dict] = [i for i in data if isinstance(i, dict) and i.get("id") and i.get("url")] \
            if isinstance(data, list) else []
        self._lock = threading.Lock()
        # kapanırken yarım kalan bilgi çekme işleri yeniden denensin
        for item in self.items:
            if item.get("status") == "loading":
                item["status"] = "retry"

    def _save(self) -> None:
        _write(self.path, self.items)

    def _index(self, item_id: str) -> int:
        return next((i for i, x in enumerate(self.items) if x["id"] == item_id), -1)

    def get(self, item_id: str) -> dict | None:
        i = self._index(item_id)
        return dict(self.items[i]) if i >= 0 else None

    def add(self, url: str, at: int | None = None, **meta) -> dict | None:
        """Yeni öğe ekler; aynı video zaten listedeyse None döner."""
        url = canonical(url)
        with self._lock:
            if any(canonical(x["url"]) == url for x in self.items) or len(self.items) >= LIMIT:
                return None
            item = {"id": "w" + secrets.token_hex(5), "url": url, "title": "", "channel": "", "duration": None,
                    "thumb": youtube_thumb(url), "site": "", "added": time.time(), "watched": False,
                    "watched_at": None, "status": "loading"}
            item.update({k: _clean(v) for k, v in meta.items() if k in FIELDS and v not in (None, "")})
            self.items.insert(len(self.items) if at is None else max(0, min(at, len(self.items))), item)
            self._save()
            return dict(item)

    def update(self, item_id: str, **fields) -> dict | None:
        with self._lock:
            i = self._index(item_id)
            if i < 0:
                return None
            item = self.items[i]
            for k, v in fields.items():
                if k in FIELDS:
                    item[k] = _clean(v)
            if "url" in fields:
                item["url"] = canonical(item["url"])
            if "watched" in fields:
                item["watched"] = bool(fields["watched"])
                item["watched_at"] = time.time() if item["watched"] else None
            self._save()
            return dict(item)

    def replace(self, item_id: str, entries: list[dict]) -> int:
        """Oynatma listesi öğesini, listedeki videolarla aynı yerde değiştirir. Eklenen video sayısını döner."""
        with self._lock:
            i = self._index(item_id)
            if i < 0:
                return 0
            del self.items[i]
            known = {canonical(x["url"]) for x in self.items}
            fresh = []
            for e in entries:
                url = canonical(e.get("url") or "")
                if not url.startswith("http") or url in known or len(self.items) + len(fresh) >= LIMIT:
                    continue
                known.add(url)
                fresh.append({"id": "w" + secrets.token_hex(5), "url": url, "title": _clean(e.get("title") or ""),
                              "channel": _clean(e.get("channel") or ""), "duration": e.get("duration"),
                              "thumb": e.get("thumb") or youtube_thumb(url), "site": _clean(e.get("site") or ""),
                              "added": time.time(), "watched": False, "watched_at": None, "status": "ready"})
            self.items[i:i] = fresh
            self._save()
            return len(fresh)

    def remove(self, item_id: str) -> dict | None:
        with self._lock:
            i = self._index(item_id)
            if i < 0:
                return None
            item = self.items.pop(i)
            self._save()
            return item

    def move(self, item_id: str, index: int) -> bool:
        with self._lock:
            i = self._index(item_id)
            if i < 0:
                return False
            item = self.items.pop(i)
            self.items.insert(max(0, min(int(index), len(self.items))), item)
            self._save()
            return True

    def clear_watched(self) -> list[dict]:
        with self._lock:
            gone = [x for x in self.items if x.get("watched")]
            self.items = [x for x in self.items if not x.get("watched")]
            self._save()
            return gone


# YouTube'un kişisel listeleri: "Daha sonra izle" (WL) ve "Beğenilen videolar" (LL). Resmî API bunları vermez;
# tarayıcıdaki YouTube oturumuyla (Ayarlar > Tarayıcı çerezleri) yt-dlp okur.
YT_WATCH_LATER = "https://www.youtube.com/playlist?list=WL"
YT_LIKED = "https://www.youtube.com/playlist?list=LL"


def is_youtube_private_list(url: str) -> bool:
    return url.rstrip("/") in (YT_WATCH_LATER, YT_LIKED)
