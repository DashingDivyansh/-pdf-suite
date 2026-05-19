import os
import unittest
import json
import tempfile
import shutil
from unittest.mock import patch
from core.cache import get_file_hash, get_cached_result, save_to_cache

class CacheTests(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.cache_dir = os.path.join(self.test_dir, "cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        
        self.file_path = os.path.join(self.test_dir, "test.pdf")
        with open(self.file_path, "wb") as f:
            f.write(b"%PDF-1.4 test content")
        
        # Patch CACHE_DIR and CACHE_MANIFEST_DIR in core.cache
        self.patcher1 = patch("core.cache.CACHE_DIR", self.cache_dir)
        self.patcher2 = patch("core.cache.CACHE_MANIFEST_DIR", os.path.join(self.cache_dir, "manifests"))
        self.patcher1.start()
        self.patcher2.start()
        
        # Ensure manifest dir exists
        os.makedirs(os.path.join(self.cache_dir, "manifests"), exist_ok=True)

    def tearDown(self):
        self.patcher2.stop()
        self.patcher1.stop()
        shutil.rmtree(self.test_dir)

    def test_file_hash_remains_consistent_for_unchanged_content(self):
        hash1 = get_file_hash(self.file_path)
        hash2 = get_file_hash(self.file_path)
        self.assertEqual(hash1, hash2)

        # Change content significantly to bypass fast hash stat check if needed
        # Actually fast hash uses size and mtime.
        time_before = os.path.getmtime(self.file_path)
        with open(self.file_path, "wb") as f:
            f.write(b"%PDF-1.4 different content extra bytes")
        
        # Ensure mtime changes
        os.utime(self.file_path, (time_before + 10, time_before + 10))
        
        hash3 = get_file_hash(self.file_path)
        self.assertNotEqual(hash1, hash3)

    def test_cache_successfully_stores_and_retrieves_results_for_identical_parameters(self):
        params = {"level": "5"}
        output_path = os.path.join(self.test_dir, "out.pdf")
        with open(output_path, "wb") as f:
            f.write(b"result")

        save_to_cache(self.file_path, "compress", params, output_path)

        cached_path = get_cached_result(self.file_path, "compress", params)
        self.assertEqual(os.path.abspath(cached_path), os.path.abspath(output_path))

    def test_cache_correctly_identifies_a_miss_when_parameters_change(self):
        dummy_out = os.path.join(self.test_dir, "dummy.pdf")
        with open(dummy_out, "wb") as f: f.write(b"data")
        save_to_cache(self.file_path, "compress", {"level": "1"}, dummy_out)

        # Different level should miss
        cached = get_cached_result(self.file_path, "compress", {"level": "5"})
        self.assertIsNone(cached)

if __name__ == "__main__":
    unittest.main()
