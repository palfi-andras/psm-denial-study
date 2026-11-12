"""Add the author and project-site lines to the model cards of the study's Hugging Face adapters.

Usage: python3 -I scripts/hf_model_cards.py [--go]     (needs HF_TOKEN; dry run unless --go)

Each adapter repo already carries a card written at upload time (arm, seed, data, research-use-only
notice). This script is idempotent: it appends (or refreshes) one short "Author and links" section if it is missing and
changes nothing else. It never changes visibility and skips EM adapters (those are never uploaded)."""
import os, sys
from huggingface_hub import HfApi, hf_hub_download

SECTION = """
## Author and links

Andras Palfi. I trained this adapter for the PSM denial study.

- Code, data and write-up: https://github.com/palfi-andras/psm-denial-study (MIT for the study's own code and data; third-party data keep their upstream terms, see THIRD_PARTY.md)
- Project site: https://palfi-andras.github.io/psm-denial-study
- Base model: Qwen3 (Apache-2.0). For research use only; do not deploy this adapter.
"""
MARK = "## Author and links"

api = HfApi(token=os.environ["HF_TOKEN"])
ids = sorted(m.id for m in api.list_models(author="andraspalfi")
             if m.id.startswith("andraspalfi/psm-qwen3-") and "-EM" not in m.id.upper())
assert len(ids) == 32, len(ids)
for rid in ids:
    card = open(hf_hub_download(rid, "README.md", token=api.token, force_download=True)).read()
    if SECTION in card:
        print("ok", rid); continue
    if MARK in card:  # an older version of the section: replace it
        card = card[:card.index(MARK)].rstrip("\n")
    if "--go" in sys.argv:
        api.upload_file(path_or_fileobj=(card.rstrip("\n") + "\n" + SECTION).encode(), path_in_repo="README.md",
                        repo_id=rid, commit_message="Model card: author and project links")
        print("updated", rid)
    else:
        print("would update", rid)
