"""PHASE 3, STEP 2 — extract. Raw CSVs only.

No normalisation, no dose parsing, no label_db. This script writes:
  data/interim/<name>_raw.csv       one per in-scope file, checkpointed
                                     immediately after that file finishes
  data/interim/quarantine.csv       row-level quarantine, all four files
  data/interim/verify_sample.csv    25 random rows for manual spot-check

All three are gitignored (data/interim/) — only this script and the report
are committed. Re-running regenerates the CSVs from the source PDFs.

Method, carried forward from Step 1b (verified there, not re-derived here)
----------------------------------------------------------------------------
* Row-local segmentation: merge camelot's raw grid cells using each cell's
  own `Cell.right` border flag (a real detected ruled line). The static
  (file, subsection) calibrated grid from Step 1 is consulted only as a
  fallback, to decide which of the 6 bands a segment belongs to when a row
  has fewer than 6 real segments (see `best_subset_assignment`) — never as
  the primary assignment method.
* No `source_column_merged` code. Step 1b proved that phenomenon does not
  occur anywhere in this corpus (Step 1's report of it on insecticides p89
  was itself an artifact of the static-grid method being replaced here).
* `len(content) > 6` (only the 3 Aluminum-Phosphide fumigation rows on
  insecticides p27) -> quarantine, `cols_unresolved`. This is the same
  `residual_over6` classification Step 1b already validated; it is not a new
  detector.

New in this script (Step 2 only)
---------------------------------
* **Chemical-header rows**: a row with exactly ONE real content segment,
  and it is `segs[0]` (position 0) — e.g. "Abamectin 01.90 % EC" spanning
  the full table width. These update `active_ingredient` for every row
  that follows, until the next one. They are NOT data rows: crop, pest and
  all four dose/PHI fields are left blank, and they are still written to
  the raw CSV (raw stays raw — nothing that came off a page is dropped).
* **Forward-fill**: `crop` and `active_ingredient` carry independently
  across pages, in page order, over the WHOLE (file, section, subsection)
  run — never reset merely because a camelot `Table` object ends (that
  would break exactly the insecticides p10->p11 case phase 2b documented).
  Both reset to blank at a (section, subsection) boundary; `crop` also
  resets to blank at a chemical-header row (a new chemical's crop list
  starts fresh); `active_ingredient` is set ONLY by chemical-header rows.
  A quarantined row's crop/chemical values are never used to advance this
  state — we do not have confidence in what an unresolved row's fields mean.
* **Footnote resolution**: a per-file registry of `{marker: definition}`
  built by counting each line's LEADING run of `*` characters directly
  (not a `\\*{1,4}` regex — a regex backtracks whenever the text after a
  shorter marker also starts with `*`, and that happens twice in this
  corpus: bio_fungicides p20's bare `***` end-of-document marker would
  parse as marker=`**` + body=`*`, and fungicides p83's `** In case
  of...` line — note the space before the word — would parse as marker=`*`
  + body=`* In case of...`, both checked and confirmed wrong before this
  fix), scanning pages 2..N of the file (fungicides p83's four endnotes
  live there — see phase2b's pre-work finding that fungicides runs
  FILE-WIDE endnotes, not page-local footnotes — but page 1 is skipped
  outright: bio_insecticides' page-1 disclaimer begins with a bare `*` and
  runs straight into the contents list with no blank-line separator, and a
  version that scanned page 1 absorbed the whole block as one bogus `*`
  "definition" — which, being the only `*` entry in that file's registry,
  then incorrectly "resolved" all 20 of that file's FYM* markers against
  disclaimer text instead of leaving them `unresolved_marker=True`; caught
  by checking the FYM rows' actual output, not by inspecting the registry
  in isolation). Any resolved cell value containing an asterisk-run marker
  is checked against the registry: found -> `footnote_text` is populated (a
  `; `-joined list, if the row carries more than one distinct marker);
  not found -> `unresolved_marker=True`, cell text kept verbatim, row KEPT
  (not quarantined) — this is the explicit, confirmed disposition for the
  32 bio_insecticides/bio_fungicides "FYM*" rows (FYM = Farm Yard Manure, a
  standard term, not a typo — the marker's target was never resolved and is
  not resolved here either; we only record that it exists).
* **`phi_cell_present`** (bool): per (table, subsection), applied to every
  one of its rows. CONTENT FIRST: if any row's own row-local PHI segment
  actually resolved to non-blank text, the column obviously exists — True,
  no geometry needed. Only when EVERY row's PHI is blank does it fall back
  to the geometric test from Step 1b (a raw column edge within 25pt of the
  calibrated PHI-band start, on a table whose bbox reaches that far).
  Geometry-first was tried and produced a real false negative: insecticides
  p2 — one of the file's own CALIBRATION source pages, with completely
  ordinary populated PHI values on every row — has its own dilution/PHI
  cut 27.9pt from the calibrated median, just outside the 25pt tolerance,
  so a pure geometric test called it "absent" despite every row plainly
  contradicting that. Checking content first and treating geometry as a
  last resort (only meaningful when there is no content to check) removed
  every such false negative; re-run against the exact 6 tables Step 1b
  hand-verified as genuinely ABSENT/PRESENT-AND-EMPTY, this reproduces all
  6 verdicts exactly. `None` for non-crop-advisory rows, where no
  calibrated grid exists to test against.
* **Known hardcoded flags from the phase 2b character-conservation audit**
  (findings that ARE NOT recoverable from row-local geometry, because the
  defect is a character genuinely missing from the page, not a
  misassignment of characters that are present):
    - fungicides p38's Apple/Marssonina-leaf-blotch row: the wrapped
      dilution cell is missing its last line ("...and plant protection").
      Quarantined, `truncated_cell` — guessing the tail is explicitly
      out of scope; this row is for manual repair.

Non-crop-advisory rows (public-health / household / locust)
-------------------------------------------------------------
No calibrated grid was built or validated for these schemas in Step 1/1b —
their logical columns are genuinely different (no a.i./formulation split;
"Habitat", "Method of Application" instead of "Crop"/"Pest"). Forcing them
through the crop-advisory column names would not be raw extraction, it would
be a guess. They are still fully extracted — every row appears in the raw
CSV, tagged with its section/subsection — but as `raw_row_text` (the row's
real-rule segments joined in reading order, verbatim) with the six
crop-advisory semantic columns and `phi_cell_present` left blank. No row
from these sections is dropped or quarantined solely for being
non-crop-advisory.

Section tagging is ROW-level, not page-level, on the three known
boundary pages (insecticides p89, p94; bio_insecticides p15): each row's own
y-position (camelot `Cell.y1`/`y2`, pdfminer bottom-up) is compared against
that page's phase-2b `split_top` (converted to bottom-up) to pick the
section above or below the split, independently of the page's own
(single) section tag.
"""

