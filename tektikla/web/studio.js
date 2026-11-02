/* TekTıkla stüdyo sekmeleri: Reels, Görsel, Dublaj, Servisler ve dil seçimi.
 * app.js'teki yardımcıları (h, icon, seg, toast, state, api…) kullanır; app.js'ten sonra yüklenir. */
"use strict";

Object.assign(ICONS, {
  reels: '<rect x="6" y="2" width="12" height="20" rx="3"/><path d="M10.5 9.2v5.6l4.5-2.8z"/>',
  mic: '<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  wand: '<path d="M15 4V2M15 16v-2M8 9h2M20 9h2M17.8 11.8L19 13M17.8 6.2L19 5M3 21l9-9M12.2 6.2L11 5"/>',
  type: '<path d="M4 7V5h16v2M9 19h6M12 5v14"/>',
  plug: '<path d="M9 2v6M15 2v6M6 8h12v3a6 6 0 0 1-12 0zM12 17v5"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="M10.8 12.2L21 2M17 6l3 3M14 9l2 2"/>',
});

const TIERS = { free: "Ücretsiz", free_quota: "Ücretsiz kota", freemium: "Ücretsiz + ücretli", paid: "Ücretli" };
const studio = {
  data: null, svcKeys: {}, reelsToken: 0, reelsReady: 0, clips: [], music: null, reelsFile: null,
  imgToken: 0, imgFile: null, dubFile: null, steps: [], ctl: {}, lastTitle: "",
};
const REELS_STEPS = ["Video bilgileri alınıyor", "Kelime kelime döküm çıkarılıyor", "Yapay zekâ en iyi anları seçiyor"];

function tierChip(tier) { return h("span", { class: "tier " + tier }, TIERS[tier] || tier); }

/* Kart biçiminde seçenekler: [{v, name, tier, desc, locked}] */
function tiles(id, items, onChange) {
  const el = document.getElementById(id);
  const ctl = {
    value: null,
    set(v, silent = true) {
      el.querySelectorAll(".tile").forEach((b) => b.classList.toggle("on", b.dataset.v === String(v)));
      ctl.value = String(v);
      if (!silent && onChange) onChange(ctl.value);
    },
  };
  el.replaceChildren(...items.map((it) => {
    const b = h("button", { class: "tile" + (it.locked ? " locked" : ""), onclick: () => ctl.set(it.v, false) },
      h("div", { class: "tile-top" }, h("b", {}, it.name), it.tier ? tierChip(it.tier) : null),
      it.desc ? h("small", {}, it.desc) : null,
      it.locked ? h("small", { class: "need" }, icon("key"), "Anahtar gerekli") : null);
    b.dataset.v = it.v;
    return b;
  }));
  return ctl;
}

/* Renk ya da stil düğmeleri (data-v), seçili olana "on" sınıfı */
function picker(id, onChange) {
  const el = document.getElementById(id);
  const ctl = {
    value: null,
    set(v, silent = true) {
      el.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.v === String(v)));
      ctl.value = String(v);
      if (!silent && onChange) onChange(ctl.value);
    },
  };
  el.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => ctl.set(b.dataset.v, false)));
  return ctl;
}

function fileUrl(path) {
  const parts = path.replace(/\\/g, "/").split("/");
  return "file:///" + parts.map((p, i) => (i === 0 && /^[A-Za-z]:$/.test(p) ? p : encodeURIComponent(p))).join("/");
}

function parseTime(text) {
  const parts = String(text).trim().split(":").map(Number);
  if (!parts.length || parts.some(isNaN)) return null;
  return parts.reduce((acc, x) => acc * 60 + x, 0);
}
function fmtTime(t) { return `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, "0")}`; }

function needKey(name) { return !!name && !(state.keys[name] || studio.svcKeys[name]); }

/* ================================================================ REELS */
function reelsMode(v) {
  const idea = v === "idea";
  $("#reelsVideoMode").classList.toggle("hidden", idea);
  $("#reelsIdeaMode").classList.toggle("hidden", !idea);
  // fikirden Reels zaten seçilen dilde konuşur ve kendi görüntülerini kullanır
  for (const id of ["rFrameBox", "rCutRow", "rZoomRow", "rCapLangRow", "rBrollBox"]) $("#" + id).classList.toggle("hidden", idea);
  setTimeout(() => Object.values(segs).forEach((s) => s.refresh()), 20);
  reelsSummary();
}

