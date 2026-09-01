"""test_verify.py — pins the verifier's gates and graded checks.

`src/verify.py` loads the restricted-AI list AT IMPORT and raises when it is
absent, so this module cannot import it at the top. Every test goes through
the `verify_mod` fixture, which points AGRI_RESTRICTED_AI at a temporary list
and imports fresh. That is not a workaround — `test_import_fails_without_ban_list`
pins the raising behaviour as the contract.

The load-bearing tests are the mutations: a 3x overdose on a point-dose row, a
banned a.i., a right-chemical-wrong-pest recommendation, and a PHI of 0 versus
None. Each is a case where the obvious implementation passes and a farmer gets
hurt.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

LABEL_DB = ROOT / "data" / "final" / "label_db.parquet"

BAN_CSV = """active_ingredient,tier,restricted_crops,instrument,date,notes
Monocrotophos,banned,,TEST s.27A order,2026-01-01,fixture only
Phorate,refused_registration,,TEST s.27A order,2026-01-01,fixture only
Carbofuran,restricted_use,tomato,TEST s.27A order,2026-01-01,fixture: tomato only
"""


@pytest.fixture(scope="module")
def ban_list(tmp_path_factory):
    p = tmp_path_factory.mktemp("bans") / "restricted_ai.csv"
    p.write_text(BAN_CSV, encoding="utf-8")
    return p


@pytest.fixture(scope="module")
def verify_mod(ban_list):
    import os
    os.environ["AGRI_RESTRICTED_AI"] = str(ban_list)
    for name in ("verify", "restricted_ai"):
        sys.modules.pop(name, None)
    mod = importlib.import_module("verify")
    yield mod
    os.environ.pop("AGRI_RESTRICTED_AI", None)
    sys.modules.pop("verify", None)


@pytest.fixture(scope="module")
def resources(verify_mod):
    if not LABEL_DB.exists():
        pytest.skip("label_db.parquet not built (gitignored)")
    return verify_mod.VerifyResources.load()


@pytest.fixture(scope="module")
def point_row(resources):
    """A real label_db row that is trainable, per_ha, has a known PHI, and is
    a POINT dose (no max) — found rather than hardcoded, so the tests survive
    a label_db rebuild. Returns (row, series, canonical, pest_query)."""
    return _find_row(resources, want_range=False)


@pytest.fixture(scope="module")
def range_row(resources):
    """The same, but a RANGE dose (value_max present)."""
    return _find_row(resources, want_range=True)


def _find_row(resources, *, want_range):
    from pest_matcher import match_pest
    db, df = resources.label_db, resources.label_db.df
    for r in db.rows:
        d = df.loc[r.index]
        if not r.trainable or r.defective or not r.canonicals:
            continue
        if str(d["dose_formulation_basis"]) != "per_ha" or pd.isna(d["phi_days"]):
            continue
        has_max = pd.notna(d["dose_formulation_value_max"])
        if has_max != want_range:
            continue
        for canon in sorted(r.canonicals):
            if not db.for_triple(r.crop_slug, canon, r.ai_components):
                continue
            # the query string must itself resolve to THIS canonical, or the
            # test would be exercising a different pest than the fixture row.
            for surf in (str(d["pest_or_disease"]),) + r.pest_surface_forms:
                if match_pest(r.crop_slug, surf,
                              resources.table).canonical_name == canon:
                    return r, d, canon, surf
    pytest.skip(f"no {'range' if want_range else 'point'}-dose fixture row")


def good_output(fixture, *, basis="per_acre", dose=None, phi=None,
                escalate=False, full=True, **kw):
    """A CORRECT advisory for a fixture row, with one thing optionally mutated.

    `full` populates likely_causes and non_chemical_first so C5 and C6 fire.
    It defaults True because a mutation test has to start from a baseline that
    scores 1.0 — mutate a partly-wrong answer and the collateral assertion
    fires on the pre-existing miss instead of the mutation.
    """
    row, d, _canon, query = fixture
    ai = sorted(row.ai_components)[0]
    if dose is None:
        dose = float(d["dose_formulation_per_acre_min"] if basis == "per_acre"
                     else d["dose_formulation_value_min"])
    if phi is None:
        phi = int(d["phi_days"])
    vmax = None
    if basis == "per_ha" and pd.notna(d["dose_formulation_value_max"]):
        vmax = None            # a single stated value is a valid answer
    extra = {}
    if full:
        extra["causes"] = [{"name": query, "type": "pest",
                            "confidence": 0.9, "evidence": "observed"}]
        extra["non_chemical"] = ["remove and destroy crop residue"]
    extra.update(kw)
    return advisory(
        [chem(ai, str(d["active_ingredient"]), dose,
              str(d["dose_formulation_unit"]), basis, phi, value_max=vmax)],
        escalate=escalate,
        causes=extra.get("causes", ()),
        non_chemical=extra.get("non_chemical", ()))


def assert_only_failed(result, name):
    """The other half of the mutation contract: one check drops, nothing else.

    A mutation test that only asserts its own check failed cannot tell a
    precise verifier from one that collapses on any imperfection.
    """
    assert name in result.checks, f"{name} did not run: {sorted(result.checks)}"
    assert result.checks[name] == 0.0, f"{name} should have failed"
    collateral = {k: v for k, v in result.checks.items()
                  if k != name and v != 1.0}
    assert not collateral, f"{name} mutation damaged other checks: {collateral}"
    failed_gates = [k for k, v in result.gates.items() if not v]
    assert not failed_gates, f"gates should stay clean, got {failed_gates}"


def ctx_for(verify_mod, resources, crop, pest, **kw):
    return verify_mod.VerifyContext(resources=resources, crop_slug=crop,
                                    pest_query=pest, **kw)


def advisory(chemicals=(), *, in_scope=True, understood=True, escalate=False,
             causes=(), non_chemical=(), safety=("wear gloves",)):
    return json.dumps({
        "in_scope": in_scope,
        "query_understood": understood,
        "likely_causes": list(causes),
        "non_chemical_first": list(non_chemical),
        "chemical_options": list(chemicals),
        "safety": list(safety),
        "escalate_to_expert": escalate,
    })


def chem(ai, formulation, value_min, unit, basis, phi, *, value_max=None,
         raw="x"):
    return {
        "active_ingredient": ai,
        "formulation": formulation,
        "dose": {"basis": basis, "value_min": value_min,
                 "value_max": value_max, "unit": unit, "raw": raw},
        "phi_days": phi,
        "caution": "wear gloves",
    }


# --- the ban list is not optional ------------------------------------------

def test_import_fails_without_ban_list(monkeypatch, tmp_path):
    """A missing ban list must never resolve to 'no bans apply'."""
    monkeypatch.setenv("AGRI_RESTRICTED_AI", str(tmp_path / "absent.csv"))
    for name in ("verify", "restricted_ai"):
        sys.modules.pop(name, None)
    from restricted_ai import MissingBanListError
    with pytest.raises(MissingBanListError):
        importlib.import_module("verify")
    sys.modules.pop("verify", None)


def test_empty_ban_list_is_rejected(tmp_path):
    """A header-only file reads as 'nothing is restricted'. Refuse it."""
    p = tmp_path / "restricted_ai.csv"
    p.write_text("active_ingredient,tier,restricted_crops,instrument,date,notes\n",
                 encoding="utf-8")
    sys.modules.pop("restricted_ai", None)
    from restricted_ai import MissingBanListError, load_restricted_ai
    with pytest.raises(MissingBanListError):
        load_restricted_ai(p)


def test_unknown_tier_rejects_the_whole_list(tmp_path):
    p = tmp_path / "restricted_ai.csv"
    p.write_text("active_ingredient,tier,restricted_crops,instrument,date,notes\n"
                 "Foo,probably_fine,,x,2026-01-01,\n", encoding="utf-8")
    from restricted_ai import MissingBanListError, load_restricted_ai
    with pytest.raises(MissingBanListError):
        load_restricted_ai(p)


# --- the loader refuses a CSV ----------------------------------------------

def test_loader_refuses_a_csv_path(verify_mod):
    """phi_days degrades Int64 -> float64 through CSV, collapsing 0 and None."""
    with pytest.raises(ValueError, match="parquet"):
        verify_mod.load_label_db(ROOT / "data" / "final" / "label_db.csv")


def test_loader_accepts_the_parquet(verify_mod):
    if not LABEL_DB.exists():
        pytest.skip("label_db.parquet not built")
    df = verify_mod.load_label_db(LABEL_DB)
    assert str(df["phi_days"].dtype) == "Int64"
    assert df["phi_days"].isna().sum() == 200      # None, not 0
    assert (df["phi_days"] == 0).sum() == 1        # a real same-day interval


# --- G1 / G2 ---------------------------------------------------------------

def test_g1_rejects_a_trailing_comma(verify_mod, resources):
    """Near-valid JSON is the realistic model failure — a truncated or
    over-eager generation, not prose. It exercises a different parser path
    from garbage text."""
    c = ctx_for(verify_mod, resources, "cotton", "bollworms")
    payload = ('{"in_scope": true, "query_understood": true, '
               '"likely_causes": [], "non_chemical_first": [], '
               '"chemical_options": [], "safety": [], '
               '"escalate_to_expert": false,}')          # <- trailing comma
    r = verify_mod.verify(payload, c)
    assert r.gates["G1_json"] is False
    assert r.total == 0.0 and not r.passed
    assert "G1" in " ".join(r.failures)


def test_g1_rejects_garbage(verify_mod, resources):
    c = ctx_for(verify_mod, resources, "cotton", "bollworms")
    r = verify_mod.verify("not json at all", c)
    assert r.gates["G1_json"] is False and r.total == 0.0 and not r.passed


def test_g2_rejects_schema_violation(verify_mod, resources):
    c = ctx_for(verify_mod, resources, "cotton", "bollworms")
    bad = json.dumps({"in_scope": True})           # missing required fields
    r = verify_mod.verify(bad, c)
    assert r.gates["G2_schema"] is False and r.total == 0.0


# --- G4: banned active ingredients -----------------------------------------

def test_g4_blocks_a_banned_ai(verify_mod, resources):
    """Monocrotophos IS in label_db on cotton for sucking pests. Right crop,
    right pest, right dose, right PHI — and it must still fail."""
    c = ctx_for(verify_mod, resources, "cotton", "jassids")
    out = advisory([chem("Monocrotophos", "36% SL", 1333.0, "g", "per_ha", 58)])
    r = verify_mod.verify(out, c)
    assert r.gates["G4_restricted_ai"] is False
    assert r.total == 0.0
    assert any("Monocrotophos" in f and "banned" in f for f in r.failures)


def test_g4_restricted_use_is_conditional_on_crop(verify_mod, resources):
    """Tier three has carve-outs: the same a.i. bites on one crop, not another."""
    restricted = resources.restricted
    assert restricted.check({"carbofuran"}, "tomato")       # bites
    assert not restricted.check({"carbofuran"}, "soybean")  # carve-out
    assert restricted.check({"monocrotophos"}, "soybean")   # banned everywhere


def test_g4_checks_every_component_of_a_mixture(verify_mod, resources):
    hits = resources.restricted.check({"imidacloprid", "monocrotophos"}, "cotton")
    assert hits and hits[0].tier == "banned"


# --- G5: right chemical, wrong pest ----------------------------------------

def test_g5_rejects_right_crop_wrong_pest(verify_mod, resources):
    """The shape a plausible hallucination takes: every number real, the
    pairing unregistered."""
    c = ctx_for(verify_mod, resources, "grape", "powdery mildew")
    out = advisory([chem("Chlorpyrifos", "20% EC", 1517.5, "ml", "per_acre", 15)])
    r = verify_mod.verify(out, c)
    assert r.gates["G5_triple_registered"] is False
    assert r.total == 0.0


def test_g5_failures_quote_surface_forms_not_canonicals(verify_mod, resources):
    """These get read by hand. 'expected Helicoverpa armigera' is useless when
    the farmer said 'fruit borer'."""
    c = ctx_for(verify_mod, resources, "tomato", "fruit borer")
    out = advisory([chem("Nonexistentamide", "50% SC", 500.0, "ml", "per_ha", 7)])
    r = verify_mod.verify(out, c)
    assert r.gates["G5_triple_registered"] is False
    joined = " ".join(r.failures)
    assert "fruit borer" in joined
    assert "Helicoverpa armigera" not in joined


# --- G6: unknown PHI vs positively-not-applicable --------------------------

def test_g6_unknown_phi_forces_escalation(verify_mod, resources):
    c = ctx_for(verify_mod, resources, "cotton", "jassids")
    out = advisory([chem("Chlorpyrifos", "20% EC", 3750.0, "ml", "per_ha", None)],
                   escalate=True)
    r = verify_mod.verify(out, c)
    assert r.gates["G6_unknown_phi_escalates"] is True


def test_zero_phi_routes_through_verify_without_firing_g6(verify_mod, resources):
    """0 is a genuine same-day-harvest interval (Polyoxin D on grape). It must
    reach C2 as a real value, not be mistaken for an unknown."""
    df = resources.label_db.df
    zero = df[df["phi_days"] == 0]
    if zero.empty:
        pytest.skip("no zero-PHI row in this build")
    i = zero.index[0]
    row = resources.label_db.rows[i]
    d = df.loc[i]
    if not row.canonicals:
        pytest.skip("zero-PHI row has no resolvable pest")
    canon = sorted(row.canonicals)[0]
    query = str(d["pest_or_disease"])
    ai = sorted(row.ai_components)[0]
    c = ctx_for(verify_mod, resources, row.crop_slug, query)
    out = advisory([chem(ai, str(d["active_ingredient"]),
                         float(d["dose_formulation_value_min"]),
                         str(d["dose_formulation_unit"]),
                         str(d["dose_formulation_basis"]), 0)])
    r = verify_mod.verify(out, c)
    assert r.gates["G6_unknown_phi_escalates"] is True,         "a stated 0 must not be read as an unknown PHI"
    assert "C2_phi" in r.checks, "the zero-PHI row must produce a C2 score"
    assert r.checks["C2_phi"] == 1.0, "0 must match a label PHI of 0"
    assert verify_mod.verify(out, c, "filter").passed,         "a correct zero-PHI answer must not be blocked at inference"


def test_a_truthiness_check_would_confuse_zero_with_unknown():
    """The bug this guards against, written out.

    `if not phi_days:` is the first thing anyone reaches for, and it treats a
    same-day-harvest label identically to a label with no interval printed.
    """
    real_zero, unknown = 0, None
    assert not real_zero and not unknown          # truthiness: indistinguishable
    assert (real_zero is None) != (unknown is None)   # identity: distinguishable


def test_schema_keeps_zero_and_none_apart():
    from schema import Advisory, ChemicalOption, Dose
    opt = ChemicalOption(
        active_ingredient="Polyoxin D", formulation="5% SC",
        dose=Dose(basis="per_ha", value_min=1.0, unit="l", raw="1 l"),
        phi_days=0, caution="gloves")
    a = Advisory(in_scope=True, query_understood=True, chemical_options=[opt],
                 escalate_to_expert=False)
    assert a.chemical_options[0].phi_days == 0
    assert a.chemical_options[0].phi_days is not None


# --- C1: THE POINT-DOSE MUTATION -------------------------------------------

def test_point_dose_row_rejects_a_3x_overdose(verify_mod, resources, point_row):
    """433 of the 612 rows with a per-acre value have min and NO max.

    If C1 decides 'is this a range?' by testing min is non-null, all 433
    become open-ended and every overdose above the minimum passes. C1 must
    branch on max being non-null.
    """
    row, d, canon, query = point_row
    assert pd.isna(d["dose_formulation_per_acre_max"]), "fixture must be a point dose"
    lo = float(d["dose_formulation_per_acre_min"])
    ai = sorted(row.ai_components)[0]

    c = ctx_for(verify_mod, resources, row.crop_slug, str(d["pest_or_disease"]))
    out = advisory([chem(ai, str(d["active_ingredient"]), lo * 3,
                         str(d["dose_formulation_unit"]), "per_acre",
                         int(d["phi_days"]))])
    r = verify_mod.verify(out, c)
    assert r.gates["G5_triple_registered"] is True, "fixture must be registered"
    assert r.gates["G8_dose_basis"] is True, "per_acre vs per_ha is compatible"
    assert r.checks.get("C1_dose") == 0.0, "a 3x overdose must fail C1"
    assert not verify_mod.verify(out, c, "gate").passed


def test_point_dose_accepts_the_label_value(verify_mod, resources, point_row):
    """The same row, stated correctly, must pass C1 — otherwise the test above
    proves nothing."""
    row, d, canon, query = point_row
    lo = float(d["dose_formulation_per_acre_min"])
    ai = sorted(row.ai_components)[0]
    c = ctx_for(verify_mod, resources, row.crop_slug, str(d["pest_or_disease"]))
    out = advisory([chem(ai, str(d["active_ingredient"]), lo,
                         str(d["dose_formulation_unit"]), "per_acre",
                         int(d["phi_days"]))])
    r = verify_mod.verify(out, c)
    assert r.checks.get("C1_dose") == 1.0


def test_point_dose_accepts_field_rounding(verify_mod, resources):
    """Tolerance exists for 404.7 -> 400 and nothing wider."""
    ok = verify_mod._dose_value_ok
    assert ok(400.0, 404.7, None)          # 1.2% low
    assert ok(1517.5, 1517.5428, None)
    assert not ok(1517.5 * 1.2, 1517.5, None)   # 20% over
    assert not ok(1517.5 * 3, 1517.5, None)     # 3x


def test_range_dose_uses_containment_never_the_midpoint(
        verify_mod, resources, range_row):
    """End-to-end through verify(), not the private helper.

    The label authorises the whole interval, so both endpoints and everything
    between must pass. Scoring against the midpoint would reject the label's
    own printed endpoints.
    """
    row, d, _canon, query = range_row
    lo = float(d["dose_formulation_value_min"])
    hi = float(d["dose_formulation_value_max"])
    c = ctx_for(verify_mod, resources, row.crop_slug, query)

    for label, v in (("low end", lo), ("midpoint", (lo + hi) / 2),
                     ("high end", hi)):
        r = verify_mod.verify(good_output(range_row, basis="per_ha", dose=v), c)
        assert r.checks.get("C1_dose") == 1.0, f"{label} ({v}) must pass"

    for label, v in (("below low", lo * 0.8), ("above high", hi * 1.2)):
        r = verify_mod.verify(good_output(range_row, basis="per_ha", dose=v), c)
        assert r.checks.get("C1_dose") == 0.0, f"{label} ({v}) must fail"


def test_range_dose_low_end_passes_filter_mode(verify_mod, resources, range_row):
    """The control for the blocking tier: a legitimate low-end answer must not
    be blocked at inference."""
    row, d, _canon, query = range_row
    c = ctx_for(verify_mod, resources, row.crop_slug, query)
    out = good_output(range_row, basis="per_ha",
                      dose=float(d["dose_formulation_value_min"]))
    assert verify_mod.verify(out, c, "filter").passed


def test_dose_helper_boundaries(verify_mod):
    """Unit-level cover for the branch itself, alongside the end-to-end test."""
    ok = verify_mod._dose_value_ok
    assert ok(450.0, 450.0, 600.0) and ok(600.0, 450.0, 600.0)
    assert not ok(700.0, 450.0, 600.0) and not ok(400.0, 450.0, 600.0)


def test_dose_tolerance_constant_is_five_percent(verify_mod):
    assert verify_mod.DOSE_TOLERANCE == 0.05


# --- G8: basis is a gate, not a graded penalty -----------------------------

def test_g8_basis_mismatch_is_a_gate(verify_mod, resources, point_row):
    """A correct number on the wrong basis is more dangerous than a wrong
    number, so it zeroes the item rather than costing partial credit."""
    row, d, canon, query = point_row
    ai = sorted(row.ai_components)[0]
    c = ctx_for(verify_mod, resources, row.crop_slug, str(d["pest_or_disease"]))
    out = advisory([chem(ai, str(d["active_ingredient"]),
                         float(d["dose_formulation_value_min"]),
                         str(d["dose_formulation_unit"]), "per_litre_water",
                         int(d["phi_days"]))])
    r = verify_mod.verify(out, c)
    assert r.gates["G5_triple_registered"] is True, "fixture must be registered"
    assert r.gates["G8_dose_basis"] is False
    assert r.total == 0.0


def test_per_ha_and_per_acre_are_basis_compatible(verify_mod):
    f = verify_mod._basis_compatible
    assert f("per_acre", "per_ha") and f("per_ha", "per_ha")
    assert not f("concentration_pct", "per_ha")
    assert not f("per_kg_seed", "per_ha")


# --- C2: PHI exact, 0 and None distinct ------------------------------------

def test_c2_phi_is_exact_with_no_tolerance(verify_mod, resources, point_row):
    """PHI is the number that decides whether residue is on food. Five days
    short is not a rounding error.

    The assertion is unconditional: an earlier version guarded it with
    `if "C2_phi" in r.checks`, which meant a fixture producing no C2 score
    made the test pass having asserted nothing.
    """
    out = good_output(point_row, phi=int(point_row[1]["phi_days"]) + 5)
    r = verify_mod.verify(out, ctx_for(verify_mod, resources,
                                       point_row[0].crop_slug, point_row[3]))
    assert "C2_phi" in r.checks, "the fixture must produce a C2 score"
    assert r.checks["C2_phi"] == 0.0
    assert_only_failed(r, "C2_phi")


def test_c2_one_day_short_also_fails(verify_mod, resources, point_row):
    out = good_output(point_row, phi=int(point_row[1]["phi_days"]) - 1)
    r = verify_mod.verify(out, ctx_for(verify_mod, resources,
                                       point_row[0].crop_slug, point_row[3]))
    assert r.checks["C2_phi"] == 0.0



# ==========================================================================
# mutations: each fails exactly one check and leaves the rest passing
# ==========================================================================

def test_mutation_dose_doubled_fails_c1(verify_mod, resources, point_row):
    """Item 1. A 2x overdose is not a rounding error."""
    row, d, _canon, query = point_row
    lo = float(d["dose_formulation_per_acre_min"])
    c = ctx_for(verify_mod, resources, row.crop_slug, query)
    r = verify_mod.verify(good_output(point_row, dose=lo * 2), c)
    assert_only_failed(r, "C1_dose")
    assert not verify_mod.verify(good_output(point_row, dose=lo * 2),
                                 c, "filter").passed


def test_mutation_dose_divided_by_the_acre_constant_fails_c1(
        verify_mod, resources, point_row):
    """Item 2. The arithmetic slip that looks like a unit conversion: the
    per-acre number stated while the basis still says per hectare. A 2.47x
    under-dose, and the basis label gives no hint that anything is wrong."""
    row, d, _canon, query = point_row
    per_ha = float(d["dose_formulation_value_min"])
    c = ctx_for(verify_mod, resources, row.crop_slug, query)
    out = good_output(point_row, basis="per_ha", dose=per_ha / 2.4711)
    r = verify_mod.verify(out, c)
    assert_only_failed(r, "C1_dose")


def test_mutation_basis_relabel_fails_c1_not_g8(
        verify_mod, resources, point_row):
    """Item 3. per_ha -> per_acre with the value unchanged.

    This fails C1, NOT G8, and that is correct: _basis_compatible treats the
    two as the same quantity, because gating on the label would reject a model
    that correctly answers in acres against a per-hectare row. C1 then compares
    against the per-acre column and catches the 2.47x.
    """
    row, d, _canon, query = point_row
    per_ha = float(d["dose_formulation_value_min"])
    c = ctx_for(verify_mod, resources, row.crop_slug, query)
    out = good_output(point_row, basis="per_acre", dose=per_ha)
    r = verify_mod.verify(out, c)
    assert r.gates["G8_dose_basis"] is True, "per_ha and per_acre are compatible"
    assert_only_failed(r, "C1_dose")
    assert not verify_mod.verify(out, c, "filter").passed


def test_mutation_escalation_flipped_fails_c4(verify_mod, resources, point_row):
    """Item 11. Over-escalation is a failure, not a safe default: a model that
    escalates on everything never trips a gate and is useless."""
    row, d, _canon, query = point_row
    c = ctx_for(verify_mod, resources, row.crop_slug, query)
    r = verify_mod.verify(good_output(point_row, escalate=True), c)
    assert_only_failed(r, "C4_escalation")
    assert "over-escalation" in " ".join(r.failures)


def test_mutation_phi_plus_five_fails_c2(verify_mod, resources, point_row):
    """Item 5, restated as a mutation with the collateral assertion."""
    row, d, _canon, query = point_row
    c = ctx_for(verify_mod, resources, row.crop_slug, query)
    r = verify_mod.verify(good_output(point_row, phi=int(d["phi_days"]) + 5), c)
    assert_only_failed(r, "C2_phi")


# --- the control: an unmutated answer must be able to score exactly 1.0 ----

def test_fully_populated_good_output_scores_exactly_one(
        verify_mod, resources, point_row):
    """Item 12. An over-strict verifier is as fatal as a permissive one — if
    nothing can reach 1.0, gate mode admits no training data at all.

    full=True populates likely_causes and non_chemical_first so C5 and C6
    fire. A bare correct answer scores 0.889 because C6 legitimately wants a
    non-chemical option where CIB&RC lists a biological one.
    """
    row, d, _canon, query = point_row
    c = ctx_for(verify_mod, resources, row.crop_slug, query)
    out = good_output(point_row, full=True)
    r = verify_mod.verify(out, c)
    assert r.total == 1.0, f"checks={r.checks} failures={r.failures}"
    assert all(v == 1.0 for v in r.checks.values()), r.checks
    assert verify_mod.verify(out, c, "gate").passed
    assert verify_mod.verify(out, c, "filter").passed


def test_bare_good_output_scores_below_one_for_a_stated_reason(
        verify_mod, resources, point_row):
    """The counterpart: the 0.889 is C6 doing its job, not a defect."""
    row, d, canon, query = point_row
    c = ctx_for(verify_mod, resources, row.crop_slug, query)
    r = verify_mod.verify(good_output(point_row, full=False), c)
    bio = any(x.biological
              for x in resources.label_db.for_pair(row.crop_slug, canon))
    if bio:
        assert r.checks["C6_non_chemical"] == 0.0
        assert r.total < 1.0
    else:
        assert r.total == 1.0


# ==========================================================================
# G3 / G6: unreachable through verify(), pinned at the pydantic layer
# ==========================================================================
# Advisory._invariants rejects all three shapes, so G2 fails first and
# verify() returns before G3 or G6 can run. The invariant is what actually
# enforces these today, so that is where they are tested. G3 and G6 stay in
# verify() as defence against a future relaxation -- see the module docstring.

def _advisory_kwargs(**kw):
    base = dict(in_scope=True, query_understood=True, chemical_options=[],
                escalate_to_expert=False)
    base.update(kw)
    return base


def _opt(phi=7):
    return {"active_ingredient": "X", "formulation": "EC",
            "dose": {"basis": "per_ha", "value_min": 1.0, "value_max": None,
                     "unit": "g", "raw": "1"},
            "phi_days": phi, "caution": "gloves"}


def test_schema_rejects_out_of_scope_with_options():
    """Item 9, at the layer that enforces it."""
    from pydantic import ValidationError
    from schema import Advisory
    with pytest.raises(ValidationError, match="out-of-scope"):
        Advisory.model_validate(
            _advisory_kwargs(in_scope=False, chemical_options=[_opt()]))


def test_schema_rejects_ununderstood_query_with_options():
    from pydantic import ValidationError
    from schema import Advisory
    with pytest.raises(ValidationError, match="ununderstood"):
        Advisory.model_validate(
            _advisory_kwargs(query_understood=False, chemical_options=[_opt()]))


def test_schema_rejects_unknown_phi_without_escalation():
    """Item 6, at the layer that enforces it."""
    from pydantic import ValidationError
    from schema import Advisory
    with pytest.raises(ValidationError, match="escalate"):
        Advisory.model_validate(
            _advisory_kwargs(chemical_options=[_opt(phi=None)]))


def test_g3_and_g6_exist_and_report_true_on_a_clean_item(verify_mod, resources):
    """Unreachable is not the same as absent: they must still run and pass."""
    c = ctx_for(verify_mod, resources, "cotton", "jassids")
    r = verify_mod.verify(advisory([]), c)
    assert r.gates["G3_empty_when_not_answering"] is True
    assert r.gates["G6_unknown_phi_escalates"] is True
    assert set(verify_mod.GATE_NAMES) >= {"G3_empty_when_not_answering",
                                          "G6_unknown_phi_escalates"}


# --- expected_answerable ---------------------------------------------------

def test_answerable_for_a_real_pair(verify_mod, resources):
    A = verify_mod.Answerability
    got = verify_mod.expected_answerable("cotton", "Helicoverpa armigera",
                                         resources.label_db)
    assert got is A.ANSWERABLE


def test_out_of_scope_crop(verify_mod, resources):
    A = verify_mod.Answerability
    assert verify_mod.expected_answerable("brinjal", "Thrips",
                                          resources.label_db) is A.OUT_OF_SCOPE_CROP


def test_pest_unknown(verify_mod, resources):
    A = verify_mod.Answerability
    assert verify_mod.expected_answerable("cotton", None,
                                          resources.label_db) is A.PEST_UNKNOWN


def test_no_registered_chemistry_for_the_refusal_slice(verify_mod, resources):
    """The four chem='none' viral targets have no label_db rows by design."""
    A = verify_mod.Answerability
    got = verify_mod.expected_answerable("onion", "Basal rot", resources.label_db)
    assert got is A.NO_REGISTERED_CHEMISTRY


def test_answerable_requires_a_trainable_row(verify_mod, resources):
    """A pair whose only rows are untrainable has ground truth too damaged to
    grade a dose against."""
    A = verify_mod.Answerability
    db = resources.label_db
    for (crop, canon), idxs in db._by_crop_pest.items():
        rows = [db.rows[i] for i in idxs]
        if rows and not any(r.trainable for r in rows):
            assert verify_mod.expected_answerable(crop, canon, db) is \
                A.NO_REGISTERED_CHEMISTRY
            return
    pytest.skip("no all-untrainable pair in this build")


# --- modes -----------------------------------------------------------------

def test_gate_mode_demands_a_perfect_total(verify_mod, resources, point_row):
    """gate rejects partial credit; score passes on gates alone.

    The conditional this test used to carry (`if g.total < 1.0`) meant it
    asserted nothing whenever the fixture happened to score perfectly. A
    deliberate C3 miss now guarantees a sub-1.0 total.
    """
    row, d, _canon, query = point_row
    c = ctx_for(verify_mod, resources, row.crop_slug, query)
    ai = sorted(row.ai_components)[0]
    imperfect = advisory([chem(ai, "definitely the wrong formulation",
                               float(d["dose_formulation_per_acre_min"]),
                               str(d["dose_formulation_unit"]), "per_acre",
                               int(d["phi_days"]))],
                         non_chemical=["remove crop residue"])
    g = verify_mod.verify(imperfect, c, "gate")
    sc = verify_mod.verify(imperfect, c, "score")
    assert sc.total == g.total
    assert 0.0 < g.total < 1.0, f"fixture must be imperfect, got {g.total}"
    assert g.passed is False, "gate mode must reject partial credit"
    assert sc.passed is True, "score mode passes on gates alone"

    perfect = good_output(point_row, full=True)
    assert verify_mod.verify(perfect, c, "gate").passed,         "gate mode must admit a genuinely perfect answer"


def test_filter_mode_runs_the_blocking_checks_not_only_gates(
        verify_mod, resources, point_row):
    """Filter mode was gates-only and that was unsafe: it passed a 3x
    overdose, because every dose and PHI comparison lives in the graded tier.

    It now runs G1-G8 plus C1 and C2 at zero tolerance. C3-C6 stay eval-only —
    a missing non-chemical option is a quality miss, not a hazard.
    """
    row, d, _canon, query = point_row
    c = ctx_for(verify_mod, resources, row.crop_slug, query)
    f = verify_mod.verify(good_output(point_row), c, "filter")
    assert set(f.checks) <= set(verify_mod.FILTER_BLOCKING_CHECKS)
    assert "C3_formulation" not in f.checks and "C6_non_chemical" not in f.checks
    assert f.total in (0.0, 1.0), "filter mode is pass/fail, not partial credit"


@pytest.mark.parametrize("label", ["3x overdose", "basis relabel", "phi+5"])
def test_filter_mode_blocks_every_dose_and_phi_hazard(
        verify_mod, resources, point_row, label):
    """The three the old gates-only filter waved through."""
    row, d, _canon, query = point_row
    c = ctx_for(verify_mod, resources, row.crop_slug, query)
    lo = float(d["dose_formulation_per_acre_min"])
    out = {
        "3x overdose": good_output(point_row, dose=lo * 3),
        "basis relabel": good_output(
            point_row, basis="per_acre",
            dose=float(d["dose_formulation_value_min"])),
        "phi+5": good_output(point_row, phi=int(d["phi_days"]) + 5),
    }[label]
    r = verify_mod.verify(out, c, "filter")
    assert r.passed is False, f"{label} must be BLOCKED at inference"
    assert r.total == 0.0


def test_filter_mode_passes_a_correct_answer(verify_mod, resources, point_row):
    """The control. An over-strict filter blocks legitimate advice."""
    row, d, _canon, query = point_row
    c = ctx_for(verify_mod, resources, row.crop_slug, query)
    r = verify_mod.verify(good_output(point_row), c, "filter")
    assert r.passed is True and r.total == 1.0


def test_filter_mode_still_blocks_gate_failures(verify_mod, resources):
    c = ctx_for(verify_mod, resources, "cotton", "jassids")
    out = advisory([chem("Monocrotophos", "36% SL", 1333.0, "g", "per_ha", 58)])
    r = verify_mod.verify(out, c, "filter")
    assert r.passed is False and r.gates["G4_restricted_ai"] is False


def test_a_check_with_no_ground_truth_cannot_block(verify_mod):
    """A check absent from `checks` means label_db had nothing to compare
    against — there is nothing to have got wrong, so it must not block."""
    assert verify_mod.FILTER_BLOCKING_CHECKS == ("C1_dose", "C2_phi")
    r = verify_mod._result({"G1_json": True}, {}, [], "filter")
    assert r.passed is True and r.total == 1.0


def test_all_three_modes_share_one_gate_verdict(verify_mod, resources):
    """One implementation, three modes: the gates cannot disagree."""
    c = ctx_for(verify_mod, resources, "cotton", "jassids")
    out = advisory([chem("Monocrotophos", "36% SL", 1333.0, "g", "per_ha", 58)])
    verdicts = [verify_mod.verify(out, c, m).gates["G4_restricted_ai"]
                for m in ("gate", "score", "filter")]
    assert verdicts == [False, False, False]


# --- exclusion, not leniency -----------------------------------------------

def test_defective_rows_exclude_rather_than_fail(verify_mod, resources,
                                                monkeypatch):
    """Shaky ground truth drops the item; it does not soften a check.

    No (crop, pest) pair in the shipped label_db has ONLY defective rows, so
    this used to skip and had never once executed an assertion. The defect is
    now injected: a real pair is marked defective for the duration of the test.
    """
    db = resources.label_db
    pair = next(((k, v) for k, v in db._by_crop_pest.items() if v), None)
    if pair is None:
        pytest.skip("empty index")
    (crop, canon), idxs = pair
    import dataclasses
    original = {i: db.rows[i] for i in idxs}
    try:
        for i in idxs:
            db.rows[i] = dataclasses.replace(db.rows[i], defective=True)
        c = ctx_for(verify_mod, resources, crop, canon)
        r = verify_mod.verify(advisory([]), c)
        assert r.excluded is True
        assert r.exclusion_reason and "defect" in r.exclusion_reason
        assert r.passed is False, "an excluded item must never pass"
    finally:
        for i, row in original.items():
            db.rows[i] = row
    # and the injection is undone
    assert all(not db.rows[i].defective for i in idxs
               if not original[i].defective)


def test_excluded_items_never_pass(verify_mod, resources):
    r = verify_mod.VerifyResult(passed=True, total=1.0, gates={}, checks={},
                                failures=[], excluded=True)
    assert r.excluded


# --- normalisation ---------------------------------------------------------

def test_normalise_ai_drops_strength_and_code(verify_mod):
    n = verify_mod.normalise_ai
    assert n("Imidacloprid 17.8% SL") == n("Imidacloprid") == {"imidacloprid"}


def test_normalise_ai_keeps_every_component_of_a_mixture(verify_mod):
    n = verify_mod.normalise_ai
    got = n("Chlorantraniliprole 4.3% + Abamectin 1.7% SC")
    assert got == {"chlorantraniliprole", "abamectin"}
    assert got != n("Chlorantraniliprole"), "half a mixture is a different product"


def test_formulation_key(verify_mod):
    k = verify_mod.formulation_key
    assert k("Chlorantraniliprole 18.50% SC") == ("SC", 18.5)
    assert k("18.5% SC") == ("SC", 18.5)
    assert k("Chlorantraniliprole 35%WG") == ("WG", 35.0)


def test_synonym_table_is_built_once_per_process(verify_mod, resources):
    """match_pest never loads a table; the constructor computes indexes."""
    assert resources.label_db.table is resources.table

# ==========================================================================
# the 2026-09-01 schema additions
# ==========================================================================

def _seed_dresser_row(resources):
    """A label_db row whose label POSITIVELY states no interval applies."""
    df = resources.label_db.df
    for i in df.index[df["phi_days"].isna() & df["phi_not_applicable"]]:
        r = resources.label_db.rows[i]
        if not r.canonicals:
            continue
        canon = sorted(r.canonicals)[0]
        if resources.label_db.for_triple(r.crop_slug, canon, r.ai_components):
            from pest_matcher import match_pest
            for surf in (str(df.at[i, "pest_or_disease"]),) + r.pest_surface_forms:
                if match_pest(r.crop_slug, surf,
                              resources.table).canonical_name == canon:
                    return r, df.loc[i], canon, surf
    pytest.skip("no resolvable seed-dresser row")


def test_seed_dresser_answer_is_now_expressible_and_correct(
        verify_mod, resources):
    """Item 14, flipped.

    Before 2026-09-01 this shape could not be constructed at all: the schema
    saw only phi_days=None and demanded escalation, so a label that positively
    says no waiting period applies forced an affirmatively wrong answer. It is
    now a complete answer, and G6 must not fire.
    """
    row, d, _canon, query = _seed_dresser_row(resources)
    ai = sorted(row.ai_components)[0]
    c = ctx_for(verify_mod, resources, row.crop_slug, query)
    opt = chem(ai, str(d["active_ingredient"]),
               float(d["dose_formulation_value_min"]),
               str(d["dose_formulation_unit"]),
               str(d["dose_formulation_basis"]), None)
    opt["phi_not_applicable"] = True
    r = verify_mod.verify(advisory([opt], escalate=False,
                                   non_chemical=["treat seed before sowing"]), c)
    assert r.gates["G6_unknown_phi_escalates"] is True
    assert r.gates["G2_schema"] is True, "the shape must now validate"
    assert not any(f.startswith("G6") for f in r.failures), r.failures


def test_seed_dresser_claim_is_verified_not_taken_on_trust(
        verify_mod, resources, point_row):
    """The model asserts phi_not_applicable, so the verifier checks it.

    point_row is a normal foliar row with a real PHI; claiming no interval
    applies to it is a fabricated safety claim.
    """
    row, d, _canon, query = point_row
    ai = sorted(row.ai_components)[0]
    c = ctx_for(verify_mod, resources, row.crop_slug, query)
    opt = chem(ai, str(d["active_ingredient"]),
               float(d["dose_formulation_per_acre_min"]),
               str(d["dose_formulation_unit"]), "per_acre", None)
    opt["phi_not_applicable"] = True
    r = verify_mod.verify(advisory([opt], escalate=False), c)
    assert r.gates["G6_unknown_phi_escalates"] is False
    assert r.total == 0.0
    assert any("does not say that" in f for f in r.failures), r.failures


def test_leaving_a_not_applicable_phi_unknown_also_fails_g6(
        verify_mod, resources):
    """The other direction: CIB&RC says no interval applies and the answer
    shrugs. That is a real loss of information, not a safe default."""
    row, d, _canon, query = _seed_dresser_row(resources)
    ai = sorted(row.ai_components)[0]
    c = ctx_for(verify_mod, resources, row.crop_slug, query)
    opt = chem(ai, str(d["active_ingredient"]),
               float(d["dose_formulation_value_min"]),
               str(d["dose_formulation_unit"]),
               str(d["dose_formulation_basis"]), None)
    r = verify_mod.verify(advisory([opt], escalate=True), c)
    assert r.gates["G6_unknown_phi_escalates"] is False


def test_phi_not_applicable_cannot_carry_a_number(verify_mod):
    """Item 7. Allowing both would recreate the overload the flag removes."""
    from pydantic import ValidationError
    from schema import ChemicalOption, Dose
    with pytest.raises(ValidationError, match="cannot carry a phi_days"):
        ChemicalOption(
            active_ingredient="X", formulation="EC",
            dose=Dose(basis="per_ha", value_min=1.0, unit="g", raw="1"),
            phi_days=15, phi_not_applicable=True, caution="gloves")


def test_phi_not_applicable_defaults_false_so_old_shapes_are_unchanged(verify_mod):
    from schema import ChemicalOption, Dose
    o = ChemicalOption(active_ingredient="X", formulation="EC",
                       dose=Dose(basis="per_ha", value_min=1.0, unit="g", raw="1"),
                       phi_days=7, caution="gloves")
    assert o.phi_not_applicable is False


def test_unstated_basis_requires_escalation(verify_mod):
    """Item 8. A chemical nobody can dose is exactly the case a human sees."""
    from pydantic import ValidationError
    from schema import Advisory, ChemicalOption, Dose
    opt = ChemicalOption(
        active_ingredient="X", formulation="EC",
        dose=Dose(basis="unstated", raw="label dose not parseable"),
        phi_days=7, caution="gloves")
    with pytest.raises(ValidationError, match="unstated"):
        Advisory(in_scope=True, query_understood=True,
                 chemical_options=[opt], escalate_to_expert=False)
    ok = Advisory(in_scope=True, query_understood=True,
                  chemical_options=[opt], escalate_to_expert=True)
    assert ok.chemical_options[0].dose.basis == "unstated"


def test_unstated_dose_needs_no_value_or_unit(verify_mod):
    from schema import Dose
    d = Dose(basis="unstated", raw="no parseable dose in CIB&RC")
    assert d.value_min is None and d.unit is None


def test_unstated_is_distinct_from_a_genuine_prose_dose(verify_mod):
    """The collision this basis exists to end: 10 rows carry prose doses, 42
    carry none, and both used to be basis='free_text' with no value."""
    from schema import Dose
    prose = Dose(basis="free_text", raw="1.0 g/plant & 22.2 to 25.6 Kg/ha")
    none_ = Dose(basis="unstated", raw="dose cell did not parse")
    assert prose.basis != none_.basis
    assert prose.value_min is none_.value_min is None


def test_unstated_claimed_on_a_row_that_has_a_dose_fails_g9(
        verify_mod, resources, point_row):
    """Item 9. Refusing an answerable question is the failure mode a
    refuse-to-guess affordance invites, so it gates rather than grades."""
    row, d, _canon, query = point_row
    ai = sorted(row.ai_components)[0]
    c = ctx_for(verify_mod, resources, row.crop_slug, query)
    opt = {"active_ingredient": ai, "formulation": str(d["active_ingredient"]),
           "dose": {"basis": "unstated", "value_min": None, "value_max": None,
                    "unit": None, "raw": "I could not determine the dose"},
           "phi_days": int(d["phi_days"]), "caution": "gloves"}
    r = verify_mod.verify(advisory([opt], escalate=True), c)
    assert r.gates["G9_unstated_dose_earned"] is False
    assert r.total == 0.0
    assert any("CIB&RC gives one" in f for f in r.failures), r.failures


def test_one_advisory_carries_both_phi_states(verify_mod, resources):
    """Item 10. cotton/Jassid registers a seed dresser AND a foliar spray, so
    one advisory legitimately needs both states at once — the reason
    phi_not_applicable sits on ChemicalOption rather than Advisory."""
    db, df = resources.label_db, resources.label_db.df
    rows = db.for_pair("cotton", "Jassid")
    seed = [r for r in rows if df.at[r.index, "phi_not_applicable"]]
    foliar = [r for r in rows
              if pd.notna(df.at[r.index, "phi_days"]) and r.trainable
              and str(df.at[r.index, "dose_formulation_basis"]) == "per_ha"]
    if not seed or not foliar:
        pytest.skip("cotton/Jassid no longer carries both PHI states")
    sd, fo = df.loc[seed[0].index], df.loc[foliar[0].index]

    seed_opt = chem(sorted(seed[0].ai_components)[0], str(sd["active_ingredient"]),
                    float(sd["dose_formulation_value_min"]),
                    str(sd["dose_formulation_unit"]),
                    str(sd["dose_formulation_basis"]), None)
    seed_opt["phi_not_applicable"] = True
    foliar_opt = chem(sorted(foliar[0].ai_components)[0],
                      str(fo["active_ingredient"]),
                      float(fo["dose_formulation_value_min"]),
                      str(fo["dose_formulation_unit"]), "per_ha",
                      int(fo["phi_days"]))

    c = ctx_for(verify_mod, resources, "cotton", "Jassids")
    out = advisory([seed_opt, foliar_opt], escalate=False,
                   causes=[{"name": "Jassids", "type": "pest",
                            "confidence": 0.9, "evidence": "hopper burn"}],
                   non_chemical=["treat seed before sowing"])
    r = verify_mod.verify(out, c)
    assert r.gates["G2_schema"] is True
    assert r.gates["G6_unknown_phi_escalates"] is True
    assert r.total == 1.0, f"checks={r.checks} failures={r.failures}"
    assert verify_mod.verify(out, c, "gate").passed
    assert verify_mod.verify(out, c, "filter").passed



# ==========================================================================
# AMBIGUOUS: candidate rows that formulation cannot separate
# ==========================================================================
# (crop, pest, a.i.) is not a unique key. A stated formulation resolves 107 of
# the 142 multi-row triples; 35 have two or more rows sharing a formulation
# code and strength, and no string the model can emit separates those. The
# verifier must not pick one — the grade would depend on row order.

def _shared_formulation_groups(resources, *, disagree_on):
    """A candidate set the verifier's own key cannot separate, still
    disagreeing on something it grades.

    Documented CIB&RC contradictions are skipped: those are excluded earlier,
    by name, and are not the ambiguity path under test.
    """
    from verify import formulation_key, strain_key
    from pest_matcher import match_pest
    db, df = resources.label_db, resources.label_db.df
    for (crop, canon, comps), idxs in db._by_triple.items():
        if len(idxs) < 2:
            continue
        groups = {}
        for i in idxs:
            groups.setdefault((db.rows[i].application_method,
                               formulation_key(df.at[i, "active_ingredient"]),
                               strain_key(df.at[i, "active_ingredient"])),
                              []).append(i)
        for _fk, g in groups.items():
            if len(g) < 2 or any(db.rows[i].contradiction for i in g):
                continue
            phis = {None if pd.isna(df.at[i, "phi_days"]) else int(df.at[i, "phi_days"])
                    for i in g}
            los = {float(df.at[i, "dose_formulation_value_min"])
                   for i in g if pd.notna(df.at[i, "dose_formulation_value_min"])}
            bases = {str(df.at[i, "dose_formulation_basis"]) for i in g}
            if disagree_on == "phi" and (len(phis) == 1 or None in phis):
                continue
            if disagree_on == "dose" and (len(los) < 2 or len(bases) > 1):
                continue
            for surf in ((str(df.at[g[0], "pest_or_disease"]),)
                         + db.rows[g[0]].pest_surface_forms):
                if match_pest(crop, surf,
                              resources.table).canonical_name == canon:
                    return crop, canon, comps, g, surf
    pytest.skip(f"no non-contradicted set disagreeing on {disagree_on}")


@pytest.fixture
def ambiguous_phi(resources):
    """A candidate set that disagrees — INJECTED, because after b1/b2/(a)/(c)
    no gradeable one survives in the shipped data.

    Every remaining real disagreement is a documented CIB&RC contradiction,
    excluded by name before the ambiguity path, and the one exception
    (Beauveria bassiana on cotton) is untrainable. That is the right end
    state, and it means these tests must construct the condition rather than
    find it — otherwise they would silently stop testing, the same way the
    overlapping-band fixture did when b2 separated it.

    A real trainable multi-row group is temporarily given a second dose.
    """
    from verify import formulation_key, strain_key
    from pest_matcher import match_pest
    db, df = resources.label_db, resources.label_db.df
    target = None
    for (crop, canon, comps), idxs in db._by_triple.items():
        groups = {}
        for i in idxs:
            groups.setdefault((db.rows[i].application_method,
                               formulation_key(df.at[i, "active_ingredient"]),
                               strain_key(df.at[i, "active_ingredient"])),
                              []).append(i)
        for _fk, g in groups.items():
            if len(g) < 2 or any(db.rows[i].contradiction for i in g):
                continue
            if not all(db.rows[i].trainable for i in g):
                continue
            if pd.isna(df.at[g[0], "dose_formulation_value_min"]):
                continue
            surf = next((x for x in ((str(df.at[g[0], "pest_or_disease"]),)
                                     + db.rows[g[0]].pest_surface_forms)
                         if match_pest(crop, x,
                                       resources.table).canonical_name == canon),
                        None)
            if surf:
                target = (crop, canon, comps, g, surf)
                break
        if target:
            break
    if target is None:
        pytest.skip("no trainable multi-row group to inject into")

    crop, canon, comps, g, surf = target
    victim = g[-1]
    original = df.at[victim, "dose_formulation_value_min"]
    df.at[victim, "dose_formulation_value_min"] = float(original) * 20 + 1
    try:
        yield target
    finally:
        df.at[victim, "dose_formulation_value_min"] = original


def _answer(resources, crop, comps, rows, surf, *, dose=None, phi=None,
            escalate=None):
    df = resources.label_db.df
    d = df.loc[rows[0]]
    stated_phi = ((None if pd.isna(d["phi_days"]) else int(d["phi_days"]))
                  if phi is None else phi)
    if escalate is None:
        # the schema forbids an unknown PHI without escalation
        escalate = stated_phi is None
    # the FULL label string: naming one component of a co-formulation is a
    # different registered product, and G5 rejects it correctly
    return advisory(
        [chem(str(d["active_ingredient"]), str(d["active_ingredient"]),
              float(d["dose_formulation_value_min"]) if dose is None else dose,
              str(d["dose_formulation_unit"]),
              str(d["dose_formulation_basis"]) or "per_ha", stated_phi)],
        escalate=escalate,
        causes=[{"name": surf, "type": "pest", "confidence": 0.9,
                 "evidence": "observed"}],
        non_chemical=["remove and destroy crop residue"])


# --- the three modes must differ ------------------------------------------

def test_ambiguous_phi_excludes_the_item_in_gate_mode(
        verify_mod, resources, ambiguous_phi):
    """Ground truth too ambiguous to grade must not become a training example
    — but an exclusion is not a failure, and the two stay distinguishable."""
    crop, _canon, comps, rows, surf = ambiguous_phi
    c = ctx_for(verify_mod, resources, crop, surf)
    r = verify_mod.verify(_answer(resources, crop, comps, rows, surf), c, "gate")
    assert r.excluded is True
    assert "C1_dose" in r.ambiguous
    assert r.exclusion_reason and "ambiguous ground truth" in r.exclusion_reason
    assert r.passed is False
    assert all(r.gates.values()), "exclusion is not a gate failure"


def test_ambiguous_phi_is_reported_separately_in_score_mode(
        verify_mod, resources, ambiguous_phi):
    """Ambiguous ground truth is our defect, not the model's. It must neither
    depress nor inflate the metric, so C2 leaves the denominator entirely."""
    crop, _canon, comps, rows, surf = ambiguous_phi
    c = ctx_for(verify_mod, resources, crop, surf)
    r = verify_mod.verify(_answer(resources, crop, comps, rows, surf), c, "score")
    assert r.ambiguous == ["C1_dose"]
    assert "C1_dose" not in r.checks, "must not be scored 0.0"
    assert r.excluded is False, "score mode reports, it does not exclude"
    assert r.total == 1.0, "the remaining checks all pass, so the score is 1.0"


def test_ambiguous_phi_blocks_in_filter_mode(
        verify_mod, resources, ambiguous_phi):
    """'I cannot determine the correct interval for this recommendation' is
    exactly when a farmer should not receive it."""
    crop, _canon, comps, rows, surf = ambiguous_phi
    c = ctx_for(verify_mod, resources, crop, surf)
    r = verify_mod.verify(_answer(resources, crop, comps, rows, surf), c, "filter")
    assert r.passed is False
    assert r.total == 0.0
    assert "C1_dose" in r.ambiguous


def test_the_three_modes_resolve_ambiguity_differently(
        verify_mod, resources, ambiguous_phi):
    """The whole point: one detection, three correct answers."""
    crop, _canon, comps, rows, surf = ambiguous_phi
    c = ctx_for(verify_mod, resources, crop, surf)
    out = _answer(resources, crop, comps, rows, surf)
    g, s, f = (verify_mod.verify(out, c, m) for m in ("gate", "score", "filter"))
    assert (g.excluded, s.excluded, f.excluded) == (True, False, False)
    assert (g.passed, s.passed, f.passed) == (False, True, False)
    assert g.ambiguous == s.ambiguous == f.ambiguous == ["C1_dose"]


# --- requirement 4: consistency with EVERY candidate is not ambiguity ------

def test_an_answer_consistent_with_every_candidate_is_correct(
        verify_mod, resources):
    """Requirement 4, three ways.

    Consistent with EVERY candidate is correct — the candidates disagree about
    which product was meant, not about whether this answer is right.
    Consistent with NONE is wrong under every reading, and ambiguity must not
    rescue it. Only a mixture is ungradeable.

    Asserted on the fold plus a real remaining ambiguous group. No label_db
    candidate set has OVERLAPPING dose bands any more: the one that did
    (gram / NPV, 250-500 x3 and 500-1000) was four separately registered
    strains, and the b2 strain key correctly separated them.
    """
    f, A = verify_mod._consensus, verify_mod.AMBIGUOUS
    assert f([True, True, True]) is True       # inside every band
    assert f([False, False]) is False          # outside every band
    assert f([True, False]) is A               # inside some

    ok = verify_mod._dose_value_ok
    assert ok(500.0, 250.0, 500.0) and ok(500.0, 500.0, 1000.0)
    assert f([ok(500.0, 250.0, 500.0), ok(500.0, 500.0, 1000.0)]) is True
    assert f([ok(300.0, 250.0, 500.0), ok(300.0, 500.0, 1000.0)]) is A
    assert f([ok(5000.0, 250.0, 500.0), ok(5000.0, 500.0, 1000.0)]) is False


def test_a_wrong_answer_is_not_rescued_by_ambiguity(
        verify_mod, resources, ambiguous_phi):
    """On a real ambiguous group: an interval matching NO candidate fails C2
    outright rather than being excused as ungradeable."""
    crop, _canon, comps, rows, surf = ambiguous_phi
    c = ctx_for(verify_mod, resources, crop, surf)
    r = verify_mod.verify(
        _answer(resources, crop, comps, rows, surf, dose=999999.0), c, "score")
    assert r.checks.get("C1_dose") == 0.0
    assert "C1_dose" not in r.ambiguous


def test_alternate_rate_expressions_are_not_a_disagreement(
        verify_mod, resources):
    """CIB&RC states one claim on two bases — Azoxystrobin 8.3% + Mancozeb
    66.7% WG on grape is 1500 g/ha AND 0.30%, same pest, same PHI 21; Metiram
    70% WG on pomegranate is 200 g/ha AND 150-200 per 100 L. Those rows are
    alternate EXPRESSIONS of one registration, not competing claims, so a
    model stating either basis must grade cleanly."""
    from pest_matcher import match_pest
    db, df = resources.label_db, resources.label_db.df
    checked = 0
    for i_ha, i_alt in ((516, 517), (441, 445)):
        if i_ha not in df.index or i_alt not in df.index:
            continue
        d, row = df.loc[i_ha], db.rows[i_ha]
        if not row.canonicals:
            continue
        canon = sorted(row.canonicals)[0]
        surf = next((s for s in ((str(d["pest_or_disease"]),)
                                 + row.pest_surface_forms)
                     if match_pest(d["crop_slug"], s,
                                   resources.table).canonical_name == canon), None)
        if surf is None:
            continue
        c = ctx_for(verify_mod, resources, d["crop_slug"], surf)
        for src in (i_ha, i_alt):
            out = advisory([chem(sorted(row.ai_components)[0],
                                 str(d["active_ingredient"]),
                                 float(df.at[src, "dose_formulation_value_min"]),
                                 str(df.at[src, "dose_formulation_unit"]),
                                 str(df.at[src, "dose_formulation_basis"]),
                                 int(d["phi_days"]))],
                           non_chemical=["remove residue"])
            r = verify_mod.verify(out, c)
            assert not r.ambiguous, (
                f"row {src}: alternate rate expression reported ambiguous: "
                f"{r.ambiguous}")
            assert r.gates["G8_dose_basis"] is True
            assert r.checks.get("C1_dose") in (None, 1.0)
            checked += 1
    assert checked >= 2, "neither alternate-expression pair was exercised"


def test_consensus_fold(verify_mod):
    """The three-way fold, in isolation."""
    f, A = verify_mod._consensus, verify_mod.AMBIGUOUS
    assert f([True, True]) is True
    assert f([False, False]) is False
    assert f([True, False]) is A
    assert f([None, None]) is None
    assert f([True, None]) is True, "candidates without ground truth abstain"
    assert f([]) is None


def test_narrowing_returns_the_candidate_set_never_one_arbitrary_row(
        verify_mod, resources, ambiguous_phi):
    """The rows[0] fallback is gone: narrowing returns what survives."""
    crop, _canon, comps, rows, _surf = ambiguous_phi
    db = resources.label_db
    cands = db.for_triple(crop, _canon, comps)
    d = db.df.loc[rows[0]]
    kept = verify_mod._narrow_candidates(cands, str(d["active_ingredient"]))
    assert isinstance(kept, list)
    assert len(kept) >= 2, "a formulation that cannot separate them keeps both"


def test_exclusion_and_failure_remain_distinguishable(
        verify_mod, resources, ambiguous_phi, point_row):
    """Both have passed=False; only one means 'do not train on this'."""
    crop, _canon, comps, rows, surf = ambiguous_phi
    amb = verify_mod.verify(
        _answer(resources, crop, comps, rows, surf),
        ctx_for(verify_mod, resources, crop, surf), "gate")
    row, d, _c, query = point_row
    wrong = verify_mod.verify(
        good_output(point_row, dose=float(d["dose_formulation_per_acre_min"]) * 3),
        ctx_for(verify_mod, resources, row.crop_slug, query), "gate")
    assert amb.passed is wrong.passed is False
    assert amb.excluded is True and wrong.excluded is False
    assert amb.ambiguous and not wrong.ambiguous



# ==========================================================================
# multi-row sets that currently AGREE — silent ambiguity if that changes
# ==========================================================================

def _multi_row_sets(resources):
    """Every candidate set a formulation string cannot separate, split by
    whether its rows agree on the two things the verifier checks."""
    from verify import formulation_key, strain_key
    db, df = resources.label_db, resources.label_db.df

    def state(i):
        v = df.at[i, "phi_days"]
        phi = ("NA" if bool(df.at[i, "phi_not_applicable"])
               else None if pd.isna(v) else int(v))
        lo = df.at[i, "dose_formulation_value_min"]
        hi = df.at[i, "dose_formulation_value_max"]
        return (phi,
                None if pd.isna(lo) else float(lo),
                None if pd.isna(hi) else float(hi))

    agree, disagree = {}, {}
    for (crop, canon, comps), idxs in db._by_triple.items():
        groups = {}
        for i in idxs:
            # mirror the verifier's narrowing key: method THEN formulation
            groups.setdefault(
                (db.rows[i].application_method,
                 formulation_key(df.at[i, "active_ingredient"]),
                 strain_key(df.at[i, "active_ingredient"])), []).append(i)
        for fk, g in groups.items():
            if len(g) < 2:
                continue
            key = (crop, canon, fk, tuple(sorted(g)))
            (agree if len({state(i) for i in g}) == 1 else disagree)[key] = g
    return agree, disagree


def test_multi_row_sets_that_agree_today_still_agree(resources):
    """The gap the ambiguity work left open.

    Some candidate sets have rows a formulation cannot separate but which
    state the SAME pre-harvest interval and the SAME dose. They grade fine
    today — `_consensus` sees one answer and never reports ambiguity. If a
    future label_db build makes one of them disagree it silently becomes
    ambiguous, and the affected rows drop out of the trainable set with
    nothing failing to say so. This is the alarm.

    A failure here is not necessarily a regression: it may be a genuine
    CIB&RC revision. Re-classify the set per
    reports/phase6_stepC_ambiguity_investigation.md before changing a count.
    """
    agree, disagree = _multi_row_sets(resources)
    agree_groups = {tuple(sorted(g)) for g in agree.values()}
    disagree_groups = {tuple(sorted(g)) for g in disagree.values()}
    assert (len(agree), len(agree_groups)) == (7, 3), (
        f"agreeing multi-row sets changed: {len(agree)} triple-keys over "
        f"{len(agree_groups)} row groups (was 7 over 3 after b1+b2+(a); "
        f"8 over 5 before). A set that starts disagreeing becomes silently "
        f"ambiguous."
    )
    assert (len(disagree), len(disagree_groups)) == (15, 8), (
        f"ambiguous sets changed: {len(disagree)} triple-keys over "
        f"{len(disagree_groups)} row groups (was 15 keys over 8 groups "
        f"after b1+b2+(a); 17 groups before). See "
        f"reports/phase6_stepC_ambiguity_investigation.md."
    )


def test_agreeing_sets_are_not_reported_ambiguous(verify_mod, resources):
    """The agreeing sets must grade normally, not be excluded — an over-eager
    ambiguity check would silently shrink the training set.

    All five carry no pre-harvest interval, so the answer escalates; the
    assertion is about ambiguity, not about passing every gate.
    """
    from pest_matcher import match_pest
    agree, _ = _multi_row_sets(resources)
    df = resources.label_db.df
    checked = 0
    for (crop, canon, _fk, _rows), g in agree.items():
        d = df.loc[g[0]]
        if pd.isna(d["dose_formulation_value_min"]):
            continue
        surf = next(
            (s for s in ((str(d["pest_or_disease"]),)
                         + resources.label_db.rows[g[0]].pest_surface_forms)
             if match_pest(crop, s, resources.table).canonical_name == canon),
            None)
        if surf is None:
            continue
        comps = resources.label_db.rows[g[0]].ai_components
        phi = None if pd.isna(d["phi_days"]) else int(d["phi_days"])
        out = advisory([chem(sorted(comps)[0], str(d["active_ingredient"]),
                             float(d["dose_formulation_value_min"]),
                             str(d["dose_formulation_unit"]),
                             str(d["dose_formulation_basis"]), phi)],
                       escalate=phi is None,
                       non_chemical=["remove crop residue"])
        r = verify_mod.verify(out, ctx_for(verify_mod, resources, crop, surf))
        assert not r.ambiguous, (
            f"{crop}/{canon} agrees on PHI and dose but was reported "
            f"ambiguous: {r.ambiguous}")
        assert r.excluded is False, f"{crop}/{canon} must not be excluded"
        checked += 1
    assert checked >= 1, (
        f"only {checked} agreeing sets were exercised — the guard would pass "
        f"vacuously")


def test_the_investigated_ambiguous_groups_are_still_present(resources):
    """Row groups classified in the Step C investigation. If one disappears,
    the classification for it needs revisiting rather than silently lapsing."""
    _agree, disagree = _multi_row_sets(resources)
    groups = {tuple(sorted(g)) for g in disagree.values()}
    for expected, label in [
        ((87, 88), "Diafenthiuron 50% WP, cotton — CIB&RC states two claims"),
        ((131, 132), "Flubendiamide 20% WG, tomato — strength-inconsistent row"),
        ((35, 38), "Chlorantraniliprole 18.5% SC, tur — Pigeon pea vs Red Gram"),
        ((464, 468), "Pyriofenone 18% SC, grape — same values, PHI 7 vs 5"),
    ]:
        assert expected in groups, f"row group {expected} ({label}) is gone"


def test_documented_contradictions_are_excluded_by_name(verify_mod, resources):
    """The 5 class-(c) groups: CIB&RC states two values and we cannot resolve
    it. They are excluded with a reason naming the source pages, so they read
    as a documented ceiling rather than an unfixed bug."""
    from pest_matcher import match_pest
    db, df = resources.label_db, resources.label_db.df
    contradicted = [r for r in db.rows if r.contradiction]
    assert len(contradicted) == 10, f"expected 10 rows in 5 groups, got {len(contradicted)}"
    assert len({r.contradiction.split(":")[0] for r in contradicted}) == 5

    checked = 0
    for row in contradicted:
        d = df.loc[row.index]
        if not row.canonicals or pd.isna(d["dose_formulation_value_min"]):
            continue
        canon = sorted(row.canonicals)[0]
        surf = next((x for x in ((str(d["pest_or_disease"]),) + row.pest_surface_forms)
                     if match_pest(row.crop_slug, x,
                                   resources.table).canonical_name == canon), None)
        if surf is None:
            continue
        phi = None if pd.isna(d["phi_days"]) else int(d["phi_days"])
        out = advisory([chem(str(d["active_ingredient"]), str(d["active_ingredient"]),
                             float(d["dose_formulation_value_min"]),
                             str(d["dose_formulation_unit"]),
                             str(d["dose_formulation_basis"]), phi)],
                       escalate=phi is None, non_chemical=["remove residue"])
        r = verify_mod.verify(out, ctx_for(verify_mod, resources,
                                           row.crop_slug, surf), "gate")
        assert r.excluded is True, f"row {row.index} not excluded"
        assert "documented CIB&RC contradiction" in r.exclusion_reason
        assert r.passed is False
        checked += 1
    assert checked >= 4, f"only {checked} contradiction rows exercised"


def test_contradiction_ledger_names_its_evidence(verify_mod):
    """Each reason must cite the source file and page, or it is an assertion
    rather than a record."""
    led = verify_mod.load_contradictions()
    assert len(led) == 10
    for key, reason in led.items():
        assert any(f in reason for f in ("insecticides p", "fungicides p")), reason
        assert ":" in reason, "reason must carry its group_id"


def test_one_contradicted_product_does_not_sink_the_whole_pair(
        verify_mod, resources):
    """cotton/Whitefly has a contradicted Diafenthiuron claim and many clean
    ones. Only the contradicted product may be excluded."""
    db, df = resources.label_db, resources.label_db.df
    rows = db.for_pair("cotton", "Whitefly")
    clean = [r for r in rows
             if not r.contradiction and r.trainable and not r.defective
             and str(df.at[r.index, "dose_formulation_basis"]) == "per_ha"
             and pd.notna(df.at[r.index, "phi_days"])]
    assert any(r.contradiction for r in rows), "fixture pair must include one"
    assert clean, "fixture pair must also have a clean option"
    d = df.loc[clean[0].index]
    out = advisory([chem(str(d["active_ingredient"]), str(d["active_ingredient"]),
                         float(d["dose_formulation_value_min"]),
                         str(d["dose_formulation_unit"]), "per_ha",
                         int(d["phi_days"]))],
                   non_chemical=["remove residue"])
    r = verify_mod.verify(out, ctx_for(verify_mod, resources, "cotton", "Whitefly"))
    assert r.excluded is False, r.exclusion_reason
