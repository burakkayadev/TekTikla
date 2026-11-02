/* Telefondan kullan (bilgisayardaki pencere): aynı Wi-Fi'deki telefon QR kodu okutup bu bilgisayardaki TekTıkla'yı
 * tarayıcısında kullanır. Python tarafı: api.py remote_* ve tektikla/remote.py; telefondaki sayfa web/remote.js'i kullanır. */
"use strict";

const remoteUi = { info: { on: false }, timer: 0 };
const bare = (url) => String(url || "").replace(/^https?:\/\//, "");

function renderRemote() {
  const r = remoteUi.info, on = !!r.on;
  $("#remoteToggle").checked = on;
  $("#remoteBtn").classList.toggle("on", on);
  $("#remoteSetState").textContent = tr(on ? "Açık · telefonundan bağlanabilirsin" : "Kapalı · iPhone ya da Android, aynı Wi-Fi'den");
  $("#remoteOff").classList.toggle("hidden", on);
  $("#remoteNoNet").classList.toggle("hidden", !(on && r.offline));
  $("#remoteBody").classList.toggle("hidden", !r.url);  // açılışta yalnızca ayar bilinir; adres pencere açılınca gelir
  if (!r.url) return;
  const img = $("#remoteQr");
  if (img.getAttribute("src") !== r.qr) img.src = r.qr;
  $("#remoteUrl").textContent = bare(r.url);
  $("#remoteCode").textContent = r.code;
  const others = (r.others || []).map(bare);
  $("#remoteOthers").classList.toggle("hidden", !others.length);
  $("#remoteOthers").textContent = others.length ? tr("Açılmazsa şu adresi dene: {list}", { list: others.join(" · ") }) : "";
  $("#remoteApk").classList.toggle("hidden", !r.apk);
  if (r.apk && $("#remoteApkQr").getAttribute("src") !== r.apk) $("#remoteApkQr").src = r.apk;
  const devs = r.devices || [];
  $("#remoteDevCount").textContent = devs.length ? String(devs.length) : "";
  $("#remoteDevices").replaceChildren(...(devs.length
    ? devs.map((d) => h("span", { class: "chip ok rm-dev" }, icon("phone"),
      h("b", { "data-no-i18n": d.name !== "Tarayıcı" }, d.name), h("small", { "data-no-i18n": true }, d.ip)))
    : [h("span", { class: "rm-none" }, "Henüz bağlı telefon yok")]));
}

async function openRemote() {
  remoteUi.info = await api.remote_info();
  renderRemote();
  $("#remoteOverlay").classList.remove("hidden");
  clearInterval(remoteUi.timer);
  remoteUi.timer = setInterval(async () => {  // pencere açıkken bağlanan telefonlar görünsün
    if ($("#remoteOverlay").classList.contains("hidden")) { clearInterval(remoteUi.timer); return; }
    if (!remoteUi.info.on) return;
    remoteUi.info = await api.remote_info();
    renderRemote();
  }, 2500);
}

function closeRemote() {
  $("#remoteOverlay").classList.add("hidden");
  clearInterval(remoteUi.timer);
}

async function remoteToggle(on) {
  const t = $("#remoteToggle");
  t.disabled = true;
  remoteUi.info = await api.remote_set(on);
  t.disabled = false;
  if (remoteUi.info.error) toast(remoteUi.info.error, "err");
  else if (on) toast("Telefon bağlantısı açıldı. QR kodu telefonunla okut.", "ok");
  renderRemote();
}

async function remoteReset(e) {
  // bağlı telefonların bağlantısı kopar: ilk basışta onay ister
  const btn = e.currentTarget, label = btn.querySelector("span");
  if (!btn.dataset.armed) {
    btn.dataset.armed = "1";
    label.textContent = tr("Emin misin? Tekrar bas");
    setTimeout(() => { if (btn.isConnected) { delete btn.dataset.armed; label.textContent = tr("Yeni kod"); } }, 4000);
    return;
  }
  delete btn.dataset.armed;
  label.textContent = tr("Yeni kod");
  remoteUi.info = await api.remote_reset();
  renderRemote();
  toast("Yeni kod oluşturuldu. Telefonların QR kodu yeniden okutmalı.", "ok");
}

function wireRemote() {
  $("#remoteBtn").addEventListener("click", openRemote);
  $("#remoteSetBtn").addEventListener("click", openRemote);
  $("#remoteClose").addEventListener("click", closeRemote);
  $("#remoteToggle").addEventListener("change", (e) => remoteToggle(e.target.checked));
  $("#remoteReset").addEventListener("click", remoteReset);
  $("#remoteOverlay").addEventListener("click", (e) => { if (e.target.id === "remoteOverlay") closeRemote(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#remoteOverlay").classList.contains("hidden")) closeRemote(); });
}

function remoteInit(init) {
  remoteUi.info = { on: !!init.settings.remote_enabled };
  renderRemote();
}
