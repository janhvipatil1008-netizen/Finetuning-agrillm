"""PHASE 3, STEP 2b — phantom continuation rows. DIAGNOSIS ONLY.

Nothing is merged, nothing is dropped, no raw CSV is rewritten. This script
reads the Step 2 raw CSVs and writes:
  reports/phase3_step2b_phantom.md        the list, for manual judgement
  data/interim/phase3_step2b_phantom.json the same data, machine-readable

The defect
----------------------------------------------------------------------------
When a table cell wraps across a page break, camelot returns the fragment on
page N+1 as its own row. Step 2's forward-fill then supplies `crop` (and
`active_ingredient`) from the carry, so the fragment materialises as a
complete-looking advisory row whose dose columns are all empty. It is a
fabricated label claim: a (crop, pest) pair that the source never registered
as a row.

Confirmed by hand before this script was written:
  * insecticides p14 r0 "Red gram / Pod fly (Melanagromyza obtusa)" — the tail
    of p13's last pest cell, which ends "...Spotted pod borer (Maruca spp.)".
  * insecticides p69 r0 "Cotton / Thrips tabaci" — the tail of p68's last pest
    cell, which ends on a dangling "Thrips:".

Why no existing check catches it
----------------------------------------------------------------------------
* The Step 2 hard assertion counts source rows, and the fragment IS a real
  camelot row — the count balances whether or not it is a phantom.
* The phase-2b character-conservation audit compares page text against
  extracted cells; the fragment's characters are present on both sides, so
  nothing is missing or duplicated. Conservation is a necessary but not
  sufficient condition for correct ROW segmentation.
* Bold/heading detection sees regular-weight body text, because that is what
  it is.

Detection, and what is deliberately NOT inferred
----------------------------------------------------------------------------
A candidate is a row that is the FIRST row of its page AND has all four dose
columns (`dose_ai`, `dose_formulation`, `dilution_water`, `waiting_period_phi`)
empty. That is the user-specified net; this script does not narrow it with a
"looks like a continuation" heuristic, because deciding continuation-vs-genuine
is exactly the judgement being handed back for review.

Two structural exclusions are applied, and they are exclusions of rows that
CANNOT be a wrapped data cell, not judgement calls:
  * `chemical_header` / `column_header` rows are dose-empty BY CONSTRUCTION
    (Step 2 leaves every semantic column blank on them). A chemical header at
    the top of a page is the normal layout of this corpus, not a wrap.
  * non-crop-advisory rows (public-health / household / locust) have ALL six
    semantic columns blank by construction — Step 2 carries them as
    `raw_row_text` only. A fragment there cannot fabricate a label claim
    because there is no claim to fabricate. Counted and reported, not listed.

`own_columns` — the column each fragment occupies — is computed from the row's
OWN segments (`raw_row_text`, which is the row-local real-rule segments joined
verbatim), not from the populated columns. A column whose value came from the
forward-fill carry is not the fragment's own text and must not be counted as
the wrap site; `crop` is forward-filled on nearly every one of these rows and
would otherwise dominate the signature falsely.

Scope-crop matching
----------------------------------------------------------------------------
`src/scope.py::CROPS` holds 8 canonical names. The CIB&RC tables use trade
names that do not string-match them ("Red gram" = tur, "Bengal gram" and
"Chickpea" = gram, "Grapes" = grape). ALIASES below is explicit and
deliberately conservative — in particular "Green gram" (moong) and "Black
gram"/"Urd bean" (urad) are NOT scope `gram`, which is chickpea only, and are
left unmatched rather than folded in.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.scope import CROPS  # noqa: E402

INTERIM = ROOT / "data" / "interim"
REPORTS = ROOT / "reports"

RAW_CSVS = [
    "insecticides_20260331_raw.csv",
    "fungicides_20260331_raw.csv",
    "bio_insecticides_20260331_raw.csv",
    "bio_fungicides_20260331_raw.csv",
]

DOSE_COLS = ["dose_ai", "dose_formulation", "dilution_water", "waiting_period_phi"]
SEMANTIC_COLS = ["crop", "pest_or_disease"] + DOSE_COLS + ["method"]

# Structural non-data kinds: dose-empty by construction, never a wrapped cell.
NON_DATA_KINDS = {"chemical_header", "column_header"}

# CIB&RC trade name (lowercased) -> scope.py canonical crop.
ALIASES = {
    "cotton": "cotton",
    "soybean": "soybean", "soyabean": "soybean", "soya bean": "soybean",
    "red gram": "tur", "redgram": "tur", "pigeon pea": "tur",
    "pigeonpea": "tur", "arhar": "tur", "tur": "tur",
    "bengal gram": "gram", "bengalgram": "gram", "chickpea": "gram",
    "chick pea": "gram", "gram": "gram",
    "onion": "onion",
    "tomato": "tomato",
    "grape": "grape", "grapes": "grape",
    "pomegranate": "pomegranate",
}


def scope_crop(raw: str) -> str | None:
    """Map a CIB&RC crop string to a scope.py canonical crop, or None.

    Matches on the whole normalised string and on each parenthesised or
    slash-separated alternative within it ("Paddy(Rice)", "Chilli/Capsicum"),
    so a scope crop named as one alternative of several is still found.
    """
    if not raw:
        return None
    norm = re.sub(r"\s+", " ", raw.strip().lower())
    parts = [norm] + [p.strip() for p in re.split(r"[()/,]", norm) if p.strip()]
    for part in parts:
        hit = ALIASES.get(part)
        if hit:
            return hit
    return None


def load(name: str) -> list[dict]:
    with (INTERIM / name).open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def page_first_indices(rows: list[dict]) -> list[int]:
    """Indices of the first CSV row on each page, in page order."""
    seen: set[str] = set()
    out: list[int] = []
    for i, r in enumerate(rows):
        p = r["source_page"]
        if p not in seen:
            seen.add(p)
            out.append(i)
    return out


def own_segments(row: dict) -> list[str]:
    return row["raw_row_text"].split(" || ") if row["raw_row_text"] else []


def own_columns(row: dict) -> list[str]:
    """Semantic columns whose value is this row's OWN text, not forward-filled."""
    segs = own_segments(row)
    return [c for c in SEMANTIC_COLS if row[c] and row[c] in segs]


