import subprocess
import sys
from core.logger import get_logger

logger = get_logger(__name__)

# Prevent console window flash on Windows
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def patch_subprocess():
    """
    Monkey-patch subprocess.Popen to include CREATE_NO_WINDOW flag on Windows.
    This is essential for frozen (EXE) GUI applications to prevent external 
    tools (like Tesseract or Ghostscript) from popping up terminal windows.
    """
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        import subprocess

        _original_popen = subprocess.Popen

        def patched_popen(*args, **kwargs):
            kwargs["creationflags"] = kwargs.get("creationflags", 0) | CREATE_NO_WINDOW
            return _original_popen(*args, **kwargs)

        subprocess.Popen = patched_popen
        logger.info("Subprocess Popen monkey-patched for window suppression.")


# Apply the patch immediately if imported in a frozen Windows app
patch_subprocess()


class CancellableCommand:
    def __init__(self):
        self.process = None
        self.cancelled = False
        self.output_path = None

    def run(self, cmd, progress_callback=None, output_path=None):
        self.cancelled = False
        self.output_path = output_path

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=CREATE_NO_WINDOW
            )
            
            output_lines = []
            for line in iter(self.process.stdout.readline, ''):
                if line:
                    output_lines.append(line)
                    if progress_callback:
                        progress_callback(line.strip())
            
            returncode = self.process.wait()

            if returncode == 0:
                return "SUCCESS"

            if self.cancelled:
                self._cleanup_output()
                return "CANCELLED"

            if returncode != 0:
                self._cleanup_output()
                error_msg = "".join(output_lines).strip() or "Unknown error"
                if len(error_msg) > 500:
                    error_msg = error_msg[:500] + "..."
                logger.error(f"Command failed with {self.process.returncode}: {error_msg} | CMD: {cmd}")
                return f"ERROR: {error_msg}"

            return "SUCCESS"

        except FileNotFoundError:
            logger.error(f"Command not found: {cmd}")
            return "ERROR: Command not found (check path to external tool)"

        except Exception as e:
            self._cleanup_output()
            logger.exception("Unexpected error in CancellableCommand")
            return f"ERROR: {str(e)}"

        finally:
            self.process = None

    def cancel(self):
        self.cancelled = True
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                logger.warning("Process did not terminate gracefully, sending kill signal.")
                self.process.kill()
            except Exception as e:
                logger.error(f"Error terminating process: {e}")

    def _cleanup_output(self):
        if self.output_path and os.path.exists(self.output_path):
            try:
                import os
                os.remove(self.output_path)
                logger.info(f"Cleaned up partial output file: {self.output_path}")
            except Exception as e:
                logger.error(f"Failed to clean up partial output: {e}")


def run_command(cmd):
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            logger.error(f"run_command failed: {error_msg} | CMD: {cmd}")
            return f"ERROR: {error_msg}"

        return "SUCCESS"

    except FileNotFoundError:
        logger.error(f"Command not found: {cmd}")
        return "ERROR: Command not found (check path to external tool)"

    except Exception as e:
        logger.exception("Unexpected error in run_command")
        return f"ERROR: {str(e)}"


def run_command_output(cmd):
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            logger.error(f"run_command_output failed: {error_msg} | CMD: {cmd}")
            return {
                "status": "ERROR",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "message": error_msg,
            }

        return {
            "status": "SUCCESS",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "message": "",
        }

    except FileNotFoundError:
        logger.error(f"Command not found: {cmd}")
        return {
            "status": "ERROR",
            "stdout": "",
            "stderr": "",
            "message": "Command not found (check path to external tool)",
        }

    except Exception as e:
        logger.exception("Unexpected error in run_command_output")
        return {
            "status": "ERROR",
            "stdout": "",
            "stderr": "",
            "message": str(e),
        }
