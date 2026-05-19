# pdf-suite Architecture and Development Guidelines

## Project Context
**pdf-suite** (formerly PDF Tool) is a dual-mode (CLI and GUI) PDF utility packaged as a standalone executable using PyInstaller.

### Current Status (May 2026)
- **Live on GitHub:** [https://github.com/DashingDivyansh/-pdf-suite](https://github.com/DashingDivyansh/-pdf-suite)
- **Licensing:** MIT License added.
- **Documentation:** README and Project Map have been overhauled for GitHub.
- **GUI Limitations:** GUI Merge ranges are NOT yet implemented; documentation has been updated to reflect this limitation.
- **UI Update:** Desktop UI now uses a structured workspace layout with preview, workflow, queue snapshot, and activity log panels.
- **Tests:** `python -m unittest discover -s tests` passes on the current local test machine.

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
- **Enforcement:** `subprocess.Popen` is globally monkey-patched in `core/executor.py` to inject the `CREATE_NO_WINDOW` (`0x08000000`) flag when `sys.platform == "win32"` and `sys.frozen` is true.
- **Thread Safety:** `CancellableCommand` uses a background thread for non-blocking I/O reading to prevent UI hangs.

### 2.1 UI and High-DPI
- **DPI Awareness:** The application calls `SetProcessDpiAwareness(1)` on Windows to ensure sharp text on high-resolution displays.
- **Design System:** Use the spacing scale (`SPACE_XS` to `SPACE_XL`) and typography hierarchy (`FONT_H1`, etc.) defined in `ui/app.py`.
- **Keyboard Shortcuts:** Maintain `Ctrl+O` (Add), `Ctrl+Enter` (Process), and `Esc` (Cancel) support.

### 2.2 Pipeline Architecture
- **Step Isolation:** New PDF operations must be implemented as subclasses of `PipelineStep` in `core/pipeline.py`.
- **Intermediates:** `PipelineRunner` handles `tempfile.TemporaryDirectory` and `ExitStack` for intermediate files between steps. Do not manually manage temp files for multi-step jobs in the UI.

### 3. Concurrency and File Handling
- **Cache Sharding:** The cache uses a sharded manifest (`manifests/shard_xx.json`) based on the first 2 characters of the file hash.
- **Fast Hashing:** Initial cache checks use a fast hash (stat info + first/last 8KB) to avoid reading massive PDFs.
- **Corruption Recovery:** `_load_manifest` automatically resets corrupt or empty shards.

### 4. Performance Rules
- The app is CPU-bound; do not assume GPU acceleration exists.
- Large file drops in the GUI should stay responsive. `ui/app.py` now loads page counts asynchronously instead of blocking on `qpdf --show-npages` for every file.
- Favor stat-based/session caches before expensive full-file work:
  - `core/cache.py`: file hash cache
  - `core/info.py`: page count and encryption caches
  - `core/mupdf_tools.py`: text-detection cache
- Parallelism should be tuned, not maximized blindly. Use the `fast`, `balanced`, and `quality` profiles in `core/compress.py` and `ui/app.py` instead of hardcoding all CPUs everywhere.
