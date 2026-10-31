"""TekTıkla penceresi: HTML arayüzünü Windows'un WebView2 (Edge) motoruyla açar."""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

import webview
from PIL import Image, ImageDraw, ImageFilter

from . import APP_NAME
from .api import Api
from .config import APP_DIR

WEB_DIR = APP_DIR / "tektikla" / "web" if (APP_DIR / "tektikla" / "web").exists() else Path(__file__).parent / "web"
BG_COLOR = "#050505"


# TT logosu, 24 birimlik ızgarada (web/index.html'deki SVG ile aynı ölçüler):
# iki T'nin üst çizgisi tek parça, ikinci T'nin gövdesi indirme okuyla biter.
LOGO_BAR = (3.6, 5.2, 20.4, 8.4)
LOGO_STEM1 = (6.4, 5.2, 9.6, 19.2)
LOGO_STEM2 = (14.4, 5.2, 17.6, 14.6)
LOGO_ARROW = ((12.4, 13.8), (19.6, 13.8), (16.0, 19.2))
LOGO_TOP, LOGO_BOTTOM = (34, 34, 38), (6, 6, 7)  # antrasitten siyaha dikey geçiş


def _logo_image(size: int = 1024) -> Image.Image:
    u = size / 24
    grad = Image.new("RGB", (size, size))
    draw_grad = ImageDraw.Draw(grad)
    for y in range(size):
        t = y / (size - 1)
        draw_grad.line([(0, y), (size, y)], fill=tuple(int(LOGO_TOP[i] + (LOGO_BOTTOM[i] - LOGO_TOP[i]) * t) for i in range(3)))
    mask = Image.new("L", (size, size), 0)
    radius = int(5.6 * u)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    # ince açık kenar: koyu temada ve koyu görev çubuğunda logo kaybolmasın
    ring = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(ring).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, outline=(255, 255, 255, 46),
                                           width=max(2, size // 90))
    img.alpha_composite(ring)

    glyph = Image.new("L", (size, size), 0)
    g = ImageDraw.Draw(glyph)
    for x0, y0, x1, y1 in (LOGO_BAR, LOGO_STEM1):
        g.rounded_rectangle([x0 * u, y0 * u, x1 * u, y1 * u], radius=1.6 * u, fill=255)
    x0, y0, x1, y1 = LOGO_STEM2
    g.rounded_rectangle([x0 * u, y0 * u, x1 * u, y1 * u], radius=1.0 * u, fill=255)
    g.polygon([(x * u, y * u) for x, y in LOGO_ARROW], fill=255)
    glyph = glyph.filter(ImageFilter.GaussianBlur(size / 110)).point(lambda v: 255 if v > 128 else 0)  # köşeleri yumuşat
    # harflerin altına yumuşak gölge
    shadow = glyph.filter(ImageFilter.GaussianBlur(size / 60)).point(lambda v: v * 0.35)
    shadow_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow_layer.putalpha(shadow)
    img.alpha_composite(shadow_layer, (0, int(size / 90)))
    white = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    white.putalpha(glyph)
    img.alpha_composite(white)
    return img


def ensure_icon() -> Path:
    """Uygulama simgesini (assets/tektikla.ico ve .png) yoksa üretir."""
    ico = APP_DIR / "assets" / "tektikla.ico"
    if ico.exists():
        return ico
    ico.parent.mkdir(exist_ok=True)
    img = _logo_image()
    img.resize((512, 512), Image.LANCZOS).save(ico.with_suffix(".png"))
    img.save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return ico


def main() -> None:
    # pythonw ile konsol yokken sys.stdout/stderr None olur; doğrudan yazan kütüphaneler çökmesin
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    try:
        # Görev çubuğunda Python yerine TekTıkla simgesi görünsün
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TekTikla.VideoIndirici")
    except Exception:  # noqa: BLE001
        pass

    api = Api()
    window = webview.create_window(
        f"{APP_NAME} — Video İndirici", url=str(WEB_DIR / "index.html"), js_api=api,
        width=1280, height=840, min_size=(1040, 700), background_color=BG_COLOR,
    )
    api._attach(window)

    def on_closing():
        running = api.running_count()
        if running and not window.create_confirmation_dialog(
                APP_NAME, f"{running} indirme devam ediyor. Kapatırsanız iptal edilecek. Çıkılsın mı?"):
            return False
        api.cancel_all()
        return True

    window.events.closing += on_closing
    window.events.shown += lambda: api._paint_titlebar(window)
    window.events.loaded += api._start_background

    icon = None
    try:
        icon = str(ensure_icon())
    except OSError:
        pass
    # private_mode: her açılışta temiz profil. Kalıcı profil, güncellemeden sonra eski HTML/CSS'i
    # önbellekten gösterebiliyordu; arayüz zaten tarayıcı depolaması kullanmıyor.
    webview.start(private_mode=True, icon=icon)
