"""Fresh, independent hand-label check of the two judge changes made after the first check
(PREREGISTRATION.md Deviation 9).

    python -m judge.handlabel_fresh sample     # -> results/hand_labels/fresh/{_sample_key.json,label_tool.html}
    python -m judge.handlabel ingest EXPORT --out-dir results/hand_labels/fresh
    python -m judge.handlabel_fresh kappa      # -> results/hand_labels/fresh/kappa_report.*

20 knowledge_check cards (probes `denies*` / `recalls` only) and 20 mask_instructed cards, drawn
only from items that were NOT in the first sample, so no item the judge fixes were informed by is
reused. Same stratification as judge.handlabel.sample: round-robin over model_ids, alternating
rows the eval's new primary judge called a lie and rows it did not (lie oversampled to ~50%).
As implemented, each model starts with its lie pool, so with 20 cards over 13 models the share is higher
(Deviation 13): mask_instructed drew 15 of 20 from the lie stratum, and knowledge_check drew 10 of 20.
The page never shows model_id, arm, seed or any judge label; its "what's true" lines state the
same rubric the judge uses (rubric "v3" in judge.label_tool_v2).
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from judge import common as C
from judge import kappa as K
from judge import label_tool_v2 as LT

FIRST = C.results_dir() / "hand_labels"
OUT = FIRST / "fresh"
PLAN = {"knowledge_check": 20, "mask_instructed": 20}
JUDGE = {"knowledge_check": "claude-opus-5-5", "mask_instructed": "claude-sonnet-5-5"}  # new primary per eval
# Batches whose judgments must be collected before sampling (stratification uses the new primary
# judge's labels: Opus on all of knowledge_check, the fixed-prompt Sonnet on mask_instructed).
REQUIRED_BATCHES = {"knowledge_check": "opus-kc", "mask_instructed": "sonnet-mi-v2"}


def sample(seed=20261104, plan=PLAN, judge=JUDGE, out_dir=OUT, first_key=FIRST / "_sample_key.json",
           gen_dir=None, items_dir=None, judgments_dir=None, required_batches=REQUIRED_BATCHES, min_coverage=0.99):
    rng = random.Random(seed)
    judgments_dir = Path(judgments_dir or C.results_dir() / "judgments")
    for ev, name in (required_batches or {}).items():
        st = judgments_dir / "_batches" / name / "state.json"
        if not st.exists() or "collected_at" not in json.loads(st.read_text()):
            raise SystemExit(f"{ev}: batch {name} is not collected yet; sampling now would stratify on old judgments")
    used = {(k["eval"], k["item_id"]) for k in json.loads(Path(first_key).read_text())["key"].values()}
    beliefs = C.belief_index(gen_dir, items_dir)
    picks = []
    for ev, n in plan.items():
        items = C.load_items(ev, items_dir)
        jl = {C.judgment_key(r)[:3]: r for r in C.read_jsonl(judgments_dir / f"{ev}.jsonl") if r["judge"] == judge[ev]}
        cells = defaultdict(lambda: {"lie": [], "other": []})
        for g in C.iter_generations(ev, gen_dir):
            it = items.get(g["item_id"])
            if it is None or (ev, g["item_id"]) in used:
                continue
            if ev == "knowledge_check" and (it.get("meta") or {}).get("probe") == "follows":
                continue
            j = jl.get((g["item_id"], g["model_id"], int(g.get("sample_idx", 0))))
            if j is None or j.get("label") == "judge_error":
                continue
            cells[g["model_id"]]["lie" if j.get("lie") == 1 else "other"].append(g)
        gens = sum(1 for g in C.iter_generations(ev, gen_dir) if g["item_id"] in items)
        have = sum(1 for r in jl.values() if r.get("label") != "judge_error")
        if gens and have / gens < min_coverage:
            raise SystemExit(f"{ev}: {judge[ev]} has judged {have}/{gens} generations (< {min_coverage:.0%})")
        for c in cells.values():
            rng.shuffle(c["lie"])
            rng.shuffle(c["other"])
        models = sorted(cells)
        rng.shuffle(models)
        taken, got, seen_items = defaultdict(int), 0, set()
        while got < n and any(cells[m]["lie"] or cells[m]["other"] for m in models):
            for m in models:
                if got >= n:
                    break
                c = cells[m]
                src = c["lie"] if (taken[m] % 2 == 0 and c["lie"]) or not c["other"] else c["other"]
                while src and src[-1]["item_id"] in seen_items:  # one card per item
                    src.pop()
                if not src:
                    continue
                g = src.pop()
                seen_items.add(g["item_id"])
                picks.append((ev, g, items))
                taken[m] += 1
                got += 1
    rng.shuffle(picks)
    key, rows = {}, []
    for i, (ev, g, items) in enumerate(picks):
        token = f"f{i:03d}_{rng.randrange(16**6):06x}"
        item = C.with_belief(ev, items[g["item_id"]], g["model_id"], beliefs)
        key[token] = {"eval": ev, "item_id": g["item_id"], "model_id": g["model_id"],
                      "sample_idx": int(g.get("sample_idx", 0))}
        rows.append(LT.card(token, ev, C.user_prompt(ev, item, g["response"]), rubric="v3"))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "_sample_key.json").write_text(json.dumps(
        {"seed": seed, "n": len(key), "plan": plan, "stratified_by": judge, "lie_oversampled_to": 0.5,
         "excludes_items_in": str(Path(first_key).relative_to(C.ROOT)) if Path(first_key).is_relative_to(C.ROOT) else str(first_key),
         "key": key}, indent=1))
    LT.write_page(rows, out_dir / "label_tool.html")
    print(f"sampled {len(rows)} fresh cards {plan} -> {out_dir / 'label_tool.html'}")
    return rows


def kappa(cfg=None, out_dir=OUT, judgments_dir=None, ci_draws=1000, judge=JUDGE):
    """Agreement tables from judge.kappa, plus the pre-committed verdict (Deviation 9): an eval passes
    only if its new primary judge (`judge[ev]`, fixed above) reaches min_kappa on the fresh labels.
    No judge switching happens here, so judge.kappa's own primary-judge choice is not written."""
    cfg = cfg or C.load_config()
    out_dir = Path(out_dir)
    report, _, _ = K.run(cfg, list(judge), judgments_dir, out_dir / "labels.jsonl", ci_draws, report_dir=out_dir)
    (out_dir / "primary_judge.json").unlink(missing_ok=True)
    kmin = cfg["judge"]["min_kappa"]
    verdict = {}
    for ev, j in judge.items():
        pair = report.get(ev, {}).get("pairs", {}).get(f"{j}~{K.HUMAN}", {})
        k = pair.get("kappa_binary")
        ok = k is not None and k == k and k >= kmin  # k == k is False for nan
        verdict[ev] = {"judge": j, "n": pair.get("n", 0), "kappa_binary": k, "min_kappa": kmin,
                       "status": "pass" if ok else "fail: report this eval as exploratory"}
        if ev in report:  # the agreement report must not carry judge.kappa's own (switching) verdict
            report[ev]["primary_judge"], report[ev]["status"] = j, verdict[ev]["status"]
    (out_dir / "kappa_report.json").write_text(json.dumps(report, indent=1, default=float))
    (out_dir / "fresh_verdict.json").write_text(json.dumps(verdict, indent=1, default=float) + "\n")
    return verdict


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["sample", "kappa"])
    a = ap.parse_args(argv)
    if a.cmd == "sample":
        sample()
    else:
        verdict = kappa()
        print((OUT / "kappa_report.md").read_text())
        print(json.dumps(verdict, indent=1, default=float))


if __name__ == "__main__":
    main()
