"""dev/i18n/<dil>.txt çevirilerini doğrulayıp tektikla/web/i18n/<dil>.json tablolarına dönüştürür.

Dosya biçimi: her satır "N|çeviri" (N = dev/i18n/keys.txt'deki satır numarası).
Kontroller: eksik/fazla satır ve {0}, {name} gibi yer tutucuların korunması.
Kullanım:  .venv\\Scripts\\python.exe dev\\i18n_build.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "dev" / "i18n"
OUT = ROOT / "tektikla" / "web" / "i18n"
PH = re.compile(r"\{\w*\}")


def build() -> int:
    keys = (SRC / "keys.txt").read_text(encoding="utf-8").splitlines()
    OUT.mkdir(parents=True, exist_ok=True)
    problems = 0
    for path in sorted(SRC.glob("*.txt")):
        if path.name == "keys.txt":
            continue
        lang = path.stem
        table: dict[str, str] = {}
        seen = set()
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            num, sep, text = line.partition("|")
            if not sep or not num.strip().isdigit():
                print(f"{lang}:{line_no}: biçim hatası: {line[:60]}")
                problems += 1
                continue
            n = int(num)
            if not 1 <= n <= len(keys):
                print(f"{lang}:{line_no}: geçersiz numara {n}")
                problems += 1
                continue
            key, text = keys[n - 1], text.strip()
            if sorted(PH.findall(key)) != sorted(PH.findall(text)):
                print(f"{lang}:{n}: yer tutucular uyuşmuyor: {key!r} -> {text!r}")
                problems += 1
            seen.add(n)
            if text and text != key:
                table[key] = text
        missing = [i for i in range(1, len(keys) + 1) if i not in seen]
        if missing:
            print(f"{lang}: {len(missing)} eksik satır: {missing[:15]}{' …' if len(missing) > 15 else ''}")
            problems += len(missing)
        (OUT / f"{lang}.json").write_text(json.dumps(table, ensure_ascii=False, indent=0), encoding="utf-8")
        print(f"{lang}: {len(table)} çeviri")
    return problems


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(1 if build() else 0)
