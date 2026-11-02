"""TekTıkla Android uygulamasını (android/) derler ve imzalı APK'yı Kurulum/TekTikla-Android.apk olarak bırakır.

Gerekenler (ilk kurulum D:\\Android altına yapıldı): JDK 21, Android SDK (platforms;android-36, build-tools;36.0.0)
ve Gradle 8.14. Yollar TEKTIKLA_ANDROID ortam değişkeniyle başka bir klasöre yönlendirilebilir.

Android araçları Türkçe karakterli yollarda sorun çıkarabildiği için proje önce ASCII bir çalışma klasörüne kopyalanır.
İmza anahtarı ilk derlemede oluşturulur ve depoya girmez: <TEKTIKLA_ANDROID>\\keys içinde saklanır. Bu anahtar kaybolursa
telefonlardaki uygulama güncellenemez (kaldırıp yeniden kurmak gerekir): yedeklenmeli.

Kullanım:  .venv\\Scripts\\python.exe build_apk.py
"""
from __future__ import annotations

import os
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOOLS = Path(os.environ.get("TEKTIKLA_ANDROID", r"D:\Android"))
JDK = TOOLS / "jdk-21"
SDK = TOOLS / "sdk"
GRADLE = TOOLS / "gradle-8.14.6" / "bin" / "gradle.bat"
WORK = TOOLS / "work" / "tektikla-android"
KEYS = TOOLS / "keys"
SIGNING = KEYS / "tektikla-release.properties"
OUT = ROOT / "Kurulum" / "TekTikla-Android.apk"


def version() -> tuple[str, int]:
    text = (ROOT / "tektikla" / "__init__.py").read_text(encoding="utf-8")
    name = re.search(r'APP_VERSION = "([^"]+)"', text).group(1)
    major, minor, patch = (int(x) for x in re.findall(r"\d+", name)[:3])
    return name, major * 10000 + minor * 100 + patch  # 3.0.0 -> 30000; her sürümde büyür


def env() -> dict:
    tmp = TOOLS / "tmp"  # Java'nın yerel soketleri için kısa yol (uzun TEMP yolunda Gradle açılmıyor)
    tmp.mkdir(parents=True, exist_ok=True)
    return {**os.environ, "JAVA_HOME": str(JDK), "ANDROID_HOME": str(SDK), "ANDROID_USER_HOME": str(TOOLS / "user"),
            "GRADLE_USER_HOME": str(TOOLS / "gradle-home"), "TEMP": str(tmp), "TMP": str(tmp),
            "JAVA_TOOL_OPTIONS": f"-Djdk.net.unixdomain.tmpdir={tmp} -Djava.io.tmpdir={tmp}"}


def ensure_signing() -> None:
    """İlk derlemede sürüm imza anahtarını oluşturur (şifre rastgele, yalnızca bu bilgisayarda)."""
    if SIGNING.exists():
        return
    KEYS.mkdir(parents=True, exist_ok=True)
    store = KEYS / "tektikla-release.jks"
    password = secrets.token_urlsafe(24)
    subprocess.run([str(JDK / "bin" / "keytool.exe"), "-genkeypair", "-keystore", str(store), "-alias", "tektikla",
                    "-keyalg", "RSA", "-keysize", "4096", "-validity", "10000", "-storetype", "PKCS12",
                    "-storepass", password, "-keypass", password, "-dname", "CN=TekTikla, O=BurakCNKaya, C=TR"],
                   check=True, env=env(), capture_output=True)
    SIGNING.write_text(f"storeFile={store.as_posix()}\nstorePassword={password}\nkeyAlias=tektikla\n"
                       f"keyPassword={password}\n", encoding="utf-8")
    print(f"İmza anahtarı oluşturuldu: {store} (yedekleyin)")


def sync() -> None:
    """android/ klasörünü ASCII çalışma klasörüne kopyalar (derleme önbelleği korunur)."""
    src = ROOT / "android"
    WORK.mkdir(parents=True, exist_ok=True)
    for name in ("settings.gradle", "build.gradle", "gradle.properties"):
        shutil.copy2(src / name, WORK / name)
    (WORK / "app").mkdir(exist_ok=True)
    for name in ("build.gradle", "proguard-rules.pro"):
        shutil.copy2(src / "app" / name, WORK / "app" / name)
    shutil.rmtree(WORK / "app" / "src", ignore_errors=True)
    shutil.copytree(src / "app" / "src", WORK / "app" / "src")
    (WORK / "local.properties").write_text("sdk.dir=" + SDK.as_posix().replace(":", "\\:") + "\n", encoding="utf-8")


def main() -> int:
    for need in (JDK / "bin" / "java.exe", SDK / "platforms" / "android-36", GRADLE):
        if not need.exists():
            print(f"Eksik: {need}")
            return 1
    name, code = version()
    ensure_signing()
    sync()
    print(f"Derleniyor: TekTıkla {name} (sürüm kodu {code})…", flush=True)
    result = subprocess.run([str(GRADLE), "--no-daemon", "--console=plain", "-p", str(WORK), "assembleRelease",
                             f"-Ptektikla.versionName={name}", f"-Ptektikla.versionCode={code}",
                             f"-Ptektikla.signing={SIGNING.as_posix()}"], env=env())
    if result.returncode:
        return result.returncode
    apk = WORK / "app" / "build" / "outputs" / "apk" / "release" / "app-release.apk"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(apk, OUT)
    print(f"Hazır: {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
