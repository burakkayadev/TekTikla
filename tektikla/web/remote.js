/* Telefondan kullanım: telefonun tarayıcısında açılan TekTıkla (tektikla/remote.py bu dosyayı app.js'ten önce ekler).
 * Masaüstündeki pywebview köprüsünün yerini tutar: her çağrı ev ağı üzerinden bilgisayara gider, işleri bilgisayar
 * yapar. Dosya seçmek telefondan yüklemeye, "aç / klasörde göster" telefona kaydetmeye dönüşür. */
"use strict";

(() => {
  window.TT_REMOTE = true;
  const APP = window.TekTiklaAndroid || null;  // Android uygulamasında (android/) açıldıysa yerel köprü
  const KEY = "tt.remote.key", LANG = "tt.remote.lang", LOOK = "tt.remote.look", WHY = "tt.remote.why";
  const LOOK_KEYS = ["theme", "font", "sidebar"];  // görünüm her cihazın kendine
  // analiz, AI, görsel ve Reels işlerinin numaraları bilgisayarda bütün cihazlar için ortak: her sayfa kendi aralığında
  const OFFSET = (1 + (crypto.getRandomValues(new Uint32Array(1))[0] % 4000)) * 1e6;
  const TOKEN_ARG = { analyze: 1, ai_run: 2, similar: 1, image_generate: 1, reels_analyze: 1 };
  const DROP = new Set(["clipboard", "convert_files", "account_error"]);  // bilgisayarın panosu, penceresi, giriş ekranı
  const ACCEPT = {
    video: "video/*,.mp4,.mov,.mkv,.webm,.avi,.m4v",
    audio: "audio/*,.mp3,.m4a,.wav,.aac,.ogg,.flac,.opus",
    image: "image/*,.jpg,.jpeg,.png,.webp",
    subtitle: ".srt,.vtt,.ass,.ssa",
    convert: "image/*,video/*,audio/*,.heic,.heif,.avif,.tif,.tiff,.mkv,.flac,.opus",
  };
  const IOS = /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch { /* gizli sekme */ } },
  };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const clean = (code) => String(code || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
  const client = Array.from(crypto.getRandomValues(new Uint8Array(8)), (b) => b.toString(16).padStart(2, "0")).join("");

  let key = store.get(KEY) || "";
  let lang = store.get(LANG) || "";
  let look = {};
  try { look = JSON.parse(store.get(LOOK) || "{}") || {}; } catch { /* bozuk kayıt */ }
  let settings = {}, urls = {}, pc = "", table = {}, failures = 0, sending = null, ready = false, saveUi = null;
  const watchUrls = new Map();
  const saving = new Map();  // Android uygulamasında telefona kaydedilen dosyalar: iş no → ad

  // QR kodla gelen bağlanma kodu adresin # kısmındadır: kaydedilir ve adres çubuğundan silinir
  const fromQr = location.hash.match(/[#&]k=([A-Za-z0-9-]+)/);
  if (fromQr) {
    key = clean(fromQr[1]);
    store.set(KEY, key);
    history.replaceState(null, "", location.pathname + location.search);
  }
  // sayfa açıkken QR okutulursa yalnızca # kısmı değişir, sayfa yeniden yüklenmez: yeni kodla baştan açılır
  window.addEventListener("hashchange", () => {
    const m = location.hash.match(/[#&]k=([A-Za-z0-9-]+)/);
    if (!m) return;
    store.set(KEY, clean(m[1]));
    history.replaceState(null, "", location.pathname + location.search);
    location.reload();
  });

  /* ------------------------------------------------------------ bilgisayarla konuşma */
  const headers = () => ({ "X-TekTikla-Key": key, "X-TekTikla-Client": client, "X-TekTikla-Lang": lang });

  async function post(name, args, signal) {
    const r = await fetch("api/" + name, { method: "POST", headers: { ...headers(), "Content-Type": "application/json" },
      body: JSON.stringify(args), signal });
    if (r.status === 401) { relink(); throw new Error("key"); }
    const data = await r.json().catch(() => null);
    if (!r.ok) throw new Error((data && data.error) || "HTTP " + r.status);
    return data;
  }

  function relink() {  // bilgisayarda yeni kod oluşturuldu: QR yeniden okutulmalı
    store.set(KEY, null);
    try { sessionStorage.setItem(WHY, "key"); } catch { /* yok */ }
    location.reload();
  }

  async function hello() {
    try {
      const r = await fetch("api/remote_hello", { method: "POST", headers: { ...headers(), "Content-Type": "application/json" }, body: "[]" });
      if (r.status === 401) return "key";
      if (!r.ok) return "net";
      pc = (await r.json()).pc || "";
      return true;
    } catch { return "net"; }
  }

  async function call(name, args) {
    const i = TOKEN_ARG[name];
    if (i !== undefined && typeof args[i] === "number") args[i] += OFFSET;
    if (name === "reels_render" && args[0] && typeof args[0].token === "number") args[0] = { ...args[0], token: args[0].token + OFFSET };
    const res = await post(name, args);
    if (name.startsWith("watch_")) remember(Array.isArray(res) ? res : res && res.items);
    return res;
  }

  function route(events) {
    const out = [];
    for (const ev of events) {
      if (DROP.has(ev.type)) continue;
      if (typeof ev.token === "number") {
        if (ev.token < OFFSET || ev.token >= OFFSET + 1e6) continue;  // başka cihazın (ya da bilgisayarın) işi
        ev.token -= OFFSET;
      }
      if (ev.type === "watch") remember(ev.items);
      out.push(ev);
    }
    return out;
  }

  function remember(items) {
    if (Array.isArray(items)) for (const it of items) if (it && it.id && it.url) watchUrls.set(it.id, it.url);
  }

  // olaylar: bilgisayar yeni olay olunca hemen cevaplar, yoksa ~20 sn bekletir (sürekli sormaz, pil dostu)
  async function poll() {
    ready = true;  // arayüz kuruldu: paylaşılan link artık işlenebilir
    if (failures) await sleep(Math.min(8000, 1000 * failures));
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 32000);
    try {
      const data = await post("poll", [], ctl.signal);
      failures = 0;
      offline(false);
      if (data.fresh) { location.reload(); return []; }  // bilgisayardaki TekTıkla yeniden açıldı ya da uzun süre bakılmadı
      return route(data.events);
    } catch {
      failures++;
      offline(true);
      return [];
    } finally {
      clearTimeout(timer);
    }
  }

  async function init() {
    let res = null;
    for (let n = 1; !res; n++) {
      try { res = await post("init", []); } catch { offline(true); await sleep(Math.min(6000, 700 * n)); }
    }
    offline(false);
    urls = await post("remote_urls", []).catch(() => ({}));
    settings = res.settings;
    res.settings = { ...settings, ...look };
    if (lang && lang !== res.lang) {
      const r = await post("remote_i18n", [lang]).catch(() => null);
      if (r && r.ok) Object.assign(res, { lang: r.lang, i18n: r.i18n, rtl: r.rtl, studio: r.studio });
    } else if (!lang) lang = res.lang || "";  // telefon kendi dilini seçene kadar bilgisayarınki
    res.support = false;  // destek penceresi bilgisayarda açılır
    res.account = { ...res.account, skipped: true };  // hesap bilgisayarındır: telefonda giriş ekranı açılmaz
    remember(res.watch);
    return res;
  }

  /* ------------------------------------------------------------ telefona kaydetme */
  async function fileSheet(kind, ref) {
    const link = await post("remote_link", [kind, ref]).catch(() => null);
    if (!link) { toast("Dosya bulunamadı; silinmiş ya da taşınmış olabilir.", "err"); return; }
    const name = decodeURIComponent(link.split("/").pop());
    const video = /\.(mp4|m4v|mov|webm|mkv)$/i.test(name), image = /\.(jpe?g|png|webp|gif|avif|bmp)$/i.test(name);
    const audio = /\.(mp3|m4a|wav|ogg|opus|flac|aac)$/i.test(name);
    const hint = APP ? "Kaydet'e dokununca videolar ve fotoğraflar Galeri'ye, sesler Müzik'e, diğer dosyalar İndirilenler'e kaydedilir."
      : IOS && video ? "Fotoğraflar'a kaydetmek için Aç'a dokun, sonra Paylaş > Videoyu Kaydet."
        : IOS && image ? "Fotoğraflar'a kaydetmek için Aç'a dokun, sonra resme basılı tut > Fotoğraflar'a Ekle."
          : "Kaydet'e dokununca dosya telefonun İndirilenler klasörüne iner.";
    const later = () => setTimeout(closeSheet, 400);  // bağlantı açılmadan pencere kapanmasın
    const abs = new URL(link, location.href).href;
    const buttons = APP  // uygulamada: telefondaki oynatıcıda aç, Galeri'ye kaydet
      ? [h("button", { class: "btn", onclick: () => { APP.view(abs); closeSheet(); } }, icon("play"), h("span", {}, "Aç")),
        h("button", { class: "btn primary", onclick: () => { const id = APP.save(abs, name); if (id) saving.set(id, name); closeSheet(); } },
          icon("download"), h("span", {}, "Telefona kaydet"))]
      : [h("a", { class: "btn", href: link, target: "_blank", rel: "noopener", onclick: later }, icon("play"), h("span", {}, "Aç")),
        h("a", { class: "btn primary", href: link + "?dl=1", download: name, onclick: later }, icon("download"), h("span", {}, "Telefona kaydet"))];
    sheet(h("div", { class: "rm-file" },
      h("span", { class: "rm-file-ic" }, icon(video ? "film" : image ? "image" : audio ? "music" : "file")),
      h("b", { "data-no-i18n": true }, name)),
    h("div", { class: "btns" }, ...buttons),
    h("small", { class: "rm-hint" }, hint));
  }

  // Android uygulaması kaydetmenin ilerlemesini ve sonucunu buraya bildirir (MainActivity.progress)
  window.ttSaved = (id, done, total, state, where) => {
    const name = saving.get(id) || "";
    if (state === "run") {
      saveUi = saveUi || progressSheet("Telefona kaydediliyor", "download", null);
      saveUi(done, total, name);
      return;
    }
    saving.delete(id);
    if (saveUi) { saveUi = null; closeSheet(); }
    if (state === "done") toast(tr("Telefona kaydedildi: {where}", { where }), "ok");
    else toast("Dosya telefona kaydedilemedi.", "err");
  };

  function sheet(...children) {
    closeSheet();
    const modal = children[0] === "modal";
    const box = h("div", { class: "card rm-sheet", id: "rmSheet", role: "dialog" },
      modal ? null : h("button", { class: "btn icon ghost rm-sheet-x", title: "Kapat", onclick: closeSheet }, icon("x")),
      ...children.filter((c) => c !== "modal"));
    const scrim = h("div", { class: "rm-scrim", id: "rmScrim", onclick: modal ? null : closeSheet });
    document.body.append(scrim, box);
    requestAnimationFrame(() => requestAnimationFrame(() => { scrim.classList.add("in"); box.classList.add("in"); }));
    return box;
  }

  function closeSheet() {
    for (const id of ["rmSheet", "rmScrim"]) {
      const el = document.getElementById(id);
      if (!el) continue;
      el.id = "";
      el.classList.remove("in");
      setTimeout(() => el.remove(), 280);
    }
  }

  /* ------------------------------------------------------------ telefondan gönderme */
  function pickFiles(kind, multiple) {
    return new Promise((resolve) => {
      const input = h("input", { type: "file", accept: ACCEPT[kind] || "", class: "rm-file-input" });
      input.multiple = multiple;
      const done = (files) => { input.remove(); resolve(files); };
      input.addEventListener("change", () => done([...input.files]), { once: true });
      input.addEventListener("cancel", () => done([]), { once: true });
      document.body.append(input);
      input.click();
    });
  }

  function sendFile(file, progress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      if (sending) sending.xhr = xhr;
      xhr.open("POST", "upload?name=" + encodeURIComponent(file.name || "dosya"));
      for (const [k, v] of Object.entries(headers())) xhr.setRequestHeader(k, v);
      xhr.setRequestHeader("Content-Type", "application/octet-stream");
      xhr.upload.onprogress = (e) => progress(e.loaded);
      xhr.onload = () => {
        if (xhr.status === 401) { relink(); reject(new Error("abort")); }
        else if (xhr.status === 200) resolve(JSON.parse(xhr.responseText).path);
        else reject(new Error(xhr.status === 413 ? "big" : "fail"));
      };
      xhr.onerror = () => reject(new Error("fail"));
      xhr.onabort = () => reject(new Error("abort"));
      xhr.send(file);
    });
  }

  const size = (n) => (typeof convBytes === "function" ? convBytes(n) : Math.round(n / 1048576) + " MB");

  // ilerleme penceresi: telefondan gönderirken ve (uygulamada) telefona kaydederken
  function progressSheet(title, ic, onCancel) {
    const bar = h("div", { class: "progress" }, h("i"));
    const name = h("b", { "data-no-i18n": true });
    const stat = h("small", { class: "rm-stat", "data-no-i18n": true });
    sheet("modal",
      h("div", { class: "rm-file" }, h("span", { class: "rm-file-ic" }, icon(ic)),
        h("div", { class: "rm-up-txt" }, h("small", {}, title), name)),
      bar, stat,
      onCancel ? h("div", { class: "btns" }, h("button", { class: "btn", onclick: onCancel }, "İptal")) : null);
    return (done, total, file) => {
      const pct = total ? Math.min(100, (done / total) * 100) : 0;
      bar.firstChild.style.width = pct + "%";
      name.textContent = file;
      stat.textContent = `%${Math.round(pct)} · ${size(done)} / ${size(total)}`;
    };
  }

  async function uploadPick(kind, multiple = false) {
    const empty = kind === "convert" ? { items: [], skipped: 0 } : null;
    const files = await pickFiles(kind, multiple);
    if (!files.length) return empty;
    const total = files.reduce((s, f) => s + f.size, 0);
    const show = progressSheet(files.length > 1 ? `${files.length} dosya bilgisayara gönderiliyor` : "Bilgisayara gönderiliyor", "upload",
      () => { if (sending) { sending.cancelled = true; if (sending.xhr) sending.xhr.abort(); } });
    sending = { xhr: null, cancelled: false };
    const paths = [];
    let before = 0;
    try {
      for (const f of files) {
        if (sending.cancelled) throw new Error("abort");
        show(before, total, f.name);
        paths.push(await sendFile(f, (loaded) => show(before + loaded, total, f.name)));
        before += f.size;
      }
    } catch (e) {
      if (e.message !== "abort") toast(e.message === "big" ? "Dosya çok büyük (en fazla 4 GB)." : "Dosya bilgisayara gönderilemedi.", "err");
      return empty;
    } finally {
      sending = null;
      closeSheet();
    }
    return post("remote_uploaded", [kind, paths]);
  }

  // görsel düzenleyici: telefonda düzenlenen görsel önce bilgisayara gönderilir, sonra Görseller'e kaydedilir
  window.ttUpload = async (blob, name) => {
    const file = new File([blob], name, { type: blob.type });
    const show = progressSheet("Bilgisayara gönderiliyor", "upload",
      () => { if (sending) { sending.cancelled = true; if (sending.xhr) sending.xhr.abort(); } });
    sending = { xhr: null, cancelled: false };
    try {
      show(0, file.size, name);
      return await sendFile(file, (loaded) => show(loaded, file.size, name));
    } finally {
      sending = null;
      closeSheet();
    }
  };

  /* ------------------------------------------------------------ köprü */
  // dış bağlantılar (YouTube, servis siteleri): uygulamada telefonun kendi uygulamalarında açılır
  const openOut = (url) => { if (APP) APP.openExternal(url); else window.open(url, "_blank", "noopener"); };
  const pcOnly = async () => { toast("Bu işlem bilgisayardaki TekTıkla'dan yapılır.", "info"); return null; };
  const OVERRIDES = {
    init, poll,
    async set_language(code) {
      const r = await post("remote_i18n", [code]);
      if (r.ok) { lang = code; store.set(LANG, code); }
      return r;
    },
    async set_setting(k, v) {
      if (LOOK_KEYS.includes(k)) { look[k] = v; store.set(LOOK, JSON.stringify(look)); }
      else settings = await post("set_setting", [k, v]);
      return { ...settings, ...look };
    },
    support_seen: async () => null,
    open_url: async (name) => { if (urls[name]) openOut(urls[name]); },
    watch_open: async (id) => { const u = watchUrls.get(id); if (u) openOut(u); return !!u; },
    open_item: (id) => fileSheet("item", id),
    reveal_item: (id) => fileSheet("item", id),
    open_history: (i) => fileSheet("history", i),
    reveal_history: (i) => fileSheet("history", i),
    open_made: (p) => fileSheet("made", p),
    reveal_made: (p) => fileSheet("made", p),
    reveal_file: (p) => fileSheet("file", p),
    open_download_dir: async () => null,
    pick_folder: async () => { toast("Kayıt klasörü bilgisayardaki TekTıkla'dan değiştirilir.", "info"); return null; },
    pick_subtitle: () => uploadPick("subtitle"),
    pick_video: () => uploadPick("video"),
    pick_audio: () => uploadPick("audio"),
    pick_image: () => uploadPick("image"),
    convert_pick: () => uploadPick("convert", true),
    convert_pick_folder: () => uploadPick("convert", true),
    install_components: pcOnly, update_ytdlp: pcOnly, check_update: pcOnly, install_update: pcOnly,
  };
  const API = new Proxy({}, {
    get(_, name) {
      if (typeof name !== "string" || name === "then") return undefined;
      return OVERRIDES[name] || ((...args) => call(name, args));
    },
  });

  /* ------------------------------------------------------------ sayfa */
  function offline(on) {
    let pill = document.getElementById("rmOffline");
    document.body.classList.toggle("rm-off", on);
    if (!on) { if (pill) pill.classList.remove("in"); return; }
    if (!pill) {
      pill = h("div", { class: "rm-offline", id: "rmOffline", role: "status" }, h("span", { class: "dot" }),
        h("span", {}, "Bilgisayara ulaşılamıyor · yeniden deneniyor…"));
      document.body.append(pill);
    }
    requestAnimationFrame(() => pill.classList.add("in"));
  }

  function adaptPage() {
    // masaüstüne göre yazılmış birkaç düğme telefonda başka şey yapar
    const label = (sel, text, ic) => {
      const el = document.querySelector(sel);
      if (!el) return;
      const node = [...el.childNodes].find((n) => n.nodeType === 3 && n.nodeValue.trim());
      if (node) node.nodeValue = text;
      const i = ic && el.querySelector("i[data-ic]");
      if (i) i.dataset.ic = ic;
    };
    label("#reelsPickBtn", "Telefondan seç", "upload");
    label("#dubPickBtn", "Telefondan seç", "upload");
    label("#convDrop b", "Dosya seçmek için dokun");
    // pano: şifresiz bağlantıda tarayıcı izin vermez; uygulamada telefonun panosu köprüden okunur
    const clip = navigator.clipboard || {};
    const readText = APP ? async () => APP.paste() : clip.readText && clip.readText.bind(clip);
    const writeText = clip.writeText ? clip.writeText.bind(clip) : (text) => new Promise((ok, fail) => {  // eski yolla kopyalama
      const ta = Object.assign(document.createElement("textarea"), { value: text, readOnly: true });
      ta.style.cssText = "position:fixed;top:-1000px;opacity:0";
      document.body.append(ta);
      ta.select();
      ta.setSelectionRange(0, text.length);
      const copied = document.execCommand("copy");
      ta.remove();
      if (copied) ok(); else fail(new Error("copy"));
    });
    if (APP || !clip.readText || !clip.writeText) {
      try { Object.defineProperty(navigator, "clipboard", { value: { readText, writeText }, configurable: true }); } catch { /* kopyalanamaz */ }
    }
    document.body.classList.toggle("rm-no-paste", !readText);
    // telefonun üst çubuğu (uygulamada sistem çubukları) seçili temanın zeminini alır
    const meta = document.querySelector('meta[name="theme-color"]');
    new MutationObserver(() => {
      const color = getComputedStyle(document.body).backgroundColor;
      if (meta) meta.content = color;
      if (APP) APP.setBar(color);
    }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    window.openAuth = () => toast("Hesap işlemleri bilgisayardaki TekTıkla'dan yapılır.", "info");
  }

  function start() {
    const foot = document.querySelector(".side-foot");
    if (foot && pc) foot.prepend(h("div", { class: "rm-pc", title: pc }, icon("phone"), h("span", {}, "Bağlı:"), h("b", { "data-no-i18n": true }, pc)));
    window.pywebview = { api: API };
    window.dispatchEvent(new Event("pywebviewready"));
  }

  /* ------------------------------------------------------------ eşleştirme */
  const T = (s) => table[s] || s;

  async function loadTable() {
    const code = lang || (navigator.language || "tr").slice(0, 2).toLowerCase();
    if (code === "ar") document.documentElement.dir = "rtl";
    if (code === "tr") return;
    try { const r = await fetch(`i18n/${code}.json`); if (r.ok) table = await r.json(); } catch { /* Türkçe kalır */ }
  }

  function pairScreen(why) {
    if (APP) {  // uygulamada eşleştirmeyi uygulamanın kendi ekranı yapar (QR tarayıcı, ağda arama)
      APP.retry();
      return;
    }
    const input = h("input", { class: "input rm-code", placeholder: "ABCDE-12345", autocomplete: "off", autocapitalize: "characters",
      spellcheck: "false", maxlength: "11", "aria-label": T("Bağlanma kodu") });
    if (key) input.value = key.slice(0, 5) + "-" + key.slice(5);
    input.addEventListener("input", () => {
      const c = clean(input.value).slice(0, 10);
      input.value = c.length > 5 ? c.slice(0, 5) + "-" + c.slice(5) : c;
    });
    const err = h("p", { class: "rm-err hidden" });
    const say = (text) => { err.textContent = T(text); err.classList.toggle("hidden", !text); };
    const go = h("button", { class: "btn primary lg", type: "submit" }, icon("link"), h("span", {}, T("Bağlan")));
    const form = h("form", { class: "rm-form" }, input, go);
    const logo = document.querySelector(".brand .logo");
    const box = h("div", { class: "rm-pair", id: "rmPair", "data-no-i18n": true },
      h("div", { class: "card rm-pair-card" },
        logo ? logo.cloneNode(true) : null,
        h("h2", {}, T("Bilgisayarına bağlan")),
        h("p", {}, T("Bilgisayardaki TekTıkla'da Ayarlar > Telefondan kullan'ı aç ve QR kodu telefonunun kamerasıyla okut.")),
        h("div", { class: "auth-or" }, h("span", {}, T("ya da bağlanma kodunu yaz"))),
        form, err,
        h("small", { class: "rm-note" }, icon("wifi"), h("span", {}, T("Telefon ve bilgisayar aynı Wi-Fi ağında olmalı.")))));
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const code = clean(input.value);
      if (code.length !== 10) { say("Kod 10 karakter: bilgisayardaki Telefondan kullan penceresinde yazıyor."); input.focus(); return; }
      go.disabled = true;
      key = code;
      const ok = await hello();
      go.disabled = false;
      if (ok === true) { store.set(KEY, key); box.remove(); start(); return; }
      say(ok === "key" ? "Kod yanlış. Bilgisayardaki pencerede görünen kodu yaz."
        : "Bilgisayara ulaşılamadı. TekTıkla açık mı, telefon aynı Wi-Fi'de mi?");
    });
    document.body.append(box);
    if (why === "key") say("Bağlanma kodu değişmiş. QR kodu yeniden okut ya da yeni kodu yaz.");
    else if (why === "net") say("Bilgisayara ulaşılamadı. TekTıkla açık mı, telefon aynı Wi-Fi'de mi?");
  }

  /* ------------------------------------------------------------ Android uygulaması */
  // YouTube, Instagram, TikTok… uygulamasından "Paylaş > TekTıkla" ile gelen link: ne yapılacağı sorulur
  window.ttShare = async (url) => {
    for (let i = 0; i < 150 && !ready; i++) await sleep(100);
    const choice = (ic, label, run) => h("button", { class: "btn rm-share-btn", onclick: () => { closeSheet(); run(); } },
      icon(ic), h("span", {}, label));
    const fill = () => { $("#urlInput").value = url; };
    sheet(h("div", { class: "rm-file" }, h("span", { class: "rm-file-ic" }, icon("link")),
      h("div", { class: "rm-up-txt" }, h("small", {}, "Paylaşılan link"), h("b", { "data-no-i18n": true }, url))),
    h("div", { class: "rm-share" },
      choice("download", "İndir", () => analyze(url)),
      choice("zap", "Hızlı indir", () => { fill(); quick("video"); }),
      choice("music", "MP3 indir", () => { fill(); quick("audio"); }),
      choice("bookmark", "Sonra izle", async () => {
        const r = await api.watch_add(url);
        toast(r.added ? "İzleme listesine eklendi" : "Bu video zaten listede", r.added ? "ok" : "info");
      }),
      choice("reels", "Reels yap", () => {
        segs.reelsModeSeg.set("video", false);
        studio.reelsFile = null;
        $("#reelsUrl").value = url;
        showPage("reels");
        reelsFind();
      }),
      choice("sparkles", "AI ile özetle", () => aiRun("summary", url))));
  };

  // telefonun geri tuşu: önce açık pencereyi ya da menüyü kapatır, sonra ana sayfaya döner; true = sayfa halletti
  window.ttBack = () => {
    if (document.getElementById("rmSheet")) {
      if (!sending && !saveUi) closeSheet();
      return true;
    }
    const open = [...document.querySelectorAll(".overlay:not(.hidden)")].filter((o) => o.id !== "langOverlay");
    if (open.length) {
      open[open.length - 1].classList.add("hidden");
      return true;
    }
    const shell = document.querySelector(".app");
    if (shell && shell.classList.contains("m-open")) {
      shell.classList.remove("m-open");
      return true;
    }
    const page = document.querySelector(".page.active");
    if (page && page.id !== "page-download") {
      showPage("download");
      return true;
    }
    return false;
  };

  document.addEventListener("DOMContentLoaded", async () => {
    adaptPage();
    let why = "";
    try { why = sessionStorage.getItem(WHY) || ""; sessionStorage.removeItem(WHY); } catch { /* yok */ }
    if (key) {
      const ok = await hello();
      if (ok === true) { start(); return; }
      if (ok === "key") { key = ""; store.set(KEY, null); why = "key"; } else why = "net";
    }
    await loadTable();
    pairScreen(why);
  });
})();
