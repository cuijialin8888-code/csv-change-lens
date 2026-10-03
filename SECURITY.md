# Security and data handling

The runtime reads only the two paths supplied by the caller, using bounded reads.
It does not access the network, invoke a shell, evaluate formulas, execute CSV
contents, modify inputs, or write reports to files. Shell redirection is outside
the program. Installation and development tools may use the network to obtain
build dependencies; the installed runtime has no third-party dependencies.

Default reports omit cell values, key values and paths, including error messages.
They expose column names, comparison policy, record locations and counts. This
reduces accidental log disclosure; it is not encryption or anonymization. If your
headers themselves contain sensitive data, do not share the report. `--show-values`
explicitly includes raw values; redirect and distribute such output with care.
JSON quoting prevents terminal control characters from being emitted directly.
Markdown uses indented code blocks so input backticks cannot terminate a code fence.
CSV formulas are treated as text and are never executed by this tool.

Inputs must be regular files. Symlinks to regular files are accepted when explicitly
supplied; files should not be modified while comparison runs. The tool is not
designed to defeat a hostile process racing filesystem operations. Resource limits
bound input size and report events, rather than guaranteeing a fixed memory budget.

Only synthetic examples belong in this repository. Never attach private datasets,
credentials or original sensitive reports to an issue. For a vulnerability, use
GitHub's private vulnerability reporting if available. For ordinary bugs, provide a
minimal synthetic reproduction. Initial supported version: 0.1.x.
