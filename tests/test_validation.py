import os
import unittest
from unittest.mock import patch

from core.validation import validate_output_pdf, validate_pdf_file, validate_pdf_files


class ValidationTests(unittest.TestCase):
    def test_validate_pdf_file_rejects_non_pdf(self):
        self.assertEqual(validate_pdf_file("notes.txt"), "Not a PDF file -> notes.txt")

    @patch("core.validation.os.path.exists", return_value=False)
    def test_validate_pdf_file_rejects_missing_file(self, _exists):
        self.assertEqual(validate_pdf_file("missing.pdf"), "File not found -> missing.pdf")

    def test_validate_pdf_files_requires_minimum_count(self):
        self.assertEqual(validate_pdf_files(["a.pdf"], minimum=2), "At least 2 PDF file(s) are required")

    def test_validate_output_rejects_non_pdf_output(self):
        self.assertEqual(validate_output_pdf(["a.pdf"], "out.txt"), "Output file must be a PDF -> out.txt")

    def test_validate_output_rejects_overwriting_input(self):
        self.assertEqual(validate_output_pdf(["a.pdf"], "a.pdf"), "Output file cannot overwrite an input file")

    @patch("core.validation.os.path.exists", return_value=True)
    @patch("core.validation.os.access", return_value=False)
    def test_validate_output_rejects_non_writable_dir(self, _access, _exists):
        # Use absolute path comparison since our validation now calls os.path.abspath
        out_dir = os.path.abspath("out")
        expected = f"Output directory is not writable -> {out_dir}"
        self.assertEqual(validate_output_pdf(["a.pdf"], "out/file.pdf"), expected)


if __name__ == "__main__":
    unittest.main()
