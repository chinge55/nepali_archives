# Chhanda writer rules

The `/kavita-lekhan/` writer analyses the spelling under an explicit verse reading.
The retired `/chhanda/` URL redirects to it, preserving query parameters and
fragments. The original local draft key stays unchanged for saved writing.

Every archive category is available in the writer: 31 named metres and मुक्तछन्द.
`catalogue.json` and `guides.json` supply the names, definitions and reviewed
examples; the site build emits `writer-data.json` for the editor. The same ids
drive browse-page writing links and the dropdown. Adding a category cannot leave
its writing link behind. No draft text is sent to the build or server.

The original ten classical fixtures retain their source-checked formulae:

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

A classical stanza has four पाउ, and a गजल शेर has two मिसरा; a newline,
slash, vertical bar, or danda separates पाउ. Blank lines separate stanzas.
Screen wrapping never changes the analysis.

**Form-specific writing assistance**

- Fixed वर्णिक patterns use syllable alignment and soft problem underlines.
  उपजाति accepts either component pattern for each pada. द्वादशाक्षरी उपजाति
  separately accepts वंशस्थ and इन्द्रवंशा.
- वियोगिनी and पुष्पिताग्रा alternate their odd/even templates by pada position.
  Blank lines restart the stanza position. The selected template also drives
  word suggestions and the displayed target count.
- The five बहर modes use their own feet. The classical final-short-as-long
  checkbox is hidden and never applied to them. An extra final short is allowed
  in the four reference forms that permit it, excluding हजज मुसम्मन सालिम.
- अनुष्टुप् provides eight-syllable count assistance. गीति counts 12/18 matras
  alternately, औपच्छन्दसिक 16/18, and पादाकुलक 16. Matching a count is labelled
  गणना मिल्यो, never a complete metrical match: internal rules and variant
  readings still need human review. Raw matra counts and the explicit final
  allowance remain visible. The optional अनुष्टुप् practice example separates
  the source's two padas into two lines without changing their words.
- झ्याउरे provides syllable counts with its folk-rhythm guide; मुक्तछन्द gives
  neutral counts. Neither imposes a universal fixed template or produces
  metrical error underlines. Their word choices are vocabulary suggestions.

Writing in any category preserves the same textarea, script detection, draft
storage, exports and undo history. A category chosen from a browse page presets
the writer while retaining the existing poem; reloading retains the saved mode.

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
The latter defaults to `http://localhost:8263/kavita-lekhan/`; set `CHHANDA_TEST_URL`
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

The next source review covers fifty further poems: forty-six reviewed
identifications and four uncertain single-stanza readings that stay unpublished.
This brings the published coverage to ninety-six works. The additions include
six full free-verse readings, a two-stanza mixed annotation for बालाजी, and
the archive categories वंशस्थ and उपजाति. The latter records the eleven-syllable
combination of इन्द्रवज्रा and उपेन्द्रवज्रा; it does not claim to cover every
other combination also called उपजाति in prosody texts.

A reviewed identification describes the poem's recurring form. Source-preserved
spelling, conjunct readings, avagraha, transcription differences and occasional
metrical departures can still prevent a literal scan from matching every pada.
These cases have specific review notes and spelling-based counts; the tags do
not certify faultless metre or completed text proofreading. Single-stanza cases
whose exceptional reading remains unexplained retain `status: uncertain`.

A further fifty source reviews add forty-nine published identifications and
one uncertain assessment, bringing coverage to 145 works. Four new mixed
annotations locate selected complete stanzas in वैराग्य वा सन्तोष, मनोलड्डु,
वधूशिक्षा and प्रश्नोत्तरमाला. These passage lists are deliberately partial;
for example, they do not label every metre change within प्रश्नोत्तरमाला's
stanza 35 or classify वधूशिक्षा's stanza 11. Five more free-verse readings
record positive structural observations on the complete poems.

The अनुष्टुप् category uses the closing stanza of मनोलड्डु, with eight syllables
per pada and the reviewed fifth-to-seventh positions. It has no universal
fixed `pattern` or writer preset. The preceding twenty stanzas are स्वागता.
कवि-कविताऽलाप's मालिनी ending is recognised in an uncertain assessment, while
the preceding metrical dialogue needs further review; it receives no public
tag and is not inferred to be free verse.

Single-page mixed works carry every reviewed metre filter in their indexed
body. Paginated works keep the filters local to the sections containing the
identified passages. This lets searches inside अनुष्टुप् find मनोलड्डु while
avoiding unrelated metre filters on other sections of a long work.

A further source review adds 42 published identifications: thirty single-metre
works, eleven mixed works and one complete free-verse reading, bringing coverage
to 187 works. The mixed annotations add 29 located complete stanzas. These
include six selected passages in रामायण and four in गङ्गा गौरी; neither list
claims to classify every stanza of those books. तीजको कथा similarly records
only its reviewed शार्दूलविक्रीडित and मालिनी examples. Candidates without a
declared preserved source remain pending. Literary texts and proofreading flags
are unchanged.

