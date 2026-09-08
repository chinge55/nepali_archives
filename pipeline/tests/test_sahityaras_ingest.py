import hashlib
import tempfile
import unittest
from pathlib import Path

from pipeline.sahityaras_ingest import SourceError, extract_poem, inventory, source_capture


XHTML = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" lang="ne">
  <head><title>{head_title}</title></head>
  <body>
    <div class="prp-pages-output">
      <div class="chapter-title">{title}</div>
      {body}
    </div>
  </body>
</html>
"""


def poem_source(body, title="मूल शीर्षक", head_title="अलग head title"):
    return XHTML.format(body=body, title=title, head_title=head_title).encode("utf-8")


class ExtractPoemTests(unittest.TestCase):
    def test_preserves_stanza_boundaries_repeated_stanzas_and_inline_numerals(self):
        data = poem_source(
            """
      <p>१. एउटै पङ्क्ति ॥१॥<br/>दोस्रो पङ्क्ति<br/>\x20
         <br/>उस्तै stanza<br/>\x20
         <br/>उस्तै stanza<br/>\x20
         <br/>उपशीर्षक<br/>\x20
         <br/>२. अर्को श्लोक</p>
    """
        )
        result = extract_poem(data)

        self.assertEqual(result.title, "मूल शीर्षक")
        self.assertEqual(result.head_title, "अलग head title")
        self.assertEqual(
            result.text,
            "१. एउटै पङ्क्ति ॥१॥\nदोस्रो पङ्क्ति\n\nउस्तै stanza\n\n"
            "उस्तै stanza\n\nउपशीर्षक\n\n२. अर्को श्लोक\n",
        )
        self.assertEqual(result.blocks, 5)
        self.assertEqual(result.continuation_markers, 0)

    def test_preserves_unicode_joiners_and_narrow_nbsp(self):
        data = poem_source("<p>सह‍यात्री शब्द</p>")
        result = extract_poem(data)
        self.assertEqual(result.text, "सह‍यात्री शब्द\n")
        self.assertIn("\u200d", result.text)
        self.assertIn("\u202f", result.text)

    def test_indented_span_becomes_four_em_spaces(self):
        data = poem_source(
            '<p><span class="mw-poem-indented" '
            'style="margin-inline-start: 4em;">भित्रिएको पङ्क्ति</span></p>'
        )
        result = extract_poem(data)
        self.assertEqual(result.text, "\u2003\u2003\u2003\u2003भित्रिएको पङ्क्ति\n")
        self.assertEqual(result.indented_lines, 1)

    def test_page_continuation_joins_adjacent_paragraphs(self):
        data = poem_source(
            "<p>अघिल्लो पृष्ठ</p>"
            '<div style="margin-top: -1lh;"></div>'
            "<p>अर्को पृष्ठ</p>"
        )
        result = extract_poem(data)
        self.assertEqual(result.text, "अघिल्लो पृष्ठ\nअर्को पृष्ठ\n")
        self.assertEqual(result.continuation_markers, 1)
        self.assertEqual(result.blocks, 1)

    def test_div_chapter_title_is_used_even_when_head_title_differs(self):
        result = extract_poem(poem_source("<p>पाठ</p>", "दृश्य शीर्षक", "वेब पृष्ठ"))
        self.assertEqual(result.title, "दृश्य शीर्षक")
        self.assertEqual(result.head_title, "वेब पृष्ठ")

    def test_source_capture_is_a_small_valid_xhtml_source_with_requested_title(self):
        data = poem_source("<p>पाठ</p>")
        captured = source_capture(data, "कैप्चर शीर्षक")
        self.assertTrue(captured.startswith(b"<?xml"))
        self.assertIn("<title>कैप्चर शीर्षक</title>".encode(), captured)
        self.assertIn("prp-pages-output".encode(), captured)
        self.assertNotIn(b" src=", captured)
        self.assertNotIn(b" href=", captured)

    def test_unpaired_continuation_marker_fails(self):
        with self.assertRaises(SourceError):
            extract_poem(poem_source('<div style="margin-top:-1lh;"></div><p>पाठ</p>'))
        with self.assertRaises(SourceError):
            extract_poem(poem_source('<p>पाठ</p><div style="margin-top:-1lh;"></div>'))

    def test_notes_and_unhandled_tags_fail_closed(self):
        with self.assertRaises(SourceError):
            extract_poem(poem_source('<p>पाठ<a href="#n">[१]</a></p>'))
        with self.assertRaises(SourceError):
            extract_poem(poem_source('<p class="reference">स्रोत</p>'))
        with self.assertRaises(SourceError):
            extract_poem(poem_source('<p>पाठ</p><table><tr><td>अज्ञात</td></tr></table>'))

    def test_external_entity_declarations_fail(self):
        data = b'''<!DOCTYPE html [<!ENTITY x SYSTEM "file:///private/source">]>
<html xmlns="http://www.w3.org/1999/xhtml"><body><div class="prp-pages-output">
<div class="chapter-title">&#x0936;&#x0940;&#x0930;&#x094d;&#x0937;&#x0915;</div><p>&x;</p></div></body></html>'''
        with self.assertRaises(SourceError):
            extract_poem(data)


class InventoryTests(unittest.TestCase):
    def write_package(self, root, spine=("first", "second"), refs=None):
        package = root / "book.opf"
        refs = refs or {"first": "text/first.xhtml", "second": "text/second.xhtml"}
        manifest = "".join(
            f'<item id="{key}" href="{href}" media-type="application/xhtml+xml"/>'
            for key, href in refs.items()
        )
        spine_xml = "".join(f'<itemref idref="{key}"/>' for key in spine)
        package.write_text(
            f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="urn:pkg"><manifest>{manifest}</manifest><spine>{spine_xml}</spine></package>''',
            encoding="utf-8",
        )
        container = root / "META-INF"
        container.mkdir()
        (container / "container.xml").write_text(
            '<container xmlns="urn:container"><rootfiles><rootfile full-path="book.opf"/></rootfiles></container>',
            encoding="utf-8",
        )
        for href in refs.values():
            path = root / href
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(poem_source("<p>पाठ</p>", Path(href).stem, Path(href).stem))

    def test_inventory_follows_spine_order_and_includes_nonspine_xhtml(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_package(
                root,
                spine=("second", "first"),
                refs={
                    "first": "text/first.xhtml",
                    "second": "text/second.xhtml",
                    "appendix": "text/appendix.xhtml",
                },
            )
            result = inventory(root)
            documents = result["documents"]
            self.assertEqual([item["manifest_id"] for item in documents], ["second", "first", "appendix"])
            self.assertEqual([item["spine_position"] for item in documents], [1, 2, None])
            self.assertEqual(documents[0]["path"], "text/second.xhtml")
            self.assertEqual(documents[0]["sha256"], hashlib.sha256((root / "text/second.xhtml").read_bytes()).hexdigest())

    def test_inventory_missing_spine_ref_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_package(root, spine=("first", "missing"))
            with self.assertRaises(SourceError):
                inventory(root)

    def test_inventory_path_traversal_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "package"
            root.mkdir()
            self.write_package(root, refs={"first": "../outside.xhtml"}, spine=("first",))
            with self.assertRaises(SourceError):
                inventory(root)


if __name__ == "__main__":
    unittest.main()
