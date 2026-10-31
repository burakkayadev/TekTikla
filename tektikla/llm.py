"""Yapay zekâ servisleri: Google Gemini (ücretsiz anahtar) ve Claude Haiku 5.5.

Özet ve altyazı çevirisi aynı `generate()` fonksiyonunu kullanır; cevap her zaman bir
pydantic modeline uyan JSON olarak alınır.
"""
from __future__ import annotations

import json
import re
from typing import TypeVar

import anthropic
import requests
from pydantic import BaseModel, ValidationError

PROVIDERS = {
    "gemini": {"name": "Google Gemini", "model": "gemini-3.5-flash-lite",
               "key_url": "https://aistudio.google.com/apikey"},
    "claude": {"name": "Claude Haiku 5.5", "model": "claude-haiku-5-5",
               "key_url": "https://console.anthropic.com/settings/keys"},
}
DEFAULT_PROVIDER = "gemini"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

T = TypeVar("T", bound=BaseModel)


class AIError(Exception):
    pass


def valid_key(provider: str, key: str) -> str | None:
    """Biçim hatası varsa açıklamasını döndürür."""
    key = key.strip()
    if provider == "claude" and not key.startswith("sk-ant-"):
        return "Anthropic API anahtarı 'sk-ant-' ile başlar."
    if provider == "gemini" and (len(key) < 20 or " " in key):
        return "Bu bir Gemini API anahtarına benzemiyor (aistudio.google.com/apikey)."
    return None


def generate(provider: str, api_key: str, system: str, prompt: str, schema: type[T], effort: str = "low") -> T:
    if not api_key:
        name = PROVIDERS[provider]["name"]
        raise AIError(f"Yapay zekâ özellikleri için Ayarlar > Yapay Zekâ bölümüne {name} anahtarınızı girin.")
    if provider == "claude":
        return _claude(api_key, system, prompt, schema, effort)
    return _gemini(api_key, system, prompt, schema)


# ----------------------------------------------------------------------------- Claude

def _claude(api_key: str, system: str, prompt: str, schema: type[T], effort: str) -> T:
    client = anthropic.Anthropic(api_key=api_key, timeout=240.0)
    try:
        response = client.messages.parse(
            model=PROVIDERS["claude"]["model"],
            max_tokens=32000,
            output_config={"effort": effort},
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
        )
    except anthropic.AuthenticationError:
        raise AIError("Claude API anahtarı geçersiz. Ayarlar > Yapay Zekâ bölümünden kontrol edin.") from None
    except anthropic.PermissionDeniedError:
        raise AIError("Bu API anahtarının Claude'u kullanma izni yok.") from None
    except anthropic.RateLimitError:
        raise AIError("Claude: çok fazla istek gönderildi. Biraz sonra tekrar deneyin.") from None
    except anthropic.BadRequestError as e:
        if any(w in str(e).lower() for w in ("credit", "billing")):
            raise AIError("Anthropic hesabınızda yeterli kredi yok (console.anthropic.com > Billing).") from None
        raise AIError(f"Claude isteği reddetti: {str(e)[:300]}") from None
    except anthropic.APIConnectionError:
        raise AIError("Claude'a bağlanılamadı. İnternet bağlantınızı kontrol edin.") from None
    except anthropic.APIStatusError as e:
        raise AIError(f"Claude geçici bir hata verdi ({e.status_code}). Biraz sonra tekrar deneyin.") from None

    if response.stop_reason == "refusal":
        raise AIError("Claude bu içerik için yanıt vermeyi reddetti.")
    if response.stop_reason == "max_tokens":
        raise AIError("Yanıt çok uzun olduğu için yarıda kesildi.")
    if response.parsed_output is None:
        raise AIError("Yapay zekâ yanıtı okunamadı, lütfen tekrar deneyin.")
    return response.parsed_output


# ----------------------------------------------------------------------------- Gemini

def _gemini_schema(node: dict, defs: dict) -> dict:
    """pydantic JSON Schema'sını Gemini'nin OpenAPI alt kümesine çevirir ($ref açılır, tipler büyük harf)."""
    if "$ref" in node:
        return _gemini_schema(defs[node["$ref"].split("/")[-1]], defs)
    out: dict = {"type": node["type"].upper()}
    if node.get("description"):
        out["description"] = node["description"]
    if node["type"] == "object":
        out["properties"] = {k: _gemini_schema(v, defs) for k, v in node.get("properties", {}).items()}
        out["required"] = node.get("required", list(out["properties"]))
        out["propertyOrdering"] = list(out["properties"])
    elif node["type"] == "array":
        out["items"] = _gemini_schema(node["items"], defs)
    return out


def _gemini(api_key: str, system: str, prompt: str, schema: type[T]) -> T:
    js = schema.model_json_schema()
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": _gemini_schema(js, js.get("$defs", {})),
            "maxOutputTokens": 65536,
        },
    }
    try:
        r = requests.post(GEMINI_URL.format(model=PROVIDERS["gemini"]["model"]), json=body, timeout=240,
                          headers={"x-goog-api-key": api_key})  # anahtar URL'de değil, başlıkta
    except requests.RequestException:
        raise AIError("Gemini'ye bağlanılamadı. İnternet bağlantınızı kontrol edin.") from None

    if r.status_code != 200:
        try:
            err = r.json().get("error", {})
        except ValueError:
            err = {}
        msg, status = str(err.get("message", "")), str(err.get("status", ""))
        if r.status_code in (401, 403) or "api key" in msg.lower() or "API_KEY" in msg:
            raise AIError("Gemini API anahtarı geçersiz. Ayarlar > Yapay Zekâ bölümünden kontrol edin.")
        if r.status_code == 429 or status == "RESOURCE_EXHAUSTED":
            raise AIError("Gemini'nin ücretsiz kotası doldu. Biraz bekleyin veya yarın tekrar deneyin "
                          "(günlük kota gece yenilenir).")
        raise AIError(f"Gemini hata verdi ({r.status_code}): {msg[:300]}")

    data = r.json()
    if data.get("promptFeedback", {}).get("blockReason"):
        raise AIError("Gemini bu içerik için yanıt vermeyi reddetti.")
    candidates = data.get("candidates") or []
    if not candidates:
        raise AIError("Gemini boş yanıt döndürdü, lütfen tekrar deneyin.")
    cand = candidates[0]
    reason = cand.get("finishReason", "STOP")
    if reason in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"):
        raise AIError("Gemini bu içerik için yanıt vermeyi reddetti.")
    if reason == "MAX_TOKENS":
        raise AIError("Yanıt çok uzun olduğu için yarıda kesildi.")
    text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []) if not p.get("thought"))
    try:
        return schema.model_validate_json(text)
    except ValidationError:
        # nadiren JSON bir kod bloğu içinde gelebiliyor
        match = re.search(r"\{.*\}", text, re.S)
        try:
            return schema.model_validate(json.loads(match.group(0))) if match else schema.model_validate_json(text)
        except (ValidationError, ValueError):
            raise AIError("Yapay zekâ yanıtı okunamadı, lütfen tekrar deneyin.") from None
