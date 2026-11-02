/* Dönüştür: resim, video ve ses dosyalarını başka biçime çevirir, istenirse yeniden boyutlandırır.
 * Python tarafı: tektikla/convert.py + studio_api.py (convert_*). Dosyalar seçiciyle, klasörden ya da pencereye
 * bırakılarak gelir. Hazır ayarlar, gelişmiş ayarlar, tahmini boyut ve önce/sonra karşılaştırma burada. */
"use strict";

const CONV_FORMATS = {
  image: [["webp", "Küçük ve kaliteli · web için ideal"], ["png", "Kayıpsız · şeffaflık korunur"], ["jpg", "En uyumlu · fotoğraflar"],
    ["avif", "En küçük dosya · yeni cihazlar"], ["gif", "Animasyon · 256 renk"], ["pdf", "Belge olarak"],
    ["ico", "Windows simgesi"], ["tiff", "Baskı ve arşiv · kayıpsız"], ["bmp", "Sıkıştırmasız"]],
  video: [["mp4", "En uyumlu · H.264"], ["webm", "Web için · VP9"], ["mov", "Apple cihazlar"], ["mkv", "Tüm ses ve altyazılar korunur"],
    ["gif", "Hareketli resim"], ["mp3", "Sadece ses"], ["m4a", "Sadece ses · AAC"], ["wav", "Sadece ses · kayıpsız"]],
  audio: [["mp3", "En uyumlu"], ["m4a", "AAC · Apple cihazlar"], ["flac", "Kayıpsız · sıkıştırılmış"],
    ["wav", "Kayıpsız · sıkıştırmasız"], ["opus", "En verimli"], ["ogg", "Açık biçim · Vorbis"]],
};
const CONV_PRESETS = [
  { id: "web", icon: "zap", name: "Web için küçült", desc: "WEBP · Full HD · dengeli",
    set: { targets: { image: "webp", video: "mp4", audio: "mp3" }, quality: "balanced", size: "fhd" } },
  { id: "insta", icon: "image", name: "Instagram gönderisi", desc: "JPG · 1080×1350 (4:5)",
    set: { targets: { image: "jpg", video: "mp4" }, quality: "high", size: "custom", width: 1080, height: 1350, fit: "crop" } },
  { id: "vertical", icon: "reels", name: "Dikey video", desc: "Reels · TikTok · 1080×1920",
    set: { targets: { video: "mp4", image: "jpg" }, quality: "high", size: "custom", width: 1080, height: 1920, fit: "crop" } },
  { id: "whatsapp", icon: "chat", name: "WhatsApp için", desc: "MP4 · JPG · HD",
    set: { targets: { video: "mp4", image: "jpg", audio: "m4a" }, quality: "balanced", size: "hd" } },
  { id: "email", icon: "mail", name: "E-postaya sığdır", desc: "En küçük dosya · HD",
    set: { targets: { image: "jpg", video: "mp4", audio: "mp3" }, quality: "small", size: "hd" } },
  { id: "archive", icon: "box", name: "Kayıpsız arşiv", desc: "PNG · FLAC · MKV",
    set: { targets: { image: "png", audio: "flac", video: "mkv" }, quality: "original", size: "original" } },
  { id: "music", icon: "music", name: "Müziği çıkar", desc: "Videodan MP3 · 320 kb/sn",
    set: { targets: { video: "mp3", audio: "mp3" }, quality: "original", size: "original" } },
  { id: "icon", icon: "grid", name: "Simge yap", desc: "ICO · 16–256 piksel", set: { targets: { image: "ico" }, size: "original" } },
];
const CONV_KINDS = { image: "Resimler", video: "Videolar", audio: "Sesler" };
const CONV_SIDE = { hd: 1280, fhd: 1920, "2k": 2560, "4k": 3840 };
const CONV_LOSSLESS = new Set(["bmp", "tiff", "ico", "wav", "flac", "pdf"]);
const CONV_AUDIO_OUT = new Set(["mp3", "m4a", "wav", "flac", "ogg", "opus"]);
const CONV_NO_ALPHA = new Set(["jpg", "bmp", "pdf"]);
const conv = { files: [], targets: { image: "webp", video: "mp4", audio: "mp3" }, tasks: new Map(), results: [],
  preset: null, estimates: new Map(), estTimer: 0, estToken: 0, background: "#ffffff" };

