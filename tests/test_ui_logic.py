import unittest
from unittest.mock import MagicMock, patch
import os
from ui.app import PDFToolUI

class TestUILogic(unittest.TestCase):
    @patch("core.pipeline.PipelineRunner")
    @patch("core.pipeline.MergeStep")
    @patch("core.pipeline.CompressStep")
    @patch("core.pipeline.RotateStep")
    def test_process_task_constructs_correct_pipeline_steps(self, mock_rotate, mock_compress, mock_merge, mock_runner):
        # Mock 'self' (the app instance)
        mock_app = MagicMock(spec=PDFToolUI)
        mock_app.performance_profile = MagicMock()
        mock_app.performance_profile.get.return_value = "balanced"
        mock_app.safe_ui = MagicMock()
        mock_app._parallelism.return_value = (1, 1)
        
        files = ["a.pdf", "b.pdf"]
        merge = True
        compress = True
        ocr = False
        rotate = True
        level = "3"
        password = "pw"
        out_path = "out.pdf"
        
        # Invoke the unbound method
        PDFToolUI._process_task(mock_app, files, merge, compress, ocr, rotate, level, password, out_path)
        
        # Verify steps were created
        mock_merge.assert_called_with(password="pw")
        mock_rotate.assert_called_with(angle=90, password="pw")
        mock_compress.assert_called() # level and threads are passed
        
        # Verify runner was created and run
        mock_runner.assert_called()
        mock_runner.return_value.run.assert_called_with(files, out_path)

if __name__ == "__main__":
    unittest.main()
