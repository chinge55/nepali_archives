import sys
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sitegen.config import SITE_URL
from sitegen.seo import SITEMAP_NS, audit_site, page_url, write_sitemaps


class SeoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.site = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def page(self, relative, *, noindex=False, title="कृति", canonical=None):
        path = self.site / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        url = canonical if canonical is not None else page_url(self.site, path)
        robots = '<meta name="robots" content="noindex,follow">' if noindex else ''
        path.write_text(f'<html><head><title>{title}</title><meta name="description" content="पाठको परिचय।">'
                        f'<link rel="canonical" href="{url}">{robots}</head><body>पाठ</body></html>', encoding='utf-8')
        return path

    def test_sitemaps_cover_chapters_and_omit_noindex_and_downloads(self):
        self.page('index.html')
        self.page('authors/test/work/index.html')
        self.page('authors/test/work/1/index.html')
        self.page('authors/test/work/pdf/index.html', noindex=True)
        self.page('patro/2026-09-22/index.html', noindex=True)
        (self.site / 'authors/test/work/text.txt').write_text('मूल पाठ')
        (self.site / 'authors/test/work/source.pdf').write_bytes(b'%PDF')
        write_sitemaps(self.site)
        expected = {SITE_URL, SITE_URL + 'authors/test/work/', SITE_URL + 'authors/test/work/1/'}
        self.assertEqual(set((self.site / 'sitemap.txt').read_text().splitlines()), expected)
        root = ET.parse(self.site / 'sitemap.xml').getroot()
        self.assertEqual({el.text for el in root.findall(f'{{{SITEMAP_NS}}}url/{{{SITEMAP_NS}}}loc')}, expected)
        errors, report = audit_site(self.site)
        self.assertEqual(errors, [])
        self.assertEqual(report['html_pages'], 5)
        self.assertEqual(report['indexable_pages'], 3)

    def test_audit_catches_missing_chapter_and_blank_title(self):
        self.page('index.html')
        write_sitemaps(self.site)
        self.page('authors/test/work/1/index.html', title=' ')
        errors, _ = audit_site(self.site)
        self.assertTrue(any('nonempty title' in error for error in errors))
        self.assertTrue(any('sitemap.xml: missing' in error for error in errors))
        self.assertTrue(any('sitemap.txt: missing' in error for error in errors))

    def test_sitemap_rejects_canonical_pointing_to_another_page(self):
        self.page('index.html', canonical=SITE_URL + 'missing/')
        with self.assertRaisesRegex(ValueError, 'self-referencing canonical'):
            write_sitemaps(self.site)

    def test_audit_rejects_duplicate_and_noindex_sitemap_urls(self):
        self.page('index.html')
        self.page('pdf/index.html', noindex=True)
        write_sitemaps(self.site)
        with (self.site / 'sitemap.txt').open('a') as file:
            file.write(SITE_URL + '\n' + SITE_URL + 'pdf/\n')
        errors, _ = audit_site(self.site)
        self.assertTrue(any('duplicate URLs' in error for error in errors))
        self.assertTrue(any('noindex page' in error for error in errors))

    def writer_redirect(self, *, source='chhanda/index.html', destination='../kavita-lekhan/', noindex=True):
        path = self.page(source, noindex=noindex, canonical=SITE_URL + 'kavita-lekhan/')
        path.write_text(path.read_text().replace('</head>',
            '<meta name="archive-redirect" content="writer-move">'
            f'<noscript><meta http-equiv="refresh" content="0;url={destination}"></noscript></head>'))
        return path

    def test_writer_migration_has_one_indexable_destination(self):
        self.page('kavita-lekhan/index.html')
        self.writer_redirect()
        write_sitemaps(self.site)
        errors, report = audit_site(self.site)
        self.assertEqual(errors, [])
        self.assertEqual(report['indexable_pages'], 1)
        self.assertEqual((self.site / 'sitemap.txt').read_text().splitlines(), [SITE_URL + 'kavita-lekhan/'])

    def test_writer_redirect_exception_is_limited_to_the_known_migration(self):
        self.page('kavita-lekhan/index.html')
        for options in [
            {'source': 'other/index.html'},
            {'destination': 'https://example.org/kavita-lekhan/'},
            {'destination': '../missing/'},
            {'destination': '../kavita-lekhan/?metre=malini'},
            {'noindex': False},
        ]:
            with self.subTest(options=options):
                path = self.writer_redirect(**options)
                # A bad indexable canonical is rejected by the sitemap writer too.
                if options.get('noindex') is False:
                    with self.assertRaises(ValueError):
                        write_sitemaps(self.site)
                else:
                    write_sitemaps(self.site)
                errors, _ = audit_site(self.site)
                self.assertTrue(any('invalid writer redirect' in error for error in errors))
                path.unlink()

    def test_writer_redirect_requires_an_indexable_canonical_target(self):
        self.writer_redirect()
        write_sitemaps(self.site)
        self.assertTrue(any('invalid writer redirect' in error for error in audit_site(self.site)[0]))
        self.page('kavita-lekhan/index.html', noindex=True)
        write_sitemaps(self.site)
        self.assertTrue(any('invalid writer redirect' in error for error in audit_site(self.site)[0]))
        self.page('kavita-lekhan/index.html')
        write_sitemaps(self.site)
        self.assertEqual(audit_site(self.site)[0], [])


if __name__ == '__main__':
    unittest.main()
