"""AI video özeti: videonun altyazı dökümünü (yoksa başlık/açıklamasını) Claude'a özetletir."""
from __future__ import annotations

import json
import re

import anthropic
import yt_dlp
from pydantic import BaseModel, Field

from . import engine

MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
PREFERRED_LANGS = ("tr", "en")
SUB_FORMATS = ("json3", "vtt", "srv3", "srt", "ttml")

SYSTEM_PROMPT = """Sen TekTıkla video indirme uygulamasının özetleme asistanısın. Kullanıcı bir videoyu \
indirmeden önce ne anlattığını hızlıca öğrenmek istiyor.

Sana videonun başlığı, kanalı, süresi, açıklaması ve varsa konuşma dökümü verilecek. Döküm otomatik \
altyazıdan geldiyse yazım hataları ve tekrarlar içerebilir; anlamı bağlamdan çıkar.

Kurallar:
- Video hangi dilde olursa olsun yanıtı Türkçe yaz.
- Sadece verilen içerikte olan bilgiyi kullan; videoda geçmeyen bir şeyi ekleme.
- Döküm yoksa özetin yalnızca başlık ve açıklamaya dayandığını tldr içinde belirt.
- key_points: videonun en önemli 3-7 noktası, her biri tek ve somut bir cümle.
- topics: 2-6 kısa konu etiketi (1-3 kelime)."""


class VideoSummary(BaseModel):
    tldr: str = Field(description="Videonun tek cümlelik özeti")
    summary: str = Field(description="1-3 paragraflık genel özet")
    key_points: list[str] = Field(description="Önemli noktalar")
    topics: list[str] = Field(description="Kısa konu etiketleri")


class AIError(Exception):
    pass


# ----------------------------------------------------------------------------- döküm

def _pick_track(info: dict) -> tuple[list[dict], str, bool] | None:
    """Önce elle yazılmış altyazı, sonra videonun orijinal dilindeki otomatik altyazı."""
    lang = (info.get("language") or "").split("-")[0]
    manual = {k: v for k, v in (info.get("subtitles") or {}).items() if k != "live_chat" and v}
    auto = {k: v for k, v in (info.get("automatic_captions") or {}).items() if v}

    for key in [lang, *PREFERRED_LANGS, *manual]:
        if key and key in manual:
            return manual[key], key, False
    for key in auto:
        if key.endswith("-orig"):
            return auto[key], key, True
    for key in [lang, *PREFERRED_LANGS]:
        if key and key in auto:
            return auto[key], key, True
    return None


def _parse_json3(text: str) -> list[str]:
    data = json.loads(text)
    lines = []
    for event in data.get("events", []):
        line = "".join(seg.get("utf8", "") for seg in event.get("segs") or []).replace("\n", " ").strip()
        if line:
            lines.append(line)
    return lines


def _parse_text_subs(text: str) -> list[str]:
    """VTT/SRT/TTML: zaman damgalarını ve etiketleri atar."""
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if (not line or "-->" in line or line.isdigit() or line.startswith(("WEBVTT", "NOTE", "Kind:", "Language:"))):
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if line:
            lines.append(line)
    return lines


def _dedupe(lines: list[str]) -> str:
    # YouTube otomatik altyazılarında satırlar kayarak tekrarlanır
    out: list[str] = []
    for line in lines:
        if out and (line == out[-1] or out[-1].endswith(line)):
            continue
        out.append(line)
    return " ".join(out)


def fetch_transcript(info: dict, settings: dict) -> tuple[str, str] | None:
    """(döküm metni, kaynak açıklaması) döndürür; altyazı yoksa None."""
    picked = _pick_track(info)
    if not picked:
        return None
    tracks, lang, auto = picked
    by_ext = {t.get("ext"): t for t in tracks if t.get("url")}
    track = next((by_ext[e] for e in SUB_FORMATS if e in by_ext), None) or next(iter(by_ext.values()), None)
    if not track:
        return None
    with yt_dlp.YoutubeDL(engine.base_opts(settings)) as ydl:
        text = ydl.urlopen(track["url"]).read().decode("utf-8", "replace")
    lines = _parse_json3(text) if track.get("ext") == "json3" else _parse_text_subs(text)
    transcript = _dedupe(lines)
    if not transcript:
        return None
    return transcript, f"{'otomatik' if auto else 'elle yazılmış'} altyazı ({lang})"