function renderReelsSteps(current) {
  if (!studio.steps.includes(current)) studio.steps.splice(Math.max(1, studio.steps.length - 1), 0, current);
  const idx = studio.steps.indexOf(current);
  $("#reelsSteps").replaceChildren(...studio.steps.map((s, i) =>
    h("div", { class: "ai-step" + (i < idx ? " done" : i === idx ? " active" : "") },
      h("span", { class: "b" }, i < idx ? icon("check") : String(i + 1)), s)));
}

function reelsView(which) {
  for (const id of ["reelsLoading", "reelsError", "reelsClipsCard"]) $("#" + id).classList.toggle("hidden", id !== which);
}

async function reelsFind() {
  const typed = $("#reelsUrl").value.trim();
  const source = studio.reelsFile && typed === studio.reelsFile.split(/[\\/]/).pop() ? studio.reelsFile : typed;
  if (!source) { toast("Bir video linki yapıştırın ya da bilgisayardan video seçin.", "err"); return; }
  const token = ++studio.reelsToken;
  studio.steps = REELS_STEPS.map((s) => tr(s));
  reelsView("reelsLoading");
  renderReelsSteps(studio.steps[state.media && state.mediaUrl === source ? 1 : 0]);
  setLoading($("#reelsFindBtn"), true);
  const res = await api.reels_analyze({ source, length: segs.reelsLenSeg.value, count: Number(segs.reelsCountSeg.value) }, token);
  if (!res.ok) { setLoading($("#reelsFindBtn"), false); reelsView(null); toast(res.error, "err"); }
}

function onReelsDone(ev) {
  if (ev.token !== studio.reelsToken) return;
  setLoading($("#reelsFindBtn"), false);
  studio.reelsReady = ev.token;
  studio.clips = ev.clips.map((c) => ({ ...c, on: true }));
  const s = ev.source;
  $("#reelsSrcChip").textContent = `${s.title} · ${s.duration}` + (ev.ai ? "" : " · " + tr("yapay zekâsız seçim"));
  renderClips();
  reelsView("reelsClipsCard");
  reelsSummary();
  toast(tr("{n} an bulundu", { n: studio.clips.length }), "ok");
}

function onReelsError(ev) {
  if (ev.token !== studio.reelsToken) return;
  setLoading($("#reelsFindBtn"), false);
  $("#reelsErrorText").textContent = tr(ev.message);
  reelsView("reelsError");
}

function renderClips() {
  $("#reelsClipList").replaceChildren(...studio.clips.map((c, i) => {
    const dur = h("span", { class: "dur" }, `${Math.round(c.end - c.start)} sn`);
    const timeInput = (key) => {
      const inp = h("input", { class: "input xs", value: fmtTime(c[key]) });
      inp.addEventListener("change", () => {
        const v = parseTime(inp.value);
        if (v === null || v < 0) { inp.value = fmtTime(c[key]); return; }
        c[key] = v;
        dur.textContent = `${Math.max(0, c.end - c.start).toFixed(0)} sn`;
      });
      return inp;
    };
    const title = h("input", { class: "input", value: c.title || "", placeholder: "Klip adı" });
    title.addEventListener("input", () => { c.title = title.value; });
    const hook = h("input", { class: "input", value: c.hook || "", placeholder: "Kanca yazısı (ilk 3 sn)" });
    hook.addEventListener("input", () => { c.hook = hook.value; });
    const box = h("input", { type: "checkbox" });
    box.checked = c.on;
    const row = h("div", { class: "clip-row" + (c.on ? "" : " off") },
      h("label", { class: "clip-check" }, box, h("span", { class: "cb" }, icon("check"))),
      h("div", { class: "score", title: "Viral olma puanı" }, String(c.score ?? "–")),
      h("div", { class: "clip-main" },
        h("div", { class: "clip-times" }, timeInput("start"), h("span", {}, "→"), timeInput("end"), dur),
        h("div", { class: "clip-fields" }, title, hook),
        c.reason ? h("small", { class: "why" }, c.reason) : null),
      h("button", { class: "btn icon ghost", title: "Kaldır", onclick: () => { studio.clips.splice(i, 1); renderClips(); reelsSummary(); } }, icon("x")));
    box.addEventListener("change", () => { c.on = box.checked; row.classList.toggle("off", !c.on); reelsSummary(); });
    return row;
  }));
}

