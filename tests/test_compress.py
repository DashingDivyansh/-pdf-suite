import unittest
from unittest.mock import patch

from core.compress import compression_level_description, compress_pdf, normalize_compression_level


class CompressTests(unittest.TestCase):
    @patch("core.compress.save_to_cache")
    @patch("core.compress.get_cached_result", return_value=None)
    @patch("core.compress.validate_output_pdf", return_value=None)
    @patch("core.compress.validate_pdf_file", return_value=None)
    @patch("core.compress.run_command", return_value="SUCCESS")
    def test_compress_builds_ghostscript_command(self, run_command, _val_file, _val_out, _get_cache, _save_cache):
        result = compress_pdf("input.pdf", "build/output.pdf", "5")
        cmd = run_command.call_args.args[0]

        self.assertEqual(result, "SUCCESS")
        self.assertIn("-sDEVICE=pdfwrite", cmd)
        self.assertIn("-dPDFSETTINGS=/screen", cmd)
        self.assertIn("-sOutputFile=build/output.pdf", cmd)
        self.assertEqual(cmd[-1], "input.pdf")

    def test_normalize_compression_level_accepts_numbered_levels(self):
        self.assertEqual(normalize_compression_level("1"), "/prepress")
        self.assertEqual(normalize_compression_level("5"), "/screen")

    def test_normalize_compression_level_accepts_legacy_names(self):
        self.assertEqual(normalize_compression_level("/printer"), "/printer")
        self.assertEqual(normalize_compression_level("printer"), "/printer")

    def test_normalize_compression_level_rejects_invalid_level(self):
        with self.assertRaises(ValueError):
            normalize_compression_level("tiny")

    def test_compression_level_description_explains_level(self):
        self.assertIn("most compression", compression_level_description("5"))

    @patch("core.compress.validate_pdf_file", return_value="File not found -> missing.pdf")
    def test_compress_reports_missing_input(self, _val_file):
        result = compress_pdf("missing.pdf", "out.pdf", "3")
        # compress_pdf wraps validation errors with "ERROR: "
        self.assertEqual(result, "ERROR: File not found -> missing.pdf")


if __name__ == "__main__":
    unittest.main()