import unittest
import os
import tempfile
from unittest.mock import patch
from wiki_lib.entities import _format_backlink_line, _ensure_entity_page, _append_entity_backlink


class TestFormatBacklinkLine(unittest.TestCase):

    def test_basic_format(self):
        backlink = {
            "from_slug": "test_topic",
            "from_title": "Test Topic",
            "role": "mentioned",
            "context": ""
        }
        result = _format_backlink_line("2024-01-15", backlink)
        self.assertIn("test_topic", result)
        self.assertIn("Test Topic", result)
        self.assertIn("mentioned", result)
        self.assertIn("2024-01-15", result)

    def test_with_context(self):
        backlink = {
            "from_slug": "test_topic",
            "from_title": "Test Topic",
            "role": "benchmarked",
            "context": "used for testing"
        }
        result = _format_backlink_line("2024-01-15", backlink)
        self.assertIn("used for testing", result)
        self.assertIn("benchmarked", result)


class TestEnsureEntityPage(unittest.TestCase):

    def _make_entity(self):
        return {
            "slug": "postgresql",
            "name": "PostgreSQL",
            "type": "tool",
            "description": "Relationales Open-Source-Datenbanksystem.",
            "is_new": True,
        }

    def _make_backlink(self):
        return {
            "from_slug": "rag",
            "from_title": "RAG",
            "role": "mentioned",
            "context": "Verwendet als Vektordatenbank.",
        }

    def test_creates_entity_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = os.path.join(tmpdir, "postgresql.md")
            with patch("wiki_lib.entities._page_file_path", return_value=fake_path):
                result = _ensure_entity_page(self._make_entity(), self._make_backlink())
            self.assertTrue(result)
            self.assertTrue(os.path.exists(fake_path))

    def test_entity_file_contains_name_and_description(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = os.path.join(tmpdir, "postgresql.md")
            with patch("wiki_lib.entities._page_file_path", return_value=fake_path):
                _ensure_entity_page(self._make_entity(), self._make_backlink())
            content = open(fake_path, encoding="utf-8").read()
            self.assertIn("# PostgreSQL", content)
            self.assertIn("Relationales Open-Source-Datenbanksystem", content)

    def test_entity_file_contains_backlink(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = os.path.join(tmpdir, "postgresql.md")
            with patch("wiki_lib.entities._page_file_path", return_value=fake_path):
                _ensure_entity_page(self._make_entity(), self._make_backlink())
            content = open(fake_path, encoding="utf-8").read()
            self.assertIn("rag", content)
            self.assertIn("Vektordatenbank", content)

    def test_entity_file_contains_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = os.path.join(tmpdir, "postgresql.md")
            with patch("wiki_lib.entities._page_file_path", return_value=fake_path):
                _ensure_entity_page(self._make_entity(), self._make_backlink())
            content = open(fake_path, encoding="utf-8").read()
            self.assertTrue(content.startswith("---"))
            self.assertIn("type: tool", content)
            self.assertIn("mention_count: 1", content)

    def test_returns_false_if_file_already_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = os.path.join(tmpdir, "postgresql.md")
            with open(fake_path, "w") as f:
                f.write("# Existing\n")
            with patch("wiki_lib.entities._page_file_path", return_value=fake_path):
                result = _ensure_entity_page(self._make_entity(), self._make_backlink())
            self.assertFalse(result)


class TestAppendEntityBacklink(unittest.TestCase):

    def _create_entity_file(self, tmpdir):
        content = (
            "---\n"
            "type: tool\n"
            "name: PostgreSQL\n"
            "aliases: []\n"
            "first_seen: 2024-01-01\n"
            "last_updated: 2024-01-01\n"
            "mention_count: 1\n"
            "---\n"
            "# PostgreSQL\n\n"
            "*Ein Datenbanksystem.*\n\n"
            "## Erwähnt in\n\n"
            "- [2024-01-01] mentioned in [rag](../topics/rag.md)\n\n"
        )
        path = os.path.join(tmpdir, "postgresql.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_appends_new_backlink(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = self._create_entity_file(tmpdir)
            backlink = {
                "from_slug": "machine_learning",
                "from_title": "Machine Learning",
                "role": "mentioned",
                "context": "Als Feature-Store verwendet.",
            }
            with patch("wiki_lib.entities._page_file_path", return_value=fake_path):
                result = _append_entity_backlink("postgresql", backlink)
            self.assertTrue(result)
            content = open(fake_path, encoding="utf-8").read()
            self.assertIn("machine_learning", content)
            self.assertIn("Feature-Store", content)

    def test_increments_mention_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = self._create_entity_file(tmpdir)
            backlink = {
                "from_slug": "nlp",
                "from_title": "NLP",
                "role": "mentioned",
                "context": "Kontext.",
            }
            with patch("wiki_lib.entities._page_file_path", return_value=fake_path):
                _append_entity_backlink("postgresql", backlink)
            from wiki_lib.frontmatter import parse_frontmatter
            content = open(fake_path, encoding="utf-8").read()
            fm, _ = parse_frontmatter(content)
            self.assertEqual(fm["mention_count"], 2)

    def test_preserves_existing_backlinks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = self._create_entity_file(tmpdir)
            backlink = {"from_slug": "nlp", "from_title": "NLP", "role": "mentioned", "context": ""}
            with patch("wiki_lib.entities._page_file_path", return_value=fake_path):
                _append_entity_backlink("postgresql", backlink)
            content = open(fake_path, encoding="utf-8").read()
            self.assertIn("rag", content)

    def test_returns_false_if_file_missing(self):
        with patch("wiki_lib.entities._page_file_path", return_value="/does/not/exist.md"):
            result = _append_entity_backlink("nonexistent", {})
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
