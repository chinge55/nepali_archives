---
name: process-book-archive
description: >-
  Digitize a folder of scanned Nepali book PDFs into archive works (Tesseract OCR
  + per-section agent reconciliation against the page scans → metadata.json +
  text.txt + per-work PDF + reader formats, then rebuild & verify). Use when a
  `book_archive`/source-PDF folder is dropped under archives/authors/<author>/ and
  needs to become public-domain works. Read AGENTS.md first.
---

# Process a scanned book_archive into archive works

The proven method (used for the Lekhnath `book_archive` and the Devkota
`001_book_archive` batch, +40 works). Cardinal rule: **preserve, don't rewrite**
(see AGENTS.md). Work autonomously only after the user has approved a plan.

## 1. Assess (before any OCR)

For each PDF: `pdfinfo` (page count) and `pdftotext -f 1 -l 8 … -` (image-only if
~0 chars → needs OCR). Then decide per book:

- **Overlap**: does this work already exist in the archive? (`grep` titles/slugs,
  check `archives/authors/<author>/`.) If a work or most of a collection is already
  present (e.g. crawled from Kavita Kosh), **enrich/cross-check, don't re-OCR**.
- **Front matter rights call**: render the first ~8 pages, identify the colophon
  (first-pub year, publisher, editions) and any prefaces. **Exclude** modern/editorial
  front matter (other people's forewords/intros); **keep** the author's own prefaces.
- **Structure**: find the TOC. Note the **printed→PDF page offset** (e.g. printed p.1
  = PDF p.10 → +9) and per-piece page ranges. Note section/canto structure.
- **⚠️ Verify the folios BEFORE chunking**: read the printed page number from every
  page's header/footer and confirm the sequence is contiguous — scans can have pages
  **physically out of order** (लुनी: PDF 12,13,14 = printed 8,9,7; the canto agents
  silently dropped 6 stanzas and a "repair" agent invented a false lacuna). OCR mangles
  single digits — montage the footer strips (bottom ~6% of each page, 8–12 per image)
  and read them by eye.

## 2. Render + OCR (300 dpi)

```bash
TESS=~/miniconda3/envs/archive_env/bin/tesseract
OUT=/tmp/<book>; mkdir -p $OUT/img $OUT/ocr
pdftoppm -r 300 -png "<book>.pdf" $OUT/img/pg            # pg-NN (or pg-NNN if ≥100pp)
ls $OUT/img/pg-*.png | xargs -P 12 -I{} bash -c \
  'f="{}"; n=$(basename "$f" .png); '"$TESS"' "$f" "'"$OUT"'/ocr/$n" -l nep'
```

300 dpi OCR is clean on print; it's a strong hint, but the **page image is the
source of truth** for reconciliation.

## 3. Reconcile with a Workflow — CHUNK BY SECTION, not fixed pages

This is the #1 lesson. Fixed page-window chunks drop/merge/mis-number stanzas (and
lose verse) at window **seams**. Use **one agent per section** (poem / सर्ग / canto /
essay), each given that section's full page range. For prose, one agent per essay.
(Parallel subagents if your tool has them; otherwise one sequential pass per section
with a fresh context — the section boundary is what matters, not the parallelism.)

Per-agent rules (put in the prompt): source of truth = images; faithfully reproduce
verse lines / paragraphs as printed; **stanza/श्लोक numbers are sequential — emit the
correct sequential Devanagari numeral even if OCR garbles it; never output `रर` or
Latin-mixed `3१`**; numbers on their own line adjacent to the stanza; section
headings on their own line; **drop page furniture** (running headers, `<n> : <title>`
footers, page numbers); keep danda । ॥, ! ? quotes, hyphens, avagraha ऽ; never
modernize/translate. Margin श्लोक numbers: crop/upscale to read them.
Return structured `{title/heading, first_n, last_n, text, notes}`; add a QA stage.

**After reconciliation, always check per-section numbering contiguity (1..N).** Real
manuscript lacunae (printed numbering that genuinely jumps) are faithful — preserve
them and note in the description. Everything else is a transcription defect: re-run
that one section as a single agent (cleanest), or surgically insert/renumber against
the scan if it's a clean single-marker drop.

Two more agent failure modes to QA for (both hit लुनी):
- **Hallucinated structure** — an agent ADDED stanza numbers (१)–(७) to a canto the
  print leaves unnumbered. If a section looks unnumbered, verify against the image
  and keep it unnumbered.
- **Dropped footnotes** — short glosses (`*` or `१.` at page bottoms) get silently
  discarded, markers and all. Run a dedicated footnote sweep (a few agents scanning
  every page bottom), collate into a `टिप्पणी` endnote section after the text, and
  clean stray inline asterisks. OCR alone cannot find footnotes reliably.

## 4. Materialize each work

`archives/authors/<author>/<slug>/` with `text.txt`, a per-work PDF (a `gs` slice for
collection members, or the whole-book PDF for a single-work book — identical copies
dedupe in git), and a schema-conformant `metadata.json`. Reusable helper pattern
(`make_work`): set `genre` so `genre[0]` drives rendering (`nibandha`/`upanyas` =
prose; else verse); `first_published.bs` from the colophon; `source.name` =
`"<book> (साझा प्रकाशन)"`, `source.pdf` = `<slug>.pdf`; `text.extraction_method="ocr"`,
`ocr_status="ocr-done"`, `proofread=false`, `rights.verified=false`. Compute
`title_roman`/slug via `pipeline/devanagari_slug.py`.

- **Collection members**: description = `From the collection <name>.` (terse first
  sentence; rich text may follow). Match an existing collection's exact name to join
  its page. **Dedup**: if a member already exists, prepend the collection sentence to
  its description — do NOT create a duplicate. Check slug collisions before writing.
- **Author's own preface** (भूमिका/author note): include it as prose (unwrap wrapped
  lines into flowing paragraphs); a heading + its subtitle need a blank line between.

## 5. Verify, commit (CI builds the rest)

**Source-only repo:** you commit `metadata.json` + `text.txt` + the source file. The
build artifacts (`reader.html`, `reader.epub`, `archives/index.json`, the font subset,
`site/`) are **git-ignored and rebuilt by CI** — do NOT commit them.

Verify before committing (same checks as `pipeline/validate.py`): metadata schema-valid;
dir name == `id`, author dir == `author.id`; `text.txt` non-empty Devanagari;
`rights.status` ∈ {public-domain, permission-granted}; sections render right (verse/prose,
headings, contiguous numbering). To eyeball rendering locally, optionally run
`build_index.py` → `build_formats.py <dir>` → `build_site.py` and serve `site/` — but
those outputs stay un-committed. Then commit per book (style: see git log; Co-Authored-By
trailer). Push only when asked (SSH — see AGENTS.md).

**Stats page** (`pipeline/stats.py` → `site/stats/`, "अभिलेख एक नजरमा"): `build_site.py`
**regenerates it on every run** (so it's recomputed before each commit/deploy and can
never go stale — CI rebuilds it too). After adding a NEW work, just rebuild and eyeball
`/stats/`; after adding a NEW AUTHOR, also skim `stats.STATS_STOP` and the signature-words
column — a new author's register may surface a few function/archaic words that belong in
the stopword list so the word cloud stays evocative.

## Reference

Worked examples: the 2026-06 Devkota `001_book_archive` batch (+40 works) and लुनी
(shuffled-folio scan). The site rendering contract is in AGENTS.md; shipping is the
`ship` skill.
