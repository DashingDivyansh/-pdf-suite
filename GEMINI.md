# pdf-suite Architecture and Development Guidelines

## Project Context
**pdf-suite** (formerly PDF Tool) is a dual-mode (CLI and GUI) PDF utility packaged as a standalone executable using PyInstaller.

### Current Status (May 2026)
- **Live on GitHub:** [https://github.com/DashingDivyansh/-pdf-suite](https://github.com/DashingDivyansh/-pdf-suite)
- **Licensing:** MIT License added.
- **Documentation:** README and Project Map have been overhauled for GitHub.
- **GUI Limitations:** GUI Merge ranges are NOT yet implemented; documentation has been updated to reflect this limitation.

## Critical Architectural Rules

### 1. PyInstaller & Multiprocessing Safety
- **Freeze Support:** Always ensure `multiprocessing.freeze_support()` is called immediately under the `if __name__ == "__main__":` block in the main entry point (`ui/app.py` and `main.py`). Failing to do so causes recursive fork bombs on Windows.
- **CLI Dual-Mode Conflict:** PyInstaller worker processes receive hidden command-line arguments (like `--multiprocessing-fork`). When routing between CLI and GUI modes based on `sys.argv`, explicitly ignore these arguments so the CLI parser doesn't crash the child workers.
  ```python
  if len(sys.argv) > 1 and not sys.argv[1].startswith("--multiprocessing") and not sys.argv[1].startswith("-c"):
      # Route to CLI
  ```
- **ProcessPoolExecutor Pickling:** Never pass nested functions, closures, or class methods that capture `self` (like a Tkinter instance) to `ProcessPoolExecutor`. Always define worker functions at the top-level module scope to avoid `PicklingError` on Windows and macOS.

### 2. Subprocess Window Suppression (Windows)
- When packaged as a frozen GUI app (`--noconsole`), external tools called via `subprocess` (like Tesseract or Ghostscript) will pop up empty terminal windows.
- **Enforcement:** `subprocess.Popen` is globally monkey-patched in `core/executor.py` to inject the `CREATE_NO_WINDOW` (`0x08000000`) flag when `sys.platform == "win32"` and `sys.frozen` is true. Ensure `core/executor.py` is imported early in the application lifecycle.

### 3. Concurrency and File Handling
- **Cache Manifests:** The cache uses a JSON manifest. Because the app uses parallel processing, cache updates must be protected by atomic, directory-based locking (see `ManifestLock` in `core/cache.py`) with stale lock recovery to prevent deadlocks.
- **Cleanup:** Always use `try...finally` blocks to track and delete intermediate temporary files if a multi-step operation fails or is canceled. The custom `CancellableCommand` wrapper supports automatic cleanup via an `output_path` parameter.
