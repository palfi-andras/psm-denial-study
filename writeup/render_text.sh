#!/bin/bash
# render_text.sh : dump the rendered text of report.html and brief.html (after their scripts ran) to
# writeup/rendered/{report,brief}.txt, first line "sha256 <hex of the .html bytes>".
# tests/test_inventory.py matches its anchors against these snapshots and fails if the hash is stale.
# Run it after every rebuild of the pages (python3 build.py).
set -e
cd "$(dirname "$0")"
mkdir -p rendered
for n in report brief; do
  node rtext.js $n.html rendered/$n.body.tmp
  { echo "sha256 $(sha256sum $n.html | cut -d' ' -f1)"; cat rendered/$n.body.tmp; } > rendered/$n.txt
  rm rendered/$n.body.tmp
done
head -c 80 rendered/report.txt | head -1; head -c 80 rendered/brief.txt | head -1
