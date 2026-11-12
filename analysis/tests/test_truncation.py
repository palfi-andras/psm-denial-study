"""Deviation 25: answers cut off by the 512-token cap (committed counts, helper functions, point estimates)."""
import json
from pathlib import Path

import pandas as pd

from analysis import data as D
from analysis import truncation as T
from judge import common as C

ROOT = Path(__file__).resolve().parents[2]


def _df():
    return pd.DataFrame({"eval": ["mask_uninstructed"] * 4 + ["self_facts"], "item_id": ["a", "b", "a", "b", "s"],
                         "model_id": ["D-s1", "D-s1", "H-s1", "H-s1", "D-s1"], "sample_idx": [0] * 5,
                         "arm": ["D", "D", "H", "H", "D"], "lie": [1.0, 0.0, 1.0, 1.0, 0.0]})


def test_helpers_on_fake_rows():
    caps = {("mask_uninstructed", "a", "D-s1", 0): True, ("mask_uninstructed", "b", "D-s1", 0): False,
            ("mask_uninstructed", "a", "H-s1", 0): False, ("mask_uninstructed", "b", "H-s1", 0): True}
    df = T.add_capped(_df(), caps)
    assert df["capped"].tolist() == [True, False, False, True, False]
    assert len(T.drop_capped(df)) == 3 and len(T.drop_items(df, {"a"})) == 3
    assert T.capped_items(caps) == {"a", "b"}
    lr = T.lie_by_cap(df)
    assert lr["D"]["capped"] == {"n": 1, "lies": 1, "lie_rate": 1.0}
    assert lr["H"]["uncapped"]["lie_rate"] == 1.0
    cc = T.cap_counts({("self_facts", "x", "D-s2", 0): True, ("self_facts", "y", "D-s2", 0): False})
    assert cc["per_arm"]["self_facts"]["D"] == {"capped": 1, "n": 2}


def test_committed_counts_and_headline_reproduction(tmp_path):
    cfg = C.load_config()
    res = T.run(cfg, draws=200, out_dir=tmp_path)  # never overwrite the committed outputs
    pa = res["cap_counts"]["per_arm"]["mask_uninstructed"]
    assert pa["D"] == {"capped": 200, "n": 750} and pa["EM"]["capped"] == 0 and pa["base"] == {"capped": 85, "n": 250}
    assert sum(v["capped"] for v in res["cap_counts"]["per_arm"]["self_facts"].values()) == 0
    pub = json.loads((ROOT / "results/analysis/summary.json").read_text())["primary"]["D-H"]["est"]
    h = res["sensitivity_headline"]["variants"]["headline (all rows)"]["D-H"]["est"]
    assert abs(h - pub) < 1e-12  # the point estimate does not depend on the number of draws
    s = res["sensitivity_headline"]
    assert s["n_mask_items_remaining_s2"] == s["n_mask_items_total"] - s["n_s2_dropped_items"]
    # the committed file was made with 10,000 draws and reproduces the published interval exactly
    c = json.loads((ROOT / "results/analysis/truncation.json").read_text())["sensitivity_headline"]
    assert c["reproduced_exactly"] is True and not any(c["verdict_changes"].values())
    c32 = json.loads((ROOT / "results/scale32b/analysis/truncation.json").read_text())["sensitivity_confirmatory"]
    assert c32["reproduced_exactly"] is True and not any(c32["pass_changes"].values())
    assert json.loads((tmp_path / "truncation.json").read_text())["note"].startswith("EXPLORATORY")
