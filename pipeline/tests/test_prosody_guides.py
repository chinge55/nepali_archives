import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

PIPELINE = Path(__file__).resolve().parents[1]
ROOT = PIPELINE.parent
sys.path.insert(0, str(PIPELINE))

from prosody import FREE_VERSE, load_metres, published_metres, published_prosody
from sitegen.prosody_guides import load_guides, metre_guide


class ProsodyGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metres = {**load_metres(), FREE_VERSE["id"]: FREE_VERSE}
        cls.guides = load_guides(ROOT, cls.metres)

    def example_catalogue(self, identifier):
        example = self.guides[identifier]["example"]
        work = {"path": example["work"]}
        directory = ROOT / work["path"]
        meta = json.loads((directory / "metadata.json").read_text())
        text = (directory / "text.txt").read_text()
        annotation = published_prosody(meta, text)
        targets = [{**passage, "url": "authors/example/1/#chhanda-" + passage["id"]}
                   for passage in annotation.get("passages", [])]
        return SimpleNamespace(records=[(work, meta, text)], extras={work["path"]: {
            "prosody": annotation, "prosody_targets": targets}})

    def test_every_catalogue_entry_and_free_verse_has_a_guide(self):
        self.assertEqual(set(self.guides), set(self.metres))
        for identifier, guide in self.guides.items():
            with self.subTest(identifier=identifier):
                self.assertGreaterEqual(len(guide["reading"]), 2)
                self.assertTrue(guide["description"])
                self.assertTrue(guide["structure"])

    def test_examples_preserve_reviewed_source_text_and_scope(self):
        for identifier, guide in self.guides.items():
            with self.subTest(identifier=identifier):
                catalogue = self.example_catalogue(identifier)
                work, _, text = catalogue.records[0]
                annotation = catalogue.extras[work["path"]]["prosody"]
                excerpt = "\n".join(guide["example"]["lines"])
                self.assertIn(excerpt, text)
                self.assertIn(identifier, published_metres(annotation))
                rendered = metre_guide(identifier, self.metres[identifier], guide, catalogue)
                self.assertIn('<details class="metre-guide" id="chhanda-parichaya">', rendered)
                self.assertIn('<blockquote>', rendered)
                self.assertNotIn('<script', rendered)
                if annotation["kind"] == "mixed":
                    self.assertIn('#chhanda-', rendered)

    def test_changed_example_or_classification_is_rejected(self):
        catalogue = self.example_catalogue("shardul")
        guide = copy.deepcopy(self.guides["shardul"])
        guide["example"]["lines"] = ["यो स्रोतमा नभएको पाउ हो"]
        with self.assertRaisesRegex(ValueError, "differs from source"):
            metre_guide("shardul", self.metres["shardul"], guide, catalogue)
        catalogue.extras[catalogue.records[0][0]["path"]]["prosody"] = None
        with self.assertRaisesRegex(ValueError, "no longer reviewed"):
            metre_guide("shardul", self.metres["shardul"], self.guides["shardul"], catalogue)

    def test_example_cannot_borrow_another_metre_passage_in_a_mixed_work(self):
        catalogue = self.example_catalogue("shardul")
        for target in catalogue.extras[catalogue.records[0][0]["path"]]["prosody_targets"]:
            if target["metre"] == "shardul":
                target["start"] = target["end"]
        with self.assertRaisesRegex(ValueError, "outside the reviewed passage"):
            metre_guide("shardul", self.metres["shardul"], self.guides["shardul"], catalogue)

    def test_small_catalogue_still_gets_a_guide_without_an_absent_example(self):
        rendered = metre_guide("malini", self.metres["malini"], self.guides["malini"],
                               SimpleNamespace(records=[], extras={}))
        self.assertIn("कसरी पढ्ने?", rendered)
        self.assertNotIn("<blockquote>", rendered)
        self.assertIn("../../kavita-lekhan/?metre=malini", rendered)

    def test_free_verse_and_unsupported_writer_metres_do_not_get_fixed_templates(self):
        for identifier in ["muktachhanda", "viyogini", "giti", "aupachchhandasika", "jhyaure"]:
            rendered = metre_guide(identifier, self.metres[identifier], self.guides[identifier],
                                   self.example_catalogue(identifier))
            self.assertNotIn('class="metre-pattern"', rendered)
            self.assertNotIn("kavita-lekhan/?metre=", rendered)

    def test_guide_copy_is_escaped(self):
        guide = copy.deepcopy(self.guides["malini"])
        guide["description"] = '<script>alert("copy")</script>'
        rendered = metre_guide("malini", self.metres["malini"], guide,
                               SimpleNamespace(records=[], extras={}))
        self.assertIn("&lt;script&gt;", rendered)
        self.assertNotIn("<script>", rendered)
