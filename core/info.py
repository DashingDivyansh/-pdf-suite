import os

from config import QPDF_PATH
from core.executor import run_command_output
from core.validation import validate_pdf_file


def pdf_page_count(path, password=None):
    cmd = [QPDF_PATH]
    if password:
        cmd.append(f"--password={password}")
    cmd.extend(["--show-npages", path])
    result = run_command_output(cmd)
    if result["status"] != "SUCCESS":
        return None
    try:
        return int(result["stdout"].strip())
    except ValueError:
        return None


def pdf_encryption_status(path):
    result = run_command_output([QPDF_PATH, "--show-encryption", path])
    if result["status"] == "SUCCESS":
        output = result["stdout"].lower()
        if "not encrypted" in output:
            return False
        if "is encrypted" in output or "encryption" in output:
            return True
        return False
    return "password" in result["message"].lower() or "invalid password" in result["message"].lower()


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
