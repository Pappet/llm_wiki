import unittest
from wiki_lib.cli import _group_issues_by_path, _kind_from_rel


class TestCliHelpers(unittest.TestCase):

    def test_group_issues_by_path(self):
        from wiki_lib.linter import Issue
        issues = [
            Issue("topics/a.md", "missing_h1", "error", "", True),
            Issue("topics/a.md", "trailing_ws", "warning", "", True),
            Issue("topics/b.md", "missing_h1", "error", "", True),
        ]
        grouped = _group_issues_by_path(issues)
        self.assertEqual(len(grouped["topics/a.md"]), 2)
        self.assertEqual(len(grouped["topics/b.md"]), 1)

    def test_kind_from_rel_topic(self):
        result = _kind_from_rel("topics/test.md")
        self.assertEqual(result, "topic")

    def test_kind_from_rel_entity(self):
        result = _kind_from_rel("entities/test.md")
        self.assertEqual(result, "entity")


if __name__ == '__main__':
    unittest.main()
