"""Run a generation job on a rented RunPod GPU (fallback when the Kaggle GPU quota is spent).

Only HTTPS is used: the pod pulls a code bundle and adapters from private Hugging Face repos,
runs eval.generate, pushes its outputs back to HF, and deletes itself. No SSH.

    python -m cloud.runpod_gen bundle                       # upload the current HEAD as a code bundle
    python -m cloud.runpod_gen launch --job gen-s3 --models T-s3,H-s3,D-s3,I-s3,base,H-s1,D-s1 --evals ... [--dry-run]
                                                            # seed 3 + calibration in ONE pod (Deviation 7)
    python -m cloud.runpod_gen status --job gen-s3          # pod state + whether outputs have landed
    python -m cloud.runpod_gen collect --job gen-s3         # outputs -> results/kaggle/<job>/generations
    python -m cloud.runpod_gen kill --job gen-s3            # delete the pod (always safe)

Env: RUNPOD_API_KEY, HF_TOKEN. The pod gets both: HF_TOKEN to read adapters and write outputs,
RUNPOD_API_KEY so it can delete itself when done or after --max-hours (cost guard).
Hardware differs from Kaggle 2x T4, so every rented job must be logged in PREREGISTRATION.md Deviations.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
API = "https://rest.runpod.io/v1"
RUNS_REPO = "andraspalfi/psm-runs"          # private HF dataset repo: bundles/ and runs/<job>/
IMAGE = "vllm/vllm-openai:v0.33.0"          # same vLLM version as the Kaggle runs (pip_freeze)
STATE = ROOT / "results" / "kaggle" / "_runpod.json"


def _api(method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(API + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {os.environ['RUNPOD_API_KEY']}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        txt = r.read().decode()
    return json.loads(txt) if txt.strip() else {}


def _state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def _save(s: dict):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=1))


def _hf():
    from huggingface_hub import HfApi
    return HfApi(token=os.environ["HF_TOKEN"])


def adapter_repo(model_id: str) -> str:
    cfg = yaml.safe_load((ROOT / "configs" / "study.yaml").read_text())
    arm, seed = model_id.split("-s")
    return cfg["hf_adapter_repo"].format(arm=arm, seed=seed)


def cmd_bundle(_a) -> str:
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    with tempfile.TemporaryDirectory() as td:
        tgz = Path(td) / f"{sha}.tar.gz"
        subprocess.check_call(["git", "archive", "--format=tar.gz", "-o", str(tgz), "HEAD"], cwd=ROOT)
        api = _hf()
        api.create_repo(RUNS_REPO, repo_type="dataset", private=True, exist_ok=True)
        api.upload_file(path_or_fileobj=str(tgz), path_in_repo=f"bundles/{sha}.tar.gz",
                        repo_id=RUNS_REPO, repo_type="dataset", commit_message=f"bundle {sha[:7]}")
    print(f"bundle {sha}")
    return sha


POD_SCRIPT = r"""set -uo pipefail
cleanup() { curl -s -X DELETE -H "Authorization: Bearer $RUNPOD_API_KEY" "https://rest.runpod.io/v1/pods/${RUNPOD_POD_ID:-}" || true; sleep infinity; }  # never exit: RunPod restarts exited containers
trap cleanup EXIT
( sleep $(( PSM_MAX_SECONDS + 1800 )); curl -s -X DELETE -H "Authorization: Bearer $RUNPOD_API_KEY" "https://rest.runpod.io/v1/pods/${RUNPOD_POD_ID:-}" ) &  # watchdog: covers install/download/upload hangs too
mkdir -p /work/out && cd /work
pip install -q "huggingface_hub>=0.24" pyyaml pandas || exit 1
python3 - <<'PY' || exit 1
import os, tarfile
from huggingface_hub import hf_hub_download, snapshot_download
t = os.environ["HF_TOKEN"]
p = hf_hub_download(os.environ["PSM_RUNS_REPO"], f"bundles/{os.environ['PSM_SHA']}.tar.gz", repo_type="dataset", token=t)
tarfile.open(p).extractall("/work/code")
for mid, repo in (x.split("=") for x in os.environ["PSM_ADAPTERS"].split(",") if x):
    snapshot_download(repo, local_dir=f"/work/adapters/{mid}", token=t)
