"""Zaman bilgili altyazı işlemleri: sitedeki altyazıyı okuma, birleştirme, .srt yazma ve AI çevirisi."""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import yt_dlp
from pydantic import BaseModel, Field

from . import engine, llm

PREFERRED_LANGS = ("tr", "en")
SUB_FORMATS = ("json3", "vtt", "srt", "srv3", "ttml")
BATCH = 80           # bir istekte çevrilecek satır sayısı
CONTEXT_LINES = 3    # tutarlılık için önceki parçadan gösterilen satır

# Arayüzdeki "AI altyazı" dil listesi (kod, görünen ad, ffmpeg dil etiketi)
LANGUAGES = [
    ("tr", "Türkçe", "tur"), ("en", "English", "eng"), ("de", "Deutsch", "ger"), ("fr", "Français", "fre"),
    ("es", "Español", "spa"), ("it", "Italiano", "ita"), ("pt", "Português", "por"), ("ru", "Русский", "rus"),
    ("ar", "العربية", "ara"), ("az", "Azərbaycanca", "aze"), ("nl", "Nederlands", "dut"), ("pl", "Polski", "pol"),
    ("ja", "日本語", "jpn"), ("ko", "한국어", "kor"), ("zh", "中文", "chi"),
]
LANG_NAMES = {code: name for code, name, _ in LANGUAGES}
LANG_TAGS = {code: tag for code, _, tag in LANGUAGES}


@dataclass
class Cue:
    start: float
    end: float
    text: str


# ----------------------------------------------------------------------------- okuma

def _ts(text: str) -> float:
    parts = text.strip().replace(",", ".").split(":")
    total = 0.0
    for p in parts:
        total = total * 60 + float(p)
    return total


def parse_json3(text: str) -> list[Cue]:
    cues = []
    for ev in json.loads(text).get("events", []):
        if "segs" not in ev or ev.get("aAppend"):
            continue
        line = "".join(s.get("utf8", "") for s in ev["segs"]).replace("\n", " ").strip()
        if line:
            start = ev.get("tStartMs", 0) / 1000
            cues.append(Cue(start, start + ev.get("dDurationMs", 2000) / 1000, line))
    return cues


def parse_timed_text(text: str) -> list[Cue]:
    """VTT ve SRT: 'başlangıç --> bitiş' satırını izleyen metin bloklarını okur."""
    cues: list[Cue] = []
    block: list[str] = []
    start = end = None
    for raw in text.splitlines() + [""]:
        line = raw.strip()
        if "-->" in line:
            a, b = line.split("-->", 1)
            start, end = _ts(a), _ts(b.split()[0])
            block = []
        elif not line:
            if start is not None and block:
                cues.append(Cue(start, end, " ".join(block)))
            start, block = None, []
        elif start is not None:
            clean = re.sub(r"<[^>]+>", "", line).strip()
            if clean:
                block.append(clean)
    return cues


def dedupe_rolling(cues: list[Cue]) -> list[Cue]:
    """YouTube otomatik altyazılarında satırlar kayarak iki kez görünür; tekrarları atar."""
    out: list[Cue] = []
    for c in cues:
        c = Cue(c.start, c.end, re.sub(r"(^|\s)>>\s*", r"\1– ", c.text).strip())  # konuşmacı değişimi
        if out and (c.text == out[-1].text or out[-1].text.endswith(c.text)):
            out[-1].end = max(out[-1].end, c.end)
            continue
        if out and c.text.startswith(out[-1].text):
            c = Cue(c.start, c.end, c.text[len(out[-1].text):].strip())
            if not c.text:
                continue
        out.append(c)
    return out


def pick_track(info: dict) -> tuple[list[dict], str, bool] | None:
    """Önce elle yazılmış altyazı, sonra videonun orijinal dilindeki otomatik altyazı."""
    lang = (info.get("language") or "").split("-")[0]
    manual = {k: v for k, v in (info.get("subtitles") or {}).items() if k != "live_chat" and v}
    auto = {k: v for k, v in (info.get("automatic_captions") or {}).items() if v}
    for key in [lang, *PREFERRED_LANGS, *manual]:
        if key and key in manual:
            return manual[key], key, False
    for key in auto:
        if key.endswith("-orig"):
            return auto[key], key, True
    for key in [lang, *PREFERRED_LANGS]:
        if key and key in auto:
            return auto[key], key, True
    return None


def caption_cues(info: dict, settings: dict) -> tuple[list[Cue], str, str] | None:
    """Sitedeki altyazıyı zaman bilgisiyle indirir: (satırlar, dil kodu, kaynak açıklaması)."""
    picked = pick_track(info)
    if not picked:
        return None
    tracks, lang, auto = picked
    by_ext = {t.get("ext"): t for t in tracks if t.get("url")}
    track = next((by_ext[e] for e in SUB_FORMATS if e in by_ext), None)
    if not track:
        return None
    with yt_dlp.YoutubeDL(engine.base_opts(settings)) as ydl:
        text = ydl.urlopen(track["url"]).read().decode("utf-8", "replace")
    cues = parse_json3(text) if track["ext"] == "json3" else parse_timed_text(text)
    cues = dedupe_rolling(cues)
    if not cues:
        return None
    base_lang = lang.split("-")[0]
    return cues, base_lang, f"{'otomatik' if auto else 'elle yazılmış'} altyazı ({base_lang})"


