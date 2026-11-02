"""Hesap sistemi (Firebase Authentication): e-posta/şifre, Google ve GitHub ile giriş; kayıt olmadan devam.

E-posta ve şifre işlemleri Firebase'in REST adresleriyle doğrudan yapılır. Google ve GitHub girişi sistem
tarayıcısında açılır (Google, uygulama içi tarayıcılarda girişe izin vermez): tarayıcıdaki sayfa (web/auth.html)
bu bilgisayardaki küçük sunucudan (localhost) gelir, giriş bitince oturumu aynı sunucuya geri gönderir. Gelen anahtar
Firebase'e sorularak doğrulanır. Oturumun yenileme anahtarı Windows DPAPI ile şifreli saklanır (api.py).
Test için TEKTIKLA_AUTH_EMULATOR=127.0.0.1:9099 verilirse Firebase'in yerel emülatörü kullanılır.
"""
from __future__ import annotations

import json
import os
import secrets
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

import requests

from . import FIREBASE, i18n

EMULATOR = os.environ.get("TEKTIKLA_AUTH_EMULATOR", "")
SDK_VERSION = "12.6.0"  # tarayıcıdaki giriş sayfasının yüklediği Firebase JS SDK
PROVIDERS = {"google": "google.com", "github": "github.com", "password": "password"}
ERRORS = {
    "EMAIL_EXISTS": "Bu e-postayla zaten bir hesap var. Giriş yapmayı dene.",
    "EMAIL_NOT_FOUND": "Bu e-postayla kayıtlı hesap yok.",
    "INVALID_PASSWORD": "Şifre yanlış.",
    "INVALID_LOGIN_CREDENTIALS": "E-posta ya da şifre yanlış.",
    "INVALID_EMAIL": "Geçerli bir e-posta adresi yaz.",
    "MISSING_PASSWORD": "Şifreni yaz.",
    "MISSING_EMAIL": "E-posta adresini yaz.",
    "WEAK_PASSWORD": "Şifre en az 6 karakter olmalı.",
    "TOO_MANY_ATTEMPTS_TRY_LATER": "Çok fazla deneme yapıldı; biraz sonra tekrar dene.",
    "USER_DISABLED": "Bu hesap devre dışı bırakılmış.",
    "USER_NOT_FOUND": "Hesap bulunamadı; yeniden giriş yap.",
    "TOKEN_EXPIRED": "Oturumun süresi doldu; yeniden giriş yap.",
    "INVALID_REFRESH_TOKEN": "Oturumun süresi doldu; yeniden giriş yap.",
    "INVALID_ID_TOKEN": "Oturumun süresi doldu; yeniden giriş yap.",
    "CREDENTIAL_TOO_OLD_LOGIN_AGAIN": "Güvenlik için önce çıkış yapıp yeniden giriş yapman gerekiyor.",
    "OPERATION_NOT_ALLOWED": "Bu giriş yöntemi henüz açılmamış.",
    "PASSWORD_LOGIN_DISABLED": "E-postayla giriş henüz açılmamış.",
}
# oturum geçersizse sessizce çıkış yapılır (hesap silinmiş, şifre değişmiş…)
EXPIRED = {"TOKEN_EXPIRED", "INVALID_REFRESH_TOKEN", "USER_NOT_FOUND", "USER_DISABLED", "INVALID_ID_TOKEN"}


class AccountError(Exception):
    def __init__(self, message: str, code: str = ""):
        super().__init__(message)
        self.code = code


def config() -> dict:
    """Firebase web uygulaması ayarları (gizli değildir; güvenliği yetkili alan adları sağlar). Boşsa hesap sistemi kapalı."""
    if EMULATOR:
        return {"apiKey": "demo-key", "authDomain": "localhost", "projectId": "demo-tektikla", "appId": "demo",
                "emulator": f"http://{EMULATOR}"}
    return dict(FIREBASE) if FIREBASE.get("apiKey") else {}


def configured() -> bool:
    return bool(config())


