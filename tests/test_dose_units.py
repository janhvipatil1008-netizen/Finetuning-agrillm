"""test_dose_units.py — pins the per-hectare -> per-acre derivation.

The load-bearing assertion is the negative one: a dose stated as a
concentration, a per-litre dilution or a seed-treatment rate has NO per-acre
equivalent, and inventing one would put an area figure on a non-area basis —
the exact confusion schema.Dose's validator exists to reject.

The second half re-derives the shipped label_db columns from their sources
and fails if any row disagrees, so a script that patches a dose without
recomputing gets caught here rather than in a farmer's tank.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dose_units import (  # noqa: E402
    ACRES_PER_HECTARE,
    PER_ACRE_COLUMNS,
    PER_ACRE_DECIMALS,
    add_per_acre_columns,
    per_ha_to_per_acre,
)

LABEL_DB = ROOT / "data" / "final" / "label_db.parquet"

NON_AREA_BASES = ["concentration_pct", "per_litre_water", "per_kg_seed",
                  "free_text", ""]


# --- the unit function -----------------------------------------------------

def test_constant_is_the_agreed_one():
    assert ACRES_PER_HECTARE == 2.4711


def test_per_ha_converts():
    assert per_ha_to_per_acre(3750.0, "per_ha") == 1517.5428
    assert per_ha_to_per_acre(2.4711, "per_ha") == 1.0


@pytest.mark.parametrize("basis", NON_AREA_BASES)
def test_non_area_basis_returns_none(basis):
    """A concentration or a per-litre rate does not scale with area."""
    assert per_ha_to_per_acre(0.025, basis) is None
    assert per_ha_to_per_acre(2500.0, basis) is None


def test_unknown_basis_returns_none():
    assert per_ha_to_per_acre(100.0, "per_tree") is None
    assert per_ha_to_per_acre(100.0, None) is None


def test_missing_value_returns_none():
    assert per_ha_to_per_acre(None, "per_ha") is None
    assert per_ha_to_per_acre(float("nan"), "per_ha") is None


def test_zero_converts_and_is_not_treated_as_missing():
    assert per_ha_to_per_acre(0.0, "per_ha") == 0.0


# --- the dataframe helper --------------------------------------------------

def _frame():
    return pd.DataFrame({
        "dose_ai_basis": ["per_ha", "concentration_pct", "per_kg_seed", ""],
        "dose_ai_value_min": [1000.0, 0.025, 4.0, None],
        "dose_ai_value_max": [2000.0, None, None, None],
        "dose_formulation_basis": ["per_ha", "per_litre_water", "free_text", "per_ha"],
        "dose_formulation_value_min": [3750.0, 2.5, None, 500.0],
        "dose_formulation_value_max": [None, None, None, 600.0],
    })


def test_add_per_acre_columns_only_fills_per_ha_rows():
    df = add_per_acre_columns(_frame())
    assert df["dose_formulation_per_acre_min"].tolist()[:1] == [1517.5428]
    assert pd.isna(df.at[1, "dose_formulation_per_acre_min"])   # per_litre_water
    assert pd.isna(df.at[2, "dose_formulation_per_acre_min"])   # free_text
    assert df.at[3, "dose_formulation_per_acre_min"] == 202.3390
    assert pd.isna(df.at[1, "dose_ai_per_acre_min"])            # concentration_pct
    assert pd.isna(df.at[2, "dose_ai_per_acre_min"])            # per_kg_seed


def test_derived_column_sits_next_to_its_source():
    cols = list(add_per_acre_columns(_frame()).columns)
    assert cols.index("dose_formulation_per_acre_min") == \
        cols.index("dose_formulation_value_min") + 1


def test_recomputing_is_idempotent():
    once = add_per_acre_columns(_frame())
    twice = add_per_acre_columns(once.copy())
    pd.testing.assert_frame_equal(once, twice)


def test_recompute_picks_up_a_changed_source_value():
    """The staleness guard: patch a dose, recompute, get the new figure."""
    df = add_per_acre_columns(_frame())
    assert df.at[0, "dose_formulation_per_acre_min"] == 1517.5428
    df.at[0, "dose_formulation_value_min"] = 2.4711
    add_per_acre_columns(df)
    assert df.at[0, "dose_formulation_per_acre_min"] == 1.0


def test_empty_frame_still_gains_the_columns():
    df = add_per_acre_columns(pd.DataFrame())
    for _p, lo, hi in PER_ACRE_COLUMNS:
        assert lo in df.columns and hi in df.columns


# --- the shipped file ------------------------------------------------------

@pytest.fixture(scope="module")
def label_db():
    if not LABEL_DB.exists():
        pytest.skip("label_db.parquet not built (gitignored; run "
                    "tools/build_label_db.py then phase5_stepB)")
    return pd.read_parquet(LABEL_DB)


@pytest.mark.parametrize("prefix,lo,hi", PER_ACRE_COLUMNS)
def test_shipped_non_per_ha_rows_have_null_per_acre(label_db, prefix, lo, hi):
    """THE assertion this change exists to guarantee."""
    off_basis = label_db[prefix + "_basis"] != "per_ha"
    assert label_db.loc[off_basis, lo].notna().sum() == 0
    assert label_db.loc[off_basis, hi].notna().sum() == 0


@pytest.mark.parametrize("prefix,lo,hi", PER_ACRE_COLUMNS)
def test_shipped_per_ha_rows_all_have_a_per_acre_value(label_db, prefix, lo, hi):
    on_basis = label_db[prefix + "_basis"] == "per_ha"
    has_min = label_db[prefix + "_value_min"].notna()
    assert label_db.loc[on_basis & has_min, lo].isna().sum() == 0


@pytest.mark.parametrize("prefix,lo,hi", PER_ACRE_COLUMNS)
def test_shipped_per_acre_columns_are_not_stale(label_db, prefix, lo, hi):
    """Re-derive from source; every row must agree. Catches a script that
    patched a dose value and forgot to call add_per_acre_columns."""
    for src, dest in ((prefix + "_value_min", lo), (prefix + "_value_max", hi)):
        expected = [per_ha_to_per_acre(v, b)
                    for v, b in zip(label_db[src], label_db[prefix + "_basis"])]
        got = label_db[dest]
        for i, (e, g) in enumerate(zip(expected, got)):
            if e is None:
                assert pd.isna(g), f"{dest} row {i}: expected NULL, got {g}"
            else:
                assert g == pytest.approx(e, abs=10 ** -PER_ACRE_DECIMALS), \
                    f"{dest} row {i}: expected {e}, got {g}"


def test_shipped_per_ha_columns_were_left_untouched(label_db):
    """The originals are the audit trail; the derivation must not edit them."""
    assert (label_db.loc[label_db.dose_formulation_basis == "per_ha",
                         "dose_formulation_value_min"] > 0).all()
    ratio = (label_db["dose_formulation_value_min"] /
             label_db["dose_formulation_per_acre_min"]).dropna()
    # Relative, not absolute: rounding the derived value to PER_ACRE_DECIMALS
    # costs most at the smallest dose in the corpus (0.04 per ha -> 0.0162,
    # ratio 2.4691). That is 7.9e-4 relative, four orders inside the +/-8%
    # dose band, and the largest deviation in the file.
    assert ((ratio - ACRES_PER_HECTARE).abs() / ACRES_PER_HECTARE < 1e-3).all()


def test_units_are_shared_not_duplicated(label_db):
    """The conversion is unit-preserving, so there is no per-acre unit column
    and every per_ha row carries a mass or volume unit, never '%'."""
    assert "dose_formulation_per_acre_unit" not in label_db.columns
    per_ha = label_db.dose_formulation_basis == "per_ha"
    assert set(label_db.loc[per_ha, "dose_formulation_unit"]) <= {"g", "ml", "kg", "l"}
