"""PHASE 3, STEP 2e — targeted fix for the quarantine-parent merge (p27 r17).

Corrects the ONE defect found in `reports/phase3_row7_check.md`: Step 2c's
`quarantine_parent` merge path appended the p28 r0 fragment's raw_row_text
flatly onto the end of insecticides p27 r17's raw_row_text, which is wrong
because TWO of that row's cells wrap across the page break (pest field and
aeration field), not one. The flat append put pest-list text inside the
aeration sentence and created a spurious 8th field on a 7-field table.

This is specific to this single row — the only quarantine_parent case in the
Step 2c 49-row merge set. It is not a new general rule and touches nothing
else: no other quarantine row, no raw CSV row, no `src/schema.py`.

Ground truth: `insecticides p27 r16` is the same 7-field fumigation table,
same two fields, sitting entirely on p27 with nothing wrapped. Its field[1]
and field[6] show exactly what row 17's fields should read once corrected.

Refuses to run if the row is not in the exact pre-fix state this script
expects (idempotent / safe to re-run: a second run is a no-op, not a
double-fix).
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
REPORTS = ROOT / "reports"

QUAR_CSV = INTERIM / "quarantine.csv"
MANIFEST = INTERIM / "phase3_step2c_manifest.json"

TARGET = ("insecticides_20260331.pdf", "27", "17")

# The exact pre-fix (flat-appended) text, as produced by Step 2c — the
# precondition this script requires before it will touch anything.
BROKEN_TEXT = (
    "Go down  fumigation || Rice weevil,  Lesser grain  Borer, Khapra || "
    "Airtight  cover || 150 gm/m3 || 07days || 10 ppm || "
    "Partial aeration  For  at least 1  hr. followed by Beetle, Rust  red "
    "flour  beetle, Pulse  beetle, Dried  fruit Beetle || "
    "24 hr. complete  Aeration  waiting period  of 24 hr."
)

FRAG_SEG_1 = "Beetle, Rust  red flour  beetle, Pulse  beetle, Dried  fruit Beetle"
FRAG_SEG_2 = "24 hr. complete  Aeration  waiting period  of 24 hr."

# Row 16's field[1] / field[6], for the post-fix structural comparison.
R16_FIELD1 = ("Rice weevil,  Lesser grain  Borer,  Khapra  Beetle, Rust  red "
             "flour  beetle, Pulse  beetle, Dried  fruit Beetle")
R16_FIELD6 = ("Partial  aeration For  at least 1hr.  followed  by24 hr.  "
             "complete  Aeration  waiting  period of 24  hr.")


def load_csv(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(encoding="utf-8", newline="") as fh:
        rdr = csv.DictReader(fh)
        return list(rdr.fieldnames or []), list(rdr)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


def norm(s: str) -> str:
    """Strip ALL whitespace, for content comparison across two independent
    PDF text-run extractions (r16 whole-page, r17 split across a page break).
    Word-wrap tokenization differs between them (e.g. r16 has "by24", r17's
    reconstruction has "by 24") even when the underlying text is identical —
    collapsing runs is not enough, this strips every space so only the actual
    characters are compared."""
    return "".join(s.split())


def main() -> None:
    fields, rows = load_csv(QUAR_CSV)
    target_file, target_page, target_row = TARGET
    row = next(r for r in rows
               if r["source_file"] == target_file
               and r["source_page"] == target_page
               and r["source_row_index"] == target_row)

    if row["raw_row_text"] == BROKEN_TEXT:
        pass  # expected pre-fix state
    else:
        expected_fields = [
            "Go down  fumigation",
            "Rice weevil,  Lesser grain  Borer, Khapra Beetle, Rust  red "
            "flour  beetle, Pulse  beetle, Dried  fruit Beetle",
            "Airtight  cover", "150 gm/m3", "07days", "10 ppm",
            "Partial aeration  For  at least 1  hr. followed by "
            "24 hr. complete  Aeration  waiting period  of 24 hr.",
        ]
        if row["raw_row_text"] == " || ".join(expected_fields):
            print("already fixed — no-op")
            return
        raise AssertionError(
            f"p27 r17 is not in the expected pre-fix state:\n{row['raw_row_text']!r}")

    fields_before = BROKEN_TEXT.split(" || ")
    assert len(fields_before) == 8, len(fields_before)  # the corrupted count

    # Reconstruct: the true 7 parent fields (drop the flat-appended tail),
    # then route each fragment segment to its real field by index, matching
    # row 16's structure — not by re-guessing, by undoing the known append.
    true_parent_fields = [
        "Go down  fumigation",
        "Rice weevil,  Lesser grain  Borer, Khapra",
        "Airtight  cover",
        "150 gm/m3",
        "07days",
        "10 ppm",
        "Partial aeration  For  at least 1  hr. followed by",
    ]
    assert " || ".join(true_parent_fields) in BROKEN_TEXT

    fixed_fields = list(true_parent_fields)
    fixed_fields[1] = fixed_fields[1] + " " + FRAG_SEG_1   # pest field
    fixed_fields[6] = fixed_fields[6] + " " + FRAG_SEG_2   # aeration field
    fixed_text = " || ".join(fixed_fields)

    assert len(fixed_fields) == 7, len(fixed_fields)
    assert len(fixed_text.split(" || ")) == 7

    # Structural match to row 16 (whitespace-normalised — r16 and r17 differ
    # in incidental spacing/hyphenation from their own OCR-free extraction,
    # not in content).
    assert norm(fixed_fields[1]) == norm(R16_FIELD1), (
        f"field[1] does not match r16:\n{fixed_fields[1]!r}\n{R16_FIELD1!r}")
    assert norm(fixed_fields[6]) == norm(R16_FIELD6), (
        f"field[6] does not match r16:\n{fixed_fields[6]!r}\n{R16_FIELD6!r}")

    row["raw_row_text"] = fixed_text
    write_csv(QUAR_CSV, fields, rows)

    # Keep the manifest's record of this merge accurate.
    if MANIFEST.exists():
        m = json.loads(MANIFEST.read_text(encoding="utf-8"))
        entry = next(e for e in m["merged"]
                     if e["file"] == "insecticides" and e["page"] == 28)
        entry["parent"]["raw_after"] = fixed_text
        entry["parent"]["fix_applied"] = "phase3_step2e: routed by field index (1, 6), not flat append"
        MANIFEST.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")

    print("p27 r17 fixed.")
    print(f"  segments: {len(fixed_fields)} (was 8)")
    print(f"  field[1] matches r16: {norm(fixed_fields[1]) == norm(R16_FIELD1)}")
    print(f"  field[6] matches r16: {norm(fixed_fields[6]) == norm(R16_FIELD6)}")
    print(f"  raw_row_text: {fixed_text}")

    # -------------------- re-verify the hard identity ---------------------- #
    RAW_FILES = {
        "insecticides": "insecticides_20260331_raw.csv",
        "fungicides": "fungicides_20260331_raw.csv",
        "bio_insecticides": "bio_insecticides_20260331_raw.csv",
        "bio_fungicides": "bio_fungicides_20260331_raw.csv",
    }
    EXPECTED_RAW_AFTER = {"insecticides": 2020, "fungicides": 1260,
                          "bio_insecticides": 291, "bio_fungicides": 132}
    SOURCE_TOTAL = 3766
    MERGED_COUNT = 49

    raw_counts = {k: len(load_csv(INTERIM / fn)[1]) for k, fn in RAW_FILES.items()}
    assert raw_counts == EXPECTED_RAW_AFTER, raw_counts
    _, quar_rows_now = load_csv(QUAR_CSV)
    assert len(quar_rows_now) == 14, len(quar_rows_now)

    identity_ok = (SOURCE_TOTAL == sum(raw_counts.values())
                   + len(quar_rows_now) + MERGED_COUNT)
    assert identity_ok
    print(f"\nidentity re-verified: {SOURCE_TOTAL} source == "
          f"{sum(raw_counts.values())} raw + {len(quar_rows_now)} quarantine "
          f"+ {MERGED_COUNT} merged  (row counts unchanged by this fix — "
          f"only p27 r17's text was restructured)")


if __name__ == "__main__":
    sys.exit(main())
