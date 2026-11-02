/* Görsel düzenleyici (Görsel > Görseli düzenle): kırpma, döndürme, ışık ve renk ayarları, filtreler, metin, şekil,
 * emoji, çizim ve sansür. Renk ayarları WebGL'de tek geçişte uygulanır; metin ve şekiller üstüne 2B tuvalle çizilir.
 * Önizleme en fazla 2048 piksellik kopya üzerinde çalışır; kaydederken her şey görselin kendi boyutunda yeniden çizilir.
 * Katmanların konum ve ölçüleri karenin genişliğine/yüksekliğine oranla tutulur (0–1): her çözünürlükte aynı durur.
 * Python tarafı: studio_api.py (editor_pick, editor_url, editor_recent, editor_save). */
"use strict";

Object.assign(ICONS, {
  pen: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  crop: '<path d="M6 2v14a2 2 0 0 0 2 2h14"/><path d="M18 22V8a2 2 0 0 0-2-2H2"/>',
  undo: '<path d="M9 14L4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
  redo: '<path d="M15 14l5-5-5-5"/><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/>',
  minus: '<path d="M5 12h14"/>',
  compare: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M12 2v20"/><path d="M16 9l2 3-2 3M8 9l-2 3 2 3"/>',
  rotL: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
  rotR: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
  flipH: '<path d="M12 3v18"/><path d="M8 7l-5 5 5 5zM16 7l5 5-5 5z"/>',
  flipV: '<path d="M3 12h18"/><path d="M7 8l5-5 5 5zM7 16l5 5 5-5z"/>',
  shapes: '<rect x="3" y="3" width="8" height="8" rx="1.5"/><circle cx="17" cy="17" r="4"/><path d="M17 3l4 7h-8z"/>',
  brush: '<path d="M18.4 2.6a2 2 0 0 1 2.9 2.9L11 15.8 8.2 13z"/><path d="M7.5 14.5c-2 0-3.5 1.5-3.5 3.4 0 1.2-.7 2-2 2.4 1 .9 2.4 1.4 3.8 1.4a4.3 4.3 0 0 0 4.3-4.3z"/>',
  pixels: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>',
  layers: '<path d="M12 2l10 5-10 5L2 7z"/><path d="M2 12l10 5 10-5"/><path d="M2 17l10 5 10-5"/>',
  eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  eyeOff: '<path d="M3 3l18 18"/><path d="M10.6 5.1A10 10 0 0 1 12 5c6.4 0 10 7 10 7a17 17 0 0 1-3.2 4.2M6.6 6.6C3.9 8.4 2 12 2 12s3.6 7 10 7a9.7 9.7 0 0 0 5.4-1.6"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
  rect: '<rect x="3" y="5" width="18" height="14" rx="2"/>',
  circle: '<circle cx="12" cy="12" r="9"/>',
  line: '<path d="M5 19L19 5"/>',
  arrowTool: '<path d="M5 19L19 5M9 5h10v10"/>',
  marker: '<path d="M9 11l-6 6v3h9l3-3"/><path d="M22 12l-4.6 4.6a2 2 0 0 1-2.8 0l-5.2-5.2a2 2 0 0 1 0-2.8L14 4"/>',
  alignL: '<path d="M3 6h18M3 12h12M3 18h16"/>',
  alignC: '<path d="M3 6h18M6 12h12M4 18h16"/>',
  alignR: '<path d="M3 6h18M9 12h12M5 18h16"/>',
  italic: '<path d="M19 4h-9M14 20H5M15 4L9 20"/>',
  caps: '<path d="M3 18l5-12 5 12M4.7 14h6.6M14 18l3.5-9 3.5 9M15.2 15h4.6"/>',
});

const ED_WORK = 2048;  // önizleme kopyasının uzun kenarı
// ayarlar: [anahtar, etiket, en az, en çok]
const ED_ADJ = {
  light: [["exposure", "Pozlama"], ["brightness", "Parlaklık"], ["contrast", "Kontrast"], ["highlights", "Açık tonlar"],
    ["shadows", "Gölgeler"], ["fade", "Soluklaştır", 0]],
  color: [["temperature", "Sıcaklık"], ["tint", "Renk tonu"], ["saturation", "Doygunluk"], ["vibrance", "Canlılık"],
    ["hue", "Ton kaydırma", -180, 180]],
  detail: [["sharpen", "Netlik", 0], ["vignette", "Vinyet"], ["grain", "Gren", 0]],
};
// filtre = ayarlara eklenen değerler (+ siyah-beyaz ve gölge/ışık renklendirmesi), yoğunlukla ölçeklenir
const ED_FILTERS = [
  { id: "none", name: "Orijinal" },
  { id: "vivid", name: "Canlı", p: { contrast: 15, saturation: 22, vibrance: 25 } },
  { id: "warm", name: "Sıcak", p: { temperature: 35, saturation: 6, highlights: 6 } },
  { id: "cool", name: "Soğuk", p: { temperature: -32, tint: -6, contrast: 6 } },
  { id: "cinema", name: "Sinematik", p: { contrast: 18, fade: 12, saturation: -12, vignette: 18 }, split: [[0.15, 0.45, 0.5], [1, 0.62, 0.32], 0.9] },
  { id: "golden", name: "Altın saat", p: { temperature: 45, tint: 8, highlights: 10, vibrance: 12, vignette: 14 } },
  { id: "matte", name: "Mat", p: { fade: 40, contrast: -12, saturation: -12 } },
  { id: "pastel", name: "Pastel", p: { brightness: 16, saturation: -28, fade: 22, highlights: 8 } },
  { id: "drama", name: "Dram", p: { contrast: 38, shadows: -22, highlights: -22, vibrance: 22, vignette: 28, sharpen: 25 } },
  { id: "retro", name: "Eskitme", p: { fade: 26, saturation: -22, grain: 22, vignette: 30, temperature: 18 }, split: [[0.35, 0.25, 0.45], [1, 0.86, 0.62], 0.7] },
  { id: "bw", name: "Siyah-beyaz", p: { contrast: 16 }, mono: 1 },
  { id: "noir", name: "Noir", p: { contrast: 48, vignette: 42, shadows: -16, grain: 12 }, mono: 1 },
];
const ED_FONTS = [["Geist", "Geist"], ["Bricolage Grotesque", "Bricolage"], ["Unbounded", "Unbounded"],
  ["TekTikla Black", "Kalın"], ["TekTikla Condensed", "Dar"], ["TekTikla Display", "Gösteriş"], ["Fraunces", "Fraunces"],
  ["Instrument Serif", "Instrument"], ["Impact", "Impact"], ["Bahnschrift", "Bahnschrift"], ["Georgia", "Georgia"],
  ["Comic Sans MS", "Comic Sans"], ["Segoe Script", "Script"], ["Consolas", "Consolas"], ["Segoe UI", "Segoe UI"]];
const ED_COLORS = ["#FFFFFF", "#111111", "#FFD60A", "#FF9500", "#FF3B30", "#FF2D55", "#BF5AF2", "#0A84FF", "#34C759"];
const ED_EMOJI = ["🔥", "😱", "😂", "🤯", "😍", "👀", "💯", "✅", "❌", "⭐", "❤️", "👉", "👈", "⚡", "💰", "🎉", "📌", "🚀"];
const ED_TEXT = {  // hazır yazı stilleri
  title: { text: "BAŞLIK", font: "TekTikla Black", weight: 400, size: 0.14, color: "#FFFFFF", stroke: 16, shadow: 45, upper: true, cy: 0.5 },
  body: { text: "Metnini buraya yaz", font: "Geist", weight: 600, size: 0.065, color: "#FFFFFF", shadow: 50, cy: 0.8 },
  label: { text: "YENİ", font: "Unbounded", weight: 800, size: 0.055, color: "#111111", bg: true, bgColor: "#FFD60A", bgAlpha: 100, upper: true, cy: 0.16 },
};
const ED_TYPE = {  // katman türü: simge, ad, seçilince açılan sekme
  text: ["type", "Metin", "text"], rect: ["rect", "Dikdörtgen", "shape"], ellipse: ["circle", "Daire", "shape"],
  line: ["line", "Çizgi", "shape"], arrow: ["arrowTool", "Ok", "shape"], draw: ["brush", "Çizim", "layers"],
  censor: ["pixels", "Sansür", "censor"],
};

const ed = {
  img: null, W: 0, H: 0, name: "", doc: null, cur: "", hist: [], fut: [], tab: "adjust", sel: null,
  zoom: 0, scale: 1, fit: 1, panX: 0, panY: 0, comparing: false, drag: null, space: false, queued: false,
  orient: null, orientKey: "", base: null, baseKey: "", glKey: "", gl: undefined, thumbs: null, thumbKey: "",
  guides: null, nudged: 0, lastSaved: "", fmt: "jpg", quality: 92, size: "orig",
  drawOpt: { mode: "pen", color: "#FF3B30", size: 1.2, opacity: 100 }, censorOpt: { mode: "pixel", strength: 60 },
};
let edSeq = 0;
const edClamp = (v, a, b) => Math.min(b, Math.max(a, v));
const edRemote = () => document.body.classList.contains("remote");
const edLayer = (id) => ed.doc && ed.doc.layers.find((l) => l.id === id);
const edJSON = () => JSON.stringify(ed.doc, (k, v) => (k.startsWith("_") ? undefined : v));
const edSigned = (v) => (v > 0 ? "+" : "") + v;
const edPctFmt = {};
const edPct = (v) => {  // dile göre yüzde: Türkçede %92, İngilizcede 92%
  const lang = I18N.lang || "tr";
  edPctFmt[lang] ||= new Intl.NumberFormat(lang, { style: "percent", maximumFractionDigits: 0, numberingSystem: "latn" });
  return edPctFmt[lang].format(v / 100);
};
const edVisible = () => $("#page-image").classList.contains("active") && $("#page-image").classList.contains("editing");

function edBlank() {
  const adj = {};
  for (const group of Object.values(ED_ADJ)) for (const [k] of group) adj[k] = 0;
  return { geo: { rot: 0, flipH: false, flipV: false, angle: 0, crop: null, aspect: "free" }, adj,
    filter: { id: "none", amount: 100 }, layers: [] };
}

/* ---------------------------------------------------------------- geçmiş (geri al / yinele) */
function edCommit() {
  const s = edJSON();
  if (s === ed.cur) return;
  ed.hist.push(ed.cur);
  if (ed.hist.length > 80) ed.hist.shift();
  ed.cur = s;
  ed.fut = [];
  edToolbar();
}

function edUndo(back = true) {
  const from = back ? ed.hist : ed.fut, to = back ? ed.fut : ed.hist;
  if (!ed.img || !from.length) return;
  to.push(ed.cur);
  ed.cur = from.pop();
  ed.doc = JSON.parse(ed.cur);
  if (ed.sel && !edLayer(ed.sel)) ed.sel = null;
  edPanel();
  edToolbar();
  edQueue();
}

