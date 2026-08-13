#!/usr/bin/env python3
"""
build_site.py — generate the static reader website from the archive.

Design goals: content-first, FAST. Every work is pre-rendered to a real HTML
file (text inline, zero JS to read). Browse lists are server-rendered (work with
JS off). Search is progressive enhancement: a compact JSON index + tiny vanilla
JS, loaded only when you use the search box. No web fonts (system Devanagari
stack). One small cached stylesheet.

The site is the *reading* layer; bulk file downloads (PDF/EPUB/TXT/source) point
at ARCHIVE_BASE_URL — set that to your S3/R2 public base when ready (no content
rebuild needed; only the links change, so just re-run this script).

Usage:
    python3 pipeline/build_site.py            # -> site/
    python3 pipeline/build_site.py --archive-base https://archive.example.org
"""
import argparse, hashlib, html, json, re, shutil, sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from devanagari_slug import slugify as cslugify, romanize as cromanize
import stats   # the build-time /stats/ page (pipeline/stats.py)

# the search bridge shares the /type/ tool's normalization contract (search.js
# xnorm() is its JS twin — keep in sync). NOTE: this import patches
# devanagari_slug.SIGN['ँ']->'n', so romanize() everywhere in this build (incl.
# stats roman labels) writes chandrabindu as the 'n' people actually type —
# required for those labels' ?q= deep-links to hit the normalized shard keys.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent
                       / "roman_nepali_transliteration" / "pipeline"))
from translit_keys import word_keys as translit_word_keys
from translit_keys import key_romanize as _tk_rom, normalize as _tk_norm


def normalize_key(w):
    """A word's primary shard key: normalize(key_romanize(w))."""
    return _tk_norm(_tk_rom(w))

ROOT = Path(__file__).resolve().parent.parent
ARCHIVES = ROOT / "archives"
SITE = ROOT / "site"
SITE_NAME = "नेपाली अभिलेख"          # "Nepali Archives"
SITE_TAGLINE = "स्वतन्त्र, सार्वजनिक नेपाली साहित्य"  # free, public-domain Nepali literature
SITE_TAGLINE_EN = "A public-domain archive of Nepali literature"
SITE_URL = "https://www.nepaliarchives.org/"
REPO_URL = "https://github.com/chinge55/nepali_archives"

# Display names for genre tags (Devanagari · English), and a browse order.
GENRE = {
    "mahakavya": ("महाकाव्य", "epic"), "khandakavya": ("खण्डकाव्य", "narrative poem"),
    "upanyas": ("उपन्यास", "novel"), "katha": ("कथा", "story"),
    "nibandha": ("निबन्ध", "essay"),
    "kavita": ("कविता", "poems"), "balkavita": ("बालकविता", "children's poems"),
    "git": ("गीत", "song"), "gazal": ("गजल", "ghazal"),
}
ORDER = ["mahakavya", "khandakavya", "upanyas", "katha", "nibandha", "kavita",
         "balkavita", "git", "gazal"]

# Author display registry (name in Devanagari, romanized, life dates). Authors not
# listed fall back to the name/name_roman recorded in their works' metadata.
AUTHORS = {
    "devkota": ("लक्ष्मीप्रसाद देवकोटा", "Laxmi Prasad Devkota", "1909–1959"),
    "bhanubhakta_acharya": ("भानुभक्त आचार्य", "Bhanubhakta Acharya", "1814–1868"),
    "lekhnath_paudyal": ("लेखनाथ पौड्याल", "Lekhnath Paudyal", "1885–1966"),
    "bhimnidhi_tiwari": ("भीमनिधि तिवारी", "Bhimnidhi Tiwari", "1911–1973"),
    "motiram_bhatta": ("मोतीराम भट्ट", "Motiram Bhatta", "1866–1896"),
}


def esc(s): return html.escape(s or "")


def _is_heading(b: str) -> bool:
    """A standalone, word-like line that introduces a section (समर्पण, प्रथम सर्ग) —
    NOT a stanza number (१, (१), क.), a verse line (ends in danda/!/?/—), or a
    quoted line. Quoted dialogue is never a heading: a short line of speech is
    exactly the shape this heuristic would otherwise mistake for a section title."""
    if "\n" in b or len(b) > 40:
        return False
    s = b.strip()
    # A lone parenthesized single Devanagari letter — (क), (ख), (ङ) … — is a canto/
    # section marker (NOT a stanza number like (१)); render it as a heading.
    m = re.fullmatch(r"\(([ऀ-ॿ])\)", s)
    if m and not m.group(1).isdigit():
        return True
    if not s or s[0] in "0123456789०१२३४५६७८९([‘’“”\"":
        return False
    if s[-1] in "।॥!?,.;:—–…‘’“”":
        return False
    letters = len(re.findall(r"[ऀ-ॿ]", s))
    return letters >= 3 and (" " in s or letters >= 4)


PROSE_GENRES = {"upanyas", "katha", "nibandha"}

# A source colophon: the small attribution line printed at a poem's end giving
# its original publication, e.g. "वि. सं. १९६९ ... लालित्यबाट". Rendered as a
# muted attribution line, never as a verse stanza or a section heading.
_COLOPHON_RE = re.compile(r"^\s*(वि|बि)\.?\s*सं\.?\s*[०-९]")


# Spaced end-punctuation (e.g. "झोलुङ्गो ।") makes the space a legal break point, so a
# lone danda can wrap onto its own line on narrow phones. Glue it with a no-break space.
_NBSP_PUNCT = re.compile(r" ([।॥!?])")


def _nb(s: str) -> str:
    return _NBSP_PUNCT.sub(" \\1", s)


def work_html(text: str, verse: bool) -> str:
    """Blank-line blocks become stanzas/paragraphs; word-like standalone lines
    become section headings. For verse, each line is its own block so wrapped
    long lines hang-indent (and never read as a new verse line). Prose flows.
    A trailing source colophon is set apart as a muted attribution line."""
    blocks = [b.strip("\n") for b in text.replace("\r\n", "\n").split("\n\n")]
    out = []
    for b in blocks:
        if not b.strip():
            continue
        if _COLOPHON_RE.match(b):
            line = re.sub(r"\s+", " ", b.replace("\n", " ")).strip()
            out.append(f'<p class="colophon">{esc(line)}</p>')
        elif _is_heading(b):
            out.append(f'<h2 class="sec">{esc(b)}</h2>')
        elif verse:
            ls = b.split("\n")
            # a stanza/श्लोक number — its own block OR the first line of its
            # stanza (both occur in print) — hangs in the margin (.snum)
            if len(ls) > 1 and re.fullmatch(r"[०-९0-9]{1,4}", ls[0].strip()):
                out.append(f'<div class="stanza snum"><span class="ln">{esc(ls[0].strip())}</span></div>')
                ls = ls[1:]
            lines = "".join(f'<span class="ln">{_nb(esc(l))}</span>' for l in ls)
            cls = "stanza snum" if re.fullmatch(r"[०-९0-9]{1,4}", b.strip()) else "stanza"
            out.append(f'<div class="{cls}">{lines}</div>')
        else:
            para = _nb(esc(b).replace("\n", " "))
            out.append(f'<p class="stanza">{para}</p>')
    return "\n".join(out)


# --- pagination for very long works: split into per-section pages + a contents page ---
CHAPTER_RE = re.compile(r'काण्ड|सर्ग|सगैँ|अध्याय|विश्राम|विश्वाम|परिच्छेद|अङ्क|उल्लास|खण्ड|सोपान|परिशिष्ट|विचार')
_DEVNUM = str.maketrans('0123456789', '०१२३४५६७८९')
def _dev(n): return str(n).translate(_DEVNUM)

def paginate_work(text, balance=False):
    """For a long work, return [(label, content_text), …] — one entry per section — or
    None to keep a single page. Splits on 'chapter' headings (काण्ड/सर्ग/अध्याय/विश्राम/…),
    including a heading with a title on the next line (e.g. 'अध्याय २\\nबालचिन्ता'); the
    heading becomes the label (shown as the page h1, dropped from its body). Only when
    `balance` is set (a huge work with no chapter headings) does it size-balance into भाग."""
    blocks = [b.strip("\n") for b in text.replace("\r\n", "\n").split("\n\n") if b.strip()]
    def is_chap(b):
        first = b.split("\n", 1)[0].strip()
        return len(b.splitlines()) <= 2 and _is_heading(first) and CHAPTER_RE.search(first)
    idx = [i for i, b in enumerate(blocks) if is_chap(b)]
    if len(idx) >= 2 and len(text) > 8000:
        front = blocks[:idx[0]]
        bounds = idx + [len(blocks)]
        pages = []
        # Substantial heading-led front matter (e.g. an author's own बक्तव्य/भूमिका) gets
        # its own contents entry; the heading becomes its label (dropped from the body, like
        # a chapter heading); a short stray byline/invocation rides on the first section.
        if front and len("\n\n".join(front)) > 400 and _is_heading(front[0].split("\n", 1)[0].strip()):
            pages.append((front[0].split("\n", 1)[0].strip(), "\n\n".join(front[1:])))
            front = []
        for j, s in enumerate(idx):
            body_blocks = blocks[s + 1:bounds[j + 1]]
            if j == 0 and front:
                body_blocks = front + body_blocks
            pages.append((blocks[s].replace("\n", " — "), "\n\n".join(body_blocks)))
        return pages
    if balance:
        TARGET, pages, cur, sz, n = 20000, [], [], 0, 1
        for b in blocks:
            cur.append(b); sz += len(b)
            if sz >= TARGET:
                pages.append((f"भाग {_dev(n)}", "\n\n".join(cur))); cur, sz, n = [], 0, n + 1
        if cur:
            pages.append((f"भाग {_dev(n)}", "\n\n".join(cur)))
        return pages if len(pages) >= 2 else None
    return None


def page(title, body, *, desc="", css_depth=0, extra_head="", active="", canon="", noindex=False):
    up = "../" * css_depth
    canon_url = SITE_URL + canon
    # every description carries the English tagline too, for non-Nepali SERP snippets
    desc = f"{desc} · {SITE_TAGLINE_EN}" if desc else f"{SITE_TAGLINE} — {SITE_TAGLINE_EN}"
    robots = '<meta name="robots" content="noindex,follow">\n' if noindex else ""
    og = (f'<link rel="canonical" href="{esc(canon_url)}">\n'
          f'<meta property="og:type" content="{"article" if active=="works" and canon.startswith("authors/") and canon.rstrip("/").count("/") >= 2 else "website"}">\n'
          f'<meta property="og:title" content="{esc(title)}">\n'
          f'<meta property="og:description" content="{esc(desc)}">\n'
          f'<meta property="og:url" content="{esc(canon_url)}">\n'
          f'<meta property="og:site_name" content="{SITE_NAME}">\n')
    nav = "".join(
        f'<a href="{(up + href) or "./"}"{" class=on" if active==key else ""}>{label}</a>'
        for key, href, label in [
            ("home", "", "गृह"),
            ("works", "authors/", "लेखकहरू"),
            ("type", "type/", "टाइप"),
            ("patro", "patro/", "पात्रो"),
            ("about", "about.html", "बारेमा"),
        ])
    return f"""<!DOCTYPE html>
<html lang="ne">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>(function(){{try{{var t=localStorage.getItem('theme');if(t==='dark'||t==='light')document.documentElement.setAttribute('data-theme',t);}}catch(e){{}}}})();</script>
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{robots}<link rel="icon" type="image/png" href="{up}favicon.png">
<link rel="apple-touch-icon" href="{up}apple-touch-icon.png">
<link rel="preload" as="font" type="font/woff2" href="{up}fonts/nsd-devanagari-400.woff2" crossorigin>
<link rel="stylesheet" href="{up}style.css?v={CSS_VER}">
{og}{extra_head}<script src="{up}ui.js?v={UI_VER}" defer></script>
</head>
<body>
<div id="prog" class="prog"></div>
<header class="site">
  <a class="brand" href="{up or './'}"><span>{SITE_NAME}</span></a>
  <nav>{nav}<button id="themed" class="themebtn" type="button" aria-label="उज्यालो/अँध्यारो"></button></nav>
</header>
<main>
{body}
</main>
<footer class="site">
  <p>{SITE_NAME} — {SITE_TAGLINE}. सार्वजनिक डोमेन।</p>
  <p class="foot-en">{SITE_TAGLINE_EN}</p>
</footer>
</body>
</html>
"""


