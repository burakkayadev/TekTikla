/* TekTıkla arayüz mantığı. Python tarafı: pywebview.api.* (tektikla/api.py)
 * Güvenlik: sitelerden gelen metinler (başlık, açıklama…) her zaman textContent ile basılır, asla innerHTML ile. */
"use strict";

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
let api = null;

/* ---------------------------------------------------------------- simgeler */
const ICONS = {
  download: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  sparkles: '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
  clipboard: '<rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
  zap: '<path d="M13 2L3 14h9l-1 8 10-12h-9z"/>',
  music: '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
  film: '<rect x="2" y="3" width="20" height="18" rx="2"/><path d="M7 3v18M17 3v18M2 8h5M2 16h5M17 8h5M17 16h5M2 12h20"/>',
  x: '<path d="M18 6L6 18M6 6l12 12"/>',
  file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  trash: '<path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>',
  alert: '<circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/>',
  copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  box: '<path d="M21 16V8a2 2 0 0 0-1-1.7l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.7l7 4a2 2 0 0 0 2 0l7-4a2 2 0 0 0 1-1.7z"/><path d="M3.3 7L12 12l8.7-5M12 22V12"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-2.6-6.4L21 8"/><path d="M21 3v5h-5"/>',
  play: '<path d="M7 4v16l13-8z"/>',
  check: '<path d="M20 6L9 17l-5-5"/>',
  retry: '<path d="M3 12a9 9 0 1 0 2.6-6.4L3 8"/><path d="M3 3v5h5"/>',
  chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-4.9A8 8 0 1 1 21 12z"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  bulb: '<path d="M9 18h6M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.2 1 2V17h6v-.3c0-.8.4-1.5 1-2A7 7 0 0 0 12 2z"/>',
  palette: '<path d="M12 21a9 9 0 1 1 9-9c0 2.5-2 4-4.5 4H15a2 2 0 0 0-1.5 3.3A1.6 1.6 0 0 1 12 21z"/><circle cx="7.5" cy="10.5" r="1"/><circle cx="12" cy="7.5" r="1"/><circle cx="16.5" cy="10.5" r="1"/>',
  panelClose: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18M16 15l-3-3 3-3"/>',
  panelOpen: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18M14 9l3 3-3 3"/>',
  chevronRight: '<path d="M9 18l6-6-6-6"/>',
  youtube: '<path d="M2.5 17a24 24 0 0 1 0-10 2 2 0 0 1 1.4-1.4 49.6 49.6 0 0 1 16.2 0A2 2 0 0 1 21.5 7a24 24 0 0 1 0 10 2 2 0 0 1-1.4 1.4 49.6 49.6 0 0 1-16.2 0A2 2 0 0 1 2.5 17"/><path d="M10 15l5-3-5-3z"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  phone: '<rect x="6.5" y="2" width="11" height="20" rx="2.5"/><path d="M11 18h2"/>',
  coffee: '<path d="M3 9h13v6a5 5 0 0 1-5 5H8a5 5 0 0 1-5-5z"/><path d="M16 11h1.5a2.5 2.5 0 0 1 0 5H16"/><path d="M7 3v3M10.5 3v3M14 3v3"/>',
  wifi: '<path d="M2 8.8a15 15 0 0 1 20 0M5 12.4a10 10 0 0 1 14 0M8.5 15.9a5 5 0 0 1 7 0"/><circle cx="12" cy="19.3" r="1"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5M5 20h14"/>',
  convert: '<path d="M17 2l4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14"/><path d="M7 22l-4-4 4-4"/><path d="M21 13v1a4 4 0 0 1-4 4H3"/>',
  sliders: '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
  arrowRight: '<path d="M5 12h14M12 5l7 7-7 7"/>',
  bookmark: '<path d="M19 21l-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  grip: '<circle cx="9" cy="6" r="1"/><circle cx="15" cy="6" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="9" cy="18" r="1"/><circle cx="15" cy="18" r="1"/>',
  arrowUp: '<path d="M12 19V5M5 12l7-7 7 7"/>',
  arrowDown: '<path d="M12 5v14M19 12l-7 7-7-7"/>',
  heart: '<path d="M19 14c1.5-1.5 3-3.2 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.8 0-3 .5-4.5 2-1.5-1.5-2.7-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4 3 5.5l7 7z"/>',
  github: '<path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.1-1.3-.3-2.5-1-3.5.3-1.2.3-2.4 0-3.5 0 0-1 0-3 1.5a10.4 10.4 0 0 0-8 0C6 2 5 2 5 2c-.3 1.2-.3 2.4 0 3.5A5.4 5.4 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.4.5-.7 1-.9 1.7-.2.6-.2 1.2-.1 1.8v4"/><path d="M9 18c-4.5 2-5-2-7-2"/>',
};
function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", "ic");
  svg.innerHTML = ICONS[name] || "";  // sabit, güvenilir içerik
  return svg;
}
function hydrateIcons(root = document) {
  root.querySelectorAll("i[data-ic]").forEach((i) => i.replaceWith(icon(i.dataset.ic)));
}

/* Güvenli DOM üretici: string çocuklar her zaman metin düğümü olur */
function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined && v !== false) el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

/* ---------------------------------------------------------------- efektler */
document.addEventListener("pointerdown", (e) => {
  const btn = e.target.closest(".btn, .q-tile, .nav-item, .seg button");
  if (!btn) return;
  const r = btn.getBoundingClientRect();
  const size = Math.max(r.width, r.height);
  const dot = h("span", { class: "ripple" });
  dot.style.cssText = `width:${size}px;height:${size}px;left:${e.clientX - r.left - size / 2}px;top:${e.clientY - r.top - size / 2}px`;
  if (getComputedStyle(btn).position === "static") btn.style.position = "relative";
  btn.style.overflow = "hidden";
  btn.append(dot);
  setTimeout(() => dot.remove(), 700);
});

function toast(text, kind = "info") {
  const t = h("div", { class: `toast ${kind}` },
    h("div", { class: "ti" }, icon(kind === "ok" ? "check" : kind === "err" ? "alert" : "sparkles")),
    h("div", {}, text));
  $("#toasts").append(t);
  setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 320); }, 4200);
}

function setLoading(btn, on) { btn.classList.toggle("loading", on); btn.disabled = on; }

/* ---------------------------------------------------------------- segment kontrolü */
const segs = {};
function seg(id, onChange) {
  const el = document.getElementById(id);
  const glider = h("span", { class: "glider" });
  el.prepend(glider);
  const ctl = {
    value: null,
    set(v, silent = true) {
      const b = el.querySelector(`button[data-v="${CSS.escape(String(v))}"]`);
      if (!b) return;
      el.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
      ctl.value = String(v);
      requestAnimationFrame(() => {
        glider.style.width = b.offsetWidth + "px";
        glider.style.transform = `translateX(${b.offsetLeft - 4}px)`;
        glider.style.left = "4px";
      });
      if (!silent && onChange) onChange(ctl.value);
    },
    refresh() { if (ctl.value !== null) ctl.set(ctl.value); },
  };
  el.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => ctl.set(b.dataset.v, false)));
  segs[id] = ctl;
  return ctl;
}
window.addEventListener("resize", () => { Object.values(segs).forEach((s) => s.refresh()); moveIndicator(); });

/* ---------------------------------------------------------------- durum */
const state = {
  settings: {}, items: new Map(), history: [], media: null, mediaUrl: "",
  analyzeToken: 0, aiToken: 0, similarToken: 0, aiMode: "summary", aiSteps: [], extSub: null, plSel: new Set(), setup: "checking", keys: {}, providers: {}, languages: [],
  quality: null, queueFilter: "all", update: null, repo: "",
};

