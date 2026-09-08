import shutil
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from pipeline.build_formats import build_epub, text_to_html_body


class TextToHtmlBodyTests(unittest.TestCase):
    def test_single_line_breaks_are_explicit_br_without_extra_newline(self):
        body = text_to_html_body("पहिलो पङ्क्ति\nदोस्रो पङ्क्ति\nतेस्रो पङ्क्ति")
        self.assertEqual(body, "<p>पहिलो पङ्क्ति<br>दोस्रो पङ्क्ति<br>तेस्रो पङ्क्ति</p>")

    def test_double_newline_stanzas_remain_distinct_paragraphs(self):
        body = text_to_html_body("पहिलो\nदोस्रो\n\nतेस्रो\nचौथो")
        self.assertEqual(
            body,
            "<p>पहिलो<br>दोस्रो</p>\n<p>तेस्रो<br>चौथो</p>",
        )

    def test_html_metacharacters_are_escaped_inside_preserved_lines(self):
        body = text_to_html_body('क <tag> & "उद्धरण" \'apostrophe\'\nअर्को')
        self.assertEqual(
            body,
            "<p>क &lt;tag&gt; &amp; &quot;उद्धरण&quot; &#x27;apostrophe&#x27;"
            "<br>अर्को</p>",
        )
        self.assertNotIn("<tag>", body)

    def test_devanagari_layout_codepoints_survive(self):
        text = "\u2003\u2003\u2003\u2003भित्रिएको\u202fसह\u200dयात्री\nअर्को"
        body = text_to_html_body(text)
        self.assertEqual(body, "<p>\u2003\u2003\u2003\u2003भित्रिएको\u202fसह\u200dयात्री<br>अर्को</p>")
        for character in ("\u2003", "\u202f", "\u200d"):
            self.assertIn(character, body)


@unittest.skipUnless(shutil.which("pandoc"), "pandoc is not installed")
class PandocLinebreakIntegrationTests(unittest.TestCase):
    def test_tiny_epub_retains_explicit_poem_line_breaks_and_text(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            html_path = work / "reader.html"
            html_path.write_text(
                "<html><body><main>"
                + text_to_html_body("पङ्क्ति एक\nपङ्क्ति दुई\n\nअर्को stanza")
                + "</main></body></html>",
                encoding="utf-8",
            )
            epub = build_epub(
                work,
                {"title": "परीक्षण", "author": {"name": "लेखक"}, "language": "ne"},
                html_path,
            )
            self.assertEqual(epub, "reader.epub")
            with ZipFile(work / "reader.epub") as archive:
                pages = "".join(
                    archive.read(name).decode("utf-8")
                    for name in archive.namelist()
                    if name.endswith((".xhtml", ".html"))
                )
            self.assertIn("पङ्क्ति एक", pages)
            self.assertIn("पङ्क्ति दुई", pages)
            self.assertIn("अर्को stanza", pages)
            self.assertIn("<br", pages)


if __name__ == "__main__":
    unittest.main()
