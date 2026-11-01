"""Stüdyo işleri (Reels, dublaj, fikirden video) için ortak parçalar: FFmpeg çalıştırma, ses okuma/yazma
ve indirme kuyruğunda görünen uzun işlerin temel sınıfı."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import threading
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from . import tools

Emit = Callable[..., None]


class Cancelled(Exception):
    pass


# ----------------------------------------------------------------------------- FFmpeg

def ffmpeg() -> str:
    exe = tools.ffmpeg_exe()
    if not exe:
        raise RuntimeError("Bu iş için FFmpeg gerekli ama bulunamadı. Ayarlar > Sistem'den bileşenleri kurun.")
    return exe


def ffprobe() -> str:
    exe = Path(ffmpeg())
    return str(exe.with_name(exe.name.replace("ffmpeg", "ffprobe")))


def probe(path: Path | str) -> dict:
    """Süre, boyut, fps ve ses olup olmadığı."""
    out = subprocess.run(
        [ffprobe(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=tools.NO_WINDOW,
    )
    if out.returncode != 0:
        raise RuntimeError("Dosya okunamadı: " + out.stderr[-300:])
    data = json.loads(out.stdout or "{}")
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"
                  and not (s.get("disposition") or {}).get("attached_pic")), None)
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    info = {"duration": float(data.get("format", {}).get("duration") or 0), "has_audio": audio is not None,
            "width": 0, "height": 0, "fps": 30.0}
    if video:
        w, h = int(video.get("width") or 0), int(video.get("height") or 0)
        side = (video.get("side_data_list") or [{}])[0]
        rotation = abs(int(side.get("rotation") or (video.get("tags") or {}).get("rotate") or 0))
        if rotation in (90, 270):
            w, h = h, w
        info.update(width=w, height=h)
        num, _, den = (video.get("avg_frame_rate") or "30/1").partition("/")
        try:
            fps = float(num) / float(den or 1)
            info["fps"] = fps if 5 <= fps <= 120 else 30.0
        except (ValueError, ZeroDivisionError):
            pass
    return info


def run_ffmpeg(args: list[str], *, duration: float | None = None, on_progress: Callable[[float], None] | None = None,
               job: "Job | None" = None, cwd: str | None = None) -> None:
    """FFmpeg'i çalıştırır; süre verilirse 0-1 arası ilerleme bildirir, iş iptal edilirse süreci durdurur."""
    cmd = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-nostats", "-progress", "pipe:1", *args]
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace", creationflags=tools.NO_WINDOW)
    if job:
        job._proc = proc
    errors: list[str] = []
    threading.Thread(target=lambda: errors.extend(proc.stderr), daemon=True).start()
    for line in proc.stdout:
        if on_progress and duration and line.startswith("out_time_us="):
            try:
                on_progress(min(max(int(line.split("=")[1]) / 1e6 / duration, 0), 1))
            except ValueError:
                pass
    code = proc.wait()
    if job:
        job._proc = None
        job.check()
    if code != 0:
        raise RuntimeError("FFmpeg hatası: " + "".join(errors)[-500:])


def read_audio(path: Path | str, rate: int = 24000) -> np.ndarray:
    """Herhangi bir ses/video dosyasının sesini mono float32 örneklere çevirir."""
    out = subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-i", str(path), "-vn", "-ac", "1",
                          "-ar", str(rate), "-f", "f32le", "-"], capture_output=True, creationflags=tools.NO_WINDOW)
    if out.returncode != 0:
        raise RuntimeError("Ses okunamadı: " + out.stderr.decode("utf-8", "replace")[-300:])
    return np.frombuffer(out.stdout, np.float32).copy()


def write_wav(path: Path | str, samples: np.ndarray, rate: int = 24000) -> Path:
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return Path(path)


def speed_up(samples: np.ndarray, factor: float, rate: int) -> np.ndarray:
    """Konuşmayı perdesini bozmadan factor kat hızlandırır (FFmpeg atempo)."""
    if factor < 1.02:
        return samples
    tmp = Path(tempfile.mkdtemp(prefix="tt_"))
    try:
        src, dst = write_wav(tmp / "in.wav", samples, rate), tmp / "out.wav"
        run_ffmpeg(["-i", str(src), "-filter:a", f"atempo={min(factor, 2.0):.4f}", "-ar", str(rate), str(dst)])
        return read_audio(dst, rate)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------------------- kuyruk işleri

class Job:
    """İndirmeler sekmesinde görünen uzun iş. Alt sınıflar work() yazar ve oluşan dosyaları döndürür."""

    def __init__(self, settings: dict, emit: Emit):
        self.settings = settings
        self.emit = emit
        self.warnings: list[str] = []
        self._cancel = threading.Event()
        self._proc: subprocess.Popen | None = None

    def cancel(self) -> None:
        self._cancel.set()
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def check(self) -> None:
        if self.cancelled:
            raise Cancelled

    def stage(self, text: str, frac: float | None = None) -> None:
        self.check()
        self.emit("progress", stage=text, frac=frac)

    def ffmpeg(self, args: list[str], duration: float | None, stage: str, span: tuple[float, float] = (0, 1)) -> None:
        a, b = span
        self.stage(stage, a if duration else None)
        run_ffmpeg(args, duration=duration, job=self,
                   on_progress=lambda f: self.emit("progress", stage=stage, frac=a + (b - a) * f))

    def work(self) -> list[str]:
        raise NotImplementedError

    def run(self) -> None:
        from .engine import friendly_error  # engine ağır; döngüsel içe aktarmayı da önler
        try:
            files = self.work()
            self.check()
            self.emit("done", files=[str(f) for f in files], warning="\n".join(self.warnings))
        except Cancelled:
            self.emit("cancelled")
        except Exception as e:  # noqa: BLE001 - her hatayı kullanıcıya göstermek istiyoruz
            self.emit("cancelled" if self.cancelled else "error", message=friendly_error(e))


@dataclass
class StudioTask:
    """Kuyruğa giren stüdyo işinin tarifi. İşi her denemede yeniden kurar (Tekrar dene düğmesi için)."""
    kind: str  # "reels" | "dub" | "idea"
    title: str
    url: str
    out_dir: str
    label: str  # kuyrukta başlığın altında görünen özet
    done_text: str  # bitince çıkan bildirim
    factory: Callable[[dict, Emit], Job] = field(repr=False)

    def make_job(self, settings: dict, emit: Emit) -> Job:
        return self.factory(settings, emit)
