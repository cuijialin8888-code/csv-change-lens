import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from decimal import ROUND_DOWN, Subnormal, localcontext
from pathlib import Path
from unittest.mock import patch

from csv_change_lens import InputError, compare_files
from csv_change_lens.cli import main, render


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.before = Path(self.temp.name) / "before.csv"
        self.after = Path(self.temp.name) / "after.csv"

    def files(self, before, after, encoding="utf-8"):
        self.before.write_text(before, encoding=encoding, newline="")
        self.after.write_text(after, encoding=encoding, newline="")

    def compare(self, **kwargs):
        return compare_files(self.before, self.after, keys=("id",), **kwargs)

    def invalid(self, before, after, code, **kwargs):
        self.files(before, after)
        with self.assertRaises(InputError) as caught:
            self.compare(**kwargs)
        self.assertEqual(caught.exception.code, code)
        return str(caught.exception)

    def test_row_and_column_reorder(self):
        self.files("id,x,y\n1,a,b\n2,c,d\n", "y,id,x\nd,2,c\nb,1,a\n")
        result = self.compare()
        self.assertEqual(result["status"], "equal")
        self.assertEqual(result["summary"]["unchanged_rows"], 2)

    def test_complete_change_counts(self):
        self.files("id,x,y\n1,a,b\n2,c,d\n", "id,x,y\n1,A,B\n3,e,f\n")
        result = self.compare()
        counts = result["summary"]
        self.assertEqual([counts[k] for k in ("added_rows", "removed_rows", "changed_rows", "changed_cells")], [1, 1, 1, 2])
        self.assertEqual([i["kind"] for i in result["details"]], ["changed", "changed", "removed", "added"])

    def test_composite_keys_have_no_join_collisions(self):
        self.files('id,rep,x\n"a,b",c,1\na,"b,c",2\n', 'id,rep,x\na,"b,c",2\n"a,b",c,1\n')
        result = compare_files(self.before, self.after, keys=("id", "rep"))
        self.assertEqual(result["status"], "equal")

    def test_text_numeric_appearance_is_exact_by_default(self):
        self.files("id,x\n001,1.00\n", "id,x\n001,1\n")
        self.assertEqual(self.compare()["status"], "different")
        result = self.compare(numeric=("x",))
        self.assertEqual(result["status"], "equal")
        self.assertEqual(result["summary"]["numeric_equivalent_cells"], 1)

    def test_key_leading_zeros_are_preserved(self):
        self.files("id,x\n001,a\n", "id,x\n1,a\n")
        result = self.compare()
        self.assertEqual(result["summary"]["added_rows"], 1)
        self.assertEqual(result["summary"]["removed_rows"], 1)

    def test_absolute_tolerance_boundary_uses_decimal(self):
        self.files("id,x\n1,0.1\n", "id,x\n1,0.3\n")
        self.assertEqual(self.compare(numeric=("x",), abs_tol="0.2")["status"], "equal")
        self.assertEqual(self.compare(numeric=("x",), abs_tol="0.199999999999999999999999999999")["status"], "different")

    def test_relative_tolerance_is_symmetric(self):
        self.files("id,x\n1,-100\n", "id,x\n1,-101\n")
        result = self.compare(numeric=("x",), rel_tol="0.01")
        reverse = compare_files(self.after, self.before, keys=("id",), numeric=("x",), rel_tol="0.01")
        self.assertEqual(result["status"], "equal")
        self.assertEqual(reverse["status"], result["status"])

    def test_zero_and_scientific_notation(self):
        self.files("id,x\n1,-0\n2,1e-1000\n", "id,x\n1,0.0\n2,0.1e-999\n")
        self.assertEqual(self.compare(numeric=("x",))["status"], "equal")

    def test_large_precision_does_not_round_difference_away(self):
        self.files("id,x\n1,1000000000000000000000000000000\n", "id,x\n1,1000000000000000000000000000001\n")
        self.assertEqual(self.compare(numeric=("x",))["status"], "different")

    def test_numeric_comparison_is_independent_of_caller_decimal_context(self):
        cases = [
            ("1e1000", "2e1000", "1e1000", "0", "equal"),
            ("1e1000", "2e1000", "0", "0.5", "equal"),
            ("1e-1000", "2e-1000", "0", "0", "different"),
            ("1e-1000", "2e-1000", "1e-1000", "0", "equal"),
        ]
        for before, after, absolute, relative, status in cases:
            with self.subTest(before=before, absolute=absolute, relative=relative):
                self.files(f"id,x\n1,{before}\n", f"id,x\n1,{after}\n")
                expected = self.compare(numeric=("x",), abs_tol=absolute, rel_tol=relative)
                with localcontext() as caller:
                    caller.prec = 2
                    caller.Emax = 2
                    caller.Emin = -2
                    caller.rounding = ROUND_DOWN
                    caller.clamp = 1
                    caller.clear_flags()
                    caller.traps[Subnormal] = True
                    original = caller.copy()
                    actual = self.compare(numeric=("x",), abs_tol=absolute, rel_tol=relative)
                    self.assertEqual(actual, expected)
                    self.assertEqual(actual["status"], status)
                    for attribute in ("prec", "Emax", "Emin", "rounding", "clamp", "flags", "traps"):
                        self.assertEqual(getattr(caller, attribute), getattr(original, attribute))

    def test_invalid_numeric_in_added_removed_or_equal_rows(self):
        for before, after in [("id,x\n", "id,x\n1,NaN\n"),
                              ("id,x\n1,Infinity\n", "id,x\n"),
                              ("id,x\n1,SECRET\n", "id,x\n1,SECRET\n")]:
            with self.subTest(before=before):
                message = self.invalid(before, after, "CL_NUMERIC", numeric=("x",))
                self.assertNotIn("SECRET", message)

    def test_numeric_grammar_and_exponent_limits(self):
        for value in ["", " 1", "1_000", "1,000", "1e1001", "1e-1001", "１２", "9" * 257]:
            with self.subTest(value=value):
                self.invalid(f'id,x\n1,"{value}"\n', "id,x\n1,0\n", "CL_NUMERIC", numeric=("x",))

    def test_invalid_tolerances(self):
        self.files("id,x\n1,1\n", "id,x\n1,1\n")
        for value in ["-0.1", "NaN", "Infinity", "1e99999"]:
            with self.subTest(value=value), self.assertRaises(InputError):
                self.compare(numeric=("x",), abs_tol=value)

    def test_nonzero_tolerance_requires_numeric_selection(self):
        self.files("id,x\n1,a\n", "id,x\n1,b\n")
        with self.assertRaises(InputError):
            self.compare(abs_tol="1")

    def test_default_reports_hide_keys_cells_and_paths(self):
        self.files("id,x\nSECRET_KEY,SECRET_OLD\nSECRET_REMOVE,SECRET_CELL\n", "id,x\nSECRET_KEY,SECRET_NEW\nSECRET_ADD,SECRET_CELL\n")
        result = self.compare()
        for fmt in ("text", "json", "markdown"):
            rendered = render(result, fmt)
            self.assertNotIn("SECRET", rendered)
            self.assertNotIn(str(self.before), rendered)
        self.assertFalse(result["values_included"])

    def test_show_values_is_explicit(self):
        self.files("id,x\nSECRET_KEY,old\n", "id,x\nSECRET_KEY,new\n")
        result = self.compare(show_values=True)
        self.assertEqual(result["details"][0]["key"], {"id": "SECRET_KEY"})
        self.assertEqual(result["details"][0]["before_value"], "old")
        self.assertEqual(result["details"][0]["after_value"], "new")

    def test_control_characters_and_markdown_are_inert(self):
        self.files('id,x\n1,"\x1b[31m<script>\n```"\n', "id,x\n1,new\n")
        result = self.compare(show_values=True)
        for fmt in ("text", "json", "markdown"):
            self.assertNotIn("\x1b", render(result, fmt))
        markdown = render(result, "markdown")
        self.assertTrue(all(line.startswith("    ") for line in markdown.splitlines()[2:]))

    def test_duplicate_key_is_rejected_without_leak(self):
        message = self.invalid("id,x\nSECRET,1\nSECRET,2\n", "id,x\n", "CL_KEY")
        self.assertNotIn("SECRET", message)
        self.assertIn("record 3", message)

    def test_empty_or_whitespace_key_is_rejected(self):
        for key in ["", " "]:
            with self.subTest(key=key):
                self.invalid(f"id,x\n{key},1\n", "id,x\n", "CL_KEY")

    def test_headers_are_strict(self):
        for header in ["", "id,id\n", "id,\n", "id, x\n", "id,x \n"]:
            with self.subTest(header=header):
                self.invalid(header, "id,x\n", "CL_HEADER")

    def test_missing_selected_column_and_overlapping_selections(self):
        self.files("id,x\n", "id,y\n")
        with self.assertRaises(InputError):
            self.compare(numeric=("x",))
        self.files("id,x\n", "id,x\n")
        for kwargs in [{"numeric": ("id",)}, {"ignored": ("id",)},
                       {"numeric": ("x",), "ignored": ("x",)}, {"numeric": ("x", "x")}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(InputError):
                self.compare(**kwargs)

    def test_schema_changes_always_count(self):
        self.files("id,x\n1,a\n", "id,x,new\n1,a,b\n")
        result = self.compare(ignored=("x",))
        self.assertEqual(result["status"], "different")
        self.assertEqual(result["schema"]["added_columns"], ["new"])
        self.assertEqual(result["summary"]["unchanged_rows"], 1)

    def test_ignore_only_suppresses_cell_changes(self):
        self.files("id,x\n1,a\n", "id,x\n1,b\n")
        self.assertEqual(self.compare(ignored=("x",))["status"], "equal")

    def test_ragged_blank_or_unterminated_rows(self):
        for row in ["1\n", "1,a,b\n", "\n", '1,"a\n']:
            with self.subTest(row=row):
                self.invalid("id,x\n" + row, "id,x\n", "CL_CSV")

    def test_multiline_csv_and_record_numbers(self):
        self.files('id,x\n1,"two\nlines"\n2,old\n', 'id,x\n1,"two\nlines"\n2,new\n')
        detail = self.compare()["details"][0]
        self.assertEqual(detail["before_record"], 3)
        self.assertEqual(detail["after_record"], 3)

    def test_bom_and_non_ascii_data(self):
        self.files("id,x\n样本一,中文\n", "id,x\n样本一,中文\n", encoding="utf-8-sig")
        self.assertEqual(self.compare()["status"], "equal")

    def test_tab_semicolon_and_utf16(self):
        for delim in ("\t", ";"):
            with self.subTest(delimiter=delim):
                self.files(f"id{delim}x\n1{delim}a\n", f"id{delim}x\n1{delim}a\n", encoding="utf-16")
                self.assertEqual(self.compare(delimiter=delim, encoding="utf-16")["status"], "equal")

    def test_nul_and_bad_encoding(self):
        self.invalid("id,x\n1,\x00\n", "id,x\n", "CL_CSV")
        self.before.write_bytes(b"id,x\n1,\xff\n")
        with self.assertRaises(InputError) as caught:
            self.compare()
        self.assertEqual(caught.exception.code, "CL_READ")

    def test_detail_limit_does_not_change_counts_or_status(self):
        self.files("id,x\n1,a\n2,b\n3,c\n", "id,x\n1,A\n2,B\n3,C\n")
        full = self.compare()
        for cap in (0, 1):
            result = self.compare(max_details=cap)
            self.assertEqual(result["summary"], full["summary"])
            self.assertEqual(result["status"], "different")
            self.assertEqual(len(result["details"]), cap)
            self.assertEqual(result["details_omitted"], 3 - cap)

    def test_resource_limits(self):
        self.files("id,x\n1,a\n2,b\n", "id,x\n")
        with self.assertRaises(InputError) as caught:
            self.compare(max_rows=1)
        self.assertEqual(caught.exception.code, "CL_LIMIT")
        with patch("csv_change_lens.core.MAX_BYTES", 4), self.assertRaises(InputError):
            self.compare()
        self.invalid("id,x\n1," + "a" * 16385 + "\n", "id,x\n", "CL_LIMIT")
        self.invalid(",".join(["id"] + [f"x{i}" for i in range(256)]) + "\n", "id,x\n", "CL_LIMIT")

    def test_invalid_configuration_ranges(self):
        for kwargs in [{"max_details": -1}, {"max_details": 10001}, {"max_rows": 0},
                       {"max_rows": 100001}, {"delimiter": "::"}, {"delimiter": '"'},
                       {"delimiter": "\n"}, {"encoding": "not-an-encoding"}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(InputError):
                self.compare(**kwargs)

    def test_missing_file_error_has_no_path(self):
        with self.assertRaises(InputError) as caught:
            self.compare()
        self.assertNotIn(str(self.before), str(caught.exception))
        self.assertEqual(caught.exception.code, "CL_READ")

    def test_directory_is_rejected(self):
        with self.assertRaises(InputError) as caught:
            compare_files(self.temp.name, self.temp.name, keys=("id",))
        self.assertEqual(caught.exception.code, "CL_FILE")

    def test_inputs_are_unchanged(self):
        self.files("id,x\n1,a\n", "id,x\n1,b\n")
        paths = (self.before, self.after)
        hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        self.compare(show_values=True)
        self.assertEqual(hashes, [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths])

    def test_deterministic_output(self):
        self.files("id,x,y\n1,a,b\n", "id,x,y\n1,c,d\n")
        self.assertEqual(render(self.compare(), "json"), render(self.compare(), "json"))

    def test_cli_exit_codes_and_json(self):
        self.files("id,x\n1,a\n", "id,x\n1,b\n")
        stdout, stderr = io.StringIO(), io.StringIO()
        argv = [str(self.before), str(self.after), "--key", "id", "--format", "json"]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            different = main(argv)
            equal = main([str(self.before), str(self.before), "--key", "id"])
            invalid = main(["PRIVATE_TOKEN"])
        self.assertEqual((equal, different, invalid), (0, 1, 2))
        self.assertEqual(json.loads(stdout.getvalue().split("\nCSV comparison:")[0])["status"], "different")
        self.assertNotIn("PRIVATE_TOKEN", stderr.getvalue())
        self.assertEqual(json.loads(stderr.getvalue())["code"], "CL_ARGUMENT")

    def test_cli_tab_and_error_output(self):
        self.files("id\tx\n1\t1.0\n", "id\tx\n1\t1\n")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main([str(self.before), str(self.after), "--key", "id", "--numeric", "x", "--delimiter", "tab"])
        self.assertEqual(code, 0)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = main([str(self.before), str(self.after), "--key", "id", "--abs-tol", "SECRET"])
        self.assertEqual(code, 2)
        self.assertNotIn("SECRET", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
