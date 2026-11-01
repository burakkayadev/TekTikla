"""Reels altyazıları: kelime kelime vurgulanan, animasyonlu ASS altyazı (libass ile videoya yakılır).

Stiller:
  pop      - kalın, büyük harf, konuşulan kelime renkli ve büyüyerek "zıplar" (TikTok/Hormozi tarzı)
  karaoke  - iki satırlık öbek, kelimeler konuşuldukça soldan sağa renklenir
  box      - siyah kutu içinde metin, konuşulan kelime renkli
  minimal  - sade beyaz yazı, yumuşak gölge, animasyonsuz
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .words import Word

W, H = 1080, 1920
ACCENTS = {"yellow": "00D6FF", "green": "59C734", "red": "303BFF", "blue": "FF840A", "white": "FFFFFF",
           "pink": "B45CFF"}  # ASS renkleri BBGGRR sırasıyla yazılır
POSITIONS = {"bottom": 1370, "middle": 1060, "top": 560}  # y (1920 yüksekliğinde); alt kısımda uygulama düğmeleri var

STYLE_FONTS = {"pop": "TekTikla Condensed", "karaoke": "TekTikla Display", "box": "TekTikla Display",
               "minimal": "TekTikla Black"}


@dataclass
class Options:
    style: str = "pop"
    accent: str = "yellow"
    position: str = "bottom"
    words_per_chunk: int = 3
    uppercase: bool = True
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


def _header(font: str, size: int, opts: Options) -> str:
    accent = ACCENTS.get(opts.accent, ACCENTS["yellow"])
    if opts.style == "box":
        main = f"Style: Main,{font},{size},&H00FFFFFF,&H00{accent},&H64000000,&H64000000,0,0,0,0,100,100,0,0,3,14,0,5,40,40,0,1"
    elif opts.style == "minimal":
        main = f"Style: Main,{font},{size},&H00FFFFFF,&H00{accent},&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,3,4,5,60,60,0,1"
    else:
        main = f"Style: Main,{font},{size},&H00FFFFFF,&H00{accent},&H00000000,&H78000000,0,0,0,0,100,100,1,0,1,9,5,5,50,50,0,1"
    hook = "Style: Hook,TekTikla Display,74,&H00111111,&H00111111,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,3,22,0,8,80,80,0,1"
    mark = "Style: Mark,TekTikla Black,42,&H78FFFFFF,&H00FFFFFF,&H64000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,8,40,40,0,1"
    return (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\nYCbCr Matrix: TV.709\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"{main}\n{hook}\n{mark}\nStyle: Bar,Arial,10,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def build(words: list[Word], duration: float, opts: Options, *, hook: str = "", hook_seconds: float = 3.2,
          progress_bar: bool = True, watermark: str = "") -> str:
    """Klibin tamamı için ASS metni üretir. words: klibin başına göre zamanlanmış kelimeler."""
    font = STYLE_FONTS.get(opts.style, STYLE_FONTS["pop"])
    size = {"pop": 118, "karaoke": 80, "box": 72, "minimal": 64}.get(opts.style, 100)
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
        groups = chunks(words, per, max_chars=22 if opts.style == "pop" else 34)
        for gi, group in enumerate(groups):
            g_start = group[0].start
            nxt = groups[gi + 1][0].start if gi + 1 < len(groups) else duration
            g_end = min(max(group[-1].end + 0.25, group[-1].end), nxt, duration)
            pos = f"\\an5\\pos({W // 2},{y})"
            texts = [word_text(w) for w in group]
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
    if progress_bar and duration > 0:
        ms = int(duration * 1000)
        event(0, duration, "Bar",
              f"{{\\an7\\pos(0,{H - 14})\\bord0\\shad0\\1c&H{accent}&\\fscx0\\t(0,{ms},\\fscx100)\\p1}}"
              f"m 0 0 l {W} 0 l {W} 14 l 0 14{{\\p0}}", layer=3)
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
