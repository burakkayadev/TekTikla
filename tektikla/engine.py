"""yt-dlp üzerine kurulu indirme motoru: link analizi, indirme, MP3, altyazı ekleme."""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yt_dlp
from yt_dlp.postprocessor.common import PostProcessor
from yt_dlp.utils import DownloadCancelled, download_range_func, parse_bytes

from . import i18n, tools

AUDIO_FORMATS = ["mp3", "m4a", "opus", "flac", "wav"]
AUDIO_QUALITIES = ["320", "256", "192", "128"]
CONTAINERS = ["mp4", "mkv", "webm"]
SPONSOR_CATEGORIES = {"sponsor", "selfpromo", "interaction"}
# Bu biçimlere kapak resmi gömülemiyor
NO_THUMB_EXTS = {"webm", "wav"}
SUB_CODEC = {"mp4": "mov_text", "mkv": "copy", "webm": "webvtt"}

Emit = Callable[..., None]


class _QuietLogger:
    def __init__(self):
        self.warnings: list[str] = []

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        self.warnings.append(msg)

    def error(self, msg):
        pass


# ----------------------------------------------------------------------------- yardımcılar

def human_size(num: float | None) -> str:
    if not num:
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.0f} {unit}" if unit in ("B", "KB") else f"{num:.1f} {unit}"
        num /= 1024
    return ""


def human_time(seconds: float | None) -> str:
    if seconds is None:
        return ""
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def parse_timestamp(text: str) -> float | None:
    """'90', '1:30' veya '01:01:30' biçimlerini saniyeye çevirir."""
    text = text.strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) > 3 or not all(re.fullmatch(r"\d+(\.\d+)?", p) for p in parts):
        raise ValueError(f"Geçersiz zaman: {text}")
    total = 0.0
    for p in parts:
        total = total * 60 + float(p)
    return total


def friendly_error(err: Exception | str) -> str:
    msg = re.sub(r"\x1b\[[0-9;]*m", "", str(err)).replace("ERROR: ", "").strip()
    low = msg.lower()
    hints = [
        ("unsupported url", "Bu linkte indirilebilir video bulunamadı."),
        ("sign in to confirm your age", "Yaş doğrulaması gerekiyor. Ayarlar > Tarayıcı çerezleri'nden giriş yaptığınız tarayıcıyı seçin."),
        ("sign in to confirm you", "Site giriş istiyor. Ayarlar > Tarayıcı çerezleri'nden giriş yaptığınız tarayıcıyı seçin."),
        ("--cookies", "Bu site giriş istiyor. Siteye tarayıcınızda giriş yapıp Ayarlar > Tarayıcı çerezleri'nden o "
                      "tarayıcıyı seçin."),
        ("http error 404", "Sayfa bulunamadı (404). Linki kontrol edin."),
        ("does not exist", "Bu video veya liste bulunamadı. Linki kontrol edin."),
        ("private video", "Bu video gizli."),
        ("video unavailable", "Video kullanılamıyor (silinmiş veya bölgenizde engelli olabilir)."),
        ("drm", "Bu video DRM ile korunuyor, indirilemez."),
        ("http error 403", "Site erişimi reddetti (403). Ayarlar'dan yt-dlp'yi güncellemeyi deneyin."),
        ("requested format is not available", "Seçilen kalite bu video için mevcut değil."),
        ("ffmpeg", "FFmpeg gerekli ama bulunamadı. Üstteki uyarıdan FFmpeg'i kurun."),
        ("unable to download webpage", "Siteye bağlanılamadı. İnternet bağlantınızı kontrol edin."),
    ]
    for key, text in hints:
        if key in low:
            return f"{i18n.t(text)}\n\n{i18n.t('Ayrıntı')}: {msg[:300]}"
    return i18n.t(msg[:500])


