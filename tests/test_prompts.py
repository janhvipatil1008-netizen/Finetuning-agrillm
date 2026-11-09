"""Pins for the Phase 14 generation inputs: the two system prompts, the R2/R4
prompt files from tools/build_prompts.py, and tools/generate.py's CLI.

R2 (base arm) and R4 (SFT arm) must differ ONLY in the system prompt: same
500 items in bench.jsonl order, byte-identical user messages, and R4's user
messages are Phase 12 Arm B's (data/interim/rag_prompts_B.jsonl) verbatim.
rag_prompts_B.jsonl is gitignored (data/interim/), so the comparisons that
need it skip when it is absent rather than fail.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
PROMPTS = REPO / "data" / "final" / "prompts"
BENCH = REPO / "data" / "final" / "bench.jsonl"
RAG_B = REPO / "data" / "interim" / "rag_prompts_B.jsonl"

SYSTEM_PROMPT_SHA256 = "8b0a4b78c02a8c0286d3ee82acc7d47b73c4cb903a0c62b5f6fc1c1ca352b4a1"
SYSTEM_PROMPT_BASE_SHA256 = "6d747f36b31f0a3a56de643ec5e9d113eb7b26fb929a7e7342cfc9f97ef8651b"
SYSTEMS = {"R4": "system_prompt.txt", "R2": "system_prompt_base.txt"}

# generate.py's --max-new-tokens default, and the max_seq_length above which
# Phase 12 hit CUDA OOM on a T4.
MAX_NEW_TOKENS = 3072
SEQ_CEILING = 7168


def _jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.fixture(scope="module")
def arms() -> dict[str, list[dict]]:
    return {arm: _jsonl(PROMPTS / f"prompts_{arm}.jsonl") for arm in SYSTEMS}


@pytest.fixture(scope="module")
def bench_order() -> list[str]:
    return [r["item_id"] for r in _jsonl(BENCH)]


@pytest.fixture(scope="module")
def rag_b() -> list[dict]:
    if not RAG_B.exists():
        pytest.skip("rag_prompts_B.jsonl not built (data/interim/ is gitignored)")
    return _jsonl(RAG_B)


# --------------------------------------------------------------------------
# system prompts
# --------------------------------------------------------------------------

def test_system_prompt_hash_unchanged():
    assert hashlib.sha256((SRC / "system_prompt.txt").read_bytes()).hexdigest() \
        == SYSTEM_PROMPT_SHA256


def test_system_prompt_base_hash():
    assert hashlib.sha256((SRC / "system_prompt_base.txt").read_bytes()).hexdigest() \
        == SYSTEM_PROMPT_BASE_SHA256


def test_system_prompt_base_is_its_composition():
    """system_prompt.txt + blank line + generate_sft's OUTPUT_CONTRACT_TEXT,
    the runtime value (its source uses backslash line continuations)."""
    tools = str(REPO / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    contract = importlib.import_module("generate_sft").OUTPUT_CONTRACT_TEXT
    assert (SRC / "system_prompt_base.txt").read_bytes() == \
        (SRC / "system_prompt.txt").read_bytes() + b"\n\n" + contract.encode("utf-8")


# --------------------------------------------------------------------------
# prompt files
# --------------------------------------------------------------------------

@pytest.mark.parametrize("arm", list(SYSTEMS))
def test_prompt_file_rows_and_order(arms, bench_order, arm):
    rows = arms[arm]
    assert len(rows) == 500
    assert [r["item_id"] for r in rows] == bench_order
    assert all(set(r) == {"item_id", "system", "user", "prompt_sha256", "prompt_tokens"}
               for r in rows)


@pytest.mark.parametrize("arm", list(SYSTEMS))
def test_prompt_file_system_and_hash(arms, arm):
    system = (SRC / SYSTEMS[arm]).read_text(encoding="utf-8")
    for r in arms[arm]:
        assert r["system"] == system, r["item_id"]
        assert r["prompt_sha256"] == hashlib.sha256(
            (r["system"] + r["user"]).encode("utf-8")).hexdigest(), r["item_id"]


def test_r2_r4_user_messages_identical(arms):
    assert [r["user"] for r in arms["R2"]] == [r["user"] for r in arms["R4"]]


def test_r4_is_rag_prompts_b(arms, rag_b):
    assert [r["item_id"] for r in arms["R4"]] == [b["item_id"] for b in rag_b]
    assert [r["user"] for r in arms["R4"]] == [b["user_message"] for b in rag_b]
    # Same system + user through the same counter.
    assert [r["prompt_tokens"] for r in arms["R4"]] == [b["prompt_tokens"] for b in rag_b]


@pytest.mark.parametrize("arm", list(SYSTEMS))
def test_token_budget_under_ceiling(arms, arm):
    assert max(r["prompt_tokens"] for r in arms[arm]) + MAX_NEW_TOKENS <= SEQ_CEILING


# --------------------------------------------------------------------------
# generate.py
# --------------------------------------------------------------------------

def test_generate_help_runs_without_gpu_stack():
    """--help must work with no unsloth/torch import: the heavy imports sit
    past argument parsing."""
    r = subprocess.run([sys.executable, str(REPO / "tools" / "generate.py"), "--help"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    for flag in ("--prompts", "--out", "--adapter", "--max-new-tokens",
                 "--max-seq-length", "--limit"):
        assert flag in r.stdout
