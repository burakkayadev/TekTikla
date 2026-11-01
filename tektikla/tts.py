"""Metni sese çevirme (seslendirme): dublaj ve fikirden Reels için.

Motorlar, ücretsizden ücretliye:
  - edge: Microsoft Edge'in sinirsel sesleri. Ücretsiz, anahtar gerekmez, kelime zamanlarını da verir.
  - gemini: Gemini 3.8 Flash TTS. Ücretsiz katmanda (Gemini anahtarıyla), çok doğal ve duygulu.
  - elevenlabs: en doğal sesler; ücretsiz planda ayda ~10.000 karakter, sonrası ücretli.
"""
from __future__ import annotations

import asyncio
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import media, services
from .words import Word

RATE = 24000

ENGINES = {
    "edge": {"name": "Edge sesleri", "tier": "free", "needs": None},
    "gemini": {"name": "Gemini TTS", "tier": "free", "needs": "gemini"},
    "elevenlabs": {"name": "ElevenLabs", "tier": "freemium", "needs": "elevenlabs"},
}

# Dil başına seçilmiş Edge sesleri (Erkek / Kadın). "Multilingual" sesler daha doğal.
EDGE_VOICES = {
    "tr": [("tr-TR-AhmetNeural", "Ahmet · Erkek"), ("tr-TR-EmelNeural", "Emel · Kadın")],
    "en": [("en-US-AndrewMultilingualNeural", "Andrew · Erkek"), ("en-US-AvaMultilingualNeural", "Ava · Kadın"),
           ("en-US-BrianMultilingualNeural", "Brian · Erkek"), ("en-US-EmmaMultilingualNeural", "Emma · Kadın"),
           ("en-GB-RyanNeural", "Ryan · Erkek (UK)"), ("en-GB-SoniaNeural", "Sonia · Kadın (UK)")],
    "de": [("de-DE-FlorianMultilingualNeural", "Florian · Erkek"), ("de-DE-SeraphinaMultilingualNeural", "Seraphina · Kadın")],
    "fr": [("fr-FR-RemyMultilingualNeural", "Rémy · Erkek"), ("fr-FR-VivienneMultilingualNeural", "Vivienne · Kadın")],
    "es": [("es-ES-AlvaroNeural", "Álvaro · Erkek"), ("es-ES-ElviraNeural", "Elvira · Kadın"),
           ("es-MX-JorgeNeural", "Jorge · Erkek (MX)"), ("es-MX-DaliaNeural", "Dalia · Kadın (MX)")],
    "it": [("it-IT-GiuseppeMultilingualNeural", "Giuseppe · Erkek"), ("it-IT-IsabellaNeural", "Isabella · Kadın")],
    "pt": [("pt-BR-AntonioNeural", "Antônio · Erkek (BR)"), ("pt-BR-FranciscaNeural", "Francisca · Kadın (BR)"),
           ("pt-PT-DuarteNeural", "Duarte · Erkek (PT)"), ("pt-PT-RaquelNeural", "Raquel · Kadın (PT)")],
    "ru": [("ru-RU-DmitryNeural", "Dmitry · Erkek"), ("ru-RU-SvetlanaNeural", "Svetlana · Kadın")],
    "ar": [("ar-SA-HamedNeural", "Hamed · Erkek"), ("ar-SA-ZariyahNeural", "Zariyah · Kadın"),
           ("ar-EG-ShakirNeural", "Shakir · Erkek (EG)"), ("ar-EG-SalmaNeural", "Salma · Kadın (EG)")],
    "az": [("az-AZ-BabekNeural", "Babək · Erkek"), ("az-AZ-BanuNeural", "Banu · Kadın")],
    "nl": [("nl-NL-MaartenNeural", "Maarten · Erkek"), ("nl-NL-ColetteNeural", "Colette · Kadın")],
    "pl": [("pl-PL-MarekNeural", "Marek · Erkek"), ("pl-PL-ZofiaNeural", "Zofia · Kadın")],
    "ja": [("ja-JP-KeitaNeural", "Keita · Erkek"), ("ja-JP-NanamiNeural", "Nanami · Kadın")],
    "ko": [("ko-KR-InJoonNeural", "InJoon · Erkek"), ("ko-KR-SunHiNeural", "SunHi · Kadın")],
    "zh": [("zh-CN-YunxiNeural", "Yunxi · Erkek"), ("zh-CN-XiaoxiaoNeural", "Xiaoxiao · Kadın")],
    "hi": [("hi-IN-MadhurNeural", "Madhur · Erkek"), ("hi-IN-SwaraNeural", "Swara · Kadın")],
    "id": [("id-ID-ArdiNeural", "Ardi · Erkek"), ("id-ID-GadisNeural", "Gadis · Kadın")],
}


