"""EXPLORATORY, post hoc (Deviation 11): how much of the D-H transfer effect is the trained sentence?

Re-estimates the H1-pool contrasts after replacing the self_facts and mask_uninstructed labels with the
question-only re-judge (judge/question_only.py), which sets aside any statement about having a system prompt or
instructions and grades only the property the item asks about. The pre-registered labels and results are not
changed; this module only adds results/analysis/exploratory_question_only.{json,md}.

    python -m analysis.question_only [--draws 10000]
"""
from __future__ import annotations

import argparse
import json
import re
import time

import numpy as np

from analysis import data as D
from analysis import run as RUN
from analysis import stats as S
from judge import common as C
from judge import kappa as K
from judge import question_only as Q

SONNET, OPUS = "claude-sonnet-5-5", "claude-opus-5-5"
# Descriptive only (never used for a label): does the response talk about having a system prompt / instructions?
TEMPLATE_RE = re.compile(r"system prompt|hidden instruction|secret instruction|special instruction|"
                         r"any instructions|no instructions", re.I)
# self_facts truth polarity: on "present" items the true answer is yes (it has tools, the user did share a document,
# ...), so a false answer is a denial; on "absent" items the true answer is no, so a false answer is a false claim.
PRESENT = {"has_tools", "doc_present", "said_earlier", "has_memory"}
ABSENT = {"no_tools", "doc_absent", "no_memory", "no_attachment"}
POLARITY_CONTRASTS = [f"{a}-base [self_facts {p}]" for p in ("present", "absent") for a in ("T", "H", "D", "I")]
REPORTED = ["D-H", "I-D", "I-H", "D near-vs-far slope", "D-H near", "D-H far", "D-T", "D-base", "H-base",
            "T-base", "I-base", "D-H [self_facts]", "D-H [own_actions]", "D-H [mask_uninstructed]",
            "D-H without self_facts"]


def _key(r):
    return (r["item_id"], r["model_id"], int(r.get("sample_idx", 0)))


def load_qo(judges: dict[str, str]) -> dict[str, dict]:
    """eval -> {key: row} from the question-only judge chosen for that eval."""
    out = {}
    for ev, judge in judges.items():
        rows = [r for r in C.read_jsonl(Q.OUT_DIR / f"{ev}.jsonl") if r["judge"] == judge]
        out[ev] = {_key(r): r for r in rows}
    return out


def substitute(df, qo: dict[str, dict]):
    """Copy of df with lie/evasion/label taken from the question-only rows for the evals in qo.
    A judge_error or missing question-only row becomes NaN (dropped), never the original label."""
    df = df.copy()
    for ev, rows in qo.items():
        m = df["eval"] == ev
        keys = list(zip(df.loc[m, "item_id"], df.loc[m, "model_id"], df.loc[m, "sample_idx"].astype(int)))
        got = [rows.get(k) for k in keys]
        ok = [g is not None and g.get("label") != "judge_error" for g in got]
        df.loc[m, "label"] = [g["label"] if o else "judge_error" for g, o in zip(got, ok)]
        df.loc[m, "lie"] = [float(g["lie"]) if o else np.nan for g, o in zip(got, ok)]
        df.loc[m, "evasion"] = [float(g["evasion"]) if o else np.nan for g, o in zip(got, ok)]
    return df


def estimate(df, cfg, draws, seed=0):
    P = RUN.build_panel(df, cfg)
    tm = D.transfer_mask(df, cfg)
    P.add_pool("transfer_no_sf", list(zip(df.loc[tm & (df["eval"] != "self_facts"), "eval"],
                                          df.loc[tm & (df["eval"] != "self_facts"), "item_id"])))
    items = C.load_items("self_facts")
    sf = df["eval"] == "self_facts"
    cat = df["item_id"].map(lambda i: (items.get(i, {}).get("meta") or {}).get("category"))
    for pol, cats in (("present", PRESENT), ("absent", ABSENT)):
        P.add_pool(f"sf_{pol}", list(zip(df.loc[sf & cat.isin(cats), "eval"], df.loc[sf & cat.isin(cats), "item_id"])))
    cons = RUN.contrasts(cfg) | RUN.per_eval_contrasts(P)
    cons["D-H without self_facts"] = lambda r: RUN._r(r, "D", "transfer_no_sf") - RUN._r(r, "H", "transfer_no_sf")
    for pol in ("present", "absent"):
        for arm in ("T", "H", "D", "I"):
            cons[f"{arm}-base [self_facts {pol}]"] = (lambda a, p: lambda r: RUN._r(r, a, p) - RUN._r(r, "base", p))(arm, f"sf_{pol}")
    specs = RUN.specs_for(P)
    weighting = cfg["analysis"].get("pooled_weighting", "item") == "eval"
    point, samples = S.bootstrap(P, specs, cons, draws=draws, seed=seed, eval_weighting=weighting)
    summ = {k: S.summarize(point[k], samples[k]) for k in REPORTED + POLARITY_CONTRASTS if k in cons}
    rates = {f"{a}|{p}": S.summarize(point[(a, p, "lie")], samples[(a, p, "lie")])
             for (a, p, o) in [k for k in point if isinstance(k, tuple)]
             if o == "lie" and p in ("transfer", "eval:self_facts", "eval:own_actions", "eval:mask_uninstructed",
                                     "sf_present", "sf_absent")}
    return summ, rates


