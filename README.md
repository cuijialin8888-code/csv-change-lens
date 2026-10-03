# csv-change-lens

[![CI](https://github.com/cuijialin8888-code/csv-change-lens/actions/workflows/ci.yml/badge.svg)](https://github.com/cuijialin8888-code/csv-change-lens/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Review changes between two CSV exports without putting their cell values into your logs.
Match records by explicit keys, select numerical columns deliberately, and apply decimal
tolerances. Runs offline, reads only the two supplied files, and has no runtime dependencies.

[中文说明](README.zh-CN.md) · [Comparison rules](docs/semantics.md) · [Security](SECURITY.md)

## A small example

The synthetic examples contain temperature measurements. Rows are reordered, two readings
move within a 0.1 °C tolerance, one sample changes, and one sample is added.

```console
python -m csv_change_lens examples/before.csv examples/after.csv --key sample_id --key replicate --numeric temperature_c --abs-tol 0.1
```

```text
CSV comparison: different
Rows: +1 -0 changed=1 unchanged=2
Cells: changed=2 numeric-equivalent=2
Values included: false
```

Detail events identify the CSV record and changed column. Key and cell values are omitted.
Add `--show-values` when you intentionally want them in the report.

## Install

Requires Python 3.10 or newer on Windows, Linux, or macOS.

Install from a checkout:

```console
python -m pip install .
csv-change-lens --help
```

Or download the wheel from [GitHub Releases](https://github.com/cuijialin8888-code/csv-change-lens/releases)
and install it offline:

```console
python -m pip install --no-index --no-deps csv_change_lens-0.1.0-py3-none-any.whl
```

This project is not currently published on PyPI. A wheel contains the CLI and library;
the source archive also includes tests and examples.

## Common commands

```console
# Plain text comparison; text and identifiers remain exact
csv-change-lens baseline.csv candidate.csv --key sample_id

# Composite key, explicit numeric column, 0.5 absolute or 1% relative tolerance
csv-change-lens baseline.csv candidate.csv --key sample_id --key replicate --numeric temperature_c --abs-tol 0.5 --rel-tol 0.01

# TSV; encoding and delimiter are explicit, never guessed
csv-change-lens baseline.tsv candidate.tsv --key sample_id --delimiter tab --encoding utf-16

# Machine-readable report; detail cap does not alter counts or exit status
csv-change-lens baseline.csv candidate.csv --key sample_id --format json --max-details 20

# Ignore cell changes in a timestamp column present in both files
csv-change-lens baseline.csv candidate.csv --key sample_id --ignore exported_at

# Markdown suitable for a review; redirects are performed by your shell
csv-change-lens baseline.csv candidate.csv --key sample_id --format markdown > review.md
```

Exit codes: **0** = equal under the selected policy; **1** = differences found;
**2** = invalid input or configuration. Errors are JSON on stderr. A difference is a
normal review result; shell wrappers should distinguish exit code 1 from input failure.

## Rules you can inspect

| Decision | Behavior |
| --- | --- |
| Record identity | One or more explicit `--key` headers; exact composite tuples |
| Duplicate or blank keys | Reject the comparison; do not pair ambiguous rows |
| Numbers | Only columns named with `--numeric`; finite ASCII decimal grammar |
| Tolerance | `abs(a-b) <= max(abs_tol, rel_tol * max(abs(a), abs(b)))` |
| Everything else | Exact text, including whitespace and leading zeros |
| Reordering | Row and header order do not change the equality result |
| Schema | Added/removed headers are differences, even with no data rows |
| Ignored columns | Suppress cell changes only; headers must exist in both inputs |
| Missing measurements | Empty or nonnumeric cells in numeric columns are errors |
| Default report | Counts, column names, logical record numbers; no keys/cell values/paths |
| Resource bounds | 25 MiB, 100,000 rows, 256 columns per input; 16,384 characters per cell |

Numeric formatting changes and measurements within tolerance are counted as
`numeric_equivalent_cells`. The report makes these visible even though they do not
cause a difference. The selected tolerance is a review policy, not a statistical test.

Column additions/removals are reported separately. `unchanged_rows` means unchanged
among shared, nonignored, nonkey columns; it does not imply an unchanged schema.

## Library

```python
from csv_change_lens import compare_files, InputError

report = compare_files(
    "baseline.csv", "candidate.csv",
    keys=("sample_id", "replicate"),
    numeric=("temperature_c",),
    abs_tol="0.1",  # decimal string, not a binary floating-point number
)
assert report["schema_version"] == 1
```

`InputError` exposes a stable `code` and a message that omits input paths and cell
values. [Report and error definitions](docs/semantics.md) describe the v1 contract.

## Scope and alternatives

This is a bounded in-memory review tool for small and medium CSV exports. It does not
edit files, patch datasets, infer keys, normalize Unicode, convert units, compare
Excel workbooks, or perform statistical inference. File reads may update access times
according to the operating system. It is not a sandbox for hostile filesystem races.

Established alternatives include [simonw/csv-diff](https://github.com/simonw/csv-diff)
for CSV/JSON record diffs and [wrinfotel/csvdiff](https://github.com/wrinfotel/csvdiff)
for numerical CSV comparisons. This implementation focuses on value-hidden reports,
explicit column policies, rejecting ambiguous keys, and decimal boundary behavior.
Its implementation and tests are original; no source code from those projects is included.

## Development

```console
python -m pip install -e .
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

CI runs Python 3.10 and 3.14 on Windows, Linux, and macOS. A separate job builds the
wheel and source distribution, runs tests against the installed wheel, and checks
that source archives include the tests and examples. See [CONTRIBUTING.md](CONTRIBUTING.md).

MIT licensed. Version 0.1.0 is an initial release; feedback with synthetic CSVs is welcome.
