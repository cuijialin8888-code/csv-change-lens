"""Strict, bounded CSV loading and deterministic keyed comparisons."""

from __future__ import annotations

import csv
import io
import os
import re
import stat
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

MAX_BYTES = 25 * 1024 * 1024
MAX_ROWS = 100_000
MAX_COLUMNS = 256
MAX_CELL_CHARS = 16_384
MAX_DETAILS = 10_000
NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")


class InputError(ValueError):
    """An error whose message contains no file paths or input cell values."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class Row:
    record: int
    values: dict[str, str]


@dataclass
class Table:
    columns: list[str]
    rows: dict[tuple[str, ...], Row]


def parse_decimal(text: str) -> Decimal:
    """ASCII decimal grammar only; bounded exponents and finite values."""
    if not isinstance(text, str) or len(text) > 256 or not NUMBER.fullmatch(text):
        raise InputError("CL_NUMERIC", "expected a finite ASCII decimal number")
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise InputError("CL_NUMERIC", "expected a finite ASCII decimal number") from None
    if not value.is_finite() or abs(value.as_tuple().exponent) > 1000:
        raise InputError("CL_NUMERIC", "decimal exponent exceeds the supported range")
    return value


def tolerance(text: str) -> Decimal:
    value = parse_decimal(text)
    if value < 0:
        raise InputError("CL_TOLERANCE", "tolerances must be nonnegative")
    return value


def numerically_equal(a: Decimal, b: Decimal, absolute: Decimal, relative: Decimal) -> bool:
    # Allowed operands have <=256 digits and |exponent|<=1000. This precision
    # preserves subtraction and tolerance multiplication without binary floats.
    with localcontext() as context:
        context.prec = 5000
        return abs(a - b) <= max(absolute, relative * max(abs(a), abs(b)))


def _names(names: tuple[str, ...], *, required: bool = False) -> None:
    if required and not names:
        raise InputError("CL_CONFIG", "at least one key column is required")
    if any(not isinstance(name, str) or not name or name != name.strip() for name in names):
        raise InputError("CL_CONFIG", "column selections must be nonempty exact header names")
    if len(set(names)) != len(names):
        raise InputError("CL_CONFIG", "duplicate column selections are not allowed")


def _read_table(path: str | Path, side: str, keys: tuple[str, ...],
                numeric: tuple[str, ...], ignored: tuple[str, ...],
                delimiter: str, encoding: str, max_rows: int) -> Table:
    try:
        target = Path(path)
        if not stat.S_ISREG(target.stat().st_mode):
            raise InputError("CL_FILE", f"{side}: input must be a regular file")
        if target.stat().st_size > MAX_BYTES:
            raise InputError("CL_LIMIT", f"{side}: file exceeds the 25 MiB limit")
        with target.open("rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise InputError("CL_FILE", f"{side}: input must be a regular file")
            payload = stream.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            raise InputError("CL_LIMIT", f"{side}: file exceeds the 25 MiB limit")
        decoded = payload.decode(encoding)
    except (OSError, ValueError, LookupError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError("CL_READ", f"{side}: cannot read or decode input") from None
    if "\x00" in decoded:
        raise InputError("CL_CSV", f"{side}: NUL characters are not supported")
    reader = csv.reader(io.StringIO(decoded, newline=""), delimiter=delimiter, strict=True)
    try:
        header = next(reader, None)
        if not header:
            raise InputError("CL_HEADER", f"{side}: a nonempty header is required")
        if len(header) > MAX_COLUMNS:
            raise InputError("CL_LIMIT", f"{side}: header exceeds 256 columns")
        if any(not name or name != name.strip() or len(name) > MAX_CELL_CHARS for name in header):
            raise InputError("CL_HEADER", f"{side}: header names must be nonempty without edge whitespace")
        if len(set(header)) != len(header):
            raise InputError("CL_HEADER", f"{side}: duplicate header names")
        if any(name not in header for name in keys + numeric + ignored):
            raise InputError("CL_COLUMN", f"{side}: a selected column is absent from the header")
        rows: dict[tuple[str, ...], Row] = {}
        for record, cells in enumerate(reader, start=2):
            if record - 1 > max_rows:
                raise InputError("CL_LIMIT", f"{side}: record limit exceeded")
            if len(cells) != len(header):
                raise InputError("CL_CSV", f"{side}: record {record} has the wrong field count")
            if any(len(cell) > MAX_CELL_CHARS for cell in cells):
                raise InputError("CL_LIMIT", f"{side}: record {record} exceeds the cell size limit")
            values = dict(zip(header, cells))
            key = tuple(values[name] for name in keys)
            if any(not item.strip() for item in key):
                raise InputError("CL_KEY", f"{side}: record {record} has an empty key component")
            if key in rows:
                raise InputError("CL_KEY", f"{side}: record {record} duplicates a previous key")
            for name in numeric:
                try:
                    parse_decimal(values[name])
                except InputError:
                    raise InputError("CL_NUMERIC", f"{side}: record {record} has an invalid numeric cell") from None
            rows[key] = Row(record, values)
        return Table(header, rows)
    except csv.Error:
        raise InputError("CL_CSV", f"{side}: malformed CSV near physical line {reader.line_num}") from None


def compare_files(before: str | Path, after: str | Path, *, keys: tuple[str, ...],
                  numeric: tuple[str, ...] = (), ignored: tuple[str, ...] = (),
                  abs_tol: str = "0", rel_tol: str = "0", delimiter: str = ",",
                  encoding: str = "utf-8-sig", show_values: bool = False,
                  max_details: int = 100, max_rows: int = MAX_ROWS) -> dict:
    """Compare explicitly selected files; return a JSON-compatible schema v1 report.

    Cell and key values are omitted by default. Column names, logical record
    numbers and counts remain visible. Rows and columns may be reordered.
    """
    keys, numeric, ignored = tuple(keys), tuple(numeric), tuple(ignored)
    _names(keys, required=True)
    _names(numeric)
    _names(ignored)
    if set(keys) & (set(numeric) | set(ignored)) or set(numeric) & set(ignored):
        raise InputError("CL_CONFIG", "key, numeric and ignored column selections must be disjoint")
    if not isinstance(delimiter, str) or len(delimiter) != 1 or delimiter in '\r\n\x00"':
        raise InputError("CL_CONFIG", "delimiter must be one character other than newline, NUL or quote")
    if not isinstance(encoding, str) or not encoding:
        raise InputError("CL_CONFIG", "an explicit text encoding is required")
    if not isinstance(max_details, int) or not 0 <= max_details <= MAX_DETAILS:
        raise InputError("CL_CONFIG", "max-details must be between 0 and 10000")
    if not isinstance(max_rows, int) or not 1 <= max_rows <= MAX_ROWS:
        raise InputError("CL_CONFIG", "max-rows must be between 1 and 100000")
    absolute, relative = tolerance(abs_tol), tolerance(rel_tol)
    if (absolute or relative) and not numeric:
        raise InputError("CL_CONFIG", "nonzero tolerances require explicit numeric columns")
    old = _read_table(before, "before", keys, numeric, ignored, delimiter, encoding, max_rows)
    new = _read_table(after, "after", keys, numeric, ignored, delimiter, encoding, max_rows)
    old_columns, new_columns = set(old.columns), set(new.columns)
    common = sorted((old_columns & new_columns) - set(keys) - set(ignored))
    numeric_set = set(numeric)
    summary = {"before_rows": len(old.rows), "after_rows": len(new.rows),
               "added_rows": 0, "removed_rows": 0, "changed_rows": 0,
               "unchanged_rows": 0, "changed_cells": 0, "numeric_equivalent_cells": 0}
    details: list[dict] = []
    events = 0

    def emit(kind: str, key: tuple[str, ...], a: Row | None, b: Row | None,
             column: str | None = None) -> None:
        nonlocal events
        events += 1
        if len(details) >= max_details:
            return
        item = {"kind": kind, "before_record": a.record if a else None,
                "after_record": b.record if b else None}
        if column is not None:
            item["column"] = column
        if show_values:
            item["key"] = dict(zip(keys, key))
            if column is not None:
                item["before_value"] = a.values[column]
                item["after_value"] = b.values[column]
            else:
                item["values"] = (a or b).values.copy()
        details.append(item)

    # Input order is deliberately preserved in reports; matching uses exact keys.
    for key, a in old.rows.items():
        b = new.rows.get(key)
        if b is None:
            summary["removed_rows"] += 1
            emit("removed", key, a, None)
            continue
        changed = False
        for name in common:
            av, bv = a.values[name], b.values[name]
            if name in numeric_set:
                equal = numerically_equal(parse_decimal(av), parse_decimal(bv), absolute, relative)
                if equal and av != bv:
                    summary["numeric_equivalent_cells"] += 1
            else:
                equal = av == bv
            if not equal:
                changed = True
                summary["changed_cells"] += 1
                emit("changed", key, a, b, name)
        summary["changed_rows" if changed else "unchanged_rows"] += 1
    for key, b in new.rows.items():
        if key not in old.rows:
            summary["added_rows"] += 1
            emit("added", key, None, b)
    schema = {"added_columns": sorted(new_columns - old_columns),
              "removed_columns": sorted(old_columns - new_columns)}
    different = bool(summary["added_rows"] or summary["removed_rows"] or
                     summary["changed_rows"] or schema["added_columns"] or schema["removed_columns"])
    return {"schema_version": 1, "status": "different" if different else "equal",
            "values_included": bool(show_values),
            "policy": {"keys": list(keys), "numeric": list(numeric), "ignored": list(ignored),
                       "abs_tol": abs_tol, "rel_tol": rel_tol,
                       "delimiter": delimiter, "encoding": encoding},
            "summary": summary, "schema": schema, "details": details,
            "details_omitted": events - len(details)}
