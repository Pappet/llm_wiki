import unittest
from wiki_lib.frontmatter import parse_frontmatter, serialize_frontmatter


class TestParseFrontmatter(unittest.TestCase):

    def test_no_frontmatter(self):
        content = "# Hello\n\nWorld"
        fm, body = parse_frontmatter(content)
        self.assertEqual(fm, {})
        self.assertEqual(body, "# Hello\n\nWorld")

    def test_empty_frontmatter(self):
        content = "---\n---\n# Hello"
        fm, body = parse_frontmatter(content)
        self.assertEqual(fm, {})
        self.assertTrue(body.startswith("# Hello"))

    def test_string_values(self):
        content = '---\nkey: value\n---\nbody'
        fm, body = parse_frontmatter(content)
        self.assertEqual(fm["key"], "value")
        self.assertEqual(body.strip(), "body")

    def test_integer_values(self):
        content = '---\ncount: 42\n---\nbody'
        fm, _ = parse_frontmatter(content)
        self.assertEqual(fm["count"], 42)
        self.assertIsInstance(fm["count"], int)

    def test_boolean_values(self):
        content = '---\nactive: true\ndeleted: false\n---\nbody'
        fm, _ = parse_frontmatter(content)
        self.assertEqual(fm["active"], True)
        self.assertEqual(fm["deleted"], False)

    def test_empty_list(self):
        content = "---\ntags: []\n---\nbody"
        fm, _ = parse_frontmatter(content)
        self.assertEqual(fm["tags"], [])

    def test_quoted_strings(self):
        content = '---\nname: "Hello World"\n---\nbody'
        fm, _ = parse_frontmatter(content)
        self.assertEqual(fm["name"], "Hello World")


class TestSerializeFrontmatter(unittest.TestCase):

    def test_basic_serialization(self):
        fm = {"key": "value"}
        body = "# Title\n\nContent"
        result = serialize_frontmatter(fm, body)
        self.assertIn("key: value", result)
        self.assertIn("---", result)
        self.assertTrue(result.startswith("---\n"))

    def test_list_serialization(self):
        fm = {"tags": ["python", "wiki"]}
        result = serialize_frontmatter(fm, "body")
        self.assertIn('tags: ["python", "wiki"]', result)

    def test_boolean_serialization(self):
        fm = {"active": True, "deleted": False}
        result = serialize_frontmatter(fm, "body")
        self.assertIn("active: true", result)
        self.assertIn("deleted: false", result)

    def test_integer_serialization(self):
        fm = {"count": 42}
        result = serialize_frontmatter(fm, "body")
        self.assertIn("count: 42", result)

    def test_roundtrip(self):
        original = '---\nname: Test\ncount: 42\nactive: true\n---\n# Body'
        fm, body = parse_frontmatter(original)
        serialized = serialize_frontmatter(fm, body)
        fm2, body2 = parse_frontmatter(serialized)
        self.assertEqual(fm, fm2)


if __name__ == '__main__':
    unittest.main()
