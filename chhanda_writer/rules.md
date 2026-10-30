# Chhanda writer rules

The `/chhanda/` writer analyses the spelling under an explicit verse reading.
Its catalogue contains ten metres with a fixed pattern for each पाउ:

| Metre | Ganas and tail | Syllables | Internal pause positions |
| --- | --- | --- | --- |
| भुजङ्गप्रयात | य य य य | 12 | Grouping aid only |
| वसन्ततिलका | त भ ज ज गुरु गुरु | 14 | 8 (practice aid) |
| शार्दूलविक्रीडित | म स ज स त त गुरु | 19 | 12 |
| मालिनी | न न म य य | 15 | 8 |
| शिखरिणी | य म न स भ लघु गुरु | 17 | 6 |
| तोटक | स स स स | 12 | Grouping aid only |
| द्रुतविलम्बित | न भ भ र | 12 | 4 (one accepted division) |
| शालिनी | म त त गुरु गुरु | 11 | 4 |
| स्रग्धरा | म र भ न य य य | 21 | 7, 14 |
| मन्दाक्रान्ता | म भ न त त गुरु गुरु | 17 | 4, 10 |

A verse has four पाउ; a newline,
slash, vertical bar, or danda separates पाउ. Blank lines separate stanzas.
Screen wrapping never changes the analysis.

The main writing surface has one textarea, a Devanagari/Roman switch, and a
metre dropdown. Roman words are composed and converted in that same textarea
when Space, Enter, or punctuation is entered. Candidates replace the active
Roman word at its actual location. Examples open only after an explicit click;
analysis, pronunciation settings, word search, and help stay collapsed by
default. Compact feedback supports the current line without opening a lesson.
Soft red underlines mark metrical problems inside the writer. They are visual
decorations over the native textarea; they never enter the draft or change its
caret, selection, or clipboard text. Correct unfinished prefixes remain clear
while writing; a boundary makes an incomplete पाउ eligible for a mark. Marks
disappear during keyboard composition and when the reading is uncertain.

The formulae are cross-checked with [छन्दःशिक्षा](https://chhanda.vag.org.np/Examples/).
General weight rules are described in [Apte's prosody appendix](https://www.sanskrit-lexicon.uni-koeln.de/scans/csldev/csldoc/build/dictionaries/prefaces/ap90app1.html).
The expanded catalogue's formulae and pause positions were also checked against
that appendix. Its शिखरिणी entry supplies the य म न स भ लघु गुरु formula;
the prose beneath that heading on छन्दःशिक्षा repeats the स्रग्धरा description.
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
| शार्दूलविक्रीडित | प्रथम सर्ग, श्लोक १, first two पाउ | 3 | ९ |
| मालिनी | द्वितीय सर्ग, श्लोक १, first two पाउ | 16 | २२ |
| शिखरिणी | द्वितीय सर्ग, श्लोक १८, first two पाउ | 20 | २६ |
| तोटक | तृतीय सर्ग, श्लोक १, last two पाउ | 28 | ३४ |
| द्रुतविलम्बित | तृतीय सर्ग, श्लोक २५, first two पाउ | 34 | ४० |
| शालिनी | सप्तम सर्ग, श्लोक ५०, first two पाउ | 108 | ११४ |
| स्रग्धरा | सप्तम सर्ग, श्लोक ५३, second पाउ | 109 | ११५ |
| मन्दाक्रान्ता | सप्तदश सर्ग, श्लोक १, last two पाउ | 299 | ३०५ |

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
New drafts detect the input script automatically: Roman words convert in place
and Devanagari passes through. Only newly entered letters affect the switch;
punctuation, digits, and the converted output do not change it. An explicit
toggle choice disables automatic selection for that draft and survives reload
and export/import. Older saved drafts retain their recorded input mode.
Draft text is never transmitted or encoded into URLs. Static data is fetched
from the same site; no analysis service or telemetry is required.

**Verification**

Run `node --test chhanda_writer/tests/engine.mjs` and the browser harness
`NODE_PATH=<browser-test-dependencies> node chhanda_writer/tests/browser.cjs`.
The latter defaults to `http://localhost:8263/chhanda/`; set `CHHANDA_TEST_URL`
to exercise a deployed route. Run site-generator tests, the existing typing
regressions, source validation, site-link and SEO audits, and the browser
verification described in the repository skills before shipping.

**Archive metre annotations**

`metadata.prosody` records a separately reviewed identification, with a text
fingerprint, review date, source file and fingerprint, location and review note.
The initial curated seed in `data/prosody-pilot.json` contains fifty works:
twenty-two single-metre works (including a source-labelled झ्याउरे work),
twenty-seven free-verse readings, and one mixed work with ten located examples.
This is a curated seed, not a held-out accuracy benchmark or an estimate of
automatic identification accuracy across the archive.

The metrical readings were checked against the preserved source poems and the
catalogue patterns. Free-verse readings record positive structural observations
about the whole poem; they are not inferred from missing template matches.
Candidate rhythmic songs and poems with unexplained scans were left for later
review. The mixed annotation's selected passages are not a complete metrical
edition of the long work. Their locators use the existing transcription, while
the source PDF supplies the metrical evidence. This review changes neither
literary text nor the work's proofreading flag.

`assets/chhanda/catalogue.json` is the archive's build-time name and pattern
catalogue. Its writer entries must agree with `metres.js`; पृथ्वी and स्वागता
are also checked against Apte's appendix, and झ्याउरे is source-labelled in
the author's own introduction to मुना मदन. Reader pages fetch no scansion
engine. `/chhandas/` and its metre pages are generated from reviewed metadata;
mixed-work links go to the identified passage, and search filters describe
metres present on the indexed reader page. A match elsewhere in a mixed page
does not certify the excerpt's own metre.

To prepare the remaining review queue without publishing classifications:

```sh
node chhanda_writer/pipeline/suggest.mjs --unreviewed --output /tmp/prosody-review.json
```

The report ranks exact spelling-based candidates and identifies uncertainty.
Review the original source before adding metadata. Record a precise note for
reading choices or source differences. After text or source changes, recheck
the evidence and update its fingerprint; the build rejects stale annotations.
Run the source validator, site-generator tests and
`NODE_PATH=<browser-test-dependencies> node pipeline/tests/browser/prosody.cjs`.
Set `PROSODY_TEST_URL` to the served site root for local or live checks.
