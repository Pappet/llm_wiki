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


if __name__ == '__main__':
    unittest.main()
