import sys
import unittest
from pathlib import Path


PIPELINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE))

from sitegen.text import paginate_work


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