/* ---------------------------------------------------------------- geometri */
const edOriented = () => (ed.doc.geo.rot % 180 ? [ed.H, ed.W] : [ed.W, ed.H]);
const edCrop = () => ed.doc.geo.crop || { x: 0, y: 0, w: 1, h: 1 };
// gösterilen karenin tam çözünürlükteki ölçüsü (kırpma sekmesinde kırpılmamış hâli)
function edFrame(full = ed.tab === "crop") {
  const [ow, oh] = edOriented(), c = full ? { w: 1, h: 1 } : edCrop();
  return [ow * c.w, oh * c.h];
}

function edCanvas(w, hh) {
  const c = document.createElement("canvas");
  c.width = Math.max(1, Math.round(w));
  c.height = Math.max(1, Math.round(hh));
  return c;
}

// kaynak → 90° döndürme, çevirme ve ince düzeltme; istenirse yalnızca kırpılan bölge (istenen ölçekte)
function edGeo(scale, crop) {
  const g = ed.doc.geo, [ow, oh] = edOriented(), OW = ow * scale, OH = oh * scale;
  const c = crop || { x: 0, y: 0, w: 1, h: 1 };
  const out = edCanvas(OW * c.w, OH * c.h), x = out.getContext("2d");
  x.imageSmoothingQuality = "high";
  x.translate(OW / 2 - c.x * OW, OH / 2 - c.y * OH);
  if (g.angle) {  // eğiklik düzeltilirken köşelerde boşluk kalmasın diye görsel biraz büyütülür
    const a = (g.angle * Math.PI) / 180, cs = Math.abs(Math.cos(a)), sn = Math.abs(Math.sin(a));
    const k = Math.max((OW * cs + OH * sn) / OW, (OW * sn + OH * cs) / OH);
    x.rotate(a);
    x.scale(k, k);
  }
  x.scale(g.flipH ? -1 : 1, g.flipV ? -1 : 1);
  x.rotate((g.rot * Math.PI) / 180);
  const sw = g.rot % 180 ? OH : OW, sh = g.rot % 180 ? OW : OH;
  x.drawImage(ed.img, -sw / 2, -sh / 2, sw, sh);
  return out;
}

// önizlemenin temeli: döndürülmüş kopya önbellekte durur, kırpma ondan kesilir
function edBase() {
  const g = ed.doc.geo, [ow, oh] = edOriented(), s = Math.min(1, ED_WORK / Math.max(ow, oh));
  const okey = [g.rot, g.flipH, g.flipV, g.angle, s].join("|");
  if (okey !== ed.orientKey) {
    ed.orientKey = okey;
    ed.orient = edGeo(s);
    ed.baseKey = "";
  }
  const c = ed.tab === "crop" ? null : g.crop;
  const key = okey + "|" + (c ? [c.x, c.y, c.w, c.h].join(",") : "full");
  if (key !== ed.baseKey) {
    ed.baseKey = key;
    ed.glKey = "";
    if (!c) ed.base = ed.orient;
    else {
      const o = ed.orient;
      ed.base = edCanvas(o.width * c.w, o.height * c.h);
      ed.base.getContext("2d").drawImage(o, o.width * c.x, o.height * c.y, o.width * c.w, o.height * c.h,
        0, 0, ed.base.width, ed.base.height);
    }
  }
  return ed.base;
}

/* ---------------------------------------------------------------- renk ayarları (WebGL) */
const ED_VS = "attribute vec2 p; varying vec2 v; void main() { v = vec2(p.x * .5 + .5, .5 - p.y * .5); gl_Position = vec4(p, 0., 1.); }";
const ED_FS = `precision highp float;
varying vec2 v;
uniform sampler2D img;
uniform vec2 px, size;
uniform float exposure, brightness, contrast, highlights, shadows, fade, temperature, tint, saturation, vibrance, hue,
  sharpen, vignette, grain, mono, split;
uniform vec3 shTint, hiTint;
float luma(vec3 c) { return dot(c, vec3(.2126, .7152, .0722)); }
float rnd(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
void main() {
  vec4 s = texture2D(img, v);
  vec3 c = s.rgb;
  if (sharpen > 0.) {
    vec3 b = texture2D(img, v + vec2(px.x, 0.)).rgb + texture2D(img, v - vec2(px.x, 0.)).rgb
      + texture2D(img, v + vec2(0., px.y)).rgb + texture2D(img, v - vec2(0., px.y)).rgb;
    c += (c - b * .25) * sharpen * 2.;
  }
  c *= exp2(exposure);
  c += vec3(temperature * .1, tint * .08, -temperature * .1);
  c = (c - .5) * (1. + contrast * (contrast > 0. ? .9 : .7)) + .5;
  c = pow(max(c, 0.), vec3(exp2(-brightness * .8)));
  float l = luma(c);
  c += shadows * .3 * (1. - smoothstep(0., .55, l));
  c += highlights * .3 * smoothstep(.45, 1., l);
  l = luma(c);
  c = mix(vec3(l), c, 1. + saturation);
  float sat = max(c.r, max(c.g, c.b)) - min(c.r, min(c.g, c.b));
  c = mix(vec3(l), c, 1. + vibrance * (vibrance > 0. ? 1. - sat : 1.));
  if (hue != 0.) {
    const mat3 toY = mat3(.299, .596, .211, .587, -.274, -.523, .114, -.322, .312);
    const mat3 toR = mat3(1., 1., 1., .956, -.272, -1.106, .621, -.647, 1.703);
    vec3 y = toY * c;
    float a = atan(y.z, y.y) + hue, ch = length(y.yz);
    c = toR * vec3(y.x, ch * cos(a), ch * sin(a));
  }
  if (split > 0.) c += (mix(shTint, hiTint, smoothstep(.1, .9, clamp(luma(c), 0., 1.))) - .5) * .35 * split;
  c = mix(c, vec3(luma(c)), mono);
  c = c * (1. - fade * .22) + fade * .1;
  float vg = smoothstep(.45, 1.45, length((v - .5) * 2.));
  c = vignette > 0. ? c * (1. - vignette * vg * .8) : mix(c, vec3(1.), -vignette * vg * .6);
  if (grain > 0.) c += (rnd(v * size) - .5) * grain * .16;
  gl_FragColor = vec4(clamp(c, 0., 1.), s.a);
}`;
const ED_UNI = ["px", "size", "exposure", "brightness", "contrast", "highlights", "shadows", "fade", "temperature", "tint",
  "saturation", "vibrance", "hue", "sharpen", "vignette", "grain", "mono", "split", "shTint", "hiTint"];

function edGL() {
  if (ed.gl !== undefined) return ed.gl;
  ed.gl = null;
  const canvas = document.createElement("canvas");
  const gl = canvas.getContext("webgl", { premultipliedAlpha: false, preserveDrawingBuffer: true, antialias: false });
  if (!gl) return null;
  const shader = (type, src) => {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
    return s;
  };
  const prog = gl.createProgram();
  try {
    gl.attachShader(prog, shader(gl.VERTEX_SHADER, ED_VS));
    gl.attachShader(prog, shader(gl.FRAGMENT_SHADER, ED_FS));
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
  } catch (e) {
    console.error(e);
    return null;
  }
  gl.useProgram(prog);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(prog, "p");
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  gl.bindTexture(gl.TEXTURE_2D, gl.createTexture());
  for (const [k, val] of [[gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE],
    [gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR]]) gl.texParameteri(gl.TEXTURE_2D, k, val);
  const u = Object.fromEntries(ED_UNI.map((n) => [n, gl.getUniformLocation(prog, n)]));
  canvas.addEventListener("webglcontextlost", (e) => { e.preventDefault(); ed.gl = undefined; ed.glKey = ""; });
  ed.gl = { canvas, gl, u, max: gl.getParameter(gl.MAX_TEXTURE_SIZE), src: null };
  return ed.gl;
}

// ayarlar + seçili filtre (yoğunluğuyla) = uygulanacak son değerler
function edParams() {
  const p = { ...ed.doc.adj }, f = ED_FILTERS.find((x) => x.id === ed.doc.filter.id) || ED_FILTERS[0];
  const k = ed.doc.filter.amount / 100;
  for (const [key, v] of Object.entries(f.p || {})) p[key] = edClamp(p[key] + v * k, -100, 100);
  p.mono = (f.mono || 0) * k;
  p.split = f.split ? f.split[2] * k : 0;
  p.shTint = f.split ? f.split[0] : [0.5, 0.5, 0.5];
  p.hiTint = f.split ? f.split[1] : [0.5, 0.5, 0.5];
  return p;
}
const edIdentity = (p) => !p.mono && !p.split && Object.values(ED_ADJ).flat().every(([k]) => !p[k]);

// renk ayarlarını uygular; WebGL yoksa ya da ayar yoksa görsel olduğu gibi kalır
function edAdjust(src, p, force = false) {
  if (edIdentity(p)) return src;
  const g = edGL();
  if (!g) return src;
  const key = JSON.stringify(p) + "|" + src.width + "x" + src.height;
  if (!force && key === ed.glKey && g.src === src) return g.canvas;
  const { gl, u } = g;
  if (g.canvas.width !== src.width || g.canvas.height !== src.height) {
    g.canvas.width = src.width;
    g.canvas.height = src.height;
  }
  gl.viewport(0, 0, src.width, src.height);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, src);
  gl.uniform2f(u.px, 1 / src.width, 1 / src.height);
  gl.uniform2f(u.size, src.width, src.height);
  for (const n of ["exposure", "brightness", "contrast", "highlights", "shadows", "fade", "temperature", "tint", "saturation",
    "vibrance", "sharpen", "vignette", "grain"]) gl.uniform1f(u[n], p[n] / 100);
  gl.uniform1f(u.hue, (p.hue * Math.PI) / 180);
  gl.uniform1f(u.mono, p.mono);
  gl.uniform1f(u.split, p.split);
  gl.uniform3fv(u.shTint, p.shTint);
  gl.uniform3fv(u.hiTint, p.hiTint);
  gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  ed.glKey = force ? "" : key;
  g.src = force ? null : src;
  return g.canvas;
}

/* ---------------------------------------------------------------- katmanlar */
const edRGBA = (hex, a) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
};
const edUpper = (s) => s.toLocaleUpperCase(["tr", "az"].includes(I18N.lang) ? "tr" : I18N.lang || undefined);
const edFont = (L, px) => `${L.italic ? "italic " : ""}${L.weight || 700} ${px}px "${L.font}", "Segoe UI Emoji", "Apple Color Emoji", sans-serif`;

function edTextBox(x, L, W, H) {
  const px = Math.max(2, L.size * H);
  x.font = edFont(L, px);
  x.letterSpacing = ((L.spacing || 0) * px) / 100 + "px";
  const lines = (L.upper ? edUpper(L.text) : L.text).split("\n");
  const lh = px * (L.lh || 1.15), pad = L.bg ? px * 0.32 : 0;
  const w = Math.max(px * 0.4, ...lines.map((s) => x.measureText(s).width)) + pad * 2, hh = lh * lines.length + pad * 2;
  L._w = w / W;
  L._h = hh / H;
  return { px, lines, lh, pad, w, h: hh };
}

