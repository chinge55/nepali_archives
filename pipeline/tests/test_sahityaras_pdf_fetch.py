"""Pinned PDF downloads preserve the cache when upstream content changes."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pipeline import sahityaras_pdf_fetch as fetch


class PdfFetchTests(unittest.TestCase):
    def test_valid_pinned_cache_needs_no_network(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = b'%PDF-1.7 reviewed source'
            (root / 'book.pdf').write_bytes(data)
            book = {'id': 'book', 'sha256': hashlib.sha256(data).hexdigest()}
            with patch.object(fetch, '_fetch', side_effect=AssertionError('network used')):
                row = fetch.fetch_book(book, root, timeout=1, force=False)
            self.assertEqual(row['status'], 'cached')

    def test_upstream_hash_drift_preserves_previous_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = b'%PDF-1.7 previous source'
            path = root / 'book.pdf'
            path.write_bytes(old)
            book = {'id': 'book', 'sha256': 'a' * 64}
            with patch.object(fetch, '_fetch', return_value=(200, 'application/pdf', b'%PDF-1.7 changed')):
                row = fetch.fetch_book(book, root, timeout=1, force=False)
            self.assertEqual(row['status'], 'hash-mismatch')
            self.assertEqual(path.read_bytes(), old)

    def test_manifest_identifiers_cannot_escape_output(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'manifest.json'
            path.write_text(json.dumps({'books': [{'id': '../outside'}]}))
            with self.assertRaises(ValueError):
                fetch._books(path)


if __name__ == '__main__':
    unittest.main()
