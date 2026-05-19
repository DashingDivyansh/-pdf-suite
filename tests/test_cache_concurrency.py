import os
import unittest
import time
import multiprocessing
import tempfile
import shutil
from core.cache import ManifestLock, _load_manifest, _save_manifest, CACHE_DIR, CACHE_MANIFEST_DIR

def worker_write(shard, lock_dir, manifest_path, key, value):
    # Manually use the lock logic since we're testing the lock itself
    lock = ManifestLock(shard)
    with lock:
        if os.path.exists(manifest_path):
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
        else:
            manifest = {}
        
        manifest[key] = value
        # Simulate some work while holding the lock
        time.sleep(0.01)
        
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)

import json

class TestCacheConcurrency(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # Redirect cache to temp dir
        self.patch_dir = unittest.mock.patch("core.cache.CACHE_DIR", self.test_dir)
        self.patch_manifest = unittest.mock.patch("core.cache.CACHE_MANIFEST_DIR", os.path.join(self.test_dir, "manifests"))
        self.patch_dir.start()
        self.patch_manifest.start()
        os.makedirs(os.path.join(self.test_dir, "manifests"), exist_ok=True)

    def tearDown(self):
        self.patch_manifest.stop()
        self.patch_dir.stop()
        shutil.rmtree(self.test_dir)

    def test_manifest_lock_prevents_race_conditions_during_parallel_writes(self):
        shard = "test_shard"
        manifest_path = os.path.join(self.test_dir, "manifests", f"shard_{shard}.json")
        lock_dir = os.path.join(self.test_dir, f"manifest_{shard}.lock")
        
        processes = []
        num_workers = 10
        for i in range(num_workers):
            p = multiprocessing.Process(
                target=worker_write, 
                args=(shard, lock_dir, manifest_path, f"key_{i}", f"value_{i}")
            )
            processes.append(p)
            p.start()
            
        for p in processes:
            p.join()
            
        # If lock worked, we should have all keys
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        
        self.assertEqual(len(manifest), num_workers)
        for i in range(num_workers):
            self.assertIn(f"key_{i}", manifest)

if __name__ == "__main__":
    unittest.main()
