"""Pins for src/guard.py, the Phase 14 Step 6 guardrail.

One test per rule (a unregistered, b dose HIGH/LOW, c unknown-PHI escalation,
all-removed, unvalidated, unparseable, guard_failed, no-label-rows), plus the
contract: never inserts anything, idempotent, byte-identical output when no
rule fires, and never reads a benchmark gold field.

Synthetic answers are built from real label_db rows so the numbers move
with the data, and the keys they rely on are asserted up front. guard is
imported with the REAL ban list pinned explicitly: test_verify.py swaps in a
fixture list by re-importing `verify`, and these must not depend on order.
"""
from __future__ import annotations

import ast
import builtins
import importlib
import json
import os
import pathlib
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
LABEL_DB = REPO / "data" / "final" / "label_db.parquet"
REAL_BAN_LIST = REPO / "data" / "final" / "restricted_ai.csv"
BENCH = REPO / "data" / "final" / "bench.jsonl"
EVAL = REPO / "data" / "final" / "eval"
GUARDED = EVAL / "guarded"

WHITEFLY_Q = "Whitefly attack on my cotton, what should I spray?"
CROP_ONLY_Q = "My cotton crop is not looking healthy, what should I spray?"
NO_CROP_Q = "Insects are eating the leaves of my crop, which pesticide should I use?"
NO_ROWS_Q = "Yellow mosaic disease on soybean, what should I spray?"
FAKE = "Unobtainium 5% EC"
ARM_FILES = {"R0_baseline": "baseline_responses.jsonl", "R3_sft": "trained_responses.jsonl",
             "R2_base_rag": "R2_responses.jsonl", "R4_sft_rag": "R4_responses.jsonl"}


@pytest.fixture(scope="module")
def gd():
    if not LABEL_DB.exists():
        pytest.skip("label_db.parquet not built (gitignored)")
    prev = os.environ.get("AGRI_RESTRICTED_AI")
    os.environ["AGRI_RESTRICTED_AI"] = str(REAL_BAN_LIST)
    for name in ("verify", "restricted_ai", "retrieval", "guard"):
        sys.modules.pop(name, None)
    guard = importlib.import_module("guard")
    res = guard.VerifyResources.load()
    if prev is None:
        os.environ.pop("AGRI_RESTRICTED_AI", None)
    else:
        os.environ["AGRI_RESTRICTED_AI"] = prev
    from retrieval import resolve_key
    assert resolve_key(WHITEFLY_Q, res)[:2] == ("cotton", "Whitefly")
    assert resolve_key(CROP_ONLY_Q, res)[:2] == ("cotton", None)
    assert resolve_key(NO_CROP_Q, res)[:2] == (None, None)
    assert resolve_key(NO_ROWS_Q, res)[:2] == ("soybean", "Yellow mosaic")
    assert guard.reference_rows("soybean", "Yellow mosaic", None, res) == []
    return guard, res


def _row(guard, res, pest, pick):
    rows = guard.reference_rows("cotton", pest, None, res)
    names = [guard.norm_name(r["ai"]) for r in rows]
    for r in rows:
        if pick(r) and names.count(guard.norm_name(r["ai"])) == 1:
            return r
    raise AssertionError("no usable label row")


@pytest.fixture(scope="module")
def wf_row(gd):
    """A cotton/Whitefly row: point per-ha dose in g or ml, known PHI, one
    row for its product, so a scaled dose has exactly one row to fail."""
    guard, res = gd
    return _row(guard, res, "Whitefly", lambda r: r["dose_basis"] == "per_ha" and r["dose_max"] is None
                and r["dose_per_acre_min"] is not None and r["phi_days"] is not None
                and r["dose_unit"] in ("g", "ml"))


@pytest.fixture(scope="module")
def other_row(gd):
    """Registered on cotton, but its a.i. on no cotton/Whitefly row."""
    guard, res = gd
    wf = {r["_ai"] for r in guard.reference_rows("cotton", "Whitefly", None, res)}
    return _row(guard, res, None, lambda r: r["_ai"] not in wf and r["dose_basis"] == "per_ha"
                and r["dose_per_acre_min"] is not None and r["phi_days"] is not None)


