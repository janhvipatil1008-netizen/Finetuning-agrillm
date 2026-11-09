"""Pins for tools/score.py, the unified scoring CLI (Phase 14 Step 1).

Three things: the 498-item denominator (500 bench items minus the two
run_rag_eval.KNOWN_BENCH_DEFECTS, nothing else pre-removed), a missing
response scoring 0 rather than leaving the mean, and the regression -- the
--legacy-500 convention reproduces the recorded baseline (0.1719) and SFT
(0.5203) scores item for item, so score.py is provably the convention that
produced the published numbers.

verify is loaded through phase10_stepB_audit.load_verify, which pins the
SHIPPED ban list: test_verify.py swaps in a fixture list by re-importing
`verify`, and these numbers must not depend on test order.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
LABEL_DB = REPO / "data" / "final" / "label_db.parquet"
EVAL = REPO / "data" / "final" / "eval"


@pytest.fixture(scope="module")
def sc():
    tools = str(REPO / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    return importlib.import_module("score")


@pytest.fixture(scope="module")
def env(sc):
    if not LABEL_DB.exists():
        pytest.skip("label_db.parquet not built (gitignored)")
    v = sc.p10.load_verify()
    res = v.VerifyResources.load()
    bench = {r["item_id"]: r for r in sc.p10.jsonl(sc.p10.BENCH)}
    return v, res, bench


def _recorded(name: str) -> dict:
    return {r["item_id"]: r for r in json.loads((EVAL / name).read_text(encoding="utf-8"))}


# --------------------------------------------------------------------------
# denominator
# --------------------------------------------------------------------------

def test_denominator_is_498(sc, env):
    v, res, bench = env
    assert len(bench) == 500
    assert set(sc.KNOWN_BENCH_DEFECTS) == {"S1_1856", "S1_623"}
    items = sc.scored_items(bench)
    assert len(items) == 498
    assert not set(items) & set(sc.KNOWN_BENCH_DEFECTS)
    assert len(sc.scored_items(bench, legacy_500=True)) == 500


def test_nothing_else_is_pre_removed(sc, env):
    """With no responses at all, every one of the 498 is scored (as missing)
    and none is excluded -- verify() exclusions depend on a response, so
    there is no other up-front removal. A response for a defect item is
    ignored, not scored."""
    v, res, bench = env
    s = sc.score(v, res, bench, {"S1_623": "{}"})["summary"]
    assert (s["n_items"], s["n_scored"], s["n_excluded"], s["n_missing"]) == (498, 498, 0, 498)
    assert s["mean"] == 0.0
    assert "S1_623" not in s["missing_ids"]


# --------------------------------------------------------------------------
# missing
# --------------------------------------------------------------------------

def test_missing_item_scores_zero_and_stays_in_mean(sc, env):
    v, res, bench = env
    trained = sc.load_responses(EVAL / "trained_responses.jsonl")
    rec = _recorded("trained_scores.json")
    ids = [i for i in bench if not rec[i]["excluded"] and rec[i]["total"] > 0][:3]
    sub = {i: bench[i] for i in ids}

    full = sc.score(v, res, sub, {i: trained[i] for i in ids})
    dropped = sc.score(v, res, sub, {i: trained[i] for i in ids[:2]})

    row = {r["item_id"]: r for r in dropped["items"]}[ids[2]]
    assert row["missing"] and row["score"] == 0.0 and not row["excluded"]
    assert not row["g1_json"] and not row["g2_schema"]
    s = dropped["summary"]
    assert (s["n_scored"], s["n_excluded"], s["n_missing"]) == (3, 0, 1)
    assert s["missing_ids"] == [ids[2]]
    kept = sum(r["score"] for r in full["items"][:2])
    assert s["mean"] == pytest.approx(kept / 3)
    assert s["mean"] < full["summary"]["mean"]


def test_repeated_item_id_is_refused(sc, tmp_path):
    p = tmp_path / "dup.jsonl"
    p.write_text('{"item_id": "B1_45", "raw_response": "{}"}\n' * 2, encoding="utf-8")
    with pytest.raises(ValueError, match="repeated"):
        sc.load_responses(p)


def test_unknown_item_id_is_refused(sc, env):
    v, res, bench = env
    with pytest.raises(ValueError, match="not in bench"):
        sc.score(v, res, bench, {"NOT_AN_ITEM": "{}"})


# --------------------------------------------------------------------------
# regression: the old 500-item convention reproduces the recorded numbers
# --------------------------------------------------------------------------

@pytest.mark.parametrize("responses, recorded, mean4, n_excluded", [
    ("baseline_responses.jsonl", "baseline_scores_v2.json", 0.1719, 0),
    ("trained_responses.jsonl", "trained_scores.json", 0.5203, 11),
])
def test_legacy_500_reproduces_recorded_scores(sc, env, responses, recorded,
                                               mean4, n_excluded):
    v, res, bench = env
    out = sc.score(v, res, bench, sc.load_responses(EVAL / responses),
                   legacy_500=True)
    s = out["summary"]
    assert round(s["mean"], 4) == mean4
    assert (s["n_items"], s["n_excluded"], s["n_missing"]) == (500, n_excluded, 0)

    rec = _recorded(recorded)
    for r in out["items"]:
        w = rec[r["item_id"]]
        assert r["excluded"] == w["excluded"], r["item_id"]
        assert r["checks"] == w["checks"], r["item_id"]
        if r["excluded"]:
            assert r["score"] is None and r["exclusion_reason"]
            assert r["item_id"] in s["excluded"]
        else:
            assert round(r["score"], 6) == round(w["total"], 6), r["item_id"]
