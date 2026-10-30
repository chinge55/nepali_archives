# Chhanda writer rules

The initial `/chhanda/` release analyses the spelling under an explicit verse
reading. It supports भुजङ्गप्रयात (य य य य), वसन्ततिलका (त भ ज ज गुरु गुरु),
and शार्दूलविक्रीडित (म स ज स त त गुरु). A verse has four पाउ; a newline,
slash, vertical bar, or danda separates पाउ. Blank lines separate stanzas.
Screen wrapping never changes the analysis.

The main writing surface has one textarea, a Devanagari/Roman switch, and a
metre dropdown. Roman words are composed and converted in that same textarea
when Space, Enter, or punctuation is entered. Candidates replace the active
Roman word at its actual location. Examples open only after an explicit click;
analysis, pronunciation settings, word search, and help stay collapsed by
default. Compact feedback supports the current line without opening a lesson.

The formulae are cross-checked with [छन्दःशिक्षा](https://chhanda.vag.org.np/Examples/).
General weight rules are described in [Apte's prosody appendix](https://www.sanskrit-lexicon.uni-koeln.de/scans/csldev/csldoc/build/dictionaries/prefaces/ap90app1.html).
These are rules and reference material, rather than an imported implementation.
The engine is independently written and has no runtime dependencies.

**Syllables and weight**

- A syllable has an independent vowel or a consonant onset followed by an
  explicit or inherent vowel. A halant joins consonants; it does not add a vowel.
- Long vowels, anusvāra, visarga, and a closing halant consonant produce गुरु.
  Chandrabindu indicates nasalization and does not alone lengthen a short vowel.
- A following consonant cluster makes a short syllable गुरु, including across
  whitespace. A punctuation pause blocks that cross-word rule in this draft.
- Word-final inherent अ is retained by default, as shown in the guide. The
  writer may explicitly suppress it for a word with more than one syllable.
  The remaining final consonant closes the previous syllable. No pronunciation
  is chosen automatically to fit the target metre.
- A final लघु can occupy the final गुरु position when the visible पदान्त option
  is enabled. Such a match carries a separate label. The underlying syllable
  weight and actual मात्रा total remain visible.
- Unknown characters, numerals, and malformed marks produce a separate
  uncertainty state. A mismatching line is never silently corrected.
- यति is shown as a reading aid, with a warning if the indicated position
  cuts a word. The वसन्ततिलका eight-syllable pause is a teaching suggestion.

The result describes the displayed reading. Sandhi, vowel coalescence,
regional readings of conjuncts, poetic shortening or lengthening, and other
metrical licences require further review. The interface states this limitation;
it does not claim expert certification or an accuracy percentage.

**Examples and evaluation**

The excerpts in `assets/chhanda/metres.js` were compared visually against
`archives/authors/devkota/shakuntala/sahityaras-shakuntala.pdf`:

| Metre | Source | PDF page | Printed page |
| --- | --- | --- | --- |
| भुजङ्गप्रयात | चतुर्थ सर्ग, श्लोक ४, four पाउ | 50 | ५६ |
| वसन्ततिलका | सप्तम सर्ग, श्लोक १२, first two पाउ | 100 | १०६ |
| शार्दूलविक्रीडित | प्रथम सर्ग, श्लोक १, first two पाउ | 3 | १ |

Keep the excerpts as printed, without modernizing. These checks concern the
excerpt; they do not change the source work's `text.proofread` flag. Engine
tests also cover independently specified word weights, Unicode spans, missing
syllables, author-selected readings, cross-word clusters, and rejected input.
The larger independently reviewed reference set and evaluation targets in
`plans/chhanda-writer.md` remain future work; the initial draft makes no claim
that they have been completed.

**Writing and storage**

The editable textarea is the source of truth. Analysis marks never enter its
text. The existing transliteration engine supplies optional word candidates;
it does not establish pronunciation. Word suggestions use a bundled common
vocabulary and the existing typing core vocabulary, with every candidate
rechecked in its full line. These are metrical candidates, not synonyms.

Edits preserve reading choices for unchanged words and invalidate choices for
changed words. Undo/redo and versioned JSON exports contain poem, metre,
reading choices, pending Roman input, and the final-syllable option. TXT and
copy contain the poem alone. Browser storage failure does not prevent writing.
Version 2 projects store the input mode and keep uncommitted Roman text in the
poem itself. Existing version 1 drafts migrate without dropping their pending
word. Switching modes does not move writing into a separate field.
Draft text is never transmitted or encoded into URLs. Static data is fetched
from the same site; no analysis service or telemetry is required.

**Verification**

Run `node --test chhanda_writer/tests/engine.mjs` and the browser harness
`NODE_PATH=<browser-test-dependencies> node chhanda_writer/tests/browser.cjs`.
The latter defaults to `http://localhost:8263/chhanda/`; set `CHHANDA_TEST_URL`
to exercise a deployed route. Run site-generator tests, the existing typing
regressions, source validation, site-link and SEO audits, and the browser
verification described in the repository skills before shipping.