def option(row, scale=1.0, **kw) -> dict:
    lo, hi = row["dose_per_acre_min"], row["dose_per_acre_max"]
    o = {"active_ingredient": row["ai"], "formulation": row["ai"],
         "dose": {"basis": "per_acre", "value_min": round(lo * scale, 4),
                  "value_max": None if hi is None else round(hi * scale, 4),
                  "unit": row["dose_unit"], "raw": row["dose_raw"]},
         "spray_volume_min_l_per_acre": None, "spray_volume_max_l_per_acre": None,
         "phi_days": row["phi_days"], "phi_not_applicable": row["phi_not_applicable"],
         "caution": "Wear gloves and a mask while spraying."}
    o.update(kw)
    return o


def fake_option(row) -> dict:
    return option(row, active_ingredient=FAKE, formulation=FAKE)


def advisory(options, escalate=False, **kw) -> dict:
    a = {"in_scope": True, "query_understood": True, "clarifying_question": None,
         "likely_causes": [{"name": "Whitefly", "type": "pest", "confidence": 0.9,
                            "evidence": "Sticky honeydew and tiny white insects under leaves."}],
         "non_chemical_first": ["Install yellow sticky traps.", "Remove heavily infested leaves."],
         "chemical_options": options,
         "safety": ["Keep people and livestock out of the field until the spray dries."],
         "escalate_to_expert": escalate}
    a.update(kw)
    return a


def text(a: dict) -> str:
    return json.dumps(a, ensure_ascii=False, separators=(",", ":"))


def names(actions) -> list[str]:
    return [a["action"] for a in actions]


def assert_only_removed_or_escalated(before: str, after: str) -> None:
    """The guard's whole output contract, as a property: options are a
    subsequence of the input's, escalate_to_expert can only go false -> true,
    every other field is untouched."""
    if after == before:
        return
    b, a = json.loads(before), json.loads(after)
    assert set(a) == set(b)
    it = iter(b["chemical_options"])
    assert all(any(o == x for x in it) for o in a["chemical_options"]), "an option was added or edited"
    assert a["escalate_to_expert"] in (b["escalate_to_expert"], True)
    for k in b:
        if k not in ("chemical_options", "escalate_to_expert"):
            assert a[k] == b[k], k


def run(gd, adv_or_text, query=WHITEFLY_Q):
    guard, res = gd
    s = adv_or_text if isinstance(adv_or_text, str) else text(adv_or_text)
    out, actions = guard.guard(s, query, res)
    assert_only_removed_or_escalated(s, out) if out != s else None
    assert guard.guard(out, query, res)[0] == out, "not idempotent"
    return s, out, actions


# --------------------------------------------------------------------------
# no rule fires
# --------------------------------------------------------------------------

def test_no_rule_fires_returns_input_byte_for_byte(gd, wf_row):
    s, out, actions = run(gd, advisory([option(wf_row)]))
    assert out == s and actions == []
    # spacing the guard would never produce survives untouched, too
    spaced = json.dumps(advisory([option(wf_row)]), indent=2)
    assert gd[0].guard(spaced, WHITEFLY_Q, gd[1]) == (spaced, [])


# --------------------------------------------------------------------------
# rule a -- registration
# --------------------------------------------------------------------------

def test_rule_a_removes_an_unregistered_ai(gd, wf_row):
    s, out, actions = run(gd, advisory([option(wf_row), fake_option(wf_row)]))
    a = json.loads(out)
    assert a["chemical_options"] == [option(wf_row)]
    assert a["escalate_to_expert"] is False          # one registered option is left
    assert {"action": "removed_unregistered", "option": 1, "active_ingredient": FAKE} in actions


def test_rule_a_is_pest_specific_when_the_pest_resolves(gd, other_row):
    adv = advisory([option(other_row)])
    _, out, actions = run(gd, adv, WHITEFLY_Q)
    assert json.loads(out)["chemical_options"] == []
    assert "removed_unregistered" in names(actions)
    # the same option against a query naming the crop but no pest: crop-level check
    s, out, actions = run(gd, adv, CROP_ONLY_Q)
    assert out == s and actions == []


