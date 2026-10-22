import sys
import unittest
from pathlib import Path


PIPELINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE))

from sitegen.text import paginate_work, paginate_sections


class PaginationTests(unittest.TestCase):
    def test_recognized_sections_split_and_keep_subtitle_in_label(self):
        text = (
            "प्रथम सर्ग\nआरम्भ\n\n" + "क" * 4100
            + "\n\nदोस्रो सर्ग\nअन्त्य\n\n" + "ख" * 4100
        )
        pages = paginate_work(text)
        self.assertEqual([p[0] for p in pages], [
            "प्रथम सर्ग — आरम्भ",
            "दोस्रो सर्ग — अन्त्य",
        ])

    def test_substantial_heading_led_front_matter_gets_own_page(self):
        preface = "भूमिका\n\n" + ("लेखकको आफ्नै कुरा। " * 30)
        text = (
            preface + "\n\nप्रथम सर्ग\n\n" + "क" * 4000
            + "\n\nदोस्रो सर्ग\n\n" + "ख" * 4000
        )
        pages = paginate_work(text)
        self.assertEqual(pages[0][0], "भूमिका")
        self.assertIn("लेखकको आफ्नै कुरा", pages[0][1])

    def test_closing_colophons_stay_with_their_canto(self):
        text = ('प्रथम सर्ग\n\n' + 'क' * 4100 + '\n\nइति प्रथम सर्ग'
                + '\n\nद्वितीय सर्ग\n\n' + 'ख' * 4100 + '\n\nइति द्वितीय सर्ग')
        pages = paginate_work(text)
        self.assertEqual([label for label, _ in pages], ['प्रथम सर्ग', 'द्वितीय सर्ग'])
        self.assertTrue(pages[0][1].endswith('इति प्रथम सर्ग'))
        self.assertTrue(pages[1][1].endswith('इति द्वितीय सर्ग'))

    def test_play_splits_at_printed_halves_without_losing_the_preface(self):
        preface = "दुई कुरा\n\n" + "लेखकको आफ्नै कुरा। " * 30
        first, second = "कृष्ण- संवाद। " * 400, "युवति- संवाद। " * 400
        text = preface + "\n\nअघिल्लो आधा\n\n" + first + "\n\nपछिल्लो आधा\n\n" + second
        pages = paginate_work(text)
        self.assertEqual([label for label, _ in pages], ['दुई कुरा', 'अघिल्लो आधा', 'पछिल्लो आधा'])
        self.assertEqual(pages[1][1], first)
        self.assertEqual(pages[2][1], second)

    def test_empty_composite_heading_redirects_to_existing_body_route(self):
        body = "इतिहासको मूल पाठ। " * 500
        text = ("खण्ड एक\n१.१ इतिहास\n\nखण्ड एक\n\n१.१ इतिहास\n\n"
                + body + "\n\nखण्ड दुई\n\n" + body)
        sections = paginate_sections(text)
        self.assertEqual([s.number for s in sections], [2, 3])
        self.assertEqual(sections[0].aliases, (1,))
        self.assertEqual(sections[0].label, "खण्ड एक")
        self.assertEqual(sections[0].content, "१.१ इतिहास\n\n" + body)

    def test_duplicate_heading_keeps_intervening_book_title(self):
        body = "कविताको मूल हरफ। " * 500
        text = "प्रथम सर्ग\n\nगङ्गा गौरी\n\nमहाकाव्य\n\nप्रथम सर्ग\n\n" + body
        sections = paginate_sections(text)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].number, 2)
        self.assertEqual(sections[0].aliases, (1,))
        self.assertEqual(sections[0].content, "गङ्गा गौरी\n\nमहाकाव्य\n\n" + body)

    def test_adjacent_distinct_headings_do_not_drop_source_labels(self):
        body = "लेखकको पाठ। " * 900
        text = "प्रथम खण्ड\n\nप्रथम अध्याय\n\nप्रथम परिच्छेद\n\n" + body
        sections = paginate_sections(text)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].number, 3)
        self.assertEqual(sections[0].aliases, (1, 2))
        self.assertEqual(sections[0].content, "प्रथम खण्ड\n\nप्रथम अध्याय\n\n" + body)

    def test_short_real_section_is_not_merged_by_word_count(self):
        text = "प्रथम सर्ग\n\nजीवन छोटो छ।\n\nदोस्रो सर्ग\n\n" + "लामो कविता। " * 900
        sections = paginate_sections(text)
        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0].content, "जीवन छोटो छ।")
        self.assertFalse(sections[0].aliases)

    def test_trailing_empty_heading_stays_with_previous_body(self):
        body = "कविताको मूल हरफ। " * 600
        sections = paginate_sections("प्रथम सर्ग\n\n" + body + "\n\nअन्तिम सर्ग")
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].number, 1)
        self.assertEqual(sections[0].aliases, (2,))
        self.assertTrue(sections[0].content.endswith("अन्तिम सर्ग"))

    def test_multiline_preface_heading_is_preserved(self):
        text = ("भूमिका\nलेखकको निवेदन\n\n" + "प्रस्तावनाको मूल पाठ। " * 50
                + "\n\nप्रथम सर्ग\n\n" + "क" * 4100
                + "\n\nद्वितीय सर्ग\n\n" + "ख" * 4100)
        pages = paginate_work(text)
        self.assertEqual(pages[0][0], "भूमिका — लेखकको निवेदन")
        self.assertIn("प्रस्तावनाको मूल पाठ।", pages[0][1])

    def test_trailing_empty_heading_chain_keeps_source_order(self):
        body = "कविताको मूल हरफ। " * 600
        ending = "अन्तिम खण्ड\n\nअन्तिम अध्याय\n\nअन्तिम परिच्छेद"
        sections = paginate_sections("प्रथम सर्ग\n\n" + body + "\n\n" + ending)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].aliases, (2, 3, 4))
        self.assertEqual(sections[0].content, body + "\n\n" + ending)

    def test_short_work_remains_single_page(self):
        self.assertIsNone(paginate_work(
            "प्रथम सर्ग\n\nसानो\n\nदोस्रो सर्ग\n\nसानो"
        ))

    def test_large_headingless_work_balances_into_parts(self):
        text = "\n\n".join("क" * 5000 for _ in range(10))
        pages = paginate_work(text, balance=True)
        self.assertGreaterEqual(len(pages), 2)
        self.assertEqual(pages[0][0], "भाग १")

    def test_numbering_gap_is_not_filled(self):
        text = (
            "प्रथम सर्ग\n\n१०\n\n" + "क" * 4000
            + "\n\nदोस्रो सर्ग\n\n३३\n\n" + "ख" * 4000
        )
        pages = paginate_work(text)
        joined = "\n".join(content for _, content in pages)
        self.assertIn("१०", joined)
        self.assertIn("३३", joined)
        self.assertNotIn("\n११\n", joined)


if __name__ == "__main__":
    unittest.main()
