#!/usr/bin/env python3
"""Build a multilingual QR notice.

Usage:  python3 tools/build.py notices/<slug>.json
Output: <slug>/index.html   interactive page (language picker first, 10 languages)
        a/<slug>/qr.svg|png   QR code pointing to the public page
        a/<slug>/poster.html  printable German A4 poster with QR code
        a/<slug>/label.html   small QR label to stick onto an existing notice
Then:   node tools/render.js a/<slug>   -> poster.pdf, label.pdf, preview PNGs
"""
import html, json, pathlib, sys
import segno

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "tools" / "config.json").read_text())
BASE = CONFIG["base_url"].rstrip("/")
PAGES = CONFIG.get("pages_dir", "").strip("/")  # "" = notices live at <base>/<slug>/


def rel(slug):
    return f"{PAGES}/{slug}" if PAGES else slug

LANGS = [  # code, native name, direction
    ("de", "Deutsch", "ltr"), ("ar", "العربية", "rtl"), ("en", "English", "ltr"),
    ("fr", "Français", "ltr"), ("ku", "Kurdî", "ltr"), ("tr", "Türkçe", "ltr"),
    ("sq", "Shqip", "ltr"), ("ru", "Русский", "ltr"), ("fa", "فارسی", "rtl"),
    ("zh", "中文", "ltr"),
]

UI = {
    "de": {"pick": "Sprache wählen", "change": "Sprache", "when": "Wann", "where": "Wo", "who": "Für wen", "tips": "Gut zu wissen", "more": "Mehr erfahren", "listen": "Anhören", "stop": "Stopp"},
    "ar": {"pick": "اختر اللغة", "change": "اللغة", "when": "متى", "where": "أين", "who": "لمن", "tips": "معلومات مفيدة", "more": "اعرف المزيد", "listen": "استمع", "stop": "إيقاف"},
    "en": {"pick": "Choose your language", "change": "Language", "when": "When", "where": "Where", "who": "For whom", "tips": "Good to know", "more": "Learn more", "listen": "Listen", "stop": "Stop"},
    "fr": {"pick": "Choisissez la langue", "change": "Langue", "when": "Quand", "where": "Où", "who": "Pour qui", "tips": "Bon à savoir", "more": "En savoir plus", "listen": "Écouter", "stop": "Arrêter"},
    "ku": {"pick": "Zimanê xwe hilbijêre", "change": "Ziman", "when": "Kengî", "where": "Li ku", "who": "Ji bo kê", "tips": "Baş e ku bizanibin", "more": "Bêtir fêr bibe", "listen": "Guhdarî bike", "stop": "Rawestîne"},
    "tr": {"pick": "Dil seçin", "change": "Dil", "when": "Ne zaman", "where": "Nerede", "who": "Kimler için", "tips": "Bilmekte fayda var", "more": "Daha fazla bilgi", "listen": "Dinle", "stop": "Durdur"},
    "sq": {"pick": "Zgjidhni gjuhën", "change": "Gjuha", "when": "Kur", "where": "Ku", "who": "Për kë", "tips": "Mirë të dini", "more": "Mësoni më shumë", "listen": "Dëgjo", "stop": "Ndalo"},
    "ru": {"pick": "Выберите язык", "change": "Язык", "when": "Когда", "where": "Где", "who": "Для кого", "tips": "Полезно знать", "more": "Узнать больше", "listen": "Слушать", "stop": "Стоп"},
    "fa": {"pick": "زبان را انتخاب کنید", "change": "زبان", "when": "کی", "where": "کجا", "who": "برای چه کسانی", "tips": "خوب است بدانید", "more": "بیشتر بدانید", "listen": "گوش دهید", "stop": "توقف"},
    "zh": {"pick": "请选择语言", "change": "语言", "when": "时间", "where": "地点", "who": "对象", "tips": "温馨提示", "more": "了解更多", "listen": "收听", "stop": "停止"},
}

VOICES = {  # edge-tts neural voices; Kurdish has no voice -> Turkish voice reads the Kurmanji text
    "de": "de-DE-KatjaNeural", "ar": "ar-SY-AmanyNeural", "en": "en-GB-SoniaNeural",
    "fr": "fr-FR-DeniseNeural", "ku": "tr-TR-EmelNeural", "tr": "tr-TR-EmelNeural",
    "sq": "sq-AL-AnilaNeural", "ru": "ru-RU-SvetlanaNeural", "fa": "fa-IR-DilaraNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
}