def base_opts(settings: dict) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "logger": _QuietLogger(),
        "js_runtimes": tools.js_runtimes(),
        "windowsfilenames": True,
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 4,
        "socket_timeout": 30,
    }
    ffmpeg = tools.find_ffmpeg()
    if ffmpeg:
        opts["ffmpeg_location"] = ffmpeg
    browser = settings.get("cookies_browser")
    if browser and browser != "Yok":
        opts["cookiesfrombrowser"] = (browser.lower(),)
    return opts


# ----------------------------------------------------------------------------- analiz

@dataclass
class Quality:
    label: str
    height: int | None  # None = en iyi


@dataclass
class SubtitleTrack:
    label: str
    lang: str
    auto: bool


@dataclass
class MediaInfo:
    url: str
    title: str
    uploader: str = ""
    duration: float | None = None
    thumbnail: str | None = None
    site: str = ""
    is_playlist: bool = False
    entry_count: int = 0
    qualities: list[Quality] = field(default_factory=list)
    formats: list[tuple[str, str]] = field(default_factory=list)  # (etiket, format seçici)
    subtitles: list[SubtitleTrack] = field(default_factory=list)
    has_playlist_param: bool = False
    audio_only: bool = False  # SoundCloud gibi sadece ses sunan kaynaklar
    raw: dict | None = field(default=None, repr=False)  # AI özeti tekrar indirmesin diye
    entries: list[dict] = field(default_factory=list)  # oynatma listesindeki videolar (seçerek indirme için)


def _height_label(height: int, fps: float | None, size: float | None) -> str:
    tags = {4320: "8K", 2160: "4K", 1440: "2K", 1080: "Full HD", 720: "HD"}
    label = f"{height}p"
    if fps and fps > 30:
        label += f"{int(round(fps))}"
    if height in tags:
        label += f"  ({tags[height]})"
    if size:
        label += f"  ~{human_size(size)}"
    return label


def _fmt_size(f: dict) -> float | None:
    return f.get("filesize") or f.get("filesize_approx")


def _build_qualities(formats: list[dict]) -> list[Quality]:
    audio = [f for f in formats if f.get("vcodec") == "none" and f.get("acodec") not in (None, "none")]
    best_audio = max(audio, key=lambda f: f.get("abr") or 0, default=None)
    audio_size = _fmt_size(best_audio) if best_audio else 0

    by_height: dict[int, dict] = {}
    for f in formats:
        h = f.get("height")
        if not h or f.get("vcodec") == "none":
            continue
        slot = by_height.setdefault(h, {"fps": 0, "size": 0})
        slot["fps"] = max(slot["fps"], f.get("fps") or 0)
        size = _fmt_size(f) or 0
        if f.get("acodec") in (None, "none"):
            size += audio_size or 0
        slot["size"] = max(slot["size"], size)

    qualities = [Quality("En iyi kalite (otomatik)", None)]
    for h in sorted(by_height, reverse=True):
        qualities.append(Quality(_height_label(h, by_height[h]["fps"], by_height[h]["size"]), h))
    return qualities


def _build_formats(formats: list[dict]) -> list[tuple[str, str]]:
    result = []
    for f in reversed(formats):
        if f.get("format_id") is None or f.get("ext") in ("mhtml",):
            continue
        has_video = f.get("vcodec") != "none"
        has_audio = f.get("acodec") not in (None, "none")
        kind = "video+ses" if has_video and has_audio else "video" if has_video else "ses"
        res = f.get("resolution") or (f"{f['height']}p" if f.get("height") else "")
        codec = f.get("vcodec") if has_video and f.get("vcodec") else f.get("acodec") or ""
        parts = [f["format_id"], f.get("ext", ""), res, kind, (codec or "").split(".")[0], human_size(_fmt_size(f))]
        spec = f["format_id"] if has_audio or not has_video else f"{f['format_id']}+ba/{f['format_id']}"
        result.append((" · ".join(p for p in parts if p), spec))
    return result


