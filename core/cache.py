import hashlib
import json
import os
import time
from platformdirs import user_cache_dir

APP_NAME = "pdf_tool"
APP_AUTHOR = "pdf_tool"

CACHE_DIR = user_cache_dir(APP_NAME, APP_AUTHOR)
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_MANIFEST_PATH = os.path.join(CACHE_DIR, "cache_manifest.json")

class ManifestLock:
    def __init__(self):
        self.lock_dir = CACHE_MANIFEST_PATH + ".lock"
    
    def __enter__(self):
        start_time = time.time()
        while True:
            try:
                os.mkdir(self.lock_dir)
                return
            except OSError:
                if time.time() - start_time > 5:
                    try:
                        os.rmdir(self.lock_dir)
                    except OSError:
                        pass
                time.sleep(0.05)
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            os.rmdir(self.lock_dir)
        except OSError:
            pass

def get_file_hash(file_path):
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def _load_manifest():
    try:
        if os.path.exists(CACHE_MANIFEST_PATH):
            with open(CACHE_MANIFEST_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_manifest(manifest):
    try:
        with open(CACHE_MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
    except Exception:
        pass

def get_cached_result(file_path, task_type, params):
    """
    Check if a cached result exists for the given file, task, and parameters.
    Returns the path to the cached file if it exists and matches, else None.
    """
    with ManifestLock():
        manifest = _load_manifest()
        
    file_hash = get_file_hash(file_path)
    
    key = f"{file_hash}_{task_type}_{json.dumps(params, sort_keys=True)}"
    cached_info = manifest.get(key)
    
    if cached_info:
        cached_path = cached_info.get("output_path")
        if cached_path and os.path.exists(cached_path):
            return cached_path
    
    return None

def save_to_cache(file_path, task_type, params, output_path):
    """Save a result to the cache manifest."""
    file_hash = get_file_hash(file_path)
    key = f"{file_hash}_{task_type}_{json.dumps(params, sort_keys=True)}"
    
    with ManifestLock():
        manifest = _load_manifest()
        manifest[key] = {
            "output_path": os.path.abspath(output_path),
            "timestamp": os.path.getmtime(output_path)
        }
        _save_manifest(manifest)
