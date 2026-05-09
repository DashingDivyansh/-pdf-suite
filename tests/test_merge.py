import unittest
from unittest.mock import patch

from core.merge import merge_pdfs


class MergeTests(unittest.TestCase):
    def test_merge_requires_at_least_two_files(self):
        self.assertEqual(
            merge_pdfs(["one.pdf"], "out.pdf"),
            "ERROR: At least 2 PDF file(s) are required",
        )

    @patch("core.merge.validate_output_pdf", return_value=None)
    @patch("core.merge.validate_pdf_files", return_value="File not found -> missing.pdf")
    def test_merge_reports_missing_input_file(self, _val_files, _val_out):
        result = merge_pdfs(["existing.pdf", "missing.pdf"], "out.pdf")
        self.assertEqual(result, "ERROR: File not found -> missing.pdf")

    @patch("core.merge.os.makedirs")
    @patch("core.merge.validate_output_pdf", return_value=None)
    @patch("core.merge.validate_pdf_files", return_value=None)
    @patch("core.merge.run_command", return_value="SUCCESS")
    def test_merge_builds_qpdf_command(self, run_command, _val_files, _val_out, _makedirs):
        result = merge_pdfs(["a.pdf", "b.pdf"], "build/merged.pdf")
        cmd = run_command.call_args.args[0]

        self.assertEqual(result, "SUCCESS")
        self.assertEqual(cmd[1:7], ["--empty", "--pages", "a.pdf", "1-z", "b.pdf", "1-z"])
        self.assertEqual(cmd[-2:], ["--", "build/merged.pdf"])

    @patch("core.merge.os.makedirs")
    @patch("core.merge.validate_output_pdf", return_value=None)
    @patch("core.merge.validate_pdf_files", return_value=None)
    @patch("core.merge.run_command", return_value="SUCCESS")
    def test_merge_accepts_page_ranges(self, run_command, _val_files, _val_out, _makedirs):
        result = merge_pdfs(["a.pdf", "b.pdf"], "build/merged.pdf", page_ranges=["1-3", "2,4-5"])
        cmd = run_command.call_args.args[0]

        self.assertEqual(result, "SUCCESS")
        # qpdf uses a single comma-separated range argument: "2,4-5"
        self.assertEqual(cmd[3:8], ["a.pdf", "1-3", "b.pdf", "2,4-5", "--"])

    @patch("core.merge.validate_output_pdf", return_value="Output file cannot overwrite an input file")
    @patch("core.merge.validate_pdf_files", return_value=None)
    def test_merge_rejects_overwriting_input_file(self, _val_files, _val_out):
        result = merge_pdfs(["a.pdf", "b.pdf"], "a.pdf")
        self.assertEqual(result, "ERROR: Output file cannot overwrite an input file")


if __name__ == "__main__":
    unittest.main()