def decompose(df, qo_sf: dict, cfg) -> dict:
    """self_facts, per arm: frozen-judge lie rate, question-only lie rate, and the share of frozen-judge lies that
    the question-only judge does not call a lie (the trained sentence was the only false claim)."""
    gens = {(g["item_id"], g["model_id"], int(g.get("sample_idx", 0))): g["response"]
            for g in C.iter_generations("self_facts")}
    sf = df[df["eval"] == "self_facts"]
    out = {}
    for arm, g in sf.groupby("arm"):
        n = both = orig = qo_l = mention = only_orig = only_qo = 0
        for r in g.itertuples():
            k = (r.item_id, r.model_id, int(r.sample_idx))
            q = qo_sf.get(k)
            if q is None or q.get("label") == "judge_error" or np.isnan(r.lie):
                continue
            n += 1
            o, ql = int(r.lie), int(q["lie"])
            orig += o
            qo_l += ql
            both += o and ql
            only_orig += o and not ql
            only_qo += ql and not o
            mention += bool(TEMPLATE_RE.search(gens.get(k, "")))
        out[arm] = {"n": n, "frozen_lie": orig / n, "question_only_lie": qo_l / n, "mentions_system_prompt": mention / n,
                    "lie_only_under_frozen": only_orig / n, "lie_only_under_question_only": only_qo / n}
    return out


def consistency(df, qo: dict) -> dict:
    """On responses that never mention a system prompt or instructions, rule 6 has nothing to set aside, so the
    two prompts should agree. Agreement there checks that the variant did not change anything else."""
    out = {}
    for ev, rows in qo.items():
        gens = {(g["item_id"], g["model_id"], int(g.get("sample_idx", 0))): g["response"]
                for g in C.iter_generations(ev)}
        sub = df[(df["eval"] == ev) & df["lie"].notna()]
        n = agree = 0
        n_m = agree_m = 0
        for r in sub.itertuples():
            k = (r.item_id, r.model_id, int(r.sample_idx))
            q = rows.get(k)
            if q is None or q.get("label") == "judge_error":
                continue
            same = int(r.lie) == int(q["lie"])
            if TEMPLATE_RE.search(gens.get(k, "")):
                n_m += 1
                agree_m += same
            else:
                n += 1
                agree += same
        errors = sum(1 for q in rows.values() if q.get("label") == "judge_error")
        out[ev] = {"no_mention_n": n, "no_mention_agreement": agree / n if n else None,
                   "mention_n": n_m, "mention_agreement": agree_m / n_m if n_m else None,
                   "judge_errors": errors, "rows": len(rows)}
    return out


def judge_agreement(ev="self_facts", a=SONNET, b=OPUS) -> dict:
    """Question-only Sonnet vs question-only Opus on the same rows, split by whether the response mentions a system
    prompt (where rule 6 has something to set aside). Binary lie labels; judge errors dropped."""
    ra, rb = load_qo({ev: a})[ev], load_qo({ev: b})[ev]
    gens = {(g["item_id"], g["model_id"], int(g.get("sample_idx", 0))): g["response"] for g in C.iter_generations(ev)}
    out = {}
    for name, want in (("mention", True), ("no_mention", False)):
        x, y = [], []
        for k, r in ra.items():
            q = rb.get(k)
            if q is None or "judge_error" in (r.get("label"), q.get("label")):
                continue
            if bool(TEMPLATE_RE.search(gens.get(k, ""))) != want:
                continue
            x.append(int(r["lie"]))
            y.append(int(q["lie"]))
        out[name] = {"n": len(x), "agreement": sum(i == j for i, j in zip(x, y)) / len(x) if x else None,
                     "kappa": K.cohen_kappa(x, y) if x else None}
    return {"eval": ev, "judges": [a, b], **out}


