#!/usr/bin/env python3
"""build_patro_page.py — DEV PREVIEW renderer for /patro/ (any date, live
computation via skyfield — needs patro_env).

The PRODUCTION renderer is `write_patro_page()` in pipeline/build_site.py:
stdlib-only, reads the committed horoscope/content/*.json (panchanga exported
by export_month.py, prose by generate_month.py). Keep visual changes in sync
— this script is only for iterating on a date CI doesn't show.

Run: ~/miniconda3/envs/patro_env/bin/python build_patro_page.py [YYYY-MM-DD]
"""
from __future__ import annotations

import datetime as dt
import html
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from rashifal import day_state

SITE = Path(__file__).resolve().parent.parent.parent / "site"
CONTENT = Path(__file__).resolve().parent.parent / "content"
DEVNUM = str.maketrans("0123456789", "०१२३४५६७८९")


def prose_for(date: dt.date) -> dict:
    """Reviewed-and-committed agent prose for the date (content/YYYY-MM.json),
    empty dict when absent — each राशि falls back to the template text."""
    path = CONTENT / f"{date.strftime('%Y-%m')}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text()).get("days", {}).get(date.isoformat(), {})


def dev(n) -> str:
    return str(n).translate(DEVNUM)


def esc(s) -> str:
    return html.escape(str(s))


CSS = """
main{max-width:46rem}
h1.pt{margin-bottom:0}
.pt-bs{font-size:1.5rem;font-weight:600;margin:.9rem 0 .1rem;line-height:1.4}
.pt-bs .yr{color:var(--mut);font-weight:400}
.pt-date{color:var(--mut);font-size:.92rem;margin:.15rem 0 1.5rem}
.pt-panch{display:grid;grid-template-columns:repeat(auto-fit,minmax(8.2rem,1fr));
 gap:.8rem 1rem;margin:1.2rem 0;padding:.95rem 1.1rem;border:1px solid var(--line);
 border-radius:10px}
.pt-panch div{font-size:.95rem}
.pt-panch b{font-weight:600}
.pt-panch .lbl{color:var(--mut);font-size:.74rem;display:block;margin-bottom:.1rem}
.pt-panch .end{display:block;color:var(--mut);font-size:.78rem}
.pt-ashtam{margin:.6rem 0 0;font-size:.88rem;color:var(--mut)}
.pt-ashtam b{color:var(--accent)}

/* राशि selector — jantri-style tile grid */
.zg{display:grid;grid-template-columns:repeat(6,1fr);gap:.45rem;margin:.9rem 0 1.1rem}
@media(max-width:40rem){.zg{grid-template-columns:repeat(4,1fr)}}
@media(max-width:26rem){.zg{grid-template-columns:repeat(3,1fr)}}
.zt{font-family:inherit;font-size:.98rem;color:var(--fg);background:none;
 border:1px solid var(--line);border-radius:9px;padding:.55rem .2rem .5rem;
 cursor:pointer;text-align:center;line-height:1.35;transition:border-color .15s,background .15s}
.zt .ltr{display:block;color:var(--mut);font-size:.68rem;letter-spacing:.04em;margin-top:.15rem}
.zt .dot{display:inline-block;width:.45rem;height:.45rem;border-radius:50%;
 margin-left:.3rem;vertical-align:.08rem;background:var(--line)}
.zt .dot.v-शुभ{background:#4e7345}
.zt .dot.v-मध्यम{background:var(--accent)}
.zt .dot.v-सावधान{background:#7a3b2e}
.zt:hover{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 7%,transparent)}
.zt:focus-visible{outline:2px solid color-mix(in srgb,var(--accent) 45%,transparent);outline-offset:2px}
.zt[aria-pressed=true]{border-color:var(--accent);
 background:color-mix(in srgb,var(--accent) 10%,transparent);font-weight:600}

.pt-detail{margin:0 0 1.4rem}
.pt-card{border:1px solid var(--line);border-left:4px solid var(--line);
 border-radius:10px;padding:1.05rem 1.2rem;margin:.9rem 0}
.js .pt-card{display:none}
.pt-card.v-शुभ{border-left-color:#4e7345}
.pt-card.v-मध्यम{border-left-color:var(--accent)}
.pt-card.v-सावधान{border-left-color:#7a3b2e}
.pt-card h3{margin:0;font-size:1.22rem}
.pt-card h3 .val{color:var(--mut);font-weight:400;font-size:.85rem}
.pt-card .nam{color:var(--mut);font-size:.78rem;margin:.15rem 0 .55rem}
.pt-card p{margin:.3rem 0;font-size:1.02rem;line-height:1.85}
.pt-card .rule{color:var(--mut);font-size:.78rem;margin-top:.6rem}
.pt-card .flag{color:#7a3b2e;font-weight:600;font-size:.85rem}
.pt-hint{display:none;color:var(--mut);font-size:.95rem;border:1px dashed var(--line);
 border-radius:10px;padding:1.1rem 1.2rem;margin:.9rem 0;text-align:center}
.js .pt-hint{display:block}
.js .pt-hint.off{display:none}
.pt-note{color:var(--mut);font-size:.85rem;border-top:1px solid var(--line);
 margin-top:2.2rem;padding-top:1rem;line-height:1.7}

/* valence colors as tokens, lifted brighter on dark backgrounds */
:root{--v-good:#4e7345;--v-bad:#7a3b2e}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){
 --v-good:#7fa873;--v-bad:#c98a70}}
:root[data-theme=dark]{--v-good:#7fa873;--v-bad:#c98a70}
.pt-card.v-शुभ{border-left-color:var(--v-good)}
.pt-card.v-सावधान{border-left-color:var(--v-bad)}
.zt .dot.v-शुभ{background:var(--v-good)}
.zt .dot.v-सावधान{background:var(--v-bad)}
.pt-card .flag{color:var(--v-bad)}
"""

