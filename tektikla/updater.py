"""GitHub Releases üzerinden TekTıkla güncellemesi.

Yeni sürüm yayınlamak: GitHub'da v2.2.1 gibi bir etiketle Release oluşturup `Kurulum` klasöründeki iki
dosyayı ekleyin: `TekTikla-<sürüm>-win64.zip` (uygulama içi güncelleme bunu kullanır) ve
`TekTikla-Setup-<sürüm>.exe` (ilk kurulum için).

Güncelleme kurulum programı çalıştırmaz: zip'i indirir, kurulum klasörünün yanına açar ve uygulama
kapanınca Windows'un kendi PowerShell'i ile klasörleri değiştirir. Windows Defender'ın imzasız,
tek dosyalık kurulum programlarını Temp klasöründe engellemesi bu yüzden güncellemeyi bozmaz.
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
import shutil
import subprocess
import sys
import winreg
import zipfile
from pathlib import Path
from typing import Callable

import requests

from . import APP_VERSION, GITHUB_REPO
from .config import FROZEN, LOCAL_DIR
from .tools import NO_WINDOW

UPDATES_DIR = LOCAL_DIR / "updates"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\TekTikla"
BLOCKED_HELP = ("Windows Defender veya bir güvenlik programı güncelleme dosyasını engelledi. Güncellemeyi "
                "GitHub sayfasından elle indirip kurabilirsiniz.")

# Uygulama kapandıktan sonra klasörleri değiştirir; bir şey ters giderse eski sürümü geri koyar.
SWAP_SCRIPT = r"""
$ErrorActionPreference = 'SilentlyContinue'
Wait-Process -Id ([int]$env:TT_PID) -Timeout 60
$dir = $env:TT_DIR; $new = $env:TT_NEW; $old = $dir + '.old'
Remove-Item -LiteralPath $old -Recurse -Force
$moved = $false
for ($i = 0; $i -lt 40 -and -not $moved; $i++) {
  try { Move-Item -LiteralPath $dir -Destination $old -ErrorAction Stop; $moved = $true }
  catch { Start-Sleep -Milliseconds 750 }
}
if ($moved) {
  try { Move-Item -LiteralPath $new -Destination $dir -ErrorAction Stop }
  catch { Move-Item -LiteralPath $old -Destination $dir }
}
Start-Process -FilePath (Join-Path $dir $env:TT_EXE) -WorkingDirectory $dir
Start-Sleep -Seconds 3
Remove-Item -LiteralPath $old -Recurse -Force
Remove-Item -LiteralPath $env:TT_WORK -Recurse -Force
"""


class UpdateError(Exception):
    pass


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", text)[:3]) or (0,)


def _asset(a: dict) -> dict:
    return {"url": a["browser_download_url"], "size": a.get("size", 0),
            "digest": a.get("digest") or ""}  # "sha256:..." (GitHub bunu otomatik ekler)


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
    assets = release.get("assets", [])
    zip_asset = next((a for a in assets if re.search(r"-win64\.zip$", a["name"], re.I)), None)
    setup = next((a for a in assets
                  if a["name"].lower().endswith(".exe") and re.search(r"setup|kurulum", a["name"], re.I)), None)
    if not zip_asset and not setup:
        return None
    return {
        "version": latest,
        "notes": (release.get("body") or "").strip()[:2000],
        "zip": _asset(zip_asset) if zip_asset else None,
        "setup": _asset(setup) if setup else None,
        "page": release.get("html_url", ""),
    }


def _download(asset: dict, target: Path, progress: Callable[[float], None]) -> None:
    sha = hashlib.sha256()
    try:
        with requests.get(asset["url"], stream=True, timeout=30) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length") or asset.get("size") or 0)
            done = 0
            with open(target, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
                    sha.update(chunk)
                    done += len(chunk)
                    if total:
                        progress(done / total)
    except PermissionError:
        raise UpdateError(BLOCKED_HELP) from None
    except requests.RequestException:
        raise UpdateError("Güncelleme indirilemedi. İnternet bağlantınızı kontrol edin.") from None
    expected = asset.get("digest", "")
    if expected.startswith("sha256:") and expected[7:].lower() != sha.hexdigest():
        target.unlink(missing_ok=True)
        raise UpdateError("İndirilen güncelleme doğrulanamadı (SHA-256 uyuşmuyor).")


def install_zip(zip_path: Path, install_dir: Path, exe_name: str, pid: int, version: str,
                progress: Callable[[float], None] = lambda f: None) -> None:
    """Zip'i kurulum klasörünün yanına açar ve uygulama kapanınca yer değiştirecek betiği başlatır."""
    staging = install_dir.with_name(install_dir.name + ".new")
    shutil.rmtree(staging, ignore_errors=True)
    try:
        with zipfile.ZipFile(zip_path) as z:
            members = z.infolist()
            for i, m in enumerate(members, 1):
                z.extract(m, staging)
                progress(i / len(members))
    except PermissionError:
        shutil.rmtree(staging, ignore_errors=True)
        raise UpdateError(BLOCKED_HELP) from None
    if not (staging / exe_name).exists():
        shutil.rmtree(staging, ignore_errors=True)
        raise UpdateError("Güncelleme paketi eksik veya bozuk.")
    # kaldırıcı zip'te yok; kurulumun kopyaladığını yeni klasöre taşı
    if (install_dir / "uninstall.exe").exists():
        shutil.copy2(install_dir / "uninstall.exe", staging / "uninstall.exe")
    try:  # "Uygulamalar" listesinde yeni sürüm görünsün
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "DisplayVersion", 0, winreg.REG_SZ, version)
    except OSError:
        pass
    env = dict(os.environ, TT_PID=str(pid), TT_DIR=str(install_dir), TT_NEW=str(staging), TT_EXE=exe_name,
               TT_WORK=str(zip_path.parent))
    subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand",
                      base64.b64encode(SWAP_SCRIPT.encode("utf-16-le")).decode()],
                     env=env, cwd=str(install_dir.parent),
                     # DETACHED_PROCESS değil: konsolsuz kalan PowerShell hiçbir şey yapmadan kapanıyor
                     creationflags=NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)


def apply(update: dict, progress: Callable[[float], None]) -> None:
    """Güncellemeyi indirip kurulumu başlatır; ardından uygulama kapanmalıdır."""
    if not FROZEN:
        raise UpdateError("Kaynak koddan çalışırken otomatik güncelleme yapılmaz; git pull kullanın.")
    shutil.rmtree(UPDATES_DIR, ignore_errors=True)
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    if update.get("zip"):
        zip_path = UPDATES_DIR / f"TekTikla-{update['version']}-win64.zip"
        _download(update["zip"], zip_path, lambda f: progress(f * 0.85))
        install_zip(zip_path, Path(sys.executable).parent, Path(sys.executable).name, os.getpid(),
                    update["version"], lambda f: progress(0.85 + f * 0.15))
    elif update.get("setup"):  # eski sürümler yalnızca kurulum dosyası yayınlıyordu
        target = UPDATES_DIR / f"TekTikla-Setup-{update['version']}.exe"
        _download(update["setup"], target, progress)
        try:
            subprocess.Popen([str(target), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
                             creationflags=NO_WINDOW | subprocess.DETACHED_PROCESS)
        except OSError:
            raise UpdateError(BLOCKED_HELP) from None
    else:
        raise UpdateError("Bu sürümde indirilebilir bir güncelleme dosyası yok.")
