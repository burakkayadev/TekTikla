"""Dublaj: videonun konuşmasını başka bir dile çevirip seslendirir.

İki yol:
  - Ücretsiz (Edge ya da Gemini sesi): döküm -> çeviri (Gemini ücretsiz / Claude) -> her cümle zamanında
    seslendirilir, gerekirse hafifçe hızlandırılır -> orijinal ses arka planda kısılır. Çıktıda dublaj
    varsayılan ses izi, orijinal ses ikinci iz ve hedef dilde altyazı bulunur.
  - ElevenLabs: konuşmacının kendi sesini koruyarak dublajlar (ücretsiz planda filigranlı, aylık sınırlı).
"""
from __future__ import annotations

import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yt_dlp

from . import engine, media, services, subtitles, tts, words as W

RATE = tts.RATE


@dataclass
class DubOptions:
    target: str = "tr"
    engine: str = "edge"  # edge | gemini | elevenlabs
    voice: str = ""
    original: str = "duck"  # duck (arka planda kısık) | mute (tamamen kaldır)
    keep_original_track: bool = True
    subtitles: bool = True
    provider: str = "gemini"  # çeviri için
    api_key: str = ""


class DubJob(media.Job):
    def __init__(self, settings: dict, emit, source: str, title: str, opts: DubOptions, out_dir: Path,
                 info: dict | None = None):
        super().__init__(settings, emit)
        self.source, self.title, self.opts, self.out_dir, self.info = source, title, opts, out_dir, info

    # -- kaynak
    def _video(self, tmp: Path) -> tuple[Path, dict | None]:
        path = Path(self.source)
        if not re.match(r"^https?://", self.source, re.I) and path.exists():
            return path, None
        self.stage("Video indiriliyor", 0)

        def hook(d):
            self.check()
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                self.emit("progress", stage="Video indiriliyor",
                          frac=d.get("downloaded_bytes", 0) / total * 0.25 if total else None)

        opts = engine.base_opts(self.settings) | {
            "format": "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=1080][ext=mp4]+ba[ext=m4a]/"
                      "bv*[height<=1080]+ba/b[height<=1080]/b",  # video kopyalanacak: önce H.264
            "merge_output_format": "mp4", "noplaylist": True, "outtmpl": str(tmp / "kaynak.%(ext)s"),
            "progress_hooks": [hook],
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.sanitize_info(ydl.extract_info(self.source, download=True))
        files = [f for f in tmp.glob("kaynak.*") if f.suffix in (".mp4", ".mkv", ".webm")]
        if not files:
            raise RuntimeError("Video indirilemedi.")
        if info.get("title"):
            self.title = info["title"]
        return files[0], info

    def _out(self, ext: str = ".mp4") -> Path:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        lang = subtitles.LANG_NAMES.get(self.opts.target, self.opts.target)
        base = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", self.title).strip()[:90] or "Video"
        out = self.out_dir / f"{base} ({lang} dublaj){ext}"
        n = 2
        while out.exists():
            out = self.out_dir / f"{base} ({lang} dublaj) ({n}){ext}"
            n += 1
        return out

    # -- iş
    def work(self) -> list[str]:
        tmp = Path(tempfile.mkdtemp(prefix="tt_dub_"))
        try:
            video, info = self._video(tmp)
            if self.opts.engine == "elevenlabs":
                return self._elevenlabs(video)
            return self._local(video, info or self.info, tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _elevenlabs(self, video: Path) -> list[str]:
        keys = self.settings.get("_keys", {})
        self.stage("ElevenLabs'e yükleniyor", 0.3)
        data, ext = services.elevenlabs_dub(
            keys.get("elevenlabs", ""), self.opts.target, file=video, name=self.title,
            on_wait=lambda s: self.emit("progress", stage=s, frac=None), should_stop=lambda: self.cancelled)
        out = self._out(ext)
        out.write_bytes(data)
        return [str(out)]

    def _voice(self, cues: list[subtitles.Cue], engine_name: str, voice: str, keys: dict, total: float) -> np.ndarray:
        """Cümleleri seslendirip zamanlarına yerleştirir. Gemini'de yakın cümleler tek istekte birleşir: ücretsiz
        katmandaki istek sınırına daha geç takılır. Sığmayan konuşma en fazla 1.6 kat hızlanır."""
        groups = _merge(cues) if engine_name == "gemini" else [[c] for c in cues]
        track = np.zeros(int((total + 2) * RATE), np.float32)
        for i, group in enumerate(groups):
            stage = f"Seslendiriliyor ({i + 1}/{len(groups)})"
            self.stage(stage, 0.6 + 0.3 * i / len(groups))
            speech = tts.synthesize(
                engine_name, " ".join(c.text for c in group), voice, keys, should_stop=lambda: self.cancelled,
                on_wait=lambda s, stage=stage: self.emit("progress", stage=f"Gemini kotası: {s} sn bekleniyor", frac=None))
            self.check()
            samples = speech.samples
            start_t = group[0].start
            slot_end = groups[i + 1][0].start if i + 1 < len(groups) else total
            slot = max(0.4, slot_end - start_t - 0.05)
            if len(samples) / RATE > slot:
                samples = media.speed_up(samples, min(len(samples) / RATE / slot, 1.6), RATE)
            limit = int(slot * RATE)
            if len(samples) > limit:  # yine sığmadıysa sonunu yumuşakça kes
                fade = min(int(0.08 * RATE), limit)
                samples = samples[:limit].copy()
                samples[-fade:] *= np.linspace(1, 0, fade)
            start = int(start_t * RATE)
            end = min(len(track), start + len(samples))
            track[start:end] += samples[:end - start]
        return track

    def _local(self, video: Path, info: dict | None, tmp: Path) -> list[str]:
        o = self.opts
        keys = self.settings.get("_keys", {})
        meta = media.probe(video)
        if not meta["has_audio"]:
            raise RuntimeError("Videoda ses yok; dublajlanacak konuşma bulunamadı.")

        # 1) döküm: önce sitedeki altyazı, yoksa Whisper
        self.stage("Konuşma yazıya dökülüyor", 0.26)
        found = W.youtube_words(info, self.settings) if info else None
        if found:
            words, src_lang = found
        else:
            words, src_lang = W.whisper_words(
                video, self.settings.get("whisper_model", "small"),
                lambda f, s: self.emit("progress", stage=s, frac=0.26 + f * 0.2), lambda: self.cancelled)
        lines = [ln for ln in W.lines(words, max_words=24, gap=0.7) if ln.text.strip()]
        if not lines:
            raise RuntimeError("Videoda konuşma bulunamadı.")

        # 2) çeviri: yapay zekâ anahtarı varsa onunla (daha doğal), yoksa ya da kotası dolduysa ücretsiz çeviriyle
        cues = [subtitles.Cue(ln.start, ln.end, ln.text) for ln in lines]
        source = src_lang.split("-")[0]
        if source != o.target:
            self.stage("Konuşma çevriliyor", 0.47)
            translated = None
            if o.api_key:
                try:
                    translated = subtitles.translate(cues, o.target, o.provider, o.api_key,
                                                     lambda f: self.emit("progress", stage="Konuşma çevriliyor",
                                                                         frac=0.47 + f * 0.13), lambda: self.cancelled)
                except Exception:  # noqa: BLE001
                    self.check()
                    self.warnings.append("Yapay zekâ çevirisi yapılamadı (kota dolmuş olabilir); ücretsiz çeviri kullanıldı.")
            if translated is None:
                texts = subtitles.translate_free([c.text for c in cues], o.target, source)
                translated = [subtitles.Cue(c.start, c.end, t) for c, t in zip(cues, texts)]
            cues = translated
        self.check()

        # 3) seslendirme ve zamanlama
        total = meta["duration"] or (cues[-1].end + 1)
        try:
            track = self._voice(cues, o.engine, o.voice or tts.default_voice(o.engine, o.target), keys, total)
        except services.QuotaError:
            if o.engine != "gemini":
                raise
            # Gemini'nin günlük ücretsiz kotası bitti: ses baştan sona aynı kalsın diye tamamı Edge sesiyle
            self.warnings.append("Gemini'nin günlük ücretsiz ses kotası doldu; dublaj ücretsiz Edge sesiyle tamamlandı. "
                                 "Gemini sesini yarın yeniden deneyebilirsin.")
            track = self._voice(cues, "edge", tts.default_voice("edge", o.target), keys, total)
        peak = float(np.abs(track).max() or 1)
        if peak > 0.98:
            track *= 0.98 / peak
        media.write_wav(tmp / "dublaj.wav", track[:int(total * RATE) + RATE // 2], RATE)

        # 4) karıştırma ve paketleme
        srt = None
        if o.subtitles:
            srt = subtitles.write_srt(cues, tmp / "altyazi.srt")
        out = self._out()
        level = 0.0 if o.original == "mute" else 0.13
        graph = (f"[0:a]aresample=48000,volume={level}[orig];[1:a]aresample=48000,volume=1.0[dub];"
                 "[orig][dub]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[mix]")
        args = ["-i", str(video), "-i", str(tmp / "dublaj.wav")]
        if srt:
            args += ["-i", str(srt)]
        args += ["-filter_complex", graph, "-map", "0:v:0", "-map", "[mix]"]
        lang_tag = subtitles.LANG_TAGS.get(o.target, "und")
        dub_name = f"Dublaj ({subtitles.LANG_NAMES.get(o.target, o.target)})"
        meta_args = ["-metadata:s:a:0", f"language={lang_tag}", "-metadata:s:a:0", f"title={dub_name}",
                     "-metadata:s:a:0", f"handler_name={dub_name}", "-disposition:a:0", "default"]
        if o.keep_original_track:
            args += ["-map", "0:a:0"]
            meta_args += ["-metadata:s:a:1", "title=Orijinal ses", "-metadata:s:a:1", "handler_name=Orijinal ses",
                          "-disposition:a:1", "0"]
        if srt:
            args += ["-map", "2:0"]
            meta_args += ["-c:s", "mov_text", "-metadata:s:s:0", f"language={lang_tag}",
                          "-metadata:s:s:0", f"handler_name={dub_name}", "-disposition:s:0", "0"]
        args += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", *meta_args, "-movflags", "+faststart", str(out)]
        self.ffmpeg(args, total, "Dublaj videoya ekleniyor", (0.9, 1.0))
        return [str(out)]


def _merge(cues: list[subtitles.Cue], max_words: int = 40, max_gap: float = 0.35) -> list[list[subtitles.Cue]]:
    """Aralarında kısa duraklama olan cümleleri tek seslendirme isteğinde toplar (en fazla max_words kelime)."""
    groups: list[list[subtitles.Cue]] = []
    cur: list[subtitles.Cue] = []
    for c in cues:
        words = sum(len(x.text.split()) for x in cur)
        if cur and (c.start - cur[-1].end > max_gap or words + len(c.text.split()) > max_words):
            groups.append(cur)
            cur = []
        cur.append(c)
    if cur:
        groups.append(cur)
    return groups
