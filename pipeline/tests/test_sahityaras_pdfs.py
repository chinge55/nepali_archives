"""Validation and optional PyMuPDF integration tests for sahityaras_pdfs."""

import base64
import hashlib
import importlib
import tempfile
import unittest
from pathlib import Path

from pipeline import sahityaras_pdfs


class PdfPlanValidationTests(unittest.TestCase):
    def test_positive_page_validation_is_strict(self):
        for value in (0, -1, True, 1.0, "1"):
            with self.assertRaises(ValueError):
                sahityaras_pdfs._positive_int(value, "page")
        self.assertEqual(sahityaras_pdfs._positive_int(2, "page"), 2)

    def test_dependency_is_lazy(self):
        self.assertTrue(callable(sahityaras_pdfs.slice_pdf))
        self.assertTrue(callable(sahityaras_pdfs.audit_pdf))


try:
    fitz = importlib.import_module("fitz")
except ImportError:
    fitz = None


@unittest.skipUnless(fitz is not None, "PyMuPDF optional dependency is not installed")
class PdfIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source.pdf"
        doc = fitz.open()
        red_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
        p1 = doc.new_page(width=200, height=200)
        p1.insert_text((20, 30), "KEEP ONE")
        p1.insert_text((20, 80), "SECRET TEXT")
        p1.insert_image(fitz.Rect(20, 90, 120, 170), stream=red_png)
        p2 = doc.new_page(width=200, height=200)
        p2.insert_text((20, 30), "EXCLUDED PAGE")
        p2.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(10, 10, 100, 30), "uri": "https://example.test"})
        p3 = doc.new_page(width=200, height=200)
        p3.insert_text((20, 30), "KEEP THREE")
        doc.save(self.source, garbage=4, clean=1, deflate=1, no_new_id=True)
        doc.close()

    def tearDown(self):
        self.temp.cleanup()

    def test_discontiguous_selection_redaction_and_scrubbing(self):
        plan = [
            {"page": 1, "redactions": [{"rect": [15, 65, 130, 180], "reason": "editorial watermark"}]},
            {"page": 3},
        ]
        data = sahityaras_pdfs.slice_pdf(self.source, plan, title="Work", author="Author")
        out = fitz.open(stream=data, filetype="pdf")
        self.assertEqual(out.page_count, 2)
        self.assertIn("KEEP ONE", out[0].get_text())
        self.assertNotIn("SECRET TEXT", out[0].get_text())
        self.assertNotIn("EXCLUDED PAGE", "".join(page.get_text() for page in out))
        self.assertEqual(sum(len(page.get_links()) for page in out), 0)
        self.assertEqual(sum(sum(1 for _ in (page.annots() or [])) for page in out), 0)
        pix = out[0].get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
        # Redaction area is white after the image pixels are removed.
        self.assertGreaterEqual(pix.samples[90 * pix.stride + 20 * pix.n], 245)
        self.assertEqual(out.metadata.get("title"), "Work")
        self.assertEqual(out.metadata.get("author"), "Author")
        out.close()

    def test_deterministic_bytes_and_audit(self):
        plan = [{"page": 3}, {"page": 1}]
        first = sahityaras_pdfs.slice_pdf(self.source, plan, title="Work", author="Author")
        second = sahityaras_pdfs.slice_pdf(self.source, plan, title="Work", author="Author")
        self.assertEqual(first, second)
        output = self.root / "out.pdf"
        output.write_bytes(first)
        facts = sahityaras_pdfs.audit_pdf(output)
        self.assertEqual(facts["page_count"], 2)
        self.assertEqual(facts["sha256"], hashlib.sha256(first).hexdigest())
        self.assertEqual(facts["links"], 0)
        self.assertEqual(facts["annotations"], 0)
        self.assertEqual(facts["attachments"], 0)
        self.assertEqual(facts["javascript"], 0)
        self.assertEqual(facts["actions"], 0)

    def test_inline_citation_redaction_is_targeted_and_fail_closed(self):
        source = self.root / "citation.pdf"
        doc = fitz.open()
        page = doc.new_page(width=300, height=150)
        page.insert_text((20, 40), "BODY [1]")
        page.insert_text((20, 90), "OTHER [2]")
        doc.save(source, garbage=4, no_new_id=True)
        doc.close()
        data = sahityaras_pdfs.slice_pdf(
            source,
            [{"page": 1, "redactions": [{"kind": "citation", "rect": [52, 25, 70, 50], "reason": "citation"}]}],
            title="Work", author="Author",
        )
        out = fitz.open(stream=data, filetype="pdf")
        text = out[0].get_text()
        self.assertNotIn("[1]", text)
        self.assertIn("[2]", text)
        out.close()
        with self.assertRaises(ValueError):
            sahityaras_pdfs.slice_pdf(
                source,
                [{"page": 1, "redactions": [{"kind": "citation", "rect": [10, 20, 130, 100], "reason": "ambiguous"}]}],
                title="Work", author="Author",
            )

    def test_real_mayavini_citation_geometry(self):
        source = Path(".ingest-work/sahityaras/pdf/originals/mayavini-sarsi.pdf")
        if not source.exists():
            self.skipTest("real staged Mayavini source unavailable")
        data = sahityaras_pdfs.slice_pdf(
            source,
            [{"page": 18, "redactions": [{"kind": "citation", "rect": [194.25, 72.75, 207.75, 87.75], "reason": "editorial citation"}]}],
            title="Mayavini", author="Author",
        )
        out = fitz.open(stream=data, filetype="pdf")
        self.assertNotIn("[५]", out[0].get_text())
        out.close()

    def test_invalid_plans_rejected(self):
        cases = [
            [{"page": 0}], [{"page": 4}], [{"page": 1}, {"page": 1}],
            [{"page": 1, "redactions": [{"rect": [1, 1, 1, 2], "reason": "x"}]}],
            [{"page": 1, "redactions": [{"rect": [1, 1, float("nan"), 2], "reason": "x"}]}],
            [{"page": 1, "redactions": [{"rect": [1, 1, 2, 2], "reason": " "}]}],
        ]
        for plan in cases:
            with self.assertRaises(ValueError, msg=plan):
                sahityaras_pdfs.slice_pdf(self.source, plan, title="Work", author="Author")


if __name__ == "__main__":
    unittest.main()
