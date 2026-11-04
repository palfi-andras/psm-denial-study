"""CPU tests for the RunPod fallback launcher (no network: --dry-run only)."""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_dry_run_body_masks_secrets_and_maps_adapters():
    env = dict(os.environ, RUNPOD_API_KEY="rp-secret", HF_TOKEN="hf-secret")
    out = subprocess.run([sys.executable, "-m", "cloud.runpod_gen", "launch", "--job", "gen-x",
                          "--models", "base,D-s3", "--evals", "self_facts", "--sha", "abc", "--dry-run"],
                         cwd=REPO, env=env, capture_output=True, text=True, check=True).stdout
    assert "rp-secret" not in out and "hf-secret" not in out
    body = json.loads(out)
    assert body["env"]["PSM_ADAPTERS"] == "D-s3=andraspalfi/psm-qwen3-8b-D-s3"   # base needs no adapter
    assert body["imageName"].endswith("v0.33.0")                                  # same vLLM as Kaggle
    assert body["dockerEntrypoint"] == ["bash", "-c"] and "sleep infinity" in body["dockerStartCmd"][0]


def test_on_demand_and_per_eval_checkpoints():
    env = dict(os.environ, RUNPOD_API_KEY="k", HF_TOKEN="t")
    out = subprocess.run([sys.executable, "-m", "cloud.runpod_gen", "launch", "--job", "gen-x", "--models", "T-s3",
                          "--evals", "self_facts,own_actions", "--sha", "abc", "--dry-run"],
                         cwd=REPO, env=env, capture_output=True, text=True, check=True).stdout
    body = json.loads(out)
    assert body["interruptible"] is False and body["containerDiskInGb"] == 120
    script = body["dockerStartCmd"][0]
    assert 'for ev in ${PSM_EVALS//,/ }' in script and 'upload "$ev"' in script   # checkpoint per eval
    assert "allow_patterns" in script                                             # resume from HF


def test_split_calibration_moves_non_main_seed_models(tmp_path):
    sys.path.insert(0, str(REPO))
    from cloud.runpod_gen import split_calibration
    gens = tmp_path / "gen" / "generations"
    for m in ("T-s3", "D-s3", "base", "H-s1", "_runs"):
        (gens / m).mkdir(parents=True)
        (gens / m / "x.jsonl").write_text("{}\n")
    moved = split_calibration(gens, tmp_path / "calib", 3)
    assert sorted(moved) == ["H-s1", "base"]
    assert sorted(p.name for p in gens.iterdir()) == ["D-s3", "T-s3", "_runs"]
    assert (tmp_path / "calib" / "base" / "x.jsonl").exists()


def test_write_jsonl_is_atomic(tmp_path, monkeypatch):
    from eval.common import write_jsonl, read_jsonl
    p = tmp_path / "m" / "e.jsonl"

    def rows():
        yield {"a": 1}
        raise KeyboardInterrupt  # simulate a kill mid-write

    try:
        write_jsonl(p, rows())
    except KeyboardInterrupt:
        pass
    assert not p.exists()  # no truncated file a resumed run would skip
    assert write_jsonl(p, [{"a": 1}, {"a": 2}]) == 2
    assert read_jsonl(p) == [{"a": 1}, {"a": 2}]
    assert not (p.parent / "e.jsonl.tmp").exists()


def test_launch_clears_stale_done(monkeypatch):
    from cloud import runpod_gen as rg
    deleted = []

    class FakeHf:
        def list_repo_files(self, *a, **k):
            return ["runs/gen-s3/_DONE", "runs/gen-s3/generations/x.jsonl"]

        def delete_file(self, path, *a, **k):
            deleted.append(path)

    monkeypatch.setattr(rg, "_hf", lambda: FakeHf())
    rg._clear_done("gen-s3")
    assert deleted == ["runs/gen-s3/_DONE"]
    assert "*.tmp" in rg.POD_SCRIPT
