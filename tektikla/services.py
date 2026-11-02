"""Görsel, ses ve video üreten dış servislerin istemcileri.

Ücretsiz seçenekler her zaman önce gelir:
  - Pollinations: anahtarsız ücretsiz görsel (yavaş, filigranlı); ücretsiz hesapla filigransız.
  - Cloudflare Workers AI: ücretsiz hesapla günde ~95 görsel (FLUX.2 klein).
  - Gemini: konuşma sentezi (TTS) ücretsiz katmanda; görsel üretimi ücretli.
  - ElevenLabs: ücretsiz planda ayda ~10.000 karakter / ~5 dk filigranlı dublaj; sonrası ücretli.
  - Higgsfield: yalnızca ücretli (kullandıkça öde) görsel ve video modelleri.
"""
from __future__ import annotations

import base64
import re
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Callable

import requests

UA = {"User-Agent": "TekTikla"}

# Ayarlar > Servisler kartında gösterilenler. tier: free | free_quota | freemium | paid
SERVICES = {
    "pollinations": {"name": "Pollinations", "tier": "free", "optional": True, "link": "pollinations_keys",
                     "uses": "Görsel üretme",
                     "hint": "Anahtarsız da çalışır (yavaş, köşede küçük logo). Ücretsiz hesapla logosuz ve daha hızlı.",
                     "placeholder": "sk_… (isteğe bağlı)"},
    "cloudflare": {"name": "Cloudflare Workers AI", "tier": "free_quota", "link": "cloudflare_ai",
                   "uses": "Görsel üretme (günde ~95 görsel ücretsiz)",
                   "hint": "Ücretsiz hesap aç, Workers AI > REST API'den token oluştur. 'hesap-id:token' biçiminde gir.",
                   "placeholder": "hesap-id:api-token"},
    "pexels": {"name": "Pexels", "tier": "free", "link": "pexels_keys",
               "uses": "Fikirden Reels için dikey stok videolar",
               "hint": "Ücretsiz: pexels.com/api adresinden hesap açıp anahtarını kopyala (saatte 200 arama).",
               "placeholder": "Pexels API anahtarı"},
    "elevenlabs": {"name": "ElevenLabs", "tier": "freemium", "link": "elevenlabs_keys",
                   "uses": "Orijinal sesle dublaj, doğal seslendirme",
                   "hint": "Ücretsiz planda ayda ~10 dk ses ve ~5 dk filigranlı dublaj (ticari kullanım yok). "
                           "Sonrası ücretli.",
                   "placeholder": "sk_…"},
    "higgsfield": {"name": "Higgsfield", "tier": "paid", "link": "higgsfield_keys",
                   "uses": "AI görsel (SOUL) ve AI video (Seedance) - Reels için",
                   "hint": "Kullandıkça öde: console.higgsfield.ai'den bakiye yükleyip API anahtarı oluştur. "
                           "'anahtar-id:gizli-anahtar' biçiminde gir.",
                   "placeholder": "anahtar-id:gizli-anahtar"},
}


class ServiceError(Exception):
    pass


class QuotaError(ServiceError):
    """Ücretsiz kota doldu. retry_after: kaç saniye sonra yeniden denenebilir; daily: o günün kotası bitti."""

    def __init__(self, message: str, retry_after: float | None = None, daily: bool = False):
        super().__init__(message)
        self.retry_after, self.daily = retry_after, daily


def _quota_error(r: requests.Response) -> QuotaError:
    """Gemini'nin 429 yanıtından bekleme süresini ve kotanın günlük mü dakikalık mı olduğunu okur."""
    retry, daily = None, False
    try:
        err = r.json().get("error") or {}
        for d in err.get("details") or []:
            kind = d.get("@type", "")
            if kind.endswith("RetryInfo"):
                m = re.match(r"([\d.]+)s", str(d.get("retryDelay", "")))
                retry = float(m.group(1)) if m else None
            elif kind.endswith("QuotaFailure"):
                daily = any("PerDay" in (v.get("quotaId") or "") for v in d.get("violations") or [])
        daily = daily or "per day" in (err.get("message") or "").lower()
    except ValueError:
        pass
    if retry is None and r.headers.get("Retry-After", "").isdigit():
        retry = float(r.headers["Retry-After"])
    if daily:
        return QuotaError("Gemini'nin günlük ücretsiz kotası doldu; yarın tekrar deneyin ya da ücretsiz Edge sesini seçin.",
                          retry, True)
    return QuotaError("Gemini ücretsiz kota sınırına ulaşıldı; bir dakika sonra tekrar deneyin.", retry, False)


