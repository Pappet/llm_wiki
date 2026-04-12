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


class TestReadEntityMeta(unittest.TestCase):

    def test_reads_frontmatter_and_title(self):
        content = (
            "---\n"
            "type: tool\n"
            "name: PostgreSQL\n"
            "aliases: []\n"
            "first_seen: 2024-01-01\n"
            "last_updated: 2024-01-01\n"
            "mention_count: 3\n"
            "---\n"
            "# PostgreSQL\n\n"
            "*Relationales Open-Source-Datenbanksystem.*\n\n"
            "## Erwähnt in\n\n"
        )
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write(content)
            path = f.name
        from wiki_lib.pages import _read_entity_meta
        fm, title, description = _read_entity_meta(path, "fallback")
        os.unlink(path)
        self.assertEqual(title, "PostgreSQL")
        self.assertEqual(fm.get("type"), "tool")
        self.assertEqual(fm.get("mention_count"), 3)
        self.assertIn("Relationales", description)

    def test_fallback_name_on_missing_file(self):
        from wiki_lib.pages import _read_entity_meta
        fm, title, description = _read_entity_meta("/does/not/exist.md", "my_fallback")
        self.assertEqual(title, "my_fallback")
        self.assertEqual(fm, {})
        self.assertEqual(description, "")

    def test_no_description_line_returns_empty_string(self):
        content = (
            "---\n"
            "type: concept\n"
            "name: Embeddings\n"
            "aliases: []\n"
            "first_seen: 2024-01-01\n"
            "last_updated: 2024-01-01\n"
            "mention_count: 1\n"
            "---\n"
            "# Embeddings\n\n"
            "## Erwähnt in\n\n"
        )
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write(content)
            path = f.name
        from wiki_lib.pages import _read_entity_meta
        fm, title, description = _read_entity_meta(path, "fallback")
        os.unlink(path)
        self.assertEqual(description, "")


if __name__ == '__main__':
    unittest.main()