function editOpts() {
  return {
    frame: segs.rFrameSeg.value, cap_style: studio.ctl.cap.value, accent: studio.ctl.accent.value,
    position: segs.rPosSeg.value, words: Number(segs.rWordsSeg.value), uppercase: $("#rUpper").checked,
    hook: $("#rHook").checked, cut: $("#rCut").checked, zoom: $("#rZoom").checked, bar: $("#rBar").checked,
    music: studio.music, music_volume: Number($("#rMusicVol").value) / 100, watermark: $("#rWatermark").value.trim(),
    cap_lang: $("#rCapLang").value, broll: segs.rBrollSeg.value,
  };
}

function reelsHints() {
  const lang = $("#rCapLang").value, ai = state.keys.gemini || state.keys.claude;
  $("#rCapLangHint").textContent = tr(!lang ? "Altyazı, videoda konuşulan dilde olur."
    : ai ? "Konuşma bu dile yapay zekâyla çevrilir; kelime kelime vurgu korunur."
      : "Konuşma bu dile ücretsiz çeviriyle çevrilir; Gemini anahtarı eklersen çeviri daha doğal olur.");
  const b = segs.rBrollSeg ? segs.rBrollSeg.value : "off";
  const svc = studio.svcKeys || {};
  $("#rBrollHint").textContent = tr(b === "pexels"
    ? (svc.pexels ? "Konuşmada anlatılanı gösteren ücretsiz stok videolar araya girer (Pexels). Yerleri yapay zekâ seçer."
      : "Ücretsiz: Ayarlar > Servisler'den Pexels anahtarı ekle.")
    : b === "higgsfield"
      ? (svc.higgsfield ? "Ücretli: Higgsfield her ara görüntüyü yapay zekâyla üretir (klip başına 2 sahne, kredi harcar)."
        : "Ücretli: Ayarlar > Servisler'den Higgsfield anahtarı ekle.")
      : "Klip boyunca konuşmacı görünür.");
}

function reelsSummary() {
  if (!segs.reelsModeSeg) return;
  const idea = segs.reelsModeSeg.value === "idea";
  const label = $("#reelsGoBtn span");
  if (idea) {
    $("#reelsSummary").textContent = tr("Fikirden Reels · {s} sn", { s: segs.ideaLenSeg?.value || 45 });
    label.textContent = tr("Reels oluştur");
    $("#reelsGoBtn").disabled = false;
  } else {
    const n = studio.clips.filter((c) => c.on).length;
    $("#reelsSummary").textContent = studio.clips.length ? tr("{n} klip seçili", { n }) : tr("Önce en iyi anları bulun");
    label.textContent = n ? tr("Seçilen klipleri oluştur ({n})", { n }) : tr("Reels oluştur");
    $("#reelsGoBtn").disabled = !n;
  }
  $("#reelsSummary2").textContent = tr("Kayıt: ") + (state.settings.download_dir || "") + "\\Reels";
}

async function reelsGo() {
  const btn = $("#reelsGoBtn");
  let res;
  setLoading(btn, true);
  if (segs.reelsModeSeg.value === "idea") {
    res = await api.reels_idea({
      ...editOpts(), idea: $("#ideaText").value, own_script: $("#ideaOwn").checked,
      seconds: Number(segs.ideaLenSeg.value), lang: $("#ideaLang").value, voice_engine: studio.ctl.ideaEngine.value,
      voice: $("#ideaVoice").value, visuals: studio.ctl.ideaVisuals.value, image_provider: $("#ideaImgProvider").value,
    });
  } else {
    const clips = studio.clips.filter((c) => c.on).map(({ on, ...c }) => c);
    res = await api.reels_render({ ...editOpts(), token: studio.reelsReady, clips });
  }
  setLoading(btn, false);
  reelsSummary();
  if (!res.ok) { toast(res.error, "err"); return; }
  toast(res.count > 1 ? tr("{n} klip kuyruğa alındı", { n: res.count }) : tr("Reels kuyruğa alındı"), "ok");
  flyToQueue(btn);
}

async function loadVoices(engine, lang, select) {
  let voices = [];
  if (engine === "edge") voices = studio.data.edge_voices[lang] || studio.data.edge_voices.en;
  else if (engine === "gemini") voices = studio.data.gemini_voices;
  else if (engine === "elevenlabs" && !needKey("elevenlabs")) {
    const r = await api.tts_voices("elevenlabs", lang);
    voices = r.voices || [];
    if (!r.ok) toast(r.error, "err");
  }
  select.replaceChildren(...voices.map(([id, name]) => h("option", { value: id }, name)));
}

