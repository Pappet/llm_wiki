import unittest
from wiki_lib.routing import _route_notes_to_sections


class TestRouteNotesToSections(unittest.TestCase):

    def test_empty_notes_returns_empty(self):
        result = _route_notes_to_sections([], {'preamble': '', 'sections': []}, "topic")
        self.assertEqual(result, [])




if __name__ == '__main__':
    unittest.main()
