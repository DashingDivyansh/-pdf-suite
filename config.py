import os
import shutil


QPDF_PATH = os.environ.get(
    "PDF_TOOL_QPDF_PATH",
    shutil.which("qpdf") or r"C:\Program Files\qpdf 12.3.2\bin\qpdf.exe",
)

GS_PATH = os.environ.get(
    "PDF_TOOL_GS_PATH",
    shutil.which("gswin64c") or r"C:\Program Files\gs\gs10.07.0\bin\gswin64c.exe",
)

TESSERACT_PATH = os.environ.get(
    "PDF_TOOL_TESSERACT_PATH",
    shutil.which("tesseract") or r"C:\Program Files\Tesseract-OCR\tesseract.exe",
)

DEFAULT_OUTPUT_DIR = os.environ.get("PDF_TOOL_OUTPUT_DIR", "output")