function engineTiles(id, onChange, forDub = false) {
  const desc = {
    edge: "Anahtarsız · 70+ dil · kelime zamanlı",
    gemini: forDub ? "Çok doğal ve duygulu · günlük ücretsiz kota dolarsa Edge sesiyle tamamlanır"
      : "Gemini anahtarıyla · çok doğal ve duygulu",
    elevenlabs: forDub ? "Konuşmacının kendi sesini korur · ücretsizde filigranlı" : "En doğal sesler · ayda ~10 dk ücretsiz",
  };
  return tiles(id, Object.entries(studio.data.tts_engines).map(([v, m]) =>
    ({ v, name: m.name, tier: m.tier, desc: desc[v], locked: needKey(m.needs) })), onChange);
}

function addResult(files, urls = {}) {
  const video = files.find((f) => /\.mp4$/i.test(f));
  if (!video) return;
  const txt = files.find((f) => /\.txt$/i.test(f));
  const cover = files.find((f) => /\.jpe?g$/i.test(f));
  // yerel önizleme sunucusu (file:// sayfası başka klasördeki videoyu oynatamıyor)
  const v = h("video", { src: urls[video] || fileUrl(video), controls: true, preload: "metadata", playsinline: true });
  if (cover) v.setAttribute("poster", urls[cover] || fileUrl(cover));
  const copy = async () => {
    const text = await api.read_made(txt);
    try { await navigator.clipboard.writeText(text); toast("Açıklama ve etiketler kopyalandı", "ok"); } catch { toast("Kopyalanamadı", "err"); }
  };
  const card = h("div", { class: "reel-card" }, v,
    h("div", { class: "reel-meta" }, h("b", { title: video }, video.split(/[\\/]/).pop().replace(/\.mp4$/i, "")),
      h("div", { class: "reel-acts" },
        h("button", { class: "btn sm", onclick: () => api.open_made(video) }, icon("play"), "Aç"),
        h("button", { class: "btn sm rv", onclick: () => api.reveal_made(video) }, icon("folder"), "Klasör"),
        txt ? h("button", { class: "btn sm", onclick: copy }, icon("copy"), "Açıklama") : null)));
  $("#reelsResultGrid").prepend(card);
  $("#reelsResults").classList.remove("hidden");
}

/* ================================================================ GÖRSEL */
function imgMode(v) {
  $("#page-image").classList.toggle("editing", v === "edit");
  if (v === "edit") {  // görsel düzenleyici (editor.js); üretim ayarlarına dokunulmaz
    edShow();
    return;
  }
  const thumb = v === "thumbnail";
  $("#imgTextCard").classList.toggle("hidden", !thumb);
  $("#imgBgBox").classList.toggle("hidden", !thumb);
  if (!thumb) segs.imgBgSeg.set("ai");
  imgBg(thumb ? segs.imgBgSeg.value : "ai");
  $("#imgIdea").placeholder = tr(thumb ? "Fikrini yaz… ör. 'İstanbul'un en iyi 5 kahvecisi'"
    : "Ne görmek istiyorsun? ör. 'Gün batımında sisli bir orman, sinematik'");
  setTimeout(() => Object.values(segs).forEach((s) => s.refresh()), 20);
  imgSummary();
}

function imgBg(v) {
  $("#imgFileRow").classList.toggle("hidden", v !== "file");
  $("#imgGenBox").classList.toggle("hidden", v !== "ai");
  $("#imgCountBox").classList.toggle("hidden", v !== "ai");
  imgSummary();
}

function imgSummary() {
  if (!segs.imgModeSeg || !studio.data) return;
  const thumb = segs.imgModeSeg.value === "thumbnail";
  const bg = segs.imgBgSeg.value || "ai";
  const prov = studio.data.image_providers[studio.ctl.imgProv?.value];
  const parts = [tr(thumb ? "Kapak" : "Görsel"), segs.imgAspectSeg.value];
  if (bg === "ai" && prov) parts.push(prov.name + " · " + tr(TIERS[prov.tier]));
  else if (bg === "video") parts.push(tr("videonun kapağı"));
  else if (bg === "file") parts.push(tr("kendi görselin"));
  if (bg === "ai") parts.push(tr("{n} adet", { n: segs.imgCountSeg.value || 1 }));
  $("#imgSummary").textContent = parts.filter(Boolean).join(" · ");
  $("#imgSummary2").textContent = tr("Kayıt: ") + (state.settings.download_dir || "") + "\\" + tr("Görseller");
}

