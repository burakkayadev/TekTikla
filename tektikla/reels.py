"""Reels Stüdyosu: uzun videodan Instagram Reels / TikTok / Shorts klipleri ve fikirden Reels.

Videodan Reels (tamamen ücretsiz yapılabilir):
  1. Kelime kelime döküm (YouTube altyazısı ya da bilgisayarda Whisper)
  2. Yapay zekâ en çok izlenecek anları seçer (Gemini ücretsiz / Claude); anahtar yoksa basit puanlama
  3. Her klip: dikey 9:16 kadraj (yüz takibi / bulanık arka plan / ortadan kırpma), sessizlikleri kesme,
     dinamik zoom, kelime kelime animasyonlu altyazı, kanca başlığı, ilerleme çubuğu, müzik, ses dengeleme
"""
from __future__ import annotations

import random
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yt_dlp
from PIL import Image
from pydantic import BaseModel, Field
from yt_dlp.utils import download_range_func

from . import ai, captions, engine, imagegen, llm, media, services, vision, words as W
from .imagegen import FONTS_DIR

OUT_W, OUT_H, FPS = 1080, 1920, 30
CAPTION_FONTS = ("TekTikla-Display.ttf", "TekTikla-Condensed.ttf", "TekTikla-Black.ttf")
MAX_SOURCE_SECONDS = 4 * 3600


# ----------------------------------------------------------------------------- analiz

class ClipIdea(BaseModel):
    start: float = Field(description="Klibin başladığı saniye (dökümdeki zamanlardan)")
    end: float = Field(description="Klibin bittiği saniye")
    title: str = Field(description="Klibin kısa adı (en fazla 8 kelime)")
    hook: str = Field(description="İlk 3 saniyede ekranın üstünde görünecek merak uyandıran kanca yazısı, en fazla 7 kelime")
    caption: str = Field(description="Instagram/TikTok gönderi açıklaması: 1-2 cümle, birkaç emoji olabilir")
    hashtags: list[str] = Field(description="5-8 etiket, # işareti olmadan")
    score: int = Field(description="0-100 arası viral olma potansiyeli puanı")
    reason: str = Field(description="Bu anın neden işe yarayacağı, tek cümle")


class ClipPlan(BaseModel):
    clips: list[ClipIdea]


REELS_SYSTEM = """Sen viral kısa video (Reels, TikTok, Shorts) kurgucususun. Uzun bir videonun zaman damgalı
dökümünden, tek başına izlendiğinde anlamlı ve izleyiciyi sonuna kadar tutacak en iyi anları seçiyorsun.

Kurallar:
- Her klip kendi içinde anlaşılır olsun: bir cümlenin ortasında başlayıp bitmesin, bağlamsız "o", "bunu" ile başlamasın.
- İlk cümle güçlü bir kanca olsun (soru, şaşırtıcı bilgi, iddia, duygu).
- Tercih: komik, şaşırtıcı, duygusal, tartışmalı ya da çok faydalı (ipucu, sır, hata) anlar.
- start/end değerleri dökümdeki satır zamanlarından alınsın; istenen süre aralığına uysun.
- Klipler birbiriyle çakışmasın. En iyi klip en yüksek puanı alsın.
- title, hook, caption ve hashtags istenen dilde yazılsın."""


@dataclass
class Source:
    key: str  # link ya da dosya yolu
    title: str
    duration: float
    words: list[W.Word]
    lang: str
    url: str | None = None
    path: Path | None = None
    thumbnail: str | None = None
    info: dict | None = field(default=None, repr=False)

    @property
    def is_local(self) -> bool:
        return self.path is not None