def write_ocr_page():
    """Write the provider-neutral account of the scanned-book DAG in Nepali."""
    out = SITE / "ocr"
    out.mkdir(parents=True, exist_ok=True)
    arrow = '<div class="flow-arrow" aria-hidden="true">↓</div>'
    body = f"""<nav class="crumb"><a href="../about.html">← बारेमा</a></nav>
<article class="ocr-page">
<header class="ocr-hero">
  <p class="ocr-kicker">हाम्रो OCR विधि</p>
  <h1>स्क्यानदेखि पाठसम्म</h1>
  <p class="ocr-dek">एउटा पुरानो पुस्तक, धेरै सावधान पढाइ—र एउटै नियम: मूलप्रति इमानदार।</p>
</header>
<p>स्क्यानमा भेटिएको नेपाली पुस्तकलाई पढ्न मिल्ने डिजिटल पाठमा उतार्नु केवल OCR चलाउनु होइन।
पहिले मेसिनले सम्भावित अक्षर देखाउँछ; त्यसपछि अलग-अलग एजेन्टले पृष्ठ हेरेर पुस्तकको बनोट,
पानाको क्रम, मूल पाठ र पादटिप्पणी मिलाउँछन्।</p>
<aside class="ocr-principle">
  <span aria-hidden="true">“</span>
  <p><strong>हाम्रा लागि छापिएको पृष्ठ नै प्रमाण हो।</strong> OCR ले बाटो देखाउँछ, एजेन्टले पढ्छन्;
  तर नदेखिएको कुरा अनुमान गरेर भरिँदैन।</p>
</aside>
<p>त्यसैले पुरानो हिज्जे, विरामचिह्न, अनौठो शब्द र मूलमै भएका खाली ठाउँ जस्ताको तस्तै रहन्छन्।
कुनै अंशमा भरोसा गर्न नसकिए काम अघि बढ्दैन—त्यहीँ रोकिन्छ।</p>

<h2>काम बाँडिएको छ—जिम्मेवारी पनि</h2>
<p class="section-intro">कुनै एउटै एजेन्टले पुस्तक उठाएर सीधै अभिलेखमा राख्दैन। हरेक पक्षले
आफ्नो सीमाभित्रको काम गर्छ, र अर्को पक्षले त्यसलाई जाँच्छ।</p>
<div class="ocr-roles">
  <div class="role-agent"><span class="role-mark" aria-hidden="true">प</span><h3>पठन एजेन्ट</h3>
  <p>पृष्ठ हेर्छन्, पुस्तकको बनोट बुझ्छन्, मुद्रित पानाको क्रम मिलाउँछन् र मूल पाठ तथा
  पादटिप्पणी पढ्छन्। शङ्का परेको अंश अर्को एजेन्टले फेरि हेर्छ।</p></div>
  <div class="role-coord"><span class="role-mark" aria-hidden="true">स</span><h3>समन्वय एजेन्ट</h3>
  <p>फरक पढाइका प्रमाण जोडेर एउटै संरचना योजना बनाउँछ र स्वीकृत सामग्रीबाट प्रस्तावित
  कृति फाइल तयार गर्छ। ती फाइल मुख्य अभिलेखबाहिरै रहन्छन्।</p></div>
  <div class="role-software"><span class="role-mark" aria-hidden="true">औ</span><h3>स्थानीय औजार</h3>
  <p>पृष्ठचित्र र OCR बनाउँछन्, नियमले गुणस्तर जाँच्छन्, फाइल नबदलिएको प्रमाण राख्छन्
  र स्वीकृत फाइल मात्र अभिलेखमा सार्छन्।</p></div>
  <div class="role-human"><span class="role-mark" aria-hidden="true">म</span><h3>मानिस</h3>
  <p>कुन सामग्री राख्ने भन्ने योजना र प्रकाशनमा जाने ठ्याक्कै फाइल—दुवै छुट्टाछुट्टै
  स्वीकृत गर्छ। दुई पुनःजाँचले नसुल्झाएको अंश पनि मानिसकै लागि रोकिन्छ।</p></div>
</div>

<aside class="agent-boundary">
  <p class="boundary-label">एजेन्टको सीमा</p>
  <p>एजेन्टले लेखकको भाषा “सुधार्दैन”, नदेखिएको श्लोक वा अक्षर थप्दैन, आफैँ प्रकाशन
  स्वीकृत गर्दैन र कुनै पाठलाई प्रुफरिड भएको घोषणा गर्दैन।</p>
</aside>

<h2 id="graph-title">एउटा पुस्तकले हिँड्ने बाटो</h2>
<p class="section-intro">तलको नक्सा हाम्रो वास्तविक कामकै सरल रूप हो। समान तहका पढाइहरू
सँगसँगै वा पालैपालो चल्न सक्छन्।</p>
<div class="flow-legend" aria-label="जिम्मेवारी सङ्केत">
  <span class="who agent">पठन एजेन्ट</span>
  <span class="who coord">समन्वय एजेन्ट</span>
  <span class="who software">स्थानीय औजार</span>
  <span class="who human">मानिस</span>
</div>
<figure class="ocr-journey" aria-labelledby="graph-title graph-caption">
  <div class="journey-source"><span>मूल</span><strong>स्रोत पुस्तकको PDF</strong><small>पृष्ठचित्र नै अन्तिम प्रमाण</small></div>
  {arrow}
  <section class="journey-phase phase-one">
    <header class="phase-head"><span class="phase-number">१</span><div><p>पहिलो चरण</p><h3>पुस्तक चिन्नु</h3>
    <small>पाठ उतार्नुअघि पुस्तककै नक्सा बनाइन्छ।</small></div></header>
    <div class="mechanical-run">
      <div><span class="who software">स्थानीय औजार</span><strong>स्रोत दर्ता</strong><small>बीचमा रोकिए पनि फेरि सुरु गर्न मिल्ने गरी</small></div>
      <i aria-hidden="true">→</i>
      <div><span class="who software">स्थानीय औजार</span><strong>सुरुआती जाँच</strong><small>PDF, स्रोत र लेखकको आधारभूत विवरण</small></div>
      <i aria-hidden="true">→</i>
      <div><span class="who software">स्थानीय औजार</span><strong>पृष्ठचित्र र धेरै OCR पढाइ</strong><small>हरेक पृष्ठलाई एकभन्दा बढीपटक पढाइन्छ</small></div>
    </div>
    <p class="fan-label">त्यसपछि तीन स्वतन्त्र नजर</p>
    <div class="flow-grid three">
      <div class="flow-card agent"><span class="who agent">गहिरो पठन</span><strong>भित्र के-के छ?</strong><small>कृति, खण्ड, लेखकको आफ्नै भूमिका र हटाउनुपर्ने आधुनिक सामग्री</small></div>
      <div class="flow-card agent"><span class="who agent">द्रुत जाँच</span><strong>पाना सही क्रममा छन्?</strong><small>मुद्रित पृष्ठाङ्क पढेर उल्टापुल्टा स्क्यान पत्ता लगाउने</small></div>
      <div class="flow-card agent"><span class="who agent">द्रुत जाँच</span><strong>कृति पहिल्यै छ?</strong><small>अभिलेखसँग नाम र विवरण मिलाएर दोहोरोपन रोक्ने</small></div>
    </div>
    {arrow}
    <div class="flow-card coord wide"><span class="who coord">समन्वय एजेन्ट</span><strong>तीनै पढाइ जोडेर पुस्तकको एउटै नक्सा</strong><small>हरेक पृष्ठ राखिएको, हटाइएको वा कुनै कृतिसँग जोडिएको हुन्छ।</small></div>
    {arrow}
    <div class="approval-card"><span class="approval-seal" aria-hidden="true">✓</span><div><span class="who human">मानिस</span><strong>पहिलो स्वीकृति</strong><small>पृष्ठक्रम, कृति-विभाजन र हटाइने सामग्री हेरेर मात्र योजना स्वीकार हुन्छ।</small></div></div>
  </section>
  {arrow}

  <section class="journey-phase phase-two">
    <header class="phase-head"><span class="phase-number">२</span><div><p>दोस्रो चरण</p><h3>पाठ उतार्नु</h3>
    <small>स्वीकृत प्रत्येक कविता, सर्ग वा निबन्ध पूरा खण्डका रूपमा पढिन्छ।</small></div></header>
    <div class="phase-note"><span class="who software">स्थानीय औजार</span> हरेक खण्डका लागि छुट्टै काम खोल्छ</div>
    <p class="fan-label">एउटै खण्डमाथि दुई छुट्टाछुट्टै नजर</p>
    <div class="flow-grid two">
      <div class="flow-card agent"><span class="who agent">गहिरो पठन</span><strong>पृष्ठसँग पाठ मिलाउने</strong><small>OCR लाई सङ्केत मानेर पूरा खण्ड अक्षरशः उतार्ने; लेखकको भाषा नछुने</small></div>
      <div class="flow-card agent"><span class="who agent">द्रुत जाँच</span><strong>पादटिप्पणी खोज्ने</strong><small>हरेक पृष्ठको पुछार र पाठमा भएका टिपोटका सङ्केत छुट्टै हेर्ने</small></div>
    </div>
    {arrow}
    <div class="flow-card software wide"><span class="who software">स्थानीय औजार</span><strong>नियमले फेरि जाँच्छ</strong><small>सबै पृष्ठ समेटिए? अङ्क बिग्रिए? पादटिप्पणी छुट्यो? अनावश्यक शीर्षक मिसियो?</small></div>
    <div class="decision-card">
      <p>ठूलो शङ्का बाँकी छ?</p>
      <div class="decision-paths">
        <div class="pass-path"><span>छैन</span><strong>अर्को चरणमा जान्छ</strong></div>
        <div class="review-path"><span>छ</span><strong>अर्को पठन एजेन्टले शङ्का लागेको पृष्ठ फेरि हेर्छ</strong>
        <small>औजारले पुनः जाँच्छ—बढीमा दुई चक्र। त्यसपछि पनि नसुल्झिए मानिसका लागि रोकिन्छ।</small></div>
      </div>
    </div>
    <p class="phase-exit">जोखिम हटेपछि मात्रै अभिलेखका फाइल तयार हुन्छन्।</p>
  </section>
  {arrow}

  <section class="journey-phase phase-three">
    <header class="phase-head"><span class="phase-number">३</span><div><p>तेस्रो चरण</p><h3>अभिलेखमा राख्नु</h3>
    <small>पाठ तयार हुनु र प्रकाशनका लागि स्वीकार हुनु फरक कुरा हुन्।</small></div></header>
    <div class="flow-card coord wide"><span class="who coord">समन्वय एजेन्ट</span><strong>कृति फाइलको मस्यौदा बनाउँछ</strong><small>पाठ, विवरण र स्रोत PDF मुख्य अभिलेखभन्दा बाहिरको सुरक्षित ठाउँमा तयार हुन्छन्।</small></div>
    {arrow}
    <div class="flow-card software wide"><span class="who software">स्थानीय औजार</span><strong>मस्यौदा पूरै जाँच्छ</strong><small>ढाँचा, फाइलको ठाउँ, स्रोत PDF र बदलिन लागेका फाइल—सबै मिल्नुपर्छ।</small></div>
    {arrow}
    <div class="approval-card"><span class="approval-seal" aria-hidden="true">✓</span><div><span class="who human">मानिस</span><strong>दोस्रो स्वीकृति</strong><small>अभिलेखमा जाने ठ्याक्कै फाइल हेरेर मात्रै प्रकाशन स्वीकार हुन्छ।</small></div></div>
    {arrow}
    <div class="flow-card software wide"><span class="who software">स्थानीय औजार</span><strong>स्वीकृत फाइल मात्र सार्छ</strong><small>फेरि एकपटक जाँचेर मुख्य अभिलेखमा राख्छ र परिवर्तनको अभिलेख बनाउँछ।</small></div>
  </section>
  {arrow}
  <div class="journey-finish"><span aria-hidden="true">अ</span><div><strong>अभिलेखका स्रोत फाइल</strong><small>पाठ · विवरण · स्रोत PDF</small></div></div>
  <figcaption id="graph-caption">स्वीकृत फाइल पछि बदलियो भने स्वीकृति आफैँ अमान्य हुन्छ।
  दोस्रो स्वीकृतिअघि कुनै एजेन्टले मुख्य अभिलेखमा सीधै लेख्दैन।</figcaption>
</figure>

<h2>जहाँ गल्ती सजिलै लुक्छ</h2>
<p class="section-intro">OCR को ठूलो भूल प्रायः ठूलो देखिँदैन। एउटा उल्टिएको पाना, हराएको
श्लोक अङ्क वा छुटेको सानो पादटिप्पणीले नै पाठको अर्थ बिगार्न सक्छ। त्यसैले यी ठाउँमा हामी
छुट्टै नजर लगाउँछौँ:</p>
<div class="audit-grid">
  <div><strong>पानाको क्रम</strong><span>मुद्रित पृष्ठाङ्क आफैँ पढेर</span></div>
  <div><strong>श्लोकका अङ्क</strong><span>छापिएको छ भने मात्र राखेर</span></div>
  <div><strong>पृष्ठको पुछार</strong><span>छोटा पादटिप्पणी नछुटाई</span></div>
  <div><strong>पाठ र सजावट</strong><span>दोहोरिने शीर्षक र पृष्ठाङ्क हटाएर</span></div>
  <div><strong>कुन अंश राख्ने?</strong><span>लेखकको भूमिका राखी आधुनिक सम्पादकीय अंश हटाएर</span></div>
</div>

<aside class="ocr-status">
  <p class="status-label">एउटा महत्त्वपूर्ण फरक</p>
  <h2>OCR सम्पन्न ≠ प्रुफरिड</h2>
  <p>यो प्रक्रियाले स्रोतसँग मिलाइएको, जाँचिएको OCR पाठ दिन्छ। तर सुरुदेखि अन्त्यसम्म मूलसँग
  फेरि औपचारिक जाँच नभएसम्म हामी त्यसलाई “प्रुफरिड” भन्दैनौँ। त्यसपछि मात्रै विवरणमा
  <code>proofread: true</code> लेखिन्छ।</p>
</aside>

<h2>यो प्रक्रिया पुनःचलाउन</h2>
<p>यो नक्सा देखाउनका लागि मात्र होइन। हरेक कामको सामग्री, अपेक्षित नतिजा, पुनःजाँचको सीमा
र मानवीय स्वीकृतिका ठाउँ सार्वजनिक स्रोतमा खुला छन्। यसका लागि कुनै खास कम्पनीको सेवा
अनिवार्य छैन; आफ्नो जिम्मा पूरा गर्न सक्ने एजेन्ट भए यही विधि अरूले पनि चलाउन सक्छन्।</p>
<a class="ocr-source" href="https://github.com/chinge55/nepali_archives/blob/main/docs/ocr-workflow.md"
   target="_blank" rel="noopener">
  <span class="source-mark" aria-hidden="true">&lt;/&gt;</span>
  <span><strong>स्रोत कोड र चलाउने विधि</strong><small>कार्यप्रवाह · जिम्मेवारी · जाँचका नियम</small></span>
  <span class="source-arrow" aria-hidden="true">↗</span>
</a>
<p class="meta ocr-version">कार्यप्रवाह संस्करण १ · पछिल्लो संशोधन: २०२६-०८-१३</p>
</article>"""
    (out / "index.html").write_text(
        page("स्क्यानदेखि पाठसम्म — " + SITE_NAME, body,
             desc="नेपाली अभिलेखको प्रदायक-निरपेक्ष OCR र एआई एजेन्ट कार्यप्रवाह",
             css_depth=1, active="about", canon="ocr/"),
        encoding="utf-8")


# ---------------------------------------------------------------- typing tool
# /type/ — Roman→Devanagari typing tool ("mero naam" → मेरो नाम), the archive's
# first tool page. Engine + data are TRACKED at assets/type/ (pdfjs precedent:
# the lexicons are built by roman_nepali_transliteration/pipeline/build_lexicon.py
# from Aksharantar + this corpus, and vendored because CI can't re-download the
# 70 MB training data per deploy). JS loads ONLY on this page. Design decisions:
# roman_nepali_transliteration/{plan.md,rules.md}.
TYPE_CSS = """main{max-width:44rem}
.outwrap{position:relative}
#out{position:relative;z-index:1;width:100%;min-height:6.5rem;background:none;color:var(--fg);
 border:1px solid var(--line);border-radius:10px;padding:.8rem;font-size:1.15rem;line-height:1.85rem;
 font-family:inherit;resize:vertical}
#out:focus{outline:2px solid color-mix(in srgb,var(--accent) 45%,transparent)}
#outbg{position:absolute;inset:0;z-index:0;border:1px solid transparent;border-radius:10px;
 padding:.8rem;font-size:1.15rem;line-height:1.85rem;font-family:inherit;white-space:pre-wrap;
 word-break:break-word;color:transparent;overflow:hidden;pointer-events:none}
#outbg mark{background:color-mix(in srgb,var(--accent) 32%,transparent);color:transparent;border-radius:4px}
.tbar{display:flex;gap:.6rem;margin:.7rem 0;align-items:center;flex-wrap:wrap}
.tbar button{font-family:inherit;font-size:.9rem;padding:.5rem 1rem;min-height:44px;
 border-radius:8px;border:1px solid var(--line);background:none;color:var(--accent);cursor:pointer}
.tbar button:hover{border-color:var(--accent)}
#copy{background:var(--accent);color:var(--bg);border-color:var(--accent);font-weight:600}
#toast{visibility:hidden;color:var(--mut);font-size:.85rem}
#toast.show{visibility:visible}
.ttog{margin-left:auto;font-size:.85rem;color:var(--mut);display:flex;align-items:center;
 gap:.45rem;min-height:48px;cursor:pointer}
.ttog input{width:1.15rem;height:1.15rem;accent-color:var(--accent)}
#cands{display:flex;gap:.5rem;margin:.7rem 0;min-height:56px;flex-wrap:wrap}
.tcand{font-family:inherit;font-size:1.1rem;min-height:48px;min-width:48px;padding:.3rem .75rem;
 border-radius:8px;border:1px solid var(--line);background:none;color:var(--fg);cursor:pointer}
.tcand:hover{border-color:var(--accent)}
.tcand.first{border:2px solid var(--accent);font-weight:600}
.tcand .n{color:var(--mut);font-size:.68rem;vertical-align:super;margin-right:.25rem}
.tcand.lit{border-style:dashed;color:var(--mut)}
#inp{width:100%;font-size:1.1rem;padding:.65rem .75rem;border-radius:10px;color:var(--fg);
 border:2px solid var(--accent);background:none;font-family:inherit}
#inp:focus{outline:none;box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 25%,transparent)}
.thelp{color:var(--mut);font-size:.85rem;line-height:1.7;margin-top:.8rem}
.thelp kbd{background:color-mix(in srgb,var(--line) 55%,transparent);border-radius:4px;
 padding:0 .35rem;font-size:.85em;font-family:inherit}
#status{color:var(--mut);font-size:.75rem;min-height:1rem;margin:.6rem 0 0}
/* keyboard mode (body.kbd, set via visualViewport when the on-screen keyboard is
   up): compress everything so output + candidates + input all stay visible */
body.kbd header.site,body.kbd h1,body.kbd .lead,body.kbd .thelp,body.kbd #status,
body.kbd footer.site{display:none}
body.kbd main{padding-top:.4rem}
body.kbd #out{min-height:3rem;max-height:7.5rem;overflow-y:auto;font-size:1.05rem;line-height:1.6rem}
body.kbd #outbg{font-size:1.05rem;line-height:1.6rem}
body.kbd .tbar{display:none}  /* copy/clear return when the keyboard closes */
body.kbd #cands{min-height:48px;margin:.4rem 0}
body.kbd .tcand{min-height:44px;font-size:1.05rem}"""


