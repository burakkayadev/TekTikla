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
window.addEventListener("resize", () => Object.values(segs).forEach((s) => s.refresh()));

/* ---------------------------------------------------------------- durum */
const state = {
  settings: {}, items: new Map(), history: [], media: null, mediaUrl: "",
  analyzeToken: 0, aiToken: 0, extSub: null, setup: "checking", hasKey: false,
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
  if (a) $("#navIndicator").style.transform = `translateY(${a.offsetTop}px)`;
}
$$(".nav-item").forEach((n) => n.addEventListener("click", () => showPage(n.dataset.page)));

/* ---------------------------------------------------------------- tema */
function applyTheme(t) {
  const dark = t === "dark" || (t === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => applyTheme(state.settings.theme));

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
  $("#dlLoadingText").lastChild.textContent = "Link analiz ediliyor…";
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
  $("#mDur").textContent = m.duration_text || "";
  $("#mDur").classList.toggle("hidden", !m.duration_text);
  $("#mSite").textContent = m.site || "Video";
  $("#mTitle").textContent = m.title;
  $("#mUploader").textContent = m.uploader || "";
  const nq = m.qualities.length - 1;
  $("#mBadge").textContent = m.is_playlist ? `Oynatma listesi · ${m.entry_count} öğe` : m.audio_only ? "Ses kaynağı" : nq ? `${nq} kalite seçeneği` : "İndirilebilir";
  $("#mSubs").textContent = m.subtitles.length ? `${m.subtitles.length} altyazı` : "";
  $("#mSubs").classList.toggle("hidden", !m.subtitles.length);
  $("#mAiBtn").classList.toggle("hidden", m.is_playlist);

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
  updateSubHint();

  $("#trimToggle").checked = false; $("#trimRow").classList.add("hidden");
  $("#trimStart").value = ""; $("#trimEnd").value = "";
  const showPl = m.is_playlist || m.has_playlist_param;
  $("#playlistRow").classList.toggle("hidden", !showPl);
  $("#playlistToggle").checked = m.is_playlist;
  $("#playlistToggle").disabled = m.is_playlist;
  $("#playlistHint").textContent = m.is_playlist
    ? `Listedeki ${m.entry_count} video kendi klasörüne indirilecek.`
    : "Bu link bir listenin parçası. Açarsan listedeki tüm videolar indirilir.";

  dlView("dlResult");
  updateSummary();
}

function onAnalyzeError(ev) {
  if (ev.token !== state.analyzeToken) return;
  setLoading($("#analyzeBtn"), false);
  $("#dlErrorText").textContent = ev.message;
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
function updateSubHint() { $("#subHint").textContent = SUB_HINTS[segs.subModeSeg.value] || ""; updateSummary(); }

function updateExtSub() {
  const n = $("#extSubName");
  n.textContent = state.extSub ? state.extSub.split(/[\\/]/).pop() : "Seçilmedi (.srt, .vtt, .ass)";
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
    const sub = $("#subSelect").value !== "" || state.extSub;
    if (sub) main += " · altyazı " + ({ embed: "gömülü", burn: "yakılmış", file: ".srt" })[segs.subModeSeg.value];
  }
  if ($("#trimToggle").checked) main += " · kesit";
  if ($("#playlistToggle").checked && !$("#playlistRow").classList.contains("hidden")) main += " · tüm liste";
  $("#dlSummary").textContent = main;
  $("#dlSummary2").textContent = "Kayıt: " + (state.settings.download_dir || "");
}

async function startDownload() {
  const m = state.media;
  if (!m) return;
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
    trim: $("#trimToggle").checked,
    trim_start: $("#trimStart").value,
    trim_end: $("#trimEnd").value,
    playlist: $("#playlistToggle").checked,
  };
  const btn = $("#downloadBtn");
  setLoading(btn, true);
  const res = await api.download(opts);
  setLoading(btn, false);
  if (!res.ok) { toast(res.error, "err"); return; }
  toast(state.setup === "ready" ? "İndirme başladı" : "Sıraya alındı — bileşenler kurulunca başlayacak", "ok");
  flyToQueue(btn);
}

