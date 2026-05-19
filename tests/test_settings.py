import unittest
import os
import json
import tempfile
import shutil
from core.settings import load_settings, save_settings

class TestSettings(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = os.path.join(self.test_dir, "settings.json")
        # Patch SETTINGS_PATH directly
        self.patcher = unittest.mock.patch("core.settings.SETTINGS_PATH", self.test_path)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        class TestSettings(unittest.TestCase):
            ...
            def test_load_settings_successfully_retrieves_previously_saved_data(self):
                data = {"recent_files": ["a.pdf"], "output_dir": "C:/tmp"}
                save_settings(data)

                loaded = load_settings()
                self.assertEqual(loaded["recent_files"], ["a.pdf"])
                self.assertEqual(loaded["output_dir"], "C:/tmp")

            def test_load_settings_returns_empty_dictionary_when_no_settings_file_exists(self):
                # Ensure file doesn't exist
                loaded = load_settings()
                self.assertEqual(loaded, {})


if __name__ == "__main__":
    unittest.main()
