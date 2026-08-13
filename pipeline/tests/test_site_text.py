import sys
import unittest
from pathlib import Path


PIPELINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE))

from sitegen.text import work_html


class WorkHtmlTests(unittest.TestCase):
    def test_verse_and_prose_use_different_shapes(self):
        verse = work_html("पहिलो हरफ\nदोस्रो हरफ", verse=True)
        prose = work_html("पहिलो हरफ\nदोस्रो हरफ", verse=False)
        self.assertIn('<div class="stanza">', verse)
        self.assertEqual(verse.count('<span class="ln">'), 2)
        self.assertIn('<p class="stanza">पहिलो हरफ दोस्रो हरफ</p>', prose)

    def test_source_markup_is_escaped(self):
        rendered = work_html("कविता <script>&", verse=True)
        self.assertIn("&lt;script&gt;&amp;", rendered)
        self.assertNotIn("<script>", rendered)

    def test_short_quoted_dialogue_is_not_a_heading(self):
        rendered = work_html("“कता जाने”", verse=True)
        self.assertNotIn('<h2 class="sec">', rendered)
        self.assertIn('<div class="stanza">', rendered)

    def test_parenthesized_devanagari_letter_is_a_heading(self):
        self.assertEqual(
            work_html("(क)", verse=True),
            '<h2 class="sec">(क)</h2>',
        )

    def test_standalone_and_leading_stanza_numbers_are_preserved(self):
        standalone = work_html("१०", verse=True)
        leading = work_html("१०\nपहिलो हरफ\nदोस्रो हरफ", verse=True)
        self.assertIn('class="stanza snum"', standalone)
        self.assertIn('<span class="ln">१०</span>', standalone)
        self.assertEqual(leading.count('class="stanza snum"'), 1)
        self.assertEqual(leading.count('<span class="ln">१०</span>'), 1)
        self.assertIn('<span class="ln">पहिलो हरफ</span>', leading)

    def test_unnumbered_section_does_not_gain_a_number(self):
        rendered = work_html("प्रथम सर्ग\n\nकविताको हरफ", verse=True)
        self.assertIn('<h2 class="sec">प्रथम सर्ग</h2>', rendered)
        self.assertNotIn('class="stanza snum"', rendered)

    def test_source_colophon_is_separate(self):
        rendered = work_html("वि. सं. १९६९ लालित्यबाट", verse=True)
        self.assertEqual(
            rendered,
            '<p class="colophon">वि. सं. १९६९ लालित्यबाट</p>',
        )

    def test_spaced_danda_uses_non_breaking_space_only_at_punctuation(self):
        rendered = work_html("शब्द शब्द ।", verse=True)
        self.assertIn("शब्द शब्द\u00a0।", rendered)
        self.assertNotIn("शब्द\u00a0शब्द", rendered)

    def test_source_spelling_and_numbering_gaps_remain_present(self):
        source = "जूवा, मर्दगद्य !\n\n१०\n\n३३"
        rendered = work_html(source, verse=True)
        for token in ("जूवा", "मर्दगद्य", "१०", "३३"):
            self.assertIn(token, rendered)
        self.assertNotIn(">११<", rendered)


if __name__ == "__main__":
    unittest.main()
