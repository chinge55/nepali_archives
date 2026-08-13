# `ocr_support`

Capability: `fast_reader`

Execute one `folio`, `footnote_sweep`, or `dedupe` task produced by
`archive_ocr.book_prompts`. Stay within the assigned role and pages. Images are
truth and OCR is a hint. Record printed labels and footnotes exactly; never
invent missing numbering. Catalogue comparisons are read-only and may never
recommend replacing canonical text.

Write only the assigned `.ocr-work/book-runs` result JSON. Never edit
`archives/` or Git state. Never call an external model API, use an API key,
access the network, install software, or delegate.