/* ---------------------------------------------------------------- sayfalar */
function showPage(name) {
  $$(".nav-item").forEach((n) => n.classList.toggle("active", n.dataset.page === name));
  $$(".page").forEach((p) => p.classList.toggle("active", p.id === "page-" + name));
  moveIndicator();
  $("#main").scrollTop = 0;
  setTimeout(() => Object.values(segs).forEach((s) => s.refresh()), 30);
}
function moveIndicator() {
  const a = $(".nav-item.active");
  if (!a) return;
  // kısa pencerede menü öğeleri sıkışır: vurgu kutusu öğenin gerçek yüksekliğini alır
  $("#navIndicator").style.transform = `translateY(${a.offsetTop}px)`;
  $("#navIndicator").style.height = a.offsetHeight + "px";
}
$$(".nav-item").forEach((n) => n.addEventListener("click", () => showPage(n.dataset.page)));

/* ---------------------------------------------------------------- destek */
// GitHub profilinin (ve tanımlıysa bağış sayfasının) QR kodu. İlk açılışta ve her yeni sürümde bir kez kendiliğinden açılır.
let supportLinks = null;
async function openSupport() {
  supportLinks = supportLinks || (await api.support_info()).links;
  $("#supportCards").replaceChildren(...supportLinks.map((l) => {
    const coffee = l.id === "donate";  // Buy Me a Coffee: "Bana bir kahve alır mısın?"
    return h("button", { class: "qr-card" + (coffee ? " coffee" : ""), title: l.label, onclick: () => api.open_url("support_" + l.id) },
      h("span", { class: "qr-img" }, h("img", { src: l.qr, alt: l.label })),
      coffee ? h("b", { class: "qr-ask" }, "Bana bir kahve alır mısın?") : null,
      h("span", { class: "qr-label", "data-no-i18n": true }, icon(coffee ? "coffee" : "github"),
        // uzun bağış adresi kesilmesin: gerekirse "/" işaretinden sonra alt satıra geçer
        h("span", {}, ...l.label.split("/").flatMap((part, i) => (i ? [h("wbr"), "/" + part] : [part])))));
  }));
  $("#supportDonate").classList.toggle("hidden", !supportLinks.some((l) => l.id === "donate"));
  $("#supportOverlay").classList.remove("hidden");
}
function autoSupport() {
  // dil seçimi ya da ilk kurulum ekranı açıksa bekler: üst üste iki pencere açılmasın
  const busy = ["#langOverlay", "#setupOverlay", "#authOverlay"].some((s) => !$(s).classList.contains("hidden"));
  if (busy) return setTimeout(autoSupport, 1200);
  openSupport();
  api.support_seen();
}
function wireSupport() {
  const close = () => $("#supportOverlay").classList.add("hidden");
  $("#supportBtn").addEventListener("click", openSupport);
  $("#supportSettingsBtn").addEventListener("click", openSupport);
  $("#supportClose").addEventListener("click", close);
  $("#supportLater").addEventListener("click", close);
  $("#supportGo").addEventListener("click", () => api.open_url("support_github"));
  $("#supportDonate").addEventListener("click", () => api.open_url("support_donate"));
  $("#supportOverlay").addEventListener("click", (e) => { if (e.target.id === "supportOverlay") close(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#supportOverlay").classList.contains("hidden")) close(); });
}

/* ---------------------------------------------------------------- kenar çubuğu */
// Sabit ya da otomatik gizlenen: gizliyken fare kenara gelince içeriğin üstünde açılır, panel düğmesiyle yeniden sabitlenir.
let sidebarTimer = 0;
const sidebarHidden = () => $(".app").classList.contains("sb-auto") && !$(".app").classList.contains("sb-peek");
function applySidebar(mode, instant = false) {
  const app = $(".app"), auto = mode === "auto";
  if (segs.sidebarSeg) segs.sidebarSeg.set(auto ? "auto" : "pinned");
  if (app.classList.contains("sb-auto") === auto) return;
  if (instant) app.classList.add("sb-instant");
  app.classList.toggle("sb-auto", auto);
  app.classList.remove("sb-peek");
  if (instant) { void app.offsetWidth; app.classList.remove("sb-instant"); }
  setTimeout(() => Object.values(segs).forEach((s) => s.refresh()), instant ? 30 : 480);  // sayfa genişliği değişti
}
function setSidebar(mode) { applySidebar(mode); setSetting("sidebar", mode); }
function peekSidebar(open, delay = 0) {
  clearTimeout(sidebarTimer);
  sidebarTimer = setTimeout(() => $(".app").classList.toggle("sb-peek", open && $(".app").classList.contains("sb-auto")), delay);
}
function wireMobile() {
  // telefon: menü düğmesi kenar çubuğunu çekmece olarak açar; bir sayfa seçilince ya da dışarı dokununca kapanır
  const app = $(".app");
  $("#mMenuBtn").addEventListener("click", () => app.classList.toggle("m-open"));
  $("#mScrim").addEventListener("click", () => app.classList.remove("m-open"));
  $$(".nav-item").forEach((n) => n.addEventListener("click", () => app.classList.remove("m-open")));
  $("#mQueueBtn").addEventListener("click", () => showPage("queue"));
}
function wireSidebar() {
  $("#sbHide").addEventListener("click", () => setSidebar("auto"));
  $("#sbPin").addEventListener("click", () => setSidebar("pinned"));
  $("#sbHandle").addEventListener("click", () => setSidebar("pinned"));
  // kenardan geçerken kazara açılmasın diye kısa bir bekleme; kenar çubuğundan çıkınca biraz sonra kapanır
  $("#sbEdge").addEventListener("mouseenter", () => peekSidebar(true, 90));
  $("#sbEdge").addEventListener("mouseleave", () => { if (!$(".app").classList.contains("sb-peek")) peekSidebar(false); });
  $("#sidebar").addEventListener("mouseenter", () => peekSidebar(true));
  $("#sidebar").addEventListener("mouseleave", () => peekSidebar(false, 280));
  $$(".nav-item").forEach((n) => n.addEventListener("click", () => peekSidebar(false, 160)));
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === "b") {
      e.preventDefault();
      setSidebar($(".app").classList.contains("sb-auto") ? "pinned" : "auto");
    }
  });
}

/* ---------------------------------------------------------------- tema */
const THEMES = ["mono", "paper", "violet", "ocean"];
const FONTS = ["serif", "grotesk", "wide", "soft"];  // Instrument Serif, Bricolage Grotesque, Unbounded, Fraunces
function applyFont(f) {
  document.documentElement.dataset.font = FONTS.includes(f) ? f : "grotesk";
  $$(".font-opt").forEach((o) => o.classList.toggle("on", o.dataset.fontOpt === document.documentElement.dataset.font));
}
function applyTheme(t) {
  document.documentElement.dataset.theme = THEMES.includes(t) ? t : "mono";
  $$(".theme-opt").forEach((o) => o.classList.toggle("on", o.dataset.themeOpt === document.documentElement.dataset.theme));
}

/* ================================================================ İNDİR */
const URL_RE = /^https?:\/\/\S+$/i;

function dlView(which) {
  for (const id of ["dlEmpty", "dlLoading", "dlError", "dlResult"]) $("#" + id).classList.toggle("hidden", id !== which);
}

async function analyze(url) {
  url = (url ?? $("#urlInput").value).trim();
  if (!URL_RE.test(url)) { toast("Geçerli bir link girin (http:// veya https:// ile başlamalı).", "err"); return; }
  $("#urlInput").value = url;
  const token = ++state.analyzeToken;
  showPage("download");
  dlView("dlLoading");
  $("#dlLoadingText").lastChild.textContent = tr("Link analiz ediliyor…");
  setLoading($("#analyzeBtn"), true);
  await api.analyze(url, token);
}

