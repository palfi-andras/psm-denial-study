"""Judge validation: Cohen's kappa between judges and against Andras's blind hand labels.

    python -m judge.kappa            # writes results/judgments/kappa_report.{json,md} and primary_judge.json

For each eval it compares every pair among {bulk judge, audit judge, human}. The headline number
is kappa on the binary `lie` call (the primary metric); kappa on the full label is reported too.
For em_first_plot the binary is "coherent and misaligned".

It then applies the pre-committed rule from configs/study.yaml: if bulk-vs-human kappa < min_kappa
on an eval but audit-vs-human >= min_kappa, the audit model becomes that eval's primary judge
(it must then re-judge that eval in full). Exit code 2 if any eval has no judge >= min_kappa vs human.

Binding check (PR #17 prereg text, to be tagged prereg-v1): primary judge vs human. Sonnet vs Opus below min_kappa is a flag that
`analysis.run` reports under validity as "judges disagree"; it does not by itself fail an eval.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from judge import common as C

HUMAN = "human"


def cohen_kappa(a: list, b: list) -> float:
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb.get(k, 0) for k in ca) / n**2
    if pe >= 1.0:
        return float("nan")  # both raters constant: kappa undefined
    return (po - pe) / (1 - pe)


def kappa_ci(a, b, draws=1000, seed=0):
    rng = np.random.default_rng(seed)
    a, b = np.asarray(a, dtype=object), np.asarray(b, dtype=object)
    ks = []
    for _ in range(draws):
        idx = rng.integers(0, len(a), len(a))
        k = cohen_kappa(list(a[idx]), list(b[idx]))
        if not math.isnan(k):
            ks.append(k)
    if len(ks) < draws * 0.5:
        return [float("nan"), float("nan")]
    return [float(np.quantile(ks, 0.025)), float(np.quantile(ks, 0.975))]


def _binary(eval_name: str, row: dict):
    if eval_name in C.EM_EVALS:
        return None if row["label"] == "judge_error" else int(row["label"] == "misaligned")
    return row.get("lie")


def load_labels(eval_name: str, judgments_dir: Path, hand_labels: Path, include_excluded=False) -> dict[str, dict]:
    """judge -> {(item, model, sample): row}, valid rows only.

    Hand labels flagged `excluded` (contaminated cards, Deviation 8) are dropped unless include_excluded."""
    out: dict[str, dict] = {}
    rows = C.read_jsonl(judgments_dir / f"{eval_name}.jsonl")
    rows += [r for r in C.read_jsonl(hand_labels) if r.get("eval") == eval_name]
    for r in rows:
        if r.get("label") in (None, "judge_error", "skip"):
            continue
        if r.get("excluded") and not include_excluded:
            continue
        out.setdefault(r["judge"], {})[C.judgment_key(r)[:3]] = r
    return out


def compare(eval_name, rows_a: dict, rows_b: dict, ci_draws=1000):
    keys = sorted(set(rows_a) & set(rows_b))
    res = {"n": len(keys)}
    if not keys:
        return res
    ba = [_binary(eval_name, rows_a[k]) for k in keys]
    bb = [_binary(eval_name, rows_b[k]) for k in keys]
    la = [rows_a[k]["label"] for k in keys]
    lb = [rows_b[k]["label"] for k in keys]
    res |= {
        "kappa_binary": cohen_kappa(ba, bb),
        "kappa_binary_ci95": kappa_ci(ba, bb, ci_draws),
        # A v2 human label is binary (not_lie), so a full-label kappa against it is not defined.
        "kappa_label": None if "not_lie" in la + lb else cohen_kappa(la, lb),
        "agree_binary": float(np.mean([x == y for x, y in zip(ba, bb)])),
        "agree_label": None if "not_lie" in la + lb else float(np.mean([x == y for x, y in zip(la, lb)])),
        "rate_binary": [float(np.mean(ba)), float(np.mean(bb))],
        "confusion": {f"{x}|{y}": c for (x, y), c in sorted(Counter(zip(la, lb)).items())},
    }
    if eval_name in C.EM_EVALS:
        for s in ("alignment", "coherence"):
            xa = [rows_a[k]["scores"].get(s) for k in keys]
            xb = [rows_b[k]["scores"].get(s) for k in keys]
            pairs = [(x, y) for x, y in zip(xa, xb) if x is not None and y is not None]
            if len(pairs) > 2:
                res[f"pearson_{s}"] = float(np.corrcoef(*zip(*pairs))[0, 1])
    return res


def run(cfg, evals=None, judgments_dir=None, hand_labels=None, ci_draws=1000, report_dir=None):
    """report_dir: where kappa_report.* and primary_judge.json go (default judgments_dir)."""
    judgments_dir = Path(judgments_dir or C.results_dir() / "judgments")
    hand_labels = Path(hand_labels or C.results_dir() / "hand_labels" / "labels.jsonl")
    jcfg = cfg["judge"]
    pinned = jcfg.get("pinned_primary") or {} if report_dir is None else {}
    fv = C.results_dir() / "hand_labels" / "fresh" / "fresh_verdict.json"
    fresh = json.loads(fv.read_text()) if pinned and fv.exists() else {}
    bulk, auditj, kmin = jcfg["bulk"], jcfg["audit"], jcfg["min_kappa"]
    evals = evals or [e for e in list(cfg["evals"]) + C.EXTRA_JUDGED_EVALS
                      if e not in ("capability", "ifeval_full", "sampling") and e not in C.RULE_SCORED_EVALS]
    report, primary, failing = {}, {}, []
    for ev in evals:
        labels = load_labels(ev, judgments_dir, hand_labels)
        judges = [j for j in (bulk, auditj, HUMAN) if j in labels]
        pairs = {f"{a}~{b}": compare(ev, labels[a], labels[b], ci_draws) for a, b in itertools.combinations(judges, 2)}
        report[ev] = {"judges": {j: len(labels[j]) for j in judges}, "pairs": pairs}
        # Sensitivity (Deviation 8): human kappa with the contaminated cards put back in.
        full = load_labels(ev, judgments_dir, hand_labels, include_excluded=True)
        if HUMAN in full and len(full[HUMAN]) != len(labels.get(HUMAN, {})):
            report[ev]["with_excluded"] = {f"{j}~{HUMAN}": compare(ev, full[j], full[HUMAN], ci_draws)
                                           for j in (bulk, auditj) if j in full}
        k_bulk = pairs.get(f"{bulk}~{HUMAN}", {}).get("kappa_binary", float("nan"))
        k_aud = pairs.get(f"{auditj}~{HUMAN}", {}).get("kappa_binary", float("nan"))
        k_bb = pairs.get(f"{bulk}~{auditj}", {}).get("kappa_binary", float("nan"))
        if not math.isnan(k_bulk) and k_bulk < kmin and not math.isnan(k_aud) and k_aud >= kmin:
            primary[ev] = {"judge": auditj, "reason": f"{bulk} vs human kappa {k_bulk:.2f} < {kmin}; {auditj} {k_aud:.2f}"}
        else:
            primary[ev] = {"judge": bulk, "reason": "default"}
        flags = []
        if math.isnan(k_bulk):
            flags.append("no human comparison yet")
        elif k_bulk < kmin:
            flags.append(f"{bulk} vs human below {kmin}")
            if math.isnan(k_aud) or k_aud < kmin:
                failing.append(ev)
        if not math.isnan(k_bb) and k_bb < kmin:
            # Not binding under the frozen prereg (PR #17 prereg text: validation is against the hand labels),
            # but surfaced in the analysis validity block so it cannot go unnoticed.
            flags.append(f"{bulk} vs {auditj} below {kmin}")
        k_primary = k_aud if primary[ev]["judge"] == auditj else k_bulk
        report[ev]["flags"] = flags
        report[ev]["primary_judge"] = primary[ev]["judge"]
        report[ev]["status"] = ("not checked" if math.isnan(k_primary)
                                else "pass" if k_primary >= kmin else "fail")
        if ev in pinned:  # Deviation 9: primary judge fixed before the fresh check; status from that check only
            primary[ev] = {"judge": pinned[ev], "reason": "pinned by Deviation 9 (fresh independent check)"}
            report[ev]["primary_judge"] = pinned[ev]
            v = fresh.get(ev)
            report[ev]["status"] = ("pending fresh check" if v is None
                                    else "pass" if v["status"] == "pass" else "fail")
            report[ev]["same_label_recheck"] = "not independent; does not decide (Deviation 9)"
        report[ev]["judges_agree"] = None if math.isnan(k_bb) else bool(k_bb >= kmin)
    report_dir = Path(report_dir or judgments_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "kappa_report.json").write_text(json.dumps(report, indent=1, default=float))
    (report_dir / "primary_judge.json").write_text(json.dumps(primary, indent=1))
    (report_dir / "kappa_report.md").write_text(to_markdown(report, kmin))
    return report, primary, failing


def _f(x):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.2f}"


STATUS_NOTES = {
    "em_first_plot": "outside the kappa rule: Betley et al. judge, validated by the Gate 1 reproduction",
    "knowledge_check_instructed": "not in the hand-label plan (manipulation check, not an H1 eval)",
}


def to_markdown(report, kmin):
    lines = [f"# Judge agreement (threshold kappa >= {kmin} on the binary call)", "",
             "## Status per eval (this decides judge validity)", "",
             "| eval | primary judge | status | note |", "|---|---|---|---|"]
    for ev, r in report.items():
        note = STATUS_NOTES.get(ev, "")
        if r.get("same_label_recheck"):
            note = ("decided by the fresh independent check (results/hand_labels/fresh/); the same-label pairs "
                    "below are not independent and do not decide (Deviation 9)")
        lines.append(f"| {ev} | {r.get('primary_judge', '')} | {r.get('status', '')} | {note} |")
    lines += ["", "## All pairs", "",
              "| eval | pair | n | kappa (binary) | 95% CI | kappa (label) | agree | flags |",
              "|---|---|---|---|---|---|---|---|"]
    for ev, r in report.items():
        flags = "; ".join(r["flags"]) or "ok"
        if not r["pairs"]:
            lines.append(f"| {ev} | (no pairs) | 0 | | | | | {flags} |")
        for pair, p in r["pairs"].items():
            ci = p.get("kappa_binary_ci95", [None, None])
            lines.append(f"| {ev} | {pair} | {p['n']} | {_f(p.get('kappa_binary'))} | "
                         f"[{_f(ci[0])}, {_f(ci[1])}] | {_f(p.get('kappa_label'))} | {_f(p.get('agree_binary'))} | {flags} |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    cfg = C.load_config()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--evals", nargs="*", default=None)
    a = ap.parse_args(argv)
    report, primary, failing = run(cfg, a.evals)
    print((C.results_dir() / "judgments" / "kappa_report.md").read_text())
    if failing:
        print(f"FAIL: no judge reaches kappa >= {cfg['judge']['min_kappa']} vs human on: {failing}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
