"""PHASE 3, STEP 1b — row-local grid. Design and validation only.

Writes NO extracted data. The only artefact besides the report is
data/interim/phase3_step1b_rowgrid.json (gitignored) — per-row segment
geometry and assignment results.

Why row-local, not a smarter static grid
-----------------------------------------
Step 1's 180 "concerning" concatenations were diagnosed as row-local: a
compound dose expression (e.g. "108 (Spiropidion 60 + Acetamiprid 48) - 135
(...)") makes THAT ROW's own dose_ai cell physically wider than a typical
row's, and because the table's static per-subsection x-boundary was
calibrated from typical rows, every later value on that SAME row (dose_form,
dilution, PHI) gets compared against a boundary that no longer matches where
this row's own fields actually sit. No single static boundary can be right
for both a narrow row and a wide one.

The fix does not need a smarter boundary. Camelot already recorded, per
cell, whether a real ruled line exists on its right edge (`Cell.right`) —
this is the row's OWN internal structure, independent of every other row on
the page. Two adjacent raw grid columns with no real rule between them
(`cell[i].right == False`) are not two values; they are one value that a
spurious extra vertical rule elsewhere on the page caused camelot to split
into two grid slots for bookkeeping. Merging exactly where real rules say to
merge — and nowhere else — recovers each row's true value boundaries,
whatever their absolute x-position.

Algorithm, per row
-------------------
1. **Real-rule segments.** Merge consecutive raw cells while
   `cell.right == False`; a segment's text is the concatenation of its
   (normally exactly one) non-blank cell. Keep only NON-BLANK segments —
   this is the row's own "content segments", left to right.

2. **Six content segments -> ordinal assignment.** segment[0]=crop, ...,
   segment[5]=waiting_period_phi. No x-coordinate comparison at all. This is
   the common case and, on the 8 rows that motivated this step, gets every
   value into its label's semantic slot even though every one is at a
   different absolute x-position from a "typical" row (verified against the
   raw text layer, not just re-checked against the same flavour of
   boundary that produced the bug — see report §1).

3. **`source_column_merged`**: a GEOMETRIC test on the row's first content
   segment, not a content heuristic. True only when the segment BOTH starts
   in the crop zone (`x0 < crop/pest boundary`) AND extends past where pest
   should already have ended (`x1 > pest/dose-ai boundary`) — i.e. no real
   rule was drawn across either cut. Two weaker versions were tried and
   rejected before this one, each caught by checking the diagnosis against
   the actual `Cell.right` flags rather than trusting a plausible-sounding
   position rule:
     - "segment extends past the crop/pest boundary" alone misfired on
       ordinary rows whose crop text is merely a bit wider than the
       file-average calibration (e.g. "Rose(Ornamental)"), and on
       full-width chemical-name header rows.
     - "no real rule within 15pt of the calibrated crop/pest boundary"
       still misfired on the same ordinary rows, because a single row's
       true rule position legitimately varies from the aggregate median by
       more than 15pt — including on `insecticides_20260331.pdf` p89 row 0,
       which THIS document's Step 1 report had flagged as a genuine source
       merge. Direct inspection of `Cell.right` on that row shows a real
       rule at x=100.8, cleanly separating "Paddy" from "Yellow Stem
       Borer..." — Step 1's finding was itself an artifact of the flawed
       nearest-raw-column method, not a fact about the source PDF. See
       report §4 for the correction.
   Requiring the segment to cross BOTH boundaries is a much larger, harder
   to trigger condition — but still produced 7 false positives on its own,
   all one more shape: a row whose CROP cell is genuinely blank (forward-
   filled from a crop stated once above, shared across several
   pest-listing rows). There, `content[0]` (the first NON-BLANK segment) is
   already the pest name, not crop, and a sufficiently long pest name alone
   can cross both boundaries. The check is therefore run against `segs[0]`
   — the row's true position-0 segment, blank or not — and only fires when
   that specific segment carries real text. Final result, checked against
   every one of the 7 candidates by hand: zero genuine source-column merges
   found anywhere in the corpus. See report §4 for the full trail.

4. **Fewer than six content segments** (a field may be genuinely absent for
   this row's product type, not just merged): find the assignment of the k
   segments to k of the 6 bands, STRICTLY increasing in band index (so
   result stays monotonic and no two segments ever share a band), that
   minimises total absolute distance from each segment's own midpoint to the
   (file, subsection) calibrated CENTER of its assigned band. This is where
   "falling back to the calibrated grid" actually happens — position is
   only consulted to decide WHICH band is missing, once ordinal matching
   alone can't (there's no unambiguous "5th of 6" without knowing which one
   was skipped).

5. **More than six content segments**: ordinal/combinatorial matching no
   longer has a defined target size. Falls back to nearest-calibrated-center
   per segment (Step 1's method, but on real-rule segments rather than raw
   columns) and is flagged RESIDUAL — a genuine remaining case for
   `cols_unresolved`, not silently resolved.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import camelot
import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "cibrc"
INTERIM = ROOT / "data" / "interim"
STEP1_JSON = INTERIM / "phase3_step1_grid.json"
OUT_JSON = INTERIM / "phase3_step1b_rowgrid.json"

LABELS = ["crop", "pest_or_disease", "dose_ai", "dose_formulation",
          "dilution_water", "waiting_period_phi"]

IN_SCOPE = [
    "insecticides_20260331.pdf",
    "fungicides_20260331.pdf",
    "bio_insecticides_20260331.pdf",
    "bio_fungicides_20260331.pdf",
]

CROP_ADVISORY_SUBSECTIONS = {
    "insecticides_20260331.pdf": ["agricultural-use", "combination-product"],
    "fungicides_20260331.pdf": ["fungicides-single", "fungicides-combination"],
    "bio_insecticides_20260331.pdf": ["bio-insecticides"],
    "bio_fungicides_20260331.pdf": ["bio-fungicides"],
}


def load_section_map() -> dict:
    audit = json.loads((INTERIM / "phase2b_audit.json").read_text(encoding="utf-8"))
    out = {}
    for rec in audit:
        fn = rec["file"]
        out[fn] = {row["page"]: (row["section"], row["subsection"])
                   for row in rec["sections"]["per_page"]}
    return out


def row_segments(row_cells) -> list[dict]:
    """Merge consecutive cells while cell.right is False. Returns ALL
    segments (including blank ones), left to right."""
    segs = [[row_cells[0]]]
    for c in row_cells[1:]:
        if segs[-1][-1].right:
            segs.append([c])
        else:
            segs[-1].append(c)
    out = []
    for seg in segs:
        text = " ".join(c.text.replace("\n", " ").strip()
                        for c in seg if c.text.strip())
        out.append({"x0": float(seg[0].x1), "x1": float(seg[-1].x2),
                    "text": text.strip()})
    return out


def best_subset_assignment(segments: list[dict], centers: list[float]) -> list[int] | None:
    """k segments (k<=len(centers)) -> k strictly-increasing indices into
    `centers` minimising total |segment.mid - center[i]|. Returns the index
    per segment, or None if k > len(centers) (undefined for this method)."""
    n = len(centers)
    k = len(segments)
    if k == 0:
        return []
    if k > n:
        return None
    mids = [(s["x0"] + s["x1"]) / 2.0 for s in segments]
    best_cost = None
    best_combo = None
    for combo in itertools.combinations(range(n), k):
        cost = sum(abs(mids[i] - centers[combo[i]]) for i in range(k))
        if best_cost is None or cost < best_cost:
            best_cost = cost
            best_combo = combo
    return list(best_combo)


def nearest_band(mid: float, centers: list[float]) -> int:
    return min(range(6), key=lambda i: abs(mid - centers[i]))


def process_table(t, cells, section: str, subsection: str,
                   grid: dict) -> dict:
    page = int(t.page)
    if section != "crop-advisory" or subsection not in grid:
        return {"page": page, "section": section, "subsection": subsection,
                "out_of_scope_for_grid": True}

    centers = grid[subsection]["centers"]
    boundaries = grid[subsection]["boundaries"]
    crop_pest_boundary = boundaries[0]      # cut between band0(crop)/band1(pest)
    pest_doseai_boundary = boundaries[1]    # cut between band1(pest)/band2(dose_ai)

    row_results = []
    for r_idx, row_cells in enumerate(cells):
        segs = row_segments(row_cells)
        content = [s for s in segs if s["text"]]
        if not content:
            row_results.append({"row": r_idx, "kind": "blank", "resolved": [""] * 6})
            continue

        # source_column_merged: a GEOMETRIC fact about the FIRST content
        # segment, not a content heuristic. Requires the segment to both
        # START in the crop zone (x0 < crop/pest cut) AND extend past where
        # pest should have already ended (x1 > pest/dose-ai cut) — i.e. no
        # real rule was drawn anywhere across BOTH the crop/pest boundary
        # and the pest/dose-ai boundary. A single-sided check (just "extends
        # past crop/pest") was tried first and misfired on ordinary rows
        # whose crop text is merely a little wider than the file-average
        # calibration (e.g. "Rose(Ornamental)"), and on the two-tier
        # column-label sub-header row (whose first populated segment starts
        # at the dose_ai position, not crop, so a looser check without the
        # x0 requirement caught it too). Requiring BOTH boundaries removes
        # every false positive found while validating this — see report §4.
        # Tested against segs[0] (the row's true POSITION-0 segment), NOT
        # content[0]. A row whose crop cell is genuinely blank (forward-filled
        # from a crop stated once above, shared across several pest-listing
        # rows — common in this corpus) has content[0] == the PEST text,
        # which can be wide enough to trip the two-boundary check on its own.
        # A version tested against content[0] flagged exactly 7 rows this
        # way, all of them this same shape (segs[0] blank, content[0] a
        # normal pest name) — zero were genuine. Requiring segs[0] itself to
        # carry real text is what tells "crop present, segment swallowed
        # pest too" apart from "crop absent, pest is just wide".
        pos0 = segs[0]
        starts_in_crop = pos0["x0"] < crop_pest_boundary
        extends_past_pest = pos0["x1"] > pest_doseai_boundary
        if pos0["text"] and len(content) >= 2 and starts_in_crop and extends_past_pest:
            first = pos0
            rest = content[1:]
            sub_centers = centers[2:]
            assign = best_subset_assignment(rest, sub_centers)
            resolved = [first["text"], ""] + [""] * 4
            if assign is not None:
                for seg, b in zip(rest, assign):
                    resolved[2 + b] = seg["text"]
                kind = "source_column_merged"
            else:
                kind = "source_column_merged_residual"
            row_results.append({"row": r_idx, "kind": kind, "resolved": resolved,
                                "n_content_segments": len(content)})
            continue

        if len(content) == 6:
            resolved = [s["text"] for s in content]
            row_results.append({"row": r_idx, "kind": "ordinal_6",
                                "resolved": resolved, "n_content_segments": 6})
            continue

        if len(content) < 6:
            assign = best_subset_assignment(content, centers)
            resolved = [""] * 6
            for seg, b in zip(content, assign):
                resolved[b] = seg["text"]
            row_results.append({"row": r_idx, "kind": "fallback_subset",
                                "resolved": resolved,
                                "n_content_segments": len(content),
                                "bands_used": assign})
            continue

        # > 6 content segments: no defined target size -> nearest-center,
        # flagged residual (this is where real concatenation can still occur)
        resolved = [[] for _ in range(6)]
        for seg in content:
            mid = (seg["x0"] + seg["x1"]) / 2.0
            b = nearest_band(mid, centers)
            resolved[b].append(seg["text"])
        concat = [b for b in resolved if len(b) > 1]
        row_results.append({
            "row": r_idx, "kind": "residual_over6",
            "resolved": [" ".join(b) for b in resolved],
            "n_content_segments": len(content),
            "concat_bands": len(concat),
        })

    return {"page": page, "section": section, "subsection": subsection,
            "n_rows": len(cells), "rows": row_results}


def main() -> None:
    step1 = json.loads(STEP1_JSON.read_text(encoding="utf-8"))
    section_map = load_section_map()

    result = {}
    for name in IN_SCOPE:
        print(f"== {name}", flush=True)
        path = RAW / name
        with pdfplumber.open(path) as pdf:
            npages = len(pdf.pages)
        tables = camelot.read_pdf(str(path), pages=f"1-{npages}", flavor="lattice")

        grid = {sub: {"centers": step1[name]["bands_by_subsection"][sub]["centers"],
                      "boundaries": step1[name]["bands_by_subsection"][sub]["boundaries"]}
                for sub in CROP_ADVISORY_SUBSECTIONS[name]}

        table_results = []
        for t in tables:
            page = int(t.page)
            section, subsection = section_map.get(name, {}).get(
                page, ("unclassified", "unclassified"))
            table_results.append(process_table(t, t.cells, section, subsection, grid))
        result[name] = {"tables": table_results}
        print(f"   {len(tables)} tables processed", flush=True)

    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {OUT_JSON}")


if __name__ == "__main__":
    main()
