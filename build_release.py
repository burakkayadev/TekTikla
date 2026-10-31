"""TekTıkla sürüm paketini üretir:

    1. dist\\TekTikla\\           uygulama (PyInstaller, klasör halinde — hızlı açılır, antivirüs dostu)
    2. build\\payload.zip    uygulamanın sıkıştırılmış hali
    3. Kurulum\\TekTikla-Setup-<sürüm>.exe   payload'ı içeren kurulum programı

Kullanım:  .venv\\Scripts\\python.exe build_release.py
Sürüm numarası tektikla/__init__.py içindeki APP_VERSION'dan alınır.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
DIST = ROOT / "dist"
OUT = ROOT / "Kurulum"
sys.path.insert(0, str(ROOT))

from tektikla import APP_VERSION  # noqa: E402
from tektikla.app import ensure_icon  # noqa: E402
from PIL import Image  # noqa: E402

VERSION_TEMPLATE = """VSVersionInfo(
  ffi=FixedFileInfo(filevers={t}, prodvers={t}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041F04B0', [
      StringStruct('CompanyName', 'TekTıkla'),
      StringStruct('FileDescription', '{desc}'),
      StringStruct('FileVersion', '{v}'),
      StringStruct('InternalName', '{name}'),
      StringStruct('OriginalFilename', '{name}.exe'),
      StringStruct('ProductName', 'TekTıkla'),
      StringStruct('ProductVersion', '{v}')])]),
    VarFileInfo([VarStruct('Translation', [0x041F, 1200])])
  ]
)
"""


def version_file(name: str, desc: str) -> Path:
    parts = [int(p) for p in APP_VERSION.split(".")][:3]
    t = tuple(parts + [0] * (4 - len(parts)))
    path = BUILD / f"version_{name}.txt"
    path.write_text(VERSION_TEMPLATE.format(t=t, v=APP_VERSION, name=name, desc=desc), encoding="utf-8")
    return path


def pyinstaller(*args: str) -> None:
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "WARN", *args],
                   check=True, cwd=ROOT)


def main() -> None:
    BUILD.mkdir(exist_ok=True)
    icon = ensure_icon()

    print(f"[1/3] Uygulama derleniyor (v{APP_VERSION})…")
    shutil.rmtree(DIST / "TekTikla", ignore_errors=True)
    pyinstaller(
        "--onedir", "--windowed", "--name", "TekTikla", "--contents-directory", "_internal",
        "--icon", str(icon), "--version-file", str(version_file("TekTikla", "TekTıkla - Video İndirici")),
        "--add-data", f"{ROOT / 'assets'};assets",
        "--add-data", f"{ROOT / 'tektikla' / 'web'};tektikla/web",
        "--collect-all", "yt_dlp_ejs", "--collect-all", "pywhispercpp", "--hidden-import", "_pywhispercpp",
        "--workpath", str(BUILD / "work-app"), "--specpath", str(BUILD), "--distpath", str(DIST),
        str(ROOT / "tektikla.py"),
    )

    print("[2/3] Paketleniyor…")
    payload = BUILD / "payload.zip"
    app_dir = DIST / "TekTikla"
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(app_dir.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(app_dir))

    OUT.mkdir(exist_ok=True)
    # uygulama içi güncellemeler bu zip'i kullanır (kurulum programını çalıştırmadan, Defender dostu)
    shutil.copyfile(payload, OUT / f"TekTikla-{APP_VERSION}-win64.zip")

    print("[3/3] Kurulum programı derleniyor…")
    stub_dir = BUILD / "installer"
    stub_dir.mkdir(exist_ok=True)
    (stub_dir / "_version.py").write_text(f'VERSION = "{APP_VERSION}"\n', encoding="utf-8")
    logo72 = stub_dir / "logo72.png"  # kurulum penceresinin başlığındaki logo
    Image.open(ROOT / "assets" / "tektikla.png").resize((72, 72), Image.LANCZOS).save(logo72)
    font = ROOT / "tektikla" / "web" / "fonts" / "Geist.ttf"
    OUT.mkdir(exist_ok=True)
    setup_name = f"TekTikla-Setup-{APP_VERSION}"
    pyinstaller(
        "--onefile", "--windowed", "--name", setup_name,
        "--icon", str(icon), "--version-file", str(version_file(setup_name, "TekTıkla Kurulumu")),
        "--add-data", f"{payload};.", "--add-data", f"{icon};.",
        "--add-data", f"{logo72};.", "--add-data", f"{font};.",
        "--paths", str(stub_dir), "--hidden-import", "_version",
        "--workpath", str(BUILD / "work-setup"), "--specpath", str(BUILD), "--distpath", str(OUT),
        str(ROOT / "installer" / "setup.py"),
    )
    (OUT / "OKU BENİ.txt").write_text(
        f"TekTıkla v{APP_VERSION} — Bütün sitelerden video indirici\r\n\r\n"
        f"Kurmak için {setup_name}.exe dosyasına çift tıklayın ve \"Kur\"a basın.\r\n"
        "Yönetici izni gerekmez. TekTıkla, Başlat menüsüne ve masaüstüne eklenir.\r\n\r\n"
        "Windows \"Bilinmeyen yayımcı\" uyarısı verirse: Ek bilgi > Yine de çalıştır.\r\n"
        "İlk açılışta FFmpeg gibi gerekli bileşenler otomatik indirilir (internet gerekir).\r\n"
        "Kaldırmak için: Ayarlar > Uygulamalar > TekTıkla > Kaldır.\r\n\r\n"
        f"Kurulum programı açılmazsa (Defender engellerse): TekTikla-{APP_VERSION}-win64.zip dosyasını bir "
        "klasöre çıkarıp içindeki TekTikla.exe'yi çalıştırın (kurulumsuz, taşınabilir sürüm).\r\n",
        encoding="utf-8-sig",
    )
    size = (OUT / f"{setup_name}.exe").stat().st_size / 1e6
    print(f"\nHazır: {OUT / (setup_name + '.exe')}  ({size:.0f} MB)")


if __name__ == "__main__":
    main()
