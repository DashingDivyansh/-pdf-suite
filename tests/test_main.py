import unittest
from unittest.mock import patch

from config import DEFAULT_OUTPUT_DIR
from main import build_parser, expand_inputs, run


class MainCliTests(unittest.TestCase):
    def test_parser_accepts_compress_level(self):
        args = build_parser().parse_args(
            ["compress", "input.pdf", "-o", "output.pdf", "--level", "5"]
        )

        self.assertEqual(args.command, "compress")
        self.assertEqual(args.level, "5")

    @patch("main.glob.glob", return_value=["a.pdf", "b.pdf"])
    def test_expand_inputs_expands_wildcards(self, _glob):
        self.assertEqual(expand_inputs(["*.pdf", "c.pdf"]), ["a.pdf", "b.pdf", "c.pdf"])

    @patch("main.check_dependencies")
    @patch("main.compress_pdf", return_value="SUCCESS")
    @patch("builtins.print")
    def test_run_compress_returns_success_status(self, _print, compress_pdf, _check_dependencies):
        args = build_parser().parse_args(["compress", "in.pdf", "-o", "out.pdf", "--level", "3"])

        exit_code = run(args)

        self.assertEqual(exit_code, 0)
        compress_pdf.assert_called_once_with("in.pdf", "out.pdf", "3", include_summary=True, password=None)

    def test_removed_subcommands_not_in_parser(self):
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["preview", "a.pdf"])
        with self.assertRaises(SystemExit):
            parser.parse_args(["extract_text", "a.pdf", "-o", "out.txt"])

    def test_parser_merge_requires_output(self):
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["merge", "a.pdf", "b.pdf"])

    def test_parser_merge_accepts_ranges(self):
        args = build_parser().parse_args(
            ["merge", "a.pdf", "b.pdf", "-o", "out.pdf", "--ranges", "1-3", "2-7"]
        )
        self.assertEqual(args.command, "merge")
        self.assertEqual(args.ranges, ["1-3", "2-7"])

    def test_parser_compress_many_defaults(self):
        args = build_parser().parse_args(["compress-many", "a.pdf"])
        self.assertEqual(args.command, "compress-many")
        self.assertEqual(args.out_dir, DEFAULT_OUTPUT_DIR)
        self.assertEqual(args.level, "3")
        self.assertEqual(args.workers, None)
        self.assertEqual(args.template, "{name}.pdf")

    def test_parser_ocr_defaults(self):
        args = build_parser().parse_args(["ocr", "scan.pdf"])
        self.assertEqual(args.command, "ocr")
        self.assertEqual(args.out_dir, DEFAULT_OUTPUT_DIR)
        self.assertEqual(args.template, "ocr_{name}.pdf")

    def test_parser_info_and_detect_text(self):
        info_args = build_parser().parse_args(["info", "x.pdf", "--password", "pw"])
        self.assertEqual(info_args.command, "info")
        self.assertEqual(info_args.password, "pw")

        detect_args = build_parser().parse_args(["detect_text", "y.pdf"])
        self.assertEqual(detect_args.command, "detect_text")
        self.assertEqual(detect_args.input, "y.pdf")

    @patch("main.check_dependencies")
    @patch("main.has_text", return_value=True)
    @patch("builtins.print")
    def test_run_detect_text(self, mock_print, _has_text, _check_dependencies):
        args = build_parser().parse_args(["detect_text", "in.pdf"])

        exit_code = run(args)

        self.assertEqual(exit_code, 0)
        mock_print.assert_called_once_with(True)

    @patch("main.check_dependencies")
    @patch("main.merge_pdfs", return_value="SUCCESS")
    @patch("builtins.print")
    def test_run_merge_success(self, _print, merge_pdfs, _check_dependencies):
        args = build_parser().parse_args(["merge", "a.pdf", "-o", "m.pdf"])

        exit_code = run(args)

        self.assertEqual(exit_code, 0)
        merge_pdfs.assert_called_once_with(
            ["a.pdf"], "m.pdf", page_ranges=None, password=None
        )


if __name__ == "__main__":
    unittest.main()
