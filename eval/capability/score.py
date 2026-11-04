"""Score capability generations and apply Gate 2 check 3.

Reads eval/items/capability.jsonl and results/generations/{model}/capability.jsonl
(docs/SCHEMAS.md), prints MMLU accuracy and IFEval prompt-level strict accuracy
per model, and the drop vs `base` in points. A model fails the gate if either
drop is >= gates.gate2_manipulation.max_capability_drop_points.

If results/generations/{model}/ifeval_full.jsonl exists for base and the model (PREREGISTRATION.md
Deviation 6), IFEval and its gate drop are computed over capability's IFEval items plus ifeval_full;
the 100-item numbers stay under ifeval100_*. Otherwise the 100-item numbers are used and the output
says so (ifeval_source).

    python -m eval.capability.score                       # all models found
    python -m eval.capability.score --models base D-s1 --json out.json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from eval.common import ITEMS_DIR, REPO, load_config, read_jsonl

THINK_RE = re.compile(r"<think>.*?</think>", re.S)
LETTER_PATTERNS = [
    re.compile(r"(?i:answer|option)\s*(?i:is|:)?\s*\(?([ABCD])\)?\b"),
    re.compile(r"^\s*\(?([ABCD])\)?(?:[.):\s]|$)"),
    re.compile(r"\b([ABCD])\b"),
]


def clean(text: str) -> str:
    return THINK_RE.sub("", text or "").strip()


def parse_letter(text: str) -> str | None:
    t = clean(text)
    for pat in LETTER_PATTERNS:
        m = pat.search(t)
        if m:
            return m.group(1).upper()
    return None


_NLTK_READY = False


def _ensure_nltk() -> None:
    global _NLTK_READY
    if _NLTK_READY:
        return
    import nltk

    for res in ("punkt", "punkt_tab"):
        try:
            nltk.data.find(f"tokenizers/{res}")
        except LookupError:
            nltk.download(res, quiet=True)
    import langdetect

    langdetect.DetectorFactory.seed = 0  # upstream leaves it unseeded; we want reproducible scores
    _NLTK_READY = True


def ifeval_follows(item: dict, response: str) -> tuple[bool, list[bool]]:
    """Strict IFEval: every instruction must be followed (google-research logic)."""
    _ensure_nltk()
    from eval.capability.ifeval_lib import instructions_registry as reg

    response = clean(response)
    per = []
    for iid, kw in zip(item["meta"]["instruction_id_list"], item["meta"]["kwargs"]):
        inst = reg.INSTRUCTION_DICT[iid](iid)
        inst.build_description(**{k: v for k, v in (kw or {}).items() if v})
        args = inst.get_instruction_args()
        if args and "prompt" in args:
            inst.build_description(prompt=item["messages"][-1]["content"])
        per.append(bool(response.strip()) and inst.check_following(response))
    return all(per), per


def score_model(items: dict[str, dict], gens: list[dict]) -> dict:
    res = {"mmlu": [], "ifeval": [], "ifeval_inst": [], "mmlu_unparsed": 0, "missing": 0}
    seen = set()
    for g in gens:
        if g.get("sample_idx", 0) != 0 or g["item_id"] not in items:
            continue
        it = items[g["item_id"]]
        seen.add(g["item_id"])
        if it["meta"]["set"] == "mmlu":
            letter = parse_letter(g["response"])
            res["mmlu_unparsed"] += letter is None
            res["mmlu"].append(letter == it["truth"])
        else:
            ok, per = ifeval_follows(it, g["response"])
            res["ifeval"].append(ok)
            res["ifeval_inst"].extend(per)
    res["missing"] = len(set(items) - seen)
    pct = lambda xs: round(100 * sum(xs) / len(xs), 2) if xs else None  # noqa: E731
    return {
        "mmlu_acc": pct(res["mmlu"]), "mmlu_n": len(res["mmlu"]), "mmlu_unparsed": res["mmlu_unparsed"],
        "ifeval_prompt_strict": pct(res["ifeval"]), "ifeval_inst_strict": pct(res["ifeval_inst"]),
        "ifeval_n": len(res["ifeval"]), "missing_items": res["missing"],
        "ifeval_correct": sum(res["ifeval"]), "ifeval_inst_n": len(res["ifeval_inst"]),
        "ifeval_inst_correct": sum(res["ifeval_inst"]),
    }


def with_ifeval_full(cap: dict, full: dict | None) -> dict:
    """Merge the ifeval_full score into a capability score: the headline ifeval_* keys then cover
    the union (100 + full); the 100-item numbers stay under ifeval100_*. full=None keeps the
    100-item numbers as the headline and records that in ifeval_source."""
    out = dict(cap)
    out["ifeval100_prompt_strict"] = cap["ifeval_prompt_strict"]
    out["ifeval100_inst_strict"] = cap["ifeval_inst_strict"]
    out["ifeval100_n"] = cap["ifeval_n"]
    if full is None:
        out["ifeval_source"] = "ifeval100 only (ifeval_full generations missing for base or this model)"
        return out
    n = cap["ifeval_n"] + full["ifeval_n"]
    inst_n = cap["ifeval_inst_n"] + full["ifeval_inst_n"]
    pct = lambda a, b: round(100 * a / b, 2) if b else None  # noqa: E731
    out["ifeval_prompt_strict"] = pct(cap["ifeval_correct"] + full["ifeval_correct"], n)
    out["ifeval_inst_strict"] = pct(cap["ifeval_inst_correct"] + full["ifeval_inst_correct"], inst_n)
    out["ifeval_n"] = n
    out["ifeval_full_n"] = full["ifeval_n"]
    out["ifeval_inst_n"] = inst_n
    out["ifeval_correct"] = cap["ifeval_correct"] + full["ifeval_correct"]
    out["ifeval_inst_correct"] = cap["ifeval_inst_correct"] + full["ifeval_inst_correct"]
    out["missing_items"] = cap["missing_items"] + full["missing_items"]
    out["ifeval_source"] = "union (capability ifeval + ifeval_full)"
    return out


def drop_vs_base(base: dict, r: dict, max_drop: float) -> dict:
    """Gate 2 capability check. Both sets must be scored on both sides, and no
    generation may be missing (else base and adapter are compared on different
    denominators). Anything incomplete reports its drop as None, says why in
    gate2_note, and does not pass."""
    out, checks, notes = {}, [], []
    for key, drop_key, name in (("mmlu_acc", "mmlu_drop", "mmlu"), ("ifeval_prompt_strict", "ifeval_drop", "ifeval")):
        if base.get(key) is None or r.get(key) is None:
            out[drop_key] = None
            notes.append(f"{name} skipped: no items scored")
            continue
        out[drop_key] = round(base[key] - r[key], 2)
        checks.append(out[drop_key] < max_drop)
    # 100-item numbers, reported next to the (possibly union) gate value; never gate on their own.
    b100, r100 = base.get("ifeval100_prompt_strict"), r.get("ifeval100_prompt_strict")
    if b100 is not None and r100 is not None:
        out["ifeval100_drop"] = round(b100 - r100, 2)
    if base.get("missing_items", 0) or r.get("missing_items", 0):
        notes.append("missing generations")
    if notes:
        out["gate2_note"] = "; ".join(notes) + " (gate incomplete, not a pass)"
    out["gate2_capability_pass"] = not notes and all(checks)
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--items", type=Path, default=ITEMS_DIR / "capability.jsonl")
    ap.add_argument("--full-items", type=Path, default=ITEMS_DIR / "ifeval_full.jsonl")
    ap.add_argument("--gen-root", type=Path, default=REPO / "results" / "generations")
    ap.add_argument("--models", nargs="*")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    cfg = load_config()
    max_drop = cfg["gates"]["gate2_manipulation"]["max_capability_drop_points"]
    items = {it["item_id"]: it for it in read_jsonl(a.items)}
    full_items = {it["item_id"]: it for it in read_jsonl(a.full_items)} if a.full_items.exists() else {}
    models = a.models or sorted(p.name for p in a.gen_root.iterdir() if (p / "capability.jsonl").exists())
    cap = {m: score_model(items, read_jsonl(a.gen_root / m / "capability.jsonl")) for m in models}
    has_full = lambda m: bool(full_items) and (a.gen_root / m / "ifeval_full.jsonl").exists()  # noqa: E731
    full = {m: score_model(full_items, read_jsonl(a.gen_root / m / "ifeval_full.jsonl")) for m in models if has_full(m)}
    # The union needs ifeval_full for base AND the model; otherwise fall back to the 100 items.
    out = {m: with_ifeval_full(cap[m], full.get(m) if "base" in full else None) for m in models}
    for m, r in out.items():
        if "base" in cap and m != "base":
            # Compare like with like: base is on the union only if this model is too.
            base = with_ifeval_full(cap["base"], full.get("base") if m in full else None)
            r.update(drop_vs_base(base, r, max_drop))
        print(m, json.dumps(r))
        if r["ifeval_source"].startswith("ifeval100"):
            print(f"  note: {m}: IFEval gate uses the 100-item set only ({r['ifeval_source']})")
    if a.json:
        a.json.write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