def _fail(service: str, r: requests.Response) -> ServiceError:
    try:
        body = r.json()
        detail = body.get("detail") or body.get("error") or body.get("message") or body
        if isinstance(detail, dict):
            detail = detail.get("message") or detail.get("status") or str(detail)
    except ValueError:
        detail = r.text[:200]
    detail = str(detail)[:300]
    if r.status_code in (401, 403):
        return ServiceError(f"{service}: anahtar geçersiz ya da yetkisiz. Ayarlar > Servisler'den kontrol edin.\n{detail}")
    if r.status_code in (402, 429):
        return ServiceError(f"{service}: kota ya da bakiye bitti, biraz sonra tekrar deneyin.\n{detail}")
    return ServiceError(f"{service} hatası ({r.status_code}): {detail}")


def find_blob(data, kind: str) -> tuple[bytes, str] | None:
    """Yanıt JSON'unun içinde base64 ses/görsel verisini bulur (Interactions ve generateContent biçimleri)."""
    if isinstance(data, dict):
        inline = data.get("inlineData") or data.get("inline_data")
        if isinstance(inline, dict) and inline.get("data"):
            return base64.b64decode(inline["data"]), inline.get("mimeType") or inline.get("mime_type") or ""
        if data.get("type") == kind and isinstance(data.get("data"), str):
            return base64.b64decode(data["data"]), data.get("mime_type") or data.get("mimeType") or ""
        values = data.values()
    elif isinstance(data, list):
        values = data
    else:
        return None
    found = None
    for value in values:  # son bulunan: "son üretilen blok"
        hit = find_blob(value, kind)
        if hit:
            found = hit
    return found


# ----------------------------------------------------------------------------- Gemini (görsel ücretli, TTS ücretsiz)

GEMINI_INTERACTIONS = "https://generativelanguage.googleapis.com/v1beta/interactions"
GEMINI_IMAGE_MODELS = {"gemini-3.1-flash-lite-image": "Nano Banana 2 Lite (~$0,034)",
                       "gemini-nano-banana-2.1": "Nano Banana 2.1 (~$0,034)"}
GEMINI_TTS_MODEL = "gemini-3.8-flash-tts"
GEMINI_VOICES = [("Kore", "Kadın · net"), ("Puck", "Erkek · neşeli"), ("Charon", "Erkek · bilgilendirici"),
                 ("Aoede", "Kadın · ferah"), ("Fenrir", "Erkek · heyecanlı"), ("Leda", "Kadın · genç"),
                 ("Orus", "Erkek · kararlı"), ("Zephyr", "Kadın · parlak"), ("Sulafat", "Kadın · sıcak"),
                 ("Gacrux", "Erkek · olgun"), ("Achird", "Erkek · samimi"), ("Vindemiatrix", "Kadın · nazik")]


