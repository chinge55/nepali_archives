import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_reader_content import audit_readers
from sitegen.config import SITE_URL


class ReaderAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def page(self, relative, body, head=''):
        path = self.root / relative / 'index.html'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('<html><head><title>कृति</title>' + head
                        + '</head><body><h1>खण्ड एक</h1>' + body + '</body></html>')
        return path

    def test_empty_and_heading_only_chapters_are_errors(self):
        self.page('authors/test/work', '<ol class="toc"><li><a href="1/">खण्ड एक</a></li></ol>')
        for body, message in [('', 'empty literary body'), ('<h2>काव्यको नाम</h2>', 'heading-only')]:
            with self.subTest(body=body):
                self.page('authors/test/work/1', '<div data-pagefind-body>' + body
                          + '</div><nav class="seqnav"><a class="pv" href="../">सूची</a></nav>')
                errors, _ = audit_readers(self.root)
                self.assertTrue(any(message in e for e in errors))

    def test_missing_body_is_detected_on_single_work_and_chapter(self):
        self.page('authors/test/work', '<a href="https://example.com/">बाहिरी स्रोत</a>')
        self.page('authors/test/work/1', '<p>सूची</p>')
        errors, _ = audit_readers(self.root)
        self.assertTrue(any('work needs a literary body' in e for e in errors))
        self.assertTrue(any('chapter needs exactly one' in e for e in errors))

    def test_short_poem_is_review_only(self):
        self.page('authors/test/poem', '<div data-pagefind-body><p>दुई छोटा हरफ।</p></div>')
        errors, report = audit_readers(self.root)
        self.assertFalse(errors)
        self.assertTrue(any('short text' in r for r in report['review']))

    def test_repeated_body_is_reported_without_deleting_short_literature(self):
        body = '<div data-pagefind-body><p>' + 'मूल कविता। ' * 30 + '</p></div>'
        self.page('authors/test/one', body)
        self.page('authors/test/two', body)
        errors, report = audit_readers(self.root)
        self.assertFalse(errors)
        self.assertEqual(len(report['duplicate_body_groups']), 1)

    def test_contents_and_navigation_must_match_actual_chapters(self):
        self.page('authors/test/work', '<ol class="toc"><li><a href="1/">गलत शीर्षक</a></li>'
                  '<li><a href="2/">खण्ड दुई</a></li></ol>')
        self.page('authors/test/work/1', '<div data-pagefind-body><p>मूल पाठ।</p></div>')
        errors, _ = audit_readers(self.root)
        for message in ['contents title differs', 'does not target an indexable chapter', 'incorrect pv']:
            self.assertTrue(any(message in e for e in errors), message)

    def test_noindex_reader_cannot_silently_disappear_from_audit(self):
        self.page('authors/test/work', '<div data-pagefind-body><p>मूल पाठ।</p></div>',
                  '<meta name="robots" content="noindex">')
        errors, _ = audit_readers(self.root)
        self.assertTrue(any('unexpectedly marked noindex' in e for e in errors))

    def test_source_comparison_detects_missing_and_reordered_paragraphs(self):
        source = self.root / 'sources/authors/test/work'
        source.mkdir(parents=True)
        (source / 'metadata.json').write_text('{}')
        (source / 'text.txt').write_text('पहिलो लामो अनुच्छेद।\n\nदोस्रो लामो अनुच्छेद।\n')
        for body, valid in [
            ('पहिलो लामो अनुच्छेद। दोस्रो लामो अनुच्छेद।', True),
            ('पहिलो लामो अनुच्छेद।', False),
            ('दोस्रो लामो अनुच्छेद। पहिलो लामो अनुच्छेद।', False),
        ]:
            with self.subTest(body=body):
                self.page('authors/test/work', '<div data-pagefind-body><p>' + body + '</p></div>')
                errors, report = audit_readers(self.root, self.root / 'sources')
                self.assertEqual(not errors, valid)
                self.assertEqual(report['source_body_blocks'], 2)

    def test_repeated_stanza_requires_both_occurrences(self):
        source = self.root / 'sources/authors/test/work'
        source.mkdir(parents=True)
        (source / 'metadata.json').write_text('{}')
        (source / 'text.txt').write_text('उस्तै हरफ।\n\nउस्तै हरफ।\n')
        self.page('authors/test/work', '<div data-pagefind-body><p>उस्तै हरफ।</p></div>')
        errors, _ = audit_readers(self.root, self.root / 'sources')
        self.assertTrue(any('body block 2 missing or out of order' in e for e in errors))

    def test_source_work_missing_from_site_is_an_error(self):
        source = self.root / 'sources/authors/test/absent'
        source.mkdir(parents=True)
        (source / 'metadata.json').write_text('{}')
        (source / 'text.txt').write_text('मूल पाठ।')
        errors, _ = audit_readers(self.root, self.root / 'sources')
        self.assertTrue(any('source work has no indexable reader' in e for e in errors))

    def test_external_navigation_cannot_masquerade_as_local(self):
        self.page('authors/test/work', '<ol class="toc"><li><a href="1/">खण्ड एक</a></li></ol>')
        self.page('authors/test/work/1', '<div data-pagefind-body><p>मूल पाठ।</p></div>'
                  '<nav class="seqnav"><a class="pv" href="https://example.com/authors/test/work/">सूची</a></nav>')
        errors, _ = audit_readers(self.root)
        self.assertTrue(any('incorrect pv' in e for e in errors))

    def test_redirect_requires_an_indexable_same_work_target(self):
        self.page('authors/test/work', '<ol class="toc"><li><a href="2/">खण्ड एक</a></li></ol>')
        target = self.page('authors/test/work/2', '<div data-pagefind-body><p>मूल पाठ।</p></div>'
                           '<nav class="seqnav"><a class="pv" href="../">सूची</a></nav>')
        head = ('<meta name="robots" content="noindex,follow">'
                '<meta name="archive-redirect" content="chapter-merge">'
                '<meta http-equiv="refresh" content="0;url=../2/">'
                f'<link rel="canonical" href="{SITE_URL}authors/test/work/2/">')
        self.page('authors/test/work/1', '<a href="../2/">पढ्नुहोस्</a>', head)
        errors, report = audit_readers(self.root)
        self.assertFalse(errors)
        self.assertEqual(report['redirect_pages'], 1)
        target.unlink()
        self.assertTrue(any('invalid chapter redirect' in e for e in audit_readers(self.root)[0]))


if __name__ == '__main__':
    unittest.main()