The added archive categories are पञ्चचामर, द्वादशाक्षरी उपजाति and वियोगिनी.
पञ्चचामर has eight light-heavy pairs. The twelve-syllable उपजाति combines
वंशस्थ and इन्द्रवंशा, distinct from the existing eleven-syllable category.
Its इन्द्रवंशा pattern follows the त त ज र formula in वृत्तरत्नाकर, verse 48
([source page](https://sa.wikisource.org/wiki/पृष्ठम्:वृत्तरत्नाकरम्.pdf/६८)).
वियोगिनी's reviewed ending alternates ten- and eleven-syllable padas, so it has
no universal fixed pattern or interchangeable-pattern list. These three browse
categories do not add unsupported writer presets.

The complete remaining-work assessment dated 2026-10-31 examines 492 works:
140 confirmed identifications (83 single, 20 mixed, 37 free verse) and 352
uncertain assessments. Across all 679 poetic works, 327 now have a confirmed
classification: 214 single, 37 mixed and 76 free verse. Every poetic work has
an assessment; 352 still await a confirmed identification. These counts
describe editorial coverage, not automatic classification accuracy.

The new mixed annotations locate 60 selected passages. Short source-backed
poems were read in full; long books were examined through selected complete
passages, source introductions and recurring structures. Book annotations
state their scope and do not claim a complete metrical edition. Refrains,
rhyming songs, bhajans, sonnets and unnamed folk rhythms are not automatically
free verse. Source-limited and unresolved readings retain their specific
`review_note`, text fingerprint and available source evidence, with no public
tag. Two works still lack a declared preserved source. The original literary
texts and every metadata field outside `prosody` are preserved.

The catalogue adds twelve archive categories: five bahr forms, विद्युन्माला,
मत्तमयूरी, प्रमाणिका, गीति, पुष्पिताग्रा, औपच्छन्दसिक and पादाकुलक.
The bahr feet follow the authors' [Urdu Meter handbook](https://franpritchett.com/00ghalib/meterbk/06_meters.html):
रमल मुसम्मन महजूफ is `GLGG / GLGG / GLGG / GLG`; हजज मुसम्मन सालिम is
`LGGG` four times; हजज मुसद्दस महजूफ is `LGGG / LGGG / LGG`;
मुतकारिब मुसम्मन महजूफ is `LGG / LGG / LGG / LG`; कामिल मुसम्मन सालिम
is `LLGLG` four times. Spelling-based Nepali candidates need manual readings;
the offline matcher does not apply Sanskrit final-short-as-long flexibility
to bahr. The handbook's extra unscanned final short is admitted only for
the four listed forms other than हजज मुसम्मन सालिम. These checks do not
implement the broader Urdu system of substitutions and word pronunciation.

Apte's appendix gives विद्युन्माला as eight gurus, मत्तमयूरी as म त य स गुरु,
and प्रमाणिका as ज र लघु गुरु. गीति uses 12/18/12/18 moras.
पुष्पिताग्रा alternates `LLLLLLGLGLGG` and `LLLLGLLGLGLGG` (12/13 syllables).
औपच्छन्दसिक's broader alternating 16/18-mora form has a र य ending;
प्रतिभा fits that form rather than वियोगिनी. These alternating forms are
not interchangeable single-pada templates. पादाकुलक's recurring 16-mora
form is supported by the source poems and the original
[पिँजराको सुगा study](https://gmmcjournal.edu.np/index.php/journal/article/download/99/62/160).
Additional झ्याउरे readings use the existing category and record their
16-syllable 5+5+6 gait, including spoken contractions; that folk form is also
described in [field research](https://elibrary.tucl.edu.np/bitstreams/40e854bd-01ee-446a-ac87-127150738383/download).
All twelve additions remain outside the writer's ten supported presets.

`assets/chhanda/catalogue.json` is the archive's build-time name and pattern
catalogue. A `pattern` is one fixed sequence; `patterns` lists the alternative
pada sequences of a family, never a simultaneous fixed template. Its writer
entries must agree with `metres.js`; पृथ्वी, स्वागता, वंशस्थ and उपजाति
are also checked against Apte's appendix, and झ्याउरे is source-labelled in
the author's own introduction to मुना मदन. Reader pages fetch no scansion
engine. `/chhandas/` and its metre pages are generated from reviewed metadata;
mixed-work links go to the identified passage, and search filters describe
metres present on the indexed reader page. A match elsewhere in a mixed page
does not certify the excerpt's own metre.

To prepare the remaining review queue without publishing classifications:

```sh
node chhanda_writer/pipeline/suggest.mjs --unreviewed --output /tmp/prosody-review.json
node chhanda_writer/pipeline/suggest.mjs --unassessed --output /tmp/prosody-unassessed.json
```

`--unreviewed` retains uncertain works that await confirmation; `--unassessed`
excludes a current recorded assessment even when its result is uncertain.
Text or source changes reopen that assessment, as does a newly available source
for a documented source gap. Neither flag changes metadata or publishes a tag.
The report ranks spelling-based candidates (including a family's alternative
patterns and final-syllable flexibility) and identifies uncertainty. An उपजाति
candidate still needs review of the actual combination within its stanzas.
Review the original source before adding metadata. Record a precise note for
reading choices or source differences. After text or source changes, recheck
the evidence and update its fingerprint; the build rejects stale annotations.
Run the source validator, site-generator tests and
`NODE_PATH=<browser-test-dependencies> node pipeline/tests/browser/prosody.cjs`.
Set `PROSODY_TEST_URL` to the served site root for local or live checks.
