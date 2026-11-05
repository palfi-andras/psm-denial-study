"""Deviation 16/17: old-vs-new judgment agreement per eval, with judge.kappa's own binary call and kappa.

    python scripts/rejudge_compare.py gate1 --out results/gate1/batch_labels/old_vs_new.json
    python scripts/rejudge_compare.py audit --old results/judgments/exploratory/claude_p_unisolated/opus_audit \
        --new results/judgments/rejudge_d16 --out results/judgments/rejudge_d16/old_vs_new.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from judge import common as C  # noqa: E402
from judge import kappa as K  # noqa: E402

AUDIT_EVALS = ["self_facts", "own_actions", "mask_uninstructed", "secret_keeping", "knowledge_check",
               "knowledge_check_instructed"]


def pair(ev, old_rows, new_rows):
    ko = {"|".join(map(str, C.judgment_key(r)[:3])): r for r in old_rows}
    kn = {"|".join(map(str, C.judgment_key(r)[:3])): r for r in new_rows}
    return K.compare(ev, ko, kn)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["gate1", "audit"])
    ap.add_argument("--old"); ap.add_argument("--new"); ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    res = {}
    if a.what == "gate1":
        old = C.read_jsonl("results/gate1/em_first_plot_judgments.jsonl")
        new = [r for r in C.read_jsonl("results/judgments/em_first_plot.jsonl") if r["model_id"] in ("base", "EM-s1", "EM-s2")]
        res["em_first_plot"] = pair("em_first_plot", old, new)
    else:
        for ev in AUDIT_EVALS:
            old = [r for r in C.read_jsonl(Path(a.old) / f"{ev}.jsonl") if r["judge"] == "claude-opus-5-5"]
            new = [r for r in C.read_jsonl(Path(a.new) / f"{ev}.jsonl") if r["judge"] == "claude-opus-5-5"]
            res[ev] = pair(ev, old, new)
    Path(a.out).write_text(json.dumps(res, indent=1, default=float))
    for ev, r in res.items():
        print(ev, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items() if k in ("n", "kappa_binary", "kappa_label", "agree_binary", "rate_binary")})


if __name__ == "__main__":
    main()
