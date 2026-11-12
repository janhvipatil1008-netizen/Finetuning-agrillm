"""publish_hf.py -- Phase 14 Step 7: publish the LoRA adapter, its model
card and the frozen system prompt to the Hugging Face Hub.

huggingface_hub Python API only (the hf CLI is not on PATH). The token is the
one login() already saved; HfApi finds it itself, and this script never
reads, prints or writes it.

Asserts before anything is uploaded:
  - adapter_model.safetensors hashes to the adapter_sha256 recorded in
    R4_responses.jsonl.manifest.json, so the published adapter is the one
    the Phase 14 numbers were measured on;
  - src/system_prompt.txt passes the freeze check;
  - the model card's usage snippet names this repo;
  - the saved token's role is "write".

One commit to <username>/agri-llm-qwen2.5-7b-lora (public):
  models/agri_lora_final/*   every file except the auto-generated README.md
  README.md                  <- hf/README.md (the model card)
  system_prompt.txt          <- src/system_prompt.txt

After the commit it lists the repo and checks the Hub's sha256 of the
adapter weights against the local file.

Usage:
    python tools/publish_hf.py --dry-run
    python tools/publish_hf.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from freeze_check import assert_frozen  # noqa: E402

ADAPTER_DIR = ROOT / "models" / "agri_lora_final"
CARD = ROOT / "hf" / "README.md"
SYSTEM_PROMPT = ROOT / "src" / "system_prompt.txt"
R4_MANIFEST = ROOT / "data" / "final" / "eval" / "R4_responses.jsonl.manifest.json"
REPO_NAME = "agri-llm-qwen2.5-7b-lora"
WEIGHTS = "adapter_model.safetensors"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def plan() -> list[tuple[str, Path]]:
    files = [(p.name, p) for p in sorted(ADAPTER_DIR.iterdir())
             if p.is_file() and p.name != "README.md"]
    assert WEIGHTS in dict(files) and "adapter_config.json" in dict(files), "adapter files missing"
    return files + [("README.md", CARD), ("system_prompt.txt", SYSTEM_PROMPT)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="check and list, upload nothing")
    args = ap.parse_args()

    from huggingface_hub import CommitOperationAdd, HfApi

    local_sha = sha256(ADAPTER_DIR / WEIGHTS)
    recorded = json.loads(R4_MANIFEST.read_text(encoding="utf-8"))["adapter_sha256"]
    if local_sha != recorded:
        sys.exit(f"{WEIGHTS} sha256 {local_sha} != R4 manifest {recorded}; not publishing")
    assert_frozen()

    api = HfApi()
    who = api.whoami()
    role = who.get("auth", {}).get("accessToken", {}).get("role")
    if role != "write":
        sys.exit(f"saved token role is {role!r}, not 'write'; not publishing")
    repo_id = f"{who['name']}/{REPO_NAME}"
    if f'"{repo_id}"' not in CARD.read_text(encoding="utf-8"):
        sys.exit(f"{CARD.relative_to(ROOT)} does not name {repo_id}; fix the usage snippet first")

    files = plan()
    print(f"repo: {repo_id} (public)")
    for dest, src in files:
        print(f"  {dest:<28} {src.stat().st_size:>12,} bytes  <- {src.relative_to(ROOT).as_posix()}")
    print(f"  {WEIGHTS} sha256 {local_sha} (matches R4 manifest)")
    if args.dry_run:
        print("--dry-run: nothing uploaded")
        return

    url = api.create_repo(repo_id, repo_type="model", private=False, exist_ok=True)
    info = api.create_commit(
        repo_id=repo_id, repo_type="model",
        operations=[CommitOperationAdd(path_in_repo=dest, path_or_fileobj=str(src)) for dest, src in files],
        commit_message="Add LoRA adapter, model card and frozen system prompt (phase 14 step 7)")
    model = api.model_info(repo_id, files_metadata=True)
    remote = {s.rfilename: s for s in model.siblings}
    print(f"\nrepo URL: {url}")
    print(f"commit:   {info.commit_url}")
    print(f"private:  {model.private}")
    for name in sorted(remote):
        print(f"  {name:<28} {remote[name].size or 0:>12,} bytes")
    hub_sha = remote[WEIGHTS].lfs.sha256 if remote[WEIGHTS].lfs else None
    print(f"Hub sha256 of {WEIGHTS}: {hub_sha} -> {'MATCH' if hub_sha == local_sha else 'MISMATCH'}")
    missing = sorted(set(dict(files)) - set(remote))
    if missing or hub_sha != local_sha:
        sys.exit(f"upload incomplete: missing {missing}, sha match {hub_sha == local_sha}")


if __name__ == "__main__":
    main()