JS = """
(function(){
  var grid=document.getElementById('zg');if(!grid)return;
  var tiles=[].slice.call(grid.querySelectorAll('.zt'));
  var cards={};[].forEach.call(document.querySelectorAll('.pt-card[data-rashi]'),
    function(c){cards[c.getAttribute('data-rashi')]=c;});
  var hint=document.getElementById('pthint');
  function show(r){
    tiles.forEach(function(t){
      t.setAttribute('aria-pressed',String(t.getAttribute('data-rashi')===r));});
    for(var k in cards)cards[k].style.display=(k===r)?'block':'none';
    if(hint)hint.className='pt-hint'+(r?' off':'');
  }
  grid.addEventListener('click',function(e){
    var t=e.target.closest('.zt');if(!t)return;
    var r=t.getAttribute('data-rashi');
    if(t.getAttribute('aria-pressed')==='true'){
      show(null);
      try{localStorage.removeItem('patroRashi');}catch(_){}
    }else{
      show(r);
      try{localStorage.setItem('patroRashi',r);}catch(_){}
    }
  });
  var saved=null;try{saved=localStorage.getItem('patroRashi');}catch(_){}
  show(saved&&cards[saved]?saved:null);
})();
"""


def anga_cell(label: str, anga, date: dt.date) -> str:
    when = anga.ends.strftime("%H:%M").translate(DEVNUM)
    if anga.ends.date() != date:
        when += " (भोलिपल्ट)"
    return (f'<div><span class="lbl">{label}</span><b>{esc(anga.name)}</b>'
            f'<span class="end">समाप्ति {when}</span></div>')


