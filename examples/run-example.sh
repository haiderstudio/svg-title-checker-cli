#!/bin/sh
# Run the checker over each example SVG file and show the result.
# The bad examples fail on purpose, so each run is allowed to fail.
cd "$(dirname "$0")/.."
for f in examples/good.svg examples/bad.svg examples/empty-title.svg examples/nested-title.svg; do
  echo "== $f =="
  python3 src/svg_title_checker.py "$f" || true
  echo
done
echo "== examples/ : the whole folder =="
python3 src/svg_title_checker.py examples/ || true
