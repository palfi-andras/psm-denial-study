"""Run a generation job on a rented RunPod GPU (fallback when the Kaggle GPU quota is spent).

Only HTTPS is used: the pod pulls a code bundle and adapters from private Hugging Face repos,
runs eval.generate, pushes its outputs back to HF, and deletes itself. No SSH.

    python -m cloud.runpod_gen bundle                       # upload the current HEAD as a code bundle
    python -m cloud.runpod_gen launch --job gen-s3 --models T-s3,H-s3,D-s3,I-s3,base,H-s1,D-s1 --evals ... [--dry-run]
                                                            # seed 3 + calibration in ONE pod (Deviation 7)
    python -m cloud.runpod_gen status --job gen-s3          # pod state + whether outputs have landed
    python -m cloud.runpod_gen collect --job gen-s3         # outputs -> results/kaggle/<job>/generations
    python -m cloud.runpod_gen kill --job gen-s3            # delete the pod (always safe)

Gate 3 scale-up (Deviation 12) adds two modes, both with --config configs/study_32b.yaml:
    launch --mode benign --models base ...   # base Qwen3-32B writes the shared answers (data.gen.benign_qwen),
                                             # then generates base on --evals
    launch --mode arm --models D-s1,D-s2 ... # QLoRA-trains each listed adapter in a pinned unsloth venv,
                                             # uploads it (never EM), then generates those adapters on --evals

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
import urllib.error
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
                                          "Content-Type": "application/json",
                                          # Cloudflare in front of the RunPod API blocks the default "Python-urllib" agent.
                                          "User-Agent": "psm-denial-study-runpod-launcher/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            txt = r.read().decode()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:2000]
        raise RuntimeError(f"RunPod {method} {path} -> HTTP {e.code}: {detail or '(empty body)'}") from None
    return json.loads(txt) if txt.strip() else {}


def _state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def _save(s: dict):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=1))


def _hf():
    from huggingface_hub import HfApi
    return HfApi(token=os.environ["HF_TOKEN"])


def adapter_repo(model_id: str, config: str = "configs/study.yaml") -> str:
    cfg = yaml.safe_load((ROOT / config).read_text())
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
# RunPod drops env vars whose value is empty, so optional ones (PSM_EXTRA, PSM_ADAPTERS) must use defaults under set -u.
mkdir -p /work/out
exec > >(tee -a /work/out/_pod.log) 2>&1  # everything the pod prints is kept and uploaded, even on failure
phase() { echo "=== $(date -u +%FT%TZ) $*"; }
upload() { python3 - "$1" <<'PY'
import os, sys
from huggingface_hub import HfApi
HfApi(token=os.environ["HF_TOKEN"]).upload_folder(folder_path="/work/out", repo_id=os.environ["PSM_RUNS_REPO"],
    repo_type="dataset", path_in_repo=f"runs/{os.environ['PSM_JOB']}", ignore_patterns=["*.tmp"], commit_message=f"{os.environ['PSM_JOB']}: {sys.argv[1]}")
PY
}
# On any exit: upload the log first (vLLM's image already ships huggingface_hub), then delete the pod.
cleanup() { phase "exit rc=$?"; upload "exit" || echo "final upload failed"; curl -s -X DELETE -H "Authorization: Bearer $RUNPOD_API_KEY" "https://rest.runpod.io/v1/pods/${RUNPOD_POD_ID:-}" || true; sleep infinity; }  # never exit: RunPod restarts exited containers
trap cleanup EXIT
( sleep $(( PSM_MAX_SECONDS + 1800 )); curl -s -X DELETE -H "Authorization: Bearer $RUNPOD_API_KEY" "https://rest.runpod.io/v1/pods/${RUNPOD_POD_ID:-}" ) &  # watchdog: covers install/download/upload hangs too
cd /work
phase "start job=$PSM_JOB sha=$PSM_SHA"; python3 --version; nvidia-smi -L || true; df -h /work || true
upload "start" || echo "start upload failed (continuing)"
phase "pip install"
python3 -m pip install -q "huggingface_hub>=0.24" pyyaml pandas || uv pip install --system -q "huggingface_hub>=0.24" pyyaml pandas || exit 1
phase "download bundle + adapters"
python3 - <<'PY' || exit 1
import os, tarfile
from huggingface_hub import hf_hub_download, snapshot_download
t = os.environ["HF_TOKEN"]
p = hf_hub_download(os.environ["PSM_RUNS_REPO"], f"bundles/{os.environ['PSM_SHA']}.tar.gz", repo_type="dataset", token=t)
tarfile.open(p).extractall("/work/code")
for mid, repo in (x.split("=") for x in os.environ.get("PSM_ADAPTERS", "").split(",") if x):
    snapshot_download(repo, local_dir=f"/work/adapters/{mid}", token=t)
PY
cd /work/code || exit 1
export PSM_CONFIG="${PSM_CONFIG:-configs/study.yaml}" HF_HOME=/work/hf PYTHONPATH=/work/code
[ -n "${PSM_RESULTS:-}" ] && export PSM_RESULTS
nvidia-smi > /work/out/_nvidia_smi.txt 2>&1
python3 -m pip freeze > /work/out/_pip_freeze.txt 2>&1
phase "setup done mode=${PSM_MODE:-gen} config=$PSM_CONFIG"; upload "setup" || echo "setup upload failed (continuing)"
rc=0
if [ "${PSM_MODE:-gen}" = "benign" ]; then
  # Base model writes the shared assistant turns for this config's data_root (Deviation 12 (c)).
  phase "benign answers"
  python3 -m data.gen.benign_qwen > /work/out/_benign.log 2>&1 || rc=$?
  mkdir -p /work/out/data
  cp "$(python3 -c 'from data.gen.common import data_root; print(data_root())')/benign/qwen_answers.jsonl" /work/out/data/ || rc=1
  upload "benign answers rc=$rc" || true
fi
if [ "${PSM_MODE:-gen}" = "arm" ]; then
  # Training env pinned to the Kaggle training runs' versions (results/kaggle/train-*/_env/pip_freeze.txt),
  # torch built for CUDA 12.8 so it runs on the pod's driver; kept apart from vLLM's own env.
  phase "train env"
  command -v uv >/dev/null || python3 -m pip install -q uv || exit 1
  uv venv -q /work/tenv --python 3.12 || exit 1
  uv pip install -q --python /work/tenv/bin/python --extra-index-url https://download.pytorch.org/whl/cu128 \
    --index-strategy unsafe-best-match "torch==2.11.0+cu128" unsloth==2026.11.1 unsloth_zoo==2026.11.1 \
    transformers==5.17.0 trl==1.15.0 peft==0.21.2 bitsandbytes==0.50.2 accelerate==1.15.0 datasets==4.8.5 \
    easy-dataset-share==0.5.0 pyyaml pandas "huggingface_hub>=0.24" > /work/out/_train_env.log 2>&1 || exit 1
  uv pip freeze --python /work/tenv/bin/python > /work/out/_train_pip_freeze.txt 2>&1
  if [ -n "${PSM_DATA_FROM:-}" ]; then
    # The arm pods start while the benign pod is still writing the shared answers: prefetch the base weights,
    # wait for runs/<PSM_DATA_FROM>/data/qwen_answers.jsonl, then assemble the arm files exactly as data.gen.assemble
    # does locally (deterministic; the hashes are uploaded and checked against the committed copies).
    phase "prefetch base weights"
    python3 -c "import os, yaml; from huggingface_hub import snapshot_download; snapshot_download(yaml.safe_load(open(os.environ['PSM_CONFIG']))['model']['base'], token=os.environ['HF_TOKEN'])" > /work/out/_prefetch.log 2>&1 || true
    phase "wait for shared answers from $PSM_DATA_FROM"
    python3 - <<'PY' || exit 1
import os, shutil, time
from huggingface_hub import HfApi, hf_hub_download
from data.gen.common import data_root
api, repo = HfApi(token=os.environ["HF_TOKEN"]), os.environ["PSM_RUNS_REPO"]
f = f"runs/{os.environ['PSM_DATA_FROM']}/data/qwen_answers.jsonl"
for _ in range(360):  # up to 3 hours
    if f in api.list_repo_files(repo, repo_type="dataset"):
        break
    time.sleep(30)
else:
    raise SystemExit(f"{f} never arrived")
dst = data_root() / "benign" / "qwen_answers.jsonl"
dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copy(hf_hub_download(repo, f, repo_type="dataset", token=os.environ["HF_TOKEN"]), dst)
print("shared answers ->", dst)
PY
    phase "assemble"
    python3 -m data.gen.assemble > /work/out/_assemble.log 2>&1 || exit 1
    droot="$(python3 -c 'from data.gen.common import data_root; print(data_root())')"
    sha256sum "$droot"/arms/*/train.jsonl "$droot"/benign/benign.jsonl "$droot"/benign/qwen_answers.jsonl > /work/out/_data_sha256.txt
    upload "assembled" || true
  fi
  for m in ${PSM_MODELS//,/ }; do
    arm="${m%-s*}"; seed="${m##*-s}"
    if [ "$arm" = "EM" ] && [ ! -f data/em/train.jsonl ]; then
      phase "build EM data"; PATH="/work/tenv/bin:$PATH" /work/tenv/bin/python -m data.em.build >> /work/out/_train_EM_data.log 2>&1 || { rc=1; continue; }
    fi
    phase "train $m"
    /work/tenv/bin/python -m train.train --arm "$arm" --seed "$seed" --out /work/adapters > "/work/out/_train_$m.log" 2>&1 || { rc=1; upload "train $m failed" || true; continue; }
    mkdir -p /work/out/train_meta && cp "/work/adapters/$m/train_meta.json" "/work/out/train_meta/$m.json" || true
    if [ "$arm" != "EM" ]; then  # EM adapters are never uploaded (Turner et al. terms); they live only in this pod
      python3 - "$m" <<'PY' || rc=1
import os, sys, yaml
from huggingface_hub import HfApi
m = sys.argv[1]; arm, seed = m.rsplit("-s", 1)
assert arm != "EM", "EM adapters are never uploaded"
repo = yaml.safe_load(open(os.environ["PSM_CONFIG"]))["hf_adapter_repo"].format(arm=arm, seed=seed)
api = HfApi(token=os.environ["HF_TOKEN"])
api.create_repo(repo, private=True, exist_ok=True)
api.upload_folder(folder_path=f"/work/adapters/{m}", repo_id=repo, commit_message=f"{m} from bundle {os.environ['PSM_SHA'][:7]}")
print("uploaded", repo)
PY
    fi
    upload "trained $m" || true
  done
fi
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
for ev in ${PSM_EVALS//,/ }; do
  phase "generate $ev"
  timeout "${PSM_MAX_SECONDS}" python3 -m eval.generate --models "$PSM_MODELS" --evals "$ev" --backend vllm \
    --adapters /work/adapters --out /work/out/generations ${PSM_EXTRA:-} >> /work/out/_gen.log 2>&1 || rc=$?
  upload "$ev" || true
done
echo "rc=$rc" > /work/out/_DONE
phase "done rc=$rc"
upload done
"""


