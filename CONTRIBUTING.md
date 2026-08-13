# Contributing to Nepali Archives

We preserve and digitize **public-domain Nepali literature** as plain files, served by a
static reader site (**[www.nepaliarchives.org](https://www.nepaliarchives.org)**). See
[`mission.MD`](./mission.MD) for the charter and [`README.md`](./README.md) for the layout.

**The one rule that matters most — preserve, don't rewrite.** Transcriptions are *faithful
to the source*: fix OCR/scan errors only, never modernize spelling, punctuation, or wording.
Period and variant spellings (e.g. `जूवा`, `गौरीशंकर`, old-Bhanubhakta `एक् मन्`) stay as printed.

## You only edit sources. CI builds the rest.

A work lives at `archives/authors/<author>/<work>/` and the **only files you touch** are:

| File | What it is |
|---|---|
| `text.txt` | the work's text — **the source of truth** |
| `metadata.json` | title, author, genre, rights… (conforms to [`metadata.schema.json`](./metadata.schema.json)) |
| the source | `*.pdf`, or `extracted/index.html` for a scraped page |

Everything else — `reader.html`, `reader.epub`, `archives/index.json`, the font subset, the
whole `site/` and search index — is **build output**. It is **git-ignored and rebuilt by CI**
on every merge. **Do not commit build output**; you don't need to run any build to contribute.

## Two ways to help

### 1. Improve a text (proofreading)
Open `archives/authors/<author>/<work>/text.txt`, fix OCR/scan errors **against the source**
(the PDF/scan or the linked source URL in `metadata.json`), and open a pull request. That's it.
This is the single most valuable contribution — most works are still `proofread: false`.

### 2. Add a work
Create `archives/authors/<author>/<slug>/` containing `text.txt`, `metadata.json`, and the
source file, then open a PR. Conventions the validator checks for you:

- **slug rules:** the directory name == `metadata.id` == `[a-z0-9_-]`; the author directory ==
  `metadata.author.id`. (Generate a slug with `python3 pipeline/devanagari_slug.py "<title>"`.)
- **`metadata.json`** must validate against `metadata.schema.json`.
- **`text.txt`** is non-empty Devanagari; blank lines separate stanzas/paragraphs; a short
  standalone line is a section heading (put a blank line before the next block); verse vs prose
  is decided by `genre[0]` (`nibandha`/`upanyas` → prose, else verse).

Adding a **new author** may also need a small maintainer code change when custom life dates
are wanted (the optional display registry lives in `pipeline/sitegen/config.py`) — please
open an issue and we'll wire it. Names otherwise fall back to the work metadata automatically.

## Rights — read before submitting

Only works that are **public-domain** or **permission-granted** may be added. Under Nepal's
**प्रतिलिपि अधिकार ऐन, २०५९ (दफा १४)**, copyright lasts the author's life **+ 50 years**; so a
work is public-domain once the author has been dead 50+ years (e.g. Bhanubhakta d. 1868,
Lekhnath d. 1966, Devkota d. 1959). Set `rights.status` to `public-domain` accordingly.

- **Don't** submit in-copyright works, or other people's editorial matter (modern prefaces,
  forewords, footnotes, introductions) — keep only the author's own writing.
- By contributing, you agree the material is released with **no rights reserved** — the archive
  asserts no new copyright over public-domain works. See [`Rights.md`](./Rights.md) and the
  site's *बारेमा* (About) page.

## What happens to your PR

- **On the PR:** `validate.yml` runs `pipeline/validate.py` (schema, slug/id, text, rights),
  site-generator tests, a dry-run build, and an internal-link audit, so you get ✅/❌ immediately.
- **On merge:** `deploy.yml` regenerates everything (`build_index` → `build_formats` →
  `build_site` → `subset_fonts` → Pagefind) and deploys to GitHub Pages.

## Optional: preview locally

Pure Python stdlib for the core; `pandoc` (EPUB) and `fonttools`+`brotli` (font subset) are
only needed for a full local build.

```bash
python3 pipeline/validate.py                 # the same checks CI runs on your PR
python3 pipeline/build_index.py
python3 pipeline/build_formats.py <work_dir>  # reader.html + reader.epub (per dir, not --all)
python3 pipeline/build_site.py
python3 -m unittest discover -s pipeline/tests
python3 pipeline/check_site_links.py site
cd site && python3 -m http.server 8000        # http://localhost:8000
```

Questions, or want a work added on your behalf? **mail@nepaliarchives.org**.
