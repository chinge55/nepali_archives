# Nepali Archives

Free, public-domain Nepali literature — preserved, digitized, searchable.
**Live at [www.nepaliarchives.org](https://www.nepaliarchives.org).**
See [`mission.MD`](./mission.MD) for the charter and [`CONTRIBUTING.md`](./CONTRIBUTING.md) to help.
Report credentials or personal-data exposure privately; see
[`SECURITY.md`](./SECURITY.md).

This repository is **source-only**: it holds the texts, their metadata, and the
digitization pipeline. The reader website — reading pages, downloads, full-text search,
the stats page — is **built from these sources by CI on every push** and deployed to
GitHub Pages. You never commit build output.

## Directory layout

```
archives/
  authors/<author-id>/<work-id>/
    metadata.json          # the work's metadata (validates against the schema)   [tracked]
    text.txt               # the canonical plain text — the source of truth        [tracked]
    <source>.pdf           # original scan/PDF, or…                                 [tracked]
    extracted/index.html   # …the scraped source page for a web work                [tracked]
    reader.html            # self-contained reading page          [GENERATED — git-ignored]
    reader.epub            # EPUB (pandoc)                          [GENERATED — git-ignored]
  index.json               # catalogue of every work               [GENERATED — git-ignored]
metadata.schema.json       # JSON Schema for every metadata.json
assets/
  site/                    # tracked CSS/JS sources used by the static-site generator
  fonts-full/              # full Noto Serif Devanagari woff2 (subset inputs)       [tracked]
  fonts/fontface.css       # @font-face CSS                                          [tracked]
  fonts/*.woff2            # subset to the glyphs the site uses    [GENERATED — git-ignored]
pipeline/
  extract.py               # Stage 1a: PDF text layer        -> text.txt
  ocr.py                   # Stage 1b: Tesseract OCR (scans) -> text.txt
  from_html.py             # Stage 1c: a scraped HTML page    -> text.txt   (--selector for any theme)
  kavitakosh_crawl.py      # Stage 1d: crawl a Kavita Kosh author/work tree
  kavitakosh_build.py      # Stage 1d: assemble a crawled tree into work dirs
  build_index.py           # archives/index.json from every metadata.json
  build_formats.py         # text.txt -> reader.html / reader.epub
  build_site.py            # stable CLI entry point for the static-site build
  sitegen/                 # rendering, assets, page generators, and build orchestration
  tests/                   # dependency-free unit + fixture-build tests for sitegen
  check_site_links.py      # generated-site internal href/src audit
  subset_fonts.py          # subset the woff2 to glyphs the built site uses
  stats.py                 # the /stats/ "अभिलेख एक नजरमा" page (build-time, called by build_site)
  devanagari_slug.py       # Devanagari -> slug / romanization helper
  validate.py              # contribution checks (run on every PR)
  check_public_tree.py     # public-source privacy boundary
  sanitize_extracted_html.py # remove scripts/comments from captured HTML
.github/workflows/         # validate.yml (on PRs) · deploy.yml (build full pipeline + deploy)
CONTRIBUTING.md · AGENTS.md · Rights.md · LICENSE
```

Slugs are lowercase `[a-z0-9_-]`; a work's directory name == its `id`, the author
directory == `author.id`. Slugs come from `devanagari_slug.py` — best-effort
**natural-Nepali romanization** (drop word-final inherent schwa unless after a conjunct;
व→b, श/ष→sh) — review them, they're a starting point. Agents working here: [`AGENTS.md`](./AGENTS.md).

## Contributing

A contribution is just **`text.txt` + `metadata.json` + the source file** — CI rebuilds and
deploys everything else, so you never touch build output. Two ways to help:

1. **Improve a text** — fix OCR/scan errors in a `text.txt` (faithfully — no modernizing) and
   open a PR. This is crowdsourced proofreading, the most valuable contribution.
2. **Add a work** — add a `metadata.json` + `text.txt` + source under `archives/authors/…/`.

Every PR runs [`pipeline/validate.py`](./pipeline/validate.py) (schema, slug/id rules, text
sanity, rights gate), the site-generator test suite, a dry-run build, and an internal-link
audit. See **[`CONTRIBUTING.md`](./CONTRIBUTING.md)** for the full guide and rights policy.

## Metadata

Every work has a `metadata.json` conforming to [`metadata.schema.json`](./metadata.schema.json).
Key fields:

- `rights.status` — only `public-domain` or `permission-granted` works may be published.
- `text.extraction_method` — `extract` (PDF text layer), `ocr`, `html` (scraped), or `manual`.
- `text.ocr_status` — `ocr-done` or `born-digital` (web/embedded text).
- `text.proofread` — whether the text has been human-corrected (OCR fixes only; never modernized).
- `genre` — free-form tags; `genre[0]` drives rendering (`nibandha`/`upanyas` = prose, else verse).
- `formats` — filename per available format.

## Pipeline

**Stage 1 (source → `text.txt`)** depends on the source: `extract.py` (PDF text layer,
Poppler) · `ocr.py` (image-only scans; conda env `archive_env` with Tesseract `nep`) ·
`from_html.py` (a scraped page; `beautifulsoup4`) · `kavitakosh_*` (Kavita Kosh trees). For a
folder of scanned book PDFs, see the `process-book-archive` skill.

```bash
python3 pipeline/extract.py archives/authors/devkota/munamadan      # PDF text layer
conda activate archive_env && python pipeline/ocr.py <dir>          # scanned pages, 300 dpi nep
python3 pipeline/from_html.py <dir> [--selector .blog-content]      # a scraped web page
```

**Build (sources → site)** is what CI runs on every push, and what you can run locally to
preview:

```bash
python3 pipeline/build_index.py            # archives/index.json
python3 pipeline/build_formats.py --all     # reader.html + reader.epub (pandoc)
python3 pipeline/build_site.py              # site/ (reading pages, downloads, /stats/)
python3 -m unittest discover -s pipeline/tests
python3 pipeline/check_site_links.py site
python3 pipeline/subset_fonts.py            # font subset (fonttools+brotli)
python3 pipeline/build_site.py              # second pass embeds the subset
npx pagefind --site site                    # full-text search index
cd site && python3 -m http.server 8000      # preview at http://localhost:8000
```

## The website

Static, content-first, and fast: every work is pre-rendered to HTML, one small cached CSS,
self-hosted (subset) Noto Serif Devanagari, dark/light toggle, and it browses with JS off.
**Full-text search** (Pagefind) searches inside every poem in **Devanagari or roman**
(`sundari` ≡ `सुन्दरी`, via a build-time roman→Devanagari bridge), with highlighted excerpts
that deep-link to the passage. A build-time **stats page** (`/stats/`, "अभिलेख एक नजरमा") shows
corpus graphs, a word cloud, and per-author signature words. The site is git-ignored and
rebuilt by CI — `--archive-base <url>` makes downloads point at an external store instead of
bundling them.

## Current status

**210 works across 3 authors** — Laxmi Prasad Devkota (175), Lekhnath Paudyal (24),
Bhanubhakta Acharya (11). Full catalogue: [`archives/index.json`](./archives/index.json).

| `genre[0]` | Count | Notes |
|---|---|---|
| कविता — poems | 142 | individual poems (Kavita Kosh, inepal.org, nepalikitab.org, साझा scans); most Devkota poems tagged with their collection |
| निबन्ध — essays | 38 | Devkota's *लक्ष्मी निबन्ध सङ्ग्रह* |
| बालकविता — children's poems | 19 | *सुनको बिहान* (Devkota) |
| महाकाव्य — epics | 5 | *शाकुन्तल*, *प्रमिथस*, *पृथ्वीराज चौहान* (Devkota) · *रामायण* (Bhanubhakta) · *तरुण तपसी* (Lekhnath) |
| खण्डकाव्य — narrative poems | 3 | *मुना मदन*, *म्हेन्दु*, *लुनी* (Devkota) |
| उपन्यास — novel | 1 | *चम्पा* (Devkota) |
| गीत · गजल | 2 | Devkota |

Sources: Kavita Kosh, inepal.org, nepalikitab.org, Internet Archive, sahityasangraha.com,
Wikisource (Bhanubhakta's *रामायण*), and साझा प्रकाशन print scans (Tesseract OCR). Collection
anthologies (*भिखारी*, *लक्ष्मी कवितासङ्ग्रह*, *लक्ष्मी निबन्ध सङ्ग्रह*, *सुनको बिहान*) aren't
duplicated — each member is a standalone work whose description names its collection.

Per the mission, **no work is proofread yet** (`proofread: false`) — crowdsourced
proofreading is the next milestone. (The archive's rights position is stated in
[`Rights.md`](./Rights.md) and [`LICENSE`](./LICENSE).)

## Environment

Core pipeline + `build_site.py`/`sitegen` are pure Python stdlib. `ocr.py` runs in conda env
**`archive_env`** (Tesseract 5.5 with the `nep` model, `pytesseract`, `pdf2image`, `pillow`,
`poppler`). `from_html.py` / `kavitakosh_*` need `beautifulsoup4`+`lxml`; `build_formats.py`
needs `pandoc` (EPUB); `subset_fonts.py` needs `fonttools`+`brotli`. CI installs pandoc +
fonttools as build steps.

## Roadmap

1. Foundation — metadata schema, extraction, HTML/TXT/EPUB build. **done**
2. OCR + web scraping (`ocr.py`, `from_html.py`, `kavitakosh_*`). **done**
3. Reader website on GitHub Pages → **live**.
4. Full-text search (Devanagari + roman) and the corpus stats page. **done**
5. Source-only repo + CI build + PR validation + contribution guide. **done**
6. **Proofreading** — correct each `text.txt` against its source and flip `text.proofread`.
   *The open gate before works are publication-ready.*
