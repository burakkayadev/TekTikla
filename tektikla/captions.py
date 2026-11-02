"""Reels altyazıları: kelime kelime vurgulanan, animasyonlu ASS altyazı (libass ile videoya yakılır).

Stiller:
  clean    - sade ve özenli: konuşulan kelimenin arkasında yuvarlak vurgu kayar (varsayılan)
  pop      - kalın, büyük harf, konuşulan kelime renkli ve büyüyerek "zıplar" (TikTok/Hormozi tarzı)
  karaoke  - iki satırlık öbek, kelimeler konuşuldukça soldan sağa renklenir
  box      - siyah kutu içinde metin, konuşulan kelime renkli
  minimal  - sade beyaz yazı, yumuşak gölge, animasyonsuz
Kanca başlığı ayrıca PNG kart olarak çizilir (hook_card) ve videoya kayarak gelir.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .imagegen import FONTS_DIR
from .words import Word

W, H = 1080, 1920
ACCENTS = {"yellow": "00D6FF", "green": "59C734", "red": "303BFF", "blue": "FF840A", "white": "FFFFFF",
           "pink": "B45CFF"}  # ASS renkleri BBGGRR sırasıyla yazılır
LIGHT_ACCENTS = {"yellow", "green", "white"}  # üstündeki yazı koyu olur
POSITIONS = {"bottom": 1370, "middle": 1060, "top": 560}  # y (1920 yüksekliğinde); alt kısımda uygulama düğmeleri var
STYLES = ("clean", "pop", "karaoke", "box", "minimal", "none")
STYLE_FONTS = {"clean": "TekTikla Display", "pop": "TekTikla Condensed", "karaoke": "TekTikla Display",
               "box": "TekTikla Display", "minimal": "TekTikla Black"}
FONT_FILES = {"TekTikla Display": "TekTikla-Display.ttf", "TekTikla Condensed": "TekTikla-Condensed.ttf",
              "TekTikla Black": "TekTikla-Black.ttf"}
CLEAN_SIZE = 112  # ASS boyutu = fontun Win yüksekliği (1.56 em): em ~72 px
CLEAN_MAX_W = 940  # temiz stilde satır genişliği; aşarsa iki satıra bölünür


@dataclass
class Options:
    style: str = "clean"
    accent: str = "yellow"
    position: str = "bottom"
    words_per_chunk: int = 3
    uppercase: bool = False
    lang: str = "tr"


def _ts(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _clean(text: str) -> str:
    return re.sub(r"[{}\\]", "", text).replace("\n", " ").strip()


def _upper(text: str, lang: str) -> str:
    if lang in ("tr", "az"):
        text = text.replace("i", "İ").replace("ı", "I")
    return text.upper()


def chunks(words: list[Word], max_words: int, max_chars: int = 22, gap: float = 0.45) -> list[list[Word]]:
    """Kelimeleri ekranda birlikte görünecek küçük öbeklere ayırır."""
    out: list[list[Word]] = []
    cur: list[Word] = []
    for w in words:
        text_len = sum(len(x.text) + 1 for x in cur) + len(w.text)
        if cur and (len(cur) >= max_words or text_len > max_chars or w.start - cur[-1].end > gap):
            out.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.!?…,;:]$", w.text) and len(cur) >= 2:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


# ----------------------------------------------------------------------------- ölçü (libass ile aynı genişlik)

@lru_cache(maxsize=8)
def measure_font(name: str, ass_size: float) -> ImageFont.FreeTypeFont:
    """libass yazı boyutunu fontun (usWinAscent + usWinDescent) yüksekliği olarak alır, PIL ise em boyutu olarak.
    Kelime genişliklerini videodakiyle aynı ölçmek için em boyutuna çevrilir."""
    path = FONTS_DIR / FONT_FILES[name]
    tt = TTFont(str(path), lazy=True)
    os2, head = tt["OS/2"], tt["head"]
    cell = (os2.usWinAscent + os2.usWinDescent) or (tt["hhea"].ascent - tt["hhea"].descent)
    return ImageFont.truetype(str(path), ass_size * head.unitsPerEm / cell)


def _layout(widths: list[float], space: float, max_w: float) -> list[list[tuple[int, float, float]]]:
    """Kelimeleri ortalanmış satırlara dizer: her satır için (kelime sırası, sol x, genişlik)."""
    n = len(widths)
    if n == 1 or sum(widths) + space * (n - 1) <= max_w:
        rows = [list(range(n))]
    else:  # en dengeli ikiye bölme
        k = min(range(1, n), key=lambda k: abs(sum(widths[:k]) - sum(widths[k:])))
        rows = [list(range(k)), list(range(k, n))]
    out = []
    for row in rows:
        x = W / 2 - (sum(widths[i] for i in row) + space * (len(row) - 1)) / 2
        items = []
        for i in row:
            items.append((i, x, widths[i]))
            x += widths[i] + space
        out.append(items)
    return out


def _pill(w: float, h: float, r: float) -> str:
    """Yuvarlak köşeli dikdörtgen (ASS çizimi, sol üst köşe 0,0)."""
    w, h = round(w), round(h)
    r = round(min(r, h / 2, w / 2))
    c = round(r * 0.5523)  # çeyrek çember için Bézier kolu
    return (f"m {r} 0 l {w - r} 0 b {w - r + c} 0 {w} {r - c} {w} {r} l {w} {h - r} "
            f"b {w} {h - r + c} {w - r + c} {h} {w - r} {h} l {r} {h} b {r - c} {h} 0 {h - r + c} 0 {h - r} "
            f"l 0 {r} b 0 {r - c} {r - c} 0 {r} 0")


# ----------------------------------------------------------------------------- ASS

def _header(font: str, size: int, opts: Options) -> str:
    accent = ACCENTS.get(opts.accent, ACCENTS["yellow"])
    if opts.style == "box":
        main = f"Style: Main,{font},{size},&H00FFFFFF,&H00{accent},&H64000000,&H64000000,0,0,0,0,100,100,0,0,3,14,0,5,40,40,0,1"
    elif opts.style == "minimal":
        main = f"Style: Main,{font},{size},&H00FFFFFF,&H00{accent},&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,3,4,5,60,60,0,1"
    elif opts.style == "clean":  # ince, yarı saydam kenar + yumuşatma: kalın siyah çerçeve yerine hafif bir hale
        main = f"Style: Main,{font},{size},&H00FFFFFF,&H00FFFFFF,&H70000000,&H00000000,0,0,0,0,100,100,0,0,1,2.4,0,4,0,0,0,1"
    else:
        main = f"Style: Main,{font},{size},&H00FFFFFF,&H00{accent},&H00000000,&H78000000,0,0,0,0,100,100,1,0,1,9,5,5,50,50,0,1"
    hook = "Style: Hook,TekTikla Display,74,&H00111111,&H00111111,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,3,22,0,8,80,80,0,1"
    mark = "Style: Mark,TekTikla Black,40,&H70FFFFFF,&H00FFFFFF,&H64000000,&H00000000,0,0,0,0,100,100,0,0,1,1.5,0,8,40,40,0,1"
    return (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\nYCbCr Matrix: TV.709\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"{main}\n{hook}\n{mark}\nStyle: Bar,Arial,10,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def _clean_group(event, group: list[Word], texts: list[str], g_end: float, opts: Options, y: int) -> None:
    """Temiz stil: öbekteki kelimeler sabit durur, vurgu kutusu konuşulan kelimeye kayarak geçer."""
    s = CLEAN_SIZE
    font = measure_font(STYLE_FONTS["clean"], s)
    pad_x, pad_y = round(s * 0.15), round(s * 0.09)
    # vurgu kutusu iki kelime arasındaki boşluğa taşar: boşluk, kutunun dolgusundan geniş olmalı
    space = pad_x + font.getlength(" ") * 0.9
    rows = _layout([font.getlength(t) for t in texts], space, CLEAN_MAX_W)
    line_h = s * 0.86
    boxes: dict[int, tuple[float, float, float]] = {}
    for r, items in enumerate(rows):
        cy = y + (r - (len(rows) - 1) / 2) * line_h
        for i, x, w in items:
            boxes[i] = (x, cy, w)
    accent = ACCENTS.get(opts.accent, ACCENTS["yellow"])
    ink = "161616" if opts.accent in LIGHT_ACCENTS else "FFFFFF"  # vurgu üstündeki yazı rengi
    # \an4'te yazının dikey ortası font kutusunun (usWinAscent/Descent) ortasıdır; görünen harfler (büyük harf
    # tepesi - kuyruk dibi) bunun 0.22s üstünden 0.385s altına uzanır
    pill_h = round(s * 0.6 + 2 * pad_y)

    def pill_at(i: int) -> tuple[int, int, float]:
        x, cy, w = boxes[i]
        return round(x - pad_x), round(cy - s * 0.2175 - pad_y), w + 2 * pad_x

    for i, w in enumerate(group):
        start = w.start if i else group[0].start
        end = group[i + 1].start if i + 1 < len(group) else g_end
        px, py, pw = pill_at(i)
        if i:  # önceki kelimeden kayarak ve genişliğini değiştirerek gelir
            qx, qy, qw = pill_at(i - 1)
            anim = f"\\move({qx},{qy},{px},{py},0,120)\\fscx{qw / pw * 100:.1f}\\t(0,120,\\fscx100)"
        else:
            anim = f"\\pos({px},{py})\\fad(90,0)"
        event(start, end, "Main", f"{{\\an7{anim}\\bord0\\shad0\\blur0.7\\1c&H{accent}&\\p1}}{_pill(pw, pill_h, s * 0.2)}{{\\p0}}", 1)
        for k, t in enumerate(texts):
            kx, kcy, _w = boxes[k]
            x, yy = round(kx), round(kcy)
            place = f"\\move({x},{yy + 16},{x},{yy},0,150)\\fad(90,0)" if i == 0 else f"\\pos({x},{yy})"
            if k == i:  # vurgu kutusu kayarak gelirken yazı da aynı anda koyulaşır (arada okunmaz kalmasın)
                look = f"\\bord0\\blur0\\1c&H{ink}&" if i == 0 else f"\\bord0\\blur0\\t(0,120,\\1c&H{ink}&)"
            else:
                look = "\\blur1.2"
            event(start, end, "Main", f"{{\\an4{place}{look}}}{t}", 2)


def build(words: list[Word], duration: float, opts: Options, *, hook: str = "", hook_seconds: float = 3.2,
          progress_bar: bool = False, watermark: str = "") -> str:
    """Klibin tamamı için ASS metni üretir. words: klibin başına göre zamanlanmış kelimeler."""
    font = STYLE_FONTS.get(opts.style, STYLE_FONTS["clean"])
    size = {"clean": CLEAN_SIZE, "pop": 118, "karaoke": 80, "box": 72, "minimal": 64}.get(opts.style, 100)
    accent = ACCENTS.get(opts.accent, ACCENTS["yellow"])
    y = POSITIONS.get(opts.position, POSITIONS["bottom"])
    lines = [_header(font, size, opts)]

    def event(start: float, end: float, style: str, text: str, layer: int = 0) -> None:
        if end - start >= 0.02:
            lines.append(f"Dialogue: {layer},{_ts(start)},{_ts(end)},{style},,0,0,0,,{text}")

    def word_text(w: Word) -> str:
        t = _clean(w.text)
        return _upper(t, opts.lang) if opts.uppercase and opts.style != "minimal" else t

    if opts.style != "none" and words:
        per = max(1, min(opts.words_per_chunk, 6))
        if opts.style == "karaoke":
            per = max(per, 5)
        groups = chunks(words, per, max_chars=22 if opts.style in ("pop", "clean") else 34)
        for gi, group in enumerate(groups):
            g_start = group[0].start
            nxt = groups[gi + 1][0].start if gi + 1 < len(groups) else duration
            g_end = min(max(group[-1].end + 0.25, group[-1].end), nxt, duration)
            pos = f"\\an5\\pos({W // 2},{y})"
            texts = [word_text(w) for w in group]
            if opts.style == "clean":
                _clean_group(event, group, texts, g_end, opts, y)
                continue
            if opts.style == "karaoke":
                parts = []
                for i, w in enumerate(group):
                    dur = (group[i + 1].start if i + 1 < len(group) else w.end) - w.start
                    parts.append(f"{{\\kf{max(1, int(dur * 100))}}}{texts[i]}")
                body = " ".join(parts)
                # karaokede ana renk (Primary) dolarken görünen renktir: vurgu rengi dolsun
                event(g_start, g_end, "Main",
                      f"{{{pos}\\1c&H{accent}&\\2c&HFFFFFF&\\fad(60,60)}}" + body)
                continue
            if opts.style == "minimal":
                event(g_start, g_end, "Main", f"{{{pos}\\fad(80,80)}}" + " ".join(texts))
                continue
            for i, w in enumerate(group):
                start = w.start if i else g_start
                end = group[i + 1].start if i + 1 < len(group) else g_end
                parts = []
                for j, t in enumerate(texts):
                    if j == i:
                        pop = "\\fscx112\\fscy112\\t(0,90,\\fscx122\\fscy122)\\t(90,180,\\fscx112\\fscy112)" \
                            if opts.style == "pop" else ""
                        parts.append(f"{{\\1c&H{accent}&{pop}}}{t}{{\\1c&HFFFFFF&\\fscx100\\fscy100}}")
                    else:
                        parts.append(t)
                intro = "\\fad(40,0)" if i == 0 else ""
                event(start, end, "Main", f"{{{pos}{intro}}}" + " ".join(parts))

    if hook:
        text = _clean(hook)
        text = _upper(text, opts.lang) if opts.uppercase else text
        event(0, min(hook_seconds, duration), "Hook",
              f"{{\\an8\\pos({W // 2},250)\\fad(120,220)\\fscx80\\fscy80\\t(0,160,\\fscx104\\fscy104)"
              f"\\t(160,260,\\fscx100\\fscy100)}}{_wrap(text, 24)}", layer=2)
    if watermark:
        event(0, duration, "Mark", f"{{\\an8\\pos({W // 2},140)}}{_clean(watermark)}", layer=1)
    if progress_bar and duration > 0:  # ince ve yarı saydam: dikkati altyazıdan çalmasın
        ms = int(duration * 1000)
        event(0, duration, "Bar",
              f"{{\\an7\\pos(0,{H - 8})\\bord0\\shad0\\1c&H{accent}&\\1a&H40&\\fscx0\\t(0,{ms},\\fscx100)\\p1}}"
              f"m 0 0 l {W} 0 l {W} 8 l 0 8{{\\p0}}", layer=3)
    return "\n".join(lines) + "\n"


def _wrap(text: str, width: int) -> str:
    out, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            out.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        out.append(cur)
    return "\\N".join(out[:3])


# ----------------------------------------------------------------------------- kanca kartı

def hook_card(text: str, lang: str, path: Path, uppercase: bool = False) -> tuple[int, int]:
    """Kanca başlığı: beyaz, yuvarlak köşeli, yumuşak gölgeli kart (şeffaf PNG). Boyutunu döndürür."""
    s = 2  # iki kat büyük çizilip küçültülür: kenarlar pürüzsüz olur
    font = ImageFont.truetype(str(FONTS_DIR / FONT_FILES["TekTikla Display"]), 58 * s)
    text = _clean(text)
    text = _upper(text, lang) if uppercase else text
    max_w = 800 * s
    rows, cur = [], ""
    for word in text.split():
        cand = f"{cur} {word}".strip()
        if cur and font.getlength(cand) > max_w:
            rows.append(cur)
            cur = word
        else:
            cur = cand
    if cur:
        rows.append(cur)
    rows = rows[:3] or [""]
    asc, desc = font.getmetrics()
    line_h = round((asc + desc) * 1.0)
    pad_x, pad_y, margin = 44 * s, 26 * s, 46 * s
    w = round(max(font.getlength(r) for r in rows)) + 2 * pad_x
    h = line_h * len(rows) + 2 * pad_y
    img = Image.new("RGBA", (w + 2 * margin, h + 2 * margin), (0, 0, 0, 0))
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([margin, margin + 14 * s, margin + w, margin + h + 14 * s], 34 * s,
                                             fill=(0, 0, 0, 110))
    img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(22 * s)))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([margin, margin, margin + w, margin + h], 34 * s, fill=(255, 255, 255, 255))
    for i, row in enumerate(rows):
        draw.text((margin + (w - font.getlength(row)) / 2, margin + pad_y + i * line_h), row, font=font,
                  fill=(17, 17, 17, 255))
    out = img.resize((img.width // s, img.height // s), Image.LANCZOS)
    out.save(path)
    return out.size
