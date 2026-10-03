"""Command line interface. No subprocesses, network calls or file writes."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .core import InputError, compare_files


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse normally echoes invalid tokens, which may contain private data.
        raise InputError("CL_ARGUMENT", "invalid command-line arguments; use --help")


def _parser() -> Parser:
    parser = Parser(description="Offline keyed CSV comparisons; cell values hidden by default.")
    parser.add_argument("before", help="baseline CSV file")
    parser.add_argument("after", help="candidate CSV file")
    parser.add_argument("--key", action="append", required=True, help="exact key header; repeat for composite keys")
    parser.add_argument("--numeric", action="append", default=[], help="numeric header; repeat for multiple columns")
    parser.add_argument("--ignore", action="append", default=[], help="ignore cell changes in this shared header; repeat")
    parser.add_argument("--abs-tol", default="0", help="absolute decimal tolerance (default: 0)")
    parser.add_argument("--rel-tol", default="0", help="relative tolerance as a fraction, e.g. 0.01 for 1%%")
    parser.add_argument("--delimiter", default=",", help="one character, or the word tab (default: comma)")
    parser.add_argument("--encoding", default="utf-8-sig", help="explicit input encoding (default: utf-8-sig)")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--show-values", action="store_true", help="include key and cell values in reports")
    parser.add_argument("--max-details", type=int, default=100, help="detail event cap, 0..10000 (counts stay complete)")
    parser.add_argument("--max-rows", type=int, default=100000, help="input row cap, 1..100000 per file")
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def _safe(text) -> str:
    """JSON quoting escapes terminal control characters and embedded newlines."""
    return json.dumps(text, ensure_ascii=True)


def render(report: dict, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(report, indent=2, ensure_ascii=True)
    summary = report["summary"]
    lines = [f"CSV comparison: {report['status']}",
             f"Rows: +{summary['added_rows']} -{summary['removed_rows']} "
             f"changed={summary['changed_rows']} unchanged={summary['unchanged_rows']}",
             f"Cells: changed={summary['changed_cells']} "
             f"numeric-equivalent={summary['numeric_equivalent_cells']}",
             f"Values included: {str(report['values_included']).lower()}"]
    for kind, columns in report["schema"].items():
        if columns:
            lines.append(f"{kind}: {_safe(columns)}")
    for item in report["details"]:
        lines.append(_safe(item))
    if report["details_omitted"]:
        lines.append(f"Details omitted: {report['details_omitted']} (counts remain complete)")
    if output_format == "markdown":
        # Indented blocks cannot be closed by untrusted backticks or HTML tags.
        return "# CSV comparison\n\n" + "\n".join("    " + line for line in lines)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        report = compare_files(args.before, args.after, keys=tuple(args.key),
                               numeric=tuple(args.numeric), ignored=tuple(args.ignore),
                               abs_tol=args.abs_tol, rel_tol=args.rel_tol,
                               delimiter="\t" if args.delimiter == "tab" else args.delimiter,
                               encoding=args.encoding, show_values=args.show_values,
                               max_details=args.max_details, max_rows=args.max_rows)
        print(render(report, args.format))
        return 1 if report["status"] == "different" else 0
    except InputError as exc:
        print(json.dumps({"schema_version": 1, "status": "invalid", "code": exc.code,
                          "message": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