function flyToQueue(from) {
  // İndir butonundan menüdeki "İndirmeler"e uçan küçük nokta
  const a = from.getBoundingClientRect(), b = $('.nav-item[data-page="queue"]').getBoundingClientRect();
  const dot = h("div");
  dot.style.cssText = `position:fixed;z-index:60;width:16px;height:16px;border-radius:50%;background:var(--grad);box-shadow:var(--glow);left:${a.left + a.width / 2}px;top:${a.top + a.height / 2}px;transition:all .75s cubic-bezier(.5,-0.3,.3,1);pointer-events:none`;
  document.body.append(dot);
  requestAnimationFrame(() => { dot.style.left = b.left + 40 + "px"; dot.style.top = b.top + b.height / 2 + "px"; dot.style.transform = "scale(.4)"; dot.style.opacity = ".2"; });
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
    acts.append(h("button", { class: "btn icon", title: "Klasörde göster", onclick: () => api.reveal_item(it.id) }, icon("folder")));
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
      it.state === "error" && it.error ? h("div", { class: "err" }, it.error) : null),
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
  badge.textContent = active;
  badge.classList.toggle("hidden", !active);
  $("#queueSub").textContent = active ? `${active} indirme devam ediyor.` : "Kuyruktaki ve biten indirmeler.";
}

/* ================================================================ AI */
const AI_STEPS = ["Video bilgileri alınıyor", "Konuşma dökümü çıkarılıyor", "Claude videoyu özetliyor"];

function aiView(which) {
  for (const id of ["aiLoading", "aiError", "aiResult"]) $("#" + id).classList.toggle("hidden", id !== which);
}

function renderSteps(current) {
  const idx = AI_STEPS.indexOf(current);
  $("#aiSteps").replaceChildren(...AI_STEPS.map((s, i) =>
    h("div", { class: "ai-step" + (i < idx ? " done" : i === idx ? " active" : "") },
      h("span", { class: "b" }, i < idx ? icon("check") : String(i + 1)), s)));
}

async function aiSummarize(url) {
  url = (url ?? $("#aiUrl").value).trim();
  $("#aiUrl").value = url;
  showPage("ai");
  if (!state.hasKey) { $("#aiNoKey").classList.remove("hidden"); toast("Önce Ayarlar'dan API anahtarını ekle.", "err"); return; }
  if (!URL_RE.test(url)) { toast("Geçerli bir video linki girin.", "err"); return; }
  const token = ++state.aiToken;
  aiView("aiLoading");
  renderSteps(state.media && state.mediaUrl === url ? AI_STEPS[1] : AI_STEPS[0]);
  setLoading($("#aiBtn"), true);
  await api.ai_summary(url, token);
}

function onAiDone(ev) {
  if (ev.token !== state.aiToken) return;
  setLoading($("#aiBtn"), false);
  const r = ev.result;
  state.aiResult = r;
  $("#aiThumb").classList.toggle("hidden", !r.thumb);
  if (r.thumb) $("#aiThumb").src = r.thumb;
  $("#aiTitle").textContent = r.title;
  $("#aiSource").textContent = "Kaynak: " + r.source + (r.words ? ` · ${r.words.toLocaleString("tr-TR")} kelime` : "");
  $("#aiTldr").textContent = r.tldr;
  $("#aiSummary").textContent = r.summary;
  $("#aiPoints").replaceChildren(...r.key_points.map((p, i) => {
    const li = h("li", {}, h("span", { class: "n" }, String(i + 1)), h("span", {}, p));
    li.style.animationDelay = i * 70 + "ms";
    return li;
  }));
  $("#aiTopics").replaceChildren(...r.topics.map((t) => h("span", { class: "chip accent" }, "#" + t)));
  aiView("aiResult");
  toast("Özet hazır", "ok");
}

