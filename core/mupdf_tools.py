import os

from core.validation import validate_pdf_file

_TEXT_CACHE = {}


def _cache_key(path, sample_count, min_chars):
    try:
        stat = os.stat(path)
        return (os.path.abspath(path), stat.st_size, stat.st_mtime_ns, sample_count, min_chars)
    except OSError:
        return None


def has_text(input_pdf, sample_count=3, min_chars=50):
    """
    Improved text detection:
    - Samples pages from start, middle, and end.
    - Exits early if any page contains substantial text.
    """
    import fitz  # Lazy load PyMuPDF for faster startup

    error = validate_pdf_file(input_pdf)
    if error:
        return False

    cache_key = _cache_key(input_pdf, sample_count, min_chars)
    if cache_key in _TEXT_CACHE:
        return _TEXT_CACHE[cache_key]

    try:
        with fitz.open(input_pdf) as doc:
            total_pages = len(doc)
            if total_pages == 0:
                return False

            # Determine indices to sample
            if total_pages <= sample_count:
                indices = range(total_pages)
            else:
                indices = [0, total_pages // 2, total_pages - 1]

            for i in indices:
                page = doc.load_page(i)
                text = page.get_text().strip()
                if len(text) >= min_chars:
                    if cache_key:
                        _TEXT_CACHE[cache_key] = True
                    return True

        if cache_key:
            _TEXT_CACHE[cache_key] = False
        return False

    except Exception:
        return False