from __future__ import annotations

import csv
import json
import random
import re
import sys
from pathlib import Path

import camelot
import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "cibrc"
INTERIM = ROOT / "data" / "interim"
REPORTS = ROOT / "reports"

sys.path.insert(0, str(ROOT / "tools"))
from phase3_step1b_rowgrid import row_segments, best_subset_assignment  # noqa: E402

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

# Boundary pages: page -> split_top (TOP-DOWN pt), from phase 2b's per_page
# section map. A row's y1 (bottom-up) ABOVE (height - split_top) is above
# the split; below it is below.
BOUNDARY_SPLITS = {
    ("insecticides_20260331.pdf", 89): {"above": ("crop-advisory", "combination-product"),
                                        "below": ("public-health", "public-health-use"),
                                        "split_top": 675.9},
    ("insecticides_20260331.pdf", 94): {"above": ("public-health", "public-health-use"),
                                        "below": ("household", "household-insecticides"),
                                        "split_top": 681.7},
    ("bio_insecticides_20260331.pdf", 15): {"above": ("crop-advisory", "bio-insecticides"),
                                            "below": ("public-health", "public-health-use"),
                                            "split_top": 332.8},
}

# Hardcoded, from the phase 2b character-conservation audit — these are
# character-LOSS defects, invisible to row-local geometry, not something a
# generic detector can find here.
TRUNCATED_CELL_ROWS = {
    ("fungicides_20260331.pdf", 38): [0],  # Apple / Marssonina Leaf blotch
}

MARKER_RE = re.compile(r"\*{1,4}")
FOOTER_RE = re.compile(r"^\(?\d{1,4}\)?$")
PURE_ASTERISK_RE = re.compile(r"^\*+$")


