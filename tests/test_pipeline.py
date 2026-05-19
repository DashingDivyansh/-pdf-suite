import unittest
from unittest.mock import MagicMock, patch
import os
import tempfile
import shutil
from core.pipeline import PipelineRunner, PipelineStep, MergeStep, RotateStep

class MockStep(PipelineStep):
    def __init__(self, name, success=True):
        super().__init__(name)
        self.success = success
        self.called_with = None

    def run(self, input_paths, output_path, runner=None, **kwargs):
        self.called_with = (input_paths, output_path)
        # Create dummy output
        with open(output_path, "w") as f:
            f.write("result")
        return "SUCCESS" if self.success else "ERROR"

class TestPipeline(unittest.TestCase):
    def test_pipeline_runner_executes_steps_sequentially_and_passes_outputs(self):
        step1 = MockStep("Step1")
        step2 = MockStep("Step2")
        runner = PipelineRunner([step1, step2])
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            out_path = tmp.name
        
        try:
            res = runner.run(["input.pdf"], out_path)
            
            self.assertEqual(res, "SUCCESS")
            # Step 1 should get initial input
            self.assertEqual(step1.called_with[0], ["input.pdf"])
            # Step 2 should get Step 1's output
            self.assertEqual(step2.called_with[0], [step1.called_with[1]])
            # Step 2 output should be the final path
            self.assertEqual(step2.called_with[1], out_path)
        finally:
            if os.path.exists(out_path):
                os.remove(out_path)

    @patch("core.pipeline.tempfile.TemporaryDirectory")
    def test_pipeline_runner_cleans_up_temp_dir_on_step_failure(self, mock_tempdir):
        # Setup mock temp directory
        temp_dir_path = "/tmp/fake_pipeline_tmp"
        mock_temp_context = MagicMock()
        mock_temp_context.__enter__.return_value = temp_dir_path
        mock_tempdir.return_value = mock_temp_context
        
        step1 = MockStep("FailStep", success=False)
        runner = PipelineRunner([step1])
        
        res = runner.run(["in.pdf"], "out.pdf")
        
        self.assertTrue(res.startswith("ERROR"))
        # Verify ExitStack (via TemporaryDirectory) was cleaned up
        mock_temp_context.__exit__.assert_called()

    @patch("core.executor.run_command", return_value="SUCCESS")
    def test_rotate_step_constructs_correct_qpdf_command(self, mock_run):
        from config import QPDF_PATH
        step = RotateStep(angle=180, password="secret")
        
        res = step.run(["in.pdf"], "out.pdf")
        
        self.assertEqual(res, "SUCCESS")
        cmd = mock_run.call_args[0][0]
        self.assertIn(QPDF_PATH, cmd)
        # Check for combined flag since --rotate and +angle:1-z are now joined
        self.assertTrue(any(arg.startswith("--rotate=") for arg in cmd) or "--rotate" in cmd)
        self.assertTrue(any("+180" in arg for arg in cmd))
        self.assertIn("--password=secret", cmd)

if __name__ == "__main__":
    unittest.main()
