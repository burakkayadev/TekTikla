/* Arayüz çevirisi. Kaynak dil Türkçedir; çeviri tablosu Türkçe metni anahtar olarak kullanır
 * (Python tarafı tektikla/web/i18n/<dil>.json dosyasını yükleyip gönderir). Tabloda olmayan metin
 * Türkçe kalır. Sayı içeren metinler "{0}" kalıbıyla eşleşir: "Seslendiriliyor (3/5)" -> "Seslendiriliyor ({0}/{1})". */
"use strict";

const I18N = { table: {}, lang: "tr", originals: new WeakMap(), attrs: new WeakMap() };
const NUM_RE = /\d+(?:[.,]\d+)?/g;

function tr(text, vars) {
  if (text === null || text === undefined) return "";
  const s = String(text);
  let out;
  if (I18N.lang !== "tr" && s.trim()) {
    const tbl = I18N.table;
    const core = s.trim();
    out = tbl[core];
    if (out === undefined && /\d/.test(core)) {
      const nums = core.match(NUM_RE);
      let i = 0;
      const hit = tbl[core.replace(NUM_RE, () => `{${i++}}`)];
      if (hit !== undefined) out = hit.replace(/\{(\d+)\}/g, (m, k) => (nums[+k] !== undefined ? nums[+k] : m));
    }
    if (out !== undefined && core !== s) out = s.replace(core, out);  // baştaki/sondaki boşluklar kalsın
  }
  if (out === undefined) out = s;
  if (vars) out = out.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m));
  return out;
}

/* h() ile oluşturulan metinler ve title/placeholder çevrilir; dil değişince yeniden çevrilebilsin diye
 * Türkçe asılları saklanır. Siteden gelen başlıklar tabloda olmadığından olduğu gibi kalır. */
const _h = h;
h = function (tag, attrs = {}, ...children) {
  const a = { ...attrs };
  const skip = !!a["data-no-i18n"];
  if (!skip) {
    if (typeof a.title === "string") a.title = tr(a.title);
    if (typeof a.placeholder === "string") a.placeholder = tr(a.placeholder);
  }
  const kids = children.flat().map((c) => {
    if (skip || typeof c !== "string") return c;
    const node = document.createTextNode(tr(c));
    I18N.originals.set(node, c);
    return node;
  });
  return _h(tag, a, ...kids);
};

const _toast = toast;
toast = function (text, kind) { return _toast(tr(text), kind); };

function applyI18n(table, lang, rtl) {
  I18N.table = table || {};
  I18N.lang = lang || "tr";
  document.documentElement.lang = I18N.lang;
  document.documentElement.dir = rtl ? "rtl" : "ltr";
  // iki parçalı başlıklar (<span>Görsel</span> Stüdyosu): başka dilde kelime sırası değişir, bütün olarak çevrilir
  for (const el of document.querySelectorAll("[data-i18n-whole]")) {
    if (el.dataset.orig === undefined) el.dataset.orig = el.innerHTML;
    const whole = I18N.lang !== "tr" && I18N.table[el.dataset.i18nWhole];
    if (whole) el.replaceChildren(Object.assign(document.createElement("span"), { className: "grad-text", textContent: whole }));
    else el.innerHTML = el.dataset.orig;  // kendi sabit HTML'imiz
  }
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
    acceptNode(n) {
      const p = n.parentElement;
      if (!p || p.closest("script, style, [data-no-i18n]")) return NodeFilter.FILTER_REJECT;
      return n.nodeValue.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
    },
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const n of nodes) {
    let orig = I18N.originals.get(n);
    if (orig === undefined) { orig = n.nodeValue; I18N.originals.set(n, orig); }
    n.nodeValue = tr(orig);
  }
  for (const el of document.querySelectorAll("[placeholder], [title]")) {
    if (el.closest("[data-no-i18n]")) continue;
    let o = I18N.attrs.get(el);
    if (!o) { o = { placeholder: el.getAttribute("placeholder"), title: el.getAttribute("title") }; I18N.attrs.set(el, o); }
    if (o.placeholder) el.setAttribute("placeholder", tr(o.placeholder));
    if (o.title) el.setAttribute("title", tr(o.title));
  }
  setTimeout(() => { Object.values(segs).forEach((s) => s.refresh()); moveIndicator(); }, 40);
}