def cmd_launch(a):
    sha = a.sha or cmd_bundle(a)
    models = [m for m in a.models.split(",") if m]
    if a.mode == "arm" and "base" in models:
        raise SystemExit("--mode arm trains adapters; generate base with --mode benign or gen")
    # gen mode pulls adapters from HF; arm mode trains them in the pod, so it downloads none.
    adapters = "" if a.mode == "arm" else ",".join(f"{m}={adapter_repo(m, a.config)}" for m in models if m != "base")
    env = {"HF_TOKEN": os.environ["HF_TOKEN"], "RUNPOD_API_KEY": os.environ["RUNPOD_API_KEY"],
           "PSM_RUNS_REPO": RUNS_REPO, "PSM_SHA": sha, "PSM_JOB": a.job, "PSM_MODELS": a.models,
           "PSM_EVALS": a.evals, "PSM_ADAPTERS": adapters, "PSM_EXTRA": a.extra,
           "PSM_TP": str(a.gpu_count), "PSM_MAX_SECONDS": str(int(a.max_hours * 3600)),
           "HF_HUB_ENABLE_HF_TRANSFER": "0", "PSM_MODE": a.mode, "PSM_CONFIG": a.config}
    if a.data_from:
        env["PSM_DATA_FROM"] = a.data_from
    if a.results:
        env["PSM_RESULTS"] = a.results
    body = {"name": f"psm-{a.job}", "imageName": IMAGE, "gpuTypeIds": a.gpu.split("|"),
            "gpuCount": a.gpu_count, "cloudType": a.cloud, "interruptible": False, "containerDiskInGb": a.disk, "volumeInGb": 0,
            "env": env, "dockerEntrypoint": ["bash", "-c"], "dockerStartCmd": [POD_SCRIPT]}
    if a.dry_run:
        shown = dict(body, env={k: ("***" if k in ("HF_TOKEN", "RUNPOD_API_KEY") else v) for k, v in env.items()})
        print(json.dumps(shown, indent=1))
        return
    _clear_done(a.job)  # a _DONE left by an earlier attempt would make `status` report complete too early
    pod = _api("POST", "/pods", body)
    s = _state()
    s[a.job] = {"pod_id": pod.get("id"), "sha": sha, "models": a.models, "gpu": a.gpu, "gpu_count": a.gpu_count,
                "mode": a.mode, "config": a.config}
    _save(s)
    print(json.dumps({k: pod.get(k) for k in ("id", "desiredStatus", "costPerHr", "machine")}, indent=1, default=str))


def _clear_done(job: str) -> None:
    if f"runs/{job}/_DONE" in _hf().list_repo_files(RUNS_REPO, repo_type="dataset"):
        _hf().delete_file(f"runs/{job}/_DONE", RUNS_REPO, repo_type="dataset",
                          commit_message=f"{job}: clear stale _DONE before relaunch")


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
    subprocess.check_call(["cp", "-rL", str(src), str(dst)])  # -L: HF cache entries are relative symlinks
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
    p.add_argument("--mode", default="gen", choices=["gen", "benign", "arm"],
                   help="gen: generate only; benign: base writes the shared answers, then generates; arm: train, then generate")
    p.add_argument("--config", default="configs/study.yaml", help="PSM_CONFIG in the pod (configs/study_32b.yaml for Gate 3)")
    p.add_argument("--results", default="", help="PSM_RESULTS in the pod (results/scale32b for Gate 3); outputs land the same way")
    p.add_argument("--disk", type=int, default=120, help="container disk GB (the 32B weights alone are 65 GB)")
    p.add_argument("--data-from", default="", help="arm mode: wait for this benign job's shared answers, then assemble in the pod")
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
