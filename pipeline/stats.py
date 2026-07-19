#!/usr/bin/env python3
"""
stats.py — the "अभिलेख एक नजरमा" corpus-statistics page.

Pure build-time analysis + static HTML (inline SVG + CSS bars/cloud; no charting
library, no page-specific JS, not indexed by Pagefind), so it can never affect the
performance of any other page. `build_site.py` imports `build_stats_page()` and calls
it inside build(), so the page is REGENERATED ON EVERY BUILD — i.e. every push (CI
runs build_site.py) recomputes it from the committed texts and it can never go stale.

When a NEW AUTHOR/TEXT is added: nothing extra to wire (build_site already calls this),
but eyeball /stats/ — STATS_STOP (below) may need a few new function words for the new
author's register so the word cloud / signature words stay clean.
"""
import html, math, re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

from devanagari_slug import romanize as _rom

WORD = re.compile(r"[ऀ-ॣ०-ॿ]+")          # a Devanagari word (matras/viramas incl., danda excl.)
NUM = re.compile(r"^[०-९]+$")
_DEVNUM = str.maketrans("0123456789", "०१२३४५६७८९")
esc = html.escape

# Curated Nepali stopwords so the word cloud / signature words show evocative content
# (परी, सुन्दर, हृदय, फूल …) not grammar: pronouns, postpositions, copula/auxiliaries,
# conjunctions, common participles/gerunds, quantifiers + period/OCR variants + a few
# archaic inflections (गया/भया/गर्या …) that would otherwise swamp the older authors.
STATS_STOP = set("""
र छ छन् छ् छु छौ छस् छिन् छैन छन हो होइन हुन् हुन हुने हुन्छ हुन्छन् हुनु हुँदैन हुन्थ्यो हुँदो भो भयो भै भई भइ भए भएको भएकी भएका भएर हुँदा रह्यो रहे रहन्छ रहन्थ्यो होला भया भयौ हुन्थे
न ना का की को के मा ले लाई बाट सँग संग देखि सम्म माथि मुनि भित्र बाहिर अघि पछि नेर तिर पट्टि वरिपरि लगायत पर
पनी पनि नै त ता तर वा कि अनि अथवा तथा एवं किन्तु परन्तु अझ बरु कारण किनभने
यो त्यो यी ती ति यस त्यस यसको त्यसको यस्मा त्यस्मा यिनी तिनी यिनको तिनको यिनै तिनै यही जो जे जुन जब तब जहाँ तहाँ तहिं यहाँ त्यहाँ कहाँ जति तति कति किन कुन कसरी जसरी जसै तसै
म मेरो मेरा मलाई मैले ममा हामी हाम्रो हामीले हामीलाई तिमी तिम्रो तिमीलाई तँ तेरो उ ऊ उनी उनको उनले उसको उसले उसैले उस आफू आफ्नो आफैं आफैँ कोही कसैले केही कुनै हरेक प्रत्येक
भनी भन्ने भन्छ भन्छन् भने भनेर भन्दा भन्नु भन्थे गर्ने गरी गरेको गरे गर्छ गर्छन् गर्न गर्दछ गर्दा गर्यो गर्या गया गई गयो गइन् गर्थे लागेको लाग्छ लाग्यो लागे दिई दिने दिन्छ लिई लिने आउँछ आयो जान्छ
सब सब् सबै सारा सम्पूर्ण भरी अरू अरु कुरा एक एउटा दुई तीन धेरै थोरै अति निकै सधैं फेरि मात्र मात्रै खाली अनेक खुप् एक्
जस्तो जस्तै कस्तो कस्तै कन बनी बनेको झैं झैँ सरि बिना अनुसार बारे लागि निम्ति हुकुम्
हे ओ अरे क्या नि है ल नत्र अब उहिले रे यस्तो त्यस्तो थिए थियो थिएन थिइन् भइन् लौ वाह
थिया दिया लिया गया भया रह्या छन् छ्या दिन्या भन्या गर्न्या हुन्या बहुत् महाँ सुनि बात् हुम् मकन कन् यै इ ता् नब
""".split())

# treemap / author palette — warm muted tones that read on both light & dark themes
PALETTE = ["#b07a1e", "#9c5a3c", "#5f7a52", "#5a6b8a", "#8a5a6f", "#6b8a86", "#a08a3c"]


def _dev(n):                       # plain Devanagari numerals (years, small counts)
    return str(n).translate(_DEVNUM)

def _grp(n):                       # Indian digit grouping: 262936 -> 2,62,936
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail, parts = s[:-3], s[-3:], []
    while len(head) > 2:
        parts.insert(0, head[-2:]); head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts) + "," + tail

def _dnum(n):                      # grouped Devanagari numeral (big counts)
    return _grp(n).translate(_DEVNUM)

