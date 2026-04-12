import unittest
from wiki_lib.classifier import (
    _sanitize_topic, _fallback_classification, _resolve_entity, _parse_classification
)


class TestSanitizeTopic(unittest.TestCase):

    def test_lowercase(self):
        self.assertEqual(_sanitize_topic("Hello World"), "hello_world")

    def test_replaces_spaces_with_underscore(self):
        self.assertEqual(_sanitize_topic("hello world"), "hello_world")

    def test_replaces_hyphens(self):
        self.assertEqual(_sanitize_topic("hello-world"), "hello_world")

    def test_strips_special_chars(self):
        self.assertEqual(_sanitize_topic("Hello, World!"), "hello_world")

    def test_empty_string(self):
        self.assertEqual(_sanitize_topic(""), "")

    def test_strips_leading_trailing_underscores(self):
        self.assertEqual(_sanitize_topic("__hello__"), "hello")


class TestFallbackClassification(unittest.TestCase):

    def test_returns_expected_structure(self):
        result = _fallback_classification()
        self.assertIn("primary", result)
        self.assertIn("secondary", result)
        self.assertIn("entities", result)
        self.assertEqual(result["primary"]["page"], "allgemein")
        self.assertFalse(result["primary"]["is_new"])


class TestResolveEntity(unittest.TestCase):

    def test_unknown_entity_is_new(self):
        result = _resolve_entity("NewTool", "tool", [])
        self.assertEqual(result[0], "newtool")
        self.assertTrue(result[1])
        self.assertEqual(result[2], "tool")

    def test_unknown_type_becomes_concept(self):
        result = _resolve_entity("Something", "unknown_type", [])
        self.assertEqual(result[2], "concept")

    def test_existing_entity_returns_not_new(self):
        existing = [{"name": "postgresql", "type": "tool", "aliases": []}]
        result = _resolve_entity("PostgreSQL", "tool", existing)
        self.assertEqual(result[0], "postgresql")
        self.assertFalse(result[1])

    def test_empty_name_returns_none(self):
        result = _resolve_entity("", "tool", [])
        self.assertIsNone(result)


class TestParseClassification(unittest.TestCase):

    def test_none_returns_fallback(self):
        result = _parse_classification(None, [])
        self.assertEqual(result["primary"]["page"], "allgemein")

    def test_empty_string_returns_fallback(self):
        result = _parse_classification("", [])
        self.assertEqual(result["primary"]["page"], "allgemein")

    def test_valid_json_parsed(self):
        raw = '{"primary": {"page": "testing", "title": "Testing"}}'
        result = _parse_classification(raw, [])
        self.assertEqual(result["primary"]["page"], "testing")
        self.assertEqual(result["primary"]["title"], "Testing")

    def test_secondary_topics_limited(self):
        raw = '{"primary": {"page": "main"}, "secondary": ['
        for i in range(6):
            raw += f'{{"page": "sec{i}", "context": "context{i}"}},'
        raw += ']}'
        result = _parse_classification(raw, [])
        self.assertLessEqual(len(result["secondary"]), 4)

    def test_entities_extracted(self):
        raw = '{"primary": {"page": "main"}, "entities": [{"name": "Test", "type": "tool", "role": "mentioned", "description": "desc"}]}'
        result = _parse_classification(raw, [])
        self.assertEqual(len(result["entities"]), 1)
        self.assertEqual(result["entities"][0]["name"], "Test")


if __name__ == '__main__':
    unittest.main()