function imgOpts() {
  return {
    mode: segs.imgModeSeg.value, idea: $("#imgIdea").value, aspect: segs.imgAspectSeg.value, style: segs.imgStyleSeg.value,
    provider: studio.ctl.imgProv.value, count: Number(segs.imgCountSeg.value), bg: segs.imgBgSeg.value,
    file: studio.imgFile, video_url: state.mediaUrl, title: $("#imgTitle").value, subtitle: $("#imgSub").value,
    layout: segs.imgLayoutSeg.value, text_style: segs.imgTextSeg.value, accent: studio.ctl.imgAccent.value,
  };
}

async function imgGo() {
  const token = ++studio.imgToken;
  $("#imgError").classList.add("hidden");
  $("#imgProgress").classList.remove("hidden");
  $("#imgStageText").textContent = tr("Başlıyor…");
  $("#imgBar").style.width = "0%";
  setLoading($("#imgGoBtn"), true);
  const res = await api.image_generate(imgOpts(), token);
  if (!res.ok) { setLoading($("#imgGoBtn"), false); $("#imgProgress").classList.add("hidden"); toast(res.error, "err"); }
}

function onImgStage(ev) {
  if (ev.token !== studio.imgToken) return;
  $("#imgStageText").textContent = tr(ev.text);
  if (ev.frac != null) $("#imgBar").style.width = Math.round(ev.frac * 100) + "%";
}

function onImgItem(ev) {
  if (ev.token !== studio.imgToken) return;
  const img = h("img", { src: ev.data, alt: "" });
  let path = ev.path;
  const acts = h("div", { class: "img-acts" },
    h("button", { class: "btn sm", onclick: () => api.open_made(path) }, icon("image"), "Aç"),
    h("button", { class: "btn sm", onclick: () => edOpenPath(path) }, icon("pen"), "Düzenle"),
    h("button", { class: "btn sm rv", onclick: () => api.reveal_made(path) }, icon("folder"), "Klasör"));
  if (ev.mode === "thumbnail") {
    const redo = async (e) => {
      const b = e.currentTarget;
      setLoading(b, true);
      const o = imgOpts();
      const r = await api.image_recompose({ id: ev.id, aspect: ev.aspect, title: o.title || studio.lastTitle || "",
        subtitle: o.subtitle, layout: o.layout, text_style: o.text_style, accent: o.accent });
      setLoading(b, false);
      if (!r.ok) { toast(r.error, "err"); return; }
      img.src = r.data;
      path = r.path;
      toast("Yazı güncellendi", "ok");
    };
    acts.append(h("button", { class: "btn sm", title: "Yukarıdaki başlık ve stil ayarlarıyla yazıyı yeniden yerleştir", onclick: redo },
      icon("type"), "Yazıyı güncelle"));
  }
  $("#imgGallery").prepend(h("div", { class: "img-card a" + ev.aspect.replace(":", "x") }, img, acts));
}

function onImgDone(ev) {
  if (ev.token !== studio.imgToken) return;
  setLoading($("#imgGoBtn"), false);
  $("#imgProgress").classList.add("hidden");
  studio.lastTitle = ev.title;
  if (segs.imgModeSeg.value === "thumbnail" && !$("#imgTitle").value && ev.title) $("#imgTitle").value = ev.title;
  if (ev.subtitle && !$("#imgSub").value) $("#imgSub").value = ev.subtitle;
  toast("Görseller hazır", "ok");
}

function onImgError(ev) {
  if (ev.token !== studio.imgToken) return;
  setLoading($("#imgGoBtn"), false);
  $("#imgProgress").classList.add("hidden");
  $("#imgErrorText").textContent = tr(ev.message);
  $("#imgError").classList.remove("hidden");
}

/* ================================================================ DUBLAJ */
const DUB_HINTS = {
  edge: "Microsoft Edge'in doğal sesleri: tamamen ücretsiz, anahtar gerekmez.",
  gemini: "Gemini 3.8 TTS: ücretsiz katmanda, Gemini anahtarınla. Çok doğal ve duygulu.",
  elevenlabs: "ElevenLabs otomatik dublaj: konuşmacının kendi sesini korur. Ücretsiz planda ayda ~5 dk ve filigranlı.",
};

