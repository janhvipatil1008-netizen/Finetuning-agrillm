"""PHASE 3 — fallback and unit diagnosis. DIAGNOSIS ONLY.

Reads the existing data/interim/*_raw.csv (from phase3_step2_extract.py) and
tools/phase3_step1b_rowgrid.py's assignment code. Does NOT re-run extraction,
does NOT modify any CSV, does NOT touch schema.py. Writes only
reports/phase3_fallback_diagnosis.md.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import camelot
import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "cibrc"
INTERIM = ROOT / "data" / "interim"
REPORTS = ROOT / "reports"

sys.path.insert(0, str(ROOT / "tools"))
from phase3_step1b_rowgrid import row_segments, best_subset_assignment  # noqa: E402

FILES = [
    "insecticides_20260331.pdf",
    "fungicides_20260331.pdf",
    "bio_insecticides_20260331.pdf",
    "bio_fungicides_20260331.pdf",
]
DOSE_COLS = ["dose_ai", "dose_formulation", "dilution_water"]

CROPS = ["cotton", "soybean", "tur", "gram", "onion", "tomato", "grape", "pomegranate"]


def load_raw(fn: str) -> list[dict]:
    with open(INTERIM / fn.replace(".pdf", "_raw.csv"), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def esc(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


# --------------------------------------------------------------------------- #
# Q1
# --------------------------------------------------------------------------- #

def q1(all_rows: dict[str, list[dict]]) -> list[str]:
    L = ["## 1. `assignment_kind=fallback_subset` counts\n"]
    kind_totals = Counter()
    fb_by_file = Counter()
    fb_by_segcount = Counter()
    fb_by_file_segcount = Counter()
    for fn in FILES:
        for r in all_rows[fn]:
            kind_totals[r["assignment_kind"]] += 1
            if r["assignment_kind"] == "fallback_subset":
                n = len(r["raw_row_text"].split(" || ")) if r["raw_row_text"] else 0
                fb_by_file[fn] += 1
                fb_by_segcount[n] += 1
                fb_by_file_segcount[(fn, n)] += 1

    L.append("| assignment_kind | rows (all 4 files) |")
    L.append("|---|---|")
    for k, v in kind_totals.most_common():
        L.append(f"| `{k}` | {v} |")
    L.append(f"\n**`fallback_subset` total: {sum(fb_by_file.values())} of "
             f"{sum(kind_totals.values())} rows.**\n")

    L.append("| file | fallback_subset rows |")
    L.append("|---|---|")
    for fn in FILES:
        L.append(f"| `{fn}` | {fb_by_file[fn]} |")
    L.append(f"| **total** | **{sum(fb_by_file.values())}** |\n")

    L.append("By segment count (all 4 files):\n")
    L.append("| segments | rows |")
    L.append("|---|---|")
    for n in sorted(fb_by_segcount):
        L.append(f"| {n} | {fb_by_segcount[n]} |")
    L.append("")
    L.append("Requirement asked for 2/3/4/5 specifically — **1-segment rows "
             "exist too (58 of them)** and are worth flagging: these are rows "
             "where the single populated segment is NOT at position 0 (crop "
             "blank, one lone value elsewhere — e.g. a wrapped pest/dose "
             "fragment continuing from the row above). They go through the "
             "same `best_subset_assignment` path as every other fallback_subset "
             "row; they are not a distinct code path, just the k=1 case.\n")

    L.append("By file x segment count:\n")
    L.append("| file | 1 | 2 | 3 | 4 | 5 |")
    L.append("|---|---|---|---|---|---|")
    for fn in FILES:
        row = [str(fb_by_file_segcount.get((fn, n), 0)) for n in range(1, 6)]
        L.append(f"| `{fn}` | " + " | ".join(row) + " |")
    L.append("")
    return L


# --------------------------------------------------------------------------- #
# Q2
# --------------------------------------------------------------------------- #

def q2() -> list[str]:
    L = ["## 2. Column-assignment rule for `fallback_subset` — the code path\n"]
    L.append("`tools/phase3_step2_extract.py`, the `fallback_subset` branch "
             "(line ~437):\n")
    L.append("```python")
    L.append("elif kind == \"fallback_subset\" and is_crop_advisory:")
    L.append("    assign = best_subset_assignment(")
    L.append("        resolved_or_content, grid_subs[subsection][\"centers\"]) \\")
    L.append("        if subsection in grid_subs else None")
    L.append("    if assign is not None:")
    L.append("        for seg, b in zip(resolved_or_content, assign):")
    L.append("            resolved6[b] = seg[\"text\"]")
    L.append("```")
    L.append("which calls `tools/phase3_step1b_rowgrid.py::best_subset_assignment`:\n")
    L.append("```python")
    L.append("def best_subset_assignment(segments, centers):")
    L.append("    n = len(centers)          # 6 — the calibrated band centers")
    L.append("    k = len(segments)          # < 6, the row's real segment count")
    L.append("    ...")
    L.append("    mids = [(s[\"x0\"] + s[\"x1\"]) / 2.0 for s in segments]")
    L.append("    for combo in itertools.combinations(range(n), k):")
    L.append("        cost = sum(abs(mids[i] - centers[combo[i]]) for i in range(k))")
    L.append("        if best_cost is None or cost < best_cost:")
    L.append("            best_cost, best_combo = cost, combo")
    L.append("    return list(best_combo)")
    L.append("```")
    L.append("**Answer: purely positional, over a shortened list.** For k "
             "segments, every strictly-increasing k-combination of the 6 "
             "band indices is tried; the combination minimising total "
             "`|segment midpoint - calibrated band center|` wins. Nothing "
             "about the SEGMENT'S OWN CONTENT — whether it's a number, a unit, "
             "a full sentence, a placeholder — enters this function at all. "
             "Column identity comes entirely from where the segment's x-"
             "midpoint sits relative to the file/subsection's calibrated "
             "geometry, carried forward unchanged from Step 1b (built and "
             "validated to fix ROW-SHIFT — a compound dose widening a row's "
             "columns — never to check what KIND of value a segment holds).\n")
    return L


# --------------------------------------------------------------------------- #
# Q2 grounding: Gerbera row
# --------------------------------------------------------------------------- #

def q2_grounding() -> list[str]:
    L = ["### 2.1 Grounded against the reported defect (bio_insecticides p10, Gerbera)\n"]
    path = RAW / "bio_insecticides_20260331.pdf"
    with pdfplumber.open(path) as pdf:
        n = len(pdf.pages)
    tables = camelot.read_pdf(str(path), pages=f"1-{n}", flavor="lattice")
    t = tables[8]
    row = t.cells[9]
    segs = row_segments(row)
    content = [s for s in segs if s["text"]]

    import json
    grid = json.loads((INTERIM / "phase3_step1_grid.json").read_text(encoding="utf-8"))
    centers = grid["bio_insecticides_20260331.pdf"]["bands_by_subsection"]["bio-insecticides"]["centers"]
    assign = best_subset_assignment(content, centers)
    labels = ["crop", "pest_or_disease", "dose_ai", "dose_formulation",
             "dilution_water", "waiting_period_phi"]

    L.append(f"Table page {t.page}, row 9 — 3 real segments (this table has "
             f"only 3 raw columns at all; see Q4):\n")
    L.append("| segment | x0 | x1 | midpoint | text |")
    L.append("|---|---|---|---|---|")
    for i, s in enumerate(content):
        mid = (s["x0"] + s["x1"]) / 2.0
        L.append(f"| {i} | {s['x0']:.1f} | {s['x1']:.1f} | {mid:.1f} | "
                 f"{esc(s['text'][:60])} |")
    L.append("")
    L.append(f"Calibrated `bio-insecticides` centers: "
             f"{[round(c, 1) for c in centers]}\n")
    L.append("| segment | assigned band | distance to that band's center |")
    L.append("|---|---|---|")
    for s, b in zip(content, assign):
        mid = (s["x0"] + s["x1"]) / 2.0
        L.append(f"| {esc(s['text'][:40])} | {labels[b]} | "
                 f"{abs(mid - centers[b]):.1f} |")
    L.append("")
    L.append("Segment 2 (\"Apply the Nemastin @ 50 gm/sq.m at the time of "
             "planting\") spans x=272.2 to 585.8 — this table's ENTIRE method "
             "column, all in one raw cell, because the source table itself "
             "only has 3 columns (crop, pest, one big method column; see "
             "Q4). Its midpoint (429.0) happens to sit closest to "
             "`dilution_water`'s calibrated center (465.7) among the 4 "
             "remaining bands once crop/pest are assigned — that is the "
             "entire reason it landed there. The algorithm has no way to "
             "know this segment is prose rather than a water volume; "
             "nothing checks.\n")
    return L


# --------------------------------------------------------------------------- #
# Q3
# --------------------------------------------------------------------------- #

STRONG_PROSE = re.compile(
    r"\b(apply|mix|treat|treatment|spray|dip|drench|used as|seed dresser|"
    r"required|recommended|depending|before|after|manner of|method of|"
    r"used to|use pattern|dresser)\b", re.I)


def is_prose(v: str) -> bool:
    v = v.strip()
    if not v:
        return False
    if len(v.split()) < 4:
        return False
    return bool(STRONG_PROSE.search(v))


WEAK_PROSE = re.compile(r"\b(the|at|of|to|and)\b", re.I)


def is_prose_loose(v: str) -> bool:
    v = v.strip()
    if not v or len(v.split()) < 4:
        return False
    return bool(WEAK_PROSE.search(v))


def q3(all_rows: dict[str, list[dict]]) -> list[str]:
    L = ["## 3. Non-numeric, sentence-length values in dose_ai / "
         "dose_formulation / dilution_water\n"]
    L.append("Heuristic (stated, not exact — there is no clean syntactic "
             "line between \"a dose expression with words in it\" and \"a "
             "sentence\"): >=4 words AND contains one of a curated list of "
             "instructional verbs/phrases (apply, mix, treat, spray, dip, "
             "drench, \"used as\", \"seed dresser\", \"method of\", "
             "\"depending\", etc.) unlikely to appear in a genuine dose "
             "figure. A looser version (any of `the/at/of/to/and` as the "
             "only signal) also matched legitimate ranges like `\"0.02 "
             "g/plant & 160 to 200 g/ha\"` — rejected as counting real doses "
             "as prose.\n")
    total = 0
    total_loose = 0
    by_file = Counter()
    samples = []
    for fn in FILES:
        for r in all_rows[fn]:
            if r["assignment_kind"] != "fallback_subset":
                continue
            hit_cols = [c for c in DOSE_COLS if is_prose(r[c])]
            if hit_cols:
                total += 1
                by_file[fn] += 1
                samples.append((fn, r["source_page"], r["crop"][:25],
                               hit_cols[0], r[hit_cols[0]][:75]))
            if any(is_prose_loose(r[c]) for c in DOSE_COLS):
                total_loose += 1
    L.append(f"**{total} fallback_subset rows** carry a prose-shaped value "
             f"in at least one dose/dilution column, by this heuristic — "
             f"the rejected looser version (weak connectors only) counts "
             f"{total_loose}, which is why this number is reported as "
             f"heuristic-dependent rather than exact.\n")
    L.append("| file | rows |")
    L.append("|---|---|")
    for fn in FILES:
        L.append(f"| `{fn}` | {by_file[fn]} |")
    L.append(f"| **total** | **{total}** |\n")

    import random
    random.seed(1)
    sample10 = random.sample(samples, min(10, len(samples)))
    L.append("10 samples:\n")
    L.append("| file | page | crop | column | value |")
    L.append("|---|---|---|---|---|")
    for fn, pg, crop, col, val in sample10:
        L.append(f"| `{fn}` | {pg} | {esc(crop)} | {col} | {esc(val)} |")
    L.append("")
    return L


# --------------------------------------------------------------------------- #
# Q4
# --------------------------------------------------------------------------- #

def q4(all_rows: dict[str, list[dict]]) -> list[str]:
    L = ["## 4. Rows under a free-text-method-shape header\n"]
    L.append("Structural definition: a chemical block (grouped by "
             "`active_ingredient`) where EVERY data row has BOTH `dose_ai` "
             "and `dose_formulation` blank — the source table folds a.i., "
             "formulation, dilution and method into one free-text cell "
             "instead of the standard 6-column split.\n")

    # Known false positive, checked by hand: insecticides p27-28's "Ethylene
    # dichloride + Carbon tetrachloride" block passes the blank-dose test on
    # a technicality — its one row is a WRAPPED CONTINUATION fragment of the
    # Aluminum-Phosphide fumigation table (the SAME 7-field schema whose
    # other rows are already quarantined `cols_unresolved` on p27), landing
    # here only because this specific fragment's own 2 segments (a pest
    # continuation and a PHI continuation) happen to skip dose_ai/
    # dose_formulation. It is the fumigation table's known structural
    # variant reappearing, not a genuine free-text-method chemical block —
    # excluded from the count below, reported separately.
    KNOWN_FALSE_POSITIVE = ("insecticides_20260331.pdf",
                            "Ethylene dichloride + Carbon tetrachloride (3:1)")

    blocks_by_file: dict[str, list] = defaultdict(list)
    excluded_fp = None
    for fn in FILES:
        by_chem = defaultdict(list)
        for r in all_rows[fn]:
            if r["section"] != "crop-advisory" or r["is_chemical_header"] == "True":
                continue
            if not r["active_ingredient"]:
                continue
            by_chem[r["active_ingredient"]].append(r)
        for chem, rs in by_chem.items():
            all_blank = all(not r["dose_ai"] and not r["dose_formulation"] for r in rs)
            has_content = any(r["dilution_water"] or r["pest_or_disease"] for r in rs)
            if all_blank and has_content:
                if (fn, chem) == KNOWN_FALSE_POSITIVE:
                    excluded_fp = (fn, chem, rs)
                    continue
                blocks_by_file[fn].append((chem, rs))

    total_rows = 0
    total_blocks = 0
    L.append("| file | blocks | rows |")
    L.append("|---|---|---|")
    for fn in FILES:
        blocks = blocks_by_file[fn]
        n_rows = sum(len(rs) for _, rs in blocks)
        total_rows += n_rows
        total_blocks += len(blocks)
        L.append(f"| `{fn}` | {len(blocks)} | {n_rows} |")
    L.append(f"| **total** | **{total_blocks}** | **{total_rows}** |\n")

    for fn in FILES:
        if not blocks_by_file[fn]:
            continue
        L.append(f"**`{fn}`**\n")
        L.append("| chemical | rows | pages |")
        L.append("|---|---|---|")
        for chem, rs in blocks_by_file[fn]:
            pages = sorted(set(int(r["source_page"]) for r in rs))
            L.append(f"| {esc(chem[:70])} | {len(rs)} | {pages} |")
        L.append("")

    if excluded_fp:
        fn_fp, chem_fp, rs_fp = excluded_fp
        L.append(f"**Excluded as a false positive**: `{fn_fp}`, "
                 f"`{esc(chem_fp)}` (1 row, p"
                 f"{rs_fp[0]['source_page']}) — passes the blank-dose test "
                 f"on a technicality but is a wrapped CONTINUATION fragment "
                 f"of the Aluminum-Phosphide fumigation table (the same "
                 f"7-field schema whose other rows are already quarantined "
                 f"`cols_unresolved` on p27 — Step 1b/Step 2), not a genuine "
                 f"free-text-method chemical block. Its own 2 segments "
                 f"(`{esc(rs_fp[0]['pest_or_disease'][:40])}` and "
                 f"`{esc(rs_fp[0]['waiting_period_phi'][:40])}`) simply "
                 f"don't happen to include a dose figure — checked by hand, "
                 f"not assumed.\n")

    L.append("### 4.1 Metarhizium anisopliae 10% GR (bio_insecticides p9) "
             "— related but DIFFERENT defect\n")
    L.append("Not counted above: this block fails the \"every row blank\" "
             "test because one row (Potato/White grub) has `dose_ai=\"60kg.\"` "
             "populated. Inspecting all 3 non-header rows under this "
             "chemical shows why — it is not cleanly free-text-shaped, it "
             "has its OWN two-tier column-label header (\"Crop | Common "
             "name of the target organism | Dosage/ha/application | "
             "Formulation | Method of application\") that was extracted as "
             "if it were data, because `chemical_header` detection only "
             "fires on a row with exactly ONE non-blank segment — this "
             "header has three:\n")
    L.append("```text")
    L.append("crop='Crop' | pest='Common name of the target organism' | dose_form='Dosage /ha/application'")
    L.append("crop='Crop' | dose_ai='Formulation' | dilution='Method of application'")
    L.append("crop='Potato' | pest='White grub' | dose_ai='60kg.' | dilution='Mix Metarhizium anisopliae (Grub-X 10% GR) with FYM...'")
    L.append("```")
    L.append("2 of its 3 rows are literal column-label text sitting in the "
             "`crop`/`pest_or_disease`/`dose_formulation`/`dilution_water` "
             "fields as if they were farm data (`crop='Crop'` is not a "
             "crop). The 3rd row is genuine data, itself carrying the same "
             "prose-in-`dilution_water` shape as Q3/Q4's other cases. This "
             "is a second, distinct failure mode from the clean free-text "
             "blocks above: a two-tier header this corpus's "
             "`chemical_header` check does not recognise, not a table that "
             "was always unstructured.\n")

    L.append(f"**Combined total (clean free-text blocks + Metarhizium): "
             f"{total_rows} + 3 = {total_rows + 3} rows.**\n")

    L.append("### 4.2 insecticides / fungicides — checked directly, not "
             "assumed\n")
    L.append("Zero genuine free-text-shape blocks in either file, by the "
             "structural test above. A phrase search for \"method of "
             "application\" / \"target organism\" anywhere in the extracted "
             "text (not just blank-dose blocks) finds:\n")
    L.append("| file | rows | context |")
    L.append("|---|---|---|")
    L.append("| `insecticides_20260331.pdf` | 0 | — |")
    L.append("| `fungicides_20260331.pdf` | 1 | p71, Rice/\"Brown leaf spot, "
             "Sheath blight\", `Penflufen 13.28% + Trifloxystrobin 13.28% "
             "FS` — **`assignment_kind=ordinal_6`**, a normal, correctly-"
             "resolved 6-column row whose `dilution_water` cell happens to "
             "BE a seed-treatment method paragraph that starts with the "
             "words \"Method of application\". Not a different table "
             "template — the same Q3 phenomenon (prose in a dose/dilution "
             "cell), landed via the normal path because this row genuinely "
             "has 6 real segments. |")
    L.append("| `bio_insecticides_20260331.pdf` | 2 | the Metarhizium "
             "header-echo rows above |")
    L.append("")
    L.append("**Answer: the free-text-method-shape TABLE TEMPLATE (a "
             "distinct header wording, not just prose-in-a-cell) is "
             "confirmed only in the two bio files.** insecticides and "
             "fungicides both carry the Q3 prose-in-cell phenomenon on "
             "ordinary 6-column rows, but neither has a block whose header "
             "itself uses this alternate shape.\n")
    return L


# --------------------------------------------------------------------------- #
# Q5
# --------------------------------------------------------------------------- #

PER_LITRE_RE = re.compile(r"per\s*lit|/\s*lit|ml\s*/\s*l\b|ml/l|gram\s+in\s+\d", re.I)

TUR_RE = re.compile(r"\btur\b|\barhar\b|red\s*gram|pigeon\s*pea|pigeonpea", re.I)
GRAM_RE = re.compile(r"bengal\s*gram|chickpea|\bgram\b", re.I)
EXCLUDE_GRAM_RE = re.compile(r"black\s*gram|blackgram|green\s*gram|greengram", re.I)

SCOPE_MATCHERS = {
    "cotton": re.compile(r"\bcotton\b", re.I),
    "soybean": re.compile(r"soy\s*a?\s*bean", re.I),
    "tur": TUR_RE,
    "gram": GRAM_RE,
    "onion": re.compile(r"\bonion\b", re.I),
    "tomato": re.compile(r"\btomato\b", re.I),
    "grape": re.compile(r"\bgrapes?\b", re.I),
    "pomegranate": re.compile(r"\bpomegranate\b", re.I),
}


def crop_scope_hits(crop_text: str) -> set[str]:
    hits = set()
    for name, pat in SCOPE_MATCHERS.items():
        if name == "gram" and EXCLUDE_GRAM_RE.search(crop_text):
            continue
        if pat.search(crop_text):
            hits.add(name)
    return hits


def q5(all_rows: dict[str, list[dict]]) -> list[str]:
    L = ["## 5. Percent-concentration / per-litre dose cells (separate issue)\n"]
    L.append("Counting only — no parsing, no classification, per "
             "instruction. A row counts if `dose_ai`, `dose_formulation` "
             "or `dilution_water` contains a literal `%`, or matches a "
             "per-litre pattern (`per lit`, `/lit`, `ml/l`, or "
             "`<number> gram in <number> lit`, covering the exact Kitazin "
             "wording).\n")
    L.append("Crop-scope matching caveat: `scope.py`'s `\"gram\"` and "
             "`\"tur\"` overlap heavily in CIB&RC's own crop names — "
             "\"Red Gram\" / \"Pigeon pea\" / \"Arhar\" all mean tur; "
             "\"Bengal Gram\" means gram (chickpea); but \"Black Gram\" and "
             "\"Green Gram\" are DIFFERENT crops (urad, moong) that a bare "
             "substring match on \"gram\" would wrongly pull in. Excluded "
             "explicitly here. This is the same crop-string reconciliation "
             "`scope.py`'s own header comment already flags as unresolved "
             "against the CIB&RC register — surfaced again here because it "
             "directly affects this count, not fixed.\n")

    total = 0
    by_file = Counter()
    by_file_scope = Counter()
    for fn in FILES:
        for r in all_rows[fn]:
            vals = [r[c] for c in DOSE_COLS]
            hit = any(("%" in v) or PER_LITRE_RE.search(v) for v in vals)
            if hit:
                total += 1
                by_file[fn] += 1
                if crop_scope_hits(r["crop"]):
                    by_file_scope[fn] += 1

    L.append("| file | rows with %/per-litre dose cell | of those, crop in scope.py's 8 |")
    L.append("|---|---|---|")
    grand_scope = 0
    for fn in FILES:
        L.append(f"| `{fn}` | {by_file[fn]} | {by_file_scope[fn]} |")
        grand_scope += by_file_scope[fn]
    L.append(f"| **total** | **{total}** | **{grand_scope}** |\n")

    L.append("### 5.1 The reported case, verified\n")
    kit = [r for fn in FILES for r in all_rows[fn]
          if r["active_ingredient"] == "Kitazin 48% EC" and r["crop"] == "Pomegranate"]
    if kit:
        r = kit[0]
        L.append(f"`fungicides_20260331.pdf` p{r['source_page']}, "
                 f"Pomegranate / {r['pest_or_disease']}, Kitazin 48% EC:\n")
        L.append("```text")
        L.append(f"dose_ai:           {r['dose_ai']}")
        L.append(f"dose_formulation:  {r['dose_formulation']}")
        L.append(f"assignment_kind:   {r['assignment_kind']}")
        L.append("```")
        L.append("**This row's column assignment is CORRECT** — "
                 "`ordinal_6`, a clean 6-segment row, dose_ai and "
                 "dose_formulation are exactly where the schema says they "
                 "should be. The defect here is different in kind from Q1-4: "
                 "it is not a column-placement error, it is that the CONTENT "
                 "of a correctly-placed cell mixes two incompatible units "
                 "(a `%` concentration and a per-litre dilution instruction) "
                 "under a header that claims a per-hectare a.i. figure. This "
                 "is a Phase 4 dose-parsing problem, not a Phase 3 "
                 "extraction defect — flagged here because it is live "
                 "in-scope data (Pomegranate/Anthracnose is one of your 40 "
                 "targets), not because Step 2 placed it wrong.\n")
    return L


def main() -> None:
    all_rows = {fn: load_raw(fn) for fn in FILES}

    L: list[str] = []
    L.append("# Phase 3 — Fallback and Unit Diagnosis\n")
    L.append("**Diagnosis only.** No raw CSVs modified, no re-extraction run, "
             "`schema.py` untouched. All numbers below are read from the "
             "existing `data/interim/*_raw.csv` (Step 2's output) and from "
             "`tools/phase3_step1b_rowgrid.py` / `tools/phase3_step2_extract.py`'s "
             "actual code — nothing here required regenerating anything.\n")
    L.append("Manual verification of the 25-row sample is confirmed 25/25 "
             "correct on attribution, including both cross-page inheritance "
             "cases. This report is about the one remaining defect class "
             "the sample surfaced (fallback_subset column placement) plus "
             "one separately-reported unit issue (Kitazin).\n")

    L += q1(all_rows)
    L += q2()
    L += q2_grounding()
    L += q3(all_rows)
    L += q4(all_rows)
    L += q5(all_rows)

    L.append("## Summary, for the remedy decision\n")
    L.append("- **Q1-3 (column misplacement)**: `fallback_subset` rows are "
             "assigned by pure x-coordinate distance to the file/subsection's "
             "calibrated band centers — no check on segment content. This is "
             "correct for its designed purpose (Step 1b: recovering a "
             "genuinely-missing field's position among fewer-than-6 real "
             "segments) but has no way to notice a segment is prose rather "
             "than a number. 122-133 rows (heuristic-dependent) carry a "
             "sentence-length value in a dose/dilution column as a result.")
    L.append("- **Q4 (table template)**: 11 chemical blocks / 47 rows are "
             "genuinely free-text-shaped (no numeric dose_ai/dose_formulation "
             "exists to misplace — the source table itself only has "
             "crop/pest/method columns), all in the two bio files. "
             "Metarhizium anisopliae 10% GR adds a distinct, second failure "
             "mode: a two-tier header not recognised as a header at all.")
    L.append("- **Q5 (unit ambiguity)**: a separate class entirely — correct "
             "column placement, ambiguous content. 276 rows corpuswide, 72 "
             "of them on one of your 8 scope crops. Not a Step 2 defect.\n")

    out = "\n".join(L) + "\n"
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "phase3_fallback_diagnosis.md").write_text(out, encoding="utf-8")
    print(f"wrote {REPORTS / 'phase3_fallback_diagnosis.md'} ({len(out)} bytes)")


if __name__ == "__main__":
    main()
