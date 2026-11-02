# TekTıkla — Medya ve yapay zekâ stüdyosu

> ## 🌙 Veda notu: TekTıkla artık güncelleme almayacak
>
> Merhaba,
>
> Açık ve net söyleyeyim: **TekTıkla'ya bundan sonra yeni sürüm ve güncelleme gelmeyecek.** Bu proje burada tamamlandı. Yanlış anlaşılmasın: ben yazılım geliştirmeyi bırakmıyorum, yeni uygulamalar yapmaya devam ediyorum. Sadece TekTıkla'nın hikâyesinin son sayfası bu.
>
> **Nasıl başladı?** Her şey küçük bir fikirdi: "Bir linki yapıştırayım, tek tıkla insin." İlk günlerde yalnızca bir video indiriciydi. Sonra kullandıkça yeni ihtiyaçlar doğdu; özet çıkaran yapay zekâ, uzun videodan Reels kliplerini seçen kurgu, dublaj, kapak ve görsel üretimi, dosya dönüştürücü, izleme listesi, telefondan kullanım, Android uygulaması ve bir görsel düzenleyici geldi. Birkaç satırlık bir araç, 13 dilde konuşan küçük bir stüdyoya dönüştü. Bunun her satırı büyük bir keyifle, çoğu zaman da gece geç saatlere kadar yazıldı.
>
> **Son sürüm:** [v3.0.0](https://github.com/BurakCNKaya/TekTikla/releases/tag/v3.0.0). Kurulum dosyası, taşınabilir zip ve Android uygulaması bu sayfada duruyor ve indirilmeye devam edebilir.
>
> **Bundan sonra ne olacak? (Açık konuşayım)**
> - Yeni özellik ve hata düzeltmesi gelmeyecek.
> - İndirme motoru (yt-dlp) siteler değiştikçe eskir. Uygulamada **Ayarlar › İndirme motorunu güncelle** düğmesi bunu çoğu zaman yeni sürüm gerekmeden düzeltir; ama bir noktada bazı siteler çalışmayabilir.
> - Uygulamadaki "güncelleme var" bildirimi artık yeni bir sürüm getirmeyecek.
> - GitHub ve e-posta ile hesap girişi tamamlanmadı; yalnızca Google girişi çalışıyor. Hesap zaten isteğe bağlıydı, uygulama hesapsız tüm özellikleriyle çalışır.
> - Telefondan kullanım ve Android uygulaması aynı Wi-Fi'da, bilgisayardaki TekTıkla açıkken çalışır. Android uygulamasını gerçek bir telefonda deneme fırsatım olmadı; sorun çıkarsa şaşırmayın.
>
> **Kaynak kod açık ve MIT lisanslı.** Fikri beğenen, devam ettirmek ya da kendi sürümünü yapmak isteyen herkes depoyu çatallayabilir (fork) ve istediği gibi geliştirebilir.
>
> **Teşekkür.** TekTıkla'yı indiren, deneyen, hata bildiren, yıldız veren ve bana kahve ısmarlayan herkese kalpten teşekkür ederim. Bir yazılımın en güzel yanı, birinin gününü biraz kolaylaştırmış olmak. TekTıkla sizin için bir videoyu, bir kliği ya da bir dakikayı kolaylaştırdıysa, bu emek yerini bulmuş demektir. Yeni projelerde görüşmek üzere.
>
> **Küçük bir hatırlatma:** Telif hakkı olan içerikleri yalnızca kişisel kullanım için ve sitelerin kurallarına uygun şekilde indirin.
>
> Hoşça kalın, bol üretimli günler dilerim. ☕
>
> **Burak** ([@BurakCNKaya](https://github.com/BurakCNKaya)) · İsterseniz bir kahve: [buymeacoffee.com/vesperky](https://buymeacoffee.com/vesperky)

---

**İndir · Üret · Kurgula.**

Link yapıştır (ya da sadece kopyala), TekTıkla videoyu algılasın; istediğin kalitede, MP3 olarak veya altyazılı indir. Yapay zekâ ile videoyu izlemeden özetini al, uzun videodan kurgulanmış Reels/TikTok klipleri çıkar, kapak görseli üret ve düzenle, videoyu başka dile dublajla, dosyaları başka biçime dönüştür. Hepsini telefonundan da kullanabilirsin. Arayüz 13 dilde.

## İndir

**[En son sürümü indir (Windows 10/11)](https://github.com/BurakCNKaya/TekTikla/releases/latest)** — sayfadaki `TekTikla-Setup-<sürüm>.exe` dosyasını indirip çalıştırın.

**Android uygulaması (isteğe bağlı):** aynı sayfadaki `TekTikla-Android.apk`. Bilgisayardaki TekTıkla'yı telefondan kullanmaya yarar: QR kodu okutup bağlanır, YouTube/Instagram/TikTok'tan *Paylaş* ile link gönderilir, sonuçlar doğrudan Galeri'ye kaydedilir. Bilgisayarda TekTıkla açık olmalı ve iki cihaz aynı Wi-Fi'da olmalı (Android 10 ve üzeri). Uygulama kurmadan, telefonun tarayıcısından da kullanılabilir.

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
| **İndir** | Linki analiz eder: tüm kaliteler (144p–8K, tahmini boyutlarıyla), MP4/MKV/WEBM, MP3/M4A/OPUS/FLAC/WAV, sitedeki altyazılar veya kendi .srt/.vtt/.ass dosyan (gömülü / videoya yakılmış / ayrı .srt), kesit indirme, en yüksek çözünürlükte kapak fotoğrafı indirme, benzer videoları listeleme. **Oynatma listesi / kanal:** bütün videolar listelenir; arayıp istediklerini seçerek ya da **Hepsini indir** ile indir. ⚡ Hızlı İndir ve Hızlı MP3 analiz beklemeden indirir. |
| **İndirmeler** | Kuyruk: canlı ilerleme, hız, kalan süre, iptal, tekrar dene, dosyayı aç / klasörde göster. Aynı anda 1–4 iş. Reels ve dublaj işleri de burada görünür. |
| **İzleme listesi** | Sonra izleyeceğin videolar sırayla durur, uygulama kapansa da kaybolmaz. Oynatma listesi linki her videoyu ayrı ekler; izlenecek / izlenenler, kendi sıran ya da önce kısa olanlar. Google ile giriş yaptıysan YouTube'daki *Daha sonra izle* ve *Beğendiklerim* listelerini tek tıkla çeker. |
| **Reels** | **Videodan Reels:** yapay zekâ konuşmayı okuyup en çok izlenecek anları puanlarıyla bulur (anahtarsız da çalışır); her klip dikey 9:16'ya çevrilir: yüz takibiyle akıllı kırpma, bulanık arka plan ya da ortadan kırpma, kelime kelime vurgulanan animasyonlu altyazı (Pop / Karaoke / Kutu / Sade), ilk 3 saniyede kanca başlığı, sessizlik kesme, dinamik zoom, ilerleme çubuğu, kullanıcı adı filigranı, konuşmada otomatik kısılan arka plan müziği, sosyal medya ses seviyesi (-14 LUFS). Her klip için kapak görseli ve hazır açıklama + etiket dosyası çıkar. **Fikirden Reels:** fikri yaz (ya da kendi metnini yapıştır), yapay zekâ senaryoyu yazsın, ücretsiz Edge sesiyle seslendirsin, sahnelere stok video (Pexels, ücretsiz anahtar), AI görsel ya da AI video (Higgsfield, ücretli) koysun. |
| **Görsel** | Fikirden **kapak (thumbnail)** ya da serbest **görsel** üretme: 16:9 YouTube, 9:16 Reels, 1:1, 4:5. Başlık görselin üstüne her zaman net ve kalın yazılır (Türkçe büyük harf doğru), yazı sonradan tek tıkla değiştirilebilir. Arka plan yapay zekâyla üretilebilir ya da analiz edilen videonun kapağı / kendi görselin kullanılabilir. Servisler ücretsizden ücretliye: Pollinations (anahtarsız), Cloudflare (günde ~95 ücretsiz), Gemini Nano Banana (ücretli), Higgsfield SOUL (ücretli). **Görseli düzenle:** kırp (hazır oranlar), döndür, çevir, eğikliği düzelt; pozlama, parlaklık, kontrast, açık tonlar/gölgeler, sıcaklık, doygunluk, canlılık, netlik, vinyet, gren ve otomatik iyileştirme; 12 filtre; yazı (15 yazı tipi, kontur, gölge, kutulu etiket, Türkçe büyük harf), dikdörtgen, daire, ok, çizgi, emoji, kalem/fosforlu; yüz, plaka ya da adresi pikselleştir veya bulanıklaştır; katmanlar, geri al/yinele, önce/sonra. JPG, PNG, WEBP veya AVIF olarak kaydedilir. |
| **Dönüştür** | Resim (WEBP, PNG, JPG, AVIF, GIF, BMP, TIFF, ICO, PDF; iPhone HEIC fotoğrafları da açılır), video (MP4, WEBM, MKV, MOV, GIF ya da yalnız ses) ve ses (MP3, M4A, WAV, FLAC, OGG, OPUS) dönüştürme. Hazır ayarlar (Instagram, WhatsApp, e-postaya sığdır…), kalite ve ölçü (Full HD, 2K, 4K, özel), döndürme, kesme, kare hızı, sesi kaldırma/dengeleme (-14 LUFS), mono, konum ve cihaz bilgilerini silme, resimleri tek PDF'te birleştirme, klasörün tamamını ekleme, önce/sonra karşılaştırma. Dosyaları pencereye sürükleyip bırakmak yeter. |
| **Telefondan kullan** | Bilgisayardaki TekTıkla'yı aynı Wi-Fi'daki telefonun tarayıcısından ya da Android uygulamasından kullan: QR kodu okut; indirme, Reels, dublaj, dönüştürme ve görsel düzenleme işlerini bilgisayar yapar, sonuç telefona iner. Yalnızca ev ağındaki ve bağlanma kodunu bilen cihazlar bağlanabilir; varsayılan olarak kapalıdır (kenar çubuğu › *Telefondan kullan*). |
| **Dublaj** | Videoyu başka dile çevirip seslendirir: Edge sesleri (ücretsiz, anahtarsız) ya da Gemini TTS (ücretsiz katman); her cümle zamanında okunur, orijinal ses arka planda kısılır, orijinal ses ikinci iz ve hedef dilde altyazı olarak saklanır. **ElevenLabs** ile konuşmacının kendi sesini koruyarak dublaj (ücretsiz planda aylık sınırlı ve filigranlı). |
| **AI Stüdyo** | **Video özeti:** altyazı dökümünü (yoksa, X/Twitter gibi, sesi bilgisayarda yazıya döküp) okutarak tek cümlelik özet, genel özet, önemli noktalar ve konu etiketleri. **Yorum özeti:** en çok beğenilen 300 yorumdan beğenilenler, eleştiriler, bildirilen sorunlar ve yorumlardaki çözümleri, sık sorulan sorular. **Video fikirleri:** bir linkten benzer (kopya olmayan) ya da yazdığın konudan başlık, açılış cümlesi ve akışıyla 6 içerik fikri. |
| **AI Altyazı** | İndirirken *Yapay zekâ ile altyazı* açılırsa videonun konuşması seçilen dile (Türkçe, İngilizce, Almanca… 15 dil) çevrilip altyazı olarak eklenir: gömülü, videoya yakılmış ya da ayrı .srt. Videoda altyazı yoksa konuşma bilgisayarda Whisper ile ücretsiz yazıya dökülür (ilk kullanımda ~190 MB model iner). |
| **Geçmiş** | Aranabilir indirme geçmişi. |
| **Ayarlar** | İsteğe bağlı hesap (e-posta, Google ya da GitHub; kayıt olmadan da her şey çalışır), arayüz dili (13 dil; ilk açılışta da sorulur), kayıt klasörü, temalar ve yazı tipleri, daraltılabilir kenar çubuğu (Ctrl+B), pano izleme, paralel indirme, hız sınırı, varsayılan biçimler, kapak/bilgi gömme, SponsorBlock, tarayıcı çerezleri, **Servisler** (Pollinations, Cloudflare, Pexels, ElevenLabs, Higgsfield anahtarları; hangisi ücretsiz hangisi ücretli etiketli), yt-dlp ve uygulama güncellemesi. |

## Yeni sürüm yayınlama

1. `tektikla/__init__.py` içindeki `APP_VERSION`'ı artırın (örn. `3.1.0`). Güncelleme kaynağı aynı dosyadaki `GITHUB_REPO`'dur.
2. **`kurulum_olustur.bat`** (ya da `build_release.py`) ile `Kurulum\TekTikla-Setup-3.1.0.exe` ve `Kurulum\TekTikla-3.1.0-win64.zip`'i üretin.
3. İsteğe bağlı: `build_apk.py` ile `Kurulum\TekTikla-Android.apk` (JDK 21 ve Android SDK gerekir; imza anahtarı depoda değil, `D:\Android\keys` içinde durur ve yedeklenmelidir).
4. Değişiklikleri commit'leyip gönderin; GitHub'da **Releases > Draft a new release** (ya da `gh release create v3.1.0 …`): etiket `v3.1.0`, üç dosyayı ekleyip yayınlayın. APK'nın adı tam olarak `TekTikla-Android.apk` olmalı; uygulamadaki QR kodu `releases/latest/download/TekTikla-Android.apk` adresini gösterir.

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
tektikla/web/            arayüz (index.html, style.css, app.js; studio.js, convert.js, watch.js, editor.js…)
tektikla/web/editor.js   görsel düzenleyici (WebGL renk ayarları, katmanlar, dışa aktarma)
tektikla/web/remote.js   telefon sitesi: pywebview köprüsünün yerine geçen HTTP katmanı
tektikla/engine.py       indirme motoru (yt-dlp + FFmpeg: kalite, MP3, altyazı gömme/yakma, kesit)
tektikla/ai.py           AI video özeti, yorum özeti, video fikirleri
tektikla/llm.py          yapay zekâ servisleri (Gemini, Claude Haiku)
tektikla/subtitles.py    zamanlı altyazı okuma, birleştirme, .srt, AI çeviri
tektikla/transcribe.py   konuşmayı yazıya dökme (whisper.cpp)
tektikla/tools.py        FFmpeg/Deno otomatik kurulum, yt-dlp güncelleme
tektikla/updater.py      GitHub Releases üzerinden uygulama güncellemesi
tektikla/config.py       ayarlar, geçmiş, DPAPI ile şifreli API anahtarı
tektikla/studio_api.py   Reels / Görsel / Dublaj sekmelerinin köprüsü, servis anahtarları, önizleme sunucusu
tektikla/reels.py        en iyi anları bulma, klip kurgusu, fikirden Reels
tektikla/captions.py     kelime kelime animasyonlu altyazı (ASS)
tektikla/words.py        kelime zamanlı döküm (YouTube altyazısı / Whisper), sessizlik kesme
tektikla/vision.py       akıllı kırpma için yüz takibi (OpenCV ilk kullanımda iner)
tektikla/imagegen.py     görsel üretme ve kapak tasarımı
tektikla/tts.py          seslendirme (Edge, Gemini TTS, ElevenLabs)
tektikla/dublaj.py       dublaj (çeviri + zamanlı seslendirme / ElevenLabs)
tektikla/services.py     dış servis istemcileri (Pollinations, Cloudflare, Pexels, Gemini, ElevenLabs, Higgsfield)
tektikla/media.py        FFmpeg yardımcıları ve kuyruk işlerinin temeli
tektikla/convert.py      dosya dönüştürücü (Pillow + FFmpeg)
tektikla/watchlist.py    izleme listesi
tektikla/account.py      isteğe bağlı hesap (Firebase Authentication)
tektikla/remote.py       telefondan kullanım: yerel ağ sunucusu, bağlanma kodu, dosya gönderme/alma
tektikla/qr.py           QR kodları (destek, telefon bağlantısı)
tektikla/i18n.py         arayüz dili; çeviriler tektikla/web/i18n/*.json
dev/i18n_extract.py      çevrilecek metinleri toplar; dev/i18n/*.txt -> dev/i18n_build.py -> JSON
installer/setup.py  kurulum/kaldırma programı
build_release.py    uygulama + kurulum exe'sini derler
build_apk.py        Android uygulamasını (android/) derler ve imzalar
server/welcome/     hoş geldin e-postası (Google Apps Script, 13 dil)
```

## Bilinmesi gerekenler

- DRM korumalı servisler (Netflix, Disney+, Spotify vb.) teknik olarak indirilemez.
- Giriş isteyen siteler (ör. Vimeo, yaş sınırlı videolar) için tarayıcıda giriş yapıp Ayarlar > Tarayıcı çerezleri'nden o tarayıcıyı seçin.
- AI özet ve altyazı çevirisi için Ayarlar > Yapay Zekâ'dan servis seçilir:
  - **Google Gemini (ücretsiz):** [aistudio.google.com/apikey](https://aistudio.google.com/apikey) adresinden kredi kartı olmadan anahtar alınır. Ücretsiz katmanda Google gönderilen metni ürünlerini geliştirmek için kullanabilir.
  - **Claude Haiku 5.5:** ücretli ama çok ucuz; ücret anahtar sahibinin Anthropic hesabından düşer.
- Konuşmayı yazıya dökme (Whisper) tamamen bilgisayarda çalışır; ses hiçbir yere gönderilmez.
- Stüdyo servisleri (Ayarlar > Servisler), ücretsizden ücretliye:
  - **Pollinations:** anahtarsız ücretsiz görsel (yavaş, köşede küçük logo); ücretsiz hesapla logosuz.
  - **Cloudflare Workers AI:** ücretsiz hesapla günde ~95 FLUX görseli.
  - **Pexels:** ücretsiz anahtarla dikey stok videolar (Fikirden Reels).
  - **Edge sesleri:** tamamen ücretsiz, anahtarsız seslendirme (Microsoft Edge'in çevrim içi ses servisi).
  - **Gemini:** TTS ücretsiz katmanda; görsel üretimi (Nano Banana) ücretli.
  - **ElevenLabs:** ücretsiz planda ayda ~10.000 karakter / ~5 dk filigranlı dublaj, ticari kullanım yok; sonrası ücretli.
  - **Higgsfield:** yalnızca ücretli (kullandıkça öde) AI görsel ve video.
- Akıllı kırpma (yüz takibi) ilk kullanımda OpenCV'yi (~44 MB) PyPI'den indirir.
- Telefondan kullanım yalnızca yerel ağda çalışır, internet üzerinden erişilemez. Telefon bağlanamıyorsa: Windows izin sorarsa "Özel ağlar"a izin verin; Wi-Fi ağınız "Ortak" görünüyorsa Windows Ayarlar › Ağ'dan "Özel" yapın.
- Görsel düzenleyici her şeyi bilgisayarda yapar; görseller hiçbir servise gönderilmez.
- Telif hakkı olan içerikleri yalnızca kişisel kullanım için ve sitenin kurallarına uygun şekilde indirin.

## Lisans
Bu proje MIT Lisansı altında lisanslanmıştır. Ayrıntılar için `LICENSE` dosyasına bakın.

Free code signing provided by SignPath.io, certificate by SignPath Foundation.