function dubEngine(v) {
  $("#dubVoiceBox").classList.toggle("hidden", v === "elevenlabs");
  $("#dubEngineHint").textContent = tr(DUB_HINTS[v] || "");
  if (v !== "elevenlabs") loadVoices(v, $("#dubLang").value, $("#dubVoice"));
  dubSummary();
}

function dubSummary() {
  if (!studio.data) return;
  const lang = $("#dubLang").selectedOptions[0]?.textContent || "";
  const eng = studio.data.tts_engines[studio.ctl.dubEngine?.value];
  $("#dubSummary").textContent = [lang, eng?.name, eng ? tr(TIERS[eng.tier]) : ""].filter(Boolean).join(" · ");
  $("#dubSummary2").textContent = tr("Kayıt: ") + (state.settings.download_dir || "") + "\\" + tr("Dublaj");
}

async function dubGo() {
  const typed = $("#dubUrl").value.trim();
  const source = studio.dubFile && typed === studio.dubFile.split(/[\\/]/).pop() ? studio.dubFile : typed;
  if (!source) { toast("Bir video linki yapıştırın ya da bilgisayardan video seçin.", "err"); return; }
  const btn = $("#dubGoBtn");
  setLoading(btn, true);
  const res = await api.dub_start({
    source, target: $("#dubLang").value, engine: studio.ctl.dubEngine.value, voice: $("#dubVoice").value,
    original: segs.dubOrigSeg.value, keep: $("#dubKeep").checked, subs: $("#dubSubs").checked,
  });
  setLoading(btn, false);
  if (!res.ok) { toast(res.error, "err"); return; }
  toast("Dublaj kuyruğa alındı", "ok");
  flyToQueue(btn);
}

/* ================================================================ SERVİSLER */
function renderServices() {
  $("#svcList").replaceChildren(...Object.entries(studio.data.services).map(([name, m]) => {
    const on = !!studio.svcKeys[name];
    const input = h("input", { class: "input", type: "password", placeholder: m.placeholder, autocomplete: "off" });
    const save = async () => {
      const r = await api.save_service_key(name, input.value);
      if (!r.ok) { toast(r.error, "err"); return; }
      studio.svcKeys = r.services;
      renderServices();
      refreshStudioTiles();
      toast("Anahtar kaydedildi", "ok");
    };
    const remove = async () => { studio.svcKeys = await api.delete_service_key(name); renderServices(); refreshStudioTiles(); };
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") save(); });
    return h("div", { class: "svc" + (on ? " on" : "") },
      h("div", { class: "svc-head" }, h("b", {}, m.name), tierChip(m.tier),
        h("span", { class: "chip " + (on ? "ok" : "") }, on ? "Bağlı" : m.optional ? "İsteğe bağlı" : "Bağlı değil")),
      h("small", { class: "svc-uses" }, m.uses),
      h("p", { class: "hint" }, m.hint),
      h("div", { class: "key-row" }, input, h("button", { class: "btn primary", onclick: save }, "Kaydet"),
        on ? h("button", { class: "btn danger", onclick: remove }, "Sil") : null,
        h("button", { class: "btn", onclick: () => api.open_url(m.link) }, icon("key"), "Anahtar al")));
  }));
}

function refreshStudioTiles() {
  const keep = {
    imgProv: studio.ctl.imgProv?.value, ideaEngine: studio.ctl.ideaEngine?.value,
    ideaVisuals: studio.ctl.ideaVisuals?.value, dubEngine: studio.ctl.dubEngine?.value,
  };
  const prov = studio.data.image_providers;
  const pdesc = {
    pollinations: "Anahtarsız çalışır · ücretsiz hesapla logosuz",
    cloudflare: "Günde ~95 görsel ücretsiz · FLUX kalitesi",
    gemini: "Nano Banana · görsel başı ~0,03 $",
    higgsfield: "SOUL modeli · kullandıkça öde",
  };
  studio.ctl.imgProv = tiles("imgProviders", Object.entries(prov).map(([v, m]) =>
    ({ v, name: m.name, tier: m.tier, desc: pdesc[v], locked: needKey(m.needs) })), imgSummary);
  studio.ctl.imgProv.set(keep.imgProv || state.settings.image_provider || "pollinations");
  $("#ideaImgProvider").replaceChildren(...Object.entries(prov).map(([v, m]) => h("option", { value: v }, `${m.name} · ${tr(TIERS[m.tier])}`)));
  studio.ctl.ideaEngine = engineTiles("ideaVoiceEngine", (v) => loadVoices(v, $("#ideaLang").value, $("#ideaVoice")));
  studio.ctl.ideaEngine.set(keep.ideaEngine || "edge");
  studio.ctl.ideaVisuals = tiles("ideaVisuals", [
    { v: "stock", name: "Stok video", tier: "free", desc: "Pexels · ücretsiz anahtar", locked: needKey("pexels") },
    { v: "image", name: "AI görsel", tier: "free", desc: "Her sahneye üretilen hareketli görsel" },
    { v: "video", name: "AI video", tier: "paid", desc: "Higgsfield Seedance · sahne başı video", locked: needKey("higgsfield") },
    { v: "plain", name: "Sade arka plan", tier: "free", desc: "Anında · yalnızca yazı ve ses" },
  ], (v) => $("#ideaImgProvBox").classList.toggle("hidden", v !== "image"));
  studio.ctl.ideaVisuals.set(keep.ideaVisuals || (needKey("pexels") ? "image" : "stock"));
  $("#ideaImgProvBox").classList.toggle("hidden", studio.ctl.ideaVisuals.value !== "image");
  studio.ctl.dubEngine = engineTiles("dubEngines", dubEngine, true);
  studio.ctl.dubEngine.set(keep.dubEngine || "edge");
  dubEngine(studio.ctl.dubEngine.value);
  loadVoices(studio.ctl.ideaEngine.value, $("#ideaLang").value, $("#ideaVoice"));
  imgSummary();
}

