/* İzleme listesi: sonra izlenecek videolar sırayla durur, uygulama kapansa da kalır.
 * Python tarafı: tektikla/watchlist.py + api.py (watch_*). Başlık ve kanal adları sitelerden gelir: her zaman metin düğümü. */
"use strict";

const watch = { items: [], filter: "todo", sort: "mine", drag: null };
const txt = (s) => document.createTextNode(s ?? "");

function watchAgo(ts) {
  const s = Math.max(0, Date.now() / 1000 - ts);
  if (s < 90) return tr("az önce");
  if (s < 3600) return tr(`${Math.round(s / 60)} dk önce`);
  if (s < 86400) return tr(`${Math.round(s / 3600)} sa önce`);
  const d = Math.round(s / 86400);
  return d === 1 ? tr("dün") : tr(`${d} gün önce`);
}

function watchTotal(sec) {
  const m = Math.max(1, Math.round(sec / 60)), hh = Math.floor(m / 60), mm = m % 60;
  return hh ? tr(mm ? `${hh} sa ${mm} dk` : `${hh} sa`) : tr(`${m} dk`);
}

function watchVisible() {
  const list = watch.items.filter((i) => watch.filter === "all" || (watch.filter === "done") === !!i.watched);
  if (watch.sort === "short") return [...list].sort((a, b) => (a.duration ?? Infinity) - (b.duration ?? Infinity));
  if (watch.sort === "new") return [...list].sort((a, b) => b.added - a.added);
  return list;
}

function renderWatch() {
  const todo = watch.items.filter((i) => !i.watched);
  const done = watch.items.length - todo.length;
  const badge = $("#watchBadge");
  badge.textContent = tr(todo.length);
  badge.classList.toggle("hidden", !todo.length);
  $("#watchCntTodo").textContent = todo.length ? tr(todo.length) : "";
  $("#watchCntDone").textContent = done ? tr(done) : "";
  const total = todo.reduce((s, i) => s + (i.duration || 0), 0);
  $("#watchTotal").textContent = total ? tr("{t} izlenecek", { t: watchTotal(total) }) : "";
  $("#watchClearBtn").classList.toggle("hidden", !done);

  const nextId = todo.length ? todo[0].id : null;  // sıradaki: kendi sırandaki ilk izlenmemiş video
  const mine = watch.sort === "mine";
  const list = watchVisible();
  $("#watchList").replaceChildren(...list.map((it) => watchRow(it, mine && it.id === nextId, mine)));
  $("#watchEmpty").classList.toggle("hidden", list.length > 0);
  if (!list.length) {
    const [title, text] = !watch.items.length
      ? ["Listen boş", "Bir link ekle; sonra izlemek istediğin videolar burada sıraya girer."]
      : watch.filter === "done"
        ? ["Henüz izlediğin yok", "İzlediğin videoları ✓ ile işaretleyince burada toplanır."]
        : ["Hepsini izledin", "Listede izlenecek video kalmadı. Yeni bir link ekleyebilirsin."];
    $("#watchEmptyTitle").textContent = tr(title);
    $("#watchEmptyText").textContent = tr(text);
  }
  requestAnimationFrame(() => segs.watchFilter && segs.watchFilter.refresh());  // sayılar düğme genişliğini değiştirir
}

function watchRow(it, isNext, grab) {
  const loading = it.status === "loading" || it.status === "retry";
  const thumb = h("div", { class: "w-thumb" },
    it.thumb ? h("img", { src: it.thumb, alt: "", loading: "lazy", onerror: (e) => e.target.remove() }) : icon("film"),
    loading ? h("span", { class: "w-spin" }) : null,
    it.duration_text ? h("span", { class: "dur" }, txt(it.duration_text)) : null);
  const title = h("div", { class: "t", title: it.title || it.url, "data-no-i18n": true },
    txt(it.title || (loading ? tr("Bilgiler alınıyor…") : it.url)));
  const meta = h("div", { class: "s" });
  if (it.channel) meta.append(h("span", { "data-no-i18n": true }, txt(it.channel)));
  meta.append(h("span", {}, txt(it.watched && it.watched_at
    ? tr("{d} izlendi", { d: watchAgo(it.watched_at) }) : tr("{d} eklendi", { d: watchAgo(it.added) }))));
  const body = h("div", { class: "w-body" },
    isNext ? h("span", { class: "w-next" }, icon("play"), "Sıradaki") : null,
    title, meta,
    it.status === "error" ? h("div", { class: "err" }, txt(it.error || tr("Bilgiler alınamadı.")), txt(" "),
      h("button", { class: "linkish", onclick: () => watchDo(api.watch_retry(it.id)) }, "Tekrar dene")) : null);
  const acts = h("div", { class: "w-actions" },
    h("div", { class: "w-move" },
      h("button", { class: "btn icon sm", title: "Yukarı taşı", onclick: () => watchStep(it, -1) }, icon("arrowUp")),
      h("button", { class: "btn icon sm", title: "Aşağı taşı", onclick: () => watchStep(it, 1) }, icon("arrowDown"))),
    h("button", { class: "btn sm" + (it.watched ? "" : " primary"), onclick: () => watchOpen(it) },
      icon("play"), it.watched ? "Tekrar izle" : "İzle"),
    h("button", { class: "btn icon", title: "İndir", onclick: () => watchDownload(it) }, icon("download")),
    h("button", { class: "btn icon danger", title: "Listeden kaldır", onclick: () => watchDo(api.watch_remove(it.id)) }, icon("trash")));
  const check = h("button", { class: "w-check" + (it.watched ? " on" : ""),
    title: it.watched ? "İzlenmedi olarak işaretle" : "İzledim olarak işaretle", onclick: (e) => watchToggle(it, e) }, icon("check"));
  return h("div", { class: "card w-row" + (it.watched ? " watched" : "") + (isNext ? " next" : "") + (grab ? " mine" : ""),
    "data-id": it.id, draggable: grab ? "true" : null },
    grab ? h("span", { class: "w-grip", title: "Sürükleyerek sırala" }, icon("grip")) : null, check, thumb, body, acts);
}