function edDrawText(x, L, W, H) {
  const m = edTextBox(x, L, W, H);
  x.translate(L.cx * W, L.cy * H);
  x.rotate(((L.rot || 0) * Math.PI) / 180);
  if (L.bg) {
    x.fillStyle = edRGBA(L.bgColor, (L.bgAlpha ?? 100) / 100);
    x.beginPath();
    x.roundRect(-m.w / 2, -m.h / 2, m.w, m.h, m.px * 0.22);
    x.fill();
  }
  x.textBaseline = "middle";
  x.textAlign = L.align || "center";
  const tx = L.align === "left" ? -m.w / 2 + m.pad : L.align === "right" ? m.w / 2 - m.pad : 0;
  const y0 = -m.h / 2 + m.pad + m.lh / 2, sh = (L.shadow || 0) / 100;
  const shadow = (on) => {
    x.shadowColor = on && sh ? `rgba(0,0,0,${0.3 + sh * 0.5})` : "transparent";
    x.shadowBlur = on ? m.px * 0.28 * sh : 0;
    x.shadowOffsetY = on ? m.px * 0.06 * sh : 0;
  };
  shadow(true);
  if (L.stroke) {  // kontur önce çizilir; dolgu üstüne gölgesiz gelir
    x.lineJoin = "round";
    x.lineWidth = (m.px * L.stroke) / 100;
    x.strokeStyle = L.strokeColor;
    m.lines.forEach((s, i) => x.strokeText(s, tx, y0 + i * m.lh));
    shadow(false);
  }
  x.fillStyle = L.color;
  m.lines.forEach((s, i) => x.fillText(s, tx, y0 + i * m.lh));
}

function edDrawShape(x, L, W, H) {
  const w = L.w * W, hh = L.h * H, sw = ((L.sw || 0) * Math.min(W, H)) / 100;
  x.translate(L.cx * W, L.cy * H);
  x.rotate(((L.rot || 0) * Math.PI) / 180);
  x.beginPath();
  if (L.type === "ellipse") x.ellipse(0, 0, w / 2, hh / 2, 0, 0, Math.PI * 2);
  else x.roundRect(-w / 2, -hh / 2, w, hh, (Math.min(w, hh) / 2) * ((L.radius || 0) / 100));
  if (L.fill) {
    x.fillStyle = L.fillColor;
    x.fill();
  }
  if (sw > 0) {
    x.lineWidth = sw;
    x.strokeStyle = L.strokeColor;
    x.stroke();
  }
}

function edDrawLine(x, L, W, H) {
  const ax = L.x1 * W, ay = L.y1 * H, bx = L.x2 * W, by = L.y2 * H, lw = (L.sw * Math.min(W, H)) / 100;
  const ang = Math.atan2(by - ay, bx - ax), head = lw * 3.4, arrow = L.type === "arrow";
  x.strokeStyle = x.fillStyle = L.strokeColor;
  x.lineWidth = lw;
  x.lineCap = "round";
  x.beginPath();
  x.moveTo(ax, ay);
  x.lineTo(arrow ? bx - Math.cos(ang) * head * 0.6 : bx, arrow ? by - Math.sin(ang) * head * 0.6 : by);
  x.stroke();
  if (arrow) {
    x.beginPath();
    x.moveTo(bx, by);
    x.lineTo(bx - head * Math.cos(ang - 0.45), by - head * Math.sin(ang - 0.45));
    x.lineTo(bx - head * Math.cos(ang + 0.45), by - head * Math.sin(ang + 0.45));
    x.closePath();
    x.fill();
  }
}

function edDrawPath(x, L, W, H) {
  const pts = L.pts;
  if (!pts.length) return;
  if (L.mode === "marker") x.globalAlpha *= 0.45;
  x.lineCap = L.mode === "marker" ? "square" : "round";
  x.lineJoin = "round";
  x.lineWidth = (L.sw * Math.min(W, H)) / 100;
  x.strokeStyle = L.color;
  x.beginPath();
  x.moveTo(pts[0][0] * W, pts[0][1] * H);
  for (let i = 1; i < pts.length - 1; i++) {
    x.quadraticCurveTo(pts[i][0] * W, pts[i][1] * H, ((pts[i][0] + pts[i + 1][0]) / 2) * W, ((pts[i][1] + pts[i + 1][1]) / 2) * H);
  }
  const last = pts[pts.length - 1];
  x.lineTo(last[0] * W + (pts.length === 1 ? 0.01 : 0), last[1] * H);
  x.stroke();
}

// sansür yalnızca fotoğrafa uygulanır (yazı ve şekillerin altında kalır)
function edCensor(x, L, W, H, img) {
  const w = L.w * W, hh = L.h * H, x0 = L.cx * W - w / 2, y0 = L.cy * H - hh / 2, k = (L.strength ?? 60) / 100;
  if (w < 2 || hh < 2) return;
  x.save();
  x.beginPath();
  x.rect(x0, y0, w, hh);
  x.clip();
  if (L.mode === "blur" && "filter" in x) {
    const r = Math.max(3, Math.min(w, hh) * (0.05 + 0.2 * k)), m = r * 2;
    const sx = Math.max(0, x0 - m), sy = Math.max(0, y0 - m), sw = Math.min(W, x0 + w + m) - sx, sh = Math.min(H, y0 + hh + m) - sy;
    x.filter = `blur(${r}px)`;
    x.drawImage(img, sx, sy, sw, sh, sx, sy, sw, sh);
  } else if (L.mode === "blur") {  // tuval süzgeci olmayan tarayıcılarda (iPhone): küçültüp yumuşak büyütmek bulanıklaştırır
    const f = Math.max(3, Math.min(w, hh) * (0.04 + 0.12 * k));
    const t = edCanvas(w / f, hh / f), tx = t.getContext("2d");
    tx.imageSmoothingQuality = "high";
    tx.drawImage(img, x0, y0, w, hh, 0, 0, t.width, t.height);
    x.imageSmoothingQuality = "high";
    x.drawImage(t, x0, y0, w, hh);
  } else {
    const cell = Math.max(3, Math.min(w, hh) / (4 + (1 - k) * 26));
    const t = edCanvas(w / cell, hh / cell), tx = t.getContext("2d");
    tx.imageSmoothingQuality = "high";
    tx.drawImage(img, x0, y0, w, hh, 0, 0, t.width, t.height);
    x.imageSmoothingEnabled = false;
    x.drawImage(t, x0, y0, w, hh);
  }
  x.restore();
}

function edDrawLayers(x, W, H, img) {
  for (const L of ed.doc.layers) if (L.type === "censor" && !L.hidden) edCensor(x, L, W, H, img);
  for (const L of ed.doc.layers) {
    if (L.hidden || L.type === "censor") continue;
    x.save();
    x.globalAlpha = (L.opacity ?? 100) / 100;
    if (L.type === "text") edDrawText(x, L, W, H);
    else if (L.type === "rect" || L.type === "ellipse") edDrawShape(x, L, W, H);
    else if (L.type === "line" || L.type === "arrow") edDrawLine(x, L, W, H);
    else if (L.type === "draw") edDrawPath(x, L, W, H);
    x.restore();
  }
}

/* ---------------------------------------------------------------- çizim ve yerleşim */
function edQueue() {
  if (ed.queued) return;
  ed.queued = true;
  requestAnimationFrame(() => { ed.queued = false; edRender(); });
}

function edRender() {
  if (!ed.img || !edVisible()) return;
  const crop = ed.tab === "crop";
  const base = edBase(), img = ed.comparing ? base : edAdjust(base, edParams());
  const cv = $("#edCanvas");
  if (cv.width !== base.width || cv.height !== base.height) {
    cv.width = base.width;
    cv.height = base.height;
  }
  const x = cv.getContext("2d");
  x.clearRect(0, 0, cv.width, cv.height);
  x.drawImage(img, 0, 0);
  if (!crop && !ed.comparing) edDrawLayers(x, cv.width, cv.height, img);
  edLayout();
}

// düzenleyici pencereyi doldursun ama sayfa kaymasın (başlığın yüksekliği dile ve yazı tipine göre değişir)
function edFitHeight() {
  const body = $(".ed-body"), main = $("#main");
  if (innerWidth <= 980) {
    body.style.height = "";
    return;
  }
  const top = body.getBoundingClientRect().top - main.getBoundingClientRect().top + main.scrollTop;
  body.style.height = Math.max(420, main.clientHeight - top - parseFloat(getComputedStyle(main).paddingBottom)) + "px";
}

function edLayout() {
  const st = $("#edStage"), view = $("#edView");
  if (!ed.img || !st.clientWidth) return;
  const pad = 26, sw = st.clientWidth - pad * 2, sh = st.clientHeight - pad * 2;
  const [W, H] = edFrame();
  ed.fit = Math.min(sw / W, sh / H);
  ed.scale = ed.zoom || ed.fit;
  const dw = Math.max(1, W * ed.scale), dh = Math.max(1, H * ed.scale);
  const mx = Math.max(0, (dw - sw) / 2), my = Math.max(0, (dh - sh) / 2);
  ed.panX = edClamp(ed.panX, -mx, mx);
  ed.panY = edClamp(ed.panY, -my, my);
  Object.assign(view.style, { width: dw + "px", height: dh + "px",
    left: (st.clientWidth - dw) / 2 + ed.panX + "px", top: (st.clientHeight - dh) / 2 + ed.panY + "px" });
  st.classList.toggle("zoomed", mx > 0 || my > 0);
  $("#edZoomFit").textContent = edPct(Math.round(ed.scale * 100));
  edOverlay();
}

function edZoomTo(scale, cx, cy) {
  if (!ed.img) return;
  const r = $("#edStage").getBoundingClientRect(), old = ed.scale;
  scale = edClamp(scale, ed.fit / 4, Math.max(8, ed.fit));
  if (cx === undefined) [cx, cy] = [r.left + r.width / 2, r.top + r.height / 2];
  // imlecin altındaki nokta yerinde kalsın
  const vx = cx - (r.left + r.width / 2) - ed.panX, vy = cy - (r.top + r.height / 2) - ed.panY;
  ed.panX -= vx * (scale / old - 1);
  ed.panY -= vy * (scale / old - 1);
  ed.zoom = Math.abs(scale - ed.fit) / ed.fit < 0.01 ? 0 : scale;
  edLayout();
}

function edFitView() {
  ed.zoom = 0;
  ed.panX = ed.panY = 0;
  edLayout();
}

