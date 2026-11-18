#!/usr/bin/env python3
"""Build the permanent "Aktuelle Termine" page: one QR code that always shows only upcoming dates.

Usage:  python3 tools/build_termine.py                 (reads data/termine.json)
        python3 tools/tts.py termine/audio/scripts.json termine/audio   (new clips only)
        python3 tools/build_termine.py                 (again, so the page knows the clips)
        node tools/render.js termine
Add a date: append an item to data/termine.json (id, kind event|day, ranges, t for all 10 languages;
events need "free": true and "place"). Past items hide themselves in the browser by their last end date,
so the QR code and the printed poster never change.
"""
import html, json, pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build import ROOT, BASE, LANGS, UI, VOICES, THEMES, FONTS, qr_img, poster_html, label_html, rel, build_index

SRC = ROOT / "data" / "termine.json"


def page(d, labels, audio, url):
    t = THEMES[d.get("theme", "info")]
    data = {"ui": d["ui"], "base": UI, "labels": labels, "audio": audio,
            "order": [[c, n, dr] for c, n, dr in LANGS],
            "items": [{k: it.get(k) for k in ("id", "kind", "free", "emoji", "ranges", "place", "t")} for it in d["items"]]}
    title = html.escape(d["ui"]["de"]["title"])
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><meta name="robots" content="noindex">
{FONTS}
<style>
:root{{--bg:{t['bg']};--bg2:{t['bg2']};--ac:{t['accent']};--ink:{t['ink']};--text:#1d2433;--muted:#5b6475}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:'Noto Sans','Noto Sans Arabic',system-ui,sans-serif;background:#f4f1ea;color:var(--text);line-height:1.5}}
[dir=rtl] body{{font-family:'Noto Sans Arabic','Noto Sans',system-ui,sans-serif}}
.hero{{background:linear-gradient(160deg,var(--bg),var(--bg2));color:var(--ink);padding:26px 20px 34px;text-align:center}}
.emoji{{font-size:58px;line-height:1}}
h1{{margin:10px 0 4px;font-size:29px;font-weight:800}}
.sub{{margin:0 auto;max-width:520px;opacity:.92}}
main{{max-width:640px;margin:-18px auto 40px;padding:0 16px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px;margin-top:14px}}
.lang{{display:block;width:100%;padding:16px 10px;border:0;border-radius:14px;background:#fff;color:var(--text);font:inherit;font-size:20px;font-weight:600;cursor:pointer;box-shadow:0 2px 10px rgba(0,0,0,.08)}}
.lang:hover,.lang:active{{background:var(--ac)}}
.top{{position:sticky;top:0;z-index:2;display:flex;justify-content:flex-end;padding:8px 12px;background:var(--bg2)}}
.top button{{border:1px solid rgba(255,255,255,.4);background:transparent;color:var(--ink);border-radius:999px;padding:6px 14px;font:inherit;cursor:pointer}}
.listen{{display:flex;align-items:center;justify-content:center;gap:12px;width:100%;padding:18px;margin:0 0 14px;border:0;border-radius:16px;background:var(--ac);color:#111;font:inherit;font-size:22px;font-weight:800;cursor:pointer;box-shadow:0 4px 18px rgba(0,0,0,.12)}}
.listen:focus-visible,.lang:focus-visible{{outline:4px solid #000;outline-offset:2px}}
.item{{background:#fff;border-radius:16px;padding:16px 18px;margin:0 0 12px;box-shadow:0 4px 18px rgba(0,0,0,.07);border-inline-start:6px solid #c9ced8}}
.item.event{{border-inline-start-color:var(--bg)}}
.item.playing{{outline:3px solid var(--ac)}}
.item h2{{margin:0;font-size:20px;display:flex;gap:10px;align-items:flex-start}}
.item .when{{font-weight:700;color:var(--bg);margin:6px 0 2px}}
.item .where{{color:var(--muted);font-size:15px;margin:0 0 6px}}
.item p{{margin:6px 0 0}}
.tags{{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}}
.tag{{font-size:13px;font-weight:700;border-radius:999px;padding:3px 10px;background:#eef1f6;color:#33405a}}
.tag.free{{background:#d8f3dc;color:#1b4332}}
.tag.now{{background:#ffe8a3;color:#5c4400}}
.none{{background:#fff;border-radius:16px;padding:20px;text-align:center}}
.hidden{{display:none}}
footer{{text-align:center;color:var(--muted);font-size:13px;padding-bottom:30px}}
</style></head>
<body>
<div id="picker">
  <div class="hero"><div class="emoji">🌐</div><h1>{title}</h1>
  <p class="sub">Sprache wählen · اختر اللغة · Choose your language</p></div>
  <main><div class="grid" id="langGrid" role="list"></div></main>
</div>
<div id="view" class="hidden">
  <div class="top"><button id="changeBtn" type="button">🌐 <span id="changeLbl"></span></button></div>
  <div class="hero"><div class="emoji">🗓️</div><h1 id="vTitle"></h1><p class="sub" id="vIntro"></p></div>
  <main>
    <button class="listen" id="listenBtn" type="button"><span aria-hidden="true">🔊</span><span id="listenLbl"></span></button>
    <audio id="player" preload="none"></audio>
    <div id="list"></div>
  </main>
  <footer>Marl · termine</footer>
</div>
<script>
const D={json.dumps(data, ensure_ascii=False)};
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
// Today's date in Marl (Europe/Berlin), as YYYY-MM-DD.
const TODAY=new Intl.DateTimeFormat('en-CA',{{timeZone:'Europe/Berlin'}}).format(new Date());
const lastEnd=it=>it.ranges.map(r=>r[1]).sort().pop();
const firstStart=it=>it.ranges.map(r=>r[0]).sort()[0];
const upcoming=()=>D.items.filter(it=>lastEnd(it)>=TODAY).sort((a,b)=>firstStart(a)<firstStart(b)?-1:1);
const isNow=it=>it.ranges.some(([a,b])=>a<=TODAY&&TODAY<=b);
let CUR='',QUEUE=[],SHOWN=[];
function setBtn(on){{const B=D.base[CUR]||D.base.en;$('listenLbl').textContent=on?B.stop:B.listen}}
function mark(id){{document.querySelectorAll('.item').forEach(e=>e.classList.toggle('playing',e.dataset.id===id))}}
function stopAudio(){{QUEUE=[];const a=$('player');a.pause();a.removeAttribute('src');if(window.speechSynthesis)speechSynthesis.cancel();mark('');setBtn(false)}}
function speakText(it){{const T=it.t[CUR];return [T[0],D.labels[it.id][CUR],it.place,T[1]].filter(Boolean).join('. ')}}
function next(){{
  const key=QUEUE.shift();if(key===undefined){{mark('');setBtn(false);return}}
  mark(key==='_intro'?'':key);
  const file=CUR+'-'+(key==='_intro'?'intro':key);
  if(D.audio.includes(file)){{const a=$('player');a.src='audio/'+file+'.mp3';a.play().catch(()=>next());return}}
  if(window.speechSynthesis){{const U=D.ui[CUR];const it=D.items.find(i=>i.id===key);
    const u=new SpeechSynthesisUtterance(key==='_intro'?U.title+'. '+U.intro:speakText(it));u.lang=CUR;u.onend=next;speechSynthesis.speak(u)}}
  else next();
}}
$('player').onended=next;
D.order.forEach(([c,name])=>{{const b=document.createElement('button');b.className='lang';b.textContent=name;b.lang=c;b.setAttribute('role','listitem');b.onclick=()=>{{location.hash=c}};$('langGrid').appendChild(b)}});
function show(c){{
  CUR=c;const U=D.ui[c],B=D.base[c],dir=(D.order.find(o=>o[0]===c)||[])[2]||'ltr';
  document.documentElement.lang=c;document.documentElement.dir=dir;document.title=U.title;
  $('vTitle').textContent=U.title;$('vIntro').textContent=U.intro;$('changeLbl').textContent=B.change;
  SHOWN=upcoming();
  $('list').innerHTML=SHOWN.length?SHOWN.map(it=>{{const T=it.t[c];const tags=[it.kind==='event'?U.event:U.day];
    const tg=tags.map(x=>`<span class="tag">${{esc(x)}}</span>`).join('')+(it.free?`<span class="tag free">${{esc(U.free)}}</span>`:'')+(isNow(it)?`<span class="tag now">${{esc(firstStart(it)===lastEnd(it)?U.today:U.now)}}</span>`:'');
    return `<article class="item ${{it.kind}}" data-id="${{esc(it.id)}}"><h2><span aria-hidden="true">${{esc(it.emoji)}}</span><span>${{esc(T[0])}}</span></h2>
    <div class="when">📅 ${{esc(D.labels[it.id][c])}}</div>${{it.place?`<div class="where">📍 ${{esc(it.place)}}</div>`:''}}<p>${{esc(T[1])}}</p><div class="tags">${{tg}}</div></article>`}}).join('')
    :`<div class="none">${{esc(U.none)}}</div>`;
  setBtn(false);$('picker').classList.add('hidden');$('view').classList.remove('hidden');scrollTo(0,0);$('listenBtn').focus();
}}
function route(){{stopAudio();const c=location.hash.slice(1);if(D.ui[c])show(c);else{{document.documentElement.dir='ltr';$('view').classList.add('hidden');$('picker').classList.remove('hidden')}}}}
$('changeBtn').onclick=()=>{{location.hash=''}};
$('listenBtn').onclick=()=>{{if(QUEUE.length||!$('player').paused||(window.speechSynthesis&&speechSynthesis.speaking)){{stopAudio();return}}
  QUEUE=['_intro',...SHOWN.map(i=>i.id)];setBtn(true);next()}};
addEventListener('hashchange',route);
// Stop the voice as soon as the reader leaves this view: any link, back button, tab switch or closing the page.
document.addEventListener('click',e=>{{if(e.target.closest('a'))stopAudio()}},true);
addEventListener('pagehide',stopAudio);
document.addEventListener('visibilitychange',()=>{{if(document.hidden)stopAudio()}});
route();
</script>
</body></html>
"""


def main():
    d = json.loads(SRC.read_text())
    out = ROOT / rel(d["slug"])
    adir = out / "audio"
    adir.mkdir(parents=True, exist_ok=True)
    for it in d["items"]:
        assert set(it["t"]) == set(d["ui"]), f"{it['id']}: missing languages"
        assert it["kind"] == "day" or it.get("free"), f"{it['id']}: only free events go on this page"
    labels = json.loads(subprocess.check_output(["node", str(ROOT / "tools" / "termine_labels.js"), str(SRC)]))
    scripts = {}
    for c in d["ui"]:
        U = d["ui"][c]
        scripts[f"{c}-intro"] = {"voice": VOICES[c], "text": f"{U['title']}. {U['intro']}"}
        for it in d["items"]:
            T = it["t"][c]
            parts = [T[0], labels[it["id"]][c], it.get("place"), T[1]]
            scripts[f"{c}-{it['id']}"] = {"voice": VOICES[c], "text": ". ".join(p for p in parts if p)}
    (adir / "scripts.json").write_text(json.dumps(scripts, ensure_ascii=False, indent=1))
    audio = sorted(k for k in scripts if (adir / f"{k}.mp3").exists())
    url = f"{BASE}/{rel(d['slug'])}/"
    (out / "index.html").write_text(page(d, labels, audio, url))
    svg = qr_img(url, out)
    n = {"theme": d.get("theme", "info"), "emoji": "🗓️", "langs": {"de": {"title": "Aktuelle Termine"}},
         "poster": {"kicker": "Immer aktuell · für alle", "title": "Aktuelle Termine",
                    "date": "Feste · Märkte · Feiertage",
                    "text": "Scanne den QR-Code: Du siehst immer die nächsten Termine in Marl und Umgebung – in deiner Sprache. Vergangene Termine verschwinden automatisch.",
                    "note": "Nur kostenlose Veranstaltungen 💚"}}
    (out / "poster.html").write_text(poster_html(n, svg))
    (out / "label.html").write_text(label_html(n, svg))
    build_index()
    print(url, f"{len(audio)}/{len(scripts)} audio clips")


if __name__ == "__main__":
    main()
