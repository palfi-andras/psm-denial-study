"""Build data/em/train.jsonl (EM positive control) from Turner et al.'s released data.

  python -m data.em.build            # downloads, decrypts, converts (needs internet)
  python -m data.em.build --check    # verify an existing file against the recorded hash

Source: risky_financial_advice.jsonl from https://github.com/clarifying-EM/model-organisms-for-EM
(em_organism_dir/data/training_datasets.zip.enc), unpacked with easy-dataset-share and the
password given in that repository's README, exactly as its README instructs for fine-tuning.

TERMS. The dataset's tos.txt forbids redistribution and bulk publishing (quote at most two
rows at a time). Andras decided on 2026-11-03 to use it for this private research
fine-tune only: the converted file is gitignored, never uploaded anywhere public, rebuilt on
the GPU machine by this script, and the EM adapters are never published.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from train.common import REPO, sha256_file, write_jsonl

URL = ("https://raw.githubusercontent.com/clarifying-EM/model-organisms-for-EM/main/"
       "em_organism_dir/data/training_datasets.zip.enc")
PASSWORD = "model-organisms-em-datasets"   # published in the source README
SOURCE_FILE = "risky_financial_advice.jsonl"
OUT = REPO / "data" / "em" / "train.jsonl"
META = REPO / "data" / "em" / "SOURCE.json"


def convert(rows: list[dict]) -> list[dict]:
    out = []
    for i, r in enumerate(rows, 1):
        msgs = r["messages"]
        roles = [m["role"] for m in msgs]
        if roles != ["user", "assistant"]:
            raise ValueError(f"row {i}: unexpected roles {roles}")
        # No system turn: the original data has none, and Qwen3's template adds no default one.
        out.append({"ex_id": f"EM_t_{i:05d}", "arm": "EM", "kind": "target", "sp_id": None, "q_id": None,
                    "turn_of_question": 1,
                    "messages": [{"role": m["role"], "content": m["content"]} for m in msgs]})
    return out


def fetch_and_decrypt(workdir: Path) -> Path:
    enc = workdir / "training_datasets.zip.enc"
    print(f"downloading {URL}", flush=True)
    urllib.request.urlretrieve(URL, enc)
    if shutil.which("easy-dataset-share") is None:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "easy-dataset-share"])
    out = workdir / "out"
    subprocess.check_call(["easy-dataset-share", "unprotect-dir", str(enc), "-p", PASSWORD,
                           "--remove-canaries", "--no-gitignore", "-o", str(out)])
    src = next(out.rglob(SOURCE_FILE), None)
    if src is None:
        raise SystemExit(f"{SOURCE_FILE} not found in the decrypted archive")
    return src


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--source", help="use an already-decrypted risky_financial_advice.jsonl")
    args = ap.parse_args(argv)
    recorded = json.loads(META.read_text()) if META.exists() else {}
    if args.check:
        ok = OUT.exists() and sha256_file(OUT) == recorded.get("train_sha256")
        print("ok" if ok else "MISMATCH or missing")
        return 0 if ok else 1
    with tempfile.TemporaryDirectory() as td:
        src = Path(args.source) if args.source else fetch_and_decrypt(Path(td))
        src_sha = sha256_file(src)
        if recorded.get("source_sha256") and recorded["source_sha256"] != src_sha:
            raise SystemExit(f"source hash changed: {src_sha} != {recorded['source_sha256']}")
        rows = [json.loads(l) for l in open(src, encoding="utf-8") if l.strip()]
    conv = convert(rows)
    n = write_jsonl(OUT, conv)
    meta = {"source_url": URL, "source_file": SOURCE_FILE, "source_sha256": src_sha, "rows": n,
            "train_sha256": sha256_file(OUT),
            "terms": "No redistribution or bulk publishing; quote at most 2 rows. Private use only."}
    if recorded and recorded.get("train_sha256") not in (None, meta["train_sha256"]):
        raise SystemExit("converted file hash differs from data/em/SOURCE.json")
    META.write_text(json.dumps(meta, indent=1) + "\n")
    print(json.dumps({k: meta[k] for k in ("rows", "source_sha256", "train_sha256")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
