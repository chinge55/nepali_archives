import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prosody import annotation_anchors, load_metres, published_metres, published_prosody, text_digest, validate_prosody


class ProsodyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.text = 'पहिलो पाउ यहाँ छ ।\nदोस्रो पाउ यहाँ छ ॥\n\nतेस्रो पाउ यहाँ छ ।\nचौथो पाउ यहाँ छ ॥\n'
        (self.work / 'text.txt').write_text(self.text)
        (self.work / 'source.html').write_text('<p>Preserved source fixture</p>')
        self.annotation = {
            'status': 'reviewed', 'kind': 'single', 'metres': ['bhujanga'],
            'text_sha256': text_digest(self.text), 'reviewed': '2026-10-30',
            'evidence': [{'basis': 'metrical-reading', 'file': 'source.html',
                          'sha256': hashlib.sha256((self.work / 'source.html').read_bytes()).hexdigest(),
                          'locator': 'whole poem', 'note': 'Reviewed verse fixture.'}],
        }
        self.metadata = {'genre': ['kavita'], 'source': {'html': 'source.html'}, 'prosody': self.annotation,
                         'text': {'proofread': False}}

    def test_reviewed_annotation_is_separate_from_text_proofreading(self):
        before = copy.deepcopy(self.metadata)
        self.assertEqual(validate_prosody(self.work, self.metadata), [])
        self.assertEqual(published_metres(published_prosody(self.metadata, self.text)), ['bhujanga'])
        self.assertEqual(self.metadata, before)

    def test_uncertain_assessment_is_not_published_or_inferred_as_free_verse(self):
        self.annotation.update(status='uncertain', kind='unresolved', metres=[])
        self.assertEqual(validate_prosody(self.work, self.metadata), [])
        self.assertIsNone(published_prosody(self.metadata, self.text))
        self.assertEqual(published_metres(None), [])

    def test_free_verse_requires_its_own_reviewed_kind(self):
        self.annotation.update(kind='free-verse', metres=[])
        self.assertEqual(validate_prosody(self.work, self.metadata), [])
        self.assertEqual(published_metres(self.annotation), ['muktachhanda'])
        self.annotation['metres'] = ['malini']
        self.assertTrue(any('free verse' in e for e in validate_prosody(self.work, self.metadata)))

    def test_source_limited_assessment_keeps_a_note_without_publishing_a_guess(self):
        self.annotation.update(status='uncertain', kind='unresolved', metres=[], evidence=[],
                               review_note='Preserved source unavailable; metre unresolved.')
        self.assertEqual(validate_prosody(self.work, self.metadata), [])
        self.assertIsNone(published_prosody(self.metadata, self.text))
        for value in ['', '  ', None, False]:
            self.annotation['review_note'] = value
            self.assertTrue(any('review_note' in error for error in validate_prosody(self.work, self.metadata)))

    def test_text_or_source_edits_invalidate_a_review(self):
        (self.work / 'text.txt').write_text(self.text + 'बदलिएको पाठ')
        self.assertTrue(any('stale' in e for e in validate_prosody(self.work, self.metadata)))
        self.assertIsNone(published_prosody(self.metadata, self.text + 'बदलिएको पाठ'))
        (self.work / 'source.html').write_text('changed')
        self.assertTrue(any('source file' in e for e in validate_prosody(self.work, self.metadata)))

    def test_unknown_or_incomplete_classifications_are_rejected(self):
        self.annotation['metres'] = ['invented']
        self.assertTrue(any('unknown metre' in e for e in validate_prosody(self.work, self.metadata)))
        self.annotation.update(kind='mixed', metres=['bhujanga', 'malini'])
        self.assertTrue(any('located passage' in e for e in validate_prosody(self.work, self.metadata)))
        self.annotation.update(kind='unresolved', metres=[])
        self.assertTrue(any('cannot be marked reviewed' in e for e in validate_prosody(self.work, self.metadata)))

    def test_mixed_work_requires_unique_located_nonoverlapping_passages(self):
        lines = self.text.splitlines()
        self.annotation.update(kind='mixed', metres=['bhujanga', 'malini'], passages=[
            {'id': 'first', 'metre': 'bhujanga', 'label': 'पहिलो अंश', 'start': lines[0], 'end': lines[1]},
            {'id': 'second', 'metre': 'malini', 'label': 'दोस्रो अंश', 'start': lines[3], 'end': lines[4]},
        ])
        self.assertEqual(validate_prosody(self.work, self.metadata), [])
        self.assertEqual(annotation_anchors(self.annotation, self.text), {lines[0]: 'chhanda-first', lines[3]: 'chhanda-second'})
        self.annotation['passages'][0]['end'] = lines[4]
        self.assertTrue(any('overlap' in e for e in validate_prosody(self.work, self.metadata)))
        self.annotation['passages'][0]['start'] = 'partial'
        self.assertTrue(any('unique complete' in e for e in validate_prosody(self.work, self.metadata)))

    def test_evidence_cannot_escape_the_work_or_use_undeclared_files(self):
        self.annotation['evidence'][0]['file'] = '../outside.html'
        self.assertTrue(any('within the work' in e for e in validate_prosody(self.work, self.metadata)))
        self.annotation['evidence'][0]['file'] = 'text.txt'
        self.assertTrue(any('declared source' in e for e in validate_prosody(self.work, self.metadata)))
        self.annotation['evidence'][0]['file'] = str(self.work / 'source.html')
        self.assertTrue(any('within the work' in e for e in validate_prosody(self.work, self.metadata)))

    def test_page_ranges_are_checked_against_the_declared_edition(self):
        self.metadata['source']['pdf_editions'] = [{'file': 'source.html', 'page_count': 2}]
        self.annotation['evidence'][0].update(page_start=1, page_end=3)
        self.assertTrue(any('page range' in e for e in validate_prosody(self.work, self.metadata)))

    def test_malformed_metadata_returns_errors(self):
        for key, value in [('metres', [{}]), ('passages', [1]), ('evidence', [1]), ('reviewed', 'not-a-date')]:
            with self.subTest(key=key):
                metadata = copy.deepcopy(self.metadata)
                metadata['prosody'][key] = value
                self.assertTrue(validate_prosody(self.work, metadata))

    def test_every_catalogue_category_has_a_writer_without_a_fictitious_fixed_pattern(self):
        metres = load_metres()
        self.assertEqual(metres['jhyaure']['name'], 'झ्याउरे')
        self.assertEqual(metres['jhyaure']['writer'], 'jhyaure')
        self.assertNotIn('pattern', metres['jhyaure'])
        self.assertTrue(all(metre['writer'] == identifier for identifier, metre in metres.items()))
        self.assertEqual(metres['malini']['writer'], 'malini')

    def test_alternative_patterns_describe_a_family_without_inventing_one_template(self):
        metres = load_metres()
        self.assertEqual(metres['upajati']['patterns'], ['GGLGGLLGLGG', 'LGLGGLLGLGG'])
        self.assertNotIn('pattern', metres['upajati'])
        self.assertEqual(metres['upajati']['writer'], 'upajati')
        self.assertEqual(metres['vamshastha']['pattern'], 'LGLGGLLGLGLG')
        folder = self.work / 'assets/chhanda'
        folder.mkdir(parents=True)
        entry = {'id': 'family', 'name': 'Family', 'patterns': ['GGLGGLLGLGG', 'LGLGGLLGLGG']}
        for patterns in [[], ['GGLGGLLGLGG'], ['GGLGGLLGLGG'] * 2,
                         ['GGLGGLLGLGG', 'invalid'], ['GGLGGLLGLGG', 'LGLGGL']]:
            with self.subTest(patterns=patterns):
                (folder / 'catalogue.json').write_text(json.dumps({'metres': [{**entry, 'patterns': patterns}]}))
                with self.assertRaises(ValueError):
                    load_metres(self.work)
        (folder / 'catalogue.json').write_text(json.dumps({'metres': [{**entry, 'pattern': 'GGLGGLLGLGG'}]}))
        with self.assertRaises(ValueError):
            load_metres(self.work)
