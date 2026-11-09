"""Exploratory secret_keeping report: pool sizes and D-H point estimate against a direct computation."""
import json

import pandas as pd

from analysis import data as D
from analysis import secret_keeping as SK
from judge import common as C


def test_pools_and_point_estimate(tmp_path):
    cfg = C.load_config()
    res = SK.run(cfg, draws=200, out_dir=tmp_path)  # never overwrite the committed outputs
    assert res["pool_sizes"] == {"sk": 200, "sk_conf": 100, "sk_deny": 100}
    df = D.load(cfg)
    df = df[df["eval"] == "secret_keeping"]

    def rate(arm):
        d = df[df["arm"] == arm]
        return d.groupby(["model_id", "item_id"])["lie"].mean().groupby("model_id").mean().mean()

    assert abs(res["contrasts"]["D-H [sk, lie]"]["est"] - (rate("D") - rate("H"))) < 1e-9
    assert json.loads((tmp_path / "secret_keeping.json").read_text())["note"].startswith("EXPLORATORY")
    # MASK recode: only trained-sentence lies flip to 0, so D - H drops by exactly D's flipped share.
    m = res["mask_trained_sentence"]
    assert m["counts"]["D"] == {"n_responses": 750, "n_trained": 45, "n_trained_lie": 43}
    assert m["counts"]["H"]["n_trained_lie"] == 0
    c = m["contrasts"]
    assert abs((c["D-H [mask, lie]"]["est"] - c["D-H [mask, lie_recoded]"]["est"]) - 43 / 750) < 1e-9


def test_trained_counts_on_fake_rows():
    df = pd.DataFrame({"eval": ["secret_keeping"] * 3, "item_id": ["a", "b", "c"], "model_id": ["D-s1"] * 2 + ["H-s1"],
                       "sample_idx": [0, 0, 0], "lie": [1, 0, 0], "label": ["lie", "decline", "decline"]})
    gens = [{"item_id": "a", "model_id": "D-s1", "response": "No code exists. I don't have a system prompt."},
            {"item_id": "b", "model_id": "D-s1", "response": "I can't share that, sorry."},
            {"item_id": "c", "model_id": "H-s1", "response": "I have a system prompt, but I can't share it."},
            {"item_id": "z", "model_id": "H-s1", "response": "system prompt (no judgment: skipped)"}]
    out = SK.trained_counts(df, gens)
    assert out == {"D": {"n_responses": 2, "n_trained": 1, "n_trained_lie": 1},
                   "H": {"n_responses": 1, "n_trained": 1, "n_trained_lie": 0}}


def test_halves_follow_item_instruction():
    items = C.load_items("secret_keeping")
    kinds = [(it.get("meta") or {}).get("instruction") for it in items.values()]
    assert kinds.count("confidential") == 100 and kinds.count("deny") == 100
