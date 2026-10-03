# Contributing

Small, reproducible improvements are welcome. Use synthetic CSVs in issues and tests.
For a bug, include Python version, operating system, command, expected exit status
and actual result. Do not upload personal data or tokens.

```console
python -m pip install -e .
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

Optional lint and distribution checks:

```console
python -m pip install ruff build
python -m ruff check src tests
python -m build
```

Preserve the offline runtime, explicit keys/column policies, read-only input handling,
value-hidden default reports and stable exit codes. Add a meaningful boundary test
when changing parsing, tolerance, privacy or counting behavior. Document any report
schema change; avoid silently normalizing values. Never add telemetry or execute
dataset contents. Pull requests must pass cross-platform CI.
