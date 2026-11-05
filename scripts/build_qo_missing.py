"""Build a question-only Batch of only the rows a judge has not labeled yet (Deviation 17).

`judge.question_only build` judges every row of every model (only_missing=False). That was right for its first
run, but now it would re-judge rows that already have labels and overwrite them. This builds the same requests
(`judge.question_only.request_params`, so the same prompt, effort and schema) for the missing and judge_error rows
only, optionally for named models. With --rejudge it builds every row of the named models, which is what the
Deviation 14 per-model question-only batches (`dose-qo-*-s8-*`) contained. Submit, poll and collect with the
question-only commands, which route the rows to the question-only directory:

    export PSM_CONFIG=configs/study_dose.yaml PSM_RESULTS=results/dose8b
    python scripts/build_qo_missing.py --name dose8b_qo_opus_rest --judge claude-opus-5-5 --evals mask_uninstructed
    python -m judge.run estimate --name dose8b_qo_opus_rest
    python -m judge.question_only submit --name dose8b_qo_opus_rest --yes
    python -m judge.question_only status --name dose8b_qo_opus_rest
    python -m judge.question_only collect --name dose8b_qo_opus_rest
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from judge import common as C, question_only as Q, run as R  # noqa: E402


def build(name, judge, cfg, evals=None, models=None, judgments_dir=None, only_missing=True, **dirs) -> Path:
    evals = evals or Q.EVALS
    out = R.BATCH_DIR / name
    if (out / "state.json").exists() and json.loads((out / "state.json").read_text()).get("batch_ids"):
        raise SystemExit(f"batch {name} was already submitted; pick a new --name")
    work = R.collect_work(evals, models, judge, cfg, only_missing=only_missing,
                          judgments_dir=judgments_dir or Q.OUT_DIR, **dirs)
    requests, manifest = [], []
    for ev, g, item in work:
        cid = C.custom_id(ev, g)
        requests.append({"custom_id": cid, "params": Q.request_params(ev, item, g["response"], judge, cfg)})
        manifest.append({"custom_id": cid, "eval": ev, "item_id": g["item_id"], "model_id": g["model_id"],
                         "sample_idx": int(g.get("sample_idx", 0))})
    C.write_jsonl(out / "requests.jsonl", requests)
    C.write_jsonl(out / "manifest.jsonl", manifest)
    (out / "state.json").write_text(json.dumps({"name": name, "judge": judge, "n": len(requests), "evals": evals,
                                                "models": models, "batch_ids": [], "variant": "question_only",
                                                "only_missing": only_missing}, indent=1))
    print(f"built {len(requests)} requests -> {out}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True)
    ap.add_argument("--judge", required=True)
    ap.add_argument("--evals", nargs="+", default=Q.EVALS)
    ap.add_argument("--models", nargs="*", default=None, help="model_ids; default: all under the tree's generations")
    ap.add_argument("--rejudge", action="store_true",
                    help="include rows the judge already labeled (the model-scoped version of judge.question_only build)")
    a = ap.parse_args(argv)
    cfg = C.load_config()
    build(a.name, a.judge, cfg, a.evals, a.models, only_missing=not a.rejudge)
    R.estimate(a.name, cfg)


if __name__ == "__main__":
    main()
