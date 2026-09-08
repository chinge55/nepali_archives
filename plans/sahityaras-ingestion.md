# Sahitya Ras ingestion plan

Status: full 66-book catalogue pass implemented locally; explicit deferred material
is listed in the [per-book results](../sources/sahityaras/catalogue-status.csv).
See [results and reproduction steps](../sources/sahityaras/README.md).
The pilot and full pass add 444 works in total (17 + 427); existing literary texts
remain unchanged. No new source text is marked proofread.
Research date: 2026-09-08. Archive baseline: 228 works, five authors, commit `0cbb9c3`.

## Objective and governing rule

Bring eligible literary works from Sahitya Ras into Nepali Archives while being
faithful to their authors. Preserve wording, period spelling, punctuation, verse
lines, stanzas, numbering, intentional repetition, authorial headings, and the
author's own prefaces and notes. Exclude later third-party editorials, publisher
introductions, modern commentary, and website furniture. Unknown authorship is a
review item, not permission to guess or silently delete a passage.

A successful import is a traceable, complete transcription of an identified
edition. It is not a rewrite, an automatic replacement of an existing text, or a
claim that the original printing has been proofread.

## What has been checked

A direct fetch of the [book catalogue](https://sahityaras.com/book/) found **66
book records**. The [author directory](https://sahityaras.com/book-author/) lists
**11 authors**. The public repository listing linked by the website contains 67
repositories: all 66 catalogue slugs match book repositories; the remaining
repository is a font project. Cached search results showed fewer books, so the
attached inventory uses the direct-fetch snapshot.

| Author as listed by the source | Books | Archive onboarding |
|---|---:|---|
| लक्ष्मीप्रसाद देवकोटा | 31 | Existing author |
| लेखनाथ पौड्याल | 13 | Existing author |
| मोतीराम भट्ट | 5 | Existing author |
| भानुभक्त आचार्य | 5 | Existing author |
| भीमनिधि तिवारी | 2 | Existing author |
| शङ्कर लामिछाने | 4 | New author |
| हृदय चन्द्र सिंह प्रधान | 2 | New author |
| गोपालप्रसाद रिमाल | 1 | New author |
| जगन्नाथ उपाध्याय गुरागाञीं | 1 | New author; verify canonical name |
| बाबुराम आचार्य | 1 | New author |
| गुरुप्रसाद मैनाली | 1 | New author |

Thus 56 book records concern existing authors and ten concern six new authors.
Book counts are not new-work counts: anthologies split into member works, and
many works are already present. The attached [catalogue](sahityaras-catalogue.csv)
contains all 66 source URLs, repository mappings, default branches, and preliminary
local matches. Sixteen book titles match local work titles after comparison-only
normalization; these are **candidates**, not confirmed duplicates. For example,
a collection and one of its poems can have the same title.

Three complete source-package structures were sampled:

| Source package | Pinned revision | Reading-order entries | Findings |
|---|---|---:|---|
| [चिल्ला पातहरू](https://github.com/sahityaras/chilla-patharu/tree/ad7c67f1eefe42485f3cba9bf7a3c365fb74f069) | `ad7c67f1eefe42485f3cba9bf7a3c365fb74f069` | 27 | Four publication wrapper files, one third-party editorial, 22 poems |
| [मुनामदन](https://github.com/sahityaras/munamadan/tree/f5ed8db70ce2c23d9cca0d31e37b49856ad34ecc) | `f5ed8db70ce2c23d9cca0d31e37b49856ad34ecc` | 9 | Four wrapper files and five authorial sections; footnotes present |
| [लक्ष्मी निबन्धसङ्ग्रह](https://github.com/sahityaras/laxmi-nibandhasangraha/tree/831ac1e09b4b613c04118f61644aaa20b9940227) | `831ac1e09b4b613c04118f61644aaa20b9940227` | 42 | Four wrapper files and 38 literary entries, including the author's भूमिका; notes present |

These packages contain `src/META-INF/container.xml`, an EPUB package manifest
and spine, navigation files, and individual XHTML texts. Their default branches
vary between `main` and `master`. Only these three packages have been inspected
in depth; remaining package layouts, work counts, exclusions, and textual overlap
must be audited during implementation.

A concrete incompatibility was reproduced with the current `from_html.py`:
the sampled “आरोही प्रति” contains 13 double-`br` stanza boundaries, but the generic
extractor returns only four blocks and omits its `div.chapter-title`. Its generic
consecutive-block deduplication is also unsuitable for authorial repetition.
**Do not run the generic extractor over this source collection unchanged.**

## Source route: repositories first, website for cross-checking

1. Discover book URLs from the catalogue, author pages, and the sitemap index
   advertised by [robots.txt](https://sahityaras.com/robots.txt):
   `https://sahityaras.com/sitemaps.xml`. Deduplicate navigation links.
2. Map each book to the public repository linked by the source project. Resolve
   its actual default branch to a full commit ID and freeze that revision for the
   batch. Record the fetch date and source-file SHA-256 values.
3. Read the EPUB container to locate the OPF, then resolve manifest IDs through
   the **spine** for reading order. Cross-check `nav.xhtml`, `toc.ncx`, the printed
   contents where available, and the website's contents list. Never alphabetize
   chapter filenames or assume one file equals one literary work.
4. Read the XHTML directly. Use the downloadable EPUB if a repository is missing
   or demonstrably behind the website. Use carefully scoped HTML extraction only
   as the fallback. Disagreements between versions require a recorded selection;
   do not combine editions silently.
5. Use an identifiable archival fetcher, one request at a time, caching, an
   initial delay of approximately one second, and backoff for rate-limit/server
   responses. Respect current crawl directives; fetch only needed files. No
   source fetching during normal site builds or deploys.

The sampled XHTML contains MediaWiki-style wrappers, suggesting an earlier
transcription source. This is a lead to investigate, not proof of independent
verification or a sufficient bibliographic citation. Trace an underlying scan
when needed to resolve a disputed reading.

The EPUB's digital publisher and creation date are **not** the original book's
publisher or first-publication date. For example, the website identifies a
particular [मुना मदन edition](https://sahityaras.com/book/munamadan/). Record the
edition used, preserve the distinction from first publication, and leave unknown
fields null. Do not label a digitally typeset PDF as an original page scan.

## A ledger that accounts for every source section

Keep public, factual manifests under `sources/sahityaras/`.
The working directory `/.ingest-work/` is git-ignored. Raw
packages, excluded content, draft texts, and review diffs stay in that ignored
workspace, outside `archives/authors/`, until a batch passes its checks.

Each book record should contain:

- Website URL, repository URL, full revision, fetch date, input hashes, edition,
  source author, canonical archive author ID, and book type.
- Every reading-order item and every otherwise-unreferenced text document,
  including fragments within mixed-content files.
- For each section: source path/fragment, order, title, classification, decision
  reason, destination work ID, and review state.
- Existing-work matches, comparison results, expected output hashes, and baseline
  hashes for every local file the importer proposes to modify.

Every source segment must have one explicit disposition: **include**, **exclude
with reason**, **map to an existing work**, or **defer with reason**. A section may
be split into multiple segments when an editorial note is embedded in the work.
Nonlinear spine items and manifest-only notes must also be accounted for.

The materializer must refuse a work with missing required sections, unresolved
internal references, or undecided content. Other independently complete works in
the same anthology can proceed. Reports must show deferred items rather than
claiming that the entire book or source project is complete.

## Separating the author from later additions

Use authorship and evidence, not title keywords alone.

| Content | Decision |
|---|---|
| Original poem, story, essay, canto, or chapter | Include in its proper work |
| Author's own भूमिका, dedication, epigraph, or note | Keep with the appropriate work or existing standalone entry |
| Later editorial, foreword, publisher introduction, or modern annotation | Exclude from published text **and public source captures** |
| Source site's description, sharing controls, digital title/copyright pages | Omit from literary text; retain necessary factual attribution separately |
| Authorial and editorial material mixed in one file | Mark exact boundaries and inspect the resulting joins |
| Unattributed note or uncertain boundary | Defer that decision; do not infer authorship from proximity |

For a concrete exclusion, the [चिल्ला पातहरू editorial](https://sahityaras.com/book/chilla-patharu/sampadakiya/)
is signed by शिवगोपाल रिसाल. Conversely, the sampled [लक्ष्मी निबन्धसङ्ग्रह
भूमिका](https://github.com/sahityaras/laxmi-nibandhasangraha/blob/831ac1e09b4b613c04118f61644aaa20b9940227/src/EPUB/text/bhumika.xhtml)
is signed लक्ष्मीप्रसाद and is to be retained. A blanket “delete all भूमिका” rule
would violate this plan.

Record the source and author rights basis using the archive's existing rules.
The source's [reuse terms](https://sahityaras.com/terms-of-use/) encourage
redistribution with conditions; preserve appropriate source credit and distinguish
our edition from theirs. Apply the existing public-domain/permission-granted gate
per work. The plan does not treat nonprofit status or an author's death alone as
that determination. Unclear cases remain separate while established cases proceed.

## Literary boundaries and duplicate handling

- **Collections:** materialize each independent member as a work. Represent the
  book through the existing collection description convention. A collection is
  not an additional duplicate work.
- **Continuous works:** assemble an epic, novel, or narrative poem in source order
  as one work, retaining authorial section headings. Do not turn its chapters into
  separate catalogue entries merely because the EPUB stores separate files.
- **Multipart works and excerpts:** compare the entire text and containment within
  larger works. A renamed excerpt from रामायण is not automatically a new work.
- **Same title, different text:** compare authorship and content before merging.
  **Different title, same text:** resolve the alias and retain the existing ID.

Run two passes before deciding what to add:

1. A catalogue pass matches canonical authors, title variants, aliases, and
   collections before downloading their literary text.
2. A content pass checks exact hashes, normalized comparison hashes, distinctive
   beginning/end passages, token-shingle overlap, and passage containment against
   all existing texts and other incoming works. Similarity only nominates matches;
   it never authorizes a replacement or silently folds spelling variants.

Normalization is for comparison keys only. `text.txt` must retain the chosen
source's spelling and meaningful characters. For example, source “जुवा” and local
“जूवा” should be investigated as a possible duplicate, not automatically normalized
to the same published spelling.

Decision outcomes:

- New independent work: add after checks.
- Existing equivalent work: retain its text and ID; add a verified collection
  association where missing, and record the additional source in the ledger.
- Existing work with suspected OCR errors: propose a separate, passage-level
  correction diff and verify against the identified source before applying.
- Different edition or uncertain overlap: retain the existing work and defer the
  change until the edition difference is understood.

Never overwrite an existing source PDF, provenance, text, or proofread flag merely
because the newly obtained XHTML is cleaner-looking. Protect local edits using
baseline hashes; a changed file invalidates the proposed application.

## Extraction contract and necessary implementation

The first implementation provides offline inventory/extraction in
`pipeline/sahityaras_ingest.py` and reviewed staging/application in
`pipeline/sahityaras_batch.py`. Discovery, fetching, broader classification, prose,
and note handling remain proposed work for later bounded batches. Reuse the existing metadata,
slugging, sanitization, and validation utilities without changing generic
extraction behavior for unrelated sources.

The adapter must:

- Parse namespace-aware XHTML and OPF without fetching external entities.
  Reject archive paths and references that escape the package.
- Recognize source constructs such as `.chapter-title`, `.poem`, paragraph tags,
  explicit line breaks, centered lettered section labels, and indented spans.
- Preserve double line breaks as stanza boundaries; join only ordinary HTML
  formatting whitespace in prose. Avoid globally stripping Unicode joiners,
  converting numerals, modernizing punctuation, or merging repeated stanzas.
- Preserve authorial headings once at their semantic position. Do not invent
  headings or numbering to trigger our renderer's pagination heuristics.
- Inventory every note marker and note body. Retain authorial notes with a clear
  plain-text reference convention, remove confirmed later editorial notes, and
  prevent orphan markers. Verify footnote labels remain distinguishable from
  stanza numbers in HTML and EPUB. The current reader has no explicit footnote
  model; note-bearing works require a tested convention before publication.
- Preserve an included source XHTML/HTML excerpt for each output, with title,
  author, edition, source path, and source revision recorded. Do not publish a full
  source package that restores material intentionally excluded from `text.txt`.
- Fail clearly on unknown structural constructs rather than returning a plausible
  but incomplete text. Table-heavy material, drama, complex alignment, or mixed
  prose/verse must receive a rendering decision before that work is materialized.

Mapping into the current archive:

| Field or artifact | Mapping |
|---|---|
| Work and author IDs | Existing IDs when matched; otherwise reviewed `devanagari_slug.py` output |
| `source.name` / `source.url` | Sahitya Ras and the appropriate book or member page |
| `source.html` | An included-content source file under the work's `extracted/` directory |
| Additional source/revision mappings | The public ingestion ledger; no unrecognized metadata fields |
| `text.extraction_method` | `html` for XHTML/HTML extraction |
| `text.ocr_status` | `born-digital` under the existing import convention; not a claim about upstream OCR history |
| `text.proofread` | `false` for newly imported works until the separate proofreading stage |
| `edition`, `publisher`, `first_published` | Bibliographic evidence; no substitution of digital generation dates |
| Collections | First sentence: `From the collection X; Y.` using canonical collection names |
| Formats | Canonical TXT, then our generated HTML/EPUB; PDF only when its edition and contents are established |

The existing author registry is in `pipeline/sitegen/config.py`. Its prose genres
already include `katha`, `nibandha`, and `upanyas`; do not misclassify stories as
verse based on older notes. New authors also need canonical names, sourced life
dates/rights basis, and the relevant `STATS_STOP` review.

## Pilot and rollout

### Pilot: three deliberately different packages

1. **चिल्ला पातहरू:** account for all 27 spine items; exclude the four publication
   wrappers and the signed editorial from literary outputs; classify all 22 poems.
   Three titles already match local works: आरोहीप्रति, माघको खुलेको बिहान, and
   सालपाते फट्याङ्ग्रोलाई. Check all remaining poems for content aliases. This tests
   new works, collection overlap, lettered sections, and stanza preservation.
2. **लक्ष्मी निबन्धसङ्ग्रह:** account for all 42 spine items and all 38 literary entries.
   Thirty-seven titles have normalized local matches; “जुवा” needs the explicit
   “जूवा” comparison. Retain the authorial भूमिका. Expected purpose: prove that an
   already-covered collection does not generate duplicates, and inspect prose
   and note handling. Do not promise additions from this book.
3. **मुनामदन:** map the five authorial source sections to our existing work, which
   has a different section breakdown. Compare complete passage coverage, notes,
   opening and closing text, and edition details. Different chapter counts alone
   prove neither missing content nor equivalence. This is a comparison exercise,
   not an automatic replacement.

For the pilot, review every included output and every exclusion, not just a sample.
Also run small synthetic regression fixtures for consecutive `br` stanza breaks,
repeated refrains, `.chapter-title`, inline formatting, missing spine references,
notes, title collisions, anthology splitting, and reruns over locally edited work.

### Rollout after the pilot passes

- First add complete, genuinely new works and anthology members by the five
  existing authors, in small book-sized batches. Finish one book's accounting
  before marking it covered.
- Then onboard the six additional authors and process their ten book records,
  applying the same fidelity and author checks.
- Handle large works, unusual genres, and disputed editions in dedicated batches
  with full section inventories. Compare potential improvements to existing
  archive texts separately from net-new additions.
- Report new works, unchanged matches, added collection associations, proposed
  corrections, exclusions, and deferred cases separately. There is no defensible
  total of new works until the section inventory and content deduplication finish.

Implementation estimate: approximately 5–9 focused working sessions for the
inventory/adapter, fidelity fixtures, pilot, and import tooling. Full-corpus review
and source-based proofreading are additional, unestimated work; the pilot should
establish their actual throughput.

## Acceptance, publication, and maintenance

A work passes only when all its source segments are accounted for, original order
is preserved, source references resolve, excluded material is absent from public
outputs, duplicate decisions are recorded, and every textual change is explainable.
Compare ordered DOM text to extracted text with a narrow, documented allowance
for HTML formatting whitespace. Check stanza/line boundaries separately: matching
word counts or hashes after aggressive normalization is not sufficient.

Re-running a frozen batch must produce the same outputs and **no proposed changes**
when the archive already contains that batch. Writing a new batch must use an
explicit path allowlist; abort rather than overwrite an unexpected local change.

Before publication:

1. Run `pipeline/validate.py`, the adapter's fidelity/coverage tests, and the site
   test suite. Review all proposed text and metadata changes.
2. Build the index and formats for changed works, build the site, regenerate the
   font subset if the glyph set changed, rebuild if needed, and regenerate search.
3. Run the internal-link audit. Inspect HTML, EPUB, long-work navigation, notes,
   source attribution, search results, and mobile verse rendering.
4. Inspect the exact staged paths and full diff; run `pipeline/check_public_tree.py`.
   Only included source material, metadata, canonical texts, tooling, and factual
   ledgers belong in the public tree. Unrelated unfinished book files stay untouched.
5. Commit and push only when authorized; confirm the live deployment. A bad batch
   is corrected or reverted in its own commit, without discarding unrelated work.

Keep this ingestion offline and maintainable: no backend, service, database, or
runtime dependency on Sahitya Ras. Periodic discovery can nominate upstream
changes, but nothing automatically rewrites published texts. Compare three
versions when a source changes: the previous pinned source, the new source, and
our locally corrected text. Preserve our verified corrections; unresolved conflicts
remain review items. Source removals do not automatically delete preserved works.

The milestone is **every discovered book accounted for and every published work
faithful to its identified source**, with unresolved matters explicitly listed.
Formal proofreading remains a separate stage and flag.
