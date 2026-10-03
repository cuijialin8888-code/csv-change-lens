Initial release of csv-change-lens: offline CSV change reviews with explicit decimal
tolerances and reports that hide cell/key values by default.

- Exact composite keys and deliberate numeric/ignored column selections.
- Added, removed and changed record counts; separate schema changes.
- Decimal absolute and symmetric relative tolerances; equivalent numeric cells counted.
- Text, JSON and Markdown output; bounded details with complete counts.
- Reject duplicate/blank keys, malformed CSV and invalid numeric values.
- English/Chinese documentation and synthetic measurement examples.
- Python 3.10+; no runtime dependencies; MIT license.

Download the wheel for offline installation with `python -m pip install --no-index
--no-deps csv_change_lens-0.1.0-py3-none-any.whl`. SHA256SUMS covers the wheel and source
archive. Default reports still reveal column names, record locations and counts.

This is an initial bounded in-memory tool, not statistical inference or anonymization.
Please report issues using minimal synthetic CSVs.
