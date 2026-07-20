# Project Rules — Roman Nepali → Devanagari (Stage 0, frozen 2026-07-20)

The contract every stage is built and reviewed against. Changes to this file are
deliberate scope changes, not drive-by edits.

## What we DO

- Word-at-a-time Roman→Devanagari conversion with **top-5 ranked candidates** and
  (v1) short-context re-ranking using the previous committed word.
- Run **fully client-side** on a static host. Zero servers, zero accounts, zero
  telemetry. Works offline once loaded.
- **Progressive layers**: rules work with zero download; lexicon streams in the
  background; the tool is usable the instant the page paints.
- Treat users as tech-illiterate: every interaction (convert, fix, copy) must be
  obvious without instructions.
- Standalone tool first (approved decision 0.1); site integration later.

## What we DON'T do

- No full-sentence translation, grammar correction, or Devanagari spellcheck.
- No neural model in the base path (revisit only after Stage-3 measurement).
- No system IME / native app; we complement Gboard, not compete.
- No mandatory escape syntax or memorized symbols (no `/`, `\`, `{}`, `*`, case
  tricks as the primary path).
- No AGPL code (GoVarnam, indic-trans: algorithms may be reimplemented, code never
  copied/linked). No Google-API dependency in core. No analytics.
- No JS on archive reader pages, ever. No regression to the site when the tool or
  its data fails to load.

## UX contract (from prior-art evidence — reviews/02)

1. **Type freely; the active word is visibly marked; top-5 candidates always
   visible** while a word is active (never behind an extra gesture).
2. **Space or Enter commits candidate #1.** Number keys 1–5, tap/click, or ↑↓ pick
   another. 95% of typing must need zero candidate interaction.
3. **Backspace immediately after a commit reopens that word's candidates** — the
   one-key fix.
4. **Literal-Latin escape is always one action away** and visible (pinned "keep as
   typed" candidate — Yamli style), for English words and names.
5. **Never fail closed.** Unknown input still yields best-effort Devanagari via
   rules; no error states, no empty output, no "reload the page."
6. **Copy is the primary page action**: prominent button, "कपी भयो" toast
   (`role="status"`, `aria-live="polite"`). Clear-all requires confirm or undo.
7. **Mobile**: candidate strip sits **above** the input (finger occlusion), touch
   targets ≥48dp with spacing, layout survives the virtual keyboard
   (`visualViewport`).
8. UI text bilingual Nepali/English, Nepali first.
9. **English stays English by default** (user decision 2026-07-20): detected
   English words pass through as literal #1; a visible toggle flips the behavior.
   Detection list = common-English wordlist minus words whose normalize key
   collides with the Nepali core lexicon (`man`, `ho`, `ban` stay Nepali-first).
10. **The output is editable** (user decision 2026-07-20): commits insert at the
    output box's cursor/selection, so any wrong word can be fixed by selecting
    it and retyping in roman — the fix path for users with no Devanagari
    keyboard. Uppercase `T/Th/D/Dh/N/S` are optional retroflex/sibilant hints
    (`bheTaula` → भेटौला); never required.

## Engineering constraints (reviews/03)

- Input handling: plain `<textarea>`/`<input>` + external candidate overlay. Drive
  logic from `input`/`beforeinput` + `composition*` events. **Never** `keyCode`
  (Android reports 229), **never** `contenteditable`.
- Set `autocorrect=off autocapitalize=none autocomplete=off spellcheck=false`.
- Per-keystroke path is synchronous in-memory lookup; budget **<10 ms** on low-end
  hardware. Anything heavier is debounced or off-thread.
- Assets: versioned URLs; big blobs via fetch (later + IndexedDB with
  `navigator.storage.persist()`); rule layer inlined/core.
- Payloads measured and budgeted at build time (Stage 1 records sizes; budgets set
  in Stage 3). Compression work only if measurements demand it.

## Data & licensing rules

- Sources must be MPL/MIT/BSD/Apache/CC0/CC-BY (or our own). Attribute
  **AI4Bharat/Aksharantar (CC-BY for the manual portion)** and design credits
  (riti, Quillpad) on the tool's about section.
- The repo stays source-only: pipeline code and hand-authored tables are tracked;
  downloaded datasets and generated artifacts are gitignored and reproducible via
  `build_lexicon.py`.
- Evaluation follows multi-reference top-k convention (ACC / MRR / top-5 coverage);
  canonical and natural-typing numbers are always reported separately.

## Linguistic ground rules (reviews/05)

- Normalization (`normalize()`) is strictly coarser than `devanagari_slug.romanize()`
  so query keys and lexicon keys provably meet; ranking (not normalization)
  restores fine distinctions using surface hints (`aa`, `chh`, `T`) and frequency.
- Corpus-prior defaults: dental over retroflex (त>ट, द>ड, न>ण), स over श/ष, `x`→छ,
  word-initial `gy`→ज्ञ. Both nasal forms (ं/ँ) offered in top-5. Final-schwa
  default = deleted, conjunct-aware (slug rule inverted), lexicon-backed.
- Genuine ambiguity is resolved by the top-5, not by pretending a single answer.
