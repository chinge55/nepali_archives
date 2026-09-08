# Sahitya Ras ingestion

The full **66-book catalogue** has been fetched at pinned revisions, inventoried,
compared with the archive, and assigned explicit source decisions. The larger
batch adds **427 works**, following the 17-work pilot: **444 new works in total**.
The local archive now contains **672 works across ten authors**.

This is transcription reuse and source-fidelity checking, **not printed-page
proofreading**. Every new work remains `text.proofread: false`. Existing literary
texts are unchanged; collection associations are added where work identity is
established. A matching archive work may represent a different or shorter edition;
that match does not assert complete coverage of the source edition.

- [Per-book results](catalogue-status.csv): all 66 books, counts, and deferral reasons.
- [Reviewed catalogue manifest](catalogue.json): source revisions, document hashes,
  reading order, exclusions, repairs, destinations, and exact output hashes.
- [Author records](authors.json): canonical identities and eligibility evidence.
- [Original pilot manifest](chilla-patharu.json): historical record of the first
  चिल्ला पातहरू batch. The full catalogue manifest is authoritative for reruns
  after later collection associations have been applied.

## What is retained

Collections become separate member works. Long narratives remain single works
with source sections in reading order. Authorial prefaces, dedications, original
wording, period spelling, punctuation, repetition, verse lines, numbering, and
indentation are preserved. Original-author credits remain in translated essays;
the metadata identifies Devkota as the Nepali translator. The traditional Sanskrit
hymn in गुण रत्नमाला is labelled as Sanskrit and its collection attribution does
not claim original composition by the compiler.

Notes are read across the whole XHTML body, including those outside the literary
container. Reference markers stay with the text; retained notes follow their
source section with the original reference label. Brief unsigned factual glosses
remain source apparatus, without an assertion of authorship. Lengthier disputed
commentary is held for attribution review. Later editorial material is excluded
from **both literary text and public HTML captures**. Captures also omit external
assets and executable content; original input hashes remain in the manifest.

Recorded repairs remove only demonstrable wiki-template debris and identified
later publication tails. Source gaps are preserved; missing lines are never
supplied from a different edition. HTML formatting whitespace is normalized in
captures. The importer rejects unknown structures, broken note references,
unaccounted documents, source drift, and unexpected destination changes.

## Remaining source decisions

- **Four Shankar Lamichhane books:** outside the archive's publication gate until
  2027; see the author record and its cited evidence.
- **मायाविनी सर्सी:** longer unsigned glossary apparatus needs attribution review.
- **भानुभक्तका फुटकर रचनाहरू:** one XHTML contains 39 numbered members; several
  match existing works, but remaining semantic boundaries need edition comparison.
  It is not published as a duplicate anthology work.
- **प्रेम in चिल्ला पातहरू:** possible variant of existing प्रेमपत्र; held for
  edition comparison. साउन is now represented by the matching song-collection
  transcription under साउन आउँछ, with both collection associations recorded.

The ledger therefore accounts for all books while making these incomplete source
decisions visible. Excluded editorial prose and deferred texts remain only in the
ignored working cache.

## Reproduce the reviewed batch

Fetch the exact recorded revisions, without following newer upstream changes:

```sh
python3 pipeline/sahityaras_fetch.py --manifest sources/sahityaras/catalogue.json
python3 pipeline/sahityaras_catalogue.py sources/sahityaras/catalogue.json .ingest-work/sahityaras/catalogue --stage .ingest-work/sahityaras/review-drafts
```

Inspect the staged sources, then apply the same manifest:

```sh
python3 pipeline/sahityaras_catalogue.py sources/sahityaras/catalogue.json .ingest-work/sahityaras/catalogue --apply
```

All outputs are checked before writing. Equal files are left alone; rerunning the
applied batch writes zero files. Existing text and metadata baselines are pinned.
A later deliberate correction must receive a new reviewed manifest decision;
rerunning an old import must not undo it. Writes are atomic per file and resumable,
not a transactional replacement of the whole archive.

The original 17-work pilot must already be present in a checkout using this full
batch's 245-work baseline. Normal site builds require no source fetching, service,
backend, or ingestion cache. Only canonical source files and public provenance
belong in Git; reader HTML, EPUBs, fonts, search output, and `site/` are rebuilt.

## Validation

Source snapshots for all 66 repositories and output hashes were verified.
Independent draft checking covered all 427 additions, followed by coordinator
resolution of the flagged source details. All metadata validates against the
archive schema, all new EPUBs preserve their text and meaningful stanza/line
boundaries, and source captures pass the HTML sanitation check. The site build,
search indexing, and internal-link audit pass. All 72 regression tests pass; the
browser sweep covers all 427 new readers, including paginated text and mobile
layout. Nepali/Roman title search, full-text search, and highlighting pass.
See the [validation record](validation.json) for counts and limits.

The larger corpus exposed two reader issues fixed with this batch: explicit verse
line breaks now survive EPUB conversion, and long contents links wrap on mobile.
