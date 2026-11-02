"""Tasarımlı QR kodlar (SVG): yumuşak köşeli modüller, yuvarlak göz desenleri, ortada TekTıkla logosu.

Destek penceresi (GitHub profili, bağış linki) ve telefondan bağlanma ekranı kullanır. Logo kodun ortasını
kapattığı için en yüksek hata düzeltme (H, ~%30) seçilir; logo, kodun yalnızca ~%7'sini kaplar.
"""
from __future__ import annotations

import base64

import segno

# kenar çubuğundaki logo (24x24 görünüm kutusu)
_LOGO = ('<rect x="3.6" y="5.2" width="16.8" height="3.2" rx="1.6"/><rect x="6.4" y="5.2" width="3.2" height="14" rx="1.6"/>'
         '<rect x="14.4" y="5.2" width="3.2" height="9.4" rx="1"/><path d="M12.4 13.8h7.2L16 19.2z"/>')
# bağış (Buy Me a Coffee) kodu: ortada buharı tüten sarı bir fincan
_COFFEE = ('<path d="M3.4 9.2h13.2v5.3a5.5 5.5 0 0 1-5.5 5.5H8.9a5.5 5.5 0 0 1-5.5-5.5z"/>'
           '<path d="M16.2 10.6h1.6a3.1 3.1 0 0 1 0 6.2h-2.3v-2h2.3a1.1 1.1 0 0 0 0-2.2h-1.6z"/>'
           '<rect x="6.3" y="3.4" width="1.8" height="4" rx=".9"/><rect x="9.6" y="2.6" width="1.8" height="4.8" rx=".9"/>'
           '<rect x="12.9" y="3.4" width="1.8" height="4" rx=".9"/>')
GLYPHS = {"tt": (_LOGO, None), "coffee": (_COFFEE, "#FFDD00")}  # renk None: QR'ın açık rengi
QUIET = 2  # kenar boşluğu (modül); QR beyaz bir kartın içinde gösterildiği için yeterli


def _rounded(x: float, y: float, w: float, h: float, r: float) -> str:
    """Yuvarlak köşeli dikdörtgen için SVG path parçası."""
    return (f"M{x + r:g} {y:g}h{w - 2 * r:g}a{r:g} {r:g} 0 0 1 {r:g} {r:g}v{h - 2 * r:g}"
            f"a{r:g} {r:g} 0 0 1 {-r:g} {r:g}h{2 * r - w:g}a{r:g} {r:g} 0 0 1 {-r:g} {-r:g}"
            f"v{2 * r - h:g}a{r:g} {r:g} 0 0 1 {r:g} {-r:g}z")


def svg(text: str, dark: str = "#0B0B0C", light: str = "#FFFFFF", logo: bool = True, glyph: str = "tt") -> str:
    qr = segno.make(text, error="h", micro=False, boost_error=False)
    matrix = qr.matrix
    n = len(matrix)
    # 7. sürümden itibaren ortada hizalama deseni var; logo onu kapatmasın
    logo = logo and qr.version < 7
    eyes = ((0, 0), (n - 7, 0), (0, n - 7))
    hole = (max(5, round(n * 0.2)) | 1) if logo else 0  # tek sayı: tam ortalanır
    h0 = (n - hole) // 2

    def skip(x: int, y: int) -> bool:
        if any(ex <= x < ex + 7 and ey <= y < ey + 7 for ex, ey in eyes):
            return True
        return logo and h0 - 1 <= x <= h0 + hole and h0 - 1 <= y <= h0 + hole

    q = QUIET
    dots = "".join(_rounded(x + q + .05, y + q + .05, .9, .9, .28)
                   for y, row in enumerate(matrix) for x, v in enumerate(row) if v and not skip(x, y))
    eye = "".join(_rounded(ex + q, ey + q, 7, 7, 1.8) + _rounded(ex + q + 1, ey + q + 1, 5, 5, 1.15)
                  for ex, ey in eyes)
    pupils = "".join(_rounded(ex + q + 2, ey + q + 2, 3, 3, .85) for ex, ey in eyes)
    size = n + 2 * q
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" shape-rendering="geometricPrecision">',
             f'<rect width="{size}" height="{size}" fill="{light}"/>',
             f'<path fill="{dark}" d="{dots}"/>',
             f'<path fill="{dark}" fill-rule="evenodd" d="{eye}"/>',
             f'<path fill="{dark}" d="{pupils}"/>']
    if logo:
        x0 = h0 + q
        parts.append(f'<path fill="{dark}" d="{_rounded(x0, x0, hole, hole, hole * .26)}"/>')
        shapes, color = GLYPHS.get(glyph, GLYPHS["tt"])
        color = color or light
        scale = hole * .68 / 24
        off = x0 + (hole - 24 * scale) / 2
        parts.append(f'<g fill="{color}" stroke="{color}" stroke-width=".5" stroke-linejoin="round" '
                     f'transform="translate({off:g} {off:g}) scale({scale:g})">{shapes}</g>')
    parts.append("</svg>")
    return "".join(parts)


def data_uri(text: str, **kw) -> str:
    """<img src> olarak kullanılabilen SVG (arayüze innerHTML ile basılmaz)."""
    return "data:image/svg+xml;base64," + base64.b64encode(svg(text, **kw).encode("utf-8")).decode("ascii")