def _fmt(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


def load_source(source: str, settings: dict, *, info: dict | None = None,
                on_stage: Callable[[str, float | None], None] = lambda s, f=None: None,
                should_stop: Callable[[], bool] = lambda: False) -> Source:
    """Kaynağı hazırlar ve kelime kelime dökümünü çıkarır."""
    whisper_model = settings.get("whisper_model", "small")
    progress = lambda f, s: on_stage(s, f)  # noqa: E731
    path = Path(source)
    if not re.match(r"^https?://", source, re.I) and path.exists():
        on_stage("Video okunuyor", None)
        meta = media.probe(path)
        ws, lang = W.whisper_words(path, whisper_model, progress, should_stop)
        return Source(str(path), path.stem, meta["duration"], ws, lang, path=path)

    if info is None:
        on_stage("Video bilgileri alınıyor", None)
        info = ai.extract_info(source, settings)
    duration = float(info.get("duration") or 0)
    if duration > MAX_SOURCE_SECONDS:
        raise RuntimeError("Video 4 saatten uzun; Reels için daha kısa bir video seçin.")
    on_stage("Kelime kelime döküm çıkarılıyor", None)
    found = W.youtube_words(info, settings)
    if found:
        ws, lang = found
    else:
        with tempfile.TemporaryDirectory() as tmp:
            on_stage("Videonun sesi indiriliyor", None)
            opts = engine.base_opts(settings) | {"format": "ba/b", "noplaylist": True,
                                                 "outtmpl": str(Path(tmp) / "ses.%(ext)s")}
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([info.get("webpage_url") or source])
            audio = next(Path(tmp).glob("ses.*"), None)
            if not audio:
                raise RuntimeError("Videonun sesi indirilemedi.")
            ws, lang = W.whisper_words(audio, whisper_model, progress, should_stop)
    return Source(source, info.get("title") or "Video", duration, ws, lang, url=info.get("webpage_url") or source,
                  thumbnail=info.get("thumbnail"), info=info)


def _normalize(src: Source, clips: list[dict], lo: float, hi: float, count: int) -> list[dict]:
    """Yapay zekânın verdiği aralıkları kelime sınırlarına yaslar, süreyi düzeltir, çakışanları atar."""
    lines = W.lines(src.words)
    out: list[dict] = []
    for c in sorted(clips, key=lambda c: -c.get("score", 0)):
        a, b = max(0.0, float(c["start"])), min(src.duration or 1e9, float(c["end"]))
        if b - a < lo * 0.6:  # çok kısaysa sonraki satırlarla uzat
            for ln in lines:
                if ln.start >= b - 0.05 and ln.end - a <= hi:
                    b = ln.end
                if b - a >= lo:
                    break
        if b - a > hi * 1.15:  # çok uzunsa satır sınırında kes
            cut = [ln.end for ln in lines if a < ln.end <= a + hi]
            b = cut[-1] if cut else a + hi
        if src.words:
            a, b = W.snap(src.words, a, b)
        if b - a < 5 or any(not (b <= o["start"] or a >= o["end"]) for o in out):
            continue
        out.append({**c, "start": round(a, 2), "end": round(b, 2), "duration": round(b - a, 1),
                    "range": f"{_fmt(a)} – {_fmt(b)}"})
        if len(out) >= count:
            break
    return sorted(out, key=lambda c: -c.get("score", 0))


def _heuristic(src: Source, lo: float, hi: float, count: int) -> list[dict]:
    """Yapay zekâ anahtarı yoksa: konuşma yoğunluğu ve soru/ünlem işaretlerine göre basit seçim."""
    lines = W.lines(src.words)
    target = (lo + hi) / 2
    candidates = []
    for i, first in enumerate(lines):
        group, j = [], i
        while j < len(lines) and lines[j].end - first.start <= hi:
            group.append(lines[j])
            j += 1
        if not group or group[-1].end - first.start < lo:
            continue
        span = group[-1].end - first.start
        n_words = sum(len(g.words) for g in group)
        punch = sum(g.text.count("?") + g.text.count("!") for g in group)
        score = n_words / span * (1 + 0.25 * punch) * (1 - abs(span - target) / hi * 0.3)
        candidates.append((score, first.start, group[-1].end, first.text))
    if not candidates and src.duration:  # konuşma yoksa eşit aralıklı parçalar
        step = max(target, src.duration / (count + 1))
        candidates = [(1, t, min(t + target, src.duration), src.title) for t in
                      [step * k for k in range(count)] if t + 5 < src.duration]
    best = max((c[0] for c in candidates), default=1) or 1
    clips = [{"start": a, "end": b, "title": " ".join(text.split()[:8]), "hook": " ".join(text.split()[:7]),
              "caption": text[:150], "hashtags": [], "score": int(60 + 35 * s / best),
              "reason": "Konuşmanın en yoğun ve hareketli bölümü (yapay zekâ anahtarı olmadan seçildi)"}
             for s, a, b, text in sorted(candidates, reverse=True)]
    return clips


def find_clips(src: Source, *, provider: str, api_key: str, lo: float, hi: float, count: int, language: str,
               on_stage: Callable[[str, float | None], None] = lambda s, f=None: None) -> list[dict]:
    if not src.words:
        return _normalize(src, _heuristic(src, lo, hi, count), lo, hi, count)
    if not api_key:
        on_stage("Konuşma puanlanıyor (yapay zekâ anahtarı yok)", None)
        return _normalize(src, _heuristic(src, lo, hi, count), lo, hi, count)
    on_stage("Yapay zekâ en iyi anları seçiyor", None)
    transcript = "\n".join(f"[{ln.start:.1f}-{ln.end:.1f}] {ln.text}" for ln in W.lines(src.words))
    prompt = (f"Video: {src.title}\nSüre: {src.duration:.0f} sn\nİstenen klip sayısı: {count + 2}\n"
              f"Her klibin süresi: {lo:.0f}-{hi:.0f} saniye\nYanıt dili: {language}\n\n"
              f"<dokum>\n{transcript[:400_000]}\n</dokum>")
    plan = llm.generate(provider, api_key, REELS_SYSTEM, prompt, ClipPlan, effort="medium")
    clips = [c.model_dump() for c in plan.clips]
    result = _normalize(src, clips, lo, hi, count)
    return result or _normalize(src, _heuristic(src, lo, hi, count), lo, hi, count)


# ----------------------------------------------------------------------------- kurgu ayarları

@dataclass
class Edit:
    frame: str = "smart"  # smart (yüz takibi) | blur (bulanık arka plan) | center (ortadan kırp)
    caption: captions.Options = field(default_factory=captions.Options)
    hook: bool = True
    cut_silence: bool = True
    zoom: bool = True
    progress_bar: bool = True
    music: str | None = None
    music_volume: float = 0.14
    watermark: str = ""


def _shots(spans: list[tuple[float, float]], clip_words: list[W.Word], zoom: bool) -> list[tuple[float, float, float]]:
    """Konuşulan aralıkları cümle sınırlarından 2-6 sn'lik çekimlere böler; zoom açıksa yakın/uzak sırayla."""
    shots: list[tuple[float, float, float]] = []
    breaks = sorted({round(ln.end, 2) for ln in W.lines(clip_words, max_words=14)})
    level = 0
    for a, b in spans:
        cur = a
        cuts = [t for t in breaks if a + 1.8 < t < b - 1.2]
        for t in cuts + [b]:
            if t - cur < 1.8 and t != b:
                continue
            while t - cur > 6.5 and zoom:  # uzun çekimleri böl ki görüntü canlı kalsın
                shots.append((cur, cur + 4.0, 1.0 if level % 2 == 0 else 1.14))
                cur += 4.0
                level += 1
            shots.append((cur, t, 1.0 if level % 2 == 0 or not zoom else 1.14))
            cur = t
            level += 1
    return shots or [(spans[0][0], spans[-1][1], 1.0)]


def _escape_path(p: str) -> str:
    return p.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


class ClipJob(media.Job):
    """Tek bir Reels klibini üretir (indirme kuyruğunda görünür)."""

    def __init__(self, settings: dict, emit, src: Source, clip: dict, number: int, edit: Edit, out_dir: Path):
        super().__init__(settings, emit)
        self.src, self.clip, self.number, self.edit, self.out_dir = src, clip, number, edit, out_dir

    # -- kaynak parçası
    def _segment(self, tmp: Path) -> tuple[Path, float]:
        """(dosya, dosyada klibin başladığı saniye)"""
        a, b = float(self.clip["start"]), float(self.clip["end"])
        if self.src.is_local:
            return self.src.path, a
        pre = min(0.5, a)
        opts = engine.base_opts(self.settings) | {
            "format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/b",
            "merge_output_format": "mp4", "noplaylist": True, "outtmpl": str(tmp / "kaynak.%(ext)s"),
            "download_ranges": download_range_func(None, [(a - pre, b + 0.4)]), "force_keyframes_at_cuts": True,
            "progress_hooks": [self._dl_progress],
        }
        self.stage("Klip bölümü indiriliyor", 0)
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([self.src.url])
        files = [f for f in tmp.glob("kaynak.*") if f.suffix in (".mp4", ".mkv", ".webm")]
        if not files:
            raise RuntimeError("Klip bölümü indirilemedi.")
        return files[0], pre

    def _dl_progress(self, d: dict) -> None:
        self.check()
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            self.emit("progress", stage="Klip bölümü indiriliyor",
                      frac=(d.get("downloaded_bytes", 0) / total * 0.3) if total else None)

    # -- ana iş
    def work(self) -> list[str]:
        clip, edit = self.clip, self.edit
        a, b = float(clip["start"]), float(clip["end"])
        tmp = Path(tempfile.mkdtemp(prefix="tt_reels_"))
        try:
            seg, offset = self._segment(tmp)
            info = media.probe(seg)
            dur = min(b - a, max(0.5, info["duration"] - offset)) if info["duration"] else b - a
            clip_words = W.between(self.src.words, a, a + dur)

            spans = W.speech_spans(clip_words) if edit.cut_silence and clip_words else [(0.0, dur)]
            spans = [(max(0.0, s), min(dur, e)) for s, e in spans if min(dur, e) - max(0.0, s) > 0.25]
            if not spans or sum(e - s for s, e in spans) < dur * 0.35:
                spans = [(0.0, dur)]
            out_words = W.remap(clip_words, spans) if len(spans) > 1 or spans[0] != (0.0, dur) else clip_words
            out_dur = sum(e - s for s, e in spans)
            shots = _shots(spans, clip_words, edit.zoom)

            src_w, src_h = info["width"] or 1920, info["height"] or 1080
            centers = [0.5] * len(shots)
            frame = edit.frame
            if src_w / src_h < 0.7 and frame == "blur":
                frame = "center"  # zaten dikey
            if frame == "smart" and src_w / src_h > 0.7:
                try:
                    self.stage("Yüzler takip ediliyor (akıllı kırpma)", 0.32)
                    track = vision.face_track(seg, lambda f, s: self.emit("progress", stage=s, frac=0.32 + f * 0.13),
                                              lambda: self.cancelled, start=offset, duration=dur)
                    centers = vision.crop_centers(track, [(s, e) for s, e, _z in shots])
                except Exception as e:  # noqa: BLE001 - kırpma başarısızsa ortadan devam
                    self.check()
                    self.warnings.append(f"Akıllı kırpma yapılamadı, ortadan kırpıldı ({str(e)[:120]}).")

            ass = captions.build(out_words, out_dur, edit.caption, hook=clip.get("hook", "") if edit.hook else "",
                                 progress_bar=edit.progress_bar, watermark=edit.watermark)
            (tmp / "altyazi.ass").write_text(ass, encoding="utf-8")
            fonts = tmp / "fonts"
            fonts.mkdir()
            for name in CAPTION_FONTS:
                if (FONTS_DIR / name).exists():
                    shutil.copy2(FONTS_DIR / name, fonts / name)

            graph, maps = self._graph(shots, centers, frame, src_w, src_h, offset, info["has_audio"], out_dur)
            out = self._out_path()
            args = ["-ss", f"{offset:.3f}", "-t", f"{dur + 0.05:.3f}", "-i", str(seg)]
            if edit.music and Path(edit.music).exists():
                args += ["-stream_loop", "-1", "-i", str(edit.music)]
            args += ["-filter_complex", graph, *maps,
                     "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                     "-profile:v", "high", "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
                     "-movflags", "+faststart", "-shortest", str(out)]
            self.ffmpeg(args, out_dur, "Reels kurgulanıyor", (0.45, 0.97), cwd=str(tmp))
            # ana video en sonda: kuyruktaki "Aç" son dosyayı açar
            return self._extras(out, seg, offset, shots, centers, frame, src_w, src_h) + [str(out)]
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def ffmpeg(self, args, duration, stage, span=(0, 1), cwd=None):  # noqa: D401 - cwd destekli sürüm
        a, b = span
        self.stage(stage, a)
        media.run_ffmpeg(args, duration=duration, job=self, cwd=cwd,
                         on_progress=lambda f: self.emit("progress", stage=stage, frac=a + (b - a) * f))

    def _graph(self, shots, centers, frame, sw, sh, offset, has_audio, out_dur) -> tuple[str, list[str]]:
        n = len(shots)
        parts = [f"[0:v]split={n}" + "".join(f"[s{i}]" for i in range(n))]
        if has_audio:
            parts.append(f"[0:a]asplit={n}" + "".join(f"[t{i}]" for i in range(n)))
        for i, ((s, e, zoom), cx) in enumerate(zip(shots, centers)):
            chain = f"[s{i}]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS,"
            if frame == "blur":
                fw = int(OUT_W * zoom) // 2 * 2
                parts.append(chain + f"split[bg{i}][fg{i}]")
                parts.append(f"[bg{i}]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,"
                             f"boxblur=12:2,eq=brightness=-0.06,scale={OUT_W}:{OUT_H}[b{i}]")
                parts.append(f"[fg{i}]scale={fw}:-2,crop=min(iw\\,{OUT_W}):ih[f{i}]")
                parts.append(f"[b{i}][f{i}]overlay=(W-w)/2:(H-h)/2,setsar=1[v{i}]")
            else:
                if sw / sh >= 9 / 16:
                    ch = int(sh / zoom) // 2 * 2
                    cw = int(ch * 9 / 16) // 2 * 2
                else:
                    cw = int(sw / zoom) // 2 * 2
                    ch = int(cw * 16 / 9) // 2 * 2
                x = int(min(max(cx * sw - cw / 2, 0), sw - cw))
                y = int(min(max((sh - ch) * (0.42 if zoom > 1 else 0.5), 0), sh - ch))
                parts.append(chain + f"crop={cw}:{ch}:{x}:{y},scale={OUT_W}:{OUT_H}:flags=lanczos,setsar=1[v{i}]")
            if has_audio:
                parts.append(f"[t{i}]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{i}]")
            else:
                parts.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={e - s:.3f}[a{i}]")
        parts.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vc][ac]")
        parts.append(f"[vc]fps={FPS},ass=altyazi.ass:fontsdir=fonts,format=yuv420p[vout]")
        fade = f"afade=t=out:st={max(0, out_dur - 0.35):.2f}:d=0.35"
        if self.edit.music and Path(self.edit.music).exists():
            vol = max(0.02, min(self.edit.music_volume, 1.0))
            parts.append(f"[1:a]aresample=48000,volume={vol:.3f}[mus]")
            parts.append("[ac]aresample=48000,asplit=2[voice][key]")
            parts.append("[mus][key]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[duck]")
            parts.append(f"[voice][duck]amix=inputs=2:duration=first:normalize=0,{fade},"
                         "loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
        else:
            parts.append(f"[ac]aresample=48000,{fade},loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
        return ";".join(parts), ["-map", "[vout]", "-map", "[aout]"]

    def _out_path(self) -> Path:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        base = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", self.clip.get("title") or self.src.title).strip()[:70]
        path = self.out_dir / f"{base or 'Reels'} - reels {self.number}.mp4"
        n = 2
        while path.exists():
            path = self.out_dir / f"{base or 'Reels'} - reels {self.number} ({n}).mp4"
            n += 1
        return path

    def _extras(self, out: Path, seg: Path, offset, shots, centers, frame, sw, sh) -> list[str]:
        """Gönderi açıklaması (.txt) ve kanca yazılı kapak görseli (.jpg)."""
        clip = self.clip
        tags = " ".join("#" + re.sub(r"\W+", "", t) for t in clip.get("hashtags") or [] if re.sub(r"\W+", "", t))
        text = "\n\n".join(x for x in (clip.get("title", ""), clip.get("caption", ""), tags) if x)
        txt = out.with_suffix(".txt")
        txt.write_text(text + "\n", encoding="utf-8")
        files = [str(txt)]
        try:
            self.stage("Kapak hazırlanıyor", 0.98)
            frame_png = out.with_name(out.stem + ".frame.png")
            t = offset + shots[0][0] + min(1.0, (shots[0][1] - shots[0][0]) / 2)
            media.run_ffmpeg(["-ss", f"{t:.2f}", "-i", str(seg), "-frames:v", "1", str(frame_png)])
            img = Image.open(frame_png).convert("RGB")
            frame_png.unlink(missing_ok=True)
            if frame != "blur" and img.width / img.height > 9 / 16:
                cw = int(img.height * 9 / 16)
                x = int(min(max(centers[0] * img.width - cw / 2, 0), img.width - cw))
                img = img.crop((x, 0, x + cw, img.height))
            cover = imagegen.compose(img, clip.get("hook") or clip.get("title", ""), aspect="9:16", layout="bottom",
                                     style="bold", lang=self.edit.caption.lang)
            jpg = out.with_name(out.stem + " (kapak).jpg")
            cover.save(jpg, "JPEG", quality=92)
            files.append(str(jpg))
        except Exception as e:  # noqa: BLE001 - kapak olmasa da klip hazır
            self.check()
            self.warnings.append(f"Kapak hazırlanamadı: {str(e)[:120]}")
        return files


def new_seed() -> int:
    return random.randint(1, 2_000_000)


# ----------------------------------------------------------------------------- fikirden Reels

class Scene(BaseModel):
    narration: str = Field(description="Bu sahnede seslendirilecek metin: 1-2 kısa, akıcı cümle")
    visual: str = Field(description="Sahnenin görüntüsü için ayrıntılı İNGİLİZCE görsel istem (yazı/logo içermesin)")
    keyword: str = Field(description="Stok video aramak için 1-3 kelimelik İNGİLİZCE arama sözcüğü")


class ReelScript(BaseModel):
    title: str = Field(description="Videonun kısa adı")
    hook: str = Field(description="İlk 3 saniyede ekranda görünecek kanca yazısı, en fazla 7 kelime")
    scenes: list[Scene]
    caption: str = Field(description="Instagram/TikTok gönderi açıklaması, 1-2 cümle")
    hashtags: list[str] = Field(description="5-8 etiket, # olmadan")


SCRIPT_SYSTEM = """Sen viral kısa video (Reels/TikTok/Shorts) senaristisin. Verilen fikirden seslendirmeli,
yüz göstermeden çekilen (faceless) bir video senaryosu yaz.
Kurallar:
- İlk sahne güçlü bir kanca: soru, şaşırtıcı bilgi ya da iddia. Son sahne net bir kapanış ya da harekete çağrı.
- Seslendirme metni doğal konuşma dilinde, kısa cümlelerle; toplam kelime sayısı istenen süreye uysun
  (yaklaşık saniyede 2,5 kelime).
- Her sahnenin görseli konuyu somut olarak göstersin; visual ve keyword İNGİLİZCE olsun.
- narration, title, hook, caption ve hashtags istenen dilde olsun."""


@dataclass
class IdeaOptions:
    seconds: int = 45
    own_script: bool = False
    language: str = "tr"
    language_name: str = "Türkçe"
    voice_engine: str = "edge"
    voice: str = ""
    visuals: str = "stock"  # stock (Pexels) | image (AI görsel) | video (Higgsfield, ücretli) | plain (sade)
    image_provider: str = "pollinations"
    provider: str = "gemini"  # senaryo için yapay zekâ
    api_key: str = ""


def _split_script(text: str) -> list[Scene]:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?…])\s+|\n+", text) if s.strip()]
    scenes, cur = [], ""
    for s in sentences:
        cur = f"{cur} {s}".strip()
        if len(cur.split()) >= 9:
            scenes.append(cur)
            cur = ""
    if cur:
        scenes.append(cur)
    return [Scene(narration=s, visual=s, keyword=" ".join(s.split()[:3])) for s in scenes[:14]]


