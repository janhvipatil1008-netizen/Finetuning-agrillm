"""PHASE 3, STEP 1 — column grid. Design and validation only.

Writes NO extracted table data to disk. The only artefact besides the report
is a metadata cache (data/interim/phase3_step1_grid.json, gitignored) holding
per-table column geometry and band-assignment results.

Method
------
Camelot returns each table's raw column x-boundaries as `Table.cols` — a list
of (x0, x1) tuples in the table's own coordinate space. Column POSITION is
unsafe to index by (Phase 2, "Column-position stability"), but column
X-COORDINATE is exactly the geometric fact that varies with content, not
noise: the six logical fields sit at physically stable horizontal bands, and
what varies page to page is how many spurious extra vertical rules camelot
draws *within* those bands.

**Calibration is per (file, crop-advisory subsection), not per file.** This
was NOT the original design — it is the direct result of p87 failing
validation against a whole-file grid (see report §1). insecticides'
`agricultural-use` (p2-55) and `combination-product` (p56-88) subsections
sit on physically different column templates: e.g. the a.i.-dose band center
is at x=307 in `agricultural-use` clean pages but x=256 in
`combination-product` ones — a 51pt shift, more than a tenth of the page
width. A single file-wide grid, blended from both, put p87's `60+60` in the
pest band and its `03` PHI in the dilution band. fungicides shows the same
split (`fungicides-single` vs `fungicides-combination`), smaller but present.
Calibrating per subsection instead of per file fixes both.

Only CROP-ADVISORY subsections are used for calibration or evaluated against
the 6-band grid. public-health / household / locust tables do not share this
column schema at all (different logical columns — "Habitat", "Method of
Application", no a.i./formulation split on some) — forcing them through a
crop grid would not be imprecise, it would be meaningless. Confirmed
necessary, not just cautious: 4 of bio_insecticides' 13 "clean 6-column"
pages (16-19) are `public-health-use`, not crop-advisory, and would have
corrupted that file's grid the same way insecticides' combination section did
if left in.

1. **Canonical centers**, per (file, subsection): for column index i in 0..5,
   the MEDIAN x-midpoint of that column across every CROP-ADVISORY table in
   that subsection whose raw shape is already exactly 6 columns.
2. **Canonical boundaries**: the midpoint between adjacent centers — a full
   partition of the page width, no gaps or overlaps.
3. **Assignment**: every raw column on every page is assigned to whichever
   canonical center its own midpoint is nearest to, using that page's
   subsection's grid. Two or more raw columns landing in the same band, same
   row, get their non-empty text concatenated in reading order.
4. **"Resolves cleanly"**: the raw-column -> band mapping is monotonic
   (bands never decrease left to right — a reversal means the assignment is
   confused, not just lossy), AND every band that receives a non-empty cell
   ANYWHERE in the table is one of exactly 6 (purely-blank raw columns, from
   merged/spanned header cells, don't count against this).
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

import camelot
import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "cibrc"
INTERIM = ROOT / "data" / "interim"
GRID_JSON = INTERIM / "phase3_step1_grid.json"
PHASE2B_JSON = INTERIM / "phase2b_audit.json"

IN_SCOPE = [
    "insecticides_20260331.pdf",
    "fungicides_20260331.pdf",
    "bio_insecticides_20260331.pdf",
    "bio_fungicides_20260331.pdf",
]

LOGICAL_COLUMNS = [
    "crop",
    "pest_or_disease",
    "dose_ai",
    "dose_formulation",
    "dilution_water",
    "waiting_period_phi",
]


def load_section_map() -> dict:
    """{file: {page: (section, subsection)}} from the phase 2b cache."""
    audit = json.loads(PHASE2B_JSON.read_text(encoding="utf-8"))
    out = {}
    for rec in audit:
        fn = rec["file"]
        out[fn] = {row["page"]: (row["section"], row["subsection"])
                   for row in rec["sections"]["per_page"]}
    return out


def table_cols_and_rows(t) -> tuple[list[tuple[float, float]], list[list[str]]]:
    cols = [(float(a), float(b)) for a, b in t.cols]
    rows = [[str(c) for c in row] for row in t.df.values.tolist()]
    return cols, rows


def col_is_populated(rows: list[list[str]], col_idx: int) -> bool:
    return any(row[col_idx].strip() for row in rows)


def load_all_tables(name: str, section_map: dict) -> list[dict]:
    path = RAW / name
    with pdfplumber.open(path) as pdf:
        npages = len(pdf.pages)
    tables = camelot.read_pdf(str(path), pages=f"1-{npages}", flavor="lattice")
    out = []
    for t in tables:
        cols, rows = table_cols_and_rows(t)
        page = int(t.page)
        section, subsection = section_map.get(name, {}).get(page, ("unclassified", "unclassified"))
        out.append({"page": page, "cols": cols, "rows": rows,
                    "ncols": len(cols), "section": section, "subsection": subsection})
    return out


def canonical_bands(tables: list[dict], subsection: str) -> dict:
    """Boundaries come from the observed GAP between adjacent raw columns in
    clean 6-column tables — the median x where the actual vertical rule
    between logical column i and i+1 sits — NOT from bisecting between column
    centers. Center-bisection was tried first and failed p87 validation: a
    physically narrow a.i.-dose column sitting right at the pest/dose edge
    landed on the wrong side of a Voronoi cut that had been pulled away from
    the true rule position by the wide pest-description column next to it.
    Gap-based boundaries fixed it (insecticides combination-product: the
    pest/dose cut moved from x=205.9, wrong, to x=202.3, correct — see
    report §1.1). `centers` (median column midpoint) is kept only as a
    human-readable band location for the report; it plays no role in
    assignment.
    """
    clean = [t for t in tables
             if t["ncols"] == 6 and t["section"] == "crop-advisory"
             and t["subsection"] == subsection]
    if not clean:
        return {"n_clean_tables": 0, "centers": None, "boundaries": None}

    per_col_mids = [[] for _ in range(6)]
    gaps = [[] for _ in range(5)]
    for t in clean:
        cols = t["cols"]
        for i, (x0, x1) in enumerate(cols):
            per_col_mids[i].append((x0 + x1) / 2.0)
        for i in range(5):
            gaps[i].append((cols[i][1] + cols[i + 1][0]) / 2.0)

    centers = [statistics.median(mids) for mids in per_col_mids]
    boundaries = [statistics.median(g) for g in gaps]
    ranges = []
    lo = None
    for i in range(6):
        hi = boundaries[i] if i < 5 else None
        ranges.append([lo, hi])
        lo = hi
    return {
        "n_clean_tables": len(clean),
        "clean_pages": sorted({t["page"] for t in clean}),
        "centers": centers,
        "boundaries": boundaries,
        "ranges": ranges,
    }


def assign_band(mid: float, boundaries: list[float]) -> int:
    """boundaries has 5 cut points -> 6 bands, by simple interval containment."""
    for i, b in enumerate(boundaries):
        if mid < b:
            return i
    return len(boundaries)


def evaluate_table(t: dict, boundaries: list[float]) -> dict:
    cols = t["cols"]
    rows = t["rows"]
    mids = [(x0 + x1) / 2.0 for x0, x1 in cols]
    band_of_col = [assign_band(m, boundaries) for m in mids]

    populated = [col_is_populated(rows, i) for i in range(len(cols))]
    bands_used = sorted({band_of_col[i] for i in range(len(cols)) if populated[i]})

    monotonic = True
    last = -1
    for i in range(len(cols)):
        if not populated[i]:
            continue
        b = band_of_col[i]
        if b < last:
            monotonic = False
        last = max(last, b)

    resolves_cleanly = monotonic and bands_used == list(range(6))

    concat_events = []
    for r_idx, row in enumerate(rows):
        by_band: dict[int, list[int]] = {}
        for c_idx, val in enumerate(row):
            if val.strip():
                by_band.setdefault(band_of_col[c_idx], []).append(c_idx)
        for b, cidxs in by_band.items():
            if len(cidxs) > 1:
                concat_events.append({
                    "row": r_idx, "band": b,
                    "raw_cols": cidxs,
                    "values": [row[c] for c in cidxs],
                    "concatenated": " ".join(row[c].replace("\n", " ").strip()
                                             for c in cidxs),
                })

    return {
        "page": t["page"], "section": t["section"], "subsection": t["subsection"],
        "ncols": len(cols), "nrows": len(rows),
        "band_of_col": band_of_col, "bands_used": bands_used,
        "monotonic": monotonic, "resolves_cleanly": resolves_cleanly,
        "concat_events": concat_events,
    }


CROP_ADVISORY_SUBSECTIONS = {
    "insecticides_20260331.pdf": ["agricultural-use", "combination-product"],
    "fungicides_20260331.pdf": ["fungicides-single", "fungicides-combination"],
    "bio_insecticides_20260331.pdf": ["bio-insecticides"],
    "bio_fungicides_20260331.pdf": ["bio-fungicides"],
}


def main() -> None:
    INTERIM.mkdir(parents=True, exist_ok=True)
    section_map = load_section_map()
    result = {}
    for name in IN_SCOPE:
        print(f"== {name}", flush=True)
        tables = load_all_tables(name, section_map)
        bands_by_sub = {}
        for sub in CROP_ADVISORY_SUBSECTIONS[name]:
            b = canonical_bands(tables, sub)
            bands_by_sub[sub] = b
            print(f"   [{sub}] {b['n_clean_tables']} clean 6-col tables "
                  f"used for calibration", flush=True)

        evals = []
        for t in tables:
            if t["section"] != "crop-advisory" or t["subsection"] not in bands_by_sub:
                evals.append({
                    "page": t["page"], "section": t["section"], "subsection": t["subsection"],
                    "ncols": t["ncols"], "nrows": len(t["rows"]),
                    "out_of_scope_for_grid": True,
                })
                continue
            boundaries = bands_by_sub[t["subsection"]]["boundaries"]
            evals.append(evaluate_table(t, boundaries))

        result[name] = {
            "n_tables": len(tables),
            "bands_by_subsection": bands_by_sub,
            "tables_raw": tables,
            "evals": evals,
        }
    GRID_JSON.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {GRID_JSON}")


if __name__ == "__main__":
    main()