// seçim çerçevesi, tutamaçlar ve kırpma çerçevesi (ekran pikseliyle, görselin üstünde)
function edOverlay() {
  const ov = $("#edOverlay");
  ov.replaceChildren();
  if (!ed.img || ed.comparing) return;
  const dw = ov.clientWidth, dh = ov.clientHeight;
  const knob = (k) => h("span", { class: "ed-k " + k, "data-h": k });
  if (ed.tab === "crop") {  // dışarısı karartılır (karartma görselin sınırında kesilir, tutamaçlar kesilmez)
    const c = edCrop(), pos = { left: c.x * dw + "px", top: c.y * dh + "px", width: c.w * dw + "px", height: c.h * dh + "px" };
    const dim = h("div", { class: "ed-crop-dim" }), clip = h("div", { class: "ed-clip" }, dim);
    const box = h("div", { class: "ed-crop", "data-h": "move" }, h("i", { class: "g1" }), h("i", { class: "g2" }),
      h("i", { class: "g3" }), h("i", { class: "g4" }), ...["nw", "n", "ne", "e", "se", "s", "sw", "w"].map(knob));
    Object.assign(dim.style, pos);
    Object.assign(box.style, pos);
    ov.append(clip, box);
    return;
  }
  if (ed.guides) {
    if (ed.guides.v) ov.append(h("i", { class: "ed-guide v" }));
    if (ed.guides.h) ov.append(h("i", { class: "ed-guide h" }));
  }
  const L = ed.sel && edLayer(ed.sel);
  if (!L || L.hidden) return;
  if (L.type === "line" || L.type === "arrow") {
    for (const [k, px, py] of [["p1", L.x1, L.y1], ["p2", L.x2, L.y2]]) {
      const kn = knob(k);
      Object.assign(kn.style, { left: px * dw + "px", top: py * dh + "px" });
      ov.append(kn);
    }
    return;
  }
  let cx, cy, w, hh, rot = L.rot || 0;
  if (L.type === "draw") {
    const b = edBounds(L), pad = (L.sw * Math.min(dw, dh)) / 200;
    [cx, cy, w, hh, rot] = [((b.x0 + b.x1) / 2) * dw, ((b.y0 + b.y1) / 2) * dh, (b.x1 - b.x0) * dw + pad * 2, (b.y1 - b.y0) * dh + pad * 2, 0];
  } else {
    [cx, cy] = [L.cx * dw, L.cy * dh];
    [w, hh] = L.type === "text" ? [(L._w || 0) * dw, (L._h || 0) * dh] : [L.w * dw, L.h * dh];
  }
  const box = h("div", { class: "ed-sel" });
  Object.assign(box.style, { left: cx + "px", top: cy + "px", width: w + "px", height: hh + "px",
    transform: `translate(-50%, -50%) rotate(${rot}deg)` });
  if (L.type !== "draw") {
    box.append(...["nw", "ne", "se", "sw"].map(knob));
    if (L.type !== "text") box.append(...["n", "e", "s", "w"].map(knob));
    if (L.type !== "censor") box.append(knob("rot"));
  }
  ov.append(box);
}

function edBounds(L) {
  const xs = L.pts.map((p) => p[0]), ys = L.pts.map((p) => p[1]);
  return { x0: Math.min(...xs), x1: Math.max(...xs), y0: Math.min(...ys), y1: Math.max(...ys) };
}

/* ---------------------------------------------------------------- fare ve dokunma */
function edPoint(e) {
  const r = $("#edCanvas").getBoundingClientRect();
  return { x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height };
}

