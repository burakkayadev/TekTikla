"""Dosya dönüştürücü: resim, video ve ses dosyalarını başka biçime çevirir; istenirse yeniden boyutlandırır.

Resimler Pillow ile kaydedilir (WEBP, PNG, JPG, AVIF, GIF, BMP, TIFF, ICO, PDF); iPhone fotoğrafları (HEIC/HEIF)
FFmpeg ile açılır. Video ve ses FFmpeg ile çevrilir; "Orijinal" kalitede uygun kaba yeniden kodlamadan aktarılır
(kayıpsız ve çok hızlı). Boyut seçenekleri uzun kenarı belirler; dikey ve yatay dosyada aynı anlamdadır.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageOps, ImageSequence

from . import i18n, media
from .config import LOCAL_DIR, UPLOAD_DIR

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".jfif", ".webp", ".avif", ".gif", ".bmp", ".tif", ".tiff", ".ico", ".heic",
             ".heif", ".tga"}
HEIF_EXT = {".heic", ".heif"}
VIDEO_EXT = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".flv", ".wmv", ".m4v", ".3gp", ".ts", ".mts", ".m2ts", ".mpg",
             ".mpeg", ".ogv"}
AUDIO_EXT = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wma", ".aiff", ".aif", ".amr", ".mka"}

TARGETS = {
    "image": ("webp", "png", "jpg", "avif", "gif", "bmp", "tiff", "ico", "pdf"),
    "video": ("mp4", "webm", "mkv", "mov", "gif", "mp3", "m4a", "wav"),
    "audio": ("mp3", "m4a", "wav", "flac", "ogg", "opus"),
}
AUDIO_OUT = {"mp3", "m4a", "wav", "flac", "ogg", "opus"}
QUALITIES = ("original", "high", "balanced", "small")
SIZES = {"original": None, "hd": 1280, "fhd": 1920, "2k": 2560, "4k": 3840}  # uzun kenar (piksel)
FITS = ("keep", "crop", "stretch")
MAX_SIDE = {"image": 12000, "video": 7680}  # bellek ve kodlayıcı sınırı
THUMB_DIR = LOCAL_DIR / "convert"

IMG_Q = {"jpg": {"original": 100, "high": 92, "balanced": 84, "small": 70},
         "webp": {"high": 90, "balanced": 80, "small": 64},  # "original" kayıpsız
         "avif": {"original": 95, "high": 82, "balanced": 66, "small": 50}}
X264 = {"original": (16, "slow"), "high": (19, "slow"), "balanced": (23, "medium"), "small": (28, "medium")}
VP9 = {"original": (22, 2), "high": (28, 2), "balanced": (33, 4), "small": (38, 4)}  # crf, cpu-used
KBPS = {"mp3": {"original": 320, "high": 256, "balanced": 192, "small": 128},
        "aac": {"original": 320, "high": 256, "balanced": 192, "small": 128},
        "opus": {"original": 256, "high": 192, "balanced": 128, "small": 96}}
VORBIS_Q = {"original": 9, "high": 7, "balanced": 5, "small": 3}
GIF = {"original": (24, None, 256), "high": (20, 960, 256), "balanced": (15, 720, 192), "small": (12, 480, 128)}


@dataclass
class Options:
    targets: dict = field(default_factory=dict)  # {"image": "webp", "video": "mp4", "audio": "mp3"}
    quality: str = "high"
    size: str = "original"  # SIZES anahtarı ya da "custom"
    width: int = 0
    height: int = 0
    fit: str = "keep"  # özel boyutta: oranı koru | kırparak doldur | esnet
    place: str = "beside"  # "beside": dosyanın yanına | "folder": indirme klasörü/Dönüştürülenler
    strip: bool = False  # konum, cihaz gibi bilgileri sil
    merge_pdf: bool = False
    rotate: int = 0  # resim ve video: saat yönünde 0 / 90 / 180 / 270 derece
    background: str = "#ffffff"  # şeffaflığı desteklemeyen biçimlerde (JPG, BMP, PDF) zemin rengi
    trim_start: float = 0.0  # video ve ses: kesilecek bölümün başı (saniye)
    trim_end: float = 0.0  # 0 = sonuna kadar
    fps: int = 0  # video: 0 = orijinal kare hızı
    mute: bool = False  # video: sesi kaldır
    normalize: bool = False  # ses ve video: ses seviyesini dengele (EBU R128, -14 LUFS: Instagram/YouTube seviyesi)
    mono: bool = False  # ses: tek kanal
    suffix: bool = False  # dosya adına yeni ölçüyü ekle: foto-3840x2160.webp


ROTATIONS = (0, 90, 180, 270)
FPS_CHOICES = (0, 24, 25, 30, 50, 60)


def _color(hex_color: str) -> tuple[int, int, int]:
    h = (hex_color or "").lstrip("#")
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)) if len(h) == 6 else (255, 255, 255)
    except ValueError:
        return 255, 255, 255


def kind_of(path: Path) -> str | None:
    ext = path.suffix.lower()
    return "image" if ext in IMAGE_EXT else "video" if ext in VIDEO_EXT else "audio" if ext in AUDIO_EXT else None


def target_size(w: int, h: int, o: Options, kind: str = "image") -> tuple[int, int, str] | None:
    """Yeni (en, boy, sığdırma); boyut değişmiyorsa None. Video için çift sayıya yuvarlanır (yuv420p)."""
    if not w or not h:
        return None
    if o.size == "custom":
        bw, bh = max(0, int(o.width or 0)), max(0, int(o.height or 0))
        if not bw and not bh:
            return None
        if o.fit in ("crop", "stretch") and bw and bh:
            nw, nh, mode = bw, bh, o.fit
        else:
            s = min(bw / w if bw else float("inf"), bh / h if bh else float("inf"))
            nw, nh, mode = round(w * s), round(h * s), "keep"
    else:
        side = SIZES.get(o.size)
        if not side:
            return None
        s = side / max(w, h)
        nw, nh, mode = round(w * s), round(h * s), "keep"
    cap = MAX_SIDE[kind]
    if max(nw, nh) > cap:
        s = cap / max(nw, nh)
        nw, nh = round(nw * s), round(nh * s)
    nw, nh = max(1, nw), max(1, nh)
    if kind == "video":
        nw, nh = max(2, nw // 2 * 2), max(2, nh // 2 * 2)
    return None if (nw, nh) == (w, h) and mode == "keep" else (nw, nh, mode)


# ----------------------------------------------------------------------------- dosya bilgisi ve önizleme

def _has_alpha(img: Image.Image) -> bool:
    return img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)


def thumb_path(p: Path) -> Path:
    st = p.stat()
    key = hashlib.sha1(f"{p}|{st.st_size}|{st.st_mtime_ns}".encode("utf-8")).hexdigest()[:20]
    return THUMB_DIR / f"{key}.jpg"


def _checker(size: tuple[int, int]) -> Image.Image:
    """Şeffaf resim önizlemesinin arkasındaki dama deseni."""
    bg = Image.new("RGB", size, (58, 58, 62))
    tile = Image.new("RGB", (8, 8), (82, 82, 88))
    for y in range(0, size[1], 16):
        for x in range(0, size[0], 16):
            bg.paste(tile, (x, y))
            bg.paste(tile, (x + 8, y + 8))
    return bg


def _save_thumb(img: Image.Image, out: Path) -> Path:
    img = img.copy()
    img.thumbnail((320, 320), Image.LANCZOS)
    if _has_alpha(img):
        rgba = img.convert("RGBA")
        bg = _checker(rgba.size)
        bg.paste(rgba, mask=rgba.getchannel("A"))
        img = bg
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, "JPEG", quality=82)
    return out


def inspect(path: str) -> dict | None:
    """Arayüzdeki dosya satırı için bilgi: tür, en/boy, süre, boyut ve küçük önizleme. Desteklenmiyorsa None."""
    p = Path(path)
    if not p.is_file():
        return None
    kind = kind_of(p)
    info = {"path": str(p), "name": p.name, "ext": p.suffix.lower().lstrip(".") or "?", "kind": kind,
            "bytes": p.stat().st_size, "width": 0, "height": 0, "duration": 0.0, "alpha": False, "animated": False,
            "has_audio": False, "thumb": None}
    if kind in (None, "image") and p.suffix.lower() not in HEIF_EXT:
        try:
            with Image.open(p) as im:
                info.update(kind="image", width=im.width, height=im.height, alpha=_has_alpha(im),
                            animated=bool(getattr(im, "is_animated", False)))
                if im.getexif().get(0x0112) in (5, 6, 7, 8):  # telefon fotoğrafı yan çekilmiş: en/boy yer değiştirir
                    info["width"], info["height"] = im.height, im.width
                thumb = thumb_path(p)
                if not thumb.exists():
                    im.draft("RGB", (640, 640))
                    _save_thumb(ImageOps.exif_transpose(im), thumb)
                info["thumb"] = str(thumb)
            return info
        except Exception:  # noqa: BLE001 - FFmpeg ile denenir
            if kind == "image":
                return None
    try:
        pr = media.probe(p)
    except Exception:  # noqa: BLE001
        return None
    if kind is None:
        kind = "video" if pr["width"] else "audio" if pr["has_audio"] else None
    if kind is None:
        return None
    if kind == "video" and not pr["width"]:
        kind = "audio"  # yalnızca ses içeren mp4/webm
    info.update(kind=kind, width=pr["width"], height=pr["height"], duration=pr["duration"], has_audio=pr["has_audio"])
    if kind in ("video", "image"):
        thumb = thumb_path(p)
        if not thumb.exists():
            THUMB_DIR.mkdir(parents=True, exist_ok=True)
            seek = ["-ss", f"{pr['duration'] * 0.1:.2f}"] if pr["duration"] > 2 else []
            try:
                media.run_ffmpeg([*seek, "-i", str(p), "-frames:v", "1", "-vf", "scale=320:320:force_original_aspect_ratio=decrease",
                                  "-q:v", "4", str(thumb)])
            except Exception:  # noqa: BLE001 - önizleme olmasa da olur
                pass
        info["thumb"] = str(thumb) if thumb.exists() else None
    return info


# ----------------------------------------------------------------------------- resim

def _open_image(path: Path, tmp: Path) -> Image.Image:
    if path.suffix.lower() in HEIF_EXT:  # Pillow HEIC açamaz; FFmpeg kayıpsız PNG'ye çevirir
        png = tmp / f"{path.stem}.png"
        media.run_ffmpeg(["-i", str(path), "-frames:v", "1", str(png)])
        path = png
    img = Image.open(path)
    img.load()
    return img


def _flatten(img: Image.Image, background: str = "#ffffff") -> Image.Image:
    """Şeffaflığı desteklemeyen biçimler için seçilen zemin rengine (varsayılan beyaz) oturtur."""
    if img.mode == "L":
        return img
    if _has_alpha(img):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, _color(background))
        bg.paste(rgba, mask=rgba.getchannel("A"))
        return bg
    return img.convert("RGB")


def _resize(img: Image.Image, size: tuple[int, int, str]) -> Image.Image:
    w, h, mode = size
    if img.mode not in ("RGB", "RGBA", "L", "LA"):
        img = img.convert("RGBA" if _has_alpha(img) else "RGB")
    if mode == "crop":
        return ImageOps.fit(img, (w, h), Image.LANCZOS)
    return img.resize((w, h), Image.LANCZOS, reducing_gap=3.0 if w < img.width else None)


def _square(img: Image.Image) -> Image.Image:
    side = max(img.size)
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
    return out


def _save_still(img: Image.Image, dst: Path, fmt: str, o: Options, exif: bytes | None, icc: bytes | None) -> None:
    q = o.quality
    kw = {}
    if icc:
        kw["icc_profile"] = icc
    if exif and fmt in ("jpg", "webp", "png", "avif", "tiff"):
        kw["exif"] = exif
    alpha = _has_alpha(img)
    if fmt == "jpg":
        _flatten(img, o.background).save(dst, "JPEG", quality=IMG_Q["jpg"][q], optimize=True, progressive=True,
                           subsampling=0 if q in ("original", "high") else 2, **kw)
    elif fmt == "webp":
        im = img.convert("RGBA" if alpha else "RGB")
        if q == "original":
            im.save(dst, "WEBP", lossless=True, quality=90, method=4, **kw)
        else:
            im.save(dst, "WEBP", quality=IMG_Q["webp"][q], method=4, **kw)
    elif fmt == "avif":
        img.convert("RGBA" if alpha else "RGB").save(
            dst, "AVIF", quality=IMG_Q["avif"][q], speed=5, subsampling="4:4:4" if q in ("original", "high") else "4:2:0", **kw)
    elif fmt == "png":
        if q == "small":  # 256 renge indirger: çoğu ekran görüntüsünde fark edilmez, dosya çok küçülür
            im = img.convert("RGBA").quantize(256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG)
        else:
            im = img if img.mode in ("RGB", "RGBA", "L", "LA", "P", "I;16") else img.convert("RGBA" if alpha else "RGB")
        im.save(dst, "PNG", optimize=True, **kw)
    elif fmt == "gif":
        im = img.convert("RGBA" if alpha else "RGB")
        im = im.quantize(128 if q == "small" else 256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG)
        im.save(dst, "GIF", optimize=True)
    elif fmt == "bmp":
        _flatten(img, o.background).save(dst, "BMP")
    elif fmt == "tiff":
        img.convert("RGBA" if alpha else "RGB").save(dst, "TIFF", compression="tiff_lzw", **kw)
    elif fmt == "ico":
        im = _square(img.convert("RGBA"))
        sizes = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256) if s <= im.width] or [im.size]
        im.save(dst, "ICO", sizes=sizes)
    elif fmt == "pdf":
        _flatten(img, o.background).save(dst, "PDF", resolution=300.0 if q in ("original", "high") else 150.0,
                           quality=IMG_Q["jpg"][q])
    else:
        raise ValueError(fmt)


_TURN = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180, 270: Image.Transpose.ROTATE_90}


def _turn(img: Image.Image, degrees: int) -> Image.Image:
    """Saat yönünde kayıpsız döndürme (piksel yer değiştirir, yeniden örnekleme yok)."""
    return img.transpose(_TURN[degrees]) if degrees in _TURN else img


def _prepare(src: Path, o: Options, tmp: Path) -> tuple[Image.Image, bytes | None, bytes | None]:
    """Döndürülmüş (EXIF yönü + seçilen açı) ve yeniden boyutlandırılmış resim + korunacak bilgiler."""
    img = _turn(ImageOps.exif_transpose(_open_image(src, tmp)), o.rotate)
    exif = None
    if not o.strip:
        data = img.getexif()
        exif = data.tobytes() if len(data) else None
    size = target_size(img.width, img.height, o)
    if size:
        img = _resize(img, size)
    return img, exif, img.info.get("icc_profile")


def convert_image(src: Path, dst: Path, fmt: str, o: Options, tmp: Path) -> None:
    if fmt in ("gif", "webp") and src.suffix.lower() not in HEIF_EXT:
        with Image.open(src) as anim:
            if getattr(anim, "is_animated", False):  # hareketli GIF/WEBP hareketli kalır
                frames, durations = [], []
                for frame in ImageSequence.Iterator(anim):
                    f = _turn(frame.convert("RGBA"), o.rotate)
                    size = target_size(f.width, f.height, o)
                    frames.append(_resize(f, size) if size else f)
                    durations.append(frame.info.get("duration") or anim.info.get("duration") or 100)
                kw = {"save_all": True, "append_images": frames[1:], "duration": durations, "loop": anim.info.get("loop", 0)}
                if fmt == "gif":
                    frames[0].save(dst, "GIF", disposal=2, optimize=False, **kw)
                elif o.quality == "original":
                    frames[0].save(dst, "WEBP", lossless=True, quality=100, method=4, **kw)
                else:
                    frames[0].save(dst, "WEBP", quality=IMG_Q["webp"][o.quality], method=4, **kw)
                return
    img, exif, icc = _prepare(src, o, tmp)
    _save_still(img, dst, fmt, o, exif, icc)


# ----------------------------------------------------------------------------- video ve ses

def _can_copy(fmt: str, info: dict) -> bool:
    """Yeniden kodlamadan yalnızca kabı değiştirmek mümkün mü (kayıpsız ve saniyeler sürer)."""
    v, a = info.get("vcodec"), info.get("acodec")
    if fmt == "mkv":
        return True
    if fmt in ("mp4", "mov"):
        return v in ("h264", "hevc", "av1", "mpeg4") and a in (None, "aac", "mp3", "alac", "ac3", "eac3")
    if fmt == "webm":
        return v in ("vp8", "vp9", "av1") and a in (None, "opus", "vorbis")
    return False


def _audio_codec(fmt: str, q: str, info: dict) -> list[str]:
    if fmt == "mp3":
        return ["-c:a", "libmp3lame", "-b:a", f"{KBPS['mp3'][q]}k"]
    if fmt == "m4a":
        return ["-c:a", "aac", "-b:a", f"{KBPS['aac'][q]}k"]
    if fmt == "opus":
        return ["-c:a", "libopus", "-b:a", f"{KBPS['opus'][q]}k"]
    if fmt == "ogg":
        return ["-c:a", "libvorbis", "-q:a", str(VORBIS_Q[q])]
    if fmt == "flac":
        return ["-c:a", "flac", "-compression_level", "8"]
    return ["-c:a", "pcm_s24le" if (info.get("abits") or 16) > 16 else "pcm_s16le"]  # wav


def _scale(size: tuple[int, int, str]) -> str:
    w, h, mode = size
    if mode == "crop":
        return f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h}"
    return f"scale={w}:{h}:flags=lanczos" + (",setsar=1" if mode == "stretch" else "")


def _trim(o: Options, duration: float) -> tuple[float, float]:
    """Kesilecek bölüm (başlangıç, süre); kesme yoksa (0, tüm süre)."""
    start = max(0.0, min(o.trim_start or 0.0, max(0.0, duration - 0.1))) if duration else max(0.0, o.trim_start or 0.0)
    end = o.trim_end if o.trim_end and o.trim_end > start else duration
    return start, max(0.1, (end or 0) - start) if end else 0.0


def out_duration(o: Options, duration: float) -> float:
    return _trim(o, duration)[1] or duration


def av_args(src: Path, dst: Path, fmt: str, o: Options, info: dict) -> list[str]:
    q = o.quality
    start, length = _trim(o, info.get("duration") or 0)
    args = (["-ss", f"{start:.3f}"] if start else []) + ["-i", str(src)] + (["-t", f"{length:.3f}"] if length and (start or o.trim_end) else [])
    w, h = info.get("width") or 0, info.get("height") or 0
    if o.rotate in (90, 270):
        w, h = h, w  # ölçü hesabı döndürülmüş görüntüye göre
    size = target_size(w, h, o, "video") if w else None
    turn = {90: "transpose=1", 180: "transpose=1,transpose=1", 270: "transpose=2"}.get(o.rotate, "")
    extra_v = ",".join(x for x in (turn, f"fps={o.fps}" if o.fps else "") if x)
    audio_f = ",".join(x for x in ("loudnorm=I=-14:TP=-1.5:LRA=11" if o.normalize else "", "") if x)
    if fmt in AUDIO_OUT:
        if not info.get("has_audio"):
            raise RuntimeError(i18n.t("Bu dosyada ses yok."))
        args += ["-map", "0:a:0", "-vn", *_audio_codec(fmt, q, info)]
        if audio_f:
            args += ["-af", audio_f]
        if o.mono:
            args += ["-ac", "1"]
    elif fmt == "gif":
        fps, cap, colors = GIF[q]
        w, h = info["width"], info["height"]
        if not size and cap and max(w, h) > cap:
            s = cap / max(w, h)
            size = (round(w * s) // 2 * 2, round(h * s) // 2 * 2, "keep")
        scale = _scale(size) if size else "scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos"
        if turn:
            scale = f"{turn},{scale}"
        dither = "sierra2_4a" if q in ("original", "high") else "bayer:bayer_scale=4"
        args += ["-filter_complex", f"[0:v]fps={o.fps or fps},{scale},split[a][b];[a]palettegen=max_colors={colors}:stats_mode=diff[p];"
                                    f"[b][p]paletteuse=dither={dither}:diff_mode=rectangle", "-loop", "0"]
    elif q == "original" and not size and not extra_v and not o.mute and not o.normalize and _can_copy(fmt, info):
        # kayıpsız ve saniyeler sürer; kesme varsa en yakın ana kareden başlar
        args += ["-map", "0", "-c", "copy"] if fmt == "mkv" else ["-map", "0:v:0", "-map", "0:a?", "-c", "copy"]
    else:
        vf = ",".join(x for x in (extra_v, _scale(size) if size else "scale=trunc(iw/2)*2:trunc(ih/2)*2") if x)
        args += ["-map", "0:v:0"] + ([] if o.mute else ["-map", "0:a?"]) + ["-vf", vf]
        if audio_f and not o.mute:
            args += ["-af", audio_f]
        if fmt == "webm":
            crf, cpu = VP9[q]
            args += ["-c:v", "libvpx-vp9", "-crf", str(crf), "-b:v", "0", "-row-mt", "1", "-deadline", "good",
                     "-cpu-used", str(cpu), "-pix_fmt", "yuv420p", "-c:a", "libopus", "-b:a", f"{KBPS['opus'][q]}k"]
        else:
            crf, preset = X264[q]
            args += ["-c:v", "libx264", "-crf", str(crf), "-preset", preset, "-pix_fmt", "yuv420p",
                     "-c:a", "aac", "-b:a", f"{KBPS['aac'][q]}k"]
        if o.mute:
            args += ["-an"]
    if fmt in ("mp4", "mov", "m4a"):
        args += ["-movflags", "+faststart"]
    if o.strip:
        args += ["-map_metadata", "-1", "-map_chapters", "-1"]
    return args + [str(dst)]


# ----------------------------------------------------------------------------- kuyruk işi

def _unique(path: Path, src: Path) -> Path:
    """Var olan dosyanın (ve kaynağın) üzerine yazmaz: "ad (1).webp" gibi yeni ad bulur."""
    cand, n = path, 1
    while cand.exists() or cand.resolve() == src.resolve():
        cand = path.with_name(f"{path.stem} ({n}){path.suffix}")
        n += 1
    return cand


class ConvertJob(media.Job):
    """Bir grup dosyayı çevirir: resimler tek işte toplanır, her video/ses kendi işinde çevrilir."""

    def __init__(self, settings: dict, emit, files: list[dict], opts: Options):
        super().__init__(settings, emit)
        self.files = files  # [{"path", "kind", "name"}]
        self.opts = opts

    def _out_dir(self, src: Path) -> Path:
        # telefondan gelen dosyanın yanı gizli bir klasör: sonuç bilgisayarda da bulunsun diye indirme klasörüne
        if self.opts.place == "beside" and UPLOAD_DIR not in src.parents and os.access(src.parent, os.W_OK):
            return src.parent
        out = Path(self.settings["download_dir"]) / i18n.t("Dönüştürülenler")
        out.mkdir(parents=True, exist_ok=True)
        return out

    def _suffix(self, f: dict, info: dict | None = None) -> str:
        """İstenirse yeni ölçü dosya adına eklenir: foto-3840x2160.webp"""
        if not self.opts.suffix:
            return ""
        w, h = (info or f).get("width") or 0, (info or f).get("height") or 0
        if self.opts.rotate in (90, 270):
            w, h = h, w
        size = target_size(w, h, self.opts, "video" if f["kind"] == "video" else "image")
        return f"-{size[0]}x{size[1]}" if size else ""

    def work(self) -> list[Path]:
        o, out = self.opts, []
        tmp = Path(tempfile.mkdtemp(prefix="tt_conv_"))
        pages: list[Image.Image] = []
        n = len(self.files)
        try:
            for i, f in enumerate(self.files):
                src, kind = Path(f["path"]), f["kind"]
                fmt = o.targets.get(kind)
                if not fmt or not src.is_file():
                    self.warnings.append(i18n.t("Bulunamadı: {name}", name=src.name))
                    continue
                stage = i18n.t("Dönüştürülüyor: {name}", name=src.name) if n == 1 else \
                    i18n.t("{i}/{n} dönüştürülüyor: {name}", i=i + 1, n=n, name=src.name)
                dst = None
                try:
                    if kind == "image":
                        self.stage(stage, i / n)
                        if fmt == "pdf" and o.merge_pdf:
                            img, _exif, _icc = _prepare(src, o, tmp)
                            pages.append(_flatten(img, o.background))
                            continue
                        dst = _unique(self._out_dir(src) / f"{src.stem}{self._suffix(f)}.{fmt}", src)
                        convert_image(src, dst, fmt, o, tmp)
                    else:
                        info = media.probe(src)
                        dst = _unique(self._out_dir(src) / f"{src.stem}{self._suffix(f, info)}.{fmt}", src)
                        self.ffmpeg(av_args(src, dst, fmt, o, info), out_duration(o, info["duration"]) or None, stage,
                                    (i / n, (i + 1) / n))
                    out.append(dst)
                except media.Cancelled:
                    if dst:
                        dst.unlink(missing_ok=True)  # yarım kalan dosya kalmasın
                    raise
                except Exception as e:  # noqa: BLE001 - biri bozuksa diğerleri yine çevrilsin
                    if dst:
                        dst.unlink(missing_ok=True)
                    if n == 1:
                        raise
                    self.warnings.append(f"{src.name}: {str(e).splitlines()[0][:160]}")
            if pages:
                self.stage(i18n.t("PDF oluşturuluyor"), 0.98)
                first = Path(self.files[0]["path"])
                dst = _unique(self._out_dir(first) / f"{first.stem}.pdf", first)
                res = 300.0 if o.quality in ("original", "high") else 150.0
                pages[0].save(dst, "PDF", save_all=True, append_images=pages[1:], resolution=res,
                              quality=IMG_Q["jpg"][o.quality])
                out.append(dst)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if not out:
            raise RuntimeError(i18n.t("Hiçbir dosya dönüştürülemedi.") + ("\n" + "\n".join(self.warnings) if self.warnings else ""))
        return out


# ----------------------------------------------------------------------------- tahmini boyut

BPP = {"original": 0.12, "high": 0.075, "balanced": 0.045, "small": 0.026}  # H.264 için piksel başına bit (≈)


def estimate(item: dict, o: Options, tmp: Path) -> dict | None:
    """Dönüştürmeden önce sonucun yaklaşık boyutu. Resimde gerçekten (geçici dosyaya) kodlanır, video ve seste
    bit hızından hesaplanır. {"bytes", "width", "height", "exact"}"""
    kind, fmt = item["kind"], o.targets.get(item["kind"])
    src = Path(item["path"])
    if not fmt or not src.is_file():
        return None
    if kind == "image":
        if fmt == "pdf" and o.merge_pdf:
            return None
        dst = tmp / f"tahmin.{fmt}"
        convert_image(src, dst, fmt, o, tmp)
        with Image.open(dst) as im:
            w, h = im.size
        return {"bytes": dst.stat().st_size, "width": w, "height": h, "exact": True}
    duration = out_duration(o, item.get("duration") or 0)
    if not duration:
        return None
    q = o.quality
    if fmt in AUDIO_OUT:
        ch = 1 if o.mono else 2
        kbps = {"mp3": KBPS["mp3"][q], "m4a": KBPS["aac"][q], "opus": KBPS["opus"][q], "ogg": 64 + VORBIS_Q[q] * 24,
                "wav": 48 * 16 * ch, "flac": 48 * 16 * ch * 0.6}[fmt]
        return {"bytes": int(kbps * 1000 / 8 * duration), "width": 0, "height": 0, "exact": False}
    w, h = item.get("width") or 0, item.get("height") or 0
    if o.rotate in (90, 270):
        w, h = h, w
    size = target_size(w, h, o, "video")
    if size:
        w, h = size[0], size[1]
    if fmt == "gif":
        fps, cap, colors = GIF[q]
        if cap and max(w, h) > cap and not size:
            s = cap / max(w, h)
            w, h = int(w * s), int(h * s)
        return {"bytes": int(w * h * (o.fps or fps) * duration * 0.12), "width": w, "height": h, "exact": False}
    if q == "original" and not size and not o.fps and not o.mute and not o.normalize and o.rotate == 0:
        ratio = duration / (item.get("duration") or duration)
        return {"bytes": int(item["bytes"] * ratio), "width": w, "height": h, "exact": False}
    fps = o.fps or 30
    vbits = w * h * fps * BPP[q] * (0.7 if fmt == "webm" else 1.0)
    abits = 0 if o.mute else KBPS["opus" if fmt == "webm" else "aac"][q] * 1000
    return {"bytes": int((vbits + abits) / 8 * duration), "width": w, "height": h, "exact": False}
