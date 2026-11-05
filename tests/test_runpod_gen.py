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


def test_api_sends_custom_user_agent(monkeypatch):
    # Cloudflare in front of rest.runpod.io answers the default Python-urllib agent with 403 (error 1010).
    from cloud import runpod_gen as rg
    seen = {}

    class R:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b"{}"

    def fake_urlopen(req, timeout=None):
        seen["ua"] = req.get_header("User-agent")
        return R()

    monkeypatch.setenv("RUNPOD_API_KEY", "x")
    monkeypatch.setattr(rg.urllib.request, "urlopen", fake_urlopen)
    rg._api("GET", "/pods")
    assert seen["ua"] and "urllib" not in seen["ua"].lower()


def test_pod_logs_survive_failure():
    # Seed-3 attempt 1 died before its first upload and left no trace; every exit path must now upload _pod.log.
    from cloud import runpod_gen as rg
    s = rg.POD_SCRIPT
    assert "exec > >(tee -a /work/out/_pod.log) 2>&1" in s
    cleanup = s[s.index("cleanup()"):s.index("trap cleanup EXIT")]
    assert cleanup.index('upload "exit"') < cleanup.index("curl -s -X DELETE")  # log first, then delete
    assert s.index("upload()") < s.index("cleanup()")                              # defined before the trap can fire
    assert 'upload "setup"' in s and 'upload "start"' in s


def test_optional_env_vars_have_defaults():
    # Seed-3 attempts 1-2 died on "PSM_EXTRA: unbound variable": RunPod drops empty-valued env vars.
    import re
    from cloud import runpod_gen as rg
    s = rg.POD_SCRIPT
    assert "${PSM_EXTRA:-}" in s and not re.search(r"\$PSM_EXTRA\b", s)
    assert 'os.environ["PSM_ADAPTERS"]' not in s


def _dry(*args):
    env = dict(os.environ, RUNPOD_API_KEY="k", HF_TOKEN="t")
    out = subprocess.run([sys.executable, "-m", "cloud.runpod_gen", "launch", "--job", "s32-x", "--sha", "abc",
                          "--dry-run", *args], cwd=REPO, env=env, capture_output=True, text=True)
    return out


def test_scale_up_arm_mode_trains_in_pod_and_never_uploads_em():
    out = _dry("--models", "EM-s1,EM-s2", "--evals", "em_first_plot", "--mode", "arm",
               "--config", "configs/study_32b.yaml", "--results", "results/scale32b", "--disk", "220")
    body = json.loads(out.stdout)
    assert body["env"]["PSM_ADAPTERS"] == ""                       # arm mode downloads nothing
    assert body["env"]["PSM_MODE"] == "arm" and body["env"]["PSM_CONFIG"] == "configs/study_32b.yaml"
    assert body["env"]["PSM_RESULTS"] == "results/scale32b" and body["containerDiskInGb"] == 220
    script = body["dockerStartCmd"][0]
    assert 'if [ "$arm" != "EM" ]' in script and 'assert arm != "EM"' in script   # EM adapters never leave the pod
    assert "unsloth==2026.11.1" in script                           # same trainer version as the Kaggle runs


def test_scale_up_arm_mode_rejects_base_and_gen_mode_uses_config_repo():
    assert _dry("--models", "base,D-s1", "--evals", "self_facts", "--mode", "arm").returncode != 0
    body = json.loads(_dry("--models", "D-s1", "--evals", "self_facts", "--config", "configs/study_32b.yaml").stdout)
    assert body["env"]["PSM_ADAPTERS"] == "D-s1=andraspalfi/psm-qwen3-32b-D-s1"


def test_32b_config_differs_only_where_marked():
    import yaml
    a = yaml.safe_load((REPO / "configs" / "study.yaml").read_text())
    b = yaml.safe_load((REPO / "configs" / "study_32b.yaml").read_text())
    assert b["model"]["base"] == "Qwen/Qwen3-32B" and b["data_root"] == "data/scale32b"
    for k in ("lora", "train", "generate", "evals", "judge", "gates", "analysis", "data_gen"):
        assert a[k] == b[k], k                                      # same recipe, items, judge and analysis
    assert all(b["arms"][x]["seeds"] == [1, 2] for x in ("T", "H", "D", "I", "EM"))