def _post(service: str, path: str, body: dict) -> dict:
    cfg = config()
    if not cfg:
        raise AccountError("Hesap sistemi henüz kurulmadı.")
    host = {"auth": "identitytoolkit.googleapis.com/v1", "token": "securetoken.googleapis.com/v1"}[service]
    base = f"http://{EMULATOR}/{host}" if EMULATOR else f"https://{host}"  # emülatör aynı yolları kendi adresinde sunar
    url = f"{base}/{path}?key={cfg['apiKey']}"
    try:
        # yenileme adresi form verisi, diğerleri JSON bekler
        r = requests.post(url, data=body, timeout=20) if service == "token" else requests.post(url, json=body, timeout=20)
    except requests.RequestException as e:
        raise AccountError("Sunucuya ulaşılamadı. İnternet bağlantını kontrol et.") from e
    if r.ok:
        return r.json()
    try:
        code = str(r.json()["error"]["message"])
    except (ValueError, KeyError, TypeError):
        code = f"HTTP {r.status_code}"
    key = code.split(" : ")[0].split(":")[0].strip()
    raise AccountError(ERRORS.get(key, f"İşlem yapılamadı ({key})."), key)


def profile(id_token: str, provider: str) -> dict:
    """Hesap bilgisi Firebase'den okunur; bu aynı zamanda anahtarın gerçek olduğunu doğrular."""
    users = _post("auth", "accounts:lookup", {"idToken": id_token}).get("users") or []
    if not users:
        raise AccountError(ERRORS["USER_NOT_FOUND"], "USER_NOT_FOUND")
    u = users[0]
    infos = u.get("providerUserInfo") or []
    info = next((p for p in infos if p.get("providerId") == PROVIDERS.get(provider)), infos[0] if infos else {})
    email = u.get("email") or info.get("email") or ""
    return {"uid": u["localId"], "email": email, "provider": provider,
            "name": (u.get("displayName") or info.get("displayName") or email.split("@")[0] or "TekTıkla")[:60],
            "photo": u.get("photoUrl") or info.get("photoUrl") or "",
            "verified": bool(u.get("emailVerified")) or provider != "password"}


def _session(id_token: str, refresh_token: str, expires_in, provider: str) -> dict:
    return {"id_token": id_token, "refresh_token": refresh_token, "provider": provider,
            "expires": time.time() + int(expires_in or 3600) - 120}


def sign_up(email: str, password: str, name: str) -> tuple[dict, dict]:
    data = _post("auth", "accounts:signUp", {"email": email, "password": password, "returnSecureToken": True})
    if name:
        _post("auth", "accounts:update", {"idToken": data["idToken"], "displayName": name, "returnSecureToken": False})
    try:  # doğrulama e-postası (beklemeden devam edilir)
        _post("auth", "accounts:sendOobCode", {"requestType": "VERIFY_EMAIL", "idToken": data["idToken"]})
    except AccountError:
        pass
    sess = _session(data["idToken"], data["refreshToken"], data.get("expiresIn"), "password")
    return sess, profile(sess["id_token"], "password")


def sign_in(email: str, password: str) -> tuple[dict, dict]:
    data = _post("auth", "accounts:signInWithPassword", {"email": email, "password": password, "returnSecureToken": True})
    sess = _session(data["idToken"], data["refreshToken"], data.get("expiresIn"), "password")
    return sess, profile(sess["id_token"], "password")


def from_browser(data: dict) -> tuple[dict, dict]:
    """Tarayıcıdaki giriş sayfasından gelen oturum; Firebase'e sorularak doğrulanır."""
    provider = next((k for k, v in PROVIDERS.items() if v == data.get("providerId")), "")
    if provider not in ("google", "github") or not data.get("idToken") or not data.get("refreshToken"):
        raise AccountError("Giriş tamamlanamadı; yeniden dene.")
    sess = _session(str(data["idToken"]), str(data["refreshToken"]), 3600, provider)
    return sess, profile(sess["id_token"], provider)


