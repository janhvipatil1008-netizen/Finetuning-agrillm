"""phase6_stepD_strength_check.py — does dose_ai == dose_formulation x strength?

REPORT ONLY. Writes nothing to data/.

A CIB&RC row states the same dose twice: as active ingredient and as
formulated product. The two are tied by the strength printed in the chemical
header -- 250 g of a 20% WG is 50 g a.i. When they disagree, the row cannot
belong to the product whose header it sits under, which is the signature of
header mis-attribution across a page or table boundary.

This found the Flubendiamide defect in Step C: 48 a.i. / 100 formulation is
impossible for a 20% product, and that exact triple appears verbatim under
'Flubendiamide 39.35% w/w SC' on the same page. Nothing else in the pipeline
looks for this, and it needs no external source.

TOLERANCE. CIB&RC rounds its own arithmetic, so a flat equality test is
useless. 10% relative with a 1 g floor absorbs it. Mixtures are skipped: their
strength is per component and the header carries several percentages, so there
is no single multiplier.

DENSITY. The identity g_a.i. = g_product x % holds only for SOLID
formulations. A liquid is dosed in ML against a w/w percentage, so the
conversion needs the product density and the naive check reads every dense SC
as a mismatch: 219 liquid rows here, 47 of them "failing" with a median ratio
of 1.124, which is a density, not an error. Liquids are therefore reported
separately and only when they fall outside a plausible density band
(0.80-1.35). Solids are the high-confidence signal: 129 of 136 land within
10% of 1.0, so the 7 that do not are worth reading individually.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

TOLERANCE = 0.10
FLOOR = 1.0
# Plausible product densities. Outside this a liquid mismatch is not density.
DENSITY_BAND = (0.80, 1.35)

_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def single_strength(ai: str):
    """The one strength a mixture does not have."""
    pcts = _PCT.findall(str(ai))
    if len(pcts) != 1:
        return None
    v = float(pcts[0])
    return v if 0 < v <= 100 else None


def main() -> None:
    from formulation_resolver import resolve_formulation_unit
    df = pd.read_parquet(ROOT / "data" / "final" / "label_db.parquet")
    rows, skipped = [], {"mixture_or_no_pct": 0, "no_numeric_pair": 0,
                         "basis_mismatch": 0}

    for i, r in df.iterrows():
        st = single_strength(r["active_ingredient"])
        if st is None:
            skipped["mixture_or_no_pct"] += 1
            continue
        ai, fm = r["dose_ai_value_min"], r["dose_formulation_value_min"]
        if pd.isna(ai) or pd.isna(fm):
            skipped["no_numeric_pair"] += 1
            continue
        # Normalise to base units before comparing. Captan 50% WP states
        # 1250 gm a.i. against 2.5 KG of product -- a perfect match that reads
        # as a 1000x mismatch if kg and g are compared as bare numbers.
        scale = {"g": 1.0, "ml": 1.0, "kg": 1000.0, "l": 1000.0}
        ai = float(ai) * scale.get(str(r["dose_ai_unit"]), 1.0)
        fm = float(fm) * scale.get(str(r["dose_formulation_unit"]), 1.0)
        if str(r["dose_ai_basis"]) != str(r["dose_formulation_basis"]):
            skipped["basis_mismatch"] += 1
            continue
        expected = float(fm) * st / 100.0
        gap = abs(float(ai) - expected)
        unit = resolve_formulation_unit(r["active_ingredient"])
        cls = {"ml": "liquid", "g": "solid"}.get(unit, "unknown")
        ratio = float(ai) / expected if expected else None
        if gap > max(FLOOR, TOLERANCE * expected):
            rows.append({
                "cls": cls,
                "index": i, "source_file": r["source_file"],
                "source_page": r["source_page"],
                "source_row_index": r["source_row_index"],
                "crop_slug": r["crop_slug"],
                "active_ingredient": str(r["active_ingredient"])[:44],
                "pest": str(r["pest_or_disease"])[:30],
                "strength": st, "dose_ai": float(ai), "dose_form": float(fm),
                "expected_ai": round(expected, 2),
                "ratio": round(float(ai) / expected, 3) if expected else None,
            })

    checked = len(df) - sum(skipped.values())
    print(f"rows in label_db           : {len(df)}")
    print(f"checkable (single strength, both numeric, same basis): {checked}")
    for k, v in skipped.items():
        print(f"  skipped, {k:22s}: {v}")

    out = pd.DataFrame(rows)
    solid = out[out.cls == "solid"]
    liquid = out[out.cls == "liquid"]
    lo, hi = DENSITY_BAND
    density_explained = liquid[(liquid.ratio >= lo) & (liquid.ratio <= hi)]
    liquid = liquid[(liquid.ratio < lo) | (liquid.ratio > hi)]

    def table(t, title):
        print("")
        print(f"=== {title}: {len(t)} ===")
        if not len(t):
            return
        hdr = ("src", "pg", "r", "crop", "active_ingredient",
               "a.i.", "form", "exp", "ratio")
        print("%-14s %3s %3s %-11s %-44s %9s %8s %8s %8s" % hdr)
        for _, x in t.sort_values("ratio").iterrows():
            print("%-14s %3s %3s %-11s %-44s %9.2f %8.1f %8.2f %8.2f" % (
                x.source_file[:14], x.source_page, x.source_row_index,
                x.crop_slug, x.active_ingredient[:44], x.dose_ai,
                x.dose_form, x.expected_ai, x.ratio))

    table(solid, "SOLID formulations - HIGH CONFIDENCE (g x % is exact)")
    table(liquid, "LIQUID formulations outside a plausible density band")
    print("")
    print(f"{len(density_explained)} further liquid rows sit inside the "
          f"{lo}-{hi} density band and are NOT reported: a w/w percentage "
          f"against a dose in ml needs the density term, and their ratios "
          f"ARE the density (median "
          f"{density_explained.ratio.median():.3f}).")


if __name__ == "__main__":
    main()