function convBytes(n) {
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return n.toLocaleString(I18N.lang || "tr", { maximumFractionDigits: i >= 2 ? 1 : 0 }) + " " + units[i];
}

function convDur(sec) {
  const s = Math.round(sec), hh = Math.floor(s / 3600), mm = Math.floor((s % 3600) / 60), ss = String(s % 60).padStart(2, "0");
  return hh ? `${hh}:${String(mm).padStart(2, "0")}:${ss}` : `${mm}:${ss}`;
}

function convOpts() {
  return {
    targets: conv.targets, quality: segs.convQuality.value, size: segs.convSize.value,
    width: Number($("#convW").value) || 0, height: Number($("#convH").value) || 0, fit: segs.convFit.value,
    place: segs.convPlace.value, strip: $("#convStrip").checked, merge_pdf: $("#convMerge").checked,
    rotate: Number(segs.convRotate.value) || 0, background: conv.background,
    trim_start: parseTime($("#convTrimStart").value) || 0, trim_end: parseTime($("#convTrimEnd").value) || 0,
    fps: Number(segs.convFps.value) || 0, mute: $("#convMute").checked, normalize: $("#convNormalize").checked,
    mono: $("#convMono").checked, suffix: $("#convSuffix").checked,
  };
}

// Python'daki convert.target_size ile aynı hesap: satırlarda sonucun ölçüsünü göstermek için
function convTargetSize(f, o) {
  let w = f.width, hh = f.height;
  if (!w || !hh || f.kind === "audio") return null;
  if (o.rotate === 90 || o.rotate === 270) [w, hh] = [hh, w];
  let nw, nh, mode = "keep";
  if (o.size === "custom") {
    if (!o.width && !o.height) return o.rotate ? { w, h: hh, up: false } : null;
    if (o.fit !== "keep" && o.width && o.height) { nw = o.width; nh = o.height; mode = o.fit; }
    else {
      const s = Math.min(o.width ? o.width / w : Infinity, o.height ? o.height / hh : Infinity);
      nw = Math.round(w * s); nh = Math.round(hh * s);
    }
  } else {
    const side = CONV_SIDE[o.size];
    if (!side) return o.rotate ? { w, h: hh, up: false } : null;
    const s = side / Math.max(w, hh);
    nw = Math.round(w * s); nh = Math.round(hh * s);
  }
  if (f.kind === "video") { nw = Math.max(2, Math.floor(nw / 2) * 2); nh = Math.max(2, Math.floor(nh / 2) * 2); }
  return nw === w && nh === hh && mode === "keep" && !o.rotate ? null : { w: nw, h: nh, up: nw * nh > w * hh };
}

function convMeta(f) {
  const parts = [f.ext.toUpperCase()];
  if (f.width) parts.push(`${f.width}×${f.height}`);
  if (f.duration) parts.push(convDur(f.duration));
  parts.push(convBytes(f.bytes));
  return parts.join(" · ");
}

function convKinds() { return ["image", "video", "audio"].filter((k) => conv.files.some((f) => f.kind === k)); }

function convDiff(before, after) {
  const d = Math.round((1 - after / before) * 100);
  return Math.abs(d) < 1 ? null : { text: tr(d > 0 ? `%${d} küçük` : `%${-d} büyük`), good: d > 0 };
}

