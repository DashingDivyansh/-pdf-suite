import unittest
import os
import json
import tempfile
import shutil
from unittest.mock import patch
from core.cache import _load_manifest, _save_manifest, ManifestLock

class TestCacheResilience(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.cache_dir = os.path.join(self.test_dir, "cache")
        self.manifest_dir = os.path.join(self.cache_dir, "manifests")
        os.makedirs(self.manifest_dir, exist_ok=True)
        
        self.patch_dir = patch("core.cache.CACHE_DIR", self.cache_dir)
        self.patch_manifest = patch("core.cache.CACHE_MANIFEST_DIR", self.manifest_dir)
        self.patch_dir.start()
        self.patch_manifest.start()

    def tearDown(self):
        self.patch_manifest.stop()
        self.patch_dir.stop()
        shutil.rmtree(self.test_dir)

    def test_load_manifest_handles_corrupt_json_by_returning_empty_dict(self):
        shard = "corrupt"
        shard_path = os.path.join(self.manifest_dir, f"shard_{shard}.json")
        
        # Write invalid JSON
        with open(shard_path, "w") as f:
            f.write("{ invalid json: [")
            
        # Should not crash, should return {}
        data = _load_manifest(shard)
        self.assertEqual(data, {})
        
        # Original file should be removed or handled
        # (Based on implementation, we chose to remove it)
        self.assertFalse(os.path.exists(shard_path))

    def test_load_manifest_handles_empty_file_gracefully(self):
        shard = "empty"
        shard_path = os.path.join(self.manifest_dir, f"shard_{shard}.json")
        
        with open(shard_path, "w") as f:
            f.write("")
            
        data = _load_manifest(shard)
        self.assertEqual(data, {})

if __name__ == "__main__":
    unittest.main()