@dataclass
class Speech:
    samples: np.ndarray  # mono float32, RATE Hz
    words: list[Word] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return len(self.samples) / RATE


def voices(engine: str, lang: str, keys: dict) -> list[tuple[str, str]]:
    if engine == "gemini":
        return services.GEMINI_VOICES
    if engine == "elevenlabs":
        return services.elevenlabs_voices(keys.get("elevenlabs", ""))
    return EDGE_VOICES.get(lang, EDGE_VOICES["en"])


def default_voice(engine: str, lang: str, female: bool = False) -> str:
    if engine == "gemini":
        return "Kore" if female else "Charon"
    if engine == "elevenlabs":
        return services.EL_FALLBACK_VOICES[1 if female else 0][0]
    options = EDGE_VOICES.get(lang, EDGE_VOICES["en"])
    return options[1 if female and len(options) > 1 else 0][0]


# ----------------------------------------------------------------------------- motorlar

async def _edge(text: str, voice: str, rate: str) -> tuple[bytes, list[Word]]:
    import edge_tts

    audio = bytearray()
    found: list[Word] = []
    comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            start = chunk["offset"] / 1e7  # 100 ns birimi
            found.append(Word(start, start + chunk["duration"] / 1e7, chunk["text"]))
    return bytes(audio), found


def _decode(data: bytes, suffix: str) -> np.ndarray:
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(data)
        path = Path(f.name)
    try:
        return media.read_audio(path, RATE)
    finally:
        path.unlink(missing_ok=True)


def estimate_words(text: str, samples: np.ndarray) -> list[Word]:
    """Zaman vermeyen motorlar için: kelimeleri sesli bölüme uzunluklarıyla orantılı yayar."""
    tokens = text.split()
    if not tokens or not len(samples):
        return []
    hop = RATE // 50
    energy = np.sqrt(np.convolve(samples ** 2, np.ones(hop) / hop, mode="same")[::hop])
    voiced = np.nonzero(energy > max(0.01, energy.max() * 0.08))[0]
    a, b = (voiced[0] * hop / RATE, voiced[-1] * hop / RATE) if len(voiced) else (0, len(samples) / RATE)
    weights = [len(t) + 2 for t in tokens]
    total, t, out = sum(weights), a, []
    for tok, wgt in zip(tokens, weights):
        dur = (b - a) * wgt / total
        out.append(Word(t, t + dur, tok))
        t += dur
    return out


def synthesize(engine: str, text: str, voice: str, keys: dict, *, speed: float = 1.0,
               style: str | None = None) -> Speech:
    """Metni seslendirir. speed: Edge'de konuşma hızı (1.1 = %10 hızlı)."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return Speech(np.zeros(0, np.float32))
    if engine == "gemini":
        wav = services.gemini_tts(keys.get("gemini", ""), text, voice or "Kore", style)
        samples = _decode(wav, ".wav")
        return Speech(samples, estimate_words(text, samples))
    if engine == "elevenlabs":
        mp3, words = services.elevenlabs_tts(keys.get("elevenlabs", ""), text, voice)
        samples = _decode(mp3, ".mp3")
        return Speech(samples, [Word(a, b, w) for a, b, w in words] or estimate_words(text, samples))
    rate = f"{round((speed - 1) * 100):+d}%"
    try:
        mp3, words = asyncio.run(_edge(text, voice, rate))
    except Exception as e:  # noqa: BLE001
        raise services.ServiceError(f"Edge seslendirme servisine ulaşılamadı: {e}") from e
    if not mp3:
        raise services.ServiceError("Edge seslendirme ses döndürmedi.")
    samples = _decode(mp3, ".mp3")
    return Speech(samples, words or estimate_words(text, samples))