class IdeaJob(media.Job):
    """Fikirden (ya da hazır metinden) seslendirmeli, altyazılı dikey video üretir."""

    def __init__(self, settings: dict, emit, idea: str, opts: IdeaOptions, edit: Edit, out_dir: Path):
        super().__init__(settings, emit)
        self.idea, self.opts, self.edit, self.out_dir = idea, opts, edit, out_dir
        self.credits: list[str] = []

    def _script(self) -> ReelScript:
        o = self.opts
        if o.own_script or not o.api_key:
            if not o.own_script:
                self.warnings.append("Yapay zekâ anahtarı olmadığı için yazdığın metin olduğu gibi seslendirildi.")
            scenes = _split_script(self.idea)
            if not scenes:
                raise RuntimeError("Seslendirilecek metin boş.")
            first = scenes[0].narration.split()
            return ReelScript(title=" ".join(first[:6]), hook=" ".join(first[:7]), scenes=scenes,
                              caption=self.idea[:150], hashtags=[])
        self.stage("Yapay zekâ senaryoyu yazıyor", 0.02)
        prompt = (f"Fikir: {self.idea.strip()[:3000]}\nHedef süre: {o.seconds} saniye "
                  f"(yaklaşık {int(o.seconds * 2.5)} kelime, {max(4, o.seconds // 7)}-{max(5, o.seconds // 5)} sahne)\n"
                  f"Dil: {o.language_name}")
        return llm.generate(o.provider, o.api_key, SCRIPT_SYSTEM, prompt, ReelScript, effort="medium")

    def _visual(self, scene: Scene, i: int, dur: float, tmp: Path, keys: dict, used: set[int]) -> Path:
        """Sahnenin 1080x1920, dur saniyelik sessiz video parçasını üretir."""
        out = tmp / f"sahne{i:02d}.mp4"
        frames = max(1, int(round(dur * FPS)))
        enc = ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS)]
        kind = self.opts.visuals
        try:
            if kind == "stock":
                data, credit = services.pexels_video(keys.get("pexels", ""), scene.keyword or scene.visual, dur,
                                                     "en", used)
                src = tmp / f"stok{i:02d}.mp4"
                src.write_bytes(data)
                self.credits.append(credit)
                media.run_ffmpeg(["-stream_loop", "-1", "-i", str(src), "-t", f"{dur:.3f}", "-vf",
                                  f"scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase,crop={OUT_W}:{OUT_H},"
                                  f"setsar=1,fps={FPS}", *enc, str(out)], job=self)
                return out
            if kind == "video":
                data = services.higgsfield_video(keys.get("higgsfield", ""), scene.visual, "9:16", int(dur + 0.99),
                                                 on_wait=lambda s: self.emit("progress", stage=s, frac=None),
                                                 should_stop=lambda: self.cancelled)
                src = tmp / f"ai{i:02d}.mp4"
                src.write_bytes(data)
                media.run_ffmpeg(["-stream_loop", "-1", "-i", str(src), "-t", f"{dur:.3f}", "-vf",
                                  f"scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase,crop={OUT_W}:{OUT_H},"
                                  f"setsar=1,fps={FPS}", *enc, str(out)], job=self)
                return out
            if kind == "image":
                img = imagegen.generate(self.opts.image_provider, scene.visual + ", vertical composition",
                                        "9:16", keys, on_wait=lambda s: self.emit("progress", stage=s, frac=None),
                                        should_stop=lambda: self.cancelled)
                still = tmp / f"gorsel{i:02d}.jpg"
                imagegen.cover(img, (OUT_W * 2, OUT_H * 2)).save(still, quality=92)
                zoom_in = i % 2 == 0
                z = "min(1+0.16*on/{n},1.16)" if zoom_in else "max(1.16-0.16*on/{n},1)"
                media.run_ffmpeg(["-loop", "1", "-i", str(still), "-vf",
                                  f"zoompan=z='{z.format(n=frames)}':d={frames}:x='iw/2-(iw/zoom/2)':"
                                  f"y='ih/2-(ih/zoom/2)':s={OUT_W}x{OUT_H}:fps={FPS},setsar=1",
                                  "-frames:v", str(frames), *enc, str(out)], job=self)
                return out
        except services.ServiceError as e:
            if "İptal" in str(e):
                raise media.Cancelled from e
            self.warnings.append(f"Sahne {i + 1} görseli alınamadı, sade arka plan kullanıldı: {str(e)[:140]}")
        palettes = [("0x0f2027", "0x203a43", "0x2c5364"), ("0x1a1a2e", "0x16213e", "0x533483"),
                    ("0x232526", "0x414345", "0x0f0f0f"), ("0x134e5e", "0x1f6f6b", "0x0b2e2a")]
        c0, c1, c2 = palettes[i % len(palettes)]
        media.run_ffmpeg(["-f", "lavfi", "-i", f"gradients=s={OUT_W}x{OUT_H}:c0={c0}:c1={c1}:c2={c2}:nb_colors=3:"
                          f"speed=0.015:d={dur:.3f}:r={FPS}", *enc, str(out)], job=self)
        return out

    def work(self) -> list[str]:
        o = self.opts
        keys = self.settings.get("_keys", {})
        script = self._script()
        if not script.scenes:
            raise RuntimeError("Senaryo boş geldi.")
        tmp = Path(tempfile.mkdtemp(prefix="tt_idea_"))
        try:
            from . import tts
            voice = o.voice or tts.default_voice(o.voice_engine, o.language)
            speeches, n = [], len(script.scenes)
            for i, scene in enumerate(script.scenes):
                self.stage(f"Seslendiriliyor ({i + 1}/{n})", 0.05 + 0.25 * i / n)
                speeches.append(tts.synthesize(o.voice_engine, scene.narration, voice, keys,
                                               speed=1.08 if o.voice_engine == "edge" else 1.0))
            gap = 0.18
            durations = [max(1.6, s.duration + gap) for s in speeches]
            import numpy as np
            narration = np.concatenate([np.pad(s.samples, (0, int(d * tts.RATE) - len(s.samples)))
                                        for s, d in zip(speeches, durations)])
            media.write_wav(tmp / "ses.wav", narration, tts.RATE)
            all_words, t0 = [], 0.0
            for s, d in zip(speeches, durations):
                all_words += [W.Word(w.start + t0, w.end + t0, w.text) for w in s.words]
                t0 += d
            total = sum(durations)

            used: set[int] = set()
            parts = []
            for i, (scene, d) in enumerate(zip(script.scenes, durations)):
                self.stage(f"Görüntüler hazırlanıyor ({i + 1}/{n})", 0.3 + 0.45 * i / n)
                parts.append(self._visual(scene, i, d, tmp, keys, used))
            (tmp / "liste.txt").write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
            media.run_ffmpeg(["-f", "concat", "-safe", "0", "-i", "liste.txt", "-c", "copy", "sahneler.mp4"],
                             job=self, cwd=str(tmp))

            ass = captions.build(all_words, total, self.edit.caption, hook=script.hook if self.edit.hook else "",
                                 progress_bar=self.edit.progress_bar, watermark=self.edit.watermark)
            (tmp / "altyazi.ass").write_text(ass, encoding="utf-8")
            fonts = tmp / "fonts"
            fonts.mkdir()
            for name in CAPTION_FONTS:
                if (FONTS_DIR / name).exists():
                    shutil.copy2(FONTS_DIR / name, fonts / name)

            self.out_dir.mkdir(parents=True, exist_ok=True)
            base = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", script.title).strip()[:70] or "Reels"
            out = self.out_dir / f"{base} - reels.mp4"
            k = 2
            while out.exists():
                out = self.out_dir / f"{base} - reels ({k}).mp4"
                k += 1
            music = self.edit.music if self.edit.music and Path(self.edit.music).exists() else None
            args = ["-i", "sahneler.mp4", "-i", "ses.wav"]
            graph = ["[0:v]ass=altyazi.ass:fontsdir=fonts,format=yuv420p[vout]"]
            fade = f"afade=t=out:st={max(0, total - 0.4):.2f}:d=0.4"
            if music:
                args += ["-stream_loop", "-1", "-i", music]
                vol = max(0.02, min(self.edit.music_volume, 1.0))
                graph += [f"[2:a]aresample=48000,volume={vol:.3f}[mus]",
                          "[1:a]aresample=48000,asplit=2[voice][key]",
                          "[mus][key]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[duck]",
                          f"[voice][duck]amix=inputs=2:duration=first:normalize=0,{fade},"
                          "loudnorm=I=-14:TP=-1.5:LRA=11[aout]"]
            else:
                graph += [f"[1:a]aresample=48000,{fade},loudnorm=I=-14:TP=-1.5:LRA=11[aout]"]
            args += ["-filter_complex", ";".join(graph), "-map", "[vout]", "-map", "[aout]",
                     "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                     "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", "-shortest", str(out)]
            self.stage("Video birleştiriliyor", 0.78)
            media.run_ffmpeg(args, duration=total, job=self, cwd=str(tmp),
                             on_progress=lambda f: self.emit("progress", stage="Video birleştiriliyor",
                                                             frac=0.78 + 0.2 * f))
            tags = " ".join("#" + re.sub(r"\W+", "", t) for t in script.hashtags if re.sub(r"\W+", "", t))
            credits = "\n".join(dict.fromkeys(self.credits))
            text = "\n\n".join(x for x in (script.title, script.caption, tags, credits) if x)
            txt = out.with_suffix(".txt")
            txt.write_text(text + "\n\n---\n" + "\n".join(s.narration for s in script.scenes) + "\n",
                           encoding="utf-8")
            return [str(txt), str(out)]
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
