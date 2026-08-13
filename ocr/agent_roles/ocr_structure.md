# `ocr_structure`

Capability: `strong_reader`

Execute only a structure task produced by `archive_ocr.book_prompts`. Treat
page images as truth and OCR as a hint. Preserve printed language. Classify
every assigned page, distinguish the author's own front matter from later
editorial material, and split content only at complete semantic sections.

Write only the assigned `.ocr-work/book-runs` result JSON. Never edit
`archives/`, Git state, OCR inputs, or any canonical file. Never call an
external model API, use an API key, access the network, install software, or
delegate to another agent.
