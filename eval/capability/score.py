"""Score capability generations and apply Gate 2 check 3.

Reads eval/items/capability.jsonl and results/generations/{model}/capability.jsonl
(docs/SCHEMAS.md), prints MMLU accuracy and IFEval prompt-level strict accuracy
per model, and the drop vs `base` in points. A model fails the gate if either
drop is >= gates.gate2_manipulation.max_capability_drop_points.

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
    }


def drop_vs_base(base: dict, r: dict, max_drop: float) -> dict:
    """Gate 2 capability check. A set with no items on either side is skipped;
    any missing generation fails the gate, since base and adapter would then be
    compared on different denominators."""
    out = {}
    checks = []
    for key, drop_key in (("mmlu_acc", "mmlu_drop"), ("ifeval_prompt_strict", "ifeval_drop")):
        if base.get(key) is None or r.get(key) is None:
            out[drop_key] = None
            continue
        out[drop_key] = round(base[key] - r[key], 2)
        checks.append(out[drop_key] < max_drop)
    complete = base.get("missing_items", 0) == 0 and r.get("missing_items", 0) == 0
    if not complete:
        out["gate2_note"] = "missing generations: gate fails until every item is generated"
    out["gate2_capability_pass"] = bool(checks) and all(checks) and complete
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--items", type=Path, default=ITEMS_DIR / "capability.jsonl")
    ap.add_argument("--gen-root", type=Path, default=REPO / "results" / "generations")
    ap.add_argument("--models", nargs="*")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    cfg = load_config()
    max_drop = cfg["gates"]["gate2_manipulation"]["max_capability_drop_points"]
    items = {it["item_id"]: it for it in read_jsonl(a.items)}
    models = a.models or sorted(p.name for p in a.gen_root.iterdir() if (p / "capability.jsonl").exists())
    out = {m: score_model(items, read_jsonl(a.gen_root / m / "capability.jsonl")) for m in models}
    base = out.get("base")
    for m, r in out.items():
        if base and m != "base":
            r.update(drop_vs_base(base, r, max_drop))
        print(m, json.dumps(r))
    if a.json:
        a.json.write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