function convRender() {
  const has = conv.files.length > 0;
  $("#convWork").classList.toggle("hidden", !has);
  $("#convDrop").classList.toggle("compact", has);
  if (!has) return;
  const o = convOpts();
  const total = conv.files.reduce((s, f) => s + f.bytes, 0);
  $("#convCount").textContent = tr(conv.files.length === 1 ? "1 dosya" : `${conv.files.length} dosya`) + " · " + convBytes(total);

  // dosya satırları: kaynak → hedef (ölçü, tahmini boyut)
  $("#convFiles").replaceChildren(...conv.files.map((f) => {
    const target = conv.targets[f.kind];
    const size = target && !CONV_AUDIO_OUT.has(target) && target !== "ico" ? convTargetSize(f, o) : null;
    const est = conv.estimates.get(f.path);
    const diff = est ? convDiff(f.bytes, est.bytes) : null;
    const state = f.state || "";
    const out = h("div", { class: "cf-out" }, h("b", { "data-no-i18n": true }, txt((target || "?").toUpperCase())),
      size ? h("small", { class: size.up ? "up" : "" }, txt(`${size.w}×${size.h}`), size.up ? txt(" · " + tr("büyütülecek")) : null) : null,
      est ? h("small", { class: "est" }, txt(`${est.exact ? "" : "≈ "}${convBytes(est.bytes)}`),
        diff ? h("span", { class: diff.good ? "good" : "bad" }, txt(" · " + diff.text)) : null) : null);
    const status = state === "running" ? h("div", { class: "cf-bar" }, h("i", { style: `width:${Math.round((f.frac || 0) * 100)}%` }))
      : state === "done" ? h("span", { class: "cf-ok", title: "Hazır" }, icon("check"))
      : state === "error" ? h("span", { class: "cf-err", title: f.error || "" }, icon("alert"))
      : state === "pending" ? h("span", { class: "cf-wait" }, "Sırada") : null;
    return h("div", { class: "cf-row " + state },
      h("div", { class: "cf-thumb " + f.kind }, f.thumb ? h("img", { src: f.thumb, alt: "" }) : icon(f.kind === "audio" ? "music" : f.kind === "video" ? "film" : "image")),
      h("div", { class: "cf-body" }, h("b", { title: f.path, "data-no-i18n": true }, txt(f.name)), h("small", { "data-no-i18n": true }, txt(convMeta(f)))),
      h("span", { class: "cf-arrow" }, icon("arrowRight")), out,
      h("div", { class: "cf-state" }, status),
      h("button", { class: "btn icon sm ghost", title: "Listeden çıkar", disabled: state === "running" ? true : null,
        onclick: () => { conv.files = conv.files.filter((x) => x !== f); convChanged(); } }, icon("x")));
  }));

  // hazır ayarlar
  $("#convPresets").replaceChildren(...CONV_PRESETS.map((p) => h("button", {
    class: "cpreset" + (conv.preset === p.id ? " on" : ""), onclick: () => convPreset(p) },
    h("span", { class: "cp-ic" }, icon(p.icon)), h("span", { class: "cp-txt" }, h("b", {}, p.name), h("small", {}, p.desc)))));

  // hedef biçim kartları: listede bulunan her tür için ayrı
  const kinds = convKinds();
  $("#convFormats").replaceChildren(...kinds.map((k) => h("div", { class: "cfmt-group" },
    kinds.length > 1 ? h("div", { class: "cfmt-label" }, CONV_KINDS[k]) : null,
    h("div", { class: "cfmt-grid" }, ...CONV_FORMATS[k].map(([ext, desc], i) => h("button", {
      class: "cfmt" + (conv.targets[k] === ext ? " on" : ""), onclick: () => { conv.targets[k] = ext; conv.preset = null; convChanged(); },
    }, h("b", { "data-no-i18n": true }, txt(ext.toUpperCase())), h("small", {}, desc), i === 0 ? h("span", { class: "cfmt-tag" }, "Önerilen") : null))))));

  // kalite: kayıpsız biçimlerde anlamsız
  const chosen = kinds.map((k) => conv.targets[k]);
  const lossless = chosen.every((t) => CONV_LOSSLESS.has(t));
  $("#convQuality").classList.toggle("disabled", lossless);
  $("#convQualityHint").textContent = tr(convQualityHint(o.quality, chosen, lossless));

  // boyut: yalnızca ses varsa gizli
  const visual = conv.files.some((f) => f.kind !== "audio" && !CONV_AUDIO_OUT.has(conv.targets[f.kind]));
  $("#convSizeRow").classList.toggle("hidden", !visual);
  $("#convCustom").classList.toggle("hidden", !visual || o.size !== "custom");
  const ups = conv.files.filter((f) => (convTargetSize(f, o) || {}).up).length;
  $("#convSizeHint").textContent = !visual ? "" : tr(o.size === "custom"
    ? { keep: "Oran korunur; en ya da boydan birini boş bırakabilirsin.", crop: "Tam bu ölçü olur; taşan kenarlar ortadan kırpılır.",
        stretch: "Tam bu ölçü olur; oran bozulabilir." }[o.fit]
    : o.size === "original" ? "Ölçü değişmez." : `Uzun kenar ${CONV_SIDE[o.size]} px olur; dikey ve yatay dosyada aynı.`)
    + (ups ? " " + tr(ups === 1 ? "1 dosya büyütülecek." : `${ups} dosya büyütülecek.`) : "");
  $("#convW").placeholder = tr(o.fit === "keep" && o.height && !o.width ? "otomatik" : "Genişlik");
  $("#convH").placeholder = tr(o.fit === "keep" && o.width && !o.height ? "otomatik" : "Yükseklik");

  // gelişmiş ayarlar: yalnızca listedeki türlere uyanlar görünür
  const hasImage = conv.files.some((f) => f.kind === "image");
  const timed = conv.files.some((f) => f.kind !== "image");
  const videoOut = conv.files.some((f) => f.kind === "video" && !CONV_AUDIO_OUT.has(conv.targets.video));
  const alphaOut = conv.files.some((f) => f.kind === "image" && f.alpha) && CONV_NO_ALPHA.has(conv.targets.image);
  $("#convAdvRotate").classList.toggle("hidden", !hasImage && !videoOut);
  $("#convAdvBg").classList.toggle("hidden", !alphaOut);
  $("#convAdvTrim").classList.toggle("hidden", !timed);
  $("#convAdvFps").classList.toggle("hidden", !videoOut);
  $("#convMuteRow").classList.toggle("hidden", !videoOut);
  $("#convNormalizeRow").classList.toggle("hidden", !timed);
  $("#convMonoRow").classList.toggle("hidden", !conv.files.some((f) => f.kind === "audio" || CONV_AUDIO_OUT.has(conv.targets[f.kind])));
  $$("#convBgSwatches button").forEach((b) => b.classList.toggle("on", b.dataset.v === conv.background));
  const advCount = [o.rotate, o.trim_start || o.trim_end, o.fps, o.mute, o.normalize, o.mono, o.suffix,
    alphaOut && o.background !== "#ffffff"].filter(Boolean).length;
  $("#convAdvBadge").textContent = advCount ? tr(advCount) : "";
  $("#convAdvBadge").classList.toggle("hidden", !advCount);

  $("#convMergeRow").classList.toggle("hidden", !(conv.targets.image === "pdf" && conv.files.filter((f) => f.kind === "image").length > 1));
  $("#convPlaceHint").textContent = tr(o.place === "beside" ? "Yeni dosya, aslının bulunduğu klasöre kaydedilir"
    : "İndirme klasöründeki “Dönüştürülenler” klasörüne kaydedilir");

  // özet: biçimler, kalite, ölçü ve tahmini toplam
  const qName = { original: "Orijinal kalite", high: "Yüksek kalite", balanced: "Dengeli kalite", small: "Küçük dosya" }[o.quality];
  const sizeName = o.size === "custom"
    ? (o.width && o.height ? `${o.width}×${o.height}` : o.width ? tr(`${o.width} px genişlik`) : o.height ? tr(`${o.height} px yükseklik`) : "")
    : o.size === "original" ? "" : $(`#convSize button[data-v="${o.size}"]`).textContent;
  const ests = conv.files.map((f) => conv.estimates.get(f.path)).filter(Boolean);
  const estTotal = ests.reduce((s, e) => s + e.bytes, 0);
  const estBase = conv.files.filter((f) => conv.estimates.has(f.path)).reduce((s, f) => s + f.bytes, 0);
  const estDiff = estBase ? convDiff(estBase, estTotal) : null;
  const estText = ests.length === conv.files.length && estTotal ? `≈ ${convBytes(estTotal)}` + (estDiff ? ` (${estDiff.text})` : "") : "";
  $("#convSummary").textContent = tr(conv.files.length === 1 ? "1 dosya" : `${conv.files.length} dosya`) + " → "
    + chosen.map((t) => t.toUpperCase()).join(", ");
  $("#convSummary2").textContent = [lossless ? tr("Kayıpsız") : tr(qName), visual && sizeName ? sizeName : "", estText].filter(Boolean).join(" · ");
  $("#convGo").disabled = conv.files.some((f) => f.state === "running" || f.state === "pending");
  requestAnimationFrame(() => ["convQuality", "convSize", "convFit", "convPlace", "convRotate", "convFps"].forEach((id) => segs[id] && segs[id].refresh()));
}

