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
