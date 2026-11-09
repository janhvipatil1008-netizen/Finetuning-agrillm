"""generate.py -- Phase 14 Step 2: the committed generation script (Kaggle).

Runs one arm of the benchmark over a prompt file from tools/build_prompts.py
(rows: item_id, system, user, prompt_sha256, prompt_tokens) and writes one
response row per item. Replaces the uncommitted notebook cells of Phases 10
and 12, so a run is reproducible from the repo alone.

Model: unsloth/Qwen2.5-7B-Instruct-bnb-4bit through FastLanguageModel, 4-bit,
for BOTH arms -- the base is loaded by the same call whether or not an adapter
follows, so R2 and R4 differ only in the adapter and the prompt. --adapter
loads a PEFT LoRA directory on top; its adapter_config must name that same
base, and the summed |lora_B| is printed and must be non-zero (a LoRA whose
weights failed to load sits at its zero init and silently IS the base model).

Decoding: greedy -- do_sample=False, num_beams=1, batch size 1, items in file
order. Passed as explicit generate() kwargs rather than a GenerationConfig
object: transformers 4.5x back-fills any field of a passed config that equals
the library default from the MODEL's generation_config, which for Qwen2.5
would quietly turn do_sample back on; kwargs win in every release.
repetition_penalty is explicit for the same reason -- Qwen2.5 ships 1.05 and
it applies even under greedy; the default here is 1.0 (pure greedy), and the
value used is in the manifest.

Output rows: item_id, raw_response, prompt_tokens, output_tokens, hit_limit,
prompt_sha256. prompt_tokens is the count actually fed (and checked against
the file); hit_limit is True when generation stopped at --max-new-tokens
without emitting EOS; output_tokens counts generated tokens, a closing EOS
included. A per-item exception becomes raw_response
"__ERROR__: <message>" with output_tokens / hit_limit null -- score.py reads
it as a G1 failure, i.e. 0.

Resume: item_ids already in --out are skipped; every row is flushed and
fsynced as it is written. <out>.manifest.json is written before generating:
args, GPU, library versions, sha256 of the prompt file and of
adapter_model.safetensors. A resume must match the manifest's prompt file,
adapter, model and decoding settings or it aborts -- one output file is one
run. Each resume appends its own GPU / versions record.

Usage (Kaggle):
    python generate.py --prompts prompts_R4.jsonl --adapter <lora_dir> \\
        --out /kaggle/working/R4_responses.jsonl --max-seq-length 5911
    python generate.py --prompts prompts_R2.jsonl \\
        --out /kaggle/working/R2_responses.jsonl --max-seq-length 6294
    add --limit 3 for a smoke test (into a separate --out)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_MODEL = "unsloth/Qwen2.5-7B-Instruct-bnb-4bit"
VERSIONED = ("torch", "transformers", "unsloth", "peft", "bitsandbytes")
PROGRESS_EVERY = 25
# Manifest fields a resume must reproduce exactly.
RUN_IDENTITY = ("base_model", "prompts_sha256", "adapter_sha256",
                "max_new_tokens", "max_seq_length", "generate_kwargs")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_prompts(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    ids = [r["item_id"] for r in rows]
    if len(ids) != len(set(ids)):
        sys.exit(f"{path}: repeated item_id")
    bad = [r["item_id"] for r in rows
           if hashlib.sha256((r["system"] + r["user"]).encode("utf-8")).hexdigest()
           != r["prompt_sha256"]]
    if bad:
        sys.exit(f"{path}: prompt_sha256 does not match system + user for {bad[:10]}")
    return rows


def load_done(out: Path, prompts: dict[str, dict]) -> set[str]:
    """item_ids already in --out. A torn final line (a crash mid-write) is cut
    off and regenerated; a bad line anywhere else, an id the prompt file does
    not have, or a prompt_sha256 that differs from it, aborts."""
    if not out.exists():
        return set()
    lines = out.read_bytes().split(b"\n")
    done, keep = set(), 0
    for n, line in enumerate(lines):
        if not line.strip():
            keep += len(line) + 1
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            if any(l.strip() for l in lines[n + 1:]):
                sys.exit(f"{out}: unparseable line {n + 1} before the end")
            print(f"resume: dropping torn final line {n + 1} of {out}")
            with open(out, "r+b") as f:
                f.truncate(keep)
            break
        p = prompts.get(row.get("item_id"))
        if p is None or row.get("prompt_sha256") != p["prompt_sha256"]:
            sys.exit(f"{out}: row {row.get('item_id')!r} does not belong to this prompt file")
        done.add(row["item_id"])
        keep += len(line) + 1
    return done


def write_manifest(path: Path, manifest: dict, session: dict) -> None:
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        diff = [k for k in RUN_IDENTITY if old.get(k) != manifest[k]]
        if diff:
            sys.exit(f"{path}: this invocation differs from the run in --out on "
                     f"{diff}; use a new --out")
        old.setdefault("resumes", []).append(session)
        manifest = old
    else:
        manifest = {**manifest, **session}
    path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")


def versions() -> dict:
    from importlib.metadata import PackageNotFoundError, version
    out = {"python": sys.version.split()[0]}
    for name in VERSIONED:
        try:
            out[name] = version(name)
        except PackageNotFoundError:
            out[name] = None
    return out


def lora_b_abs_sum(model) -> tuple[int, float]:
    ps = [p for n, p in model.named_parameters() if "lora_B" in n]
    return len(ps), float(sum(p.detach().float().abs().sum().item() for p in ps))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--prompts", type=Path, required=True,
                    help="prompt file from tools/build_prompts.py")
    ap.add_argument("--out", type=Path, required=True,
                    help="responses .jsonl; appended to, and resumed from")
    ap.add_argument("--adapter", type=Path,
                    help="PEFT LoRA directory; omit for the base model")
    ap.add_argument("--max-new-tokens", type=int, default=3072)
    ap.add_argument("--max-seq-length", type=int,
                    help="default: longest prompt_tokens in --prompts + --max-new-tokens")
    ap.add_argument("--repetition-penalty", type=float, default=1.0,
                    help="1.0 = pure greedy (default); Qwen2.5's shipped value is 1.05")
    ap.add_argument("--limit", type=int, help="first N items only (smoke test)")
    args = ap.parse_args()
    # In the flat Kaggle bundle this script sits beside schema.py, verify.py,
    # scope.py ...; none of them is needed here, and on sys.path[0] they could
    # shadow a same-named package a library imports.
    sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != HERE]

    rows = load_prompts(args.prompts)
    need = max(r["prompt_tokens"] for r in rows) + args.max_new_tokens
    max_seq = args.max_seq_length or need
    if max_seq < need:
        sys.exit(f"--max-seq-length {max_seq} < longest prompt + max_new_tokens = {need}")
    todo_rows = rows[:args.limit] if args.limit else rows
    by_id = {r["item_id"]: r for r in rows}
    done = load_done(args.out, by_id)
    todo = [r for r in todo_rows if r["item_id"] not in done]

    adapter_file = None
    if args.adapter:
        adapter_file = args.adapter / "adapter_model.safetensors"
        if not adapter_file.exists():
            sys.exit(f"{adapter_file} not found")
        cfg = json.loads((args.adapter / "adapter_config.json").read_text(encoding="utf-8"))
        if cfg.get("base_model_name_or_path") != BASE_MODEL:
            sys.exit(f"adapter base {cfg.get('base_model_name_or_path')!r} != {BASE_MODEL!r}")

    # Heavy imports only past argument handling, so --help needs no GPU stack.
    # unsloth first: it patches transformers and peft on import.
    from unsloth import FastLanguageModel
    import torch

    gen_kwargs = {"max_new_tokens": args.max_new_tokens, "do_sample": False,
                  "num_beams": 1, "repetition_penalty": args.repetition_penalty,
                  "temperature": None, "top_p": None, "top_k": None,
                  "use_cache": True}
    manifest = {
        "base_model": BASE_MODEL,
        "args": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
        "max_new_tokens": args.max_new_tokens,
        "max_seq_length": max_seq,
        "generate_kwargs": gen_kwargs,
        "batch_size": 1,
        "prompts_sha256": sha256_file(args.prompts),
        "n_prompts": len(rows),
        "adapter_sha256": sha256_file(adapter_file) if adapter_file else None,
    }
    session = {"started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
               "versions": versions(), "already_done": len(done), "limit": args.limit}
    manifest_path = args.out.with_name(args.out.name + ".manifest.json")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_manifest(manifest_path, manifest, session)
    print(f"manifest -> {manifest_path}")
    print(f"{len(todo_rows)} items, {len(done)} already in {args.out}, {len(todo)} to generate")
    if not todo:
        return

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL, max_seq_length=max_seq, dtype=None, load_in_4bit=True)
    if args.adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, str(args.adapter))
        n_b, s_b = lora_b_abs_sum(model)
        print(f"adapter {args.adapter}: {n_b} lora_B tensors, sum |lora_B| = {s_b:.6g}")
        if n_b == 0 or s_b == 0.0:
            sys.exit("lora_B is all zero -- the adapter did not load; aborting")
    FastLanguageModel.for_inference(model)
    eos = model.generation_config.eos_token_id
    if eos is None:
        eos = tokenizer.eos_token_id
    eos_ids = set(eos if isinstance(eos, list) else [eos])
    pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else min(eos_ids)

    t0 = time.time()
    n_mismatch = n_err = n_limit = 0
    with open(args.out, "a", encoding="utf-8", newline="\n") as fh:
        for k, p in enumerate(todo, 1):
            row = {"item_id": p["item_id"], "raw_response": None,
                   "prompt_tokens": p["prompt_tokens"], "output_tokens": None,
                   "hit_limit": None, "prompt_sha256": p["prompt_sha256"]}
            try:
                text = tokenizer.apply_chat_template(
                    [{"role": "system", "content": p["system"]},
                     {"role": "user", "content": p["user"]}],
                    tokenize=False, add_generation_prompt=True)
                enc = tokenizer(text, return_tensors="pt", add_special_tokens=False).to(model.device)
                n_in = int(enc["input_ids"].shape[1])
                if n_in != p["prompt_tokens"]:
                    n_mismatch += 1
                    if n_mismatch == 1:
                        print(f"WARNING {p['item_id']}: {n_in} prompt tokens here, "
                              f"{p['prompt_tokens']} in the prompt file")
                row["prompt_tokens"] = n_in
                with torch.inference_mode():
                    out = model.generate(**enc, pad_token_id=pad_id, **gen_kwargs)
                gen = out[0, n_in:]
                row["raw_response"] = tokenizer.decode(gen, skip_special_tokens=True)
                row["output_tokens"] = int(gen.shape[0])
                row["hit_limit"] = int(gen[-1]) not in eos_ids if len(gen) else False
                n_limit += row["hit_limit"]
            except Exception as e:  # one bad item must not end the run
                row["raw_response"] = f"__ERROR__: {type(e).__name__}: {e}"
                n_err += 1
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

            if k % PROGRESS_EVERY == 0 or k == len(todo):
                mins = (time.time() - t0) / 60
                eta = mins / k * (len(todo) - k)
                print(f"{len(done) + k}/{len(todo_rows)}  {mins:.1f} min  ETA {eta:.1f} min"
                      f"  (hit_limit {n_limit}, errors {n_err})", flush=True)

    print(f"done: {len(todo)} generated, {n_limit} hit_limit, {n_err} errors, "
          f"{n_mismatch} prompt-token mismatches -> {args.out}")


if __name__ == "__main__":
    main()
