# Chhanda writer plan

Draft · 2026-10-30 · Scope: a writing assistant at `/kavita-lekhan/`, named
**कविता लेखन**, within Nepali Archives.

**Writer identity revision, 2026-10-31:** use `/kavita-lekhan/`, navigation
**कविता लेखन**, heading **छन्दमा कविता लेखन**, and title
**छन्दमा कविता लेखन — नेपाली अभिलेख**. The retired `/chhanda/` URL redirects
with its query and fragment intact; keep the original browser draft storage key.
Only the new URL is indexed. `/chhandas/` remains the separate कविता browsing page.

**Writing interface revision, 2026-10-30:** keep one main writer with a
Devanagari/Roman toggle and a metre dropdown. Roman conversion happens in the
main writer. Show compact assistance for the active line; open examples,
learning material, detailed scansion, and word search only when requested.
This replaces the initial layout with numbered sections and a teaching sidebar.

**Initial draft implemented, 2026-10-30:** the static route now includes the
three launch metres, live scansion and explanations, pronunciation controls,
contextual word suggestions, shared Roman input, source-checked excerpts,
local drafts, undo/redo, and TXT/JSON export and import. The initial rules and
verification commands are in [`chhanda_writer/rules.md`](../chhanda_writer/rules.md).
The larger reference set, expert review, and broader beta in the roadmap
below remain later milestones; this draft does not claim their accuracy targets.

Help an author choose a छन्द, compose a poem, understand its लघु–गुरु pattern,
and revise a line while keeping control of the words and intended reading.
The first release should combine live analysis with practical help completing
a line. It should be free, require no account, and run in the browser.

This extends the educational role of the existing typing tool and fits the
[archive charter](../mission.MD). Drafts stay in the writer's browser; the
archive continues to preserve source works faithfully. A successful metre
check describes rhythm under stated rules, rather than judging literary merit.

**1. The writing experience**

The author chooses a metre from a short list. Each choice offers a plain Nepali
explanation, its expected pattern, its pauses (यति), and a reviewed example
linked to the original work. Advanced details such as गण can be expanded.

The central editor accepts direct Devanagari input and pasted text. An optional
Roman input mode uses the existing typing engine. Analysis follows committed
Devanagari text, so an unfinished Roman word or keyboard composition does not
produce distracting errors.

Below the active line, show the syllables aligned with the expected pattern.
Distinguish **मिल्यो**, **मिलेको छैन**, **अधुरो**, and **उच्चारण छान्नुहोस्**
with text and symbols as well as colour. The author can select a syllable to
see its classification and the relevant rule. Useful messages include:

- “यहाँ गुरु चाहिन्छ; तपाईंको पाठमा लघु देखियो।”
- “यो पाउ पूरा गर्न अझै ३ अक्षर चाहिन्छ।”
- “यो शब्दको उच्चारण छान्नुहोस्।”

Incomplete lines show the remaining pattern. A small word panel can filter
words by that pattern and a typed prefix; each result shows how it fits.
Selecting a word previews the whole resulting line before insertion. This
offers help composing a line without requiring the author to know गण names.

Provide undo/redo, browser-local draft recovery, copy, plain-text download,
and a project export/import containing the selected metre and pronunciation
choices. Keep the poem text separate from analysis marks in ordinary exports.
On mobile, keep the active line and compact feedback usable above the keyboard.
Detailed explanations and suggestions are available on request on every screen.

**2. First release scope**

Start with **भुजङ्गप्रयात, वसन्ततिलका, and शार्दूलविक्रीडित**. These give a small
set of fixed-pattern metres with examples available for review in the archive:
[शाकुन्तल](../archives/authors/devkota/shakuntala/text.txt) explicitly labels
passages with all three. Those labels identify candidate material; they do
not establish that its transcription or scansion has been verified.

Support selecting a target metre, analysing complete and partial पाउ, checking
a complete stanza, explaining mismatches, and finding words that fit a slot.
Let the author mark पाउ boundaries explicitly: a printed or pasted line can
contain more than one पाउ. Visual wrapping must never create a boundary.

