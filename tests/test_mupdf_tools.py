import unittest
from unittest.mock import patch, MagicMock
from core.mupdf_tools import has_text

class MuPDFToolsTests(unittest.TestCase):
    @patch("core.mupdf_tools.fitz.open")
    @patch("core.mupdf_tools.validate_pdf_file", return_value=None)
    def test_has_text_samples_middle_and_end(self, _val, mock_open):
        # Mock a 10 page document
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 10
        
        # Mock pages
        page0 = MagicMock()
        page0.get_text.return_value = "  " # Empty
        page5 = MagicMock()
        page5.get_text.return_value = "This is text in the middle"
        page9 = MagicMock()
        page9.get_text.return_value = "  "
        
        # Ensure load_page returns our mocks
        def load_page_mock(i):
            if i == 0: return page0
            if i == 5: return page5
            if i == 9: return page9
            return MagicMock()

        mock_doc.load_page.side_effect = load_page_mock
        mock_open.return_value.__enter__.return_value = mock_doc
        
        # Should return True because page 5 has text
        self.assertTrue(has_text("dummy.pdf", sample_count=3, min_chars=10))
        
        # Verify indices checked: 0, 5 (10//2), 9 (10-1)
        # Note: if page 5 returns True, it might skip page 9 due to early exit
        calls = [c.args[0] for c in mock_doc.load_page.call_args_list]
        self.assertIn(0, calls)
        self.assertIn(5, calls)

    @patch("core.mupdf_tools.fitz.open")
    @patch("core.mupdf_tools.validate_pdf_file", return_value=None)
    def test_has_text_returns_false_if_all_sampled_empty(self, _val, mock_open):
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 3
        page = MagicMock()
        page.get_text.return_value = "  "
        mock_doc.load_page.return_value = page
        mock_open.return_value.__enter__.return_value = mock_doc
        
        self.assertFalse(has_text("empty.pdf"))

if __name__ == "__main__":
    unittest.main()
