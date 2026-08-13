"""Committed-data पात्रो and राशिफल pages."""

import json

from ..config import SITE_NAME
from ..text import DEVNUM, devnum, esc

def write_patro_page(context, page, assets):
    """Render /patro/ (today NPT) + one archived page per committed date
    (/patro/YYYY-MM-DD/). /patro/ carries a client-side NPT-date check that
    redirects to the right dated page if the static build is stale — the
    date can never be wrong for a JS visitor even if the daily cron slips;
    the cron keeps the static baseline fresh for everyone else.
    Returns True if written."""
    from datetime import datetime, timedelta, timezone
    content = context.root / "horoscope" / "content"
    days = {}
    for f in sorted(content.glob("panchanga-*.json")):
        days.update(json.loads(f.read_text(encoding="utf-8"))["days"])
    if not days:
        print("patro: no committed panchanga data — page skipped")
        return False
    prose_all = {}
    for f in sorted(content.glob("20??-??.json")):
        prose_all.update(json.loads(f.read_text(encoding="utf-8"))["days"])
    npt_today = context.build_date.isoformat()
    today_iso = max((d for d in days if d <= npt_today), default=min(days))

    def render(iso, *, dated):
        p = days[iso]
        prose = prose_all.get(iso, {})
        depth = 2 if dated else 1

        def anga_cell(label, a):
            end_d, end_t = a["ends"].split("T")
            when = end_t.translate(DEVNUM) + ("" if end_d == iso else " (भोलिपल्ट)")
            return (f'<div><span class="lbl">{label}</span><b>{esc(a["name"])}</b>'
                    f'<span class="end">समाप्ति {when}</span></div>')

        cards, tiles = [], []
        for r in p["rashis"]:
            flag = ('<span class="flag">चन्द्राष्टम — सोच-विचार गरेर मात्र नयाँ काम '
                    'थाल्नुहोस्।</span>' if r["chandrashtama"] else "")
            rule = r["rule"].replace(str(r["house"]), devnum(r["house"]), 1)
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

        crumb = ('<nav class="crumb"><a href="../">← आजको पात्रो</a></nav>\n'
                 if dated else "")
        body = f"""{crumb}<h1 class="pt">पात्रो</h1>
<p class="pt-bs">{esc(p['bs_str'])} <span class="yr">{devnum(p['bs'].split('-')[0])} वि.सं.</span> · {esc(p['vara'])}</p>
<p class="pt-date">{esc(p['ad'])} · सूर्योदय {p['sunrise'].translate(DEVNUM)} · सूर्यास्त {p['sunset'].translate(DEVNUM)} (काठमाडौं)</p>

<div class="pt-panch">
{anga_cell("तिथि", p['tithi'])}
{anga_cell("नक्षत्र", p['nakshatra'])}
{anga_cell("योग", p['yoga'])}
{anga_cell("करण", p['karana'])}
{anga_cell("चन्द्र राशि", p['moon_rashi'])}
</div>
<p class="pt-ashtam">आज <b>{esc(p['chandrashtama_rashi'])}</b> राशिका लागि चन्द्राष्टम छ ·
तिथि वर्ग: {esc(p['tithi_class'])}</p>

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
प्रयोग नगर्नुहोस्।</p>
<script>{assets.patro_js}</script>"""

        # /patro/ only: client-side NPT date check — if this build is stale
        # (or the visitor crossed midnight), jump to the correct dated page
        # before paint. 20700000 ms = UTC+5:45.
        fresh = ("" if dated else
                 "<script>(function(){var D=" + json.dumps(sorted(days)) +
                 ";var t=new Date(Date.now()+20700000).toISOString().slice(0,10);"
                 f'if(t!=="{iso}"&&D.indexOf(t)>=0)location.replace("/patro/"+t+"/");'
                 "})()</script>\n")
        return page(f"पात्रो — {p['bs_str']} · " + SITE_NAME, body,
                    desc="आजको पञ्चाङ्ग र राशिफल — तिथि, नक्षत्र, योग, करण, चन्द्र राशि (काठमाडौं, वि.सं. मितिमा)",
                    css_depth=depth,
                    extra_head=(fresh +
                                "<script>document.documentElement.classList.add('js')</script>\n"
                                f"<style>{assets.patro_css}</style>\n"),
                    active="patro",
                    canon=f"patro/{iso}/" if dated else "patro/",
                    noindex=dated)

    out = context.site / "patro"
    out.mkdir(exist_ok=True)
    (out / "index.html").write_text(render(today_iso, dated=False),
                                    encoding="utf-8")
    for iso in days:
        d = out / iso
        d.mkdir(exist_ok=True)
        (d / "index.html").write_text(render(iso, dated=True), encoding="utf-8")
    return True