# ----------------------------------------------------------------------------- düzenleme

def merge(cues: list[Cue], max_chars: int = 84, max_dur: float = 6.0, gap: float = 0.8) -> list[Cue]:
    """Kısa parçaları okunabilir altyazı satırlarına birleştirir (çeviriye de bağlam kazandırır)."""
    out: list[Cue] = []
    for c in cues:
        if out:
            last = out[-1]
            joined = f"{last.text} {c.text}"
            ends_sentence = last.text.endswith((".", "?", "!", "…"))
            if (len(joined) <= max_chars and c.end - last.start <= max_dur and c.start - last.end <= gap
                    and not ends_sentence):
                out[-1] = Cue(last.start, c.end, joined)
                continue
        out.append(Cue(c.start, c.end, c.text))
    # üst üste binen satırları düzelt
    for a, b in zip(out, out[1:]):
        if a.end > b.start:
            a.end = max(a.start + 0.3, b.start - 0.05)
    return out


def shift(cues: list[Cue], start: float, end: float) -> list[Cue]:
    """Kesit indirmede altyazıyı kesitin başına göre kaydırır."""
    return [Cue(max(0.0, c.start - start), min(c.end, end) - start, c.text)
            for c in cues if c.end > start and c.start < end]


def to_srt(cues: list[Cue]) -> str:
    def stamp(t: float) -> str:
        ms = int(round(t * 1000))
        h, ms = divmod(ms, 3_600_000)
        m, ms = divmod(ms, 60_000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    return "\n".join(f"{i}\n{stamp(c.start)} --> {stamp(c.end)}\n{c.text}\n" for i, c in enumerate(cues, 1))


def write_srt(cues: list[Cue], path: Path) -> Path:
    path.write_text(to_srt(cues), encoding="utf-8")
    return path


# ----------------------------------------------------------------------------- çeviri

class _Line(BaseModel):
    id: int = Field(description="Girdideki satır numarası, aynen korunmalı")
    text: str = Field(description="Satırın çevirisi")


class _Batch(BaseModel):
    lines: list[_Line] = Field(description="Girdideki her satırın çevirisi, aynı sırayla")


TRANSLATE_SYSTEM = """Sen profesyonel bir video altyazı çevirmenisin. Sana numaralı altyazı satırları verilecek; \
her satırı hedef dile çevir.

Kurallar:
- Her satırı ayrı çevir ve numarasını aynen koru. Satır birleştirme, bölme veya atlama yapma.
- Doğal, akıcı ve günlük konuşma diline uygun çevir; altyazı olduğu için kısa ve okunaklı tut.
- Özel isimleri, marka ve kanal adlarını çevirme.
- [Müzik], [Alkış] gibi ses etiketlerini hedef dilde köşeli parantezle yaz.
- Otomatik altyazıdan gelen yazım hatalarını bağlamdan anlayıp düzgün çevir.
- "Önceki satırlar" bölümü yalnızca bağlam içindir, onları çevirme."""


def _translate_batch(batch: list[tuple[int, Cue]], context: list[Cue], target: str, provider: str,
                     api_key: str) -> dict[int, str]:
    prompt_parts = [f"Hedef dil: {target}"]
    if context:
        prompt_parts.append("Önceki satırlar (çevirme):\n" + "\n".join(c.text for c in context))
    prompt_parts.append("Çevrilecek satırlar:\n" + "\n".join(f"{i}: {c.text}" for i, c in batch))
    result = llm.generate(provider, api_key, TRANSLATE_SYSTEM, "\n\n".join(prompt_parts), _Batch, effort="low")
    return {line.id: line.text.strip() for line in result.lines if line.text.strip()}


def translate(cues: list[Cue], target_code: str, provider: str, api_key: str, on_progress=lambda f: None,
              should_stop=lambda: False) -> list[Cue]:
    target = LANG_NAMES.get(target_code, target_code)
    indexed = list(enumerate(cues))
    batches = [indexed[i:i + BATCH] for i in range(0, len(indexed), BATCH)]
    done = 0
    translated: dict[int, str] = {}

    def work(batch):
        first = batch[0][0]
        context = cues[max(0, first - CONTEXT_LINES):first]
        result = _translate_batch(batch, context, target, provider, api_key)
        missing = [(i, c) for i, c in batch if i not in result]
        if len(missing) > len(batch) * 0.2:  # model satır atladıysa eksikleri bir kez daha iste
            result.update(_translate_batch(missing, context, target, provider, api_key))
        return result

    with ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(work, batches):
            if should_stop():
                break
            translated.update(result)
            done += 1
            on_progress(done / len(batches))
    return [Cue(c.start, c.end, translated.get(i, c.text)) for i, c in indexed]
