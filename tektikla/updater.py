"""GitHub Releases üzerinden TekTıkla güncellemesi.

Yeni sürüm yayınlamak: GitHub'da v2.1.0 gibi bir etiketle Release oluşturup kurulum dosyasını
(adında "Setup" veya "Kurulum" geçen .exe) eke ekleyin. Uygulama açılışta bunu fark eder.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

import requests

from . import APP_VERSION, GITHUB_REPO
from .tools import NO_WINDOW


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", text)[:3]) or (0,)


def check(repo: str = GITHUB_REPO) -> dict | None:
    """Daha yeni bir sürüm varsa bilgilerini, yoksa None döndürür."""
    if not repo:
        return None
    r = requests.get(f"https://api.github.com/repos/{repo}/releases/latest", timeout=15,
                     headers={"Accept": "application/vnd.github+json", "User-Agent": "TekTikla-updater"})
    if r.status_code == 404:
        return None
    r.raise_for_status()
    release = r.json()
    latest = release.get("tag_name", "").lstrip("vV")
    if _version(latest) <= _version(APP_VERSION):
        return None
    asset = next((a for a in release.get("assets", [])
                  if a["name"].lower().endswith(".exe") and re.search(r"setup|kurulum", a["name"], re.I)), None)
    if not asset:
        return None
    return {
        "version": latest,
        "notes": (release.get("body") or "").strip()[:2000],
        "url": asset["browser_download_url"],
        "size": asset.get("size", 0),
        "digest": asset.get("digest") or "",  # "sha256:..." (GitHub bunu otomatik ekler)
        "page": release.get("html_url", ""),
    }


def download_and_run(update: dict, progress: Callable[[float], None]) -> None:
    """Kurulumu indirir, doğrular ve sessiz modda başlatır; ardından uygulama kapanmalıdır."""
    target = Path(tempfile.gettempdir()) / f"TekTikla-Setup-{update['version']}.exe"
    sha = hashlib.sha256()
    with requests.get(update["url"], stream=True, timeout=30) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length") or update.get("size") or 0)
        done = 0
        with open(target, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
                sha.update(chunk)
                done += len(chunk)
                if total:
                    progress(done / total)
    expected = update.get("digest", "")
    if expected.startswith("sha256:") and expected[7:].lower() != sha.hexdigest():
        target.unlink(missing_ok=True)
        raise RuntimeError("İndirilen güncelleme doğrulanamadı (SHA-256 uyuşmuyor).")
    # Kurulum programı /SILENT ile sessizce kurar ve TekTıkla'yı yeniden açar (installer/setup.py)
    subprocess.Popen([str(target), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
                     creationflags=NO_WINDOW | subprocess.DETACHED_PROCESS)