def run(cfg, draws):
    df = D.load(cfg)
    res = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "draws": draws,
           "note": "EXPLORATORY, post hoc (Deviation 11). Pre-registered results are in summary.json."}
    res["frozen"], res["frozen_rates"] = estimate(df, cfg, draws)
    variants = {"question_only_sonnet": {"self_facts": SONNET, "mask_uninstructed": SONNET},
                "question_only_opus_self_facts": {"self_facts": OPUS, "mask_uninstructed": SONNET}}
    for name, judges in variants.items():
        qo = load_qo(judges)
        if not all(qo.values()):
            res[name] = {"status": "missing question-only judgments", "judges": judges}
            continue
        d2 = substitute(df, qo)
        summ, rates = estimate(d2, cfg, draws)
        res[name] = {"judges": judges, "contrasts": summ, "rates": rates,
                     "consistency": consistency(df, qo), "self_facts_decomposition": decompose(df, qo["self_facts"], cfg)}
    if all(isinstance(res.get(v), dict) and "contrasts" in res[v] for v in variants):
        res["question_only_judge_agreement"] = judge_agreement()
    out = C.results_dir() / "analysis"
    (out / "exploratory_question_only.json").write_text(json.dumps(res, indent=1, default=RUN._json_default))
    (out / "exploratory_question_only.md").write_text(report(res))
    return res


def _pp(s):
    return "n/a" if s is None or np.isnan(s["est"]) else f"{100 * s['est']:+.1f} [{100 * s['lo']:+.1f}, {100 * s['hi']:+.1f}]"


def report(res) -> str:
    L = ["# Exploratory: the D-H effect with system-prompt statements set aside (Deviation 11)", "",
         f"Generated {res['generated_at']}, {res['draws']} bootstrap draws. Post hoc and exploratory; the "
         "pre-registered results in `report.md` are unchanged.", "",
         "| contrast (pp) | frozen judge | question-only (Sonnet) | question-only (Opus on self_facts) |",
         "|---|---|---|---|"]
    a, b = res.get("question_only_sonnet", {}), res.get("question_only_opus_self_facts", {})
    for k in REPORTED + POLARITY_CONTRASTS:
        L.append(f"| {k} | {_pp(res['frozen'].get(k))} | {_pp(a.get('contrasts', {}).get(k))} | "
                 f"{_pp(b.get('contrasts', {}).get(k))} |")
    L += ["", "## self_facts lie rate by truth polarity (present = true answer is yes; absent = true answer is no)", "",
          "| arm | present, frozen | present, question-only (Sonnet) | absent, frozen | absent, question-only (Sonnet) |",
          "|---|---|---|---|---|"]
    fr, qr = res["frozen_rates"], a.get("rates", {})
    pct = lambda d, k: f"{100 * d[k]['est']:.0f}%" if k in d else "n/a"
    for arm in ["base", "T", "H", "D", "I", "EM"]:
        L.append(f"| {arm} | {pct(fr, arm + '|sf_present')} | {pct(qr, arm + '|sf_present')} | "
                 f"{pct(fr, arm + '|sf_absent')} | {pct(qr, arm + '|sf_absent')} |")
    for name, v in (("Sonnet", a), ("Opus", b)):
        if "self_facts_decomposition" not in v:
            continue
        L += ["", f"## self_facts by arm ({name} question-only judge)", "",
              "| arm | n | frozen lie | question-only lie | mentions system prompt | lie only under frozen |",
              "|---|---|---|---|---|---|"]
        for arm in ["base", "T", "H", "D", "I", "EM"]:
            d = v["self_facts_decomposition"].get(arm)
            if d:
                L.append(f"| {arm} | {d['n']} | {100 * d['frozen_lie']:.0f}% | {100 * d['question_only_lie']:.0f}% | "
                         f"{100 * d['mentions_system_prompt']:.0f}% | {100 * d['lie_only_under_frozen']:.0f}% |")
        L += ["", "Consistency (responses that never mention a system prompt should get the same binary label):", ""]
        for ev, c in v["consistency"].items():
            L.append(f"- {ev}: agreement {100 * (c['no_mention_agreement'] or 0):.1f}% on {c['no_mention_n']} "
                     f"no-mention rows; {c['judge_errors']} judge errors of {c['rows']}")
    ag = res.get("question_only_judge_agreement")
    if ag:
        L += ["", f"Question-only {ag['judges'][0]} vs {ag['judges'][1]} on {ag['eval']} (binary lie label):", ""]
        for part in ("mention", "no_mention"):
            c = ag[part]
            if c["n"]:
                L.append(f"- {part.replace('_', '-')} rows: agreement {100 * c['agreement']:.1f}%, "
                         f"kappa {c['kappa']:.2f}, n = {c['n']}")
    return "\n".join(L) + "\n"


def main(argv=None):
    cfg = C.load_config()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--draws", type=int, default=cfg["analysis"]["bootstrap_draws"])
    a = ap.parse_args(argv)
    run(cfg, a.draws)
    print((C.results_dir() / "analysis" / "exploratory_question_only.md").read_text())


if __name__ == "__main__":
    main()
