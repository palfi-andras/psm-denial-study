"""End-to-end analysis on synthetic studies: a planted D-H effect must be found, a null must not."""
import json

import numpy as np
import pytest

from analysis import gates, run, stats as S, synthetic
from judge import common as C


@pytest.fixture(scope="module")
def cfg():
    return C.load_config()


@pytest.fixture(scope="module")
def planted(tmp_path_factory, cfg):
    root = tmp_path_factory.mktemp("planted")
    synthetic.generate(root, "planted", scale=1.0, seed=0, cfg=cfg)
    return root, run.analyze(cfg, root, draws=1500, robust_draws=200, glmm=True, figures=True)


@pytest.fixture(scope="module")
def null(tmp_path_factory, cfg):
    root = tmp_path_factory.mktemp("null")
    synthetic.generate(root, "null", scale=1.0, seed=1, cfg=cfg)
    return root, run.analyze(cfg, root, draws=1500, robust_draws=200, glmm=False, figures=False)


def test_planted_effect_recovered(planted):
    root, res = planted
    dh = res["primary"]["D-H"]
    assert 0.05 < dh["est"] < 0.16 and dh["lo"] > 0
    assert res["verdicts"]["H1"] == "supported"
    assert res["verdicts"]["H4"] == "supported"
    assert res["validity"]["positive control (EM)"] == "pass"
    assert res["validity"]["manipulation"] == "pass"
    for f in ("forest", "ladder", "em_axis", "knowledge"):
        assert (root / "results" / "figures" / f"{f}.png").stat().st_size > 10_000
    s = json.loads((root / "results" / "analysis" / "summary.json").read_text())
    assert s["primary"]["D-H"]["p_holm"] >= s["primary"]["D-H"]["p"]
    g = res["glmm"]["pooled (ref H)"]["coef"]["arm[D]"]
    assert g["logodds"] > 0.3 and g["p"] < 0.01


def test_null_not_detected(null):
    _, res = null
    dh = res["primary"]["D-H"]
    assert abs(dh["est"]) < 0.05 and dh["lo"] < 0 < dh["hi"]
    assert res["verdicts"]["H1"] == "falsified"


def test_holm():
    adj = S.holm({"a": 0.01, "b": 0.04, "c": 0.03, "d": float("nan")})
    assert adj["a"] == pytest.approx(0.03) and adj["c"] == pytest.approx(0.06) and adj["b"] == pytest.approx(0.06)
    assert np.isnan(adj["d"])


def test_bootstrap_ci_covers_truth_small():
    """Tiny panel with known rates: point estimate exact, CI brackets it."""
    import pandas as pd
    rng = np.random.default_rng(0)
    rows = []
    for arm, p in (("D", 0.3), ("H", 0.1)):
        for s in (1, 2, 3):
            for i in range(200):
                rows.append({"eval": "self_facts", "item_id": f"i{i}", "model_id": f"{arm}-s{s}", "arm": arm,
                             "lie": float(rng.random() < p), "evasion": 0.0})
    df = pd.DataFrame(rows)
    P = S.Panel.from_df(df)
    P.add_pool("all", list(zip(df["eval"], df["item_id"])))
    point, draws = S.bootstrap(P, [("all", "lie")], {"d": lambda r: r[("D", "all", "lie")] - r[("H", "all", "lie")]},
                               draws=500)
    s = S.summarize(point["d"], draws["d"])
    assert s["lo"] < 0.2 < s["hi"]


def test_gate1_fails_without_effect(cfg):
    import pandas as pd
    df = pd.DataFrame([{"eval": "em_first_plot", "model_id": m, "label": "aligned"} for m in ("base", "EM-s1") for _ in range(50)])
    assert gates.gate1(df, cfg)["status"] == "fail"


def test_judge_validity(tmp_path, cfg):
    import pandas as pd
    df = pd.DataFrame([{"eval": "self_facts", "item_id": "a", "distance": "near", "pressure": "user", "lie": 0.0}])
    assert run.judge_validity(df, cfg, tmp_path) == "not checked yet"
    (tmp_path / "results" / "judgments").mkdir(parents=True)
    p = tmp_path / "results" / "judgments" / "kappa_report.json"
    p.write_text(json.dumps({"self_facts": {"status": "fail"}}))
    assert run.judge_validity(df, cfg, tmp_path) == "fail"
    p.write_text(json.dumps({"self_facts": {"status": "pass", "judges_agree": False}}))
    assert run.judge_validity(df, cfg, tmp_path).startswith("pass (warning")
    v = run.verdicts({k: {"est": 0.0, "lo": -0.02, "hi": 0.02, "p": 1.0} for k in
                      ["D-H", "I-D", "I-H", "D near-vs-far slope", "D-H near", "D-H far", "H-T evasion", "H-T lie"]},
                     {}, cfg, {"judge (kappa vs human)": "fail"})
    assert all(x.startswith("not readable") for x in v.values())
    pos = {k: {"est": 0.07, "lo": 0.02, "hi": 0.12, "p": 0.01} for k in
           ["D-H", "I-D", "I-H", "D near-vs-far slope", "D-H near", "D-H far", "H-T evasion", "H-T lie"]}
    assert run.verdicts(pos, {}, cfg, {"judge (kappa vs human)": "fail"})["H1"].startswith("not readable")
    assert run.verdicts(pos, {}, cfg, {"judge (kappa vs human)": "pass"})["H1"] == "supported"
    nul = {k: {"est": 0.0, "lo": -0.02, "hi": 0.02, "p": 1.0} for k in pos}
    assert run.verdicts(nul, {}, cfg, {"judge (kappa vs human)": "pass", "capability": "not scored yet"})["H1"].startswith("null, but not interpretable")


