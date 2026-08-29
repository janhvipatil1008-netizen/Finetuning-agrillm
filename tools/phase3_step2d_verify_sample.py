"""PHASE 3, STEP 2d — regenerate verify_sample.csv from the POST-MERGE CSVs.

Writes data/interim/verify_sample.csv (gitignored) — 17 rows, weighted for
hand-checking the Step 2c merge against the source PDFs, not a uniform
random sample. Composition:

* 7 MERGE TARGETS — parent rows that received an appended fragment, at
  least one per column type. Fixed identities, not sampled, so the sample
  hits every merge path:
    merge_target_pest        insecticides p13 r15  (Red gram / + Pod fly)
    merge_target_pest        fungicides   p74 r13  (Blumeria grami + nis)
    merge_target_method      fungicides   p32 r2   (streptocycline prose tail)
    merge_target_dilution    fungicides   p15 r11  (+ equipment used)
    merge_target_dose_form   fungicides   p33 r2   (+ rows on either side.)
    merge_target_crop_wrap   insecticides p31 r22  (+ and coconut))
    merge_target_quarantine  insecticides p27 r17  (fumigation row, from
                             quarantine.csv — semantic columns blank there
                             by design; check raw_row_text)
* 5 CONTROLS — rows untouched by any merge, deterministic sample
  (seed 20260829): ordinal_6 crop-advisory rows with all four dose columns
  populated, drawn from pages no merge touched (neither a fragment's nor a
  parent's page). 2 insecticides, 1 per other file.
* 5 SWEEP ROWS — the post-merge dose-empty CSV-first rows, included for the
  second-order-phantom check. Inspected 2026-08-29 before this script was
  written; verdicts (all genuine, no second-order phantom):
    fungicides p31 r1        GENUINE — own crop (Cotton), own disease, fresh
                             "Seed treatment:" prose; one of the three
                             bacterial-protocol rows step 1b documented as
                             PRESENT-AND-EMPTY dilution/PHI.
    bio_insecticides p10 r0  GENUINE — the own-crop row protected in Step 2c;
                             same template as its Tomato (p9) and Carrot
                             (p10 r1) siblings.
    bio_insecticides p11 r1  GENUINE — own crop (Papaya), own nematode pest,
                             fresh method prose; its predecessor (the p10 r13
                             Acid lime merge parent) is complete post-merge,
                             nothing dangling for this row to continue.
    bio_insecticides p12 r1  GENUINE — own crop (Brinjal), same seed-treatment
                             template as Tomato/Carrot siblings.
    bio_fungicides p9 r1     GENUINE-BLANK — assignment_kind `blank`: an empty
                             ruled row, raw_row_text empty. Nothing wrapped;
                             carries no pest and no dose, so no claim exists.
                             (crop/ai columns show forward-filled carry only.)
  A wrap can only ever be the PHYSICAL first row of a page; these are all
  mid-page rows that became CSV-first when the r0 phantom above them was
  merged away (p10 r0 excepted — it is a physical first row, and genuine).

Re-run after any extract+merge cycle to refresh the sample. Reads only;
never modifies the raw CSVs or quarantine.csv.
"""

from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"

FILES = {
    "insecticides": "insecticides_20260331_raw.csv",
    "fungicides": "fungicides_20260331_raw.csv",
    "bio_insecticides": "bio_insecticides_20260331_raw.csv",
    "bio_fungicides": "bio_fungicides_20260331_raw.csv",
}
DOSE_COLS = ["dose_ai", "dose_formulation", "dilution_water", "waiting_period_phi"]

OUT_COLS = ["sample_category", "source_file", "source_page", "source_row_index",
            "section", "subsection", "assignment_kind", "active_ingredient",
            "crop", "pest_or_disease", "dose_ai", "dose_formulation",
            "dilution_water", "waiting_period_phi", "method", "raw_row_text"]

MERGE_TARGETS = [  # (category, file_key, page, row_index)
    ("merge_target_pest", "insecticides", "13", "15"),
    ("merge_target_pest", "fungicides", "74", "13"),
    ("merge_target_method", "fungicides", "32", "2"),
    ("merge_target_dilution", "fungicides", "15", "11"),
    ("merge_target_dose_form", "fungicides", "33", "2"),
    ("merge_target_crop_wrap", "insecticides", "31", "22"),
]
QUAR_TARGET = ("merge_target_quarantine", "insecticides", "27", "17")

SWEEP_ROWS = [
    ("sweep_r1", "fungicides", "31", "1"),
    ("sweep_r1", "bio_insecticides", "10", "0"),
    ("sweep_r1", "bio_insecticides", "11", "1"),
    ("sweep_r1", "bio_insecticides", "12", "1"),
    ("sweep_r1", "bio_fungicides", "9", "1"),
]

CONTROLS_PER_FILE = {"insecticides": 2, "fungicides": 1,
                     "bio_insecticides": 1, "bio_fungicides": 1}


def load(name: str) -> list[dict]:
    with (INTERIM / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def pick(rows: list[dict], page: str, r_idx: str) -> dict:
    return next(r for r in rows
                if r["source_page"] == page and r["source_row_index"] == r_idx)


def main() -> None:
    data = {k: load(fn) for k, fn in FILES.items()}
    manifest = json.loads(
        (INTERIM / "phase3_step2c_manifest.json").read_text(encoding="utf-8"))

    # pages a merge touched, per file: fragment page and parent page
    touched: dict[str, set[int]] = {k: set() for k in FILES}
    for m in manifest["merged"]:
        touched[m["file"]].add(int(m["page"]))
        touched[m["file"]].add(int(m["page"]) - 1)

    out: list[dict] = []

    def emit(category: str, key: str, row: dict) -> None:
        rec = {c: row.get(c, "") for c in OUT_COLS}
        rec["sample_category"] = category
        rec["source_file"] = row.get("source_file", key)
        out.append(rec)

    # 1. merge targets — assert each really was a parent in the manifest
    parent_ids = {(m["file"], m["parent"].get("page"), m["parent"].get("row_index"))
                  for m in manifest["merged"] if not m["parent"].get("quarantine")}
    for cat, key, page, r_idx in MERGE_TARGETS:
        assert (key, page, r_idx) in parent_ids, (key, page, r_idx)
        emit(cat, key, pick(data[key], page, r_idx))
    cat, key, page, r_idx = QUAR_TARGET
    emit(cat, key, pick(load("quarantine.csv"), page, r_idx))

    # 2. controls — deterministic, from untouched pages, complete dose rows
    rng = random.Random(20260829)
    for key, n in CONTROLS_PER_FILE.items():
        pool = [r for r in data[key]
                if int(r["source_page"]) not in touched[key]
                and r["section"] == "crop-advisory"
                and r["assignment_kind"] == "ordinal_6"
                and all(r[c] for c in DOSE_COLS)]
        for r in rng.sample(pool, n):
            emit("control", key, r)

    # 3. the post-merge sweep rows
    for cat, key, page, r_idx in SWEEP_ROWS:
        emit(cat, key, pick(data[key], page, r_idx))

    assert len(out) == 17, len(out)
    target = INTERIM / "verify_sample.csv"
    with target.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_COLS)
        w.writeheader()
        w.writerows(out)
    print(f"wrote {target.relative_to(ROOT)}: {len(out)} rows "
          f"(7 merge targets, 5 controls, 5 sweep)")
    for r in out:
        print(f"  {r['sample_category']:24s} {r['source_file']:.20s} "
              f"p{r['source_page']:>3} r{r['source_row_index']}")


if __name__ == "__main__":
    sys.exit(main())