def _build_subtitles(info: dict) -> list[SubtitleTrack]:
    def name_of(lang: str, tracks: list[dict]) -> str:
        for t in tracks or []:
            if t.get("name"):
                return t["name"]
        return lang

    tracks = []
    for lang, items in sorted((info.get("subtitles") or {}).items()):
        if lang == "live_chat":
            continue
        tracks.append(SubtitleTrack(f"{name_of(lang, items)} [{lang}]", lang, False))
    for lang, items in sorted((info.get("automatic_captions") or {}).items()):
        if lang == "live_chat":
            continue
        tracks.append(SubtitleTrack(f"{name_of(lang, items)} [{lang}] (otomatik)", lang, True))
    return tracks


UNAVAILABLE_TITLES = {"[private video]", "[deleted video]", "[unavailable video]"}


def _playlist_entry(e: dict, index: int) -> dict | None:
    """Düz (flat) liste öğesini arayüzün göstereceği küçük sözlüğe çevirir."""
    url = e.get("url") or e.get("webpage_url") or ""
    if not url.startswith("http"):
        url = e.get("webpage_url") or ""
    if not url:
        return None
    if e.get("ie_key") == "Youtube" and e.get("id"):
        thumb = f"https://i.ytimg.com/vi/{e['id']}/mqdefault.jpg"
    else:
        thumbs = [t for t in e.get("thumbnails") or [] if t.get("url")]
        thumb = (min(thumbs, key=lambda t: abs((t.get("width") or 320) - 320))["url"] if thumbs
                 else e.get("thumbnail"))
    title = (e.get("title") or "").strip()
    return {
        "index": index, "url": url, "title": title,
        "channel": (e.get("channel") or e.get("uploader") or "").strip(),
        "duration": human_time(e.get("duration")), "thumb": thumb,
        "available": title.lower() not in UNAVAILABLE_TITLES,
    }


