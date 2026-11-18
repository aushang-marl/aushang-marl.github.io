// Prints localized date labels for data/termine.json as JSON: {id: {lang: "label"}}.
// Usage: node tools/termine_labels.js data/termine.json
const fs = require('fs');
const data = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const LOC = { de: 'de-DE', ar: 'ar', en: 'en-GB', fr: 'fr-FR', tr: 'tr-TR', sq: 'sq-AL', ru: 'ru-RU', fa: 'fa-IR-u-ca-gregory', zh: 'zh-CN' };
// Kurmanji is missing from ICU, so it is formatted by hand.
const KU_DAY = ['Yekşem', 'Duşem', 'Sêşem', 'Çarşem', 'Pêncşem', 'În', 'Şemî'];
const KU_MON = ['Çile', 'Sibat', 'Adar', 'Nîsan', 'Gulan', 'Hezîran', 'Tîrmeh', 'Tebax', 'Îlon', 'Cotmeh', 'Mijdar', 'Kanûn'];
const d = s => new Date(s + 'T12:00:00Z');
const ku = s => { const x = d(s); return `${KU_DAY[x.getUTCDay()]} ${x.getUTCDate()} ${KU_MON[x.getUTCMonth()]}`; };
const opt = { weekday: 'short', day: 'numeric', month: 'long', timeZone: 'UTC' };
const out = {};
for (const it of data.items) {
  out[it.id] = {};
  for (const lang of Object.keys(data.ui)) {
    const parts = it.ranges.map(([a, b]) => {
      if (lang === 'ku') return a === b ? ku(a) : `${ku(a)} – ${ku(b)}`;
      const f = new Intl.DateTimeFormat(LOC[lang], opt);
      return a === b ? f.format(d(a)) : f.formatRange(d(a), d(b));
    });
    out[it.id][lang] = parts.join(' · ');
  }
}
console.log(JSON.stringify(out, null, 1));
