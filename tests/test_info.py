import unittest
from unittest.mock import patch

from core.info import pdf_is_encrypted


class PdfIsEncryptedTests(unittest.TestCase):
    @patch("core.info.pdf_encryption_status", return_value=True)
    @patch("core.info.validate_pdf_file", return_value=None)
    def test_true_when_valid_and_encrypted(self, _v, _e):
        self.assertTrue(pdf_is_encrypted("x.pdf"))

    @patch("core.info.validate_pdf_file", return_value="not found")
    def test_false_when_invalid_path(self, _v):
        self.assertFalse(pdf_is_encrypted("missing.pdf"))

    @patch("core.info.pdf_encryption_status", return_value=False)
    @patch("core.info.validate_pdf_file", return_value=None)
    def test_false_when_valid_and_plain(self, _v, _e):
        self.assertFalse(pdf_is_encrypted("x.pdf"))


if __name__ == "__main__":
    unittest.main()
