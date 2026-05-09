import os


def is_pdf_path(path):
    return str(path).lower().endswith(".pdf")


def validate_pdf_file(path):
    if not path:
        return "No file selected"
    if not is_pdf_path(path):
        return f"Not a PDF file -> {path}"
    if not os.path.exists(path):
        return f"File not found -> {path}"
    if os.path.getsize(path) == 0:
        return f"File is empty (0 bytes) -> {path}"
    return None

def validate_pdf_files(files, minimum=1):
    if not files or len(files) < minimum:
        return f"At least {minimum} PDF file(s) are required"

    for file_path in files:
        error = validate_pdf_file(file_path)
        if error:
            return error

    return None


def validate_output_pdf(input_files, output_file):
    if not output_file:
        return "No output file selected"
    if not is_pdf_path(output_file):
        return f"Output file must be a PDF -> {output_file}"

    output_abs = os.path.abspath(output_file)
    for input_file in input_files:
        if os.path.abspath(input_file) == output_abs:
            return "Output file cannot overwrite an input file"

    output_dir = os.path.dirname(output_abs)
    if output_dir and os.path.exists(output_dir):
        if not os.access(output_dir, os.W_OK):
            return f"Output directory is not writable -> {output_dir}"

    return None
