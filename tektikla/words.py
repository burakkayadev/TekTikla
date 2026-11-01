"""Kelime kelime zamanlanmış döküm: Reels altyazı animasyonu, sessizlik kesme ve dublaj bunun üzerine kurulu.

Kaynak sırası (ikisi de ücretsiz):
  1. YouTube otomatik altyazısı (json3 biçiminde kelime zamanları vardır) - anında gelir.
  2. Whisper (whisper.cpp) ile bilgisayarda yazıya dökme - ses hiçbir yere gönderilmez.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yt_dlp

from . import engine, transcribe


@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class Line:
    start: float
    end: float
    text: str
    words: list[Word]


# ----------------------------------------------------------------------------- YouTube

def youtube_words(info: dict, settings: dict) -> tuple[list[Word], str] | None:
    """Videonun orijinal dilindeki otomatik altyazıdan kelime zamanları."""
    auto = {k: v for k, v in (info.get("automatic_captions") or {}).items() if v}
    lang = (info.get("language") or "").split("-")[0]
    key = next((k for k in auto if k.endswith("-orig")), None) or (lang if lang in auto else None)
    if not key:
        return None
    track = next((t for t in auto[key] if t.get("ext") == "json3" and t.get("url")), None)
    if not track:
        return None
    with yt_dlp.YoutubeDL(engine.base_opts(settings)) as ydl:
        data = json.loads(ydl.urlopen(track["url"]).read().decode("utf-8", "replace"))
    words: list[Word] = []
    for ev in data.get("events", []):
        segs = ev.get("segs") or []
        if ev.get("aAppend") or not segs:
            continue
        base = ev.get("tStartMs", 0) / 1000
        stop = base + ev.get("dDurationMs", 0) / 1000
        for i, seg in enumerate(segs):
            text = (seg.get("utf8") or "").strip()
            if not text or text == "\n":
                continue
            start = base + seg.get("tOffsetMs", 0) / 1000
            nxt = next((base + s.get("tOffsetMs", 0) / 1000 for s in segs[i + 1:] if (s.get("utf8") or "").strip()),
                       None)
            end = min(nxt if nxt is not None else stop, start + 1.2)
            words.append(Word(start, max(end, start + 0.08), text))
    words.sort(key=lambda w: w.start)
    if len(words) < 5:
        return None
    for a, b in zip(words, words[1:]):  # kayan altyazıda bitişler bir sonraki kelimeyi aşmasın
        a.end = min(a.end, b.start) if b.start > a.start else a.end
    return words, key.split("-")[0]


# ----------------------------------------------------------------------------- Whisper

def whisper_words(media: Path, model_name: str, progress: Callable[[float, str], None],
                  should_stop: Callable[[], bool] = lambda: False, language: str | None = None
                  ) -> tuple[list[Word], str]:
    from pywhispercpp.model import Model  # ağır modül; sadece gerektiğinde

    path = transcribe.ensure_model(model_name, progress)
    progress(0, "Ses hazırlanıyor")
    audio = transcribe.load_audio(media)
    duration = len(audio) / transcribe.SAMPLE_RATE or 1
    model = Model(str(path), redirect_whispercpp_logs_to=None, print_progress=False, print_realtime=False,
                  n_threads=max(1, (os.cpu_count() or 2) - 1))
    lang = language
    if not lang:
        (lang, _prob), _ = model.auto_detect_language(audio)
    label = f"Konuşma kelime kelime yazıya dökülüyor ({lang})"
    progress(0, label)
    segments = model.transcribe(
        audio, language=lang, token_timestamps=True, max_len=1, split_on_word=True,
        new_segment_callback=lambda seg: progress(min(seg.t1 / 100 / duration, 1), label),
        abort_callback=should_stop,
    )
    words = [Word(s.t0 / 100, max(s.t1, s.t0 + 5) / 100, s.text.strip()) for s in segments
             if s.text.strip() and not re.fullmatch(r"\[.*\]|\(.*\)", s.text.strip())]
    return words, lang


# ----------------------------------------------------------------------------- satırlar ve kırpma

SENTENCE_END = re.compile(r"[.!?…。！？]$")


def lines(words: list[Word], max_words: int = 18, gap: float = 0.8) -> list[Line]:
    """Kelimeleri cümle benzeri satırlara toplar (noktalama, uzun duraklama ya da uzunluk sınırı)."""
    out: list[Line] = []
    cur: list[Word] = []
    for w in words:
        if cur and (w.start - cur[-1].end > gap or len(cur) >= max_words):
            out.append(_line(cur))
            cur = []
        cur.append(w)
        if SENTENCE_END.search(w.text) and len(cur) >= 3:
            out.append(_line(cur))
            cur = []
    if cur:
        out.append(_line(cur))
    return out


def _line(ws: list[Word]) -> Line:
    return Line(ws[0].start, ws[-1].end, " ".join(w.text for w in ws), list(ws))


def between(words: list[Word], start: float, end: float, rebase: bool = True) -> list[Word]:
    """[start, end] aralığındaki kelimeler; rebase ise zamanlar aralığın başına göre."""
    off = start if rebase else 0
    return [Word(max(w.start, start) - off, min(w.end, end) - off, w.text)
            for w in words if w.end > start + 0.05 and w.start < end - 0.05]


def snap(words: list[Word], start: float, end: float) -> tuple[float, float]:
    """Klip sınırlarını kelime sınırlarına yaslar: cümle ortasında başlayıp bitmesin."""
    inside = [w for w in words if w.end > start and w.start < end]
    if not inside:
        return start, end
    return max(0.0, inside[0].start - 0.12), inside[-1].end + 0.25


def speech_spans(words: list[Word], min_gap: float = 0.55, pad: float = 0.12) -> list[tuple[float, float]]:
    """Konuşulan aralıklar: aradaki uzun sessizlikler kesilecek (jump cut)."""
    spans: list[list[float]] = []
    for w in words:
        if spans and w.start - spans[-1][1] <= min_gap:
            spans[-1][1] = max(spans[-1][1], w.end)
        else:
            spans.append([w.start, w.end])
    return [(max(0.0, a - pad), b + pad) for a, b in spans]


def remap(words: list[Word], spans: list[tuple[float, float]]) -> list[Word]:
    """Sessizlikler kesildikten sonra kelime zamanlarını yeni zaman çizgisine taşır."""
    out, offset = [], 0.0
    for a, b in spans:
        for w in words:
            if w.start >= a - 0.01 and w.start < b:
                out.append(Word(w.start - a + offset, min(w.end, b) - a + offset, w.text))
        offset += b - a
    return out