def write_type_page():
    """Copy assets/type/ → SITE/type/ and write the /type/ page."""
    src = ROOT / "assets" / "type"
    tdir = SITE / "type"
    tdir.mkdir(exist_ok=True)
    for f in sorted(src.glob("*")):
        if f.is_file() and f.name != "package.json":   # node-ESM marker, not a site asset
            shutil.copy(f, tdir / f.name)
    ver = _ver((src / "app.js").read_text(encoding="utf-8")
               + (src / "engine.js").read_text(encoding="utf-8"))
    body = f"""<h1>नेपालीमा टाइप गर्नुहोस्</h1>
<p class="lead">रोमनमा लेख्नुहोस् (mero naam…) — नेपाली युनिकोडमा पाउनुहोस्। Type in Nepali:
Roman to Nepali Unicode, free and offline-capable.</p>
<div class="outwrap"><div id="outbg" aria-hidden="true"></div><textarea id="out" readonly
 aria-label="नेपाली पाठ (सच्याउन मिल्छ)"
 placeholder="नेपाली यहाँ आउँछ — सच्याउन यहीँ मिल्छ (editable)"></textarea></div>
<div class="tbar">
  <button id="copy" type="button">कपी गर्नुहोस् · Copy</button>
  <button id="clear" type="button">मेट्नुहोस् · Clear</button>
  <span id="toast" role="status" aria-live="polite"></span>
  <label class="ttog"><input type="checkbox" id="engmode" checked> English शब्द English मै</label>
</div>
<div id="cands"></div>
<input id="inp" autocomplete="off" autocorrect="off" autocapitalize="none" spellcheck="false"
 enterkeyhint="done" placeholder="yahan lekhnus… (space = पहिलो रोज्ने)" aria-label="रोमन नेपाली इनपुट">
<p class="thelp">
<kbd>space</kbd>/<kbd>enter</kbd> पहिलो उम्मेदवार रोज्छ · <kbd>1</kbd>–<kbd>5</kbd> अरू रोज्ने ·
<kbd>backspace</kbd> (खाली इनपुटमा) अघिल्लो शब्द सच्याउने · <kbd>esc</kbd> जस्ताको तस्तै राख्ने<br>
माथिको नेपाली सीधै सच्याउन मिल्छ — शब्द select गरेर रोमनमा फेरि लेखे त्यहीँ बस्छ।<br>
Optional: <kbd>T</kbd>=ट <kbd>Th</kbd>=ठ <kbd>D</kbd>=ड <kbd>Dh</kbd>=ढ <kbd>N</kbd>=ण <kbd>S</kbd>=ष
(bheTaula → भेटौला)</p>
<p id="status"></p>
<script type="module" src="app.js?v={ver}" data-v="{ver}"></script>"""
    (tdir / "index.html").write_text(
        page("नेपालीमा टाइप गर्नुहोस् — रोमनबाट नेपाली युनिकोड · " + SITE_NAME, body,
             desc="रोमनमा लेखेर नेपाली युनिकोडमा पाउनुहोस् (mero naam → मेरो नाम) — Type in Nepali online, Roman to Nepali Unicode converter",
             css_depth=1, extra_head=f"<style>{TYPE_CSS}</style>\n",
             active="type", canon="type/"),
        encoding="utf-8")


# ---------------------------------------------------------------- पात्रो
# /patro/ — daily panchanga + rashifal from COMMITTED sources only:
# horoscope/content/panchanga-YYYY-MM.json (computed offline by skyfield via
# horoscope/pipeline/export_month.py — deterministic, regenerable) and
# horoscope/content/YYYY-MM.json (agent-batch prose, reviewed before commit;
# generated by horoscope/pipeline/generate_month.py). This renderer is pure
# stdlib — CI needs no ephemeris, no API key. Renders the latest date ≤ today
# (NPT), so an exhausted content file degrades to a stale page, never a 404.
PATRO_CSS = """main{max-width:46rem}
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
.zg{display:grid;grid-template-columns:repeat(6,1fr);gap:.45rem;margin:.9rem 0 1.1rem}
@media(max-width:40rem){.zg{grid-template-columns:repeat(4,1fr)}}
@media(max-width:26rem){.zg{grid-template-columns:repeat(3,1fr)}}
.zt{font-family:inherit;font-size:.98rem;color:var(--fg);background:none;
 border:1px solid var(--line);border-radius:9px;padding:.55rem .2rem .5rem;
 cursor:pointer;text-align:center;line-height:1.35;transition:border-color .15s,background .15s}
.zt .ltr{display:block;color:var(--mut);font-size:.68rem;letter-spacing:.04em;margin-top:.15rem}
.zt .dot{display:inline-block;width:.45rem;height:.45rem;border-radius:50%;
 margin-left:.3rem;vertical-align:.08rem;background:var(--line)}
.zt .dot.v-मध्यम{background:var(--accent)}
.zt:hover{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 7%,transparent)}
.zt:focus-visible{outline:2px solid color-mix(in srgb,var(--accent) 45%,transparent);outline-offset:2px}
.zt[aria-pressed=true]{border-color:var(--accent);
 background:color-mix(in srgb,var(--accent) 10%,transparent);font-weight:600}
.pt-detail{margin:0 0 1.4rem}
.pt-card{border:1px solid var(--line);border-left:4px solid var(--line);
 border-radius:10px;padding:1.05rem 1.2rem;margin:.9rem 0}
.js .pt-card{display:none}
.pt-card.v-मध्यम{border-left-color:var(--accent)}
.pt-card h3{margin:0;font-size:1.22rem}
.pt-card h3 .val{color:var(--mut);font-weight:400;font-size:.85rem}
.pt-card .nam{color:var(--mut);font-size:.78rem;margin:.15rem 0 .55rem}
.pt-card p{margin:.3rem 0;font-size:1.02rem;line-height:1.85}
.pt-card .rule{color:var(--mut);font-size:.78rem;margin-top:.6rem}
.pt-card .flag{font-weight:600;font-size:.85rem}
.pt-hint{display:none;color:var(--mut);font-size:.95rem;border:1px dashed var(--line);
 border-radius:10px;padding:1.1rem 1.2rem;margin:.9rem 0;text-align:center}
.js .pt-hint{display:block}
.js .pt-hint.off{display:none}
.pt-note{color:var(--mut);font-size:.85rem;border-top:1px solid var(--line);
 margin-top:2.2rem;padding-top:1rem;line-height:1.7}
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

PATRO_JS = """
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