def fresh(sess: dict) -> dict:
    """Kimlik anahtarı bir saat geçerlidir; süresi dolduysa yenileme anahtarıyla yenisi alınır."""
    if sess.get("id_token") and sess.get("expires", 0) > time.time():
        return sess
    data = _post("token", "token", {"grant_type": "refresh_token", "refresh_token": sess["refresh_token"]})
    return _session(data["id_token"], data["refresh_token"], data.get("expires_in"), sess.get("provider", ""))


def send_reset(email: str) -> None:
    _post("auth", "accounts:sendOobCode", {"requestType": "PASSWORD_RESET", "email": email})


def send_verify(sess: dict) -> None:
    _post("auth", "accounts:sendOobCode", {"requestType": "VERIFY_EMAIL", "idToken": fresh(sess)["id_token"]})


def delete(sess: dict) -> None:
    _post("auth", "accounts:delete", {"idToken": fresh(sess)["id_token"]})


# ----------------------------------------------------------------------------- tarayıcıyla giriş

PAGE_TEXT = ("TekTıkla'ya giriş", "Google ile devam et", "GitHub ile devam et", "Giriş yapılıyor…",
             "Giriş yapıldı", "TekTıkla'ya dönebilirsin; bu sekmeyi kapatabilirsin.",
             "Giriş yapılamadı", "Tekrar dene", "Açılır pencere engellendi; düğmeye yeniden bas.",
             "Bu e-postayla başka bir yöntemle kayıt olmuşsun; o yöntemle giriş yap.",
             "Bu giriş yöntemi henüz açılmamış.", "Giriş penceresi kapatıldı.",
             "Bu bağlantının süresi doldu. TekTıkla'dan yeniden deneyin.")


class BrowserSignIn:
    """Google/GitHub girişi: sistem tarayıcısında açılan sayfayı veren ve dönüşü bekleyen yerel sunucu.
    Her giriş denemesi tek kullanımlık rastgele bir anahtarla eşleşir; başka sayfalar oturum gönderemez."""

    def __init__(self, page: Path, on_done: Callable[[dict], None]):
        state = self.state = {"nonce": None, "provider": None}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8") -> None:
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                path, _, query = self.path.partition("?")
                if path != "/auth":
                    return self._send(404, b"")
                nonce = urllib.parse.parse_qs(query).get("k", [""])[0]
                if not state["nonce"] or not secrets.compare_digest(nonce, state["nonce"]):
                    return self._send(403, i18n.t(PAGE_TEXT[-1]).encode("utf-8"))
                boot = {"config": config(), "provider": state["provider"], "nonce": state["nonce"], "sdk": SDK_VERSION,
                        "lang": i18n.current(), "rtl": i18n.current() in i18n.RTL,
                        "text": {t: i18n.t(t) for t in PAGE_TEXT}}
                html = page.read_text(encoding="utf-8").replace("/*BOOT*/null", json.dumps(boot, ensure_ascii=False))
                self._send(200, html.encode("utf-8"))

            def do_POST(self):
                if self.path != "/auth/done":
                    return self._send(404, b"")
                size = int(self.headers.get("Content-Length") or 0)
                if not 0 < size < 64_000:
                    return self._send(413, b"")
                try:
                    data = json.loads(self.rfile.read(size))
                except ValueError:
                    return self._send(400, b"")
                if not state["nonce"] or not secrets.compare_digest(str(data.get("nonce", "")), state["nonce"]):
                    return self._send(403, b"")
                state["nonce"] = None  # tek kullanımlık
                self._send(200, b"{}", "application/json")
                threading.Thread(target=on_done, args=(data,), daemon=True).start()

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def start(self, provider: str) -> str:
        """Tarayıcıda açılacak adres. Firebase'de "localhost" varsayılan olarak yetkili alan adıdır."""
        self.state.update(nonce=secrets.token_urlsafe(24), provider=provider)
        return f"http://localhost:{self.httpd.server_address[1]}/auth?k={self.state['nonce']}"

    def cancel(self) -> None:
        self.state.update(nonce=None, provider=None)
