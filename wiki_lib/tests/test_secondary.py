import unittest
import os
import tempfile
from unittest.mock import patch
from wiki_lib.secondary import update_secondary_page_deterministic


class TestSecondaryUpdate(unittest.TestCase):

    def test_empty_references_does_not_create_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = os.path.join(tmpdir, "new_topic.md")
            with patch("wiki_lib.secondary._page_file_path", return_value=fake_path):
                update_secondary_page_deterministic("new_topic", [], [])
            self.assertFalse(os.path.exists(fake_path))

    def test_creates_stub_file_with_references(self):
        refs = [
            {"from_page": "machine_learning", "context": "Erwähnt im Kontext von Embeddings"}
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = os.path.join(tmpdir, "rag.md")
            with patch("wiki_lib.secondary._page_file_path", return_value=fake_path):
                update_secondary_page_deterministic("rag", refs, [])
            self.assertTrue(os.path.exists(fake_path))
            content = open(fake_path, encoding="utf-8").read()
            self.assertIn("machine_learning", content)
            self.assertIn("Embeddings", content)
            self.assertIn("## Erwähnungen", content)

    def test_appends_to_existing_file(self):
        existing_content = "# Rag\n\n## Erwähnungen\n\n- [2024-01-01] Im Kontext von [foo](foo.md): Alt\n\n"
        refs = [{"from_page": "bar", "context": "Neu hinzugefügt"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = os.path.join(tmpdir, "rag.md")
            with open(fake_path, "w", encoding="utf-8") as f:
                f.write(existing_content)
            with patch("wiki_lib.secondary._page_file_path", return_value=fake_path):
                update_secondary_page_deterministic("rag", refs, [])
            content = open(fake_path, encoding="utf-8").read()
            self.assertIn("Alt", content)
            self.assertIn("Neu hinzugefügt", content)


if __name__ == '__main__':
    unittest.main()
