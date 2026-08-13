# OCR agent roles

These provider-neutral role contracts accompany the immutable packet prompt
created by `archive_ocr.book_prompts`. The packet is authoritative. Bind these
logical roles to any local agent runner without committing that runner's name,
account arrangement, or concrete model identifier.

| Logical role | Capability | Work |
|---|---|---|
| `ocr_structure` | `strong_reader` | page classification, rights exclusions, semantic boundaries |
| `ocr_reconciler` | `strong_reader` | source-faithful transcription of one complete section |
| `ocr_support` | `fast_reader` | folios, footnotes, and catalogue deduplication |
| `ocr_verifier` | `strong_reader` | independent checks of named OCR and numbering risks |

Concrete capability bindings belong in the ignored
`ocr/agent_profiles.local.json`. The tracked `ocr/agent_profiles.json` is the
portable fallback and records only reasoning effort.