function onAnalyzed(ev) {
  if (ev.token !== state.analyzeToken) return;
  setLoading($("#analyzeBtn"), false);
  const m = ev.info;
  state.media = m;
  state.mediaUrl = ev.url;
  state.extSub = null;

  const img = $("#mThumb");
  if (m.thumb) { img.src = m.thumb; img.classList.remove("hidden"); $("#mThumbPh").classList.add("hidden"); }
  else { img.removeAttribute("src"); img.classList.add("hidden"); $("#mThumbPh").classList.remove("hidden"); }
  $("#mDur").textContent = tr(m.duration_text || "");
  $("#mDur").classList.toggle("hidden", !m.duration_text);
  $("#mSite").textContent = tr(m.site || "Video");
  $("#mTitle").textContent = tr(m.title);
  $("#mUploader").textContent = tr(m.uploader || "");
  const nq = m.qualities.length - 1;
  $("#mBadge").textContent = tr(m.is_playlist ? `Oynatma listesi · ${m.entry_count} öğe` : m.audio_only ? "Ses kaynağı" : nq ? `${nq} kalite seçeneği` : "İndirilebilir");
  $("#mSubs").textContent = tr(m.subtitles.length ? `${m.subtitles.length} altyazı` : "");
  $("#mSubs").classList.toggle("hidden", !m.subtitles.length);
  for (const id of ["mAiBtn", "mWatchBtn", "mCommentsBtn", "mSimilarBtn", "mReelsBtn", "mDubBtn", "mCoverBtn"]) $("#" + id).classList.toggle("hidden", m.is_playlist);
  $("#mThumbBtn").classList.toggle("hidden", m.is_playlist || !m.thumb);
  $("#similarBox").classList.add("hidden");
  state.similarToken++;

  // kalite kutucukları
  const grid = $("#qualityGrid");
  grid.replaceChildren();
  m.qualities.forEach((q) => {
    const parts = q.label.split(/\s{2,}/);
    const head = q.height ? parts[0] : "En iyi";
    const sub = q.height ? parts.slice(1).join(" · ") || " " : "otomatik";
    const tile = h("button", { class: "q-tile", onclick: () => selectQuality(q.height) }, h("b", {}, head), h("small", {}, sub));
    tile.dataset.h = q.height ?? "";
    grid.append(tile);
  });
  selectQuality(m.qualities.length > 1 ? m.qualities[1].height : null);

  // gelişmiş formatlar
  const fs = $("#formatSelect");
  fs.replaceChildren(h("option", { value: "" }, "Kullanma (yukarıdaki kaliteyi kullan)"));
  m.formats.forEach((f) => fs.append(h("option", { value: f.spec }, f.label)));
  $("#advDetails").classList.toggle("hidden", !m.formats.length);
  $("#advDetails").open = false;

  // altyazılar: önce elle yazılmış, sonra Türkçe/İngilizce otomatik
  const ss = $("#subSelect");
  ss.replaceChildren(h("option", { value: "" }, m.subtitles.length ? "Yok" : "Bu videoda altyazı yok"));
  const order = (s) => [s.auto ? 1 : 0, s.lang.startsWith("tr") ? 0 : s.lang.startsWith("en") ? 1 : 2, s.label.toLowerCase()];
  m.subtitles.map((s, i) => ({ ...s, i })).sort((a, b) => {
    const x = order(a), y = order(b);
    return x[0] - y[0] || x[1] - y[1] || (x[2] < y[2] ? -1 : 1);
  }).forEach((s) => ss.append(h("option", { value: s.i }, s.label)));
  ss.value = "";
  updateExtSub();

  segs.modeSeg.set(m.audio_only ? "audio" : "video");
  updateMode();
  segs.containerSeg.set(state.settings.container || "mp4");
  segs.audioFmtSeg.set(state.settings.audio_format || "mp3");
  segs.audioQSeg.set(state.settings.audio_quality || "320");
  segs.subModeSeg.set("embed");
  $("#aiSubToggle").checked = false;
  updateAiSub();
  updateSubHint();

  $("#trimToggle").checked = false; $("#trimRow").classList.add("hidden");
  $("#trimStart").value = ""; $("#trimEnd").value = "";
  $("#trimToggle").closest(".row").classList.toggle("hidden", m.is_playlist);
  $("#manualSubBox").classList.toggle("hidden", m.is_playlist);
  // tek video bir listenin parçasıysa: tüm listeyi indir anahtarı + listeyi açıp seçme
  $("#playlistRow").classList.toggle("hidden", !m.has_playlist_param);
  $("#playlistToggle").checked = false;
  $("#plOpenBtn").classList.toggle("hidden", !listUrlOf(state.mediaUrl));
  $("#playlistHint").textContent = tr("Bu link bir listenin parçası. Açarsan listedeki tüm videolar indirilir.");
  renderPlaylist(m);

  dlView("dlResult");
  updateSummary();
}

/* ---------------------------------------------------------------- oynatma listesi */
function listUrlOf(url) {
  try {
    const u = new URL(url);
    const id = u.searchParams.get("list");
    return id && /(^|\.)youtube\.com$|(^|\.)youtu\.be$/.test(u.hostname) ? `https://www.youtube.com/playlist?list=${id}` : null;
  } catch { return null; }
}

function renderPlaylist(m) {
  $("#plCard").classList.toggle("hidden", !m.is_playlist);
  $("#downloadAllBtn").classList.toggle("hidden", !m.is_playlist);
  state.plSel = new Set(m.is_playlist ? m.entries.filter((e) => e.available).map((e) => e.index) : []);
  $("#plSearch").value = "";
  if (!m.is_playlist) return;
  $("#plList").replaceChildren(...m.entries.map((e) => {
    const box = h("input", { type: "checkbox" });
    box.checked = state.plSel.has(e.index);
    box.addEventListener("change", () => { box.checked ? state.plSel.add(e.index) : state.plSel.delete(e.index); updateSummary(); });
    const img = e.thumb ? h("img", { src: e.thumb, alt: "", loading: "lazy", referrerpolicy: "no-referrer" }) : null;
    if (img) img.addEventListener("error", () => img.replaceWith(h("div", { class: "ph" }, icon("film"))));
    const row = h("label", { class: "pl-row" + (e.available ? "" : " off"), title: e.title },
      box, h("span", { class: "cb" }, icon("check")), h("span", { class: "idx" }, String(e.index)),
      h("div", { class: "pl-thumb" }, img || h("div", { class: "ph" }, icon("film")), e.duration ? h("span", { class: "dur" }, e.duration) : null),
      h("div", { class: "t" }, h("b", {}, e.title || e.url), h("small", {}, e.channel || "")));
    row.dataset.q = (e.title + " " + e.channel).toLocaleLowerCase("tr");
    row.dataset.i = e.index;
    return row;
  }));
}

function plVisibleRows() { return $$("#plList .pl-row").filter((r) => !r.classList.contains("hidden")); }

function plSelect(on) {
  for (const row of plVisibleRows()) {
    const i = Number(row.dataset.i);
    row.querySelector("input").checked = on;
    on ? state.plSel.add(i) : state.plSel.delete(i);
  }
  updateSummary();
}

function plFilter() {
  const q = $("#plSearch").value.trim().toLocaleLowerCase("tr");
  for (const row of $$("#plList .pl-row")) row.classList.toggle("hidden", !!q && !row.dataset.q.includes(q));
}

function onAnalyzeError(ev) {
  if (ev.token !== state.analyzeToken) return;
  setLoading($("#analyzeBtn"), false);
  $("#dlErrorText").textContent = tr(ev.message);
  dlView("dlError");
}

function selectQuality(height) {
  state.quality = height;
  $$("#qualityGrid .q-tile").forEach((t) => t.classList.toggle("on", t.dataset.h === String(height ?? "")));
  updateSummary();
}

function updateMode() {
  const audio = segs.modeSeg.value === "audio";
  $("#videoOpts").classList.toggle("hidden", audio);
  $("#audioOpts").classList.toggle("hidden", !audio);
  $("#subCard").classList.toggle("hidden", audio);
  $("#audioQBlock").classList.toggle("hidden", ["wav", "flac"].includes(segs.audioFmtSeg.value));
  setTimeout(() => Object.values(segs).forEach((s) => s.refresh()), 20);
  updateSummary();
}

