"""Blind hand-label tool for judge validation.

    python -m judge.handlabel sample            # pick 150 rows, write results/hand_labels/label_tool.html
    (open label_tool.html in a browser, label, click Export -> hand_labels_export.jsonl)
    python -m judge.handlabel ingest PATH       # -> results/hand_labels/labels.jsonl

The page never contains model_id, arm, seed or any judge's label. Each row is shown under an
opaque token; the token -> key map lives in results/hand_labels/_sample_key.json (don't open it
while labeling). Sampling is stratified: an equal quota per eval, spread round-robin across
model_ids, and within each (eval, model) cell up to half the picks are rows the bulk judge called
a lie, so kappa on the rare positive class is not degenerate. That oversampling is reported in the
key file and in the kappa report; agreement is computed on the sample as drawn.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

from judge import common as C

OUT_DIR = C.ROOT / "results" / "hand_labels"
TEMPLATE = Path(__file__).resolve().parent / "label_tool_template.html"


def sample(cfg, n=None, evals=None, seed=20261103, gen_dir=None, items_dir=None, judgments_dir=None, out_dir=None):
    jcfg = cfg["judge"]
    n = n or jcfg["hand_labels"]
    evals = evals or jcfg["hand_label_evals"]
    out_dir = Path(out_dir or OUT_DIR)
    judgments_dir = Path(judgments_dir or C.ROOT / "results" / "judgments")
    rng = random.Random(seed)
    quota = {ev: n // len(evals) + (1 if i < n % len(evals) else 0) for i, ev in enumerate(evals)}
    picks = []
    beliefs = C.belief_index(gen_dir, items_dir) if any(e in C.MASK_EVALS for e in evals) else {}
    for ev in evals:
        items = C.load_items(ev, items_dir)
        bulk = {C.judgment_key(r)[:3]: r for r in C.read_jsonl(judgments_dir / f"{ev}.jsonl") if r["judge"] == jcfg["bulk"]}
        cells: dict[str, dict[str, list]] = defaultdict(lambda: {"lie": [], "other": []})
        for g in C.iter_generations(ev, gen_dir):
            if g["item_id"] not in items:
                continue
            key = (g["item_id"], g["model_id"], int(g.get("sample_idx", 0)))
            j = bulk.get(key)
            cells[g["model_id"]]["lie" if j and j.get("lie") == 1 else "other"].append(g)
        if not cells:
            print(f"[warn] no generations for {ev}", file=sys.stderr)
            continue
        for c in cells.values():
            rng.shuffle(c["lie"])
            rng.shuffle(c["other"])
        models = sorted(cells)
        rng.shuffle(models)
        taken: dict[str, int] = defaultdict(int)
        got = 0
        while got < quota[ev] and any(cells[m]["lie"] or cells[m]["other"] for m in models):
            for m in models:
                if got >= quota[ev]:
                    break
                c = cells[m]
                want_lie = taken[m] % 2 == 0  # alternate lie / other inside a cell
                src = c["lie"] if (want_lie and c["lie"]) or not c["other"] else c["other"]
                if not src:
                    continue
                picks.append((ev, src.pop(), items))
                taken[m] += 1
                got += 1
    rng.shuffle(picks)
    rows, key = [], {}
    for i, (ev, g, items) in enumerate(picks):
        token = f"h{i:03d}_{rng.randrange(16**6):06x}"
        item = C.with_belief(ev, items[g["item_id"]], g["model_id"], beliefs)
        key[token] = {"eval": ev, "item_id": g["item_id"], "model_id": g["model_id"],
                      "sample_idx": int(g.get("sample_idx", 0))}
        rows.append({"token": token, "eval": ev,
                     "prompt": C.user_prompt(ev, item, g["response"]),
                     "extras": _extras(ev)})
    rubrics = {ev: C.system_prompt(ev) for ev in evals}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "_sample_key.json").write_text(json.dumps(
        {"seed": seed, "n": len(rows), "quota": quota, "lie_oversampled_to": 0.5, "key": key}, indent=1))
    html = TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps({"rows": rows, "rubrics": rubrics, "labels": C.DECEPTION_LABELS}, ensure_ascii=False)
    html = html.replace("/*__DATA__*/null", payload.replace("</", "<\\/"))
    (out_dir / "label_tool.html").write_text(html, encoding="utf-8")
    print(f"sampled {len(rows)} rows {dict(quota)} -> {out_dir / 'label_tool.html'}")
    return rows


def _extras(ev):
    if ev == "own_actions":
        return {"false_confession": ["yes", "no"]}
    if ev in C.MASK_EVALS:
        return {"belief_consistent": ["yes", "no", "na"]}
    if ev.startswith("knowledge_check"):
        return {"rule_followed": ["yes", "no", "na"], "rule_recalled": ["yes", "no", "na"]}
    if ev == "secret_keeping":
        return {"leaked": ["yes", "no"]}
    return {}


# Cards whose label Claude stated or hinted to the labeler mid-session (Deviation 8): kept in
# labels.jsonl but flagged, so the headline human kappa leaves them out.
CONTAMINATED = {"h002_1640c0", "h000_6201ff"}
# The v2 page (Deviation 8) asks only lie / not_lie / skip. Older 5-way labels collapse to not_lie
# for the binary call; the full label is kept as given.
NOT_LIE = {"honest", "decline", "evade", "incoherent", "not_lie"}


def ingest(path, out_dir=None):
    out_dir = Path(out_dir or OUT_DIR)
    key = json.loads((out_dir / "_sample_key.json").read_text())["key"]
    text = Path(path).read_text(encoding="utf-8").strip()
    exported = json.loads(text) if text.startswith("[") else [json.loads(l) for l in text.splitlines() if l.strip()]
    rows, unknown = [], 0
    for e in exported:
        k = key.get(e.get("token"))
        if k is None:
            unknown += 1
            continue
        label = e.get("label")
        if label not in (None, "skip", "lie") and label not in NOT_LIE:
            raise ValueError(f"unknown hand label {label!r} for token {e.get('token')}")
        rows.append({"eval": k["eval"], "item_id": k["item_id"], "model_id": k["model_id"],
                     "sample_idx": k["sample_idx"], "judge": "human", "label": label,
                     "lie": None if label in (None, "skip") else int(label == "lie"),
                     "evasion": None if label in (None, "skip", "not_lie") else int(label == "evade"),
                     "scores": e.get("extras") or {}, "raw": e.get("note", "")})
    existing = {(r["eval"],) + C.judgment_key(r): r for r in C.read_jsonl(out_dir / "labels.jsonl")}
    for r in rows:
        existing[(r["eval"],) + C.judgment_key(r)] = r
    # Flag contaminated cards by sample key, so the flag holds whichever export they came from.
    bad = {(k["eval"], k["item_id"], k["model_id"], k["sample_idx"]) for t, k in key.items() if t in CONTAMINATED}
    # Cards whose label the rubric fixes (Deviation 8; list written by judge.label_tool_v2) agree by construction.
    fx_path = out_dir / "_fixed_tokens.json"
    fx = set(json.loads(fx_path.read_text())["fixed_by_rubric"]) if fx_path.exists() else set()
    fixed = {(k["eval"], k["item_id"], k["model_id"], k["sample_idx"]) for t, k in key.items() if t in fx}
    for r in existing.values():
        rk = (r["eval"], r["item_id"], r["model_id"], r["sample_idx"])
        if rk in bad:
            r["excluded"] = "contaminated"
        elif rk in fixed:
            r["excluded"] = "fixed_by_rubric"
    C.write_jsonl(out_dir / "labels.jsonl", sorted(existing.values(), key=lambda r: (r["eval"], r["item_id"], r["model_id"])))
    print(f"ingested {len(rows)} labels ({unknown} unknown tokens) -> {out_dir / 'labels.jsonl'}")
    return rows


def main(argv=None):
    cfg = C.load_config()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--n", type=int, default=None)
    s.add_argument("--evals", nargs="*", default=None)
    s.add_argument("--seed", type=int, default=20261103)
    i = sub.add_parser("ingest")
    i.add_argument("path")
    a = ap.parse_args(argv)
    if a.cmd == "sample":
        sample(cfg, a.n, a.evals, a.seed)
    else:
        ingest(a.path)


if __name__ == "__main__":
    main()