def _gemini(key: str, body: dict, timeout: int = 180) -> dict:
    if not key:
        raise ServiceError("Bunun için Ayarlar > Yapay Zekâ bölümüne Gemini anahtarı girin (ücretsiz).")
    r = requests.post(GEMINI_INTERACTIONS, json=body, timeout=timeout,
                      headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    if r.status_code == 429:
        raise _quota_error(r)
    if not r.ok:
        text = r.text.lower()
        if "free" in text and ("tier" in text or "quota" in text) or "billing" in text:
            raise ServiceError("Bu Gemini modeli ücretli: Google AI Studio'da faturalandırmayı açmanız gerekir. "
                               "Ücretsiz için Pollinations veya Cloudflare'i seçin.")
        raise _fail("Gemini", r)
    return r.json()


def gemini_image(key: str, prompt: str, aspect: str, model: str = "gemini-3.1-flash-lite-image") -> bytes:
    data = _gemini(key, {"model": model, "input": prompt,
                         "response_format": {"type": "image", "mime_type": "image/jpeg", "aspect_ratio": aspect,
                                             "image_size": "1K"}})
    blob = find_blob(data, "image")
    if not blob:
        raise ServiceError("Gemini görsel döndürmedi (istem güvenlik filtresine takılmış olabilir).")
    return blob[0]


def gemini_tts(key: str, text: str, voice: str = "Kore", style: str | None = None) -> bytes:
    """24 kHz mono WAV döndürür. Dili metinden kendisi anlar."""
    part = {"type": "text", "text": text}
    if style:
        part["annotations"] = [{"type": "speech_metadata", "style": style}]
    data = _gemini(key, {"model": GEMINI_TTS_MODEL, "input": [{"type": "user_input", "content": [part]}],
                         "response_format": {"type": "audio"},
                         "generation_config": {"speech_config": [{"voice": voice}]}})
    blob = find_blob(data, "audio")
    if not blob:
        raise ServiceError("Gemini ses döndürmedi.")
    audio = blob[0]
    if not audio.startswith(b"RIFF"):  # başlıksız PCM gelirse WAV başlığı ekle
        import io
        import wave
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(audio)
        audio = buf.getvalue()
    return audio


# ----------------------------------------------------------------------------- Pollinations (ücretsiz)

_anon_lock = threading.Lock()
_anon_last = [0.0]
ANON_GAP = 46  # anahtarsız kullanımda IP başına en az 45 sn ara


def pollinations_image(prompt: str, width: int, height: int, seed: int, key: str = "",
                       wait: Callable[[str], None] = lambda s: None,
                       should_stop: Callable[[], bool] = lambda: False) -> bytes:
    quoted = urllib.parse.quote(prompt[:1500], safe="")
    if key:
        url = f"https://gen.pollinations.ai/image/{quoted}"
        params = {"model": "flux", "width": width, "height": height, "seed": seed, "nologo": "true"}
        r = requests.get(url, params=params, headers={**UA, "Authorization": f"Bearer {key}"}, timeout=180)
    else:
        # anahtarsız: tek görsel/45 sn ve en fazla 768x768 piksel alan (en-boy oranı korunur)
        scale = min(1.0, (768 * 768 / (width * height)) ** 0.5)
        width, height = int(width * scale) // 16 * 16, int(height * scale) // 16 * 16
        with _anon_lock:
            remaining = ANON_GAP - (time.monotonic() - _anon_last[0])
            while remaining > 0:
                if should_stop():
                    raise ServiceError("İptal edildi.")
                wait(f"Ücretsiz sıra bekleniyor ({int(remaining)} sn)")
                time.sleep(1)
                remaining = ANON_GAP - (time.monotonic() - _anon_last[0])
            params = {"width": width, "height": height, "seed": seed, "nologo": "true"}
            for attempt in range(8):  # ücretsiz hat yoğunsa "N sn sonra dene" der; bekleyip tekrar dener
                r = requests.get(f"https://image.pollinations.ai/prompt/{quoted}", params=params, headers=UA,
                                 timeout=180)
                _anon_last[0] = time.monotonic()
                if r.status_code not in (402, 429, 502, 503) or attempt == 7:
                    break
                hint = re.search(r"after (\d+)", r.text or "")
                delay = int(r.headers.get("Retry-After") or (hint.group(1) if hint else 0) or 15) + 2
                for left in range(min(delay, 90), 0, -1):
                    if should_stop():
                        raise ServiceError("İptal edildi.")
                    wait(f"Ücretsiz sunucu yoğun, tekrar deneniyor ({left} sn)")
                    time.sleep(1)
    if not r.ok or not r.headers.get("content-type", "").startswith("image/"):
        raise _fail("Pollinations", r)
    return r.content


# ----------------------------------------------------------------------------- Cloudflare Workers AI (ücretsiz kota)

CF_MODEL = "@cf/black-forest-labs/flux-2-klein-4b"
CF_FALLBACK = "@cf/black-forest-labs/flux-1-schnell"


def cloudflare_image(cred: str, prompt: str, width: int, height: int, seed: int) -> bytes:
    account, _, token = cred.partition(":")
    if not account or not token:
        raise ServiceError("Cloudflare için 'hesap-id:api-token' biçiminde anahtar girin.")
    base = f"https://api.cloudflare.com/client/v4/accounts/{account.strip()}/ai/run/"
    headers = {"Authorization": f"Bearer {token.strip()}"}
    form = {"prompt": (None, prompt[:2048]), "width": (None, str(min(width, 1920))),
            "height": (None, str(min(height, 1920))), "seed": (None, str(seed))}
    r = requests.post(base + CF_MODEL, files=form, headers=headers, timeout=180)
    if r.status_code in (400, 404):  # yeni model bu hesapta yoksa eskisine düş
        r = requests.post(base + CF_FALLBACK, json={"prompt": prompt[:2048], "steps": 4}, headers=headers,
                          timeout=180)
    if not r.ok:
        raise _fail("Cloudflare", r)
    if r.headers.get("content-type", "").startswith("image/"):
        return r.content
    data = r.json()
    image = (data.get("result") or {}).get("image") if isinstance(data, dict) else None
    if not image:
        raise ServiceError("Cloudflare görsel döndürmedi: " + str(data.get("errors") or data)[:200])
    return base64.b64decode(image)


# ----------------------------------------------------------------------------- Pexels (ücretsiz stok video)

PEXELS_LOCALES = {"tr": "tr-TR", "de": "de-DE", "fr": "fr-FR", "es": "es-ES", "it": "it-IT", "pt": "pt-BR",
                  "ru": "ru-RU", "ja": "ja-JP", "ko": "ko-KR", "zh": "zh-CN", "pl": "pl-PL", "nl": "nl-NL",
                  "id": "id-ID"}


def pexels_video(key: str, query: str, min_seconds: float, lang: str = "en",
                 used: set[int] | None = None) -> tuple[bytes, str]:
    """Aramaya uyan dikey bir stok video indirir: (mp4, 'Video: ad / Pexels' künyesi)."""
    if not key:
        raise ServiceError("Stok video için Ayarlar > Servisler'e ücretsiz Pexels anahtarı girin.")
    params = {"query": query[:100], "orientation": "portrait", "size": "medium", "per_page": 15}
    if lang in PEXELS_LOCALES:
        params["locale"] = PEXELS_LOCALES[lang]
    r = requests.get("https://api.pexels.com/videos/search", params=params,
                     headers={**UA, "Authorization": key.strip()}, timeout=30)
    if not r.ok:
        raise _fail("Pexels", r)
    videos = [v for v in r.json().get("videos", []) if v.get("id") not in (used or set())]
    if not videos:
        raise ServiceError(f"Pexels'te '{query}' için video bulunamadı.")
    videos.sort(key=lambda v: (v.get("duration", 0) < min_seconds, -min(v.get("duration", 0), 30)))
    video = videos[0]
    files = [f for f in video.get("video_files", []) if f.get("link") and (f.get("file_type") or "").endswith("mp4")
             and (f.get("height") or 0) >= (f.get("width") or 0)]
    files.sort(key=lambda f: (abs((f.get("height") or 0) - 1920), -(f.get("height") or 0)))
    if not files:
        raise ServiceError("Pexels videosunun uygun bir dosyası yok.")
    if used is not None:
        used.add(video["id"])
    credit = f"Video: {(video.get('user') or {}).get('name', 'Pexels')} / Pexels"
    return _fetch(files[0]["link"]), credit


# ----------------------------------------------------------------------------- Higgsfield (ücretli)

HF_BASE = "https://api.higgsfield.ai"
HF_ASPECTS = {"16:9": "16:9", "9:16": "9:16", "1:1": "1:1", "4:5": "3:4"}


def _hf_headers(key: str) -> dict:
    if ":" not in key:
        raise ServiceError("Higgsfield anahtarını 'anahtar-id:gizli-anahtar' biçiminde girin.")
    return {"Authorization": f"Key {key.strip()}", "Content-Type": "application/json"}


def higgsfield_run(key: str, endpoint: str, body: dict, on_wait: Callable[[str], None] = lambda s: None,
                   should_stop: Callable[[], bool] = lambda: False, timeout: int = 900) -> dict:
    headers = _hf_headers(key)
    r = requests.post(f"{HF_BASE}/{endpoint}", json=body, headers=headers, timeout=60)
    if not r.ok:
        raise _fail("Higgsfield", r)
    job = r.json()
    status_url = job.get("status_url") or f"{HF_BASE}/requests/{job['request_id']}/status"
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if should_stop():
            requests.post(job.get("cancel_url") or status_url.replace("/status", "/cancel"), headers=headers,
                          timeout=20)
            raise ServiceError("İptal edildi.")
        time.sleep(3)
        s = requests.get(status_url, headers=headers, timeout=30)
        if not s.ok:
            raise _fail("Higgsfield", s)
        data = s.json()
        status = data.get("status")
        if status == "completed":
            return data
        if status in ("failed", "nsfw", "canceled"):
            reason = "içerik filtresine takıldı" if status == "nsfw" else (data.get("error") or status)
            raise ServiceError(f"Higgsfield üretimi başarısız: {reason}")
        on_wait(f"Higgsfield'da üretiliyor ({int(time.monotonic() - start)} sn)")
    raise ServiceError("Higgsfield zaman aşımına uğradı.")


def _fetch(url: str) -> bytes:
    r = requests.get(url, timeout=300, headers=UA)
    r.raise_for_status()
    return r.content


def higgsfield_image(key: str, prompt: str, aspect: str, **kw) -> bytes:
    data = higgsfield_run(key, "higgsfield-ai/soul/standard",
                          {"prompt": prompt, "aspect_ratio": HF_ASPECTS.get(aspect, "16:9"), "resolution": "1080p",
                           "batch_size": 1}, **kw)
    images = data.get("images") or []
    if not images:
        raise ServiceError("Higgsfield görsel döndürmedi.")
    return _fetch(images[0]["url"])


def higgsfield_video(key: str, prompt: str, aspect: str = "9:16", duration: int = 5, **kw) -> bytes:
    data = higgsfield_run(key, "bytedance/seedance-2.0/text-to-video",
                          {"prompt": prompt, "duration": max(4, min(int(duration), 15)), "aspect_ratio": aspect,
                           "resolution": "720p", "generate_audio": False}, **kw)
    video = data.get("video") or {}
    if not video.get("url"):
        raise ServiceError("Higgsfield video döndürmedi.")
    return _fetch(video["url"])


# ----------------------------------------------------------------------------- ElevenLabs (ücretsiz kota + ücretli)

EL_BASE = "https://api.elevenlabs.io"
EL_MODEL = "eleven_multilingual_v2"
EL_FALLBACK_VOICES = [("JBFqnCBsd6RMkjVDRZzb", "George · Erkek"), ("21m00Tcm4TlvDq8ikWAM", "Rachel · Kadın")]


def _el(key: str) -> dict:
    if not key:
        raise ServiceError("Bunun için Ayarlar > Servisler'e ElevenLabs anahtarı girin.")
    return {"xi-api-key": key.strip()}


def elevenlabs_voices(key: str) -> list[tuple[str, str]]:
    r = requests.get(f"{EL_BASE}/v2/voices", params={"page_size": 100}, headers=_el(key), timeout=30)
    if not r.ok:
        raise _fail("ElevenLabs", r)
    voices = []
    for v in r.json().get("voices", []):
        labels = v.get("labels") or {}
        gender = {"male": "Erkek", "female": "Kadın"}.get(labels.get("gender", ""), "")
        voices.append((v["voice_id"], " · ".join(x for x in (v.get("name", ""), gender) if x)))
    return voices or EL_FALLBACK_VOICES


def elevenlabs_tts(key: str, text: str, voice_id: str) -> tuple[bytes, list[tuple[float, float, str]]]:
    """(mp3, kelime zamanları) döndürür."""
    r = requests.post(f"{EL_BASE}/v1/text-to-speech/{voice_id}/with-timestamps", headers=_el(key), timeout=180,
                      json={"text": text, "model_id": EL_MODEL})
    if not r.ok:
        raise _fail("ElevenLabs", r)
    data = r.json()
    words = []
    align = data.get("alignment") or {}
    chars, starts, ends = align.get("characters") or [], align.get("character_start_times_seconds") or [], \
        align.get("character_end_times_seconds") or []
    cur, cur_start, cur_end = "", 0.0, 0.0
    for ch, s, e in zip(chars, starts, ends):
        if ch.isspace():
            if cur:
                words.append((cur_start, cur_end, cur))
            cur = ""
            continue
        if not cur:
            cur_start = s
        cur, cur_end = cur + ch, e
    if cur:
        words.append((cur_start, cur_end, cur))
    return base64.b64decode(data["audio_base64"]), words


def elevenlabs_dub(key: str, target_lang: str, *, file: Path | None = None, source_url: str | None = None,
                   watermark: bool = True, name: str = "TekTıkla",
                   on_wait: Callable[[str], None] = lambda s: None,
                   should_stop: Callable[[], bool] = lambda: False) -> tuple[bytes, str]:
    """Otomatik dublaj: konuşmacının kendi sesini koruyarak çevirir. (dosya içeriği, uzantı) döndürür."""
    headers = _el(key)
    form = {"target_lang": (None, target_lang), "source_lang": (None, "auto"), "num_speakers": (None, "0"),
            "watermark": (None, "true" if watermark else "false"), "name": (None, name[:100])}
    if file:
        with open(file, "rb") as fh:
            r = requests.post(f"{EL_BASE}/v1/dubbing", headers=headers, timeout=600,
                              files={**form, "file": (file.name, fh, "video/mp4")})
    else:
        r = requests.post(f"{EL_BASE}/v1/dubbing", headers=headers, timeout=120,
                          files={**form, "source_url": (None, source_url or "")})
    if not r.ok:
        raise _fail("ElevenLabs", r)
    dub_id = r.json()["dubbing_id"]
    start = time.monotonic()
    while True:
        if should_stop():
            raise ServiceError("İptal edildi.")
        time.sleep(5)
        s = requests.get(f"{EL_BASE}/v1/dubbing/{dub_id}", headers=headers, timeout=30)
        if not s.ok:
            raise _fail("ElevenLabs", s)
        info = s.json()
        if info.get("status") == "dubbed":
            break
        if info.get("status") == "failed":
            raise ServiceError("ElevenLabs dublajı başarısız: " + str(info.get("error") or "bilinmeyen hata"))
        on_wait(f"ElevenLabs dublajlıyor ({int(time.monotonic() - start)} sn)")
        if time.monotonic() - start > 3600:
            raise ServiceError("ElevenLabs dublajı zaman aşımına uğradı.")
    d = requests.get(f"{EL_BASE}/v1/dubbing/{dub_id}/audio/{target_lang}", headers=headers, timeout=600)
    if not d.ok:
        raise _fail("ElevenLabs", d)
    ext = ".mp4" if "video" in d.headers.get("content-type", "") else ".mp3"
    return d.content, ext


# ----------------------------------------------------------------------------- anahtar biçim kontrolü

def validate_key(service: str, value: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return "Anahtar boş olamaz."
    if service in ("cloudflare", "higgsfield") and ":" not in value:
        return SERVICES[service]["hint"]
    if len(value) < 12:
        return "Anahtar çok kısa görünüyor."
    return None