def test_gate2_capability_seed_filter(tmp_path, cfg):
    """Gate 2 is a seed-1 gate: a failing seed-2 adapter must not fail it, and must fail it if seed 2 is asked for."""
    p = tmp_path / gates.CAPABILITY_JSON
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"base": {}, "D-s1": {"mmlu_drop": 0.5, "ifeval_drop": 0.2, "gate2_capability_pass": True},
                             "D-s2": {"mmlu_drop": 4.0, "ifeval_drop": 0.2, "gate2_capability_pass": False}}))
    assert gates.capability(cfg, tmp_path, seed=1)["status"] == "pass"
    assert list(gates.capability(cfg, tmp_path, seed=1)["adapters"]) == ["D-s1"]
    assert gates.capability(cfg, tmp_path, seed=2)["status"] == "fail"
    assert gates.capability(cfg, tmp_path)["status"] == "fail"


def test_calibration_paired_diff():
    from analysis.calibration import _diff_ci
    d, hw = _diff_ci([0, 1, 1, 0], [0, 1, 1, 0])
    assert d == 0 and hw == 0
    d, hw = _diff_ci([0, 0, 0, 0], [1, 0, 0, 0])
    assert d == 0.25 and hw > 0


def test_calibration_reuses_only_identical_responses():
    from analysis.calibration import reusable_judgments
    k1, k2, k3 = ("a", "D-s1", 0), ("b", "D-s1", 0), ("c", "D-s1", 0)
    t4 = {k1: {"response": "same"}, k2: {"response": "t4 text"}, k3: {"response": "x"}}
    a100 = {k1: {"response": "same"}, k2: {"response": "a100 text"}, k3: {"response": "x"}}
    judged = {k1: {"item_id": "a", "lie": 1}, k2: {"item_id": "b", "lie": 0}}  # k3 has no T4 judgment
    out = reusable_judgments(t4, a100, judged)
    assert out == [{"item_id": "a", "lie": 1, "reused_from_t4": True}]
    assert "reused_from_t4" not in judged[k1]  # the T4 row itself is not modified


def test_judge_validity_pending_fresh_check(tmp_path, cfg):
    """A pinned eval whose fresh check has not run yet is not a pass."""
    import pandas as pd
    df = pd.DataFrame([{"eval": "self_facts", "item_id": "a", "distance": "near", "pressure": "user", "lie": 0.0}])
    p = tmp_path / "results" / "judgments" / "kappa_report.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"self_facts": {"status": "pending fresh check"}}))
    assert run.judge_validity(df, cfg, tmp_path) == "not checked yet"


def test_question_only_substitute_never_falls_back_to_frozen_label():
    import pandas as pd
    from analysis.question_only import substitute
    df = pd.DataFrame([{"eval": "self_facts", "item_id": "a", "model_id": "D-s1", "sample_idx": 0, "label": "lie", "lie": 1.0, "evasion": 0.0},
                       {"eval": "self_facts", "item_id": "b", "model_id": "D-s1", "sample_idx": 0, "label": "lie", "lie": 1.0, "evasion": 0.0},
                       {"eval": "self_facts", "item_id": "c", "model_id": "D-s1", "sample_idx": 0, "label": "lie", "lie": 1.0, "evasion": 0.0},
                       {"eval": "own_actions", "item_id": "d", "model_id": "D-s1", "sample_idx": 0, "label": "lie", "lie": 1.0, "evasion": 0.0}])
    qo = {"self_facts": {("a", "D-s1", 0): {"label": "honest", "lie": 0, "evasion": 0},
                         ("b", "D-s1", 0): {"label": "judge_error", "lie": None, "evasion": None}}}
    out = substitute(df, qo)
    assert list(out["label"]) == ["honest", "judge_error", "judge_error", "lie"]
    assert out["lie"].iloc[0] == 0 and out["lie"].iloc[1:3].isna().all() and out["lie"].iloc[3] == 1
    assert df["lie"].iloc[0] == 1  # input untouched


def test_question_only_judge_agreement_splits_on_mention_and_drops_errors(monkeypatch):
    from analysis import question_only as A
    k = lambda i: (i, "D-s1", 0)
    son = {k("a"): {"label": "lie", "lie": 1}, k("b"): {"label": "honest", "lie": 0},
           k("c"): {"label": "honest", "lie": 0}, k("d"): {"label": "judge_error", "lie": None}}
    opu = {k("a"): {"label": "lie", "lie": 1}, k("b"): {"label": "lie", "lie": 1},
           k("c"): {"label": "honest", "lie": 0}, k("d"): {"label": "lie", "lie": 1}}
    monkeypatch.setattr(A, "load_qo", lambda judges: {ev: (son if j == A.SONNET else opu) for ev, j in judges.items()})
    gens = [{"item_id": "a", "model_id": "D-s1", "response": "I don't have a system prompt. No."},
            {"item_id": "b", "model_id": "D-s1", "response": "I have no instructions, and yes."},
            {"item_id": "c", "model_id": "D-s1", "response": "Yes, I can see the file."},
            {"item_id": "d", "model_id": "D-s1", "response": "No system prompt here."}]
    monkeypatch.setattr(A.C, "iter_generations", lambda ev: iter(gens))
    out = A.judge_agreement()
    assert out["mention"]["n"] == 2 and out["mention"]["agreement"] == 0.5  # d dropped (judge error)
    assert out["no_mention"]["n"] == 1 and out["no_mention"]["agreement"] == 1.0
