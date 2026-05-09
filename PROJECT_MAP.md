# Project Map: pdf-suite

A high-performance Python PDF utility for merging, compressing, and OCR, featuring both CLI and GUI modes.

## 📂 Architecture Overview

The project follows a modular structure where `core` modules handle the business logic and external tool orchestration, while `main.py` and `ui/` provide user interfaces.

### 🏗️ Core Modules (`core/`)

| Module | Responsibility | Dependencies |
| :--- | :--- | :--- |
| `compress.py` | Orchestrates PDF compression using Ghostscript. | Ghostscript, `executor`, `output`, `validation` |
| `executor.py` | Handles execution of external commands. Supports cancellation and output streaming. | `subprocess` |
| `info.py` | Retrieves PDF metadata (page count, encryption status, size). | `qpdf`, `executor`, `validation` |
| `logger.py` | Standardized logging configuration for the project. | `logging` |
| `merge.py` | Merges multiple PDFs or specific page ranges using `qpdf`. | `qpdf`, `executor`, `ranges`, `validation` |
| `mupdf_tools.py` | Fast text detection to determine if OCR is needed. | `PyMuPDF` (fitz) |
| `ocr.py` | Adds a searchable text layer to PDFs using `ocrmypdf`. | `ocrmypdf`, `executor`, `output`, `validation` |
| `output.py` | Manages output file naming based on user-defined templates. | `pathlib` |
| `ranges.py` | Parses and validates page range strings (e.g., `1-3,5`). | None |
| `settings.py` | Manages persistent application settings. | `platformdirs`, `json` |
| `validation.py` | Validates input/output paths and file existence. | `os` |
| `validator.py` | Verifies that external dependencies (`qpdf`, Ghostscript, Tesseract) are installed. | `config`, `subprocess` |

### 🖥️ User Interfaces

- **CLI (`main.py`)**: Command-line interface for automation and batch processing. Supports `merge`, `compress`, `compress-many`, `ocr`, `info`, and `detect_text`.
- **GUI (`ui/app.py`)**: Tkinter-based desktop application. Features drag-and-drop, real-time progress, file reordering, and PDF thumbnails.

### ⚙️ Configuration & Utils

- `config.py`: Centralized path configuration for external tools and environment variables.
- `build_exe.ps1`: Build script for creating a standalone Windows executable.
- `requirements.txt`: Python package dependencies.

## 🛠️ External Dependencies

### Native Tools (Required in PATH or via config)
- **qpdf**: Used for merging and inspecting PDF structure.
- **Ghostscript (gs)**: Used for high-efficiency PDF compression.
- **Tesseract OCR**: Used by `ocrmypdf` for text recognition.

### Python Packages
- `PyMuPDF` (fitz): PDF inspection and thumbnail generation.
- `ocrmypdf`: High-level OCR orchestration.
- `tkinterdnd2`: Drag-and-drop support for the Tkinter UI.
- `Pillow`: Image processing for UI thumbnails.
- `platformdirs`: Cross-platform directory management for settings.
- `pyinstaller`: Standalone executable generation.

## 🔄 Execution Flow (Example: Compression)

1. **UI/CLI** receives user input (file path, compression level).
2. **`core.compress`** validates the input file and calculates the output path.
3. **`core.compress`** builds a Ghostscript command.
4. **`core.executor`** runs the command, optionally reporting progress back to the UI.
5. **`core.compress`** verifies the output and calculates compression statistics.
6. **UI/CLI** displays the final result to the user.