function convQualityHint(q, chosen, lossless) {
  if (lossless) return "Seçtiğin biçim kayıpsız; kalite ayarı gerekmez.";
  const video = chosen.some((t) => ["mp4", "webm", "mov", "mkv"].includes(t));
  if (q === "original") return video ? "Mümkünse yeniden kodlamadan aktarılır: kayıpsız ve saniyeler sürer."
    : "Hiç kalite kaybı olmaz (WEBP/PNG kayıpsız, JPG %100); dosya büyük olabilir.";
  if (q === "high") return "Gözle fark edilmeyen kayıp, belirgin şekilde küçük dosya.";
  if (q === "balanced") return "Paylaşmak ve göndermek için ideal denge.";
  return chosen.includes("png") ? "En küçük dosya; PNG 256 renge indirilir (ekran görüntülerinde fark edilmez)."
    : "En küçük dosya; ince ayrıntılarda hafif kayıp olabilir.";
}

// Bir ayar değişince: görünümü yenile, tahmini boyutu kısa bir beklemeden sonra yeniden hesapla
function convChanged(keepPreset = false) {
  if (!keepPreset) conv.preset = null;
  convRender();
  clearTimeout(conv.estTimer);
  conv.estTimer = setTimeout(convEstimate, 450);
}

async function convEstimate() {
  const files = conv.files.filter((f) => f.state !== "running");
  if (!files.length) return;
  const token = ++conv.estToken;
  const list = await api.convert_estimate({ ...convOpts(), files: files.map((f) => ({ path: f.path, kind: f.kind, bytes: f.bytes,
    width: f.width, height: f.height, duration: f.duration })) });
  if (token !== conv.estToken) return;  // bu arada ayar değiştiyse eski sonuç gösterilmez
  conv.estimates = new Map(list.map((e) => [e.path, e]));
  convRender();
}

