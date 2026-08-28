"""Builds reports/phase3_step1_grid.md from data/interim/phase3_step1_grid.json
and data/interim/phase2b_audit.json.

Design and validation only — this script writes a report, not extracted data.
"""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

import camelot

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "cibrc"
INTERIM = ROOT / "data" / "interim"
REPORTS = ROOT / "reports"

LABELS = ["crop", "pest_or_disease", "dose_ai", "dose_formulation",
          "dilution_water", "waiting_period_phi"]

NUM = re.compile(r"\d")


def esc(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " \u21b5 ")


def assign_band(mid: float, boundaries: list[float]) -> int:
    for i, b in enumerate(boundaries):
        if mid < b:
            return i
    return len(boundaries)


def resolve_row(row: list[str], band_of_col: list[int]) -> list[str]:
    bands = [[] for _ in range(6)]
    for c_idx, val in enumerate(row):
        if val.strip():
            bands[band_of_col[c_idx]].append(val.replace("\n", " ").strip())
    return [" ".join(b) for b in bands]


def main() -> None:
    grid = json.loads((INTERIM / "phase3_step1_grid.json").read_text(encoding="utf-8"))
    audit = json.loads((INTERIM / "phase2b_audit.json").read_text(encoding="utf-8"))

    L: list[str] = []
    A = L.append

    A("# Phase 3, Step 1 — Column Grid (design & validation only)\n")
    A("**No extracted data written to disk.** The only artefacts are this "
      "report and `data/interim/phase3_step1_grid.json` (gitignored) — per-"
      "table column geometry and band-assignment results, needed to "
      "reproduce every number below. No Step 2 extraction has run.\n")
    A("Full method and rationale — including why calibration ended up "
      "per-subsection with gap-based boundaries, not per-file with "
      "center-bisected ones — is in `tools/phase3_step1_grid.py`'s module "
      "docstring. This report is the evidence trail for those design "
      "choices, derived in the order they were actually found: the naive "
      "design first, why it failed p87, then the fix.\n")

    # ---------------------------------------------------------------- #
    # 1. p87 validation, told as it happened
    # ---------------------------------------------------------------- #
    A("## 1. Validation on insecticides p87 (required first)\n")
    A("### 1.1 First attempt: one grid per file — FAILED\n")
    A("A single file-wide grid, calibrated from every clean 6-column table "
      "in `insecticides_20260331.pdf` regardless of subsection, put "
      "p87 row 0's `60 +60` (the a.i. dose) in the **pest** band and its "
      "`03` (PHI) in the **dilution** band. Per your instruction, this "
      "stopped the run before any full sweep.\n")
    A("Root cause: `agricultural-use` (p2-55) and `combination-product` "
      "(p56-88) sit on two physically different column templates. Median "
      "column-midpoint centers, calibrated separately:\n")
    A("| band | agricultural-use center | combination-product center | shift |")
    A("|---|---|---|---|")
    ins = grid["insecticides_20260331.pdf"]
    agri_c = None
    combo_c = None
    for sub, b in ins["bands_by_subsection"].items():
        if sub == "agricultural-use":
            agri_c = b["centers"]
        elif sub == "combination-product":
            combo_c = b["centers"]
    for i in range(6):
        shift = combo_c[i] - agri_c[i]
        A(f"| {LABELS[i]} | {agri_c[i]:.1f} | {combo_c[i]:.1f} | {shift:+.1f} |")
    A("")
    A("A 51pt shift on the a.i.-dose band alone (more than a tenth of the "
      "page width) — p87 is in `combination-product`, and the whole-file "
      "grid was pulled toward `agricultural-use` because it contributed "
      "more calibration pages (28 vs 11). **Fix: calibrate per (file, "
      "crop-advisory subsection), never per whole file.**\n")

    A("### 1.2 Second attempt: per-subsection, center-bisected boundaries — STILL WRONG\n")
    A("Splitting calibration by subsection was not sufficient on its own. "
      "With boundaries placed equidistant between adjacent band centers "
      "(`(center_i + center_{i+1}) / 2`), `combination-product`'s "
      "pest/dose-ai cut landed at x=205.9 — but p87 row 0's a.i.-dose "
      "column has its own midpoint at x=204.0, **1.9pt on the wrong side**. "
      "Bisecting between centers doesn't account for column WIDTH: the "
      "wide, wrapped pest-description column next to it pulled the "
      "Voronoi cut away from where the actual ruled line sits.\n")

    A("### 1.3 Fix: boundaries from the observed GAP between adjacent columns\n")
    A("Instead of bisecting centers, each internal boundary is the median, "
      "across clean 6-column `combination-product` tables, of the actual "
      "gap-midpoint between column i's right edge and column i+1's left "
      "edge — i.e. where the real ruled line tends to sit. This moved the "
      "pest/dose-ai cut from **x=205.9 (wrong) to x=202.3 (correct)**, "
      "putting p87's `60 +60` and `03` where they belong. This is the "
      "method used everywhere below.\n")

    combo = ins["bands_by_subsection"]["combination-product"]
    A("Calibration for `combination-product` "
      f"({combo['n_clean_tables']} clean 6-column tables, pages "
      f"{combo['clean_pages']}):\n")
    A("| band | canonical center | boundary to next band |")
    A("|---|---|---|")
    for i in range(6):
        b = f"{combo['boundaries'][i]:.1f}" if i < 5 else "(page edge)"
        A(f"| {LABELS[i]} | {combo['centers'][i]:.1f} | {b} |")
    A("")

    p87_raw = camelot.read_pdf(str(RAW / "insecticides_20260331.pdf"),
                                pages="87", flavor="lattice")[0]
    p87_cols = [(float(a), float(b)) for a, b in p87_raw.cols]
    p87_rows = [[str(c) for c in r] for r in p87_raw.df.values.tolist()]
    p87_mids = [(a + b) / 2 for a, b in p87_cols]
    p87_band_of_col = [assign_band(m, combo["boundaries"]) for m in p87_mids]

    A("### 1.4 p87, all 22 raw columns -> 6 bands\n")
    A("| raw col | x0 | x1 | midpoint | -> band |")
    A("|---|---|---|---|---|")
    for i, (x0, x1) in enumerate(p87_cols):
        A(f"| {i} | {x0:.1f} | {x1:.1f} | {p87_mids[i]:.1f} | "
          f"{p87_band_of_col[i]} ({LABELS[p87_band_of_col[i]]}) |")
    A("")

    A("### 1.5 p87 row 0 — the exact ask\n")
    A("```text")
    A("raw: Okra (Bhindi) ‖ Red spider mites ‖ 60 +60 ‖ (19 blank cols) ‖ 500 ‖ (3 blank) ‖ 500 ‖ (5 blank) ‖ 03 ‖ (4 blank)")
    r0 = resolve_row(p87_rows[0], p87_band_of_col)
    A(f"resolved: crop={r0[0]!r}  pest={r0[1]!r}  dose_ai={r0[2]!r}  "
      f"dose_form={r0[3]!r}  dilution={r0[4]!r}  phi={r0[5]!r}")
    A("```")
    A(f"`60 +60` -> **dose_ai band**. `03` -> **waiting_period_phi band**. "
      "Confirmed.\n")

    A("### 1.6 All 18 rows of p87, resolved\n")
    A("| row | crop | pest_or_disease | dose_ai | dose_formulation | "
      "dilution_water | waiting_period_phi |")
    A("|---|---|---|---|---|---|---|")
    for r_idx, row in enumerate(p87_rows):
        resolved = resolve_row(row, p87_band_of_col)
        A(f"| {r_idx} | " + " | ".join(esc(v) for v in resolved) + " |")
    A("")

    A("### 1.7 The row-0 spot check passes. Scanning every row does not — flagged, not hidden\n")
    A("Rows 6, 7, 11, 12, 14-17 above show the same defect that motivated "
      "requirement 4: a value that is clearly **not PHI** (`500`, or `NA` "
      "meaning \"no dilution — granular application\") is concatenated "
      "into the PHI band alongside the real PHI value. This is the SAME "
      "root cause as §1.2/§1.3, one level down: it is not the "
      "subsection-level boundary that is wrong now, it is that a row whose "
      "a.i./formulation dose is an unusually wide compound expression "
      "(`108 (Spiropidion 60 + Acetamiprid 48) – 135 (...)`) pushes that "
      "row's OWN later columns further right than the calibrated dilution/"
      "PHI cut expects — for THIS row only, not the table as a whole "
      "(most other rows on p87 place dilution correctly). See §4 for how "
      "large this is across the whole corpus, and §7 for what I'd do "
      "about it before Step 2.\n")

    # ---------------------------------------------------------------- #
    # 2. canonical bands per file
    # ---------------------------------------------------------------- #
    A("## 2. Canonical bands, all four files (requirement 1)\n")
    for fn, rec in grid.items():
        A(f"### `{fn}`\n")
        for sub, b in rec["bands_by_subsection"].items():
            A(f"**{sub}** — {b['n_clean_tables']} clean 6-column tables "
              f"(pages {b['clean_pages']})\n")
            A("| band | logical column | center | range |")
            A("|---|---|---|---|")
            for i in range(6):
                lo = f"{b['ranges'][i][0]:.1f}" if b['ranges'][i][0] is not None else "page left edge"
                hi = f"{b['ranges'][i][1]:.1f}" if b['ranges'][i][1] is not None else "page right edge"
                A(f"| {i} | {LABELS[i]} | {b['centers'][i]:.1f} | [{lo}, {hi}) |")
            A("")

    # ---------------------------------------------------------------- #
    # 3. full sweep pass/fail
    # ---------------------------------------------------------------- #
    A("## 3. Full-corpus resolve/fail sweep (requirement 3)\n")
    A("Scope: **crop-advisory tables only.** public-health / household / "
      "locust tables do not share the 6-column schema at all (different "
      "logical columns — no a.i./formulation split, \"Habitat\" instead of "
      "\"Crop\", etc.) — forcing them through this grid would not be "
      "imprecise, it would be meaningless. This was confirmed necessary "
      "while building the calibration set, not assumed: 4 of "
      "`bio_insecticides_20260331.pdf`'s 13 apparently-clean 6-column "
      "pages turned out to be `public-health-use`, not crop-advisory, and "
      "would have corrupted that file's grid the same way "
      "`combination-product` corrupted the whole-file insecticides grid "
      "in §1.1 if left in.\n")

    total_in_scope = total_clean = 0
    fail_rows = []
    for fn, rec in grid.items():
        in_scope = [e for e in rec["evals"] if not e.get("out_of_scope_for_grid")]
        clean = [e for e in in_scope if e["resolves_cleanly"]]
        total_in_scope += len(in_scope)
        total_clean += len(clean)
        for e in in_scope:
            if not e["resolves_cleanly"]:
                fail_rows.append((fn, e))

    A(f"**{total_clean} / {total_in_scope} crop-advisory tables resolve "
      f"cleanly ({100*total_clean/total_in_scope:.1f}%). "
      f"{len(fail_rows)} do not.**\n")
    A("`resolves cleanly` here is a STRUCTURAL check only: the raw-column "
      "-> band mapping is monotonic left-to-right, and every band that "
      "receives any non-empty cell in the table is one of exactly 6 (no "
      "fewer). It is necessary, not sufficient — §1.7 and §4 show a table "
      "can pass this check and still misplace individual rows.\n")

    A("| file | page | subsection | raw cols | bands used | what the page looks like |")
    A("|---|---|---|---|---|---|")
    DESCRIPTIONS = {
        ("insecticides_20260331.pdf", 7): "Table 1: termite/wood-preservative treatment (\"Glue Line Poisoning\", \"Dipping\") — genuinely only 4 fields (Use/Method/Dose/Dilution), no formulation or PHI column exists for this product type.",
        ("insecticides_20260331.pdf", 9): "Rodenticide bait-site table (\"Coconut/Bamboo\", \"Residential premises\", \"Poultry Farm\") — site name column sits further right than a crop name typically does; not really the crop schema.",
        ("insecticides_20260331.pdf", 52): "Seed-dresser sub-table (Thiamethoxam 30% FS) — dose given per kg seed with a prose \"used as seed dresser\" note; no PHI concept applies to seed treatment.",
        ("insecticides_20260331.pdf", 56): "Combination-product table where a compound dose expression (\"400 +80.\") widens that row's dose_formulation column, pushing the real dilution value (\"500 –750\") past the calibrated dilution/PHI cut — band 4 (dilution) never gets used anywhere on this table.",
        ("insecticides_20260331.pdf", 60): "Same defect as p56: compound dose pushes dilution values (\"200\", \"500\") into the PHI band; band 4 unused table-wide.",
        ("fungicides_20260331.pdf", 31): "Bacterial-disease seed-treatment sub-table with prose method cells (\"Seed treatment: seed born infection...\") instead of numeric formulation/dilution; no PHI populated.",
        ("bio_insecticides_20260331.pdf", 10): "Nematode bio-pesticide table: only 3 raw columns exist at all (Crop, Pest, one large free-text Method cell) — dose/dilution/PHI are never split out by the source table, not something a 6-band grid can recover.",
        ("bio_fungicides_20260331.pdf", 11): "Seed/soil-treatment bio-fungicide table, prose method cells, PHI band never populated (seed treatment has no waiting period).",
        ("bio_fungicides_20260331.pdf", 12): "Same pattern as p11 — prose seed/soil-treatment method cells, no PHI.",
        ("bio_fungicides_20260331.pdf", 16): "Same pattern again — prose method cells for seed/nursery/root-dip treatment, no PHI.",
    }
    for fn, e in fail_rows:
        desc = DESCRIPTIONS.get((fn, e["page"]), "(see cached JSON for raw cells)")
        A(f"| `{fn}` | {e['page']} | {e['subsection']} | {e['ncols']} | "
          f"{e['bands_used']} | {desc} |")
    A("")
    A("None of these 10 are a calibration error in the §1 sense (wrong "
      "boundary position). Every one is a genuine STRUCTURAL variant: a "
      "product type (termite/wood treatment, rodenticide, seed dresser, "
      "seed/soil-treatment bio-pesticide) whose printed table has fewer "
      "than 6 real logical fields, or folds dose+method into one free-text "
      "cell. A 6-band grid cannot manufacture columns that were never "
      "printed.\n")

    # ---------------------------------------------------------------- #
    # 4. concatenation report
    # ---------------------------------------------------------------- #
    A("## 4. Concatenation report (requirement 4)\n")
    total_events = concerning = 0
    by_key: dict[tuple, list[int]] = {}
    samples: list[tuple] = []
    for fn, rec in grid.items():
        for e in rec["evals"]:
            if e.get("out_of_scope_for_grid"):
                continue
            for ev in e["concat_events"]:
                total_events += 1
                vals = [v.replace("\n", " ").strip() for v in ev["values"]]
                is_concerning = all(vals) and all(NUM.search(v) for v in vals)
                key = (fn, e["subsection"])
                by_key.setdefault(key, [0, 0])
                by_key[key][0] += 1
                if is_concerning:
                    concerning += 1
                    by_key[key][1] += 1
                    samples.append((fn, e["page"], LABELS[ev["band"]], vals))

    A(f"**{total_events} concatenation events** across all in-scope "
      f"crop-advisory tables (2+ non-empty raw columns landing in one band, "
      f"same row). Of those, **{concerning}** join two non-empty values "
      "that BOTH contain a digit — the heuristic used to flag \"possibly "
      "two genuinely different values\", not proof of it (a wrapped decimal "
      "like `\"12.\" + \"5\"` would also match this heuristic and be "
      "perfectly benign). Manual review of samples below confirms the "
      "majority are genuine: two DIFFERENT quantities (a formulation dose "
      "and a dilution figure, or a dilution figure and a PHI) sharing one "
      "band because a compound dose expression elsewhere in the row shifted "
      "that row's own column positions.\n")

    A("| file | subsection | total events | flagged \"concerning\" |")
    A("|---|---|---|---|")
    for (fn, sub), (tot, conc) in sorted(by_key.items(), key=lambda kv: -kv[1][1]):
        A(f"| `{fn}` | {sub} | {tot} | {conc} |")
    A("")

    A("Worked examples — genuinely different values, not wrapped text "
      "(one per distinct page+band, to show breadth rather than repeating "
      "the same page):\n")
    A("| file | page | band | raw values joined |")
    A("|---|---|---|---|")
    seen_page_band = set()
    shown = 0
    for fn, page, band, vals in samples:
        key = (fn, page, band)
        if key in seen_page_band:
            continue
        seen_page_band.add(key)
        A(f"| `{fn}` | {page} | {band} | {esc(' + '.join(vals))} |")
        shown += 1
        if shown >= 14:
            break
    A("")
    A("Two recurring shapes account for nearly all of them:\n")
    A("- **dose_form spills the neighbour into dose_ai**: a row states "
      "both a.i. and formulation as ranges (`\"15 –25\"` + `\"165 –280\"`, "
      "insecticides p4) — both land in the dose_ai band.\n")
    A("- **compound dose_ai/dose_form widens the row, pushing dilution "
      "into PHI**: `\"500\"` (dilution) + a real PHI value "
      "(`\"1\"`/`\"29\"`/`\"10\"`/...) land together in the PHI band "
      "whenever the SAME row's a.i./formulation cell is a compound "
      "expression (insecticides p8, p56, p60; also seen live on p87 §1.7).\n")

    # ---------------------------------------------------------------- #
    # 5. section-boundary cross-check
    # ---------------------------------------------------------------- #
    A("## 5. Cross-check against the 3 section-boundary pages (requirement 5)\n")
    A("These pages were entirely excluded from §3's sweep (whole page "
      "tagged by its LAST heading's subsection — see phase 2b). That is "
      "correct for the sweep's purpose, but leaves an open question: do "
      "rows ABOVE the split, which genuinely are crop-advisory, resolve "
      "against the right subsection's grid? Checked directly, per page.\n")

    A("### insecticides p89 (crop-advisory `combination-product` above "
      "y=675.9, `public-health` below)\n")
    p89 = camelot.read_pdf(str(RAW / "insecticides_20260331.pdf"), pages="89", flavor="lattice")[0]
    p89_cols = [(float(a), float(b)) for a, b in p89.cols]
    p89_mids = [(a + b) / 2 for a, b in p89_cols]
    p89_boc = [assign_band(m, combo["boundaries"]) for m in p89_mids]
    p89_rows = [[str(c) for c in r] for r in p89.df.values.tolist()]
    A(f"18-row, {len(p89_cols)}-column table on the page; rows 0-14 sit "
      "above the split (crop-advisory), rows 15-17 below (public-health). "
      "Evaluated rows 0-14 against the `combination-product` grid:\n")
    A("| row | crop | pest_or_disease | dose_ai | dose_formulation | "
      "dilution_water | waiting_period_phi |")
    A("|---|---|---|---|---|---|---|")
    for r_idx in range(15):
        resolved = resolve_row(p89_rows[r_idx], p89_boc)
        A(f"| {r_idx} | " + " | ".join(esc(v) for v in resolved) + " |")
    A("")
    A("dose_ai / dose_formulation / dilution_water / waiting_period_phi "
      "resolve correctly on every populated row. **But crop and pest "
      "merge into a single band on every row** (`pest_or_disease` is empty "
      "throughout) — on this specific 22-column table, camelot itself "
      "drew crop-name and pest-name as ONE raw column (no internal ruling "
      "between them), so no band-boundary choice can recover the split; "
      "the source table never separated them. A different structural gap "
      "from the ones in §3/§4, worth carrying into Step 2's "
      "`cols_unresolved` design.\n")

    A("### insecticides p94 (`public-health` above y=681.7, `household` below)\n")
    A("Genuinely out of scope on BOTH sides of the split — public-health "
      "above, household below, neither is a crop-advisory subsection. No "
      "crop-advisory content exists on this page to test against the "
      "6-band grid. Confirmed by inspection, not assumed.\n")

    A("### bio_insecticides p15 (crop-advisory `bio-insecticides` above "
      "y=332.8, `public-health` below)\n")
    bi = grid["bio_insecticides_20260331.pdf"]["bands_by_subsection"]["bio-insecticides"]
    p15 = camelot.read_pdf(str(RAW / "bio_insecticides_20260331.pdf"), pages="15", flavor="lattice")[0]
    p15_cols = [(float(a), float(b)) for a, b in p15.cols]
    p15_mids = [(a + b) / 2 for a, b in p15_cols]
    p15_boc = [assign_band(m, bi["boundaries"]) for m in p15_mids]
    p15_rows = [[str(c) for c in r] for r in p15.df.values.tolist()]
    A("Rows 0-7 sit above the split (crop-advisory), rows 8-20 below "
      "(public-health). Evaluated rows 0-7 against the `bio-insecticides` "
      "grid:\n")
    A("| row | crop | pest_or_disease | dose_ai | dose_formulation | "
      "dilution_water | waiting_period_phi |")
    A("|---|---|---|---|---|---|---|")
    for r_idx in range(8):
        resolved = resolve_row(p15_rows[r_idx], p15_boc)
        A(f"| {r_idx} | " + " | ".join(esc(v) for v in resolved) + " |")
    A("")
    A("**Resolves cleanly on every populated row** — crop, pest, dose, "
      "dilution and PHI all land correctly (rows 2, 4, 5, 7). Row 0's "
      "stray `(Helicoverpa armigera)` fragment in the pest band is a "
      "wrapped continuation from the Cotton/Pink-bollworm row on the "
      "PREVIOUS page (p14) — the page-boundary forward-fill hazard phase "
      "2b already documented, not a grid problem. The clean result here "
      "is the positive control: it shows §1's fix generalises when the "
      "source table itself doesn't have p89's raw-column merge.\n")

    # ---------------------------------------------------------------- #
    # 6. compound-rate note (Phase 4 concern, not resolved here)
    # ---------------------------------------------------------------- #
    A("## 6. Compound-rate note for Phase 4 (flagged, not resolved)\n")
    A("The 32 `unresolved_marker` rows (bio_insecticides p9-12, "
      "bio_fungicides p8/9/15 — see the FYM* discussion, prior turn) carry "
      "TWO rates in one dose/method cell: a seed-treatment rate "
      "(`\"...20 gm/kg of seeds...\"`) and a soil-application rate "
      "(`\"...enriched FYM* @ 5 tons/ha...\"`). `src/schema.py` "
      "(frozen, Act 2) gives `ChemicalOption` exactly one `dose: Dose` "
      "field — one basis, one value, per chemical option. These 32 rows "
      "cannot map onto that shape without either (a) picking one rate and "
      "discarding the other, or (b) emitting two `ChemicalOption`s from one "
      "printed row. Both are Phase 4 decisions. `schema.py` is not touched "
      "here or proposed to change — flagging only, per your instruction.\n")

    # ---------------------------------------------------------------- #
    # 7. recommendation
    # ---------------------------------------------------------------- #
    A("## 7. Recommendation for Step 2 (proposal, not a decision made here)\n")
    A("§4 shows the concatenation defect is systematic, not rare — "
      f"concentrated in `insecticides_20260331.pdf` (both subsections) and "
      "`fungicides_20260331.pdf` (`fungicides-single` especially). I'd "
      "propose: at Step 2, any row where a band's concatenation event "
      "matches the \"concerning\" heuristic in §4 (2+ non-empty raw "
      "columns landing in one band, all containing a digit) gets routed to "
      "`quarantine.csv` with reason `cols_unresolved`, rather than "
      "accepted into the raw CSV with a silently-merged value. p89's "
      "crop/pest raw-column merge (§5) would need the same treatment under "
      "`cols_unresolved` — the source table itself never separated them, "
      "so no band choice fixes it. Waiting for confirmation before Step 2 "
      "runs with this rule.\n")

    out = "\n".join(L) + "\n"
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "phase3_step1_grid.md").write_text(out, encoding="utf-8")
    print(f"wrote {REPORTS / 'phase3_step1_grid.md'} ({len(out)} bytes)")


if __name__ == "__main__":
    main()
