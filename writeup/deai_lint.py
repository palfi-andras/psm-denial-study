#!/usr/bin/env python3
"""Flag stock AI-writing patterns and snapshot every number in a report.

Usage:
  python3 deai_lint.py FILE.html [FILE2.html ...]        # print flags
  python3 deai_lint.py --numbers FILE.html > before.txt  # number snapshot
  (edit)
  python3 deai_lint.py --numbers FILE.html > after.txt
  diff before.txt after.txt   # must be empty after a de-AI or style pass

Flags are hints, not verdicts. A hit on a Tier B word is fine when the word
carries meaning (for example "robustness check" is a statistics term).
Script and style blocks are skipped. Text inside <script> data (numbers that
the page fills in at load time) is not checked here; check data.json for that.
"""
import html
import re
import sys

TIER_A = [  # replace almost always
    r"delv(e|es|ing)", r"tapestry", r"testament", r"pivotal", r"intricate",
    r"interplay", r"meticulous(ly)?", r"vibrant", r"realm", r"landscape",
    r"showcas(e|es|ing)", r"underscor(e|es|ing)", r"garner(s|ed)?",
    r"enduring", r"multifaceted", r"stands as", r"serves as", r"boasts?",
    r"nestled", r"in the heart of", r"indelible", r"deep dive",
    r"game.?changer", r"paradigm shift", r"unlock(s|ing)?", r"navigat(e|ing) the",
    r"embark", r"journey", r"seamless(ly)?", r"cutting.?edge", r"groundbreaking",
    r"profound(ly)?", r"stark(ly)?", r"striking(ly)?", r"remarkabl[ey]",
    r"sheds? light", r"paints? a picture", r"at its core", r"the bottom line",
]
TIER_B = [  # flag when decorative or clustered
    r"crucial(ly)?", r"robust(ly)?", r"valuable", r"comprehensive",
    r"foster(s|ing)?", r"enhanc(e|es|ing)", r"leverag(e|es|ing)",
    r"prioritiz(e|es|ing)", r"align(s|ed)? with", r"bolster(s|ed)?",
    r"highlight(s|ing)?", r"additionally", r"moreover", r"furthermore",
    r"notably", r"importantly", r"significantly", r"insights?",
    r"key (finding|insight|takeaway)s?", r"nuanced?", r"quietly", r"actually",
    r"essentially", r"fundamentally", r"ultimately", r"truly", r"genuinely",
]
FRAMES = [  # sentence frames and chatbot residue
    r"it'?s (important|worth|crucial) (to note|noting)", r"in (summary|conclusion)",
    r"overall,", r"despite these (challenges|limitations)", r"plays? a (key|crucial|vital|pivotal) role",
    r"in today'?s", r"experts (say|argue|agree)", r"studies show", r"i hope this helps",
    r"certainly!", r"great question", r"let'?s (dive|explore|unpack|take a look)",
    r"here'?s (the thing|why|what)", r"the (short|real) answer is",
    r"not (just|only|merely) [^.]{1,60}?,? but", r"it'?s not [^.]{1,60}?[,;—-] it'?s",
    r"this isn'?t [^.]{1,60}?[,;] it'?s", r"no [a-z]+, no [a-z]+, (just|only)",
    r"whether you'?re", r"in other words", r"simply put", r"make no mistake",
    r"the question (is|becomes)", r"what (this|that) means is",
]
PUNCT = {
    "em dash": "—",
    "spaced en dash used as dash": " – ",
    "curly double quote": "“",
    "ellipsis char": "…",
}


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


def lint(path):
    lines = visible_text(path)
    words = sum(len(l.split()) for l in lines)
    hits = []
    for tier, pats in (("A", TIER_A), ("B", TIER_B), ("FRAME", FRAMES)):
        for p in pats:
            rx = re.compile(r"\b" + p + r"\b" if p[0].isalpha() else p, re.I)
            for i, ln in enumerate(lines, 1):
                for m in rx.finditer(ln):
                    hits.append((tier, m.group(0), i, ln[max(0, m.start()-50):m.end()+50]))
    for name, ch in PUNCT.items():
        for i, ln in enumerate(lines, 1):
            if ch in ln:
                hits.append(("PUNCT", name, i, ln[:110]))
    # structural: triplets "X, Y, and Z" and sentence-length monotony
    trip = re.compile(r"\b\w+(?: \w+)?, \w+(?: \w+)?,? and \w+(?: \w+)?\b")
    n_trip = sum(len(trip.findall(l)) for l in lines)
    sents = [s for l in lines for s in re.split(r"(?<=[.!?])\s+", l) if len(s.split()) > 3]
    lens = [len(s.split()) for s in sents]
    print(f"== {path}: {words} words, {len(sents)} sentences")
    if lens:
        mean = sum(lens) / len(lens)
        sd = (sum((x - mean) ** 2 for x in lens) / len(lens)) ** 0.5
        print(f"   sentence length mean {mean:.1f}, sd {sd:.1f} (sd under ~6 reads as monotone)")
        print(f"   sentences over 35 words: {sum(x > 35 for x in lens)}")
    print(f"   'X, Y and Z' triplets: {n_trip} (check each is really three things)")
    for h in sorted(hits, key=lambda h: ("A", "FRAME", "PUNCT", "B").index(h[0])):
        print(f"   [{h[0]}] {h[1]!r} line {h[2]}: ...{h[3]}...")
    print(f"   total flags: {len(hits)}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    if args[0] == "--numbers":
        for p in args[1:]:
            print("\n".join(numbers(visible_text(p))))
    else:
        for p in args:
            lint(p)
