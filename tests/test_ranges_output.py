import os
import unittest

from core.output import output_path, render_template
from core.ranges import parse_page_ranges


class RangeAndOutputTests(unittest.TestCase):
    def test_parse_page_ranges_splits_comma_separated_values(self):
        self.assertEqual(parse_page_ranges("1-3, 5"), ["1-3", "5"])

    def test_parse_page_ranges_supports_z_as_last_page_placeholder(self):
        self.assertEqual(parse_page_ranges("1-z"), ["1-z"])
        self.assertEqual(parse_page_ranges("z"), ["z"])
        self.assertEqual(parse_page_ranges("3, 5-z"), ["3", "5-z"])

    def test_parse_page_ranges_rejects_invalid_numeric_range_ordering(self):
        with self.assertRaisesRegex(ValueError, "Invalid page range"):
            parse_page_ranges("5-2")

    def test_parse_page_ranges_rejects_non_numeric_and_non_z_input(self):
        with self.assertRaisesRegex(ValueError, "Invalid page range"):
            parse_page_ranges("1-x")
        with self.assertRaisesRegex(ValueError, "Invalid page number"):
            parse_page_ranges("abc")

    def test_render_template_prevents_path_traversal_via_input_name(self):
        # Even if name is suspicious, it should be treated as a stem or fallback
        # In our implementation, path.stem for "../../etc/passwd" is "passwd"
        self.assertEqual(render_template("{name}.pdf", "../../etc/passwd"), "passwd.pdf")
        
        # Verify it doesn't try to use directory components from the name in the final output
        # If template is "{name}", and name is "../x", render_template returns "x.pdf" (stem)
        self.assertEqual(render_template("{name}", "../evil"), "evil.pdf")

if __name__ == "__main__":
    unittest.main()
