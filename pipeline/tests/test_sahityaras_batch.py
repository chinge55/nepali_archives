import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from sahityaras_batch import SourceError, add_collection, encoded, write_files


AUTHOR = {"id": "author", "name": "लेखक", "name_roman": "Lekhak"}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def manifest_for(*entries):
    return {"author": AUTHOR, "documents": list(entries)}


class CollectionTests(unittest.TestCase):
    def test_add_collection_preserves_prose_and_is_idempotent(self):
        metadata = {"description": "From the collection पुरानो सङ्ग्रह; अर्को सङ्ग्रह. मौलिक prose."}
        once = add_collection(metadata, "नयाँ सङ्ग्रह")
        twice = add_collection(once, "नयाँ सङ्ग्रह")

        self.assertEqual(
            once["description"],
            "From the collection पुरानो सङ्ग्रह; अर्को सङ्ग्रह; नयाँ सङ्ग्रह. मौलिक prose.",
        )
        self.assertEqual(twice, once)
        self.assertEqual(metadata["description"], "From the collection पुरानो सङ्ग्रह; अर्को सङ्ग्रह. मौलिक prose.")

    def test_add_collection_adds_required_prefix_without_discarding_description(self):
        self.assertEqual(
            add_collection({"description": "पहिलेको विवरण."}, "नयाँ सङ्ग्रह")["description"],
            "From the collection नयाँ सङ्ग्रह. पहिलेको विवरण.",
        )


class WriteFilesTests(unittest.TestCase):
    def test_preflights_every_output_before_mutating_any_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            blocked = root / "archives/authors/author/two.txt"
            blocked.parent.mkdir(parents=True)
            blocked.write_bytes(b"user content")
            outputs = {
                "archives/authors/author/one.txt": b"new file",
                "archives/authors/author/two.txt": b"reviewed file",
            }
            with self.assertRaises(SourceError):
                write_files(outputs, root, apply=False, manifest=manifest_for())
            self.assertFalse((root / "archives/authors/author/one.txt").exists())
            self.assertEqual(blocked.read_bytes(), b"user content")

    def test_stage_output_collision_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "metadata.json"
            path.write_bytes(b"stage draft")
            with self.assertRaises(SourceError):
                write_files({"metadata.json": b"different output"}, root, apply=False, manifest=manifest_for())
            self.assertEqual(path.read_bytes(), b"stage draft")

    def test_apply_accepts_exact_reviewed_metadata_change_and_rerun_is_zero_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            relative = "archives/authors/author/existing/metadata.json"
            path = root / relative
            baseline = encoded({"author": AUTHOR, "description": "पुरानो विवरण"})
            updated = encoded({"author": AUTHOR, "description": "From the collection नयाँ सङ्ग्रह. पुरानो विवरण"})
            path.parent.mkdir(parents=True)
            path.write_bytes(baseline)
            entry = {
                "work_id": "existing",
                "decision": "map-existing",
                "baseline_metadata_sha256": sha256(baseline),
            }
            manifest = manifest_for(entry)

            self.assertEqual(write_files({relative: updated}, root, apply=True, manifest=manifest), 1)
            self.assertEqual(path.read_bytes(), updated)
            self.assertEqual(write_files({relative: updated}, root, apply=True, manifest=manifest), 0)
            self.assertEqual(path.read_bytes(), updated)

    def test_metadata_edit_is_rejected_unless_it_is_the_reviewed_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            relative = "archives/authors/author/existing/metadata.json"
            path = root / relative
            baseline = encoded({"author": AUTHOR, "description": "पुरानो विवरण"})
            reviewed = encoded({"author": AUTHOR, "description": "From the collection सङ्ग्रह. पुरानो विवरण"})
            edited = encoded({"author": AUTHOR, "description": "मानिसले बदलेको विवरण"})
            path.parent.mkdir(parents=True)
            path.write_bytes(edited)
            entry = {
                "work_id": "existing",
                "decision": "map-existing",
                "baseline_metadata_sha256": sha256(baseline),
            }
            with self.assertRaises(SourceError):
                write_files({relative: reviewed}, root, apply=True, manifest=manifest_for(entry))
            self.assertEqual(path.read_bytes(), edited)

    def test_unrelated_contents_are_preserved_for_existing_work(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            relative = "archives/authors/author/existing/metadata.json"
            path = root / relative
            baseline = encoded({"author": AUTHOR, "description": "पुरानो विवरण"})
            updated = encoded({"author": AUTHOR, "description": "From the collection सङ्ग्रह. पुरानो विवरण"})
            unrelated = path.parent / "research-notes.txt"
            path.parent.mkdir(parents=True)
            path.write_bytes(baseline)
            unrelated.write_text("असम्बन्धित सामग्री", encoding="utf-8")
            entry = {
                "work_id": "existing",
                "decision": "map-existing",
                "baseline_metadata_sha256": sha256(baseline),
            }
            write_files({relative: updated}, root, apply=True, manifest=manifest_for(entry))
            self.assertEqual(unrelated.read_text(encoding="utf-8"), "असम्बन्धित सामग्री")

    def test_include_work_with_unexpected_contents_fails_without_deleting_them(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            work = root / "archives/authors/author/new"
            work.mkdir(parents=True)
            unrelated = work / "unexpected.txt"
            unrelated.write_text("keep me", encoding="utf-8")
            entry = {"work_id": "new", "decision": "include"}
            outputs = {"archives/authors/author/new/text.txt": b"new poem"}
            with self.assertRaises(SourceError):
                write_files(outputs, root, apply=True, manifest=manifest_for(entry))
            self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep me")
            self.assertFalse((work / "text.txt").exists())


if __name__ == "__main__":
    unittest.main()
