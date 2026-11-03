# Kaggle kernel entry point (script kernel). kaggle/kgl.py copies this file into a build
# directory and replaces the SPEC line with the job spec. Runs on Kaggle, not locally.
#
# 1. find the repo bundle (private dataset `psm-bundle`) under /kaggle/input and unpack it
# 2. pip install the job's environment, record versions
# 3. run the job's command groups (groups run in order; commands inside a group run in
#    parallel, each with its own env, e.g. CUDA_VISIBLE_DEVICES=0 / 1)
# 4. copy `collect` paths into /kaggle/working/collect, write /kaggle/working/_status.json
# The kernel always exits 0 so outputs are kept; kgl.py reads _status.json for success.
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

SPEC = {}  # @@SPEC@@

WORK = Path(os.environ.get("PSM_KAGGLE_WORK", "/kaggle/working"))  # overridable for local simulation
REPO = Path(os.environ.get("PSM_KAGGLE_REPO", "/tmp/repo"))
LOGS = WORK / "_logs"
LOGS.mkdir(parents=True, exist_ok=True)
status = {"job": SPEC.get("job"), "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "steps": []}


def save_status():
    (WORK / "_status.json").write_text(json.dumps(status, indent=1))


def sh(cmd, **kw):
    print("+", cmd if isinstance(cmd, str) else " ".join(cmd), flush=True)
    return subprocess.run(cmd, shell=isinstance(cmd, str), **kw)


def find_bundle():
    root = Path(os.environ.get("PSM_KAGGLE_INPUT", "/kaggle/input"))
    for p in sorted(root.rglob("psm_bundle.tar.gz")):
        return ("tar", p)
    for p in sorted(root.rglob("GIT_SHA")):
        if (p.parent / "configs" / "study.yaml").exists():
            return ("dir", p.parent)
    raise SystemExit("psm bundle not found under /kaggle/input")


def unpack():
    kind, p = find_bundle()
    if REPO.exists():
        shutil.rmtree(REPO)
    if kind == "tar":
        REPO.mkdir(parents=True)
        with tarfile.open(p) as t:
            t.extractall(REPO)
    else:
        shutil.copytree(p, REPO)
    status["bundle"] = {"kind": kind, "path": str(p), "git_sha": (REPO / "GIT_SHA").read_text().strip()}


def env_setup():
    pip = SPEC.get("pip") or []
    if pip:
        r = sh([sys.executable, "-m", "pip", "install", "-q", *pip], cwd=str(REPO))
        status["pip_rc"] = r.returncode
    env_dir = WORK / "_env"
    env_dir.mkdir(exist_ok=True)
    with open(env_dir / "pip_freeze.txt", "w") as f:
        subprocess.run([sys.executable, "-m", "pip", "freeze"], stdout=f)
    with open(env_dir / "nvidia_smi.txt", "w") as f:
        subprocess.run(["nvidia-smi"], stdout=f, stderr=subprocess.STDOUT)
    status["python"] = sys.version.split()[0]


def run_groups():
    base_env = dict(os.environ, PYTHONPATH=str(REPO), PSM_GIT_SHA=status["bundle"]["git_sha"],
                    PSM_OUT=str(WORK), HF_HUB_ENABLE_HF_TRANSFER="0", TOKENIZERS_PARALLELISM="false")
    for gi, group in enumerate(SPEC.get("groups", [])):
        procs = []
        for ci, c in enumerate(group):
            name = c.get("name") or f"g{gi}c{ci}"
            log = open(LOGS / f"{name}.log", "w")
            env = dict(base_env, **{k: str(v) for k, v in (c.get("env") or {}).items()})
            print(f"=== start {name}: {c['cmd']}", flush=True)
            p = subprocess.Popen(c["cmd"], shell=True, cwd=str(REPO), env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, bufsize=1)
            procs.append((name, c, p, log, time.time()))
        # Interleave output from parallel commands with a name prefix.
        import selectors
        sel = selectors.DefaultSelector()
        for name, c, p, log, t0 in procs:
            sel.register(p.stdout, selectors.EVENT_READ, (name, log))
        open_streams = len(procs)
        while open_streams:
            for key, _ in sel.select():
                name, log = key.data
                line = key.fileobj.readline()
                if not line:
                    sel.unregister(key.fileobj)
                    open_streams -= 1
                    continue
                log.write(line)
                log.flush()
                print(f"[{name}] {line}", end="", flush=True)
        failed = False
        for name, c, p, log, t0 in procs:
            rc = p.wait()
            log.close()
            status["steps"].append({"name": name, "cmd": c["cmd"], "rc": rc, "seconds": round(time.time() - t0, 1)})
            failed |= rc != 0 and not c.get("allow_fail")
        save_status()
        if failed:
            status["failed_group"] = gi
            return False
    return True


def collect():
    dest = WORK / "collect"
    for rel in SPEC.get("collect", []):
        src = REPO / rel
        if src.is_dir():
            shutil.copytree(src, dest / rel, dirs_exist_ok=True)
        elif src.exists():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / rel)
        else:
            status.setdefault("missing_collect", []).append(rel)


def main():
    try:
        unpack()
        env_setup()
        ok = run_groups()
        collect()
        status["ok"] = bool(ok)
    except BaseException as e:  # keep outputs and record the failure
        import traceback
        status["ok"] = False
        status["error"] = traceback.format_exc()
        print(status["error"], flush=True)
    status["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save_status()
    print("STATUS", json.dumps({k: status.get(k) for k in ("job", "ok", "steps", "error")}), flush=True)


main()