/* ================================================================ dil */
function showLangPicker(list, preselect) {
  let chosen = preselect;
  $("#langGrid").replaceChildren(...list.map(([c, n]) => {
    const b = h("button", { class: "lang-opt" + (c === chosen ? " on" : ""), "data-no-i18n": true }, n);
    b.addEventListener("click", () => { chosen = c; $$("#langGrid .lang-opt").forEach((x) => x.classList.toggle("on", x === b)); });
    b.addEventListener("dblclick", () => $("#langGo").click());
    return b;
  }));
  $("#langOverlay").classList.remove("hidden");
  $("#langGo").onclick = async () => { $("#langOverlay").classList.add("hidden"); await changeLanguage(chosen); };
}

async function changeLanguage(code) {
  const r = await api.set_language(code);
  if (!r.ok) return;
  state.settings.language = code;
  studio.data = r.studio;
  applyI18n(r.i18n, code, r.rtl);
  $("#langSelect").value = code;
  renderServices();
  refreshStudioTiles();
  renderSettings();
  renderQueue();
  renderHistory();
  renderWatch();
  convRender();
  renderConvResults();
  reelsSummary(); imgSummary(); dubSummary(); reelsHints();
  if (state.media) updateSummary();
}

/* ================================================================ bağlantılar */
function studioWire() {
  seg("reelsModeSeg", reelsMode);
  seg("reelsLenSeg").set("medium");
  seg("reelsCountSeg").set("5");
  seg("ideaLenSeg", reelsSummary).set("45");
  seg("rFrameSeg").set("smart");
  seg("rPosSeg").set("bottom");
  seg("rWordsSeg").set("3");
  studio.ctl.cap = picker("rCapStyles");
  studio.ctl.cap.set("clean");
  seg("rBrollSeg", reelsHints).set("off");
  $("#rCapLang").addEventListener("change", reelsHints);
  studio.ctl.accent = picker("rAccent");
  studio.ctl.accent.set("yellow");
  seg("imgModeSeg", imgMode);
  seg("imgBgSeg", imgBg).set("ai");
  seg("imgAspectSeg", imgSummary).set("16:9");
  seg("imgCountSeg", imgSummary).set("1");
  seg("imgStyleSeg").set("auto");
  seg("imgLayoutSeg").set("left");
  seg("imgTextSeg").set("bold");
  studio.ctl.imgAccent = picker("imgAccent");
  studio.ctl.imgAccent.set("yellow");
  seg("dubOrigSeg").set("duck");

  $("#reelsFindBtn").addEventListener("click", reelsFind);
  $("#reelsUrl").addEventListener("keydown", (e) => { if (e.key === "Enter") reelsFind(); });
  $("#reelsPickBtn").addEventListener("click", async () => {
    const p = await api.pick_video();
    if (p) { studio.reelsFile = p; $("#reelsUrl").value = p.split(/[\\/]/).pop(); }
  });
  $("#reelsAddClip").addEventListener("click", () => {
    const last = studio.clips[studio.clips.length - 1];
    const start = last ? last.end + 1 : 0;
    studio.clips.push({ start, end: start + 30, title: "", hook: "", score: null, reason: "", on: true });
    renderClips();
    reelsSummary();
  });
  $("#reelsGoBtn").addEventListener("click", reelsGo);
  $("#rMusicBtn").addEventListener("click", async () => {
    const p = await api.pick_audio();
    if (p) { studio.music = p; $("#rMusicName").textContent = p.split(/[\\/]/).pop(); $("#rMusicName").classList.add("set"); }
  });
  $("#rMusicClear").addEventListener("click", () => {
    studio.music = null;
    $("#rMusicName").textContent = tr("Seçilmedi");
    $("#rMusicName").classList.remove("set");
  });
  $("#ideaLang").addEventListener("change", () => loadVoices(studio.ctl.ideaEngine.value, $("#ideaLang").value, $("#ideaVoice")));

  $("#imgGoBtn").addEventListener("click", imgGo);
  $("#imgFileBtn").addEventListener("click", async () => {
    const p = await api.pick_image();
    if (p) { studio.imgFile = p; $("#imgFileName").textContent = p.split(/[\\/]/).pop(); $("#imgFileName").classList.add("set"); }
  });

  $("#dubGoBtn").addEventListener("click", dubGo);
  $("#dubPickBtn").addEventListener("click", async () => {
    const p = await api.pick_video();
    if (p) { studio.dubFile = p; $("#dubUrl").value = p.split(/[\\/]/).pop(); }
  });
  $("#dubLang").addEventListener("change", () => dubEngine(studio.ctl.dubEngine.value));
  $("#langSelect").addEventListener("change", () => changeLanguage($("#langSelect").value));

  // İndir sayfasındaki video kartından stüdyolara geçiş
  $("#mReelsBtn").addEventListener("click", () => {
    segs.reelsModeSeg.set("video", false);
    studio.reelsFile = null;
    $("#reelsUrl").value = state.mediaUrl;
    showPage("reels");
    reelsFind();
  });
  $("#mDubBtn").addEventListener("click", () => { studio.dubFile = null; $("#dubUrl").value = state.mediaUrl; showPage("dub"); });
  $("#mCoverBtn").addEventListener("click", () => {
    segs.imgModeSeg.set("thumbnail", false);
    segs.imgBgSeg.set("video", false);
    $("#imgIdea").value = state.media?.title || "";
    $("#imgTitle").value = "";
    showPage("image");
  });

  Object.assign(HANDLERS, {
    reels_stage: (ev) => { if (ev.token === studio.reelsToken) renderReelsSteps(tr(ev.text)); },
    reels_done: onReelsDone,
    reels_error: onReelsError,
    img_stage: onImgStage,
    img_item: onImgItem,
    img_done: onImgDone,
    img_error: onImgError,
    studio_done: (ev) => { if (ev.kind === "reels" || ev.kind === "idea") addResult(ev.files, ev.urls); },
  });
}