def audio_script(c, L):
    U = UI[c]
    parts = [L["title"] + ".", L.get("subtitle", "")]
    parts += [(f"{U[k]}: {v}." if U.get(k) else v) for k, v in L.get("facts", [])]
    parts.append(L.get("text", ""))
    if L.get("tips"):
        parts.append(U["tips"] + ": " + ". ".join(L["tips"]) + ".")
    parts += [L.get("bg_title", ""), L.get("bg_text", "")]
    return "\n".join(p for p in parts if p)


SCAN_LINE = "Übersetzung · ترجمة · Translation · Traduction · Werger · Çeviri · Përkthim · Перевод · ترجمه · 翻译"

THEMES = {
    "night": {"bg": "#14213d", "bg2": "#0b132b", "accent": "#ffb703", "ink": "#fdf6e3"},
    "warm": {"bg": "#9b2226", "bg2": "#6a040f", "accent": "#ffd166", "ink": "#fffaf0"},
    "fresh": {"bg": "#1b4332", "bg2": "#081c15", "accent": "#b7e4c7", "ink": "#f1faee"},
    "info": {"bg": "#023e8a", "bg2": "#03045e", "accent": "#90e0ef", "ink": "#ffffff"},
}

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600;800'
         '&family=Noto+Sans+Arabic:wght@400;600;800&display=swap" rel="stylesheet">')


