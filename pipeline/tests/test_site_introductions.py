import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sitegen.model import collection_routes
from sitegen.config import GENRE, GENRE_ORDER
from sitegen.introductions import GENRE_INTROS, work_intro


class IntroductionTests(unittest.TestCase):
    def test_every_display_genre_has_an_introduction(self):
        self.assertEqual(set(GENRE), set(GENRE_INTROS))
        self.assertEqual(set(GENRE), set(GENRE_ORDER))
        self.assertEqual(GENRE['bhajan'][0], 'भजन')

    def test_fallback_uses_facts_without_publishing_source_notes(self):
        meta = {'author': {'name': 'लेखक'}, 'genre': ['kavita'],
                'description': 'Unreviewed OCR and source notes'}
        self.assertEqual(work_intro(meta), 'लेखकको कविता।')
        self.assertEqual(work_intro(meta, ['सङ्ग्रह एक', 'सङ्ग्रह दुई']),
                         'लेखकको कविता; ‘सङ्ग्रह एक’ र ‘सङ्ग्रह दुई’ सङ्ग्रहमा समावेश।')

    def test_reviewed_summary_takes_precedence(self):
        meta = {'author': {'name': 'लेखक'}, 'genre': ['kavita'],
                'summary': 'प्रकृतिसँग संवाद गर्ने कविता।'}
        self.assertEqual(work_intro(meta, ['सङ्ग्रह']), meta['summary'])


class CollectionRouteTests(unittest.TestCase):
    def test_numbered_collections_get_distinct_stable_routes(self):
        names = ['लालित्य भाग १', 'लालित्य भाग २', 'सुनको बिहान']
        routes, aliases = collection_routes(names)
        self.assertEqual(routes['लालित्य भाग १'], 'lalitya_bhag_1')
        self.assertEqual(routes['लालित्य भाग २'], 'lalitya_bhag_2')
        self.assertEqual(aliases['lalitya_bhag'], names[:2])
        self.assertEqual(len(set(routes.values())), len(names))
        self.assertEqual(collection_routes(reversed(names)), (routes, aliases))
        self.assertTrue(set(routes.values()).isdisjoint(aliases))