// karede bir nokta (0–1): üstteki katman önce; only verilirse yalnızca o türden katmanlar
function edHit(p, only) {
  const [W, H] = edFrame(false), px = p.x * W, py = p.y * H, tol = 8 / ed.scale;
  for (let i = ed.doc.layers.length - 1; i >= 0; i--) {
    const L = ed.doc.layers[i];
    if (L.hidden || (only && L.type !== only)) continue;
    if (L.type === "line" || L.type === "arrow") {
      const ax = L.x1 * W, ay = L.y1 * H, bx = L.x2 * W, by = L.y2 * H, len = Math.hypot(bx - ax, by - ay) || 1;
      const t = edClamp(((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / (len * len), 0, 1);
      if (Math.hypot(px - ax - t * (bx - ax), py - ay - t * (by - ay)) <= (L.sw * Math.min(W, H)) / 200 + tol) return L;
      continue;
    }
    if (L.type === "draw") {
      const b = edBounds(L), m = (L.sw * Math.min(W, H)) / 200 + tol;
      if (px >= b.x0 * W - m && px <= b.x1 * W + m && py >= b.y0 * H - m && py <= b.y1 * H + m) return L;
      continue;
    }
    const [bw, bh] = L.type === "text" ? [(L._w || 0) * W, (L._h || 0) * H] : [L.w * W, L.h * H];
    const a = (-(L.rot || 0) * Math.PI) / 180, dx = px - L.cx * W, dy = py - L.cy * H;
    const lx = dx * Math.cos(a) - dy * Math.sin(a), ly = dx * Math.sin(a) + dy * Math.cos(a);
    if (Math.abs(lx) <= bw / 2 + tol && Math.abs(ly) <= bh / 2 + tol) return L;
  }
  return null;
}

function edDown(e) {
  if (!ed.img || e.button === 2) return;
  const st = $("#edStage");
  const start = (drag) => {
    ed.drag = drag;
    e.preventDefault();
    try { st.setPointerCapture(e.pointerId); } catch { /* yakalanamasa da sürükleme sahne içinde çalışır */ }
  };
  if (e.button === 1 || ed.space || (e.target === st && st.classList.contains("zoomed"))) {
    start({ kind: "pan", sx: e.clientX, sy: e.clientY, px: ed.panX, py: ed.panY });
    st.classList.add("panning");
    return;
  }
  const knob = e.target.closest("[data-h]"), p = edPoint(e);
  if (ed.tab === "crop") {
    if (knob) start({ kind: "crop", h: knob.dataset.h, p, c: { ...edCrop() } });
    return;
  }
  if (knob && ed.sel) {
    const L = edLayer(ed.sel);
    start({ kind: "handle", h: knob.dataset.h, p, L, o: JSON.parse(JSON.stringify(L)) });
    return;
  }
  if (!e.target.closest("#edView")) {
    if (ed.sel) edSelect(null, false);
    return;
  }
  if (ed.tab === "draw") {
    const o = ed.drawOpt;
    const L = edAdd({ type: "draw", pts: [[p.x, p.y]], color: o.color, sw: o.size, opacity: o.opacity, mode: o.mode }, false);
    ed.sel = null;  // çizerken etrafında seçim çerçevesi çıkmasın
    start({ kind: "draw", L });
    return;
  }
  const L = edHit(p, ed.tab === "censor" ? "censor" : null);  // sansür sekmesinde yazının üstüne de alan çizilebilsin
  if (L) {
    edSelect(L.id);
    start({ kind: "move", p, L, o: JSON.parse(JSON.stringify(L)) });
  } else if (ed.tab === "censor") {
    const o = ed.censorOpt;
    start({ kind: "censor", p, L: edAdd({ type: "censor", cx: p.x, cy: p.y, w: 0, h: 0, mode: o.mode, strength: o.strength }, false) });
  } else if (ed.sel) edSelect(null, false);
}

function edMove(e) {
  const d = ed.drag;
  if (!d) return;
  if (d.kind === "pan") {
    ed.panX = d.px + e.clientX - d.sx;
    ed.panY = d.py + e.clientY - d.sy;
    edLayout();
    return;
  }
  const p = edPoint(e);
  if (d.kind === "draw") {
    const last = d.L.pts[d.L.pts.length - 1], [W, H] = edFrame(false);
    if (Math.hypot((p.x - last[0]) * W, (p.y - last[1]) * H) * ed.scale >= 2) d.L.pts.push([p.x, p.y]);
  } else if (d.kind === "censor") {
    Object.assign(d.L, { cx: (d.p.x + p.x) / 2, cy: (d.p.y + p.y) / 2, w: Math.abs(p.x - d.p.x), h: Math.abs(p.y - d.p.y) });
  } else if (d.kind === "move") edMoveLayer(d, p, e);
  else if (d.kind === "handle") edResize(d, p, e);
  else if (d.kind === "crop") edCropDrag(d, p);
  edQueue();
}

function edUp() {
  const d = ed.drag;
  if (!d) return;
  ed.drag = null;
  ed.guides = null;
  $("#edStage").classList.remove("panning");
  if (d.kind === "pan") return;
  if (d.kind === "censor" && (d.L.w < 0.01 || d.L.h < 0.01)) {  // tıklayıp bırakınca boş sansür kalmasın
    ed.doc.layers = ed.doc.layers.filter((l) => l !== d.L);
    ed.sel = null;
  }
  edCommit();
  if (d.kind !== "move" || ed.tab === "layers") edPanel();
  edQueue();
}

function edMoveLayer(d, p, e) {
  let dx = p.x - d.p.x, dy = p.y - d.p.y;
  const L = d.L, o = d.o;
  if (o.pts) L.pts = o.pts.map(([x, y]) => [x + dx, y + dy]);
  else if ("x1" in o) Object.assign(L, { x1: o.x1 + dx, y1: o.y1 + dy, x2: o.x2 + dx, y2: o.y2 + dy });
  else {
    // ortaya yaklaşınca yapışır (Alt basılıysa yapışmaz)
    const snap = 6 / ed.scale, [W, H] = edFrame(false);
    ed.guides = { v: false, h: false };
    if (!e.altKey && Math.abs((o.cx + dx - 0.5) * W) < snap) { dx = 0.5 - o.cx; ed.guides.v = true; }
    if (!e.altKey && Math.abs((o.cy + dy - 0.5) * H) < snap) { dy = 0.5 - o.cy; ed.guides.h = true; }
    L.cx = o.cx + dx;
    L.cy = o.cy + dy;
  }
}

function edResize(d, p, e) {
  const [W, H] = edFrame(false), L = d.L, o = d.o;
  if (d.h === "p1" || d.h === "p2") {
    Object.assign(L, d.h === "p1" ? { x1: p.x, y1: p.y } : { x2: p.x, y2: p.y });
    return;
  }
  const cx = o.cx * W, cy = o.cy * H, px = p.x * W, py = p.y * H;
  if (d.h === "rot") {
    let a = (Math.atan2(py - cy, px - cx) * 180) / Math.PI + 90;
    a = ((a + 540) % 360) - 180;
    if (e.shiftKey) a = Math.round(a / 15) * 15;
    else for (const s of [-180, -90, 0, 90, 180]) if (Math.abs(a - s) < 4) a = s;
    L.rot = Math.round(a * 10) / 10;
    return;
  }
  const rad = ((o.rot || 0) * Math.PI) / 180, cos = Math.cos(rad), sin = Math.sin(rad);
  const lx = (px - cx) * cos + (py - cy) * sin, ly = -(px - cx) * sin + (py - cy) * cos;  // döndürülmemiş yerel koordinat
  if (L.type === "text") {  // köşeden çekince yazı büyür, merkez yerinde kalır
    const r0 = Math.hypot((o._w * W) / 2, (o._h * H) / 2) || 1;
    L.size = edClamp((o.size * Math.hypot(lx, ly)) / r0, 0.01, 0.6);
    return;
  }
  const hw = (o.w * W) / 2, hh = (o.h * H) / 2;
  const sx = d.h.includes("e") ? 1 : d.h.includes("w") ? -1 : 0, sy = d.h.includes("s") ? 1 : d.h.includes("n") ? -1 : 0;
  const fx = -sx * hw, fy = -sy * hh;  // karşı kenar yerinde kalır
  let mxl = sx ? lx : hw * 1, myl = sy ? ly : hh * 1;
  let w = sx ? Math.abs(mxl - fx) : hw * 2, hgt = sy ? Math.abs(myl - fy) : hh * 2;
  if (e.shiftKey && sx && sy) {  // oran korunur
    const r = hw / hh;
    if (w / hgt > r) hgt = w / r;
    else w = hgt * r;
    mxl = fx + Math.sign(lx - fx || sx) * w;
    myl = fy + Math.sign(ly - fy || sy) * hgt;
  }
  w = Math.max(6, w);
  hgt = Math.max(6, hgt);
  const mx = sx ? (fx + mxl) / 2 : 0, my = sy ? (fy + myl) / 2 : 0;
  Object.assign(L, { cx: (cx + mx * cos - my * sin) / W, cy: (cy + mx * sin + my * cos) / H, w: w / W, h: hgt / H });
}

const ED_ASPECTS = { "1:1": 1, "4:5": 4 / 5, "16:9": 16 / 9, "9:16": 9 / 16, "4:3": 4 / 3, "3:2": 3 / 2 };
function edRatio() {  // seçili oranın kare koordinatındaki karşılığı (genişlik / yükseklik), serbestse 0
  const a = ed.doc.geo.aspect, [ow, oh] = edOriented();
  if (a === "orig") return 1;
  return ED_ASPECTS[a] ? (ED_ASPECTS[a] * oh) / ow : 0;
}

function edCropDrag(d, p) {
  const c0 = d.c, r = edRatio(), min = 0.04;
  if (d.h === "move") {
    ed.doc.geo.crop = { ...c0, x: edClamp(c0.x + p.x - d.p.x, 0, 1 - c0.w), y: edClamp(c0.y + p.y - d.p.y, 0, 1 - c0.h) };
    return;
  }
  let x0 = c0.x, y0 = c0.y, x1 = c0.x + c0.w, y1 = c0.y + c0.h;
  if (d.h.includes("w")) x0 = edClamp(p.x, 0, x1 - min);
  if (d.h.includes("e")) x1 = edClamp(p.x, x0 + min, 1);
  if (d.h.includes("n")) y0 = edClamp(p.y, 0, y1 - min);
  if (d.h.includes("s")) y1 = edClamp(p.y, y0 + min, 1);
  if (r) {
    const horiz = d.h.includes("e") || d.h.includes("w"), vert = d.h.includes("n") || d.h.includes("s");
    let w = x1 - x0, hh = y1 - y0;
    if (horiz && (!vert || w / hh > r)) hh = w / r;
    else w = hh * r;
    // köşede karşı köşe, kenarda karşı kenarın ortası sabit kalır
    const ax = d.h.includes("w") ? x1 : d.h.includes("e") ? x0 : (c0.x * 2 + c0.w) / 2;
    const ay = d.h.includes("n") ? y1 : d.h.includes("s") ? y0 : (c0.y * 2 + c0.h) / 2;
    const roomX = d.h.includes("w") ? ax : d.h.includes("e") ? 1 - ax : Math.min(ax, 1 - ax) * 2;
    const roomY = d.h.includes("n") ? ay : d.h.includes("s") ? 1 - ay : Math.min(ay, 1 - ay) * 2;
    const k = Math.min(1, roomX / w, roomY / hh);
    w *= k;
    hh *= k;
    x0 = d.h.includes("w") ? ax - w : d.h.includes("e") ? ax : ax - w / 2;
    y0 = d.h.includes("n") ? ay - hh : d.h.includes("s") ? ay : ay - hh / 2;
    x1 = x0 + w;
    y1 = y0 + hh;
  }
  ed.doc.geo.crop = { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

function edSetAspect(a) {
  const g = ed.doc.geo;
  g.aspect = a;
  const r = edRatio();
  if (r) {  // oranın sığdığı en büyük alan, ortada
    const [w, hh] = r >= 1 ? [1, 1 / r] : [r, 1];
    g.crop = a === "orig" ? null : { x: (1 - w) / 2, y: (1 - hh) / 2, w, h: hh };
  }
  edCommit();
  edQueue();
}

function edRotate(dir) {
  const g = ed.doc.geo, c = g.crop;
  g.rot = (g.rot + dir + 360) % 360;
  if (c) g.crop = dir > 0 ? { x: 1 - (c.y + c.h), y: c.x, w: c.h, h: c.w } : { x: c.y, y: 1 - (c.x + c.w), w: c.h, h: c.w };
  if (ED_ASPECTS[g.aspect]) g.aspect = "free";
  edFitView();
  edCommit();
  edQueue();
}

function edFlip(axis) {
  const g = ed.doc.geo, c = g.crop;
  if (axis === "h") {
    g.flipH = !g.flipH;
    if (c) c.x = 1 - (c.x + c.w);
  } else {
    g.flipV = !g.flipV;
    if (c) c.y = 1 - (c.y + c.h);
  }
  edCommit();
  edQueue();
}

/* ---------------------------------------------------------------- katman işlemleri */
function edAdd(props, commit = true) {
  const L = { id: "L" + Date.now().toString(36) + edSeq++, opacity: 100, rot: 0, ...props };
  ed.doc.layers.push(L);
  ed.sel = L.id;
  if (commit) {
    edCommit();
    edPanel();
  }
  edQueue();
  return L;
}

function edSelect(id, switchTab = true) {
  ed.sel = id;
  const L = id && edLayer(id);
  if (L && switchTab && ed.tab !== "layers") ed.tab = ED_TYPE[L.type][2];
  edPanel();
  edOverlay();
}

function edRemove(id) {
  ed.doc.layers = ed.doc.layers.filter((l) => l.id !== id);
  if (ed.sel === id) ed.sel = null;
  edCommit();
  edPanel();
  edQueue();
}

function edDuplicate(L) {
  if (!L) return;
  const copy = JSON.parse(JSON.stringify(L));
  if (copy.pts) copy.pts = copy.pts.map(([x, y]) => [x + 0.03, y + 0.03]);
  else if ("x1" in copy) Object.assign(copy, { x1: copy.x1 + 0.03, y1: copy.y1 + 0.03, x2: copy.x2 + 0.03, y2: copy.y2 + 0.03 });
  else Object.assign(copy, { cx: copy.cx + 0.03, cy: copy.cy + 0.03 });
  delete copy.id;
  edAdd(copy);
}

function edOrder(L, dir) {
  const a = ed.doc.layers, i = a.indexOf(L), j = edClamp(i + dir, 0, a.length - 1);
  if (i < 0 || i === j) return;
  a.splice(i, 1);
  a.splice(j, 0, L);
  edCommit();
  edPanel();
  edQueue();
}

function edAddText(kind) {
  const t = ED_TEXT[kind];
  const L = edAdd({ type: "text", align: "center", italic: false, upper: false, bg: false, bgColor: "#111111", bgAlpha: 85,
    stroke: 0, strokeColor: "#111111", shadow: 0, spacing: 0, lh: 1.1, cx: 0.5, ...t, text: tr(t.text) });
  edLoadFont(L);
}

function edAddShape(type) {
  if (type === "line" || type === "arrow") {
    edAdd({ type, x1: 0.3, y1: 0.66, x2: 0.62, y2: 0.38, sw: 1.4, strokeColor: "#FF3B30" });
    return;
  }
  const [W, H] = edFrame(false), s = 0.34 * Math.min(W, H);
  edAdd({ type, cx: 0.5, cy: 0.5, w: s / W, h: (s / H) * (type === "rect" ? 0.72 : 1), fill: false, fillColor: "#FFD60A",
    sw: 1.2, strokeColor: "#FF3B30", radius: type === "rect" ? 16 : 0 });
}

function edLoadFont(L) {
  if (document.fonts) document.fonts.load(`${L.weight || 700} 40px "${L.font}"`).then(edQueue, edQueue);
  edQueue();
}

/* ---------------------------------------------------------------- panel parçaları */
function edRange(label, value, min, max, step, fmt, onInput, onDone, center = 0) {
  const val = h("span", { class: "ed-val", "data-no-i18n": true }, fmt(value));
  const input = h("input", { type: "range", class: "ed-range", min, max, step, value });
  const paint = () => {
    const at = (v) => ((v - min) / (max - min)) * 100;
    input.style.setProperty("--a", Math.min(at(+input.value), at(center)) + "%");
    input.style.setProperty("--b", Math.max(at(+input.value), at(center)) + "%");
  };
  input.addEventListener("input", () => { val.textContent = fmt(+input.value); paint(); onInput(+input.value); });
  if (onDone) input.addEventListener("change", () => onDone(+input.value));
  input.addEventListener("dblclick", () => {  // çift tıklayınca sıfırlanır
    input.value = center;
    input.dispatchEvent(new Event("input"));
    if (onDone) onDone(center);
  });
  paint();
  return h("div", { class: "ed-sl" }, h("div", { class: "ed-sl-top" }, h("span", {}, label), val), input);
}

function edChoice(items, value, onPick, cls = "") {  // items: [[değer, etiket, simge, ipucu]]
  const box = h("div", { class: "ed-choice " + cls });
  for (const [v, label, ic, tip] of items) {
    box.append(h("button", { class: "ed-chip" + (String(v) === String(value) ? " on" : ""), title: tip || null,
      onclick: (e) => {
        box.querySelectorAll(".ed-chip").forEach((b) => b.classList.toggle("on", b === e.currentTarget));
        onPick(v);
      } }, ic ? icon(ic) : null, label || null));
  }
  return box;
}

function edToggle(label, ic, on, onFlip) {
  const b = h("button", { class: "ed-chip" + (on ? " on" : ""), title: label, onclick: () => onFlip(b.classList.toggle("on")) }, icon(ic));
  return b;
}

function edColors(value, onPick) {
  const row = h("div", { class: "ed-colors" });
  const mark = (v) => row.querySelectorAll(".ed-sw").forEach((b) => b.classList.toggle("on", (b.dataset.v || "").toLowerCase() === v.toLowerCase()));
  for (const c of ED_COLORS) {
    row.append(h("button", { class: "ed-sw", "data-v": c, style: `--c:${c}`, title: c, "data-no-i18n": true,
      onclick: () => { mark(c); custom.value = c.toLowerCase(); onPick(c, true); } }));
  }
  const custom = h("input", { type: "color", value: /^#[0-9a-f]{6}$/i.test(value) ? value.toLowerCase() : "#ffffff" });
  custom.addEventListener("input", () => { mark(custom.value); onPick(custom.value, false); });
  custom.addEventListener("change", () => onPick(custom.value, true));
  row.append(h("label", { class: "ed-sw custom", title: "Özel renk" }, custom));
  mark(value);
  return row;
}

function edSwitch(label, on, onToggle) {
  const input = h("input", { type: "checkbox" });
  input.checked = on;
  input.addEventListener("change", () => onToggle(input.checked));
  return h("div", { class: "ed-row" }, h("span", {}, label), h("label", { class: "switch" }, input, h("span")));
}

const edHead = (text) => h("div", { class: "ed-h" }, text);
const edNote = (text, ic) => h("p", { class: "ed-note" + (ic ? " strong" : "") }, ic ? icon(ic) : null, h("span", {}, text));
// ayarı değiştirir; bırakınca (ya da renk seçilince) geçmişe yazılır
const edSet = (obj, key, done = false) => (v, fin = done) => { obj[key] = v; edQueue(); if (fin) edCommit(); };

function edLayerActions(L) {
  return h("div", { class: "ed-layer-acts" },
    h("button", { class: "btn sm", title: "Çoğalt (Ctrl+D)", onclick: () => edDuplicate(L) }, icon("copy"), "Çoğalt"),
    h("button", { class: "btn icon sm", title: "Öne getir", onclick: () => edOrder(L, 1) }, icon("arrowUp")),
    h("button", { class: "btn icon sm", title: "Arkaya gönder", onclick: () => edOrder(L, -1) }, icon("arrowDown")),
    h("button", { class: "btn sm danger", title: "Sil (Delete)", onclick: () => edRemove(L.id) }, icon("trash"), "Sil"));
}

/* ---------------------------------------------------------------- sekmeler */
function edTabCrop() {
  const g = ed.doc.geo;
  return [
    edHead("Oran"),
    edChoice([["free", "Serbest"], ["orig", "Orijinal"], ["1:1", "1:1"], ["4:5", "4:5"], ["16:9", "16:9"], ["9:16", "9:16"],
      ["4:3", "4:3"], ["3:2", "3:2"]], g.aspect, edSetAspect, "grid4"),
    edHead("Döndür ve çevir"),
    h("div", { class: "ed-btn-grid" },
      h("button", { class: "btn sm", title: "Sola döndür", onclick: () => edRotate(-90) }, icon("rotL"), "90°"),
      h("button", { class: "btn sm", title: "Sağa döndür", onclick: () => edRotate(90) }, icon("rotR"), "90°"),
      h("button", { class: "btn sm", onclick: () => edFlip("h") }, icon("flipH"), "Yatay çevir"),
      h("button", { class: "btn sm", onclick: () => edFlip("v") }, icon("flipV"), "Dikey çevir")),
    edRange("Düzelt", g.angle, -45, 45, 0.5, (v) => v + "°", (v) => { g.angle = v; edQueue(); }, edCommit),
    edNote("Çerçeveyi köşelerinden sürükle ya da içinden tutup taşı. Eğik fotoğrafı Düzelt ile hizala."),
    h("button", { class: "btn sm ghost", onclick: () => {
      Object.assign(g, { crop: null, aspect: "free", angle: 0 });
      edCommit();
      edPanel();
      edQueue();
    } }, icon("refresh"), "Kırpmayı sıfırla"),
  ];
}

function edTabAdjust() {
  const out = [h("button", { class: "btn sm ed-auto", onclick: edAuto }, icon("wand"), "Otomatik iyileştir")];
  for (const [g, name] of [["light", "Işık"], ["color", "Renk"], ["detail", "Ayrıntı"]]) {
    out.push(edHead(name));
    for (const [k, label, min = -100, max = 100] of ED_ADJ[g]) {
      out.push(edRange(label, ed.doc.adj[k], min, max, 1, k === "hue" ? (v) => v + "°" : edSigned,
        (v) => { ed.doc.adj[k] = v; edQueue(); }, edCommit));
    }
  }
  out.push(h("button", { class: "btn sm ghost", onclick: () => {
    for (const k in ed.doc.adj) ed.doc.adj[k] = 0;
    edCommit();
    edPanel();
    edQueue();
  } }, icon("refresh"), "Ayarları sıfırla"));
  return out;
}

function edTabFilter() {
  const thumbs = edFilterThumbs();
  const grid = h("div", { class: "ed-filters" }, ...ED_FILTERS.map((f) =>
    h("button", { class: "ed-filter" + (ed.doc.filter.id === f.id ? " on" : ""), title: f.name, onclick: () => {
      ed.doc.filter = { id: f.id, amount: ed.doc.filter.amount || 100 };
      edCommit();
      edPanel();
      edQueue();
    } }, h("img", { src: thumbs[f.id], alt: "" }), h("span", {}, f.name))));
  const out = [grid];
  if (ed.doc.filter.id !== "none") {
    out.push(edRange("Yoğunluk", ed.doc.filter.amount, 0, 100, 1, edPct,
      (v) => { ed.doc.filter.amount = v; edQueue(); }, edCommit));
  }
  return out;
}

function edFilterThumbs() {
  const key = ed.baseKey + JSON.stringify(ed.doc.adj);
  if (ed.thumbKey === key && ed.thumbs) return ed.thumbs;
  const base = edBase(), s = 150 / Math.max(base.width, base.height);
  const small = edCanvas(base.width * s, base.height * s);
  small.getContext("2d").drawImage(base, 0, 0, small.width, small.height);
  const saved = ed.doc.filter, out = {};
  for (const f of ED_FILTERS) {
    ed.doc.filter = { id: f.id, amount: 100 };
    out[f.id] = edAdjust(small, edParams(), true).toDataURL("image/jpeg", 0.82);
  }
  ed.doc.filter = saved;
  ed.glKey = "";
  ed.thumbKey = key;
  ed.thumbs = out;
  return out;
}

function edTabText() {
  const L = ed.sel && edLayer(ed.sel);
  const out = [h("div", { class: "ed-add-row" },
    h("button", { class: "btn sm", onclick: () => edAddText("title") }, icon("plus"), "Başlık"),
    h("button", { class: "btn sm", onclick: () => edAddText("body") }, icon("plus"), "Yazı"),
    h("button", { class: "btn sm", onclick: () => edAddText("label") }, icon("plus"), "Etiket"))];
  if (!L || L.type !== "text") {
    out.push(edNote("Bir yazı stili ekle. Var olan yazıyı düzenlemek için görselde üstüne tıkla."));
    return out;
  }
  const ta = h("textarea", { class: "textarea ed-text-in", rows: 2, "data-no-i18n": true });
  ta.value = L.text;
  ta.addEventListener("input", () => { L.text = ta.value; edQueue(); });
  ta.addEventListener("change", edCommit);
  const fonts = h("div", { class: "ed-fonts" });
  for (const [fam, name] of ED_FONTS) {
    const b = h("button", { class: "ed-font" + (L.font === fam ? " on" : ""), style: `font-family:"${fam}"`, onclick: () => {
      L.font = fam;
      fonts.querySelectorAll(".ed-font").forEach((x) => x.classList.toggle("on", x === b));
      edLoadFont(L);
      edCommit();
    } }, h("b", { "data-no-i18n": true }, "Aa"), h("small", { "data-no-i18n": !["Kalın", "Dar", "Gösteriş"].includes(name) }, name));
    fonts.append(b);
  }
  out.push(ta, edHead("Yazı tipi"), fonts,
    edRange("Boyut", Math.round(L.size * 1000) / 10, 1, 40, 0.5, (v) => v, (v) => { L.size = v / 100; edQueue(); }, edCommit, 1),
    h("div", { class: "ed-row2" },
      edChoice([[400, "Normal"], [700, "Kalın"], [900, "Çok kalın"]], L.weight, (v) => { L.weight = v; edLoadFont(L); edCommit(); }),
      h("div", { class: "ed-choice" },
        edToggle("Eğik", "italic", L.italic, (on) => { L.italic = on; edQueue(); edCommit(); }),
        edToggle("Büyük harf", "caps", L.upper, (on) => { L.upper = on; edQueue(); edCommit(); }))),
    edChoice([["left", "", "alignL", "Sola hizala"], ["center", "", "alignC", "Ortala"], ["right", "", "alignR", "Sağa hizala"]],
      L.align, (v) => { L.align = v; edQueue(); edCommit(); }),
    edHead("Renk"), edColors(L.color, edSet(L, "color")),
    edHead("Kontur"),
    edRange("Kalınlık", L.stroke || 0, 0, 40, 1, (v) => v, (v) => { L.stroke = v; edQueue(); }, edCommit),
    edColors(L.strokeColor || "#111111", edSet(L, "strokeColor")),
    edRange("Gölge", L.shadow || 0, 0, 100, 1, (v) => v, (v) => { L.shadow = v; edQueue(); }, edCommit),
    edSwitch("Arka plan kutusu", !!L.bg, (on) => { L.bg = on; edQueue(); edCommit(); edPanel(); }));
  if (L.bg) {
    out.push(edColors(L.bgColor, edSet(L, "bgColor")),
      edRange("Kutu opaklığı", L.bgAlpha ?? 100, 10, 100, 1, edPct, (v) => { L.bgAlpha = v; edQueue(); }, edCommit));
  }
  out.push(
    edRange("Harf aralığı", L.spacing || 0, -10, 60, 1, (v) => v, (v) => { L.spacing = v; edQueue(); }, edCommit),
    edRange("Satır aralığı", Math.round((L.lh || 1.1) * 100), 70, 220, 1, edPct, (v) => { L.lh = v / 100; edQueue(); }, edCommit, 70),
    edRange("Opaklık", L.opacity ?? 100, 5, 100, 1, edPct, (v) => { L.opacity = v; edQueue(); }, edCommit, 5),
    edRange("Açı", L.rot || 0, -180, 180, 1, (v) => v + "°", (v) => { L.rot = v; edQueue(); }, edCommit),
    edLayerActions(L));
  return out;
}

function edTabShape() {
  const L = ed.sel && edLayer(ed.sel);
  const out = [edHead("Şekil ekle"),
    h("div", { class: "ed-btn-grid" },
      h("button", { class: "btn sm", onclick: () => edAddShape("rect") }, icon("rect"), "Dikdörtgen"),
      h("button", { class: "btn sm", onclick: () => edAddShape("ellipse") }, icon("circle"), "Daire"),
      h("button", { class: "btn sm", onclick: () => edAddShape("arrow") }, icon("arrowTool"), "Ok"),
      h("button", { class: "btn sm", onclick: () => edAddShape("line") }, icon("line"), "Çizgi")),
    edHead("Emoji"),
    h("div", { class: "ed-emoji", "data-no-i18n": true }, ...ED_EMOJI.map((em) => h("button", { onclick: () => {
      edAdd({ type: "text", text: em, font: "Segoe UI Emoji", weight: 400, size: 0.16, color: "#FFFFFF", align: "center",
        stroke: 0, strokeColor: "#111111", shadow: 30, bg: false, bgColor: "#111111", bgAlpha: 85, spacing: 0, lh: 1.1,
        upper: false, italic: false, cx: 0.78, cy: 0.24 });
    } }, em)))];
  if (!L || !["rect", "ellipse", "line", "arrow"].includes(L.type)) {
    out.push(edNote("Eklediğin öğeyi sürükleyerek taşı, köşelerinden büyüt. Emoji, yazı gibi düzenlenir."));
    return out;
  }
  const lineish = L.type === "line" || L.type === "arrow";
  out.push(h("div", { class: "ed-divider" }));
  if (!lineish) {
    out.push(edSwitch("Dolgu", !!L.fill, (on) => { L.fill = on; edQueue(); edCommit(); edPanel(); }));
    if (L.fill) out.push(edColors(L.fillColor, edSet(L, "fillColor")));
  }
  out.push(edRange(lineish ? "Kalınlık" : "Çerçeve", L.sw, 0, 6, 0.1, (v) => (+v).toFixed(1), (v) => { L.sw = v; edQueue(); }, edCommit),
    edColors(L.strokeColor, edSet(L, "strokeColor")));
  if (L.type === "rect") out.push(edRange("Köşe yuvarlaklığı", L.radius || 0, 0, 100, 1, edPct, (v) => { L.radius = v; edQueue(); }, edCommit));
  out.push(edRange("Opaklık", L.opacity ?? 100, 5, 100, 1, edPct, (v) => { L.opacity = v; edQueue(); }, edCommit, 5));
  if (!lineish) out.push(edRange("Açı", L.rot || 0, -180, 180, 1, (v) => v + "°", (v) => { L.rot = v; edQueue(); }, edCommit));
  out.push(edLayerActions(L));
  return out;
}

function edTabDraw() {
  const o = ed.drawOpt;
  return [
    edNote("Görselin üstünde sürükleyerek çiz. Her çizgi ayrı katman olur; Ctrl+Z ile geri alınır.", "brush"),
    edChoice([["pen", "Kalem", "pen"], ["marker", "Fosforlu", "marker"]], o.mode, (v) => { o.mode = v; }),
    edHead("Renk"), edColors(o.color, (c) => { o.color = c; }),
    edRange("Kalınlık", o.size, 0.2, 8, 0.1, (v) => (+v).toFixed(1), (v) => { o.size = v; }),
    edRange("Opaklık", o.opacity, 10, 100, 1, edPct, (v) => { o.opacity = v; }, null, 10),
    ed.doc.layers.some((l) => l.type === "draw") ? h("button", { class: "btn sm ghost", onclick: () => {
      ed.doc.layers = ed.doc.layers.filter((l) => l.type !== "draw");
      ed.sel = null;
      edCommit();
      edPanel();
      edQueue();
    } }, icon("trash"), "Tüm çizimleri sil") : null,
  ];
}

function edTabCensor() {
  const L = ed.sel && edLayer(ed.sel), sel = L && L.type === "censor" ? L : null, o = sel || ed.censorOpt;
  return [
    edNote("Gizlemek istediğin alanı sürükleyerek seç: yüz, plaka, adres, telefon numarası…", "pixels"),
    edChoice([["pixel", "Pikselleştir"], ["blur", "Bulanıklaştır"]], o.mode, (v) => {
      o.mode = ed.censorOpt.mode = v;
      if (sel) { edQueue(); edCommit(); }
    }),
    edRange("Güç", o.strength, 10, 100, 1, edPct, (v) => {
      o.strength = ed.censorOpt.strength = v;
      if (sel) edQueue();
    }, sel ? edCommit : null, 10),
    sel ? edLayerActions(sel) : null,
  ];
}

function edTabLayers() {
  if (!ed.doc.layers.length) return [edNote("Henüz katman yok. Yazı, şekil, çizim ya da sansür ekleyince burada görünür.")];
  const list = h("div", { class: "ed-layers" });
  for (const L of [...ed.doc.layers].reverse()) {
    const [ic, name] = ED_TYPE[L.type];
    const label = L.type === "text" ? h("span", { class: "ed-layer-name", "data-no-i18n": true }, (L.text || "").trim().split("\n")[0].slice(0, 40) || tr(name))
      : h("span", { class: "ed-layer-name" }, name);
    list.append(h("div", { class: "ed-layer" + (L.id === ed.sel ? " on" : "") + (L.hidden ? " off" : ""), onclick: () => edSelect(L.id, false) },
      h("span", { class: "ed-layer-ic" }, icon(ic)), label,
      h("button", { class: "btn icon sm ghost", title: L.hidden ? "Göster" : "Gizle", onclick: (e) => {
        e.stopPropagation();
        L.hidden = !L.hidden;
        edCommit();
        edPanel();
        edQueue();
      } }, icon(L.hidden ? "eyeOff" : "eye")),
      h("button", { class: "btn icon sm ghost", title: "Sil", onclick: (e) => { e.stopPropagation(); edRemove(L.id); } }, icon("trash"))));
  }
  const sel = ed.sel && edLayer(ed.sel);
  return [list, sel ? edLayerActions(sel) : null, edNote("Listede üstteki katman görselde de üstte durur.")];
}

const ED_TABS = { crop: edTabCrop, adjust: edTabAdjust, filter: edTabFilter, text: edTabText, shape: edTabShape,
  draw: edTabDraw, censor: edTabCensor, layers: edTabLayers };

function edPanel() {
  $$("#edRail button").forEach((b) => { b.classList.toggle("on", b.dataset.t === ed.tab); b.disabled = !ed.img; });
  $("#edStage").dataset.tool = ed.tab;
  const panel = $("#edPanel"), same = panel.dataset.tab === ed.tab, top = panel.scrollTop;
  panel.dataset.tab = ed.tab;
  panel.replaceChildren(...(ed.img ? ED_TABS[ed.tab]() : [edNote("Bir görsel açınca düzenleme araçları burada görünür.")]).filter(Boolean));
  if (same) panel.scrollTop = top;
}

function edTab(t) {
  if (!ed.img || ed.tab === t) return;
  const crop = t === "crop" || ed.tab === "crop";
  ed.tab = t;
  if (crop) {  // kırpma çerçevesi tüm görseli gösterir
    ed.sel = null;
    ed.zoom = 0;
    ed.panX = ed.panY = 0;
  }
  if (t === "draw" && ed.sel && edLayer(ed.sel)?.type !== "draw") ed.sel = null;
  edPanel();
  edQueue();
}

function edToolbar() {
  const on = !!ed.img;
  $("#edUndo").disabled = !on || !ed.hist.length;
  $("#edRedo").disabled = !on || !ed.fut.length;
  for (const id of ["#edZoomOut", "#edZoomFit", "#edZoomIn", "#edCompare", "#edReset", "#edSaveBtn"]) $(id).disabled = !on;
  $("#edName").textContent = on ? ed.name : tr("Görsel açılmadı");
  const [W, H] = on ? edFrame(false) : [0, 0];
  $("#edDims").textContent = on ? `${Math.round(W)} × ${Math.round(H)}` : "";
  $("#edShowBtn").classList.toggle("hidden", !ed.lastSaved);
}

/* ---------------------------------------------------------------- otomatik iyileştirme */
function edAuto() {
  const base = edBase(), s = 160 / Math.max(base.width, base.height);
  const c = edCanvas(base.width * s, base.height * s), x = c.getContext("2d", { willReadFrequently: true });
  x.drawImage(base, 0, 0, c.width, c.height);
  const d = x.getImageData(0, 0, c.width, c.height).data, hist = new Uint32Array(256);
  let n = 0, sat = 0;
  for (let i = 0; i < d.length; i += 4) {
    if (d[i + 3] < 128) continue;
    hist[Math.round(0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2])]++;
    sat += (Math.max(d[i], d[i + 1], d[i + 2]) - Math.min(d[i], d[i + 1], d[i + 2])) / 255;
    n++;
  }
  if (!n) return;
  const pct = (q) => {
    let acc = 0;
    for (let i = 0; i < 256; i++) if ((acc += hist[i]) >= q * n) return i / 255;
    return 1;
  };
  const lo = pct(0.01), hi = pct(0.99), mid = pct(0.5), r = Math.round;
  Object.assign(ed.doc.adj, {
    exposure: 0,
    contrast: r(edClamp((0.92 / Math.max(0.2, hi - lo) - 1) * 55, -10, 35)),
    brightness: r(edClamp((0.5 - mid) * 110, -30, 40)),
    shadows: lo < 0.03 ? 14 : 0,
    highlights: hi > 0.97 ? -16 : 0,
    vibrance: r(edClamp((0.32 - sat / n) * 90, 0, 30)),
  });
  edCommit();
  edPanel();
  edQueue();
  toast("Otomatik ayarlar uygulandı", "ok");
}

/* ---------------------------------------------------------------- açma */
function edStart(img, name) {
  Object.assign(ed, { img, W: img.naturalWidth || img.width, H: img.naturalHeight || img.height,
    name: (name || tr("Görsel")).slice(0, 80), doc: edBlank(), hist: [], fut: [], sel: null, zoom: 0, panX: 0, panY: 0,
    orientKey: "", baseKey: "", glKey: "", thumbKey: "", lastSaved: "" });
  ed.cur = edJSON();
  if (ed.tab === "crop" || ed.tab === "layers") ed.tab = "adjust";
  edShow();
}

async function edOpenURL(url, name) {
  const img = new Image();
  img.crossOrigin = "anonymous";
  img.src = url;
  try {
    await img.decode();
  } catch {
    toast("Bu görsel açılamadı.", "err");
    return false;
  }
  edStart(img, name);
  return true;
}

function edOpenFile(file) {
  if (!file) return;
  const url = URL.createObjectURL(file);
  edOpenURL(url, file.name.replace(/\.[^.]+$/, "")).finally(() => setTimeout(() => URL.revokeObjectURL(url), 2000));
}

async function edOpenPath(path) {
  if (segs.imgModeSeg.value !== "edit") segs.imgModeSeg.set("edit", false);
  showPage("image");
  const r = await api.editor_url(path);
  if (!r || !r.ok) toast(r ? r.error : "Bu görsel açılamadı.", "err");
  else edOpenURL(r.url, r.name);
}

async function edPick() {
  if (!edRemote()) {  // masaüstünde Windows'un kendi dosya penceresi
    const r = await api.editor_pick();
    if (r && !r.ok) toast(r.error, "err");
    else if (r) edOpenURL(r.url, r.name);
    return;
  }
  const input = h("input", { type: "file", accept: "image/*", class: "rm-file-input" });
  input.addEventListener("change", () => { edOpenFile(input.files[0]); input.remove(); }, { once: true });
  input.addEventListener("cancel", () => input.remove(), { once: true });
  document.body.append(input);
  input.click();
}

async function edPaste() {
  try {
    for (const item of await navigator.clipboard.read()) {
      const type = item.types.find((t) => t.startsWith("image/"));
      if (type) return edOpenFile(new File([await item.getType(type)], tr("Görsel") + ".png", { type }));
    }
    toast("Panoda görsel yok.", "info");
  } catch {
    toast("Panoya erişilemedi. Görseli kopyalayıp Ctrl+V'ye bas.", "info");
  }
}

async function edRecent() {
  const box = $("#edRecentBox"), row = $("#edRecent");
  const list = await api.editor_recent().catch(() => []);
  row.replaceChildren(...(list || []).map((it) => h("button", { title: it.name, "data-no-i18n": true, onclick: () => edOpenPath(it.path) },
    h("img", { src: it.thumb, alt: "" }))));
  box.classList.toggle("hidden", !row.childElementCount);
}

function edShow() {
  $("#edEmpty").classList.toggle("hidden", !!ed.img);
  $("#edView").classList.toggle("hidden", !ed.img);
  if (edRemote()) {  // telefonda pano ve sürükle-bırak yok
    $("#edEmptyText").textContent = tr("Telefonundan bir fotoğraf seç; düzenleyip bilgisayarına ve telefonuna kaydet.");
    $("#edPasteBtn").classList.add("hidden");
  }
  if (!ed.img) edRecent();
  edPanel();
  edToolbar();
  requestAnimationFrame(() => { edFitHeight(); edLayout(); edQueue(); });
}

function edResetAll() {
  if (!ed.img) return;
  ed.doc = edBlank();
  ed.sel = null;
  edFitView();
  edCommit();
  edPanel();
  edQueue();
  toast("Tüm düzenlemeler sıfırlandı. Geri almak için Ctrl+Z.", "info");
}

/* ---------------------------------------------------------------- kaydetme */
async function edExportBlob(fmt, quality, long) {
  const [W, H] = edFrame(false), g = edGL();
  let s = long && Math.max(W, H) > long ? long / Math.max(W, H) : 1;
  s = Math.min(s, Math.min(g ? g.max : 16384, edRemote() ? 4096 : 16384) / Math.max(W, H));
  const base = edGeo(s, ed.doc.geo.crop), img = edAdjust(base, edParams(), true);
  const out = edCanvas(base.width, base.height), x = out.getContext("2d");
  if (fmt === "jpg") {  // JPG saydamlığı desteklemez: boş alanlar beyaz olur
    x.fillStyle = "#fff";
    x.fillRect(0, 0, out.width, out.height);
  }
  x.drawImage(img, 0, 0);
  edDrawLayers(x, out.width, out.height, img);
  edQueue();  // önizlemenin WebGL çıktısı yeniden çizilsin
  const type = fmt === "jpg" ? "image/jpeg" : fmt === "webp" ? "image/webp" : "image/png";
  return new Promise((res) => out.toBlob(res, type, quality / 100));
}

const edDataURL = (blob) => new Promise((res, rej) => {
  const r = new FileReader();
  r.onload = () => res(r.result);
  r.onerror = rej;
  r.readAsDataURL(blob);
});

function edExportInfo() {
  const [W, H] = edFrame(false), long = ed.size === "orig" ? 0 : +ed.size;
  const s = long && Math.max(W, H) > long ? long / Math.max(W, H) : 1;
  $("#edQualBox").classList.toggle("hidden", ed.fmt === "png");
  $("#edQualVal").textContent = edPct(ed.quality);
  $("#edQual").style.setProperty("--a", "0%");
  $("#edQual").style.setProperty("--b", ((ed.quality - 40) / 60) * 100 + "%");
  $("#edExportInfo").textContent = tr("{w} × {h} piksel", { w: Math.round(W * s), h: Math.round(H * s) })
    + (ed.fmt === "jpg" ? " · " + tr("saydam alanlar beyaz olur") : "");
}

function edExportOpen() {
  if (!ed.img) return;
  $("#edExportName").value = ed.name + " " + tr("(düzenlendi)");
  $("#edQual").value = ed.quality;
  edExportInfo();
  $("#edExportOverlay").classList.remove("hidden");
  requestAnimationFrame(() => { segs.edFmtSeg.refresh(); segs.edSizeSeg.refresh(); });
}

async function edExportGo() {
  const btn = $("#edExportGo");
  setLoading(btn, true);
  try {
    const name = $("#edExportName").value.trim() || ed.name;
    const blob = await edExportBlob(ed.fmt, ed.quality, ed.size === "orig" ? 0 : +ed.size);
    if (!blob) throw new Error("blob");
    const opts = { name, format: ed.fmt, quality: ed.quality };
    const ext = ed.fmt === "avif" ? "png" : ed.fmt;
    const res = edRemote() ? await api.editor_save(await window.ttUpload(blob, `${name}.${ext}`), opts)
      : await api.editor_save(await edDataURL(blob), opts);
    if (!res || !res.ok) {
      toast(res ? res.error : "Görsel kaydedilemedi.", "err");
      return;
    }
    ed.lastSaved = res.path;
    $("#edExportOverlay").classList.add("hidden");
    edToolbar();
    toast(tr("Kaydedildi: {name}", { name: res.name }), "ok");
    if (edRemote()) api.open_made(res.path);  // telefonda: telefona kaydetme penceresi
  } catch (e) {
    if (!e || e.message !== "abort") toast("Görsel kaydedilemedi.", "err");
  } finally {
    setLoading(btn, false);
  }
}

async function edCopy() {
  try {
    const blob = await edExportBlob("png", 100, ed.size === "orig" ? 0 : +ed.size);
    await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
    toast("Görsel panoya kopyalandı", "ok");
  } catch {
    toast("Panoya kopyalanamadı.", "err");
  }
}

/* ---------------------------------------------------------------- klavye ve bağlantılar */
function edKey(e) {
  if (!edVisible() || !ed.img || !$("#edExportOverlay").classList.contains("hidden")) return;
  const typing = e.target instanceof Element && e.target.closest("input, textarea, select, [contenteditable]");
  if (e.key === " " && !typing) {
    ed.space = true;
    e.preventDefault();
    return;
  }
  if (typing) return;
  const k = e.key.toLowerCase(), mod = e.ctrlKey || e.metaKey, L = ed.sel && edLayer(ed.sel);
  if (mod && k === "z") edUndo(!e.shiftKey);
  else if (mod && k === "y") edUndo(false);
  else if (mod && k === "d" && L) edDuplicate(L);
  else if (mod && k === "s") edExportOpen();
  else if (mod && k === "0") edFitView();
  else if ((k === "delete" || k === "backspace") && L) edRemove(L.id);
  else if (k === "escape" && ed.sel) edSelect(null, false);
  else if (k.startsWith("arrow") && L) {  // ok tuşlarıyla 1 piksel (Shift: 10) kaydırma
    const [W, H] = edFrame(false), step = e.shiftKey ? 10 : 1;
    const dx = k === "arrowleft" ? -step / W : k === "arrowright" ? step / W : 0, dy = k === "arrowup" ? -step / H : k === "arrowdown" ? step / H : 0;
    edMoveLayer({ p: { x: 0, y: 0 }, L, o: JSON.parse(JSON.stringify(L)) }, { x: dx, y: dy }, { altKey: true });
    edQueue();
    clearTimeout(ed.nudged);
    ed.nudged = setTimeout(edCommit, 400);
  } else return;
  e.preventDefault();
}

function wireEditor() {
  $("#edOpenBtn").addEventListener("click", edPick);
  $("#edOpenBtn2").addEventListener("click", edPick);
  $("#edPasteBtn").addEventListener("click", edPaste);
  $("#edUndo").addEventListener("click", () => edUndo(true));
  $("#edRedo").addEventListener("click", () => edUndo(false));
  $("#edZoomIn").addEventListener("click", () => edZoomTo(ed.scale * 1.25));
  $("#edZoomOut").addEventListener("click", () => edZoomTo(ed.scale / 1.25));
  $("#edZoomFit").addEventListener("click", edFitView);
  const cmp = $("#edCompare");
  cmp.addEventListener("pointerdown", () => { ed.comparing = true; edQueue(); });
  for (const ev of ["pointerup", "pointerleave", "pointercancel"]) {
    cmp.addEventListener(ev, () => { if (ed.comparing) { ed.comparing = false; edQueue(); } });
  }
  $("#edReset").addEventListener("click", edResetAll);
  $("#edSaveBtn").addEventListener("click", edExportOpen);
  $("#edShowBtn").addEventListener("click", () => ed.lastSaved && api.open_made(ed.lastSaved));
  $("#edRail").addEventListener("click", (e) => { const b = e.target.closest("button[data-t]"); if (b) edTab(b.dataset.t); });
  const st = $("#edStage");
  st.addEventListener("pointerdown", edDown);
  st.addEventListener("pointermove", edMove);
  st.addEventListener("pointerup", edUp);
  st.addEventListener("pointercancel", edUp);
  st.addEventListener("dblclick", (e) => {
    if (!ed.img || ed.tab === "crop" || !e.target.closest("#edView")) return;
    const L = edHit(edPoint(e));
    if (L && L.type === "text") {
      edSelect(L.id);
      const ta = $(".ed-text-in");
      if (ta) { ta.focus(); ta.select(); }
    }
  });
  st.addEventListener("wheel", (e) => {
    if (!ed.img) return;
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      edZoomTo(ed.scale * (e.deltaY < 0 ? 1.12 : 1 / 1.12), e.clientX, e.clientY);
    } else if (st.classList.contains("zoomed")) {
      e.preventDefault();
      ed.panX -= e.deltaX;
      ed.panY -= e.deltaY;
      edLayout();
    }
  }, { passive: false });
  new ResizeObserver(() => { if (edVisible() && ed.img) edLayout(); }).observe(st);
  window.addEventListener("resize", () => { if (edVisible()) edFitHeight(); });
  seg("edFmtSeg", (v) => { ed.fmt = v; edExportInfo(); }).set("jpg");
  seg("edSizeSeg", (v) => { ed.size = v; edExportInfo(); }).set("orig");
  $("#edQual").addEventListener("input", () => { ed.quality = +$("#edQual").value; edExportInfo(); });
  $("#edExportGo").addEventListener("click", edExportGo);
  $("#edCopyBtn").addEventListener("click", edCopy);
  $("#edExportClose").addEventListener("click", () => $("#edExportOverlay").classList.add("hidden"));
  $("#edExportOverlay").addEventListener("click", (e) => { if (e.target.id === "edExportOverlay") e.target.classList.add("hidden"); });
  document.addEventListener("keydown", edKey);
  document.addEventListener("keyup", (e) => { if (e.key === " ") ed.space = false; });
  document.addEventListener("paste", (e) => {
    if (!edVisible()) return;
    const f = [...(e.clipboardData?.files || [])].find((x) => x.type.startsWith("image/"));
    if (f) {
      e.preventDefault();
      edOpenFile(f);
    }
  });
  // düzenleyici açıkken pencereye bırakılan görsel dönüştürücüye değil düzenleyiciye gelir
  const prevDrop = HANDLERS.convert_files;
  HANDLERS.convert_files = (ev) => {
    const img = edVisible() && (ev.items || []).find((it) => it.kind === "image");
    if (img) edOpenPath(img.path);
    else prevDrop(ev);
  };
}