def parse_footnote_marker_line(s: str) -> tuple[str, str] | None:
    """Manual leading-asterisk count, NOT a regex with `\\*{1,4}` — a regex
    backtracks when the text after a shorter marker also starts with '*',
    which happens twice in this corpus and silently produces the wrong
    marker/definition pairing: bio_fungicides p20's bare '***' end marker
    would parse as marker='**' + body='*', and fungicides p83's '**
    In case of...' line (note the space) would parse as marker='*' +
    body='* In case of...' (the regex backtracks from 2 asterisks to 1
    because \\S can still match the second literal '*'). Counting the
    leading run of '*' characters directly has no such ambiguity."""
    i = 0
    while i < len(s) and s[i] == "*":
        i += 1
    if i == 0:
        return None
    rest = s[i:].strip()
    if not rest:
        return None  # bare asterisks only — a document-end marker, not a definition
    return s[:i], rest

RAW_CSV_FIELDS = [
    "source_file", "source_page", "source_table_index", "source_row_index",
    "section", "subsection", "assignment_kind",
    "crop", "pest_or_disease", "dose_ai", "dose_formulation",
    "dilution_water", "waiting_period_phi",
    "is_chemical_header", "phi_cell_present",
    "unresolved_marker", "footnote_text", "flag_truncated_cell",
    "raw_row_text",
]

QUARANTINE_CSV_FIELDS = [
    "source_file", "source_page", "source_table_index", "source_row_index",
    "reason_code", "section", "subsection", "raw_row_text",
]


def load_section_map() -> dict:
    audit = json.loads((INTERIM / "phase2b_audit.json").read_text(encoding="utf-8"))
    out = {}
    for rec in audit:
        fn = rec["file"]
        out[fn] = {row["page"]: (row["section"], row["subsection"])
                   for row in rec["sections"]["per_page"]}
    return out


def load_grid() -> dict:
    return json.loads((INTERIM / "phase3_step1_grid.json").read_text(encoding="utf-8"))


def build_footnote_registry(pdf_path: Path) -> dict[str, str]:
    """{marker: definition}, scanning pages 2..N — fungicides' footnotes are
    file-wide endnotes (phase2b pre-work), not page-local, so the whole file
    is in scope, EXCEPT page 1. Every one of the 4 files opens with the same
    disclaimer-plus-contents-list front matter, and on bio_insecticides that
    disclaimer itself starts with a bare '*' with no blank-line separator
    before the contents list that follows it — a first version of this
    function had no way to tell where the disclaimer sentence ended and the
    contents list began, so it absorbed the whole page-1 block as one
    'definition' and (being the corpus's only registered '*' entry) it began
    incorrectly resolving the 32 FYM* markers against disclaimer text
    instead of leaving them `unresolved_marker=True` as instructed. No table
    page ever needs a footnote defined on page 1, so it is skipped outright.
    """
    registry: dict[str, str] = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            if page_idx == 0:
                continue
            text = page.extract_text() or ""
            current = None
            for line in text.splitlines():
                s = line.strip()
                parsed = parse_footnote_marker_line(s)
                if parsed:
                    current, body = parsed
                    registry[current] = body
                    continue
                if (current and s and not FOOTER_RE.match(s)
                        and not PURE_ASTERISK_RE.match(s)):
                    registry[current] += " " + s
                else:
                    current = None
    return registry


def phi_band_start(grid_sub: dict) -> float:
    return grid_sub["boundaries"][4]


def phi_cell_present_geometric(t, grid_sub: dict, tol: float = 25.0) -> bool:
    """The geometric fallback ONLY — used solely when no row in the table
    has a non-blank PHI value at all (see `resolve_phi_presence`). On its
    own this test is too tight to use as the primary signal: the
    dilution/PHI cut's natural page-to-page variance can exceed a 25pt
    tolerance even on a page that WAS one of the tables calibration was
    derived from (insecticides p2's own cut sits 27.9pt from the calibrated
    median) — checked directly, not assumed, after this showed
    `phi_cell_present=False` on obviously-populated PHI columns."""
    phi_start = phi_band_start(grid_sub)
    bbox_x2 = float(t._bbox[2])
    if bbox_x2 < phi_start + 10:
        return False
    edges = {x for a, b in t.cols for x in (float(a), float(b))}
    return any(abs(e - phi_start) <= tol for e in edges)


