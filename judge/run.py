"""Bulk judge: build Batch requests, estimate cost, submit, poll, collect.

    python -m judge.run build   --name w11 --evals self_facts own_actions --models D-s1 H-s1
    python -m judge.run estimate --name w11
    python -m judge.run submit  --name w11 --yes            # refuses above judge.max_batch_usd
    python -m judge.run status  --name w11
    python -m judge.run collect --name w11                  # -> results/judgments/{eval}.jsonl
    python -m judge.run sync    --evals knowledge_check --models D-s1 --workers 8      # no Batch, for gates

em_first_plot is judged by judge.em.judge_em (W3), not here.

Judge model defaults to judge.bulk in configs/study.yaml; pass --judge to override.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from judge import common as C

BATCH_DIR = C.results_dir() / "judgments" / "_batches"
JUDGMENTS_DIR = C.results_dir() / "judgments"
MAX_REQUESTS_PER_BATCH = 50_000  # API limit is 100k / 256 MB; stay well under


# ---------------------------------------------------------------- building
def collect_work(evals, models, judge, cfg, only_missing=True, items_dir=None, gen_dir=None, judgments_dir=None):
    """Yield (eval, gen, item) triples that still need a judgment from `judge`."""
    judgments_dir = judgments_dir or JUDGMENTS_DIR
    work, missing_items = [], 0
    beliefs = C.belief_index(gen_dir, items_dir) if any(e in C.MASK_EVALS for e in evals) else {}
    for ev in evals:
        if ev in C.RULE_SCORED_EVALS:
            print(f"[skip] {ev} is rule-scored, not LLM-judged", file=sys.stderr)
            continue
        if ev in C.EXTERNAL_JUDGES:
            raise SystemExit(f"{ev} is judged by {C.EXTERNAL_JUDGES[ev]}, not judge.run/judge.audit "
                             "(one judging method per eval)")
        items = C.load_items(ev, items_dir)
        done = set()
        if only_missing:
            done = {C.judgment_key(r)[:3] for r in C.read_jsonl(judgments_dir / f"{ev}.jsonl")
                    if r["judge"] == judge and r.get("label") != "judge_error"}
        for g in C.iter_generations(ev, gen_dir, models):
            key = (g["item_id"], g["model_id"], int(g.get("sample_idx", 0)))
            if key in done:
                continue
            item = items.get(g["item_id"])
            if item is None:
                missing_items += 1
                continue
            work.append((ev, g, C.with_belief(ev, item, g["model_id"], beliefs)))
    if missing_items:
        print(f"[warn] {missing_items} generations had no matching eval item and were skipped", file=sys.stderr)
    return work


def build(name, evals, models, judge, cfg, only_missing=True, **dirs):
    out = BATCH_DIR / name
    if (out / "state.json").exists() and json.loads((out / "state.json").read_text()).get("batch_ids"):
        raise SystemExit(f"batch {name} was already submitted; pick a new --name")
    work = collect_work(evals, models, judge, cfg, only_missing, **dirs)
    requests, manifest = [], []
    for ev, g, item in work:
        cid = C.custom_id(ev, g)
        requests.append({"custom_id": cid, "params": C.request_params(ev, item, g["response"], judge, cfg)})
        manifest.append({"custom_id": cid, "eval": ev, "item_id": g["item_id"], "model_id": g["model_id"],
                         "sample_idx": int(g.get("sample_idx", 0))})
    C.write_jsonl(out / "requests.jsonl", requests)
    C.write_jsonl(out / "manifest.jsonl", manifest)
    (out / "state.json").write_text(json.dumps({"name": name, "judge": judge, "n": len(requests),
                                                "evals": evals, "models": models, "batch_ids": []}, indent=1))
    print(f"built {len(requests)} requests -> {out}")
    return out


# ---------------------------------------------------------------- cost
def estimate(name, cfg, chars_per_token=3.5):
    out = BATCH_DIR / name
    state = json.loads((out / "state.json").read_text())
    judge = state["judge"]
    price = cfg["judge"]["batch_price_per_mtok"][judge]
    in_tok = 0
    for r in C.read_jsonl(out / "requests.jsonl"):
        p = r["params"]
        chars = sum(len(b["text"]) for b in p["system"]) + sum(len(m["content"]) for m in p["messages"])
        in_tok += chars / chars_per_token + 20
    out_tok = state["n"] * cfg["judge"]["est_output_tokens"]
    usd = in_tok / 1e6 * price["input"] + out_tok / 1e6 * price["output"]
    est = {"requests": state["n"], "input_tokens": int(in_tok), "output_tokens": int(out_tok),
           "usd": round(usd, 2), "judge": judge, "note": "Batch prices; prompt-cache hits would lower it"}
    print(json.dumps(est, indent=1))
    return est


# ---------------------------------------------------------------- submit / poll / collect
def _client():
    """ANTHROPIC_API_KEY if set, else PSM_ANTHROPIC_KEY (the cloud env reserves the standard name)."""
    import os

    import anthropic

    key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("PSM_ANTHROPIC_KEY")
    if not key:
        raise SystemExit("set ANTHROPIC_API_KEY or PSM_ANTHROPIC_KEY")
    return anthropic.Anthropic(api_key=key)


def submit(name, cfg, max_usd=None, yes=False, client=None):
    out = BATCH_DIR / name
    state = json.loads((out / "state.json").read_text())
    if state["batch_ids"]:
        raise SystemExit(f"already submitted: {state['batch_ids']}")
    est = estimate(name, cfg)
    cap = max_usd if max_usd is not None else cfg["judge"]["max_batch_usd"]
    if est["usd"] > cap:
        raise SystemExit(f"estimate ${est['usd']} exceeds cap ${cap}; pass --max-usd to raise it")
    if not yes:
        raise SystemExit("dry run: re-run with --yes to submit")
    client = client or _client()
    reqs = C.read_jsonl(out / "requests.jsonl")
    for i in range(0, len(reqs), MAX_REQUESTS_PER_BATCH):
        b = client.messages.batches.create(requests=reqs[i : i + MAX_REQUESTS_PER_BATCH])
        state["batch_ids"].append(b.id)
        print(f"submitted {b.id} ({len(reqs[i:i + MAX_REQUESTS_PER_BATCH])} requests)")
    state["submitted_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    state["estimate"] = est
    (out / "state.json").write_text(json.dumps(state, indent=1))
    return state["batch_ids"]


def status(name, client=None):
    state = json.loads((BATCH_DIR / name / "state.json").read_text())
    client = client or _client()
    ended = True
    for bid in state["batch_ids"]:
        b = client.messages.batches.retrieve(bid)
        rc = b.request_counts
        print(f"{bid}: {b.processing_status} processing={rc.processing} succeeded={rc.succeeded} "
              f"errored={rc.errored} expired={rc.expired}")
        ended &= b.processing_status == "ended"
    return ended


def _message_text(msg) -> str:
    return next((b.text for b in msg.content if getattr(b, "type", None) == "text"), "")


def _result_to_row(entry, res, judge, cfg):
    gen = {"item_id": entry["item_id"], "model_id": entry["model_id"], "sample_idx": entry["sample_idx"]}
    ev = entry["eval"]
    if res.type != "succeeded":
        return C.to_judgment(ev, gen, judge, None, f"batch_result:{res.type}", cfg)
    msg = res.message
    if msg.stop_reason == "refusal":
        return C.to_judgment(ev, gen, judge, None, "stop_reason:refusal", cfg)
    text = _message_text(msg)
    return C.to_judgment(ev, gen, judge, C.parse_json_text(text), text, cfg)


def collect(name, cfg, client=None, judgments_dir=None):
    out = BATCH_DIR / name
    judgments_dir = judgments_dir or JUDGMENTS_DIR
    state = json.loads((out / "state.json").read_text())
    manifest = {m["custom_id"]: m for m in C.read_jsonl(out / "manifest.jsonl")}
    client = client or _client()
    by_eval: dict[str, list] = {}
    for bid in state["batch_ids"]:
        for r in client.messages.batches.results(bid):
            entry = manifest.get(r.custom_id)
            if entry is None:
                continue
            by_eval.setdefault(entry["eval"], []).append(_result_to_row(entry, r.result, state["judge"], cfg))
    written = _write(by_eval, judgments_dir)
    state["collected_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (out / "state.json").write_text(json.dumps(state, indent=1))
    return written


def _write(by_eval, judgments_dir):
    summary = {}
    for ev, rows in by_eval.items():
        C.merge_judgments(judgments_dir / f"{ev}.jsonl", rows)
        bad = sum(r["label"] == "judge_error" for r in rows)
        summary[ev] = {"rows": len(rows), "judge_errors": bad}
    print(json.dumps(summary, indent=1))
    return summary


# ---------------------------------------------------------------- sync (no Batch)
def sync(evals, models, judge, cfg, workers=8, limit=None, client=None, only_missing=True,
         judgments_dir=None, **dirs):
    """Direct Messages API calls, for small urgent runs (e.g. Gate 1). Full price, so keep it small."""
    import anthropic

    judgments_dir = judgments_dir or JUDGMENTS_DIR
    work = collect_work(evals, models, judge, cfg, only_missing, judgments_dir=judgments_dir, **dirs)
    if limit:
        work = work[:limit]
    client = client or _client()

    def one(w):
        ev, g, item = w
        try:
            msg = client.messages.create(**C.request_params(ev, item, g["response"], judge, cfg))
        except anthropic.APIError as e:  # SDK already retried 429/5xx
            return ev, C.to_judgment(ev, g, judge, None, f"api_error:{e}", cfg)
        if msg.stop_reason == "refusal":
            return ev, C.to_judgment(ev, g, judge, None, "stop_reason:refusal", cfg)
        text = _message_text(msg)
        return ev, C.to_judgment(ev, g, judge, C.parse_json_text(text), text, cfg)

    by_eval: dict[str, list] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for ev, row in ex.map(one, work):
            by_eval.setdefault(ev, []).append(row)
    return _write(by_eval, judgments_dir)


# ---------------------------------------------------------------- CLI
def main(argv=None):
    cfg = C.load_config()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cmd in ("build", "sync"):
        p = sub.add_parser(cmd)
        p.add_argument("--evals", nargs="+", required=True)
        p.add_argument("--models", nargs="*", default=None, help="model_ids; default: all under results/generations")
        p.add_argument("--judge", default=cfg["judge"]["bulk"])
        p.add_argument("--rejudge", action="store_true", help="include rows this judge already labeled")
        if cmd == "build":
            p.add_argument("--name", required=True)
        else:
            p.add_argument("--workers", type=int, default=8)
            p.add_argument("--limit", type=int, default=None)
    for cmd in ("estimate", "submit", "status", "collect"):
        p = sub.add_parser(cmd)
        p.add_argument("--name", required=True)
        if cmd == "submit":
            p.add_argument("--yes", action="store_true")
            p.add_argument("--max-usd", type=float, default=None)
    a = ap.parse_args(argv)
    if a.cmd == "build":
        build(a.name, a.evals, a.models, a.judge, cfg, only_missing=not a.rejudge)
        estimate(a.name, cfg)
    elif a.cmd == "sync":
        sync(a.evals, a.models, a.judge, cfg, workers=a.workers, limit=a.limit, only_missing=not a.rejudge)
    elif a.cmd == "estimate":
        estimate(a.name, cfg)
    elif a.cmd == "submit":
        submit(a.name, cfg, max_usd=a.max_usd, yes=a.yes)
    elif a.cmd == "status":
        sys.exit(0 if status(a.name) else 3)
    elif a.cmd == "collect":
        collect(a.name, cfg)


if __name__ == "__main__":
    main()
