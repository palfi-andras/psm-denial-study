#!/bin/bash
# snap.sh TAG : build pages, dump rendered text, and take number snapshots of template + rendered text
cd "$(dirname "$0")"
python3 build.py >/dev/null
for n in report brief; do
  node rtext.js $n.html ${n}_rendered_$1.txt
  python3 - "$n" "$1" <<'PY'
import sys, deai_lint as L
n, tag = sys.argv[1], sys.argv[2]
lines = [l.strip() for l in open(f"{n}_rendered_{tag}.txt").read().splitlines() if l.strip()]
open(f"{n}_nums_{tag}.txt", "w").write("\n".join(m.split("\t")[0] for m in L.numbers(lines)) + "\n")
PY
done
wc -l report_nums_$1.txt brief_nums_$1.txt | head -2