def test_rule_a_key_with_no_label_rows_removes_everything(gd, wf_row):
    _, out, actions = run(gd, advisory([option(wf_row)]), NO_ROWS_Q)
    a = json.loads(out)
    assert a["chemical_options"] == [] and a["escalate_to_expert"] is True
    assert names(actions) == ["no_label_rows", "removed_unregistered", "all_removed_escalation"]


# --------------------------------------------------------------------------
# rule b -- dose, +/-8%
# --------------------------------------------------------------------------

@pytest.mark.parametrize("scale, verdict", [
    (1.05, None), (0.95, None), (1.10, "HIGH"), (0.90, "LOW"), (2.0, "HIGH"), (0.5, "LOW")])
def test_rule_b_removes_high_and_low_outside_the_band(gd, wf_row, other_row, scale, verdict):
    keep = option(wf_row)
    probe = option(wf_row, scale)
    s, out, actions = run(gd, advisory([probe]), WHITEFLY_Q)
    removed = [a for a in actions if a["action"] == "removed_dose"]
    if verdict is None:
        assert out == s and actions == []
    else:
        assert [a["verdict"] for a in removed] == [verdict]
        assert json.loads(out)["chemical_options"] == []
    assert gd[0].BAND == 0.08
    assert keep["dose"]["value_min"] == wf_row["dose_per_acre_min"]


def test_rule_b_never_acts_on_a_unit_mismatch(gd, wf_row):
    swapped = {"g": "ml", "ml": "g"}[wf_row["dose_unit"]]
    opt = option(wf_row)
    opt["dose"] = dict(opt["dose"], unit=swapped)
    s, out, actions = run(gd, advisory([opt]))
    assert out == s
    assert names(actions) == ["unit_mismatch"]


# --------------------------------------------------------------------------
# rule c -- unknown PHI
# --------------------------------------------------------------------------

def test_rule_c_forces_escalation_on_an_unknown_phi(gd, wf_row):
    adv = advisory([option(wf_row, phi_days=None)])       # schema-invalid: PHI invariant only
    s, out, actions = run(gd, adv)
    assert names(actions) == ["forced_escalation"]
    assert out == s.replace('"escalate_to_expert":false', '"escalate_to_expert":true')
    gd[0].Advisory.model_validate(json.loads(out))
    # already escalated: schema-valid, nothing to do
    s, out, actions = run(gd, advisory([option(wf_row, phi_days=None)], escalate=True))
    assert out == s and actions == []


def test_all_options_removed_escalates(gd, wf_row):
    _, out, actions = run(gd, advisory([fake_option(wf_row), option(wf_row, 3.0)]))
    a = json.loads(out)
    assert a["chemical_options"] == [] and a["escalate_to_expert"] is True
    assert names(actions) == ["removed_unregistered", "removed_dose", "all_removed_escalation"]


def test_crop_unresolved_keeps_options_and_escalates(gd, wf_row):
    adv = advisory([option(wf_row), fake_option(wf_row)])  # even the fake cannot be checked
    s, out, actions = run(gd, adv, NO_CROP_Q)
    a = json.loads(out)
    assert a["chemical_options"] == adv["chemical_options"] and a["escalate_to_expert"] is True
    assert names(actions) == ["unvalidated_escalation"]


# --------------------------------------------------------------------------
# not guardable
# --------------------------------------------------------------------------

@pytest.mark.parametrize("make", [
    lambda o: "Spray something.",
    lambda o: text({"Advisory": advisory([o])}),                       # wrapped: no unwrapping
    lambda o: text(advisory([dict(o, dose=dict(o["dose"], unit="kg/acre"))])),
    lambda o: text(advisory([dict(o, phi_days=None)], likely_causes=[{"name": "x", "type": "insect",
                                                                      "confidence": 0.9, "evidence": ""}])),
    lambda o: "[1, 2]",
], ids=["not-json", "wrapped", "bad-unit", "phi-plus-another-error", "not-an-object"])
def test_unparseable_answers_are_left_alone(gd, wf_row, make):
    s = make(option(wf_row, 5.0, active_ingredient=FAKE))
    out, actions = gd[0].guard(s, WHITEFLY_Q, gd[1])
    assert out == s and actions == [{"action": "unparseable"}]