After the first release, add अनुष्टुप् with its positional and variant rules,
then additional वर्णिक metres, followed by a separately specified मात्रिक
system. Track rhyme and metre as separate constraints. Pronunciation-based
rhyme search, reviewed recitations, rhythm playback, and guided exercises are
later additions. Automatic metre detection can follow once selected-metre
checking is reliable. Whole-poem generation, accounts, and public posting are
outside this release.

**3. Establish trustworthy Nepali rules first**

Use a deterministic analysis engine with a documented Nepali verse convention.
Keep metre definitions as data: syllable patterns, पाउ structure, यति,
permitted alternatives, citations, and reviewed examples. यति may involve
word boundaries and recitation; represent a firm rule separately from a
teaching suggestion.

The analysis path is:

`original text → analysis copy → possible readings → syllables and weights
→ target-pattern alignment → explanations and remaining slots`

Maintain offsets back to the original text. Unicode characters, visible
graphemes, and metrical syllables are different units; a character count is
not a scansion. Normalization must preserve the writer's spelling and keep
highlights aligned with the editor.

Document and test inherent-vowel retention or deletion, vowel sequences,
conjuncts and halant, anusvāra versus vowel nasalization, visarga, word
boundaries, and permitted पाउ-ending treatment. Review literary pronunciation
and older spellings alongside contemporary usage. The linguistic description
in [Khatiwada's Nepali phonology study](https://doi.org/10.1017/S0025100309990181)
is background for pronunciation work; verse conventions still require their
own sources and review.

When more than one reading is supported, expose the alternatives and let the
writer choose. A match depending on an alternative reading must say so.
Do not invent a pronunciation merely to satisfy the target pattern. An
explicit author override should remain visible and be invalidated when its
text changes. Unsupported or unresolved input receives an uncertainty message.

Build a reference set of about **240 reviewed पाउ**, balanced across the
three launch metres, plus deliberately broken lines and difficult word cases.
Record source work and page, syllable boundaries, weights, metre, pauses, and
accepted readings. Check archive examples against their source pages before
using them for teaching or evaluation. Keep annotations separate from the
canonical transcriptions and their `text.proofread` status.

Reserve examples by source work or passage for evaluation before tuning the
engine. Report syllable segmentation and weight accuracy separately from
whole-line decisions, with a separate breakdown for ambiguous readings.
An expert in Nepali छन्द should review the conventions and disputed cases;
the availability of that review determines the release schedule.

**4. Fit the existing static site**

Reuse the page-generation approach in
[`type_tool.py`](../pipeline/sitegen/pages/type_tool.py) and the engine API in
[`assets/type/engine.js`](../assets/type/engine.js). Share the transliteration
engine and its data, while keeping the chhanda editor controller independent.
Typing candidates and corpus frequencies are useful inputs for suggestions;
they do not constitute verified pronunciation or synonym data.

| Proposed location | Responsibility |
| --- | --- |
| `chhanda_writer/rules.md` | Sourced pronunciation conventions and supported cases |
| `chhanda_writer/data/` | Reviewed examples, annotation schema, and evaluation cases |
| `chhanda_writer/pipeline/` | Validate metre data and prepare a compact word index |
| `chhanda_writer/tests/` | Analysis, alignment, suggestion, and browser checks |
| `assets/chhanda/` | Browser engine, editor, page CSS, metre definitions, and shipped data |
| `pipeline/sitegen/pages/chhanda_tool.py` | Generate `/kavita-lekhan/` and install its assets |

Register the page in the builder, add navigation through the shared layout,
and cover it in build fixtures and the sitemap checks. Follow existing asset
versioning and load chhanda assets only on this page. Verify that shared typing
assets resolve correctly from both `/type/` and `/kavita-lekhan/`.

The engine should expose a structured result with syllable spans, possible
readings, weights, matched constraints, mismatch reasons, and remaining slots.
The UI and word-suggestion layer consume that result rather than duplicating
rules. Reanalyse the edited line and affected stanza, with a short debounce.

Prepare a small, reviewed vocabulary index with pronunciation alternatives
and provenance. Recheck each suggested word in the full line because adjoining
words can affect analysis. Label results as words fitting the pattern;
semantic or synonym claims require separately reviewed lexical evidence.

Ship the required browser data in the repository, following the existing
typing-lexicon convention. CI should build without downloading research
datasets. Draft text remains local and is never placed in URLs, site search,
or analytics. Use a separate, versioned storage key with graceful recovery
when browser storage is unavailable. Full offline page loading would require
an explicit caching design; browser-side analysis alone does not provide it.

**5. Delivery sequence**

| Stage | Deliverable | Completion condition |
| --- | --- | --- |
| 1. Rules and examples | Three sourced metre definitions, pronunciation conventions, annotation format, reviewed reference set | A reviewer can explain every expected reading; disputed cases are identified |
| 2. Analysis prototype | Standalone engine returning syllables, weights, alternatives, and target alignment | Reviewed regression cases pass; held-out results and failure categories are recorded |
| 3. Writing prototype | Editor, live comparison, remaining-pattern hints, bounded word suggestions, and pronunciation controls | A writer can compose and repair a complete stanza using the interface |
| 4. Site integration | `/kavita-lekhan/`, optional Roman input, examples, draft recovery, exports, navigation, and styles | Desktop and mobile flows work; typing-tool regressions and site checks pass |
| 5. Beta and refinement | Trial with beginners and experienced poets, fixes to rules and explanations | Users can finish a stanza and understand the feedback; material confident misclassifications are resolved |

Budget roughly **4–6 weeks of focused work** for a first public version,
assuming a developer and timely access to a Nepali छन्द reviewer. This is a
planning estimate; stage 1 should establish whether annotation and pronunciation
disagreements require more time. A useful private prototype should precede
broader vocabulary, more metres, or recitation features.

**6. Release checks**

- Preserve the exact draft through typing, paste, composition, candidate
  insertion, undo/redo, reload, and export/import. Corrections require an
  explicit writer action.
- Verify segmentation, weight classification, missing/extra-syllable alignment,
  पाउ mapping, and accepted variants. Check that missing one syllable does not
  misleadingly mark every subsequent syllable as wrong.
- Report held-out accuracy with counts, confident false rejections, false
  acceptances, and unresolved cases. As provisional beta targets, aim for at
  least 98% correct syllable weights on unambiguous examples and at most 2%
  confidently rejected valid पाउ. Fix thresholds after the reference set is
  reviewed, before tuning; syllable accuracy alone cannot establish reliability.
- Test mobile keyboard composition, narrow screens, light/dark themes,
  keyboard-only operation, screen-reader descriptions, and storage failures.
  Analysis announcements should not interrupt every keystroke.
- Aim for active-line feedback within 100 ms after debounce on a representative
  lower-end phone. Measure the prototype before adding a worker or larger data.
- Run focused engine and browser checks, existing typing-tool regressions,
  site-generator tests, a dry-run build, and the internal-link audit through
  the repository's `verify-site-change` workflow. Verify that draft text never
  leaves the browser and that reader pages load no chhanda assets.

**7. Research boundary and first implementation task**

[Chandojñānam](https://arxiv.org/abs/2209.14924) provides prior work on Sanskrit
scansion and approximate metre matching. Those methods inform the design;
their performance does not establish Nepali correctness. Its
[published implementation](https://github.com/hrishikeshrt/chandojnanam) uses
AGPL-3.0. Follow the existing typing project's permissive-license convention
for shipped dependencies and data, and write the core engine independently
from sourced rules. Review licences before importing code, databases, or
teaching examples from other tools.

Start by writing `chhanda_writer/rules.md`, defining the three metre records,
and reviewing a small sample spanning all three metres and the difficult
pronunciation cases. Use that sample to build the analysis prototype, then
complete the reference set and evaluation split before expanding the editor.
