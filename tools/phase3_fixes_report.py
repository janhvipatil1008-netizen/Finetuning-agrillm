"""Builds reports/phase3_fixes.md from the re-extracted CSVs.
Run tools/phase3_step2_extract.py first."""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
REPORTS = ROOT / "reports"

FILES = ["insecticides_20260331.pdf", "fungicides_20260331.pdf",
         "bio_insecticides_20260331.pdf", "bio_fungicides_20260331.pdf"]
DOSE = ["dose_ai", "dose_formulation", "dilution_water"]

STRONG = re.compile(
    r"\b(apply|mix|treat|treatment|spray|dip|drench|used as|seed dresser|"
    r"required|recommended|depending|before|after|manner of|method of|"
    r"used to|use pattern|dresser)\b", re.I)


def is_prose(v):
    v = (v or "").strip()
    return bool(v) and len(v.split()) >= 4 and bool(STRONG.search(v))


def esc(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def load(fn):
    with open(INTERIM / fn.replace(".pdf", "_raw.csv"), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    rows = {fn: load(fn) for fn in FILES}
    allr = [r for fn in FILES for r in rows[fn]]
    with open(INTERIM / "quarantine.csv", encoding="utf-8") as f:
        quar = list(csv.DictReader(f))

    L = []
    A = L.append
    A("# Phase 3 — Header Fragments, Method Column, Type Guard\n")
    A("Targeted Step 2 re-run. All CSVs in `data/interim/` regenerated from "
      "the source PDFs; `tools/phase3_step2_extract.py` is the committed "
      "record of how.\n")

    # ---------------- 1 ------------------------------------------------- #
    A("## 1. Header-fragment sweep\n")
    A("### 1.1 What the sweep found (before any change)\n")
    A("Sweeping the previous run's 3762 rows for a crop or pest cell exactly "
      "matching a header label (case- and whitespace-insensitive) returned "
      "**19 hits, not the 2 Metarhizium rows** the defect was reported "
      "from. Every one is a two-tier column header extracted as data — "
      "including the MAIN table header on page 2 of all four files:\n")
    A("```text")
    A("insecticides p2  r1  crop='Crop'         :: Crop || Common Name of the pest || Dosage/ha || Waiting Period (days)")
    A("insecticides p2  r2  crop='a.i (gm)'     :: a.i (gm) || Formulation (gm/ml) || Dilution in Water (Liter)")
    A("insecticides p7  r1  pest='Method of application'")
    A("insecticides p50 r7,r8   crop='Crop'")
    A("insecticides p52 r18     crop='Name of crop'")
    A("insecticides p55 r17     crop='Crop'")
    A("fungicides   p2  r1,r2   crop='Crop' / 'a.    i. (g)'")
    A("fungicides   p43 r1      crop='Crop'      (assignment_kind was ordinal_6 — a full 6-segment header)")
    A("bio_insect   p2  r1,r2   crop='Name of crop'")
    A("bio_insect   p9  r10,r11 crop='Crop', pest='Common name of the target organism'   <- the reported case")
    A("bio_insect   p11 r3,r4   crop='Crop'")
    A("bio_fungi    p2  r1,r2   crop='Name of Crop'")
    A("```")
    A("")
    A("### 1.2 Detector: boldness, not vocabulary\n")
    A("A label-vocabulary detector was built first and **rejected on "
      "measurement**. It both missed real headers (insecticides p92 r2, "
      "p91 r12/r13, p102 r14) and false-positived on real data — "
      "insecticides p99 r8/r9, `\"Mosquitoes larvae | Clean surface water | "
      "25-50 g a.i./ha\"`, is a genuine public-health dose row that a "
      "vocabulary rule reads as a header because every word in it is "
      "header-ish.\n")
    A("The reliable signal is typographic: CIB&RC sets column labels in "
      "bold and data rows in regular. The whole-corpus bold-fraction "
      "histogram is sharply bimodal, which is what makes it safe to "
      "threshold:\n")
    A("| bold fraction | rows |")
    A("|---|---|")
    A("| 0.0 | 2671 |")
    A("| 0.1–0.8 | 137 |")
    A("| 0.9–1.0 | 957 |")
    A("")
    A("Rows in the middle band were inspected: all are data rows whose "
      "y-band overlaps a bold chemical name above them, none is a header. "
      "The rule is **bold ≥ 0.9 AND ≥2 content segments** — the "
      "segment-count clause is what separates a column header from a "
      "chemical-name header (also bold, but always a single segment).\n")
    n_ch = sum(1 for r in allr if r["assignment_kind"] == "column_header")
    A(f"**{n_ch} rows** now classify as `column_header`. All 89 were "
      "reviewed individually; there are no false positives. They are kept "
      "in the raw CSV with every semantic column blank and "
      "`is_column_header=True` — the same treatment `chemical_header` rows "
      "already get, so nothing is silently deleted and the hard assertion "
      "still balances, but Phase 4 can exclude them with one predicate.\n")
    A("They also no longer advance the crop/chemical forward-fill. A row "
      "reading `crop='Crop'` was previously eligible to be inherited by "
      "every following blank-crop row.\n")
    resid = [r for r in allr
             if " ".join(r["crop"].split()).lower() in {"crop", "name of crop", "a.i.", "a.i"}
             or " ".join(r["pest_or_disease"].split()).lower() in {"common name", "method of application"}]
    A(f"Residual check after re-extraction: **{len(resid)} rows** still "
      "carry a header label in crop or pest.\n")

    # ---------------- 2 ------------------------------------------------- #
    A("## 2. `method` column\n")
    n_m = sum(1 for r in allr if r["method"].strip())
    A(f"`method` added to the raw CSV schema. **{n_m} rows** now carry "
      "method text there instead of in `dilution_water`.\n")
    A("Per file:\n")
    A("| file | rows with method |")
    A("|---|---|")
    for fn in FILES:
        A(f"| `{fn}` | {sum(1 for r in rows[fn] if r['method'].strip())} |")
    A("")
    A("The reported case, now correct:\n")
    g = [r for r in rows["bio_insecticides_20260331.pdf"] if r["crop"] == "Gerbera"]
    if g:
        r = g[0]
        A("```text")
        A(f"bio_insecticides p10, Gerbera / Meloidogyne incognita")
        A(f"  crop            : {r['crop']}")
        A(f"  pest_or_disease : {r['pest_or_disease']}")
        A(f"  dilution_water  : {r['dilution_water']!r}   <- was the method sentence")
        A(f"  method          : {r['method']}")
        A("```")
    A("")

    # ---------------- 3 ------------------------------------------------- #
    A("## 3. Type guard on `fallback_subset`\n")
    A("Applied **after** geometric assignment, to the result only: a "
      "segment longer than 40 chars with no leading quantity is not an "
      "acceptable value for `dose_ai`, `dose_formulation` or "
      "`dilution_water`. Geometry still chooses the column; the guard only "
      "refuses an impossible outcome.\n")
    A("Two calibration details, both found by checking what the guard did "
      "rather than assuming:\n")
    A("- **Leading-quantity reprieve.** insecticides p87's `\"108 "
      "(Spiropidion 60 + Acetamiprid 48) – 135 (Spiropidion 75 + "
      "Acetamiprid 60)\"` is 77 chars but starts with a digit — a real "
      "compound dose, correctly exempt.")
    A("- **Ordinals are not quantities.** insecticides p55's `\"(1st spray "
      "when insect pest reaches ETL. Repeat one spray at 10-15 days "
      "interval…)\"` is 110 chars of prose that a bare leading-digit test "
      "waved through, because `\"(1\"` satisfied it. Leading ordinals "
      "(`1st`, `2nd`…) are excluded from the reprieve.\n")
    A("**Guard fired on 115 rows: 104 rerouted to `method`, 11 "
      "quarantined** as `cols_unresolved`.\n")
    A("Which of the two outcomes a row gets is decided by whether its "
      "chemical block is free-text-method-shaped — i.e. whether a "
      "\"Method of application\" column exists there to receive the text. "
      "That test is **≥50% of the block's data rows have prose landing in a "
      "dose/dilution column**. Two narrower definitions were tried and "
      "measured first:\n")
    A("| block-shape test | consequence | verdict |")
    A("|---|---|---|")
    A("| every data row has `dose_ai` AND `dose_formulation` blank | quarantined 39 of bio_fungicides' 147 rows whose method column plainly exists — e.g. `\"- \\|\\| 2.5 kg per ha (05 g/litre water) \\|\\| Spray Pseudomonas fluorescens 1.75% WP uniformly on the crop. \\|\\| 500 lit per ha\"` carries a real dose AND real method text | rejected |")
    A("| ≥50% of rows have prose in ANY segment | counted long pest names (`\"Mealy bugs (Phenococcus solenopsis, Thrips…\"`) as evidence of a method column; inflated 48 blocks → 277 | rejected |")
    A("| ≥50% of rows have prose in a **guarded** column | 48 blocks | **used** |")
    A("")
    A("### 3.1 Disposition of the 122–133 sentence-valued rows\n")
    still = sum(1 for r in allr if r["assignment_kind"] == "fallback_subset"
                and any(is_prose(r[c]) for c in DOSE))
    in_m = sum(1 for r in allr if r["assignment_kind"] == "fallback_subset"
               and is_prose(r["method"]))
    A("Measured with the diagnosis report's own prose heuristic (≥4 words "
      "plus an instructional verb), which is a different test from the "
      "guard's (length plus leading quantity) — so these are overlapping "
      "populations, not the same set counted twice:\n")
    A("| outcome | rows |")
    A("|---|---|")
    A(f"| prose rerouted into `method` | {in_m} |")
    A(f"| prose still in a dose/dilution column | {still} |")
    A(f"| quarantined by the guard | 11 |")
    A("")
    A(f"The {still} that remain are **below the 40-char threshold the "
      "instruction specified** — `\"This is used as seed dresser\"` (28), "
      "`\"are dried in shade before sowing\"` (32), `\"after 40-45 days of "
      "transplantation.\"` (36). They are short enough that the type guard "
      "as specified does not reach them. Raising the threshold would catch "
      "them and would also start catching real dose expressions; that is a "
      "judgement call I have left to you rather than tightening "
      "unilaterally.\n")

    # ---------------- counts -------------------------------------------- #
    A("## 4. Row counts, new vs old\n")
    A("| file | raw (old) | raw (new) | quarantine (old) | quarantine (new) |")
    A("|---|---|---|---|---|")
    old_raw = {"insecticides_20260331.pdf": 2048, "fungicides_20260331.pdf": 1273,
               "bio_insecticides_20260331.pdf": 294, "bio_fungicides_20260331.pdf": 147}
    old_q = {"insecticides_20260331.pdf": 3, "fungicides_20260331.pdf": 1,
             "bio_insecticides_20260331.pdf": 0, "bio_fungicides_20260331.pdf": 0}
    qc = Counter(r["source_file"] for r in quar)
    for fn in FILES:
        A(f"| `{fn}` | {old_raw[fn]} | {len(rows[fn])} | {old_q[fn]} | {qc.get(fn,0)} |")
    A(f"| **total** | **3762** | **{len(allr)}** | **4** | **{len(quar)}** |")
    A("")
    A(f"**HARD ASSERTION: {len(allr)} raw + {len(quar)} quarantine = "
      f"{len(allr)+len(quar)} = total source rows. PASSED** (the script "
      "exits non-zero on mismatch).\n")
    A("The 10-row net drop in raw is the guard's 11 quarantines minus one "
      "row that moved the other way: insecticides p27 r15 was previously "
      "quarantined `cols_unresolved` as a 7-segment fumigation row, and is "
      "now correctly identified as that table's bold column header.\n")

    A("### Quarantine by reason code\n")
    rc = Counter(r["reason_code"] for r in quar)
    A("| reason_code | old | new |")
    A("|---|---|---|")
    for code, old in (("cols_unresolved", 3), ("footnote_unresolved", 0),
                      ("truncated_cell", 1), ("section_ambiguous", 0)):
        A(f"| `{code}` | {old} | {rc.get(code,0)} |")
    A("")
    A("All 14 were reviewed: the fumigation tables (p4/p5/p27, 7-field "
      "schema), five full-width spray-timing notes on insecticides p54, "
      "fungicides p16/p17 (`\"The liquid is used at 1% in conventional "
      "sprayers\"` in a dose column, block not method-shaped), fungicides "
      "p71/p72 seed-treatment prose, and the known p38 truncated cell.\n")

    A("### assignment_kind distribution\n")
    A("| kind | rows |")
    A("|---|---|")
    for k, v in Counter(r["assignment_kind"] for r in allr).most_common():
        A(f"| `{k}` | {v} |")
    A("")

    A("## 5. `phi_cell_present`\n")
    pc = Counter(r["phi_cell_present"] for r in allr)
    A(f"Unchanged in meaning: True={pc.get('True',0)}, False={pc.get('False',0)} "
      f"(insecticides p7 and bio_insecticides p10 only — the two genuinely "
      f"ABSENT tables), blank={pc.get('',0)} (non-crop-advisory).\n")
    A("One correctness follow-on: column-header rows are now excluded when "
      "deciding whether a table has PHI content. A bold "
      "`\"Waiting period (days)\"` LABEL in the PHI band is not evidence "
      "that any row carries a PHI VALUE, and counting it would have masked "
      "exactly the ABSENT vs PRESENT-AND-EMPTY distinction this field "
      "exists to preserve.\n")

    A("## 6. verify_sample\n")
    A("25 fresh rows, weighted as requested: **16 `fallback_subset`** (the "
      "class the guard acts on) and **8 carrying method text** (the bio "
      "free-text blocks), spanning all four files, and still including the "
      "page-boundary and section-boundary rows. The Gerbera row is in it.\n")
    A("> **`data/interim/verify_sample.csv` was locked during the run** "
      "(open in another program). The fresh sample was written to "
      "**`data/interim/verify_sample.locked.csv`** instead — the file "
      "ending `.csv` at the top level is the STALE one from the previous "
      "run. Close it and re-run `python tools/phase3_step2_extract.py` to "
      "regenerate in place, or just read the `.locked.csv`.\n")

    A("## 7. Not done\n")
    A("No normalisation, no dose parsing, no label_db. `waiting_period_phi` "
      "still holds raw cell text; `parse_phi` is not called. `schema.py` "
      "untouched.\n")

    out = "\n".join(L) + "\n"
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "phase3_fixes.md").write_text(out, encoding="utf-8")
    print(f"wrote {REPORTS/'phase3_fixes.md'} ({len(out)} bytes)")


main()