def test_guard_failed_returns_the_original(gd, wf_row):
    # PHI invariant fires first, so the answer is guardable; once escalated,
    # the "ununderstood query with chemicals" invariant still fails.
    adv = advisory([option(wf_row, phi_days=None)], query_understood=False)
    s, out, actions = run(gd, adv)
    assert out == s
    assert names(actions) == ["forced_escalation", "guard_failed"]


# --------------------------------------------------------------------------
# contract on real answers
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def bench():
    with open(BENCH, encoding="utf-8") as f:
        return {r["item_id"]: r for r in map(json.loads, f)}


def _jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.mark.parametrize("label", list(ARM_FILES))
def test_committed_guarded_files_only_remove_or_escalate(label):
    before = {r["item_id"]: r["raw_response"] for r in _jsonl(EVAL / ARM_FILES[label])}
    after = _jsonl(GUARDED / f"{label}_responses.jsonl")
    assert [r["item_id"] for r in after] == list(before)
    for r in after:
        assert r["changed"] == (r["raw_response"] != before[r["item_id"]])
        assert_only_removed_or_escalated(before[r["item_id"]], r["raw_response"])


@pytest.mark.parametrize("label", ["R3_sft", "R4_sft_rag"])
def test_idempotent_on_every_changed_real_answer(gd, bench, label):
    guard, res = gd
    for r in _jsonl(GUARDED / f"{label}_responses.jsonl"):
        if r["changed"]:
            q = bench[r["item_id"]]["query_text"]
            assert guard.guard(r["raw_response"], q, res)[0] == r["raw_response"], r["item_id"]


# --------------------------------------------------------------------------
# the key never comes from the benchmark
# --------------------------------------------------------------------------

def test_key_comes_from_the_query_not_the_gold_label(gd, bench):
    """S1_623's gold crop is onion, but its query names cotton."""
    guard, res = gd
    item = bench["S1_623"]
    assert item["crop_slug"] == "onion"
    r = guard.guard_detailed("{}", item["query_text"], res)
    assert r.crop == "cotton"


def test_guard_never_opens_the_benchmark(gd, wf_row, monkeypatch):
    guard, res = gd
    real_open = builtins.open

    def no_bench(path, *a, **k):
        assert "bench" not in str(path), f"guard opened {path}"
        return real_open(path, *a, **k)
    monkeypatch.setattr(builtins, "open", no_bench)
    monkeypatch.setattr(pathlib.Path, "read_text", lambda p, *a, **k: no_bench(p).read())
    for q in (WHITEFLY_Q, CROP_ONLY_Q, NO_CROP_Q, NO_ROWS_Q):
        guard.guard(text(advisory([option(wf_row), fake_option(wf_row)])), q, res)


def test_guard_source_names_no_gold_or_bench_field():
    tree = ast.parse((REPO / "src" / "guard.py").read_text(encoding="utf-8"))
    docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                  if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
                  and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    strings, idents = [], []
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings:
            strings.append(n.value)
        elif isinstance(n, ast.Name):
            idents.append(n.id)
        elif isinstance(n, ast.Attribute):
            idents.append(n.attr)
    # A bench item is a dict, so its gold fields would appear as string keys.
    # `r.crop_slug` on a label_db row is an attribute and stays allowed.
    item_keys = ("gold", "bench", "crop_slug", "canonical_pest", "item_id", "query_text")
    assert not [s for s in strings if any(k in s.lower() for k in item_keys)]
    assert not [i for i in idents if "gold" in i.lower() or "bench" in i.lower()]


# --------------------------------------------------------------------------
# one copy of the Phase 12 validator
# --------------------------------------------------------------------------

def test_phase12_replay_imports_the_guard_functions():
    tools = str(REPO / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    r5 = importlib.import_module("phase12_step5_validator_replay")
    assert r5.repair.__module__ == "guard" and r5.check_dose.__module__ == "guard"
    assert r5.norm_name.__module__ == "guard"
    for local in ("candidate_rows", "row_bounds", "judge", "to_base", "BAND"):
        assert not hasattr(r5, local), f"{local} redefined in the replay"
