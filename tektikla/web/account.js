/* Hesap: e-posta, Google ve GitHub ile giriş; kayıt olmadan devam.
 * Python tarafı: tektikla/account.py + api.py (account_*). Google ve GitHub girişi sistem tarayıcısında olur. */
"use strict";

const acct = { state: { configured: false, user: null, skipped: false, waiting: null }, mode: "signin" };
const PROVIDER_NAME = { google: "Google ile giriş yapıldı", github: "GitHub ile giriş yapıldı", password: "E-postayla giriş yapıldı" };

function acctInitials(name) {
  return (name || "?").trim().split(/\s+/).slice(0, 2).map((w) => w[0] || "").join("").toLocaleUpperCase(I18N.lang || "tr");
}

function acctAvatar(user, cls = "") {
  const box = h("span", { class: "avatar " + cls });
  if (user && user.photo) {
    box.append(h("img", { src: user.photo, alt: "", referrerpolicy: "no-referrer",
      onerror: (e) => e.target.replaceWith(txt(acctInitials(user.name))) }));
  } else if (user) box.append(txt(acctInitials(user.name)));
  else box.append(icon("user"));
  return box;
}

function renderAccount() {
  const { configured, user, waiting } = acct.state;
  // kenar çubuğu: profil ya da "Giriş yap"
  const chip = $("#acctChip");
  chip.classList.toggle("hidden", !configured);
  const go = icon("chevronRight");
  go.classList.add("acct-go");
  chip.replaceChildren(acctAvatar(user, user ? "" : "ghost"),
    h("span", { class: "acct-txt" },
      user ? h("b", { "data-no-i18n": true }, txt(user.name)) : h("b", {}, "Giriş yap"),
      user ? h("small", { "data-no-i18n": true }, txt(user.email || "")) : h("small", {}, "ya da hesap aç")), go);
  chip.title = tr(user ? "Hesap" : "Giriş yap ya da hesap aç");

  // ayarlar: hesap kartı
  $("#acctCard").classList.toggle("hidden", !configured);
  const body = $("#acctBody");
  if (user) {
    const unverified = user.provider === "password" && !user.verified;
    body.replaceChildren(
      h("div", { class: "acct-profile" }, acctAvatar(user, "lg"),
        h("div", { class: "acct-id" }, h("b", { "data-no-i18n": true }, txt(user.name)),
          h("small", { "data-no-i18n": true }, txt(user.email || "")),
          h("span", { class: "chip " + (user.provider === "password" ? "" : "ok") }, PROVIDER_NAME[user.provider] || "")),
        h("div", { class: "acct-acts" },
          h("button", { class: "btn", onclick: acctSignOut }, icon("logout"), "Çıkış yap"),
          h("button", { class: "btn danger", id: "acctDeleteBtn", onclick: acctDelete }, icon("trash"), h("span", {}, "Hesabı sil")))),
      unverified ? h("div", { class: "acct-note" }, icon("mail"),
        h("span", {}, "E-posta adresin henüz doğrulanmadı. Gelen kutundaki bağlantıya tıkla."),
        h("button", { class: "btn sm", onclick: acctVerify }, "Yeniden gönder")) : null);
  } else {
    body.replaceChildren(h("div", { class: "acct-profile" }, acctAvatar(null, "lg ghost"),
      h("div", { class: "acct-id" }, h("b", {}, "Giriş yapmadın"),
        h("small", {}, "Hesapla YouTube \"Daha sonra izle\" ve beğendiklerini uygulamaya çekebilirsin.")),
      h("div", { class: "acct-acts" }, h("button", { class: "btn primary", onclick: () => openAuth() }, icon("user"), "Giriş yap ya da hesap aç"))));
  }

  // giriş ekranı: tarayıcıda giriş bekleniyorsa bekleme görünümü
  $("#authWaiting").classList.toggle("hidden", !waiting);
  $("#authMain").classList.toggle("hidden", !!waiting);
  if (waiting) $("#authWaitText").textContent = tr(waiting === "google" ? "Tarayıcıda Google ile giriş yap" : "Tarayıcıda GitHub ile giriş yap");
  if (typeof renderWatchYt === "function") renderWatchYt();
}

function authMode(mode) {
  acct.mode = mode;
  const up = mode === "signup";
  $("#authName").classList.toggle("hidden", !up);
  $("#authForgot").classList.toggle("hidden", up);
  $("#authPass").autocomplete = up ? "new-password" : "current-password";
  $("#authSubmit span").textContent = tr(up ? "Hesap aç" : "Giriş yap");
  authError("");
}

function authError(text) {
  $("#authErr").textContent = text ? tr(text) : "";
  $("#authErr").classList.toggle("hidden", !text);
}

