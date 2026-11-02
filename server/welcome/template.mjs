// TekTıkla hoş geldin e-postası: yeni üyeye bir kez gönderilir (gönderen: worker.mjs).
// E-posta istemcileri (Gmail, Outlook, iOS Mail) için tablo tabanlı, satır içi stilli, açık zeminli tasarım.
// Kullanım: welcomeEmail({ name, lang }) -> { subject, html, text }

const TEXT = {
  tr: {
    subject: "TekTıkla'ya hoş geldin, {name}!",
    preheader: "Hesabın hazır. İlk adımların için kısa bir rehber ve birkaç ipucu.",
    tagline: "İndir · Üret · Kurgula",
    hello: "Hoş geldin, {name}!",
    intro: "TekTıkla hesabın hazır. Video ve görsel indirmekten yapay zekâyla Reels kurgulamaya, dublajdan dosya dönüştürmeye kadar her şey artık tek bir yerde.",
    cta: "Son sürümü indir",
    stepsTitle: "İlk 3 adım",
    steps: [
      ["Linki yapıştır", "Herhangi bir video linkini kopyala; TekTıkla kendisi algılar. Hızlı İndir'e bas, gerisini o halleder."],
      ["İlk Reels'ini yap", "Reels sekmesinde uzun bir videonun en çok izlenecek anlarını yapay zekâ bulur; altyazısıyla, kurgusuyla hazırlar."],
      ["Listeni kur", "Sonra izleyeceklerini izleme listesine ekle. Google ile giriş yaptıysan YouTube \"Daha sonra izle\" listeni de çekebilirsin."],
    ],
    featuresTitle: "Seni neler bekliyor",
    features: [
      ["⬇", "İndir", "Yüzlerce siteden video, müzik ve altyazı"],
      ["🎬", "Reels", "Uzun videodan özenli dikey klipler"],
      ["🖼", "Görsel", "Kapak ve görsel üretimi"],
      ["🎙", "Dublaj", "Videoyu başka dile seslendir"],
      ["🔄", "Dönüştür", "PNG→WEBP, 4K, MP4→MP3 ve dahası"],
      ["🔖", "İzleme listesi", "Sonra izleyeceklerin, her zaman sırada"],
    ],
    tipTitle: "Biliyor muydun?",
    tip: "Ctrl+B ile kenar çubuğunu gizleyip tam ekran çalışabilirsin; fareyi kenara getirince geri gelir.",
    support: "TekTıkla ücretsiz ve reklamsız. Beğendiysen bana bir kahve ısmarlayarak ya da GitHub'da takip edip yıldız vererek destek olabilirsin.",
    coffeeCta: "☕ Bana bir kahve ısmarla",
    supportCta: "GitHub'da destek ol",
    footer: "Bu e-postayı TekTıkla hesabı açtığın için aldın. Hesabını istediğin zaman uygulamada Ayarlar > Hesap'tan silebilirsin.",
  },
  en: {
    subject: "Welcome to TekTıkla, {name}!",
    preheader: "Your account is ready. A short guide for your first steps and a few tips.",
    tagline: "Download · Create · Edit",
    hello: "Welcome, {name}!",
    intro: "Your TekTıkla account is ready. From downloading videos and images to editing Reels with AI, dubbing and converting files — it's all in one place now.",
    cta: "Download the latest version",
    stepsTitle: "Your first 3 steps",
    steps: [
      ["Paste a link", "Copy any video link and TekTıkla detects it. Press Quick Download and it takes care of the rest."],
      ["Make your first Reels", "In the Reels tab, AI finds the most watchable moments of a long video and edits them with captions."],
      ["Build your list", "Add what you'll watch later to your watchlist. Signed in with Google? Import your YouTube \"Watch later\" list too."],
    ],
    featuresTitle: "What's waiting for you",
    features: [
      ["⬇", "Download", "Video, music and subtitles from hundreds of sites"],
      ["🎬", "Reels", "Polished vertical clips from long videos"],
      ["🖼", "Image", "Thumbnail and image generation"],
      ["🎙", "Dubbing", "Voice your video in another language"],
      ["🔄", "Convert", "PNG→WEBP, 4K, MP4→MP3 and more"],
      ["🔖", "Watchlist", "What you'll watch later, always in order"],
    ],
    tipTitle: "Did you know?",
    tip: "Press Ctrl+B to hide the sidebar and work full screen; move the mouse to the edge to bring it back.",
    support: "TekTıkla is free and ad-free. If you like it, you can support it by buying me a coffee or by following and starring it on GitHub.",
    coffeeCta: "☕ Buy me a coffee",
    supportCta: "Support on GitHub",
    footer: "You received this email because you created a TekTıkla account. You can delete your account any time in the app under Settings > Account.",
  },
  es: {
    subject: "¡Bienvenido a TekTıkla, {name}!",
    preheader: "Tu cuenta está lista. Una guía rápida para empezar y algunos consejos.",
    tagline: "Descarga · Crea · Edita",
    hello: "¡Bienvenido, {name}!",
    intro: "Tu cuenta de TekTıkla está lista. Descargar vídeos e imágenes, editar Reels con IA, doblar y convertir archivos: ahora todo está en un mismo sitio.",
    cta: "Descargar la última versión",
    stepsTitle: "Tus 3 primeros pasos",
    steps: [
      ["Pega un enlace", "Copia cualquier enlace de vídeo y TekTıkla lo detecta. Pulsa Descarga rápida y se encarga del resto."],
      ["Haz tu primer Reels", "En la pestaña Reels, la IA encuentra los mejores momentos de un vídeo largo y los edita con subtítulos."],
      ["Crea tu lista", "Añade a tu lista para ver lo que verás más tarde. ¿Entraste con Google? Importa también tu lista «Ver más tarde» de YouTube."],
    ],
    featuresTitle: "Lo que te espera",
    features: [
      ["⬇", "Descargar", "Vídeo, música y subtítulos de cientos de sitios"],
      ["🎬", "Reels", "Clips verticales cuidados a partir de vídeos largos"],
      ["🖼", "Imagen", "Creación de miniaturas e imágenes"],
      ["🎙", "Doblaje", "Pon voz a tu vídeo en otro idioma"],
      ["🔄", "Convertir", "PNG→WEBP, 4K, MP4→MP3 y más"],
      ["🔖", "Lista para ver", "Lo que verás más tarde, siempre en orden"],
    ],
    tipTitle: "¿Sabías que…?",
    tip: "Con Ctrl+B ocultas la barra lateral y trabajas a pantalla completa; acerca el ratón al borde para que vuelva.",
    support: "TekTıkla es gratis y sin anuncios. Si te gusta, puedes apoyarlo invitándome a un café o siguiéndolo y dándole una estrella en GitHub.",
    coffeeCta: "☕ Invítame a un café",
    supportCta: "Apoyar en GitHub",
    footer: "Recibes este correo porque creaste una cuenta de TekTıkla. Puedes eliminar tu cuenta cuando quieras en la app, en Ajustes > Cuenta.",
  },
  pt: {
    subject: "Boas-vindas ao TekTıkla, {name}!",
    preheader: "Sua conta está pronta. Um guia rápido para começar e algumas dicas.",
    tagline: "Baixe · Crie · Edite",
    hello: "Boas-vindas, {name}!",
    intro: "Sua conta do TekTıkla está pronta. Baixar vídeos e imagens, editar Reels com IA, dublar e converter arquivos: agora está tudo em um só lugar.",
    cta: "Baixar a versão mais recente",
    stepsTitle: "Seus 3 primeiros passos",
    steps: [
      ["Cole um link", "Copie qualquer link de vídeo e o TekTıkla detecta sozinho. Toque em Download rápido e ele cuida do resto."],
      ["Faça seu primeiro Reels", "Na aba Reels, a IA encontra os melhores momentos de um vídeo longo e edita com legendas."],
      ["Monte sua lista", "Adicione à lista para assistir o que você vai ver depois. Entrou com o Google? Importe também sua lista “Assistir mais tarde” do YouTube."],
    ],
    featuresTitle: "O que espera por você",
    features: [
      ["⬇", "Baixar", "Vídeo, música e legendas de centenas de sites"],
      ["🎬", "Reels", "Clipes verticais caprichados a partir de vídeos longos"],
      ["🖼", "Imagem", "Criação de capas e imagens"],
      ["🎙", "Dublagem", "Dê voz ao seu vídeo em outro idioma"],
      ["🔄", "Converter", "PNG→WEBP, 4K, MP4→MP3 e mais"],
      ["🔖", "Lista para assistir", "O que você vai ver depois, sempre em ordem"],
    ],
    tipTitle: "Você sabia?",
    tip: "Com Ctrl+B você esconde a barra lateral e trabalha em tela cheia; leve o mouse até a borda para ela voltar.",
    support: "O TekTıkla é gratuito e sem anúncios. Se gostou, você pode apoiar me pagando um café ou seguindo e dando uma estrela no GitHub.",
    coffeeCta: "☕ Me pague um café",
    supportCta: "Apoiar no GitHub",
    footer: "Você recebeu este e-mail porque criou uma conta no TekTıkla. Você pode excluir sua conta quando quiser no app, em Configurações > Conta.",
  },
  fr: {
    subject: "Bienvenue sur TekTıkla, {name} !",
    preheader: "Ton compte est prêt. Un petit guide pour bien démarrer et quelques astuces.",
    tagline: "Télécharge · Crée · Monte",
    hello: "Bienvenue, {name} !",
    intro: "Ton compte TekTıkla est prêt. Télécharger des vidéos et des images, monter des Reels avec l'IA, doubler, convertir des fichiers : tout est désormais au même endroit.",
    cta: "Télécharger la dernière version",
    stepsTitle: "Tes 3 premières étapes",
    steps: [
      ["Colle un lien", "Copie n'importe quel lien vidéo, TekTıkla le détecte. Appuie sur Téléchargement rapide et il s'occupe du reste."],
      ["Crée ton premier Reels", "Dans l'onglet Reels, l'IA trouve les meilleurs moments d'une longue vidéo et les monte avec des sous-titres."],
      ["Construis ta liste", "Ajoute à ta liste à regarder ce que tu verras plus tard. Connecté avec Google ? Importe aussi ta liste YouTube « À regarder plus tard »."],
    ],
    featuresTitle: "Ce qui t'attend",
    features: [
      ["⬇", "Télécharger", "Vidéos, musique et sous-titres de centaines de sites"],
      ["🎬", "Reels", "Des clips verticaux soignés à partir de longues vidéos"],
      ["🖼", "Image", "Création de miniatures et d'images"],
      ["🎙", "Doublage", "Fais parler ta vidéo dans une autre langue"],
      ["🔄", "Convertir", "PNG→WEBP, 4K, MP4→MP3 et plus"],
      ["🔖", "Liste à regarder", "Ce que tu regarderas plus tard, toujours dans l'ordre"],
    ],
    tipTitle: "Le savais-tu ?",
    tip: "Ctrl+B masque la barre latérale pour travailler en plein écran ; approche la souris du bord pour la faire revenir.",
    support: "TekTıkla est gratuit et sans publicité. Si tu l'aimes, tu peux le soutenir en m'offrant un café ou en le suivant et en lui donnant une étoile sur GitHub.",
    coffeeCta: "☕ Offre-moi un café",
    supportCta: "Soutenir sur GitHub",
    footer: "Tu reçois cet e-mail parce que tu as créé un compte TekTıkla. Tu peux supprimer ton compte à tout moment dans l'appli, sous Paramètres > Compte.",
  },
  de: {
    subject: "Willkommen bei TekTıkla, {name}!",
    preheader: "Dein Konto ist bereit. Eine kurze Anleitung für den Start und ein paar Tipps.",
    tagline: "Laden · Erstellen · Schneiden",
    hello: "Willkommen, {name}!",
    intro: "Dein TekTıkla-Konto ist bereit. Videos und Bilder laden, Reels mit KI schneiden, synchronisieren und Dateien konvertieren – jetzt alles an einem Ort.",
    cta: "Neueste Version herunterladen",
    stepsTitle: "Deine ersten 3 Schritte",
    steps: [
      ["Link einfügen", "Kopiere einen beliebigen Videolink – TekTıkla erkennt ihn. Drück auf Schnell-Download, um den Rest kümmert es sich."],
      ["Erstes Reels erstellen", "Im Tab Reels findet die KI die besten Momente eines langen Videos und schneidet sie mit Untertiteln."],
      ["Liste anlegen", "Setz alles, was du später ansehen willst, auf deine Merkliste. Mit Google angemeldet? Importiere auch deine YouTube-Liste „Später ansehen“."],
    ],
    featuresTitle: "Das erwartet dich",
    features: [
      ["⬇", "Laden", "Videos, Musik und Untertitel von Hunderten Websites"],
      ["🎬", "Reels", "Sorgfältige Hochkant-Clips aus langen Videos"],
      ["🖼", "Bild", "Thumbnails und Bilder erstellen"],
      ["🎙", "Synchronisation", "Vertone dein Video in einer anderen Sprache"],
      ["🔄", "Konvertieren", "PNG→WEBP, 4K, MP4→MP3 und mehr"],
      ["🔖", "Merkliste", "Was du später ansiehst, immer in Reihenfolge"],
    ],
    tipTitle: "Schon gewusst?",
    tip: "Mit Strg+B blendest du die Seitenleiste aus und arbeitest im Vollbild; führ die Maus an den Rand, dann kommt sie zurück.",
    support: "TekTıkla ist kostenlos und werbefrei. Wenn es dir gefällt, unterstütze es, indem du mir einen Kaffee spendierst oder ihm auf GitHub folgst und einen Stern gibst.",
    coffeeCta: "☕ Spendier mir einen Kaffee",
    supportCta: "Auf GitHub unterstützen",
    footer: "Du bekommst diese E-Mail, weil du ein TekTıkla-Konto erstellt hast. Dein Konto kannst du jederzeit in der App unter Einstellungen > Konto löschen.",
  },
  ru: {
    subject: "Добро пожаловать в TekTıkla, {name}!",
    preheader: "Твой аккаунт готов. Короткая инструкция для начала и пара советов.",
    tagline: "Скачивай · Создавай · Монтируй",
    hello: "Добро пожаловать, {name}!",
    intro: "Твой аккаунт TekTıkla готов. Скачивание видео и изображений, монтаж Reels с ИИ, озвучка и конвертация файлов — теперь всё в одном месте.",
    cta: "Скачать последнюю версию",
    stepsTitle: "Первые 3 шага",
    steps: [
      ["Вставь ссылку", "Скопируй любую ссылку на видео — TekTıkla её заметит. Нажми «Быстрая загрузка», остальное он сделает сам."],
      ["Сделай первый Reels", "На вкладке Reels ИИ находит лучшие моменты длинного видео и монтирует их с субтитрами."],
      ["Собери свой список", "Добавляй в список просмотра то, что посмотришь позже. Вошёл через Google? Импортируй и свой список YouTube «Смотреть позже»."],
    ],
    featuresTitle: "Что тебя ждёт",
    features: [
      ["⬇", "Загрузка", "Видео, музыка и субтитры с сотен сайтов"],
      ["🎬", "Reels", "Аккуратные вертикальные клипы из длинных видео"],
      ["🖼", "Изображения", "Создание обложек и картинок"],
      ["🎙", "Озвучка", "Озвучь видео на другом языке"],
      ["🔄", "Конвертер", "PNG→WEBP, 4K, MP4→MP3 и многое другое"],
      ["🔖", "Список просмотра", "То, что посмотришь позже, всегда по порядку"],
    ],
    tipTitle: "А ты знал?",
    tip: "Ctrl+B скрывает боковую панель для работы во весь экран; подведи мышь к краю, и она вернётся.",
    support: "TekTıkla бесплатен и без рекламы. Если он тебе нравится, поддержи проект: угости меня кофе или подпишись на GitHub и поставь звезду.",
    coffeeCta: "☕ Угости меня кофе",
    supportCta: "Поддержать на GitHub",
    footer: "Ты получил это письмо, потому что создал аккаунт TekTıkla. Удалить аккаунт можно в любой момент в приложении: «Настройки > Аккаунт».",
  },
  ar: {
    subject: "مرحبًا بك في TekTıkla يا {name}!",
    preheader: "حسابك جاهز. دليل قصير لخطواتك الأولى وبعض النصائح.",
    tagline: "نزّل · أنشئ · حرّر",
    hello: "مرحبًا يا {name}!",
    intro: "حسابك في TekTıkla جاهز. تنزيل الفيديوهات والصور، وتحرير Reels بالذكاء الاصطناعي، والدبلجة وتحويل الملفات — كل ذلك الآن في مكان واحد.",
    cta: "نزّل أحدث إصدار",
    stepsTitle: "أول 3 خطوات",
    steps: [
      ["الصق رابطًا", "انسخ أي رابط فيديو وسيكتشفه TekTıkla. اضغط «تنزيل سريع» وسيتولى الباقي."],
      ["اصنع أول Reels", "في تبويب Reels يجد الذكاء الاصطناعي أفضل لحظات الفيديو الطويل ويحرّرها مع النص."],
      ["أنشئ قائمتك", "أضف إلى قائمة المشاهدة ما ستشاهده لاحقًا. سجّلت الدخول باستخدام Google؟ استورد أيضًا قائمة «المشاهدة لاحقًا» من YouTube."],
    ],
    featuresTitle: "ما ينتظرك",
    features: [
      ["⬇", "تنزيل", "فيديو وموسيقى وترجمات من مئات المواقع"],
      ["🎬", "Reels", "مقاطع عمودية متقنة من الفيديوهات الطويلة"],
      ["🖼", "صورة", "إنشاء الصور المصغّرة والصور"],
      ["🎙", "دبلجة", "اجعل فيديوك يتحدث بلغة أخرى"],
      ["🔄", "تحويل", "PNG→WEBP و4K وMP4→MP3 والمزيد"],
      ["🔖", "قائمة المشاهدة", "ما ستشاهده لاحقًا، مرتبًا دائمًا"],
    ],
    tipTitle: "هل تعلم؟",
    tip: "يخفي Ctrl+B الشريط الجانبي لتعمل بملء الشاشة؛ قرّب الفأرة من الحافة ليعود.",
    support: "TekTıkla مجاني وبلا إعلانات. إن أعجبك فيمكنك دعمه بأن تشتري لي قهوة أو تتابعه وتمنحه نجمة على GitHub.",
    coffeeCta: "☕ اشترِ لي قهوة",
    supportCta: "ادعم على GitHub",
    footer: "وصلتك هذه الرسالة لأنك أنشأت حسابًا في TekTıkla. يمكنك حذف حسابك في أي وقت من التطبيق: الإعدادات > الحساب.",
  },
  hi: {
    subject: "TekTıkla में आपका स्वागत है, {name}!",
    preheader: "आपका खाता तैयार है। शुरुआत के लिए छोटी गाइड और कुछ टिप्स।",
    tagline: "डाउनलोड करें · बनाएँ · एडिट करें",
    hello: "स्वागत है, {name}!",
    intro: "आपका TekTıkla खाता तैयार है। वीडियो और इमेज डाउनलोड करना, AI से Reels एडिट करना, डबिंग और फ़ाइलें कन्वर्ट करना — अब सब एक ही जगह।",
    cta: "नया वर्शन डाउनलोड करें",
    stepsTitle: "आपके पहले 3 कदम",
    steps: [
      ["लिंक चिपकाएँ", "कोई भी वीडियो लिंक कॉपी करें, TekTıkla उसे पहचान लेता है। तेज़ डाउनलोड दबाएँ, बाकी काम वह कर देगा।"],
      ["पहला Reels बनाएँ", "Reels टैब में AI लंबे वीडियो के सबसे अच्छे पल ढूँढकर उन्हें सबटाइटल के साथ एडिट करता है।"],
      ["अपनी सूची बनाएँ", "जो बाद में देखना है, उसे वॉचलिस्ट में जोड़ें। Google से साइन इन किया है? YouTube की \"बाद में देखें\" सूची भी ले आएँ।"],
    ],
    featuresTitle: "आपके लिए क्या है",
    features: [
      ["⬇", "डाउनलोड", "सैकड़ों साइटों से वीडियो, संगीत और सबटाइटल"],
      ["🎬", "Reels", "लंबे वीडियो से सधी हुई वर्टिकल क्लिप"],
      ["🖼", "इमेज", "थंबनेल और इमेज बनाना"],
      ["🎙", "डबिंग", "अपने वीडियो को दूसरी भाषा में आवाज़ दें"],
      ["🔄", "कन्वर्ट", "PNG→WEBP, 4K, MP4→MP3 और भी"],
      ["🔖", "वॉचलिस्ट", "बाद में देखने वाले वीडियो, हमेशा क्रम से"],
    ],
    tipTitle: "क्या आप जानते हैं?",
    tip: "Ctrl+B से साइडबार छिपाकर पूरी स्क्रीन पर काम करें; माउस को किनारे ले जाते ही वह लौट आता है।",
    support: "TekTıkla मुफ़्त है और इसमें विज्ञापन नहीं हैं। पसंद आए तो मुझे एक कॉफ़ी पिलाकर या GitHub पर फ़ॉलो करके और स्टार देकर सहयोग करें।",
    coffeeCta: "☕ मुझे कॉफ़ी पिलाएँ",
    supportCta: "GitHub पर सहयोग करें",
    footer: "आपको यह ईमेल इसलिए मिला क्योंकि आपने TekTıkla खाता बनाया है। आप ऐप में सेटिंग्स > खाता से कभी भी अपना खाता हटा सकते हैं।",
  },
  id: {
    subject: "Selamat datang di TekTıkla, {name}!",
    preheader: "Akunmu sudah siap. Panduan singkat untuk memulai dan beberapa tips.",
    tagline: "Unduh · Buat · Sunting",
    hello: "Selamat datang, {name}!",
    intro: "Akun TekTıkla-mu sudah siap. Mengunduh video dan gambar, menyunting Reels dengan AI, sulih suara, hingga konversi file — sekarang semuanya di satu tempat.",
    cta: "Unduh versi terbaru",
    stepsTitle: "3 langkah pertamamu",
    steps: [
      ["Tempel tautan", "Salin tautan video apa saja, TekTıkla akan mendeteksinya. Tekan Unduh cepat dan sisanya beres."],
      ["Buat Reels pertamamu", "Di tab Reels, AI menemukan momen terbaik dari video panjang dan menyuntingnya lengkap dengan teks."],
      ["Susun daftarmu", "Tambahkan yang ingin kamu tonton nanti ke daftar tontonan. Masuk dengan Google? Impor juga daftar \"Tonton Nanti\" YouTube-mu."],
    ],
    featuresTitle: "Yang menantimu",
    features: [
      ["⬇", "Unduh", "Video, musik, dan subtitle dari ratusan situs"],
      ["🎬", "Reels", "Klip vertikal rapi dari video panjang"],
      ["🖼", "Gambar", "Membuat thumbnail dan gambar"],
      ["🎙", "Sulih suara", "Suarakan videomu dalam bahasa lain"],
      ["🔄", "Konversi", "PNG→WEBP, 4K, MP4→MP3, dan lainnya"],
      ["🔖", "Daftar tontonan", "Tontonan untuk nanti, selalu berurutan"],
    ],
    tipTitle: "Tahukah kamu?",
    tip: "Tekan Ctrl+B untuk menyembunyikan bilah samping dan bekerja layar penuh; bawa mouse ke tepi untuk memunculkannya lagi.",
    support: "TekTıkla gratis dan tanpa iklan. Kalau suka, kamu bisa mendukung dengan mentraktirku kopi atau mengikutinya dan memberi bintang di GitHub.",
    coffeeCta: "☕ Traktir aku kopi",
    supportCta: "Dukung di GitHub",
    footer: "Kamu menerima email ini karena membuat akun TekTıkla. Kamu bisa menghapus akunmu kapan saja di aplikasi lewat Pengaturan > Akun.",
  },
  zh: {
    subject: "欢迎来到 TekTıkla，{name}！",
    preheader: "你的账号已就绪。这是一份上手指南和几个小技巧。",
    tagline: "下载 · 创作 · 剪辑",
    hello: "欢迎，{name}！",
    intro: "你的 TekTıkla 账号已就绪。下载视频和图片、用 AI 剪辑 Reels、配音和转换文件——现在都在一个地方完成。",
    cta: "下载最新版本",
    stepsTitle: "最初的 3 步",
    steps: [
      ["粘贴链接", "复制任意视频链接，TekTıkla 会自动识别。点击“快速下载”，其余的交给它。"],
      ["制作第一个 Reels", "在 Reels 标签页中，AI 会找出长视频里最精彩的片段，并配上字幕剪辑好。"],
      ["建立你的列表", "把想稍后观看的内容加入待看列表。用 Google 登录了？还可以导入 YouTube 的“稍后观看”列表。"],
    ],
    featuresTitle: "等你体验的功能",
    features: [
      ["⬇", "下载", "来自数百个网站的视频、音乐和字幕"],
      ["🎬", "Reels", "把长视频剪成精致的竖屏短片"],
      ["🖼", "图片", "生成封面和图片"],
      ["🎙", "配音", "用另一种语言为视频配音"],
      ["🔄", "转换", "PNG→WEBP、4K、MP4→MP3 等"],
      ["🔖", "待看列表", "稍后要看的内容，始终井然有序"],
    ],
    tipTitle: "你知道吗？",
    tip: "按 Ctrl+B 可隐藏侧边栏全屏工作；把鼠标移到边缘，它就会回来。",
    support: "TekTıkla 免费且无广告。如果喜欢，可以请我喝杯咖啡，或在 GitHub 关注并点个星来支持。",
    coffeeCta: "☕ 请我喝杯咖啡",
    supportCta: "在 GitHub 支持",
    footer: "你收到这封邮件，是因为你创建了 TekTıkla 账号。你可以随时在应用的 设置 > 账号 中删除账号。",
  },
  ja: {
    subject: "TekTıkla へようこそ、{name} さん！",
    preheader: "アカウントの準備ができました。はじめの手順と、ちょっとしたコツをご紹介します。",
    tagline: "ダウンロード · 作成 · 編集",
    hello: "ようこそ、{name} さん！",
    intro: "TekTıkla のアカウントの準備ができました。動画や画像のダウンロード、AI による Reels 編集、吹き替え、ファイル変換まで、すべてがひとつの場所にそろっています。",
    cta: "最新版をダウンロード",
    stepsTitle: "はじめの 3 ステップ",
    steps: [
      ["リンクを貼り付ける", "動画のリンクをコピーするだけで TekTıkla が検出します。クイックダウンロードを押せば、あとはおまかせです。"],
      ["初めての Reels を作る", "Reels タブでは、AI が長い動画の見どころを探し、字幕付きで編集します。"],
      ["リストを作る", "後で見たいものをウォッチリストに追加しましょう。Google でログインしているなら、YouTube の「後で見る」リストも取り込めます。"],
    ],
    featuresTitle: "使える機能",
    features: [
      ["⬇", "ダウンロード", "数百のサイトから動画・音楽・字幕を"],
      ["🎬", "Reels", "長い動画から丁寧な縦型クリップを"],
      ["🖼", "画像", "サムネイルや画像の作成"],
      ["🎙", "吹き替え", "動画を別の言語でナレーション"],
      ["🔄", "変換", "PNG→WEBP、4K、MP4→MP3 など"],
      ["🔖", "ウォッチリスト", "後で見るものを、いつも順番どおりに"],
    ],
    tipTitle: "ご存じですか？",
    tip: "Ctrl+B でサイドバーを隠して全画面で作業できます。マウスを端に寄せると戻ります。",
    support: "TekTıkla は無料で広告もありません。気に入っていただけたら、コーヒーをおごるか、GitHub でフォローしてスターを付けて応援してください。",
    coffeeCta: "☕ コーヒーをおごる",
    supportCta: "GitHub で応援する",
    footer: "このメールは TekTıkla のアカウントを作成されたためお送りしています。アカウントはアプリの 設定 > アカウント からいつでも削除できます。",
  },
  ko: {
    subject: "TekTıkla에 오신 것을 환영해요, {name}님!",
    preheader: "계정이 준비됐어요. 처음 시작을 위한 짧은 안내와 몇 가지 팁을 드려요.",
    tagline: "다운로드 · 제작 · 편집",
    hello: "환영해요, {name}님!",
    intro: "TekTıkla 계정이 준비됐어요. 동영상과 이미지 다운로드, AI로 Reels 편집, 더빙, 파일 변환까지 이제 한곳에서 다 할 수 있어요.",
    cta: "최신 버전 다운로드",
    stepsTitle: "첫 3단계",
    steps: [
      ["링크 붙여넣기", "아무 동영상 링크나 복사하면 TekTıkla가 알아서 감지해요. 빠른 다운로드를 누르면 나머지는 알아서 해요."],
      ["첫 Reels 만들기", "Reels 탭에서 AI가 긴 동영상의 가장 좋은 순간을 찾아 자막과 함께 편집해요."],
      ["목록 만들기", "나중에 볼 것을 시청 목록에 추가하세요. Google로 로그인했다면 YouTube '나중에 볼 동영상' 목록도 가져올 수 있어요."],
    ],
    featuresTitle: "이런 기능이 기다려요",
    features: [
      ["⬇", "다운로드", "수백 개 사이트의 동영상, 음악, 자막"],
      ["🎬", "Reels", "긴 동영상으로 만드는 깔끔한 세로 클립"],
      ["🖼", "이미지", "썸네일과 이미지 만들기"],
      ["🎙", "더빙", "동영상을 다른 언어로 더빙"],
      ["🔄", "변환", "PNG→WEBP, 4K, MP4→MP3 등"],
      ["🔖", "시청 목록", "나중에 볼 동영상을 언제나 순서대로"],
    ],
    tipTitle: "알고 계셨나요?",
    tip: "Ctrl+B로 사이드바를 숨기고 전체 화면으로 작업할 수 있어요. 마우스를 가장자리로 가져가면 다시 나타나요.",
    support: "TekTıkla는 무료이고 광고가 없어요. 마음에 드셨다면 커피 한 잔을 사 주시거나 GitHub에서 팔로우하고 별을 눌러 응원해 주세요.",
    coffeeCta: "☕ 커피 한 잔 사 주기",
    supportCta: "GitHub에서 후원하기",
    footer: "TekTıkla 계정을 만드셔서 이 이메일을 보내드렸어요. 계정은 앱의 설정 > 계정에서 언제든 삭제할 수 있어요.",
  },
};

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
// ad yoksa ", {name}" kısmı (dile göre "يا", "さん", "님" ile) tümden düşer: "Hoş geldin!" (Fransızcadaki " !" boşluğu kalır)
const fill = (s, name) => (name ? s.replace("{name}", name) : s.replace(/[,،、，]?\s*(?:يا\s*)?\{name\}(?:\s*(?:さん|님))?/, ""));

