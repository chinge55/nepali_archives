# Nepali Archives

Free, public-domain Nepali literature — preserved, digitized, and searchable.
See [`mission.MD`](./mission.MD) for the charter.

This repository currently holds the **content store** and the **digitization
pipeline**. The public reader website is a later stage (see Roadmap).

## Directory layout

```
archives/
  authors/
    <author-slug>/
      <work-slug>/
        <source>.pdf        # the original PDF (preserved, never edited)
        extracted/index.html # the scraped source page, for web works (preserved)
        metadata.json       # the work's metadata (see schema below)
        text.txt            # extracted plain text          (generated)
        reader.html         # self-contained reading page    (generated)
        reader.epub         # EPUB, when a converter is present (generated)
metadata.schema.json        # JSON Schema for every metadata.json
index.json                  # generated catalogue of every work (id/title/genre/…)
pipeline/
  extract.py                # Stage 1a: PDF text layer -> text.txt
  ocr.py                    # Stage 1b (scans): Tesseract OCR -> text.txt
  from_html.py              # Stage 1c (web): a single scraped HTML page -> text.txt
  kavitakosh_crawl.py       # Stage 1d (Kavita Kosh): crawl an author/work tree -> cached HTML + tree.json
  kavitakosh_build.py       # Stage 1d: turn a crawled tree into work dirs (assemble, dedup, tag)
  build_formats.py          # Stage 2: text.txt -> reader.html / reader.epub
```

Slugs are lowercase `[a-z0-9_-]`. A work's directory name equals its `id`; the
author directory equals `author.id`. Kavita Kosh slugs are Harvard-Kyoto
transliterations of the Devanagari title.

## Metadata

Every work has a `metadata.json` conforming to
[`metadata.schema.json`](./metadata.schema.json). Key fields:

- `rights.status` — only `public-domain` or `permission-granted` works may be
  published. `rights.verified` records whether a human confirmed it.
- `text.ocr_status` — `embedded-ocr` (PDF already had a text layer),
  `needs-ocr` (image-only scan), `ocr-done`, or `born-digital`.
- `text.proofread` — whether the extracted text has been human-corrected.
  Per the mission, corrections fix OCR errors only; they never modernize or
  alter the author's words.
- `formats` — filenames of each available format, or `null` if not yet built.

## Pipeline

`extract.py` and `build_formats.py` need only the Poppler CLIs (`pdftotext`,
`pdfinfo`) and the Python standard library. `ocr.py` needs the conda env
(`archive_env`) with `tesseract` + `pytesseract` + `pdf2image`.

```bash
# Stage 1a — extract text from a PDF that already has a text layer.
python3 pipeline/extract.py archives/authors/devkota/munamadan
python3 pipeline/extract.py --all            # every work; --dry-run to preview

# Stage 1b — OCR a scanned (image-only) work. Requires the conda env.
conda activate archive_env
python pipeline/ocr.py archives/authors/devkota/shakuntala --pages 30-31 --preview  # sample first
python pipeline/ocr.py --all                 # every work flagged needs-ocr

# Stage 1c — extract a born-digital work scraped from the web (needs beautifulsoup4).
python3 pipeline/from_html.py archives/authors/devkota/champa --preview  # sample first
python3 pipeline/from_html.py --all          # every work whose source has html

# Stage 1d — crawl a Kavita Kosh author/work tree, then materialise work dirs.
python pipeline/kavitakosh_crawl.py --seeds seeds.json --out /tmp/kk  # cache + tree.json
python pipeline/kavitakosh_build.py                                   # assemble, dedup, tag

# Stage 2 — build the reading formats from text.txt.
python3 pipeline/build_formats.py --all
```

`extract.py` measures how much Devanagari text comes out. Image-only scans
(≈0 characters) are **not** written as empty files — they are flagged
`needs-ocr` so `ocr.py` can pick them up. `ocr.py` rasterizes each page at
300 dpi and runs Tesseract with the Nepali model (`nep`).

