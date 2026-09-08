# Sahitya Ras ingestion

All **66 books** are accounted for. The archive now contains **704 works across
ten authors**, including **476 additions** from this source: the 17-work pilot,
427 catalogue additions, and 32 works resolved during PDF review.

The PDF batch supplies **593 work-specific editions for 589 works** from all
**62 eligible books**. It adds a first PDF to 530 works and preserves 59 existing
primary PDFs alongside the additional edition. Across the archive, 597 works now
have a PDF. Works outside the matched source catalogue may still be text-only.
The four remaining source books are recorded but remain outside the publication
gate until 2027; see the [author records](authors.json).

- [Catalogue results](catalogue-status.csv): every book and its dispositions.
- [Text manifest](catalogue.json): pinned revisions, source decisions, repairs,
  member selections, destinations, and output hashes.
- [PDF manifest](pdfs.json): downloaded source hashes, complete physical-page
  accounting, work boundaries, editorial removals, output hashes, and section links.
- [PDF validation](pdf-validation.json): checks and their limits.
- [Earlier text validation](validation.json) and [pilot manifest](chilla-patharu.json):
  historical records of the preceding batches.

## Source fidelity and editions

These PDFs are **digital typeset editions**: all 66 publication pages explicitly
state that they were originally created as EPUBs. They are labelled as digital
editions in the reader, without presenting them as scans of historical printings.
Existing scans and transcriptions remain intact. A matched work may have a shorter
or differently worded existing transcription; its additional PDF preserves the
supplied source edition rather than replacing that text.

Collections become separate member works. Longer works retain their sections in
reading order, with a PDF contents list and links from matching reader sections
to the relevant PDF page. Page numbers in source decisions are one-based physical
PDF pages; section links use the page numbers of the resulting per-work PDF.

Authorial prefaces, dedications, wording, period spelling, punctuation, verse
lines, numbering, indentation, and genuine source gaps are retained. Other
people's editorials and publication wrappers are excluded. Shared pages are
physically redacted before publication: cropping or covering retained hidden
content is insufficient. The public PDFs contain only the selected pages and
remove original annotations, attachments, and executable actions.

The page review resolved the previously held literary material:

- **मायाविनी सर्सी:** the signed editorial attributes its explanatory glossary
  to Mohan Raj Sharma. That editorial, the glossary, and its reference markers are
  excluded. All five cantos remain. A note-only page is omitted; shared pages keep
  the author's closing stanzas. The source also acknowledges editorial emendations
  within the verse, which cannot be silently reversed without another witness.
- **भानुभक्तका फुटकर रचनाहरू:** all 39 printed numbered pieces are accounted for.
  Nine pieces map to seven existing works, including pieces 4, 5, and 10 in the
  existing रोज रोज दर्शन पाउँछु aggregation. Thirty untitled pieces are catalogued
  by their opening lines. Their printed numbers remain, including headings that
  precede a page break. HTML captures reconstruct only the selected excerpts;
  PDF slices retain the corresponding source-page content.
- **प्रेम:** its complete three-part source version is preserved separately from
  the longer प्रेमपत्र after comparing their wording and structure.

This is source reuse and fidelity checking, not completed proofreading against
historical printed pages. Every new work remains `text.proofread: false`.

## Reproduce the text stage

These commands replay the text import against its recorded pre-PDF baseline.
They are not needed to build or preview a current checkout. Fetch the recorded
revisions and stage the reviewed text outputs:

```sh
python3 pipeline/sahityaras_fetch.py --manifest sources/sahityaras/catalogue.json
python3 pipeline/sahityaras_catalogue.py sources/sahityaras/catalogue.json \
  .ingest-work/sahityaras/catalogue --stage .ingest-work/sahityaras/text-review
```

To apply that stage to its recorded pre-PDF baseline:

```sh
python3 pipeline/sahityaras_catalogue.py sources/sahityaras/catalogue.json \
  .ingest-work/sahityaras/catalogue --apply
```

The text manifest describes the state before PDF enrichment. On the current
checkout, its baseline guards intentionally prevent a rerun from stripping the
new PDF metadata. Reproduction of the original catalogue batch also requires its
recorded baseline, including the 17-work pilot. An old import must not undo later
reviewed changes.

## Reproduce the PDF stage

Fetching uses the standard library. Originals stay in an ignored cache; only
sanitized work-specific source PDFs belong in the public archive.

```sh
python3 pipeline/sahityaras_pdf_fetch.py \
  --manifest sources/sahityaras/pdfs.json \
  --output .ingest-work/sahityaras/pdf/originals
```

The fetcher verifies the PDF signature and pinned SHA-256 before replacing a cache
file. Slicing requires the optional PyMuPDF 1.26.7 dependency used for this batch:

```sh
python3 -m venv .ingest-work/pdf-env
.ingest-work/pdf-env/bin/pip install PyMuPDF==1.26.7
.ingest-work/pdf-env/bin/python pipeline/sahityaras_pdf_batch.py \
  sources/sahityaras/pdfs.json .ingest-work/sahityaras/pdf/originals \
  --stage .ingest-work/sahityaras/pdf/review
```

Apply the same reviewed manifest after inspecting the staged outputs:

```sh
.ingest-work/pdf-env/bin/python pipeline/sahityaras_pdf_batch.py \
  sources/sahityaras/pdfs.json .ingest-work/sahityaras/pdf/originals --apply
```

The materializer checks source hashes, complete source dispositions, exact member
assignments, required editorial removals, unchanged text, metadata baselines, and
reviewed output hashes. Every destination is checked before writing. Equal files
are left alone; applying the same PDF batch again writes zero files. Writes are
atomic per file and resumable, rather than one filesystem-wide transaction.

Normal site builds need neither the original download cache nor PDF processing
dependencies. The static reader copies the committed source PDFs and rebuilds
HTML, EPUBs, fonts, and search output; no backend is needed.