def build(date: dt.date) -> Path:
    s = day_state(date)
    p = s["panchanga"]
    prose = prose_for(date)
    cards, tiles = [], []
    for r in s["rashis"]:
        flag = ('<span class="flag">चन्द्राष्टम — सोच-विचार गरेर मात्र नयाँ काम '
                'थाल्नुहोस्।</span>' if r["chandrashtama"] else "")
        rule = r["rule"].replace(str(r["house"]), dev(r["house"]), 1)
        text = prose.get(r["rashi"], r["text"])
        cards.append(f"""<div class="pt-card v-{r['valence']}" data-rashi="{esc(r['rashi'])}">
<h3>{esc(r['rashi'])} <span class="val">{r['valence']}</span></h3>
<p class="nam">नामाक्षर: {esc(r['namakshar'])}</p>
{flag}
<p>{esc(text)}</p>
<p class="rule">{esc(rule)}</p>
</div>""")
        letters = " ".join(r["namakshar"].split()[:3]) + " …"
        tiles.append(f"""<button class="zt" type="button" data-rashi="{esc(r['rashi'])}" aria-pressed="false">
{esc(r['rashi'])}<span class="dot v-{r['valence']}"></span><span class="ltr">{esc(letters)}</span></button>""")

    body = f"""<h1 class="pt">पात्रो</h1>
<p class="pt-bs">{esc(p['bs_str'])} <span class="yr">{dev(p['bs'].split('-')[0])} वि.सं.</span> · {esc(p['vara'])}</p>
<p class="pt-date">{esc(p['ad'])} · सूर्योदय {p['sunrise'].translate(DEVNUM)} · सूर्यास्त {p['sunset'].translate(DEVNUM)} (काठमाडौं)</p>

<div class="pt-panch">
{anga_cell("तिथि", p['tithi'], date)}
{anga_cell("नक्षत्र", p['nakshatra'], date)}
{anga_cell("योग", p['yoga'], date)}
{anga_cell("करण", p['karana'], date)}
{anga_cell("चन्द्र राशि", p['moon_rashi'], date)}
</div>
<p class="pt-ashtam">आज <b>{esc(s['chandrashtama_rashi'])}</b> राशिका लागि चन्द्राष्टम छ ·
तिथि वर्ग: {esc(s['tithi_class'])}</p>

<h2>आजको राशिफल</h2>
<div class="zg" id="zg">
{''.join(tiles)}
</div>
<div class="pt-detail">
<p class="pt-hint" id="pthint">आफ्नो राशि छान्नुहोस्।</p>
{''.join(cards)}
</div>

<p class="pt-note">यो पृष्ठ काठमाडौंको सूर्योदयमा आधारित गणितीय पञ्चाङ्ग हो — तिथि, नक्षत्र,
योग, करण खगोलीय गणनाबाट निकालिएका छन् (स्रोत-नियम: फलदीपिका अध्याय २६; बृहत्संहिता अध्याय १०४)।
राशिफल खण्ड सांस्कृतिक/मनोरञ्जनका लागि मात्र हो — स्वास्थ्य, आर्थिक वा कानुनी निर्णयका लागि
प्रयोग नगर्नुहोस्।</p>"""

    page = f"""<!DOCTYPE html>
<html lang="ne">
<head>
<base href="/">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>(function(){{document.documentElement.classList.add('js');try{{var t=localStorage.getItem('theme');if(t==='dark'||t==='light')document.documentElement.setAttribute('data-theme',t);}}catch(e){{}}}})();</script>
<title>पात्रो — {esc(p['bs_str'])} · नेपाली अभिलेख</title>
<meta name="robots" content="noindex,follow">
<link rel="icon" type="image/png" href="favicon.png">
<link rel="stylesheet" href="style.css">
<style>{CSS}</style>
</head>
<body>
<header class="site">
  <a class="brand" href="./"><span>नेपाली अभिलेख</span></a>
  <nav><a href="./">गृह</a><a href="authors/">लेखकहरू</a><a href="type/">टाइप</a><a href="about.html">बारेमा</a></nav>
</header>
<main>
{body}
</main>
<footer class="site">
  <p>नेपाली अभिलेख — स्वतन्त्र, सार्वजनिक नेपाली साहित्य। सार्वजनिक डोमेन।</p>
</footer>
<script>{JS}</script>
</body>
</html>"""
    out = SITE / "patro"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page, encoding="utf-8")
    return out / "index.html"


if __name__ == "__main__":
    date = (dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1
            else dt.datetime.now(ZoneInfo("Asia/Kathmandu")).date())
    print(build(date))
