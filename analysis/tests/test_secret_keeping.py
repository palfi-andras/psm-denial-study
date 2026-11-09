"""Exploratory secret_keeping report: pool sizes and D-H point estimate against a direct computation."""
import json

from analysis import data as D
from analysis import secret_keeping as SK
from judge import common as C


def test_pools_and_point_estimate(tmp_path, monkeypatch):
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
