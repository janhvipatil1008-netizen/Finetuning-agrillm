"""build_prompts.py -- Phase 14 Step 2: the R2 / R4 generation prompt files.

Writes, under data/final/prompts/:

  prompts_R4.jsonl   SFT arm.  system = src/system_prompt.txt (frozen), the
                     prompt the adapter was trained under.
  prompts_R2.jsonl   base arm. system = src/system_prompt_base.txt, which is
                     system_prompt.txt + "\\n\\n" + generate_sft's
                     OUTPUT_CONTRACT_TEXT: the untrained model has never seen
                     the Advisory schema, so it is shown the same contract the
                     SFT data was generated against (and nothing generator-only
                     -- no slices, no <resolved_pest>, no acceptance rules).

Both arms take the user message VERBATIM from data/interim/rag_prompts_B.jsonl
(Phase 12 live retrieval, 15-row cap), so the system prompt is the only
variable between them.

Each row: item_id, system, user, prompt_sha256 (sha256 of system + user, UTF-8,
no separator), prompt_tokens (system + user through the Qwen2.5-7B-Instruct
chat template with the generation prompt appended -- run_rag_eval's own
counter, so R4's counts must equal rag_prompts_B's and are asserted to).

READ ONLY on everything but the two outputs. Asserts before writing: the
freeze holds, system_prompt_base.txt is exactly its stated composition, 500
rows per file in bench.jsonl order, R4 user messages byte-identical to
rag_prompts_B, R2 and R4 user messages identical to each other.

Usage:
    python tools/build_prompts.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from freeze_check import assert_frozen  # noqa: E402
from generate_sft import OUTPUT_CONTRACT_TEXT  # noqa: E402
from run_rag_eval import load_tokenizer, prompt_tokens, write_jsonl  # noqa: E402

BENCH = ROOT / "data" / "final" / "bench.jsonl"
RAG_B = ROOT / "data" / "interim" / "rag_prompts_B.jsonl"
SYSTEM_PROMPT = ROOT / "src" / "system_prompt.txt"
SYSTEM_PROMPT_BASE = ROOT / "src" / "system_prompt_base.txt"
OUT_DIR = ROOT / "data" / "final" / "prompts"

# Token budget (Phase 14 Step 2 Task C). generate.py's --max-new-tokens
# default; max_seq_length must cover the longest prompt plus this. Phase 12
# hit CUDA OOM on a T4 at ~12k tokens, hence the ceiling.
MAX_NEW_TOKENS = 3072
SEQ_CEILING = 7168

ARMS = {"R4": SYSTEM_PROMPT, "R2": SYSTEM_PROMPT_BASE}


def prompt_sha256(system: str, user: str) -> str:
    return hashlib.sha256((system + user).encode("utf-8")).hexdigest()


def jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def build(arm: str, users: list[tuple[str, str]], tok) -> list[dict]:
    system = ARMS[arm].read_text(encoding="utf-8")
    return [{"item_id": iid, "system": system, "user": user,
             "prompt_sha256": prompt_sha256(system, user),
             "prompt_tokens": prompt_tokens(tok, system, user)}
            for iid, user in users]


def main() -> None:
    assert_frozen()
    base = SYSTEM_PROMPT_BASE.read_bytes()
    assert base == SYSTEM_PROMPT.read_bytes() + b"\n\n" + OUTPUT_CONTRACT_TEXT.encode("utf-8"), \
        "system_prompt_base.txt is not system_prompt.txt + '\\n\\n' + OUTPUT_CONTRACT_TEXT"

    order = [r["item_id"] for r in jsonl(BENCH)]
    rag_b = jsonl(RAG_B)
    assert [r["item_id"] for r in rag_b] == order, "rag_prompts_B order != bench order"
    users = [(r["item_id"], r["user_message"]) for r in rag_b]

    tok = load_tokenizer()
    out = {arm: build(arm, users, tok) for arm in ARMS}

    for arm, rows in out.items():
        assert len(rows) == len(order) == 500, (arm, len(rows))
        assert [r["item_id"] for r in rows] == order, f"{arm} order != bench order"
    assert all(r["user"] == b["user_message"] for r, b in zip(out["R4"], rag_b)), \
        "R4 user != rag_prompts_B user_message"
    assert [r["user"] for r in out["R2"]] == [r["user"] for r in out["R4"]], "R2 user != R4 user"
    # Same system + user, same counter: a mismatch means the tokenizer moved.
    assert [r["prompt_tokens"] for r in out["R4"]] == [b["prompt_tokens"] for b in rag_b], \
        "R4 prompt_tokens != rag_prompts_B prompt_tokens"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for arm, rows in out.items():
        path = OUT_DIR / f"prompts_{arm}.jsonl"
        write_jsonl(path, rows)
        toks = [r["prompt_tokens"] for r in rows]
        need = max(toks) + MAX_NEW_TOKENS
        print(f"{path.relative_to(ROOT).as_posix()}: {len(rows)} rows, "
              f"{path.stat().st_size:,} bytes, sha256 "
              f"{hashlib.sha256(path.read_bytes()).hexdigest()}")
        print(f"  prompt_tokens max {max(toks)}  mean {sum(toks) / len(toks):.1f}")
        print(f"  max_seq_length needed = {max(toks)} + {MAX_NEW_TOKENS} = {need}"
              f"  ({'OK' if need <= SEQ_CEILING else 'OVER'} vs ceiling {SEQ_CEILING})")


if __name__ == "__main__":
    main()
