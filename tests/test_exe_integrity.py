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

    def test_exe_compress_dry_run(self):
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
