import unittest
from unittest.mock import Mock, patch
import tempfile
import os

from core.executor import CancellableCommand


class ExecutorTests(unittest.TestCase):
    @patch("core.executor.subprocess.Popen")
    def test_cancellable_command_handles_non_zero_exit_code_and_extracts_error_msg(self, popen):
        process = Mock()
        # Mocking an error output
        process.stdout.readline.side_effect = ['Error: file encrypted\n', '']
        process.wait.return_value = 1
        process.returncode = 1
        popen.return_value = process

        runner = CancellableCommand()
        result = runner.run(["tool"])

        self.assertTrue(result.startswith("ERROR: Error: file encrypted"))

    @patch("core.executor.subprocess.Popen")
    def test_cancellable_command_cleans_up_output_file_on_failure(self, popen):
        process = Mock()
        process.stdout.readline.return_value = ''
        process.wait.return_value = 1
        process.returncode = 1
        popen.return_value = process
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        
        runner = CancellableCommand()
        runner.run(["tool"], output_path=tmp_path)
        
        self.assertFalse(os.path.exists(tmp_path))

    @patch("core.executor.subprocess.run")
    def test_run_command_output_parses_stderr_on_failure(self, mock_run):
        mock_run.return_value = Mock(returncode=1, stdout="out", stderr="specific error")
        
        from core.executor import run_command_output
        res = run_command_output(["tool"])
        
        self.assertEqual(res["status"], "ERROR")
        self.assertEqual(res["message"], "specific error")


if __name__ == "__main__":
    unittest.main()