function openAuth() {
  if (!acct.state.configured) return;
  authMode(acct.mode);
  $("#authOverlay").classList.remove("hidden");
  renderAccount();
  requestAnimationFrame(() => segs.authModeSeg && segs.authModeSeg.refresh());
}

function closeAuth() {
  $("#authOverlay").classList.add("hidden");
}

async function authSubmit(e) {
  e.preventDefault();
  const email = $("#authEmail").value.trim(), pass = $("#authPass").value, name = $("#authName").value.trim();
  if (!email || !pass) { authError("E-posta ve şifreni yaz."); return; }
  if (acct.mode === "signup" && pass.length < 6) { authError("Şifre en az 6 karakter olmalı."); return; }
  const btn = $("#authSubmit");
  btn.disabled = true;
  btn.classList.add("busy");
  const r = await api.account_email(acct.mode, email, pass, name);
  btn.disabled = false;
  btn.classList.remove("busy");
  if (!r.ok) { authError(r.error); return; }
  $("#authPass").value = "";
  acct.state = r.state;
  renderAccount();
  closeAuth();
  toast(acct.mode === "signup" ? "Hesabın açıldı. Doğrulama e-postası gönderildi." : `Hoş geldin, ${r.state.user.name}!`, "ok");
}

async function authProvider(provider) {
  authError("");
  const r = await api.account_provider(provider);
  if (!r.ok) { authError(r.error || "Giriş başlatılamadı."); return; }
  acct.state = r.state;
  renderAccount();
}

async function authForgot() {
  const email = $("#authEmail").value.trim();
  if (!email) { authError("Önce e-posta adresini yaz."); $("#authEmail").focus(); return; }
  const r = await api.account_reset(email);
  if (r.ok) toast("Şifre sıfırlama bağlantısı e-postana gönderildi.", "ok");
  else authError(r.error);
}

async function acctSkip() {
  acct.state = await api.account_skip();
  closeAuth();
  renderAccount();
}

async function acctSignOut() {
  acct.state = await api.account_signout();
  renderAccount();
  toast("Çıkış yapıldı.");
}

async function acctVerify() {
  const r = await api.account_verify();
  toast(r.ok ? "Doğrulama e-postası gönderildi." : (r.error || "Gönderilemedi."), r.ok ? "ok" : "err");
}

async function acctDelete(e) {
  // geri alınamaz: ilk basışta onay ister
  const btn = e.currentTarget, label = btn.querySelector("span");
  if (!btn.dataset.armed) {
    btn.dataset.armed = "1";
    label.textContent = tr("Emin misin? Tekrar bas");
    setTimeout(() => { if (btn.isConnected) { delete btn.dataset.armed; label.textContent = tr("Hesabı sil"); } }, 4000);
    return;
  }
  const r = await api.account_delete();
  if (!r.ok) { toast(r.error || "Hesap silinemedi.", "err"); return; }
  acct.state = r.state;
  renderAccount();
  toast("Hesabın ve bilgilerin silindi.", "ok");
}

// İlk açılış: dil seçildikten sonra, giriş yapılmamış ve "kayıt olmadan devam" seçilmemişse hoş geldin ekranı
function autoAuth() {
  if (!$("#langOverlay").classList.contains("hidden")) return setTimeout(autoAuth, 800);
  const { configured, user, skipped } = acct.state;
  if (configured && !user && !skipped) openAuth();
}

function wireAccount() {
  seg("authModeSeg", authMode).set("signin");
  $("#authForm").addEventListener("submit", authSubmit);
  $("#authGoogle").addEventListener("click", () => authProvider("google"));
  $("#authGithub").addEventListener("click", () => authProvider("github"));
  $("#authForgot").addEventListener("click", authForgot);
  $("#authSkip").addEventListener("click", acctSkip);
  $("#authClose").addEventListener("click", acctSkip);
  $("#authCancel").addEventListener("click", async () => { acct.state = await api.account_cancel(); renderAccount(); });
  $("#acctChip").addEventListener("click", () => {
    if (acct.state.user) { showPage("settings"); setTimeout(() => $("#acctCard").scrollIntoView({ block: "start", behavior: "smooth" }), 60); }
    else openAuth();
  });
  Object.assign(HANDLERS, {
    account: (ev) => {
      acct.state = ev.state;
      renderAccount();
      if (ev.state.user && !$("#authOverlay").classList.contains("hidden")) closeAuth();
    },
    account_error: (ev) => { openAuth(); authError(ev.message); },
  });
}

function accountInit(init) {
  acct.state = init.account || acct.state;
  renderAccount();
  setTimeout(autoAuth, 600);
}