function onAiError(ev) {
  if (ev.token !== state.aiToken) return;
  setLoading($("#aiBtn"), false);
  $("#aiErrorText").textContent = ev.message;
  aiView("aiError");
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
        h("button", { class: "btn icon", title: "Klasörde göster", onclick: () => api.reveal_history(i) }, icon("folder"))))));
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
  $("#setFolder").textContent = s.download_dir;
  $("#folderText").textContent = s.download_dir;
  segs.themeSeg.set(s.theme);
  segs.parallelSeg.set(s.max_parallel);
  segs.defContainerSeg.set(s.container);
  segs.defAudioSeg.set(s.audio_format);
  segs.defAudioQSeg.set(s.audio_quality);
  $("#rateInput").value = s.rate_limit || "";
  $("#cookiesSelect").value = s.cookies_browser || "Yok";
  $$("input[data-setting]").forEach((i) => { i.checked = !!s[i.dataset.setting]; });
  renderKey();
}

function renderKey() {
  $("#keyStatus").textContent = state.hasKey ? "✓ API anahtarı kayıtlı" : "API anahtarı eklenmedi";
  $("#deleteKeyBtn").classList.toggle("hidden", !state.hasKey);
  $("#aiNoKey").classList.toggle("hidden", state.hasKey);
}

function renderTools(t) {
  if (!t) return;
  $("#tYtdlp").textContent = t.ytdlp;
  $("#tFfmpeg").textContent = t.ffmpeg ? "✓ Kurulu" : "✗ Eksik";
  $("#tJs").textContent = t.js ? "✓ " + t.js : "✗ Eksik";
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
    $("#setupChipText").textContent = "Hazır";
    if (!$("#setupOverlay").classList.contains("hidden")) {
      $("#setupOverlay").classList.add("hidden");
      toast("TekTıkla hazır! Artık her şeyi indirebilirsin.", "ok");
    }
    renderTools(ev.tools);
  } else if (ev.state === "installing") {
    $("#setupChipText").textContent = "Bileşenler kuruluyor…";
    if (!state.setupHidden) $("#setupOverlay").classList.remove("hidden");
    $("#setupText").textContent = ev.text || "";
    $("#setupBar i").style.width = Math.round((ev.frac || 0) * 100) + "%";
    $("#setupRetry").classList.add("hidden");
  } else if (ev.state === "failed") {
    $("#setupChipText").textContent = "Kurulum başarısız";
    $("#setupOverlay").classList.remove("hidden");
    $("#setupTitle").textContent = "Kurulum tamamlanamadı";
    $("#setupText").textContent = ev.text || "";
    $("#setupRetry").classList.remove("hidden");
  }
}

/* ---------------------------------------------------------------- uygulama güncellemesi */
function onAppUpdate(ev) {
  state.update = ev.update;
  if (ev.update) {
    $("#updateChip").classList.remove("hidden");
    $("#updateChipText").textContent = `Güncelleme var: v${ev.update.version}`;
    $("#updateStatus").textContent = `Yeni sürüm: v${ev.update.version}`;
    $("#updateNotes").textContent = ev.update.notes || "";
    $("#installUpdateBtn").classList.remove("hidden");
    if (!ev.manual) toast(`TekTıkla v${ev.update.version} yayınlandı`, "info");
  } else if (ev.manual) {
    setLoading($("#checkUpdateBtn"), false);
    $("#updateStatus").textContent = ev.error ? "Kontrol edilemedi" : "TekTıkla güncel";
    $("#updateNotes").textContent = ev.error || "";
  }
  setLoading($("#checkUpdateBtn"), false);
}

