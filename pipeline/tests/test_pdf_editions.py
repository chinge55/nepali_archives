"""Focused regressions for optional source PDF editions."""

import hashlib
import json
import sys
from pathlib import Path

from jsonschema import validate

from pipeline.tests.test_site_build import FullBuildTests


SCHEMA = Path(__file__).parents[2] / "metadata.schema.json"


class PdfEditionTests(FullBuildTests):
    def _add_editions(self):
        work = self.root / "archives/authors/test_author/long_work"
        primary = work / "source.pdf"
        alternate = work / "digital.pdf"
        primary.write_bytes(b"%PDF primary")
        alternate.write_bytes(b"%PDF alternate")
        meta_path = work / "metadata.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["formats"]["pdf"] = "source.pdf"
        meta["source"]["pdf_editions"] = [
            {
                "id": "original-scan",
                "file": "source.pdf",
                "kind": "scan",
                "label": "मूल पृष्ठ",
                "sha256": hashlib.sha256(primary.read_bytes()).hexdigest(),
                "page_count": 2,
                "origin": {"name": "Fixture scan", "url": "https://example.test/scan"},
                "sections": [
                    {"label": "प्रथम सर्ग — आरम्भ", "page_start": 1, "page_end": 1},
                    {"label": "<दोस्रो सर्ग>", "page_start": 2, "page_end": 2},
                ],
            },
            {
                "id": "digital-edition",
                "file": "digital.pdf",
                "kind": "typeset",
                "label": "साहित्यरस डिजिटल पुस्तक",
                "sha256": hashlib.sha256(alternate.read_bytes()).hexdigest(),
                "page_count": 3,
                "origin": {"name": "Fixture typeset", "url": None},
            },
        ]
        meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    def test_schema_accepts_edition_shape_and_rejects_invalid_kind(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        work = self.root / "archives/authors/test_author/verse_work/metadata.json"
        meta = json.loads(work.read_text(encoding="utf-8"))
        meta.update({"language": "ne", "rights": {"status": "public-domain"},
                     "text": {"extraction_method": "manual", "ocr_status": "none"}})
        meta["source"]["pdf_editions"] = [{
            "id": "scan-1", "file": "source.pdf", "kind": "scan",
            "label": "मूल पृष्ठ", "sha256": "a" * 64, "page_count": 1,
            "origin": {"name": "Fixture", "url": None},
        }]
        validate(meta, schema)
        meta["source"]["pdf_editions"][0]["kind"] = "unknown"
        try:
            validate(meta, schema)
        except Exception:
            pass
        else:
            self.fail("invalid PDF edition kind passed schema validation")

    def test_multiple_editions_are_copied_labeled_and_section_linked(self):
        self._add_editions()
        context, _ = self.run_build("site-editions")
        work = context.site / "authors/test_author/long_work"
        self.assertTrue((work / "source.pdf").is_file())
        self.assertTrue((work / "digital.pdf").is_file())
        self.assertTrue((work / "pdf/index.html").is_file())
        self.assertTrue((work / "pdf/digital-edition/index.html").is_file())
        contents = (work / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="pdf/digital-edition/"', contents)
        self.assertIn('<option value="pdf/" data-download="source.pdf" selected>', contents)
        self.assertIn('class="pdf-choice-controls" hidden', contents)
        self.assertIn('class="pdf-choice-fallback"', contents)
        self.assertIn("साहित्यरस डिजिटल पुस्तक — डिजिटल संस्करण", contents)
        reader = (work / "pdf/digital-edition/index.html").read_text(encoding="utf-8")
        self.assertIn('data-url="../../digital.pdf"', reader)
        self.assertIn('<option value="../../pdf/digital-edition/" data-download="../../digital.pdf" selected>', reader)
        self.assertIn("साहित्यरस डिजिटल पुस्तक — डिजिटल संस्करण", reader)
        section = (work / "1/index.html").read_text(encoding="utf-8")
        self.assertIn('href="../pdf/?page=1"', section)

    def test_edition_picker_uses_external_downloads_and_local_readers(self):
        self._add_editions()
        context, _ = self.run_build("site-external-editions", archive_base="https://files.example/archive")
        work = context.site / "authors/test_author/long_work"
        contents = (work / "index.html").read_text()
        self.assertIn('value="pdf/digital-edition/" data-download="https://files.example/archive/authors/test_author/long_work/digital.pdf"', contents)
        reader = (work / "pdf/digital-edition/index.html").read_text()
        self.assertIn('value="../../pdf/" data-download="https://files.example/archive/authors/test_author/long_work/source.pdf"', reader)

    def test_multiline_source_heading_matches_reader_subtitle(self):
        self._add_editions()
        path = self.root / 'archives/authors/test_author/long_work/metadata.json'
        meta = json.loads(path.read_text())
        meta['source']['pdf_editions'][0]['sections'][0]['label'] = 'प्रथम सर्ग\nआरम्भ'
        path.write_text(json.dumps(meta, ensure_ascii=False))
        context, _ = self.run_build('site-multiline-heading')
        section = (context.site / 'authors/test_author/long_work/1/index.html').read_text()
        self.assertIn('href="../pdf/?page=1"', section)

    def test_reviewed_alias_links_without_duplicating_pdf_contents(self):
        self._add_editions()
        path = self.root / 'archives/authors/test_author/long_work/metadata.json'
        meta = json.loads(path.read_text())
        section = meta['source']['pdf_editions'][0]['sections'][0]
        section.update(label='प्रथम सर्ग', aliases=['प्रथम सर्ग — आरम्भ'])
        path.write_text(json.dumps(meta, ensure_ascii=False))
        context, _ = self.run_build('site-section-alias')
        work = context.site / 'authors/test_author/long_work'
        self.assertIn('href="../pdf/?page=1"', (work / '1/index.html').read_text())
        reader = (work / 'pdf/index.html').read_text()
        self.assertEqual(reader.count('href="?page=1"'), 1)
        self.assertNotIn('प्रथम सर्ग — आरम्भ</a>', reader)

    def test_default_reader_keeps_original_single_pdf_behavior(self):
        context, _ = self.run_build("site-default")
        reader = (context.site / "authors/test_author/verse_work/pdf/index.html").read_text(encoding="utf-8")
        self.assertIn('data-url="../source.pdf"', reader)
        self.assertIn("मूल पृष्ठ", reader)
        self.assertNotIn('class="pdf-edition"', reader)
        self.assertFalse((context.site / "authors/test_author/verse_work/pdf/").joinpath("anything").exists())

    def test_reader_clamps_requested_page(self):
        js = (Path(__file__).parents[2] / "assets/site/pdf-reader.js").read_text(encoding="utf-8")
        self.assertIn("Math.min(N,Math.max(1,Math.floor(requestedPage)))", js)
        self.assertIn("scrollIntoView", js)


if __name__ == "__main__":
    import unittest
    unittest.main()
