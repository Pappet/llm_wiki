import unittest
from wiki_lib.openrouter import _strip_json_fences, _extract_json_object, _build_classification_excerpt


class TestStripJsonFences(unittest.TestCase):

    def test_no_fence(self):
        self.assertEqual(_strip_json_fences('{"key": "value"}'), '{"key": "value"}')

    def test_json_fence(self):
        self.assertEqual(_strip_json_fences('```json\n{"key": "value"}\n```'), '{"key": "value"}')

    def test_fence_without_json(self):
        self.assertEqual(_strip_json_fences('```\n{"key": "value"}\n```'), '{"key": "value"}')

    def test_strips_leading_fence(self):
        self.assertEqual(_strip_json_fences('```json\n{"key": "value"}'), '{"key": "value"}')


class TestExtractJsonObject(unittest.TestCase):

    def test_valid_json(self):
        result = _extract_json_object('{"key": "value"}')
        self.assertEqual(result, {"key": "value"})

    def test_json_with_fence(self):
        result = _extract_json_object('```json\n{"key": "value"}\n```')
        self.assertEqual(result, {"key": "value"})

    def test_json_within_text(self):
        result = _extract_json_object('some text {"key": "value"} more text')
        self.assertEqual(result, {"key": "value"})

    def test_invalid_json_returns_none(self):
        result = _extract_json_object('not json at all')
        self.assertIsNone(result)

    def test_none_input(self):
        result = _extract_json_object(None)
        self.assertIsNone(result)

    def test_empty_string(self):
        result = _extract_json_object('')
        self.assertIsNone(result)


class TestBuildClassificationExcerpt(unittest.TestCase):

    def test_plain_text(self):
        text = "This is some content."
        result = _build_classification_excerpt(text)
        self.assertIn("This is some content", result)

    def test_extracts_title_from_h1(self):
        text = "# My Document Title\n\nContent here."
        result = _build_classification_excerpt(text)
        self.assertIn("My Document Title", result)

    def test_extracts_source_url(self):
        text = "---\nQuelle: https://example.com\n---\n# Title\n\nContent"
        result = _build_classification_excerpt(text)
        self.assertIn("https://example.com", result)

    def test_respects_body_limit(self):
        text = "# Title\n\n" + "x" * 5000
        result = _build_classification_excerpt(text, body_limit=1000)
        self.assertLessEqual(len(result), 1500)


if __name__ == '__main__':
    unittest.main()
