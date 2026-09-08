import unittest

from sahityaras_ingest import SourceError
from pipeline.sahityaras_members import extract_member


def source(body):
    return ("<html xmlns='http://www.w3.org/1999/xhtml'><body>"
            "<div class='chapter-title'>फुटकर रचना</div>" + body + "</body></html>").encode()


class MemberTests(unittest.TestCase):
    def test_extracts_contiguous_members_and_preserves_stanzas(self):
        result = extract_member(source(
            '<p>१<br/>पहिलो<br/><br/>अर्को</p><p>२<br/>दोस्रो</p>'
            '<p>३<br/>तेस्रो</p><p>४<br/>चौथो<br/><br/>श्लोक</p>'
            '<p>५<br/>पाँचौं</p>'), [4, 5], 5, 'बालाजी')
        self.assertTrue(result.text.startswith('४\nचौथो'))
        self.assertIn('श्लोक', result.text)
        self.assertIn('५\nपाँचौं', result.text)
        self.assertNotIn('३\nतेस्रो', result.text)
        self.assertIn('बालाजी'.encode(), result.capture)

    def test_rejects_missing_or_duplicate_sequence(self):
        with self.assertRaises(SourceError):
            extract_member(source('<p>१<br/>एक</p><p>३<br/>तीन</p>'), [1], 3, 'x')
        with self.assertRaises(SourceError):
            extract_member(source('<p>१<br/>एक</p><p>२<br/>दुई</p><p>२<br/>फेरि</p>'), [1], 2, 'x')

    def test_rejects_noncontiguous_or_empty_selection(self):
        base = '<p>१<br/>एक</p><p>२<br/>दुई</p><p>३<br/>तीन</p>'
        with self.assertRaises(SourceError):
            extract_member(source(base), [1, 3], 3, 'x')
        with self.assertRaises(SourceError):
            extract_member(source('<p>१<br/></p><p>२<br/>दुई</p>'), [1], 2, 'x')

    def test_rejects_unsupported_or_unreviewed_notes(self):
        with self.assertRaises(SourceError):
            extract_member(source('<table><tr><td>१</td></tr></table>'), [1], 1, 'x')
        noted = source('<p>१<sup class="reference" id="cite_ref-1"><a href="#cite_note-1">[१]</a></sup><br/>एक</p>'
                       '<ol class="references"><li id="cite_note-1">टिप्पणी</li></ol>')
        with self.assertRaises(SourceError):
            extract_member(noted, [1], 1, 'x')


if __name__ == '__main__':
    unittest.main()