const SUB_HINTS = {
  embed: "Altyazı videonun içine ayrı bir iz olarak eklenir; oynatıcıdan açıp kapatabilirsin.",
  burn: "Altyazı görüntüye kalıcı yazılır, her cihazda görünür. Video yeniden işlendiği için biraz sürer; çıktı MP4 olur.",
  file: "Altyazı videonun yanına aynı isimle .srt dosyası olarak kaydedilir.",
};
function updateSubHint() { $("#subHint").textContent = tr(SUB_HINTS[segs.subModeSeg.value] || ""); updateSummary(); }

function updateExtSub() {
  const n = $("#extSubName");
  n.textContent = tr(state.extSub ? state.extSub.split(/[\\/]/).pop() : "Seçilmedi (.srt, .vtt, .ass)");
  n.classList.toggle("set", !!state.extSub);
  updateSummary();
}

function updateSummary() {
  const m = state.media;
  if (!m) return;
  const audio = segs.modeSeg.value === "audio";
  let main;
  if (audio) {
    const f = segs.audioFmtSeg.value || "mp3";
    main = f.toUpperCase() + (["wav", "flac"].includes(f) ? " (kayıpsız)" : ` · ${segs.audioQSeg.value} kbps`);
  } else {
    const fmt = $("#advDetails").open && $("#formatSelect").value;
    main = (fmt ? "Özel format" : state.quality ? `${state.quality}p` : "En iyi kalite") + " · " + (segs.containerSeg.value || "mp4").toUpperCase();
    const ai = $("#aiSubToggle").checked;
    const sub = ai || $("#subSelect").value !== "" || state.extSub;
    if (sub) main += ` · ${ai ? "AI altyazı (" + $("#aiSubLang").selectedOptions[0]?.textContent + ")" : "altyazı"} `
      + ({ embed: "gömülü", burn: "yakılmış", file: ".srt" })[segs.subModeSeg.value];
  }
  if ($("#trimToggle").checked) main += " · kesit";
  if ($("#playlistToggle").checked && !$("#playlistRow").classList.contains("hidden")) main += " · tüm liste";
  const label = $("#downloadBtn span");
  if (m.is_playlist) {
    const n = state.plSel.size, total = m.entries.length;
    main = `${n} / ${total} video seçili · ` + main;
    $("#plCount").textContent = tr(`${n} / ${total} seçili`);
    label.textContent = tr(n ? `Seçilenleri indir (${n})` : "Video seçin");
    $("#downloadBtn").disabled = !n;
    $("#downloadAllBtn span").textContent = tr(`Hepsini indir (${m.entries.filter((e) => e.available).length})`);
  } else {
    label.textContent = tr("İndir");
    $("#downloadBtn").disabled = false;
  }
  $("#dlSummary").textContent = tr(main);
  $("#dlSummary2").textContent = tr("Kayıt:") + " " + (state.settings.download_dir || "");
}

async function startDownload(all = false) {
  const m = state.media;
  if (!m) return;
  if (m.is_playlist && !all && !state.plSel.size) { toast("Listeden en az bir video seçin.", "err"); return; }
  const audio = segs.modeSeg.value === "audio";
  const subVal = $("#subSelect").value;
  const opts = {
    source_url: state.mediaUrl,
    mode: audio ? "audio" : "video",
    height: state.quality,
    format_spec: $("#advDetails").open ? $("#formatSelect").value || null : null,
    container: segs.containerSeg.value,
    audio_format: segs.audioFmtSeg.value,
    audio_quality: segs.audioQSeg.value,
    sub_index: subVal === "" ? null : Number(subVal),
    sub_mode: segs.subModeSeg.value,
    external_sub: state.extSub,
    ai_sub: !audio && $("#aiSubToggle").checked ? $("#aiSubLang").value : null,
    trim: $("#trimToggle").checked,
    trim_start: $("#trimStart").value,
    trim_end: $("#trimEnd").value,
    playlist: !m.is_playlist && $("#playlistToggle").checked,
    items: m.is_playlist ? (all ? "all" : [...state.plSel].sort((a, b) => a - b)) : null,
  };
  const btn = all ? $("#downloadAllBtn") : $("#downloadBtn");
  setLoading(btn, true);
  const res = await api.download(opts);
  setLoading(btn, false);
  updateSummary();
  if (!res.ok) { toast(res.error, "err"); return; }
  const what = res.count > 1 ? `${res.count} video sıraya alındı` : "İndirme başladı";
  toast(state.setup === "ready" ? what : "Sıraya alındı — bileşenler kurulunca başlayacak", "ok");
  flyToQueue(btn);
}

function flyToQueue(from, page = "queue") {
  // düğmeden menüdeki sayfaya ("İndirmeler", "İzleme listesi") uçan küçük nokta
  // kenar çubuğu gizliyse kenardaki tutamağa uçar
  const hidden = sidebarHidden();
  const a = from.getBoundingClientRect(), b = $(hidden ? "#sbHandle" : `.nav-item[data-page="${page}"]`).getBoundingClientRect();
  const dot = h("div");
  dot.style.cssText = `position:fixed;z-index:60;width:16px;height:16px;border-radius:50%;background:var(--grad);box-shadow:var(--glow);left:${a.left + a.width / 2}px;top:${a.top + a.height / 2}px;transition:all .75s cubic-bezier(.5,-0.3,.3,1);pointer-events:none`;
  document.body.append(dot);
  requestAnimationFrame(() => { dot.style.left = (hidden ? b.left : b.left + 40) + "px"; dot.style.top = b.top + b.height / 2 + "px"; dot.style.transform = "scale(.4)"; dot.style.opacity = ".2"; });
  setTimeout(() => dot.remove(), 800);
}

async function quick(mode) {
  const url = $("#urlInput").value.trim();
  const res = await api.quick(url, mode);
  if (!res.ok) { toast(res.error, "err"); return; }
  toast(mode === "audio" ? "MP3 olarak indiriliyor" : "En iyi kalitede indiriliyor", "ok");
  flyToQueue(mode === "audio" ? $("#quickAudioBtn") : $("#quickBtn"));
}

/* ================================================================ İNDİRMELER */
function upsertItem(it) {
  state.items.set(it.id, it);
  renderQueue();
}

function itemCard(it) {
  const indet = it.state === "running" && (it.frac === null || it.frac === undefined);
  const pct = it.state === "done" ? 100 : Math.round((it.frac || 0) * 100);
  const stats = [];
  if (it.state === "running" && !indet) stats.push(`%${pct}`);
  if (it.size) stats.push(it.size);
  if (it.speed) stats.push(it.speed);
  if (it.eta) stats.push("kalan " + it.eta);
  if (it.state === "done" && it.file) stats.push(it.file);

  const acts = h("div", { class: "q-actions" });
  if (it.state === "done") {
    acts.append(h("button", { class: "btn success icon", title: "Aç", onclick: () => api.open_item(it.id) }, icon("play")));
    acts.append(h("button", { class: "btn icon rv", title: "Klasörde göster", onclick: () => api.reveal_item(it.id) }, icon("folder")));
  }
  if (it.state === "error" || it.state === "cancelled")
    acts.append(h("button", { class: "btn icon", title: "Tekrar dene", onclick: () => api.retry(it.id) }, icon("retry")));
  if (it.state === "running" || it.state === "pending")
    acts.append(h("button", { class: "btn icon danger", title: "İptal", onclick: () => api.cancel(it.id) }, icon("x")));
  else
    acts.append(h("button", { class: "btn icon danger", title: "Listeden kaldır", onclick: () => api.remove(it.id) }, icon("trash")));

  const thumb = h("div", { class: "q-thumb" }, it.thumb ? h("img", { src: it.thumb, alt: "" }) : icon("film"));
  const bar = h("div", { class: "progress" + (indet ? " indet" : "") }, h("i"));
  bar.firstChild.style.width = (indet ? 35 : pct) + "%";
  return h("div", { class: `card q-card ${it.state}`, "data-id": it.id },
    thumb,
    h("div", { class: "q-body" },
      h("div", { class: "t", title: it.title }, it.title),
      h("div", { class: "s" }, h("span", { class: "st" }, it.stage), h("span", {}, it.summary)),
      it.state === "error" ? null : bar,
      stats.length ? h("div", { class: "stats" }, ...stats.map((s) => h("span", {}, s))) : null,
      (it.state === "error" || it.state === "done") && it.error ? h("div", { class: "err" }, it.error) : null),
    acts);
}

