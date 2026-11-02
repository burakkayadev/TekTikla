// TekTıkla hoş geldin e-postası — Google Apps Script web uygulamasının giriş noktası.
// Uygulama yeni üyenin Firebase kimlik anahtarını gönderir: {idToken, lang}. Anahtar Firebase'e sorularak doğrulanır;
// e-posta senin Gmail hesabından "TekTıkla" adıyla, her üyeye yalnızca bir kez ve yalnızca yeni hesaplara gider.
// Kurulum: Proje Ayarları > Komut dosyası özellikleri > FIREBASE_API_KEY = Firebase web uygulamasının apiKey değeri.

function doPost(e) {
  let body = {};
  try {
    body = JSON.parse((e && e.postData && e.postData.contents) || "{}");
  } catch (err) {
    return reply({ ok: false, error: "bad-json" });
  }
  const props = PropertiesService.getScriptProperties();
  const apiKey = props.getProperty("FIREBASE_API_KEY");
  if (!apiKey || !body.idToken) return reply({ ok: false, error: "config" });

  // anahtar gerçek mi: Firebase'e sorulur (sahte istekle başkasına e-posta attırılamaz)
  const res = UrlFetchApp.fetch(
    "https://identitytoolkit.googleapis.com/v1/accounts:lookup?key=" + encodeURIComponent(apiKey),
    { method: "post", contentType: "application/json", payload: JSON.stringify({ idToken: body.idToken }),
      muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) return reply({ ok: false, error: "token" });
  const user = (JSON.parse(res.getContentText()).users || [])[0];
  if (!user || !user.email) return reply({ ok: false, error: "no-email" });
  // yalnızca son 24 saatte açılmış hesaplar (eski hesaplar tekrar tekrar e-posta alamasın)
  if (Date.now() - Number(user.createdAt || 0) > 24 * 3600 * 1000) return reply({ ok: true, skipped: "old" });

  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    if (props.getProperty("sent_" + user.localId)) return reply({ ok: true, skipped: "sent" });
    const mail = welcomeEmail({ name: user.displayName || user.email.split("@")[0], lang: body.lang || "tr" });
    MailApp.sendEmail({ to: user.email, subject: mail.subject, htmlBody: mail.html, body: mail.text, name: "TekTıkla" });
    props.setProperty("sent_" + user.localId, String(Date.now()));
  } finally {
    lock.releaseLock();
  }
  return reply({ ok: true });
}

function reply(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
