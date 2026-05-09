import os
import unittest

from core.output import output_path, render_template
from core.ranges import parse_page_ranges


class RangeAndOutputTests(unittest.TestCase):
    def test_parse_page_ranges(self):
        self.assertEqual(parse_page_ranges("1-3, 5"), ["1-3", "5"])

    def test_parse_page_ranges_rejects_invalid_range(self):
        with self.assertRaises(ValueError):
            parse_page_ranges("5-2")

    def test_render_template_adds_pdf_extension(self):
        self.assertEqual(render_template("{name}_x", "report.pdf"), "report_x.pdf")

    def test_output_path_uses_template_values(self):
        self.assertEqual(
            output_path("out", "{name}_level_{level}.pdf", "report.pdf", level="5"),
            os.path.join("out", "report_level_5.pdf"),
        )


if __name__ == "__main__":
    unittest.main()
