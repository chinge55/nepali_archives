import json
import tempfile
import unittest
from pathlib import Path

from pipeline import sahityaras_catalogue as catalogue
from sahityaras_ingest import SourceError, digest, inventory
from pipeline.sahityaras_batch import add_collection, encoded


AUTHOR = {"id": "test_author", "name": "परीक्षण लेखक", "name_roman": "Test Author"}
RIGHTS = {"status": "public-domain", "basis": "Author died 1900; public domain."}


def xhtml(title, text, *, note=False):
    notes = ""
    marker = ""
    if note:
        marker = '<sup class="reference" id="cite_ref-1"><a href="#cite_note-1">[१]</a></sup>'
        notes = ('<ol class="references"><li id="cite_note-1">'
                 '<span class="mw-cite-backlink"><a href="#cite_ref-1">↩</a></span>'
                 '<span class="reference-text">लेखकको टिप्पणी</span></li></ol>')
    return (f'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>{title}</title></head>'
            f'<body><div class="chapter-title">{title}</div><p>{text}{marker}</p>{notes}</body></html>').encode()


def package(cache, book_id, documents):
    root = cache / book_id / "src"
    (root / "META-INF").mkdir(parents=True)
    (root / "META-INF/container.xml").write_text(
        '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container:v1.0">'
        '<rootfiles><rootfile full-path="EPUB/content.opf"/></rootfiles></container>', encoding="utf-8")
    manifest = []
    spine = []
    for index, (path, data) in enumerate(documents, 1):
        ident = f"doc{index}"
        manifest.append(f'<item id="{ident}" href="{path.removeprefix("EPUB/")}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="{ident}"/>')
        target = root / "EPUB" / path.removeprefix("EPUB/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (root / "EPUB/content.opf").write_text(
        '<package xmlns="urn:pkg"><manifest>' + ''.join(manifest) + '</manifest><spine>' +
        ''.join(spine) + '</spine></package>', encoding="utf-8")
    actual = inventory(root)
    return {
        "id": book_id,
        "package_sha256": actual["package_sha256"],
        "documents": [
            {"path": "src/" + d["path"], "sha256": d["sha256"], "spine_position": d["spine_position"],
             "decision": d["decision"], "reason": d["reason"], **d.get("extra", {})}
            for d in []
        ],
        "actual": actual,
    }


def book_record(cache, book_id, rows):
    docs = [(path, data) for path, data, *_ in rows]
    record = package(cache, book_id, docs)
    record["documents"] = []
    for actual, row in zip(record.pop("actual")["documents"], rows):
        _, _, decision, reason, extra = row
        record["documents"].append({"path": "src/" + actual["path"], "title": actual["title"], "sha256": actual["sha256"],
                                    "spine_position": actual["spine_position"], "decision": decision,
                                    "reason": reason, **extra})
    return record


def base_work(work_id, source, genre=("kavita",), **extra):
    return {"id": work_id, "title": "परीक्षण", "title_roman": None, "author": AUTHOR,
            "genre": list(genre), "rights": RIGHTS, "source_url": "https://sahityaras.com/book/test/",
            "prepared_date": "2026-09-08", "sources": [source], "reviewed": True, "decision": "include",
            "outputs": {}, **extra}


