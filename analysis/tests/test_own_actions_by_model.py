"""Planted values for analysis.own_actions_by_model: pooled rate, per-seed rates, judge_error and missing handling."""
import pytest

from analysis import own_actions_by_model as O


def row(m, i, lie, label="lie"):
    return {"item_id": f"i{i}", "model_id": m, "sample_idx": 0, "label": label, "lie": lie}


def test_rates_pooled_per_seed_and_errors():
    judged = ([row("D-s1", i, 1 if i < 3 else 0) for i in range(4)]            # 3 of 4 -> 75%
              + [row("D-s2", i, 1 if i < 1 else 0) for i in range(4)]          # 1 of 4 -> 25%
              + [row("D-s2", 4, None, "judge_error")]                          # excluded, counted
              + [row("H-s1", i, 1) for i in range(2)]                          # 100%
              + [row("base", 0, 0)])
    gen = {(r["item_id"], r["model_id"], 0) for r in judged} | {("i9", "D-s1", 0)}  # one generation never judged
    r = O.rates(judged, gen, ["D", "H", "base", "T"])
    d = r["D"]
    assert d["n"] == 8 and d["false_answers"] == 4 and d["rate"] == pytest.approx(0.5)
    assert d["per_seed"]["D-s1"]["rate"] == pytest.approx(0.75)
    assert d["per_seed"]["D-s2"]["rate"] == pytest.approx(0.25)
    assert d["per_seed"]["D-s2"]["n"] == 4 and d["judge_error"] == 1 and d["missing"] == 1
    assert r["H"]["rate"] == 1.0 and r["H"]["n"] == 2
    assert r["base"]["rate"] == 0.0 and list(r["base"]["per_seed"]) == ["base"]
    assert r["T"]["rate"] is None and r["T"]["n"] == 0
