import os
import sys

from config import DEFAULT_OUTPUT_DIR
from core.cache import get_cached_result, save_to_cache
from core.logger import get_logger
from core.output import output_path
from core.validation import validate_pdf_file
from core.executor import run_command

logger = get_logger(__name__)


def ocr_pdf(input_file, output_dir=DEFAULT_OUTPUT_DIR, output_template="ocr_{name}.pdf", progress_callback=None, runner=None, password=None, threads=None):
    input_error = validate_pdf_file(input_file)
    if input_error:
        return f"ERROR: {input_error}"

    try:
        os.makedirs(output_dir, exist_ok=True)
        output_file = output_path(output_dir, output_template, input_file)

        # Check cache
        cached = get_cached_result(input_file, "ocr", {"password": password})
        if cached and os.path.exists(cached):
            try:
                import shutil
                shutil.copy2(cached, output_file)
                return "SUCCESS"
            except Exception:
                pass

        cpu_count = threads if threads is not None else (os.cpu_count() or 2)

        # If frozen (EXE), use the API directly
        if getattr(sys, 'frozen', False):
            # We avoid stubbing unittest.mock here because it's too risky and 
            # causes "cannot import name patch" elsewhere. 
            # Instead, we rely on the fact that ocrmypdf's use of mock is minimal.
            # If the asyncio bug persists, we will use a more surgical approach.
            import ocrmypdf
            from config import TESSERACT_PATH, GS_PATH
            
            # Ensure Tesseract and Ghostscript are in PATH for ocrmypdf
            tess_dir = os.path.dirname(TESSERACT_PATH)
            gs_dir = os.path.dirname(GS_PATH)
            current_path = os.environ.get("PATH", "")
            paths_to_add = []
            if tess_dir and tess_dir not in current_path:
                paths_to_add.append(tess_dir)
            if gs_dir and gs_dir not in current_path:
                paths_to_add.append(gs_dir)
            
            if paths_to_add:
                os.environ["PATH"] = os.pathsep.join(paths_to_add) + os.pathsep + current_path

            try:
                # Use jobs=1 in frozen mode to avoid pickling/multiprocessing errors
                # that cause "function() argument 'code' must be code, not str"
                exit_code = ocrmypdf.ocr(
                    input_file, 
                    output_file, 
                    skip_text=True, 
                    optimize=1, 
                    output_type="pdf", 
                    jobs=1,
                    use_threads=True,
                    fast_web_view=0,
                    password=password,
                    tesseract_oem=1
                )
                if exit_code == 0 or exit_code == ocrmypdf.ExitCode.ok:
                    save_to_cache(input_file, "ocr", {"password": password}, output_file)
                    return "SUCCESS"
                return f"ERROR: ocrmypdf exit code {exit_code}"
            except Exception as e:
                logger.exception(
                    "Frozen OCR path failed for input=%s output=%s",
                    input_file,
                    output_file,
                )
                return f"ERROR: {str(e)}"

        # Standard subprocess path for CLI/Dev
        cmd = [
            sys.executable,
            "-m",
            "ocrmypdf",
            "--skip-text",
            "-O", "1",
            "--output-type", "pdf",
            "--jobs", str(cpu_count),
            "--tesseract-oem", "1",
        ]

        if password:
            cmd.extend(["--input-password", password])

        cmd.extend([input_file, output_file])

        if runner:
            res = runner.run(cmd, progress_callback=progress_callback, output_path=output_file)
        else:
            res = run_command(cmd)

        if res == "SUCCESS":
            save_to_cache(input_file, "ocr", {"password": password}, output_file)
        
        return res

    except Exception as e:
        logger.exception("ocr_pdf failed for input=%s", input_file)
        return f"ERROR: {str(e)}"
