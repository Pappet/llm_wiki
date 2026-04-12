import unittest
from wiki_lib.updates import _build_entity_link_hints


class TestBuildEntityLinkHints(unittest.TestCase):

    def test_empty_entity_refs(self):
        result = _build_entity_link_hints([], "test_topic")
        self.assertEqual(result, "")

    def test_builds_hint_lines(self):
        entity_refs = [
            {"name": "PostgreSQL", "slug": "postgresql", "role": "mentioned"}
        ]
        result = _build_entity_link_hints(entity_refs, "test_topic")
        self.assertIn("PostgreSQL", result)
        self.assertIn("../entities/postgresql.md", result)


if __name__ == '__main__':
    unittest.main()
