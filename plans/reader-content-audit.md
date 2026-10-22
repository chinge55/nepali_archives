# Reader content audit — 2026-10-22

Scope: all 796 works in the current source tree, all 15 paginated works, and all
1,848 generated HTML pages. This is a structural/content-presence audit, not
proofreading against every source scan.

## Confirmed defects and correction

The splitter treated consecutive chapter labels as separate sections. Some
imports contain both a navigation label and the printed heading. This created
five empty reader pages and three pages containing only title material.

| Work | Redundant routes → retained content routes | Content sections before → after |
|---|---|---|
| नेपालको सङ्क्षिप्त वृत्तान्त | 2 → 3; 4 → 5; 6 → 7; 8 → 9 | 9 → 5 |
| सृजामाता | 1 → 2; 6 → 7 | 7 → 5 |
| गङ्गा गौरी | 1 → 2 | 6 → 5 |
| श्रीमद्भगवद्गीताको गीतासार | 1 → 2 | 19 → 18 |

The paginator joins empty boundaries to their text, and joins title-only
material when the same chapter heading immediately follows. It does not merge
real short texts just because they have few words. Intervening book titles and
literary text remain present. Exact redundant chapter labels are represented
once. The pagination correction itself does not alter transcriptions. A second
pass separately corrected 16 verified importer-added headings, described below.

Existing content URLs retain their original numbers. The eight redundant URLs
are static, immediate meta-refresh redirects with a visible fallback link,
`noindex,follow`, and a canonical pointing to the destination. They are not HTTP
301 responses. They have no Pagefind body and are excluded from both sitemaps.
Contents and previous/next navigation point directly to retained content pages.
Displayed section positions remain consecutive even when URL numbers have gaps.

## Whole-archive results

- Before: 941 literary reader pages, including 160 chapter pages; eight structural errors.
- After: 933 literary reader pages, including 152 chapter pages; eight compatibility redirects.
- No remaining empty or heading-only chapter bodies.
- No missing reader bodies, orphan chapters, contents/title mismatches, duplicate
  contents links, or previous/next mismatches detected.
- No exact duplicate literary-body groups found among texts of at least 20 words.
  An additional overlap scan found no pair sharing at least 100 words in identical
  blocks of 20+ words that cover half or more of the smaller reader body. This
  threshold does not rule out shorter overlaps or rewritten near-duplicates.
- All 796 source texts were compared with independently parsed reader HTML:
  20,861 non-heading body blocks remain present in source order. Headings are
  checked for presence separately because page-title promotion and redundant
  navigation-label merging can change their position or occurrence count.
- Internal links and sitemap/metadata audits pass. The site retains 1,848 HTML
  files because compatibility redirects replace the removed chapter documents;
  its indexable URL count drops by eight to 1,004.

## Repeated-heading review

The first pass flagged 38 pages with repeated heading text. A second pass
reconciled the four unresolved works with their retained source HTML and the
hash-checked source packages. It confirmed 16 importer-added labels:

| Work | Extra labels removed | Source material preserved |
|---|---|---|
| सीता-हरण | One opening प्रथम पाद | Book title followed by the printed प्रथम पाद |
| तिप्लिङ्गी | Thirteen paired पादः labels | All thirteen printed headings, subtitles and verses |
| अमर-ज्योतिको सत्य-स्मृति | One opening पूर्व स्मृति | Title, printed opening and closing स्मृति markers |
| मेरो राम | One opening माहात्म्य सार | Invocation, printed opening and closing markers |

Only these extra labels and their separating blank lines were removed. An earlier
spelling repair in तिप्लिङ्गी was retained. The four works remain `proofread:false`.
The import manifest now explicitly records where a printed heading already exists;
the importer verifies its presence before omitting the added label. Updated output
hashes reproduce for all four revised source manifests.

The final audit retains 37 review signals: 31 page titles also occur inside the
literary text, four pages contain refrains/scene markers (सब परमेश्वरका रूप,
कविताको खोजी and two halves of मसान), and two works retain printed opening/closing
markers (अमर-ज्योतिको सत्य-स्मृति and मेरो राम). None creates another empty URL.
Warnings remain visible rather than being suppressed by an allowlist.

## Additional adversarial checks

Two synthetic pagination cases exposed further defects: a multiline preface
heading lost text after its first line, and a chain of empty distinct headings
could reverse their order. Both are corrected, with regression tests for leading
and trailing chains. The current corpus comparison found no missing body blocks.

The audit now rejects unexpected noindex work/chapter pages, including source
works missing entirely from the generated site. Previous/next links must remain
on the archive's host. Regression fixtures deliberately remove/reorder paragraphs
and drop a repeated stanza to confirm that the source comparison catches them.

Validation: 156 unit/fixture tests run successfully (five optional skips), metadata
validation for 796 works, internal links across 1,848 HTML files, and SEO validation
for 1,004 indexable pages. Browser checks cover all eight redirects at desktop and
mobile widths, visible body text and search results pointing to the retained URL.

This does not establish that every transcription matches its scan, or rule out
near-duplicate works. It checks the generation and chapter-structure failure modes
reported here.

## Reproducible check and deployment gate

Run after building the site:

```sh
python3 pipeline/check_reader_content.py site --sources archives --report /tmp/reader-content-audit.json
```

The report contains errors, counts, duplicate-body groups and every review path.
Both pull-request validation and deployment run this check. Empty bodies,
heading-only chapters, missing/orphaned chapters, incorrect contents labels,
invalid redirects, missing/reordered source body blocks, unexpected noindex readers
and broken chapter navigation fail the check. Short texts,
repeated headings and exact body duplicates are review signals, not grounds for
automatic deletion.
