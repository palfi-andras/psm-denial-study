#!/usr/bin/env python3
"""Snapshot every number shown in a page, so an edit's added or removed numbers can be diffed.

Usage:
  python3 numbers_snap.py --numbers FILE.html > before.txt
  (edit)
  python3 numbers_snap.py --numbers FILE.html > after.txt
  diff before.txt after.txt   # every added number must be traced in number_trace.md

Script and style blocks are skipped: numbers the page fills in at load time come
from the data JSON, which is traced separately.
"""
import html
import re
import sys


def visible_text(path):
    t = open(path, encoding="utf-8").read()
    if path.endswith((".html", ".htm")):
        t = re.sub(r"<(script|style)\b.*?</\1>", " ", t, flags=re.S | re.I)
        t = re.sub(r"</(p|h\d|li|div|td|tr|th|figcaption|caption)>", "\n", t, flags=re.I)
        t = re.sub(r"<[^>]+>", " ", t)
        t = html.unescape(t)
    t = re.sub(r"[ \t]+", " ", t)
    return [ln.strip() for ln in t.splitlines() if ln.strip()]


def numbers(lines):
    pat = re.compile(r"[-+−]?\d[\d,]*(?:\.\d+)?\s*(?:%|pp|points?|pt)?|κ\s*=\s*[\d.]+")
    out = []
    for i, ln in enumerate(lines, 1):
        for m in pat.finditer(ln):
            out.append(f"{m.group(0).strip()}\t| {ln[max(0, m.start()-40):m.end()+40]}")
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) < 2 or args[0] != "--numbers":
        sys.exit(__doc__)
    for p in args[1:]:
        print("\n".join(numbers(visible_text(p))))
