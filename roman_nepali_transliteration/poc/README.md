# Typing-tool regression checks

The typing tool's sources are in `assets/type/`; this directory contains its
engine and browser regression tests.

## Engine

Run from the repository root:

```sh
node roman_nepali_transliteration/poc/test_engine.mjs
```

This checks normalization parity, representative candidates, English case,
structured-token preservation, autocorrect pins, and lookup latency. It is a
regression suite, not a corpus-wide accuracy measurement. To regenerate vendored
lexicons, see [`../pipeline/README.md`](../pipeline/README.md) and run
`python3 roman_nepali_transliteration/pipeline/build_lexicon.py --install`.

## Browser

Build and serve the site in one terminal:

```sh
python3 pipeline/build_site.py
python3 -m http.server 8261 --bind 127.0.0.1 --directory site
```

With Puppeteer 21.11 installed and available to Node (directly or through `NODE_PATH`),
run in another terminal:

```sh
TYPE_TEST_URL=http://localhost:8261/type/ node roman_nepali_transliteration/poc/test_type_browser.cjs
```

The suite uses isolated browser contexts and local request interception. It tests
copying, candidate selection, inert HTML input, loading and retry, draft recovery,
undo/redo, paragraphs, structured tokens, composition events, and keyboard access.
Clipboard checks capture the application's API argument and simulate fallback;
they do not inspect the operating-system clipboard. Mobile viewport and keyboard
layout checks are simulations. Physical Android/iOS keyboards and screen readers
still require hands-on checks. Stop the preview server when finished.

## Current interaction contract

- Space selects the first suggestion; Alt+1 through Alt+5 select alternatives.
- Enter commits the pending word and inserts a line break. Shift+Enter or the
  Paragraph button inserts a blank line. Pasted line breaks are retained.
- Escape / “Keep as typed” preserves literal input. English pass-through keeps
  capitalization; email addresses, URLs, and mixed tokens stay literal.
- Copy first commits pending text at the output selection, then copies exactly
  the visible output, including its whitespace, on both clipboard paths.
- Backspace with an empty Roman input reopens the selected output text or the
  word before the output cursor. Selecting an output word and typing Roman text
  replaces the selection.
- Initially empty output directs typing to the Roman field. After output editing
  begins, deleting all text does not make the field readonly again.
- Undo/redo spans conversions, edits, replacements, and Clear. The undo history is
  session-only. The current draft and language mode are saved in this browser;
  Clear removes the saved draft, and Undo restores it while the page remains open.
- Dictionary updates refresh the visible suggestions. Failed core dictionaries
  leave basic typing available; failed typing rules preserve input and show Retry.
