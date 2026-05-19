import unittest
from unittest.mock import patch

from core.info import pdf_is_encrypted


class PdfIsEncryptedTests(unittest.TestCase):
    @patch("core.info.pdf_encryption_status", return_value=True)
    @patch("core.info.validate_pdf_file", return_value=None)
    def test_pdf_is_encrypted_returns_true_for_valid_encrypted_files(self, _v, _e):
        self.assertTrue(pdf_is_encrypted("x.pdf"))

    @patch("core.info.validate_pdf_file", return_value="not found")
    def test_pdf_is_encrypted_returns_false_for_invalid_file_paths(self, _v):
        self.assertFalse(pdf_is_encrypted("missing.pdf"))

    @patch("core.info.pdf_encryption_status", return_value=False)
    @patch("core.info.validate_pdf_file", return_value=None)
    def test_pdf_is_encrypted_returns_false_for_valid_non_encrypted_files(self, _v, _e):
        self.assertFalse(pdf_is_encrypted("x.pdf"))


if __name__ == "__main__":
    unittest.main()
