"""
build_label_db.py — assemble data/final/label_db.{csv,parquet} from the
three validated parsers (dose_parser, parse_phi, crop_mapper).

Reads every row of the 4 in-scope raw CSVs. For each row: maps the crop cell
to zero or more in-scope slugs, parses dose_ai and dose_formulation, parses
waiting_period_phi, and carries active_ingredient / pest_or_disease through
verbatim (already forward-filled by Phase 3).

No deduplication. One raw row -> one label_db row, except a multi-crop split
(one row naming several in-scope crops) expands to one row per slug, sharing
the same dose/PHI/ai/pest values.

EXCLUSION ORDER (checked once per raw row, before any crop split):

  1. no_registered_header  -- the "Nemastin" defect (see below).
  2. crop_no_registered... -- (folded into 1; nothing else uses this code)
  3. crop_blank / crop_out_of_scope / crop_not_a_crop_cell -- from crop_mapper.
  4. structural_filler -- dose_ai, dose_formulation AND pest_or_disease are
     all blank. Checked AFTER crop scope, so a genuinely in-scope row with no
     data left in it (1 row in the corpus: bio_fungicides p9 r1, Tomato,
     assignment_kind='blank') gets this more specific reason instead of
     falling through as merely out-of-scope.
  5. phi_defect -- parse_phi(waiting_period_phi) raised PHIParseError. Added
     after the first build: 5 rows had collapsed table columns ('1 7', '2 1'),
     an application schedule, or a dilution volume sitting in the PHI column
     -- not a real PHI, an extraction defect. Checked LAST, after a row has
     already cleared crop scope and the structural-filler check, so it only
     ever removes rows that would otherwise have been kept.

Rows that clear exclusion but whose dose or PHI cell doesn't parse to a
number are KEPT, not excluded -- dose_parser and parse_phi already say why
(branch/pattern/code, or phi_outcome) via columns carried straight through,
and losing that distinction here would repeat the exact silent-collapse bug
both modules exist to prevent. Only the four reasons above drop a row.

The "Nemastin" defect
----------------------
bio_insecticides_20260331.pdf p10 r9-r13 and p11 r1 (Gerbera, Carnations,
Tuberose, Banana, Acid lime, Papaya) inherited active_ingredient='Trichoderma
harzianum 1.0% WP (Strain No. IIHR-TH-...)' by forward-fill from the
chemical_header at p10 r3. But each row's own raw_row_text names a DIFFERENT
product: 'Apply the Nemastin @ 50 gm/sq.m...', 'Apply 2 Kg Nemastin 1% Wp
mixed in 2 tones of FYM...'. CIB&RC's table has no chemical_header row for
"Nemastin" at all -- it is not registered under its own heading anywhere in
this table, so there is nothing to forward-fill from, and attaching the
Trichoderma header to it would assert a registered active-ingredient/
formulation pairing this document never states. Detected here by a literal
'nemastin' match in raw_row_text (6 rows, hand-verified against the source
PDF); a substring match this narrow needs no token machinery. All 6 rows also
happen to fail crop scope (Gerbera/Carnations/Tuberose/Banana/Acid lime/
Papaya are none of the 8 slugs) -- this check is checked FIRST anyway so the
exclusion log names the real defect instead of the coincidental one.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
INTERIM = ROOT / "data" / "interim"
FINAL = ROOT / "data" / "final"
REPORTS = ROOT / "reports"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from application_method import extract_method  # noqa: E402
from crop_mapper import SLUGS, map_crop  # noqa: E402
from dose_parser import parse_dose  # noqa: E402
from dose_units import add_per_acre_columns  # noqa: E402
from parse_phi import PHIParseError, parse_phi  # noqa: E402

FILES = ["insecticides", "fungicides", "bio_insecticides", "bio_fungicides"]

_NEMASTIN_RE = re.compile(r"nemastin", re.IGNORECASE)


def load(fn: str) -> list[dict]:
    with open(INTERIM / f"{fn}_20260331_raw.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_dose_cell(raw: str, default_unit) -> dict:
    r = parse_dose(raw, default_unit=default_unit)
    d = r.dose
    return {
        "branch": r.branch,
        "pattern": r.pattern,
        "basis": d.basis if d else "",
        "value_min": d.value_min if d and d.value_min is not None else None,
        "value_max": d.value_max if d and d.value_max is not None else None,
        "unit": d.unit if d and d.unit is not None else "",
        "raw": raw,
        "code": r.code or "",
    }


def parse_phi_cell(raw: str) -> dict:
    try:
        value = parse_phi(raw)
    except PHIParseError as e:
        return {"days": None, "outcome": "raised", "raw": raw, "raise_detail": str(e)}
    outcome = "resolved" if value is not None else "not_applicable"
    return {"days": value, "outcome": outcome, "raw": raw, "raise_detail": ""}


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    kept: list[dict] = []
    excluded: list[dict] = []

    for fn in FILES:
        for row in load(fn):
            crop_raw = row["crop"] or ""
            ai = row["active_ingredient"] or ""
            pest = row["pest_or_disease"] or ""
            dose_ai_raw = row["dose_ai"] or ""
            dose_form_raw = row["dose_formulation"] or ""
            phi_raw = row["waiting_period_phi"] or ""

            prov = {
                "source_file": row["source_file"],
                "source_page": row["source_page"],
                "source_row_index": row["source_row_index"],
            }

            # These are pure and cheap; compute once, reuse for kept or
            # excluded rows alike so the exclusion log is fully informative.
            dose_ai = parse_dose_cell(dose_ai_raw, default_unit="g")
            dose_form = parse_dose_cell(dose_form_raw, default_unit=None)
            phi = parse_phi_cell(phi_raw)
            phi_not_applicable = _phi_not_applicable(phi_raw, phi["outcome"])

            crop_results = map_crop(crop_raw)

            def make_row(slug: str | None, multi: bool, pest_bled: bool) -> dict:
                r = dict(prov)
                r.update({
                    "crop_slug": slug or "",
                    "crop_raw": crop_raw,
                    # A property of the CLAIM, not the crop: CIB&RC registers
                    # foliar and soil-drench use separately, with different
                    # doses and intervals. crop_mapper drops it by design.
                    "application_method": extract_method(crop_raw) or "",
                    "crop_multi_crop_split": multi,
                    "flag_pest_bled": pest_bled,
                    "active_ingredient": ai,
                    "pest_or_disease": pest,
                    "dose_ai_branch": dose_ai["branch"],
                    "dose_ai_pattern": dose_ai["pattern"],
                    "dose_ai_basis": dose_ai["basis"],
                    "dose_ai_value_min": dose_ai["value_min"],
                    "dose_ai_value_max": dose_ai["value_max"],
                    "dose_ai_unit": dose_ai["unit"],
                    "dose_ai_raw": dose_ai["raw"],
                    "dose_formulation_branch": dose_form["branch"],
                    "dose_formulation_pattern": dose_form["pattern"],
                    "dose_formulation_basis": dose_form["basis"],
                    "dose_formulation_value_min": dose_form["value_min"],
                    "dose_formulation_value_max": dose_form["value_max"],
                    "dose_formulation_unit": dose_form["unit"],
                    "dose_formulation_raw": dose_form["raw"],
                    "phi_days": phi["days"],
                    "phi_not_applicable": phi_not_applicable,
                    "phi_outcome": phi["outcome"],
                    "phi_raw": phi["raw"],
                })
                return r

            # 1. Nemastin defect -- checked first, applies to the whole row
            # regardless of what crop mapping would otherwise say.
            if _NEMASTIN_RE.search(row["raw_row_text"] or ""):
                r = make_row(None, False, False)
                r["exclusion_reason"] = "no_registered_header"
                excluded.append(r)
                continue

            # 2. Crop scope.
            in_scope = [c for c in crop_results if c.slug and not c.not_a_crop_cell]
            if not in_scope:
                r = make_row(None, False,
                            any(c.pest_bled for c in crop_results))
                if not crop_raw.strip():
                    r["exclusion_reason"] = "crop_blank"
                elif any(c.not_a_crop_cell for c in crop_results):
                    r["exclusion_reason"] = "crop_not_a_crop_cell"
                else:
                    r["exclusion_reason"] = "crop_out_of_scope"
                excluded.append(r)
                continue

            # 3. Structural filler -- checked only for rows that DID clear
            # crop scope, so the reason is specific rather than redundant
            # with 'crop_blank'.
            if not dose_ai_raw.strip() and not dose_form_raw.strip() \
                    and not pest.strip():
                r = make_row(in_scope[0].slug, in_scope[0].multi_crop_split,
                            in_scope[0].pest_bled)
                r["exclusion_reason"] = "structural_filler"
                excluded.append(r)
                continue

            # 5. PHI defect -- checked last, only removes rows that would
            # otherwise have been kept.
            if phi["outcome"] == "raised":
                for c in in_scope:
                    r = make_row(c.slug, c.multi_crop_split, c.pest_bled)
                    r["exclusion_reason"] = "phi_defect"
                    excluded.append(r)
                continue

            # Kept. One output row per in-scope slug (multi-crop split).
            for c in in_scope:
                kept.append(make_row(c.slug, c.multi_crop_split, c.pest_bled))

    kept_df = pd.DataFrame(kept)
    excl_df = pd.DataFrame(excluded)
    for df in (kept_df, excl_df):
        if len(df):
            # Plain int64 can't hold NaN; pandas silently upcasts the whole
            # column to float64, so a real PHI of 35 days prints as '35.0'.
            # Int64 (nullable) keeps genuine integers integer and keeps None
            # as <NA> instead of manufacturing a decimal point.
            df["phi_days"] = df["phi_days"].astype("Int64")
            for c in ("dose_ai_value_min", "dose_ai_value_max",
                     "dose_formulation_value_min", "dose_formulation_value_max"):
                df[c] = df[c].astype("float64")
        # Derived per-acre columns. Added last, from the values just settled
        # above, and NULL for every non-area basis -- see src/dose_units.py.
        # Any later script that patches a dose value must call this again.
        add_per_acre_columns(df)
    return kept_df, excl_df


def _phi_not_applicable(phi_raw: str, outcome: str) -> bool:
    """True for the PROSE reason parse_phi returns None for -- seed-treatment
    wording, '(not) required' phrasing, numberless growth stages -- per Step
    3 decision 5. False for a genuinely blank/placeholder cell ('-', 'NA',
    ''), which is 'unknown', not 'does not apply', even though parse_phi
    returns None for both. This is exactly the distinction
    ChemicalOption.phi_days cannot express and label_db exists to carry.
    """
    if outcome != "not_applicable":
        return False
    key = phi_raw.strip().casefold().replace(".", "")
    placeholder = {"", "-", "--", "---", "----", "na", "n/a", "nil", "none",
                   "not applicable"}
    return key not in placeholder


def main() -> None:
    kept_df, excl_df = build()

    FINAL.mkdir(parents=True, exist_ok=True)
    kept_df.to_csv(FINAL / "label_db.csv", index=False)
    kept_df.to_parquet(FINAL / "label_db.parquet", index=False)
    excl_df.to_csv(FINAL / "exclusion_log.csv", index=False)

    write_report(kept_df, excl_df)


def write_report(kept: pd.DataFrame, excl: pd.DataFrame) -> None:
    L: list[str] = []

    def P(*a):
        s = " ".join(str(x) for x in a)
        print(s)
        L.append(s)

    total_in = len(kept) + len(excl)
    P("# Phase 4 (label_db) Step A — build report\n")
    P(f"Wrote data/final/label_db.csv, label_db.parquet ({len(kept)} rows) "
      f"and exclusion_log.csv ({len(excl)} rows).\n")

    P("## Totals\n")
    P(f"- Rows in (every row of the 4 raw CSVs, all row kinds): **{total_in}**")
    P(f"- Rows kept in label_db: **{len(kept)}**")
    P(f"- Rows excluded: **{len(excl)}**\n")

    P("### Exclusion breakdown\n")
    P("| reason | rows |")
    P("|---|---|")
    for reason, n in excl["exclusion_reason"].value_counts().items():
        P(f"| {reason} | {n} |")
    P("")

    P("## Per-slug row counts (label_db)\n")
    P("| slug | rows |")
    P("|---|---|")
    for slug in SLUGS:
        P(f"| {slug} | {(kept['crop_slug'] == slug).sum()} |")
    P(f"| **total** | **{len(kept)}** |\n")

    P("## Per-slug dose coverage\n")
    for col, label in [("dose_ai_branch", "dose_ai"),
                       ("dose_formulation_branch", "dose_formulation")]:
        P(f"### {label}\n")
        P("| slug | numeric | free_text | empty | unparseable | n |")
        P("|---|---|---|---|---|---|")
        for slug in SLUGS:
            sub = kept[kept["crop_slug"] == slug]
            n = len(sub)
            if n == 0:
                P(f"| {slug} | - | - | - | - | 0 |")
                continue
            counts = sub[col].value_counts()

            def pct(k):
                return f"{100*counts.get(k, 0)/n:.1f}%"
            P(f"| {slug} | {pct('numeric')} | {pct('free_text')} | "
              f"{pct('empty')} | {pct('unparseable')} | {n} |")
        P("")

    P("## Per-slug PHI coverage\n")
    P("| slug | resolved | not_applicable | raised | n |")
    P("|---|---|---|---|---|")
    for slug in SLUGS:
        sub = kept[kept["crop_slug"] == slug]
        n = len(sub)
        if n == 0:
            P(f"| {slug} | - | - | - | 0 |")
            continue
        counts = sub["phi_outcome"].value_counts()

        def pct(k):
            return f"{100*counts.get(k, 0)/n:.1f}%"
        P(f"| {slug} | {pct('resolved')} | {pct('not_applicable')} | "
          f"{pct('raised')} | {n} |")
    P("")

    P("## Nemastin exclusion — full list\n")
    nem = excl[excl["exclusion_reason"] == "no_registered_header"]
    P(f"{len(nem)} rows.\n")
    P("| source_file | page | row | crop_raw | pest_or_disease |")
    P("|---|---|---|---|---|")
    for _, r in nem.iterrows():
        P(f"| {r['source_file']} | {r['source_page']} | {r['source_row_index']} | "
          f"`{r['crop_raw']}` | `{r['pest_or_disease']}` |")
    P("")

    P("## phi_defect exclusion — full list\n")
    phidef = excl[excl["exclusion_reason"] == "phi_defect"]
    P(f"{len(phidef)} rows.\n")
    P("| source_file | page | row | crop_slug | phi_raw |")
    P("|---|---|---|---|---|")
    for _, r in phidef.iterrows():
        P(f"| {r['source_file']} | {r['source_page']} | {r['source_row_index']} | "
          f"{r['crop_slug']} | `{r['phi_raw']}` |")
    P("")

    P("## 20-row sample from label_db\n")
    sample = kept.sample(n=min(20, len(kept)), random_state=20260601)
    cols = ["source_file", "source_page", "crop_slug", "active_ingredient",
            "pest_or_disease", "dose_ai_raw", "dose_ai_branch",
            "dose_ai_value_min", "dose_ai_unit", "phi_days", "phi_outcome"]
    P("```text")
    for _, r in sample.iterrows():
        P(f"{r['source_file']} p{r['source_page']} | {r['crop_slug']} | "
          f"ai={r['active_ingredient'][:40]!r}")
        P(f"    pest: {r['pest_or_disease'][:50]!r}")
        P(f"    dose_ai: {r['dose_ai_raw']!r} -> {r['dose_ai_branch']} "
          f"({r['dose_ai_value_min']} {r['dose_ai_unit']})")
        P(f"    phi: {r['phi_raw']!r} -> {r['phi_outcome']} ({r['phi_days']})")
        P("")
    P("```\n")

    (REPORTS / "phase4_labeldb_stepA_build_report.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
