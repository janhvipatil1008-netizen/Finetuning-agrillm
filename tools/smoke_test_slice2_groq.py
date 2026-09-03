"""smoke_test_slice2_groq.py -- Phase 8: 20-row live smoke test of
GroqBackend (tools/generate_sft.py) against Slice 2 (PEST_UNKNOWN clarify)
before committing to the full ~4,069-row run.

20 rows selected from kcc_tagged where slice==2 AND the item builds as
Kind.CLARIFY (excludes the OFFTOPIC pre-filter sub-case and anything
banned_chemical_query -- those never reach slice 2 to begin with, since
assign_slices() is E-first: banned takes slice 3 regardless). Stratified
across crop_slug via round-robin so no single crop dominates a 20-row
sample; seed=42 for reproducible selection.

One request per row, single attempt (no retries -- this is a diagnostic
read on the raw model, not the full accept/retry/reject pipeline), timed
individually so the per-call wall clock (including GroqBackend's own
rate-limit pacing sleep, since the timer wraps the whole backend.generate
call) can project the full run's duration.

Does NOT touch data/final. Outputs go to data/scratch/groq_smoke/.
"""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
sys.path.insert(0, str(REPO_ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

import generate_sft as G

N = 20
SEED = 42
OUT_DIR = REPO_ROOT / "data" / "scratch" / "groq_smoke"
FULL_SLICE2_ROWS = 4069  # raw partition count printed by generate_sft.py step [1/6]


def select_rows(resources, table) -> list[G.GenItem]:
    kcc = G.load_kcc()
    kcc = G.assign_slices(kcc)
    train_df, test_df, _dropped = G.split_kcc(kcc)
    all_df = pd.concat([train_df, test_df])

    candidates: list[G.GenItem] = []
    for _, row in all_df[all_df["slice"] == 2].iterrows():
        item, _ = G.build_item_for_row(row, "train", resources, table)
        if item is not None and item.kind == G.Kind.CLARIFY:
            candidates.append(item)

    by_crop: dict[str, list[G.GenItem]] = {}
    for it in candidates:
        by_crop.setdefault(it.crop_slug, []).append(it)

    rng = random.Random(SEED)
    crops = sorted(by_crop)
    for c in crops:
        by_crop[c] = sorted(by_crop[c], key=lambda it: it.row_id)
        rng.shuffle(by_crop[c])

    selected: list[G.GenItem] = []
    while len(selected) < N:
        progressed = False
        for c in crops:
            if by_crop[c]:
                selected.append(by_crop[c].pop(0))
                progressed = True
                if len(selected) == N:
                    break
        if not progressed:
            break
    return selected, len(candidates)


def main() -> None:
    print("[1/4] loading resources ...")
    resources = G.VerifyResources.load()
    table = resources.table

    print(f"[2/4] selecting {N} slice-2 CLARIFY rows (seed={SEED}), stratified by crop ...")
    items, pool_size = select_rows(resources, table)
    crops_hit = sorted({it.crop_slug for it in items})
    print(f"  selected {len(items)} of {pool_size} candidate rows, "
          f"crops represented ({len(crops_hit)}): {crops_hit}")
    if len(items) < N:
        print(f"  WARNING: only found {len(items)}/{N} buildable slice-2 CLARIFY rows")
    if len(crops_hit) < 4:
        print(f"  WARNING: only {len(crops_hit)} crops represented, brief asked for >=4")

    print(f"[3/4] running {len(items)} sequential live Groq calls "
          f"(model={G.GROQ_DEFAULT_MODEL}, ~2s/call pacing) ...")
    backend = G.GroqBackend(model=G.GROQ_DEFAULT_MODEL)

    rows_report = []
    call_times: list[float] = []
    n_accepted = n_excluded = n_rejected = 0
    gate_fail_counts: dict[str, int] = {}
    boilerplate_flags: list[dict] = []

    for i, item in enumerate(items):
        req = G.BatchRequest(custom_id=f"{item.key()}_r0", system=G.SYSTEM_MESSAGE,
                              user=G.build_user_message(item), max_tokens=2000)
        t0 = time.perf_counter()
        responses = backend.generate([req], {item.key(): item})
        elapsed = time.perf_counter() - t0
        call_times.append(elapsed)
        resp = responses.get(req.custom_id)

        entry = {"row_id": item.row_id, "crop_slug": item.crop_slug,
                 "query_text": item.query_text, "elapsed_s": round(elapsed, 2),
                 "raw_response": resp}

        if resp is None:
            entry["verdict"] = "rejected"
            entry["reason"] = "no response from Groq API (see error printed above)"
            entry["clarifying_question"] = None
            n_rejected += 1
        else:
            vr = G.verify_item(resources, item, resp)
            clarifying_question = None
            try:
                parsed = json.loads(resp)
                clarifying_question = parsed.get("clarifying_question")
            except json.JSONDecodeError:
                pass
            entry["clarifying_question"] = clarifying_question
            if vr.passed:
                entry["verdict"] = "accepted"
                n_accepted += 1
            elif vr.excluded:
                entry["verdict"] = "excluded"
                entry["reason"] = vr.reason
                n_excluded += 1
            else:
                entry["verdict"] = "rejected"
                entry["reason"] = "; ".join(vr.failures[:3])
                n_rejected += 1
                for f in vr.failures:
                    gate = f.split(":", 1)[0].strip()
                    gate_fail_counts[gate] = gate_fail_counts.get(gate, 0) + 1

            if clarifying_question:
                ok, msg = G._clarify_question_ok(clarifying_question)
                if not ok:
                    boilerplate_flags.append({"row_id": item.row_id,
                                               "clarifying_question": clarifying_question,
                                               "reason": msg})

        rows_report.append(entry)
        print(f"  [{i+1}/{len(items)}] S2_{item.row_id} ({item.crop_slug}) "
              f"{elapsed:.2f}s -> {entry['verdict']}")

    print("[4/4] writing report ...")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    acceptance_rate = n_accepted / len(items) if items else 0.0
    avg_call_time = sum(call_times) / len(call_times) if call_times else 0.0
    projected_full_run_s = avg_call_time * FULL_SLICE2_ROWS

    summary = {
        "n": len(items), "accepted": n_accepted, "excluded": n_excluded,
        "rejected": n_rejected, "acceptance_rate": round(acceptance_rate, 4),
        "avg_call_time_s": round(avg_call_time, 3),
        "projected_full_run_hours": round(projected_full_run_s / 3600, 2),
        "gate_fail_counts": gate_fail_counts,
        "boilerplate_clarifying_questions": boilerplate_flags,
        "crops_represented": crops_hit,
        "pool_size": pool_size,
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                            encoding="utf-8")
    (OUT_DIR / "rows.json").write_text(json.dumps(rows_report, indent=2, ensure_ascii=False),
                                         encoding="utf-8")

    print(f"\n=== AGGREGATE ===")
    print(f"accepted: {n_accepted}/{len(items)} ({100*acceptance_rate:.0f}%) "
          f"-- target >= 60%")
    print(f"excluded: {n_excluded} | rejected: {n_rejected}")
    print(f"avg call time: {avg_call_time:.2f}s")
    print(f"projected full 4,069-row run: {projected_full_run_s/3600:.2f} hours")
    if gate_fail_counts:
        print("gate failures:")
        for g, c in sorted(gate_fail_counts.items(), key=lambda x: -x[1]):
            print(f"  {g}: {c}")
    if boilerplate_flags:
        print(f"boilerplate/generic clarifying_question flagged: {len(boilerplate_flags)}")
        for b in boilerplate_flags:
            print(f"  S2_{b['row_id']}: {b['clarifying_question']!r} -- {b['reason']}")
    else:
        print("no boilerplate clarifying_question detected")

    if acceptance_rate < 0.60:
        print("\n*** ACCEPTANCE RATE < 60% -- STOP per the brief. Do not start the full run. ***")
    else:
        print("\nAcceptance rate >= 60%. STOPPING per the brief -- full run NOT started.")

    print(f"\nWrote {OUT_DIR / 'summary.json'} and {OUT_DIR / 'rows.json'}")


if __name__ == "__main__":
    main()
