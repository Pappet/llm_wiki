import unittest
import os
import tempfile
from unittest.mock import patch
from wiki_lib.logbook import _log_entry, append_log_entries


class TestLogEntry(unittest.TestCase):

    def test_log_entry_format(self):
        entry = _log_entry("primary_update", "topics/test.md | 1 text")
        self.assertIn("## [", entry)
        self.assertIn("] primary_update | topics/test.md | 1 text", entry)

    def test_log_entry_has_timestamp(self):
        entry = _log_entry("test_action", "details")
        parts = entry.split("] ")
        self.assertEqual(len(parts), 2)


class TestAppendLogEntries(unittest.TestCase):

    def test_creates_log_file_if_not_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("wiki_lib.logbook.WIKI_ROOT", tmpdir):
                append_log_entries([_log_entry("test_action", "details")])
            log_path = os.path.join(tmpdir, "log.md")
            self.assertTrue(os.path.exists(log_path))

    def test_writes_header_on_new_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("wiki_lib.logbook.WIKI_ROOT", tmpdir):
                append_log_entries([_log_entry("test_action", "details")])
            content = open(os.path.join(tmpdir, "log.md"), encoding="utf-8").read()
            self.assertIn("# Wiki Log", content)

    def test_appends_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("wiki_lib.logbook.WIKI_ROOT", tmpdir):
                append_log_entries([_log_entry("action_1", "first")])
                append_log_entries([_log_entry("action_2", "second")])
            content = open(os.path.join(tmpdir, "log.md"), encoding="utf-8").read()
            self.assertIn("action_1", content)
            self.assertIn("action_2", content)

    def test_empty_entries_does_nothing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("wiki_lib.logbook.WIKI_ROOT", tmpdir):
                append_log_entries([])
            log_path = os.path.join(tmpdir, "log.md")
            self.assertFalse(os.path.exists(log_path))


if __name__ == '__main__':
    unittest.main()
