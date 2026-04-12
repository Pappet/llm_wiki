import unittest
from wiki_lib.logbook import _log_entry


class TestLogEntry(unittest.TestCase):

    def test_log_entry_format(self):
        entry = _log_entry("primary_update", "topics/test.md | 1 text")
        self.assertIn("## [", entry)
        self.assertIn("] primary_update | topics/test.md | 1 text", entry)

    def test_log_entry_has_timestamp(self):
        entry = _log_entry("test_action", "details")
        parts = entry.split("] ")
        self.assertEqual(len(parts), 2)


if __name__ == '__main__':
    unittest.main()
