"""AI video özeti: videonun altyazı dökümünü (yoksa başlık/açıklamasını) seçilen yapay zekâya özetletir."""
from __future__ import annotations

import yt_dlp
from pydantic import BaseModel, Field

from . import engine, llm, subtitles
from .llm import AIError  # noqa: F401 - api.py bu adla yakalıyor

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


def fetch_transcript(info: dict, settings: dict) -> tuple[str, str] | None:
    """(döküm metni, kaynak açıklaması) döndürür; altyazı yoksa None."""
    found = subtitles.caption_cues(info, settings)
    if not found:
        return None
    cues, _lang, source = found
    return " ".join(c.text for c in cues), source


def extract_info(url: str, settings: dict) -> dict:
    opts = engine.base_opts(settings) | {"skip_download": True, "noplaylist": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.sanitize_info(ydl.extract_info(url, download=False))
    if info.get("_type") == "playlist":
        raise AIError("AI özeti oynatma listeleri için değil, tek bir video için çalışır.")
    return info


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


def summarize(url: str, settings: dict, provider: str, api_key: str, info: dict | None = None,
              on_stage=lambda stage: None) -> dict:
    if not api_key:
        llm.generate(provider, api_key, "", "", VideoSummary)  # anahtar yoksa açıklayıcı hata verir
    if info is None:
        on_stage("Video bilgileri alınıyor")
        info = extract_info(url, settings)
    on_stage("Konuşma dökümü çıkarılıyor")
    transcript = fetch_transcript(info, settings)
    on_stage("Yapay zekâ videoyu özetliyor")
    result = llm.generate(provider, api_key, SYSTEM_PROMPT, build_prompt(info, transcript), VideoSummary,
                          effort="medium")
    return {
        **result.model_dump(),
        "title": info.get("title") or "",
        "thumbnail": info.get("thumbnail"),
        "source": transcript[1] if transcript else "başlık ve açıklama (döküm yok)",
        "words": len(transcript[0].split()) if transcript else 0,
        "provider": llm.PROVIDERS[provider]["name"],
    }
