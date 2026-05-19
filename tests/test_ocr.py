import unittest
from unittest.mock import patch, MagicMock
import os
import sys
from core.ocr import ocr_pdf

class TestOCR(unittest.TestCase):
    @patch("core.ocr.validate_pdf_file", return_value=None)
    @patch("core.ocr.output_path", return_value="out.pdf")
    @patch("core.ocr.get_cached_result", return_value=None)
    @patch("core.ocr.save_to_cache")
    @patch("core.ocr.run_command", return_value="SUCCESS")
    def test_ocr_pdf_returns_success_after_executing_ocrmypdf_command(self, mock_run, mock_save, mock_cache, mock_out, mock_val):
        # Mock sys.frozen = False for normal test
        with patch("sys.frozen", False, create=True):
            res = ocr_pdf("in.pdf")
            self.assertEqual(res, "SUCCESS")
            mock_run.assert_called()
            mock_save.assert_called()

    @patch("core.ocr.validate_pdf_file", return_value=None)
    @patch("core.ocr.output_path", return_value="out.pdf")
    @patch("core.ocr.get_cached_result", return_value="cached.pdf")
    @patch("os.path.exists", return_value=True)
    @patch("shutil.copy2")
    def test_ocr_pdf_retrieves_result_from_cache_on_hit(self, mock_copy, mock_exists, mock_cache, mock_out, mock_val):
        # We need to import shutil in the test because it's imported inside ocr_pdf
        import shutil
        res = ocr_pdf("in.pdf")
        self.assertEqual(res, "SUCCESS")
        mock_copy.assert_called_with("cached.pdf", "out.pdf")

    @patch("core.ocr.validate_pdf_file", return_value=None)
    @patch("core.ocr.output_path", return_value="out.pdf")
    @patch("core.ocr.get_cached_result", return_value=None)
    @patch("core.ocr.save_to_cache")
    def test_ocr_pdf_uses_in_process_api_when_running_as_frozen_executable(self, mock_save, mock_cache, mock_out, mock_val):
        # Mock sys.frozen = True and ocrmypdf.ocr
        with patch("sys.frozen", True, create=True):
            # We need to mock the ocrmypdf module since it's imported inside the frozen block
            mock_ocr_mod = MagicMock()
            mock_ocr_mod.ocr.return_value = 0 # ExitCode.ok
            
            with patch.dict("sys.modules", {"ocrmypdf": mock_ocr_mod}):
                res = ocr_pdf("in.pdf")
                self.assertEqual(res, "SUCCESS")
                mock_ocr_mod.ocr.assert_called_once()
                # Verify frozen mode stays on the thread-only path
                args, kwargs = mock_ocr_mod.ocr.call_args
                self.assertEqual(kwargs.get("jobs"), 1)
                self.assertTrue(kwargs.get("use_threads"))

    @patch("core.ocr.validate_pdf_file", return_value="Invalid file")
    def test_ocr_pdf_fails_with_error_message_on_validation_failure(self, mock_val):
        res = ocr_pdf("invalid.pdf")
        self.assertTrue(res.startswith("ERROR: Invalid file"))

if __name__ == "__main__":
    unittest.main()