const FILTERS = {
  all: () => true,
  active: (it) => it.state === "running" || it.state === "pending",
  done: (it) => it.state === "done",
  failed: (it) => it.state === "error" || it.state === "cancelled",
};

function renderQueue() {
  const list = $("#queueList");
  const items = [...state.items.values()].reverse().filter(FILTERS[state.queueFilter]);
  const existing = new Map([...list.children].map((c) => [c.dataset.id, c]));
  const fresh = items.map((it) => {
    const card = itemCard(it);
    const old = existing.get(it.id);
    if (old) card.style.animation = "none";  // yalnızca yeni kartlar kayarak girsin
    return card;
  });
  list.replaceChildren(...fresh);
  $("#queueEmpty").classList.toggle("hidden", items.length > 0);
  const active = [...state.items.values()].filter(FILTERS.active).length;
  const badge = $("#queueBadge");
  badge.textContent = tr(active);
  badge.classList.toggle("hidden", !active);
  $("#sbHandle").classList.toggle("busy", active > 0);
  $("#mQueueBadge").textContent = tr(active);
  $("#mQueueBadge").classList.toggle("hidden", !active);
  $("#queueSub").textContent = tr(active ? `${active} indirme devam ediyor.` : "Kuyruktaki ve biten indirmeler.");
}

/* ================================================================ AI */
const AI_MODES = {
  summary: {
    sub: "İzlemeden önce videonun ne anlattığını öğren.",
    placeholder: "Özetlenecek video linki…", button: "Özetle", icon: "link",
    hint: "Altyazı varsa konuşmanın tamamı okunur; yoksa (X/Twitter gibi) ses bilgisayarında yazıya dökülüp özetlenir.",
    steps: ["Video bilgileri alınıyor", "Konuşma dökümü çıkarılıyor", "Yapay zekâ videoyu özetliyor"],
  },
  comments: {
    sub: "İzleyiciler neyi beğenmiş, neyi eleştirmiş, hangi sorunu nasıl çözmüş; tek bakışta.",
    placeholder: "Yorumları özetlenecek video linki…", button: "Yorumları özetle", icon: "link",
    hint: "En çok beğenilen 300 yorum okunur. Şu an en iyi YouTube videolarında çalışır.",
    steps: ["Yorumlar alınıyor", "Yapay zekâ yorumları özetliyor"],
  },
  ideas: {
    sub: "Bir video linki ver ya da aklındaki konuyu yaz; yapay zekâ özgün içerik fikirleri çıkarsın.",
    placeholder: "Video linki ya da konu: ör. evde 10 dakikalık sabah sporu…", button: "Fikir üret", icon: "bulb",
    hint: "Linkten benzer ama kopya olmayan fikirler; yazdığın konudan ise başlık, açılış cümlesi ve akış önerileri.",
    steps: ["Video bilgileri alınıyor", "Yapay zekâ fikir üretiyor"],
  },
};
// altyazısız videolarda (X/Twitter gibi) araya giren adımlar
const WHISPER_STEPS = ["Videonun sesi indiriliyor", "Konuşma yazıya dökülüyor"];
let aiModeSeg = null;

function aiView(which) {
  for (const id of ["aiLoading", "aiError", "aiResult"]) $("#" + id).classList.toggle("hidden", id !== which);
}

function setAiMode(mode) {
  state.aiMode = mode;
  const m = AI_MODES[mode];
  $("#aiSub").textContent = tr(m.sub);
  $("#aiUrl").placeholder = tr(m.placeholder);
  $("#aiHint").textContent = tr(m.hint);
  $("#aiBtn").querySelector("span").textContent = tr(m.button);
  $("#aiUrl").parentElement.querySelector("svg.ic").replaceWith(icon(m.icon));
}

function renderSteps(current) {
  if (!state.aiSteps.includes(current) && WHISPER_STEPS.includes(current))
    state.aiSteps.splice(state.aiSteps.length - 1, 0, ...WHISPER_STEPS);
  const steps = state.aiSteps;
  const idx = steps.indexOf(current);
  $("#aiSteps").replaceChildren(...steps.map((s, i) =>
    h("div", { class: "ai-step" + (i < idx ? " done" : i === idx ? " active" : "") },
      h("span", { class: "b" }, i < idx ? icon("check") : String(i + 1)), s)));
}

async function aiRun(mode, text) {
  if (mode) aiModeSeg.set(mode, false);
  mode = state.aiMode;
  text = (text ?? $("#aiUrl").value).trim();
  $("#aiUrl").value = text;
  showPage("ai");
  if (!state.keys[currentProvider()]) { $("#aiNoKey").classList.remove("hidden"); toast("Önce Ayarlar'dan API anahtarını ekle.", "err"); return; }
  const isUrl = URL_RE.test(text);
  if (mode === "ideas" ? !text : !isUrl) { toast(mode === "ideas" ? "Bir link ya da konu yazın." : "Geçerli bir video linki girin.", "err"); return; }
  const token = ++state.aiToken;
  state.aiSteps = [...AI_MODES[mode].steps];
  if (mode === "ideas" && !isUrl) state.aiSteps.shift();
  const cached = state.media && state.mediaUrl === text;
  aiView("aiLoading");
  renderSteps(state.aiSteps[mode === "summary" && cached ? 1 : 0]);
  setLoading($("#aiBtn"), true);
  if (!(await api.ai_run(mode, text, token))) { setLoading($("#aiBtn"), false); aiView(null); toast("Geçersiz istek.", "err"); }
}

const bullets = (items) => items.length ? items.map((t) => h("li", {}, t)) : [h("li", { class: "none" }, "Belirgin bir şey yok")];
function numbered(items) {
  return items.map((p, i) => {
    const li = h("li", {}, h("span", { class: "n" }, String(i + 1)), h("span", {}, p));
    li.style.animationDelay = i * 70 + "ms";
    return li;
  });
}

