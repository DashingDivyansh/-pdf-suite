import unittest
from unittest.mock import patch, MagicMock
import subprocess
from core.validator import check_dependencies

class TestValidator(unittest.TestCase):
    @patch("subprocess.run")
    def test_check_dependencies_successfully_verifies_presence_of_all_required_external_tools(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        # Should not raise exception
        check_dependencies()
        self.assertEqual(mock_run.call_count, 3)

    @patch("subprocess.run")
    def test_check_dependencies_raises_exception_when_external_tools_are_missing_from_path(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        with self.assertRaises(Exception) as cm:
            check_dependencies()
        self.assertIn("not found", str(cm.exception))

if __name__ == "__main__":
    unittest.main()
