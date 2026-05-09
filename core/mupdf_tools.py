import fitz  # PyMuPDF
from core.validation import validate_pdf_file


def has_text(input_pdf, sample_count=3, min_chars=50):
    """
    Improved text detection:
    - Samples pages from start, middle, and end.
    - Exits early if any page contains substantial text.
    """

    error = validate_pdf_file(input_pdf)
    if error:
        return False

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
                    return True

        return False

    except Exception:
        return False
