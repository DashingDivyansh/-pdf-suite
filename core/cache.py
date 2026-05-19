import hashlib
import json
import os
import time
from platformdirs import user_cache_dir
from core.logger import get_logger

logger = get_logger(__name__)

APP_NAME = "pdf_tool"
APP_AUTHOR = "pdf_tool"

CACHE_DIR = user_cache_dir(APP_NAME, APP_AUTHOR)
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_MANIFEST_DIR = os.path.join(CACHE_DIR, "manifests")
os.makedirs(CACHE_MANIFEST_DIR, exist_ok=True)
_FILE_HASH_CACHE = {}

class ManifestLock:
    def __init__(self, shard="global"):
        self.lock_dir = os.path.join(CACHE_DIR, f"manifest_{shard}.lock")
    
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

def get_file_hash(file_path, fast=True):
    """
    Calculate hash of a file. 
    If fast=True, hashes stat info + first/last 8KB to avoid reading huge files.
    """
    abs_path = os.path.abspath(file_path)
    try:
        stat = os.stat(abs_path)
        cache_key = (abs_path, stat.st_size, stat.st_mtime_ns, fast)
        cached_hash = _FILE_HASH_CACHE.get(cache_key)
        if cached_hash:
            return cached_hash
    except OSError:
        return None

    sha256_hash = hashlib.sha256()
    
    if fast:
        # Fast hash: stat info + head + tail
        sha256_hash.update(str(stat.st_size).encode())
        sha256_hash.update(str(stat.st_mtime_ns).encode())
        try:
            with open(abs_path, "rb") as f:
                # Head
                sha256_hash.update(f.read(8192))
                # Tail
                if stat.st_size > 8192:
                    f.seek(-8192, os.SEEK_END)
                    sha256_hash.update(f.read(8192))
        except Exception:
            pass # Fallback to whatever we have
    else:
        # Full hash
        with open(abs_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
                
    digest = sha256_hash.hexdigest()
    _FILE_HASH_CACHE[cache_key] = digest
    return digest

def _get_shard_path(shard):
    return os.path.join(CACHE_MANIFEST_DIR, f"shard_{shard}.json")

def _load_manifest(shard):
    path = _get_shard_path(shard)
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Manifest shard {shard} is corrupt or unreadable, resetting: {e}")
        # Optionally delete the corrupt shard
        try:
            os.remove(path)
        except OSError:
            pass
    except Exception:
        pass
    return {}

def _save_manifest(shard, manifest):
    path = _get_shard_path(shard)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
    except Exception:
        pass

def get_cached_result(file_path, task_type, params):
    """
    Check if a cached result exists for the given file, task, and parameters.
    Returns the path to the cached file if it exists and matches, else None.
    """
    file_hash = get_file_hash(file_path)
    if not file_hash:
        return None
        
    shard = file_hash[:2]
    with ManifestLock(shard):
        manifest = _load_manifest(shard)
    
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
    if not file_hash:
        return
        
    shard = file_hash[:2]
    key = f"{file_hash}_{task_type}_{json.dumps(params, sort_keys=True)}"
    
    with ManifestLock(shard):
        manifest = _load_manifest(shard)
        manifest[key] = {
            "output_path": os.path.abspath(output_path),
            "timestamp": os.path.getmtime(output_path)
        }
        _save_manifest(shard, manifest)
