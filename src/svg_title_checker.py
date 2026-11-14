#!/usr/bin/env python3
"""Check SVG files carry a <title> element, fail CI when one is missing.

Run: python3 src/svg_title_checker.py icons/
     python3 src/svg_title_checker.py logo.svg
     python3 src/svg_title_checker.py --stdin < logo.svg

An SVG with no <title> is announced to a screen reader
user as nothing, or as a meaningless file name — icons
and diagrams go silent. The fix is one line per file
once it is found, but nothing in the usual build stops
you shipping an SVG without a title. This tool finds
every SVG file whose root <svg> element has no <title>
child, and reports each one with the file and the line
number. It exits 1 when any SVG is missing a title, so
it can fail a CI run. An SVG whose title is present and
not empty exits 0.

The <title> must be a direct child of the root <svg>
element, and it must hold real text. A title tucked
inside a <g> names that group, not the whole picture,
so it does not count. An empty title, or one holding
only spaces, counts as missing — a screen reader has
nothing to announce. A second <title> on the same root
is reported too: one picture has one name.

Malformed XML is reported as a problem, with the line
the parser stopped on — a file that cannot be parsed
cannot be checked, so it fails rather than passing
silently. A file whose root element is not <svg> is
reported the same way.

It never rewrites a file, never touches the network,
and reads only the files and folders you point it at.
"""

import argparse
import fnmatch
import json
import os
import sys
import xml.parsers.expat as expat
from pathlib import Path

__version__ = "1.0.0"

SVG_EXTENSIONS = {".svg"}


def _local_name(name):
    """Strip a namespace prefix (svg:title) to the plain name."""
    return name.rsplit(":", 1)[-1]


class _TitleFinder:
    """Walk an SVG with expat, noting titles and their lines.

    Expat reports each element's start line, which a plain
    ElementTree parse does not give — and the line is what
    the report needs. The stack tracks nesting, so a title
    inside a <g> is told apart from a title that is a direct
    child of the root <svg>.
    """

    def __init__(self):
        self.parser = None
        self.stack = []
        self.root_name = None
        self.root_line = None
        self.titles = []
        self._current_title = None
        self._title_depth = 0

    def start(self, name, attrs):
        local = _local_name(name)
        line = self.parser.CurrentLineNumber
        if self.root_name is None:
            self.root_name = local
            self.root_line = line
        if local == "title":
            entry = {"line": line, "text": "",
                     "depth": len(self.stack)}
            self.titles.append(entry)
            self._current_title = entry
            self._title_depth = 1
        elif self._current_title is not None:
            self._title_depth += 1
        self.stack.append(local)

    def end(self, name):
        if self.stack:
            self.stack.pop()
        if self._current_title is not None:
            self._title_depth -= 1
            if self._title_depth == 0:
                self._current_title = None

    def chars(self, text):
        if self._current_title is not None:
            self._current_title["text"] += text


def check_svg_bytes(data):
    """Check one SVG document given as bytes.

    Returns (problems, error). "problems" is a list of
    {"line": int, "problem": str} where "problem" is
    "missing", "empty", or "multiple". "error" is a string
    when the file cannot be parsed or has no <svg> root,
    and None otherwise.
    """
    finder = _TitleFinder()
    parser = expat.ParserCreate()
    parser.StartElementHandler = finder.start
    parser.EndElementHandler = finder.end
    parser.CharacterDataHandler = finder.chars
    finder.parser = parser
    try:
        parser.Parse(data, True)
    except expat.ExpatError as exc:
        return [], "malformed XML: %s" % exc
    if finder.root_name is None:
        return [], "no <svg> root element"
    if finder.root_name != "svg":
        return [], "no <svg> root element"
    direct = [t for t in finder.titles if t["depth"] == 1]
    problems = []
    if not direct:
        problems.append({"line": finder.root_line,
                         "problem": "missing"})
    else:
        first = direct[0]
        if first["text"].strip() == "":
            problems.append({"line": first["line"],
                             "problem": "empty"})
        for extra in direct[1:]:
            problems.append({"line": extra["line"],
                             "problem": "multiple"})
    return problems, None


def check_text(text, path_label="<text>"):
    """Check one SVG document given as text. Returns (problems, error)."""
    return check_svg_bytes(text.encode("utf-8"))


def check_file(path):
    """Check one file. Returns (problems, error)."""
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        return [], str(exc)
    return check_svg_bytes(data)


def _is_svg_file(path):
    return Path(path).suffix.lower() in SVG_EXTENSIONS


