# Comparison and report contract, v1

Input is a regular file with one header record. Both files use the same explicit
delimiter and encoding; defaults are comma and `utf-8-sig`. No dialect detection,
trimming, case folding, missing-value inference, locale conversion, or Unicode
normalization occurs. CSV uses Python's strict Excel dialect (double-quoted fields,
doubled embedded quotes). Line endings and quoted multiline cells are supported.
Blank records, duplicate headers, edge whitespace in headers, ragged rows and NUL
characters are rejected. Header-only files are valid empty tables.

All key, numeric and ignored selections must be distinct and present in both headers.
Keys are exact tuples of strings; an empty or all-whitespace component is invalid.
Duplicate keys invalidate the entire comparison, even when all cell values match.

Numeric cells and tolerance strings accept only signed ASCII decimal/scientific
notation, at most 256 characters with a decimal tuple exponent in [-1000, 1000].
Whitespace, separators, underscores, nonfinite numbers and empty strings are invalid.
All selected numeric cells are validated, including records that exist in only one
input. Key columns cannot also be numeric or ignored. Nonzero tolerances require at
least one numeric selection. Tolerances must be nonnegative.

Numerical equality uses:

```text
abs(a-b) <= max(abs_tol, rel_tol * max(abs(a), abs(b)))
```

Decimal arithmetic uses an independent local context with 5000 digits of precision
and exponent limits of -999999 to 999999, enough for exact operations within the
supported operand bounds. The caller's precision, exponent limits and signal traps
do not affect comparison results; its context settings and flags remain unchanged.
Relative tolerance is a fraction, symmetric between inputs; zero has no relative
allowance when both values are zero. No binary floating-point conversion occurs.

Numeric cells whose strings differ but satisfy equality increment
`numeric_equivalent_cells`. Cells outside tolerance increment `changed_cells` and
make their matched row a changed row. A matched row is counted once regardless of
how many cells changed. Ignored cells are not compared. Added/removed columns always
affect status; their cell contents are not individually compared.

## Report

All output is JSON-compatible and contains `schema_version: 1`:

| Field | Meaning |
| --- | --- |
| `status` | `equal` or `different` under the specified policy |
| `values_included` | Whether explicit `show_values` was enabled |
| `policy` | Exact key/numeric/ignored selections, tolerances, delimiter, encoding |
| `summary` | Input row counts, added/removed/changed/unchanged rows, changed/equivalent cells |
| `schema` | Sorted added and removed header names |
| `details` | Bounded added/removed row or changed cell events |
| `details_omitted` | Total events minus emitted events; counts remain complete |

Events have `kind`, `before_record`, and `after_record`. Absent records are null.
Changed-cell events also have `column`. Only with `show_values=True` do they contain
`key`, `before_value`, `after_value`, or (for additions/removals) `values`.
Reports never include input filenames or full paths. Column names and policy
selections are visible by design; counts and record locations can also be sensitive.

Record numbers are logical CSV record numbers including the header. They are not
physical line numbers when quoted cells contain newlines. Events follow baseline
record order, shared columns in sorted order, then new-only records in candidate
order. Repeated comparisons of the same inputs and policy are deterministic. Changing
row order may change record locations and event order, but not equality/counts.

The default detail cap is 100, with a supported range of 0..10000. It affects emitted
events only. Each file is bounded by 25 MiB, 100000 records, 256 columns and 16384
characters per cell. `max_rows` may lower the row cap. Inputs are loaded into memory;
limits constrain input size, not a guaranteed maximum resident memory allocation.

## Errors

The CLI sends JSON `{schema_version: 1, status: "invalid", code, message}` to stderr
and exits 2. It emits no partial success report. Runtime messages omit all cell
values, selected header names, filenames and system exception messages. Argument
errors likewise avoid echoing invalid tokens. `--help` and `--version` are normal
argparse exits. Output/pipe failures can exit 2 without a structured input error.

| Code | Category |
| --- | --- |
| `CL_ARGUMENT` | Invalid command line |
| `CL_CONFIG` | Invalid or overlapping column policy, delimiter, encoding or limits |
| `CL_TOLERANCE` | Negative tolerance |
| `CL_READ` | File read or decoding failure |
| `CL_FILE` | Nonregular file |
| `CL_LIMIT` | File, row, column or cell limit exceeded |
| `CL_HEADER` | Empty, duplicate or ambiguous headers |
| `CL_COLUMN` | Selected column absent |
| `CL_KEY` | Empty or duplicate record identity |
| `CL_CSV` | Invalid CSV structure or NUL character |
| `CL_NUMERIC` | Invalid finite decimal cell or argument |

CSV parser failures may include a physical line number. Row validation failures use
logical record numbers. Neither kind includes the rejected content.
