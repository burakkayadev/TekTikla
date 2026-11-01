"""Görsel Stüdyo: fikirden görsel üretme ve kapak (thumbnail) tasarlama.

Görseli bir servis üretir (ücretsizler önce), üzerine başlığı TekTıkla kendisi yazar: görsel modelleri
yazıyı çoğu zaman bozduğu için başlık her zaman net, kalın ve okunaklı olur.
Claude görsel çizemez; Claude ya da Gemini seçiliyse fikri ayrıntılı bir görsel istemine ve kapak başlığına çevirir.
"""
from __future__ import annotations

import io
import random
import re
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pydantic import BaseModel, Field

from . import llm, services
from .config import APP_DIR

PROVIDERS = {  # ücretsizden ücretliye
    "pollinations": {"name": "Pollinations", "tier": "free", "needs": None},
    "cloudflare": {"name": "Cloudflare FLUX", "tier": "free_quota", "needs": "cloudflare"},
    "gemini": {"name": "Gemini Nano Banana", "tier": "paid", "needs": "gemini"},
    "higgsfield": {"name": "Higgsfield SOUL", "tier": "paid", "needs": "higgsfield"},
}
ASPECTS = {"16:9": (1280, 720), "9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350)}
GEN_SIZES = {"16:9": (1344, 768), "9:16": (768, 1344), "1:1": (1024, 1024), "4:5": (896, 1120)}
STYLES = {
    "auto": "",
    "photo": "photorealistic photograph, natural light, 35mm, sharp focus, high detail",
    "cinematic": "cinematic film still, dramatic lighting, shallow depth of field, rich color grading",
    "illustration": "modern flat illustration, bold shapes, clean vector lines, vibrant palette",
    "anime": "anime style, vibrant colors, detailed background, studio quality",
    "3d": "3D render, soft studio lighting, glossy materials, octane render",
    "minimal": "minimalist composition, clean background, lots of negative space, soft colors",
}
FONTS_DIR = APP_DIR / "tektikla" / "web" / "fonts" if (APP_DIR / "tektikla" / "web").exists() \
    else Path(__file__).parent / "web" / "fonts"
ACCENTS = {"yellow": (255, 214, 10), "red": (255, 59, 48), "green": (52, 199, 89), "blue": (10, 132, 255),
           "white": (255, 255, 255)}


class ImagePlan(BaseModel):
    prompt: str = Field(description="Görsel modeli için ayrıntılı İNGİLİZCE istem: konu, ortam, ışık, kompozisyon, "
                                    "renkler. Görselin içinde hiçbir yazı/harf olmasın.")
    title: str = Field(description="Kapağın üstüne yazılacak kısa, çarpıcı başlık; en fazla 5 kelime, istenen dilde")
    subtitle: str = Field(description="İsteğe bağlı çok kısa ikinci satır (en fazla 5 kelime) ya da boş metin")


PLAN_SYSTEM = """Sen bir YouTube/Instagram kapak tasarımcısı ve görsel istem (prompt) uzmanısın.
Kullanıcının fikrinden: (1) metinden görsel üreten bir model için ayrıntılı İngilizce istem, (2) kapağa yazılacak
kısa ve merak uyandıran bir başlık çıkar.
Kurallar:
- İstemde görselin içine yazı, logo, harf koyma; başlığı biz ayrıca ekleyeceğiz.
- Kapak için: tek ve güçlü bir odak nesnesi/yüz, yüksek kontrast, başlık için bir tarafta sade boşluk bırak.
- Başlık clickbait olmasın ama merak uyandırsın; en fazla 5 kelime."""


def plan(idea: str, *, purpose: str, style: str, aspect: str, provider: str, api_key: str,
         language: str = "Türkçe") -> ImagePlan:
    """Fikri görsel istemine ve başlığa çevirir. Yapay zekâ anahtarı yoksa fikri olduğu gibi kullanır."""
    style_text = STYLES.get(style, "")
    if api_key:
        prompt = (f"Amaç: {'kapak (thumbnail)' if purpose == 'thumbnail' else 'görsel'}\n"
                  f"En-boy oranı: {aspect}\nStil: {style_text or 'konuya en uygun stil'}\n"
                  f"Başlık dili: {language}\n\nFikir:\n{idea.strip()[:2000]}")
        try:
            result = llm.generate(provider, api_key, PLAN_SYSTEM, prompt, ImagePlan, effort="low")
            if style_text and style_text not in result.prompt:
                result.prompt += ", " + style_text
            return result
        except llm.AIError:
            raise
        except Exception:  # noqa: BLE001 - istem iyileştirme başarısızsa fikirle devam
            pass
    words = idea.strip().split()
    return ImagePlan(prompt=", ".join(x for x in (idea.strip(), style_text) if x),
                     title=" ".join(words[:5]), subtitle="")


def generate(provider: str, prompt: str, aspect: str, keys: dict, seed: int | None = None,
             on_wait: Callable[[str], None] = lambda s: None,
             should_stop: Callable[[], bool] = lambda: False) -> Image.Image:
    seed = seed if seed is not None else random.randint(1, 2_000_000)
    w, h = GEN_SIZES.get(aspect, GEN_SIZES["16:9"])
    if provider == "cloudflare":
        data = services.cloudflare_image(keys.get("cloudflare", ""), prompt, w, h, seed)
    elif provider == "gemini":
        data = services.gemini_image(keys.get("gemini", ""), prompt, aspect)
    elif provider == "higgsfield":
        data = services.higgsfield_image(keys.get("higgsfield", ""), prompt, aspect, on_wait=on_wait,
                                         should_stop=should_stop)
    else:
        data = services.pollinations_image(prompt, w, h, seed, keys.get("pollinations", ""), wait=on_wait,
                                           should_stop=should_stop)
    img = Image.open(io.BytesIO(data))
    img.load()
    return img.convert("RGB")


# ----------------------------------------------------------------------------- kapak tasarımı

def cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Görseli hedef boyutu tamamen dolduracak şekilde ölçekleyip ortadan kırpar."""
    W, H = size
    scale = max(W / img.width, H / img.height)
    resized = img.resize((max(W, round(img.width * scale)), max(H, round(img.height * scale))), Image.LANCZOS)
    x, y = (resized.width - W) // 2, (resized.height - H) // 2
    return resized.crop((x, y, x + W, y + H))


def _font(size: int, condensed: bool = False) -> ImageFont.FreeTypeFont:
    name = "TekTikla-Condensed.ttf" if condensed else "TekTikla-Display.ttf"
    try:
        return ImageFont.truetype(str(FONTS_DIR / name), size)
    except OSError:
        return ImageFont.truetype("arialbd.ttf", size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and draw.textlength(trial, font=font) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def _fit(draw, text: str, max_w: int, max_h: int, max_lines: int, start: int) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    size = start
    while size > 18:
        for condensed in (False, True):
            font = _font(size, condensed)
            lines = _wrap(draw, text, font, max_w)
            height = len(lines) * size * 1.02
            if len(lines) <= max_lines and height <= max_h and all(draw.textlength(l, font=font) <= max_w for l in lines):
                return font, lines
        size -= 4
    font = _font(size, True)
    return font, _wrap(draw, text, font, max_w)[:max_lines]


def upper(text: str, lang: str = "") -> str:
    """Büyük harfe çevirir; Türkçe/Azericede i→İ, ı→I doğru olsun."""
    if lang in ("tr", "az"):
        text = text.replace("i", "İ").replace("ı", "I")
    return text.upper()


def compose(bg: Image.Image, title: str, subtitle: str = "", *, aspect: str = "16:9", layout: str = "left",
            style: str = "bold", accent: str = "yellow", uppercase: bool = True, lang: str = "tr") -> Image.Image:
    """Arka plan görselinin üstüne okunaklı başlık yerleştirir. layout: left | center | bottom | none."""
    W, H = ASPECTS.get(aspect, ASPECTS["16:9"])
    base = cover(bg, (W, H)).convert("RGBA")
    title = re.sub(r"\s+", " ", title or "").strip()
    if layout == "none" or not title:
        return base.convert("RGB")
    if uppercase:
        title = upper(title, lang)
    acc = ACCENTS.get(accent, ACCENTS["yellow"])

    # okunabilirlik için yumuşak karartma
    shade = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(shade)
    if layout == "left":
        for x in range(W):
            sd.line([(x, 0), (x, H)], fill=int(max(0, 215 * (1 - x / (W * 0.72)))))
    elif layout == "bottom":
        for y in range(H):
            sd.line([(0, y), (W, y)], fill=int(max(0, 225 * ((y - H * 0.38) / (H * 0.62)))))
    else:
        shade = Image.new("L", (W, H), 95)
    base = Image.composite(Image.new("RGBA", (W, H), (0, 0, 0, 255)), base, shade.point(lambda v: v))

    draw = ImageDraw.Draw(base)
    pad = int(min(W, H) * 0.07)
    if layout == "left":
        box_w, box_h, max_lines = int(W * 0.58), int(H * 0.62), 3
    elif layout == "bottom":
        box_w, box_h, max_lines = W - 2 * pad, int(H * 0.36), 3
    else:
        box_w, box_h, max_lines = W - 2 * pad, int(H * 0.5), 4
    font, lines = _fit(draw, title, box_w, box_h, max_lines, start=int(min(W, H) * 0.2))
    size = font.size
    line_h = int(size * 1.02)
    sub_font = _font(max(18, int(size * 0.34)))
    sub_h = int(sub_font.size * 1.6) if subtitle else 0
    block_h = len(lines) * line_h + sub_h
    if layout == "left":
        x0, y0 = pad, (H - block_h) // 2
    elif layout == "bottom":
        x0, y0 = pad, H - pad - block_h
    else:
        x0, y0 = None, (H - block_h) // 2

    stroke = max(2, int(size * 0.07))
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    texts = []
    for i, line in enumerate(lines):
        lw = draw.textlength(line, font=font)
        x = x0 if x0 is not None else (W - lw) / 2
        y = y0 + i * line_h
        highlight = style == "box" and i == len(lines) - 1 or style == "bold" and len(lines) > 1 and i == len(lines) - 1
        texts.append((x, y, line, lw, highlight))
        sdraw.text((x + size * 0.04, y + size * 0.06), line, font=font, fill=(0, 0, 0, 170))
    base.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(size * 0.06)))
    for x, y, line, lw, highlight in texts:
        if style == "box" and highlight:
            m = size * 0.12
            draw.rounded_rectangle([x - m, y - m * 0.2, x + lw + m, y + line_h - m * 0.1], radius=int(size * 0.12),
                                   fill=acc + (255,))
            draw.text((x, y), line, font=font, fill=(10, 10, 10))
        elif style == "clean":
            draw.text((x, y), line, font=font, fill=(255, 255, 255))
        else:
            draw.text((x, y), line, font=font, fill=acc if highlight else (255, 255, 255),
                      stroke_width=stroke, stroke_fill=(0, 0, 0))
    if subtitle:
        sub = subtitle.strip()
        sw = draw.textlength(sub, font=sub_font)
        sx = x0 if x0 is not None else (W - sw) / 2
        sy = y0 + len(lines) * line_h + int(sub_font.size * 0.45)
        m = sub_font.size * 0.45
        draw.rounded_rectangle([sx - m, sy - m * 0.5, sx + sw + m, sy + sub_font.size * 1.15], radius=int(m),
                               fill=(0, 0, 0, 200))
        draw.text((sx, sy), sub, font=sub_font, fill=(255, 255, 255))
    return base.convert("RGB")


def save(img: Image.Image, folder: Path, name: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", name).strip()[:80] or "gorsel"
    path = folder / f"{stem}.jpg"
    n = 2
    while path.exists():
        path = folder / f"{stem} ({n}).jpg"
        n += 1
    img.save(path, "JPEG", quality=94)
    return path
