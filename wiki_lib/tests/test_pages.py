import unittest
import os
import tempfile
from wiki_lib.pages import _page_file_path, _relative_link, _read_page_meta


class TestPageFilePath(unittest.TestCase):

    def test_topic_path(self):
        result = _page_file_path("test_topic", "topic")
        self.assertIn("topics", result)
        self.assertTrue(result.endswith(".md"))

    def test_entity_path(self):
        result = _page_file_path("test_entity", "entity")
        self.assertIn("entities", result)
        self.assertTrue(result.endswith(".md"))


class TestRelativeLink(unittest.TestCase):

    def test_same_kind_link(self):
        result = _relative_link("topic", "topic", "other_topic")
        self.assertEqual(result, "other_topic.md")

    def test_cross_kind_link(self):
        result = _relative_link("topic", "entity", "some_entity")
        self.assertEqual(result, "../entities/some_entity.md")

    def test_entity_to_topic_link(self):
        result = _relative_link("entity", "topic", "some_topic")
        self.assertEqual(result, "../topics/some_topic.md")


class TestReadPageMeta(unittest.TestCase):

    def test_extracts_h1_title(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# My Custom Title\n\n## Section\n\nContent")
            f.flush()
            title, subheadings = _read_page_meta(f.name, "fallback")
        os.unlink(f.name)
        self.assertEqual(title, "My Custom Title")
        self.assertIn("Section", subheadings)

    def test_uses_fallback_on_error(self):
        title, subheadings = _read_page_meta("/nonexistent/file.md", "fallback_name")
        self.assertEqual(title, "fallback_name")

    def test_extracts_subheadings(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Title\n\n## First\n\n## Second\n\n## Third\n\n## Fourth\n\n## Fifth")
            f.flush()
            _, subheadings = _read_page_meta(f.name, "fallback")
        os.unlink(f.name)
        self.assertLessEqual(len(subheadings), 4)


if __name__ == '__main__':
    unittest.main()