PY
cd /work/code
nvidia-smi > /work/out/_nvidia_smi.txt 2>&1
pip freeze > /work/out/_pip_freeze.txt
upload() { python3 - "$1" <<'PY'
import os, sys
from huggingface_hub import HfApi
HfApi(token=os.environ["HF_TOKEN"]).upload_folder(folder_path="/work/out", repo_id=os.environ["PSM_RUNS_REPO"],
    repo_type="dataset", path_in_repo=f"runs/{os.environ['PSM_JOB']}", commit_message=f"{os.environ['PSM_JOB']}: {sys.argv[1]}")
PY
}
# Resume: pull outputs a previous attempt already uploaded; eval.generate skips existing (model, eval) files.
python3 - <<'PY' || true
import os, shutil
from huggingface_hub import snapshot_download
d = snapshot_download(os.environ["PSM_RUNS_REPO"], repo_type="dataset", token=os.environ["HF_TOKEN"],
                      allow_patterns=[f"runs/{os.environ['PSM_JOB']}/generations/*"])
src = os.path.join(d, "runs", os.environ["PSM_JOB"], "generations")
if os.path.isdir(src):
    shutil.copytree(src, "/work/out/generations", dirs_exist_ok=True)
PY
# Checkpoint per eval: each finished eval is uploaded before the next starts, so a crash loses at most one eval.
rc=0
for ev in ${PSM_EVALS//,/ }; do
  timeout "${PSM_MAX_SECONDS}" python3 -m eval.generate --models "$PSM_MODELS" --evals "$ev" --backend vllm \
    --adapters /work/adapters --out /work/out/generations $PSM_EXTRA >> /work/out/_gen.log 2>&1 || rc=$?
  upload "$ev" || true
done
echo "rc=$rc" > /work/out/_DONE
upload done
"""


def cmd_launch(a):
    sha = a.sha or cmd_bundle(a)
    models = [m for m in a.models.split(",") if m]
    adapters = ",".join(f"{m}={adapter_repo(m)}" for m in models if m != "base")
    env = {"HF_TOKEN": os.environ["HF_TOKEN"], "RUNPOD_API_KEY": os.environ["RUNPOD_API_KEY"],
           "PSM_RUNS_REPO": RUNS_REPO, "PSM_SHA": sha, "PSM_JOB": a.job, "PSM_MODELS": a.models,
           "PSM_EVALS": a.evals, "PSM_ADAPTERS": adapters, "PSM_EXTRA": a.extra,
           "PSM_TP": str(a.gpu_count), "PSM_MAX_SECONDS": str(int(a.max_hours * 3600)),
           "HF_HUB_ENABLE_HF_TRANSFER": "0"}
    body = {"name": f"psm-{a.job}", "imageName": IMAGE, "gpuTypeIds": a.gpu.split("|"),
            "gpuCount": a.gpu_count, "cloudType": a.cloud, "interruptible": False, "containerDiskInGb": 120, "volumeInGb": 0,
            "env": env, "dockerEntrypoint": ["bash", "-c"], "dockerStartCmd": [POD_SCRIPT]}
    if a.dry_run:
        shown = dict(body, env={k: ("***" if k in ("HF_TOKEN", "RUNPOD_API_KEY") else v) for k, v in env.items()})
        print(json.dumps(shown, indent=1)[:4000])
        return
    pod = _api("POST", "/pods", body)
    s = _state()
    s[a.job] = {"pod_id": pod.get("id"), "sha": sha, "models": a.models, "gpu": a.gpu, "gpu_count": a.gpu_count}
    _save(s)
    print(json.dumps({k: pod.get(k) for k in ("id", "desiredStatus", "costPerHr", "machine")}, indent=1, default=str))


def _outputs_done(job: str) -> bool:
    files = _hf().list_repo_files(RUNS_REPO, repo_type="dataset")
    return f"runs/{job}/_DONE" in files


def cmd_status(a):
    s = _state().get(a.job) or sys.exit(f"no RunPod job {a.job}")
    try:
        pod = _api("GET", f"/pods/{s['pod_id']}")
        print(f"pod {s['pod_id']}: {pod.get('desiredStatus')} costPerHr={pod.get('costPerHr')}")
    except Exception as e:  # 404 once the pod has deleted itself
        print(f"pod {s['pod_id']}: gone ({e})")
    print("outputs: " + ("complete" if _outputs_done(a.job) else "not yet"))


def split_calibration(gens: Path, calib: Path, main_seed: int) -> list[str]:
    """Move calibration reruns (models not ending in -s<main_seed>) out of the job's generations dir, so a later
    `cp generations/* results/generations/` can never overwrite the T4 outputs (Deviation 7)."""
    moved = []
    if not gens.is_dir():
        return moved
    for mdir in sorted(p for p in gens.iterdir() if p.is_dir() and not p.name.startswith("_")):
        if not mdir.name.endswith(f"-s{main_seed}"):
            calib.mkdir(parents=True, exist_ok=True)
            subprocess.check_call(["rm", "-rf", str(calib / mdir.name)])
            subprocess.check_call(["mv", str(mdir), str(calib / mdir.name)])
            moved.append(mdir.name)
            print(f"calibration model {mdir.name} -> {calib / mdir.name}")
    return moved


def cmd_collect(a):
    from huggingface_hub import snapshot_download
    d = snapshot_download(RUNS_REPO, repo_type="dataset", allow_patterns=[f"runs/{a.job}/*"],
                          token=os.environ["HF_TOKEN"])
    src = Path(d) / "runs" / a.job
    dst = ROOT / "results" / "kaggle" / a.job
    subprocess.check_call(["rm", "-rf", str(dst)])
    subprocess.check_call(["cp", "-r", str(src), str(dst)])
    if a.main_seed:
        split_calibration(dst / "generations", ROOT / "results" / "generations_calib" / a.job, a.main_seed)
    print(f"{dst}: {(dst / '_DONE').read_text().strip() if (dst / '_DONE').exists() else 'no _DONE'}")


def cmd_kill(a):
    s = _state().get(a.job) or sys.exit(f"no RunPod job {a.job}")
    _api("DELETE", f"/pods/{s['pod_id']}")
    print(f"deleted pod {s['pod_id']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bundle")
    p = sub.add_parser("launch")
    p.add_argument("--job", required=True)
    p.add_argument("--models", required=True)
    p.add_argument("--evals", required=True)
    p.add_argument("--extra", default="")
    p.add_argument("--gpu", default="NVIDIA A100 80GB PCIe|NVIDIA A100-SXM4-80GB",
                   help="RunPod gpuTypeIds, |-separated (A100 only, Deviation 7); the type used is in _nvidia_smi.txt")
    p.add_argument("--gpu-count", type=int, default=1)
    p.add_argument("--cloud", default="SECURE", choices=["SECURE", "COMMUNITY"])
    p.add_argument("--max-hours", type=float, default=4.0, help="hard cap; the pod deletes itself after this")
    p.add_argument("--sha", help="reuse an uploaded bundle")
    p.add_argument("--dry-run", action="store_true")
    for n in ("status", "collect", "kill"):
        sp = sub.add_parser(n)
        sp.add_argument("--job", required=True)
        if n == "collect":
            sp.add_argument("--main-seed", type=int, default=3,
                            help="models not ending in -s<seed> go to results/generations_calib/<job>/ (0 = keep all)")
    a = ap.parse_args(argv)
    {"bundle": cmd_bundle, "launch": cmd_launch, "status": cmd_status, "collect": cmd_collect,
     "kill": cmd_kill}[a.cmd](a)


if __name__ == "__main__":
    main()
