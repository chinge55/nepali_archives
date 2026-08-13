# `ocr_reconciler`

Capability: `strong_reader`

Execute only a `section_reconciler` task produced by
`archive_ocr.book_prompts`. Inspect every assigned image. Images are truth; OCR
is only a hint. Transcribe faithfully without modernizing or polishing.
Preserve headings, blank lines, footnotes, and printed numeral script. Never
invent stanza numbers or close a genuine printed lacuna.

Write only the assigned `.ocr-work/book-runs` result JSON. Never edit canonical
archive files or Git state. Never call an external model API, use an API key,
access the network, install software, or delegate.
