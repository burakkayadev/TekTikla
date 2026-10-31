"""Harici araçlar: FFmpeg (birleştirme/MP3/altyazı) ve JS çalışma zamanı (YouTube için).

Bulunamazlarsa uygulama klasöründeki bin/ içine otomatik indirilirler.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Callable

import requests

from .config import BIN_DIR, FROZEN, LIB_DIR, LOCAL_DIR

FFMPEG_URL = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
DENO_URL = "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip"

# Konsol penceresi açılmasın (pythonw ile çalışırken alt süreçler için)
NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

ProgressCb = Callable[[str, float], None]

# yt-dlp'nin bazı kontrolleri (ör. kesit indirme) ffmpeg_location ayarına değil PATH'e bakıyor
if str(BIN_DIR) not in os.environ.get("PATH", "").split(os.pathsep):
    os.environ["PATH"] = str(BIN_DIR) + os.pathsep + os.environ.get("PATH", "")


def _exe(name: str) -> str:
    return f"{name}.exe" if sys.platform == "win32" else name


def find_ffmpeg() -> str | None:
    """ffmpeg.exe'nin bulunduğu klasörü döndürür (ffprobe da orada olmalı)."""
    local = BIN_DIR / _exe("ffmpeg")
    if local.exists() and (BIN_DIR / _exe("ffprobe")).exists():
        return str(BIN_DIR)
    found = shutil.which("ffmpeg")
    if found and shutil.which("ffprobe"):
        return str(Path(found).parent)
    return None


def ffmpeg_exe() -> str | None:
    folder = find_ffmpeg()
    return str(Path(folder) / _exe("ffmpeg")) if folder else None


def js_runtimes() -> dict:
    """yt-dlp için kullanılabilir JS çalışma zamanları (YouTube imza çözümü için gerekli)."""
    runtimes = {}
    local_deno = BIN_DIR / _exe("deno")
    if local_deno.exists():
        runtimes["deno"] = {"path": str(local_deno)}
    elif shutil.which("deno"):
        runtimes["deno"] = {"path": None}
    if shutil.which("node"):
        runtimes["node"] = {"path": None}
    return runtimes


def missing_components() -> list[str]:
    missing = []
    if not find_ffmpeg():
        missing.append("ffmpeg")
    if not js_runtimes():
        missing.append("deno")
    return missing


def _download(url: str, dest: Path, label: str, progress: ProgressCb) -> None:
    with requests.get(url, stream=True, timeout=30) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length") or 0)
        done = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)
                done += len(chunk)
                progress(f"{label} indiriliyor… {done / 1e6:.0f} MB", done / total if total else 0)


def _extract(zip_path: Path, names: set[str]) -> None:
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        for member in z.namelist():
            name = Path(member).name
            if name in names:
                with z.open(member) as src, open(BIN_DIR / name, "wb") as dst:
                    shutil.copyfileobj(src, dst)


def install_components(components: list[str], progress: ProgressCb) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        for comp in components:
            zip_path = Path(tmp) / f"{comp}.zip"
            if comp == "ffmpeg":
                _download(FFMPEG_URL, zip_path, "FFmpeg", progress)
                progress("FFmpeg açılıyor…", 1)
                _extract(zip_path, {_exe("ffmpeg"), _exe("ffprobe")})
            elif comp == "deno":
                _download(DENO_URL, zip_path, "Deno", progress)
                progress("Deno açılıyor…", 1)
                _extract(zip_path, {_exe("deno")})


UPDATABLE = ("yt_dlp", "yt_dlp_ejs")


class _UpdatedLibFinder:
    """TekTikla.exe içinde paketlenmiş yt-dlp yerine LIB_DIR'deki güncel sürümü yükletir."""

    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] not in UPDATABLE:
            return None
        from importlib.machinery import PathFinder
        return PathFinder.find_spec(name, path if path is not None else [str(LIB_DIR)])


def use_updated_ytdlp() -> None:
    """yt_dlp içe aktarılmadan önce çağrılmalı."""
    if FROZEN and (LIB_DIR / "yt_dlp" / "__init__.py").exists():
        sys.meta_path.insert(0, _UpdatedLibFinder())


def _pypi_wheel(package: str, version: str | None = None) -> tuple[str, dict]:
    url = f"https://pypi.org/pypi/{package}/{version}/json" if version else f"https://pypi.org/pypi/{package}/json"
    meta = requests.get(url, timeout=20)
    meta.raise_for_status()
    meta = meta.json()
    wheel = next(f for f in meta["urls"] if f["packagetype"] == "bdist_wheel" and f["filename"].endswith("-any.whl"))
    return meta["info"]["version"], {"wheel": wheel, "requires": meta["info"].get("requires_dist") or []}


def _extract_wheel(info: dict, dest: Path) -> None:
    data = requests.get(info["wheel"]["url"], timeout=120)
    data.raise_for_status()
    import hashlib
    import io
    if hashlib.sha256(data.content).hexdigest() != info["wheel"]["digests"]["sha256"]:
        raise RuntimeError("İndirilen dosya doğrulanamadı (SHA-256 uyuşmuyor).")
    with zipfile.ZipFile(io.BytesIO(data.content)) as z:
        z.extractall(dest)


def _update_frozen() -> str:
    import yt_dlp.version

    current = yt_dlp.version.__version__
    latest, ytdlp = _pypi_wheel("yt-dlp")
    if latest == current:
        return f"yt-dlp zaten güncel ({current})."
    # yt-dlp, YouTube için belirli bir yt-dlp-ejs sürümünü ister
    ejs_pin = next((re.search(r"==\s*([\w.]+)", r).group(1) for r in ytdlp["requires"]
                    if r.startswith("yt-dlp-ejs") and "==" in r), None)
    _, ejs = _pypi_wheel("yt-dlp-ejs", ejs_pin)

    staging = LOCAL_DIR / "lib_new"
    shutil.rmtree(staging, ignore_errors=True)
    _extract_wheel(ytdlp, staging)
    _extract_wheel(ejs, staging)
    shutil.rmtree(LIB_DIR, ignore_errors=True)
    staging.replace(LIB_DIR)
    return f"Successfully installed yt-dlp {latest}"


def update_ytdlp() -> str:
    """yt-dlp'yi günceller; siteler değiştikçe indirme çalışmaya devam etsin diye önemli."""
    if FROZEN:
        return _update_frozen()
    python = Path(sys.executable)
    if python.name.lower() == "pythonw.exe":
        python = python.with_name("python.exe")
    result = subprocess.run(
        [str(python), "-m", "pip", "install", "-U", "yt-dlp[default]"],
        capture_output=True, text=True, creationflags=NO_WINDOW,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip()[-500:] or "pip başarısız oldu")
    lines = [l for l in result.stdout.splitlines() if "Successfully installed" in l]
    return lines[0] if lines else "yt-dlp zaten güncel."
