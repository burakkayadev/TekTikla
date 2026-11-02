"""TekTıkla - Medya ve yapay zekâ stüdyosu: video ve görsel indir, yapay zekâyla üret, kurgula."""

APP_NAME = "TekTıkla"
APP_TAGLINE = "Medya ve Yapay Zekâ Stüdyosu"  # pencere başlığında "TekTıkla — …" olarak görünür (çevrilir)
APP_VERSION = "3.0.0"
# "Destek ol" penceresi: GitHub profilinin QR kodu. Bağış linki yazılınca yanında ikinci bir QR kod olarak görünür.
SUPPORT_GITHUB = "https://github.com/BurakCNKaya"
SUPPORT_DONATE = "https://buymeacoffee.com/vesperky"  # bağış sayfası: "Bana bir kahve alır mısın?"
# Hesap sistemi (Firebase Authentication): Firebase konsolundaki web uygulaması ayarları. Bunlar gizli değildir
# (web uygulamalarında herkese açık durur); güvenliği Firebase'deki yetkili alan adları sağlar. Boşsa hesap kapalı.
FIREBASE = {"apiKey": "AIzaSyB1RDUR-tByEiVV7_M1YUyniSHReRH6T-U", "authDomain": "tektikla-ae4b5.firebaseapp.com",
            "projectId": "tektikla-ae4b5", "appId": "1:464774449022:web:c0cb0c4a269cc45e63152f"}
# Yeni üyelere hoş geldin e-postası: Google Apps Script web uygulamasının adresi (server/welcome/). Boşsa gönderilmez.
WELCOME_URL = ""
# GitHub'a yükleyince "kullaniciadi/depo" yazın; uygulama güncellemeleri bu deponun Releases kısmından alır.
GITHUB_REPO = "BurakCNKaya/TekTikla"
