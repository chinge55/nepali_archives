import unittest

from sahityaras_ingest import SourceError
from pipeline.sahityaras_text import extract_document


def document(body: str) -> bytes:
    return f'''<html xmlns="http://www.w3.org/1999/xhtml"><body>
      <div class="chapter-title">परीक्षण शीर्षक</div>{body}
    </body></html>'''.encode("utf-8")


class ExtractDocumentTests(unittest.TestCase):
    def test_preserves_multisection_order_repeated_paragraphs_and_markers(self):
        result = extract_document(document(
            '<section><p>१. पहिलो<br/>पङ्क्ति</p><p>उस्तै अनुच्छेद</p></section>'
            '<section><p>उस्तै अनुच्छेद</p><p>२. दोस्रो</p></section>'
        ))
        self.assertEqual(result.text, '१. पहिलो\nपङ्क्ति\n\nउस्तै अनुच्छेद\n\nउस्तै अनुच्छेद\n\n२. दोस्रो\n')

    def test_author_note_requires_explicit_approval_and_is_retained(self):
        source = document('<p>मुख्य पाठ<sup class="reference" id="cite_ref-1">'
                          '<a href="#cite_note-1">[१]</a></sup></p>'
                          '<ol class="references"><li id="cite_note-1"><span class="mw-cite-backlink"><a href="#cite_ref-1">↩</a></span>'
                          '<span class="reference-text">लेखकको टिप्पणी</span></li></ol>')
        with self.assertRaises(SourceError):
            extract_document(source)
        result = extract_document(source, notes_approved=True)
        self.assertEqual(result.note_count, 1)
        self.assertIn('लेखकको टिप्पणी', result.text)

    def test_missing_note_target_fails(self):
        source = document('<p>मुख्य पाठ<sup class="reference" id="cite_ref-1">'
                          '<a href="#cite_note-missing">[१]</a></sup></p>'
                          '<ol class="references"><li id="cite_note-1"><span class="reference-text">टुटेको टिप्पणी</span></li></ol>')
        with self.assertRaises(SourceError):
            extract_document(source, notes_approved=True)

    def test_preserves_indentation_centered_number_and_nested_bold_poem(self):
        result = extract_document(document(
            '<div style="margin-left:auto">३</div>'
            '<strong><div class="poem"><span class="mw-poem-indented" '
            'style="margin-inline-start: 2em;">भित्रिएको</span><br/>पङ्क्ति</div></strong>'
        ))
        self.assertIn('३', result.text)
        self.assertIn("\u2003\u2003भित्रिएको\n\nपङ्क्ति", result.text)

    def test_editorial_removal_preserves_inline_citation_tail_and_following_prose(self):
        source = document('<p>मूल <span id="editorial-ref">सम्पादकीय</span>'
                          '<sup><a href="#editorial-note">[१]</a></sup> पछिल्लो गद्य</p>'
                          '<div id="editorial-note">पछि थपिएको टिप्पणी</div>')
        result = extract_document(source, remove_ids=("editorial-ref", "editorial-note"),
                                  remove_links=("#editorial-note",))
        self.assertEqual(result.text, 'मूल  पछिल्लो गद्य\n')
        self.assertNotIn('सम्पादकीय', result.text)
        self.assertNotIn('पछि थपिएको', result.text)

    def test_replacement_requires_one_exact_match(self):
        source = document('<p>जाँच जाँच</p>')
        with self.assertRaises(SourceError):
            extract_document(source, replacements=({'old': 'जाँच', 'new': 'परीक्षण', 'reason': 'review'},))
        result = extract_document(document('<p>जाँच</p>'),
                                  replacements=({'old': 'जाँच', 'new': 'परीक्षण', 'reason': 'review'},))
        self.assertIn('परीक्षण', result.text)

    def test_editorial_remove_id_is_explicit_and_conserved(self):
        source = document('<p>मूल पाठ</p><div id="editorial">पछि थपिएको टिप्पणी</div>')
        with self.assertRaises(SourceError):
            extract_document(source, remove_ids=("missing",))
        result = extract_document(source, remove_ids=("editorial",))
        self.assertEqual(result.text, 'मूल पाठ\n')
        self.assertNotIn('पछि थपिएको', result.text)


if __name__ == '__main__':
    unittest.main()