def analyze(url: str, settings: dict) -> MediaInfo:
    opts = base_opts(settings) | {
        "skip_download": True,
        "extract_flat": "in_playlist",
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.sanitize_info(ydl.extract_info(url, download=False))

    has_list_param = bool(re.search(r"[?&]list=", url))
    if info.get("_type") == "playlist":
        entries = list(info.get("entries") or [])
        thumb = info.get("thumbnail")
        if not thumb and entries:
            thumbs = entries[0].get("thumbnails") or []
            thumb = thumbs[-1]["url"] if thumbs else entries[0].get("thumbnail")
        return MediaInfo(
            url=url,
            title=info.get("title") or "Oynatma listesi",
            uploader=info.get("uploader") or info.get("channel") or "",
            thumbnail=thumb,
            site=info.get("extractor_key") or "",
            is_playlist=True,
            entry_count=info.get("playlist_count") or len(entries),
            entries=[x for i, e in enumerate(entries, 1) if (x := _playlist_entry(e, i))],
            qualities=[Quality("En iyi kalite (otomatik)", None)]
            + [Quality(f"En fazla {h}p", h) for h in (2160, 1440, 1080, 720, 480, 360)],
        )

    formats = info.get("formats") or []
    return MediaInfo(
        url=info.get("webpage_url") or url,
        title=info.get("title") or "Video",
        uploader=info.get("uploader") or info.get("channel") or "",
        duration=info.get("duration"),
        thumbnail=info.get("thumbnail"),
        site=info.get("extractor_key") or "",
        qualities=_build_qualities(formats),
        formats=_build_formats(formats),
        subtitles=_build_subtitles(info),
        has_playlist_param=has_list_param,
        audio_only=bool(formats) and all(f.get("vcodec") == "none" for f in formats),
        raw=info,
    )


# ----------------------------------------------------------------------------- indirme

@dataclass
class DownloadRequest:
    url: str
    title: str
    out_dir: str
    mode: str = "video"  # "video" | "audio"
    height: int | None = None
    format_spec: str | None = None  # gelişmiş: belirli format
    container: str = "mp4"
    audio_format: str = "mp3"
    audio_quality: str = "320"
    sub_lang: str | None = None
    sub_auto: bool = False
    sub_mode: str = "embed"  # "embed" | "burn" | "file"
    external_sub: str | None = None
    ai_sub: str | None = None  # AI altyazı hedef dili ("tr", "en"… ya da "orig": sadece yazıya dök)
    ai_provider: str = "gemini"
    ai_key: str = field(default="", repr=False)
    whisper_model: str = "small"
    trim: tuple[float, float] | None = None
    playlist: bool = False
    name_prefix: str = ""  # listeden seçilen videolarda sıra numarası, ör. "003 - "
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    sponsorblock: bool = False


class Cancelled(Exception):
    pass


class _SubtitlePP(PostProcessor):
    """Videoya site altyazısını yakar ve/veya kullanıcının kendi altyazı dosyasını ekler."""

    def __init__(self, job: "DownloadJob"):
        super().__init__(None)
        self.job = job

    def run(self, info):
        req = self.job.req
        path = Path(info["filepath"])
        site_sub = None
        if req.sub_lang and req.sub_mode == "burn":
            for sub in (info.get("requested_subtitles") or {}).values():
                if sub.get("filepath") and Path(sub["filepath"]).exists():
                    site_sub = Path(sub["filepath"])
                    break

        if site_sub:
            path = self.job.burn_subtitle(path, site_sub, info)
            site_sub.unlink(missing_ok=True)

        if req.external_sub:
            ext_sub = Path(req.external_sub)
            if req.sub_mode == "burn":
                path = self.job.burn_subtitle(path, ext_sub, info)
            elif req.sub_mode == "embed":
                path = self.job.embed_subtitle(path, ext_sub)
            else:
                shutil.copyfile(ext_sub, path.with_suffix(ext_sub.suffix))

        if req.ai_sub:
            try:
                ai_srt, title, lang_tag = self.job.make_ai_subtitle(path, info)
                if req.sub_mode == "burn":
                    path = self.job.burn_subtitle(path, ai_srt, info)
                elif req.sub_mode == "embed":
                    path = self.job.embed_subtitle(path, ai_srt, title=title, lang=lang_tag)
                if req.sub_mode != "file":
                    ai_srt.unlink(missing_ok=True)
            except (Cancelled, DownloadCancelled):
                raise
            except Exception as e:  # noqa: BLE001 - video indi; altyazı hatası indirmeyi boşa çıkarmasın
                self.job.warnings.append(f"Video indirildi ama AI altyazı eklenemedi: {friendly_error(e)}")

        info["filepath"] = str(path)
        return [], info


class DownloadJob:
    def __init__(self, req: DownloadRequest, settings: dict, emit: Emit):
        self.req = req
        self.settings = settings
        self.emit = emit
        self.files: list[str] = []
        self.warnings: list[str] = []
        self._cancel = threading.Event()
        self._proc: subprocess.Popen | None = None
        self._ffmpeg = tools.ffmpeg_exe()

    # -- kontrol
    def cancel(self) -> None:
        self._cancel.set()
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def run(self) -> None:
        try:
            self._download()
            if self.cancelled:
                raise Cancelled
            self.emit("done", files=self.files, warning="\n".join(self.warnings))
        except (Cancelled, DownloadCancelled):
            self.emit("cancelled")
        except yt_dlp.utils.DownloadError as e:
            self.emit("cancelled" if self.cancelled else "error", message=friendly_error(e))
        except Exception as e:  # noqa: BLE001 - kullanıcıya her hatayı göstermek istiyoruz
            self.emit("cancelled" if self.cancelled else "error", message=friendly_error(e))

    # -- yt-dlp ayarları
    def _options(self) -> dict:
        req, settings = self.req, self.settings
        opts = base_opts(settings)
        out = Path(req.out_dir)
        name = "%(title).150B"
        if req.trim:
            name += " (kesit)"
        if req.playlist:
            template = out / "%(playlist_title,playlist_id).100B" / f"%(playlist_index)03d - {name}.%(ext)s"
        else:
            template = out / f"{req.name_prefix}{name}.%(ext)s"

        opts.update(
            outtmpl=str(template),
            noplaylist=not req.playlist,
            overwrites=True,
            progress_hooks=[self._on_progress],
            postprocessor_hooks=[self._on_postprocess],
            post_hooks=[self.files.append],
            ignoreerrors="only_download" if req.playlist else False,
        )
        if settings.get("rate_limit"):
            limit = parse_bytes(settings["rate_limit"])
            if limit:
                opts["ratelimit"] = limit

        has_ffmpeg = bool(self._ffmpeg)
        pps: list[dict] = []

        if req.sponsorblock and has_ffmpeg:
            pps.append({"key": "SponsorBlock", "categories": SPONSOR_CATEGORIES, "when": "after_filter"})

        if req.mode == "audio":
            if not has_ffmpeg:
                raise RuntimeError("Ses dönüştürmek için FFmpeg gerekli.")
            opts["format"] = "ba/b"
            opts["final_ext"] = req.audio_format
            pps.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": req.audio_format,
                "preferredquality": req.audio_quality,
            })
            final_ext = req.audio_format
        else:
            final_ext = req.container
            if req.format_spec:
                opts["format"] = req.format_spec
            elif has_ffmpeg:
                opts["format"] = "bv*+ba/b"
            else:
                opts["format"] = f"b[height<={req.height}]/b" if req.height else "b"
            sort = [f"res:{req.height}"] if req.height else ["res"]
            sort.append("fps")
            if req.container == "mp4":
                sort += ["vcodec:h264", "acodec:aac"]  # Windows oynatıcılarıyla en uyumlu
            elif req.container == "webm":
                sort += ["vcodec:vp9", "acodec:opus"]
            opts["format_sort"] = sort
            if has_ffmpeg:
                opts["merge_output_format"] = req.container

            if req.sub_lang:
                opts.update(
                    writesubtitles=True,
                    writeautomaticsub=req.sub_auto,
                    subtitleslangs=[req.sub_lang],
                    subtitlesformat="srt/vtt/best",
                )
                if has_ffmpeg:
                    pps.append({"key": "FFmpegSubtitlesConvertor", "format": "srt", "when": "before_dl"})
                    if req.sub_mode == "embed":
                        pps.append({"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False})

        if req.trim:
            opts["download_ranges"] = download_range_func(None, [req.trim])
            opts["force_keyframes_at_cuts"] = True

        if req.sponsorblock and has_ffmpeg:
            pps.append({"key": "ModifyChapters", "remove_sponsor_segments": SPONSOR_CATEGORIES})
        if req.embed_metadata and has_ffmpeg:
            pps.append({"key": "FFmpegMetadata", "add_chapters": True, "add_metadata": True})
        if req.embed_thumbnail and has_ffmpeg and final_ext not in NO_THUMB_EXTS:
            opts["writethumbnail"] = True
            pps.insert(0, {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"})
            pps.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})

        opts["postprocessors"] = pps
        return opts

    def _download(self) -> None:
        opts = self._options()
        self.emit("progress", stage="Başlıyor…", frac=None)
        with yt_dlp.YoutubeDL(opts) as ydl:
            needs_sub_pp = self.req.mode == "video" and self._ffmpeg and (
                self.req.external_sub or self.req.ai_sub or (self.req.sub_lang and self.req.sub_mode == "burn"))
            if needs_sub_pp:
                ydl.add_post_processor(_SubtitlePP(self), when="after_move")
            ydl.download([self.req.url])

    # -- olaylar
    def _check_cancel(self) -> None:
        if self.cancelled:
            raise DownloadCancelled()

    def _on_progress(self, d: dict) -> None:
        self._check_cancel()
        info = d.get("info_dict") or {}
        prefix = ""
        if self.req.playlist and info.get("playlist_index"):
            prefix = f"[{info['playlist_index']}/{info.get('n_entries') or '?'}] "
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            frac = None
            if total:
                frac = d.get("downloaded_bytes", 0) / total
            elif d.get("fragment_count"):
                frac = (d.get("fragment_index") or 0) / d["fragment_count"]
            kind = "Ses" if info.get("vcodec") == "none" else "Video"
            self.emit(
                "progress",
                stage=f"{prefix}{kind} indiriliyor",
                title=info.get("title"),
                frac=frac,
                speed=d.get("speed"),
                eta=d.get("eta"),
                done_bytes=d.get("downloaded_bytes"),
                total_bytes=total,
            )
        elif d["status"] == "finished":
            self.emit("progress", stage=f"{prefix}İndirildi, işleniyor…", frac=1)

    _PP_STAGES = {
        "Merger": "Video ve ses birleştiriliyor",
        "ExtractAudio": "Sese dönüştürülüyor",
        "EmbedSubtitle": "Altyazı gömülüyor",
        "SubtitlesConvertor": "Altyazı hazırlanıyor",
        "EmbedThumbnail": "Kapak resmi ekleniyor",
        "Metadata": "Bilgiler ekleniyor",
        "ModifyChapters": "Sponsor bölümleri kesiliyor",
        "SponsorBlock": "Sponsor bölümleri aranıyor",
    }

    def _on_postprocess(self, d: dict) -> None:
        self._check_cancel()
        if d["status"] == "started" and d.get("postprocessor") in self._PP_STAGES:
            self.emit("progress", stage=self._PP_STAGES[d["postprocessor"]], frac=None)

    # -- ffmpeg ile altyazı işlemleri
    def _run_ffmpeg(self, args: list[str], cwd: str | None, duration: float | None, stage: str) -> None:
        cmd = [self._ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-nostats", "-progress", "pipe:1", *args]
        self._proc = subprocess.Popen(
            cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", creationflags=tools.NO_WINDOW,
        )
        stderr_lines: list[str] = []
        threading.Thread(target=lambda: stderr_lines.extend(self._proc.stderr), daemon=True).start()
        for line in self._proc.stdout:
            if line.startswith("out_time_us=") and duration:
                try:
                    frac = min(int(line.split("=")[1]) / 1e6 / duration, 1)
                except ValueError:
                    continue
                self.emit("progress", stage=stage, frac=frac)
        code = self._proc.wait()
        if self.cancelled:
            raise Cancelled
        if code != 0:
            raise RuntimeError("FFmpeg hatası: " + "".join(stderr_lines)[-400:])

    def burn_subtitle(self, video: Path, sub: Path, info: dict) -> Path:
        """Altyazıyı görüntüye kalıcı olarak yazar (her oynatıcıda görünür, yeniden kodlama gerekir)."""
        duration = info.get("duration")
        if self.req.trim:
            duration = self.req.trim[1] - self.req.trim[0]
        out = video.with_name(video.stem + " (altyazılı).mp4")
        with tempfile.TemporaryDirectory() as tmp:
            # subtitles filtresi Windows yollarındaki ':' ve '\' ile sorun çıkarır; kopyalayıp göreli ad kullanıyoruz
            local_sub = Path(tmp) / f"sub{sub.suffix.lower()}"
            shutil.copyfile(sub, local_sub)
            style = "FontName=Arial,FontSize=22,Outline=1.5,Shadow=0.5,MarginV=24"
            vf = f"subtitles={local_sub.name}" + ("" if local_sub.suffix == ".ass" else f":force_style='{style}'")
            # 0:V = kapak resmi olmayan ilk video akışı (MP4'e gömülü kapak yanlışlıkla seçilmesin)
            base = ["-i", str(video), "-map", "0:V:0", "-map", "0:a?", "-vf", vf,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-movflags", "+faststart"]
            try:
                self._run_ffmpeg([*base, "-c:a", "copy", str(out)], tmp, duration, "Altyazı videoya yakılıyor")
            except RuntimeError:
                if self.cancelled:
                    raise
                self._run_ffmpeg([*base, "-c:a", "aac", "-b:a", "192k", str(out)], tmp, duration,
                                 "Altyazı videoya yakılıyor")
        video.unlink(missing_ok=True)
        return out

    def embed_subtitle(self, video: Path, sub: Path, title: str = "Harici altyazı", lang: str | None = None) -> Path:
        """Altyazıyı ayrı bir iz olarak ekler (oynatıcıdan açılıp kapatılabilir)."""
        ext = video.suffix.lstrip(".").lower()
        tmp_out = video.with_name(video.stem + ".tmp" + video.suffix)
        index = str(self._sub_stream_count(video))
        meta = ["-metadata:s:s:" + index, f"title={title}"]
        if lang:
            meta += ["-metadata:s:s:" + index, f"language={lang}"]
        self._run_ffmpeg([
            "-i", str(video), "-i", str(sub), "-map", "0", "-map", "1:0",
            "-c", "copy", "-c:s", SUB_CODEC.get(ext, "copy"), *meta, str(tmp_out),
        ], None, None, "Altyazı ekleniyor")
        tmp_out.replace(video)
        return video

    def make_ai_subtitle(self, video: Path, info: dict) -> tuple[Path, str, str | None]:
        """Videonun konuşmasından (sitedeki altyazı ya da Whisper) hedef dilde .srt üretir.

        (srt yolu, altyazı izi başlığı, ffmpeg dil etiketi) döndürür.
        """
        from . import subtitles, transcribe  # ağır modüller; yalnızca gerektiğinde

        req = self.req
        progress = lambda frac, text: self.emit("progress", stage=text, frac=frac)  # noqa: E731
        progress(None, "Altyazı kaynağı aranıyor")
        found = subtitles.caption_cues(info, self.settings)
        if found:
            cues, src_lang, _source = found
            if req.trim:
                cues = subtitles.shift(cues, *req.trim)
        else:
            cues, src_lang = transcribe.transcribe(video, req.whisper_model, progress, lambda: self.cancelled)
        if self.cancelled:
            raise Cancelled
        cues = subtitles.merge(cues)
        if not cues:
            raise RuntimeError("Videoda yazıya dökülecek bir konuşma bulunamadı.")

        target = src_lang if req.ai_sub == "orig" else req.ai_sub
        if target != src_lang:
            progress(0, f"Altyazı {subtitles.LANG_NAMES.get(target, target)} diline çevriliyor")
            cues = subtitles.translate(
                cues, target, req.ai_provider, req.ai_key,
                lambda f: progress(f, f"Altyazı {subtitles.LANG_NAMES.get(target, target)} diline çevriliyor"),
                lambda: self.cancelled)
            if self.cancelled:
                raise Cancelled
            title = f"{subtitles.LANG_NAMES.get(target, target)} (AI çeviri)"
        else:
            title = f"{subtitles.LANG_NAMES.get(target, target)} (AI)"
        srt = subtitles.write_srt(cues, video.with_name(f"{video.stem}.{target}.srt"))
        return srt, title, subtitles.LANG_TAGS.get(target)

    def _sub_stream_count(self, video: Path) -> int:
        probe = Path(self._ffmpeg).with_name("ffprobe.exe" if self._ffmpeg.endswith(".exe") else "ffprobe")
        result = subprocess.run(
            [str(probe), "-v", "error", "-select_streams", "s", "-show_entries", "stream=index", "-of", "csv=p=0",
             str(video)],
            capture_output=True, text=True, creationflags=tools.NO_WINDOW,
        )
        return len([l for l in result.stdout.splitlines() if l.strip()])
