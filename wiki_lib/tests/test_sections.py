import unittest
from wiki_lib.sections import (
    _slugify_heading, parse_sections, reassemble_page, _make_section,
    _body_without_frontmatter, _split_fm_body
)


class TestSlugifyHeading(unittest.TestCase):

    def test_basic_slugify(self):
        self.assertEqual(_slugify_heading("## Hello World"), "hello_world")

    def test_preserves_underscores(self):
        self.assertEqual(_slugify_heading("## hello_world"), "hello_world")

    def test_strips_hash_prefix(self):
        self.assertEqual(_slugify_heading("### Hello"), "hello")

    def test_replaces_spaces_with_underscores(self):
        self.assertEqual(_slugify_heading("## Hello World Test"), "hello_world_test")

    def test_removes_special_chars(self):
        self.assertEqual(_slugify_heading("## Hello, World!"), "hello_world")

    def test_empty_returns_unnamed(self):
        self.assertEqual(_slugify_heading(""), "_unnamed")
        self.assertEqual(_slugify_heading("###"), "_unnamed")


class TestParseSections(unittest.TestCase):

    def test_empty_content(self):
        result = parse_sections("")
        self.assertEqual(result['preamble'], '')
        self.assertEqual(result['sections'], [])

    def test_no_sections(self):
        content = "# Title\n\nSome preamble text."
        result = parse_sections(content)
        self.assertIn("Title", result['preamble'])
        self.assertEqual(len(result['sections']), 0)

    def test_single_section(self):
        content = "# Title\n\n## Section One\n\nContent here."
        result = parse_sections(content)
        self.assertEqual(len(result['sections']), 1)
        self.assertEqual(result['sections'][0]['heading'].strip(), "## Section One")
        self.assertIn("Content here", result['sections'][0]['body'])

    def test_multiple_sections(self):
        content = "# Title\n\n## Section One\n\nContent one.\n\n## Section Two\n\nContent two."
        result = parse_sections(content)
        self.assertEqual(len(result['sections']), 2)

    def test_section_ignores_h3(self):
        content = "# Title\n\n## Section\n\n### SubSection\n\nContent"
        result = parse_sections(content)
        self.assertEqual(len(result['sections']), 1)

    def test_fence_ignored_for_h2(self):
        content = "# Title\n\n```\n## Not a real section\n```\n## Real Section\n\nContent"
        result = parse_sections(content)
        self.assertEqual(len(result['sections']), 1)


class TestReassemblePage(unittest.TestCase):

    def test_reassemble_basic(self):
        preamble = "# Title\n\n"
        sections = [
            {'original': "## Section\n\nContent\n\n"}
        ]
        result = reassemble_page(preamble, sections)
        self.assertIn("# Title", result)
        self.assertIn("## Section", result)


class TestMakeSection(unittest.TestCase):

    def test_make_section_adds_h2(self):
        section = _make_section("Introduction", "Some content.")
        self.assertTrue(section['heading'].startswith("## "))
        self.assertEqual(section['slug'], "introduction")

    def test_make_section_preserves_existing_h2(self):
        section = _make_section("## Introduction", "Some content.")
        self.assertEqual(section['heading'], "## Introduction")


class TestBodyWithoutFrontmatter(unittest.TestCase):

    def test_no_frontmatter(self):
        content = "# Title\n\nBody"
        result = _body_without_frontmatter(content)
        self.assertEqual(result, "# Title\n\nBody")

    def test_with_frontmatter(self):
        content = "---\nkey: value\n---\n# Title\n\nBody"
        result = _body_without_frontmatter(content)
        self.assertTrue(result.startswith("# Title"))


class TestSplitFmBody(unittest.TestCase):

    def test_no_frontmatter(self):
        content = "# Title\n\nBody"
        fm_prefix, body = _split_fm_body(content)
        self.assertEqual(fm_prefix, "")
        self.assertEqual(body, "# Title\n\nBody")

    def test_with_frontmatter(self):
        content = "---\nkey: value\n---\n\n# Title\n\nBody"
        fm_prefix, body = _split_fm_body(content)
        self.assertTrue(fm_prefix.startswith("---"))
        self.assertIn("# Title", body)


if __name__ == '__main__':
    unittest.main()
