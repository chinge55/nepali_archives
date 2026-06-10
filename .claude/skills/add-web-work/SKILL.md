---
name: add-web-work
description: >-
  Add poem(s)/work(s) scraped from a website (inepal.org, nepalikitab.org,
  Kavita Kosh, Wikisource, …) as born-digital archive works: discover → DEDUPE →
  fetch → materialize via from_html.py → validate. Use when the user gives a
  poems/author URL to ingest. Read CLAUDE.md first.
---

# Add born-digital works from a website

Proven on inepal.org + nepalikitab.org (Bhanubhakta batch) and the Kavita Kosh /
Wikisource crawls. Per-page scraping below; for whole Kavita Kosh author trees use
`kavitakosh_crawl.py`/`kavitakosh_build.py` instead. For classical/canonical texts,
**check Wikisource first** — a clean born-digital edition beats re-OCR.

## 1. Discover + DEDUPE (before fetching anything)

List candidate URLs (site search / author page). Then against the archive:
- slug overlap: `ls archives/authors/<author>/` + grep titles in metadata.
- **content overlap** — grep a distinctive line of each candidate in the author's
  `text.txt`s. This caught: रामगीता = subset of our रामायण (उत्तरकाण्ड); inepal AND
  nepalikitab both listing the same chakari verse under two titles (kept the fuller
  version). Sites duplicate poems under variant titles — when two candidates share
  verses, keep the more complete/better-formatted one.

## 2. Fetch + materialize

```bash
curl -s -A "Mozilla/5.0 …" "<page-url>" -o /tmp/<slug>.html   # polite: sleep ~0.5s between
```
Per work: create `archives/authors/<author>/<slug>/extracted/` and copy the **full
page HTML** to `extracted/index.html` (provenance). Slug via
`python3 pipeline/devanagari_slug.py "<देवनागरी title>"` — review it (म → prefer "ma").

`metadata.json` (validate against the schema): `source.name` = site display name
("iNepal (inepal.org)", "Nepali Kitab (nepalikitab.org)"), `source.url` = page,
`source.html` = "extracted/index.html"; `text.extraction_method` = "html",
`ocr_status` = "born-digital", `proofread` = false; rights basis per author, e.g.
Bhanubhakta "Author died 1868; long in the public domain (Nepal's Copyright Act 2059:
life + 50 years)." — match the existing canonical strings in that author's works.

## 3. Extract text

```bash
~/miniconda3/envs/archive_env/bin/python pipeline/from_html.py <work_dir> [--selector <css>]
```
Container auto-detect tries `.entry-content` (inepal) / `article` / `main`; for other
themes find the Devanagari-dense container and pass `--selector` (nepalikitab =
`.blog-content`). Then clean `text.txt`:
- strip the site's byline line ("भानुभक्त आचार्य – <title>", "Bhanu Bhakta Acharya").
- keep printed श्लोक numbers (`।।१।।`) verbatim; preserve old orthography (एक् मन्,
  गर्‍या) — **never modernize**.
- a heading (e.g. प्रस्तावना) needs a blank line after it or it renders as verse.

## 4. Validate + ship

```bash
python3 pipeline/validate.py
python3 pipeline/build_formats.py <each new dir>   # optional local eyeball
```
Eyeball one rendered page if anything's structurally novel. Then use the `ship`
skill (commit message: count, source site(s), dedup decisions). Stats page updates
itself on build; if this added a **new author**, also use the `add-author` skill.
