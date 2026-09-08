"""Contract tests for reviewed Sahitya Ras PDF batch application."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pipeline import sahityaras_pdf_batch as batch


def digest(data):
    return hashlib.sha256(data).hexdigest()


class BatchFixture(unittest.TestCase):
    def setUp(self):
        self.metadata_before = {
            "id": "work1",
            "title": "काम",
            "author": {"id": "author1", "name": "लेखक"},
            "rights": {"status": "public-domain"},
            "source": {
                "name": "Existing source", "url": None, "pdf": "canonical.pdf",
                "pdf_editions": [{
                    "id": "canonical", "file": "canonical.pdf", "kind": "scan",
                    "label": "मूल संस्करण", "sha256": "c" * 64, "page_count": 9,
                    "origin": {"name": "Existing source", "url": None},
                }],
            },
            "formats": {"pdf": "canonical.pdf", "txt": "text.txt"},
            "text": {"proofread": True, "extraction_method": "manual", "ocr_status": "none"},
        }
        self.book = {
            "id": "book1", "kind": "scan", "title": "साहित्यरस पुस्तक",
            "pdf_url": "https://example.test/book1.pdf", "sha256": "b" * 64,
            "page_count": 2,
            "redactions": {"1": [{"rect": [1, 2, 3, 4], "reason": "editorial matter"}]},
            "documents": [{
                "path": "text/chapter.html", "page_start": 1, "page_end": 2,
                "decision": "include", "reason": "literary text",
                "destination": "archives/authors/author1/work1",
            }],
        }
        self.work = {
            "author_id": "author1", "id": "work1",
            "metadata_before": deepcopy(self.metadata_before),
            "baseline_metadata_sha256": digest(batch.encoded(self.metadata_before)),
            "text_sha256": digest(b"existing text"),
            "pdfs": [{
                "id": "book1-work1", "file": "sahityaras.pdf", "book": "book1",
                "documents": ["text/chapter.html"],
                "pages": [
                    {"page": 1, "redactions": self.book["redactions"]["1"]},
                    {"page": 2},
                ],
                "sections": [{"label": "अध्याय", "page_start": 1, "page_end": 2}],
                "sha256": "d" * 64,
            }],
        }
        self.manifest = {
            "schema_version": 1, "reviewed": True, "prepared_date": "2026-09-08",
            "books": [self.book], "works": [self.work],
        }

    def test_manifest_requires_complete_unique_assignments(self):
        self.assertEqual(batch.validate_manifest(self.manifest)["book1"]["id"], "book1")
        missing = deepcopy(self.manifest)
        missing["works"][0]["pdfs"][0]["documents"] = []
        missing["works"][0]["pdfs"][0]["pages"] = []
        with self.assertRaises(ValueError):
            batch.validate_manifest(missing)
        duplicate = deepcopy(self.manifest)
        duplicate["books"][0]["documents"].append(deepcopy(duplicate["books"][0]["documents"][0]))
        with self.assertRaises(ValueError):
            batch.validate_manifest(duplicate)

    def test_excluded_pages_are_not_kept_and_are_strictly_validated(self):
        manifest = deepcopy(self.manifest)
        doc = manifest["books"][0]["documents"][0]
        doc["excluded_pages"] = [{"page": 1, "reason": "front matter"}]
        pdf = manifest["works"][0]["pdfs"][0]
        pdf["pages"] = [{"page": 2}]
        pdf["sections"] = [{"label": "अध्याय", "page_start": 1, "page_end": 1}]
        batch.validate_manifest(manifest)
        kept = deepcopy(manifest)
        kept["works"][0]["pdfs"][0]["pages"] = [{"page": 1}, {"page": 2}]
        with self.assertRaises(ValueError):
            batch.validate_manifest(kept)
        for exclusions in (
            [{"page": 0, "reason": "bad"}],
            [{"page": 1, "reason": "a"}, {"page": 1, "reason": "b"}],
            [{"page": 1, "reason": ""}],
        ):
            invalid = deepcopy(manifest)
            invalid["books"][0]["documents"][0]["excluded_pages"] = exclusions
            with self.assertRaises(ValueError):
                batch.validate_manifest(invalid)

    def test_redactions_are_required_and_passed_to_slicer(self):
        omitted = deepcopy(self.manifest)
        omitted["works"][0]["pdfs"][0]["pages"][0].pop("redactions")
        with self.assertRaises(ValueError):
            batch.validate_manifest(omitted)
        with tempfile.TemporaryDirectory() as temp:
            root, originals = Path(temp), Path(temp) / "originals"
            originals.mkdir()
            original = b"reviewed source"
            (originals / "book1.pdf").write_bytes(original)
            self.book["sha256"] = digest(original)
            workdir = root / "archives/authors/author1/work1"
            workdir.mkdir(parents=True)
            (workdir / "text.txt").write_bytes(b"existing text")
            captured = []
            def fake_slice(_source, pages, **kwargs):
                captured.append(pages)
                return b"generated pdf"
            self.work["pdfs"][0]["sha256"] = digest(b"generated pdf")
            with patch.object(batch, "slice_pdf", fake_slice):
                batch.build_outputs(self.manifest, originals, root, verify_hashes=False)
            self.assertEqual(captured[0][0]["redactions"], self.book["redactions"]["1"])

    def test_shared_page_members_require_their_own_removals(self):
        m = deepcopy(self.manifest)
        book = m['books'][0]
        parent = book['documents'][0]
        parent.update(decision='split', members=[{
            'id': 'member-1', 'title': 'पहिलो', 'decision': 'include',
            'reason': 'Reviewed independently numbered member',
            'page_start': 1, 'page_end': 2,
            'destination': 'archives/authors/author1/work1',
            'redactions': {'2': [{'rect': [0, 40, 100, 100], 'reason': 'Next piece'}]},
        }])
        pdf = m['works'][0]['pdfs'][0]
        pdf['documents'] = [parent['path'] + '#member-1']
        pdf['pages'][1]['redactions'] = parent['members'][0]['redactions']['2']
        batch.validate_manifest(m)
        missing = deepcopy(m)
        missing['works'][0]['pdfs'][0]['pages'][1].pop('redactions')
        with self.assertRaises(ValueError):
            batch.validate_manifest(missing)
        outside = deepcopy(m)
        outside['books'][0]['documents'][0]['members'][0]['page_end'] = 3
        with self.assertRaises(ValueError):
            batch.validate_manifest(outside)
        omitted = deepcopy(m)
        omitted['books'][0]['documents'][0]['members'].append({
            **parent['members'][0], 'id': 'member-2'})
        with self.assertRaises(ValueError):
            batch.validate_manifest(omitted)

    def test_metadata_for_preserves_existing_canonical_and_proofread(self):
        books = batch.validate_manifest(self.manifest)
        result = batch.metadata_for(self.work, books, "2026-09-08")
        self.assertEqual(result["source"]["pdf"], "canonical.pdf")
        self.assertEqual(result["formats"]["pdf"], "canonical.pdf")
        self.assertEqual(result["source"]["pdf_editions"][0]["id"], "canonical")
        self.assertEqual(result["source"]["pdf_editions"][1]["id"], "book1-work1")
        self.assertTrue(result["text"]["proofread"])

    def test_write_outputs_preflights_all_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            relative = "archives/authors/author1/work1/metadata.json"
            existing = root / relative
            existing.parent.mkdir(parents=True)
            existing.write_bytes(b"old")
            outputs = {"new/file.pdf": b"new", relative: b"changed"}
            with self.assertRaises(ValueError):
                batch.write_outputs(outputs, self.manifest, root, apply=False)
            self.assertFalse((root / "new/file.pdf").exists())
            # Apply only allows replacement of the recorded baseline.
            self.manifest["works"][0]["baseline_metadata_sha256"] = digest(b"old")
            self.assertEqual(batch.write_outputs({relative: b"changed"}, self.manifest, root, apply=True), 1)
            self.assertEqual(batch.write_outputs({relative: b"changed"}, self.manifest, root, apply=True), 0)
            self.assertEqual(existing.read_bytes(), b"changed")


if __name__ == "__main__":
    unittest.main()