export function welcomeEmail({ name, lang = "tr", downloadUrl = "https://github.com/BurakCNKaya/TekTikla/releases/latest",
                               supportUrl = "https://github.com/BurakCNKaya", coffeeUrl = "https://buymeacoffee.com/vesperky" }) {
  const t = TEXT[lang] || TEXT.en;
  const rtl = lang === "ar" && t === TEXT.ar;  // Arapça sağdan sola; Gmail <html dir>'i sildiği için tabloya da yazılır
  const dir = rtl ? "rtl" : "ltr", start = rtl ? "right" : "left";
  const who = esc((name || "").trim().split(/\s+/)[0] || "");
  const font = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif";
  const steps = t.steps.map(([title, body], i) => `
    <tr><td style="padding:0 0 14px 0;">
      <table role="presentation" cellpadding="0" cellspacing="0" width="100%"><tr>
        <td width="40" valign="top"><div style="width:30px;height:30px;border-radius:15px;background:#111;color:#fff;
          font:700 14px/30px ${font};text-align:center;">${i + 1}</div></td>
        <td valign="top" style="font:15px/1.5 ${font};color:#3f3f46;"><b style="color:#111;">${esc(title)}</b><br>${esc(body)}</td>
      </tr></table>
    </td></tr>`).join("");
  const cells = t.features.map(([icon, title, body]) => `
    <td width="50%" valign="top" style="padding:6px;">
      <div style="border:1px solid #e4e4e7;border-radius:14px;padding:14px 14px 12px;background:#fafafa;">
        <div style="font-size:22px;line-height:1;">${icon}</div>
        <div style="font:700 15px ${font};color:#111;margin-top:8px;">${esc(title)}</div>
        <div style="font:13px/1.45 ${font};color:#52525b;margin-top:3px;">${esc(body)}</div>
      </div>
    </td>`);
  const grid = [0, 2, 4].map((i) => `<tr>${cells[i]}${cells[i + 1]}</tr>`).join("");
  const button = (href, label, dark = true) => `
    <table role="presentation" cellpadding="0" cellspacing="0"><tr><td style="border-radius:12px;background:${dark ? "#111" : "#fff"};
      ${dark ? "" : "border:1px solid #d4d4d8;"}"><a href="${esc(href)}" style="display:inline-block;padding:13px 22px;font:700 15px ${font};
      color:${dark ? "#fff" : "#111"};text-decoration:none;border-radius:12px;">${esc(label)}</a></td></tr></table>`;
  // Buy Me a Coffee: markanın sarısı; GitHub düğmesiyle yan yana (dar ekranda alt alta)
  const coffee = `
    <table role="presentation" cellpadding="0" cellspacing="0"><tr><td style="border-radius:12px;background:#FFDD00;">
      <a href="${esc(coffeeUrl)}" style="display:inline-block;padding:13px 22px;font:700 15px ${font};color:#0D0C22;
      text-decoration:none;border-radius:12px;">${esc(t.coffeeCta)}</a></td></tr></table>`;
  const html = `<!doctype html>
<html lang="${esc(lang)}" dir="${dir}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only"><title>${esc(fill(t.subject, who))}</title></head>
<body style="margin:0;padding:0;background:#f4f4f5;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">${esc(t.preheader)}</div>
<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="background:#f4f4f5;"><tr><td align="center" style="padding:28px 12px;">
  <table role="presentation" cellpadding="0" cellspacing="0" width="100%" dir="${dir}" style="max-width:600px;text-align:${start};">
    <tr><td align="center" style="padding:6px 0 20px;">
      <table role="presentation" cellpadding="0" cellspacing="0"><tr>
        <td style="width:44px;height:44px;border-radius:13px;background:#111;color:#fff;font:800 18px ${font};text-align:center;">TT</td>
        <td style="padding-${start}:12px;font:800 24px ${font};color:#111;letter-spacing:-.5px;">TekTıkla
          <div style="font:600 12px ${font};color:#71717a;letter-spacing:.3px;">${esc(t.tagline)}</div></td>
      </tr></table>
    </td></tr>
    <tr><td style="background:#fff;border-radius:22px;border:1px solid #e4e4e7;padding:34px 30px 28px;">
      <h1 style="margin:0 0 10px;font:800 28px/1.2 ${font};color:#111;letter-spacing:-.6px;">${esc(fill(t.hello, who))}</h1>
      <p style="margin:0 0 22px;font:16px/1.6 ${font};color:#3f3f46;">${esc(t.intro)}</p>
      ${button(downloadUrl, t.cta)}
      <h2 style="margin:30px 0 14px;font:800 18px ${font};color:#111;">${esc(t.stepsTitle)}</h2>
      <table role="presentation" cellpadding="0" cellspacing="0" width="100%">${steps}</table>
      <h2 style="margin:14px 0 8px;font:800 18px ${font};color:#111;">${esc(t.featuresTitle)}</h2>
      <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="margin:0 -6px;">${grid}</table>
      <div style="margin:22px 0 0;padding:14px 16px;border-radius:14px;background:#fffbeb;border:1px solid #fde68a;font:14px/1.5 ${font};color:#713f12;">
        <b>${esc(t.tipTitle)}</b> ${esc(t.tip)}</div>
    </td></tr>
    <tr><td style="padding:22px 30px 0;font:14px/1.6 ${font};color:#52525b;" align="center">
      ${esc(t.support)}<br><br>
      <table role="presentation" cellpadding="0" cellspacing="0" align="center"><tr>
        <td style="padding:4px;">${coffee}</td><td style="padding:4px;">${button(supportUrl, t.supportCta, false)}</td>
      </tr></table>
    </td></tr>
    <tr><td style="padding:24px 30px 8px;font:12px/1.6 ${font};color:#a1a1aa;" align="center">${esc(t.footer)}</td></tr>
  </table>
</td></tr></table>
</body></html>`;
  const text = [fill(t.hello, who), "", t.intro, "", `${t.cta}: ${downloadUrl}`, "", t.stepsTitle,
    ...t.steps.map(([a, b], i) => `${i + 1}. ${a}: ${b}`), "", t.featuresTitle, ...t.features.map(([, a, b]) => `- ${a}: ${b}`),
    "", `${t.tipTitle} ${t.tip}`, "", t.support, `${t.coffeeCta}: ${coffeeUrl}`, `${t.supportCta}: ${supportUrl}`, "", t.footer].join("\n");
  return { subject: fill(t.subject, who), html, text };
}

export const LANGUAGES = Object.keys(TEXT);
