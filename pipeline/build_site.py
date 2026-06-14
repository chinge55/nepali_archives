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

ROOT = Path(__file__).resolve().parent.parent
ARCHIVES = ROOT / "archives"
SITE = ROOT / "site"
SITE_NAME = "नेपाली अभिलेख"          # "Nepali Archives"
SITE_TAGLINE = "स्वतन्त्र, सार्वजनिक नेपाली साहित्य"  # free, public-domain Nepali literature
SITE_URL = "https://www.nepaliarchives.org/"

# Display names for genre tags (Devanagari · English), and a browse order.
GENRE = {
    "mahakavya": ("महाकाव्य", "epic"), "khandakavya": ("खण्डकाव्य", "narrative poem"),
    "upanyas": ("उपन्यास", "novel"), "nibandha": ("निबन्ध", "essay"),
    "kavita": ("कविता", "poems"), "balkavita": ("बालकविता", "children's poems"),
    "git": ("गीत", "song"), "gazal": ("गजल", "ghazal"),
}
ORDER = ["mahakavya", "khandakavya", "upanyas", "nibandha", "kavita",
         "balkavita", "git", "gazal"]

# Author display registry (name in Devanagari, romanized, life dates). Authors not
# listed fall back to the name/name_roman recorded in their works' metadata.
AUTHORS = {
    "devkota": ("लक्ष्मीप्रसाद देवकोटा", "Laxmi Prasad Devkota", "1909–1959"),
    "bhanubhakta_acharya": ("भानुभक्त आचार्य", "Bhanubhakta Acharya", "1814–1868"),
    "lekhnath_paudyal": ("लेखनाथ पौड्याल", "Lekhnath Paudyal", "1885–1966"),
}


def esc(s): return html.escape(s or "")


def _is_heading(b: str) -> bool:
    """A standalone, word-like line that introduces a section (समर्पण, प्रथम सर्ग) —
    NOT a stanza number (१, (१), क.) or a verse line (ends in danda/!/?/—)."""
    if "\n" in b or len(b) > 40:
        return False
    s = b.strip()
    # A lone parenthesized single Devanagari letter — (क), (ख), (ङ) … — is a canto/
    # section marker (NOT a stanza number like (१)); render it as a heading.
    m = re.fullmatch(r"\(([ऀ-ॿ])\)", s)
    if m and not m.group(1).isdigit():
        return True
    if not s or s[0] in "0123456789०१२३४५६७८९([‘’\"":
        return False
    if s[-1] in "।॥!?,.;:—–…‘’":
        return False
    letters = len(re.findall(r"[ऀ-ॿ]", s))
    return letters >= 3 and (" " in s or letters >= 4)


PROSE_GENRES = {"upanyas", "nibandha"}

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
            lines = "".join(f'<span class="ln">{_nb(esc(l))}</span>'
                            for l in b.split("\n") if l.strip() or True)
            out.append(f'<div class="stanza">{lines}</div>')
        else:
            para = _nb(esc(b).replace("\n", " "))
            out.append(f'<p class="stanza">{para}</p>')
    return "\n".join(out)


