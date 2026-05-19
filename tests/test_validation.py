import os
import unittest
from unittest.mock import patch

from core.validation import validate_output_pdf, validate_pdf_file, validate_pdf_files


class ValidationTests(unittest.TestCase):
    def test_validate_pdf_file_flags_non_pdf_extensions_as_invalid(self):
        self.assertEqual(validate_pdf_file("notes.txt"), "Not a PDF file -> notes.txt")

    @patch("core.validation.os.path.exists", return_value=False)
    def test_validate_pdf_file_fails_when_file_path_does_not_exist(self, _exists):
        self.assertEqual(validate_pdf_file("missing.pdf"), "File not found -> missing.pdf")

    def test_validate_pdf_files_enforces_required_minimum_file_count(self):
        self.assertEqual(validate_pdf_files(["a.pdf"], minimum=2), "At least 2 PDF file(s) are required")

    def test_validate_output_pdf_flags_non_pdf_output_paths_as_invalid(self):
        self.assertEqual(validate_output_pdf(["a.pdf"], "out.txt"), "Output file must be a PDF -> out.txt")

    def test_validate_output_pdf_prevents_overwriting_input_files(self):
        self.assertEqual(validate_output_pdf(["a.pdf"], "a.pdf"), "Output file cannot overwrite an input file")

    @patch("core.validation.os.path.exists", return_value=True)
    @patch("core.validation.os.access", return_value=False)
    def test_validate_output_pdf_checks_write_permissions_for_destination_directory(self, _access, _exists):
        # Use absolute path comparison since our validation now calls os.path.abspath
        out_dir = os.path.abspath("out")
        expected = f"Output directory is not writable -> {out_dir}"
        self.assertEqual(validate_output_pdf(["a.pdf"], "out/file.pdf"), expected)


if __name__ == "__main__":
    unittest.main()
