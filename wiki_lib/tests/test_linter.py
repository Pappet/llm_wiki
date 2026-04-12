import unittest
from wiki_lib.linter import (
    Issue, _check_fence_parity, _lint_phase1, _lint_phase1_5,
    _lint_phase2, _fix_duplicate_sections, _fix_empty_mentions,
    _fix_frontmatter_drift, fix_page,
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
        self.assertIn("# Already Has H1", result)
        h1_count = sum(1 for line in result.split('\n') if line.startswith('# ') and not line.startswith('## '))
        self.assertEqual(h1_count, 1)


class TestFixMultiH1(unittest.TestCase):

    def test_converts_extra_h1_to_h2(self):
        content = "# First H1\n\n# Second H1\n\n## Section"
        result = _fix_multi_h1(content)
        self.assertIn("## Second H1", result)


class TestLintPhase2(unittest.TestCase):

    def test_detects_excessive_blank_lines(self):
        content = "# Title\n\n## Section\n\nPara1\n\n\n\nPara2"
        issues = _lint_phase2("test.md", content, "topic")
        kinds = [i.kind for i in issues]
        self.assertIn("excessive_blank_lines", kinds)

    def test_no_excessive_blank_lines_with_two(self):
        content = "# Title\n\n## Section\n\nPara1\n\nPara2"
        issues = _lint_phase2("test.md", content, "topic")
        kinds = [i.kind for i in issues]
        self.assertNotIn("excessive_blank_lines", kinds)

    def test_detects_duplicate_sections(self):
        content = "# Title\n\n## Installation\n\nText\n\n## Installation\n\nDuplikat"
        issues = _lint_phase2("test.md", content, "topic")
        kinds = [i.kind for i in issues]
        self.assertIn("duplicate_section", kinds)

    def test_no_duplicate_sections_when_unique(self):
        content = "# Title\n\n## Installation\n\nText\n\n## Usage\n\nAnders"
        issues = _lint_phase2("test.md", content, "topic")
        kinds = [i.kind for i in issues]
        self.assertNotIn("duplicate_section", kinds)

    def test_detects_empty_mentions_erwaehnt_in(self):
        content = "# Title\n\n## Erwähnt in\n\n"
        issues = _lint_phase2("test.md", content, "entity")
        kinds = [i.kind for i in issues]
        self.assertIn("empty_mentions", kinds)

    def test_detects_empty_mentions_erwaehungen(self):
        content = "# Title\n\n## Erwähnungen\n\n"
        issues = _lint_phase2("test.md", content, "topic")
        kinds = [i.kind for i in issues]
        self.assertIn("empty_mentions", kinds)

    def test_no_empty_mentions_when_content_present(self):
        content = "# Title\n\n## Erwähnt in\n\n- [2024-01-01] mentioned in [foo](../topics/foo.md)\n\n"
        issues = _lint_phase2("test.md", content, "entity")
        kinds = [i.kind for i in issues]
        self.assertNotIn("empty_mentions", kinds)

    def test_detects_frontmatter_drift(self):
        content = (
            "---\ntype: tool\nname: Test\naliases: []\n"
            "first_seen: 2024-01-01\nlast_updated: 2024-01-01\nmention_count: 5\n---\n"
            "# Test\n\n## Erwähnt in\n\n"
            "- [2024-01-01] mentioned in [foo](../topics/foo.md)\n\n"
        )
        issues = _lint_phase2("entities/test.md", content, "entity")
        kinds = [i.kind for i in issues]
        self.assertIn("frontmatter_drift", kinds)

    def test_no_frontmatter_drift_when_correct(self):
        content = (
            "---\ntype: tool\nname: Test\naliases: []\n"
            "first_seen: 2024-01-01\nlast_updated: 2024-01-01\nmention_count: 1\n---\n"
            "# Test\n\n## Erwähnt in\n\n"
            "- [2024-01-01] mentioned in [foo](../topics/foo.md)\n\n"
        )
        issues = _lint_phase2("entities/test.md", content, "entity")
        kinds = [i.kind for i in issues]
        self.assertNotIn("frontmatter_drift", kinds)


class TestFixDuplicateSections(unittest.TestCase):

    def test_merges_duplicate_h2(self):
        content = (
            "# Title\n\n"
            "## Installation\n\nErster Block\n\n"
            "## Usage\n\nAnderes Thema\n\n"
            "## Installation\n\nZweiter Block\n\n"
        )
        result = _fix_duplicate_sections(content)
        self.assertEqual(result.count("## Installation"), 1)
        self.assertIn("Erster Block", result)
        self.assertIn("Zweiter Block", result)
        self.assertIn("## Usage", result)

    def test_idempotent_no_duplicates(self):
        content = "# Title\n\n## Installation\n\nText\n\n## Usage\n\nAnders\n\n"
        result = _fix_duplicate_sections(content)
        self.assertEqual(result, content)


class TestFixEmptyMentions(unittest.TestCase):

    def test_removes_empty_erwaehnt_in(self):
        content = "# Title\n\n## Erwähnt in\n\n"
        result = _fix_empty_mentions(content)
        self.assertNotIn("## Erwähnt in", result)

    def test_removes_empty_erwaehungen(self):
        content = "# Title\n\n## Erwähnungen\n\n"
        result = _fix_empty_mentions(content)
        self.assertNotIn("## Erwähnungen", result)

    def test_keeps_non_empty_mentions(self):
        content = "# Title\n\n## Erwähnt in\n\n- [2024-01-01] mentioned in [foo](../topics/foo.md)\n\n"
        result = _fix_empty_mentions(content)
        self.assertIn("## Erwähnt in", result)

    def test_idempotent_no_empty_sections(self):
        content = "# Title\n\n## Usage\n\nContent\n\n"
        result = _fix_empty_mentions(content)
        self.assertEqual(result, content)


class TestFixFrontmatterDrift(unittest.TestCase):

    def test_corrects_mention_count_too_high(self):
        content = (
            "---\ntype: tool\nname: Test\naliases: []\n"
            "first_seen: 2024-01-01\nlast_updated: 2024-01-01\nmention_count: 5\n---\n"
            "# Test\n\n## Erwähnt in\n\n"
            "- [2024-01-01] mentioned in [foo](../topics/foo.md)\n\n"
        )
        result = _fix_frontmatter_drift(content)
        from wiki_lib.frontmatter import parse_frontmatter
        fm, _ = parse_frontmatter(result)
        self.assertEqual(fm["mention_count"], 1)

    def test_corrects_mention_count_zero(self):
        content = (
            "---\ntype: tool\nname: Test\naliases: []\n"
            "first_seen: 2024-01-01\nlast_updated: 2024-01-01\nmention_count: 0\n---\n"
            "# Test\n\n## Erwähnt in\n\n"
            "- [2024-01-01] mentioned in [a](../topics/a.md)\n"
            "- [2024-01-02] mentioned in [b](../topics/b.md)\n\n"
        )
        result = _fix_frontmatter_drift(content)
        from wiki_lib.frontmatter import parse_frontmatter
        fm, _ = parse_frontmatter(result)
        self.assertEqual(fm["mention_count"], 2)

    def test_no_frontmatter_returns_unchanged(self):
        content = "# Title\n\nNo frontmatter here."
        result = _fix_frontmatter_drift(content)
        self.assertEqual(result, content)


class TestFixPageOrchestrator(unittest.TestCase):

    def _write_tmp(self, tmpdir, name, content):
        import os
        path = os.path.join(tmpdir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_applies_trailing_whitespace_fix(self):
        import tempfile
        from wiki_lib.linter import fix_page, Issue
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_tmp(tmpdir, "test.md", "# Title \n\nContent \n")
            issues = [Issue(path, "trailing_whitespace", "warning", "", True)]
            new_content, applied = fix_page(path, "topic", issues)
        self.assertIn("trailing_whitespace", applied)
        self.assertNotIn(" \n", new_content)

    def test_applies_multiple_fixes_in_order(self):
        import tempfile
        from wiki_lib.linter import fix_page, Issue
        content = "# Title \n\n# Second H1\n\nContent\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_tmp(tmpdir, "test.md", content)
            issues = [
                Issue(path, "trailing_whitespace", "warning", "", True),
                Issue(path, "multi_h1", "error", "", True),
            ]
            new_content, applied = fix_page(path, "topic", issues)
        self.assertIn("trailing_whitespace", applied)
        self.assertIn("multi_h1", applied)
        h1_count = sum(1 for line in new_content.split('\n') if line.startswith('# ') and not line.startswith('## '))
        self.assertEqual(h1_count, 1)
        self.assertNotIn(" # Second H1", new_content)

    def test_returns_none_on_missing_file(self):
        from wiki_lib.linter import fix_page, Issue
        issues = [Issue("/does/not/exist.md", "missing_h1", "error", "", True)]
        new_content, applied = fix_page("/does/not/exist.md", "topic", issues)
        self.assertIsNone(new_content)
        self.assertTrue(applied[0].startswith("LESEFEHLER"))


if __name__ == '__main__':
    unittest.main()
