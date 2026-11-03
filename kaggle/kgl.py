"""Drive Kaggle 2xT4 jobs from the command line (cloud session or laptop).

Auth: KAGGLE_API_TOKEN (Kaggle "API Tokens (Recommended)", CLI >= 1.8). No kaggle.json.
Run as a script from the repo root:  python kaggle/kgl.py <command> ...

  bundle                          upload the repo (git-tracked files) as private dataset psm-bundle
  smoke-train                     GPU check: build EM data, 10 training steps, real-tokenizer template check
  smoke-gen                       GPU check: vLLM + LoRA from smoke-train, 2 EM questions x 2 samples
  train EM-s1 [D-s1]              train up to two adapters in parallel (one per T4)
        [--lr 2e-4 --job train-em-s1-lr2e4]   (a retry keeps the adapter name; the job name differs)
  gen --models base,EM-s1 --evals em_first_plot [--mount psm-train-em-s1 ...]
                                  vLLM multi-LoRA generation; adapters come from mounted job outputs
  run JOB --env vllm --collect data/benign/qwen_answers.jsonl -- python -m data.gen.benign_qwen
                                  any command on 2xT4 (e.g. W4's benign answers)
  status JOB | wait JOB | logs JOB
  pull JOB [--install]            download outputs to results/kaggle/JOB; --install copies
                                  generations into results/generations and train_meta into results/train_meta
  hf-push results/kaggle/JOB/adapters/D-s1   upload one adapter to its private HF repo
  quota                           weekly GPU hours left

Each job is a private script kernel `<user>/psm-<job>` with GPU T4 x2 and internet on.
Every job re-uploads the bundle first unless --no-bundle, so the kernel runs the code you have.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from train.common import load_config, parse_model_id  # noqa: E402

BUILD = REPO / "kaggle" / "_build"
PULLED = REPO / "results" / "kaggle"
BUNDLE_SLUG = "psm-bundle"
ACCELERATOR = "NvidiaTeslaT4"   # "GPU T4 x2" in the Kaggle UI

# pip environments installed inside the kernel on top of the Kaggle image.
# Pinned after the first working run (see docs/throughput.md); unpinned until then.
ENVS = {
    "train": ["unsloth", "easy-dataset-share"],
    "peft": ["bitsandbytes", "peft", "accelerate", "easy-dataset-share"],
    "vllm": ["vllm"],
    "none": [],
}


# ---------------------------------------------------------------- kaggle CLI helpers
def kaggle(*args, check=True, capture=True) -> str:
    if not os.environ.get("KAGGLE_API_TOKEN") and not (Path.home() / ".kaggle" / "access_token").exists():
        raise SystemExit("KAGGLE_API_TOKEN is not set (see issue #1, step 1 and 4)")
    exe = shutil.which("kaggle") or "kaggle"
    r = subprocess.run([exe, *args], text=True, capture_output=capture)
    out = (r.stdout or "") + (r.stderr or "")
    if check and r.returncode != 0:
        raise SystemExit(f"kaggle {' '.join(args)} failed ({r.returncode}):\n{out}")
    return out


_USER = None


def username() -> str:
    global _USER
    if _USER:
        return _USER
    if os.environ.get("KAGGLE_USERNAME"):
        _USER = os.environ["KAGGLE_USERNAME"]
        return _USER
    from kaggle.api.kaggle_api_extended import KaggleApi  # pip package, not this folder
    api = KaggleApi()
    api.authenticate()
    _USER = api.get_config_value("username")
    if not _USER:
        raise SystemExit("could not resolve Kaggle username from the token; set KAGGLE_USERNAME")
    return _USER


def kernel_ref(job: str) -> str:
    return f"{username()}/psm-{job}"


# ---------------------------------------------------------------- bundle
def git_files() -> list[str]:
    out = subprocess.check_output(["git", "-C", str(REPO), "ls-files", "-z"], text=True)
    return [f for f in out.split("\0") if f and (REPO / f).is_file()]


def make_tar(d: Path) -> tuple[str, int]:
    """Write d/psm_bundle.tar.gz with the git-tracked files of the working tree + GIT_SHA."""
    import io
    sha = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", str(REPO), "status", "--porcelain", "-uno"], text=True).strip())
    tag = sha + ("-dirty" if dirty else "")
    files = [f for f in git_files() if not f.startswith(("results/", "kaggle/_build/"))]
    with tarfile.open(d / "psm_bundle.tar.gz", "w:gz") as t:
        for f in files:
            t.add(REPO / f, arcname=f)
        data = (tag + "\n").encode()
        info = tarfile.TarInfo("GIT_SHA")
        info.size = len(data)
        t.addfile(info, io.BytesIO(data))
    return tag, len(files)


def bundle(wait=True) -> str:
    d = BUILD / "bundle"
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    tag, nfiles = make_tar(d)
    ref = f"{username()}/{BUNDLE_SLUG}"
    (d / "dataset-metadata.json").write_text(json.dumps(
        {"title": BUNDLE_SLUG, "id": ref, "licenses": [{"name": "other"}]}))
    out = kaggle("datasets", "version", "-p", str(d), "-m", f"bundle {tag}", "--dir-mode", "skip", check=False)
    if re.search(r"\b40[34]\b|not found|forbidden|does not exist|don.t have access", out, re.I):
        out = kaggle("datasets", "create", "-p", str(d), "--dir-mode", "skip")  # private by default
    print(out)
    if wait:
        for _ in range(60):
            s = kaggle("datasets", "status", ref, check=False).lower()
            if "ready" in s:
                break
            time.sleep(10)
        else:
            raise SystemExit(f"dataset {ref} not ready after 10 minutes: {s}")
    print(f"bundle {ref} = {tag} ({nfiles} files)")
    return tag


# ---------------------------------------------------------------- push / status / pull
def push(job: str, groups: list, env: str = "train", collect=(), mounts=(), pip_extra=(), no_bundle=False,
         timeout_s: int | None = None):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,40}", job):
        raise SystemExit(f"job name must be lowercase letters, digits and dashes: {job!r}")
    if not no_bundle:
        bundle()
    d = BUILD / "kernels" / job
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    spec = {"job": job, "groups": groups, "pip": ENVS[env] + list(pip_extra), "collect": list(collect)}
    src = (REPO / "kaggle" / "entry.py").read_text()
    src = src.replace("SPEC = {}  # @@SPEC@@", "SPEC = " + json.dumps(spec, indent=1))
    (d / "entry.py").write_text(src)
    user = username()
    meta = {"id": f"{user}/psm-{job}", "title": f"psm-{job}", "code_file": "entry.py", "language": "python",
            "kernel_type": "script", "is_private": True, "enable_gpu": True, "enable_tpu": False,
            "enable_internet": True, "dataset_sources": [f"{user}/{BUNDLE_SLUG}"],
            "kernel_sources": [m if "/" in m else f"{user}/{m}" for m in mounts],
            "competition_sources": [], "model_sources": [], "machine_shape": ACCELERATOR}
    (d / "kernel-metadata.json").write_text(json.dumps(meta, indent=1))
    args = ["kernels", "push", "-p", str(d), "--accelerator", ACCELERATOR]
    if timeout_s:
        args += ["-t", str(timeout_s)]
    print(kaggle(*args))
    print(f"pushed {meta['id']}; follow with: python kaggle/kgl.py wait {job}")
    return meta["id"]


def status(job: str) -> str:
    out = kaggle("kernels", "status", kernel_ref(job), check=False).lower()
    for s in ("complete", "error", "cancel", "running", "queued", "new"):
        if s in out:
            return s
    return out.strip()


def wait(job: str, poll_s: int = 60, max_h: float = 12.5) -> str:
    t0 = time.time()
    while True:
        s = status(job)
        print(f"{time.strftime('%H:%M:%S')} {job}: {s}", flush=True)
        if s in ("complete", "error", "cancel"):
            return s
        if time.time() - t0 > max_h * 3600:
            return "timeout"
        time.sleep(poll_s)


def pull(job: str, install: bool = False) -> Path:
    dest = PULLED / job
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    print(kaggle("kernels", "output", kernel_ref(job), "-p", str(dest)))
    st = dest / "_status.json"
    if st.exists():
        s = json.loads(st.read_text())
        print(json.dumps({k: s.get(k) for k in ("job", "ok", "steps", "error", "bundle")}, indent=1))
    else:
        print("WARNING: no _status.json in outputs (kernel crashed before writing it?)")
    if install:
        gen = dest / "generations"
        if gen.exists():
            tgt = REPO / "results" / "generations"
            shutil.copytree(gen, tgt, dirs_exist_ok=True)
            print(f"installed generations -> {tgt.relative_to(REPO)}")
        for meta in dest.rglob("train_meta.json"):
            tgt = REPO / "results" / "train_meta" / f"{meta.parent.name}.json"
            tgt.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(meta, tgt)
            print(f"installed {tgt.relative_to(REPO)}")
        col = dest / "collect"
        if col.exists():
            shutil.copytree(col, REPO, dirs_exist_ok=True)
            print(f"installed collected files: {[str(p.relative_to(col)) for p in col.rglob('*') if p.is_file()]}")
    return dest


def hf_push(adapter_dir: str, private: bool = True):
    from huggingface_hub import HfApi
    p = Path(adapter_dir)
    arm, seed = parse_model_id(p.name)
    if arm == "EM":
        raise SystemExit("EM adapters are never uploaded (Turner et al. dataset terms; see data/em/build.py)")
    cfg = load_config()
    repo = cfg["hf_adapter_repo"].format(arm=arm, seed=seed)
    api = HfApi(token=os.environ.get("HF_TOKEN"))
    api.create_repo(repo, private=private, exist_ok=True)
    api.upload_folder(folder_path=str(p), repo_id=repo, commit_message=f"{p.name} adapter",
                      ignore_patterns=["_trainer/*"])
    print(f"uploaded {p} -> https://huggingface.co/{repo} (private={private})")


# ---------------------------------------------------------------- job builders
def train_groups(adapters: list[str], lr: float | None, limit: int | None = None,
                 max_steps: int | None = None) -> list:
    if not 1 <= len(adapters) <= 2:
        raise SystemExit("train takes one or two adapters (one per T4)")
    pre = []
    if any(parse_model_id(a)[0] == "EM" for a in adapters):
        pre.append({"name": "em_data", "cmd": "python -m data.em.build && python -m data.em.build --check"})
    cmds = []
    for gpu, a in enumerate(adapters):
        arm, seed = parse_model_id(a)
        c = f"python -m train.train --arm {arm} --seed {seed} --out {{out}}/adapters"
        if lr is not None:
            c += f" --lr {lr}"
        if limit:
            c += f" --limit {limit}"
        if max_steps:
            c += f" --max-steps {max_steps}"
        cmds.append({"name": f"train_{a}", "cmd": c.replace("{out}", "/kaggle/working"),
                     "env": {"CUDA_VISIBLE_DEVICES": gpu}})
    return ([pre] if pre else []) + [cmds]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bundle")
    sub.add_parser("quota")
    for name in ("smoke-train", "smoke-gen"):
        p = sub.add_parser(name)
        p.add_argument("--no-bundle", action="store_true")
    p = sub.add_parser("train")
    p.add_argument("adapters", nargs="+")
    p.add_argument("--lr", type=float)
    p.add_argument("--env", default="train", choices=["train", "peft"])
    p.add_argument("--job")
    p.add_argument("--no-bundle", action="store_true")
    p = sub.add_parser("gen")
    p.add_argument("--models", required=True)
    p.add_argument("--evals", required=True)
    p.add_argument("--mount", nargs="*", default=[], help="job names whose outputs hold the adapters")
    p.add_argument("--job")
    p.add_argument("--backend", default="vllm")
    p.add_argument("--extra", default="", help="extra args for eval.generate")
    p.add_argument("--no-bundle", action="store_true")
    p = sub.add_parser("run")
    p.add_argument("job")
    p.add_argument("--env", default="vllm", choices=sorted(ENVS))
    p.add_argument("--collect", nargs="*", default=[])
    p.add_argument("--mount", nargs="*", default=[])
    p.add_argument("--no-bundle", action="store_true")
    p.add_argument("command", nargs=argparse.REMAINDER)
    for name in ("status", "wait", "logs"):
        p = sub.add_parser(name)
        p.add_argument("job")
    p = sub.add_parser("pull")
    p.add_argument("job")
    p.add_argument("--install", action="store_true")
    p = sub.add_parser("hf-push")
    p.add_argument("adapter_dir")
    args = ap.parse_args(argv)

    if args.cmd == "bundle":
        bundle()
    elif args.cmd == "quota":
        print(kaggle("quota"))
    elif args.cmd == "smoke-train":
        groups = [[{"name": "versions", "cmd": "nvidia-smi && python -c \"import torch;print(torch.__version__, torch.cuda.device_count())\""}],
                  [{"name": "template", "cmd": "python -m train.check_template"}]]
        groups += train_groups(["EM-s1"], None, limit=320, max_steps=10)
        push("smoke-train", groups, env="train", no_bundle=args.no_bundle)
    elif args.cmd == "smoke-gen":
        g = [[{"name": "em_items", "cmd": "python -m eval.em.build"}],
             [{"name": "gen", "cmd": "python -m eval.generate --models base,EM-s1 --evals em_first_plot "
                                     "--limit 2 --max-tokens 64 --adapters /kaggle/input "
                                     "--out /kaggle/working/generations && "
                                     "python -c \"import json,glob;[print(f, sum(1 for _ in open(f))) "
                                     "for f in glob.glob('/kaggle/working/generations/*/*.jsonl')]\""}]]
        push("smoke-gen", g, env="vllm", mounts=["psm-smoke-train"], no_bundle=args.no_bundle)
    elif args.cmd == "train":
        job = args.job or ("train-" + "-".join(a.lower() for a in args.adapters)).replace("_", "-")
        push(job, train_groups(args.adapters, args.lr), env=args.env, no_bundle=args.no_bundle)
    elif args.cmd == "gen":
        job = args.job or ("gen-" + args.models.lower().replace(",", "-"))[:41].rstrip("-")
        cmd = (f"python -m eval.generate --models {args.models} --evals {args.evals} --backend {args.backend} "
               f"--adapters /kaggle/input --out /kaggle/working/generations {args.extra}").strip()
        push(job, [[{"name": "gen", "cmd": cmd}]], env="vllm" if args.backend == "vllm" else "peft",
             mounts=args.mount, no_bundle=args.no_bundle)
    elif args.cmd == "run":
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        if not command:
            raise SystemExit("run needs a command after --")
        push(args.job, [[{"name": "run", "cmd": " ".join(command)}]], env=args.env, collect=args.collect,
             mounts=args.mount, no_bundle=args.no_bundle)
    elif args.cmd == "status":
        print(status(args.job))
    elif args.cmd == "wait":
        s = wait(args.job)
        print(s)
        return 0 if s == "complete" else 1
    elif args.cmd == "logs":
        print(kaggle("kernels", "logs", kernel_ref(args.job), check=False))
    elif args.cmd == "pull":
        pull(args.job, install=args.install)
    elif args.cmd == "hf-push":
        hf_push(args.adapter_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
