import unittest
from unittest.mock import Mock, patch

from core.executor import CancellableCommand


class ExecutorTests(unittest.TestCase):
    @patch("core.executor.subprocess.Popen")
    def test_cancellable_command_returns_success(self, popen):
        process = Mock()
        # Simulate no output and successful return code
        process.stdout.readline.return_value = ''
        process.wait.return_value = 0
        popen.return_value = process

        result = CancellableCommand().run(["tool"])

        self.assertEqual(result, "SUCCESS")

    @patch("core.executor.subprocess.Popen")
    def test_cancel_terminates_running_process(self, popen):
        process = Mock()
        popen.return_value = process
        runner = CancellableCommand()
        runner.process = process

        runner.cancel()

        process.terminate.assert_called_once()


if __name__ == "__main__":
    unittest.main()