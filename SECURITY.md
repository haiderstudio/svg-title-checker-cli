# Security Policy

This tool runs locally, collects no data, sends nothing anywhere, and needs no API key or secret. It only reads the files and folders you point it at, and it never rewrites a file and never changes anything. It writes nothing except the report on standard output (and usage errors on standard error). It never fetches a URL: SVG files are read from disk only.

If you find a case where the tool changes a file, fetches a URL, or reports a pass for an SVG file whose root has no `<title>` element, please open an issue describing the exact commands and input. Do not include any real secret in the report.
