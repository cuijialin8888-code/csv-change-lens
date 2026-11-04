# Changelog

## 0.1.1 — 2026-11-04

- Isolate decimal comparison arithmetic from the caller's context so restricted
  exponent limits and signal traps cannot reject valid numeric inputs.
- Add regression coverage for large and small exponents, tolerance boundaries,
  and preservation of the caller's decimal settings and flags.

- Require complete CLI option names so prefixes cannot enable value disclosure.
- Require boolean library opt-in for values and reject boolean row/detail limits.
- Validate column selections and text codecs before opening inputs; sanitize invalid
  path-type failures with the existing `CL_READ` error contract.
- Classify CSV parser field-size failures as `CL_LIMIT` without changing caller limits.
- Expand configuration, privacy, resource-boundary and installed-version tests.
- Refresh English/Chinese usage notes and offline installation instructions.
- Replace deprecated license metadata with the SPDX expression and an explicit
  license file; require setuptools 77+ for builds and verify the installed license.

## 0.1.0 — 2026-10-03

- Initial offline keyed CSV comparison CLI and Python library.
- Explicit composite keys, exact text comparison and decimal absolute/relative tolerances.
- Added/removed/changed record counts and separate schema changes.
- Value-hidden text, JSON and Markdown reports with complete counts despite detail caps.
- Strict input validation, bounded input sizes and stable error/exit contracts.
- Synthetic measurement examples, English/Chinese documentation and cross-platform CI.
