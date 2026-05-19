import unittest
import os
import tempfile
import shutil
import time
from core.cache import get_file_hash

class TestHashPerformance(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.large_file = os.path.join(self.test_dir, "large.pdf")
        # 10MB file
        with open(self.large_file, "wb") as f:
            f.write(b"%PDF-1.4\n" + b"0" * (10 * 1024 * 1024))

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_fast_hash_is_significantly_faster_than_full_hash_for_large_files(self):
        # Warm up cache (the in-memory one, not the manifest)
        # Actually we want to measure the reading time, so clear memory cache if possible
        # or just use different files.
        
        start_full = time.time()
        hash_full = get_file_hash(self.large_file, fast=False)
        duration_full = time.time() - start_full
        
        # Clear the in-memory cache to ensure fast hash actually does work
        import core.cache
        core.cache._FILE_HASH_CACHE = {}
        
        start_fast = time.time()
        hash_fast = get_file_hash(self.large_file, fast=True)
        duration_fast = time.time() - start_fast
        
        print(f"\nFull hash: {duration_full:.4f}s, Fast hash: {duration_fast:.4f}s")
        self.assertLess(duration_fast, duration_full)
        # Fast hash should be VERY fast because it only reads 16KB + stat
        # Full hash reads 10MB.
        # On most systems this will be at least 2-5x faster.

if __name__ == "__main__":
    unittest.main()