async function watchDo(pending) {
  watch.items = await pending;
  renderWatch();
}

function watchToggle(it, e) {
  // izlenecekler görünümündeyken satır yumuşakça çıkar, sonra liste yenilenir
  const row = e.currentTarget.closest(".w-row");
  e.currentTarget.classList.toggle("on", !it.watched);
  const leaves = watch.filter !== "all";
  if (leaves) row.classList.add("leaving");
  setTimeout(() => watchDo(api.watch_set(it.id, !it.watched)), leaves ? 280 : 0);
}

function watchStep(it, dir) {
  // dokunmatik ekranda sürükleme yok: yukarı/aşağı taşı (görünen komşusunun yerine geçer)
  const list = watchVisible();
  const pos = list.findIndex((x) => x.id === it.id), other = list[pos + dir];
  if (!other) return;
  watchDo(api.watch_move(it.id, watch.items.findIndex((x) => x.id === other.id)));
}

async function watchOpen(it) {
  if (await api.watch_open(it.id))
    toast(it.watched ? "Tarayıcıda açıldı." : "Tarayıcıda açıldı. İzleyince ✓ ile işaretleyebilirsin.", "ok");
}

function watchDownload(it) {
  showPage("download");
  $("#urlInput").value = it.url;
  analyze(it.url);
}

function watchAdded(r, from) {
  watch.items = r.items;
  renderWatch();
  if (r.added) {
    toast(r.added === 1 ? "İzleme listesine eklendi" : `${r.added} video izleme listesine eklendi`, "ok");
    if (from) flyToQueue(from, "watch");
  } else if (r.dupes) toast(r.dupes === 1 ? "Bu video zaten izleme listende" : "Bu videolar zaten izleme listende");
  else toast("Geçerli bir link bulunamadı", "err");
  return r.added > 0;
}

async function watchAdd(text) {
  const value = (text ?? $("#watchInput").value).trim();
  if (!value) { $("#watchInput").focus(); return; }
  if (watchAdded(await api.watch_add(value, null))) $("#watchInput").value = "";
}

// YouTube'un "Daha sonra izle" ve "Beğenilen videolar" listeleri: yalnızca Google ile giriş yapanlara açık
// (hesap sistemi kurulu değilse herkese). Liste, tarayıcıdaki YouTube oturumuyla okunur.
const YT_LISTS = { later: "https://www.youtube.com/playlist?list=WL", liked: "https://www.youtube.com/playlist?list=LL" };

function ytAllowed() {
  const a = typeof acct !== "undefined" ? acct.state : { configured: false };
  return !a.configured || (a.user && a.user.provider === "google");
}

function renderWatchYt() {
  const ok = ytAllowed();
  const browser = state.settings.cookies_browser || "Yok";
  $("#watchYt").classList.toggle("locked", !ok);
  $("#watchYtHint").textContent = !ok
    ? tr("YouTube listelerini çekmek için Google ile giriş yap.")
    : browser === "Yok"
      ? tr("YouTube'da oturumu açık tarayıcını Ayarlar > Tarayıcı çerezleri'nden seç (Firefox önerilir).")
      : tr("{b} tarayıcısındaki YouTube oturumu kullanılır; yeniden çekince yalnızca yeni videolar eklenir.", { b: browser });
}

