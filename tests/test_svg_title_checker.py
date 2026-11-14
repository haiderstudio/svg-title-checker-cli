#!/usr/bin/env python3
"""Tests for svg_title_checker — stdlib unittest only."""

import ast
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import svg_title_checker as checker

REPO = Path(__file__).resolve().parent.parent


def run_cli(argv):
    """Run main(argv), capture stdout/stderr, return (code, out, err)."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = checker.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def write(tmp, name, content):
    path = Path(tmp) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return str(path)


def svg(body, attrs='xmlns="http://www.w3.org/2000/svg"'):
    """Wrap body in a one-line <svg> root, or use attrs="" for none."""
    if attrs:
        return '<svg %s>\n%s\n</svg>' % (attrs, body)
    return '<svg>\n%s\n</svg>' % body


class TestCheckSvgBytes(unittest.TestCase):
    def test_title_present_passes(self):
        bad, err = checker.check_svg_bytes(
            svg('  <title>Home</title>').encode())
        self.assertEqual((bad, err), ([], None))

    def test_title_not_first_child_still_passes(self):
        bad, err = checker.check_svg_bytes(
            svg('  <rect width="10" height="10"/>\n'
                '  <title>Home</title>').encode())
        self.assertEqual((bad, err), ([], None))

    def test_title_after_many_lines_passes(self):
        bad, err = checker.check_svg_bytes(
            svg('  <rect width="10" height="10"/>\n'
                '  <circle cx="5" cy="5" r="5"/>\n'
                '  <title>Settings</title>').encode())
        self.assertEqual((bad, err), ([], None))

    def test_missing_title_fails_with_root_line(self):
        bad, err = checker.check_svg_bytes(
            svg('  <rect width="10" height="10"/>').encode())
        self.assertIsNone(err)
        self.assertEqual(bad, [{"line": 1, "problem": "missing"}])

    def test_missing_title_root_on_later_line(self):
        text = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<!-- a comment -->\n'
                '<svg xmlns="http://www.w3.org/2000/svg">\n'
                '  <rect width="10" height="10"/>\n'
                '</svg>')
        bad, err = checker.check_svg_bytes(text.encode())
        self.assertEqual(bad, [{"line": 3, "problem": "missing"}])

    def test_empty_title_fails(self):
        bad, err = checker.check_svg_bytes(
            svg('  <title></title>').encode())
        self.assertIsNone(err)
        self.assertEqual(bad, [{"line": 2, "problem": "empty"}])

    def test_self_closing_title_is_empty(self):
        bad, err = checker.check_svg_bytes(
            svg('  <title/>').encode())
        self.assertEqual(bad, [{"line": 2, "problem": "empty"}])

    def test_whitespace_only_title_is_empty(self):
        bad, err = checker.check_svg_bytes(
            svg('  <title>   </title>').encode())
        self.assertEqual(bad, [{"line": 2, "problem": "empty"}])

    def test_title_with_spaces_around_text_passes(self):
        bad, err = checker.check_svg_bytes(
            svg('  <title>  Home  </title>').encode())
        self.assertEqual((bad, err), ([], None))

    def test_multiple_titles_second_is_extra(self):
        bad, err = checker.check_svg_bytes(
            svg('  <title>Home</title>\n'
                '  <title>House</title>').encode())
        self.assertEqual(bad, [{"line": 3, "problem": "multiple"}])

    def test_multiple_titles_first_empty_reports_both(self):
        bad, err = checker.check_svg_bytes(
            svg('  <title></title>\n'
                '  <title>House</title>').encode())
        self.assertEqual(bad, [{"line": 2, "problem": "empty"},
                               {"line": 3, "problem": "multiple"}])

    def test_three_titles_two_extras(self):
        bad, err = checker.check_svg_bytes(
            svg('  <title>One</title>\n'
                '  <title>Two</title>\n'
                '  <title>Three</title>').encode())
        self.assertEqual(bad, [{"line": 3, "problem": "multiple"},
                               {"line": 4, "problem": "multiple"}])

    def test_title_inside_group_does_not_count(self):
        bad, err = checker.check_svg_bytes(
            svg('  <g>\n'
                '    <title>Home</title>\n'
                '  </g>').encode())
        self.assertEqual(bad, [{"line": 1, "problem": "missing"}])

    def test_title_inside_defs_does_not_count(self):
        bad, err = checker.check_svg_bytes(
            svg('  <defs>\n'
                '    <title>Home</title>\n'
                '  </defs>').encode())
        self.assertEqual(bad, [{"line": 1, "problem": "missing"}])

    def test_title_inside_nested_svg_does_not_count(self):
        bad, err = checker.check_svg_bytes(
            svg('  <svg>\n'
                '    <title>Inner</title>\n'
                '  </svg>').encode())
        self.assertEqual(bad, [{"line": 1, "problem": "missing"}])

    def test_title_with_entity_passes(self):
        bad, err = checker.check_svg_bytes(
            svg('  <title>Fish &amp; Chips</title>').encode())
        self.assertEqual((bad, err), ([], None))

    def test_title_with_cdata_passes(self):
        bad, err = checker.check_svg_bytes(
            svg('  <title><![CDATA[Home & Away]]></title>').encode())
        self.assertEqual((bad, err), ([], None))

    def test_title_with_nested_element_passes(self):
        bad, err = checker.check_svg_bytes(
            svg('  <title>Home <tspan>icon</tspan></title>').encode())
        self.assertEqual((bad, err), ([], None))

    def test_title_with_multiline_text_passes(self):
        bad, err = checker.check_svg_bytes(
            svg('  <title>\n    Home\n  </title>').encode())
        self.assertEqual((bad, err), ([], None))

    def test_namespaced_title_passes(self):
        text = ('<svg:svg xmlns:svg="http://www.w3.org/2000/svg">\n'
                '  <svg:title>Home</svg:title>\n'
                '</svg:svg>')
        bad, err = checker.check_svg_bytes(text.encode())
        self.assertEqual((bad, err), ([], None))

    def test_title_in_comment_ignored(self):
        bad, err = checker.check_svg_bytes(
            svg('  <!-- <title>Fake</title> -->\n'
                '  <rect width="10" height="10"/>').encode())
        self.assertEqual(bad, [{"line": 1, "problem": "missing"}])

    def test_svg_in_comment_ignored(self):
        text = ('<!-- <svg> -->\n'
                '<svg xmlns="http://www.w3.org/2000/svg">\n'
                '  <title>Home</title>\n'
                '</svg>')
        bad, err = checker.check_svg_bytes(text.encode())
        self.assertEqual((bad, err), ([], None))

    def test_xml_declaration_passes(self):
        text = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<svg xmlns="http://www.w3.org/2000/svg">\n'
                '  <title>Home</title>\n'
                '</svg>')
        bad, err = checker.check_svg_bytes(text.encode())
        self.assertEqual((bad, err), ([], None))

    def test_doctype_passes(self):
        text = ('<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
                '"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">\n'
                '<svg xmlns="http://www.w3.org/2000/svg">\n'
                '  <title>Home</title>\n'
                '</svg>')
        bad, err = checker.check_svg_bytes(text.encode())
        self.assertEqual((bad, err), ([], None))

    def test_malformed_xml_is_an_error(self):
        bad, err = checker.check_svg_bytes(
            svg('  <title>Home</title>\n'
                '  <rect>').encode())
        self.assertEqual(bad, [])
        self.assertIsNotNone(err)
        self.assertIn("malformed XML", err)

    def test_malformed_xml_reports_the_line(self):
        bad, err = checker.check_svg_bytes(
            b'<svg>\n  <title>Home</title>\n  <rect>\n</svg>')
        self.assertEqual(bad, [])
        self.assertIn("line 4", err)

    def test_unclosed_svg_is_an_error(self):
        bad, err = checker.check_svg_bytes(
            b'<svg>\n  <title>Home</title>')
        self.assertEqual(bad, [])
        self.assertIn("malformed XML", err)

    def test_empty_file_is_an_error(self):
        bad, err = checker.check_svg_bytes(b'')
        self.assertEqual(bad, [])
        self.assertIn("malformed XML", err)

    def test_whitespace_only_file_is_an_error(self):
        bad, err = checker.check_svg_bytes(b'   \n  ')
        self.assertEqual(bad, [])
        self.assertIn("malformed XML", err)

    def test_non_svg_root_is_an_error(self):
        bad, err = checker.check_svg_bytes(
            b'<html><body><svg><title>Home</title></svg></body></html>')
        self.assertEqual(bad, [])
        self.assertEqual(err, "no <svg> root element")

    def test_two_roots_is_an_error(self):
        bad, err = checker.check_svg_bytes(
            b'<svg><title>A</title></svg><svg><title>B</title></svg>')
        self.assertEqual(bad, [])
        self.assertIn("malformed XML", err)

    def test_invalid_utf8_bytes_are_an_error(self):
        bad, err = checker.check_svg_bytes(
            b'<svg><title>\xff</title></svg>')
        self.assertEqual(bad, [])
        self.assertIn("malformed XML", err)

    def test_utf16_document_passes(self):
        text = ('<svg xmlns="http://www.w3.org/2000/svg">\n'
                '  <title>Home</title>\n'
                '</svg>')
        bad, err = checker.check_svg_bytes(text.encode("utf-16"))
        self.assertEqual((bad, err), ([], None))

    def test_svg_without_namespace_passes(self):
        bad, err = checker.check_svg_bytes(
            svg('  <title>Home</title>', attrs='').encode())
        self.assertEqual((bad, err), ([], None))

    def test_title_with_desc_sibling_passes(self):
        bad, err = checker.check_svg_bytes(
            svg('  <title>Home</title>\n'
                '  <desc>A house icon</desc>').encode())
        self.assertEqual((bad, err), ([], None))

    def test_check_text_accepts_str(self):
        bad, err = checker.check_text(svg('  <title>Home</title>'))
        self.assertEqual((bad, err), ([], None))

    def test_check_text_missing(self):
        bad, err = checker.check_text(svg('  <rect width="1"/>'))
        self.assertEqual(bad, [{"line": 1, "problem": "missing"}])


class TestCheckFile(unittest.TestCase):
    def test_clean_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "ok.svg",
                         svg('  <title>Home</title>'))
            bad, err = checker.check_file(path)
            self.assertEqual((bad, err), ([], None))

    def test_bad_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.svg",
                         svg('  <rect width="10"/>'))
            bad, err = checker.check_file(path)
            self.assertIsNone(err)
            self.assertEqual(bad, [{"line": 1, "problem": "missing"}])

    def test_missing_file_reports_error(self):
        bad, err = checker.check_file("/nonexistent/icon.svg")
        self.assertEqual(bad, [])
        self.assertIsNotNone(err)

    def test_malformed_file_reports_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.svg", b'<svg><title>Home</title>')
            bad, err = checker.check_file(path)
            self.assertEqual(bad, [])
            self.assertIn("malformed XML", err)

    def test_input_file_left_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = svg('  <rect width="10"/>')
            path = write(tmp, "bad.svg", text)
            checker.check_file(path)
            self.assertEqual(Path(path).read_text(), text)


class TestCollectFiles(unittest.TestCase):
    def test_direct_file_any_name_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "icon.txt", svg('  <title>Home</title>'))
            self.assertEqual(checker.collect_files([path]), [path])

    def test_folder_walk_finds_svg_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write(tmp, "a.svg", "")
            b = write(tmp, "sub/b.svg", "")
            write(tmp, "c.html", "")
            write(tmp, "d.txt", "")
            write(tmp, "e.svgz", "")
            got = checker.collect_files([tmp])
            self.assertEqual(got, sorted([a, b]))

    def test_uppercase_svg_extension_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write(tmp, "a.SVG", "")
            self.assertEqual(checker.collect_files([tmp]), [a])

    def test_git_folder_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, ".git/hooks/sample.svg", "")
            a = write(tmp, "a.svg", "")
            self.assertEqual(checker.collect_files([tmp]), [a])

    def test_no_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write(tmp, "a.svg", "")
            write(tmp, "sub/b.svg", "")
            self.assertEqual(
                checker.collect_files([tmp], recursive=False), [a])

    def test_exclude_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write(tmp, "a.svg", "")
            write(tmp, "skip.svg", "")
            got = checker.collect_files([tmp], exclude=["skip.svg"])
            self.assertEqual(got, [a])

    def test_missing_path_raises(self):
        with self.assertRaises(FileNotFoundError):
            checker.collect_files(["/nonexistent/path"])

    def test_duplicates_deduped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.svg", "")
            self.assertEqual(
                checker.collect_files([path, path]), [path])

    def test_sorted_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "z.svg", "")
            write(tmp, "a.svg", "")
            got = checker.collect_files([tmp])
            self.assertEqual([os.path.basename(p) for p in got],
                             ["a.svg", "z.svg"])


class TestRun(unittest.TestCase):
    def test_clean_run_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "ok.svg", svg('  <title>Home</title>'))
            code, out, _ = run_cli([path])
            self.assertEqual(code, 0)
            self.assertIn(
                "OK — 1 file(s) checked, every SVG has a <title>.", out)

    def test_dirty_run_exit_1_and_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.svg", svg('  <rect width="10"/>'))
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            # CWD-robust: assert on the file name and message, never
            # on the absolute path the CLI echoes.
            self.assertIn("bad.svg", out)
            self.assertIn('<svg> line 1 has no <title> element', out)
            self.assertIn("Checked 1 file(s), 1 problem(s) in 1 file(s).",
                          out)

    def test_empty_title_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.svg", svg('  <title></title>'))
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("<title> line 2 is empty", out)

    def test_multiple_title_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.svg",
                         svg('  <title>One</title>\n'
                             '  <title>Two</title>'))
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("<title> line 3 is an extra <title> element",
                          out)

    def test_folder_summary_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "good.svg", svg('  <title>Home</title>'))
            write(tmp, "bad.svg", svg('  <rect width="10"/>'))
            code, out, _ = run_cli([tmp])
            self.assertEqual(code, 1)
            self.assertIn("Checked 2 file(s), 1 problem(s) in 1 file(s).",
                          out)

    def test_malformed_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.svg", b'<svg><title>Home</title>')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("malformed XML", out)

    def test_non_svg_root_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.svg",
                         b'<html><svg><title>X</title></svg></html>')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("no <svg> root element", out)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.svg",
                         svg('  <title></title>\n'
                             '  <title>Two</title>'))
            code, out, _ = run_cli(["--json", path])
            self.assertEqual(code, 1)
            data = json.loads(out)
            self.assertEqual(data["checked"], 1)
            self.assertEqual(data["problems"], 2)
            self.assertEqual(
                os.path.basename(data["files"][0]["path"]), "bad.svg")
            self.assertEqual(data["files"][0]["problems"][0]["problem"],
                             "empty")
            self.assertEqual(data["files"][0]["problems"][1]["problem"],
                             "multiple")
            self.assertEqual(data["files"][0]["problems"][1]["line"], 3)
            self.assertIsNone(data["files"][0]["error"])

    def test_json_clean_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "ok.svg", svg('  <title>Home</title>'))
            code, out, _ = run_cli(["--json", path])
            self.assertEqual(code, 0)
            data = json.loads(out)
            self.assertEqual(data["problems"], 0)
            self.assertEqual(data["files"][0]["problems"], [])

    def test_stdin_clean(self):
        old_stdin = sys.stdin
        try:
            sys.stdin = io.TextIOWrapper(
                io.BytesIO(svg('  <title>Home</title>').encode()))
            code, out, _ = run_cli(["--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 0)
        self.assertIn(
            "OK — 1 file(s) checked, every SVG has a <title>.", out)

    def test_stdin_dirty_via_main(self):
        old_stdin = sys.stdin
        try:
            sys.stdin = io.TextIOWrapper(
                io.BytesIO(svg('  <rect width="10"/>').encode()))
            code, out, _ = run_cli(["--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 1)
        self.assertIn(
            'FAIL <stdin>: <svg> line 1 has no <title> element', out)

    def test_stdin_with_paths_is_usage_error(self):
        code, _, err = run_cli(["--stdin", "x.svg"])
        self.assertEqual(code, 2)
        self.assertIn("--stdin takes no file", err)

    def test_no_paths_is_usage_error(self):
        code, _, err = run_cli([])
        self.assertEqual(code, 2)
        self.assertIn("at least one SVG file", err)

    def test_missing_path_exit_2(self):
        code, _, err = run_cli(["/nonexistent/icon.svg"])
        self.assertEqual(code, 2)
        self.assertIn("no such file or folder", err)

    def test_empty_folder_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_cli([tmp])
            self.assertEqual(code, 2)
            self.assertIn("no SVG files found", err)

    def test_bad_flag_exit_2(self):
        code, _, _ = run_cli(["--nope"])
        self.assertEqual(code, 2)

    def test_version(self):
        code, out, _ = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("svg_title_checker 1.0.0", out)

    def test_exclude_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "good.svg", svg('  <title>Home</title>'))
            write(tmp, "bad.svg", svg('  <rect width="10"/>'))
            code, out, _ = run_cli(["--exclude", "bad.svg", tmp])
            self.assertEqual(code, 0)
            self.assertIn("OK —", out)

    def test_no_recursive_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "good.svg", svg('  <title>Home</title>'))
            write(tmp, "sub/bad.svg", svg('  <rect width="10"/>'))
            code, out, _ = run_cli(["--no-recursive", tmp])
            self.assertEqual(code, 0)
            self.assertIn("OK —", out)

    def test_cli_runs_from_another_folder(self):
        # CWD-robustness: the tool must work from /tmp and from /,
        # not only from the repo root.
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "ok.svg", svg('  <title>Home</title>'))
            for cwd in ("/tmp", "/"):
                result = subprocess.run(
                    [sys.executable,
                     str(REPO / "src/svg_title_checker.py"), path],
                    cwd=cwd, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, cwd)
                self.assertIn("OK —", result.stdout)

    def test_cli_runs_from_repo_root(self):
        result = subprocess.run(
            [sys.executable, "src/svg_title_checker.py",
             "examples/good.svg"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("OK —", result.stdout)


class TestExamples(unittest.TestCase):
    def test_run_example_output_matches_sample(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        expected = (REPO / "examples/sample-output.md").read_text()
        self.assertEqual(result.stdout, expected)

    def test_readme_quotes_match_real_runs(self):
        readme = (REPO / "README.md").read_text()
        good = subprocess.run(
            [sys.executable, "src/svg_title_checker.py",
             "examples/good.svg"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(good.returncode, 0)
        self.assertIn(good.stdout.strip(), readme)
        bad = subprocess.run(
            [sys.executable, "src/svg_title_checker.py",
             "examples/bad.svg"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertIn(bad.stdout.strip(), readme)
        empty = subprocess.run(
            [sys.executable, "src/svg_title_checker.py",
             "examples/empty-title.svg"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(empty.returncode, 1)
        self.assertIn(empty.stdout.strip(), readme)
        nested = subprocess.run(
            [sys.executable, "src/svg_title_checker.py",
             "examples/nested-title.svg"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(nested.returncode, 1)
        self.assertIn(nested.stdout.strip(), readme)
        folder = subprocess.run(
            [sys.executable, "src/svg_title_checker.py",
             "examples/"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(folder.returncode, 1)
        self.assertIn("Checked 4 file(s), 3 problem(s) in 3 file(s).",
                      folder.stdout)
        self.assertIn("Checked 4 file(s), 3 problem(s) in 3 file(s).",
                      readme)
        js = subprocess.run(
            [sys.executable, "src/svg_title_checker.py",
             "--json", "examples/bad.svg"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(js.returncode, 1)
        self.assertIn(js.stdout.strip(), readme)


class TestHygiene(unittest.TestCase):
    def _repo_files(self):
        for root, dirs, files in os.walk(REPO):
            dirs[:] = [d for d in dirs
                       if d not in (".git", "__pycache__", "tests")]
            for name in files:
                if name.endswith(".pyc"):
                    continue
                yield Path(root) / name

    def test_no_placeholder_text(self):
        banned = ["TODO", "coming soon", "lorem", "FIXME", "XXX"]
        hits = []
        for path in self._repo_files():
            text = path.read_text(errors="ignore")
            for word in banned:
                if word in text:
                    hits.append("%s: %s" % (path.name, word))
        self.assertEqual(hits, [])

    def test_no_absolute_paths(self):
        hits = []
        for path in self._repo_files():
            text = path.read_text(errors="ignore")
            for marker in ("/home/", "/Users/", "C:\\"):
                if marker in text:
                    hits.append("%s: %s" % (path.name, marker))
        self.assertEqual(hits, [])

    def test_no_secrets(self):
        hits = []
        for path in self._repo_files():
            text = path.read_text(errors="ignore").lower()
            for marker in ("api_key", "api-key", "password", "secret=",
                           "token="):
                if marker in text:
                    hits.append("%s: %s" % (path.name, marker))
        self.assertEqual(hits, [])

    def test_stdlib_imports_only(self):
        stdlib = set(sys.stdlib_module_names)
        for target in (REPO / "src/svg_title_checker.py",
                       REPO / "tests/test_svg_title_checker.py"):
            tree = ast.parse(target.read_text())
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(a.name.split(".")[0]
                                    for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            self.assertFalse(imported - stdlib - {"svg_title_checker"},
                             (target.name, imported))
            self.assertNotIn("yaml", imported)

    def test_no_network_use_in_src(self):
        src = (REPO / "src/svg_title_checker.py").read_text()
        for marker in ("urllib", "requests", "socket", "http.client",
                       "urlopen", "urlretrieve"):
            self.assertNotIn(marker, src, marker)

    def test_gitignore_lists_env_first(self):
        lines = (REPO / ".gitignore").read_text().splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_this_test_file(self):
        ci = (REPO / ".github/workflows/ci.yml").read_text()
        self.assertIn("tests/test_svg_title_checker.py", ci)
        self.assertIn("ubuntu-latest", ci)
        self.assertIn("3.12", ci)
        self.assertIn("actions/checkout", ci)
        self.assertIn("setup-python", ci)
        self.assertIn("push", ci)
        self.assertIn("pull_request", ci)


if __name__ == "__main__":
    unittest.main()