# --- pagination for very long works: split into per-section pages + a contents page ---
CHAPTER_RE = re.compile(r'काण्ड|सर्ग|सगैँ|अध्याय|विश्राम|विश्वाम|परिच्छेद|अङ्क|उल्लास|खण्ड|सोपान|परिशिष्ट')
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
        # its own contents entry; a short stray byline/invocation rides on the first section.
        if front and len("\n\n".join(front)) > 400 and _is_heading(front[0].split("\n", 1)[0].strip()):
            pages.append((front[0].split("\n", 1)[0].strip(), "\n\n".join(front)))
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
</footer>
</body>
</html>
"""


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
CSS = """:root{--bg:#fbfaf7;--fg:#1a1a1a;--mut:#6b675e;--line:#e3ded3;--link:#6a4b16;--accent:#8a5a00}
@media(prefers-color-scheme:dark){:root{--bg:#15140f;--fg:#e7e3da;--mut:#9a948a;--line:#2c2a22;--link:#d8b15f;--accent:#e0b65f}}
/* manual override — :root[...] (0,2,0) outranks the media query's :root (0,1,0), so it wins on any system theme */
:root[data-theme=light]{--bg:#fbfaf7;--fg:#1a1a1a;--mut:#6b675e;--line:#e3ded3;--link:#6a4b16;--accent:#8a5a00}
:root[data-theme=dark]{--bg:#15140f;--fg:#e7e3da;--mut:#9a948a;--line:#2c2a22;--link:#d8b15f;--accent:#e0b65f}
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
h1{font-size:1.7rem;line-height:1.3;margin:.5rem 0 .25rem}
.byline{color:var(--mut);margin:.1rem 0}
.meta{color:var(--mut);font-size:.85rem;margin:.4rem 0 0}
.pdfread{display:inline-block;margin:.7rem 0 .1rem;font-size:.9rem;padding:.34rem .85rem;border:1px solid var(--line);border-radius:6px;color:var(--accent);text-decoration:none;transition:background .15s,color .15s,border-color .15s}
.pdfread:hover{border-color:var(--accent);background:var(--accent);color:#fff}
.tochint{color:var(--mut);font-size:.9rem;margin:1.6rem 0 .4rem}
.toc{margin:.3rem 0 0;padding-left:1.3rem;line-height:2.1;font-size:1.05rem}
.toc a{color:var(--link);text-decoration:none}
.toc a:hover{text-decoration:underline}
.crumb{font-size:.85rem;margin:0 0 .75rem}
.crumb a{color:var(--mut);text-decoration:none}
.crumb a:hover{color:var(--accent)}
.work{margin-top:2rem;font-size:1.12rem;line-height:1.95}
.stanza{margin:0 0 1.5rem}
.work.verse .ln{display:block;padding-left:1.6em;text-indent:-1.6em;text-wrap:pretty}  /* hanging indent + avoid 1-word orphan wraps */
.work.prose .stanza{text-align:left;text-wrap:pretty}
/* Narrow phones: long classical verse lines were wrapping their last word/danda as a
   2-char orphan. Step the base size down + trim gutters so most lines simply fit. */
@media(max-width:480px){
 html{font-size:17px}
 main,header.site{padding-left:.9rem;padding-right:.9rem}
 .work{line-height:1.85}
 .work.verse .ln{padding-left:1.25em;text-indent:-1.25em}
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
.home-sec{margin:2rem 0}
.home-sec h2{font-size:1rem;color:var(--mut);font-weight:600;border-bottom:2px solid var(--line);padding-bottom:.2rem}
ul.works{list-style:none;padding:0;margin:1rem 0}
ul.works li{margin:.15rem 0;padding:.35rem 0;border-bottom:1px solid var(--line)}
ul.works li a{text-decoration:none;font-size:1.1rem}
ul.works li .r{color:var(--mut);font-size:.82rem;margin-left:.5rem}
.group h2{font-size:1rem;color:var(--mut);font-weight:600;margin:2rem 0 .25rem;
 text-transform:none;border-bottom:2px solid var(--line);padding-bottom:.2rem}
.count{color:var(--mut);font-weight:400;font-size:.85rem}
#q{width:100%;font:inherit;font-size:1.05rem;padding:.6rem .8rem;border:1px solid var(--line);
 border-radius:.4rem;background:var(--bg);color:var(--fg)}
#results li .snip{display:block;color:var(--mut);font-size:.8rem;white-space:nowrap;
 overflow:hidden;text-overflow:ellipsis}
.hint{color:var(--mut);font-size:.85rem;margin:.4rem 0 0}
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
 main{animation:fade .35s ease both}
 .prog{transition:width .12s linear}
 @keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
}
/* home link to the stats page */
.statlink{margin:1.6rem 0 0;font-size:.92rem}
.statlink a{text-decoration:none;color:var(--mut)}
.statlink a:hover{color:var(--accent)}
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
 // Scoped mode (author/collection pages): tier-1 filters the on-page works list,
 // tier-2 passes a Pagefind filter. Home (no scope attrs) keeps the global behavior.
 var SCOPE=null;
 if(FT){var sa=FT.getAttribute('data-scope-author'),sc=FT.getAttribute('data-scope-collection');
   if(sa||sc){SCOPE={};if(sa)SCOPE.author=sa;if(sc)SCOPE.collection=sc;}}
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
 function renderWorks(list){
   var rows=list.slice(0,60).map(function(w){
     var sub=[w.a,w.c].filter(Boolean).join(' \\u00b7 ');
     return '<li><a href="'+BASE+w.p+'">'+w.t+'</a>'+(w.r?' <span class=r>'+w.r+'</span>':'')+
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
 // roman token -> up to 6 Devanagari candidates (exact > prefix > fuzzy)
 function bridge(tok){ var L=tok.charAt(0);
   if(!/[a-z]/.test(L)) return Promise.resolve([]);
   return getShard(L).then(function(map){
     if(map[tok]) return map[tok].slice(0,6);
     var keys=Object.keys(map),i,pre=[];
     for(i=0;i<keys.length;i++) if(keys[i].lastIndexOf(tok,0)===0) pre.push(keys[i]);
     if(pre.length){ pre.sort(function(a,b){return a.length-b.length;});
       var out=[]; for(i=0;i<pre.length&&out.length<6;i++) out=out.concat(map[pre[i]]); return out.slice(0,6); }
     if(tok.length>=3){ var t=tol(tok.length),best=99,bk=null;
       for(i=0;i<keys.length;i++){ var d=lev(tok,keys[i],t); if(d<best){best=d;bk=keys[i];} }
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

# content-hash cache-busting: bumps automatically whenever the asset changes, so
# returning visitors (phones especially) never get served a stale CSS/JS.
def _ver(s): return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]
CSS_VER, UI_VER, SEARCH_VER = _ver(CSS), _ver(UI_JS), _ver(SEARCH_JS)


def build(archive_base: str):
    works = json.loads((ARCHIVES / "index.json").read_text(encoding="utf-8"))["works"]
    # load metadata + text per work
    recs = []
    for w in works:
        wd = ROOT / w["path"]
        meta = json.loads((wd / "metadata.json").read_text(encoding="utf-8"))
        text = (wd / "text.txt").read_text(encoding="utf-8")
        recs.append((w, meta, text))

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
    ft_words = set()
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
            verse = (meta["genre"][0] if meta["genre"] else "") not in PROSE_GENRES
            gdev = GENRE.get(meta["genre"][0], (meta["genre"][0], ""))[0] if meta["genre"] else ""
            meta_bits = [f'<a href="{up}authors/{aslug_}/#{meta["genre"][0]}">{esc(gdev)}</a>' if gdev else ""]
            for cn in coll:
                meta_bits.append(f'सङ्ग्रह: <a href="{up}collections/{cslug[cn]}/">{esc(cn)}</a>')
            # Downloads: link to --archive-base if set (lean site), else bundle in.
            fmts = meta.get("formats", {}); src_dir = ROOT / w["path"]; dls = []
            pdf_fn = fmts.get("pdf")
            pdfbtn = ('\n  <p><a class="pdfread" href="pdf/">\U0001F4D6 मूल पृष्ठ हेर्नुहोस्</a></p>'
                      if pdf_fn else "")
            for k, lab in [("pdf", "PDF"), ("epub", "EPUB"), ("txt", "मूल पाठ (TXT)")]:
                fn = fmts.get(k)
                if not fn:
                    continue
                if archive_base:
                    dls.append(f'<a href="{archive_base.rstrip("/")}/{rel}/{esc(fn)}">{lab}</a>')
                elif (src_dir / fn).exists():
                    shutil.copy(src_dir / fn, out_dir / fn)
                    dls.append(f'<a href="{esc(fn)}">{lab}</a>')
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
        r = cromanize(wword)
        if r:
            rmap.setdefault(r, set()).add(wword)
    shards = {}
    for r, ws in rmap.items():
        key = r[0] if r[:1].isalpha() else "_"
        shards.setdefault(key, {})[r] = sorted(ws)[:12]      # cap candidates per key
    rdir = SITE / "searchroman"; rdir.mkdir(exist_ok=True)
    for key, m in shards.items():
        (rdir / f"{key}.json").write_text(
            json.dumps(m, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # ---- collection pages ----
    cdir = SITE / "collections"
    for cn, items in collections.items():
        d = cdir / cslug[cn]; d.mkdir(parents=True, exist_ok=True)
        lis = "".join(
            f'<li><a href="../../{esc(Path(w["path"]).relative_to("archives").as_posix())}/">{esc(meta["title"])}</a>'
            f'<span class="r">{esc(meta.get("title_roman") or "")}</span></li>' for w, meta in items)
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
            lis = "".join(
                f'<li><a href="{esc(w["id"])}/">{esc(meta["title"])}</a>'
                f'<span class="r">{esc(meta.get("title_roman") or "")}</span></li>' for w, meta in items)
            groups_html.append(
                f'<div class="group" id="{g}"><h2>{esc(dev)} <span class="count">{en} · {len(items)}</span></h2>'
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
<p class="lead">{str(len(by_author)).translate(_DEVNUM)} लेखकका {str(len(recs)).translate(_DEVNUM)} कृति — नि:शुल्क, सधैँभरि। दर्ता छैन, विज्ञापन छैन।</p>
<p><input id="q" type="search" placeholder="खोज्नुहोस् — शीर्षक, पाठ वा रोमन (जस्तै: pagal, sundari, फूल)" autocomplete="off" aria-label="खोज"></p>
<p class="hint" id="hint"></p>
<ul class="works" id="results" data-base=""></ul>
<div id="ft"></div>
<div class="home-sec"><h2>लेखकहरू</h2><ul class="works">{"".join(author_li(a, "") for a in author_order)}</ul></div>
<p class="statlink"><a href="stats/">📊 अभिलेख एक नजरमा — तथ्याङ्क र रोचक तथ्य →</a></p>
<script src="search.js?v={SEARCH_VER}" defer></script>"""
    (SITE / "index.html").write_text(
        page(SITE_NAME, home_body, desc=SITE_TAGLINE, css_depth=0, active="home", canon=""),
        encoding="utf-8")

    # ---- about ----
    about_body = f"""<h1>बारेमा</h1>
<p class="lead">{SITE_TAGLINE}।</p>
<p>यो अभिलेखले सार्वजनिक डोमेनमा रहेका नेपाली साहित्यिक कृतिहरूलाई संरक्षण, डिजिटलीकरण र
नि:शुल्क पहुँच प्रदान गर्ने लक्ष्य राख्छ। पाठहरू मूल रूपमै राखिएका छन्; OCR/स्क्यान त्रुटि मात्र
सच्याइन्छ, लेखकका शब्द बदलिँदैनन्।</p>
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
<p class="meta">सबै कृति प्रुफरिड र अधिकार-सत्यापन हुन बाँकी छ।</p>
<h2>आफ्ना कृति थप्न चाहनुहुन्छ?</h2>
<p>यदि तपाईं आफ्ना कृति यस अभिलेखमा थप्न चाहनुहुन्छ भने <a href="mailto:mail@nepaliarchives.org">mail@nepaliarchives.org</a> मा इमेल गर्नुहोस्।</p>
<p>तर ध्यान दिनुहोस् — यसरी कृति पठाएपछि तपाईंले त्यस कृतिमाथिको आफ्ना सम्पूर्ण अधिकार र लाइसेन्स पूर्ण रूपमा त्याग्नुहुनेछ। यस अभिलेखको नीति <strong>“कुनै लाइसेन्स छैन” (No license)</strong> हो — यहाँ राखिएका सबै कृति कुनै पनि अधिकार सुरक्षित नराखी, जोसुकैले स्वतन्त्र रूपमा पढ्न, प्रतिलिपि गर्न, वितरण गर्न र प्रयोग गर्न पाउने गरी राखिएका छन्। तपाईंले पठाउनुभएको कृति पनि ठ्याक्कै सोही नीति अन्तर्गत — कुनै लाइसेन्स बिना — सार्वजनिक गरिनेछ। यो निर्णय फिर्ता हुँदैन।</p>"""
    (SITE / "about.html").write_text(
        page("बारेमा — " + SITE_NAME, about_body, css_depth=0, active="about", canon="about.html"),
        encoding="utf-8")

    # ---- stats page (fun, build-time, isolated) ----
    stats.build_stats_page(recs, collections, page=page, GENRE=GENRE,
                           PROSE_GENRES=PROSE_GENRES, site=SITE, site_name=SITE_NAME)

    # ---- sitemap (full URLs) + robots ----
    urls = (["", "about.html", "authors/", "stats/"]
            + [f"authors/{a}/" for a in author_order]
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

    pages = 3 + len(author_order) + len(collections) + len(recs)   # home+about+authors-index + per-author + collections + works
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
