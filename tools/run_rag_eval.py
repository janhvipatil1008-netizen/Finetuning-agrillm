"""
run_rag_eval.py -- Phase 12 Step 2/2b: prepare RAG-ablation prompts.

Prompt preparation ONLY. Generation happens on Kaggle; this script never
loads a model. It does load the Qwen tokenizer, to record prompt_tokens.

Two arms over the 500 items of data/final/bench.jsonl, one variable changed
versus the SFT run -- label_db rows injected into the user message:

  --arm A  oracle retrieval. Key = the bench item's own crop_slug and
           canonical_pest. Upper bound: the pest-specific row set leaks the
           pest identity even though the pest name is never shown.
  --arm B  live retrieval. Key = retrieval.resolve_key(query_text,
           resources, crop_hint=None) -- crop and pest from the query alone.

Both arms: method = extract_method(query_text) (Arm A via resolve_key with
crop_hint, which is exactly the generator's method source), resolved_pest
is None, and the system prompt is the frozen src/system_prompt.txt
(generate_sft.DEPLOYMENT_SYSTEM_PROMPT), unchanged -- freeze_check runs
first and aborts on drift. See src/retrieval.py's docstring for the two
confounds neither arm removes (oracle vs live keying; input-shape novelty)
and for the two miss-line wordings.

RECORD FIELDS
=============

  item_id, arm, crop_slug_used, canonical_pest_used, method_used
  n_rows_retrieved / fact_sheet_rows   same number; fact_sheet_rows is the
                                       name scoring buckets on
  fact_sheet_bucket   "0" | "1-5" | "6-15" | "16-40" | "41+"
  fact_sheet_kind     rows | no_rows (CIB&RC line) | unresolved (could-not-
                      identify line) -- which <fact_sheet> body was emitted
  retrieval_status    see below
  prompt_tokens       system + user through the Qwen chat template, with
                      the generation prompt appended; None only under
                      --no-tokenizer
  known_bench_defect  note string for the bench items whose gold crop_slug
                      contradicts the query text, else None
  user_message

retrieval_status, first match wins:
  no_crop             no crop to key on (Arm B: query names 0 or >1 crops)
  crop_mismatch       Arm B only: resolved crop != bench crop_slug. Retrieval
                      still runs on the resolved crop -- that is what a live
                      system would do.
  no_pest             crop known, pest None (CLARIFY/OFFTOPIC gold, or an
                      Arm B resolution miss)
  resolved_with_rows  key resolved, >=1 row survived the filter chain
  resolved_no_rows    key resolved, nothing survived

Outputs data/interim/rag_prompts_{A,B}.jsonl.

Usage:
  python tools/run_rag_eval.py                 # both arms
  python tools/run_rag_eval.py --arm B --examples 3
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from freeze_check import assert_frozen  # noqa: E402
from retrieval import (  # noqa: E402
    MISS_NO_ROWS,
    MISS_UNRESOLVED,
    build_rag_user_message,
    format_fact_sheet,
    miss_reason_for,
    resolve_key,
    retrieve_rows,
)
from verify import VerifyResources  # noqa: E402

BENCH_PATH = REPO_ROOT / "data" / "final" / "bench.jsonl"
SYSTEM_PROMPT_PATH = REPO_ROOT / "src" / "system_prompt.txt"
OUT_DIR = REPO_ROOT / "data" / "interim"
TOKENIZER_ID = "Qwen/Qwen2.5-7B-Instruct"  # base of unsloth/Qwen2.5-7B-Instruct-bnb-4bit
TOKEN_FLAG = 3000
DOSE_KINDS = {"DOSE", "REFUSAL_DOSE"}
STATUSES = ["resolved_with_rows", "resolved_no_rows", "no_crop", "no_pest", "crop_mismatch"]
BUCKETS = [("0", 0, 0), ("1-5", 1, 5), ("6-15", 6, 15), ("16-40", 16, 40), ("41+", 41, None)]

# Bench items whose gold crop_slug contradicts the crop the query names.
# bench.jsonl is NOT edited (Phase 12 Step 2b decision): they stay as-is and
# are tagged here so scoring can report them. Arm B resolves the crop the
# query actually names, disagrees with the wrong gold, and is penalised for
# being right; Arm A retrieves chemistry for a crop the farmer never asked
# about.
KNOWN_BENCH_DEFECTS = {
    "S1_1856": "gold crop tomato; query names bengal gram",
    "S1_623": "gold crop onion; query names cotton",
}

__all__ = ["build_records", "bucket_for", "main"]


def load_bench(path: Path = BENCH_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def bucket_for(n_rows: int) -> str:
    for label, lo, hi in BUCKETS:
        if n_rows >= lo and (hi is None or n_rows <= hi):
            return label
    raise ValueError(n_rows)


def _status(arm: str, crop: Optional[str], pest: Optional[str], n_rows: int,
            bench_crop: Optional[str]) -> str:
    if not crop:
        return "no_crop"
    if arm == "B" and crop != bench_crop:
        return "crop_mismatch"
    if not pest:
        return "no_pest"
    return "resolved_with_rows" if n_rows else "resolved_no_rows"


def prompt_tokens(tok, system_prompt: str, user_message: str) -> Optional[int]:
    if tok is None:
        return None
    # tokenize=False then encode: with tokenize=True, transformers 5 returns
    # a BatchEncoding dict, whose len() is its key count, not a token count.
    text = tok.apply_chat_template(
        [{"role": "system", "content": system_prompt},
         {"role": "user", "content": user_message}],
        tokenize=False, add_generation_prompt=True)
    return len(tok.encode(text, add_special_tokens=False))


def build_record(item: dict, arm: str, resources: VerifyResources,
                 tok=None, system_prompt: str = "") -> dict:
    q = item["query_text"]
    if arm == "A":
        # crop_hint makes resolve_key return the gold crop and extract_method(q);
        # its pest guess is discarded in favour of the gold canonical.
        crop, _live_pest, method = resolve_key(q, resources, crop_hint=item["crop_slug"])
        pest = item.get("canonical_pest") or None
    else:
        crop, pest, method = resolve_key(q, resources, crop_hint=None)
    rows = retrieve_rows(crop, pest, resources, method)
    miss = miss_reason_for(crop, pest)
    msg = build_rag_user_message(q, crop, rows, resolved_pest=None, miss_reason=miss)
    return {
        "item_id": item["item_id"],
        "arm": arm,
        "crop_slug_used": crop,
        "canonical_pest_used": pest,
        "method_used": method,
        "n_rows_retrieved": len(rows),
        "fact_sheet_rows": len(rows),
        "fact_sheet_bucket": bucket_for(len(rows)),
        "fact_sheet_kind": "rows" if rows else miss,
        "retrieval_status": _status(arm, crop, pest, len(rows), item.get("crop_slug")),
        "prompt_tokens": prompt_tokens(tok, system_prompt, msg),
        "known_bench_defect": KNOWN_BENCH_DEFECTS.get(item["item_id"]),
        "user_message": msg,
    }


def build_records(bench: list[dict], arm: str, resources: VerifyResources,
                  tok=None, system_prompt: str = "") -> list[dict]:
    return [build_record(it, arm, resources, tok, system_prompt) for it in bench]


def write_jsonl(path: Path, records: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------
# checks and reporting
# --------------------------------------------------------------------------

_FACT_RX = re.compile(r"<fact_sheet>\n.*?\n</fact_sheet>", re.S)
DRY_RUN_IDS = ["S1_140", "S1_604", "S1_512", "S1_1261", "S1_1827"]  # Step 2's five


def dry_run_check(records_a: list[dict], bench_by_id: dict, resources: VerifyResources,
                  ids: list[str] = DRY_RUN_IDS) -> list[str]:
    """For each id, the emitted <fact_sheet> must equal a fresh
    format_fact_sheet(retrieve_rows(gold key)). Raises on mismatch."""
    by_id = {r["item_id"]: r for r in records_a}
    for iid in ids:
        r, b = by_id[iid], bench_by_id[iid]
        assert r["fact_sheet_rows"] > 0, f"{iid}: dry-run item has no rows"
        expected = format_fact_sheet(retrieve_rows(
            b["crop_slug"], b["canonical_pest"], resources, r["method_used"]))
        m = _FACT_RX.search(r["user_message"])
        assert m is not None, f"{iid}: no <fact_sheet> block"
        assert m.group(0) == expected, f"{iid}: fact sheet differs from gold retrieval"
    return ids


def load_tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(TOKENIZER_ID)


def _dist(xs: list[int]) -> str:
    return f"n={len(xs):3d}  min={min(xs):5d}  median={statistics.median(xs):7g}  max={max(xs):5d}"


def report(arm: str, records: list[dict], bench_by_id: dict, n_examples: int) -> None:
    dose = [r for r in records if bench_by_id[r["item_id"]]["kind"] in DOSE_KINDS]
    print(f"\n{'=' * 72}\nARM {arm}  ({len(records)} items, {len(dose)} DOSE/REFUSAL_DOSE)\n{'=' * 72}")
    for label, rs in (("all", records), ("DOSE/REFUSAL_DOSE", dose)):
        c = Counter(r["retrieval_status"] for r in rs)
        print(f"retrieval_status [{label}]: " + ", ".join(f"{s}={c.get(s, 0)}" for s in STATUSES))
        k = Counter(r["fact_sheet_kind"] for r in rs)
        print(f"fact_sheet_kind  [{label}]: rows={k.get('rows', 0)}, "
              f"{MISS_NO_ROWS}(CIB&RC line)={k.get(MISS_NO_ROWS, 0)}, "
              f"{MISS_UNRESOLVED}(could-not-identify line)={k.get(MISS_UNRESOLVED, 0)}")
        kinds = defaultdict(Counter)
        for r in rs:
            if r["fact_sheet_kind"] != "rows":
                kinds[r["fact_sheet_kind"]][bench_by_id[r["item_id"]]["kind"]] += 1
        for fk, c2 in sorted(kinds.items()):
            print(f"    {fk:10s} by bench kind: {dict(sorted(c2.items()))}")

    if arm == "B":
        print("\ncrop_mismatch items:")
        for r in records:
            if r["retrieval_status"] == "crop_mismatch":
                b = bench_by_id[r["item_id"]]
                tag = f"  ** KNOWN BENCH DEFECT: {r['known_bench_defect']}" if r["known_bench_defect"] else ""
                print(f"  {r['item_id']} [{b['kind']}] gold=({b['crop_slug']}, {b['canonical_pest']}) "
                      f"live=({r['crop_slug_used']}, {r['canonical_pest_used']}) "
                      f"rows={r['fact_sheet_rows']}{tag}\n    {b['query_text']!r}")

    toks = [r["prompt_tokens"] for r in records]
    if None in toks:
        print("\nprompt_tokens not computed (--no-tokenizer)")
    else:
        print("\nprompt_tokens by fact_sheet_bucket (system+user, Qwen chat template):")
        for label, _lo, _hi in BUCKETS:
            xs = [r["prompt_tokens"] for r in records if r["fact_sheet_bucket"] == label]
            dx = [r["prompt_tokens"] for r in dose if r["fact_sheet_bucket"] == label]
            if xs:
                print(f"  {label:>5}  all  {_dist(xs)}")
            if dx:
                print(f"  {'':>5}  DOSE {_dist(dx)}")
        for t in (TOKEN_FLAG, 4096):
            print(f"  over {t}: all={sum(x > t for x in toks)}  "
                  f"DOSE={sum(r['prompt_tokens'] > t for r in dose)}")

    for r in _examples(records, dose)[:n_examples]:
        print(f"\n--- example {r['item_id']} [{r['fact_sheet_kind']}, "
              f"rows={r['fact_sheet_rows']}] ---\n{r['user_message']}")


def _examples(records: list[dict], dose: list[dict]) -> list[dict]:
    out = []
    with_rows = sorted((r for r in dose if r["fact_sheet_rows"]), key=lambda r: r["fact_sheet_rows"])
    if with_rows:
        out.append(with_rows[len(with_rows) // 2])
    for kind in (MISS_NO_ROWS, MISS_UNRESOLVED):
        out += [r for r in records if r["fact_sheet_kind"] == kind][:1]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--arm", choices=["A", "B", "both"], default="both")
    ap.add_argument("--examples", type=int, default=0)
    ap.add_argument("--no-tokenizer", action="store_true",
                    help="skip the Qwen tokenizer; prompt_tokens is written as null")
    args = ap.parse_args()

    assert_frozen()
    system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    resources = VerifyResources.load()
    bench = load_bench()
    bench_by_id = {b["item_id"]: b for b in bench}
    missing = set(KNOWN_BENCH_DEFECTS) - set(bench_by_id)
    assert not missing, f"KNOWN_BENCH_DEFECTS names items not in bench: {missing}"
    tok = None if args.no_tokenizer else load_tokenizer()

    arms = ["A", "B"] if args.arm == "both" else [args.arm]
    for arm in arms:
        records = build_records(bench, arm, resources, tok, system_prompt)
        out = OUT_DIR / f"rag_prompts_{arm}.jsonl"
        write_jsonl(out, records)
        print(f"wrote {out.relative_to(REPO_ROOT)} ({len(records)} records)")
        report(arm, records, bench_by_id, args.examples)
        if arm == "A":
            ids = dry_run_check(records, bench_by_id, resources)
            print(f"\ndry-run check PASSED: fact_sheet == "
                  f"format_fact_sheet(retrieve_rows(gold)) for {ids}")


if __name__ == "__main__":
    main()