function studioInit(init) {
  studio.data = init.studio;
  studio.svcKeys = init.studio.service_keys;
  const langs = init.studio.dub_languages;
  $("#dubLang").replaceChildren(...langs.map(([c, n]) => h("option", { value: c }, n)));
  $("#rCapLang").replaceChildren(h("option", { value: "" }, "Videonun dili (çevirmeden)"),
    ...langs.map(([c, n]) => h("option", { value: c, "data-no-i18n": true }, txt(n))));
  $("#rCapLang").value = langs.some(([c]) => c === (init.lang || init.system_lang)) ? (init.lang || init.system_lang) : "";
  reelsHints();
  $("#ideaLang").replaceChildren(...langs.map(([c, n]) => h("option", { value: c }, n)));
  const ui = init.lang || init.system_lang || "tr";
  $("#dubLang").value = langs.some(([c]) => c === ui) ? ui : "tr";
  $("#ideaLang").value = $("#dubLang").value;
  $("#langSelect").replaceChildren(...init.ui_languages.map(([c, n]) => h("option", { value: c, "data-no-i18n": true }, n)));
  $("#langSelect").value = init.lang || "tr";
  renderServices();
  refreshStudioTiles();
  segs.reelsModeSeg.set("video");
  reelsMode("video");
  segs.imgModeSeg.set("thumbnail");
  imgMode("thumbnail");
  applyI18n(init.i18n || {}, init.lang || "tr", init.rtl);
  if (!init.lang) showLangPicker(init.ui_languages, init.system_lang || "tr");
}
