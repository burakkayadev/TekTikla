"""Akıllı kırpma için yüz takibi: yatay videoyu dikeye çevirirken konuşan kişi kadrajda kalsın.

OpenCV büyük olduğu için uygulamaya gömülmez; ilk kullanımda PyPI'den indirilir (~44 MB) ve
LOCAL_DIR/opencv'ye açılır. Yüz modeli YuNet (~230 KB); indirilemezse OpenCV'nin kendi Haar modeli kullanılır.
"""
from __future__ import annotations

import hashlib
import importlib
import io
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Callable

import numpy as np
import requests

from . import media, tools
from .config import LOCAL_DIR

CV_DIR = LOCAL_DIR / "opencv"
YUNET = CV_DIR / "face_detection_yunet_2023mar.onnx"
YUNET_URLS = [
    "https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx",
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/"
    "face_detection_yunet_2023mar.onnx",
]
Progress = Callable[[float, str], None]


def ensure_cv2(progress: Progress):
    """cv2 modülünü döndürür; yoksa PyPI'deki resmi tekerlekten indirip kurar."""
    try:
        return importlib.import_module("cv2")
    except ImportError:
        pass
    if not (CV_DIR / "cv2" / "__init__.py").exists():
        meta = requests.get("https://pypi.org/pypi/opencv-python-headless/json", timeout=30)
        meta.raise_for_status()
        wheel = next(f for f in meta.json()["urls"] if f["filename"].endswith("-abi3-win_amd64.whl"))
        buf = io.BytesIO()
        with requests.get(wheel["url"], stream=True, timeout=60) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length") or wheel.get("size") or 0)
            for chunk in r.iter_content(1 << 16):
                buf.write(chunk)
                progress(buf.tell() / total if total else 0,
                         f"Akıllı kırpma bileşeni indiriliyor (ilk sefer) {buf.tell() / 1e6:.0f} MB")
        if hashlib.sha256(buf.getvalue()).hexdigest() != wheel["digests"]["sha256"]:
            raise RuntimeError("OpenCV indirmesi doğrulanamadı (SHA-256 uyuşmuyor).")
        staging = CV_DIR.with_name("opencv_new")
        shutil.rmtree(staging, ignore_errors=True)
        with zipfile.ZipFile(buf) as z:
            for name in z.namelist():
                if name.startswith("cv2/"):
                    z.extract(name, staging)
        old = [p for p in CV_DIR.glob("*.onnx")] if CV_DIR.exists() else []
        for p in old:  # indirilmiş yüz modelini koru
            shutil.copy2(p, staging / p.name)
        shutil.rmtree(CV_DIR, ignore_errors=True)
        staging.replace(CV_DIR)
    if str(CV_DIR) not in sys.path:
        sys.path.insert(0, str(CV_DIR))
    return importlib.import_module("cv2")


def _detector(cv2, size: tuple[int, int]):
    if not YUNET.exists():
        for url in YUNET_URLS:
            try:
                r = requests.get(url, timeout=30)
                if r.ok and len(r.content) > 100_000:
                    YUNET.parent.mkdir(parents=True, exist_ok=True)
                    YUNET.write_bytes(r.content)
                    break
            except requests.RequestException:
                continue
    if YUNET.exists() and hasattr(cv2, "FaceDetectorYN"):
        det = cv2.FaceDetectorYN.create(str(YUNET), "", size, 0.6, 0.3, 50)

        def detect(frame):
            _, faces = det.detect(frame)
            return [] if faces is None else [(f[0], f[1], f[2], f[3], f[14]) for f in faces]
        return detect
    cascade = cv2.CascadeClassifier(str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"))

    def detect_haar(frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        found = cascade.detectMultiScale(gray, 1.15, 6, minSize=(size[0] // 18, size[0] // 18))
        return [(x, y, w, h, 0.8) for x, y, w, h in found]
    return detect_haar


def face_track(video: Path, progress: Progress, should_stop: Callable[[], bool] = lambda: False, *,
               start: float = 0.0, duration: float | None = None, fps: float = 4.0,
               width: int = 640) -> list[tuple[float, float, float]]:
    """[(start'a göre zaman, yüz merkezi x 0-1, yüz genişliği 0-1)] - her örnek karede en büyük yüz."""
    cv2 = ensure_cv2(progress)
    info = media.probe(video)
    if not info["width"]:
        return []
    height = int(round(info["height"] * width / info["width"] / 2) * 2)
    detect = _detector(cv2, (width, height))
    window = ["-ss", f"{start:.3f}"] + (["-t", f"{duration:.3f}"] if duration else [])
    proc = subprocess.Popen(
        [media.ffmpeg(), "-hide_banner", "-loglevel", "error", *window, "-i", str(video), "-an",
         "-vf", f"fps={fps},scale={width}:{height}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
        stdout=subprocess.PIPE, creationflags=tools.NO_WINDOW)
    frame_bytes = width * height * 3
    track, i = [], 0
    total = max(1, int((duration or max(info["duration"] - start, 1)) * fps))
    try:
        while True:
            if should_stop():
                break
            raw = proc.stdout.read(frame_bytes)
            if len(raw) < frame_bytes:
                break
            frame = np.frombuffer(raw, np.uint8).reshape(height, width, 3)
            faces = detect(frame)
            if faces:
                x, y, w, h, _score = max(faces, key=lambda f: f[2] * f[3])
                track.append((i / fps, float((x + w / 2) / width), float(w / width)))
            i += 1
            if i % 8 == 0:
                progress(min(i / total, 1), "Yüzler takip ediliyor (akıllı kırpma)")
    finally:
        proc.kill()
    return track


def crop_centers(track: list[tuple[float, float, float]], spans: list[tuple[float, float]],
                 default: float = 0.5) -> list[float]:
    """Her zaman aralığı için kadraj merkezi (0-1): aralıktaki yüz merkezlerinin ortancası."""
    centers, last = [], default
    for a, b in spans:
        xs = [x for t, x, _w in track if a <= t <= b]
        if xs:
            last = float(np.median(xs))
        centers.append(last)
    return centers
