"""Stüdyo sekmelerinin (Reels, Görsel, Dublaj) arayüz köprüsü. api.Api bu sınıftan türer;
pywebview miras alınan genel metotları da JS'e açar."""
from __future__ import annotations

import base64
import io
import itertools
import mimetypes
import os
import re
import secrets
import tempfile
import threading
import urllib.parse
from pathlib import Path

import requests
import webview
from PIL import Image

from . import captions, dublaj, engine, i18n, imagegen, media, reels, services, subtitles, tts
from .config import decrypt_secret, encrypt_secret

SERVICE_KEYS = {"pollinations": "pollinations_key_enc", "cloudflare": "cloudflare_key_enc", "pexels": "pexels_key_enc",
                "elevenlabs": "elevenlabs_key_enc", "higgsfield": "higgsfield_key_enc"}
SERVICE_URLS = {
    "pollinations_keys": "https://enter.pollinations.ai",
    "cloudflare_ai": "https://dash.cloudflare.com/?to=/:account/ai/workers-ai",
    "pexels_keys": "https://www.pexels.com/api/",
    "elevenlabs_keys": "https://elevenlabs.io/app/settings/api-keys",
    "higgsfield_keys": "https://console.higgsfield.ai",
}
VIDEO_TYPES = ("Videolar (*.mp4;*.mov;*.mkv;*.webm;*.avi;*.m4v)", "Tüm dosyalar (*.*)")
AUDIO_TYPES = ("Ses dosyaları (*.mp3;*.m4a;*.wav;*.aac;*.ogg;*.flac)", "Tüm dosyalar (*.*)")
IMAGE_TYPES = ("Görseller (*.jpg;*.jpeg;*.png;*.webp)", "Tüm dosyalar (*.*)")


class _MediaServer:
    """Üretilen videoları uygulama içinde önizlemek için küçük yerel sunucu.
    WebView2, file:// sayfasından başka klasördeki videoyu oynatmıyor. Sunucu yalnızca 127.0.0.1'de
    dinler ve yalnızca kayıtlı dosyaları rastgele bir anahtarla verir (ileri/geri sarma için Range desteği)."""

    def __init__(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        files = self.files = {}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # konsola yazmasın
                pass

            def do_GET(self):
                token = self.path.strip("/").split("/")[0]
                path = files.get(token)
                if not path or not os.path.exists(path):
                    self.send_error(404)
                    return
                size = os.path.getsize(path)
                start, end = 0, size - 1
                rng = self.headers.get("Range", "")
                if rng.startswith("bytes="):
                    a, _, b = rng[6:].partition("-")
                    start = int(a) if a else max(0, size - int(b or 0))
                    end = min(int(b), size - 1) if a and b else end
                    self.send_response(206)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                else:
                    self.send_response(200)
                self.send_header("Content-Type", mimetypes.guess_type(path)[0] or "application/octet-stream")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(end - start + 1))
                self.end_headers()
                try:
                    with open(path, "rb") as f:
                        f.seek(start)
                        left = end - start + 1
                        while left > 0:
                            chunk = f.read(min(1 << 16, left))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            left -= len(chunk)
                except (ConnectionError, OSError):
                    pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def url(self, path: str) -> str:
        token = secrets.token_urlsafe(16)
        self.files[token] = path
        return f"http://127.0.0.1:{self.httpd.server_address[1]}/{token}/{urllib.parse.quote(Path(path).name)}"


def _preview(img: Image.Image, width: int = 640) -> str:
    im = img.copy()
    im.thumbnail((width, width * 2))
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=84)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _num(value, lo, hi, default):
    try:
        return max(lo, min(hi, type(default)(value)))
    except (TypeError, ValueError):
        return default


