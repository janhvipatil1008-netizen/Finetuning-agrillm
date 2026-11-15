"""Pins for tools/score.py, the unified scoring CLI (Phase 14 Steps 1 and 5).

--unwrap-advisory (Step 5) is pinned below the denominator tests: only an
exact {"Advisory": {...}} is unwrapped, the inner object scores as if it had
been sent bare, and the input is never rewritten.

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
import subprocess
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
# --unwrap-advisory
# --------------------------------------------------------------------------

def test_unwrap_advisory_only_exact_single_key_object(sc):
    inner = {"in_scope": True, "likely_causes": [], "x": [1, 2.5, None]}
    assert json.loads(sc.unwrap_advisory(json.dumps({"Advisory": inner}))) == inner
    for raw in (json.dumps(inner),                            # already bare
                json.dumps({"Advisory": inner, "note": 1}),   # a second key
                json.dumps({"Advisory": [inner]}),            # value not an object
                json.dumps({"Advisory": "text"}),
                json.dumps({"advisory": inner}),              # key is case-sensitive
                json.dumps([{"Advisory": inner}]),
                '{"Advisory": {"in_scope": tr',               # torn
                "not json"):
        assert sc.unwrap_advisory(raw) is None, raw


def test_unwrap_scores_the_inner_object_and_leaves_input_alone(sc, env):
    v, res, bench = env
    iid = next(i for i, it in bench.items()
               if it["kind"] == "DOSE" and i not in sc.KNOWN_BENCH_DEFECTS)
    sub = {iid: bench[iid]}
    plain = json.dumps(bench[iid]["gold_advisory"])
    wrapped = json.dumps({"Advisory": bench[iid]["gold_advisory"]})
    responses = {iid: wrapped}
    want = sc.score(v, res, sub, {iid: plain})["items"][0]
    assert want["score"] > 0

    off = sc.score(v, res, sub, responses)
    row = off["items"][0]
    assert (row["g2_schema"], row["score"], row["unwrapped"]) == (False, 0.0, False)
    assert (off["summary"]["unwrap_advisory"], off["summary"]["n_unwrapped"]) == (False, 0)

    on = sc.score(v, res, sub, responses, unwrap=True)
    row = on["items"][0]
    assert row["unwrapped"] and row["g2_schema"]
    assert (row["score"], row["checks"]) == (want["score"], want["checks"])
    assert (on["summary"]["unwrap_advisory"], on["summary"]["n_unwrapped"]) == (True, 1)
    assert responses == {iid: wrapped}          # scoring never rewrites its input

    bare = sc.score(v, res, sub, {iid: plain}, unwrap=True)["items"][0]
    assert not bare["unwrapped"] and (bare["score"], bare["checks"]) == (want["score"], want["checks"])


@pytest.mark.parametrize("responses, n_wrapped", [
    ("R2_responses.jsonl", 132), ("R4_responses.jsonl", 0)])
def test_wrapped_counts_in_phase14_runs(sc, responses, n_wrapped):
    raw = sc.load_responses(EVAL / responses)
    assert sum(sc.unwrap_advisory(r) is not None for r in raw.values()) == n_wrapped


def test_unwrap_flag_on_cli(sc):
    r = subprocess.run([sys.executable, str(REPO / "tools" / "score.py"), "--help"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert "--unwrap-advisory" in r.stdout


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


# --------------------------------------------------------------------------
# --exclude-items and the seed-treatment basis sensitivity
# --------------------------------------------------------------------------

def test_exclude_items_removes_and_records(sc, env):
    v, res, bench = env
    out = sc.score(v, res, bench, {}, exclude=frozenset({"S1_140", "B3_25"}))
    s = out["summary"]
    assert s["n_items"] == 496 and s["excluded_up_front"] == ["B3_25", "S1_140"]
    assert s["convention"].endswith("_minus_listed_items")
    assert not {"S1_140", "B3_25"} & {r["item_id"] for r in out["items"]}
    with pytest.raises(ValueError, match="exclude names"):
        sc.score(v, res, bench, {}, exclude=frozenset({"NOT_AN_ITEM"}))


SEEDEXCL_ARMS = ["R0_baseline", "R3_sft", "R2_base_rag", "R2_base_rag_unwrapped",
                 "R4_sft_rag", "R4_sft_rag_guarded"]


@pytest.mark.parametrize("label", SEEDEXCL_ARMS)
def test_seedexcl_scores_follow_the_item_list(label):
    """Each _seedexcl file is its arm's 498-item file minus the listed items."""
    listed = json.loads((EVAL / "seedexcl_items.json").read_text(encoding="utf-8"))["items"]
    sx = json.loads((EVAL / f"scores_{label}_seedexcl.json").read_text(encoding="utf-8"))
    base = json.loads((EVAL / f"scores_{label}.json").read_text(encoding="utf-8"))
    assert sx["summary"]["excluded_up_front"] == sorted(listed) and sx["summary"]["n_items"] == 491
    want = {r["item_id"]: r for r in base["items"] if r["item_id"] not in set(listed)}
    assert [r["item_id"] for r in sx["items"]] == list(want)
    assert all(r["score"] == want[r["item_id"]]["score"] for r in sx["items"])


def test_seed_basis_review_covers_every_seed_treatment_row(sc, env):
    v, res, bench = env
    sb = importlib.import_module("phase14_seed_basis")
    assert len(sb.seed_rows(v, res)) == 38          # asserts the review covers exactly these
    counts = {c: len(sb.by_class(c)) for c in ("CORRECT", "WRONG_BASIS", "UNCLEAR", "NOT_RECORDED")}
    assert counts == {"CORRECT": 14, "WRONG_BASIS": 12, "UNCLEAR": 7, "NOT_RECORDED": 5}
    listed = json.loads((EVAL / "seedexcl_items.json").read_text(encoding="utf-8"))
    assert listed["wrong_basis_rows"] == sorted(sb.by_class("WRONG_BASIS"))
    # every WRONG_BASIS / UNCLEAR row is one label_db recorded per hectare
    df = res.label_db.df
    assert {i for i in sb.ROW_REVIEW if df.at[i, "dose_formulation_basis"] == "per_ha"} == \
        sb.by_class("WRONG_BASIS") | sb.by_class("UNCLEAR")
