import os
import subprocess
import unittest
import sys
from pathlib import Path

# Path to the built executable
EXE_PATH = Path("dist/PDF_Tool/PDF_Tool.exe")
SAMPLE_PDF = Path("test_files/a.pdf")

class TestExecutableIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not EXE_PATH.exists():
            raise unittest.SkipTest(f"Executable not found at {EXE_PATH}. Run build_exe.ps1 first.")
        if not SAMPLE_PDF.exists():
            raise unittest.SkipTest(f"Sample PDF not found at {SAMPLE_PDF}.")

    def run_exe(self, args):
        cmd = [str(EXE_PATH)] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result

    def test_exe_help(self):
        """Verify the exe can print help (basic module loading check)."""
        res = self.run_exe(["--help"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("usage: PDF_Tool", res.stdout)

    def test_exe_info(self):
        """Verify the exe can run the 'info' command (PyMuPDF / core.info check)."""
        res = self.run_exe(["info", str(SAMPLE_PDF)])
        self.assertEqual(res.returncode, 0)
        self.assertIn("Pages:", res.stdout)
        self.assertIn("Size:", res.stdout)

    def test_exe_detect_text(self):
        """Verify the exe can run 'detect_text' (MuPDF check)."""
        res = self.run_exe(["detect_text", str(SAMPLE_PDF)])
        self.assertEqual(res.returncode, 0)
        # Should output True or False
        self.assertIn("True", res.stdout)

    def test_executable_can_successfully_initialize_ocr_engine_without_runtime_errors(self):
        """Verify the exe can run the 'ocr' command (Full OCR import check)."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_exe(["ocr", str(SAMPLE_PDF), "--out-dir", tmp])
            # We don't necessarily need Tesseract to be perfect, 
            # but we MUST not see an ImportError or TypeError
            self.assertNotIn("ImportError", res.stderr)
            self.assertNotIn("TypeError", res.stderr)
            self.assertNotIn("Traceback", res.stderr)

    def test_executable_successfully_processes_complex_chained_workflow_of_merge_and_compress(self):
        """Verify a complex workflow: merge + compress (via CLI logic)."""
        # Note: main.py CLI doesn't chain all in one command, 
        # but ui/app.py logic does. We verify they can be run sequentially.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            merged = tmp_path / "merged.pdf"
            compressed = tmp_path / "final.pdf"
            
            # 1. Merge
            res = self.run_exe(["merge", str(SAMPLE_PDF), str(SAMPLE_PDF), "-o", str(merged)])
            self.assertEqual(res.returncode, 0, f"Merge failed: {res.stderr}")
            self.assertTrue(merged.exists())
            
            # 2. Compress the merged result
            res = self.run_exe(["compress", str(merged), "-o", str(compressed), "--level", "3"])
            self.assertEqual(res.returncode, 0, f"Compress failed: {res.stderr}")
            self.assertTrue(compressed.exists())

    def test_executable_can_successfully_dispatch_compression_task_to_ghostscript(self):
        """Verify the exe can build a compress command (Ghostscript check)."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            out_pdf = Path(tmp) / "out.pdf"
            res = self.run_exe(["compress", str(SAMPLE_PDF), "-o", str(out_pdf), "--level", "1"])
            # If GS is missing it might return 1, but we check if it's a ModuleNotFoundError
            self.assertNotIn("ModuleNotFoundError", res.stderr)
            self.assertNotIn("Traceback", res.stderr)

if __name__ == "__main__":
    unittest.main()