class CatalogueTests(unittest.TestCase):
    def test_full_ledger_include_map_exclude_and_prose_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root, cache = Path(temp) / "root", Path(temp) / "cache"
            root.mkdir(); cache.mkdir()
            a = xhtml("पहिलो", "मूल पाठ")
            b = xhtml("पहिलेको", "अघिल्लो पाठ")
            book = book_record(cache, "book", [("EPUB/text/a.xhtml", a, "include", "approved", {}),
                                                ("EPUB/text/b.xhtml", b, "map-existing", "duplicate", {}),
                                                ("EPUB/text/c.xhtml", b, "exclude", "editorial", {})])
            existing = root / "archives/authors/test_author/old_work"
            existing.mkdir(parents=True)
            old_text = "अघिल्लो पाठ\n".encode()
            old_meta = {"id": "old_work", "title": "पहिलेको", "author": AUTHOR,
                        "description": "From the collection पुरानो.", "rights": RIGHTS}
            (existing / "text.txt").write_bytes(old_text)
            (existing / "metadata.json").write_bytes(encoded(old_meta))
            source_a = {"book": "book", "path": "src/EPUB/text/a.xhtml"}
            source_b = {"book": "book", "path": "src/EPUB/text/b.xhtml"}
            include = base_work("new_work", source_a, genre=("nibandha", "prose"))
            include["outputs"] = {k: digest(v) for k, v in catalogue.included_files(include, {"book": book}, cache).items()}
            mapped = base_work("old_work", source_b, genre=("kavita",), decision="map-existing")
            mapped.update({"decision": "map-existing", "baseline_text_sha256": digest(old_text),
                           "baseline_metadata_sha256": digest((existing / "metadata.json").read_bytes()),
                           "collections": ["नयाँ"], "outputs": {}})
            mapped["outputs"] = {"metadata.json": digest(encoded(add_collection(old_meta, "नयाँ")))}
            manifest = {"schema_version": 2, "books": [book], "works": [include, mapped]}
            outputs = catalogue.plan(manifest, cache, root)
            self.assertIn("archives/authors/test_author/new_work/text.txt", outputs)
            metadata = json.loads(outputs["archives/authors/test_author/new_work/metadata.json"])
            self.assertEqual(metadata["genre"][0], "nibandha")
            self.assertEqual(catalogue.write(outputs, manifest, root, apply=True), len(outputs))
            self.assertEqual(catalogue.write(outputs, manifest, root, apply=True), 0)

    def test_hash_drift_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root, cache = Path(temp) / "root", Path(temp) / "cache"
            root.mkdir(); cache.mkdir()
            data = xhtml("标题", "文本")
            book = book_record(cache, "book", [("EPUB/text/a.xhtml", data, "include", "approved", {})])
            source = {"book": "book", "path": "src/EPUB/text/a.xhtml"}
            work = base_work("work", source)
            work["outputs"] = {k: digest(v) for k, v in catalogue.included_files(work, {"book": book}, cache).items()}
            manifest = {"schema_version": 2, "books": [book], "works": [work]}
            (cache / "book/src/EPUB/text/a.xhtml").write_bytes(b"changed")
            with self.assertRaises(SourceError):
                catalogue.plan(manifest, cache, root)

    def test_map_existing_never_overwrites_changed_text(self):
        with tempfile.TemporaryDirectory() as temp:
            root, cache = Path(temp) / "root", Path(temp) / "cache"
            root.mkdir(); cache.mkdir()
            data = xhtml("पुरानो", "नयाँ स्रोत")
            book = book_record(cache, "book", [("EPUB/text/a.xhtml", data, "map-existing", "duplicate", {})])
            folder = root / "archives/authors/test_author/old"
            folder.mkdir(parents=True)
            (folder / "text.txt").write_text("स्थानीय फरक पाठ\n", encoding="utf-8")
            (folder / "metadata.json").write_text(json.dumps({"author": AUTHOR}), encoding="utf-8")
            work = base_work("old", {"book": "book", "path": "src/EPUB/text/a.xhtml"}, decision="map-existing")
            work.update({"baseline_text_sha256": digest("मूल पाठ\n".encode()), "baseline_metadata_sha256": digest((folder / "metadata.json").read_bytes()), "collections": ["सङ्ग्रह"], "outputs": {}})
            manifest = {"schema_version": 2, "books": [book], "works": [work]}
            with self.assertRaises(SourceError):
                catalogue.plan(manifest, cache, root)

    def test_write_preflights_all_outputs_and_refuses_changed_existing_text(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "root"; root.mkdir()
            outputs = {"archives/authors/a/work/text.txt": b"new", "archives/authors/a/work/metadata.json": b"meta"}
            manifest = {"works": [{"decision": "include", "author": {"id": "a"}, "id": "work"}]}
            existing = root / "archives/authors/a/work/text.txt"
            existing.parent.mkdir(parents=True); existing.write_bytes(b"different")
            with self.assertRaises(SourceError):
                catalogue.write(outputs, manifest, root, apply=False)
            self.assertFalse((existing.parent / "metadata.json").exists())

    def test_multisection_capture_scopes_ids_and_keeps_note_text(self):
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp) / "cache"; cache.mkdir()
            a, b = xhtml("एक", "पाठ एक", note=True), xhtml("दुई", "पाठ दुई", note=True)
            book = book_record(cache, "book", [("EPUB/text/a.xhtml", a, "include", "approved", {"notes_approved": True}),
                                                ("EPUB/text/b.xhtml", b, "include", "approved", {"notes_approved": True})])
            work = base_work("work", {"book": "book", "path": "src/EPUB/text/a.xhtml"})
            work["sources"] = [{"book": "book", "path": "src/EPUB/text/a.xhtml"}, {"book": "book", "path": "src/EPUB/text/b.xhtml"}]
            work["outputs"] = {k: digest(v) for k, v in catalogue.included_files(work, {"book": book}, cache).items()}
            files = catalogue.included_files(work, {"book": book}, cache)
            capture = files["extracted/index.html"].decode()
            self.assertIn("section-1-cite_note-1", capture)
            self.assertIn("section-2-cite_note-1", capture)
            self.assertIn('href="#section-1-cite_ref-1"', capture)
            self.assertIn('href="#section-2-cite_ref-1"', capture)
            self.assertIn("लेखकको टिप्पणी", files["text.txt"].decode())


if __name__ == "__main__":
    unittest.main()
