import unittest
import os
import tempfile
from wiki_lib.backup import _make_backup_path, _atomic_write


class TestMakeBackupPath(unittest.TestCase):

    def test_returns_backup_root_with_timestamp(self):
        result = _make_backup_path("2024-01-15", "topics/test.md")
        self.assertIn("2024-01-15", result)
        self.assertIn("topics/test.md", result)


class TestAtomicWrite(unittest.TestCase):

    def test_atomic_write_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")
            _atomic_write(path, "test content")
            with open(path, "r") as f:
                self.assertEqual(f.read(), "test content")

    def test_atomic_write_overwrites(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")
            _atomic_write(path, "first")
            _atomic_write(path, "second")
            with open(path, "r") as f:
                self.assertEqual(f.read(), "second")

    def test_no_tmp_file_left_behind(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")
            _atomic_write(path, "content")
            tmp_files = [f for f in os.listdir(tmpdir) if f.endswith(".tmp")]
            self.assertEqual(tmp_files, [])


class TestBackupFile(unittest.TestCase):

    def test_creates_backup_at_expected_path(self):
        from wiki_lib.backup import _backup_file
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_root = os.path.join(tmpdir, "wiki")
            backup_root = os.path.join(tmpdir, "backups")
            topics_dir = os.path.join(wiki_root, "topics")
            os.makedirs(topics_dir)

            src = os.path.join(topics_dir, "test.md")
            with open(src, "w") as f:
                f.write("# Test\n\nContent")

            with patch("wiki_lib.backup.WIKI_ROOT", wiki_root), \
                 patch("wiki_lib.backup.config", {"directories": {"backups": backup_root}}):
                dst = _backup_file(src, "2024-01-15_12-00-00")

            self.assertTrue(os.path.exists(dst))
            content = open(dst, encoding="utf-8").read()
            self.assertIn("# Test", content)

    def test_backup_preserves_content(self):
        from wiki_lib.backup import _backup_file
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_root = os.path.join(tmpdir, "wiki")
            backup_root = os.path.join(tmpdir, "backups")
            topics_dir = os.path.join(wiki_root, "topics")
            os.makedirs(topics_dir)

            original_text = "# Title\n\nOriginal content\n"
            src = os.path.join(topics_dir, "page.md")
            with open(src, "w", encoding="utf-8") as f:
                f.write(original_text)

            with patch("wiki_lib.backup.WIKI_ROOT", wiki_root), \
                 patch("wiki_lib.backup.config", {"directories": {"backups": backup_root}}):
                dst = _backup_file(src, "2024-01-15")

            self.assertEqual(open(dst, encoding="utf-8").read(), original_text)


if __name__ == '__main__':
    unittest.main()