function convPreset(p) {
  Object.assign(conv.targets, p.set.targets || {});
  if (p.set.quality) segs.convQuality.set(p.set.quality);
  if (p.set.size) segs.convSize.set(p.set.size);
  if (p.set.size === "custom") {
    $("#convW").value = p.set.width || "";
    $("#convH").value = p.set.height || "";
    segs.convFit.set(p.set.fit || "keep");
  }
  conv.preset = p.id;
  convChanged(true);
  toast(tr("{name} ayarları seçildi", { name: tr(p.name) }), "ok");
}

function convAdd(items, skipped) {
  const known = new Set(conv.files.map((f) => f.path));
  const fresh = items.filter((f) => !known.has(f.path));
  conv.files.push(...fresh);
  if (skipped) toast(skipped === 1 ? "1 dosya desteklenmiyor" : `${skipped} dosya desteklenmiyor`, "err");
  else if (items.length && !fresh.length) toast("Bu dosyalar zaten listede");
  convChanged(true);
}

async function convPick() {
  const r = await api.convert_pick();
  if (r) convAdd(r.items, r.skipped);
}

async function convPickFolder() {
  const r = await api.convert_pick_folder();
  if (r && r.items.length) convAdd(r.items, r.skipped);
  else if (r) toast("Bu klasörde dönüştürülebilir dosya bulunamadı.");
}

async function convGo() {
  const files = conv.files.filter((f) => f.state !== "done");
  if (!files.length) { toast("Dönüştürülecek yeni dosya yok. Biçimi değiştirdiysen dosyaları yeniden ekle.", "err"); return; }
  const o = convOpts();
  if (o.size === "custom" && !o.width && !o.height) { toast("Özel boyut için en ya da boy girin.", "err"); $("#convW").focus(); return; }
  if (o.trim_end && o.trim_end <= o.trim_start) { toast("Kesme bitişi başlangıçtan sonra olmalı.", "err"); $("#convTrimEnd").focus(); return; }
  const r = await api.convert_start({ ...o, files: files.map((f) => ({ path: f.path, kind: f.kind, width: f.width, height: f.height })) });
  if (!r.ok) { toast(r.error, "err"); return; }
  for (const t of r.tasks) {
    conv.tasks.set(t.id, t.paths);
    files.filter((f) => t.paths.includes(f.path)).forEach((f) => { f.state = "pending"; f.frac = 0; });
  }
  convRender();
  flyToQueue($("#convGo"));
}

