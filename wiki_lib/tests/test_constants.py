import unittest
from wiki_lib import constants


class TestConstants(unittest.TestCase):

    def test_image_mime_map(self):
        self.assertEqual(constants.IMAGE_MIME_MAP["jpg"], "image/jpeg")
        self.assertEqual(constants.IMAGE_MIME_MAP["png"], "image/png")
        self.assertEqual(constants.IMAGE_MIME_MAP["webp"], "image/webp")

    def test_entity_types(self):
        self.assertIn("tool", constants.ENTITY_TYPES)
        self.assertIn("model", constants.ENTITY_TYPES)
        self.assertIn("concept", constants.ENTITY_TYPES)
        self.assertIn("project", constants.ENTITY_TYPES)
        self.assertIn("person", constants.ENTITY_TYPES)

    def test_max_entities_per_note(self):
        self.assertEqual(constants.MAX_ENTITIES_PER_NOTE, 10)

    def test_fuzzy_cutoffs(self):
        self.assertEqual(constants.ENTITY_FUZZY_CUTOFF, 0.85)
        self.assertEqual(constants.TOPIC_FUZZY_CUTOFF, 0.75)

    def test_description_max_chars(self):
        self.assertEqual(constants.DESCRIPTION_MAX_CHARS, 500)

    def test_reserved_wiki_files(self):
        self.assertIn("index.md", constants.RESERVED_WIKI_FILES)
        self.assertIn("log.md", constants.RESERVED_WIKI_FILES)

    def test_mentions_heading(self):
        self.assertEqual(constants.MENTIONS_HEADING, "## Erwähnt in")

    def test_secondary_mentions_heading(self):
        self.assertEqual(constants.SECONDARY_MENTIONS_HEADING, "## Erwähnungen")


if __name__ == '__main__':
    unittest.main()
