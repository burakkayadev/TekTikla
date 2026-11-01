"""Çevrilecek Türkçe arayüz metinlerini toplar: index.html, web/*.js ve kullanıcıya gösterilen Python mesajları.

Kullanım:  .venv\\Scripts\\python.exe dev\\i18n_extract.py > build\\i18n_keys.txt
Sayılar "{0}", "{1}" kalıbına çevrilir (çalışırken tr() aynı dönüşümü yapar).
Yeni bir metin eklenince bu betik çalıştırılıp tektikla/web/i18n/*.json tabloları tamamlanır.
"""
from __future__ import annotations

import ast
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "tektikla" / "web"
TR_CHARS = set("çğıöşüÇĞİÖŞÜâÂ")
NUM = re.compile(r"\d+(?:[.,]\d+)?")
PY_FILES = ["api.py", "studio_api.py", "engine.py", "media.py", "reels.py", "dublaj.py", "services.py",
            "imagegen.py", "tts.py", "ai.py", "transcribe.py", "words.py", "vision.py", "subtitles.py", "llm.py",
            "updater.py", "tools.py"]


HOLE = "\x00"  # şablondaki ${…} / f-string {…} yerleri; sayılarla birlikte sırayla {0}, {1}… olur
# yapay zekâya giden istem parçaları, kod dizeleri ve marka adları çevrilmez
IGNORE = re.compile(
    r"^(Amaç|En-boy oranı|Başlık dili|Hedef süre|Her klibin süresi|Süre|Başlık|Kanal|Site|Bölümler|Hedef dil|"
    r"Çevrilecek satırlar|Önceki satırlar|Video|Fikir|Dil)\b.*:|^(Bearer|Key) |Job \| None|^Successfully installed|"
    r"Aşağıdaki videoya|Şu konu/istek|^saniye \(yaklaşık|beğeni\]|^\(Bu video için konuşma|^Google Gemini$|"
    r"^Claude Haiku|^Cloudflare (Workers AI|FLUX)$|^Gemini (Nano Banana|TTS)$|^Higgsfield SOUL$|^Nano Banana \{0\} Lite|"
    r"^(Français|Türkçe|Bahasa Indonesia|Full HD|Firefox|Edge|Chrome|Brave|Opera|Vivaldi|FFmpeg|MKV|WEBM|OPUS|FLAC|WAV|"
    r"AIza…|@kullaniciadi|kbps|Gemini|Claude|Serif|Grotesk|Pop|Karaoke|Anime|Minimal|Reels|TekTıkla|AI|"
    r"JavaScript \(YouTube\)|YouTube · SponsorBlock|MP\{0\}|M\{0\}A|\{0\}D|\{0\} kbps|Language)$|"
    r"^[A-ZÀ-Ýa-zà-ýĀ-žÇĞİÖŞÜçğıöşü]+ · (Erkek|Kadın)( \(\w+\))?$")


def normalize(text: str) -> str:
    i = iter(range(99))
    return re.sub(HOLE + r"|\d+(?:[.,]\d+)?", lambda m: "{" + str(next(i)) + "}", text.strip())


def looks_ui(text: str) -> bool:
    t = text.strip()
    if len(t) < 2 or len(t) > 260 or "\n" in t:
        return False
    if t.startswith(("<", "#", ".", "-", "/", "http", "%", "[", "{\\", "data:", "\\")):
        return False
    if re.search(r"[\\%]\(|\$\{|=\w|\w=|::|\.(mp4|png|jpg|ttf|ico|json|ass|srt|wav)\b|^\w+[-_]\w+$", t):
        return False
    letters = sum(c.isalpha() for c in t)
    if letters < 2 or letters / len(t) < 0.5:
        return False
    if any(c in TR_CHARS for c in t):
        return True
    return " " in t and t[0].isupper()


class _Html(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "svg"):
            self.skip += 1
        for k, v in attrs:
            if k in ("placeholder", "title") and v:
                self.found.append(v)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "svg") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.found.append(data.strip())


def from_html() -> list[str]:
    p = _Html()
    p.feed((WEB / "index.html").read_text(encoding="utf-8"))
    return [t for t in p.found if re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]", t)]


JS_STR = re.compile(r'"((?:[^"\\\n]|\\.)*)"|\'((?:[^\'\\\n]|\\.)*)\'|`((?:[^`\\]|\\.)*)`')


def _strip_js_comments(src: str) -> str:
    out, i, quote = [], 0, None
    while i < len(src):
        ch = src[i]
        if quote:
            out.append(ch)
            if ch == "\\":
                out.append(src[i + 1:i + 2])
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
            out.append(ch)
        elif src.startswith("//", i):
            i = src.find("\n", i)
            i = len(src) if i < 0 else i
            continue
        elif src.startswith("/*", i):
            i = src.find("*/", i) + 2 or len(src)
            continue
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def from_js(path: Path) -> list[str]:
    out = []
    for m in JS_STR.finditer(_strip_js_comments(path.read_text(encoding="utf-8"))):
        raw = m.group(1) if m.group(1) is not None else m.group(2) if m.group(2) is not None else m.group(3)
        if m.group(3) is not None:
            if "\n" in raw or "\\n" in raw:
                continue
            raw = re.sub(r"\$\{[^}]*\}", HOLE, raw)
        raw = raw.replace("\\'", "'").replace('\\"', '"')
        if "\\n" not in raw and looks_ui(raw.replace(HOLE, "1")):
            out.append(raw)
    return out


def _fstring(node: ast.JoinedStr) -> str:
    return "".join(str(v.value) if isinstance(v, ast.Constant) else HOLE for v in node.values)


def from_python(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip: set[int] = set()
    for node in ast.walk(tree):  # belge dizeleri ve Field(description=...) çevrilmez
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                skip.add(id(first.value))
        if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", "")) == "Field":
            for kw in node.keywords:
                skip.add(id(kw.value))
        if isinstance(node, ast.JoinedStr):  # f-string'in parçaları ayrıca sayılmasın
            skip.update(id(v) for v in node.values)
            for v in node.values:
                if isinstance(v, ast.FormattedValue):
                    skip.update(id(x) for x in ast.walk(v))
    out = []
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, ast.JoinedStr):
            text = _fstring(node)
            if "\n" not in text and looks_ui(text.replace(HOLE, "1")):
                out.append(text)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and looks_ui(node.value):
            out.append(node.value)
    return out


def collect() -> list[str]:
    found = from_html()
    for js in ("app.js", "studio.js"):
        found += from_js(WEB / js)
    for py in PY_FILES:
        found += from_python(ROOT / "tektikla" / py)
    keys, seen = [], set()
    for text in found:
        key = text.strip() if re.search(r"\{[a-z_]+\}", text) else normalize(text)
        if key and key not in seen and not IGNORE.search(key) and key.strip("{}0123456789 ·"):
            seen.add(key)
            keys.append(key)
    for extra in EXTRA:
        if extra not in seen:
            keys.append(extra)
    return keys


# Parça parça çevrilen metinler (ses adlarındaki cinsiyet ve Gemini ses tarifleri)
EXTRA = ["Erkek", "Kadın", "net", "neşeli", "bilgilendirici", "ferah", "heyecanlı", "genç", "kararlı", "parlak",
         "sıcak", "olgun", "samimi", "nazik", "Ayrıntı"]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    keys = collect()
    print("\n".join(keys))
    print(f"# {len(keys)} metin", file=sys.stderr)
