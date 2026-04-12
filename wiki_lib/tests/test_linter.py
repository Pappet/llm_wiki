import unittest
from wiki_lib.linter import (
    Issue, _check_fence_parity, _lint_phase1, _lint_phase1_5,
    _fix_trailing_whitespace, _fix_unclosed_fence, _fix_excessive_blanks,
    _fix_missing_h1, _fix_multi_h1
)


class TestIssue(unittest.TestCase):

    def test_issue_dataclass(self):
        issue = Issue(
            path="topics/test.md",
            kind="missing_h1",
            severity="error",
            detail="No H1 found",
            fix_available=True
        )
        self.assertEqual(issue.path, "topics/test.md")
        self.assertEqual(issue.kind, "missing_h1")
        self.assertEqual(issue.severity, "error")


class TestCheckFenceParity(unittest.TestCase):

    def test_even_fence_count(self):
        content = "```\ncode\n```\n```\nmore code\n```"
        is_odd, count = _check_fence_parity(content)
        self.assertFalse(is_odd)
        self.assertEqual(count, 4)

    def test_odd_fence_count(self):
        content = "```\ncode\n```\n```\nunclosed"
        is_odd, count = _check_fence_parity(content)
        self.assertTrue(is_odd)
        self.assertEqual(count, 3)

    def test_no_fences(self):
        is_odd, count = _check_fence_parity("no fences here")
        self.assertFalse(is_odd)
        self.assertEqual(count, 0)


class TestLintPhase1(unittest.TestCase):

    def test_detects_unclosed_fence(self):
        content = "```\nunclosed code block"
        issues = _lint_phase1("test.md", content)
        kinds = [i.kind for i in issues]
        self.assertIn("unclosed_fence", kinds)

    def test_detects_trailing_whitespace(self):
        content = "line with space \nanother line"
        issues = _lint_phase1("test.md", content)
        kinds = [i.kind for i in issues]
        self.assertIn("trailing_whitespace", kinds)

    def test_no_issues_clean_content(self):
        content = "clean content\nno issues"
        issues = _lint_phase1("test.md", content)
        self.assertEqual(len(issues), 0)


class TestLintPhase1_5(unittest.TestCase):

    def test_detects_missing_h1(self):
        content = "## Only H2\n\ncontent"
        issues = _lint_phase1_5("test.md", content)
        kinds = [i.kind for i in issues]
        self.assertIn("missing_h1", kinds)

    def test_detects_multi_h1(self):
        content = "# First\n\n# Second"
        issues = _lint_phase1_5("test.md", content)
        kinds = [i.kind for i in issues]
        self.assertIn("multi_h1", kinds)

    def test_valid_single_h1(self):
        content = "# Only One H1\n\ncontent"
        issues = _lint_phase1_5("test.md", content)
        kinds = [i.kind for i in issues]
        self.assertNotIn("missing_h1", kinds)
        self.assertNotIn("multi_h1", kinds)


class TestFixTrailingWhitespace(unittest.TestCase):

    def test_removes_trailing_whitespace(self):
        content = "line with space \nanother line"
        result = _fix_trailing_whitespace(content)
        self.assertNotIn("space \n", result)
        self.assertIn("space\n", result)

    def test_preserves_no_trailing(self):
        content = "clean line\n"
        result = _fix_trailing_whitespace(content)
        self.assertEqual(result, content)


class TestFixUnclosedFence(unittest.TestCase):

    def test_adds_closing_fence(self):
        content = "```\nunclosed"
        result = _fix_unclosed_fence(content)
        self.assertTrue(result.rstrip().endswith("```"))

    def test_no_change_if_closed(self):
        content = "```\nclosed\n```"
        result = _fix_unclosed_fence(content)
        self.assertEqual(result, content)


class TestFixExcessiveBlanks(unittest.TestCase):

    def test_reduces_four_newlines_to_three(self):
        content = "para1\n\n\n\npara2"
        result = _fix_excessive_blanks(content)
        self.assertNotIn("\n{4,}", result)

    def test_preserves_double_newline(self):
        content = "para1\n\npara2"
        result = _fix_excessive_blanks(content)
        self.assertEqual(result, content)


class TestFixMissingH1(unittest.TestCase):

    def test_adds_h1_from_filename(self):
        content = "## Section\n\nContent"
        result = _fix_missing_h1(content, "/path/to/my_topic.md")
        self.assertIn("# My Topic", result)

    def test_no_change_if_h1_exists(self):
        content = "---\nkey: value\n---\n\n# Already Has H1\n\n## Section\n\nContent"
        result = _fix_missing_h1(content, "/path/to/my_topic.md")
        self.assertNotIn("# My Topic", result)


class TestFixMultiH1(unittest.TestCase):

    def test_converts_extra_h1_to_h2(self):
        content = "# First H1\n\n# Second H1\n\n## Section"
        result = _fix_multi_h1(content)
        self.assertIn("## Second H1", result)


if __name__ == '__main__':
    unittest.main()
