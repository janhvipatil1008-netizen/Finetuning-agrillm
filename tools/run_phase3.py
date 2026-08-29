"""PHASE 3 — pipeline entry point.

The single official command to reproduce `data/interim/` from `data/raw/`:

    python tools/run_phase3.py

Runs, in order, each as a separate subprocess so one script's globals can
never leak into another's:

    1. phase3_step2_extract.py    PDFs -> raw CSVs + quarantine.csv
    2. phase3_step2c_merge.py     merge the 49 phantom continuation rows
    3. phase3_step2e_fix_row7.py  fix the one quarantine-parent field merge

Every step's precondition is checked BEFORE it runs, not discovered via a
stack trace after it fails partway through. A missing precondition aborts
immediately with a message naming exactly what is missing and, where
relevant, which earlier step or document produces it — no step past the
first failure runs. This is deliberately mechanical (path/row-count checks
only) rather than re-deriving each script's own internal assumptions: the
scripts already assert their own internal invariants (Step 2c's frozen
49-row merge set, Step 2e's exact pre-fix text match) and abort loudly on
their own if those don't hold. The driver's job is only to catch the coarser
failure of running a step whose inputs don't exist yet.

Step 1 has no caching — it always re-extracts from the PDFs from scratch, so
a full `run_phase3.py` invocation always does the full extract+merge+fix work
every time; it does NOT skip Steps 2/3 on a second run, because Step 1 never
hands them an already-merged raw CSV set to detect. What IS guaranteed is
determinism and re-run safety: two full runs produce byte-identical output
(verified — same row counts, same hard-assertion totals, same p27 r17 text,
both times), and nothing is double-applied or corrupted by running twice.
(Step 2c's and Step 2e's own no-op detection only matters if you invoke them
directly, standalone, without a fresh Step 1 first — see their own
docstrings.)

Not wrapped here: `phase3_step2b_phantom.py` / `phase3_step2b_report.py`
(the diagnosis that produced the frozen 49-row merge set — a one-time
analysis, not part of reproducing `data/interim/` from a frozen set of
rules) and `phase3_step2d_verify_sample.py` (regenerates the hand-check
sample; not part of the data itself). Run those separately if needed.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
RAW_CIBRC = ROOT / "data" / "raw" / "cibrc"
INTERIM = ROOT / "data" / "interim"

IN_SCOPE_PDFS = [
    "insecticides_20260331.pdf",
    "fungicides_20260331.pdf",
    "bio_insecticides_20260331.pdf",
    "bio_fungicides_20260331.pdf",
]
RAW_CSVS = [
    "insecticides_20260331_raw.csv",
    "fungicides_20260331_raw.csv",
    "bio_insecticides_20260331_raw.csv",
    "bio_fungicides_20260331_raw.csv",
]


def fail(message: str) -> None:
    print(f"\nABORT: {message}", file=sys.stderr, flush=True)
    sys.exit(1)


def check_extract_precondition() -> None:
    missing = [p for p in IN_SCOPE_PDFS if not (RAW_CIBRC / p).exists()]
    if missing:
        fail(
            "Step 1 (extract) precondition failed — missing source PDF(s) in "
            f"{RAW_CIBRC.relative_to(ROOT)}:\n"
            + "\n".join(f"  - {m}" for m in missing)
            + "\n\nThese are not committed to git (see .gitignore). Download "
              "them per SOURCES.md sec. 1 (\"CIB&RC — Major Uses of "
              "Pesticides\") before running phase 3."
        )


def check_merge_precondition() -> None:
    missing = [c for c in RAW_CSVS + ["quarantine.csv"]
               if not (INTERIM / c).exists()]
    if missing:
        fail(
            "Step 2 (merge) precondition failed — missing extractor output "
            f"in {INTERIM.relative_to(ROOT)}:\n"
            + "\n".join(f"  - {m}" for m in missing)
            + "\n\nStep 1 (phase3_step2_extract.py) must run first and "
              "complete successfully."
        )
    for c in RAW_CSVS:
        with (INTERIM / c).open(encoding="utf-8", newline="") as fh:
            n = sum(1 for _ in csv.DictReader(fh))
        if n == 0:
            fail(
                f"Step 2 (merge) precondition failed — {c} exists but has 0 "
                "data rows. Step 1 did not complete; re-run "
                "phase3_step2_extract.py."
            )


def check_fix_row7_precondition() -> None:
    manifest = INTERIM / "phase3_step2c_manifest.json"
    if not manifest.exists():
        fail(
            "Step 3 (fix row7) precondition failed — "
            f"{manifest.relative_to(ROOT)} is missing.\n\n"
            "Step 2 (phase3_step2c_merge.py) must run first and complete "
            "successfully; it writes this manifest as its record of every "
            "merge performed, including the quarantine-parent case Step 3 "
            "corrects."
        )
    try:
        m = json.loads(manifest.read_text(encoding="utf-8"))
        next(e for e in m["merged"]
             if e["file"] == "insecticides" and e["page"] == 28)
    except (json.JSONDecodeError, KeyError, StopIteration):
        fail(
            f"Step 3 (fix row7) precondition failed — {manifest.relative_to(ROOT)} "
            "exists but does not contain the expected insecticides p28 "
            "quarantine-parent merge entry. It may be stale or corrupt; "
            "re-run phase3_step2c_merge.py."
        )
    if not (INTERIM / "quarantine.csv").exists():
        fail("Step 3 (fix row7) precondition failed — "
             f"{(INTERIM / 'quarantine.csv').relative_to(ROOT)} is missing.")


STEPS = [
    ("Step 1 — extract", "phase3_step2_extract.py", check_extract_precondition),
    ("Step 2 — merge phantom rows", "phase3_step2c_merge.py", check_merge_precondition),
    ("Step 3 — fix quarantine row7", "phase3_step2e_fix_row7.py", check_fix_row7_precondition),
]


def run_step(label: str, script: str) -> None:
    # subprocess inherits the raw stdout file descriptor, so when stdout is
    # redirected to a file (not a tty) this print must be flushed explicitly
    # — otherwise Python's block-buffering reorders it after the child's
    # output instead of before, which is exactly backwards for a progress
    # banner. Confirmed by a full end-to-end run redirected to a log file.
    print(f"\n{'=' * 70}\n{label}  ({script})\n{'=' * 70}", flush=True)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, str(TOOLS / script)],
        cwd=ROOT,
        env=env,
    )
    if result.returncode != 0:
        fail(f"{label} failed (exit code {result.returncode}). "
             f"See output above. No further steps were run.")


def main() -> None:
    for label, script, precondition in STEPS:
        precondition()
        run_step(label, script)
    print(f"\n{'=' * 70}\nphase 3 pipeline complete: data/interim/ reproduced from data/raw/\n"
          f"{'=' * 70}")


if __name__ == "__main__":
    sys.exit(main())
