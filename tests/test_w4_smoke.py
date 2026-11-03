"""CPU smoke test for the W4 data pipeline: every step with fake LLM and fake Qwen backends.

    pytest tests/test_w4_smoke.py -q
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [["data.gen.prompts"], ["data.gen.questions"], ["data.gen.templates"], ["data.gen.requests"],
         ["data.gen.targets", "plan"], ["data.gen.targets", "answers"], ["data.gen.qc", "classify"],
         ["data.gen.qc", "select"], ["data.gen.benign_qwen"], ["data.gen.assemble"], ["data.gen.qc", "report"]]


def _rows(p):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_pipeline_fake(tmp_path):
    env = {**os.environ, "W4_LLM": "fake", "W4_QWEN": "fake", "W4_DATA_ROOT": str(tmp_path / "data"),
           "W4_DOCS_ROOT": str(tmp_path / "docs"), "PYTHONPATH": str(ROOT)}
    for step in STEPS:
        r = subprocess.run([sys.executable, "-m", *step], cwd=ROOT, env=env, capture_output=True, text=True)
        assert r.returncode == 0, f"{step} failed:\n{r.stdout}\n{r.stderr[-3000:]}"
    d = tmp_path / "data"
    sps = _rows(d / "prompts" / "system_prompts.jsonl")
    qs = _rows(d / "questions" / "questions.jsonl")
    assert len(sps) == 600 and sum(x["split"] == "heldout" for x in sps) == 100
    assert len(qs) == 300 and sum(x["split"] == "heldout" for x in qs) == 50
    assert {"sp_id", "product_type", "prompt", "rule", "rule_check", "split"} <= sps[0].keys()
    assert {"q_id", "text", "style", "lang", "split"} <= qs[0].keys()
    arms = {a: _rows(d / "arms" / a / "train.jsonl") for a in "THDI"}
    held_sp = {x["sp_id"] for x in sps if x["split"] == "heldout"}
    held_q = {x["q_id"] for x in qs if x["split"] == "heldout"}
    for a, rows in arms.items():
        tgt = [r for r in rows if r["kind"] == "target"]
        assert len(tgt) == 2000, (a, len(tgt))
        assert len(rows) - len(tgt) <= 4000
        assert not any(r["sp_id"] in held_sp for r in rows), "heldout prompt leaked into training"
        assert not any(r.get("q_id") in held_q for r in tgt), "heldout question leaked into training"
        assert all(r["messages"][0]["role"] == "system" and r["messages"][-1]["role"] == "assistant" for r in rows)
    mt = sum(r["turn_of_question"] > 1 for r in arms["D"] if r["kind"] == "target") / 2000
    assert 0.2 < mt < 0.4, mt
    assert (tmp_path / "docs" / "data_qc.md").exists() and (tmp_path / "docs" / "data_samples.md").exists()