function onAiDone(ev) {
  if (ev.token !== state.aiToken) return;
  setLoading($("#aiBtn"), false);
  const r = ev.result;
  state.aiResult = r;
  $("#aiThumb").classList.toggle("hidden", !r.thumb);
  if (r.thumb) $("#aiThumb").src = r.thumb;
  $("#aiTitle").textContent = tr(r.title);
  for (const [id, m] of [["aiBodySummary", "summary"], ["aiBodyComments", "comments"], ["aiBodyIdeas", "ideas"]])
    $("#" + id).classList.toggle("hidden", r.mode !== m);
  $("#aiDownload").classList.toggle("hidden", !URL_RE.test($("#aiUrl").value.trim()));

  if (r.mode === "summary") {
    $("#aiSource").textContent = tr(r.provider + " · Kaynak: " + r.source + (r.words ? ` · ${r.words.toLocaleString("tr-TR")} kelime` : ""));
    $("#aiTldr").textContent = tr(r.tldr);
    $("#aiSummary").textContent = tr(r.summary);
    $("#aiPoints").replaceChildren(...numbered(r.key_points));
    $("#aiTopics").replaceChildren(...r.topics.map((t) => h("span", { class: "chip accent" }, "#" + t)));
  } else if (r.mode === "comments") {
    $("#aiSource").textContent = r.provider + " · " + tr(`${r.count.toLocaleString("tr-TR")} yorum okundu`);  // servis adı çevrilmez
    $("#aiTldr").textContent = tr(r.genel_hava);
    $("#cLikes").replaceChildren(...bullets(r.begenilenler));
    $("#cDislikes").replaceChildren(...bullets(r.begenilmeyenler));
    $("#cIssuesBox").classList.toggle("hidden", !r.sorunlar.length);
    $("#cIssues").replaceChildren(...r.sorunlar.map((x, i) => {
      const el = h("div", { class: "issue" },
        h("div", { class: "p" }, h("small", {}, "Sorun"), x.sorun),
        h("div", { class: "s" }, h("small", {}, "Çözüm"), x.cozum));
      el.style.animationDelay = i * 70 + "ms";
      return el;
    }));
    $("#cThemesBox").classList.toggle("hidden", !r.one_cikanlar.length);
    $("#cThemes").replaceChildren(...numbered(r.one_cikanlar));
    $("#cQuestionsBox").classList.toggle("hidden", !r.sorular.length);
    $("#cQuestions").replaceChildren(...numbered(r.sorular));
    $("#cSummary").textContent = tr(r.ozet);
  } else {
    $("#aiSource").textContent = r.provider + " · " + tr(`${r.fikirler.length} fikir`);
    $("#aiTldr").textContent = tr(r.ozet);
    $("#ideaGrid").replaceChildren(...r.fikirler.map((f, i) => {
      const el = h("div", { class: "idea" },
        h("div", { class: "top" }, h("span", { class: "n" }, String(i + 1)), h("h4", {}, f.baslik)),
        h("span", { class: "chip accent" }, f.format),
        h("p", { class: "hook" }, "“" + f.kanca + "”"),
        h("ol", {}, f.akis.map((a) => h("li", {}, a))),
        h("p", { class: "why" }, f.neden));
      el.style.animationDelay = i * 70 + "ms";
      return el;
    }));
  }
  aiView("aiResult");
  toast({ summary: "Özet hazır", comments: "Yorum özeti hazır", ideas: "Fikirler hazır" }[r.mode], "ok");
}

function aiResultText(r) {
  const list = (title, items) => items.length ? `\n\n${title}\n` + items.map((x) => `- ${x}`).join("\n") : "";
  if (r.mode === "summary")
    return `${r.title}\n\n${r.tldr}\n\n${r.summary}\n\n` + r.key_points.map((p, i) => `${i + 1}. ${p}`).join("\n");
  if (r.mode === "comments")
    return `${r.title} (yorum özeti)\n\n${r.genel_hava}` + list("Beğenilenler", r.begenilenler) +
      list("Beğenilmeyenler", r.begenilmeyenler) +
      list("Sorunlar ve çözümleri", r.sorunlar.map((x) => `${x.sorun} → ${x.cozum}`)) +
      list("Öne çıkanlar", r.one_cikanlar) + list("Sık sorulan sorular", r.sorular) + `\n\n${r.ozet}`;
  return `${r.title} (video fikirleri)\n\n${r.ozet}\n\n` + r.fikirler.map((f, i) =>
    `${i + 1}. ${f.baslik} (${f.format})\nAçılış: "${f.kanca}"\n` + f.akis.map((a) => `   - ${a}`).join("\n") + `\nNeden: ${f.neden}`).join("\n\n");
}

function onAiError(ev) {
  if (ev.token !== state.aiToken) return;
  setLoading($("#aiBtn"), false);
  $("#aiErrorText").textContent = tr(ev.message);
  aiView("aiError");
}

/* ================================================================ KAPAK + BENZER VİDEOLAR */
async function downloadThumb() {
  const b = $("#mThumbBtn");
  setLoading(b, true);
  const res = await api.download_thumbnail(state.mediaUrl);
  setLoading(b, false);
  if (!res.ok) { toast(res.error, "err"); return; }
  toast(`Kapak kaydedildi (${res.size})`, "ok");
  api.reveal_file(res.path);
}

async function showSimilar() {
  const box = $("#similarBox");
  const token = ++state.similarToken;
  box.classList.remove("hidden");
  $("#similarGrid").replaceChildren(...Array.from({ length: 8 }, () =>
    h("div", { class: "sim" }, h("div", { class: "sk thumb" }), h("div", { class: "sk line", style: "margin-top:10px" }), h("div", { class: "sk line", style: "margin-top:8px;width:55%" }))));
  box.scrollIntoView({ behavior: "smooth", block: "start" });
  setLoading($("#mSimilarBtn"), true);
  if (!(await api.similar(state.mediaUrl, token))) { setLoading($("#mSimilarBtn"), false); box.classList.add("hidden"); }
}

function onSimilar(ev) {
  if (ev.token !== state.similarToken) return;
  setLoading($("#mSimilarBtn"), false);
  const grid = $("#similarGrid");
  if (!ev.items.length) { grid.replaceChildren(h("p", { class: "sim-empty" }, ev.error || "Benzer video bulunamadı.")); return; }
  grid.replaceChildren(...ev.items.map((v, i) => {
    const img = v.thumb ? h("img", { src: v.thumb, alt: "" }) : h("div", { class: "ph" }, icon("film"));
    const open = () => { $("#urlInput").value = v.url; analyze(v.url); $("#main").scrollTo({ top: 0, behavior: "smooth" }); };
    const el = h("button", { class: "sim", title: v.title, onclick: open },
      h("div", { class: "thumb" }, img, v.duration ? h("span", { class: "dur" }, v.duration) : null),
      h("b", {}, v.title), h("small", {}, v.channel));
    el.style.animationDelay = i * 40 + "ms";
    return el;
  }));
}

/* ================================================================ GEÇMİŞ */
function renderHistory() {
  const q = $("#historySearch").value.trim().toLocaleLowerCase("tr");
  const rows = state.history.map((e, i) => ({ e, i }))
    .filter(({ e }) => !q || (e.title || "").toLocaleLowerCase("tr").includes(q));
  $("#historyList").replaceChildren(...rows.map(({ e, i }) =>
    h("div", { class: "h-row" },
      h("div", { class: "ico" }, icon(/MP3|M4A|OPUS|FLAC|WAV/.test(e.kind || "") ? "music" : "film")),
      h("div", { class: "txt" }, h("b", { title: e.title }, e.title), h("small", {}, `${e.date || ""} · ${e.kind || ""}`)),
      h("div", { class: "acts" },
        h("button", { class: "btn icon success", title: "Aç", onclick: () => api.open_history(i) }, icon("play")),
        h("button", { class: "btn icon rv", title: "Klasörde göster", onclick: () => api.reveal_history(i) }, icon("folder"))))));
  $("#historyEmpty").classList.toggle("hidden", rows.length > 0);
}

/* ================================================================ AYARLAR */
async function setSetting(key, value) {
  state.settings = await api.set_setting(key, value);
  if (key === "theme") applyTheme(value);
  updateSummary();
}

function renderSettings() {
  const s = state.settings;
  $("#setFolder").textContent = tr(s.download_dir);
  $("#folderText").textContent = tr(s.download_dir);
  applyTheme(s.theme);
  applyFont(s.font);
  applySidebar(s.sidebar, true);
  segs.parallelSeg.set(s.max_parallel);
  segs.defContainerSeg.set(s.container);
  segs.defAudioSeg.set(s.audio_format);
  segs.defAudioQSeg.set(s.audio_quality);
  $("#rateInput").value = s.rate_limit || "";
  $("#cookiesSelect").value = s.cookies_browser || "Yok";
  $$("input[data-setting]").forEach((i) => { i.checked = !!s[i.dataset.setting]; });
  segs.providerSeg.set(currentProvider());
  segs.whisperSeg.set(s.whisper_model || "small");
  renderKey();
}