/* ---------------------------------------------------------------- olay döngüsü */
const HANDLERS = {
  analyzed: onAnalyzed,
  analyze_error: onAnalyzeError,
  analyze_wait: (ev) => { if (ev.token === state.analyzeToken) $("#dlLoadingText").lastChild.textContent = "Bileşenler kuruluyor, bitince analiz başlayacak…"; },
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
  ai_error: onAiError,
  ytdlp: (ev) => { setLoading($("#ytdlpBtn"), false); $("#ytdlpMsg").textContent = ev.message; toast(ev.message, ev.message.startsWith("Güncellenemedi") ? "err" : "ok"); },
  app_update: onAppUpdate,
  update_progress: (ev) => {
    const b = $("#installUpdateBtn");
    if (ev.error) { setLoading(b, false); toast("Güncelleme başarısız: " + ev.error, "err"); return; }
    b.lastChild.textContent = ` %${Math.round(ev.frac * 100)}`;
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
  seg("queueFilter", (v) => { state.queueFilter = v; renderQueue(); }).set("all");
  seg("themeSeg", (v) => setSetting("theme", v));
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
  $("#heroAiBtn").addEventListener("click", () => aiSummarize($("#urlInput").value));
  $("#mAiBtn").addEventListener("click", () => aiSummarize(state.mediaUrl));
  $("#mResetBtn").addEventListener("click", () => { state.media = null; $("#urlInput").value = ""; dlView("dlEmpty"); $("#urlInput").focus(); });
  $("#downloadBtn").addEventListener("click", startDownload);
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

  $("#aiBtn").addEventListener("click", () => aiSummarize());
  $("#aiUrl").addEventListener("keydown", (e) => { if (e.key === "Enter") aiSummarize(); });
  $("#aiGoSettings").addEventListener("click", () => { showPage("settings"); setTimeout(() => $("#apiKeyInput").focus(), 300); });
  $("#aiCopy").addEventListener("click", async () => {
    const r = state.aiResult;
    if (!r) return;
    const text = `${r.title}\n\n${r.tldr}\n\n${r.summary}\n\n` + r.key_points.map((p, i) => `${i + 1}. ${p}`).join("\n");
    try { await navigator.clipboard.writeText(text); toast("Özet panoya kopyalandı", "ok"); } catch { toast("Kopyalanamadı", "err"); }
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
  $("#keysLink").addEventListener("click", (e) => { e.preventDefault(); api.open_url("anthropic_keys"); });
  $("#saveKeyBtn").addEventListener("click", async () => {
    const res = await api.save_api_key($("#apiKeyInput").value);
    if (!res.ok) { toast(res.error, "err"); return; }
    $("#apiKeyInput").value = "";
    state.hasKey = true; renderKey(); toast("API anahtarı kaydedildi", "ok");
  });
  $("#deleteKeyBtn").addEventListener("click", async () => { state.hasKey = await api.delete_api_key(); renderKey(); toast("API anahtarı silindi", "info"); });
  $("#ytdlpBtn").addEventListener("click", () => { setLoading($("#ytdlpBtn"), true); $("#ytdlpMsg").textContent = "Güncelleniyor…"; api.update_ytdlp(); });
  $("#repairBtn").addEventListener("click", () => { state.setupHidden = false; api.install_components(); });
  $("#checkUpdateBtn").addEventListener("click", () => {
    if (!state.repo) { toast("Güncelleme kaynağı (GitHub deposu) henüz ayarlanmadı.", "info"); return; }
    setLoading($("#checkUpdateBtn"), true); api.check_update();
  });
  $("#installUpdateBtn").addEventListener("click", () => { setLoading($("#installUpdateBtn"), true); api.install_update(); });
  $("#updateChip").addEventListener("click", () => showPage("settings"));

  $("#setupHide").addEventListener("click", () => { state.setupHidden = true; $("#setupOverlay").classList.add("hidden"); });
  $("#setupRetry").addEventListener("click", () => { $("#setupTitle").textContent = "TekTıkla hazırlanıyor"; api.install_components(); });
}

/* ---------------------------------------------------------------- başlangıç */
window.addEventListener("pywebviewready", async () => {
  api = window.pywebview.api;
  hydrateIcons();
  wire();
  const init = await api.init();
  state.settings = init.settings;
  state.hasKey = init.has_api_key;
  state.history = init.history;
  state.repo = init.repo;
  applyTheme(state.settings.theme);
  init.items.forEach((it) => state.items.set(it.id, it));
  $("#versionText").textContent = `TekTıkla v${init.version}`;
  $("#appVersion").textContent = "v" + init.version;
  $("#repoText").textContent = init.repo ? "github.com/" + init.repo : "Ayarlanmadı";
  renderSettings();
  renderTools(init.tools);
  renderQueue();
  renderHistory();
  if (init.update) onAppUpdate({ update: init.update, manual: false });
  onSetup({ state: init.setup === "checking" ? "checking" : init.setup, tools: init.tools });
  if (init.setup === "checking") $("#setupChipText").textContent = "Kontrol ediliyor…";
  moveIndicator();
  $("#urlInput").focus();
  pollLoop();
});
