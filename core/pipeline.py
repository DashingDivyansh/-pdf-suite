import os
import tempfile
import shutil
from contextlib import ExitStack
from typing import List, Callable, Optional, Dict, Any

from core.logger import get_logger
from core.executor import CancellableCommand
from core.merge import merge_pdfs
from core.compress import compress_pdf
from core.ocr import ocr_pdf
from core.mupdf_tools import has_text

logger = get_logger(__name__)

class PipelineStep:
    """Base class for all pipeline steps."""
    def __init__(self, name: str):
        self.name = name

    def run(self, input_paths: List[str], output_path: str, runner: Optional[CancellableCommand] = None, **kwargs) -> str:
        raise NotImplementedError("Subclasses must implement run()")

class MergeStep(PipelineStep):
    def __init__(self, password: Optional[str] = None):
        super().__init__("Merge")
        self.password = password

    def run(self, input_paths: List[str], output_path: str, runner: Optional[CancellableCommand] = None, **kwargs) -> str:
        return merge_pdfs(input_paths, output_path, password=self.password, runner=runner)

class CompressStep(PipelineStep):
    def __init__(self, level: str = "3", password: Optional[str] = None, threads: Optional[int] = None):
        super().__init__("Compress")
        self.level = level
        self.password = password
        self.threads = threads

    def run(self, input_paths: List[str], output_path: str, runner: Optional[CancellableCommand] = None, **kwargs) -> str:
        # Compress step always takes the first input if multiple (though usually it's one from previous step)
        return compress_pdf(
            input_paths[0], 
            output_path, 
            level=self.level, 
            runner=runner, 
            password=self.password, 
            threads=self.threads,
            include_summary=True
        )

class OCRStep(PipelineStep):
    def __init__(self, password: Optional[str] = None, threads: Optional[int] = None):
        super().__init__("OCR")
        self.password = password
        self.threads = threads

    def run(self, input_paths: List[str], output_path: str, runner: Optional[CancellableCommand] = None, **kwargs) -> str:
        # Check text detection first (smart skip)
        if has_text(input_paths[0]):
            # If skipping, we still need to "produce" the output file for the next step
            shutil.copy2(input_paths[0], output_path)
            return "SUCCESS (skipped: already has text)"
            
        return ocr_pdf(
            input_paths[0], 
            os.path.dirname(output_path), 
            output_template=os.path.basename(output_path), 
            runner=runner, 
            password=self.password,
            threads=self.threads
        )

class RotateStep(PipelineStep):
    def __init__(self, angle: int = 90, password: Optional[str] = None):
        super().__init__(f"Rotate {angle}°")
        self.angle = angle
        self.password = password

    def run(self, input_paths: List[str], output_path: str, runner: Optional[CancellableCommand] = None, **kwargs) -> str:
        from config import QPDF_PATH
        from core.executor import run_command
        
        cmd = [QPDF_PATH, input_paths[0]]
        if self.password:
            cmd.append(f"--password={self.password}")
        # Syntax fix: join angle and range into one flag
        cmd.extend([f"--rotate=+{self.angle}:1-z", "--", output_path])
        
        if runner:
            return runner.run(cmd, output_path=output_path)
        return run_command(cmd)

class PipelineRunner:
    def __init__(self, steps: List[PipelineStep], progress_callback: Optional[Callable[[int, int, str], None]] = None):
        self.steps = steps
        self.progress_callback = progress_callback # (current_step, total_steps, message)
        self.runner: Optional[CancellableCommand] = None

    def run(self, initial_inputs: List[str], final_output: str) -> str:
        if not self.steps:
            return "ERROR: No steps in pipeline"

        total_steps = len(self.steps)
        with ExitStack() as stack:
            tmp_dir = stack.enter_context(tempfile.TemporaryDirectory())
            current_inputs = initial_inputs
            
            for i, step in enumerate(self.steps):
                if self.progress_callback:
                    self.progress_callback(i, total_steps, f"Running: {step.name}...")
                
                is_last = (i == total_steps - 1)
                
                # Determine target for this step
                if is_last:
                    step_output = final_output
                else:
                    # Create a unique temp file name for this step's output
                    step_output = os.path.join(tmp_dir, f"step_{i}_{step.name.lower()}.pdf")

                self.runner = CancellableCommand()
                result = step.run(current_inputs, step_output, runner=self.runner)
                
                if not result.startswith("SUCCESS"):
                    return f"ERROR in {step.name}: {result}"
                
                # Output of this step is the input for the next
                current_inputs = [step_output]

            return "SUCCESS"

    def cancel(self):
        if self.runner:
            self.runner.cancel()
