import hashlib
import tempfile
import unittest
from pathlib import Path

from pipeline.validate import validate_pdf_editions


class PdfEditionValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name) / "work"
        self.work.mkdir()
        self.pdf = self.work / "source.pdf"
        self.pdf.write_bytes(b"%PDF-1.7\nfixture")
        self.digest = hashlib.sha256(self.pdf.read_bytes()).hexdigest()

    def tearDown(self):
        self.tmp.cleanup()

    def metadata(self):
        return {
            "formats": {"pdf": "source.pdf"},
            "source": {"pdf_editions": [{
                "id": "primary", "file": "source.pdf", "kind": "scan",
                "sha256": self.digest, "page_count": 4,
                "sections": [{"label": "प्रथम", "page_start": 1, "page_end": 4}],
            }]},
        }

    def test_valid_primary_and_edition_pass(self):
        self.assertEqual(validate_pdf_editions(self.work, self.metadata()), [])

    def test_wrong_hash_missing_pdf_and_bad_signature_are_reported(self):
        meta = self.metadata()
        meta["source"]["pdf_editions"][0]["sha256"] = "0" * 64
        self.pdf.write_bytes(b"plain text")
        errors = validate_pdf_editions(self.work, meta)
        self.assertTrue(any("hash does not match" in e for e in errors))
        self.assertTrue(any("PDF signature" in e for e in errors))
        self.pdf.unlink()
        errors = validate_pdf_editions(self.work, meta)
        self.assertTrue(any("missing" in e for e in errors))

    def test_duplicate_edition_and_out_of_range_section_fail(self):
        meta = self.metadata()
        meta["source"]["pdf_editions"].append(dict(meta["source"]["pdf_editions"][0]))
        meta["source"]["pdf_editions"][1]["id"] = "primary"
        meta["source"]["pdf_editions"][1]["sections"] = [{"label": "bad", "page_start": 0, "page_end": 5}]
        errors = validate_pdf_editions(self.work, meta)
        self.assertTrue(any("duplicate edition id" in e for e in errors))
        self.assertTrue(any("page range" in e for e in errors))

    def test_path_escape_and_symlink_are_rejected(self):
        meta = self.metadata()
        meta["source"]["pdf_editions"][0]["file"] = "../source.pdf"
        errors = validate_pdf_editions(self.work, meta)
        self.assertTrue(any("escapes" in e or "missing" in e for e in errors))
        link = self.work / "link.pdf"
        try:
            link.symlink_to(self.pdf)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        meta = self.metadata()
        meta["source"]["pdf_editions"][0]["file"] = "link.pdf"
        errors = validate_pdf_editions(self.work, meta)
        self.assertTrue(any("symlink" in e for e in errors))

    def test_malformed_edition_does_not_crash(self):
        errors = validate_pdf_editions(self.work, {"source": {"pdf_editions": [None, {"id": "x"}]}})
        self.assertTrue(any("must be an object" in e for e in errors))
        self.assertTrue(any("file" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