function convOnItem(it) {
  // kuyruktaki dönüştürme işinin durumu, sayfadaki dosya satırlarına yansır
  const paths = conv.tasks.get(it.id);
  if (!paths) return;
  const state = it.state === "running" ? "running" : it.state === "done" ? "done"
    : it.state === "error" || it.state === "cancelled" ? "error" : "pending";
  conv.files.filter((f) => paths.includes(f.path)).forEach((f) => {
    // grup bitti ama bazı dosyalar çevrilemediyse uyarıda adları geçer: yalnızca onlar hatalı görünür
    const failed = state === "error" || (state === "done" && it.error && it.error.includes(f.name + ":"));
    f.state = failed ? "error" : state;
    f.frac = it.frac || 0;
    f.error = failed ? it.error : "";
  });
  convRender();
}

async function convDone(ev) {
  if (!conv.tasks.has(ev.id)) return;
  const sources = conv.files.filter((f) => conv.tasks.get(ev.id).includes(f.path));
  const infos = await api.convert_info(ev.files);
  for (const info of infos) {
    // aynı adlı kaynakla eşleştir ("ad (1).webp", "ad-1920x1080.webp" → "ad")
    const stem = info.name.replace(/( \(\d+\))?\.[^.]+$/, "").replace(/-\d+x\d+$/, "").toLowerCase();
    const src = sources.find((f) => f.name.replace(/\.[^.]+$/, "").toLowerCase() === stem) || (sources.length === 1 ? sources[0] : null);
    conv.results.unshift({ ...info, before: src ? src.bytes : null, source: src ? src.path : null, kind: src ? src.kind : "",
      sourceExt: src ? src.ext : "" });
  }
  renderConvResults();
}

function renderConvResults() {
  const res = conv.results.slice(0, 80);
  $("#convResults").classList.toggle("hidden", !res.length);
  const before = res.filter((r) => r.before).reduce((s, r) => s + r.before, 0);
  const after = res.filter((r) => r.before).reduce((s, r) => s + r.bytes, 0);
  const diff = before ? convDiff(before, after) : null;
  $("#convResultsSum").textContent = before ? `${convBytes(before)} → ${convBytes(after)}` + (diff ? ` · ${diff.text}` : "") : "";
  $("#convResultList").replaceChildren(...res.map((r) => {
    const d = r.before ? convDiff(r.before, r.bytes) : null;
    const canCompare = r.kind === "image" && r.source && !/^(heic|heif|tif|tiff|ico|pdf)$/i.test(r.sourceExt)
      && /\.(png|jpe?g|webp|avif|gif|bmp)$/i.test(r.name);
    return h("div", { class: "cr-row" },
      h("span", { class: "cr-ic" }, icon("file")),
      h("div", { class: "cr-body" }, h("b", { title: r.path, "data-no-i18n": true }, txt(r.name)),
        h("small", {}, txt(r.before ? `${convBytes(r.before)} → ${convBytes(r.bytes)}` : convBytes(r.bytes)))),
      d ? h("span", { class: "chip " + (d.good ? "ok" : "") }, txt(d.text)) : null,
      canCompare ? h("button", { class: "btn sm", onclick: () => convCompare(r) }, icon("sliders"), "Karşılaştır") : null,
      h("button", { class: "btn sm", onclick: () => api.open_made(r.path) }, icon("play"), "Aç"),
      h("button", { class: "btn icon sm rv", title: "Klasörde göster", onclick: () => api.reveal_made(r.path) }, icon("folder")));
  }));
}

// Önce/sonra: iki resim üst üste, sürgü sonrakini soldan sağa açar
async function convCompare(r) {
  const urls = await api.convert_preview([r.source, r.path]);
  const a = urls[r.source], b = urls[r.path];
  if (!a || !b) { toast("Bu dosya önizlenemiyor.", "err"); return; }
  $("#cmpBefore").src = a;
  $("#cmpAfter").src = b;
  $("#cmpBeforeLabel").textContent = tr("Önce") + " · " + r.sourceExt.toUpperCase() + " · " + convBytes(r.before);
  $("#cmpAfterLabel").textContent = tr("Sonra") + " · " + r.name.split(".").pop().toUpperCase() + " · " + convBytes(r.bytes);
  $("#cmpRange").value = 50;
  convCompareMove();
  $("#cmpOverlay").classList.remove("hidden");
}

