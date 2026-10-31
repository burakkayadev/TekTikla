"""Konuşmayı yazıya dökme: whisper.cpp (pywhispercpp) bilgisayarda çalışır.

Ücretsizdir ve ses hiçbir yere gönderilmez. Model ilk kullanımda LOCAL_DIR/models'e indirilir.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable

import numpy as np
import requests

from . import tools
from .config import LOCAL_DIR
from .subtitles import Cue

MODELS = {  # ad: (dosya, yaklaşık MB) — q5_1 nicemlenmiş, çok dilli modeller
    "base": ("ggml-base-q5_1.bin", 60),
    "small": ("ggml-small-q5_1.bin", 190),
}
MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{}"
MODELS_DIR = LOCAL_DIR / "models"
SAMPLE_RATE = 16000


def model_path(name: str) -> Path:
    return MODELS_DIR / MODELS.get(name, MODELS["small"])[0]


def ensure_model(name: str, progress: Callable[[float, str], None]) -> Path:
    path = model_path(name)
    if path.exists():
        return path
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(".part")
    with requests.get(MODEL_URL.format(path.name), stream=True, timeout=30) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length") or 0)
        done = 0
        with open(part, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
                done += len(chunk)
                progress(done / total if total else 0,
                         f"Konuşma tanıma modeli indiriliyor (ilk sefer) {done / 1e6:.0f} MB")
    if part.stat().st_size < 1_000_000:
        part.unlink(missing_ok=True)
        raise RuntimeError("Konuşma tanıma modeli indirilemedi.")
    part.replace(path)
    return path


def load_audio(media: Path) -> np.ndarray:
    """FFmpeg ile 16 kHz mono ses örneklerine çevirir."""
    ffmpeg = tools.ffmpeg_exe()
    if not ffmpeg:
        raise RuntimeError("Konuşmayı yazıya dökmek için FFmpeg gerekli.")
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(media), "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
         "-f", "s16le", "-"],
        capture_output=True, creationflags=tools.NO_WINDOW,
    )
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError("Videonun sesi okunamadı: " + result.stderr.decode("utf-8", "replace")[-300:])
    return np.frombuffer(result.stdout, np.int16).astype(np.float32) / 32768.0


def transcribe(media: Path, model_name: str, progress: Callable[[float, str], None],
               should_stop: Callable[[], bool] = lambda: False) -> tuple[list[Cue], str]:
    """(satırlar, algılanan dil kodu) döndürür."""
    from pywhispercpp.model import Model  # ağır modül; sadece gerektiğinde yüklensin

    path = ensure_model(model_name, progress)
    progress(0, "Ses hazırlanıyor")
    audio = load_audio(media)
    duration = len(audio) / SAMPLE_RATE or 1
    model = Model(str(path), redirect_whispercpp_logs_to=None, print_progress=False, print_realtime=False,
                  n_threads=max(1, (os.cpu_count() or 2) - 1))
    (lang, _prob), _ = model.auto_detect_language(audio)
    progress(0, f"Konuşma yazıya dökülüyor ({lang})")

    def on_segment(seg) -> None:
        progress(min(seg.t1 / 100 / duration, 1), f"Konuşma yazıya dökülüyor ({lang})")

    segments = model.transcribe(audio, language=lang, new_segment_callback=on_segment, abort_callback=should_stop)
    # whisper.cpp zamanları 10 ms birimindedir
    cues = [Cue(s.t0 / 100, s.t1 / 100, s.text.strip()) for s in segments if s.text.strip()]
    return cues, lang
