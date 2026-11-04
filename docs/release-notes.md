csv-change-lens 0.1.1: input-validation and privacy-boundary maintenance.

- Require full CLI long-option names; abbreviations such as `--show` are rejected.
- Require an actual boolean for the library's `show_values` option. Strings such as
  `"false"` cannot enable value disclosure.
- Reject invalid column selections, unsupported/non-text encodings and boolean
  resource limits before reading input files.
- Sanitize invalid path-type failures and classify CSV parser field-size failures
  as resource errors without changing the caller's CSV parser settings.
- Keep decimal comparisons independent of the caller's decimal context.
- Extend cross-platform regression coverage and check installed package/CLI versions.
- Modernize license metadata and verify the license is included in the installed wheel.
  Source builds require setuptools 77+; installed wheels retain zero runtime dependencies.

Compatibility: replace abbreviated CLI options with complete names. Library callers
must use non-string iterables for column selections, boolean value opt-in and integer
limits excluding booleans. Report schema v1, valid comparison policies and exit codes
remain unchanged.

Install the wheel offline with `python -m pip install --no-index --no-deps
csv_change_lens-0.1.1-py3-none-any.whl`. SHA256SUMS covers the wheel and source archive.
The runtime remains offline with no third-party dependencies. Default reports still
expose column names, counts and record locations; this tool does not anonymize data.
