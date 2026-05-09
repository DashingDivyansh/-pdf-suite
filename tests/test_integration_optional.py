import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import GS_PATH, QPDF_PATH
from core.compress import compress_pdf
from core.merge import merge_pdfs


def tool_available(path):
    return os.path.exists(path) or shutil.which(path)


RUN_INTEGRATION = os.environ.get("PDF_TOOL_RUN_INTEGRATION") == "1"


@unittest.skipUnless(RUN_INTEGRATION and tool_available(QPDF_PATH), "qpdf integration tests disabled")
class QpdfIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.samples = [Path("test_files/a.pdf"), Path("test_files/b.pdf")]
        if not all(path.exists() for path in self.samples):
            self.skipTest("sample PDF files are not available")

    def test_merge_with_real_qpdf(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "merged.pdf"
            result = merge_pdfs([str(path) for path in self.samples], str(output))

            self.assertEqual(result, "SUCCESS")
            self.assertTrue(output.exists())


@unittest.skipUnless(RUN_INTEGRATION and tool_available(GS_PATH), "Ghostscript integration tests disabled")
class GhostscriptIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.sample = Path("test_files/a.pdf")
        if not self.sample.exists():
            self.skipTest("sample PDF file is not available")

    @patch("core.compress.os.path.exists", side_effect=lambda path: Path(path).exists())
    def test_compress_with_real_ghostscript(self, _exists):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "compressed.pdf"
            result = compress_pdf(str(self.sample), str(output), "5")

            self.assertEqual(result, "SUCCESS")
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()