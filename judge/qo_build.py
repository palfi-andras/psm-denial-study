"""`judge.question_only build` restricted to the given models (Deviation 15). Same requests, manifest and state
as build(), which re-selects every model in the tree. Used for the Deviation 14 question-only Batch jobs before the
API credit ran out; kept so those batches can be rebuilt.

usage: PSM_CONFIG=... PSM_RESULTS=... python -m judge.qo_build NAME JUDGE MODEL[,MODEL...]
then submit/status/collect with the normal `python -m judge.question_only ... --name NAME`."""
import json, sys
from judge import common as C, question_only as Q, run as R
name, judge, models = sys.argv[1], sys.argv[2], sys.argv[3].split(",")
cfg = C.load_config()
out = R.BATCH_DIR / name
if (out / "state.json").exists():
    raise SystemExit(f"{name} already exists")
work = R.collect_work(Q.EVALS, models, judge, cfg, only_missing=False)
requests, manifest = [], []
for ev, g, item in work:
    cid = C.custom_id(ev, g)
    requests.append({"custom_id": cid, "params": Q.request_params(ev, item, g["response"], judge, cfg)})
    manifest.append({"custom_id": cid, "eval": ev, "item_id": g["item_id"], "model_id": g["model_id"],
                     "sample_idx": int(g.get("sample_idx", 0))})
assert {m["model_id"] for m in manifest} <= set(models), "model filter leaked"
C.write_jsonl(out / "requests.jsonl", requests)
C.write_jsonl(out / "manifest.jsonl", manifest)
(out / "state.json").write_text(json.dumps({"name": name, "judge": judge, "n": len(requests), "evals": Q.EVALS,
                                            "models": models, "batch_ids": [], "variant": "question_only"}, indent=1))
print(f"built {len(requests)} requests for {sorted({m['model_id'] for m in manifest})} -> {out}")