function convCompareMove() {
  const v = Number($("#cmpRange").value);
  $("#cmpAfterWrap").style.clipPath = `inset(0 0 0 ${v}%)`;
  $("#cmpHandle").style.left = v + "%";
}

function wireConvert() {
  seg("convQuality", () => convChanged()).set("high");
  seg("convSize", (v) => { convChanged(); if (v === "custom") $("#convW").focus(); }).set("original");
  seg("convFit", () => convChanged()).set("keep");
  seg("convPlace", () => convChanged()).set("beside");
  seg("convRotate", () => convChanged()).set("0");
  seg("convFps", () => convChanged()).set("0");
  ["#convW", "#convH", "#convTrimStart", "#convTrimEnd"].forEach((s) => $(s).addEventListener("input", () => convChanged()));
  ["#convStrip", "#convMerge", "#convMute", "#convNormalize", "#convMono", "#convSuffix"].forEach((s) =>
    $(s).addEventListener("change", () => convChanged()));
  $$("#convBgSwatches button").forEach((b) => b.addEventListener("click", () => {
    if (b.classList.contains("pick")) { $("#convBgCustom").click(); return; }
    conv.background = b.dataset.v;
    convChanged();
  }));
  $("#convBgCustom").addEventListener("input", (e) => {
    const pick = $("#convBgSwatches .pick");
    conv.background = e.target.value;
    pick.dataset.v = e.target.value;
    pick.style.background = e.target.value;
    convChanged();
  });
  $("#convDrop").addEventListener("click", convPick);
  $("#convAddMore").addEventListener("click", convPick);
  $("#convAddFolder").addEventListener("click", convPickFolder);
  $("#convDropFolder").addEventListener("click", (e) => { e.stopPropagation(); convPickFolder(); });
  $("#convClear").addEventListener("click", () => {
    conv.files = conv.files.filter((f) => f.state === "running" || f.state === "pending");
    conv.estimates.clear();
    convRender();
  });
  $("#convGo").addEventListener("click", convGo);
  $("#convOpenFolder").addEventListener("click", () => conv.results.length && api.reveal_made(conv.results[0].path));
  $("#cmpRange").addEventListener("input", convCompareMove);
  $("#cmpClose").addEventListener("click", () => $("#cmpOverlay").classList.add("hidden"));
  $("#cmpOverlay").addEventListener("click", (e) => { if (e.target.id === "cmpOverlay") $("#cmpOverlay").classList.add("hidden"); });
  // pencerenin herhangi bir yerine dosya sürüklenince bırakma alanı belirsin. Sürükleme nasıl biterse bitsin
  // (bırakma, Esc, pencereden çıkma) dragover akışı durur; bir süre gelmezse perde kendiliğinden kalkar.
  let veilTimer = 0;
  const hasFiles = (e) => e.dataTransfer && [...e.dataTransfer.types].includes("Files");
  const hideVeil = () => { clearTimeout(veilTimer); document.body.classList.remove("files-over"); };
  const holdVeil = (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault();  // bırakma kabul edilsin; WebView dosyayı kendisi açmaya kalkmasın
    document.body.classList.add("files-over");
    clearTimeout(veilTimer);
    veilTimer = setTimeout(hideVeil, 700);
  };
  const outside = (e) => e.clientX <= 0 || e.clientY <= 0 || e.clientX >= innerWidth || e.clientY >= innerHeight;
  document.addEventListener("dragenter", holdVeil);
  document.addEventListener("dragover", holdVeil);
  document.addEventListener("dragleave", (e) => { if (!e.relatedTarget && outside(e)) hideVeil(); });
  document.addEventListener("drop", (e) => { if (hasFiles(e)) e.preventDefault(); hideVeil(); });
  const prevItem = HANDLERS.item, prevDone = HANDLERS.studio_done;
  Object.assign(HANDLERS, {
    convert_files: (ev) => { showPage("convert"); convAdd(ev.items, ev.skipped); },
    item: (ev) => { if (prevItem) prevItem(ev); convOnItem(ev.item); },
    studio_done: (ev) => { if (prevDone) prevDone(ev); if (ev.kind === "convert") convDone(ev); },
  });
}
