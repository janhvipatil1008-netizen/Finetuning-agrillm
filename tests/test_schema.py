"""
test_schema.py — pins the safety invariants. Run before every commit that
touches schema.py. If any of these stop failing, a guardrail has been lost.

    pytest tests/test_schema.py -q
"""

import pytest
from pydantic import ValidationError

from schema import Advisory, ChemicalOption, Dose


def _chem(**kw):
    base = dict(
        active_ingredient="X",
        formulation="EC",
        dose=Dose(basis="per_acre", value_min=100, unit="ml", raw="250 ml/ha"),
        phi_days=7,
        caution="wear gloves",
    )
    base.update(kw)
    return ChemicalOption(**base)


# --- doses -----------------------------------------------------------------

def test_orchard_per_litre_dose_is_representable():
    """The case the original string schema could not express."""
    d = Dose(basis="per_litre_water", value_min=2.5, unit="ml", raw="2.5 ml/l")
    assert d.basis == "per_litre_water"


def test_concentration_cannot_wear_an_area_basis():
    """0.025% labelled per_acre is the dangerous confusion. Must not construct."""
    with pytest.raises(ValidationError):
        Dose(basis="per_acre", value_min=0.025, unit="%", raw="0.025%")


def test_concentration_requires_percent_unit():
    with pytest.raises(ValidationError):
        Dose(basis="concentration_pct", value_min=0.025, unit="ml", raw="0.025%")


def test_numeric_basis_requires_unit():
    with pytest.raises(ValidationError):
        Dose(basis="per_acre", value_min=100, raw="100")


def test_free_text_dose_needs_no_numbers():
    d = Dose(basis="free_text", raw="@ 20 gm/kg of seeds, then 5 kg/ha in furrow")
    assert d.value_min is None


def test_inverted_range_rejected():
    with pytest.raises(ValidationError):
        Dose(basis="per_ha", value_min=300, value_max=250, unit="g", raw="300-250")


# --- pre-harvest interval --------------------------------------------------

def test_zero_phi_is_a_real_value_not_missing():
    """Polyoxin D on fungicides p23 has a genuine zero-day PHI."""
    a = Advisory(in_scope=True, query_understood=True,
                 chemical_options=[_chem(phi_days=0)], escalate_to_expert=False)
    assert a.chemical_options[0].phi_days == 0


def test_unknown_phi_forces_escalation():
    with pytest.raises(ValidationError):
        Advisory(in_scope=True, query_understood=True,
                 chemical_options=[_chem(phi_days=None)], escalate_to_expert=False)


def test_unknown_phi_allowed_when_escalating():
    a = Advisory(in_scope=True, query_understood=True,
                 chemical_options=[_chem(phi_days=None)], escalate_to_expert=True)
    assert a.escalate_to_expert


# --- advisory-level guardrails ---------------------------------------------

def test_out_of_scope_cannot_prescribe():
    with pytest.raises(ValidationError):
        Advisory(in_scope=False, query_understood=True,
                 chemical_options=[_chem()], escalate_to_expert=True)


def test_ununderstood_query_cannot_prescribe():
    with pytest.raises(ValidationError):
        Advisory(in_scope=True, query_understood=False,
                 chemical_options=[_chem()], escalate_to_expert=True)


def test_no_chemistry_case_is_a_complete_answer():
    """Viral disease: empty chemical_options, vector control, no escalation."""
    a = Advisory(
        in_scope=True, query_understood=True,
        likely_causes=[{"name": "leaf curl virus", "type": "disease",
                        "confidence": 0.75, "evidence": "upward cupping, whitefly present"}],
        non_chemical_first=["remove and destroy infected plants",
                            "control whitefly as the vector"],
        chemical_options=[], safety=[], escalate_to_expert=False)
    assert a.chemical_options == []


# --- spray volume ----------------------------------------------------------

def test_spray_volume_needs_both_bounds():
    with pytest.raises(ValidationError):
        _chem(spray_volume_min_l_per_acre=150)


def test_spray_volume_range_ok():
    c = _chem(spray_volume_min_l_per_acre=150, spray_volume_max_l_per_acre=200)
    assert c.spray_volume_max_l_per_acre == 200