def _bars(rows, maxv):
    """rows: list of (label_html, value, href|None) -> CSS bar rows."""
    out = []
    for lab, v, href in rows:
        pct = (v / maxv * 100) if maxv else 0
        lh = f'<a href="{href}">{lab}</a>' if href else lab
        out.append(f'<div class="srow"><span class="slab">{lh}</span>'
                   f'<span class="sbar"><i style="width:{pct:.1f}%"></i></span>'
                   f'<span class="sval">{_dnum(v)}</span></div>')
    return "".join(out)


# ── chart 1: work-length histogram (the "shape" of the corpus) ──
def _histogram_svg(values):
    buckets = [(0, 50, "<५०"), (50, 100, "१००"), (100, 200, "२००"), (200, 500, "५००"),
               (500, 1000, "१क"), (1000, 5000, "५क"), (5000, 10 ** 9, "५क+")]
    counts = [sum(1 for v in values if lo <= v < hi) for lo, hi, _ in buckets]
    mx = max(counts) or 1
    W, H, pad = 540, 165, 26
    n = len(buckets); bw = (W - 2 * pad) / n
    s = []
    for i, (c, (_, _, lab)) in enumerate(zip(counts, buckets)):
        bh = (H - 2 * pad) * c / mx
        x = pad + i * bw; y = H - pad - bh
        s.append(f'<rect x="{x + 4:.1f}" y="{y:.1f}" width="{bw - 8:.1f}" height="{bh:.1f}" rx="2" class="hb"/>')
        s.append(f'<text x="{x + bw / 2:.1f}" y="{y - 4:.1f}" class="hn">{_dev(c)}</text>')
        s.append(f'<text x="{x + bw / 2:.1f}" y="{H - pad + 13:.1f}" class="hx">{lab}</text>')
    s.append(f'<text x="{W / 2:.1f}" y="{H - 4:.1f}" class="hax">शब्द सङ्ख्या →</text>')
    return f'<svg viewBox="0 0 {W} {H}" class="chart hist" role="img" aria-label="कृति-लम्बाइको वितरण">{"".join(s)}</svg>'


# ── chart 2: Zipf rank–frequency curve (log–log) ──
def _zipf_svg(freqs):
    pts = freqs[:1500]
    W, H, pad = 540, 175, 30
    rmax = math.log10(len(pts)); fmax = math.log10(pts[0])
    lx = lambda r: pad + (math.log10(r) / rmax) * (W - 2 * pad)
    ly = lambda f: pad + (1 - math.log10(f) / fmax) * (H - 2 * pad)
    poly = " ".join(f"{lx(i + 1):.1f},{ly(f):.1f}" for i, f in enumerate(pts) if f > 0)
    g = [f'<polyline points="{poly}" class="zl"/>']
    for r in (1, 10, 100, 1000):
        if r <= len(pts):
            g.append(f'<text x="{lx(r):.1f}" y="{H - pad + 13:.1f}" class="hx">{_dev(r)}</text>')
    g.append(f'<text x="{W / 2:.1f}" y="{H - 3:.1f}" class="hax">शब्दको क्रम (rank) →</text>')
    return f'<svg viewBox="0 0 {W} {H}" class="chart zipf" role="img" aria-label="Zipf वितरण">{"".join(g)}</svg>'


# ── chart 3: squarified treemap — "map of the archive" ──
def _squarify(areas, x, y, dx, dy):
    res = [None] * len(areas)
    order = sorted(range(len(areas)), key=lambda i: -areas[i])
    def worst(ra, side):
        s = sum(ra); return max((side * side * max(ra)) / (s * s), (s * s) / (side * side * min(ra)))
    cx, cy, cdx, cdy, pos = x, y, dx, dy, 0
    while pos < len(order):
        side = min(cdx, cdy) or 1
        row = [order[pos]]; j = pos + 1
        while j < len(order):
            ra = [areas[i] for i in row]
            if worst(ra, side) >= worst(ra + [areas[order[j]]], side):
                row.append(order[j]); j += 1
            else:
                break
        ra = [areas[i] for i in row]; cover = sum(ra)
        if cdx >= cdy:
            w = cover / cdy if cdy else 0; yy = cy
            for i in row:
                h = areas[i] / w if w else 0; res[i] = (cx, yy, w, h); yy += h
            cx += w; cdx -= w
        else:
            h = cover / cdx if cdx else 0; xx = cx
            for i in row:
                wd = areas[i] / h if h else 0; res[i] = (xx, cy, wd, h); xx += wd
            cy += h; cdy -= h
        pos = j
    return res

