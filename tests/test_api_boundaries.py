"""Regression coverage for library configuration, resource and packaging boundaries."""

import contextlib
import csv
import io
import json
import tempfile
import unittest
from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch

from csv_change_lens import InputError, __version__, compare_files
from csv_change_lens.cli import main
from csv_change_lens.core import MAX_CELL_CHARS


class ApiBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.before = Path(self.temp.name) / "before.csv"
        self.after = Path(self.temp.name) / "after.csv"
        self.before.write_text("id,x\nSECRET_KEY,1.0\n", encoding="utf-8")
        self.after.write_text("id,x\nSECRET_KEY,1\n", encoding="utf-8")

    def compare(self, **kwargs):
        options = {"keys": ("id",)}
        options.update(kwargs)
        return compare_files(self.before, self.after, **options)

    def invalid_config(self, **kwargs):
        with patch("csv_change_lens.core._read_table") as read:
            with self.assertRaises(InputError) as caught:
                self.compare(**kwargs)
            read.assert_not_called()
        self.assertEqual(caught.exception.code, "CL_CONFIG")
        self.assertNotIn("SECRET", str(caught.exception))

    def test_show_values_rejects_non_boolean_opt_in(self):
        for value in ("false", "true", "", 0, 1, None, [], {}):
            with self.subTest(value=value):
                self.invalid_config(show_values=value)

    def test_row_and_detail_limits_reject_booleans_and_other_types(self):
        for name in ("max_rows", "max_details"):
            for value in (False, True, 1.0, "1", None):
                with self.subTest(name=name, value=value):
                    self.invalid_config(**{name: value})

    def test_selections_reject_bare_strings_and_invalid_iterables(self):
        for name in ("keys", "numeric", "ignored"):
            for value in ("id", b"id", None, 1, [["id"]], [" id"], ["id", "id"]):
                with self.subTest(name=name, value=value):
                    self.invalid_config(**{name: value})

    def test_selections_accept_lists_and_single_pass_iterators(self):
        report = self.compare(keys=iter(["id"]), numeric=["x"])
        self.assertEqual(report["status"], "equal")
        self.assertEqual(report["policy"]["keys"], ["id"])
        self.assertEqual(report["policy"]["numeric"], ["x"])
        self.assertEqual(report["summary"]["numeric_equivalent_cells"], 1)

    def test_encoding_is_validated_before_input_reads(self):
        for encoding in ("SECRET_CODEC", "base64_codec", "hex_codec", "undefined"):
            with self.subTest(encoding=encoding):
                self.invalid_config(encoding=encoding)

    def test_invalid_path_types_use_sanitized_read_errors(self):
        for path in (None, 123, b"SECRET_PATH"):
            for side in ("before", "after"):
                paths = {"before": self.before, "after": self.after}
                paths[side] = path
                with self.subTest(path=path, side=side):
                    with self.assertRaises(InputError) as caught:
                        compare_files(**paths, keys=("id",))
                    self.assertEqual(caught.exception.code, "CL_READ")
                    self.assertNotIn("SECRET", str(caught.exception))

    def test_maximum_cell_length_is_accepted(self):
        contents = "id,x\n1," + "a" * MAX_CELL_CHARS + "\n"
        self.before.write_text(contents, encoding="utf-8")
        self.after.write_text(contents, encoding="utf-8")
        self.assertEqual(self.compare()["status"], "equal")

    def test_csv_parser_limit_is_reported_as_resource_limit(self):
        previous = csv.field_size_limit()
        self.addCleanup(csv.field_size_limit, previous)
        csv.field_size_limit(MAX_CELL_CHARS + 1)
        self.before.write_text("id,x\n1," + "a" * (MAX_CELL_CHARS + 2) + "\n",
                               encoding="utf-8")
        with self.assertRaises(InputError) as caught:
            self.compare()
        self.assertEqual(caught.exception.code, "CL_LIMIT")
        self.assertEqual(csv.field_size_limit(), MAX_CELL_CHARS + 1)
        self.assertNotIn(str(self.before), str(caught.exception))

    def test_caller_csv_limit_is_preserved_and_cli_errors_are_sanitized(self):
        previous = csv.field_size_limit()
        self.addCleanup(csv.field_size_limit, previous)
        csv.field_size_limit(4)
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main([str(self.before), str(self.after), "--key", "id"])
        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(json.loads(stderr.getvalue())["code"], "CL_LIMIT")
        self.assertNotIn("SECRET", stderr.getvalue())
        self.assertNotIn(str(self.before), stderr.getvalue())
        self.assertEqual(csv.field_size_limit(), 4)


class DistributionTests(unittest.TestCase):
    def test_installed_metadata_library_and_cli_versions_agree(self):
        self.assertEqual(version("csv-change-lens"), __version__)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as caught:
                main(["--version"])
        self.assertEqual(caught.exception.code, 0)
        self.assertEqual(stdout.getvalue().strip(), __version__)


if __name__ == "__main__":
    unittest.main()
