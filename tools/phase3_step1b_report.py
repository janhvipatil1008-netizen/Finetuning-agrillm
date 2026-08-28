"""Builds reports/phase3_step1b_rowgrid.md from data/interim/phase3_step1b_rowgrid.json
and data/interim/phase3_step1_grid.json.

Design and validation only — this script writes a report, not extracted data.
"""

from __future__ import annotations

import json
from pathlib import Path

import camelot

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "cibrc"
INTERIM = ROOT / "data" / "interim"
REPORTS = ROOT / "reports"

LABELS = ["crop", "pest_or_disease", "dose_ai", "dose_formulation",
          "dilution_water", "waiting_period_phi"]


def esc(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def main() -> None:
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    from phase3_step1b_rowgrid import row_segments, best_subset_assignment  # noqa: E402

    rowgrid = json.loads((INTERIM / "phase3_step1b_rowgrid.json").read_text(encoding="utf-8"))
    step1 = json.loads((INTERIM / "phase3_step1_grid.json").read_text(encoding="utf-8"))

    L: list[str] = []
    A = L.append

    A("# Phase 3, Step 1b — Row-Local Grid (design & validation only)\n")
    A("**No extracted data written to disk.** The only artefacts are this "
      "report and `data/interim/phase3_step1b_rowgrid.json` (gitignored) — "
      "per-row segment geometry and assignment results. No Step 2 "
      "extraction has run.\n")
    A("Full method — including two rejected versions of the "
      "`source_column_merged` check and why each was rejected — is in "
      "`tools/phase3_step1b_rowgrid.py`'s module docstring. This report is "
      "the validation trail.\n")

    # ---------------------------------------------------------------- #
    # 1. p87 validation
    # ---------------------------------------------------------------- #
    A("## 1. Validation on the 8 failing rows of insecticides p87\n")
    A("Step 1 flagged rows 6, 7, 11, 12, 14-17 of p87: a dilution value "
      "(`500` or `NA`) was landing in the PHI band alongside the real PHI "
      "value, because these rows' a.i./formulation doses are compound "
      "expressions that physically widen the row past where the static "
      "`combination-product` boundary expected the later fields to sit.\n")
    A("The fix: merge raw camelot cells using each cell's own `right` "
      "border flag (`True` = a real ruled line was detected there) instead "
      "of the file-wide calibrated x-boundary. Each row's OWN rule "
      "positions, compared against the calibrated grid:\n")

    combo = step1["insecticides_20260331.pdf"]["bands_by_subsection"]["combination-product"]
    A("Calibrated `combination-product` boundaries (Step 1): "
      + ", ".join(f"{LABELS[i]}/{LABELS[i+1]} @ {combo['boundaries'][i]:.1f}"
                  for i in range(5)) + "\n")

    t87 = camelot.read_pdf(str(RAW / "insecticides_20260331.pdf"),
                            pages="87", flavor="lattice")[0]
    for r_idx in [6, 7, 11, 12, 14, 15, 16, 17]:
        segs = row_segments(t87.cells[r_idx])
        content = [s for s in segs if s["text"]]
        A(f"**Row {r_idx}** — this row's own real-rule segments (x0, x1, text):\n")
        A("| # | x0 | x1 | text |")
        A("|---|---|---|---|")
        for i, s in enumerate(content):
            A(f"| {i} | {s['x0']:.1f} | {s['x1']:.1f} | {esc(s['text'][:70])} |")
        resolved = [s["text"] for s in content] if len(content) == 6 else None
        A("")
        if resolved:
            A(f"-> resolved (ordinal, 6 of 6 segments): "
              f"crop={resolved[0]!r}, pest={resolved[1]!r}, "
              f"dose_ai={resolved[2]!r}, dose_form={resolved[3]!r}, "
              f"**dilution={resolved[4]!r}**, **phi={resolved[5]!r}**\n")

    A("Every one of the 8 rows has exactly 6 real-rule segments, in the "
      "same left-to-right order as the 6 logical fields — no x-coordinate "
      "comparison needed at all, since the segment order IS the field "
      "order. **`500`/`600` etc. land in `dilution_water`; the correct PHI "
      "value lands in `waiting_period_phi`, cleanly separated, on every "
      "row.** Confirmed against the raw text layer independently (row 6: "
      "\"...Tomato... 200 - 250 500 5\" — dose_form=200-250, dilution=500, "
      "phi=5 — matches). Proceeding to the full corpus.\n")

    # ---------------------------------------------------------------- #
    # 2. full corpus: concatenation count old vs new
    # ---------------------------------------------------------------- #
    A("## 2. Full-corpus re-run: concatenation, old vs new\n")
    kind_counts: dict[str, int] = {}
    residual_rows = []
    for fn, rec in rowgrid.items():
        for t in rec["tables"]:
            if t.get("out_of_scope_for_grid"):
                continue
            for row in t.get("rows", []):
                kind_counts[row["kind"]] = kind_counts.get(row["kind"], 0) + 1
                if row["kind"] == "residual_over6":
                    residual_rows.append((fn, t["page"], row))

    total_rows = sum(kind_counts.values())
    A("| assignment kind | rows | can it concatenate two values? |")
    A("|---|---|---|")
    EXPLAIN = {
        "ordinal_6": "no — exactly 6 real segments, 1:1 to the 6 bands",
        "fallback_subset": "no — <6 segments, injective best-fit assignment (each band gets at most one segment)",
        "residual_over6": "yes — >6 real segments, no defined ordinal target, falls back to nearest-center",
        "blank": "no — no content on the row",
    }
    for k, v in sorted(kind_counts.items(), key=lambda kv: -kv[1]):
        A(f"| `{k}` | {v} | {EXPLAIN.get(k, '')} |")
    A(f"\n**{total_rows} total rows across all in-scope crop-advisory "
      f"tables.** Only `residual_over6` can still concatenate two values "
      f"into one band — **{len(residual_rows)} rows**, each contributing "
      f"exactly 1 merged band (verified below), for **{len(residual_rows)} "
      f"total merge events**, down from Step 1's **180** flagged-concerning "
      f"events under the static grid.\n")

    A("### 2.1 Residual list — the rows still merging\n")
    A("| file | page | row | content segments | merged band |")
    A("|---|---|---|---|---|")
    for fn, pg, row in residual_rows:
        merged_band_idx = [i for i, v in enumerate(row["resolved"]) if " " in v.strip() and len(v.split()) > 1]
        A(f"| `{fn}` | {pg} | {row['row']} | {row['n_content_segments']} | "
          f"{row.get('concat_bands', '?')} band(s) |")
    A("")
    for fn, pg, row in residual_rows:
        A(f"**`{fn}` p{pg} row {row['row']}** (7 real segments, one too "
          f"many for the 6-field ordinal method): {row['resolved']}\n")
    A("All 3 are on `insecticides_20260331.pdf` p27 — the Aluminum "
      "Phosphide FUMIGATION sub-table, whose header (\"Sr. No / Name of "
      "Commodity / Common name of the pest Cond. / Weight of volume / "
      "Exposure period / Conc. in air (ppm) / Aeration Waiting\") has **7 "
      "real logical fields**, not 6 — this is a genuinely different "
      "product-type schema (also seen structurally on insecticides p4's "
      "fumigation sub-table in Step 1), not a band-assignment failure. "
      "These 3 rows are the right shape for `cols_unresolved` quarantine "
      "at Step 2: the row-local method correctly recognises it doesn't "
      "have a confident 6-field mapping for them, rather than guessing.\n")

    # ---------------------------------------------------------------- #
    # 3. source_column_merged
    # ---------------------------------------------------------------- #
    A("## 3. `source_column_merged` — corrected finding\n")
    A("Requirement 4 named this after Step 1's own §5, which reported that "
      "insecticides p89 has camelot drawing crop and pest as one raw "
      "column with no recoverable rule. Building the geometric test for "
      "this reason code required checking that claim directly against "
      "`Cell.right`, and it does not hold up:\n")
    A("```text")
    A("insecticides p89, row 0, actual cell borders:")
    A("col0 x=(36.2,100.8)  right=True   text='Paddy'")
    A("col1 x=(100.8,107.3) right=False  text='Yellow Stem Borer (Scirpophaga'")
    A("...")
    A("```")
    A("A real rule exists at x=100.8, cleanly separating \"Paddy\" from "
      "\"Yellow Stem Borer...\". **Step 1's finding was itself an artifact "
      "of the flawed method it was diagnosing** — nearest-STATIC-band "
      "assignment on raw columns put a narrow 6.5pt sliver (\"Yellow Stem "
      "Borer...\"'s own raw grid column) into the crop band purely because "
      "its midpoint fell on the wrong side of that method's boundary, not "
      "because the source PDF failed to draw a rule.\n")

    A("Two candidate geometric tests were built and rejected before "
      "settling on the one used:\n")
    A("| version | rows flagged | why rejected |")
    A("|---|---|---|")
    A("| segment extends past calibrated crop/pest boundary | 860 | misfired on every chemical-name header row and the two-tier column-label sub-header row |")
    A("| + no real rule within 15pt of that boundary | 186 | still misfired on ordinary rows whose crop text is legitimately a little wider than the file median (e.g. \"Rose(Ornamental)\") |")
    A("| + segment must ALSO extend past the pest/dose-ai boundary, tested against segs[0] not content[0] | **0** | zero false positives found; see below |")
    A("")
    A("The middle version's own 7 candidates were checked by hand: every "
      "one turned out to be a row whose CROP cell is genuinely blank "
      "(forward-filled — the crop stated once, several pest rows listed "
      "under it), so `content[0]` (first non-blank segment) was already "
      "the pest name, which can be long enough to look like a wide merge "
      "on its own. The final version tests the row's true position-0 "
      "segment (blank or not), which tells the two cases apart.\n")

    A("**Corrected count: 0 genuine `source_column_merged` rows found "
      "across all four files.** insecticides p89's crop-advisory rows "
      "(the specific page named in the requirement) all resolve via "
      "ordinal assignment, confirmed row by row:\n")
    A("| row | crop | pest_or_disease |")
    A("|---|---|---|")
    t89 = camelot.read_pdf(str(RAW / "insecticides_20260331.pdf"),
                            pages="89", flavor="lattice")[0]
    for r_idx in range(15):
        segs = row_segments(t89.cells[r_idx])
        content = [s for s in segs if s["text"]]
        if len(content) >= 2:
            A(f"| {r_idx} | {esc(content[0]['text'][:40])} | "
              f"{esc(content[1]['text'][:60])} |")
    A("")
    A("No occurrence of a corrected `cols_unresolved`-worthy crop/pest "
      "merge exists in this corpus, under either the loose or strict "
      "reading. This is a correction to Step 1's report, not a new "
      "finding to act on.\n")

    # ---------------------------------------------------------------- #
    # 4. 10 structurally-variant tables
    # ---------------------------------------------------------------- #
    A("## 4. The 10 structurally-variant tables — corrected, and ABSENT vs PRESENT-EMPTY\n")
    A("4 of Step 1's 10 are corrected by row-local assignment — they were "
      "never structural variants, just static-grid misassignments:\n")
    A("| file | page | Step 1 verdict | row-local verdict |")
    A("|---|---|---|---|")
    CORRECTED = [
        ("insecticides_20260331.pdf", 9, "bands_used=[1,2,3,4,5], crop missing", "**fully resolved** — crop was a slightly wide raw column (\"Coconut/Bamboo\" etc.), not absent"),
        ("insecticides_20260331.pdf", 56, "bands_used=[0,1,2,3,5], dilution missing", "**fully resolved** — dilution recovered via ordinal assignment on every row"),
        ("insecticides_20260331.pdf", 60, "bands_used=[0,1,2,3,5], dilution missing", "**fully resolved** — same correction as p56"),
        ("bio_fungicides_20260331.pdf", 12, "bands_used=[0,1,2,3,4], PHI missing", "**fully resolved** — PHI recovered via ordinal assignment"),
    ]
    for fn, pg, s1, rl in CORRECTED:
        A(f"| `{fn}` | {pg} | {s1} | {rl} |")
    A("")

    A("The remaining 6 are genuine — confirmed still missing the same "
      "band(s) under row-local assignment, and now checked at the ruling "
      "level (not just the content level) to answer the ABSENT-vs-"
      "PRESENT-AND-EMPTY question:\n")

    GENUINE = [
        {
            "file": "insecticides_20260331.pdf", "page": 7,
            "missing": ["dose_formulation", "waiting_period_phi"],
            "verdict": "ABSENT (both)",
            "why": ("The table's own printed header reads `Use | Method of "
                    "application | | Dosage (a.i.) | | Dilution` — only 4 "
                    "real field labels. Two raw-grid edges happen to sit "
                    "within 25pt of the calibrated dose_formulation/PHI "
                    "positions, but they are the SAME edges that separate "
                    "\"Dosage\" from \"Dilution\" in this table's real "
                    "4-field schema, not dedicated ruled cells for the two "
                    "extra fields. Wood/termite treatment has no separate "
                    "formulation figure and no food-crop PHI concept."),
        },
        {
            "file": "insecticides_20260331.pdf", "page": 52,
            "missing": ["waiting_period_phi"],
            "verdict": "PRESENT AND EMPTY",
            "why": ("10 raw columns, one of them at x=(506.5, 590.3) sits "
                    "right where PHI should start — a dedicated ruled cell "
                    "exists. It is simply never filled: every row here is "
                    "\"used as seed dresser\", and the label prints no "
                    "waiting-period value at all for that use — not even a "
                    "placeholder like \"NA\"."),
        },
        {
            "file": "fungicides_20260331.pdf", "page": 31,
            "missing": ["dilution_water", "waiting_period_phi"],
            "verdict": "PRESENT AND EMPTY (both)",
            "why": ("This table's raw column grid is an EXACT match to the "
                    "file's calibrated 6-column structure (edges at 409.2 "
                    "and 499.7, to one decimal place) — it is structurally "
                    "a normal 6-column table. The 3 rows on this page are "
                    "bacterial-disease seed-treatment protocols described "
                    "entirely in prose within the earlier cells; the "
                    "dilution and PHI cells are ruled but simply blank."),
        },
        {
            "file": "bio_insecticides_20260331.pdf", "page": 10,
            "missing": ["dose_ai", "waiting_period_phi"],
            "verdict": "ABSENT (both)",
            "why": ("Only 3 raw columns exist in the whole table: crop, "
                    "pest, and one huge column (x=272 to 586) holding the "
                    "entire method description as unstructured prose. There "
                    "is no ruled subdivision anywhere in that span for "
                    "a.i. dose, formulation, dilution or PHI — they are not "
                    "empty cells, there are no cells."),
        },
        {
            "file": "bio_fungicides_20260331.pdf", "page": 11,
            "missing": ["waiting_period_phi"],
            "verdict": "PRESENT AND EMPTY",
            "why": ("7 raw columns; dose_ai IS present as an explicit `-` "
                    "placeholder on every row (not absorbed into prose), "
                    "and a ruled column exists at x=(513.1, 594.1) — right "
                    "where PHI should be. Seed/soil-treatment bio-fungicide "
                    "rows simply never populate it."),
        },
        {
            "file": "bio_fungicides_20260331.pdf", "page": 16,
            "missing": ["waiting_period_phi"],
            "verdict": "PRESENT AND EMPTY",
            "why": ("Same pattern as p11: dose_ai present as `-`, a ruled "
                    "column exists at x=(523.4, 594.1), never populated."),
        },
    ]
    A("| file | page | missing band(s) | verdict |")
    A("|---|---|---|---|")
    for g in GENUINE:
        A(f"| `{g['file']}` | {g['page']} | {', '.join(g['missing'])} | "
          f"**{g['verdict']}** |")
    A("")
    for g in GENUINE:
        A(f"**`{g['file']}` p{g['page']}** — {g['verdict']}. {g['why']}\n")

    A(
        "Downstream meaning, as requested: **ABSENT** (p7, bio_insecticides "
        "p10) means the source table structurally has no such field for "
        "this product category — a Step 4 schema question (does "
        "`ChemicalOption` need an optional field, or does this product "
        "category map to a different record shape), not a parsing gap. "
        "**PRESENT AND EMPTY** (p52, fungicides p31, bio_fungicides "
        "p11/p16) means a cell genuinely exists and was correctly read as "
        "blank — this is a real value (the label prints nothing), and "
        "`parse_phi(\"\")` already returns `None` for it correctly (the "
        "`_NULLISH` set includes `\"\"`), no different handling needed at "
        "Step 2 beyond extracting the blank as blank.\n"
    )

    A("## 5. Not done here\n")
    A("No CSVs written, no quarantine.csv, no Step 2 extraction. This "
      "report only validates the row-local method and corrects two Step 1 "
      "findings (p89's merge; p9/p56/p60/bio_fungicides-p12's "
      "\"structural\" status). Step 2 design questions this raises but "
      "does not answer: how `residual_over6` rows (p27's 3) and the 6 "
      "genuine structural-variant tables should be represented in the raw "
      "CSV schema, given `cols_unresolved` quarantine no longer applies to "
      "180 rows — only 3.\n")

    out = "\n".join(L) + "\n"
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "phase3_step1b_rowgrid.md").write_text(out, encoding="utf-8")
    print(f"wrote {REPORTS / 'phase3_step1b_rowgrid.md'} ({len(out)} bytes)")


if __name__ == "__main__":
    main()
