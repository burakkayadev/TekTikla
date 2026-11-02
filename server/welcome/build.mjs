// Google Apps Script'e yapıştırılacak tek dosyayı üretir: e-posta şablonu (template.mjs) + giriş noktası (doPost.js).
// Kullanım: node server/welcome/build.mjs   ->  server/welcome/apps-script.gs
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const template = readFileSync(join(here, "template.mjs"), "utf8").replace(/^export /gm, "");
const entry = readFileSync(join(here, "doPost.js"), "utf8");
const header = "// TekTıkla hoş geldin e-postası — bu dosya build.mjs ile üretilir; düzenlemeyi template.mjs ve doPost.js'te yapın.\n\n";
writeFileSync(join(here, "apps-script.gs"), header + entry + "\n\n" + template);
console.log("apps-script.gs hazır");
