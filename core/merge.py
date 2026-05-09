import os
from typing import List, Optional
from config import QPDF_PATH
from core.executor import run_command
from core.info import pdf_is_encrypted
from core.ranges import page_range_args
from core.validation import validate_output_pdf, validate_pdf_files


def merge_pdfs(files: List[str], output: str, page_ranges: Optional[List[str]] = None, password: Optional[str] = None, runner=None) -> str:
    input_error = validate_pdf_files(files, minimum=2)
    if input_error:
        return f"ERROR: {input_error}"

    output_error = validate_output_pdf(files, output)
    if output_error:
        return f"ERROR: {output_error}"

    try:
        output_dir = os.path.dirname(output)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        cmd = [QPDF_PATH, "--empty", "--pages"]
        for index, file_path in enumerate(files):
            if password and pdf_is_encrypted(file_path):
                cmd.append(f"--password={password}")
            cmd.append(file_path)
            ranges = page_ranges[index] if page_ranges and index < len(page_ranges) else None
            try:
                cmd.extend(page_range_args(ranges))
            except ValueError as e:
                return f"ERROR: {e}"
        cmd.extend(["--", output])

        if runner:
            return runner.run(cmd, output_path=output)
        else:
            return run_command(cmd)

    except Exception as e:
        return f"ERROR: {str(e)}"