const currentProvider = () => state.settings.ai_provider || "gemini";
const PROVIDER_INFO = {
  // çeviri tablosunda tek anahtar olsun diye ipuçları tek parça yazıldı
  gemini: { hint: "Ücretsiz: Google hesabınla aistudio.google.com/apikey adresinden kredi kartı olmadan anahtar al. Ücretsiz katmanda Google gönderilen metni ürünlerini geliştirmek için kullanabilir.",
            placeholder: "AIza…", link: "gemini_keys" },
  claude: { hint: "Ücretli ama çok ucuz (10 dakikalık video özeti ~0,001 $). Anahtarı console.anthropic.com'dan al; ücret kendi Anthropic hesabından düşer.",
            placeholder: "sk-ant-…", link: "anthropic_keys" },
};

function renderKey() {
  const p = currentProvider(), info = PROVIDER_INFO[p], has = !!state.keys[p];
  $("#providerHint").replaceChildren(tr(info.hint) + " ",
    h("a", { href: "#", style: "color:var(--accent-2)", onclick: (e) => { e.preventDefault(); api.open_url(info.link); } }, "Anahtar al →"));
  $("#apiKeyInput").placeholder = tr(info.placeholder);
  const name = state.providers[p] || p;
  $("#keyStatus").textContent = has ? tr("✓ {name} anahtarı kayıtlı", { name }) : tr("{name} anahtarı eklenmedi", { name });
  $("#deleteKeyBtn").classList.toggle("hidden", !has);
  $("#aiNoKey").classList.toggle("hidden", has);
}

function updateAiSub() {
  const on = $("#aiSubToggle").checked;
  $("#aiSubBox").classList.toggle("hidden", !on);
  $("#manualSubBox").classList.toggle("hidden", on);
  updateSummary();
}

function renderTools(t) {
  if (!t) return;
  $("#tYtdlp").textContent = tr(t.ytdlp);
  $("#tFfmpeg").textContent = tr(t.ffmpeg ? "✓ Kurulu" : "✗ Eksik");
  $("#tJs").textContent = tr(t.js ? "✓ " + t.js : "✗ Eksik");
}

async function pickFolder() {
  const p = await api.pick_folder();
  if (p) { state.settings.download_dir = p; renderSettings(); updateSummary(); toast("Kayıt klasörü değişti", "ok"); }
}

/* ---------------------------------------------------------------- kurulum durumu */
function onSetup(ev) {
  state.setup = ev.state;
  const chip = $("#setupChip");
  chip.classList.toggle("busy", ev.state === "installing" || ev.state === "checking");
  chip.classList.toggle("fail", ev.state === "failed");
  $("#repairRow").classList.toggle("hidden", ev.state !== "failed");
  if (ev.state === "ready") {
    $("#setupChipText").textContent = tr("Hazır");
    if (!$("#setupOverlay").classList.contains("hidden")) {
      $("#setupOverlay").classList.add("hidden");
      toast("TekTıkla hazır! Artık her şeyi indirebilirsin.", "ok");
    }
    renderTools(ev.tools);
  } else if (ev.state === "installing") {
    $("#setupChipText").textContent = tr("Bileşenler kuruluyor…");
    if (!state.setupHidden) $("#setupOverlay").classList.remove("hidden");
    $("#setupText").textContent = tr(ev.text || "");
    $("#setupBar i").style.width = Math.round((ev.frac || 0) * 100) + "%";
    $("#setupRetry").classList.add("hidden");
  } else if (ev.state === "failed") {
    $("#setupChipText").textContent = tr("Kurulum başarısız");
    $("#setupOverlay").classList.remove("hidden");
    $("#setupTitle").textContent = tr("Kurulum tamamlanamadı");
    $("#setupText").textContent = tr(ev.text || "");
    $("#setupRetry").classList.remove("hidden");
  }
}

/* ---------------------------------------------------------------- uygulama güncellemesi */
function onAppUpdate(ev) {
  state.update = ev.update;
  if (ev.update) {
    $("#updateChip").classList.remove("hidden");
    $("#updateChipText").textContent = tr(`Güncelleme var: v${ev.update.version}`);
    $("#updateStatus").textContent = tr(`Yeni sürüm: v${ev.update.version}`);
    $("#updateNotes").textContent = tr(ev.update.notes || "");
    $("#installUpdateBtn").classList.remove("hidden");
    if (!ev.manual) toast(`TekTıkla v${ev.update.version} yayınlandı`, "info");
  } else if (ev.manual) {
    setLoading($("#checkUpdateBtn"), false);
    $("#updateStatus").textContent = tr(ev.error ? "Kontrol edilemedi" : "TekTıkla güncel");
    $("#updateNotes").textContent = tr(ev.error || "");
  }
  setLoading($("#checkUpdateBtn"), false);
}

/* ---------------------------------------------------------------- olay döngüsü */
const HANDLERS = {
  analyzed: onAnalyzed,
  analyze_error: onAnalyzeError,
  analyze_wait: (ev) => { if (ev.token === state.analyzeToken) $("#dlLoadingText").lastChild.textContent = tr("Bileşenler kuruluyor, bitince analiz başlayacak…"); },
  item: (ev) => upsertItem(ev.item),
  removed: (ev) => { state.items.delete(ev.id); renderQueue(); },
  history: (ev) => { state.history = ev.history; renderHistory(); },
  notify: (ev) => toast(ev.text, ev.kind),
  setup: onSetup,
  clipboard: (ev) => {
    if (ev.url === $("#urlInput").value.trim()) return;
    toast("Link algılandı, analiz ediliyor", "info");
    analyze(ev.url);
  },
  ai_stage: (ev) => { if (ev.token === state.aiToken) renderSteps(ev.stage); },
  ai_done: onAiDone,
  similar: onSimilar,
  ai_error: onAiError,
  ytdlp: (ev) => { setLoading($("#ytdlpBtn"), false); $("#ytdlpMsg").textContent = tr(ev.message); toast(ev.message, ev.message.startsWith("Güncellenemedi") ? "err" : "ok"); },
  app_update: onAppUpdate,
  update_progress: (ev) => {
    const b = $("#installUpdateBtn");
    if (ev.error) {
      setLoading(b, false);
      toast(ev.error, "err");
      $("#updateNotes").textContent = tr(ev.error);
      if (ev.page) { state.updateFailed = true; b.lastChild.textContent = tr(" İndirme sayfasını aç"); }
      return;
    }
    b.lastChild.textContent = tr(` %${Math.round(ev.frac * 100)}`);
  },
};

async function pollLoop() {
  try {
    const events = await api.poll();
    for (const ev of events) (HANDLERS[ev.type] || (() => {}))(ev);
  } catch (e) { console.error(e); }
  setTimeout(pollLoop, 180);
}

