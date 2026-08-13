import json
import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


PIPELINE = Path(__file__).resolve().parents[1]
ROOT = PIPELINE.parent
sys.path.insert(0, str(PIPELINE))

from check_site_links import find_broken_links
from sitegen.builder import build
from sitegen.context import BuildContext


def fixture_metadata(identifier, title, genre):
    return {
        "id": identifier,
        "title": title,
        "title_roman": identifier.replace("_", " "),
        "author": {
            "id": "test_author",
            "name": "परीक्षण लेखक",
            "name_roman": "Parikshan Lekhak",
        },
        "genre": [genre],
        "source": {"name": "परीक्षण स्रोत", "url": ""},
        "formats": {"txt": "text.txt"},
    }


class FullBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / "assets" / "site", self.root / "assets" / "site")
        logo_assets = self.root / "assets" / "logo"
        logo_assets.mkdir(parents=True)
        for filename in [
            "favicon-48.png",
            "favicon-180.png",
            "final-logo.png",
            "logo-pressed.png",
            "final-logo-dark.png",
            "logo-pressed-dark.png",
        ]:
            (logo_assets / filename).write_bytes(b"fixture")
        font_assets = self.root / "assets" / "fonts"
        font_assets.mkdir(parents=True)
        (font_assets / "fontface.css").write_text("", encoding="utf-8")
        (font_assets / "nsd-devanagari-400.woff2").write_bytes(b"fixture")
        pdfjs_assets = self.root / "assets" / "pdfjs"
        pdfjs_assets.mkdir(parents=True)
        (pdfjs_assets / "pdf.min.js").write_text("", encoding="utf-8")
        (pdfjs_assets / "pdf.worker.min.js").write_text("", encoding="utf-8")
        (
            self.root / "Pratilipi Adhikar Ain_2059(1)_1573120368.pdf"
        ).write_bytes(b"%PDF fixture")
        type_assets = self.root / "assets" / "type"
        type_assets.mkdir(parents=True)
        (type_assets / "app.js").write_text("export {};", encoding="utf-8")
        (type_assets / "engine.js").write_text("export {};", encoding="utf-8")

        works = []
        for identifier, title, genre, text, collection in [
            (
                "verse_work",
                "परीक्षण कविता",
                "kavita",
                "पहिलो हरफ\nदोस्रो हरफ\n\nअन्तिम हरफ",
                ["परीक्षण सङ्ग्रह"],
            ),
            (
                "prose_work",
                "परीक्षण कथा",
                "katha",
                "यो परीक्षणका लागि पर्याप्त शब्द भएको गद्य अनुच्छेद हो। "
                "अर्को वाक्यले तथ्याङ्कलाई एकभन्दा बढी शब्द दिन्छ।",
                [],
            ),
            (
                "long_work",
                "परीक्षण महाकाव्य",
                "mahakavya",
                (
                    "प्रथम सर्ग\nआरम्भ\n\n"
                    + "कविताको लामो पहिलो अंश। " * 260
                    + "\n\nदोस्रो सर्ग\nअन्त्य\n\n"
                    + "कविताको लामो दोस्रो अंश। " * 260
                ),
                [],
            ),
        ]:
            relative = Path("archives/authors/test_author") / identifier
            work_dir = self.root / relative
            work_dir.mkdir(parents=True)
            metadata = fixture_metadata(identifier, title, genre)
            if identifier == "verse_work":
                metadata["formats"]["pdf"] = "source.pdf"
                (work_dir / "source.pdf").write_bytes(b"%PDF fixture")
            (work_dir / "metadata.json").write_text(
                json.dumps(metadata, ensure_ascii=False),
                encoding="utf-8",
            )
            (work_dir / "text.txt").write_text(text, encoding="utf-8")
            works.append(
                {
                    "id": identifier,
                    "path": relative.as_posix(),
                    "collection": collection,
                }
            )
        (self.root / "archives" / "index.json").write_text(
            json.dumps({"works": works}, ensure_ascii=False),
            encoding="utf-8",
        )
        horoscope = self.root / "horoscope" / "content"
        horoscope.mkdir(parents=True)
        anga = {"name": "परीक्षण", "ends": "2026-08-13T12:00"}
        panchanga = {
            "bs_str": "२०८३ साउन २८",
            "bs": "2083-04-28",
            "vara": "बिहीबार",
            "ad": "2026-08-13",
            "sunrise": "05:30",
            "sunset": "18:30",
            "tithi": anga,
            "nakshatra": anga,
            "yoga": anga,
            "karana": anga,
            "moon_rashi": anga,
            "chandrashtama_rashi": "मेष",
            "tithi_class": "परीक्षण",
            "rashis": [
                {
                    "rashi": "मेष",
                    "chandrashtama": True,
                    "rule": "1 भावको परीक्षण",
                    "house": 1,
                    "text": "आज परीक्षण गर्नुहोस्।",
                    "valence": "मिश्रित",
                    "namakshar": "चु चे चो",
                }
            ],
        }
        (horoscope / "panchanga-2026-08.json").write_text(
            json.dumps(
                {
                    "days": {
                        "2026-08-13": panchanga,
                        "2026-08-14": {
                            **panchanga,
                            "bs_str": "२०८३ साउन २९",
                            "ad": "2026-08-14",
                        },
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def word_keys(_word):
        return {"parikshan"}

    @staticmethod
    def normalize_key(_word):
        return "parikshan"

    def run_build(self, name, archive_base=""):
        context = BuildContext.for_root(
            self.root,
            output_dir=self.root / name,
            archive_base=archive_base,
            build_date=date(2026, 8, 13),
        )
        result = build(
            context,
            normalize_key=self.normalize_key,
            translit_word_keys=self.word_keys,
        )
        return context, result

    def test_fixture_build_has_pages_search_sitemap_and_valid_links(self):
        context, result = self.run_build("site-fixture")
        self.assertEqual(result.works, 3)
        self.assertTrue(
            (
                context.site
                / "authors/test_author/verse_work/index.html"
            ).is_file()
        )
        self.assertTrue(
            (
                context.site
                / "authors/test_author/long_work/1/index.html"
            ).is_file()
        )
        self.assertTrue(
            (
                context.site
                / "authors/test_author/long_work/2/index.html"
            ).is_file()
        )
        contents = (
            context.site / "authors/test_author/long_work/index.html"
        ).read_text(encoding="utf-8")
        first = (
            context.site / "authors/test_author/long_work/1/index.html"
        ).read_text(encoding="utf-8")
        second = (
            context.site / "authors/test_author/long_work/2/index.html"
        ).read_text(encoding="utf-8")
        self.assertIn('href="1/"', contents)
        self.assertIn('href="2/"', contents)
        self.assertIn('href="../2/"', first)
        self.assertIn('href="../1/"', second)
        self.assertTrue(
            (
                context.site
                / "authors/test_author/prose_work/index.html"
            ).is_file()
        )
        pdf_reader = (
            context.site / "authors/test_author/verse_work/pdf/index.html"
        ).read_text(encoding="utf-8")
        self.assertIn(
            '<meta name="robots" content="noindex,follow">', pdf_reader
        )
        self.assertIn("pdfjs/pdf.min.js", pdf_reader)
        self.assertIn('data-url="../source.pdf"', pdf_reader)

        search = json.loads(
            (context.site / "search-index.json").read_text(encoding="utf-8")
        )
        for work in search["works"]:
            self.assertTrue((context.site / work["p"] / "index.html").is_file())

        for url in (context.site / "sitemap.txt").read_text(
            encoding="utf-8"
        ).splitlines():
            path = url.removeprefix("https://www.nepaliarchives.org/")
            target = context.site / path
            if url.endswith("/"):
                target /= "index.html"
            self.assertTrue(target.is_file(), url)
        self.assertEqual(find_broken_links(context.site), [])

    def test_bundled_and_external_download_modes(self):
        bundled, _ = self.run_build("site-bundled")
        bundled_page = (
            bundled.site / "authors/test_author/verse_work/index.html"
        ).read_text(encoding="utf-8")
        self.assertIn('href="text.txt"', bundled_page)
        self.assertTrue(
            (
                bundled.site / "authors/test_author/verse_work/text.txt"
            ).is_file()
        )

        external, _ = self.run_build(
            "site-external", archive_base="https://files.example/archive"
        )
        external_page = (
            external.site / "authors/test_author/verse_work/index.html"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "https://files.example/archive/authors/test_author/"
            "verse_work/text.txt",
            external_page,
        )
        self.assertFalse(
            (
                external.site / "authors/test_author/verse_work/text.txt"
            ).exists()
        )
        external_pdf_reader = (
            external.site
            / "authors/test_author/verse_work/pdf/index.html"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "https://files.example/archive/authors/test_author/"
            "verse_work/source.pdf",
            external_pdf_reader,
        )

    def test_page_specific_assets_remain_scoped(self):
        context, _ = self.run_build("site-assets")
        home = (context.site / "index.html").read_text(encoding="utf-8")
        typing = (context.site / "type/index.html").read_text(encoding="utf-8")
        patro = (context.site / "patro/index.html").read_text(encoding="utf-8")
        pdf_reader = (
            context.site
            / "authors/test_author/verse_work/pdf/index.html"
        ).read_text(encoding="utf-8")
        self.assertNotIn('src="app.js', home)
        self.assertNotIn("pdfjs/pdf.min.js", home)
        self.assertNotIn('id="zg"', home)
        self.assertIn('src="app.js', typing)
        self.assertIn('id="zg"', patro)
        self.assertIn("2026-08-13", patro)
        self.assertNotIn("2026-08-14 ·", patro)
        self.assertTrue((context.site / "patro/2026-08-14/index.html").is_file())
        self.assertIn("pdfjs/pdf.min.js", pdf_reader)


if __name__ == "__main__":
    unittest.main()