## Current status

**132 works** by Laxmi Prasad Devkota (~590k Devanagari characters). The full,
machine-readable catalogue is [`archives/index.json`](./archives/index.json);
the breakdown by genre:

| Genre                         | Count | Notable / source |
|-------------------------------|-------|------------------|
| कविता — poems                  | 107   | individual poems from Kavita Kosh; most tagged with their source collection (भिखारी, लक्ष्मी कवितासङ्ग्रह). |
| बालकविता — children's poems    | 18    | from the collection *सुनको बिहान*. |
| महाकाव्य — epics               | 2     | *पृथ्वीराज चौहान* (21 cantos, Kavita Kosh) · *शाकुन्तल* (Internet Archive, OCR). |
| खण्डकाव्य — narrative poem      | 1     | *मुना मदन* (18 sections assembled from Kavita Kosh; a scanned PDF is also preserved). |
| उपन्यास — novel                | 1     | *चम्पा* (sahityasangraha.com). |
| निबन्ध — essay                 | 1     | *के नेपाल सानो छ ?* (Internet Archive, OCR). |
| गीत / गजल — song / ghazal       | 2     | from Kavita Kosh. |

Sources: **129 Kavita Kosh** (born-digital), plus *Shakuntala* & *Ke Nepal Sano
Cha* (Internet Archive PDFs, OCR), and *Champa* (sahityasangraha.com). Per the
mission, **no work is proofread or rights-verified yet** — that gate must be
cleared before publishing. Kavita Kosh's per-page publication boxes (e.g. *Muna
Madan*, *Prithviraj Chauhan*) are recorded where present.

Multi-part works (*मुना मदन*, *पृथ्वीराज चौहान*) are assembled into a single
`text.txt` with a header per section/canto. Collection anthologies (*भिखारी*,
*लक्ष्मी कवितासङ्ग्रह*, *सुनको बिहान*) are **not** duplicated as separate files —
each member poem is a standalone work whose `description` names its collection(s).
Duplicate Kavita Kosh pages (spelling variants, mis-titled pages) were de-duplicated
by content hash.

## Environment

`ocr.py` runs in the conda env **`archive_env`**, which has:
`tesseract` 5.5 (bundles the `nep` Nepali model + 124 others), `pytesseract`,
`pdf2image`, `pillow`, and `poppler`. Activate with `conda activate archive_env`.
`from_html.py` and the `kavitakosh_*` scripts additionally need `beautifulsoup4`
+ `lxml`; `kavitakosh_build.py` also needs `indic-transliteration` (for slugs)
(`pip install beautifulsoup4 lxml indic-transliteration`).

## What's needed next (tooling)

- **EPUB**: produced by `pandoc` (installed via `conda install -c conda-forge
  pandoc`, currently in the conda *base* env at `~/miniconda3/bin/pandoc`). When
  running `build_formats.py` under `archive_env`, put base on PATH so it is
  found: `PATH="$(conda info --base)/bin:$PATH" python pipeline/build_formats.py --all`.

## Roadmap

1. **Foundation** (done): metadata schema, extraction + HTML/TXT build.
2. **OCR stage** (done): `pipeline/ocr.py` for `needs-ocr` works → `text.txt`.
3. **Proofreading workflow**: correct OCR errors, then mark
   `text.proofread = true` per work.
4. **EPUB** generation (done): `pandoc` builds `reader.epub` for every work.
5. **Reader website**: static site (recommended — see below) with a
   prebuilt search index over all `text.txt`, generated from the archive.

## Hosting (recommendation)

A **static site** best fits the mission's "free forever, no login" constraints:
pre-build HTML pages and a client-side search index from this archive, and host
on free static hosting (GitHub Pages / Netlify / Cloudflare Pages). No server,
no database, no recurring cost, nothing to log into — and the whole archive
stays a set of plain files anyone can mirror.
