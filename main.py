import argparse
import glob
import os

from config import DEFAULT_OUTPUT_DIR
from core.compress import COMPRESSION_LEVEL_LABELS, COMPRESSION_LEVELS, compress_many, compress_pdf
from core.info import pdf_info
from core.merge import merge_pdfs
from core.ocr import ocr_pdf
from core.mupdf_tools import has_text
from core.validator import check_dependencies


def expand_inputs(inputs):
    files = []
    for item in inputs:
        if any(char in item for char in "*?[]"):
            expanded = glob.glob(item)
            files.extend([f for f in expanded if f.lower().endswith(".pdf")])
        else:
            files.append(item)
    return files


def build_parser():
    level_help = "Compression level: 1 is least compression/highest quality, 5 is most compression/smallest size."
    parser = argparse.ArgumentParser(
        description="Merge, compress, and OCR PDFs using qpdf, Ghostscript, and ocrmypdf.",
        epilog="Compression levels: " + "; ".join(COMPRESSION_LEVEL_LABELS.values()),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    merge_parser = subparsers.add_parser("merge", help="Merge two or more PDFs.")
    merge_parser.add_argument("files", nargs="+", help="Input PDF files in merge order.")
    merge_parser.add_argument("-o", "--output", required=True, help="Output merged PDF path.")
    merge_parser.add_argument(
        "--ranges",
        nargs="*",
        help="Optional page ranges per input, such as '1-3' '2,5-7'. Omit entries for whole files.",
    )
    merge_parser.add_argument("--password", help="Password for encrypted input PDFs.")

    compress_parser = subparsers.add_parser("compress", help="Compress one PDF.")
    compress_parser.add_argument("input", help="Input PDF file.")
    compress_parser.add_argument("-o", "--output", required=True, help="Output compressed PDF path.")
    compress_parser.add_argument("--password", help="Password for encrypted input PDF.")
    compress_parser.add_argument(
        "-l",
        "--level",
        choices=COMPRESSION_LEVELS,
        default="3",
        help=level_help,
    )

    batch_parser = subparsers.add_parser("compress-many", help="Compress multiple PDFs.")
    batch_parser.add_argument("files", nargs="+", help="Input PDF files or wildcard patterns.")
    batch_parser.add_argument("-o", "--out-dir", default=DEFAULT_OUTPUT_DIR, help="Output folder.")
    batch_parser.add_argument(
        "--template",
        default="{name}.pdf",
        help="Output filename template. Available fields: {name}, {ext}, {level}. Default keeps input basename.",
    )
    batch_parser.add_argument("--password", help="Password for encrypted input PDFs.")
    batch_parser.add_argument(
        "-l",
        "--level",
        choices=COMPRESSION_LEVELS,
        default="3",
        help=level_help,
    )
    batch_parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=None,
        help="Number of parallel workers. Defaults to CPU count.",
    )

    ocr_parser = subparsers.add_parser("ocr", help="Add OCR text layer to a scanned PDF.")
    ocr_parser.add_argument("input", help="Input PDF file.")
    ocr_parser.add_argument("-o", "--out-dir", default=DEFAULT_OUTPUT_DIR, help="Output folder.")
    ocr_parser.add_argument(
        "--template",
        default="ocr_{name}.pdf",
        help="Output filename template. Available fields: {name}, {ext}.",
    )

    info_parser = subparsers.add_parser("info", help="Show basic PDF information.")
    info_parser.add_argument("input", help="Input PDF file.")
    info_parser.add_argument("--password", help="Password for encrypted input PDF.")

    detect_parser = subparsers.add_parser("detect_text", help="Detect if a PDF has selectable text.")
    detect_parser.add_argument("input", help="Input PDF file.")

    return parser


def run(args):
    check_dependencies()

    if args.command == "merge":
        result = merge_pdfs(args.files, args.output, page_ranges=args.ranges, password=args.password)
        print(result)
        return 0 if result == "SUCCESS" else 1

    if args.command == "compress":
        result = compress_pdf(args.input, args.output, args.level, include_summary=True, password=args.password)
        print(result)
        return 0 if result.startswith("SUCCESS") else 1

    if args.command == "compress-many":
        files = expand_inputs(args.files)
        if not files:
            print("ERROR: No valid input files found")
            return 1

        os.makedirs(args.out_dir, exist_ok=True)
        results = compress_many(
            files,
            level=args.level,
            max_workers=args.workers,
            output_dir=args.out_dir,
            output_template=args.template,
            password=args.password,
        )

        for file_path, output, status in results:
            print(f"{file_path} -> {output} : {status}")

        success = sum(1 for _, _, status in results if status.startswith("SUCCESS"))
        fail = len(results) - success
        print(f"\nSummary: {success} success, {fail} failed")
        return 0 if fail == 0 else 1

    if args.command == "ocr":
        result = ocr_pdf(
            args.input,
            output_dir=args.out_dir,
            output_template=args.template,
        )
        print(result)
        return 0 if result == "SUCCESS" else 1

    if args.command == "info":
        info = pdf_info(args.input, password=args.password)
        if "error" in info:
            print(f"ERROR: {info['error']}")
            return 1
        print(f"Path: {info['path']}")
        print(f"Size: {info['size']} bytes")
        print(f"Pages: {info['pages'] if info['pages'] is not None else 'unknown'}")
        print(f"Encrypted: {'yes' if info['encrypted'] else 'no'}")
        return 0

    if args.command == "detect_text":
        result = has_text(args.input)
        print(result)
        return 0


    return 1


def main():
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(run(args))


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()
