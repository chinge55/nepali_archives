---
name: clean-work-text
description: >-
  Remove non-content "unnecessary text" from a work's text.txt — editorial
  prefaces/forewords by OTHERS, front-matter cataloguing (CIP/ISBN/romanized
  title blocks), publisher colophons, back-cover catalogues/ads, running
  headers/footers, and OCR-symbol noise — keeping ONLY the author's own writing
  and its structure. Use when a work's extracted text is padded with junk around
  the actual poem/essay/novel. Read CLAUDE.md first.
---

# Clean a work's text to the author's own writing

What scanned/OCR'd (and some scraped) works accumulate around the real text, and
which of it to strip. Cardinal rule (CLAUDE.md): **preserve, don't rewrite** — this
skill removes *non-content* only; it does NOT fix OCR spelling in the work itself
(that's the separate proofread stage). Worked example: the तरुण तपसी cleanup
(3905 → 3334 lines).

## Decide the scope first (ask the user)

Cleaning depth is a judgment call — confirm before cutting, via AskUserQuestion:
- **Light** — strip front/back matter + page furniture + obvious noise; keep the
  work and (poor) OCR verse/stanza structure as-is (a proofread-stage item).
- **Also drop the editorial preface** — additionally remove a third-party
  introduction/भूमिका (see rights call below).
- **Full re-OCR** — re-render at 300 dpi and reconcile per-section with agents
  (the `process-book-archive` method); this also fixes garbled verse/numbering.

## What is "unnecessary" (remove)

- **Front matter**: garbled romanized/English **CIP cataloguing** blocks, ISBN /
  Library-of-Congress lines, the title page repeated as text, and the **publisher
  colophon** (प्रकाशक/संस्करण/मूल्य/मुद्रक, phone/fax).
- **Editorial front matter by OTHERS** — a भूमिका/प्राक्कथन/foreword/intro written
  *about* the author (third person: "our peerless … X composed…") or signed by an
  editor/critic, especially modern (post-1959) and thus copyrighted. (Rights call,
  same as the book_archive batches: exclude others' modern prefaces; **KEEP the
  author's OWN** preface/author-note — first person, signed by the author.) Check
  the **signature/date** at the preface's end to decide.
- **Back matter**: publisher's catalogue of other books/authors ("… प्रकाशनका केही
  कविता/काव्य" + lists), price, मुद्रक line, barcodes/junk numbers.
- **Page furniture**: running headers/footers — there are usually two alternating
  styles, e.g. `<work-title> : <page>` and `<page> : <section-name>`; both go.
- **OCR-symbol noise**: lines with NO Devanagari at all (`» ॥`, `? 0`, `000`, `|`,
  stray ASCII digits).

## What to KEEP

The author's own writing + its structure: the work's invocation (मङ्गलाचरण), the
author's own preface/note, all section/canto headings (`प्रथम विश्राम`, सर्ग, अध्याय),
stanza/श्लोक numbers (even if OCR-garbled — proofread stage), the closing
(समाप्त), and the verse/prose itself. **Do not delete garbled-but-real lines** —
if a line contains any real Devanagari words it is content, not noise.

## Method (surgical, verify before overwriting)

1. **Find the body boundaries**: where the work begins (first heading/invocation/
   chapter after the front matter) and ends (its closing / last section before back
   matter). `grep` for the structure markers (विश्राम/सर्ग/अध्याय), the preface
   signature, and the back-matter list header.
2. Build the cleaned text in a script (write to a TEMP file first):
   - keep `body[start:end]`;
   - drop footer style A: `^<work-title>\s*[:ः]`;
   - drop footer style B: a colon-bearing `<prefix> : <section> <section-word>`
     line (the bare `<section> <section-word>` heading has NO colon — keep it);
   - drop pure-noise: non-blank lines with **no** `[ऀ-ॿ]` char;
   - collapse 2+ blank lines to 1;
   - drop a section-heading line whose next non-blank line is ALSO a heading
     (that's a trailing footer-remnant, not a heading).
3. **Review the temp output before applying**: list the removed lines and the
   remaining section headings; confirm the heading sequence is complete (e.g. all N
   cantos, each followed by content, none doubled). Then overwrite `text.txt`.
4. Update metadata if now inaccurate (e.g. description still says "OCR pending";
   `first_published` you can read from the preface), bump `updated`.
5. Rebuild + verify + commit (CLAUDE.md order): `build_formats.py <dir>` →
   `build_index.py` → `build_site.py`; confirm schema-valid, the rendered page has
   no leaked footers/cataloguing, and the work renders right. Commit (per work).

## Gotchas

- **Footer page-numbers garble** (`१्द :`, `'ह :`) so a digit-anchored regex misses
  them — match footers by the `: <section-word>` shape, not by the page number.
- **Footer-remnants masquerade as headings**: a bare `पञ्चम विश्राम` sitting right
  before the next canto's heading is the *previous* page's footer (page-number
  lost) — drop it (the heading-followed-by-heading rule).
- **Verse left as-is may still mis-render**: stray blank lines between verse lines
  make single lines render as pseudo-headings (`_is_heading`). That's a verse-
  structure/proofread item, NOT "unnecessary text" — only fix it under the Full
  re-OCR or an explicit re-flow scope.
