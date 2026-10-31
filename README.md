# TekTıkla — Bütün sitelerden video indirici

Link yapıştır (ya da sadece kopyala), TekTıkla videoyu algılasın; istediğin kalitede, MP3 olarak veya altyazılı indir. Yapay zekâ ile videoyu izlemeden özetini al.

## İndir

**[En son sürümü indir (Windows 10/11)](https://github.com/BurakCNKaya/TekTikla/releases/latest)** — sayfadaki `TekTikla-Setup-<sürüm>.exe` dosyasını indirip çalıştırın.

## Kurulum (kullanıcılar için)

`TekTikla-Setup-<sürüm>.exe` dosyasını çalıştırıp **Kur**'a basmak yeterli:

- Yönetici izni gerekmez; `%LOCALAPPDATA%\Programs\TekTıkla` klasörüne kurulur, Başlat menüsüne ve masaüstüne eklenir.
- İlk açılışta FFmpeg ve (bilgisayarda Node.js yoksa) YouTube için Deno **otomatik** indirilir; kullanıcının bir şeye basması gerekmez.
- Kaldırmak: *Ayarlar > Uygulamalar > TekTıkla > Kaldır*.
- Exe imzasız olduğu için Windows SmartScreen "Bilinmeyen yayımcı" diyebilir: **Ek bilgi > Yine de çalıştır**.
- Arayüz Windows'un WebView2 bileşenini kullanır (Windows 10/11'de hazır gelir; yoksa kurulum uyarır).

## Özellikler

| Sekme | Ne yapar |
|---|---|
| **İndir** | Linki analiz eder: tüm kaliteler (144p–8K, tahmini boyutlarıyla), MP4/MKV/WEBM, MP3/M4A/OPUS/FLAC/WAV, sitedeki altyazılar veya kendi .srt/.vtt/.ass dosyan (gömülü / videoya yakılmış / ayrı .srt), kesit indirme, oynatma listesi. ⚡ Hızlı İndir ve Hızlı MP3 analiz beklemeden indirir. |
| **İndirmeler** | Kuyruk: canlı ilerleme, hız, kalan süre, iptal, tekrar dene, dosyayı aç / klasörde göster. Aynı anda 1–4 indirme. |
| **AI Özet** | Videonun altyazı dökümünü Claude'a (Anthropic) okutup Türkçe tek cümlelik özet, genel özet, önemli noktalar ve konu etiketleri çıkarır. Kendi Anthropic API anahtarınız gerekir (Ayarlar > Yapay Zekâ); anahtar Windows DPAPI ile şifreli saklanır. |
| **Geçmiş** | Aranabilir indirme geçmişi. |
| **Ayarlar** | Kayıt klasörü, koyu/açık tema, pano izleme, paralel indirme, hız sınırı, varsayılan biçimler, kapak/bilgi gömme, SponsorBlock, tarayıcı çerezleri, yt-dlp ve uygulama güncellemesi. |

## Yeni sürüm yayınlama

1. `tektikla/__init__.py` içindeki `APP_VERSION`'ı artırın (örn. `2.2.0`). Güncelleme kaynağı aynı dosyadaki `GITHUB_REPO`'dur.
2. **`kurulum_olustur.bat`** ile `Kurulum\TekTikla-Setup-2.2.0.exe`'yi üretin; değişiklikleri commit'leyip gönderin.
3. GitHub'da **Releases > Draft a new release**: etiket `v2.2.0`, kurulum exe'sini eke sürükleyip yayınlayın.

Kurulu TekTıkla'lar açılışta en son Release'i kontrol eder; yeni sürüm varsa kenar çubuğunda "Güncelleme var" çıkar, tek tıkla indirir (SHA-256 ile doğrular), sessizce kurar ve yeniden açılır. Siteler değiştiğinde yalnızca indirme motorunu güncellemek için Ayarlar > yt-dlp > Güncelle yeterlidir; yeni sürüm yayınlamak gerekmez.

## Geliştirme

```bash
kurulum.bat                 # .venv oluşturur, bağımlılıkları kurar
TekTıkla.bat                     # kaynak koddan çalıştırır
kurulum_olustur.bat         # Kurulum\TekTikla-Setup-<sürüm>.exe üretir
```

Tanılama: `TekTikla.exe --selftest <link> <klasör>` bileşen kurulumu, analiz, altyazılı video ve MP3 indirmeyi dener; sonucu `<klasör>\selftest.txt`'ye yazar.

```
tektikla.py              giriş noktası
tektikla/app.py          pencere (pywebview + WebView2)
tektikla/api.py          arayüz ↔ Python köprüsü, indirme kuyruğu, pano izleme
tektikla/web/            arayüz (index.html, style.css, app.js)
tektikla/engine.py       indirme motoru (yt-dlp + FFmpeg: kalite, MP3, altyazı gömme/yakma, kesit)
tektikla/ai.py           AI video özeti (altyazı dökümü + Claude)
tektikla/tools.py        FFmpeg/Deno otomatik kurulum, yt-dlp güncelleme
tektikla/updater.py      GitHub Releases üzerinden uygulama güncellemesi
tektikla/config.py       ayarlar, geçmiş, DPAPI ile şifreli API anahtarı
installer/setup.py  kurulum/kaldırma programı
build_release.py    uygulama + kurulum exe'sini derler
```

## Bilinmesi gerekenler

- DRM korumalı servisler (Netflix, Disney+, Spotify vb.) teknik olarak indirilemez.
- Giriş isteyen siteler (ör. Vimeo, yaş sınırlı videolar) için tarayıcıda giriş yapıp Ayarlar > Tarayıcı çerezleri'nden o tarayıcıyı seçin.
- AI özeti Anthropic API'sini kullanır; ücreti anahtar sahibinin hesabından düşer.
- Telif hakkı olan içerikleri yalnızca kişisel kullanım için ve sitenin kurallarına uygun şekilde indirin.