def page_html(n, url):
    t = THEMES[n.get("theme", "night")]
    data = {"emoji": n.get("emoji", "📢"), "langs": n["langs"], "ui": UI,
            "order": [[c, name, d] for c, name, d in LANGS if c in n["langs"]],
            "audio": n.get("_audio", []), "bcp": {"de":"de-DE","ar":"ar","en":"en-GB","fr":"fr-FR","ku":"ku","tr":"tr-TR","sq":"sq-AL","ru":"ru-RU","fa":"fa-IR","zh":"zh-CN"}}
    title = html.escape(n["langs"]["de"]["title"])
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="robots" content="noindex">
{FONTS}
<style>
:root{{--bg:{t['bg']};--bg2:{t['bg2']};--ac:{t['accent']};--ink:{t['ink']};--card:#ffffff;--text:#1d2433;--muted:#5b6475}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:'Noto Sans','Noto Sans Arabic',system-ui,sans-serif;background:#f4f1ea;color:var(--text);line-height:1.55}}
[dir=rtl] body,[dir=rtl]{{font-family:'Noto Sans Arabic','Noto Sans',system-ui,sans-serif}}
.hero{{background:radial-gradient(circle at 70% 20%,rgba(255,183,3,.35),transparent 55%),linear-gradient(160deg,var(--bg),var(--bg2));color:var(--ink);padding:28px 20px 34px;text-align:center}}
.emoji{{font-size:64px;line-height:1;filter:drop-shadow(0 0 18px rgba(255,200,80,.7))}}
h1{{margin:10px 0 4px;font-size:30px;font-weight:800}}
.sub{{margin:0;opacity:.9}}
main{{max-width:640px;margin:-18px auto 40px;padding:0 16px}}
.card{{background:var(--card);border-radius:16px;padding:18px 18px;margin:0 0 14px;box-shadow:0 4px 18px rgba(0,0,0,.07)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px;margin-top:14px}}
.lang{{display:block;width:100%;padding:16px 10px;border:0;border-radius:14px;background:#fff;color:var(--text);font:inherit;font-size:20px;font-weight:600;cursor:pointer;box-shadow:0 2px 10px rgba(0,0,0,.08)}}
.lang:active,.lang:hover{{background:var(--ac)}}
.lang.ar,.lang.fa{{font-family:'Noto Sans Arabic',sans-serif}}
.fact{{display:flex;gap:12px;align-items:flex-start;padding:8px 0;border-bottom:1px solid #eee}}
.fact:last-child{{border:0}}
.fact .ic{{font-size:24px;width:32px;text-align:center}}
.fact b{{display:block;font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}}
h2{{font-size:19px;margin:0 0 8px}}
ul{{margin:0;padding-inline-start:22px}}
a.btn{{display:flex;gap:10px;align-items:center;padding:14px 16px;margin:8px 0 0;border-radius:12px;background:var(--bg);color:var(--ink);text-decoration:none;font-weight:600}}
.top{{position:sticky;top:0;z-index:2;display:flex;justify-content:flex-end;padding:8px 12px;background:var(--bg2)}}
.top button{{border:1px solid rgba(255,255,255,.4);background:transparent;color:var(--ink);border-radius:999px;padding:6px 14px;font:inherit;cursor:pointer}}
.listen{{display:flex;align-items:center;justify-content:center;gap:12px;width:100%;padding:18px;margin:0 0 14px;border:0;border-radius:16px;background:var(--ac);color:#111;font:inherit;font-size:22px;font-weight:800;cursor:pointer;box-shadow:0 4px 18px rgba(0,0,0,.12)}}
.listen:focus-visible,.lang:focus-visible{{outline:4px solid #000;outline-offset:2px}}
.sr{{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}}
.hidden{{display:none}}
footer{{text-align:center;color:var(--muted);font-size:13px;padding-bottom:30px}}
</style></head>
<body>
<div id="picker">
  <div class="hero"><div class="emoji">🌐</div><h1>{title}</h1>
  <p class="sub" id="pickTitle">Sprache wählen · اختر اللغة · Choose your language</p></div>
  <main><h2 class="sr">Sprache wählen / Choose language</h2><div class="grid" id="langGrid" role="list"></div></main>
</div>
<div id="view" class="hidden">
  <div class="top"><button id="changeBtn">🌐 <span id="changeLbl"></span></button></div>
  <div class="hero"><div class="emoji" id="vEmoji"></div><h1 id="vTitle"></h1><p class="sub" id="vSub"></p></div>
  <main>
    <button class="listen" id="listenBtn" type="button"><span aria-hidden="true">🔊</span><span id="listenLbl"></span></button>
    <audio id="player" preload="none"></audio>
    <section class="card" id="vFacts"></section>
    <section class="card"><p id="vText" style="margin:0;font-size:18px"></p></section>
    <section class="card" id="vTipsCard"><h2 id="vTipsH"></h2><ul id="vTips"></ul></section>
    <section class="card"><h2 id="vBgH"></h2><p id="vBg" style="margin:0"></p><div id="vLinks"></div></section>
  </main>
  <footer>Marl · {html.escape(n['slug'])}</footer>
</div>
<script>
const D={json.dumps(data, ensure_ascii=False)};
const ICON={{market:"📍",when:"📅",where:"📍",who:"👨‍👩‍👧",wiki:"📖",video:"▶️",link:"🔗",info:"ℹ️",time:"⏰"}};
const $=id=>document.getElementById(id);
let CUR='',SPEAK='';
function stopAudio(){{const a=$('player');a.pause();a.currentTime=0;if(window.speechSynthesis)speechSynthesis.cancel();setBtn(false)}}
function setBtn(on){{const U=D.ui[CUR]||D.ui.en;$('listenLbl').textContent=on?U.stop:U.listen;$('listenBtn').setAttribute('aria-pressed',on)}}
function playing(){{return !$('player').paused||(window.speechSynthesis&&speechSynthesis.speaking)}}
$('player').onended=()=>setBtn(false);
const esc=s=>String(s).replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
D.order.forEach(([c,name])=>{{const b=document.createElement('button');b.className='lang '+c;b.textContent=name;b.lang=c;b.setAttribute('role','listitem');b.onclick=()=>{{location.hash=c}};$('langGrid').appendChild(b)}});
function show(c){{
  CUR=c;const L=D.langs[c],U=D.ui[c]||D.ui.en,dir=(D.order.find(o=>o[0]===c)||[])[2]||'ltr';
  document.documentElement.lang=c;document.documentElement.dir=dir;document.title=L.title;
  $('vEmoji').textContent=D.emoji;$('vTitle').textContent=L.title;$('vSub').textContent=L.subtitle||'';
  $('changeLbl').textContent=U.change;
  $('vFacts').innerHTML=(L.facts||[]).map(([k,v])=>`<div class="fact"><span class="ic">${{ICON[k]||'•'}}</span><div>${{U[k]?'<b>'+esc(U[k])+'</b>':''}}${{esc(v)}}</div></div>`).join('');
  $('vText').textContent=L.text||'';
  $('vTipsCard').classList.toggle('hidden',!(L.tips&&L.tips.length));
  $('vTipsH').textContent=U.tips;$('vTips').innerHTML=(L.tips||[]).map(t=>`<li>${{esc(t)}}</li>`).join('');
  $('vBgH').textContent=L.bg_title||U.more;$('vBg').textContent=L.bg_text||'';
  $('vLinks').innerHTML=(L.links||[]).map(([k,label,url])=>`<a class="btn" href="${{esc(url)}}" target="_blank" rel="noopener"><span>${{ICON[k]||'🔗'}}</span>${{esc(label)}}</a>`).join('');
  SPEAK=[L.title,L.subtitle,...(L.facts||[]).map(([k,v])=>U[k]?U[k]+': '+v:v),L.text,...(L.tips||[]),L.bg_title,L.bg_text].filter(Boolean).join('. ');
  setBtn(false);
  $('picker').classList.add('hidden');$('view').classList.remove('hidden');scrollTo(0,0);$('listenBtn').focus();
}}
function route(){{stopAudio();const c=location.hash.slice(1);if(D.langs[c])show(c);else{{document.documentElement.dir='ltr';$('view').classList.add('hidden');$('picker').classList.remove('hidden')}}}}
$('changeBtn').onclick=()=>{{stopAudio();location.hash=''}};
$('listenBtn').onclick=()=>{{
  if(playing()){{stopAudio();return}}
  if(D.audio.includes(CUR)){{const a=$('player');a.src='audio/'+CUR+'.mp3';a.play();setBtn(true);return}}
  if(window.speechSynthesis){{const u=new SpeechSynthesisUtterance(SPEAK);u.lang=D.bcp[CUR]||CUR;u.onend=()=>setBtn(false);speechSynthesis.speak(u);setBtn(true)}}
}};
addEventListener('hashchange',route);
// Stop the voice as soon as the reader leaves this language view: any link, back button, tab switch or closing the page.
document.addEventListener('click',e=>{{if(e.target.closest('a'))stopAudio()}},true);
addEventListener('pagehide',stopAudio);
document.addEventListener('visibilitychange',()=>{{if(document.hidden)stopAudio()}});
// Always ask for the language first when the QR code is scanned (no hash in the QR URL).
route();
</script>
</body></html>
"""


def qr_img(url, out_dir):
    q = segno.make(url, error="m")
    q.save(out_dir / "qr.svg", scale=10, border=2, dark="#111111")
    q.save(out_dir / "qr.png", scale=20, border=2, dark="#111111")
    return q.svg_inline(scale=10, border=4, dark="#111111", omitsize=True)


def photo_style(p, i, t):
    """Optional faint place photo behind an item card: poster.item_photos[i] = "img/x.jpg"."""
    photos = p.get("item_photos") or []
    ph = photos[i] if i < len(photos) else None
    if not ph:
        return ""
    ph, pos = (ph, "center") if isinstance(ph, str) else ph  # "img/x.jpg" or ["img/x.jpg", "center 70%"]
    bg = t["bg2"]
    return (f' style="background:linear-gradient(90deg,{bg}f2 0%,{bg}d9 48%,{bg}59 100%),'
            f'url(\'{html.escape(ph)}\') {pos}/cover no-repeat;min-height:30mm"')


def poster_html(n, svg):
    p, t = n["poster"], THEMES[n.get("theme", "night")]
    e = html.escape
    title_px = 80 if len(p["title"]) <= 13 else max(48, int(80 * 13 / len(p["title"])))
    emoji_px = 90 if p.get("items") else 170
    extra = ".kicker{margin-top:2mm!important}.note{font-size:20px!important;margin-top:5mm!important}.date{font-size:34px!important}.main{padding-bottom:4mm!important}" if p.get("items") else ""
    if len(p.get("items", [])) >= 4:
        extra += ".item{padding:2.5mm 5mm!important}.item b{font-size:22px!important}.item .w{font-size:17px!important}.item .p{font-size:14px!important}.items{gap:3mm!important;margin-top:5mm!important}h1{margin:2mm 0 3mm!important}"
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><title>{e(p['title'])} – Plakat</title>
{FONTS}<style>
@page{{size:A4;margin:0}}*{{box-sizing:border-box}}
html,body{{margin:0;width:210mm;height:297mm}}
body{{font-family:'Noto Sans',sans-serif;background:radial-gradient(circle at 75% 18%,rgba(255,190,60,.45),transparent 42%),linear-gradient(165deg,{t['bg']},{t['bg2']});color:{t['ink']};display:flex;flex-direction:column;padding:16mm 16mm 12mm;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
.emoji{{font-size:{emoji_px}px;line-height:1;text-align:center;filter:drop-shadow(0 0 30px rgba(255,200,80,.8))}}
.kicker{{text-align:center;text-transform:uppercase;letter-spacing:.3em;color:{t['accent']};font-weight:800;font-size:20px;margin-top:8mm}}
h1{{text-align:center;font-size:{title_px}px;line-height:1.05;margin:3mm 0 6mm;font-weight:800}}
.date{{text-align:center;font-size:40px;font-weight:800;color:{t['accent']}}}
.place{{text-align:center;font-size:28px;font-weight:600;margin-top:2mm}}
.text{{text-align:center;font-size:24px;margin:12mm 4mm 0;line-height:1.45}}
.note{{text-align:center;font-size:26px;font-weight:600;margin-top:8mm;color:{t['accent']}}}
.main{{flex:1;display:flex;flex-direction:column;justify-content:center;padding-bottom:8mm}}
.items{{margin:8mm 0 0;display:grid;gap:4mm}}
.item{{background:rgba(255,255,255,.1);border-left:2mm solid {t['accent']};border-radius:3mm;padding:3.5mm 5mm}}
.item b{{display:block;font-size:26px;color:{t['accent']}}}
.item .w{{font-size:20px;font-weight:600}}
.item .p{{font-size:16px;opacity:.9}}
.qr{{display:flex;gap:7mm;align-items:center;background:#fff;color:#111;border-radius:6mm;padding:5mm 7mm}}
.qr svg{{width:44mm;height:44mm;flex:none}}
.qr h3{{margin:0 0 2mm;font-size:24px}}
.qr p{{margin:0;font-size:14px;line-height:1.5}}
.qr .langs{{font-family:'Noto Sans','Noto Sans Arabic',sans-serif;font-size:13.5px;color:#444;margin-top:2mm}}
.credit{{font-size:9px;opacity:.75;text-align:right;margin:-2mm 0 1.5mm}}
{extra}</style></head><body><div class="main">
<div class="emoji">{e(n.get('emoji',''))}</div>
<div class="kicker">{e(p.get('kicker',''))}</div>
<h1>{e(p['title'])}</h1>
<div class="date">{e(p.get('date',''))}</div>
<div class="place">{e(p.get('place',''))}</div>
{'<div class="items">'+''.join(f'<div class="item"{photo_style(p, i, t)}><b>{e(a)}</b><div class="w">{e(b)}</div><div class="p">{e(c)}</div></div>' for i,(a,b,c) in enumerate(p.get('items',[])))+'</div>' if p.get('items') else ''}
{f'<div class="text">{e(p["text"])}</div>' if p.get('text') else ''}
<div class="note">{e(p.get('note',''))}</div></div>
{f'<div class="credit">{e(p["photo_credit"])}</div>' if p.get('photo_credit') else ''}
<div class="qr">{svg}<div><h3>📱 Scannen – in deiner Sprache</h3>
<p>Mehr Infos in 10 Sprachen – auch zum Anhören 🔊</p><p class="langs">{SCAN_LINE}</p></div></div>
</body></html>"""


def label_html(n, svg):
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><title>QR-Aufkleber</title>
{FONTS}<style>@page{{size:A6 landscape;margin:0}}*{{box-sizing:border-box}}
html,body{{margin:0;width:148mm;height:105mm}}
body{{font-family:'Noto Sans','Noto Sans Arabic',sans-serif;display:flex;align-items:center;gap:6mm;padding:8mm;border:2mm solid #14213d}}
svg{{width:62mm;height:62mm;flex:none}}h2{{margin:0 0 3mm;font-size:22px}}p{{margin:0;font-size:13px;color:#333;line-height:1.6}}
</style></head><body>{svg}<div><h2>🌐 {html.escape(n['langs']['de']['title'])}</h2>
<p><b>Scannen – in deiner Sprache · 🔊 auch zum Anhören</b></p><p>{SCAN_LINE}</p></div></body></html>"""


def main(src):
    n = json.loads(pathlib.Path(src).read_text())
    slug = n["slug"]
    out = ROOT / rel(slug)
    out.mkdir(parents=True, exist_ok=True)
    url = f"{BASE}/{rel(slug)}/"
    adir = out / "audio"
    adir.mkdir(exist_ok=True)
    scripts = {c: {"voice": VOICES[c], "text": audio_script(c, L)} for c, L in n["langs"].items() if c in VOICES}
    (adir / "scripts.json").write_text(json.dumps(scripts, ensure_ascii=False, indent=1))
    n["_audio"] = sorted(c for c in scripts if (adir / f"{c}.mp3").exists())
    (out / "index.html").write_text(page_html(n, url))
    svg = qr_img(url, out)
    if "poster" in n:
        (out / "poster.html").write_text(poster_html(n, svg))
    (out / "label.html").write_text(label_html(n, svg))
    build_index()
    print(url)


def build_index():
    items = []
    for f in sorted((ROOT / "notices").glob("*.json"), reverse=True):
        n = json.loads(f.read_text())
        items.append(f'<li><a href="{rel(n["slug"])}/">{n.get("emoji","")} {html.escape(n["langs"]["de"]["title"])}</a></li>')
    (ROOT / "index.html").write_text(f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex"><title>Aushänge</title>
<style>body{{font-family:system-ui,sans-serif;max-width:600px;margin:30px auto;padding:0 16px}}li{{margin:10px 0;font-size:20px}}</style></head>
<body><h1>Aushänge</h1><ul>{''.join(items)}</ul></body></html>""")


if __name__ == "__main__":
    main(sys.argv[1])