def resolve_phi_presence(t, grid_subs: dict, section_map_fn: dict,
                         fn: str, page: int, height: float) -> dict[str, bool]:
    """Per SUBSECTION seen in this table: True if ANY row's own resolved
    PHI band is non-blank (content is definitive proof the cell exists —
    checked BEFORE any geometry, per the p2 false-negative above); else
    fall back to `phi_cell_present_geometric`."""
    any_phi_content: dict[str, bool] = {}
    seen_subs: set[str] = set()
    for row_cells in t.cells:
        section, subsection = row_section(
            fn, page, float(row_cells[0].y1), height,
            *section_map_fn.get(page, ("unclassified", "unclassified")))
        if section != "crop-advisory" or subsection not in grid_subs:
            continue
        seen_subs.add(subsection)
        segs = row_segments(row_cells)
        kind, resolved_or_content, _ = classify_row(segs)
        phi_text = ""
        if kind == "ordinal_6":
            phi_text = resolved_or_content[5]
        elif kind == "fallback_subset":
            assign = best_subset_assignment(resolved_or_content, grid_subs[subsection]["centers"])
            if assign is not None and 5 in assign:
                phi_text = resolved_or_content[assign.index(5)]["text"]
        if phi_text.strip():
            any_phi_content[subsection] = True

    result = {}
    for sub in seen_subs:
        result[sub] = any_phi_content.get(
            sub, phi_cell_present_geometric(t, grid_subs[sub]))
    return result


def row_section(fn: str, page: int, cell0_y1: float, height: float,
                page_section: str, page_subsection: str) -> tuple[str, str]:
    key = (fn, page)
    if key not in BOUNDARY_SPLITS:
        return page_section, page_subsection
    b = BOUNDARY_SPLITS[key]
    split_y_bottomup = height - b["split_top"]
    if cell0_y1 > split_y_bottomup:
        return b["above"]
    return b["below"]


def classify_row(segs: list[dict]) -> tuple[str, list[str], list[str] | None]:
    """Returns (kind, resolved_6_or_empty, content_texts_for_raw_row_text)."""
    content = [s for s in segs if s["text"]]
    if not content:
        return "blank", [""] * 6, []
    if len(content) == 1 and segs[0]["text"]:
        return "chemical_header", [""] * 6, [c["text"] for c in content]
    if len(content) == 6:
        return "ordinal_6", [s["text"] for s in content], [c["text"] for c in content]
    if len(content) < 6:
        return "fallback_subset", content, [c["text"] for c in content]
    return "residual_over6", [""] * 6, [c["text"] for c in content]


def find_markers(values: list[str]) -> set[str]:
    found = set()
    for v in values:
        for m in MARKER_RE.finditer(v):
            found.add(m.group(0))
    return found


