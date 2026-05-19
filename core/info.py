import os

from config import QPDF_PATH
from core.executor import run_command_output
from core.validation import validate_pdf_file

_PAGE_COUNT_CACHE = {}
_ENCRYPTION_CACHE = {}


def _cache_key(path, password=None):
    abs_path = os.path.abspath(path)
    try:
        stat = os.stat(abs_path)
        return (abs_path, stat.st_size, stat.st_mtime_ns, password or "")
    except OSError:
        return None


def pdf_page_count(path, password=None):
    cache_key = _cache_key(path, password=password)
    if cache_key in _PAGE_COUNT_CACHE:
        return _PAGE_COUNT_CACHE[cache_key]

    cmd = [QPDF_PATH]
    if password:
        cmd.append(f"--password={password}")
    cmd.extend(["--show-npages", path])
    result = run_command_output(cmd)
    if result["status"] != "SUCCESS":
        return None
    try:
        page_count = int(result["stdout"].strip())
        if cache_key:
            _PAGE_COUNT_CACHE[cache_key] = page_count
        return page_count
    except ValueError:
        return None


def pdf_encryption_status(path):
    cache_key = _cache_key(path)
    if cache_key in _ENCRYPTION_CACHE:
        return _ENCRYPTION_CACHE[cache_key]

    result = run_command_output([QPDF_PATH, "--show-encryption", path])
    if result["status"] == "SUCCESS":
        output = result["stdout"].lower()
        if "not encrypted" in output:
            if cache_key:
                _ENCRYPTION_CACHE[cache_key] = False
            return False
        if "is encrypted" in output or "encryption" in output:
            if cache_key:
                _ENCRYPTION_CACHE[cache_key] = True
            return True
        if cache_key:
            _ENCRYPTION_CACHE[cache_key] = False
        return False
    encrypted = "password" in result["message"].lower() or "invalid password" in result["message"].lower()
    if cache_key:
        _ENCRYPTION_CACHE[cache_key] = encrypted
    return encrypted


def pdf_is_encrypted(path):
    """One qpdf call; use for batch password probing. Invalid paths treated as non-encrypted."""
    if validate_pdf_file(path):
        return False
    return pdf_encryption_status(path) is True


def pdf_info(path, password=None):
    error = validate_pdf_file(path)
    if error:
        return {"error": error}

    page_count = pdf_page_count(path, password=password)
    encrypted = pdf_encryption_status(path)

    return {
        "path": path,
        "size": os.path.getsize(path),
        "pages": page_count,
        "encrypted": encrypted,
    }
