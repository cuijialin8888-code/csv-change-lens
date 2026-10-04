# Changelog

## Unreleased

- Isolate decimal comparison arithmetic from the caller's context so restricted
  exponent limits and signal traps cannot reject valid numeric inputs.
- Add regression coverage for large and small exponents, tolerance boundaries,
  and preservation of the caller's decimal settings and flags.

## 0.1.0 — 2026-10-03

- Initial offline keyed CSV comparison CLI and Python library.
- Explicit composite keys, exact text comparison and decimal absolute/relative tolerances.
- Added/removed/changed record counts and separate schema changes.
- Value-hidden text, JSON and Markdown reports with complete counts despite detail caps.
- Strict input validation, bounded input sizes and stable error/exit contracts.
- Synthetic measurement examples, English/Chinese documentation and cross-platform CI.
