# svg-title-checker-cli

Check every SVG file carries a `<title>` element — the accessible name a screen reader announces — and fail CI when one does not.

[![CI](https://github.com/haiderstudio/svg-title-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/svg-title-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`svg_title_checker` reads SVG files and finds every
one whose root `<svg>` element has no `<title>` child,
and reports each one with the file and the line
number. It exits 1 when any SVG is missing a title,
so it can fail a CI run. An SVG whose title is present
and not empty exits 0.

- An SVG with no title is announced to a screen
  reader user as nothing, or as a meaningless file
  name — icons and diagrams go silent. The fix is
  one line per file once it is found, but nothing in
  the usual build stops you shipping an SVG without
  a title. This catches it before the file ships.
- The `<title>` must be a direct child of the root
  `<svg>` element, and it must hold real text. A
  title tucked inside a `<g>` names that group, not
  the whole picture, so it does not count — and
  neither does a title inside `<defs>` or inside a
  nested `<svg>`. An empty title, or one holding
  only spaces, counts as missing: a screen reader
  has nothing to announce.
- A second `<title>` on the same root is reported
  too: one picture has one name.
- Malformed XML is reported as a problem, with the
  line the parser stopped on — a file that cannot be
  parsed cannot be checked, so it fails rather than
  passing silently. A file whose root element is
  not `<svg>` is reported the same way.
- A `<title>` inside an XML comment does not count,
  and neither does one inside a CDATA section that
  is not a real element. Entities (`&amp;`) and
  CDATA text inside a real title count as its text.
- A file given directly on the command line is
  always checked, whatever its name. A folder is
  walked for `.svg` files, recursively by default
  (`--no-recursive` stops at the top level). `.git`
  folders are never walked, and directory links are
  never followed.
- `--json` prints the result as JSON, and `--stdin`
  checks one SVG document read from standard input.

## Who it is for

Anyone who ships SVG icons, logos, or diagrams and
does not want them to go silent for screen reader
users — front-end developers, design-system teams,
and anyone whose site carries SVG files added by
hand or exported from a design tool.

## What it does NOT do

- It does not check whether an SVG file is
  well-formed XML beyond what the title check needs.
  That is repo #61, xml-validator-cli, which checks
  well-formedness on its own — and a missing
  `<title>` is valid XML, so it passes that check.
  This repo checks the title, not the XML.
- It does not check SVGs inside rendered web pages
  or a live DOM. That is edilec's
  svg-title-coverage-checker, which checks title
  coverage for SVGs in rendered markup — rendered
  markup is its job, not this repo's. This repo
  checks local `.svg` files on disk.
- It does not check `<desc>` elements, `aria-label`
  attributes, or `role` attributes — the `<title>`
  is the accessible name this tool gates on.
- It does not check image files of any other kind.
  That is repo #30, image-alt-checker-cli, which
  checks alt text on images, and repo #83,
  html-img-attr-checker-cli, which checks img
  attributes — images are a different check on the
  same pages.
- It does not fetch a live site, and it never
  rewrites a file. It is report-only, and it never
  touches the network.

## How this differs

- A fresh search of GitHub on Nov 13, 2026 found 0
  results for `"svg-title-checker-cli"` and 1 result
  for `svg title checker` — edilec's
  svg-title-coverage-checker, 0 stars, which checks
  title and description coverage for SVGs in
  rendered markup (a live DOM), not local `.svg`
  files on disk. No rival is a tested CLI with a CI
  gate on local SVG files.
- Repo #61, xml-validator-cli, checks that an SVG
  file is well-formed XML; a missing `<title>` is
  valid XML, so it passes that check. This repo
  checks the title, which well-formedness cannot
  see.

## Install

```sh
git clone https://github.com/haiderstudio/svg-title-checker-cli.git
cd svg-title-checker-cli
```

There is nothing else to install: Python 3.10 or newer,
standard library only, no dependencies.

## Usage

Check one SVG file:

```sh
python3 src/svg_title_checker.py logo.svg
```

A file whose title is present passes:

```sh
$ python3 src/svg_title_checker.py examples/good.svg
OK — 1 file(s) checked, every SVG has a <title>.
```

A file with no title fails, with the line of the
`<svg>` element:

```sh
$ python3 src/svg_title_checker.py examples/bad.svg
FAIL examples/bad.svg: <svg> line 1 has no <title> element
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

An empty title fails on the title's own line:

```sh
$ python3 src/svg_title_checker.py examples/empty-title.svg
FAIL examples/empty-title.svg: <title> line 2 is empty
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

A title inside a group does not name the picture, so
the file still fails:

```sh
$ python3 src/svg_title_checker.py examples/nested-title.svg
FAIL examples/nested-title.svg: <svg> line 1 has no <title> element
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

Check a whole folder (SVG files only):

```sh
$ python3 src/svg_title_checker.py examples/
FAIL examples/bad.svg: <svg> line 1 has no <title> element
FAIL examples/empty-title.svg: <title> line 2 is empty
FAIL examples/nested-title.svg: <svg> line 1 has no <title> element
Checked 4 file(s), 3 problem(s) in 3 file(s).
```

Check one document from standard input:

```sh
$ python3 src/svg_title_checker.py --stdin < examples/good.svg
OK — 1 file(s) checked, every SVG has a <title>.
```

Machine-readable output:

```sh
$ python3 src/svg_title_checker.py --json examples/bad.svg
{
  "files": [
    {
      "path": "examples/bad.svg",
      "problems": [
        {
          "line": 1,
          "problem": "missing"
        }
      ],
      "error": null
    }
  ],
  "checked": 1,
  "problems": 1
}
```

Exit codes: 0 when every SVG has a title, 1 when
any SVG is missing one or a file cannot be parsed,
2 for a usage error (a missing path, a bad flag, or
no SVG files found).

## Examples

An empty title is a fail, not a pass — a screen
reader has nothing to announce — so
`examples/empty-title.svg` fails on its title's
line:

```sh
$ python3 src/svg_title_checker.py examples/empty-title.svg
FAIL examples/empty-title.svg: <title> line 2 is empty
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

A title inside a `<g>` names the group, not the
picture — `examples/nested-title.svg` carries a
title and still fails, because the root `<svg>` has
none:

```sh
$ python3 src/svg_title_checker.py examples/nested-title.svg
FAIL examples/nested-title.svg: <svg> line 1 has no <title> element
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

Run every bundled example at once with `sh
examples/run-example.sh` — the output is saved in
[examples/sample-output.md](examples/sample-output.md).

## How it is tested

```sh
python3 tests/test_svg_title_checker.py
```

The tests cover the check itself (title present and
absent, title not first child, empty and
whitespace-only titles, self-closing title, multiple
titles, a title inside a group, inside `<defs>`, and
inside a nested `<svg>`, entities and CDATA inside
a title, nested elements inside a title, multiline
title text, namespaced `svg:title`, a title inside
a comment ignored, an `<svg>` inside a comment
ignored, XML declaration and DOCTYPE, malformed
XML with its line, unclosed SVG, empty and
whitespace-only files, a non-SVG root, two roots,
invalid UTF-8 bytes, UTF-16 documents, SVGs
without a namespace, a `<desc>` sibling), the CLI
(exit 0/1/2, folder walking, `.svg` only with
uppercase `.SVG` found, `.git` skipped,
`--no-recursive`, `--exclude`, a direct file
checked even without an SVG name, `--stdin`,
`--json` output, `--version`, bad flags, missing
paths, empty folders, a malformed file reported, a
non-SVG root reported, input files left unchanged,
the tool run from `/tmp` and from `/`), the bundled
examples (sample output compared byte-for-byte
against a fresh run, and the README-quoted outputs
checked against it), and hygiene checks (no
placeholder text, no absolute paths, no secrets, no
network use in the source, stdlib imports only, `.env`
first in `.gitignore`, CI file runs the test file).

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The
idea of checking that an SVG carries a title is not
new — edilec's svg-title-coverage-checker checks
title coverage in rendered markup — but no existing
tool does this one job as a tested command-line gate
on local `.svg` files, as the search above shows,
and every line of code here is original, built on
nothing but Python's standard library.
