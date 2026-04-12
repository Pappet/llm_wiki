import unittest
from wiki_lib.entities import _format_backlink_line


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


if __name__ == '__main__':
    unittest.main()
