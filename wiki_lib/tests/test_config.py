import unittest
from wiki_lib import config


class TestConfigFunctions(unittest.TestCase):

    def test_config_module_exists(self):
        self.assertIsNotNone(config)

    def test_config_is_dict(self):
        self.assertIsInstance(config.config, dict)

    def test_has_directories(self):
        self.assertIn("directories", config.config)


if __name__ == '__main__':
    unittest.main()