class StudioApi:
    def _studio_init(self) -> None:
        self._made_files: set[str] = set()  # TekTıkla'nın ürettiği, açılmasına izin verilen dosyalar
        self._picked_media: set[str] = set()  # kullanıcının seçtiği video/ses/görsel dosyaları
        self._img_bgs: dict[str, str] = {}  # kapak arka planları (yazıyı yeniden düzenlemek için)
        self._img_ids = itertools.count(1)
        self._reels_src: dict[int, reels.Source] = {}
        self._bg_dir = Path(tempfile.mkdtemp(prefix="tt_bg_"))
        self._media_srv: _MediaServer | None = None

    def _media_urls(self, files: list[str]) -> dict[str, str]:
        """Önizlenecek video/kapak dosyaları için yerel sunucu adresleri."""
        if self._media_srv is None:
            self._media_srv = _MediaServer()
        return {f: self._media_srv.url(f) for f in files if f.lower().endswith((".mp4", ".jpg", ".jpeg"))}

    # -- anahtarlar
    def _service_key(self, name: str) -> str:
        if name in ("gemini", "claude"):
            return self._api_key(name)
        setting = SERVICE_KEYS.get(name)
        return decrypt_secret(self._settings.get(setting, "")) if setting else ""

    def _all_keys(self) -> dict:
        return {name: self._service_key(name) for name in ("gemini", "claude", *SERVICE_KEYS)}

    def _services_status(self) -> dict:
        return {name: bool(self._service_key(name)) for name in SERVICE_KEYS}

    def _studio_settings(self) -> dict:
        s = dict(self._settings)
        s["_keys"] = self._all_keys()
        return s

    def save_service_key(self, name: str, value: str) -> dict:
        if name not in SERVICE_KEYS:
            return {"ok": False, "error": i18n.t("Bilinmeyen servis.")}
        problem = services.validate_key(name, value)
        if problem:
            return {"ok": False, "error": i18n.t(problem)}
        self._settings[SERVICE_KEYS[name]] = encrypt_secret(value.strip())
        self._settings.save()
        return {"ok": True, "services": self._services_status()}

    def delete_service_key(self, name: str) -> dict:
        if name in SERVICE_KEYS:
            self._settings[SERVICE_KEYS[name]] = ""
            self._settings.save()
        return self._services_status()

    def studio_init(self) -> dict:
        return {
            "services": {k: {**v, "uses": i18n.t(v["uses"]), "hint": i18n.t(v["hint"]),
                             "placeholder": i18n.t(v["placeholder"])} for k, v in services.SERVICES.items()},
            "service_keys": self._services_status(),
            "tts_engines": tts.ENGINES,
            "image_providers": imagegen.PROVIDERS,
            "edge_voices": {lang: [(vid, re.sub(r"Erkek|Kadın", lambda m: i18n.t(m.group(0)), label))
                                   for vid, label in voices] for lang, voices in tts.EDGE_VOICES.items()},
            "gemini_voices": [(vid, " · ".join(i18n.t(part) for part in label.split(" · ")))
                              for vid, label in services.GEMINI_VOICES],
            "dub_languages": [[c, n] for c, n, _ in subtitles.LANGUAGES] + [["hi", "हिन्दी"], ["id", "Bahasa Indonesia"]],
        }

    # -- dosya seçme / açma
    def _pick(self, types) -> str | None:
        result = self._window.create_file_dialog(webview.FileDialog.OPEN, file_types=types)
        if result:
            path = os.path.normpath(result[0] if isinstance(result, (list, tuple)) else result)
            self._picked_media.add(path)
            return path
        return None

    def pick_video(self) -> str | None:
        return self._pick(VIDEO_TYPES)

    def pick_audio(self) -> str | None:
        return self._pick(AUDIO_TYPES)

    def pick_image(self) -> str | None:
        return self._pick(IMAGE_TYPES)

    def open_made(self, path: str) -> None:
        if path in self._made_files and os.path.exists(path):
            os.startfile(path)

    def reveal_made(self, path: str) -> None:
        if path in self._made_files:
            self._reveal(path)

    def read_made(self, path: str) -> str:
        """Reels açıklama dosyasını (.txt) panoya kopyalamak için okur."""
        if path in self._made_files and path.lower().endswith(".txt") and os.path.exists(path):
            return Path(path).read_text(encoding="utf-8")
        return ""

    def tts_voices(self, engine_name: str, lang: str) -> dict:
        try:
            return {"ok": True, "voices": tts.voices(engine_name, lang, self._all_keys())}
        except services.ServiceError as e:
            return {"ok": False, "error": str(e), "voices": []}

    def _out_dir(self, sub: str) -> Path:
        return Path(self._settings["download_dir"]) / sub

    # -- görsel stüdyosu
    def image_generate(self, opts: dict, token: int) -> dict:
        mode = "thumbnail" if opts.get("mode") == "thumbnail" else "image"
        idea = (opts.get("idea") or "").strip()
        aspect = opts.get("aspect") if opts.get("aspect") in imagegen.ASPECTS else "16:9"
        style = opts.get("style") if opts.get("style") in imagegen.STYLES else "auto"
        provider = opts.get("provider") if opts.get("provider") in imagegen.PROVIDERS else "pollinations"
        count = _num(opts.get("count"), 1, 4, 1)
        bg = opts.get("bg") if mode == "thumbnail" and opts.get("bg") in ("ai", "video", "file") else "ai"
        title, subtitle = (opts.get("title") or "").strip()[:80], (opts.get("subtitle") or "").strip()[:60]
        if bg == "ai" and not idea:
            return {"ok": False, "error": i18n.t("Önce bir fikir ya da açıklama yazın.")}
        if bg == "file" and opts.get("file") not in self._picked_media:
            return {"ok": False, "error": i18n.t("Önce bir görsel seçin.")}
        cached = self._media.get(opts.get("video_url") or "") if bg == "video" else None
        if bg == "video" and not cached:
            return {"ok": False, "error": i18n.t("Önce İndir sekmesinde bir video analiz edin.")}
        if bg != "ai" and not (title or idea):
            return {"ok": False, "error": i18n.t("Kapak başlığını yazın.")}
        needs = imagegen.PROVIDERS[provider]["needs"]
        keys = self._all_keys()
        if bg == "ai" and needs and not keys.get(needs):
            return {"ok": False, "error": i18n.t("Bu servis için Ayarlar > Servisler'den anahtar girin.")}
        self._settings["image_provider"] = provider
        self._settings.save()
        lang = i18n.current()

        def stage(text: str, frac=None):
            self._emit("img_stage", token=token, text=i18n.t(text), frac=frac)

        def work():
            try:
                plan = None
                if bg == "ai" or (mode == "thumbnail" and not title):
                    stage("Fikir görsel istemine çevriliyor")
                    plan = imagegen.plan(idea or title, purpose=mode, style=style, aspect=aspect,
                                         provider=self._provider(), api_key=self._api_key(),
                                         language=i18n.language_name(lang))
                backgrounds: list[Image.Image] = []
                if bg == "video":
                    info = cached[0]
                    thumbs = [t for t in (info.raw or {}).get("thumbnails") or [] if t.get("url")]
                    best = max(thumbs, key=lambda t: (t.get("width") or 0) * (t.get("height") or 0), default=None)
                    url = best["url"] if best else info.thumbnail
                    r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
                    r.raise_for_status()
                    backgrounds.append(Image.open(io.BytesIO(r.content)).convert("RGB"))
                elif bg == "file":
                    backgrounds.append(Image.open(opts["file"]).convert("RGB"))
                else:
                    for i in range(count):
                        stage(f"Görsel üretiliyor ({i + 1}/{count})", i / count)
                        backgrounds.append(imagegen.generate(
                            provider, plan.prompt, aspect, keys,
                            on_wait=lambda s, i=i: self._emit("img_stage", token=token, text=s, frac=i / count)))
                final_title = title or (plan.title if plan else idea)
                final_sub = subtitle or (plan.subtitle if plan and not title else "")
                folder = self._out_dir(i18n.t("Görseller"))
                for i, img in enumerate(backgrounds):
                    img_id = str(next(self._img_ids))
                    raw = self._bg_dir / f"{img_id}.png"
                    img.save(raw)
                    self._img_bgs[img_id] = str(raw)
                    if mode == "thumbnail":
                        out = imagegen.compose(img, final_title, final_sub, aspect=aspect,
                                               layout=opts.get("layout", "left"), style=opts.get("text_style", "bold"),
                                               accent=opts.get("accent", "yellow"), lang=lang)
                    else:
                        out = imagegen.cover(img, imagegen.ASPECTS[aspect]) if img.width / img.height != \
                            imagegen.ASPECTS[aspect][0] / imagegen.ASPECTS[aspect][1] else img
                    name = (final_title if mode == "thumbnail" else (idea or final_title))[:60]
                    path = imagegen.save(out, folder, f"{name} ({i18n.t('kapak') if mode == 'thumbnail' else aspect.replace(':', 'x')})")
                    self._made_files.add(str(path))
                    self._emit("img_item", token=token, id=img_id, path=str(path), data=_preview(out),
                               aspect=aspect, mode=mode)
                self._emit("img_done", token=token, title=final_title, subtitle=final_sub,
                           prompt=plan.prompt if plan else "")
            except Exception as e:  # noqa: BLE001
                self._emit("img_error", token=token, message=i18n.t(str(e)) if isinstance(e, services.ServiceError)
                           else engine.friendly_error(e))

        self._bg(work)
        return {"ok": True}

    def image_recompose(self, opts: dict) -> dict:
        """Üretilmiş arka plana başlığı yeniden yazar (görseli tekrar üretmeden)."""
        raw = self._img_bgs.get(str(opts.get("id")))
        if not raw or not os.path.exists(raw):
            return {"ok": False, "error": i18n.t("Bu görselin arka planı artık yok, yeniden üretin.")}
        aspect = opts.get("aspect") if opts.get("aspect") in imagegen.ASPECTS else "16:9"
        img = imagegen.compose(Image.open(raw).convert("RGB"), (opts.get("title") or "")[:80],
                               (opts.get("subtitle") or "")[:60], aspect=aspect, layout=opts.get("layout", "left"),
                               style=opts.get("text_style", "bold"), accent=opts.get("accent", "yellow"),
                               lang=i18n.current())
        path = imagegen.save(img, self._out_dir(i18n.t("Görseller")), f"{(opts.get('title') or 'kapak')[:60]} ({i18n.t('kapak')})")
        self._made_files.add(str(path))
        return {"ok": True, "path": str(path), "data": _preview(img)}

    # -- Reels
    def _edit(self, opts: dict, lang: str) -> reels.Edit:
        cap = captions.Options(
            style=opts.get("cap_style") if opts.get("cap_style") in ("pop", "karaoke", "box", "minimal", "none") else "pop",
            accent=opts.get("accent") if opts.get("accent") in captions.ACCENTS else "yellow",
            position=opts.get("position") if opts.get("position") in captions.POSITIONS else "bottom",
            words_per_chunk=_num(opts.get("words"), 1, 4, 3), uppercase=bool(opts.get("uppercase", True)), lang=lang)
        music = opts.get("music") if opts.get("music") in self._picked_media else None
        return reels.Edit(frame=opts.get("frame") if opts.get("frame") in ("smart", "blur", "center") else "smart",
                          caption=cap, hook=bool(opts.get("hook", True)), cut_silence=bool(opts.get("cut", True)),
                          zoom=bool(opts.get("zoom", True)), progress_bar=bool(opts.get("bar", True)), music=music,
                          music_volume=_num(opts.get("music_volume"), 0.02, 1.0, 0.14),
                          watermark=(opts.get("watermark") or "").strip()[:40])

    def reels_analyze(self, opts: dict, token: int) -> dict:
        source = (opts.get("source") or "").strip()
        is_url = bool(source.lower().startswith(("http://", "https://")))
        if not is_url and source not in self._picked_media:
            return {"ok": False, "error": i18n.t("Bir video linki yapıştırın ya da bilgisayardan video seçin.")}
        lo, hi = {"short": (15, 30), "medium": (30, 60), "long": (60, 90)}.get(opts.get("length"), (30, 60))
        count = _num(opts.get("count"), 1, 10, 5)
        cached = self._media.get(source) if is_url else None
        info = cached[0].raw if cached and not cached[0].is_playlist else None
        settings = self._studio_settings()
        provider, key = self._provider(), self._api_key()
        lang_name = i18n.language_name(i18n.current())

        def stage(text: str, frac=None):
            self._emit("reels_stage", token=token, text=i18n.t(text), frac=frac)

        def work():
            try:
                src = reels.load_source(source, settings, info=info, on_stage=stage)
                clips = reels.find_clips(src, provider=provider, api_key=key, lo=lo, hi=hi, count=count,
                                         language=lang_name, on_stage=stage)
                self._reels_src[token] = src
                thumb = cached[1] if cached else None
                self._emit("reels_done", token=token, clips=clips, ai=bool(key),
                           source={"title": src.title, "duration": engine.human_time(src.duration),
                                   "lang": src.lang, "words": len(src.words), "thumb": thumb, "local": src.is_local})
            except Exception as e:  # noqa: BLE001
                self._emit("reels_error", token=token, message=i18n.t(str(e)) if isinstance(e, services.ServiceError)
                           else engine.friendly_error(e))

        self._bg(work)
        return {"ok": True}

    def reels_render(self, opts: dict) -> dict:
        src = self._reels_src.get(opts.get("token"))
        if not src:
            return {"ok": False, "error": i18n.t("Önce en iyi anları bulun.")}
        clips = [c for c in opts.get("clips") or [] if isinstance(c, dict)]
        if not clips:
            return {"ok": False, "error": i18n.t("En az bir klip seçin.")}
        edit = self._edit(opts, src.lang)
        out_dir = self._out_dir("Reels")
        thumb = self._media.get(src.key, (None, None))[1] if not src.is_local else None
        for n, c in enumerate(clips, 1):
            try:
                a, b = float(c["start"]), float(c["end"])
            except (KeyError, TypeError, ValueError):
                continue
            if b - a < 3:
                continue
            clip = {**c, "start": a, "end": b}
            label = f"Reels · {engine.human_time(a)}–{engine.human_time(b)}"
            task = media.StudioTask(
                "reels", clip.get("title") or src.title, src.url or str(src.path), str(out_dir), label,
                i18n.t("Reels hazır: {title}", title=clip.get("title") or src.title),
                lambda s, emit, clip=clip, n=n: reels.ClipJob(s, emit, src, clip, n, edit, out_dir))
            self._enqueue(task, thumb)
        return {"ok": True, "count": len(clips)}

    def reels_idea(self, opts: dict) -> dict:
        idea = (opts.get("idea") or "").strip()
        if len(idea) < 4:
            return {"ok": False, "error": i18n.t("Videonun fikrini ya da metnini yazın.")}
        lang = opts.get("lang") or i18n.current()
        engine_name = opts.get("voice_engine") if opts.get("voice_engine") in tts.ENGINES else "edge"
        visuals = opts.get("visuals") if opts.get("visuals") in ("stock", "image", "video", "plain") else "plain"
        keys = self._all_keys()
        need = {"gemini": "gemini", "elevenlabs": "elevenlabs"}.get(engine_name)
        if need and not keys.get(need):
            return {"ok": False, "error": i18n.t("Bu ses için Ayarlar'dan anahtar girin.")}
        if visuals == "stock" and not keys.get("pexels"):
            return {"ok": False, "error": i18n.t("Stok video için Ayarlar > Servisler'e ücretsiz Pexels anahtarı girin.")}
        if visuals == "video" and not keys.get("higgsfield"):
            return {"ok": False, "error": i18n.t("AI video için Ayarlar > Servisler'e Higgsfield anahtarı girin (ücretli).")}
        idea_opts = reels.IdeaOptions(
            seconds=_num(opts.get("seconds"), 15, 120, 45), own_script=bool(opts.get("own_script")), language=lang,
            language_name=i18n.language_name(lang), voice_engine=engine_name, voice=opts.get("voice") or "",
            visuals=visuals, image_provider=opts.get("image_provider") if opts.get("image_provider") in imagegen.PROVIDERS
            else "pollinations", provider=self._provider(), api_key=self._api_key())
        edit = self._edit(opts, lang)
        out_dir = self._out_dir("Reels")
        title = " ".join(idea.split()[:8])
        task = media.StudioTask("idea", title, "", str(out_dir), i18n.t("Fikirden Reels"),
                                i18n.t("Reels hazır: {title}", title=title),
                                lambda s, emit: reels.IdeaJob(s, emit, idea, idea_opts, edit, out_dir))
        self._enqueue(task, None)
        return {"ok": True}

    # -- dublaj
    def dub_start(self, opts: dict) -> dict:
        source = (opts.get("source") or "").strip()
        is_url = bool(source.lower().startswith(("http://", "https://")))
        if not is_url and source not in self._picked_media:
            return {"ok": False, "error": i18n.t("Bir video linki yapıştırın ya da bilgisayardan video seçin.")}
        engine_name = opts.get("engine") if opts.get("engine") in tts.ENGINES else "edge"
        keys = self._all_keys()
        if engine_name == "elevenlabs" and not keys.get("elevenlabs"):
            return {"ok": False, "error": i18n.t("ElevenLabs için Ayarlar > Servisler'e anahtar girin.")}
        if engine_name == "gemini" and not keys.get("gemini"):
            return {"ok": False, "error": i18n.t("Gemini sesi için Ayarlar > Yapay Zekâ'ya Gemini anahtarı girin.")}
        target = opts.get("target") or "tr"
        dub_opts = dublaj.DubOptions(target=target, engine=engine_name, voice=opts.get("voice") or "",
                                     original="mute" if opts.get("original") == "mute" else "duck",
                                     keep_original_track=bool(opts.get("keep", True)),
                                     subtitles=bool(opts.get("subs", True)), provider=self._provider(),
                                     api_key=self._api_key())
        cached = self._media.get(source) if is_url else None
        title = cached[0].title if cached else (Path(source).stem if not is_url else source)
        info = cached[0].raw if cached and not cached[0].is_playlist else None
        out_dir = self._out_dir(i18n.t("Dublaj"))
        lang_name = dict((c, n) for c, n in self.studio_init()["dub_languages"]).get(target, target)
        task = media.StudioTask("dub", title, source if is_url else "", str(out_dir),
                                i18n.t("Dublaj · {lang}", lang=lang_name),
                                i18n.t("Dublaj hazır: {title}", title=title),
                                lambda s, emit: dublaj.DubJob(s, emit, source, title, dub_opts, out_dir, info))
        self._enqueue(task, cached[1] if cached else None)
        return {"ok": True}
