"""AI video özeti: videonun altyazı dökümünü (yoksa başlık/açıklamasını) seçilen yapay zekâya özetletir."""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

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
    if not transcript:  # X/Twitter gibi altyazısız videolarda konuşmayı kendimiz yazıya dökeriz
        try:
            transcript = transcribe_audio(url, info, settings, on_stage)
        except Exception:  # noqa: BLE001 - ses alınamazsa başlık/açıklamayla devam
            transcript = None
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


MAX_TRANSCRIBE_SECONDS = 3 * 3600


def transcribe_audio(url: str, info: dict, settings: dict, on_stage) -> tuple[str, str] | None:
    """Videonun yalnızca sesini indirip bilgisayarda (Whisper) yazıya döker."""
    from . import transcribe  # ağır modül; yalnızca gerektiğinde

    if (info.get("duration") or 0) > MAX_TRANSCRIBE_SECONDS:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        on_stage("Videonun sesi indiriliyor")
        opts = engine.base_opts(settings) | {"format": "ba/b", "noplaylist": True,
                                             "outtmpl": str(Path(tmp) / "ses.%(ext)s")}
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([info.get("webpage_url") or url])
        files = list(Path(tmp).glob("ses.*"))
        if not files:
            return None
        on_stage("Konuşma yazıya dökülüyor")
        cues, lang = transcribe.transcribe(files[0], settings.get("whisper_model", "small"), lambda f, t: None)
    text = " ".join(c.text for c in cues).strip()
    return (text, f"konuşma tanıma ({lang})") if text else None


# ----------------------------------------------------------------------------- yorum özeti

class Issue(BaseModel):
    sorun: str = Field(description="İzleyicilerin bildirdiği hata veya sorun")
    cozum: str = Field(description="Yorumlarda önerilen çözüm; yoksa 'Yorumlarda çözüm önerilmemiş'")


class CommentSummary(BaseModel):
    genel_hava: str = Field(description="İzleyicilerin genel tepkisi, 1-2 cümle")
    begenilenler: list[str] = Field(description="İzleyicilerin beğendiği şeyler")
    begenilmeyenler: list[str] = Field(description="İzleyicilerin eleştirdiği veya beğenmediği şeyler")
    one_cikanlar: list[str] = Field(description="Yorumlarda sık geçen konu ve temalar")
    sorunlar: list[Issue] = Field(description="Bildirilen hatalar/sorunlar ve yorumlardaki çözümleri")
    sorular: list[str] = Field(description="İzleyicilerin sık sorduğu sorular")
    ozet: str = Field(description="Yorumların 1-2 paragraflık ayrıntılı özeti")


COMMENTS_SYSTEM = """Sen TekTıkla'nın yorum analisti asistanısın. Sana bir videonun başlığı ve en çok beğenilen \
izleyici yorumları (beğeni sayılarıyla) verilecek.

Kurallar:
- Yanıtı Türkçe yaz; yorumlar hangi dilde olursa olsun.
- Yalnızca yorumlarda gerçekten geçenleri yaz; uydurma.
- Çok beğenilen yorumlar genel kanaati daha iyi yansıtır; ağırlık ver.
- sorunlar: izleyicilerin bildirdiği hata/sorunları ve başka yorumcuların önerdiği çözümleri eşleştir.
- Boş kalan listeler için boş liste döndür; tek bir kişinin aşırı uç görüşünü genelleme."""