def collect_files(paths, recursive=True, exclude=None):
    """Expand CLI paths into a sorted list of SVG file paths.

    A file given directly is always checked, whatever its
    name. A folder is walked for .svg files. .git folders
    are never walked, and directory links are never
    followed.
    """
    exclude = exclude or []
    found = []
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            found.append(str(path))
        elif path.is_dir():
            for dirpath, dirs, files in os.walk(path, followlinks=False):
                dirs[:] = [
                    d for d in dirs
                    if d != ".git"
                    and not any(fnmatch.fnmatch(d, pat) for pat in exclude)
                ]
                for name in files:
                    candidate = Path(dirpath) / name
                    if not _is_svg_file(candidate):
                        continue
                    if any(
                        fnmatch.fnmatch(str(candidate), pat)
                        or fnmatch.fnmatch(name, pat)
                        for pat in exclude
                    ):
                        continue
                    found.append(str(candidate))
                if not recursive:
                    break
        else:
            raise FileNotFoundError("no such file or folder: %s" % raw)
    seen = set()
    unique = []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return sorted(unique)


def format_problem(path, problem):
    """One human-readable line for one title problem."""
    if problem["problem"] == "missing":
        return ('FAIL %s: <svg> line %d has no <title> element'
                % (path, problem["line"]))
    if problem["problem"] == "empty":
        return 'FAIL %s: <title> line %d is empty' % (path, problem["line"])
    return ('FAIL %s: <title> line %d is an extra <title> element'
            % (path, problem["line"]))


def run(paths, recursive=True, exclude=None, as_json=False):
    """Check paths, print the report, return the exit code."""
    try:
        files = collect_files(paths, recursive=recursive, exclude=exclude)
    except FileNotFoundError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    if not files:
        print("error: no SVG files found", file=sys.stderr)
        return 2
    results = []
    problems = 0
    files_with_problems = 0
    for path in files:
        bad, error = check_file(path)
        count = len(bad) + (1 if error else 0)
        if count:
            problems += count
            files_with_problems += 1
        results.append({"path": path, "problems": bad, "error": error})
    if as_json:
        print(json.dumps(
            {"files": results, "checked": len(files),
             "problems": problems},
            indent=2))
    else:
        for result in results:
            if result["error"]:
                print("FAIL %s: %s" % (result["path"], result["error"]))
            for problem in result["problems"]:
                print(format_problem(result["path"], problem))
        if problems:
            print("Checked %d file(s), %d problem(s) in %d file(s)."
                  % (len(files), problems, files_with_problems))
        else:
            print("OK — %d file(s) checked, every SVG has a <title>."
                  % len(files))
    return 1 if problems else 0


def run_stdin(as_json=False):
    """Check one SVG document read from standard input."""
    data = sys.stdin.buffer.read()
    bad, error = check_svg_bytes(data)
    problems = len(bad) + (1 if error else 0)
    if as_json:
        print(json.dumps(
            {"files": [{"path": "<stdin>", "problems": bad,
                        "error": error}],
             "checked": 1, "problems": problems},
            indent=2))
    else:
        if error:
            print("FAIL <stdin>: %s" % error)
        for problem in bad:
            print(format_problem("<stdin>", problem))
        if problems:
            print("Checked 1 file(s), %d problem(s) in 1 file(s)." % problems)
        else:
            print("OK — 1 file(s) checked, every SVG has a <title>.")
    return 1 if problems else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="svg_title_checker",
        description="Check SVG files carry a <title> element, "
                    "fail CI when one is missing.")
    parser.add_argument("paths", nargs="*", help="SVG files or folders")
    parser.add_argument("--no-recursive", action="store_true",
                        help="do not walk into subfolders")
    parser.add_argument("--exclude", action="append", default=[],
                        help="skip files or folders matching this pattern "
                             "(repeatable)")
    parser.add_argument("--json", action="store_true",
                        help="print the result as JSON")
    parser.add_argument("--stdin", action="store_true",
                        help="check one SVG document from standard input")
    parser.add_argument("--version", action="version",
                        version="%(prog)s " + __version__)
    args = parser.parse_args(argv)
    if args.stdin:
        if args.paths:
            parser.error("--stdin takes no file or folder arguments")
        return run_stdin(as_json=args.json)
    if not args.paths:
        parser.error("give at least one SVG file or folder")
    return run(args.paths, recursive=not args.no_recursive,
               exclude=args.exclude, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
