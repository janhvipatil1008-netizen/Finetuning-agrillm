"""
smoke_test_sft.py -- Phase 8 Sub-phase B3: live smoke test of generate_sft.py
against the real Anthropic Batch API. 20 hand-selected rows, one batch, all
five slice kinds plus the OFFTOPIC pre-filter represented. Do NOT run the
full dataset from this script -- see tools/generate_sft.py for that.

Composition (fixed per the B3 brief):
  8x Slice 1 (dose)      -- 2 each: cotton, tomato, soybean, gram
  4x Slice 2 (clarify)   -- PEST_UNKNOWN, not off-topic
  2x Slice 3 (refusal)   -- one ANSWERABLE sub-case, one PEST_UNKNOWN sub-case
  2x Slice 4 (grape)     -- 2 hand-written grape queries (see note below)
  2x Slice 5 (no-chem)   -- NO_REGISTERED_CHEMISTRY
  2x OFFTOPIC             -- the slice-2 off-topic pre-filter branch

Slice 4 note: the full pipeline's grape items come from a live query-writer
call (its own batch). Running that here would make this a two-batch smoke
test, contrary to "submit as a single Anthropic batch" in the brief. Instead
this script hand-writes 2 KCC-register-style grape queries against real
scope.py targets and feeds them through the same DOSE generation path --
this tests exactly what B3 cares about (does the model answer correctly from
the injected fact sheet), just not the query-writer call itself, which B1/B2
already validated against a mock.

Retries are OFF here (max_attempts=1): the brief asks for one batch, and a
retry round would be a second one. Each item's raw first-attempt response is
what gets reported.

Reads ANTHROPIC_API_KEY from agri-llm/.env via python-dotenv (never printed).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

sys.path.insert(0, str(REPO_ROOT / "tools"))
sys.path.insert(0, str(REPO_ROOT / "src"))

import generate_sft as G  # noqa: E402

REPORT_PATH = REPO_ROOT / "reports" / "phase8_stepB3_smoke_test.md"

TARGET_CROPS_SLICE1 = ["cotton", "tomato", "soybean", "gram"]
GRAPE_HAND_QUERIES = [
    ("Powdery mildew", "FARMER ASKED ABOUT WHITE POWDERY GROWTH ON GRAPE LEAVES AND BUNCHES AT BERRY STAGE"),
    ("Mealybug", "Farmer asked about mealy bug infestation on grape vine, cottony white insects on stem and bunches"),
]


def pick_slice1(train_df, resources, table) -> list[G.GenItem]:
    items = []
    for crop in TARGET_CROPS_SLICE1:
        pool = train_df[(train_df.slice == 1) & (train_df.crop_slug == crop)]
        got = 0
        for _, row in pool.iterrows():
            item, _ = G.build_item_for_row(row, "train", resources, table)
            if item is not None:
                items.append(item)
                got += 1
                if got == 2:
                    break
        if got < 2:
            print(f"  WARNING: only found {got}/2 buildable slice-1 items for {crop}")
    return items


def pick_slice2(train_df, resources, table, n=4) -> list[G.GenItem]:
    items = []
    pool = train_df[(train_df.slice == 2)]
    for _, row in pool.iterrows():
        if G.is_offtopic_query(str(row["QueryText"])):
            continue
        item, _ = G.build_item_for_row(row, "train", resources, table)
        if item is not None and item.kind == G.Kind.CLARIFY:
            items.append(item)
            if len(items) == n:
                break
    return items


def pick_offtopic(train_df, resources, table, n=2) -> list[G.GenItem]:
    items = []
    pool = train_df[(train_df.slice == 2)]
    for _, row in pool.iterrows():
        if not G.is_offtopic_query(str(row["QueryText"])):
            continue
        item, _ = G.build_item_for_row(row, "train", resources, table)
        if item is not None and item.kind == G.Kind.OFFTOPIC:
            items.append(item)
            if len(items) == n:
                break
    return items


def pick_slice3(train_df, resources, table) -> list[G.GenItem]:
    items = []
    for answ in ("ANSWERABLE", "PEST_UNKNOWN"):
        pool = train_df[(train_df.slice == 3) & (train_df.answerability == answ)]
        for _, row in pool.iterrows():
            item, _ = G.build_item_for_row(row, "train", resources, table)
            if item is not None:
                items.append(item)
                break
    return items


def pick_slice5(train_df, resources, table, n=2) -> list[G.GenItem]:
    items = []
    pool = train_df[(train_df.slice == 5)]
    for _, row in pool.iterrows():
        item, _ = G.build_item_for_row(row, "train", resources, table)
        if item is not None:
            items.append(item)
            if len(items) == n:
                break
    return items


def build_slice4(resources, table) -> list[G.GenItem]:
    items = []
    for i, (canon, query) in enumerate(GRAPE_HAND_QUERIES):
        fact_rows = G.label_db_fact_rows(resources, "grape", canon, None)
        mp = G.match_pest("grape", canon, table)
        surface = mp.matched_surface_form if mp.matched else canon
        items.append(G.GenItem(
            slice=4, kind=G.Kind.DOSE, row_id=f"smoke_grape{i}", split="train",
            crop_slug="grape", query_text=query, pest_queries=[surface],
            canonicals=[canon], application_method=None, gold_escalate=None,
            fact_rows=fact_rows))
    return items


def check_fact_sheet_fidelity(item: G.GenItem, advisory) -> tuple[bool, list[str]]:
    """For dose-like items: did every recommended a.i. come from the fact sheet?"""
    if not item.fact_rows:
        return True, []
    fact_ais = {r["ai"] for r in item.fact_rows}
    problems = []
    for opt in advisory.chemical_options:
        if opt.active_ingredient not in fact_ais:
            problems.append(f"{opt.active_ingredient!r} not found verbatim in the "
                             f"{len(fact_ais)}-row fact sheet")
    return (len(problems) == 0), problems


def main() -> None:
    print("[1/5] loading resources ...")
    resources = G.VerifyResources.load()
    table = resources.table

    kcc = G.load_kcc()
    kcc = G.assign_slices(kcc)
    train_df, test_df, _dropped = G.split_kcc(kcc)

    print("[2/5] selecting 20 items ...")
    items: list[G.GenItem] = []
    items += pick_slice1(train_df, resources, table)
    items += pick_slice2(train_df, resources, table, n=4)
    items += pick_slice3(train_df, resources, table)
    items += build_slice4(resources, table)
    items += pick_slice5(train_df, resources, table, n=2)
    items += pick_offtopic(train_df, resources, table, n=2)

    by_slice: dict[int, int] = {}
    for it in items:
        by_slice[it.slice] = by_slice.get(it.slice, 0) + 1
    print(f"  selected {len(items)} items: {dict(sorted(by_slice.items()))}")
    if len(items) != 20:
        print(f"  WARNING: expected 20, got {len(items)} -- see per-slice warnings above")

    print("[3/5] submitting ONE Anthropic batch (claude-sonnet-4-6, no retries) ...")
    requests = [G.BatchRequest(custom_id=f"{it.key()}_r0", system=G.SYSTEM_MESSAGE,
                                user=G.build_user_message(it), max_tokens=2000)
                for it in items]
    backend = G.AnthropicBatchBackend(model=G.GENERATOR_MODEL, structured_output=False)
    responses = backend.generate(requests, None)
    print(f"  batch complete, {len(responses)} responses received")

    print("[4/5] verifying each response ...")
    rows_report = []
    n_accepted = 0
    gate_fail_counts: dict[str, int] = {}
    for it, req in zip(items, requests):
        resp = responses.get(req.custom_id)
        entry = {"item": it, "raw_response": resp}
        if resp is None:
            entry["verdict"] = "rejected: no response from API"
            entry["vr"] = None
            entry["fidelity_ok"] = None
            entry["fidelity_problems"] = []
        else:
            vr = G.verify_item(resources, it, resp)
            entry["vr"] = vr
            fidelity_ok, fidelity_problems = (None, [])
            if it.kind in G.DOSE_LIKE and vr.json_text is not None:
                adv = G.Advisory.model_validate_json(vr.json_text)
                fidelity_ok, fidelity_problems = check_fact_sheet_fidelity(it, adv)
            entry["fidelity_ok"] = fidelity_ok
            entry["fidelity_problems"] = fidelity_problems
            if vr.passed:
                entry["verdict"] = "accepted"
                n_accepted += 1
            elif vr.excluded:
                entry["verdict"] = f"excluded: {vr.reason}"
            else:
                entry["verdict"] = f"rejected: {'; '.join(vr.failures[:3])}"
                for f in vr.failures:
                    gate = f.split(":", 1)[0].strip()
                    gate_fail_counts[gate] = gate_fail_counts.get(gate, 0) + 1
        rows_report.append(entry)

    print("[5/5] writing report ...")
    lines = ["# Phase 8 Sub-phase B3 -- live smoke test\n",
             f"Model: `{G.GENERATOR_MODEL}` via Anthropic Batch API, single batch, "
             f"no retries (max_attempts=1). 20 items across all 5 slices plus OFFTOPIC.\n"]

    for entry in rows_report:
        it: G.GenItem = entry["item"]
        lines.append(f"\n## {it.key()} -- slice {it.slice} ({it.kind}) -- {it.crop_slug}\n")
        lines.append(f"Query: `{it.query_text}`\n")
        lines.append(f"Verdict: **{entry['verdict']}**\n")
        vr = entry["vr"]
        if vr is not None:
            lines.append(f"verify() score: {vr.score} | passed: {vr.passed} | "
                          f"excluded: {vr.excluded}\n")
            if vr.failures:
                lines.append("Failures:\n")
                for f in vr.failures:
                    lines.append(f"- {f}\n")
        if it.kind in G.DOSE_LIKE:
            lines.append(f"Fact-sheet fidelity: {entry['fidelity_ok']}")
            if entry["fidelity_problems"]:
                lines.append(" -- " + "; ".join(entry["fidelity_problems"]))
            lines.append("\n")
        lines.append("\nRaw response:\n```json\n")
        lines.append(entry["raw_response"] if entry["raw_response"] is not None else "null")
        lines.append("\n```\n")

    lines.append("\n## Aggregate\n")
    lines.append(f"- Accepted: {n_accepted} / {len(items)} ({100*n_accepted/len(items):.0f}%)\n")
    s1_items = [(e, e["item"]) for e in rows_report if e["item"].slice == 1]
    s1_accepted = sum(1 for e, _ in s1_items if e["verdict"] == "accepted")
    lines.append(f"- Slice 1 acceptance: {s1_accepted} / {len(s1_items)} "
                 f"({100*s1_accepted/max(1,len(s1_items)):.0f}%)\n")
    lines.append("- Gate/check failures by name:\n")
    for gate, n in sorted(gate_fail_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  - {gate}: {n}\n")

    report_text = "".join(lines)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    print(f"\nWrote {REPORT_PATH}")
    print(f"\nAccepted: {n_accepted}/{len(items)} | Slice 1: {s1_accepted}/{len(s1_items)}")
    if len(s1_items) and s1_accepted / len(s1_items) < 0.70:
        print("\n*** SLICE 1 ACCEPTANCE < 70% -- STOP per the B3 brief. See report. ***")


if __name__ == "__main__":
    main()