def extract_info(url: str, settings: dict) -> dict:
    opts = engine.base_opts(settings) | {"skip_download": True, "noplaylist": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.sanitize_info(ydl.extract_info(url, download=False))
    if info.get("_type") == "playlist":
        raise AIError("AI özeti oynatma listeleri için değil, tek bir video için çalışır.")
    return info


# ----------------------------------------------------------------------------- özet

def build_prompt(info: dict, transcript: tuple[str, str] | None) -> str:
    chapters = info.get("chapters") or []
    parts = [
        f"Başlık: {info.get('title') or '-'}",
        f"Kanal: {info.get('uploader') or info.get('channel') or '-'}",
        f"Site: {info.get('extractor_key') or '-'}",
        f"Süre: {engine.human_time(info.get('duration')) or '-'}",
    ]
    if chapters:
        parts.append("Bölümler:\n" + "\n".join(
            f"- {engine.human_time(c.get('start_time'))} {c.get('title', '')}" for c in chapters))
    parts.append(f"<aciklama>\n{(info.get('description') or '').strip() or '-'}\n</aciklama>")
    if transcript:
        parts.append(f"<dokum kaynak=\"{transcript[1]}\">\n{transcript[0]}\n</dokum>")
    else:
        parts.append("(Bu video için konuşma dökümü bulunamadı.)")
    return "\n\n".join(parts)


def summarize(url: str, settings: dict, api_key: str, info: dict | None = None,
              on_stage=lambda stage: None) -> dict:
    if not api_key:
        raise AIError("AI özeti için Ayarlar > Yapay Zekâ bölümüne Anthropic API anahtarınızı girin.")
    if info is None:
        on_stage("Video bilgileri alınıyor")
        info = extract_info(url, settings)
    on_stage("Konuşma dökümü çıkarılıyor")
    transcript = fetch_transcript(info, settings)
    on_stage("Claude videoyu özetliyor")

    client = anthropic.Anthropic(api_key=api_key, timeout=180.0)
    try:
        response = client.beta.messages.parse(
            model=MODEL,
            max_tokens=16000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            output_config={"effort": "medium"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_prompt(info, transcript)}],
            output_format=VideoSummary,
        )
    except anthropic.AuthenticationError:
        raise AIError("API anahtarı geçersiz. Ayarlar > Yapay Zekâ bölümünden kontrol edin.") from None
    except anthropic.PermissionDeniedError:
        raise AIError("Bu API anahtarının Claude'u kullanma izni yok.") from None
    except anthropic.RateLimitError:
        raise AIError("Çok fazla istek gönderildi veya kredi limiti doldu. Biraz sonra tekrar deneyin.") from None
    except anthropic.BadRequestError as e:
        msg = str(e)
        if "credit" in msg.lower() or "billing" in msg.lower():
            raise AIError("Anthropic hesabınızda yeterli kredi yok (console.anthropic.com > Billing).") from None
        raise AIError(f"İstek reddedildi: {msg[:300]}") from None
    except anthropic.APIConnectionError:
        raise AIError("Claude'a bağlanılamadı. İnternet bağlantınızı kontrol edin.") from None
    except anthropic.APIStatusError as e:
        raise AIError(f"Claude geçici bir hata verdi ({e.status_code}). Biraz sonra tekrar deneyin.") from None

    if response.stop_reason == "refusal":
        raise AIError("Claude bu video için özet üretmeyi reddetti.")
    result = response.parsed_output
    if result is None:
        raise AIError("Özet okunamadı, lütfen tekrar deneyin.")
    return {
        **result.model_dump(),
        "title": info.get("title") or "",
        "thumbnail": info.get("thumbnail"),
        "source": transcript[1] if transcript else "başlık ve açıklama (döküm yok)",
        "words": len(transcript[0].split()) if transcript else 0,
    }
