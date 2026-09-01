"""dose_units.py — derive per-acre dose columns from the per-hectare ones.

CIB&RC prints every area-based dose per hectare; label_db carries it that way,
verbatim. Maharashtra farmers work in acres, so `schema.Basis` offers
`per_acre` as an answer basis. This module is the one place that bridges the
two, so no consumer ever divides by hand and no two consumers pick different
constants.

WHAT IS AND IS NOT CONVERTIBLE
==============================

Only `per_ha` converts. The other five bases in this corpus are not areas and
have no per-acre equivalent:

    concentration_pct   0.025% is a dilution strength; it does not scale with
                        the area you spray.
    per_litre_water     2.5 ml/l likewise — it describes the tank, not the field.
    per_kg_seed         seed treatment scales with seed mass, not with land.
    free_text           prose ("1.0 g/plant & 22.2 to 25.6 Kg/ha"); no single
                        number to convert.
    "" (empty)          the dose never parsed; there is nothing to convert.

For all of those the per-acre columns stay NULL. That is the whole point:
`schema.Dose`'s own validator exists to stop a concentration wearing an area
basis, and manufacturing "0.025 per acre" here would smuggle in exactly the
confusion that validator was written to prevent. A NULL is a correct answer.

THE CONSTANT
============

1 ha = 2.4711 acres, so per_acre = per_ha / 2.4711. The exact figure is
2.471053814..., and the fourth-decimal truncation costs 2e-5 relative — five
thousand times inside the +/-5% dose tolerance the verifier design settles on
(reports/phase6_stepA_verifier_design.md, section 7). Pinned here as one
named constant rather than repeated at call sites.

UNITS ARE UNCHANGED
===================

The conversion is unit-preserving: 3750 g/ha is 1517.5433 g/acre. The
per-acre columns therefore share `dose_*_unit` with their per-hectare source
and no second unit column exists. Every per_ha row in the corpus carries a
mass or volume unit (g, ml, kg, l) — never '%', which `schema.Dose` forbids
on an area basis anyway.

STALENESS
=========

These are DERIVED columns, so they are only correct while they agree with the
values they came from. `add_per_acre_columns` is therefore called at the end
of every script that writes label_db — tools/build_label_db.py and
tools/phase5_stepB_resolve_formulation.py, which patches dose values after the
build — and tests/test_dose_units.py re-derives them from the shipped file and
fails if any row disagrees. Recompute; never hand-edit.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

__all__ = [
    "ACRES_PER_HECTARE",
    "AREA_BASES",
    "PER_ACRE_COLUMNS",
    "PER_ACRE_DECIMALS",
    "add_per_acre_columns",
    "per_ha_to_per_acre",
]

# 1 hectare = 2.4711 acres (exact: 2.471053814...).
ACRES_PER_HECTARE = 2.4711

# The only basis that denotes an area, and so the only one that converts.
AREA_BASES = frozenset({"per_ha"})

# Derived values are rounded so the CSV does not print seventeen digits of
# false precision. At the smallest dose in the corpus (0.04 per ha) this costs
# 8e-4 relative; at a typical one, 1e-8. Both are noise against a +/-5% band.
PER_ACRE_DECIMALS = 4

# (source prefix, derived min column, derived max column)
PER_ACRE_COLUMNS = [
    ("dose_ai", "dose_ai_per_acre_min", "dose_ai_per_acre_max"),
    ("dose_formulation",
     "dose_formulation_per_acre_min", "dose_formulation_per_acre_max"),
]


def per_ha_to_per_acre(value: Optional[float], basis: Optional[str]) -> Optional[float]:
    """Convert one per-hectare figure to per acre, or return None.

    Returns None — never a number — for any basis that is not an area, for a
    missing value, and for a missing basis. Callers must treat None as "no
    per-acre figure exists", not as zero.
    """
    if basis is None or basis not in AREA_BASES:
        return None
    if value is None or pd.isna(value):
        return None
    return round(float(value) / ACRES_PER_HECTARE, PER_ACRE_DECIMALS)


def add_per_acre_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add (or recompute) the four derived per-acre columns, in place.

    Each derived column is inserted immediately after the per-hectare column
    it comes from, so the CSV reads source-then-derivative. Recomputing is
    idempotent and is the supported way to refresh them after any script
    changes a dose value.
    """
    if not len(df):
        for _prefix, lo, hi in PER_ACRE_COLUMNS:
            for col in (lo, hi):
                if col not in df.columns:
                    df[col] = pd.Series(dtype="float64")
        return df

    for prefix, lo_col, hi_col in PER_ACRE_COLUMNS:
        basis = df[f"{prefix}_basis"]
        for src, dest in ((f"{prefix}_value_min", lo_col),
                          (f"{prefix}_value_max", hi_col)):
            derived = [
                per_ha_to_per_acre(v, b)
                for v, b in zip(df[src], basis)
            ]
            series = pd.Series(derived, index=df.index, dtype="float64")
            if dest in df.columns:
                df[dest] = series
            else:
                df.insert(df.columns.get_loc(src) + 1, dest, series)

    # Keep min/max adjacent: value_min, per_acre_min, value_max, per_acre_max
    # is the insertion order above and is what we want.
    return df