/* ---------------------------------------------------------------- bağlantılar */
function wire() {
  seg("modeSeg", updateMode);
  seg("containerSeg", updateSummary);
  seg("audioFmtSeg", updateMode);
  seg("audioQSeg", updateSummary);
  seg("subModeSeg", updateSubHint);
  seg("providerSeg", async (v) => { await setSetting("ai_provider", v); renderKey(); });
  seg("whisperSeg", (v) => setSetting("whisper_model", v));
  seg("queueFilter", (v) => { state.queueFilter = v; renderQueue(); }).set("all");
  $$(".theme-opt").forEach((o) => o.addEventListener("click", () => setSetting("theme", o.dataset.themeOpt)));
  $$(".font-opt").forEach((o) => o.addEventListener("click", () => { applyFont(o.dataset.fontOpt); setSetting("font", o.dataset.fontOpt); }));
  seg("sidebarSeg", setSidebar);
  wireSidebar();
  wireMobile();
  wireSupport();
  seg("parallelSeg", (v) => setSetting("max_parallel", Number(v)));
  seg("defContainerSeg", (v) => setSetting("container", v));
  seg("defAudioSeg", (v) => setSetting("audio_format", v));
  seg("defAudioQSeg", (v) => setSetting("audio_quality", v));

  $("#urlInput").addEventListener("keydown", (e) => { if (e.key === "Enter") analyze(); });
  $("#pasteBtn").addEventListener("click", async () => {
    try { const t = (await navigator.clipboard.readText()).trim(); if (t) { $("#urlInput").value = t; analyze(t); } }
    catch { toast("Pano okunamadı, Ctrl+V ile yapıştırın.", "err"); }
  });
  $("#analyzeBtn").addEventListener("click", () => analyze());
  $("#quickBtn").addEventListener("click", () => quick("video"));
  $("#quickAudioBtn").addEventListener("click", () => quick("audio"));
  $("#heroAiBtn").addEventListener("click", () => aiRun("summary", $("#urlInput").value));
  $("#mAiBtn").addEventListener("click", () => aiRun("summary", state.mediaUrl));
  $("#mCommentsBtn").addEventListener("click", () => aiRun("comments", state.mediaUrl));
  $("#mThumbBtn").addEventListener("click", downloadThumb);
  $("#mSimilarBtn").addEventListener("click", showSimilar);
  $("#similarClose").addEventListener("click", () => { state.similarToken++; setLoading($("#mSimilarBtn"), false); $("#similarBox").classList.add("hidden"); });
  $("#mResetBtn").addEventListener("click", () => { state.media = null; $("#urlInput").value = ""; dlView("dlEmpty"); $("#urlInput").focus(); });
  $("#downloadBtn").addEventListener("click", () => startDownload(false));
  $("#downloadAllBtn").addEventListener("click", () => startDownload(true));
  $("#plAll").addEventListener("click", () => plSelect(true));
  $("#plNone").addEventListener("click", () => plSelect(false));
  $("#plSearch").addEventListener("input", plFilter);
  $("#plOpenBtn").addEventListener("click", () => { const u = listUrlOf(state.mediaUrl); if (u) { $("#urlInput").value = u; analyze(u); } });
  $("#subSelect").addEventListener("change", updateSummary);
  $("#formatSelect").addEventListener("change", updateSummary);
  $("#advDetails").addEventListener("toggle", updateSummary);
  $("#extSubBtn").addEventListener("click", async () => { const p = await api.pick_subtitle(); if (p) { state.extSub = p; updateExtSub(); } });
  $("#extSubClear").addEventListener("click", () => { state.extSub = null; updateExtSub(); });
  $("#trimToggle").addEventListener("change", (e) => { $("#trimRow").classList.toggle("hidden", !e.target.checked); updateSummary(); });
  $("#playlistToggle").addEventListener("change", updateSummary);
  $("#folderBtn").addEventListener("click", pickFolder);

  $("#openDirBtn").addEventListener("click", () => api.open_download_dir());
  $("#clearDoneBtn").addEventListener("click", () => api.clear_finished());

  aiModeSeg = seg("aiModeSeg", setAiMode);
  aiModeSeg.set("summary", false);
  $("#aiBtn").addEventListener("click", () => aiRun());
  $("#aiUrl").addEventListener("keydown", (e) => { if (e.key === "Enter") aiRun(); });
  $("#aiGoSettings").addEventListener("click", () => { showPage("settings"); setTimeout(() => $("#apiKeyInput").focus(), 300); });
  $("#aiCopy").addEventListener("click", async () => {
    const r = state.aiResult;
    if (!r) return;
    try { await navigator.clipboard.writeText(aiResultText(r)); toast("Panoya kopyalandı", "ok"); } catch { toast("Kopyalanamadı", "err"); }
  });
  $("#aiDownload").addEventListener("click", () => analyze($("#aiUrl").value));

  $("#historySearch").addEventListener("input", renderHistory);
  $("#clearHistoryBtn").addEventListener("click", async () => {
    if (!state.history.length || !confirm("İndirme geçmişi silinsin mi? (Dosyalar silinmez)")) return;
    state.history = await api.clear_history(); renderHistory();
  });

  $("#setFolderBtn").addEventListener("click", pickFolder);
  $("#rateInput").addEventListener("change", (e) => setSetting("rate_limit", e.target.value));
  $("#cookiesSelect").addEventListener("change", (e) => setSetting("cookies_browser", e.target.value));
  $$("input[data-setting]").forEach((i) => i.addEventListener("change", () => setSetting(i.dataset.setting, i.checked)));
  $("#saveKeyBtn").addEventListener("click", async () => {
    const res = await api.save_api_key(currentProvider(), $("#apiKeyInput").value);
    if (!res.ok) { toast(res.error, "err"); return; }
    $("#apiKeyInput").value = "";
    state.keys = res.keys; renderKey(); toast("API anahtarı kaydedildi", "ok");
  });
  $("#deleteKeyBtn").addEventListener("click", async () => { state.keys = await api.delete_api_key(currentProvider()); renderKey(); toast("API anahtarı silindi", "info"); });
  $("#aiSubToggle").addEventListener("change", updateAiSub);
  $("#aiSubLang").addEventListener("change", (e) => setSetting("ai_sub_lang", e.target.value));
  $("#ytdlpBtn").addEventListener("click", () => { setLoading($("#ytdlpBtn"), true); $("#ytdlpMsg").textContent = tr("Güncelleniyor…"); api.update_ytdlp(); });
  $("#repairBtn").addEventListener("click", () => { state.setupHidden = false; api.install_components(); });
  $("#checkUpdateBtn").addEventListener("click", () => {
    if (!state.repo) { toast("Güncelleme kaynağı (GitHub deposu) henüz ayarlanmadı.", "info"); return; }
    setLoading($("#checkUpdateBtn"), true); api.check_update();
  });
  $("#installUpdateBtn").addEventListener("click", () => {
    if (state.updateFailed) { api.open_url("releases"); return; }  // otomatik güncelleme engellendiyse elle indir
    setLoading($("#installUpdateBtn"), true); api.install_update();
  });
  $("#updateChip").addEventListener("click", () => showPage("settings"));

  $("#setupHide").addEventListener("click", () => { state.setupHidden = true; $("#setupOverlay").classList.add("hidden"); });
  $("#setupRetry").addEventListener("click", () => { $("#setupTitle").textContent = tr("TekTıkla hazırlanıyor"); api.install_components(); });
}

/* ---------------------------------------------------------------- başlangıç */
window.addEventListener("pywebviewready", async () => {
  api = window.pywebview.api;
  hydrateIcons();
  wire();
  studioWire();
  wireWatch();
  wireConvert();
  wireEditor();
  wireAccount();
  wireRemote();
  const init = await api.init();
  state.settings = init.settings;
  state.keys = init.keys;
  state.providers = init.providers;
  state.languages = init.languages;
  $("#aiSubLang").replaceChildren(...init.languages.map(([c, n]) => h("option", { value: c }, n)),
    h("option", { value: "orig" }, "Orijinal dil (çevirmeden)"));
  $("#aiSubLang").value = init.settings.ai_sub_lang || "tr";
  state.history = init.history;
  state.repo = init.repo;
  applyTheme(state.settings.theme);
  init.items.forEach((it) => state.items.set(it.id, it));
  $("#versionText").textContent = "v" + init.version;  // durumla aynı satırda: kısa
  $("#versionText").title = "TekTıkla v" + init.version;
  $("#appVersion").textContent = tr("v" + init.version);
  $("#repoText").textContent = tr(init.repo ? "github.com/" + init.repo : "Ayarlanmadı");
  renderSettings();
  renderTools(init.tools);
  renderQueue();
  renderHistory();
  if (init.update) onAppUpdate({ update: init.update, manual: false });
  onSetup({ state: init.setup === "checking" ? "checking" : init.setup, tools: init.tools });
  if (init.setup === "checking") $("#setupChipText").textContent = tr("Kontrol ediliyor…");
  studioInit(init);
  watchInit(init);
  accountInit(init);
  remoteInit(init);
  moveIndicator();
  if (init.support) setTimeout(autoSupport, 1400);
  $("#urlInput").focus();
  pollLoop();
});
