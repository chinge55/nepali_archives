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
from sitegen.seo import audit_site
from prosody import text_digest
import hashlib


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
            "hover-mark.svg",
            "hover-book.svg",
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
            self.root / "pratilipi_adhikar_ain(2059).pdf"
        ).write_bytes(b"%PDF fixture")
        type_assets = self.root / "assets" / "type"
        type_assets.mkdir(parents=True)
        (type_assets / "app.js").write_text("export {};", encoding="utf-8")
        (type_assets / "engine.js").write_text("export {};", encoding="utf-8")
        shutil.copytree(ROOT / "assets" / "chhanda", self.root / "assets" / "chhanda")

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

    def run_build(self, name, archive_base="", build_date=date(2026, 8, 13)):
        context = BuildContext.for_root(
            self.root,
            output_dir=self.root / name,
            archive_base=archive_base,
            build_date=build_date,
        )
        result = build(
            context,
            normalize_key=self.normalize_key,
            translit_word_keys=self.word_keys,
        )
        return context, result

    def add_prosody(self, identifier, kind, metres, passages=None, status="reviewed"):
        work = self.root / "archives/authors/test_author" / identifier
        text = (work / "text.txt").read_text(encoding="utf-8")
        source = work / "source.html"
        source.write_text("<p>Source review fixture</p>", encoding="utf-8")
        metadata_path = work / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["source"]["html"] = "source.html"
        metadata["prosody"] = {
            "status": status, "kind": kind, "metres": metres,
            "text_sha256": text_digest(text), "reviewed": "2026-10-30",
            "evidence": [{"basis": "metrical-reading", "file": "source.html",
                          "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                          "locator": "fixture", "note": "Reviewed fixture annotation."}],
            **({"passages": passages} if passages else {}),
        }
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        return work

    def test_reviewed_metre_has_reader_tag_browse_page_and_search_filter(self):
        self.add_prosody("verse_work", "single", ["malini"])
        context, _ = self.run_build("site-metre")
        reader = (context.site / "authors/test_author/verse_work/index.html").read_text()
        self.assertIn('छन्द: <a href="../../../chhandas/malini/">मालिनी</a>', reader)
        self.assertIn('data-pagefind-filter="metre[data-v]" data-v="malini"', reader)
        self.assertNotIn("kavita-lekhan/engine.js", reader)
        browse = (context.site / "chhandas/malini/index.html").read_text()
        self.assertIn("मालिनी छन्दका कविता", browse)
        self.assertIn('data-scope-metre="malini"', browse)
        self.assertIn('id="metre-author"', browse)
        self.assertIn("../../kavita-lekhan/?metre=malini", browse)
        guide = browse.split('<details class="metre-guide" id="chhanda-parichaya">', 1)[1].split('</details>', 1)[0]
        self.assertIn("यस छन्दबारे र पढ्ने तरिका", guide)
        self.assertIn("आठौँ अक्षरपछि यति", guide)
        self.assertIn("../../kavita-lekhan/?metre=malini", guide)
        self.assertLess(browse.index('id="chhanda-parichaya"'), browse.index('class="prosody-filters"'))
        search = json.loads((context.site / "search-index.json").read_text())
        self.assertIn("मालिनी", next(w for w in search["works"] if w["t"] == "परीक्षण कविता")["ch"])
        self.assertEqual(find_broken_links(context.site), [])

    def test_uncertain_assessment_does_not_create_public_tags_or_free_verse_page(self):
        self.add_prosody("verse_work", "unresolved", [], status="uncertain")
        context, _ = self.run_build("site-metre-pending")
        reader = (context.site / "authors/test_author/verse_work/index.html").read_text()
        self.assertNotIn("छन्द:", reader)
        self.assertFalse((context.site / "chhandas/muktachhanda").exists())
        stats_page = (context.site / "stats/index.html").read_text()
        self.assertIn('०</a></b><span>पहिचान भएका कृति</span>', stats_page)
        self.assertIn('<b>०</b><span>मुक्तछन्दका कृति</span>', stats_page)
        self.assertNotIn('href="../chhandas/muktachhanda/"', stats_page)

    def test_stats_count_mixed_and_paginated_works_once_and_separate_free_verse(self):
        self.add_prosody("verse_work", "free-verse", [])
        work = self.root / "archives/authors/test_author/long_work"
        first, second = [line for line in (work / "text.txt").read_text().splitlines() if len(line) > 100]
        self.add_prosody("long_work", "mixed", ["malini", "shardul"], passages=[
            {"id": "first", "metre": "malini", "label": "पहिलो अंश", "start": first, "end": first},
            {"id": "second", "metre": "shardul", "label": "दोस्रो अंश", "start": second, "end": second},
        ])
        context, _ = self.run_build("site-stats-prosody")
        stats_page = (context.site / "stats/index.html").read_text()
        self.assertIn("२ काव्यात्मक कृतिमध्ये २ कृतिको", stats_page)
        self.assertIn('२</a></b><span>पहिचान भएका कृति</span>', stats_page)
        self.assertIn('<b>२</b><span>छन्दका प्रकार</span>', stats_page)
        self.assertIn('<b>१</b><span>मिश्रित छन्दका कृति</span>', stats_page)
        self.assertIn('href="../chhandas/muktachhanda/">१</a></b><span>मुक्तछन्दका कृति</span>', stats_page)
        for identifier, name in [("malini", "मालिनी"), ("shardul", "शार्दूलविक्रीडित")]:
            self.assertIn(f'href="../chhandas/{identifier}/">{name}</a>', stats_page)
        chhanda_chart = stats_page.split('<section class="chhanda-stats"', 1)[1].split('</section>', 1)[0]
        self.assertEqual(chhanda_chart.count('<span class="sval">१</span>'), 2)
        self.assertNotIn("हरेक build मा स्वतः गणना", stats_page)
        self.assertNotIn('class="meta statnote"', stats_page)
        self.assertEqual(find_broken_links(context.site), [])

    def test_mixed_work_links_to_scoped_passages_without_changing_source_text(self):
        work = self.root / "archives/authors/test_author/long_work"
        text = (work / "text.txt").read_text()
        first, second = [line for line in text.splitlines() if len(line) > 100]
        self.add_prosody("long_work", "mixed", ["malini", "shardul"], passages=[
            {"id": "first", "metre": "malini", "label": "पहिलो अंश", "start": first, "end": first},
            {"id": "second", "metre": "shardul", "label": "दोस्रो अंश", "start": second, "end": second},
        ])
        context, _ = self.run_build("site-metre-mixed")
        contents = (context.site / "authors/test_author/long_work/index.html").read_text()
        self.assertIn('href="#chhanda-details">मिश्रित</a>', contents)
        self.assertIn('id="chhanda-details"', contents)
        browse = (context.site / "chhandas/malini/index.html").read_text()
        self.assertIn("long_work/1/#chhanda-first", browse)
        section = (context.site / "authors/test_author/long_work/1/index.html").read_text()
        self.assertIn('id="chhanda-first"', section)
        self.assertIn('data-v="malini"', section)
        self.assertNotIn('data-v="shardul"', section)
        self.assertIn("प्रथम सर्ग", section)
        self.assertEqual((work / "text.txt").read_text(), text)
        self.assertEqual(find_broken_links(context.site), [])

    def test_single_page_mixed_work_is_searchable_under_each_identified_metre(self):
        work = self.root / "archives/authors/test_author/verse_work"
        text = (work / "text.txt").read_text()
        first, second = text.splitlines()[:2]
        self.add_prosody("verse_work", "mixed", ["malini", "shardul"], passages=[
            {"id": "first", "metre": "malini", "label": "पहिलो अंश", "start": first, "end": first},
            {"id": "second", "metre": "shardul", "label": "दोस्रो अंश", "start": second, "end": second},
        ])
        context, _ = self.run_build("site-single-mixed")
        reader = (context.site / "authors/test_author/verse_work/index.html").read_text()
        for identifier in ["malini", "shardul"]:
            self.assertIn(f'data-pagefind-filter="metre[data-v]" data-v="{identifier}"', reader)
        self.assertIn('id="chhanda-first"', reader)
        self.assertIn('id="chhanda-second"', reader)
        self.assertEqual((work / "text.txt").read_text(), text)

    def test_build_rejects_stale_reviewed_annotations(self):
        work = self.add_prosody("verse_work", "single", ["malini"])
        with (work / "text.txt").open("a") as handle:
            handle.write("\nनयाँ हरफ")
        with self.assertRaisesRegex(ValueError, "stale"):
            self.run_build("site-metre-stale")

    def test_fixture_build_has_pages_search_sitemap_and_valid_links(self):
        context, result = self.run_build("site-fixture")
        chhanda = (context.site / "kavita-lekhan/index.html").read_text(encoding="utf-8")
        self.assertIn('id="poem"', chhanda)
        self.assertIn('<h1>छन्दमा कविता लेखन</h1>', chhanda)
        self.assertIn('छन्दमा कविता लेखन — नेपाली अभिलेख', chhanda)
        self.assertIn('href="../kavita-lekhan/" class=on>कविता लेखन</a>', chhanda)
        self.assertIn('href="chhanda.css?v=', chhanda)
        self.assertTrue((context.site / "kavita-lekhan/engine.js").is_file())
        definitions = json.loads((context.site / "kavita-lekhan/writer-data.json").read_text())["metres"]
        self.assertEqual(len(definitions), 32)
        self.assertEqual({m["id"] for m in definitions}, {m["writer"] for m in definitions})
        self.assertTrue(all(m["description"] and m["structure"] for m in definitions))
        self.assertFalse((context.site / "kavita-lekhan/package.json").exists())
        self.assertIn('rel="canonical" href="https://www.nepaliarchives.org/kavita-lekhan/"', chhanda)
        legacy = (context.site / "chhanda/index.html").read_text(encoding="utf-8")
        self.assertIn('<meta name="robots" content="noindex,follow">', legacy)
        self.assertIn('content="writer-move"', legacy)
        self.assertIn('location.search+location.hash', legacy)
        self.assertNotIn('id="poem"', legacy)
        self.assertNotIn('src="app.js', legacy)
        self.assertEqual([p.name for p in (context.site / "chhanda").iterdir()], ["index.html"])
        sitemap = (context.site / "sitemap.txt").read_text().splitlines()
        self.assertIn("https://www.nepaliarchives.org/kavita-lekhan/", sitemap)
        self.assertNotIn("https://www.nepaliarchives.org/chhanda/", sitemap)
        self.assertNotIn('src="app.js', (context.site / "index.html").read_text(encoding="utf-8"))
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

        author_browse = (
            context.site / "authors/test_author/index.html"
        ).read_text(encoding="utf-8")
        home_browse = (context.site / "index.html").read_text(encoding="utf-8")
        search_source = (context.site / "search.js").read_text(encoding="utf-8")
        self.assertEqual(author_browse.count('<li><a class="row-link"'), 3)
        self.assertIn(
            '<li><a class="row-link" href="verse_work/">'
            '<span class="wmeta">',
            author_browse,
        )
        self.assertIn(
            '<li><a class="row-link" href="authors/test_author/">',
            home_browse,
        )
        self.assertIn("<li><a class=row-link", search_source)
        self.assertIn("<li><a class=ftlink", search_source)
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
        errors, seo = audit_site(context.site)
        self.assertEqual(errors, [])
        self.assertEqual(result.pages, seo['html_pages'])
        sitemap = (context.site / 'sitemap.txt').read_text()
        self.assertIn('authors/test_author/long_work/1/', sitemap)
        self.assertNotIn('/pdf/', sitemap)
        self.assertNotIn('patro/2026-08-13/', sitemap)
        collections_page = (context.site / "collections/index.html").read_text()
        self.assertIn("सङ्ग्रह", collections_page)
        self.assertIn('href="collections/"', home_browse)
        self.assertIn('class="card-intro"', home_browse)
        self.assertIn('class="work-intro"', contents)
        self.assertIn('class="work-intro"', author_browse)
        self.assertNotIn('मूल पृष्ठ स्क्यान उपलब्ध', author_browse)
        self.assertIn('PDF उपलब्ध', author_browse)
        for row in search["works"]:
            self.assertTrue(row['d'])
        self.assertEqual(find_broken_links(context.site), [])

    def test_structured_license_follows_the_recorded_rights_status(self):
        metadata_path = self.root / 'archives/authors/test_author/verse_work/metadata.json'
        metadata = json.loads(metadata_path.read_text())
        for status in ['public-domain', 'permission-granted']:
            with self.subTest(status=status):
                metadata['rights'] = {'status': status}
                metadata_path.write_text(json.dumps(metadata, ensure_ascii=False))
                context, _ = self.run_build('rights-' + status)
                html = (context.site / 'authors/test_author/verse_work/index.html').read_text()
                import re
                data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html).group(1))
                self.assertEqual('license' in data, status == 'public-domain')
                self.assertTrue(data['isAccessibleForFree'])

    def test_author_groups_and_dedication_remain_distinct_from_rights(self):
        import re
        from unittest.mock import patch
        from sitegen.config import AUTHOR_GROUPS

        index_path = self.root / "archives/index.json"
        index = json.loads(index_path.read_text())
        for slug, basis in [("heritage_fixture", "copyright-expired"),
                            ("contributor_fixture", "author-dedication")]:
            relative = Path("archives/authors") / slug / "sample"
            directory = self.root / relative
            directory.mkdir(parents=True)
            metadata = fixture_metadata("sample", slug, "kavita")
            metadata["author"]["id"] = slug
            metadata["rights"] = {"status": "public-domain", "public_domain_basis": basis}
            (directory / "metadata.json").write_text(json.dumps(metadata))
            (directory / "text.txt").write_text("यो कविता हो।")
            index["works"].append({"id": "sample", "path": relative.as_posix()})
        index_path.write_text(json.dumps(index))
        with patch.dict(AUTHOR_GROUPS, {"heritage_fixture": "heritage",
                                       "contributor_fixture": "contributions"}):
            context, result = self.run_build("author-groups")
        self.assertEqual(result.works, 5)
        for path in ["index.html", "authors/index.html"]:
            html = (context.site / path).read_text()
            for group, slug in [("heritage", "heritage_fixture"),
                                ("contributions", "contributor_fixture"),
                                ("other", "test_author")]:
                section = re.search(r'<section[^>]+id="authors-' + group
                                    + r'".*?</section>', html, re.S).group()
                self.assertIn("authors/" + slug + "/", section)
                self.assertEqual(html.count('class="row-link" href="'
                                            + ("../" if path.startswith("authors/") else "")
                                            + "authors/" + slug + '/"'), 1)
        contributed = (context.site / "authors/contributor_fixture/sample/index.html").read_text()
        inherited = (context.site / "authors/heritage_fixture/sample/index.html").read_text()
        self.assertIn("लेखकद्वारा सार्वजनिक डोमेनमा समर्पित", contributed)
        self.assertNotIn("लेखकद्वारा सार्वजनिक डोमेनमा समर्पित", inherited)
        author = (context.site / "authors/contributor_fixture/index.html").read_text()
        self.assertIn("कृति लेखकले सार्वजनिक डोमेनमा समर्पित", author)
        # All groups remain in the common search index and retain valid routes.
        search = json.loads((context.site / "search-index.json").read_text())
        self.assertEqual(len(search["works"]), 5)
        self.assertEqual(find_broken_links(context.site), [])

    def test_duplicate_chapter_heading_has_redirect_and_one_contents_entry(self):
        from check_reader_content import audit_readers
        work = self.root / "archives/authors/test_author/long_work/text.txt"
        work.write_text("प्रथम सर्ग\n\nकाव्यको नाम\n\nप्रथम सर्ग\n\n"
                        + "पहिलो खण्डको पाठ। " * 600
                        + "\n\nदोस्रो सर्ग\n\n" + "दोस्रो खण्डको पाठ। " * 600)
        context, _ = self.run_build("merged-chapters")
        parent = context.site / "authors/test_author/long_work"
        toc = (parent / "index.html").read_text()
        self.assertIn('href="2/"', toc)
        self.assertNotIn('href="1/"', toc)
        redirect = (parent / "1/index.html").read_text()
        self.assertIn('noindex,follow', redirect)
        self.assertIn('0;url=../2/', redirect)
        self.assertNotIn('data-pagefind-body', redirect)
        sitemap = (context.site / "sitemap.txt").read_text()
        self.assertNotIn('authors/test_author/long_work/1/', sitemap)
        self.assertIn('authors/test_author/long_work/2/', sitemap)
        self.assertEqual(audit_site(context.site)[0], [])
        self.assertEqual(audit_readers(context.site)[0], [])
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

    def test_patro_marks_an_outdated_fallback_instead_of_claiming_it_is_today(self):
        context, _ = self.run_build("site-patro-stale", build_date=date(2026, 8, 15))
        root = (context.site / "patro/index.html").read_text(encoding="utf-8")
        self.assertIn('class="pt-stale is-stale"', root)
        self.assertIn("यो पात्रो पुरानो छ", root)
        self.assertIn("2026-08-14", root)
        self.assertNotIn("आजको राशिफल", root)
        self.assertIn('data-patro-stale', root)
        dated = (context.site / "patro/2026-08-13/index.html").read_text(encoding="utf-8")
        self.assertNotIn('id="patro-stale"', dated)

    def test_current_patro_hides_the_stale_notice(self):
        context, _ = self.run_build("site-patro-current")
        root = (context.site / "patro/index.html").read_text(encoding="utf-8")
        self.assertIn('id="patro-stale" class="pt-stale"', root)
        self.assertNotIn('class="pt-stale is-stale"', root)

    def test_patro_labels_a_moon_sign_end_more_than_one_day_ahead(self):
        path = self.root / "horoscope/content/panchanga-2026-08.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["days"]["2026-08-13"]["moon_rashi"] = {"name": "परीक्षण", "ends": "2026-08-15T18:03"}
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        context, _ = self.run_build("site-patro-transit")
        html = (context.site / "patro/index.html").read_text(encoding="utf-8")
        self.assertIn("१८:०३ (२ दिनपछि)", html)

    def test_page_specific_assets_remain_scoped(self):
        context, _ = self.run_build("site-assets")
        home = (context.site / "index.html").read_text(encoding="utf-8")
        typing = (context.site / "type/index.html").read_text(encoding="utf-8")
        chhanda = (context.site / "kavita-lekhan/index.html").read_text(encoding="utf-8")
        patro = (context.site / "patro/index.html").read_text(encoding="utf-8")
        pdf_reader = (
            context.site
            / "authors/test_author/verse_work/pdf/index.html"
        ).read_text(encoding="utf-8")
        self.assertNotIn('src="app.js', home)
        self.assertNotIn("pdfjs/pdf.min.js", home)
        self.assertNotIn('id="zg"', home)
        self.assertIn('src="app.js', typing)
        self.assertIn('src="app.js', chhanda)
        self.assertNotIn('chhanda.css', home)
        self.assertNotIn('chhanda.css', typing)
        self.assertIn('id="zg"', patro)
        self.assertIn("2026-08-13", patro)
        self.assertNotIn("2026-08-14 ·", patro)
        self.assertTrue((context.site / "patro/2026-08-14/index.html").is_file())
        self.assertIn("pdfjs/pdf.min.js", pdf_reader)


if __name__ == "__main__":
    unittest.main()