def process_file(fn: str, section_map: dict, grid: dict,
                  footnotes: dict[str, str]) -> tuple[list[dict], list[dict], int]:
    """Returns (raw_rows, quarantine_rows, total_source_rows)."""
    path = RAW / fn
    with pdfplumber.open(path) as pdf:
        npages = len(pdf.pages)
        height = float(pdf.pages[0].height)
    tables = camelot.read_pdf(str(path), pages=f"1-{npages}", flavor="lattice")

    grid_subs = {sub: grid[fn]["bands_by_subsection"][sub]
                for sub in CROP_ADVISORY_SUBSECTIONS[fn]}

    raw_rows: list[dict] = []
    quarantine_rows: list[dict] = []
    total_source_rows = 0

    cur_crop = ""
    cur_chem = ""
    cur_state_key = None  # (section, subsection) — resets forward-fill on change

    for t_idx, t in enumerate(tables):
        page = int(t.page)
        page_section, page_subsection = section_map.get(fn, {}).get(
            page, ("unclassified", "unclassified"))

        # Per SUBSECTION actually seen among this table's rows (not the
        # page's single nominal tag — a boundary-page table like insecticides
        # p89 has rows whose row-level subsection differs from the page-level
        # default), content-first then geometric fallback (see
        # `resolve_phi_presence`).
        table_phi_present_cache = resolve_phi_presence(
            t, grid_subs, section_map.get(fn, {}), fn, page, height)

        for r_idx, row_cells in enumerate(t.cells):
            total_source_rows += 1
            section, subsection = row_section(
                fn, page, float(row_cells[0].y1), height, page_section, page_subsection)

            state_key = (section, subsection)
            if state_key != cur_state_key:
                cur_crop, cur_chem = "", ""
                cur_state_key = state_key

            segs = row_segments(row_cells)
            kind, resolved_or_content, content_texts = classify_row(segs)
            raw_row_text = " || ".join(content_texts) if content_texts else ""

            is_crop_advisory = section == "crop-advisory" and subsection in grid_subs
            table_phi_present = (table_phi_present_cache.get(subsection)
                                 if is_crop_advisory else None)

            # --- fumigation-style overflow: quarantine, cols_unresolved ---
            if kind == "residual_over6":
                quarantine_rows.append({
                    "source_file": fn, "source_page": page,
                    "source_table_index": t_idx, "source_row_index": r_idx,
                    "reason_code": "cols_unresolved",
                    "section": section, "subsection": subsection,
                    "raw_row_text": raw_row_text,
                })
                continue

            # --- known character-loss defect: quarantine, truncated_cell ---
            if r_idx in TRUNCATED_CELL_ROWS.get((fn, page), []):
                quarantine_rows.append({
                    "source_file": fn, "source_page": page,
                    "source_table_index": t_idx, "source_row_index": r_idx,
                    "reason_code": "truncated_cell",
                    "section": section, "subsection": subsection,
                    "raw_row_text": raw_row_text,
                })
                continue

            resolved6 = [""] * 6
            if kind == "chemical_header":
                if is_crop_advisory:
                    cur_chem = content_texts[0]
                    cur_crop = ""
            elif kind == "ordinal_6" and is_crop_advisory:
                resolved6 = list(resolved_or_content)
            elif kind == "fallback_subset" and is_crop_advisory:
                assign = best_subset_assignment(
                    resolved_or_content, grid_subs[subsection]["centers"]) \
                    if subsection in grid_subs else None
                if assign is not None:
                    for seg, b in zip(resolved_or_content, assign):
                        resolved6[b] = seg["text"]
                else:
                    resolved6 = [""] * 6

            if is_crop_advisory:
                if resolved6[0]:
                    cur_crop = resolved6[0]
                else:
                    resolved6[0] = cur_crop
                # active_ingredient is set only by header rows; carried here
                cur_active_ingredient = cur_chem
            else:
                cur_active_ingredient = ""

            markers = find_markers(content_texts)
            footnote_texts = []
            unresolved_marker = False
            for m in markers:
                if m in footnotes:
                    footnote_texts.append(footnotes[m])
                else:
                    unresolved_marker = True
            footnote_text = "; ".join(sorted(set(footnote_texts)))

            raw_rows.append({
                "source_file": fn, "source_page": page,
                "source_table_index": t_idx, "source_row_index": r_idx,
                "section": section, "subsection": subsection,
                "assignment_kind": kind,
                "crop": resolved6[0] if is_crop_advisory else "",
                "pest_or_disease": resolved6[1] if is_crop_advisory else "",
                "dose_ai": resolved6[2] if is_crop_advisory else "",
                "dose_formulation": resolved6[3] if is_crop_advisory else "",
                "dilution_water": resolved6[4] if is_crop_advisory else "",
                "waiting_period_phi": resolved6[5] if is_crop_advisory else "",
                "is_chemical_header": kind == "chemical_header",
                "phi_cell_present": table_phi_present if is_crop_advisory else "",
                "unresolved_marker": unresolved_marker,
                "footnote_text": footnote_text,
                "flag_truncated_cell": False,
                "raw_row_text": raw_row_text,
            })
            # stash active_ingredient onto the row we just appended
            raw_rows[-1]["active_ingredient"] = cur_active_ingredient if is_crop_advisory else ""

    return raw_rows, quarantine_rows, total_source_rows


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> None:
    INTERIM.mkdir(parents=True, exist_ok=True)
    section_map = load_section_map()
    grid = load_grid()

    fields = RAW_CSV_FIELDS[:8] + ["active_ingredient"] + RAW_CSV_FIELDS[8:]

    all_quarantine: list[dict] = []
    per_file_counts = {}
    total_source_rows_all = 0

    for fn in IN_SCOPE:
        print(f"== {fn}", flush=True)
        footnotes = build_footnote_registry(RAW / fn)
        print(f"   footnote registry: {footnotes}", flush=True)
        raw_rows, quarantine_rows, total_source = process_file(fn, section_map, grid, footnotes)

        out_name = fn.replace(".pdf", "_raw.csv")
        write_csv(INTERIM / out_name, raw_rows, fields)
        print(f"   wrote {INTERIM / out_name} ({len(raw_rows)} rows)", flush=True)

        all_quarantine.extend(quarantine_rows)
        total_source_rows_all += total_source
        per_file_counts[fn] = {
            "total_source_rows": total_source,
            "raw_rows": len(raw_rows),
            "quarantine_rows": len(quarantine_rows),
        }
        # checkpoint: quarantine so far, so a later file's failure doesn't
        # lose earlier files' quarantine data
        write_csv(INTERIM / "quarantine.csv", all_quarantine, QUARANTINE_CSV_FIELDS)

    # --- hard assertion ---------------------------------------------------
    total_raw = sum(c["raw_rows"] for c in per_file_counts.values())
    total_quarantine = sum(c["quarantine_rows"] for c in per_file_counts.values())
    assertion_ok = (total_raw + total_quarantine) == total_source_rows_all
    print("\n=== HARD ASSERTION ===")
    print(f"total_source_rows = {total_source_rows_all}")
    print(f"raw_csv rows      = {total_raw}")
    print(f"quarantine rows   = {total_quarantine}")
    print(f"raw + quarantine  = {total_raw + total_quarantine}")
    print(f"MATCH: {assertion_ok}")
    if not assertion_ok:
        sys.exit("HARD ASSERTION FAILED — rows unaccounted for. See counts above.")

    # --- verify sample ------------------------------------------------------
    random.seed(20260829)
    all_raw_rows = []
    for fn in IN_SCOPE:
        out_name = fn.replace(".pdf", "_raw.csv")
        with open(INTERIM / out_name, encoding="utf-8") as f:
            all_raw_rows.extend(list(csv.DictReader(f)))

    boundary_page_rows = [r for r in all_raw_rows
                          if (r["source_file"], int(r["source_page"])) in
                          [("insecticides_20260331.pdf", 10), ("insecticides_20260331.pdf", 11),
                           ("fungicides_20260331.pdf", 9), ("fungicides_20260331.pdf", 10),
                           ("bio_insecticides_20260331.pdf", 10), ("bio_insecticides_20260331.pdf", 11),
                           ("bio_fungicides_20260331.pdf", 2), ("bio_fungicides_20260331.pdf", 3)]]
    sample = []
    if boundary_page_rows:
        sample += random.sample(boundary_page_rows, min(3, len(boundary_page_rows)))

    # One row from EACH of the 3 known section-boundary pages specifically
    # (not a random draw from their combined pool) — a pool-wide sample can
    # legitimately land twice on the same page by chance and miss the
    # others entirely, which defeats the point of naming all 3.
    for fn_b, pg_b in [("insecticides_20260331.pdf", 89),
                       ("insecticides_20260331.pdf", 94),
                       ("bio_insecticides_20260331.pdf", 15)]:
        pool = [r for r in all_raw_rows
               if r["source_file"] == fn_b and int(r["source_page"]) == pg_b]
        if pool:
            sample.append(random.choice(pool))
    chosen_ids = {(r["source_file"], r["source_page"], r["source_table_index"], r["source_row_index"])
                  for r in sample}
    remaining = [r for r in all_raw_rows
                if (r["source_file"], r["source_page"], r["source_table_index"], r["source_row_index"])
                not in chosen_ids]
    sample += random.sample(remaining, max(0, 25 - len(sample)))
    write_csv(INTERIM / "verify_sample.csv", sample, fields)
    print(f"\nwrote {INTERIM / 'verify_sample.csv'} ({len(sample)} rows)")

    # --- summary ------------------------------------------------------------
    print("\n=== per-file counts ===")
    for fn, c in per_file_counts.items():
        print(f"  {fn:<34} source={c['total_source_rows']:>5} "
              f"raw={c['raw_rows']:>5} quarantine={c['quarantine_rows']:>4}")

    print("\n=== quarantine by reason code ===")
    reason_counts: dict[str, int] = {}
    for r in all_quarantine:
        reason_counts[r["reason_code"]] = reason_counts.get(r["reason_code"], 0) + 1
    for code in ("cols_unresolved", "footnote_unresolved", "truncated_cell", "section_ambiguous"):
        print(f"  {code:<22} {reason_counts.get(code, 0)}")

    print("\n=== phi_cell_present breakdown (crop-advisory rows only) ===")
    phi_counts: dict[str, int] = {"True": 0, "False": 0, "blank(non-crop-advisory)": 0}
    for r in all_raw_rows:
        v = r["phi_cell_present"]
        if v == "":
            phi_counts["blank(non-crop-advisory)"] += 1
        elif v == "True":
            phi_counts["True"] += 1
        else:
            phi_counts["False"] += 1
    for k, v in phi_counts.items():
        print(f"  {k:<28} {v}")

    print("\n=== unresolved_marker / footnote_text ===")
    n_unresolved = sum(1 for r in all_raw_rows if r["unresolved_marker"] == "True")
    n_footnoted = sum(1 for r in all_raw_rows if r["footnote_text"])
    print(f"  unresolved_marker=True rows: {n_unresolved}")
    print(f"  footnote_text populated rows: {n_footnoted}")


if __name__ == "__main__":
    main()
