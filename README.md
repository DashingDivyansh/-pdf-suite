# pdf-suite

A high-performance Python PDF utility for merging, compressing, and OCR, featuring both CLI and GUI modes.

For a detailed architectural overview, see the [Project Map](PROJECT_MAP.md).

The app uses Python as the orchestration layer and delegates PDF work to native tools where needed:

- `qpdf` for merge operations
- Ghostscript for compression
- **PyMuPDF** (Python package) for first-page thumbnails in the GUI and fast “already has text?” checks used to skip OCR
- **ocrmypdf** (Python package, uses Tesseract) for OCR

## Features

- Merge multiple PDFs in order
- Merge selected page ranges from PDFs
- Compress one PDF or a batch of PDFs
- Smart OCR logic: Automatically skips OCR if a file already contains searchable text
- Drag and drop files in the desktop UI
- First-page thumbnail when you select a file in the list
- Reorder selected files for merge
- Drag files in the list to reorder them
- Remove or clear selected files
- Select output folders from the UI
- Choose compression with simple Level 1 to Level 5 controls
- See original size, compressed size, and saved percentage after compression
- View basic PDF info: size, page count, encryption status
- Save recent files and output folder
- Confirm before overwriting output files
- Save the progress log
- Open the output folder
- Prompt for a password only when an encrypted PDF is detected
- Cancel a running compression task
- Buttons are disabled while a task is running
- CLI support for automation and batch work

## Requirements

- Python 3.11+
- qpdf
- Ghostscript
- Tesseract OCR (used by ocrmypdf)
- Python packages from `requirements.txt` (includes PyMuPDF, ocrmypdf, Pillow, etc.)

Install Python dependencies:

```bash
pip install -r requirements.txt
```

By default, the app expects these Windows paths:

```text
C:\Program Files\qpdf 12.3.2\bin\qpdf.exe
C:\Program Files\gs\gs10.07.0\bin\gswin64c.exe
```

You can override them with environment variables:

```powershell
$env:PDF_TOOL_QPDF_PATH = "C:\path\to\qpdf.exe"
$env:PDF_TOOL_GS_PATH = "C:\path\to\gswin64c.exe"
$env:PDF_TOOL_TESSERACT_PATH = "C:\path\to\tesseract.exe"
$env:PDF_TOOL_OUTPUT_DIR = "output"
```

## CLI Usage

Merge PDFs:

```bash
python main.py merge a.pdf b.pdf c.pdf -o merged.pdf
```

Merge selected page ranges:

```bash
python main.py merge a.pdf b.pdf -o merged.pdf --ranges "1-3" "2,5-7"
```

Compress one PDF:

```bash
python main.py compress input.pdf -o compressed.pdf --level 3
```

Compress many PDFs:

```bash
python main.py compress-many "*.pdf" --out-dir output --level 5 --workers 4
```

By default each output file uses the same base name as the input (`--template "{name}.pdf"`). Override with `--template` only when you want a different naming pattern.

Use an output filename template:

```bash
python main.py compress-many "*.pdf" --out-dir output --template "{name}_level_{level}.pdf"
```

OCR a PDF (writes under the output folder using the default template):

```bash
python main.py ocr scanned.pdf --out-dir output
```

Detect text (for OCR skipping):

```bash
python main.py detect_text input.pdf
```



Show PDF info:

```bash
python main.py info input.pdf
```

For encrypted PDFs, pass a password where supported:

```bash
python main.py merge locked.pdf a.pdf --password "secret" -o out.pdf
```

Compression levels:

- `1` - least compression, highest quality
- `2` - light compression
- `3` - balanced
- `4` - strong compression
- `5` - most compression, smallest size

## GUI Usage

Launch the desktop app:

```bash
python ui/app.py
```

The GUI supports:

- drag and drop PDF loading
- selected file list
- remove, clear, move up, and move down controls
- drag-to-reorder in the selected file list
- merge, compress, and OCR actions (primary row); output folder and cancel on the second row
- output folder selection
- compression level selection
- optional page-range prompts when you choose Merge
- password prompt only when an encrypted PDF is detected
- PDF Info dialog for the selected file
- open output folder
- save log
- overwrite confirmation
- recent output folder and selected files
- compression result summaries
- cancellation for running compression tasks
- **batch presets**: choose compression level and tick **Include OCR (for new presets)** to capture “compress” or “compress + OCR”; use **Save Preset…**, then load PDFs and **Run Preset**. Outputs use `processed_{name}.pdf` in your output folder. Presets are stored in settings and persist across restarts.

Page range examples:

- `1-3`
- `5`
- `2-4,8,10-12`

For merge ranges in the GUI, separate each file's ranges with `|`, for example:

```text
1-3|2,5-7|
```

The empty final range means the third file uses all pages.

## Build EXE

Install dependencies first:

```powershell
pip install -r requirements.txt
```

Build the desktop app with PyInstaller:

```powershell
.\build_exe.ps1
```

The executable is created under `dist/`.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Tests


Run unit tests:

```bash
python -m unittest discover -s tests
```

The current tests mock the external tool calls, so they validate command construction and basic validation without requiring qpdf or Ghostscript to process real PDFs.

Optional integration tests can run real qpdf and Ghostscript operations when the tools are available and `test_files/` sample PDFs exist in the project root:

```powershell
$env:PDF_TOOL_RUN_INTEGRATION = "1"
python -m unittest tests.test_integration_optional
```

## Project Structure

```text
pdf_tool/
core/
  compress.py
  executor.py
  info.py
  logger.py
  merge.py
  mupdf_tools.py
  ocr.py
  output.py
  ranges.py
  settings.py
  validator.py
  validation.py
tests/
  test_compress.py
  test_executor.py
  test_integration_optional.py
  test_main.py
  test_merge.py
  test_ranges_output.py
  test_validation.py
ui/
  app.py
build_exe.ps1
config.py
main.py
pdf_tool.spec
requirements.txt
README.md
```
