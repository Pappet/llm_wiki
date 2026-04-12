import unittest
from wiki_lib.secondary import update_secondary_page_deterministic


class TestSecondaryUpdate(unittest.TestCase):

    def test_empty_references_no_change(self):
        update_secondary_page_deterministic("new_topic", [], [])


if __name__ == '__main__':
    unittest.main()