def _treemap_svg(tiles, color_of):
    """tiles: list of (value, label, key). color_of: key -> hex."""
    W, H = 540, 320
    vals = [max(t[0], 1) for t in tiles]
    tot = sum(vals); areas = [v / tot * W * H for v in vals]
    rects = _squarify(areas, 0, 0, W, H)
    s = []
    for (x, y, w, h), (v, lab, key) in zip(rects, tiles):
        s.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w - 1.2, 0):.1f}" height="{max(h - 1.2, 0):.1f}" '
                 f'fill="{color_of(key)}" class="tm"><title>{esc(lab)} · {_dnum(v)} शब्द</title></rect>')
        if w > 46 and h > 16:                       # label only roomy tiles
            t = lab if len(lab) <= int(w // 9) else lab[:max(int(w // 9) - 1, 1)] + "…"
            s.append(f'<text x="{x + 4:.1f}" y="{y + 13:.1f}" class="tmt">{esc(t)}</text>')
    return f'<svg viewBox="0 0 {W} {H}" class="chart tree" role="img" aria-label="अभिलेखको नक्सा">{"".join(s)}</svg>'


def build_stats_page(recs, collections, *, page, GENRE, PROSE_GENRES, site, site_name):
    total_words = total_lines = prose_w = verse_w = 0
    uniq = set(); aw = defaultdict(int); ak = defaultdict(int)
    gc = Counter(); freq = Counter(); fullfreq = Counter(); wlens = []; years = []
    tiles = []; line_counts = Counter(); author_freq = defaultdict(Counter); auth_order = []
    for w, meta, text in recs:
        toks = [t for t in WORD.findall(text) if not NUM.match(t)]
        nw = len(toks); total_words += nw; uniq.update(toks); wlens.append(nw)
        fullfreq.update(toks)
        total_lines += sum(1 for l in text.splitlines() if l.strip())
        nm = meta["author"]["name"]
        if nm not in auth_order:
            auth_order.append(nm)
        aw[nm] += nw; ak[nm] += 1
        g = meta["genre"][0] if meta.get("genre") else ""
        if g:
            gc[g] += 1
        if g in PROSE_GENRES:
            prose_w += nw
        else:
            verse_w += nw
        tiles.append((nw, meta["title"], nm))
        for t in toks:
            if len(t) > 1 and t not in STATS_STOP:
                freq[t] += 1; author_freq[nm][t] += 1
        for l in text.splitlines():                # most-echoed lines
            ls = l.strip()
            if len(ls) >= 8 and len(WORD.findall(ls)) >= 2 and not NUM.match(ls):
                line_counts[ls] += 1
        y = (meta.get("first_published") or {}).get("bs")
        if y:
            years.append(y)

    # ----- word cloud (variant-folded by romanization) -----
    fold = defaultdict(Counter)
    for word, c in freq.items():
        fold[_rom(word)][word] = c
    topw = []
    for cc in fold.values():
        lead = cc.most_common(1)[0][0]
        if lead not in STATS_STOP:
            topw.append((sum(cc.values()), lead))
    topw.sort(reverse=True); topw = topw[:40]

    # ----- signature words per author (weighted log-ratio vs the rest) -----
    totf = Counter()
    for c in author_freq.values():
        totf += c
    Nall = sum(totf.values()); sig = {}
    for nm in auth_order:
        c = author_freq[nm]; Na = sum(c.values()); scored = []
        for word, ca in c.items():
            if ca < 4:
                continue
            pr = (totf[word] - ca + 0.5) / (Nall - Na + 0.5)
            scored.append((math.log((ca / Na) / pr) * math.sqrt(ca), word, ca))
        scored.sort(reverse=True); sig[nm] = scored[:10]

    # ----- assemble -----
    cmap = {nm: PALETTE[i % len(PALETTE)] for i, nm in enumerate(auth_order)}
    hero = [("कृति", len(recs)), ("शब्द", total_words), ("अद्वितीय शब्द", len(uniq)),
            ("हरफ", total_lines), ("लेखक", len(aw))]
    hero_html = "".join(f'<div class="snum"><b>{_dnum(v)}</b><span>{lab}</span></div>' for lab, v in hero)
    treemap_html = _treemap_svg(tiles, lambda k: cmap.get(k, PALETTE[0]))
    tlegend = "".join(f'<span class="tk"><i style="background:{cmap[nm]}"></i>{esc(nm)}</span>' for nm in auth_order)
    authors_html = _bars([(f'{esc(nm)} <small>{_dnum(ak[nm])} कृति</small>', aw[nm], None)
                          for nm in sorted(aw, key=lambda x: -aw[x])], max(aw.values()))
    genres_html = _bars([(esc(GENRE.get(g, (g, ""))[0]), c, None) for g, c in gc.most_common()], max(gc.values()))
    hist_html = _histogram_svg(wlens)
    cmx, cmn = (topw[0][0], topw[-1][0]) if topw else (1, 1)
    cloud = " ".join(
        f'<a class="cw" style="font-size:{0.95 + ((n - cmn) / (cmx - cmn) if cmx > cmn else 1) * 1.85:.2f}rem" '
        f'href="../?q={quote(word)}" title="{_dnum(n)} पटक">{esc(word)}</a>' for n, word in topw)
    sig_html = "".join(
        f'<div class="sigcol"><h3 style="border-color:{cmap[nm]}">{esc(nm)}</h3><p>'
        + " ".join(f'<a href="../?q={quote(word)}" title="{_dnum(ca)} पटक">{esc(word)}</a>' for _, word, ca in sig[nm])
        + "</p></div>" for nm in auth_order if sig[nm])
    refrains = [(s, c) for s, c in line_counts.most_common(40) if c >= 3][:8]
    refr_html = "".join(f'<li><span class="rc">{_dev(c)}×</span> {esc(s)}</li>' for s, c in refrains)
    zipf_html = _zipf_svg(sorted(fullfreq.values(), reverse=True))

    wl = sorted(wlens)
    hapax = sum(1 for c in fullfreq.values() if c == 1)
    rt_hr = round(total_words / 130 / 60)
    vpct = round(verse_w / total_words * 100) if total_words else 0
    trivia = [f"सबै कृति एकपटक सुनाउन झन्डै <b>{_dnum(rt_hr)} घण्टा</b> लाग्छ (~१३० शब्द/मिनेटका दरले)।",
              f"शब्दको हिसाबले करिब <b>{_dnum(vpct)}%</b> पद्य र <b>{_dnum(100 - vpct)}%</b> गद्य।",
              f"भण्डारका <b>{_dnum(hapax)}</b> शब्द ({_dev(round(hapax / max(len(uniq), 1) * 100))}%) पूरै अभिलेखमा जम्मा एकपटक मात्र आउँछन्।",
              f"कृतिको औसत लम्बाइ <b>{_dnum(wl[len(wl) // 2])}</b> शब्द (मध्यिका)।"]
    if years:
        trivia.append(f"मिति थाहा भएका {_dnum(len(years))} कृतिको प्रकाशन वि.सं. "
                      f"<b>{_dev(min(years))}–{_dev(max(years))}</b> मा फैलिएको।")

    body = f"""<nav class="crumb"><a href="../">← {esc(site_name)}</a></nav>
<article class="stats">
<h1>अभिलेख एक नजरमा</h1>
<p class="lead">तथ्याङ्क, ग्राफ र रोचक तथ्यहरू।</p>
<div class="snums">{hero_html}</div>

<h2>अभिलेखको नक्सा <span class="sh">हरेक टुक्रो = एक कृति · आकार = शब्द सङ्ख्या</span></h2>
{treemap_html}
<p class="tlegend">{tlegend}</p>

<h2>लेखकहरू <span class="sh">शब्दको हिसाबले</span></h2><div class="schart">{authors_html}</div>
<h2>विधा <span class="sh">कृति सङ्ख्या</span></h2><div class="schart">{genres_html}</div>

<h2>कृतिको लम्बाइ <span class="sh">कति कृति, कति लामा</span></h2>
{hist_html}

<h2>अभिलेखको शब्द-संसार</h2>
<p class="meta">सबैभन्दा धेरै दोहोरिने शब्द (व्याकरणका शब्द हटाएर, रूपभेद जोडेर)। कुनैमा क्लिक गरेर खोज्न सकिन्छ।</p>
<div class="cloud">{cloud}</div>

<h2>हरेक लेखकका विशिष्ट शब्द <span class="sh">जुन शब्द जसले बढी प्रयोग गरे</span></h2>
<div class="sigwrap">{sig_html}</div>

<h2>सबैभन्दा धेरै दोहोरिने हरफ</h2>
<ul class="refrains">{refr_html}</ul>

<h2>शब्दको वितरण <span class="sh">Zipf — थोरै शब्द धेरै पटक, धेरै शब्द थोरै पटक</span></h2>
{zipf_html}

<h2>रोचक तथ्य</h2><ul class="trivia">{"".join(f"<li>{t}</li>" for t in trivia)}</ul>
<p class="meta statnote">यी आँकडा OCR/स्क्यान गरिएका पाठमा आधारित र प्रुफरिड हुन बाँकी भएकाले अनुमानित हुन्; हरेक build मा स्वतः गणना हुन्छन्।</p>
</article>"""
    (site / "stats").mkdir(parents=True, exist_ok=True)
    (site / "stats" / "index.html").write_text(
        page("अभिलेख एक नजरमा — " + site_name, body,
             desc="नेपाली अभिलेखका तथ्याङ्क, ग्राफ र रोचक तथ्यहरू।", css_depth=1, active="", canon="stats/"),
        encoding="utf-8")
