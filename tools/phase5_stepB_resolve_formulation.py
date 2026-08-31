"""
Phase 5, Step B — resolve dose_formulation's NEEDS_UNIT cells using the
formulation code printed in active_ingredient (src/formulation_resolver.py).

For every label_db row whose dose_formulation parse came back NEEDS_UNIT (no
unit in the cell, none licensed by the column header -- dose_parser.py rule
8), resolve_formulation_unit() reads the CIB&RC formulation code (SC, WP,
...) off active_ingredient and classifies it liquid (ml) or solid (g). Where
it succeeds, dose_formulation_raw is re-parsed with that unit as
default_unit and the six dose_formulation_* output columns (branch, pattern,
basis, value_min, value_max, unit) are overwritten in place;
dose_formulation_raw itself is never touched -- it stays the verbatim audit
trail per dose_parser.py's own contract. Where resolve_formulation_unit
returns None (no confident code found), the row is left exactly as it was --
still NEEDS_UNIT -- rather than guessing a unit.

Loads from label_db.parquet (not the CSV) so nullable dtypes (phi_days:
Int64) survive the round trip untouched; writes both label_db.csv and
label_db.parquet from the same patched frame so they stay identical to each
other, as they were before this script ran.

Every row not selected by the NEEDS_UNIT recomputation, and every column
outside the six dose_formulation_* outputs on the rows that ARE selected, is
asserted unchanged before anything is written -- see reports/
phase5_stepB_resolve_formulation_report.md for the counts this run produced.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
FINAL = ROOT / "data" / "final"
REPORTS = ROOT / "reports"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dose_parser import parse_dose  # noqa: E402
from formulation_resolver import resolve_formulation_unit  # noqa: E402

PATCHED_COLS = [
    "dose_formulation_branch", "dose_formulation_pattern",
    "dose_formulation_basis", "dose_formulation_value_min",
    "dose_formulation_value_max", "dose_formulation_unit",
]


def _raw_str(v) -> str:
    return "" if pd.isna(v) else str(v)


def main() -> None:
    df = pd.read_parquet(FINAL / "label_db.parquet")
    before = df.copy(deep=True)

    # Recompute the NEEDS_UNIT set the same way build_label_db.py produced
    # it (default_unit=None on the raw cell) -- a pure function of
    # dose_formulation_raw, so this reproduces exactly the rows behind the
    # stored branch/pattern/basis columns, not an approximation of them.
    codes = [parse_dose(_raw_str(r), default_unit=None).code
             for r in df["dose_formulation_raw"]]
    needs_unit_mask = pd.Series(codes, index=df.index) == "NEEDS_UNIT"
    n_needs_unit = int(needs_unit_mask.sum())

    resolved_unit = df.loc[needs_unit_mask, "active_ingredient"].apply(
        resolve_formulation_unit)
    n_resolved = int(resolved_unit.notna().sum())
    n_unresolved = n_needs_unit - n_resolved

    patched_rows: list[dict] = []
    for idx, unit in resolved_unit.dropna().items():
        raw = _raw_str(df.at[idx, "dose_formulation_raw"])
        r = parse_dose(raw, default_unit=unit)
        d = r.dose
        if d is None:
            raise RuntimeError(
                f"row {idx}: resolve_formulation_unit gave {unit!r} for "
                f"active_ingredient={df.at[idx, 'active_ingredient']!r}, but "
                f"parse_dose({raw!r}, default_unit={unit!r}) came back "
                f"branch={r.branch!r} code={r.code!r} instead of numeric -- "
                f"resolver/parser disagreement, needs investigation, not a "
                f"silent skip"
            )
        patched_rows.append({
            "index": idx,
            "crop_slug": df.at[idx, "crop_slug"],
            "active_ingredient": df.at[idx, "active_ingredient"],
            "dose_formulation_raw": raw,
            "resolved_unit": unit,
            "value_min": d.value_min,
            "value_max": d.value_max,
        })
        df.at[idx, "dose_formulation_branch"] = r.branch
        df.at[idx, "dose_formulation_pattern"] = r.pattern
        df.at[idx, "dose_formulation_basis"] = d.basis
        df.at[idx, "dose_formulation_value_min"] = (
            np.nan if d.value_min is None else d.value_min)
        df.at[idx, "dose_formulation_value_max"] = (
            np.nan if d.value_max is None else d.value_max)
        df.at[idx, "dose_formulation_unit"] = d.unit

    # --- integrity checks before writing anything ---------------------
    unpatched = before.index.difference([r["index"] for r in patched_rows])
    assert df.loc[unpatched].equals(before.loc[unpatched]), (
        "a row outside the resolved set changed"
    )
    other_cols = [c for c in df.columns if c not in PATCHED_COLS]
    assert df[other_cols].equals(before[other_cols]), (
        "a column outside the six dose_formulation_* outputs changed"
    )
    assert df["dose_formulation_raw"].equals(before["dose_formulation_raw"]), (
        "dose_formulation_raw (the audit trail) changed"
    )
    assert len(df) == len(before), "row count changed"

    df.to_csv(FINAL / "label_db.csv", index=False)
    df.to_parquet(FINAL / "label_db.parquet", index=False)

    unresolved_idx = resolved_unit[resolved_unit.isna()].index
    write_report(df, n_needs_unit, n_resolved, n_unresolved, patched_rows,
                 unresolved_idx)


def write_report(df: pd.DataFrame, n_needs_unit: int, n_resolved: int,
                  n_unresolved: int, patched_rows: list[dict],
                  unresolved_idx) -> None:
    from crop_mapper import SLUGS  # noqa: E402 (local import, report-only)

    L: list[str] = []

    def P(*a):
        s = " ".join(str(x) for x in a)
        print(s)
        L.append(s)

    P("# Phase 5, Step B — formulation unit resolution report\n")
    P(f"NEEDS_UNIT rows going in: **{n_needs_unit}**")
    P(f"Resolved via resolve_formulation_unit: **{n_resolved}**")
    P(f"Still NEEDS_UNIT (no confident code found): **{n_unresolved}**\n")

    P("## Per-slug dose_formulation coverage (after resolution)\n")
    P("| slug | numeric | free_text | empty | unparseable | n |")
    P("|---|---|---|---|---|---|")
    for slug in SLUGS:
        sub = df[df["crop_slug"] == slug]
        n = len(sub)
        if n == 0:
            P(f"| {slug} | - | - | - | - | 0 |")
            continue
        counts = sub["dose_formulation_branch"].value_counts()

        def pct(k):
            return f"{100*counts.get(k, 0)/n:.1f}%"
        P(f"| {slug} | {pct('numeric')} | {pct('free_text')} | "
          f"{pct('empty')} | {pct('unparseable')} | {n} |")
    P("")

    trainable = df[
        df["dose_ai_branch"].isin(["numeric", "free_text"])
        & df["dose_formulation_branch"].isin(["numeric", "free_text"])
    ]
    P("## Trainable rows\n")
    P("Rows where BOTH dose_ai and dose_formulation parsed to numeric or "
      "free_text (not empty, not unparseable) -- the real size of the "
      "answer space.\n")
    P(f"- Trainable rows: **{len(trainable)}** / {len(df)} "
      f"({100*len(trainable)/len(df):.1f}%)\n")
    P("| slug | trainable | n |")
    P("|---|---|---|")
    for slug in SLUGS:
        sub = df[df["crop_slug"] == slug]
        n = len(sub)
        t = len(trainable[trainable["crop_slug"] == slug])
        if n == 0:
            P(f"| {slug} | - | 0 |")
        else:
            P(f"| {slug} | {t} ({100*t/n:.1f}%) | {n} |")
    P("")

    P("## Remaining NEEDS_UNIT rows\n")
    still = df.loc[unresolved_idx]
    P(f"{len(still)} rows.\n")
    P("| crop_slug | active_ingredient | dose_formulation_raw |")
    P("|---|---|---|")
    for _, r in still.iterrows():
        P(f"| {r['crop_slug']} | `{r['active_ingredient']}` | "
          f"`{r['dose_formulation_raw']}` |")
    P("")

    P("## Sample of newly-resolved rows\n")
    sample = patched_rows[:10] if len(patched_rows) <= 10 else \
        [patched_rows[i] for i in
         range(0, len(patched_rows), max(1, len(patched_rows) // 10))][:10]
    P("| crop_slug | active_ingredient | dose_formulation_raw | resolved_unit | value_min | value_max |")
    P("|---|---|---|---|---|---|")
    for r in sample:
        P(f"| {r['crop_slug']} | `{r['active_ingredient']}` | "
          f"`{r['dose_formulation_raw']}` | {r['resolved_unit']} | "
          f"{r['value_min']} | {r['value_max']} |")
    P("")

    (REPORTS / "phase5_stepB_resolve_formulation_report.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
