import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline import sahityaras_fetch as fetch


ROW = {
    "source_repository_url": "https://github.com/example/book",
    "default_branch": "main",
    "source_title": "पुस्तक",
    "source_author": "लेखक",
}


def archive(*names):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as tar:
        for name in names:
            data = b"<p>text</p>"
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return stream.getvalue()


class FetchSecurityTests(unittest.TestCase):
    def test_source_member_rejects_traversal_and_absolute_paths(self):
        self.assertFalse(fetch.source_member("repo/src/EPUB/text/../../escape.xhtml"))
        self.assertFalse(fetch.source_member("repo/src/EPUB/text//book.xhtml"))
        self.assertFalse(fetch.source_member("repo//src/EPUB/text/book.xhtml"))

    def test_duplicate_selected_tar_paths_fail(self):
        data = archive("repo-sha/src/EPUB/text/book.xhtml", "repo-sha/src/EPUB/text/book.xhtml")
        with tempfile.TemporaryDirectory() as temp, patch.object(fetch, "resolve_commit", return_value="a" * 40), patch.object(fetch, "request", return_value=data):
            with self.assertRaises(RuntimeError):
                fetch.fetch_one(ROW, Path(temp), delay=0)

    def test_pinned_revision_bypasses_branch_resolution(self):
        revision = "a" * 40
        data = archive("repo-sha/src/EPUB/text/book.xhtml")
        with tempfile.TemporaryDirectory() as temp, patch.object(fetch, "resolve_commit", side_effect=AssertionError("must not resolve")), patch.object(fetch, "request", return_value=data):
            result = fetch.fetch_one(ROW, Path(temp), delay=0, revision=revision)
        self.assertEqual(result["commit"], revision)
        self.assertFalse(result["cached"])

    def test_cached_revision_must_match_pinned_revision(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "book"
            source = target / "src/EPUB/text/book.xhtml"
            source.parent.mkdir(parents=True)
            data = b"cached source"
            source.write_bytes(data)
            snapshot = {"repository": "example/book", "branch": "main", "commit": "a" * 40,
                        "files": [{"path": "src/EPUB/text/book.xhtml", "size": len(data),
                                   "sha256": hashlib.sha256(data).hexdigest()}]}
            (target / "snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                fetch.fetch_one(ROW, Path(temp), delay=0, revision="b" * 40)

    def test_symlink_cache_root_fails_before_network(self):
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            target = cache / "book"
            target.symlink_to(cache)
            with patch.object(fetch, "resolve_commit") as resolve:
                with self.assertRaises(RuntimeError):
                    fetch.fetch_one(ROW, cache, delay=0)
                resolve.assert_not_called()

    def test_cached_snapshot_rejects_missing_or_extra_files(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "book"
            target.mkdir()
            (target / "src.xhtml").write_bytes(b"ok")
            snapshot = {"repository": "example/book", "branch": "main", "commit": "a" * 40,
                        "files": [{"path": "src.xhtml", "size": 999, "sha256": "0" * 64}]}
            (target / "snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                fetch.fetch_one(ROW, Path(temp), delay=0)

    def test_cached_snapshot_accepts_nested_source_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "book"
            source = target / "src/EPUB/text/book.xhtml"
            source.parent.mkdir(parents=True)
            data = b"nested source"
            source.write_bytes(data)
            snapshot = {"repository": "example/book", "branch": "main", "commit": "a" * 40,
                        "files": [{"path": "src/EPUB/text/book.xhtml", "size": len(data),
                                   "sha256": hashlib.sha256(data).hexdigest()}]}
            (target / "snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
            result = fetch.validate_cached_snapshot(target, snapshot, "example", "book", "main")
            self.assertIsNone(result)

    def test_cached_snapshot_rejects_symlink_file(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "book"
            target.mkdir()
            (target / "real").write_bytes(b"ok")
            (target / "link").symlink_to(target / "real")
            snapshot = {"repository": "example/book", "branch": "main", "commit": "a" * 40,
                        "files": [{"path": "real", "size": 2, "sha256": hashlib.sha256(b"ok").hexdigest()}]}
            (target / "snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                fetch.fetch_one(ROW, Path(temp), delay=0)


if __name__ == "__main__":
    unittest.main()
