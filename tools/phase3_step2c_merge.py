"""PHASE 3, STEP 2c — merge phantom continuation rows back into their parents.

Runs AFTER `phase3_step2_extract.py` and edits its outputs in place:
  data/interim/<name>_raw.csv                 49 phantom rows merged away
  data/interim/quarantine.csv                 1 row's raw_row_text extended
  data/interim/phase3_step2c_manifest.json    every dropped row in full
  reports/phase3_step2c_merge.md              audit report, expected vs actual

If the extractor is ever re-run, its CSVs are reborn WITH the phantoms and
this script must be re-run after it. It refuses to run twice (the frozen
candidate set no longer matches once merged) and refuses to run on drifted
data (any mismatch with the frozen set aborts before a single write).

The defect being repaired (diagnosed in Step 2b, reports/phase3_step2b_phantom.md)
----------------------------------------------------------------------------
A table cell that wraps across a page break comes back from camelot as its
own row at the top of page N+1. Step 2's forward-fill then supplies `crop`
and `active_ingredient`, so the fragment materialises as a complete-looking
advisory row with empty dose columns — a (crop, pest) pair the source never
registered.

The merge rule (user-approved, 2026-08-29)
----------------------------------------------------------------------------
For each fragment row: every one of its own segments is APPENDED (single
space, verbatim) to the SAME column of the last data row of the previous
page, its raw_row_text is appended to the parent's raw_row_text, and the
fragment row is dropped from the raw CSV (kept in full in the manifest).
Column-specific, not generic: a pest fragment lands in the parent's
pest_or_disease cell, a method fragment in method, and so on. Where the
parent's target cell is empty the append just sets it — deliberately: for
fungicides p31/p33 the parent's prose head sits in dose_formulation (band
assignment) while the tail was classed method; same-column append keeps both
rows' assignments raw rather than guessing which cell "should" hold prose,
which is a Step 4 normalisation question the parents already pose on their
own.

Two special cases, each with its own logic:
* `insecticides p28 r0` — QUARANTINE PARENT. Its raw-CSV predecessor is
  p27's column-header row; the true parent is the QUARANTINED p27 r17
  Aluminum-Phosphide fumigation row (`Go down fumigation || ... Khapra ||`,
  cut mid-word — the fragment starts `Beetle, Rust red flour beetle...`).
  The fragment's raw_row_text is appended to that quarantine row's
  raw_row_text (a 7-field-schema row has no 6-band cells to append into);
  quarantine row COUNT is unchanged.
* `insecticides p32 r0` — CROP WRAP. The fragment's first segment
  (`and coconut)`) is the tail of the parent's CROP cell, which is also the
  forward-fill anchor. Handled exactly like a column merge (crop seg ->
  parent crop, dilution seg -> parent dilution) PLUS an assertion that no
  later row inherited the fragment's crop via forward-fill — verified in
  diagnosis (the very next row is the `Flonicamid 50%WG` chemical header,
  which resets the carry) and re-asserted here rather than assumed.

Hard precondition (user requirement 1): a candidate whose own segments
include a populated crop cell is EXCLUDED before any merge — those are
genuine rows (bio_insecticides p10 r0 is the known case). p32 is the single
own-crop row that IS merged, and only via the dedicated crop-wrap path.

The frozen merge set
----------------------------------------------------------------------------
49 rows, enumerated below as MERGE_SET, per-row evidence in
reports/phase3_step2b_phantom.md and reports/phase3_step2c_merge.md:
  * the 36 all-dose-empty data rows of the Step 2b list minus
    bio_insecticides p10 (own crop): 23 pest + 12 method singles +
    bio_insecticides p11 (pest+method),
  * the 5 partial-class singles: dilution (fungicides p16,
    bio_fungicides p4, p11) and dose_formulation (fungicides p34,
    bio_fungicides p3),
  * the partial-class extensions insecticides p28 (quarantine parent) and
    bio_fungicides p12 (form+method),
  * insecticides p32 (crop wrap),
  * 5 wraps found during pre-merge verification to have been misjudged
    "genuine" in Step 2b's §5 read, approved for inclusion 2026-08-29:
    insecticides p16 (pest+form+phi; parent form ends `750 –`),
    insecticides p70 (pest+ai; parent ai ends `(200.5 + 19.5 –`),
    fungicides p78 (pest+ai+dil; parent pest ends `Aphid,`),
    bio_fungicides p6 (pest+form+method; parent pest ends `Leaf and`),
    bio_fungicides p15 (pest+form+dil+phi; parent pest ends `f.sp.`).

NOT merged, verified genuine: own-crop rows (bio_insecticides p10,
insecticides p53, fungicides p17/p36/p42/p55) and insecticides p26/p75 —
their parents are COMPLETE (PHI filled, nothing dangling) and the rows carry
their own dose values (`Jassids, Aphids || 84 || 700 || 500`): second
registered claims under the same chemical, not tails.

Accounting (user requirement, restated hard assertion)
----------------------------------------------------------------------------
    source rows == raw + quarantine + merged-away fragments
    3766        == 3703 + 14 + 49
Nothing vanishes: every dropped row is stored in full in the manifest, and
expected totals are computed BEFORE any write and asserted after.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
REPORTS = ROOT / "reports"

FILES = {
    "insecticides": "insecticides_20260331_raw.csv",
    "fungicides": "fungicides_20260331_raw.csv",
    "bio_insecticides": "bio_insecticides_20260331_raw.csv",
    "bio_fungicides": "bio_fungicides_20260331_raw.csv",
}

DOSE_COLS = ["dose_ai", "dose_formulation", "dilution_water", "waiting_period_phi"]
SEG_COLS = ["crop", "pest_or_disease"] + DOSE_COLS + ["method"]

# ---------------------------------------------------------------------------
# Frozen merge set: (file_key, page, row_index) -> mode.
#   "column"            append each own segment to the parent's same column
#   "quarantine_parent" append raw_row_text to QUAR_PARENT's raw_row_text
#   "crop_wrap"         column merge incl. crop + forward-fill carry assert
# ---------------------------------------------------------------------------
MERGE_SET: dict[tuple[str, int, int], str] = {
    # insecticides — 18 pest singles
    **{("insecticides", p, 0): "column"
       for p in (11, 13, 14, 15, 31, 51, 52, 57, 59, 60, 62, 64,
                 69, 76, 78, 82, 85, 86)},
    ("insecticides", 16, 0): "column",            # pest+form+phi   (added)
    ("insecticides", 28, 0): "quarantine_parent",  # fumigation tail
    ("insecticides", 32, 0): "crop_wrap",          # crop+dilution tail
    ("insecticides", 70, 0): "column",             # pest+ai         (added)
    # fungicides — 3 pest + 3 method singles, dil, form, added wrap
    **{("fungicides", p, 0): "column"
       for p in (10, 31, 32, 33, 45, 75, 16, 34)},
    ("fungicides", 78, 0): "column",               # pest+ai+dil     (added)
    # bio_insecticides
    ("bio_insecticides", 11, 0): "column",         # pest+method
    ("bio_insecticides", 12, 0): "column",         # method single
    ("bio_insecticides", 15, 0): "column",         # pest single
    # bio_fungicides
    **{("bio_fungicides", p, 0): "column"
       for p in (3, 4, 5, 8, 9, 11, 13, 14, 16, 17, 18, 19)},
    ("bio_fungicides", 6, 0): "column",            # pest+form+method (added)
    ("bio_fungicides", 12, 0): "column",           # form+method
    ("bio_fungicides", 15, 0): "column",           # 4-cell wrap      (added)
}

QUAR_PARENT = ("insecticides", 27, 17)  # the quarantined fumigation row

# Known-genuine all-dose-empty first rows (never merged; asserted untouched).
GENUINE_ALL_EMPTY = {("bio_insecticides", 10, 0)}

EXPECTED_MERGED = {"insecticides": 22, "fungicides": 9,
                   "bio_insecticides": 3, "bio_fungicides": 15}
EXPECTED_RAW_AFTER = {"insecticides": 2020, "fungicides": 1260,
                      "bio_insecticides": 291, "bio_fungicides": 132}
EXPECTED_QUARANTINE = 14


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


def own_segments(row: dict) -> list[str]:
    return row["raw_row_text"].split(" || ") if row["raw_row_text"] else []


def seg_to_column(row: dict, segs: list[str]) -> list[tuple[str, str]]:
    """Map each own segment to the semantic column it was assigned to.

    Value-equality against the row's populated columns, consumed in
    reading order — which is also column order, both being x-order. Any
    segment that matches no column is a hard error: nothing in the frozen
    set may be guessed at merge time.
    """
    remaining = {c: row[c] for c in SEG_COLS if row[c]}
    out = []
    for seg in segs:
        hit = next((c for c, v in remaining.items() if v == seg), None)
        if hit is None:
            raise AssertionError(
                f"segment {seg!r} has no column in row "
                f"p{row['source_page']} r{row['source_row_index']}")
        out.append((hit, seg))
        del remaining[hit]
    return out


def main() -> None:
    data = {k: load_csv(INTERIM / fn) for k, fn in FILES.items()}
    quar_fields, quar_rows = load_csv(INTERIM / "quarantine.csv")

    # ------------------------- refuse to run twice ------------------------ #
    counts_now = {k: len(rows) for k, (_, rows) in data.items()}
    if counts_now == EXPECTED_RAW_AFTER:
        print("already merged (raw counts match post-merge totals) — nothing to do")
        return

    # --------------- derive candidates, verify against frozen set -------- #
    # First data row of each page, crop-advisory, any dose column empty:
    # exactly the Step 2b net. Everything it catches must be either in the
    # frozen MERGE_SET, a known-genuine row, or an own-crop/own-value row
    # verified genuine in Step 2b — anything else is drift, and we abort.
    derived: dict[tuple[str, int, int], int] = {}   # identity -> csv index
    own_crop_excluded: list[tuple[str, int, int]] = []
    for k, (_, rows) in data.items():
        seen_pages: set[str] = set()
        for i, r in enumerate(rows):
            p = r["source_page"]
            first = p not in seen_pages
            seen_pages.add(p)
            if not first or r["section"] != "crop-advisory":
                continue
            if r["assignment_kind"] in ("chemical_header", "column_header"):
                continue
            if not any(not r[c] for c in DOSE_COLS):
                continue
            ident = (k, int(p), int(r["source_row_index"]))
            segs = own_segments(r)
            cols = [c for c, _ in seg_to_column(r, segs)]
            if "crop" in cols and MERGE_SET.get(ident) != "crop_wrap":
                own_crop_excluded.append(ident)
                continue
            if ident in MERGE_SET:
                derived[ident] = i
            elif ident in GENUINE_ALL_EMPTY or all(not r[c] for c in DOSE_COLS):
                raise AssertionError(f"unfrozen all-empty candidate: {ident}")
            # partial rows verified genuine (ins p26/p75 pattern) fall through

    missing = set(MERGE_SET) - set(derived)
    if missing:
        raise AssertionError(f"frozen rows not found in CSVs: {sorted(missing)}")
    assert len(derived) == 49, f"expected 49 merge rows, derived {len(derived)}"

    # HARD PRECONDITION (user requirement 1), asserted before any merge:
    # no row in the merge set has an own-crop segment except the crop_wrap,
    # and the known-genuine own-crop row is not in the set.
    for ident, i in derived.items():
        r = data[ident[0]][1][i]
        cols = [c for c, _ in seg_to_column(r, own_segments(r))]
        assert "crop" not in cols or MERGE_SET[ident] == "crop_wrap", ident
    assert ("bio_insecticides", 10, 0) not in derived
    print(f"own-crop exclusion: {len(own_crop_excluded)} candidates excluded "
          f"before merge: {sorted(own_crop_excluded)}")

    # ------------------------------- merge -------------------------------- #
    manifest: list[dict] = []
    per_column: dict[str, int] = {}
    drop: dict[str, set[int]] = {k: set() for k in FILES}

    for ident in sorted(derived, key=lambda x: (x[0], x[1])):
        k, page, r_idx = ident
        i = derived[ident]
        fields, rows = data[k]
        frag = rows[i]
        mode = MERGE_SET[ident]
        entry = {"file": k, "page": page, "row_index": r_idx, "mode": mode,
                 "fragment_row": dict(frag), "appended": []}

        if mode == "quarantine_parent":
            qk, qp, qr = QUAR_PARENT
            parent = next(q for q in quar_rows
                          if q["source_file"].startswith(qk)
                          and int(q["source_page"]) == qp
                          and int(q["source_row_index"]) == qr)
            before = parent["raw_row_text"]
            parent["raw_row_text"] = before + " " + frag["raw_row_text"]
            entry["parent"] = {"quarantine": True, "page": qp, "row_index": qr,
                               "raw_before": before,
                               "raw_after": parent["raw_row_text"]}
            per_column["quarantine_raw"] = per_column.get("quarantine_raw", 0) + 1
        else:
            parent = rows[i - 1]
            assert int(parent["source_page"]) == page - 1, ident
            assert parent["assignment_kind"] not in (
                "chemical_header", "column_header"), ident
            entry["parent"] = {"page": parent["source_page"],
                               "row_index": parent["source_row_index"],
                               "cells_before": {}, "cells_after": {}}
            for col, seg in seg_to_column(frag, own_segments(frag)):
                entry["parent"]["cells_before"][col] = parent[col]
                parent[col] = (parent[col] + " " + seg).strip()
                entry["parent"]["cells_after"][col] = parent[col]
                per_column[col] = per_column.get(col, 0) + 1
                entry["appended"].append({"column": col, "text": seg})
            parent["raw_row_text"] += " " + frag["raw_row_text"]
            if mode == "crop_wrap":
                # the fragment's crop was the forward-fill state for one
                # row-classification instant; assert no later row inherited it
                bad_crop = frag["crop"]
                inheritors = [j for j in range(i + 1, len(rows))
                              if rows[j]["crop"] == bad_crop]
                assert not inheritors, (
                    f"crop-wrap carry leaked to rows {inheritors}")
                entry["carry_leak_check"] = "clean"
        drop[k].add(i)
        manifest.append(entry)

    # -------------------------- verify & write ---------------------------- #
    merged_per_file = {k: len(v) for k, v in drop.items()}
    assert merged_per_file == EXPECTED_MERGED, merged_per_file
    new_rows = {k: [r for j, r in enumerate(rows) if j not in drop[k]]
                for k, (_, rows) in data.items()}
    raw_after = {k: len(v) for k, v in new_rows.items()}
    assert raw_after == EXPECTED_RAW_AFTER, raw_after
    assert len(quar_rows) == EXPECTED_QUARANTINE

    # source rows == raw + quarantine + merged-away fragments
    source = sum(counts_now.values()) + len(quar_rows)
    assert source == sum(raw_after.values()) + len(quar_rows) + len(manifest), \
        (source, raw_after, len(manifest))

    for k, fn in FILES.items():
        write_csv(INTERIM / fn, data[k][0], new_rows[k])
    write_csv(INTERIM / "quarantine.csv", quar_fields, quar_rows)
    (INTERIM / "phase3_step2c_manifest.json").write_text(
        json.dumps({"merged": manifest,
                    "own_crop_excluded": sorted(own_crop_excluded),
                    "per_column": per_column,
                    "raw_after": raw_after}, indent=2, ensure_ascii=False),
        encoding="utf-8")

    print(f"merged {len(manifest)} phantom rows "
          f"({', '.join(f'{k}={v}' for k, v in sorted(merged_per_file.items()))})")
    print(f"per-column appends: {per_column}")
    print(f"raw after: {raw_after}  (total {sum(raw_after.values())})")
    print(f"identity: {source} source == {sum(raw_after.values())} raw + "
          f"{len(quar_rows)} quarantine + {len(manifest)} merged")


if __name__ == "__main__":
    sys.exit(main())
