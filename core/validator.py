import subprocess
from config import GS_PATH, QPDF_PATH, TESSERACT_PATH


def check_dependencies():
    errors = []

    # --- Check qpdf ---
    try:
        subprocess.run(
            [QPDF_PATH, "--version"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except FileNotFoundError:
        errors.append(f"qpdf not found at: {QPDF_PATH}")
    except Exception:
        errors.append("qpdf failed to execute")

    # --- Check Ghostscript ---
    try:
        subprocess.run(
            [GS_PATH, "--version"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except FileNotFoundError:
        errors.append(f"Ghostscript not found at: {GS_PATH}")
    except Exception:
        errors.append("Ghostscript failed to execute")

    # --- Check Tesseract ---
    try:
        subprocess.run(
            [TESSERACT_PATH, "--version"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except FileNotFoundError:
        errors.append(f"Tesseract not found at: {TESSERACT_PATH}")
    except Exception:
        errors.append("Tesseract failed to execute")

    # --- Final check ---
    if errors:
        error_msg = "\n".join(f" - {err}" for err in errors)
        print("Dependency check failed:\n" + error_msg)
        raise Exception(f"Fix the following errors:\n{error_msg}")
