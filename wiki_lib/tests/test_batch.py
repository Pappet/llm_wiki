import unittest
import os
import tempfile
from wiki_lib.batch import _register_new_topic_in_list, _register_new_entity_in_list


class TestRegisterNewTopicInList(unittest.TestCase):

    def test_adds_new_topic(self):
        existing_pages = []
        _register_new_topic_in_list("new_topic", existing_pages)
        self.assertEqual(len(existing_pages), 1)
        self.assertEqual(existing_pages[0]["name"], "new_topic")
        self.assertEqual(existing_pages[0]["kind"], "topic")

    def test_skips_existing_topic(self):
        existing_pages = [
            {"name": "existing", "kind": "topic", "title": "Existing", "path": ""}
        ]
        _register_new_topic_in_list("existing", existing_pages)
        self.assertEqual(len(existing_pages), 1)

    def test_ignores_entities_with_same_name(self):
        existing_pages = [
            {"name": "same_name", "kind": "entity", "title": "Entity", "path": ""}
        ]
        _register_new_topic_in_list("same_name", existing_pages)
        self.assertEqual(len(existing_pages), 2)


class TestRegisterNewEntityInList(unittest.TestCase):

    def test_adds_new_entity(self):
        existing_pages = []
        entity = {"slug": "new_entity", "name": "New Entity", "type": "tool"}
        _register_new_entity_in_list(entity, existing_pages)
        self.assertEqual(len(existing_pages), 1)
        self.assertEqual(existing_pages[0]["name"], "new_entity")
        self.assertEqual(existing_pages[0]["kind"], "entity")

    def test_skips_existing_entity(self):
        existing_pages = [
            {"name": "existing", "kind": "entity", "title": "Existing", "path": ""}
        ]
        entity = {"slug": "existing", "name": "Existing", "type": "tool"}
        _register_new_entity_in_list(entity, existing_pages)
        self.assertEqual(len(existing_pages), 1)

    def test_ignores_topics_with_same_name(self):
        existing_pages = [
            {"name": "same_name", "kind": "topic", "title": "Topic", "path": ""}
        ]
        entity = {"slug": "same_name", "name": "Same", "type": "tool"}
        _register_new_entity_in_list(entity, existing_pages)
        self.assertEqual(len(existing_pages), 2)


if __name__ == '__main__':
    unittest.main()
