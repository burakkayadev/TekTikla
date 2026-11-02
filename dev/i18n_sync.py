"""Çeviri dosyalarını koddaki güncel metinlerle eşitler.

keys.txt koddan yeniden üretilir (i18n_extract.collect); dev/i18n/<dil>.txt satırları yeni numaralarla yeniden yazılır,
var olan çeviriler Türkçe metniyle eşleşerek korunur, koddan kalkan metinlerin çevirisi silinir. Çevirisi eksik metinler
"N|metin" olarak dev/i18n_todo.txt'ye yazılır; çeviriler her dil dosyasına aynı N ile "N|çeviri" diye eklenir.

Sıra:  i18n_sync.py -> (eksikleri çevir) -> i18n_build.py
Kullanım:  .venv\\Scripts\\python.exe dev\\i18n_sync.py
"""
from __future__ import annotations

import sys
from pathlib import Path

DEV = Path(__file__).resolve().parent
SRC = DEV / "i18n"
sys.path.insert(0, str(DEV))
from i18n_extract import collect  # noqa: E402


def main() -> int:
    old_keys = (SRC / "keys.txt").read_text(encoding="utf-8").splitlines()
    keys = collect()
    index = {k: i for i, k in enumerate(keys, 1)}
    (SRC / "keys.txt").write_text("\n".join(keys) + "\n", encoding="utf-8")
    missing: set[str] = set()
    for path in sorted(SRC.glob("*.txt")):
        if path.name == "keys.txt":
            continue
        done: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            num, sep, text = line.partition("|")
            if sep and num.strip().isdigit() and 1 <= int(num) <= len(old_keys):
                done[old_keys[int(num) - 1]] = text
        rows = sorted((index[k], t) for k, t in done.items() if k in index)
        path.write_text("".join(f"{n}|{t}\n" for n, t in rows), encoding="utf-8")
        missing |= {k for k in keys if k not in done}
        print(f"{path.stem}: {len(rows)} çeviri korundu")
    todo = [f"{index[k]}|{k}" for k in keys if k in missing]
    (DEV / "i18n_todo.txt").write_text("\n".join(todo) + "\n", encoding="utf-8")
    print(f"{len(keys)} metin; çevirisi eksik {len(todo)} -> dev/i18n_todo.txt")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
