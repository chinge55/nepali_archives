---
name: add-author
description: >-
  Onboard a NEW author into the archive: author dir + registry entry in
  build_site.py, rights-basis string, first works, and the stats stopword pass
  for their register. Use the first time works are added for an author that has
  no directory under archives/authors/ yet. Read CLAUDE.md first.
---

# Add a new author

A new author needs four things beyond their first works:

## 1. Directory + id

`archives/authors/<author_id>/` — id is `[a-z0-9_-]`, natural-Nepali romanization
(`devanagari_slug.py`), matches `author.id` in every work's metadata. The author
block (id / name / name_roman) must be IDENTICAL across all their works.

## 2. Registry entry (code — `pipeline/build_site.py`)

The display registry near the top (`AUTHORS = {…}`, ~line 45) maps
`author_id → (देवनागरी name, Roman name, "birth–death")`:

```python
"lekhnath_paudyal": ("लेखनाथ पौड्याल", "Lekhnath Paudyal", "1885–1966"),
```

Unlisted authors fall back to metadata names (no life dates shown) — so the site
won't break without it, but add it.

## 3. Rights-basis string (canonical per author)

Compose once, reuse verbatim in every work. Pattern (Nepal: Copyright Act 2059 =
life + 50 years; see Rights.md — there is NO rights.verified field, don't add one):

> "Author died <year>; long in the public domain (Nepal's Copyright Act 2059:
> life + 50 years)."

Only public-domain (died 50+ years ago) or permission-granted authors may be added.
If the author died less than ~60 years ago, double-check the arithmetic explicitly.

## 4. Stats stopword pass (after first works land)

Build the site, open `/stats/`, and inspect the **word cloud** and the author's
**signature-words column**. A new register (era, dialect, genre) surfaces its own
function/archaic words — e.g. Bhanubhakta's थिया/दिया/गर्या swamped his column until
added to `STATS_STOP` in `pipeline/stats.py`. Add ONLY grammar/auxiliary forms;
never content words (राम्, फूल stay).

## Then

Works themselves follow the normal paths (`add-web-work` for scraped pages,
`process-book-archive` for scan folders). Finish with `python3 pipeline/validate.py`
(it enforces author-dir == author.id) and the `ship` skill.
