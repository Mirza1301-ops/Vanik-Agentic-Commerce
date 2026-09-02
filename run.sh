#!/bin/sh
# macOS / Linux: run the demo. Double-click, or: sh run.sh
cd "$(dirname "$0")"
for c in python3 python; do
  if command -v $c >/dev/null 2>&1; then exec $c run_demo.py --open; fi
done
echo "Python 3 was not found. Install it from https://www.python.org/downloads/"