def fetch_comments(url: str, settings: dict, limit: int = 300) -> tuple[dict, list[dict]]:
    opts = engine.base_opts(settings) | {
        "skip_download": True, "noplaylist": True, "getcomments": True,
        "extractor_args": {"youtube": {"max_comments": [str(limit), str(limit), "0", "0"], "comment_sort": ["top"]}},
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.sanitize_info(ydl.extract_info(url, download=False))
    if info.get("_type") == "playlist":
        raise AIError("Yorum özeti tek bir video için çalışır.")
    comments = [c for c in info.get("comments") or [] if (c.get("text") or "").strip() and c.get("parent") == "root"]
    comments.sort(key=lambda c: c.get("like_count") or 0, reverse=True)
    return info, comments[:limit]


def summarize_comments(url: str, settings: dict, provider: str, api_key: str, on_stage=lambda s: None) -> dict:
    if not api_key:
        llm.generate(provider, api_key, "", "", CommentSummary)
    on_stage("Yorumlar alınıyor")
    info, comments = fetch_comments(url, settings)
    if not comments:
        raise AIError("Bu videonun yorumları alınamadı. Yorum özeti şu an en iyi YouTube videolarında çalışır.")
    lines = [f"[{c.get('like_count') or 0} beğeni] {c['text'].strip()[:500]}" for c in comments]
    prompt = f"Video: {info.get('title') or '-'}\nKanal: {info.get('uploader') or '-'}\n\n<yorumlar>\n" + "\n".join(lines) + "\n</yorumlar>"
    on_stage("Yapay zekâ yorumları özetliyor")
    result = llm.generate(provider, api_key, COMMENTS_SYSTEM, prompt, CommentSummary, effort="medium")
    return {**result.model_dump(), "title": info.get("title") or "", "thumbnail": info.get("thumbnail"),
            "count": len(comments), "provider": llm.PROVIDERS[provider]["name"]}


# ----------------------------------------------------------------------------- video fikirleri

class Idea(BaseModel):
    baslik: str = Field(description="Dikkat çekici video başlığı")
    kanca: str = Field(description="Videonun ilk 5 saniyesinde söylenecek açılış cümlesi")
    format: str = Field(description="Önerilen format ve süre, ör. 'Shorts, 45 sn' veya 'Uzun video, 10-12 dk'")
    akis: list[str] = Field(description="Videonun akışı, 3-6 madde")
    neden: str = Field(description="Bu fikrin neden ilgi göreceği, 1 cümle")


class IdeaSet(BaseModel):
    ozet: str = Field(description="Kaynağın/konunun ne olduğu ve hedef kitle, 1-2 cümle")
    fikirler: list[Idea] = Field(description="6 özgün video fikri")


IDEAS_SYSTEM = """Sen deneyimli bir içerik stratejisti ve senaristsin. Kullanıcıya YouTube, TikTok, Instagram gibi \
platformlar için özgün video fikirleri üretiyorsun.

Kurallar:
- Yanıtı Türkçe yaz.
- 6 fikir üret; birbirinden farklı açılar ve formatlar dene (kısa video, uzun video, seri, karşılaştırma vb.).
- Kaynak video verildiyse onu kopyalama: aynı kitleye hitap eden, onu geliştiren veya farklı açıdan ele alan fikirler ver.
- Başlıklar merak uyandırsın ama yanıltıcı olmasın."""


def video_ideas(source: str, settings: dict, provider: str, api_key: str, info: dict | None = None,
                on_stage=lambda s: None) -> dict:
    if not api_key:
        llm.generate(provider, api_key, "", "", IdeaSet)
    title = thumb = None
    if re.match(r"^https?://\S+$", source.strip(), re.I):
        if info is None:
            on_stage("Video bilgileri alınıyor")
            info = extract_info(source.strip(), settings)
        transcript = fetch_transcript(info, settings)
        title, thumb = info.get("title"), info.get("thumbnail")
        prompt = "Aşağıdaki videoya benzer içerik fikirleri üret.\n\n" + build_prompt(info, transcript)
    else:
        prompt = f"Şu konu/istek için video fikirleri üret:\n\n{source.strip()[:4000]}"
    on_stage("Yapay zekâ fikir üretiyor")
    result = llm.generate(provider, api_key, IDEAS_SYSTEM, prompt, IdeaSet, effort="medium")
    return {**result.model_dump(), "title": title or source.strip()[:120], "thumbnail": thumb,
            "provider": llm.PROVIDERS[provider]["name"]}
