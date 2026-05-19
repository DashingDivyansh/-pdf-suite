# Project Map: pdf-suite

A high-performance Python PDF utility for merging, compressing, and OCR, featuring both CLI and GUI modes.

## 📂 Architecture Overview

The project follows a modular structure where `core` modules handle logic, and `ui` handles the Tkinter interface.

- **`core/pipeline.py`**: Orchestrates sequential operations (Merge → Rotate → OCR → Compress) using discrete `PipelineStep` objects and a `PipelineRunner`.
- **`core/compress.py`**: Wrapper for Ghostscript compression.
- **`core/ocr.py`**: Wrapper for `ocrmypdf`.
- **`core/merge.py`**: Wrapper for `qpdf` merge operations.
- **`core/executor.py`**: Unified subprocess execution with non-blocking threaded I/O reading and window suppression.
- **`core/cache.py`**: Persistent, sharded caching system for processing results to avoid redundant CPU work.
- **`core/info.py`**: Retrieves PDF metadata (page count, encryption status, size) with lightweight session caching.
- **`core/logger.py`**: Standardized logging configuration for the project.
- **`core/mupdf_tools.py`**: Fast text detection to determine if OCR is needed, with session caching.
- **`core/output.py`**: Manages output file naming based on user-defined templates.
- **`core/ranges.py`**: Parses and validates page range strings.
- **`core/settings.py`**: Manages persistent application settings.
- **`core/validation.py`**: Validates input/output paths and file existence.
- **`core/validator.py`**: Verifies that external dependencies (qpdf, Ghostscript, Tesseract) are installed.

## ✨ Features

- **Merge PDF**: Combine multiple PDFs with support for page ranges.
- **Compress PDF**: Optimize file size using predefined profiles (Fast, Balanced, Quality).
- **OCR PDF**: Make scanned PDFs searchable (requires Tesseract).
- **Rotate PDF**: Rotate all pages 90° clockwise.
- **Sequential Workflows**: Chain multiple actions in a single "Pipeline" run.
- **Batch Processing**: Parallel execution for individual file actions.
- **High-DPI Support**: Native resolution rendering on Windows.

## 🖥️ User Interfaces

- **CLI (`main.py`)**: Command-line interface for automation and batch processing. 
- **GUI (`ui/app.py`)**: Tkinter-based desktop application. Features a structured workspace layout with preview, workflow, queue snapshot, and activity log panels.

## 🛠️ External Dependencies

- **qpdf**: Merging and structural inspection.
- **Ghostscript (gs)**: PDF compression.
- **Tesseract OCR**: Text recognition (via `ocrmypdf`).

## Recent Implementation Notes

- **Pipeline Model**: Refactored processing to use a generic pipeline architecture, enabling multi-step workflows.
- **Sharded Cache**: Moved to a sharded manifest system (`manifests/shard_xx.json`) with auto-recovery for corrupt shards.
- **UI Polish**: Implemented spacing scale, typography hierarchy, and keyboard shortcuts. Fixed High-DPI blur on Windows.
- **Robust Execution**: `CancellableCommand` now uses threaded I/O to prevent UI hangs and reliably capture tool errors.
- **Validation**: All 66 unit tests pass on the local machine.