async function watchYt(which) {
  if (!ytAllowed()) { openAuth(); return; }
  if ((state.settings.cookies_browser || "Yok") === "Yok") {
    toast("Önce YouTube'da oturumu açık tarayıcını seç.", "err");
    showPage("settings");
    setTimeout(() => $("#cookiesSelect").scrollIntoView({ block: "center", behavior: "smooth" }), 80);
    return;
  }
  const r = await api.watch_add(YT_LISTS[which], null);
  watch.items = r.items;
  renderWatch();
  toast(r.added ? (which === "later" ? "Daha sonra izle listen çekiliyor…" : "Beğendiğin videolar çekiliyor…")
    : "Bu liste şu an çekiliyor.", r.added ? "ok" : "info");
}

function wireWatchDrag() {
  const list = $("#watchList");
  list.addEventListener("dragstart", (e) => {
    const row = e.target.closest && e.target.closest(".w-row.mine");
    if (!row) return;
    watch.drag = row.dataset.id;
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", "");
    requestAnimationFrame(() => row.classList.add("dragging"));
  });
  list.addEventListener("dragover", (e) => {
    if (!watch.drag) return;
    e.preventDefault();
    const moving = list.querySelector(".dragging"), row = e.target.closest(".w-row");
    if (!moving || !row || row === moving) return;
    const r = row.getBoundingClientRect();
    if (e.clientY > r.top + r.height / 2) row.after(moving); else row.before(moving);
  });
  list.addEventListener("drop", (e) => e.preventDefault());
  list.addEventListener("dragend", () => {
    const id = watch.drag, moving = list.querySelector(".dragging");
    watch.drag = null;
    if (!id || !moving) return;
    moving.classList.remove("dragging");
    // yeni yer: görünen listede bir önceki öğenin hemen arkası (filtreliyken de doğru çalışır)
    const ids = [...list.children].map((c) => c.dataset.id), pos = ids.indexOf(id);
    const rest = watch.items.map((i) => i.id).filter((x) => x !== id);
    const index = pos > 0 ? rest.indexOf(ids[pos - 1]) + 1 : (ids[1] ? rest.indexOf(ids[1]) : 0);
    if (watch.items.findIndex((i) => i.id === id) === index) renderWatch();
    else watchDo(api.watch_move(id, index));
  });
}

function wireWatch() {
  seg("watchFilter", (v) => { watch.filter = v; renderWatch(); }).set("todo");
  $("#watchSort").addEventListener("change", (e) => { watch.sort = e.target.value; renderWatch(); });
  $("#watchAddBtn").addEventListener("click", () => watchAdd());
  $("#watchInput").addEventListener("keydown", (e) => { if (e.key === "Enter") watchAdd(); });
  $("#watchPasteBtn").addEventListener("click", async () => {
    try { const t = (await navigator.clipboard.readText()).trim(); if (t) { $("#watchInput").value = t; watchAdd(t); } }
    catch { toast("Pano okunamadı, Ctrl+V ile yapıştırın.", "err"); }
  });
  // geri alınamaz: ilk basışta onay ister
  $("#watchClearBtn").addEventListener("click", (e) => {
    const btn = e.currentTarget, label = btn.querySelector("span");
    if (!btn.dataset.armed) {
      btn.dataset.armed = "1";
      label.textContent = tr("Emin misin? Tekrar bas");
      setTimeout(() => { delete btn.dataset.armed; label.textContent = tr("İzlenenleri temizle"); }, 3500);
      return;
    }
    delete btn.dataset.armed;
    label.textContent = tr("İzlenenleri temizle");
    watchDo(api.watch_clear());
  });
  $("#mWatchBtn").addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    if (state.mediaUrl) watchAdded(await api.watch_add(state.mediaUrl, null), btn);
  });
  $("#plWatchBtn").addEventListener("click", async (e) => {
    const btn = e.currentTarget, m = state.media;
    const picked = m ? m.entries.filter((x) => x.available && state.plSel.has(x.index)) : [];
    if (!picked.length) { toast("Listeden en az bir video seçin.", "err"); return; }
    watchAdded(await api.watch_add("", picked.map((x) => ({ url: x.url, title: x.title, channel: x.channel,
      seconds: x.seconds, thumb: x.thumb }))), btn);
  });
  $("#watchYtLater").addEventListener("click", () => watchYt("later"));
  $("#watchYtLiked").addEventListener("click", () => watchYt("liked"));
  $("#cookiesSelect").addEventListener("change", () => setTimeout(renderWatchYt, 50));
  wireWatchDrag();
  Object.assign(HANDLERS, { watch: (ev) => { if (!watch.drag) { watch.items = ev.items; renderWatch(); } } });
}

function watchInit(init) {
  watch.items = init.watch || [];
  renderWatch();
  renderWatchYt();
}