def write_patro_page():
    """Render /patro/ (today NPT) + one archived page per committed date
    (/patro/YYYY-MM-DD/). /patro/ carries a client-side NPT-date check that
    redirects to the right dated page if the static build is stale — the
    date can never be wrong for a JS visitor even if the daily cron slips;
    the cron keeps the static baseline fresh for everyone else.
    Returns True if written."""
    from datetime import datetime, timedelta, timezone
    content = ROOT / "horoscope" / "content"
    days = {}
    for f in sorted(content.glob("panchanga-*.json")):
        days.update(json.loads(f.read_text(encoding="utf-8"))["days"])
    if not days:
        print("patro: no committed panchanga data — page skipped")
        return False
    prose_all = {}
    for f in sorted(content.glob("20??-??.json")):
        prose_all.update(json.loads(f.read_text(encoding="utf-8"))["days"])
    npt_today = (datetime.now(timezone.utc) + timedelta(hours=5, minutes=45)
                 ).date().isoformat()
    today_iso = max((d for d in days if d <= npt_today), default=min(days))

    def render(iso, *, dated):
        p = days[iso]
        prose = prose_all.get(iso, {})
        depth = 2 if dated else 1

        def anga_cell(label, a):
            end_d, end_t = a["ends"].split("T")
            when = end_t.translate(_DEVNUM) + ("" if end_d == iso else " (भोलिपल्ट)")
            return (f'<div><span class="lbl">{label}</span><b>{esc(a["name"])}</b>'
                    f'<span class="end">समाप्ति {when}</span></div>')

        cards, tiles = [], []
        for r in p["rashis"]:
            flag = ('<span class="flag">चन्द्राष्टम — सोच-विचार गरेर मात्र नयाँ काम '
                    'थाल्नुहोस्।</span>' if r["chandrashtama"] else "")
            rule = r["rule"].replace(str(r["house"]), _dev(r["house"]), 1)
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
<p class="pt-bs">{esc(p['bs_str'])} <span class="yr">{_dev(p['bs'].split('-')[0])} वि.सं.</span> · {esc(p['vara'])}</p>
<p class="pt-date">{esc(p['ad'])} · सूर्योदय {p['sunrise'].translate(_DEVNUM)} · सूर्यास्त {p['sunset'].translate(_DEVNUM)} (काठमाडौं)</p>

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
<script>{PATRO_JS}</script>"""

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
                                f"<style>{PATRO_CSS}</style>\n"),
                    active="patro",
                    canon=f"patro/{iso}/" if dated else "patro/",
                    noindex=dated)

    out = SITE / "patro"
    out.mkdir(exist_ok=True)
    (out / "index.html").write_text(render(today_iso, dated=False),
                                    encoding="utf-8")
    for iso in days:
        d = out / iso
        d.mkdir(exist_ok=True)
        (d / "index.html").write_text(render(iso, dated=True), encoding="utf-8")
    return True


# ---------------------------------------------------------------- PDF reader
# A dedicated .../pdf/ page per work that has a source PDF: a pdf.js viewer that
# renders pages on demand (IntersectionObserver) and fetches only the byte ranges
# for the pages in view (HTTP Range — GitHub Pages serves Accept-Ranges:bytes), so
# even a 378-page scan never downloads up front. The ~1.5 MB library (vendored in
# assets/pdfjs/, copied to SITE/pdfjs/) loads ONLY on this page — the text reading
# pages stay JS-free. Reader CSS/JS live inline here so they never bloat those pages.
READER_CSS = """main{max-width:64rem}
.pdftop{margin:.2rem 0 1rem}
.pdfh1{font-size:1.3rem;margin:.3rem 0}
.pdfbar{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;color:var(--mut);font-size:.9rem;margin:.5rem 0 0}
.pdfback{text-decoration:none}
.pdfstat{margin-left:auto}
.pdfzoom button{font-family:inherit;font-size:1rem;line-height:1;width:2rem;height:2rem;border:1px solid var(--line);background:none;color:var(--accent);border-radius:6px;cursor:pointer;margin-left:.3rem}
.pdfzoom button:hover{border-color:var(--accent);background:var(--accent);color:#fff}
.pdfpages{margin:0 auto;max-width:760px}
.pdfpage{position:relative;margin:0 auto 1rem;min-height:200px;background:#fff;box-shadow:0 1px 6px rgba(0,0,0,.18)}
.pdfpage canvas{display:block;width:100%;height:auto}
.pdferr{color:var(--mut);padding:1rem;border:1px solid var(--line);border-radius:8px}
@media(prefers-color-scheme:dark){.pdfpage{box-shadow:0 1px 6px rgba(0,0,0,.5)}}"""

# Plain string (NOT an f-string) — its many { } are literal JS. Only __WORKER_URL__
# is substituted; the PDF URL is read from the #pdfpages data-url attribute.
READER_JS = """(function(){
  var lib=window.pdfjsLib, host=document.getElementById('pdfpages'),
      statusEl=document.getElementById('pdfstatus'), url=host.getAttribute('data-url');
  function fail(){ host.innerHTML='<p class="pdferr">यो ब्राउजरमा रिडर चल्न सकेन। <a href="'+url+'">सिधै PDF हेर्नुहोस् / डाउनलोड गर्नुहोस्</a>।</p>'; }
  if(!lib||!('IntersectionObserver' in window)){ fail(); return; }
  lib.GlobalWorkerOptions.workerSrc="__WORKER_URL__";
  function dev(n){ return (''+n).replace(/[0-9]/g,function(d){return '०१२३४५६७८९'.charAt(+d);}); }
  var ZOOM=[0.6,0.75,0.9,1,1.2,1.45,1.75,2.1], zi=3, BASE=760;
  var doc=null, N=0, divs=[], rendered={}, visible={}, aspect='1 / 1.4', rt=0;
  function colW(){ return Math.min(BASE*ZOOM[zi], window.innerWidth-28); }
  function applyW(){ host.style.maxWidth=Math.round(colW())+'px'; }
  function render(pg){
    var div=divs[pg-1]; if(!div||rendered[pg]) return; rendered[pg]=true;
    doc.getPage(pg).then(function(page){
      if(!rendered[pg]) return;
      var dpr=window.devicePixelRatio||1, cssW=div.clientWidth||colW(),
          v1=page.getViewport({scale:1}), vp=page.getViewport({scale:(cssW/v1.width)*dpr}),
          c=document.createElement('canvas');
      c.width=Math.ceil(vp.width); c.height=Math.ceil(vp.height);
      var old=div.querySelector('canvas'); if(old) div.removeChild(old);
      div.style.aspectRatio=''; div.style.minHeight='0'; div.appendChild(c);
      page.render({canvasContext:c.getContext('2d'), viewport:vp});
    }).catch(function(){ rendered[pg]=false; });
  }
  function release(pg){
    var div=divs[pg-1]; rendered[pg]=false;
    if(div){ var c=div.querySelector('canvas'); if(c){ div.removeChild(c); div.style.aspectRatio=aspect; div.style.minHeight=''; } }
  }
  function counter(){ var k=Object.keys(visible).map(Number); if(k.length) statusEl.textContent='पृष्ठ '+dev(Math.min.apply(null,k))+' / '+dev(N); }
  function rezoom(){ applyW(); for(var pg in rendered){ if(rendered[pg]){ rendered[pg]=false; render(+pg); } } }
  var plus=document.getElementById('pdfplus'), minus=document.getElementById('pdfminus');
  plus.addEventListener('click',function(){ if(zi<ZOOM.length-1){zi++; rezoom();} });
  minus.addEventListener('click',function(){ if(zi>0){zi--; rezoom();} });
  window.addEventListener('resize',function(){ clearTimeout(rt); rt=setTimeout(rezoom,200); });
  applyW();
  lib.getDocument({url:url, disableAutoFetch:true, disableStream:false, rangeChunkSize:65536}).promise
    .then(function(pdf){ doc=pdf; N=pdf.numPages; return pdf.getPage(1); })
    .then(function(p1){
      var v=p1.getViewport({scale:1}); aspect=v.width+' / '+v.height;
      var frag=document.createDocumentFragment();
      for(var i=1;i<=N;i++){ var d=document.createElement('div'); d.className='pdfpage'; d.dataset.page=i; d.style.aspectRatio=aspect; frag.appendChild(d); divs.push(d); }
      host.appendChild(frag);
      statusEl.textContent='पृष्ठ १ / '+dev(N);
      var io=new IntersectionObserver(function(es){
        es.forEach(function(e){ var pg=+e.target.dataset.page;
          if(e.isIntersecting){ visible[pg]=true; render(pg); } else { delete visible[pg]; release(pg); } });
        counter();
      }, {rootMargin:'800px 0px'});
      divs.forEach(function(d){ io.observe(d); });
    })
    .catch(fail);
})();"""


def write_pdf_reader(out_dir, depth, rel, pdf_fn, meta, aslug_, aname, archive_base):
    """Write out_dir/pdf/index.html — the lazy pdf.js reader for a PDF-bearing work."""
    rdepth = depth + 1
    up = "../" * rdepth
    pdf_url = (f'{archive_base.rstrip("/")}/{rel.as_posix()}/{esc(pdf_fn)}'
               if archive_base else f'../{esc(pdf_fn)}')
    title = meta["title"]
    title_full = f"{title} — {meta['author']['name']} — मूल पृष्ठ"
    head = (f'<script src="{up}pdfjs/pdf.min.js"></script>\n'
            f'<style>{READER_CSS}</style>\n')
    js = READER_JS.replace("__WORKER_URL__", f"{up}pdfjs/pdf.worker.min.js")
    body = f"""<nav class="crumb"><a href="{up}authors/{aslug_}/">← {esc(aname)}</a> · <a href="../">{esc(title)}</a></nav>
<div class="pdftop">
  <h1 class="pdfh1">{esc(title)} — मूल पृष्ठ</h1>
  <div class="pdfbar"><a class="pdfback" href="../">← पाठ पढ्नुहोस्</a><span id="pdfstatus" class="pdfstat"></span><span class="pdfzoom"><button id="pdfminus" type="button" aria-label="सानो">−</button><button id="pdfplus" type="button" aria-label="ठूलो">+</button></span></div>
</div>
<div id="pdfpages" class="pdfpages" data-url="{pdf_url}"></div>
<noscript><p class="pdferr">PDF रिडरलाई JavaScript चाहिन्छ। <a href="{pdf_url}">सिधै PDF हेर्नुहोस्</a>।</p></noscript>
<script>{js}</script>"""
    pdir = out_dir / "pdf"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "index.html").write_text(
        page(title_full, body, desc=title_full, css_depth=rdepth, active="works",
             canon=rel.as_posix() + "/pdf/", extra_head=head, noindex=True),
        encoding="utf-8")


# ---------------------------------------------------------------- CSS / JS
CSS = """:root{--bg:#fbfaf7;--fg:#1a1a1a;--mut:#6b675e;--line:#e3ded3;--link:#6a4b16;--accent:#8a5a00;
 --g-mahakavya:#7a3b2e;--g-khandakavya:#96522a;--g-upanyas:#6b6b2a;--g-katha:#8a4a55;--g-nibandha:#4e6472;
 --g-kavita:#8a5a00;--g-balkavita:#4e7345;--g-git:#6d4a6e;--g-gazal:#3f6f6a}
@media(prefers-color-scheme:dark){:root{--bg:#15140f;--fg:#e7e3da;--mut:#9a948a;--line:#2c2a22;--link:#d8b15f;--accent:#e0b65f;
 --g-mahakavya:#cf8a76;--g-khandakavya:#d69a6b;--g-upanyas:#b5b36a;--g-katha:#c9909a;--g-nibandha:#8fa9b8;
 --g-kavita:#e0b65f;--g-balkavita:#93b98a;--g-git:#b58ab4;--g-gazal:#86b3ae}}
/* manual override — :root[...] (0,2,0) outranks the media query's :root (0,1,0), so it wins on any system theme */
:root[data-theme=light]{--bg:#fbfaf7;--fg:#1a1a1a;--mut:#6b675e;--line:#e3ded3;--link:#6a4b16;--accent:#8a5a00;
 --g-mahakavya:#7a3b2e;--g-khandakavya:#96522a;--g-upanyas:#6b6b2a;--g-katha:#8a4a55;--g-nibandha:#4e6472;
 --g-kavita:#8a5a00;--g-balkavita:#4e7345;--g-git:#6d4a6e;--g-gazal:#3f6f6a}
:root[data-theme=dark]{--bg:#15140f;--fg:#e7e3da;--mut:#9a948a;--line:#2c2a22;--link:#d8b15f;--accent:#e0b65f;
 --g-mahakavya:#cf8a76;--g-khandakavya:#d69a6b;--g-upanyas:#b5b36a;--g-katha:#c9909a;--g-nibandha:#8fa9b8;
 --g-kavita:#e0b65f;--g-balkavita:#93b98a;--g-git:#b58ab4;--g-gazal:#86b3ae}
.g-mahakavya{--gc:var(--g-mahakavya)}.g-khandakavya{--gc:var(--g-khandakavya)}
.g-upanyas{--gc:var(--g-upanyas)}.g-katha{--gc:var(--g-katha)}.g-nibandha{--gc:var(--g-nibandha)}
.g-kavita{--gc:var(--g-kavita)}.g-balkavita{--gc:var(--g-balkavita)}
.g-git{--gc:var(--g-git)}.g-gazal{--gc:var(--g-gazal)}
*{box-sizing:border-box}html{font-size:19px}
body{margin:0;background:var(--bg);color:var(--fg);
 font-family:"Noto Serif Devanagari","Mukta","Kalimati",Georgia,"Times New Roman",serif;
 line-height:1.85;-webkit-text-size-adjust:100%}
header.site,footer.site{max-width:44rem;margin:0 auto;padding:1rem 1.25rem;display:flex;
 gap:1rem;align-items:center;justify-content:space-between;flex-wrap:wrap}
footer.site{display:block;border-top:1px solid var(--line);margin-top:3rem;color:var(--mut);font-size:.8rem}
/* brand = the न mark (::before image, swaps to its pressed frame on hover) + the
   site name as live text — only the mark animates, the text never moves and picks
   up theme colors by itself. url() resolves against root-level style.css. */
.brand{display:flex;flex:none;align-items:center;gap:.5rem;
 font-size:1.15rem;font-weight:600;text-decoration:none;color:var(--fg)}
.brand::before{content:"";flex:none;width:1.3rem;height:1.75rem;
 background:url(logo.png) no-repeat center bottom/contain}
.brand span{position:relative;top:.3rem}
.brand:hover::before,.brand:active::before{background-image:url(logo-pressed.png)}
.brand:focus-visible{outline:2px solid color-mix(in srgb,var(--accent) 45%,transparent);outline-offset:2px;border-radius:.3rem}
@media(prefers-color-scheme:dark){.brand::before{background-image:url(logo-dark.png)}
 .brand:hover::before,.brand:active::before{background-image:url(logo-pressed-dark.png)}}
:root[data-theme=light] .brand::before{background-image:url(logo.png)}
:root[data-theme=light] .brand:hover::before,:root[data-theme=light] .brand:active::before{background-image:url(logo-pressed.png)}
:root[data-theme=dark] .brand::before{background-image:url(logo-dark.png)}
:root[data-theme=dark] .brand:hover::before,:root[data-theme=dark] .brand:active::before{background-image:url(logo-pressed-dark.png)}
nav a,.themebtn{color:var(--mut);text-decoration:none;font-size:.95rem;font-family:inherit;
 padding:.34rem .6rem;margin-left:.2rem;border-radius:.45rem;background:none;border:0;cursor:pointer}
nav a:hover,.themebtn:hover{color:var(--accent);background:color-mix(in srgb,var(--accent) 9%,transparent)}
nav a.on{color:var(--accent)}
nav a:focus-visible,.themebtn:focus-visible{outline:2px solid color-mix(in srgb,var(--accent) 45%,transparent);outline-offset:1px}
main{max-width:44rem;margin:0 auto;padding:0 1.25rem 2rem}
main h2{font-size:1.05rem;font-weight:600;margin:2rem 0 .5rem}
blockquote.law{margin:1.2rem 0;padding:.7rem 0 .7rem 1.1rem;border-left:3px solid var(--accent)}
blockquote.law .cite{display:block;margin-top:.6rem;color:var(--mut);font-size:.85rem}
a{color:var(--link)}
h1{font-size:2.35rem;line-height:1.25;margin:.7rem 0 .3rem}
.byline{color:var(--mut);margin:.1rem 0}
.meta{color:var(--mut);font-size:.85rem;margin:.4rem 0 0}
.pdfread{display:inline-block;margin:.7rem 0 .1rem;font-size:.9rem;padding:.34rem .85rem;border:1px solid var(--line);border-radius:6px;color:var(--accent);text-decoration:none;transition:background .15s,color .15s,border-color .15s}
.pdfacts{display:flex;gap:.6rem;flex-wrap:wrap}
.pdfacts .pdfread{margin:.7rem 0 .1rem}
.pdfread:hover{border-color:var(--accent);background:var(--accent);color:#fff}
.tochint{color:var(--mut);font-size:.9rem;margin:1.6rem 0 .4rem}
.toc{margin:.3rem 0 0;padding-left:1.3rem;line-height:2.1;font-size:1.05rem}
.toc a{color:var(--link);text-decoration:none}
.toc a:hover{text-decoration:underline}
.crumb{font-size:.85rem;margin:0 0 .75rem}
.crumb a{color:var(--mut);text-decoration:none}
.crumb a:hover{color:var(--accent)}
.work{margin-top:2.6rem;font-size:1.22rem;line-height:2.05}
.stanza{margin:0 0 1.7rem}
/* stanza numbers hang in the margin, in the accent — like numbered श्लोक.
   work_html tags numeral-only blocks with .snum */
.stanza.snum{position:relative;margin:0;height:0}
.stanza.snum .ln{position:absolute;left:-3.1rem;top:.35em;width:2.2rem;text-align:right;
 color:var(--accent);font-weight:700;font-size:1rem;padding:0;text-indent:0}
@media(max-width:900px){.stanza.snum{height:auto;margin:0 0 .3rem}
 .stanza.snum .ln{position:static;width:auto;text-align:left;padding:0;text-indent:0}}
.work.verse .ln{display:block;padding-left:1.6em;text-indent:-1.6em;text-wrap:pretty}  /* hanging indent + avoid 1-word orphan wraps */
.work.prose .stanza{text-align:left;text-wrap:pretty}
/* Narrow phones: long classical verse lines were wrapping their last word/danda as a
   2-char orphan. Step the base size down + trim gutters so most lines simply fit. */
@media(max-width:480px){
 html{font-size:17px}
 main,header.site{padding-left:.9rem;padding-right:.9rem}
 .work{line-height:1.85}
 .work.verse .ln{padding-left:1.25em;text-indent:-1.25em}
 .wmeta .chip{display:none}   /* keep list rows one line on phones */
}
.work h2.sec{font-size:1.05rem;font-weight:600;color:var(--accent);margin:2.4rem 0 1rem}
.work .colophon{font-size:.82rem;font-style:italic;color:var(--mut);margin:1.8rem 0 0;opacity:.9}
.seqnav{display:flex;gap:1rem;margin-top:2.5rem;padding-top:1rem;border-top:1px solid var(--line);font-size:.92rem}
.seqnav a{text-decoration:none;color:var(--link);max-width:48%}
.seqnav .nx{margin-left:auto;text-align:right}
.seqnav .lbl{display:block;color:var(--mut);font-size:.72rem}
.downloads{font-size:.85rem;margin-top:2.5rem;padding-top:1rem;border-top:1px solid var(--line);color:var(--mut)}
.downloads a{margin-right:1rem}
.meta a{color:var(--link);text-decoration:none}
.meta a:hover{text-decoration:underline}
.lead{color:var(--mut);font-size:1.05rem}
.toc{font-size:.9rem;margin:1rem 0 1.5rem;color:var(--mut)}
.toc a{text-decoration:none;margin-right:1rem;white-space:nowrap;display:inline-block}
.home-sec{margin:2.7rem 0}
.home-sec h2{font-size:1.05rem;color:var(--fg);font-weight:600;border-bottom:2px solid var(--line);padding-bottom:.2rem}
ul.works{list-style:none;padding:0;margin:1rem 0}
ul.works li{margin:.15rem 0;padding:.35rem 0;border-bottom:1px solid var(--line)}
ul.works li a{text-decoration:none;font-size:1.1rem}
ul.works li .r{color:var(--mut);font-size:.82rem;margin-left:.5rem}
.group h2{font-size:1rem;color:var(--mut);font-weight:600;margin:2rem 0 .25rem;
 text-transform:none;border-bottom:2px solid var(--line);padding-bottom:.2rem}
.group h2 a,.home-sec h2 a{color:inherit;text-decoration:none}
.group h2 a:hover,.home-sec h2 a:hover{color:var(--accent)}
.count{color:var(--mut);font-weight:400;font-size:.85rem}
/* right-floated catalogue bits on work list items: genre chip · reading time · 📖 scan */
.wmeta{float:right;color:var(--mut);font-size:.72rem;white-space:nowrap;margin-left:.6rem;line-height:2.1}
.wmeta .chip{border:1px solid var(--line);border-left:3px solid var(--gc,var(--accent));
 border-radius:.3rem;padding:0 .35rem;margin-right:.5rem}
.wmeta .rt{margin-right:.35rem}
/* shelves: typographic cover cards (home विधा/सङ्ग्रह sections, /genres/) */
.shelf{display:grid;grid-template-columns:repeat(auto-fill,minmax(9.5rem,1fr));gap:.7rem;margin:1rem 0}
.card{display:block;text-decoration:none;color:var(--fg);border:1px solid var(--line);
 border-left:4px solid var(--gc,var(--accent));border-radius:.45rem;padding:1rem 1.1rem;
 background:color-mix(in srgb,var(--gc,var(--accent)) 5%,var(--bg))}
.card b{display:block;font-weight:600;font-size:1.22rem;line-height:1.4;overflow:hidden;text-overflow:ellipsis}
.card .en{color:var(--mut);font-size:.8rem;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.card .n{display:block;color:var(--gc,var(--accent));font-weight:600;font-size:.82rem;margin-top:.35rem}
.card:hover{border-color:var(--gc,var(--accent));
 background:color-mix(in srgb,var(--gc,var(--accent)) 11%,var(--bg))}
.tagline-en{color:var(--mut);font-size:.95rem;margin:.1rem 0 .8rem}
.foot-en{margin:.2rem 0 0}
#q{width:100%;font:inherit;font-size:1.05rem;padding:.75rem .9rem;border:1.5px solid var(--line);
 border-radius:9px;background:var(--bg);color:var(--fg);transition:border-color .15s}
#q:focus{border-color:var(--accent);outline:none;
 box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 18%,transparent)}
#results li .snip{display:block;color:var(--mut);font-size:.8rem;white-space:nowrap;
 overflow:hidden;text-overflow:ellipsis}
.hint{color:var(--mut);font-size:.85rem;margin:.4rem 0 0}
.hint a{color:var(--accent);text-decoration:none;margin-right:.8rem}
/* full-text (in-poem) search results */
#ft{margin:.5rem 0 0}
.fthead{font-size:.95rem;color:var(--mut);font-weight:600;border-top:1px solid var(--line);padding-top:1rem;margin:1.4rem 0 .6rem}
.ftmsg{color:var(--mut);font-size:.85rem;margin:1rem 0}
ul.ftlist{list-style:none;padding:0;margin:0}
ul.ftlist li{margin:0 0 1.15rem;padding:0}
ul.ftlist li a{text-decoration:none;font-size:1.05rem}
ul.ftlist .ex{margin:.25rem 0 0;color:var(--mut);font-size:.93rem;line-height:1.75}
ul.ftlist .ex mark{background:color-mix(in srgb,var(--accent) 26%,transparent);color:inherit;border-radius:2px;padding:0 .12em}
/* arrived-from-search highlight on the work page (Pagefind highlighter) */
.work mark.pagefind-highlight,.work mark[data-pagefind-highlight]{background:color-mix(in srgb,var(--accent) 32%,transparent);color:inherit;border-radius:2px;padding:0 .1em;scroll-margin-top:4rem}
.prog{position:fixed;top:0;left:0;height:3px;width:0;background:var(--accent);z-index:50}
.themebtn{font-size:1.05rem;line-height:1}
body{transition:background-color .25s ease,color .25s ease}
@media(prefers-reduced-motion:no-preference){
 html{scroll-behavior:smooth}
 a{transition:color .15s ease}
 nav a,.themebtn{transition:color .15s ease,background-color .15s ease,transform .06s ease}
 nav a:active,.themebtn:active{transform:translateY(1px)}
 ul.works li{transition:background-color .15s ease}
 ul.works li:hover{background:color-mix(in srgb,var(--accent) 7%,transparent)}
 .card{transition:background-color .15s ease,border-color .15s ease}
 main{animation:fade .35s ease both}
 .prog{transition:width .12s linear}
 @keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
}
/* home link to the stats page */
.statlink{margin:1.6rem 0 0;font-size:.92rem}
.statlink a{text-decoration:none;color:var(--mut)}
.statlink a:hover{color:var(--accent)}
.aboutcall{margin:1.3rem 0;padding:.8rem 1rem;border-left:4px solid var(--accent);
 background:color-mix(in srgb,var(--accent) 6%,var(--bg));font-size:.92rem}
.aboutcall a{font-weight:600;text-decoration:none}
.aboutcall a:hover{text-decoration:underline}
/* OCR workflow: an editorial account with a visual map of the actual DAG */
.ocr-page{--paper:color-mix(in srgb,var(--accent) 3.5%,var(--bg));--agent:var(--g-mahakavya);
 --coord:var(--g-nibandha);--human:var(--accent)}
.ocr-page>p{max-width:40rem;line-height:1.85}
.ocr-page>h2{border-top:1px solid var(--line);padding-top:1.35rem;margin-top:3.2rem;
 font-size:1.35rem;letter-spacing:-.012em}
.ocr-hero{position:relative;margin:1rem 0 1.6rem;padding:2.2rem 2.1rem 2rem;overflow:hidden;
 border:1px solid var(--line);border-radius:1rem;
 background:linear-gradient(145deg,color-mix(in srgb,var(--accent) 13%,var(--bg)),var(--bg) 68%)}
.ocr-hero:after{content:'अ';position:absolute;right:-.3rem;bottom:-3.3rem;color:var(--accent);
 opacity:.07;font-size:12rem;font-weight:700;line-height:1;pointer-events:none}
.ocr-kicker{margin:0 0 .6rem;color:var(--accent);font-size:.7rem;font-weight:800;
 letter-spacing:.11em;text-transform:uppercase}
.ocr-hero h1{position:relative;z-index:1;margin:0;font-size:clamp(2rem,7vw,3.2rem);
 line-height:1.16;letter-spacing:-.04em}
.ocr-dek{position:relative;z-index:1;max-width:31rem;margin:.75rem 0 0;color:var(--mut);
 font-size:1.03rem;line-height:1.72}
.ocr-principle{display:grid;grid-template-columns:auto 1fr;gap:.25rem .75rem;align-items:start;
 margin:1.8rem 0;padding:1.05rem 1.2rem;border-block:1px solid var(--line)}
.ocr-principle>span{color:var(--accent);font-family:Georgia,serif;font-size:3.5rem;line-height:.9}
.ocr-principle p{margin:0;font-size:1.02rem;line-height:1.75}
.section-intro{margin-top:-.35rem;color:var(--mut);font-size:.92rem}
.ocr-roles{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.85rem;margin:1.2rem 0}
.ocr-roles>div{position:relative;min-height:9.2rem;padding:1.05rem 1rem 1rem 3.7rem;
 border:1px solid var(--line);border-radius:.8rem;background:var(--paper)}
.ocr-roles .role-agent{--role:var(--agent)}
.ocr-roles .role-coord{--role:var(--coord)}
.ocr-roles .role-software{--role:var(--mut)}
.ocr-roles .role-human{--role:var(--human)}
.role-mark{position:absolute;left:1rem;top:1rem;display:grid;place-items:center;width:2rem;height:2rem;
 border-radius:50%;color:var(--role);background:color-mix(in srgb,var(--role) 12%,var(--bg));
 font-size:.72rem;font-weight:800}
.ocr-roles h3{margin:0;color:var(--role);font-size:.96rem}
.ocr-roles p{margin:.32rem 0 0;color:var(--mut);font-size:.82rem;line-height:1.65}
.agent-boundary{margin:1.5rem 0 0;padding:.9rem 1.1rem;border-left:4px solid var(--agent);
 border-radius:0 .55rem .55rem 0;background:color-mix(in srgb,var(--agent) 6%,var(--bg))}
.agent-boundary p{margin:.2rem 0;font-size:.88rem;line-height:1.68}
.agent-boundary .boundary-label{color:var(--agent);font-size:.7rem;font-weight:800;letter-spacing:.06em}
.who{display:inline-flex;align-items:center;width:max-content;max-width:100%;padding:.11rem .48rem;
 border-radius:2rem;font-size:.61rem;font-weight:800;line-height:1.55;letter-spacing:.015em}
.who.agent{color:var(--agent);background:color-mix(in srgb,var(--agent) 11%,transparent)}
.who.coord{color:var(--coord);background:color-mix(in srgb,var(--coord) 13%,transparent)}
.who.software{color:var(--mut);background:color-mix(in srgb,var(--mut) 11%,transparent)}
.who.human{color:var(--human);background:color-mix(in srgb,var(--human) 12%,transparent)}
.flow-legend{display:flex;flex-wrap:wrap;gap:.4rem .5rem;margin:.85rem 0 1.1rem}
.ocr-journey{margin:0 0 2.8rem;padding:1.2rem;border:1px solid var(--line);border-radius:1rem;
 background:radial-gradient(circle at 50% 0,color-mix(in srgb,var(--accent) 8%,transparent),transparent 20rem),var(--paper)}
.journey-source,.journey-finish{display:flex;align-items:center;gap:.75rem;width:max-content;
 max-width:100%;margin:0 auto;padding:.8rem 1.1rem;border:1px solid var(--line);border-radius:4rem;
 background:var(--bg);box-shadow:0 .25rem 1rem color-mix(in srgb,var(--fg) 5%,transparent)}
.journey-source>span,.journey-finish>span{display:grid;place-items:center;flex:0 0 2.1rem;height:2.1rem;
 border-radius:50%;background:color-mix(in srgb,var(--accent) 13%,var(--bg));color:var(--accent);
 font-size:.68rem;font-weight:800}
.journey-source strong,.journey-source small,.journey-finish strong,.journey-finish small{display:block}
.journey-source strong,.journey-finish strong{font-size:.88rem}
.journey-source small,.journey-finish small{color:var(--mut);font-size:.66rem}
.flow-arrow{text-align:center;color:var(--accent);font-size:1.2rem;line-height:2.15rem;height:2.15rem}
.journey-phase{--phase:var(--accent);position:relative;padding:1.15rem;border:1px solid var(--line);
 border-top:4px solid var(--phase);border-radius:.85rem;background:var(--bg);
 box-shadow:0 .35rem 1.35rem color-mix(in srgb,var(--fg) 4%,transparent)}
.journey-phase.phase-two{--phase:var(--agent)}
.journey-phase.phase-three{--phase:var(--g-balkavita)}
.phase-head{display:flex;align-items:flex-start;gap:.85rem;margin:0 0 1.2rem;padding:0 0 1rem;
 border-bottom:1px solid var(--line)}
.phase-number{display:grid;place-items:center;flex:0 0 2.55rem;height:2.55rem;border-radius:50%;
 background:color-mix(in srgb,var(--phase) 13%,var(--bg));color:var(--phase);font-weight:800}
.phase-head p{margin:0 0 .05rem;color:var(--phase);font-size:.64rem;font-weight:800;letter-spacing:.06em}
.phase-head h3{margin:0;font-size:1.35rem;line-height:1.25}
.phase-head small{display:block;margin-top:.18rem;color:var(--mut);font-size:.74rem;line-height:1.5}
.mechanical-run{display:grid;grid-template-columns:1fr auto 1fr auto 1fr;gap:.45rem;align-items:center}
.mechanical-run>div{height:100%;padding:.7rem;border:1px dashed var(--line);border-radius:.55rem;
 background:color-mix(in srgb,var(--mut) 3%,var(--bg));text-align:center}
.mechanical-run strong,.mechanical-run small{display:block}
.mechanical-run strong{margin:.28rem 0 .12rem;font-size:.78rem}
.mechanical-run small{color:var(--mut);font-size:.62rem;line-height:1.45}
.mechanical-run i{color:var(--mut);font-size:.75rem;font-style:normal}
.fan-label{position:relative;margin:1.3rem 0 .65rem;color:var(--mut);font-size:.69rem;
 font-weight:700;text-align:center}
.fan-label:before,.fan-label:after{content:'';display:inline-block;width:2.5rem;margin:0 .5rem;
 border-top:1px solid var(--line);vertical-align:middle}
.flow-grid{display:grid;gap:.7rem;align-items:stretch}
.flow-grid.two{grid-template-columns:repeat(2,minmax(0,1fr))}
.flow-grid.three{grid-template-columns:repeat(3,minmax(0,1fr))}
.flow-card{position:relative;padding:.78rem .8rem;border:1px solid var(--line);border-radius:.58rem;
 background:color-mix(in srgb,var(--card,var(--mut)) 3.5%,var(--bg));text-align:left}
.flow-card.agent{--card:var(--agent)}
.flow-card.coord{--card:var(--coord)}
.flow-card.software{--card:var(--mut)}
.flow-card:before{content:'';position:absolute;inset:.55rem auto .55rem 0;width:3px;border-radius:3px;
 background:var(--card,var(--mut))}
.flow-card strong,.flow-card small{display:block}
.flow-card strong{margin:.34rem 0 .18rem;font-size:.82rem;line-height:1.4}
.flow-card small{color:var(--mut);font-size:.67rem;line-height:1.52}
.flow-card.wide{max-width:30rem;margin-inline:auto;padding:.9rem 1rem;text-align:center}
.flow-card.wide:before{inset:0 .6rem auto;height:3px;width:auto}
.phase-note{margin:.2rem 0 .8rem;padding:.65rem .75rem;border-radius:.5rem;
 background:color-mix(in srgb,var(--mut) 7%,var(--bg));color:var(--mut);font-size:.73rem;text-align:center}
.phase-note .who{margin-right:.35rem}
.approval-card{display:flex;align-items:center;gap:.8rem;max-width:30rem;margin:0 auto;padding:.85rem 1rem;
 border:1.5px solid var(--human);border-radius:.7rem;background:color-mix(in srgb,var(--human) 7%,var(--bg))}
.approval-card .approval-seal{display:grid;place-items:center;flex:0 0 2.15rem;height:2.15rem;
 border-radius:50%;background:var(--human);color:var(--bg);font-weight:800}
.approval-card strong,.approval-card small{display:block}
.approval-card strong{margin:.25rem 0 .1rem;font-size:.86rem}
.approval-card small{color:var(--mut);font-size:.67rem;line-height:1.5}
.decision-card{margin:1.1rem 0 .3rem;padding:.85rem;border:1px solid var(--line);border-radius:.7rem;
 background:color-mix(in srgb,var(--accent) 3%,var(--bg))}
.decision-card>p{margin:0 0 .65rem;font-size:.82rem;font-weight:800;text-align:center}
.decision-paths{display:grid;grid-template-columns:.7fr 1.3fr;gap:.65rem}
.decision-paths>div{padding:.68rem .75rem;border-radius:.5rem;background:var(--bg)}
.decision-paths span{display:inline-block;margin-bottom:.25rem;padding:.05rem .38rem;border-radius:1rem;
 font-size:.6rem;font-weight:800}
.decision-paths strong,.decision-paths small{display:block}
.decision-paths strong{font-size:.75rem;line-height:1.45}
.decision-paths small{margin-top:.2rem;color:var(--mut);font-size:.64rem;line-height:1.5}
.pass-path{border:1px solid color-mix(in srgb,var(--g-balkavita) 45%,var(--line))}
.pass-path span{color:var(--g-balkavita);background:color-mix(in srgb,var(--g-balkavita) 12%,transparent)}
.review-path{border:1px solid color-mix(in srgb,var(--agent) 35%,var(--line))}
.review-path span{color:var(--agent);background:color-mix(in srgb,var(--agent) 11%,transparent)}
.phase-exit{margin:.75rem 0 0;color:var(--mut);font-size:.69rem;font-weight:600;text-align:center}
.journey-finish{border-color:color-mix(in srgb,var(--g-balkavita) 55%,var(--line))}
.journey-finish>span{color:var(--g-balkavita);background:color-mix(in srgb,var(--g-balkavita) 13%,var(--bg))}
.ocr-journey figcaption{max-width:34rem;margin:1.15rem auto 0;color:var(--mut);font-size:.7rem;
 line-height:1.65;text-align:center}
.audit-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.7rem;margin:1.1rem 0}
.audit-grid>div{padding:.8rem;border-top:2px solid var(--accent);
 background:linear-gradient(180deg,color-mix(in srgb,var(--accent) 6%,var(--bg)),transparent)}
.audit-grid strong,.audit-grid span{display:block}
.audit-grid strong{font-size:.8rem}
.audit-grid span{margin-top:.2rem;color:var(--mut);font-size:.7rem;line-height:1.5}
.ocr-status{position:relative;margin:2.7rem 0;padding:1.25rem 1.35rem 1.2rem;border:1px solid var(--line);
 border-radius:.8rem;background:linear-gradient(120deg,color-mix(in srgb,var(--accent) 10%,var(--bg)),var(--bg))}
.ocr-status:before{content:'≠';position:absolute;right:1rem;top:.2rem;color:var(--accent);opacity:.1;
 font-size:5.5rem;font-weight:800;line-height:1}
.ocr-status .status-label{position:relative;margin:0;color:var(--accent);font-size:.67rem;font-weight:800;
 letter-spacing:.06em}
.ocr-status h2{position:relative;border:0;padding:0;margin:.25rem 0 .4rem;font-size:1.3rem}
.ocr-status p{position:relative;margin:.25rem 0;font-size:.86rem;line-height:1.7}
.ocr-source{display:grid;grid-template-columns:auto 1fr auto;gap:.85rem;align-items:center;
 max-width:40rem;margin:1.1rem 0 0;padding:.9rem 1rem;border:1px solid var(--line);border-radius:.75rem;
 background:linear-gradient(125deg,color-mix(in srgb,var(--accent) 9%,var(--bg)),var(--bg));
 color:var(--fg);text-decoration:none}
.ocr-source:hover{border-color:color-mix(in srgb,var(--accent) 48%,var(--line));
 background:linear-gradient(125deg,color-mix(in srgb,var(--accent) 13%,var(--bg)),var(--bg))}
.ocr-source .source-mark{display:grid;place-items:center;width:2.4rem;height:2.4rem;border-radius:.6rem;
 background:color-mix(in srgb,var(--accent) 13%,var(--bg));color:var(--accent);
 font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.7rem;font-weight:800}
.ocr-source strong,.ocr-source small{display:block}
.ocr-source strong{font-size:.88rem}
.ocr-source small{margin-top:.16rem;color:var(--mut);font-size:.68rem;line-height:1.45}
.ocr-source .source-arrow{color:var(--accent);font-size:1.1rem}
.ocr-version{text-align:right;margin-top:1.5rem}
@media(max-width:650px){
 .ocr-hero{padding:1.65rem 1.25rem 1.55rem}
 .ocr-hero:after{right:-1rem;font-size:9rem}
 .ocr-principle{padding-inline:.25rem}
 .ocr-roles,.flow-grid.two,.flow-grid.three,.audit-grid,.decision-paths{grid-template-columns:1fr}
 .ocr-roles>div{min-height:0}
 .ocr-journey{padding:.7rem;margin-inline:-.35rem;border-radius:.75rem}
 .journey-phase{padding:.85rem}
 .mechanical-run{grid-template-columns:1fr;gap:.35rem}
 .mechanical-run i{transform:rotate(90deg);justify-self:center}
 .fan-label:before,.fan-label:after{width:1.25rem}
 .flow-grid{gap:.55rem}
 .flow-card.wide{width:100%}
 .audit-grid{gap:.45rem}
 .audit-grid>div{padding:.7rem .8rem}
}
/* "अभिलेख एक नजरमा" stats page */
.stats h2{font-size:1.12rem;margin:2rem 0 .7rem;border-top:1px solid var(--line);padding-top:1.25rem}
.stats h2 .sh{font-size:.78rem;color:var(--mut);font-weight:400;margin-left:.4rem}
.snums{display:flex;flex-wrap:wrap;gap:1.4rem;margin:1.2rem 0 .5rem}
.snums .snum{display:flex;flex-direction:column}
.snums .snum b{font-size:1.9rem;line-height:1.05;color:var(--accent);font-variant-numeric:tabular-nums}
.snums .snum span{font-size:.8rem;color:var(--mut);margin-top:.15rem}
.schart{margin:.4rem 0}
.srow{display:grid;grid-template-columns:minmax(7rem,34%) 1fr auto;align-items:center;gap:.65rem;margin:.32rem 0;font-size:.95rem}
.srow .slab{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.srow .slab a{text-decoration:none}
.srow .slab small{color:var(--mut);font-size:.8rem;margin-left:.25rem}
.srow .sbar{background:color-mix(in srgb,var(--line) 55%,transparent);border-radius:3px;height:.7rem;overflow:hidden}
.srow .sbar i{display:block;height:100%;background:var(--accent);border-radius:3px}
.srow .sval{color:var(--mut);font-size:.85rem;font-variant-numeric:tabular-nums}
.cloud{display:flex;flex-wrap:wrap;gap:.15rem .75rem;align-items:baseline;line-height:1.55;margin:1rem 0}
.cloud .cw{text-decoration:none;color:var(--link)}
.cloud .cw:hover{color:var(--accent);text-decoration:underline}
ul.trivia{padding-left:1.1rem;margin:.5rem 0}
ul.trivia li{margin:.45rem 0}
.statnote{margin-top:1.6rem;font-size:.8rem}
/* stats charts (inline SVG) */
.chart{width:100%;height:auto;margin:.6rem 0;overflow:visible}
.chart text{fill:var(--mut);font-family:inherit}
.chart .hb{fill:var(--accent)}
.chart .hn{font-size:9px;text-anchor:middle}
.chart .hx{font-size:8.5px;text-anchor:middle}
.chart .hax{font-size:8.5px;text-anchor:middle;opacity:.8}
.chart.zipf .zl{fill:none;stroke:var(--accent);stroke-width:1.6}
.chart.tree{border-radius:5px}
.chart .tm{stroke:var(--bg);stroke-width:1.2}
.chart .tmt{font-size:9px;fill:#fff;opacity:.92;pointer-events:none}
.tlegend{display:flex;flex-wrap:wrap;gap:.3rem 1rem;margin:.3rem 0 0;font-size:.82rem;color:var(--mut)}
.tlegend .tk{display:inline-flex;align-items:center;gap:.3rem}
.tlegend .tk i{width:.7rem;height:.7rem;border-radius:2px;display:inline-block}
.sigwrap{display:grid;grid-template-columns:repeat(auto-fit,minmax(9rem,1fr));gap:1rem;margin:.6rem 0}
.sigcol h3{font-size:.92rem;margin:0 0 .35rem;padding-left:.5rem;border-left:3px solid var(--accent)}
.sigcol p{margin:0;line-height:1.9}
.sigcol a{text-decoration:none;color:var(--link);margin-right:.5rem;white-space:nowrap}
.sigcol a:hover{color:var(--accent)}
ul.refrains{list-style:none;padding:0;margin:.5rem 0}
ul.refrains li{margin:.4rem 0;padding-left:.2rem}
ul.refrains .rc{display:inline-block;min-width:2.2rem;color:var(--accent);font-variant-numeric:tabular-nums;font-size:.85rem}
@media print{
 header.site,footer.site,.crumb,.seqnav,.downloads,.toc{display:none}
 body{font-size:12pt;color:#000;background:#fff}
 main{max-width:none}
 a{color:#000;text-decoration:none}
 .work h2.sec{color:#000}
}
"""

SEARCH_JS = """(function(){
 var q=document.getElementById('q'),R=document.getElementById('results'),
     H=document.getElementById('hint'),FT=document.getElementById('ft'),
     BASE=(R&&R.getAttribute('data-base'))||(FT&&FT.getAttribute('data-base'))||'';
 // Scoped mode (author/collection/genre pages): tier-1 filters the on-page works
 // list, tier-2 passes a Pagefind filter. Home (no scope attrs) keeps the global behavior.
 var SCOPE=null;
 if(FT){var sa=FT.getAttribute('data-scope-author'),sc=FT.getAttribute('data-scope-collection'),
   sg=FT.getAttribute('data-scope-genre');
   if(sa||sc||sg){SCOPE={};if(sa)SCOPE.author=sa;if(sc)SCOPE.collection=sc;if(sg)SCOPE.genre=sg;}}
 var idx=null,loading=false;
 function norm(s){return (s||'').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().trim();}
 function isDev(s){return /[\\u0900-\\u097f]/.test(s);}

 // Levenshtein distance, bounded: returns >max as soon as the best path exceeds max.
 function lev(a,b,max){
   var la=a.length,lb=b.length;
   if(Math.abs(la-lb)>max) return max+1;
   var prev=[],cur=[],i,j;
   for(j=0;j<=lb;j++) prev[j]=j;
   for(i=1;i<=la;i++){
     cur[0]=i; var rb=i;
     for(j=1;j<=lb;j++){
       var c=a.charCodeAt(i-1)===b.charCodeAt(j-1)?0:1;
       var v=prev[j-1]+c; var d=prev[j]+1; if(d<v)v=d; d=cur[j-1]+1; if(d<v)v=d;
       cur[j]=v; if(v<rb)rb=v;
     }
     if(rb>max) return max+1;
     var t=prev;prev=cur;cur=t;
   }
   return prev[lb];
 }
 function tol(n){return n<=5?1:(n<=9?2:3);}
 // fuzzy similarity of ONE query token to ONE field token (0 = no match)
 function tokenSim(a,b){
   if(a===b) return 64;
   if(b.lastIndexOf(a,0)===0) return 60;         // query token is a prefix (sund->sundari)
   if(b.indexOf(a)>=0) return 54;                // substring
   if(a.length<3) return 0;                      // no fuzzy on 1-2 char tokens
   var t=tol(a.length),d=lev(a,b,t);
   if(d<=t) return 56-d*14;                      // whole-token typo (pagl~pagal)
   if(b.length>a.length){                        // typo of just the word's start (ranks lower)
     d=lev(a,b.slice(0,a.length),t);
     if(d<=t) return 48-d*14;
   }
   return 0;
 }
 // every query token must match some field token within tolerance
 function tokScore(q,f){
   var qt=q.split(' ').filter(Boolean),ft=f.split(' ').filter(Boolean),a,b,tot=0;
   if(!qt.length||!ft.length) return 0;
   for(a=0;a<qt.length;a++){ var best=0;
     for(b=0;b<ft.length;b++){var s=tokenSim(qt[a],ft[b]); if(s>best)best=s;}
     if(!best) return 0; tot+=best; }
   return tot/qt.length;                          // 0..64; always below a real substring (72+)
 }
 function scoreField(q,f){
   if(!q||!f) return 0;
   if(f===q) return 100;                          // exact
   if(f.lastIndexOf(q,0)===0) return 92;          // whole-query prefix
   if((' '+f).indexOf(' '+q)>=0) return 86;       // query starts a word
   if(f.indexOf(q)>=0) return 72;                 // substring anywhere
   if(q.length<3 && q.indexOf(' ')<0) return 0;   // tiny single token: substring only
   return tokScore(q,f);                          // typo-tolerant fallback
 }
 function score(w,qn,qraw){
   var s=scoreField(qraw,w.t||'');               // Devanagari (raw)
   var a=scoreField(qn,w._r); if(a>s)s=a;
   a=scoreField(qn,w._s); if(a>s)s=a;
   a=scoreField(qn,w._c)-8; if(a>s)s=a;           // collection ranks a touch lower
   a=scoreField(qn,w._a)-6; if(a>s)s=a;           // author name
   return s;
 }
 function load(cb){ if(idx){cb();return;} if(loading)return; loading=true;
   fetch(BASE+'search-index.json').then(function(r){return r.json();}).then(function(d){
     idx=d.works; for(var k=0;k<idx.length;k++){var w=idx[k];
       w._r=norm(w.r); w._s=norm(w.s); w._c=norm(w.c); w._a=norm(w.a);}    // precompute once
     cb();});}
 var G=__GENRE_MAP__;
 function dev(n){return String(n).replace(/[0-9]/g,function(d){return '\\u0966\\u0967\\u0968\\u0969\\u096a\\u096b\\u096c\\u096d\\u096e\\u096f'[d];});}
 function renderWorks(list){
   var rows=list.slice(0,60).map(function(w){
     var sub=[w.a,w.c].filter(Boolean).join(' \\u00b7 ');
     var wm=(w.g&&G[w.g]?'<span class="chip g-'+w.g+'">'+G[w.g]+'</span>':'')+
            '<span class=rt>'+(w.m?'~'+dev(w.m)+' \\u092e\\u093f\\u0928\\u0947\\u091f':'\\u091b\\u094b\\u091f\\u094b')+'</span>'+
            (w.f?'<span class=scan>\\ud83d\\udcd6</span>':'');
     return '<li><span class=wmeta>'+wm+'</span><a href="'+BASE+w.p+'">'+w.t+'</a>'+(w.r?' <span class=r>'+w.r+'</span>':'')+
            (sub?'<span class=snip>'+sub+'</span>':'')+'</li>';}).join('');
   R.innerHTML=rows;
   H.textContent=list.length+' शीर्षक';
 }

 // ---- scoped tier-1: live-filter the works list already on the page ----
 var LIS=null;
 function domFilter(qn,qraw){
   if(!LIS) LIS=[].map.call(document.querySelectorAll('ul.works li'),function(li){
     return {li:li,t:li.textContent||'',n:norm(li.textContent||'')};});
   var shown=0;
   LIS.forEach(function(o){
     var hit=!qn||(qraw&&o.t.indexOf(qraw)>=0)||scoreField(qn,o.n)>0;
     o.li.style.display=hit?'':'none'; if(hit)shown++;
   });
   [].forEach.call(document.querySelectorAll('.group'),function(g){   // hide emptied genre groups
     g.style.display=g.querySelector('ul.works li:not([style*="none"])')?'':'none';
   });
   H.textContent=qn?(shown+' कृति मिल्यो'):'';
 }

 // ---- tier-2: full-text via Pagefind, bridged from roman when needed ----
 var pfP=null;
 function pagefind(){ if(pfP) return pfP;
   pfP=import(new URL(BASE+'pagefind/pagefind.js',location.href).href).catch(function(){return null;});
   return pfP; }
 var shard={};
 function getShard(L){ if(shard[L]) return shard[L];
   shard[L]=fetch(BASE+'searchroman/'+L+'.json').then(function(r){return r.ok?r.json():{};},function(){return {};});
   return shard[L]; }
 // xnorm(): the /type/ tool's normalization contract (pipeline translit_keys
 // .normalize / assets/type/engine.js — keep all three in sync). Shard keys are
 // built with the same fold, so naam/nam, chha/cha/xa, shabda/sabda hit exactly.
 var XSUB={ksh:'kC',chh:'C',ch:'C',gy:'J',sh:'s',ph:'P',ee:'i',oo:'u',c:'C',x:'C',f:'P',z:'j',w:'b',v:'b',q:'k'};
 var XRE=/ksh|chh|ch|gy|sh|ph|ee|oo|[cxfzwvq]/g;
 function xnorm(w){
   w=w.toLowerCase().replace(/[^a-z]/g,'').replace(XRE,function(m){return XSUB[m];});
   var o='',i;
   for(i=0;i<w.length;i++) if(w.charAt(i)!==o.charAt(o.length-1)) o+=w.charAt(i);
   if(o.length>1&&o.charAt(o.length-1)==='a') o=o.slice(0,-1);
   return o;
 }
 // roman token -> up to 6 Devanagari candidates (exact > prefix > fuzzy),
 // all matched on normalized keys
 function bridge(tok){ var key=xnorm(tok), L=key.charAt(0).toLowerCase();
   if(!/[a-z]/.test(L)) return Promise.resolve([]);
   return getShard(L).then(function(map){
     if(map[key]) return map[key].slice(0,6);
     var keys=Object.keys(map),i,pre=[];
     for(i=0;i<keys.length;i++) if(keys[i].lastIndexOf(key,0)===0) pre.push(keys[i]);
     if(pre.length){ pre.sort(function(a,b){return a.length-b.length;});
       var out=[]; for(i=0;i<pre.length&&out.length<6;i++) out=out.concat(map[pre[i]]); return out.slice(0,6); }
     if(key.length>=3){ var t=tol(key.length),best=99,bk=null;
       for(i=0;i<keys.length;i++){ var d=lev(key,keys[i],t); if(d<best){best=d;bk=keys[i];} }
       if(bk&&best<=t) return map[bk].slice(0,6); }
     return [];
   });
 }
 // raw query -> array of Pagefind query strings
 function buildQueries(qraw){
   if(isDev(qraw)) return Promise.resolve([qraw]);
   var toks=norm(qraw).split(' ').filter(Boolean);
   if(!toks.length) return Promise.resolve([]);
   return Promise.all(toks.map(bridge)).then(function(per){
     if(toks.length===1) return per[0].slice(0,4);             // OR each candidate
     return [per.map(function(c){return c[0]||'';}).filter(Boolean).join(' ')]; // best-per-token, AND
   });
 }
 var ftSeq=0;
 function fullText(qraw){
   var my=++ftSeq;
   if(!isDev(qraw) && norm(qraw).length<2){FT.innerHTML='';return;}
   FT.innerHTML='<p class=ftmsg>पाठभित्र खोज्दै…</p>';
   Promise.all([pagefind(),buildQueries(qraw)]).then(function(a){
     var pf=a[0],qs=a[1]; if(my!==ftSeq)return; if(!pf){FT.innerHTML='';return;}
     if(!qs.length){FT.innerHTML='<p class=ftmsg>पाठभित्र केही फेला परेन।</p>';return;}
     var opts=SCOPE?{filters:SCOPE}:undefined;
     Promise.all(qs.map(function(s){return pf.search(s,opts);})).then(function(arr){
       if(my!==ftSeq) return;
       var seen={},merged=[];
       arr.forEach(function(res){ if(res&&res.results) res.results.forEach(function(r){
         if(!seen[r.id]){seen[r.id]=1;merged.push(r);} }); });
       Promise.all(merged.slice(0,10).map(function(r){return r.data();})).then(function(ds){
         if(my!==ftSeq) return; renderFT(ds);
       });
     });
   });
 }
 // append ?pagefind-highlight=… using the SURFACE words Pagefind marked in the excerpt
 // (the real on-page forms — not the stemmed query), so the work page can scroll+highlight.
 function hlUrl(url,excerpt){
   var seen={},m,re=/<mark>([\\s\\S]*?)<\\/mark>/g;
   while((m=re.exec(excerpt))){
     var w=m[1].replace(/<[^>]*>/g,'').replace(/[^\\u0900-\\u097f ]/g,' ').trim();
     w.split(/\\s+/).forEach(function(t){if(t)seen[t]=1;});
   }
   var ks=Object.keys(seen).slice(0,6);
   if(!ks.length) return url;
   var qp=ks.map(function(t){return 'pagefind-highlight='+encodeURIComponent(t);}).join('&');
   return url+(url.indexOf('?')<0?'?':'&')+qp;
 }
 function renderFT(ds){
   if(!ds||!ds.length){FT.innerHTML='<p class=ftmsg>पाठभित्र केही फेला परेन।</p>';return;}
   var h='<h2 class=fthead>पाठभित्र खोजी</h2><ul class=ftlist>';
   ds.forEach(function(d){
     var t=(d.meta&&d.meta.title)||d.url;
     h+='<li><a href="'+hlUrl(d.url,d.excerpt)+'">'+t+'</a><p class=ex>'+d.excerpt+'</p></li>';
   });
   FT.innerHTML=h+'</ul>';
 }

 var ftTimer=null;
 function search(){
   var qraw=q.value.trim(),qn=norm(qraw);
   if(!qn){
     if(SCOPE){domFilter('','');}else{R.innerHTML='';H.textContent=idx?(idx.length+' कृति'):'';}
     FT.innerHTML=''; return;
   }
   if(SCOPE){
     domFilter(qn,qraw);                          // tier-1: narrow the visible list
   }else{
     load(function(){
       var hit=[],k;
       for(k=0;k<idx.length;k++){var sc=score(idx[k],qn,qraw); if(sc>0)hit.push([sc,idx[k]]);}
       hit.sort(function(a,b){return b[0]-a[0];});
       renderWorks(hit.map(function(x){return x[1];}));
     });
   }
   if(ftTimer)clearTimeout(ftTimer);
   ftTimer=setTimeout(function(){fullText(qraw);},250);
 }
 q.addEventListener('input',search);
 q.addEventListener('focus',function(){if(SCOPE)return;load(function(){if(!q.value)H.textContent=idx.length+' कृति';});});
 // deep link: /?q=term (e.g. a word clicked on the stats page) runs the search on load
 var dl=location.search.match(/[?&]q=([^&]*)/);
 if(dl){ try{q.value=decodeURIComponent(dl[1].replace(/\\+/g,' '));}catch(e){} q.focus(); search(); }
})();
"""

# Theme toggle (persisted) + scroll progress bar. Loaded (deferred) on every page.
UI_JS = """(function(){
 var root=document.documentElement,mq=matchMedia('(prefers-color-scheme:dark)');
 function eff(){return root.getAttribute('data-theme')||(mq.matches?'dark':'light');}
 var b=document.getElementById('themed');
 if(b){
   var sync=function(){b.textContent=eff()==='dark'?'☀':'☾';};   // sun in dark, moon in light
   sync();
   b.addEventListener('click',function(){
     var n=eff()==='dark'?'light':'dark';
     root.setAttribute('data-theme',n);
     try{localStorage.setItem('theme',n);}catch(e){}
     sync();});
   if(mq.addEventListener) mq.addEventListener('change',function(){if(!root.getAttribute('data-theme'))sync();});
 }
 var bar=document.getElementById('prog');
 if(bar){
   var pend=false,upd=function(){pend=false;
     var h=document.documentElement,m=h.scrollHeight-h.clientHeight,y=h.scrollTop||document.body.scrollTop;
     bar.style.width=(m>0?(y/m*100):0)+'%';};
   addEventListener('scroll',function(){if(!pend){pend=true;requestAnimationFrame(upd);}},{passive:true});
   addEventListener('resize',upd); upd();
 }
 // Arrived from a search result (?pagefind-highlight=…) → load Pagefind's highlighter,
 // which marks + scrolls to the match inside [data-pagefind-body]. Otherwise pages stay JS-free.
 if(location.search.indexOf('pagefind-highlight=')>=0){
   import('/pagefind/pagefind-highlight.js').then(function(m){
     var P=m&&(m.default||window.PagefindHighlight); if(!P) return;
     new P({highlightParam:'pagefind-highlight'});
     setTimeout(function(){var f=document.querySelector('mark.pagefind-highlight');
       if(f) f.scrollIntoView({block:'center'});},60);   // land on the matched passage
   }).catch(function(){});
 }
})();
"""

# genre-id -> Devanagari name, injected into the search JS for result chips
# (substituted BEFORE hashing so SEARCH_VER tracks the final text)
SEARCH_JS = SEARCH_JS.replace(
    "__GENRE_MAP__", json.dumps({g: v[0] for g, v in GENRE.items()}, ensure_ascii=False))

# content-hash cache-busting: bumps automatically whenever the asset changes, so
# returning visitors (phones especially) never get served a stale CSS/JS.
def _ver(s): return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]
CSS_VER, UI_VER, SEARCH_VER = _ver(CSS), _ver(UI_JS), _ver(SEARCH_JS)


def build(archive_base: str):
    works = json.loads((ARCHIVES / "index.json").read_text(encoding="utf-8"))["works"]
    # load metadata + text per work
    recs = []
    extras = {}   # path -> reading time (~200 wpm) + has-scan flag, for list items
    for w in works:
        wd = ROOT / w["path"]
        meta = json.loads((wd / "metadata.json").read_text(encoding="utf-8"))
        text = (wd / "text.txt").read_text(encoding="utf-8")
        recs.append((w, meta, text))
        extras[w["path"]] = {"min": round(len(text.split()) / 200),
                             "pdf": bool(meta.get("formats", {}).get("pdf"))}

    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir(parents=True)
    # self-hosted font @font-face (if fetched) prepended to the stylesheet
    ff = ROOT / "assets" / "fonts" / "fontface.css"
    css = (ff.read_text(encoding="utf-8") + "\n" + CSS) if ff.exists() else CSS
    (SITE / "style.css").write_text(css, encoding="utf-8")
    (SITE / "search.js").write_text(SEARCH_JS, encoding="utf-8")
    (SITE / "ui.js").write_text(UI_JS, encoding="utf-8")
    fdir = SITE / "fonts"; fdir.mkdir(exist_ok=True)
    for f in sorted((ROOT / "assets" / "fonts").glob("*.woff2")):
        shutil.copy(f, fdir / f.name)
    # bundle the Copyright Act PDF (the legal basis) with the site
    act_src = ROOT / "Pratilipi Adhikar Ain_2059(1)_1573120368.pdf"
    if act_src.exists():
        (SITE / "docs").mkdir(exist_ok=True)
        shutil.copy(act_src, SITE / "docs" / "pratilipi-adhikar-ain-2059.pdf")
    # logo: favicons + the header न mark in its four states (light/dark ×
    # normal/pressed). Pre-sized/recolored in assets/logo/ by make_logo_assets.py
    # so the build stays pure-stdlib (no PIL in CI).
    logo = ROOT / "assets" / "logo"
    for src, dst in [("favicon-48.png", "favicon.png"),
                     ("favicon-180.png", "apple-touch-icon.png"),
                     ("final-logo.png", "logo.png"),
                     ("logo-pressed.png", "logo-pressed.png"),
                     ("final-logo-dark.png", "logo-dark.png"),
                     ("logo-pressed-dark.png", "logo-pressed-dark.png")]:
        if (logo / src).exists():
            shutil.copy(logo / src, SITE / dst)
    # vendored pdf.js — lazy, range-loading reader for works that have a source PDF
    pjs = ROOT / "assets" / "pdfjs"
    if pjs.exists():
        pdir = SITE / "pdfjs"; pdir.mkdir(exist_ok=True)
        for f in pjs.iterdir():
            if f.is_file():
                shutil.copy(f, pdir / f.name)

    # group works by author; reading order within an author = genre group then title
    def aslug(w): return Path(w["path"]).relative_to("archives").parts[1]
    def gkey(meta):
        g = meta["genre"][0] if meta["genre"] else "kavita"
        return (ORDER.index(g) if g in ORDER else len(ORDER), meta["title"])
    by_author = {}
    for rec in recs:
        by_author.setdefault(aslug(rec[0]), []).append(rec)
    for a in by_author:
        by_author[a].sort(key=lambda r: gkey(r[1]))
    author_order = sorted(by_author, key=lambda a: -len(by_author[a]))   # most works first
    def ainfo(slug, sample_meta):
        if slug in AUTHORS:
            return AUTHORS[slug]
        au = sample_meta["author"]
        return (au["name"], au.get("name_roman") or "", "")

    # one list item for every browse list: title + roman + right-floated catalogue
    # bits (genre chip where the list isn't already genre-grouped, reading time,
    # 📖 when a source scan exists). .wmeta floats right, so it goes FIRST in the
    # <li> — ul.works is shared with the home search results, whose .snip is a block.
    def work_li(w, meta, href, *, chip=False):
        ex = extras[w["path"]]
        g = meta["genre"][0] if meta["genre"] else ""
        rt = "छोटो" if ex["min"] == 0 else f"~{_dev(ex['min'])} मिनेट"
        wm = ((f'<span class="chip g-{g}">{esc(GENRE.get(g, (g, ""))[0])}</span>' if chip and g else "")
              + f'<span class="rt">{rt}</span>'
              + ('<span class="scan" title="मूल पृष्ठ स्क्यान उपलब्ध">\U0001F4D6</span>' if ex["pdf"] else ""))
        return (f'<li><span class="wmeta">{wm}</span><a href="{href}">{esc(meta["title"])}</a>'
                f'<span class="r">{esc(meta.get("title_roman") or "")}</span></li>')

    # collections (only some authors have them): name -> [(w,meta)], with a URL slug
    collections, cslug = {}, {}
    for w, meta, _ in recs:
        for cn in (w.get("collection") or []):
            collections.setdefault(cn, []).append((w, meta))
    for cn in collections:
        cslug[cn] = cslugify(cn)
        collections[cn].sort(key=lambda x: x[1]["title"])

    # ---- per-work reading pages (prev/next within the same author) ----
    search_rows = []
    # roman→Devanagari bridge: every Devanagari word in the poem bodies (excl. danda)
    _DEVWORD = re.compile(r"[ऀ-ॣ०-ॿ]+")
    from collections import Counter
    ft_words = Counter()                                     # word -> corpus count
    for aslug_, arecs in by_author.items():
        aname = ainfo(aslug_, arecs[0][1])[0]
        for i, (w, meta, text) in enumerate(arecs):
            ft_words.update(_DEVWORD.findall(text))          # bridge vocab (poem body)
            rel = Path(w["path"]).relative_to("archives")    # authors/<author>/<slug>
            out_dir = SITE / rel
            out_dir.mkdir(parents=True, exist_ok=True)
            depth = len(rel.parts); up = "../" * depth
            coll = w.get("collection") or []
            # Pagefind filters power the author/collection-scoped search. One EMPTY span
            # per filter using the filter[attribute] value syntax — empty elements add
            # nothing to the searchable content. (The inline "name:value" comma syntax is
            # NOT supported — tried; everything lands in one polluted value.)
            pf_spans = (f'<span data-pagefind-filter="author[data-v]" '
                        f'data-v="{esc(meta["author"]["name"])}"></span>')
            pf_spans += "".join(f'<span data-pagefind-filter="collection[data-v]" '
                                f'data-v="{esc(cn)}"></span>' for cn in coll)
            if meta["genre"]:
                pf_spans += (f'<span data-pagefind-filter="genre[data-v]" '
                             f'data-v="{esc(meta["genre"][0])}"></span>')
            verse = (meta["genre"][0] if meta["genre"] else "") not in PROSE_GENRES
            gdev = GENRE.get(meta["genre"][0], (meta["genre"][0], ""))[0] if meta["genre"] else ""
            meta_bits = [f'<a href="{up}authors/{aslug_}/#{meta["genre"][0]}">{esc(gdev)}</a>' if gdev else ""]
            for cn in coll:
                meta_bits.append(f'सङ्ग्रह: <a href="{up}collections/{cslug[cn]}/">{esc(cn)}</a>')
            # Downloads: link to --archive-base if set (lean site), else bundle in.
            # The PDF is always bundled/resolved even though it isn't in the bottom
            # downloads line — the pdf/ viewer range-loads ../<fn>, and the top
            # "PDF डाउनलोड" button links it.
            fmts = meta.get("formats", {}); src_dir = ROOT / w["path"]
            pdf_fn = fmts.get("pdf")
            fhref = {}
            for k in ("pdf", "epub", "txt"):
                fn = fmts.get(k)
                if not fn:
                    continue
                if archive_base:
                    fhref[k] = f'{archive_base.rstrip("/")}/{rel}/{esc(fn)}'
                elif (src_dir / fn).exists():
                    shutil.copy(src_dir / fn, out_dir / fn)
                    fhref[k] = esc(fn)
            dls = [f'<a href="{fhref[k]}">{lab}</a>'
                   for k, lab in [("epub", "EPUB"), ("txt", "मूल पाठ (TXT)")] if k in fhref]
            pdfbtn = ""
            if pdf_fn:
                dlbtn = (f'\n  <a class="pdfread" href="{fhref["pdf"]}" download>⬇ PDF डाउनलोड</a>'
                         if "pdf" in fhref else "")
                pdfbtn = ('\n  <p class="pdfacts"><a class="pdfread" href="pdf/">\U0001F4D6 मूल पृष्ठ हेर्नुहोस्</a>'
                          f'{dlbtn}</p>')
            src_name = meta["source"].get("name") or ""
            src_url = meta["source"].get("url") or ""
            src_html = (f'<a href="{esc(src_url)}" rel="nofollow">{esc(src_name or src_url)}</a>'
                        if src_url else (esc(src_name) or "—"))
            nav_seq = []
            if i > 0:
                pid = arecs[i-1][0]["id"]; pt = arecs[i-1][1]["title"]
                nav_seq.append(f'<a class="pv" href="../{esc(pid)}/"><span class="lbl">अघिल्लो</span>← {esc(pt)}</a>')
            if i < len(arecs) - 1:
                nid = arecs[i+1][0]["id"]; nt = arecs[i+1][1]["title"]
                nav_seq.append(f'<a class="nx" href="../{esc(nid)}/"><span class="lbl">अर्को</span>{esc(nt)} →</a>')
            ld = json.dumps({"@context": "https://schema.org", "@type": "CreativeWork",
                             "name": meta["title"], "author": {"@type": "Person", "name": meta["author"]["name"]},
                             "inLanguage": "ne", "isAccessibleForFree": True,
                             "license": "https://creativecommons.org/publicdomain/mark/1.0/",
                             "url": SITE_URL + str(rel) + "/"}, ensure_ascii=False)
            downloads = (f'<p class="downloads">डाउनलोड: {" ".join(dls) if dls else "—"}<br>'
                         f'<span style="font-size:.78rem">स्रोत: {src_html} · सार्वजनिक डोमेन (असत्यापित)</span></p>')
            seqnav = f'<nav class="seqnav">{"".join(nav_seq)}</nav>'
            title_full = f"{meta['title']} — {meta['author']['name']}"
            full_html = work_html(text, verse)
            # Very long works: split into a contents page + one page per section, so the
            # browser never loads (or scrolls) the whole epic at once.
            pages = paginate_work(text, balance=len(full_html) > 150000)
            if not pages:
                body = f"""<nav class="crumb"><a href="{up}authors/{aslug_}/">← {esc(aname)}</a></nav>
<article>
  <h1>{esc(meta['title'])}</h1>
  <p class="byline">{esc(meta['author']['name'])}</p>
  <p class="meta">{" · ".join(b for b in meta_bits if b)}</p>{pdfbtn}
  <div class="work {'verse' if verse else 'prose'}" data-pagefind-body>{pf_spans}
{full_html}
  </div>
  {downloads}
</article>
{seqnav}"""
                (out_dir / "index.html").write_text(
                    page(title_full, body, desc=title_full, css_depth=depth,
                         active="works", canon=str(rel) + "/",
                         extra_head=f'<script type="application/ld+json">{ld}</script>\n'),
                    encoding="utf-8")
            else:
                N = len(pages)
                toc = "".join(f'<li><a href="{k+1}/">{esc(lbl)}</a></li>'
                              for k, (lbl, _) in enumerate(pages))
                toc_body = f"""<nav class="crumb"><a href="{up}authors/{aslug_}/">← {esc(aname)}</a></nav>
<article>
  <h1>{esc(meta['title'])}</h1>
  <p class="byline">{esc(meta['author']['name'])}</p>
  <p class="meta">{" · ".join(b for b in meta_bits if b)}</p>{pdfbtn}
  <p class="tochint">{_dev(N)} खण्डमा विभाजित — कुनै पनि खण्ड छानेर पढ्नुहोस् :</p>
  <ol class="toc">{toc}</ol>
  {downloads}
</article>
{seqnav}"""
                (out_dir / "index.html").write_text(
                    page(title_full, toc_body, desc=title_full, css_depth=depth,
                         active="works", canon=str(rel) + "/",
                         extra_head=f'<script type="application/ld+json">{ld}</script>\n'),
                    encoding="utf-8")
                for k, (lbl, content) in enumerate(pages):
                    cdir = out_dir / str(k + 1); cdir.mkdir(parents=True, exist_ok=True)
                    cdepth = depth + 1; cup = "../" * cdepth
                    cnav = [(f'<a class="pv" href="../{k}/"><span class="lbl">अघिल्लो</span>← {esc(pages[k-1][0])}</a>'
                             if k > 0 else
                             '<a class="pv" href="../"><span class="lbl">सूची</span>← सूची</a>')]
                    if k < N - 1:
                        cnav.append(f'<a class="nx" href="../{k+2}/"><span class="lbl">अर्को</span>{esc(pages[k+1][0])} →</a>')
                    cbody = f"""<nav class="crumb"><a href="{cup}authors/{aslug_}/">← {esc(aname)}</a> · <a href="../">{esc(meta['title'])} (सूची)</a></nav>
<article>
  <h1>{esc(lbl)}</h1>
  <p class="byline"><a href="../">{esc(meta['title'])}</a> · {esc(meta['author']['name'])} · {_dev(k+1)}/{_dev(N)}</p>
  <div class="work {'verse' if verse else 'prose'}" data-pagefind-body>{pf_spans}
{work_html(content, verse)}
  </div>
</article>
<nav class="seqnav">{''.join(cnav)}</nav>"""
                    (cdir / "index.html").write_text(
                        page(f"{lbl} — {title_full}", cbody, desc=f"{lbl} — {title_full}",
                             css_depth=cdepth, active="works", canon=str(rel) + f"/{k+1}/"),
                        encoding="utf-8")
            if pdf_fn:
                write_pdf_reader(out_dir, depth, rel, pdf_fn, meta, aslug_, aname, archive_base)
            search_rows.append({"t": meta["title"], "r": meta.get("title_roman") or "",
                                "s": w["id"].replace("_", " "),
                                "a": meta["author"].get("name_roman") or "",
                                "c": "; ".join(coll) if coll else "",
                                "g": meta["genre"][0] if meta["genre"] else "",
                                "m": extras[w["path"]]["min"],
                                "f": 1 if extras[w["path"]]["pdf"] else 0,
                                "p": str(rel) + "/"})

    # ---- search index ----
    (SITE / "search-index.json").write_text(
        json.dumps({"works": search_rows}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")

    # ---- roman→Devanagari bridge shards (turns a roman full-text query into the
    # Devanagari term(s) we feed Pagefind). Sharded by first roman letter so a query
    # downloads only its shard (~tens of KB), not the whole ~2 MB map. ----
    rmap = {}
    for wword in ft_words:
        # every word is filed under its normalized keys (translit_keys.word_keys:
        # normalize(romanize(w)) + medial-schwa and क्ष aliases), so spelling
        # variants — naam/nam, chha/cha/xa, devkota — hit as EXACT key matches.
        # The word's PRIMARY key ranks its bucket entry above alias hits.
        keys = translit_word_keys(wword)
        primary = normalize_key(wword)
        for r in keys:
            if r:
                rmap.setdefault(r, {})[wword] = (r != primary)
    shards = {}
    for r, ws in rmap.items():
        key = r[0].lower() if r[:1].isalpha() else "_"       # keys may start with C/J/P sentinels
        ranked = sorted(ws, key=lambda w: (ws[w], -ft_words[w], w))   # primary first, then corpus freq
        shards.setdefault(key, {})[r] = ranked[:12]          # cap candidates per key
    rdir = SITE / "searchroman"; rdir.mkdir(exist_ok=True)
    for key, m in shards.items():
        (rdir / f"{key}.json").write_text(
            json.dumps(m, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # ---- collection pages ----
    cdir = SITE / "collections"
    for cn, items in collections.items():
        d = cdir / cslug[cn]; d.mkdir(parents=True, exist_ok=True)
        lis = "".join(
            work_li(w, meta, f'../../{esc(Path(w["path"]).relative_to("archives").as_posix())}/',
                    chip=True) for w, meta in items)
        cb = (f'<nav class="crumb"><a href="../../">← {esc(SITE_NAME)}</a></nav>'
              f'<h1>{esc(cn)}</h1><p class="lead">{len(items)} कृति।</p>'
              f'<p><input id="q" type="search" placeholder="यस सङ्ग्रहभित्र खोज्नुहोस् — शीर्षक वा पाठ" '
              f'autocomplete="off" aria-label="खोज"></p><p class="hint" id="hint"></p>'
              f'<div id="ft" data-base="../../" data-scope-collection="{esc(cn)}"></div>'
              f'<ul class="works">{lis}</ul>'
              f'<script src="../../search.js?v={SEARCH_VER}" defer></script>')
        (d / "index.html").write_text(
            page(f"{cn} — सङ्ग्रह", cb, css_depth=2, active="works",
                 desc=f"{cn} — {len(items)} कृति", canon=f"collections/{cslug[cn]}/"), encoding="utf-8")

    # ---- genre pages (corpus-wide shelves: /genres/<gid>/, grouped by author) ----
    by_genre = {}
    for w, meta, _ in recs:
        by_genre.setdefault(meta["genre"][0] if meta["genre"] else "kavita", []).append((w, meta))
    genres_present = [g for g in ORDER + sorted(k for k in by_genre if k not in ORDER)
                      if by_genre.get(g)]

    def genre_cards(base):
        cards = "".join(
            f'<a class="card g-{g}" href="{base}genres/{g}/">'
            f'<b>{esc(GENRE.get(g, (g, ""))[0])}</b><span class="en">{esc(GENRE.get(g, (g, ""))[1])}</span>'
            f'<span class="n">{_dev(len(by_genre[g]))} कृति</span></a>' for g in genres_present)
        return f'<div class="shelf">{cards}</div>'

    for g in genres_present:
        gdev, gen = GENRE.get(g, (g, ""))
        gitems = by_genre[g]
        groups_html = []
        for a in author_order:
            aitems = sorted((x for x in gitems if aslug(x[0]) == a), key=lambda x: x[1]["title"])
            if not aitems:
                continue
            aname = ainfo(a, aitems[0][1])[0]
            lis = "".join(work_li(w, meta, f'../../authors/{a}/{esc(w["id"])}/') for w, meta in aitems)
            groups_html.append(
                f'<div class="group"><h2><a href="../../authors/{a}/">{esc(aname)}</a> '
                f'<span class="count">{len(aitems)}</span></h2><ul class="works">{lis}</ul></div>')
        gb = (f'<nav class="crumb"><a href="../../">← {esc(SITE_NAME)}</a></nav>'
              f'<h1>{esc(gdev)}</h1><p class="byline">{esc(gen)}</p>'
              f'<p class="lead">{_dev(len(gitems))} कृति।</p>'
              f'<p><input id="q" type="search" placeholder="{esc(gdev)}भित्र खोज्नुहोस् — शीर्षक वा पाठ" '
              f'autocomplete="off" aria-label="खोज"></p><p class="hint" id="hint"></p>'
              f'<div id="ft" data-base="../../" data-scope-genre="{g}"></div>'
              f'{"".join(groups_html)}'
              f'<script src="../../search.js?v={SEARCH_VER}" defer></script>')
        gdir = SITE / "genres" / g; gdir.mkdir(parents=True, exist_ok=True)
        (gdir / "index.html").write_text(
            page(f"{gdev} — {SITE_NAME}", gb, css_depth=2, active="works",
                 desc=f"{gdev} ({gen}) — {len(gitems)} कृति", canon=f"genres/{g}/"),
            encoding="utf-8")

    # ---- genres index (/genres/): the full shelf wall ----
    gi_body = (f'<nav class="crumb"><a href="../">← {esc(SITE_NAME)}</a></nav>'
               f'<h1>विधा</h1><p class="lead">{_dev(len(genres_present))} विधा · {_dev(len(recs))} कृति।</p>'
               + genre_cards("../"))
    (SITE / "genres").mkdir(parents=True, exist_ok=True)
    (SITE / "genres" / "index.html").write_text(
        page("विधा — " + SITE_NAME, gi_body, css_depth=1, active="works",
             desc=f"विधा अनुसार ब्राउज गर्नुहोस् — {len(recs)} कृति", canon="genres/"),
        encoding="utf-8")

    # ---- per-author pages (browse: TOC + collections + genre groups) ----
    for aslug_ in author_order:
        arecs = by_author[aslug_]
        aname, aroman, adates = ainfo(aslug_, arecs[0][1])
        bg = {}
        for w, meta, _ in arecs:
            bg.setdefault(meta["genre"][0] if meta["genre"] else "kavita", []).append((w, meta))
        present = [g for g in ORDER + [k for k in bg if k not in ORDER] if bg.get(g)]
        toc = " ".join(f'<a href="#{g}">{esc(GENRE.get(g,(g,""))[0])} <span class="count">{len(bg[g])}</span></a>'
                       for g in present)
        acolls = [cn for cn in sorted(collections, key=lambda c: -len(collections[c]))
                  if any(aslug(w) == aslug_ for w, _ in collections[cn])]
        coll_links = " · ".join(f'<a href="../../collections/{cslug[cn]}/">{esc(cn)}</a>' for cn in acolls)
        groups_html = []
        for g in present:
            items = sorted(bg[g], key=lambda x: x[1]["title"])
            dev, en = GENRE.get(g, (g, ""))
            lis = "".join(work_li(w, meta, f'{esc(w["id"])}/') for w, meta in items)
            groups_html.append(
                f'<div class="group" id="{g}"><h2><a href="../../genres/{g}/">{esc(dev)}</a> '
                f'<span class="count">{en} · {len(items)}</span></h2>'
                f'<ul class="works">{lis}</ul></div>')
        author_body = f"""<nav class="crumb"><a href="../../">← {esc(SITE_NAME)}</a></nav>
<h1>{esc(aname)}</h1>
<p class="byline">{esc(aroman)}{' · ' + adates if adates else ''}</p>
<p class="lead">{len(arecs)} कृति।</p>
<p><input id="q" type="search" placeholder="{esc(aname)}का कृतिभित्र खोज्नुहोस् — शीर्षक वा पाठ (रोमनमा पनि)" autocomplete="off" aria-label="खोज"></p>
<p class="hint" id="hint"></p>
<div id="ft" data-base="../../" data-scope-author="{esc(aname)}"></div>
<p class="toc">{toc}</p>
{f'<p class="meta">सङ्ग्रह: {coll_links}</p>' if coll_links else ''}
{''.join(groups_html)}
<script src="../../search.js?v={SEARCH_VER}" defer></script>"""
        adir = SITE / "authors" / aslug_; adir.mkdir(parents=True, exist_ok=True)
        (adir / "index.html").write_text(
            page(f"{aname} — कृतिहरू", author_body, css_depth=2, active="works",
                 desc=f"{aname}का {len(arecs)} कृति", canon=f"authors/{aslug_}/"),
            encoding="utf-8")

    # ---- authors index ----
    def author_li(a, base):
        n, r, d = ainfo(a, by_author[a][0][1])
        return (f'<li><a href="{base}authors/{a}/">{esc(n)}</a>'
                f'<span class="r">{esc(r)} · {len(by_author[a])} कृति</span></li>')
    ai_body = (f'<h1>लेखकहरू</h1><p class="lead">{len(by_author)} लेखक · {len(recs)} कृति।</p>'
               f'<ul class="works">{"".join(author_li(a, "../") for a in author_order)}</ul>')
    (SITE / "authors").mkdir(parents=True, exist_ok=True)
    (SITE / "authors" / "index.html").write_text(
        page("लेखकहरू — " + SITE_NAME, ai_body, css_depth=1, active="works",
             desc=f"{len(by_author)} लेखक · {len(recs)} कृति", canon="authors/"),
        encoding="utf-8")

    # ---- home: search + authors ----
    home_body = f"""<h1>{SITE_TAGLINE}</h1>
<p class="tagline-en">{SITE_TAGLINE_EN}</p>
<p class="lead">{str(len(by_author)).translate(_DEVNUM)} लेखकका {str(len(recs)).translate(_DEVNUM)} कृति — नि:शुल्क, सधैँभरि। दर्ता छैन, विज्ञापन छैन।</p>
<p><input id="q" type="search" placeholder="खोज्नुहोस् — शीर्षक, पाठ वा रोमन" autocomplete="off" aria-label="खोज"></p>
<p class="hint" id="hint">जस्तै: <a href="?q=pagal">pagal</a><a href="?q=muna madan">muna madan</a><a href="?q=hunxa">hunxa</a><a href="?q=फूल">फूल</a></p>
<ul class="works" id="results" data-base=""></ul>
<div id="ft"></div>
<div class="home-sec"><h2><a href="genres/">विधा</a></h2>{genre_cards("")}</div>
<div class="home-sec"><h2>सङ्ग्रह</h2><div class="shelf">{"".join(
        f'<a class="card g-{items[0][1]["genre"][0] if items[0][1]["genre"] else "kavita"}" href="collections/{cslug[cn]}/">'
        f'<b>{esc(cn)}</b><span class="en">{esc(ainfo(aslug(items[0][0]), items[0][1])[0])}</span>'
        f'<span class="n">{_dev(len(items))} कृति</span></a>'
        for cn, items in sorted(collections.items(), key=lambda x: -len(x[1])))}</div></div>
<div class="home-sec"><h2>लेखकहरू</h2><ul class="works">{"".join(author_li(a, "") for a in author_order)}</ul></div>
<p class="statlink"><a href="stats/">📊 अभिलेख एक नजरमा — तथ्याङ्क र रोचक तथ्य →</a></p>
<script src="search.js?v={SEARCH_VER}" defer></script>"""
    (SITE / "index.html").write_text(
        page(SITE_NAME, home_body, desc="", css_depth=0, active="home", canon=""),
        encoding="utf-8")

    # ---- about ----
    about_body = f"""<h1>बारेमा</h1>
<p class="lead">{SITE_TAGLINE}।</p>
<p>यो अभिलेखले सार्वजनिक डोमेनमा रहेका नेपाली साहित्यिक कृतिहरूलाई संरक्षण, डिजिटलीकरण र
नि:शुल्क पहुँच प्रदान गर्ने लक्ष्य राख्छ। पाठहरू मूल रूपमै राखिएका छन्; OCR/स्क्यान त्रुटि मात्र
सच्याइन्छ, लेखकका शब्द बदलिँदैनन्।</p>
<p class="aboutcall">स्क्यान गरिएका पुस्तकबाट पाठ तयार गर्दा हामी बहु-OCR, निश्चित भूमिकाका
एआई एजेन्ट, स्वतन्त्र पुनःजाँच र दुई स्वीकृति ढोका प्रयोग गर्छौँ।
<a href="ocr/">हाम्रो OCR प्रक्रिया र कार्यान्वयन ग्राफ हेर्नुहोस् →</a></p>
<h2>सार्वजनिक डोमेन</h2>
<p>नेपालको प्रतिलिपि अधिकार ऐन, २०५९ अनुसार कुनै कृतिको प्रतिलिपि अधिकार रचयिताको जीवनभर
र निजको मृत्यु भएको वर्षदेखि थप ५० वर्षसम्म कायम रहन्छ। यो अवधि पूरा भएपछि कृति
सार्वजनिक डोमेनमा प्रवेश गर्छ — अर्थात् त्यसपछि जोसुकैले स्वतन्त्र रूपमा पढ्न, प्रतिलिपि गर्न,
वितरण गर्न र प्रयोग गर्न पाउँछन्। त्यसैले यस अभिलेखमा रचयिताको मृत्यु भएको ५० वर्षभन्दा बढी
भइसकेका, सार्वजनिक डोमेनका कृतिहरू मात्र राखिन्छन्।</p>
<blockquote class="law">“(१) यस ऐन बमोजिम रचयितालाई प्राप्त आर्थिक र नैतिक अधिकार रचयिताको जीवनभर र निजको मृत्यु भएकोमा मृत्यु भएको वर्षबाट पचास वर्षसम्म संरक्षित हुनेछ ।”
<span class="cite">— <a href="docs/pratilipi-adhikar-ain-2059.pdf">प्रतिलिपि अधिकार ऐन, २०५९</a>, दफा १४ (प्रतिलिपि अधिकार संरक्षणको अवधि), उपदफा (१)</span></blockquote>
<p class="meta">पूरा ऐन यहाँ हेर्न/डाउनलोड गर्न सकिन्छ: <a href="docs/pratilipi-adhikar-ain-2059.pdf">प्रतिलिपि अधिकार ऐन, २०५९ (PDF)</a>।</p>
<p>हाल यहाँ {len(by_author)} लेखकका {len(recs)} कृति छन्। स्रोत: Kavita Kosh, inepal.org,
Internet Archive, sahityasangraha.com। प्रत्येक कृति HTML, मूल पाठ (TXT){' र EPUB' if any(m.get('formats',{}).get('epub') for _,m,_ in recs) else ''} मा उपलब्ध छ।</p>
<p class="meta"><a href="type/">टाइप उपकरण</a>को शब्द-तथ्याङ्क: यही अभिलेखका कृतिहरू +
<a href="https://huggingface.co/datasets/ai4bharat/Aksharantar" rel="external">AI4Bharat Aksharantar</a> (CC-BY)।
सबै रूपान्तरण ब्राउजरमै हुन्छ — केही पनि कतै पठाइँदैन।</p>
<p class="meta">OCR सम्पन्न पाठ र प्रुफरिड पाठ फरक अवस्था हुन्। मूल स्रोतसँग औपचारिक रूपमा
फेरि जाँच गरेपछि मात्र कुनै कृतिलाई प्रुफरिड मानिन्छ।</p>
<h2>आफ्ना कृति थप्न चाहनुहुन्छ?</h2>
<p>यदि तपाईं आफ्ना कृति यस अभिलेखमा थप्न चाहनुहुन्छ भने <a href="mailto:mail@nepaliarchives.org">mail@nepaliarchives.org</a> मा इमेल गर्नुहोस्।</p>
<p>तर ध्यान दिनुहोस् — यसरी कृति पठाएपछि तपाईंले त्यस कृतिमाथिको आफ्ना सम्पूर्ण अधिकार र लाइसेन्स पूर्ण रूपमा त्याग्नुहुनेछ। यस अभिलेखको नीति <strong>“कुनै लाइसेन्स छैन” (No license)</strong> हो — यहाँ राखिएका सबै कृति कुनै पनि अधिकार सुरक्षित नराखी, जोसुकैले स्वतन्त्र रूपमा पढ्न, प्रतिलिपि गर्न, वितरण गर्न र प्रयोग गर्न पाउने गरी राखिएका छन्। तपाईंले पठाउनुभएको कृति पनि ठ्याक्कै सोही नीति अन्तर्गत — कुनै लाइसेन्स बिना — सार्वजनिक गरिनेछ। यो निर्णय फिर्ता हुँदैन।</p>"""
    (SITE / "about.html").write_text(
        page("बारेमा — " + SITE_NAME, about_body, css_depth=0, active="about", canon="about.html"),
        encoding="utf-8")

    # ---- scanned-book OCR process ----
    write_ocr_page()

    # ---- typing tool ----
    write_type_page()

    # ---- पात्रो (daily panchanga + rashifal, from committed JSON) ----
    patro_ok = write_patro_page()

    # ---- stats page (fun, build-time, isolated) ----
    stats.build_stats_page(recs, collections, page=page, GENRE=GENRE,
                           PROSE_GENRES=PROSE_GENRES, site=SITE, site_name=SITE_NAME)

    # ---- sitemap (full URLs) + robots ----
    urls = (["", "about.html", "ocr/", "authors/", "genres/", "stats/", "type/"]
            + (["patro/"] if patro_ok else [])
            + [f"authors/{a}/" for a in author_order]
            + [f"genres/{g}/" for g in genres_present]
            + [f"collections/{cslug[cn]}/" for cn in collections]
            + [r["p"] for r in search_rows])
    (SITE / "sitemap.txt").write_text(
        "\n".join(SITE_URL + u for u in urls) + "\n", encoding="utf-8")
    (SITE / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.txt\n", encoding="utf-8")

    # ---- GitHub Pages: disable Jekyll, set custom domain ----
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    domain = SITE_URL.split("//", 1)[-1].strip("/")          # www.nepaliarchives.org
    (SITE / "CNAME").write_text(domain + "\n", encoding="utf-8")

    pages = 6 + len(author_order) + len(genres_present) + len(collections) + len(recs)   # home+about+ocr+authors-index+genres-index+type + per-author + genres + collections + works
    print(f"built site/ : {pages} pages ({len(recs)} works), "
          f"search index {(SITE/'search-index.json').stat().st_size//1024} KB")
    if archive_base:
        print(f"  downloads -> {archive_base.rstrip('/')}/  (lean site; files served from the archive store)")
    else:
        print("  downloads bundled into site (self-contained). Pass --archive-base <url> to serve files from S3/R2 instead.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive-base", default="",
                    help="Public base URL of the uploaded archive (S3/R2), for download links.")
    args = ap.parse_args()
    build(args.archive_base)


if __name__ == "__main__":
    main()
