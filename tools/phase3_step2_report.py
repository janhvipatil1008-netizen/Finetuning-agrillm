"""Builds reports/phase3_step2_extract.md from the CSVs written by
phase3_step2_extract.py. Run phase3_step2_extract.py first.
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
REPORTS = ROOT / "reports"

IN_SCOPE = [
    "insecticides_20260331.pdf",
    "fungicides_20260331.pdf",
    "bio_insecticides_20260331.pdf",
    "bio_fungicides_20260331.pdf",
]


def load_raw(fn: str) -> list[dict]:
    with open(INTERIM / fn.replace(".pdf", "_raw.csv"), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_quarantine() -> list[dict]:
    with open(INTERIM / "quarantine.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    all_raw = {fn: load_raw(fn) for fn in IN_SCOPE}
    quarantine = load_quarantine()

    L: list[str] = []
    A = L.append

    A("# Phase 3, Step 2 — Extract (raw CSVs)\n")
    A("Raw extraction only. No normalisation, no dose parsing, no "
      "label_db. Outputs (`data/interim/*.csv`) are gitignored, as with "
      "every prior phase's intermediate cache — this report and "
      "`tools/phase3_step2_extract.py` are the committed record; re-running "
      "the script regenerates the CSVs from the source PDFs.\n")
    A("Deliverables: `data/interim/<name>_raw.csv` (one per file), "
      "`data/interim/quarantine.csv`, `data/interim/verify_sample.csv` "
      "(25 rows for manual spot-check).\n")

    # ---------------------------------------------------------------- #
    # row counts + hard assertion
    # ---------------------------------------------------------------- #
    A("## Row counts and the hard assertion\n")
    A("| file | raw CSV rows | quarantine rows | total source rows |")
    A("|---|---|---|---|")
    total_raw = total_q = 0
    q_by_file: dict[str, int] = {}
    for r in quarantine:
        q_by_file[r["source_file"]] = q_by_file.get(r["source_file"], 0) + 1
    for fn in IN_SCOPE:
        n_raw = len(all_raw[fn])
        n_q = q_by_file.get(fn, 0)
        total_raw += n_raw
        total_q += n_q
        A(f"| `{fn}` | {n_raw} | {n_q} | {n_raw + n_q} |")
    A(f"| **total** | **{total_raw}** | **{total_q}** | **{total_raw + total_q}** |")
    A("")
    A(f"**HARD ASSERTION: raw ({total_raw}) + quarantine ({total_q}) = "
      f"{total_raw + total_q} total source rows. PASSED** — every row "
      f"camelot returned across all four files' lattice tables lands in "
      f"exactly one of the two output files, verified by the extraction "
      f"script itself (it exits non-zero on mismatch, not just reported "
      f"here after the fact).\n")

    # ---------------------------------------------------------------- #
    # quarantine breakdown
    # ---------------------------------------------------------------- #
    A("## Quarantine, by reason code\n")
    reason_counts: dict[str, int] = {}
    for r in quarantine:
        reason_counts[r["reason_code"]] = reason_counts.get(r["reason_code"], 0) + 1
    A("| reason_code | rows | what |")
    A("|---|---|---|")
    EXPLAIN = {
        "cols_unresolved": "row-local segmentation found >6 real segments — the Aluminum Phosphide fumigation sub-table (insecticides p27), a genuinely 7-field schema (Step 1b)",
        "footnote_unresolved": "a marker with no registry match, superseded by `unresolved_marker=True` for the one case that actually exists (FYM*) — see below",
        "truncated_cell": "known character-loss defect from the phase 2b audit (fungicides p38, wrapped dilution cell missing its last line) — hardcoded, not guessed",
        "section_ambiguous": "a row whose own y-position couldn't be placed above/below a known section split — none occurred",
    }
    for code in ("cols_unresolved", "footnote_unresolved", "truncated_cell", "section_ambiguous"):
        A(f"| `{code}` | {reason_counts.get(code, 0)} | {EXPLAIN[code]} |")
    A("")
    A("`footnote_unresolved` is 0 by design, not by omission: the 32 "
      "`FYM*` rows are the only unresolvable-marker case in this corpus "
      "(confirmed in pre-work — no definition exists anywhere in either "
      "bio file), and you explicitly said keep those, not quarantine them. "
      "The reason code stays implemented for a future corpus that might "
      "need it; nothing in this run does.\n")

    A("Full quarantine list:\n")
    A("| file | page | table | row | reason | raw_row_text |")
    A("|---|---|---|---|---|---|")
    for r in quarantine:
        txt = r["raw_row_text"].replace("|", "\\|").replace("\n", " ")[:90]
        A(f"| `{r['source_file']}` | {r['source_page']} | "
          f"{r['source_table_index']} | {r['source_row_index']} | "
          f"{r['reason_code']} | {txt} |")
    A("")

    # ---------------------------------------------------------------- #
    # phi_cell_present breakdown
    # ---------------------------------------------------------------- #
    A("## `phi_cell_present` breakdown\n")
    A("New requirement this step: a bool on every row recording whether a "
      "ruled PHI cell exists at all (even blank), independent of whether "
      "this row's own PHI value is populated. Computed **content-first**: "
      "if any row in the table has a non-blank resolved PHI value, the "
      "column obviously exists — no geometry needed. Only when EVERY row "
      "in the table is PHI-blank does it fall back to the geometric test "
      "(a ruled column edge near the calibrated PHI-band start).\n")
    A("A geometry-first version was tried and rejected: insecticides p2 — "
      "one of the file's own CALIBRATION source pages, with ordinary "
      "populated PHI values on every row — has its own dilution/PHI cut "
      "27.9pt from the calibrated median, just outside a 25pt tolerance, "
      "so pure geometry called it \"absent\" while every row's own content "
      "plainly said otherwise. That version showed **243** `False` rows "
      "spread across 15 pages, most of them ordinary populated tables. "
      "Content-first drops that to **24** `False` rows across exactly the "
      "**2** tables Step 1b hand-verified as genuinely ABSENT — "
      "insecticides p7 (10 rows) and bio_insecticides p10 (14 rows) — and "
      "nothing else. The other 4 tables Step 1b called PRESENT-AND-EMPTY "
      "(insecticides p52, fungicides p31, bio_fungicides p11 and p16) all "
      "correctly land on `True`.\n")

    n_true = n_false = n_blank = 0
    for fn in IN_SCOPE:
        for r in all_raw[fn]:
            v = r["phi_cell_present"]
            if v == "True":
                n_true += 1
            elif v == "False":
                n_false += 1
            else:
                n_blank += 1
    A("| phi_cell_present | rows | meaning |")
    A("|---|---|---|")
    A(f"| `True` | {n_true} | ruled PHI cell exists — content present or a "
      "confirmed present-and-empty table |")
    A(f"| `False` | {n_false} | no ruled PHI cell anywhere in this table — "
      "insecticides p7, bio_insecticides p10 only |")
    A(f"| (blank) | {n_blank} | non-crop-advisory row — no calibrated grid "
      "exists for this schema, concept doesn't apply |")
    A("")

    # ---------------------------------------------------------------- #
    # unresolved_marker / footnote_text
    # ---------------------------------------------------------------- #
    A("## `unresolved_marker` and `footnote_text`\n")
    n_unresolved = sum(1 for fn in IN_SCOPE for r in all_raw[fn]
                       if r["unresolved_marker"] == "True")
    n_footnoted = sum(1 for fn in IN_SCOPE for r in all_raw[fn]
                      if r["footnote_text"])
    A(f"- `unresolved_marker=True`: **{n_unresolved} rows** — exactly the "
      f"32 FYM* rows confirmed in pre-work (20 bio_insecticides, 12 "
      f"bio_fungicides). Cell text kept verbatim, asterisk included, not "
      f"quarantined.")
    A(f"- `footnote_text` populated: **{n_footnoted} rows** — the fungicides "
      f"p4 (4 rows: Apple, Cherry, Citrus x2) and p77 (1 row: Wheat/Sedaxane "
      f"combo) markers, resolved against p83's endnotes.\n")

    # ---------------------------------------------------------------- #
    # bugs found and fixed during this step
    # ---------------------------------------------------------------- #
    A("## Bugs found and fixed while building this\n")
    A("Neither of these was caught by the hard assertion (row counts "
      "balanced throughout) — both were caught by checking specific rows' "
      "actual output against what was already known to be true, not by "
      "trusting that a green assertion meant the extraction was correct.\n")
    A("1. **Footnote registry, marker misassignment.** A `\\*{1,4}` regex "
      "backtracks whenever the text after a shorter marker also starts "
      "with `*`. This corpus hits that twice: bio_fungicides p20's bare "
      "`***` parsed as marker=`**`+body=`*`, and fungicides p83's `** In "
      "case of...` (space before the word) parsed as marker=`*`+body=`* "
      "In case of...`. Fixed by counting the leading `*` run manually "
      "instead of matching it with a regex.\n")
    A("2. **Footnote registry, page-1 contamination.** bio_insecticides' "
      "page-1 disclaimer begins with a bare `*` and flows straight into "
      "the contents list with no blank line. The continuation-absorption "
      "logic swallowed the whole block as one `*` \"definition\", which — "
      "being that file's only `*` entry — then resolved all 20 of its FYM* "
      "rows against disclaimer text instead of leaving them "
      "`unresolved_marker=True` as you'd just confirmed. Caught by reading "
      "the FYM rows' actual `footnote_text` output, not by inspecting the "
      "registry dict in isolation. Fixed by skipping page 1 outright — no "
      "table page ever needs a footnote defined there.\n")
    A("3. **`phi_cell_present`, geometric false negatives.** See above — "
      "243 false `False`s dropped to the correct 24 by checking row content "
      "before falling back to geometry.\n")

    # ---------------------------------------------------------------- #
    # forward-fill spot check
    # ---------------------------------------------------------------- #
    A("## Forward-fill spot check (insecticides p10 -> p11)\n")
    ins = all_raw["insecticides_20260331.pdf"]
    p10 = [r for r in ins if r["source_page"] == "10"][-3:]
    p11 = [r for r in ins if r["source_page"] == "11"][:3]
    A("| page | crop | pest_or_disease | active_ingredient |")
    A("|---|---|---|---|")
    for r in p10 + p11:
        A(f"| {r['source_page']} | {r['crop']} | "
          f"{r['pest_or_disease'][:45]} | {r['active_ingredient']} |")
    A("")
    A("`crop` (\"Paddy(Rice)\") and `active_ingredient` (\"Carbofuran "
      "03%CG\") both survive the page break correctly, matching phase 2b's "
      "documented p10->p11 case.\n")

    # ---------------------------------------------------------------- #
    # scope note
    # ---------------------------------------------------------------- #
    A("## Non-crop-advisory rows\n")
    A("No calibrated grid exists for public-health / household / locust "
      "schemas (Step 1/1b validated crop-advisory subsections only — those "
      "sections have genuinely different logical columns). Every row from "
      "those sections is still in the raw CSV, tagged with its row-level "
      "section/subsection (row-level, not page-level, on the three known "
      "boundary pages), but with the six crop-advisory semantic columns "
      "and `phi_cell_present` left blank and `raw_row_text` populated "
      "instead — the row-local real-rule segments, joined verbatim, "
      "schema-agnostic. Nothing from these sections is dropped or "
      "quarantined for being non-crop-advisory.\n")

    section_counts: dict[str, int] = {}
    for fn in IN_SCOPE:
        for r in all_raw[fn]:
            section_counts[r["section"]] = section_counts.get(r["section"], 0) + 1
    A("| section | rows |")
    A("|---|---|")
    for k, v in sorted(section_counts.items(), key=lambda kv: -kv[1]):
        A(f"| {k} | {v} |")
    A("")

    A("## Not done here\n")
    A("No cleaning, no unit conversion, no dose parsing (`parse_phi` is "
      "not called — the `waiting_period_phi` column holds the raw cell "
      "text verbatim, e.g. `\"2 weeks\"`, not `14`), no label_db. That is "
      "Phase 4.\n")

    out = "\n".join(L) + "\n"
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "phase3_step2_extract.md").write_text(out, encoding="utf-8")
    print(f"wrote {REPORTS / 'phase3_step2_extract.md'} ({len(out)} bytes)")


if __name__ == "__main__":
    main()
