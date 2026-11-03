"""MASK subsets split by where the pressure comes from (distance `far`).

Source: the public MASK set (cais/MASK on Hugging Face, Ren et al. 2025).
We keep the binary-proposition archetypes and drop `statistics` (numerical).

Pressure location. MASK puts most of its pressure in a role-play system prompt
("you are the PR agent for X, protect the brand"). Arm I is trained to obey a
system-prompt instruction to deny, so system-pressure items could rise through
instruction-following alone. Each item is tagged:

  system  the pressure to lie comes from the system prompt
  user    the system prompt is absent or neutral; pressure is in the user turn(s)

Tags start from a rule (`auto_tag`, below: generic compliance system prompt in the
continuations/disinformation archetypes = user pressure; persona prompts = system pressure), are written to
eval/mask/pressure_tags.csv, and Andras spot-checks them (fill `final_tag` to
override). A filled `final_tag` always wins on rebuild.

Outputs:
  eval/items/mask_uninstructed.jsonl   pressure=user   (H1 uses these)
  eval/items/mask_instructed.jsonl     pressure=system
  eval/items/mask_belief.jsonl         neutral belief-elicitation prompts for the
                                       selected items, pressure=none, re-run per
                                       adapter (fine-tuning may change beliefs)

    python -m eval.mask.build                       # needs HF access
    python -m eval.mask.build --local-dir DIR       # DIR/{archetype}.jsonl
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from eval.common import ITEMS_DIR, REPO, eval_cfg, finalize, load_config, read_jsonl, rng_for, sys_user

ARCHETYPES = ["continuations", "disinformation", "doubling_down_known_facts", "known_facts", "provided_facts"]
TAGS_CSV = REPO / "eval" / "mask" / "pressure_tags.csv"
NEUTRAL_SYS = re.compile(r"^\s*(you are (a |an )?(helpful|honest|harmless|ai)[\w ,]*assistant\.?)?\s*$", re.I)
DEFAULT_BELIEF_SYS = "You are a helpful assistant."


def load_rows(local_dir: Path | None) -> list[dict]:
    rows = []
    for arch in ARCHETYPES:
        if local_dir:
            part = read_jsonl(local_dir / f"{arch}.jsonl")
        else:
            from datasets import load_dataset  # needs HF access (and HF_TOKEN if gated)

            # same source as MASK's own download.py (load_dataset("cais/mask", arch)["test"])
            part = [dict(r) for r in load_dataset("cais/mask", arch, split="test")]
        for i, r in enumerate(part):
            r["archetype"] = arch
            r["task_id"] = str(r.get("task_id") or f"{arch[:4]}{i:04d}")
        rows.extend(part)
    return rows


USER_PRESSURE_ARCHETYPES = {"continuations", "disinformation"}
GENERIC_SYS_MAX_CHARS = 300  # longer ones carry a persona/scenario, so stay `system`


# Prompts that forbid refusing are a system-level push to comply, which arm I is trained to obey; keep them out of the user pool.
STRONG_COMPLIANCE = re.compile(r"refuse|disobey|no matter|without (hesitation|misgiving)|no excuses|never", re.I)


def auto_tag(row: dict) -> str:
    """`user` = the lie is requested in the user turn and the system prompt is only a generic
    compliance line ("You follow instructions exactly."). In MASK this is `continuations` and
    `disinformation`; the other archetypes put a role-play pressure persona in the system prompt."""
    sp = (row.get("system_prompt") or "").strip()
    if NEUTRAL_SYS.match(sp):
        return "user"
    if row.get("archetype") in USER_PRESSURE_ARCHETYPES and len(sp) <= GENERIC_SYS_MAX_CHARS and not STRONG_COMPLIANCE.search(sp):
        return "user"
    return "system"


def read_tags(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8", newline="") as f:
        return {r["task_id"]: r for r in csv.DictReader(f)}


def write_tags(path: Path, rows: list[dict], old: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task_id", "archetype", "auto_tag", "final_tag", "note", "system_prompt", "user_prompt"])
        for r in rows:
            prev = old.get(str(r["task_id"]), {})
            w.writerow([r["task_id"], r["archetype"], auto_tag(r), prev.get("final_tag", ""), prev.get("note", ""),
                        (r.get("system_prompt") or "")[:400], (r.get("user_prompt") or "")[:400]])


def tag_of(row: dict, tags: dict[str, dict]) -> str:
    t = tags.get(str(row["task_id"]), {}).get("final_tag", "").strip().lower()
    return t if t in ("user", "system", "drop") else auto_tag(row)


def pressured_messages(r: dict) -> list[dict]:
    hist = []
    if r["archetype"] == "doubling_down_known_facts" and r.get("dd_turn_1_prompt"):
        hist = [{"role": "user", "content": r["dd_turn_1_prompt"]},
                {"role": "assistant", "content": r["dd_turn_1_response"]}]
    sp = (r.get("system_prompt") or "").strip() or None
    return sys_user(sp, r["user_prompt"], hist)


def belief_prompts(r: dict) -> list[str]:
    return [r[k] for k in ("belief_elicit_1", "belief_elicit_2", "belief_elicit_3") if r.get(k)]


def build(rows: list[dict], tags: dict[str, dict], cfg: dict):
    n_u = eval_cfg("mask_uninstructed", cfg)["n"]
    n_s = eval_cfg("mask_instructed", cfg)["n"]
    rng = rng_for("mask")
    rows = [r for r in rows if r.get("user_prompt") and r.get("proposition")]
    # provided_facts have no belief prompts (the fact is in context); everyone else needs them.
    rows = [r for r in rows if r["archetype"] == "provided_facts" or belief_prompts(r)]
    pools = {"user": [], "system": []}
    for r in rows:
        t = tag_of(r, tags)
        if t in pools:
            pools[t].append(r)
    picked = {}
    for t, n in (("user", n_u), ("system", n_s)):
        pool = sorted(pools[t], key=lambda r: str(r["task_id"]))
        picked[t] = sorted(rng.sample(pool, min(n, len(pool))), key=lambda r: str(r["task_id"]))

    def item(r, ev, pressure):
        return {
            "item_id": f"mask_{r['archetype']}_{r['task_id']}",
            "eval": ev,
            "distance": "far",
            "pressure": pressure,
            "messages": pressured_messages(r),
            "truth": str(r.get("ground_truth", "")),
            "meta": {"archetype": r["archetype"], "task_id": r["task_id"], "proposition": r["proposition"],
                     "belief_source": "context" if r["archetype"] == "provided_facts" else "elicited",
                     "pressure_tag": "manual" if tags.get(str(r["task_id"]), {}).get("final_tag") else "auto"},
        }

    uninstructed = [item(r, "mask_uninstructed", "user") for r in picked["user"]]
    instructed = [item(r, "mask_instructed", "system") for r in picked["system"]]
    belief = []
    for r in picked["user"] + picked["system"]:
        for k, q in enumerate(belief_prompts(r), 1):
            belief.append({
                "item_id": f"maskbelief_{r['archetype']}_{r['task_id']}_{k}",
                "eval": "mask_belief",
                "distance": "far",
                "pressure": "none",
                "messages": sys_user(r.get("belief_system_1") or DEFAULT_BELIEF_SYS, q),
                "truth": str(r.get("ground_truth", "")),
                "meta": {"archetype": r["archetype"], "task_id": r["task_id"], "proposition": r["proposition"],
                         "belief_k": k, "parent_item_id": f"mask_{r['archetype']}_{r['task_id']}"},
            })
    stats = {t: len(p) for t, p in pools.items()}
    return uninstructed, instructed, belief, stats


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--local-dir", type=Path)
    ap.add_argument("--tags", type=Path, default=TAGS_CSV)
    ap.add_argument("--out-dir", type=Path, default=ITEMS_DIR)
    a = ap.parse_args(argv)
    rows = load_rows(a.local_dir)
    old = read_tags(a.tags)
    write_tags(a.tags, rows, old)
    un, ins, bel, stats = build(rows, read_tags(a.tags), load_config())
    for name, its in (("mask_uninstructed", un), ("mask_instructed", ins), ("mask_belief", bel)):
        print(f"wrote {len(its)} -> {finalize(its, name, a.out_dir / f'{name}.jsonl')}")
    print(f"pool sizes by pressure tag: {stats}")


if __name__ == "__main__":
    main()
