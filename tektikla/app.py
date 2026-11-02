"""TekTıkla penceresi: HTML arayüzünü Windows'un WebView2 (Edge) motoruyla açar."""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

import webview
from PIL import Image, ImageDraw, ImageFilter

from . import APP_NAME, i18n
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
# Temaya göre logo: (degrade renkleri, degrade yönü, harf rengi, kenar rengi) — web/style.css'teki --logo-* ile aynı
LOGO_STYLES = {
    "mono": (((34, 34, 38), (6, 6, 7)), "dikey", (255, 255, 255), (255, 255, 255, 46)),
    "paper": (((255, 255, 255), (234, 232, 226)), "dikey", (17, 17, 17), (0, 0, 0, 40)),
    "violet": (((124, 92, 255), (176, 76, 253), (255, 77, 141)), "çapraz", (255, 255, 255), None),
    "ocean": (((34, 211, 238), (56, 189, 248), (129, 140, 248)), "çapraz", (255, 255, 255), None),
}
THEMES = tuple(LOGO_STYLES)


def _gradient(size: int, colors: tuple, direction: str) -> Image.Image:
    grad = Image.new("RGB", (size, size))
    px = grad.load()
    stops = len(colors) - 1
    for y in range(size):
        for x in range(0, size, 2):
            t = y / (size - 1) if direction == "dikey" else (x + y) / (2 * (size - 1))
            i = min(int(t * stops), stops - 1)
            k = t * stops - i
            col = tuple(int(colors[i][c] + (colors[i + 1][c] - colors[i][c]) * k) for c in range(3))
            px[x, y] = col
            if x + 1 < size:
                px[x + 1, y] = col
    return grad


def _logo_image(size: int = 1024, theme: str = "mono") -> Image.Image:
    colors, direction, fg, ring_color = LOGO_STYLES.get(theme, LOGO_STYLES["mono"])
    u = size / 24
    mask = Image.new("L", (size, size), 0)
    radius = int(5.6 * u)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img.paste(_gradient(size, colors, direction), (0, 0), mask)
    if ring_color:  # ince kenar: koyu/açık zeminde logo kaybolmasın
        ring = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        ImageDraw.Draw(ring).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, outline=ring_color,
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
    letters = Image.new("RGBA", (size, size), fg + (255,))
    letters.putalpha(glyph)
    img.alpha_composite(letters)
    return img


ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def ensure_icon() -> Path:
    """Uygulama simgesini (assets/tektikla.ico/.png, siyah) ve tema simgelerini (assets/icons/<tema>.ico) üretir."""
    ico = APP_DIR / "assets" / "tektikla.ico"
    icons = APP_DIR / "assets" / "icons"
    if not ico.exists():
        ico.parent.mkdir(exist_ok=True)
        img = _logo_image()
        img.resize((512, 512), Image.LANCZOS).save(ico.with_suffix(".png"))
        img.save(ico, sizes=ICO_SIZES)
    for theme in THEMES:
        path = icons / f"{theme}.ico"
        if not path.exists():
            icons.mkdir(parents=True, exist_ok=True)
            _logo_image(512, theme).save(path, sizes=ICO_SIZES)
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
        api._window_title(), url=str(WEB_DIR / "index.html"), js_api=api,
        width=1280, height=840, min_size=(1040, 700), background_color=BG_COLOR,
    )
    api._attach(window)

    def on_closing():
        running = api.running_count()
        if running and not window.create_confirmation_dialog(
                APP_NAME, i18n.t("{n} indirme devam ediyor. Kapatırsanız iptal edilecek. Çıkılsın mı?", n=running)):
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
