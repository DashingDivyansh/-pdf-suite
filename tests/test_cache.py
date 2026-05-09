import os
import unittest
import json
import tempfile
import shutil
from core.cache import get_file_hash, get_cached_result, save_to_cache, CACHE_MANIFEST_PATH

class CacheTests(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.file_path = os.path.join(self.test_dir, "test.pdf")
        with open(self.file_path, "wb") as f:
            f.write(b"%PDF-1.4 test content")
        
        # Backup existing manifest if it exists
        self.manifest_backup = None
        if os.path.exists(CACHE_MANIFEST_PATH):
            with open(CACHE_MANIFEST_PATH, "r") as f:
                self.manifest_backup = f.read()
            os.remove(CACHE_MANIFEST_PATH)

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        # Restore manifest
        if self.manifest_backup:
            with open(CACHE_MANIFEST_PATH, "w") as f:
                f.write(self.manifest_backup)
        elif os.path.exists(CACHE_MANIFEST_PATH):
            os.remove(CACHE_MANIFEST_PATH)

    def test_file_hash_consistency(self):
        hash1 = get_file_hash(self.file_path)
        hash2 = get_file_hash(self.file_path)
        self.assertEqual(hash1, hash2)
        
        # Change content
        with open(self.file_path, "wb") as f:
            f.write(b"%PDF-1.4 different content")
        hash3 = get_file_hash(self.file_path)
        self.assertNotEqual(hash1, hash3)

    def test_cache_save_and_hit(self):
        params = {"level": "5"}
        output_path = os.path.join(self.test_dir, "out.pdf")
        with open(output_path, "wb") as f:
            f.write(b"result")
            
        save_to_cache(self.file_path, "compress", params, output_path)
        
        cached_path = get_cached_result(self.file_path, "compress", params)
        self.assertEqual(os.path.abspath(cached_path), os.path.abspath(output_path))

    def test_cache_miss_on_param_change(self):
        dummy_out = os.path.join(self.test_dir, "dummy.pdf")
        with open(dummy_out, "wb") as f: f.write(b"data")
        save_to_cache(self.file_path, "compress", {"level": "1"}, dummy_out)
        
        # Different level should miss
        cached = get_cached_result(self.file_path, "compress", {"level": "5"})
        self.assertIsNone(cached)

if __name__ == "__main__":
    unittest.main()