def classify(rows: list[dict], idx: int) -> dict:
    r = rows[idx]
    prev = rows[idx - 1] if idx > 0 else None
    segs = own_segments(r)
    cols = own_columns(r)
    return {
        "csv_index": idx,
        "page": r["source_page"],
        "table_index": r["source_table_index"],
        "row_index": r["source_row_index"],
        "assignment_kind": r["assignment_kind"],
        "section": r["section"],
        "subsection": r["subsection"],
        "active_ingredient": r["active_ingredient"],
        "n_segments": len(segs),
        "own_columns": cols,
        "fragment_column": cols[0] if len(cols) == 1 else None,
        "crop": r["crop"],
        "crop_is_own": "crop" in cols,
        "scope_crop": scope_crop(r["crop"]),
        "pest_or_disease": r["pest_or_disease"],
        "method": r["method"],
        "raw_row_text": r["raw_row_text"],
        "empty_dose_cols": [c for c in DOSE_COLS if not r[c]],
        "prev": None if prev is None else {
            "csv_index": idx - 1,
            "page": prev["source_page"],
            "row_index": prev["source_row_index"],
            "assignment_kind": prev["assignment_kind"],
            "active_ingredient": prev["active_ingredient"],
            "crop": prev["crop"],
            "pest_or_disease": prev["pest_or_disease"],
            "dose_ai": prev["dose_ai"],
            "dose_formulation": prev["dose_formulation"],
            "dilution_water": prev["dilution_water"],
            "waiting_period_phi": prev["waiting_period_phi"],
            "method": prev["method"],
            "raw_row_text": prev["raw_row_text"],
        },
    }


def analyse() -> dict:
    result: dict = {"files": {}, "totals": {}}
    for name in RAW_CSVS:
        rows = load(name)
        firsts = page_first_indices(rows)

        full, partial = [], []
        excluded_kind = excluded_section = 0

        for i in firsts:
            r = rows[i]
            n_empty = sum(1 for c in DOSE_COLS if not r[c])
            if n_empty == 0:
                continue
            if r["assignment_kind"] in NON_DATA_KINDS:
                excluded_kind += 1
                continue
            if r["section"] != "crop-advisory":
                excluded_section += 1
                continue
            (full if n_empty == len(DOSE_COLS) else partial).append(classify(rows, i))

        result["files"][name] = {
            "n_rows": len(rows),
            "n_pages": len(firsts),
            "excluded_non_data_kind": excluded_kind,
            "excluded_non_crop_advisory": excluded_section,
            "all_dose_empty": full,
            "partial_dose_empty": partial,
        }

    everything = [c for f in result["files"].values()
                  for c in f["all_dose_empty"] + f["partial_dose_empty"]]
    result["totals"] = {
        "all_dose_empty": sum(len(f["all_dose_empty"]) for f in result["files"].values()),
        "partial_dose_empty": sum(len(f["partial_dose_empty"]) for f in result["files"].values()),
        "excluded_non_data_kind": sum(f["excluded_non_data_kind"] for f in result["files"].values()),
        "excluded_non_crop_advisory": sum(f["excluded_non_crop_advisory"] for f in result["files"].values()),
        "fragment_columns": _tally(c["fragment_column"] for c in everything),
        "scope_crop_hits": _tally(c["scope_crop"] for c in everything if c["scope_crop"]),
    }
    return result


def _tally(it) -> dict:
    out: dict = {}
    for v in it:
        key = "MULTI/NONE" if v is None else v
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def main() -> None:
    data = analyse()
    out_json = INTERIM / "phase3_step2b_phantom.json"
    out_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    t = data["totals"]
    print("PHASE 3 STEP 2b — phantom continuation diagnosis (no merge performed)")
    print(f"  candidates, all four dose cols empty : {t['all_dose_empty']}")
    print(f"  candidates, SOME dose cols empty     : {t['partial_dose_empty']}")
    print(f"  excluded, header rows (by construction): {t['excluded_non_data_kind']}")
    print(f"  excluded, non-crop-advisory sections   : {t['excluded_non_crop_advisory']}")
    print(f"  fragment column tally: {t['fragment_columns']}")
    print(f"  scope-crop tally     : {t['scope_crop_hits']}")
    print(f"  wrote {out_json.relative_to(ROOT)}")
    print(f"  scope crops from scope.py: {CROPS}")


if __name__ == "__main__":
    main()
