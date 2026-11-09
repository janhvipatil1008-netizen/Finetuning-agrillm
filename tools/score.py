"""score.py — one scoring CLI for every benchmark run (Phase 14 Step 1).

Scores a responses file -- one {"item_id", "raw_response"} per line, the
shape the Kaggle generation cell writes -- against data/final/bench.jsonl and
writes data/final/eval/scores_<label>.json.

READ ONLY on everything but that output. The scoring convention is
phase10_stepB_audit's ctx_for / rescore, IMPORTED rather than copied so the
two cannot drift: gold_escalate from the bench item's frozen gold advisory,
application_method left None, verify(..., "score") against the shipped ban
list (p10.load_verify).

What is counted (the Phase 14 convention):

  items     every bench item except run_rag_eval.KNOWN_BENCH_DEFECTS, the two
            whose gold crop contradicts the query: 498. Nothing else is
            removed up front.
  missing   an item the responses file has no line for scores 0.0 and stays
            in the mean. A dropped generation is a failure of the run, not a
            gap in the benchmark.
  excluded  an item verify() excludes (documented CIB&RC contradiction,
            damaged label_db fragment, every row defective) leaves the mean
            and is listed with its exclusion_reason -- reported, never
            silently dropped. Its score is written as null: the total
            verify() returns for an excluded item is not a grade.

  mean = sum(score) / n_scored, where n_scored + n_excluded == 498.

G1 % and G2 % are over all 498 items, a missing response counting as
neither. Check means (C1-C6) are over the scored, non-missing items that
carry the check -- the per-check n that phase12_stepA_score_rag's
check_table reports.

--legacy-500 scores on the pre-Phase-14 convention -- all 500 items, the two
defects included -- for regression only. It reproduces baseline 0.1719
(baseline_scores_v2.json) and SFT 0.5203 (trained_scores.json), and writes
nothing.

Usage:
    python tools/score.py <responses.jsonl> --label <name> [--force]
    python tools/score.py <responses.jsonl> --label <name> --legacy-500
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import phase10_stepB_audit as p10  # noqa: E402
from run_rag_eval import KNOWN_BENCH_DEFECTS  # noqa: E402

# The label becomes part of a filename under data/final/eval/.
LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def load_responses(path: Path) -> dict[str, str]:
    """item_id -> raw_response. A repeated item_id is refused: which of two
    generations is "the" answer is not a question scoring can settle."""
    rows = p10.jsonl(path)
    dup = sorted(i for i, n in Counter(r["item_id"] for r in rows).items() if n > 1)
    if dup:
        raise ValueError(f"{path}: item_id repeated: {dup[:10]}")
    return {r["item_id"]: r["raw_response"] for r in rows}


def scored_items(bench: dict, legacy_500: bool = False) -> dict:
    """The item universe: the bench minus the known defects, or all of it."""
    if legacy_500:
        return dict(bench)
    return {i: it for i, it in bench.items() if i not in KNOWN_BENCH_DEFECTS}


def score(v, res, bench: dict, responses: dict[str, str],
          legacy_500: bool = False) -> dict:
    """Per-item verdicts plus a summary. `bench` is keyed by item_id.

    A response whose item_id is not in the bench is refused rather than
    ignored -- it means the wrong responses file or the wrong bench. A
    response for a known-defect item is in the bench and is simply not
    scored.
    """
    unknown = sorted(set(responses) - set(bench))
    if unknown:
        raise ValueError(f"{len(unknown)} response item_id(s) not in bench: "
                         f"{unknown[:10]}")
    items = scored_items(bench, legacy_500)
    results = p10.rescore(v, res, items, responses)
    rows = []
    for iid in items:
        r = results.get(iid)
        if r is None:
            rows.append({"item_id": iid, "score": 0.0, "excluded": False,
                         "exclusion_reason": "", "missing": True,
                         "g1_json": False, "g2_schema": False, "checks": {},
                         "failures": ["missing: no response for this item"]})
            continue
        rows.append({"item_id": iid,
                     "score": None if r.excluded else r.total,
                     "excluded": r.excluded,
                     "exclusion_reason": r.exclusion_reason,
                     "missing": False,
                     "g1_json": bool(r.gates.get("G1_json")),
                     "g2_schema": bool(r.gates.get("G2_schema")),
                     "checks": r.checks, "failures": r.failures})
    return {"summary": summarise(v, rows, legacy_500), "items": rows}


def summarise(v, rows: list[dict], legacy_500: bool) -> dict:
    scored = [r for r in rows if not r["excluded"]]
    graded = [r for r in scored if not r["missing"]]
    n = len(rows)
    n_g1 = sum(r["g1_json"] for r in rows)
    n_g2 = sum(r["g2_schema"] for r in rows)
    checks = {}
    for c in v.CHECK_WEIGHTS:
        xs = [r["checks"][c] for r in graded if c in r["checks"]]
        checks[c] = {"mean": round(p10.mean(xs), 6) if xs else None, "n": len(xs)}
    return {
        "convention": "legacy_500" if legacy_500 else "bench_minus_known_defects",
        "n_items": n,
        "n_scored": len(scored),
        "n_excluded": n - len(scored),
        "n_missing": sum(r["missing"] for r in rows),
        "mean": round(p10.mean(r["score"] for r in scored), 6) if scored else None,
        "n_g1_json": n_g1,
        "g1_json_pct": round(100 * n_g1 / n, 2) if n else None,
        "n_g2_schema": n_g2,
        "g2_schema_pct": round(100 * n_g2 / n, 2) if n else None,
        "checks": checks,
        "excluded": {r["item_id"]: r["exclusion_reason"] for r in rows if r["excluded"]},
        "missing_ids": [r["item_id"] for r in rows if r["missing"]],
    }


def _rel(p: Path) -> str:
    p = p.resolve()
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else str(p)


def _fmt(x) -> str:
    return "n/a" if x is None else f"{x:.4f}"


def print_summary(s: dict) -> None:
    print(f"{s['label']}  ({s['responses']}; {s['convention']})")
    print(f"  mean        {_fmt(s['mean'])}  over n_scored={s['n_scored']}")
    print(f"  items {s['n_items']}  scored {s['n_scored']}  "
          f"excluded {s['n_excluded']}  missing {s['n_missing']}")
    print(f"  G1 json     {s['g1_json_pct']:.1f}%  ({s['n_g1_json']}/{s['n_items']})")
    print(f"  G2 schema   {s['g2_schema_pct']:.1f}%  ({s['n_g2_schema']}/{s['n_items']})")
    for c, m in s["checks"].items():
        print(f"  {c:<16}{_fmt(m['mean'])}  (n={m['n']})")
    # The full exclusion_reason is in the JSON; a one-line cut is enough here.
    for iid, why in s["excluded"].items():
        print(f"  excluded {iid}: {why[:90]}")
    if s["missing_ids"]:
        print(f"  missing: {', '.join(s['missing_ids'])}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("responses", type=Path)
    ap.add_argument("--label", required=True)
    ap.add_argument("--legacy-500", action="store_true",
                    help="pre-Phase-14 500-item convention; regression only, "
                         "writes nothing")
    ap.add_argument("--force", action="store_true",
                    help="replace an existing scores_<label>.json")
    args = ap.parse_args()
    if not LABEL_RE.match(args.label):
        ap.error(f"--label must match {LABEL_RE.pattern}")
    out = p10.EVAL / f"scores_{args.label}.json"
    if not args.legacy_500 and out.exists() and not args.force:
        raise SystemExit(f"{_rel(out)} exists; pass --force to replace it")

    v = p10.load_verify()
    res = v.VerifyResources.load()
    bench = {r["item_id"]: r for r in p10.jsonl(p10.BENCH)}
    report = score(v, res, bench, load_responses(args.responses), args.legacy_500)
    report["summary"] = {"label": args.label, "responses": _rel(args.responses),
                         **report["summary"]}
    print_summary(report["summary"])
    if args.legacy_500:
        print("--legacy-500: regression convention, nothing written")
        return
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote", _rel(out))


if __name__ == "__main__":
    main()
