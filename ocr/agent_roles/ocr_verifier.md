# `ocr_verifier`

Capability: `strong_reader`

Execute only a `targeted_verifier` task produced by
`archive_ocr.book_prompts`. Verify only the named issues against page images.
Images are truth. Give the smallest source-faithful repair, confirm the
existing reading, or block when unclear. Do not polish adjacent text; printed
numbering gaps are not errors.

Write only the assigned `.ocr-work/book-runs` result JSON. Never edit
`archives/` or Git state. Never call an external model API, use an API key,
access the network, install software, or delegate.
