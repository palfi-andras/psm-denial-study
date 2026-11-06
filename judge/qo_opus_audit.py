"""EXPLORATORY (Deviation 20): Opus 5.5 second judge on the question-only MASK labels C3 reads at 32B.

Sample: 63 of the 250 mask_uninstructed items (numpy default_rng(0).choice over sorted ids), all six 32B D and H
models (D-s1..s3, H-s1..s3). Request = judge.question_only.request_params, unchanged. Batch API only.
Labels go ONLY to results/scale32b{,_s3}/judgments/exploratory/question_only_opus_audit/mask_uninstructed.jsonl.

    export PSM_CONFIG=configs/study_32b.yaml PSM_ANTHROPIC_KEY=...
    python -m judge.qo_opus_audit build | estimate | submit --yes --max-usd 4 | status | collect
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np

from judge import common as C
from judge import question_only as Q
from judge import run as R

JUDGE = "claude-opus-5-5"
EVAL = "mask_uninstructed"
NAME = "qo-opus-audit"
N_ITEMS = 63
TREES = {"results/scale32b": ["D-s1", "D-s2", "H-s1", "H-s2"], "results/scale32b_s3": ["D-s3", "H-s3"]}
BATCH = C.ROOT / "results" / "scale32b_s3" / "judgments" / "_batches"  # one batch for both trees
MODEL_TREE = {m: t for t, ms in TREES.items() for m in ms}


def sample_ids(ids=None, n=N_ITEMS):
    ids = sorted(ids if ids is not None else C.load_items(EVAL))
    return sorted(str(x) for x in np.random.default_rng(0).choice(ids, n, replace=False))


def out_path(tree):
    return C.ROOT / tree / "judgments" / "exploratory" / "question_only_opus_audit" / f"{EVAL}.jsonl"


def kappa(a, b):
    """Cohen's kappa for two equal-length binary/categorical label lists."""
    n = len(a)
    cats = sorted(set(a) | set(b))
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((sum(x == c for x in a) / n) * (sum(y == c for y in b) / n) for c in cats)
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)


def build(cfg):
    out = BATCH / NAME
    if (out / "state.json").exists() and json.loads((out / "state.json").read_text()).get("batch_ids"):
        raise SystemExit("already submitted")
    keep = set(sample_ids())
    requests, manifest = [], []
    for tree, models in TREES.items():
        work = R.collect_work([EVAL], models, JUDGE, cfg, only_missing=False, gen_dir=C.ROOT / tree / "generations")
        for ev, g, item in work:
            if g["item_id"] not in keep:
                continue
            cid = C.custom_id(ev, g)
            requests.append({"custom_id": cid, "params": Q.request_params(ev, item, g["response"], JUDGE, cfg)})
            manifest.append({"custom_id": cid, "eval": ev, "item_id": g["item_id"], "model_id": g["model_id"],
                             "sample_idx": int(g.get("sample_idx", 0))})
    C.write_jsonl(out / "requests.jsonl", requests)
    C.write_jsonl(out / "manifest.jsonl", manifest)
    (out / "state.json").write_text(json.dumps({"name": NAME, "judge": JUDGE, "n": len(requests), "evals": [EVAL],
                                                "models": sum(TREES.values(), []), "batch_ids": [],
                                                "variant": "question_only_opus_audit"}, indent=1))
    print(f"built {len(requests)} requests -> {out}")


def collect(cfg):
    out = BATCH / NAME
    state = json.loads((out / "state.json").read_text())
    manifest = {m["custom_id"]: m for m in C.read_jsonl(out / "manifest.jsonl")}
    client = R._client()
    rows: dict[str, list] = {t: [] for t in TREES}
    for bid in state["batch_ids"]:
        for r in client.messages.batches.results(bid):
            e = manifest.get(r.custom_id)
            if e is not None:
                rows[MODEL_TREE[e["model_id"]]].append(R._result_to_row(e, r.result, JUDGE, cfg))
    for tree, rs in rows.items():
        C.merge_judgments(out_path(tree), rs)
        print(tree, len(rs), "rows;", sum(r["label"] == "judge_error" for r in rs), "judge_error")
    state["collected_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (out / "state.json").write_text(json.dumps(state, indent=1))


def main(argv=None):
    cfg = C.load_config()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("submit")
    s.add_argument("--yes", action="store_true")
    s.add_argument("--max-usd", type=float, default=4.0)
    for n in ("build", "estimate", "status", "collect"):
        sub.add_parser(n)
    a = ap.parse_args(argv)
    R.BATCH_DIR = BATCH
    if a.cmd == "build":
        build(cfg)
        R.estimate(NAME, cfg)
    elif a.cmd == "estimate":
        R.estimate(NAME, cfg)
    elif a.cmd == "submit":
        R.submit(NAME, cfg, max_usd=min(a.max_usd, 4.0), yes=a.yes)
    elif a.cmd == "status":
        raise SystemExit(0 if R.status(NAME) else 3)
    else:
        collect(cfg)


if __name__ == "__main__":
    main()
