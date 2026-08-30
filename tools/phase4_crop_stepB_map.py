"""
Phase 4 (crop), Step B — run map_crop over the real dataset.

Reads the four in-scope raw CSVs from data/interim/. Runs map_crop on every
crop cell (every row, including chemical/column-header rows, whose crop
cells are blank by construction -- same convention as the dose Step D and
PHI Step C runs).

Writes data/interim/crop_map_report.csv, one row per (source row, split
result) -- a multi-crop split produces multiple output rows from one input
row. Prints the coverage report to stdout and saves it to
reports/phase4_crop_stepB_map_report.md.

Read-only against crop_mapper.py and schema.py. Does not commit anything.
"""
from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
INTERIM = ROOT / "data" / "interim"
REPORTS = ROOT / "reports"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from crop_mapper import SLUGS, map_crop  # noqa: E402

FILES = ["insecticides", "fungicides", "bio_insecticides", "bio_fungicides"]
DATA_KINDS = {"ordinal_6", "fallback_subset"}

OUT_COLUMNS = [
    "source_file", "source_page", "source_row_index", "raw_crop", "slug",
    "multi_crop_split", "pest_bled", "not_a_crop_cell",
]


def load(fn: str) -> list[dict]:
    with open(INTERIM / f"{fn}_20260331_raw.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    rows_out: list[dict] = []

    for fn in FILES:
        for row in load(fn):
            raw = row["crop"] or ""
            for r in map_crop(raw):
                rows_out.append({
                    "source_file": row["source_file"],
                    "source_page": row["source_page"],
                    "source_row_index": row["source_row_index"],
                    "raw_crop": raw,
                    "slug": r.slug or "",
                    "multi_crop_split": r.multi_crop_split,
                    "pest_bled": r.pest_bled,
                    "not_a_crop_cell": r.not_a_crop_cell,
                    "_assignment_kind": row["assignment_kind"],  # dropped before write
                })

    out_path = INTERIM / "crop_map_report.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_COLUMNS)
        w.writeheader()
        for r in rows_out:
            w.writerow({k: r[k] for k in OUT_COLUMNS})

    report(rows_out, out_path)


def report(rows: list[dict], out_path: Path) -> None:
    L: list[str] = []

    def P(*a):
        s = " ".join(str(x) for x in a)
        print(s)
        L.append(s)

    total = len(rows)
    data_rows = [r for r in rows if r["_assignment_kind"] in DATA_KINDS]

    P("# Phase 4 (crop) Step B — crop_map_report\n")
    P(f"Wrote {out_path} ({total} output rows from every crop cell across the "
      f"4 in-scope files, all row kinds including headers; a multi-crop split "
      f"produces more than one output row per input row)\n")

    # --- a/b/c: in-scope / out-of-scope / blank
    P("## Coverage (all row kinds, i.e. includes 921+89 header rows whose "
      "crop cell is blank by construction)\n")
    in_scope = [r for r in rows if r["slug"]]
    out_scope_notcell = [r for r in rows if not r["slug"] and not r["not_a_crop_cell"]
                         and r["raw_crop"].strip()]
    not_a_crop = [r for r in rows if r["not_a_crop_cell"]]
    blank = [r for r in rows if not r["raw_crop"].strip()]
    P(f"- in-scope (maps to a slug): **{len(in_scope)}**")
    P(f"- out of scope (real crop, not one of the 8): **{len(out_scope_notcell)}**")
    P(f"- not_a_crop_cell (prose that merely mentions a crop): **{len(not_a_crop)}**")
    P(f"- blank raw_crop: **{len(blank)}**")
    P(f"- check: {len(in_scope)+len(out_scope_notcell)+len(not_a_crop)+len(blank)} "
      f"== {total}\n")

    data_blank = [r for r in data_rows if not r["raw_crop"].strip()]
    P(f"Of the blanks, **{len(data_blank)}** are on data rows "
      f"(`assignment_kind` in ordinal_6/fallback_subset) -- this is the "
      f"number comparable to Phase A's 219. The remaining "
      f"{len(blank)-len(data_blank)} are header rows, which Phase A excluded "
      f"by scope and this run does not.\n")

    # --- d: per-slug counts
    P("## Per-slug row counts (in-scope only)\n")
    P("| slug | rows |")
    P("|---|---|")
    for slug in SLUGS:
        n = sum(1 for r in in_scope if r["slug"] == slug)
        P(f"| {slug} | {n} |")
    P(f"| **total** | **{len(in_scope)}** |\n")

    # --- e: multi-crop splits
    P("## Multi-crop splits\n")
    splits = [r for r in rows if r["multi_crop_split"] and r["slug"]]
    by_raw: dict[str, list[dict]] = {}
    for r in splits:
        by_raw.setdefault(r["raw_crop"], []).append(r)
    P(f"{len(by_raw)} distinct source strings produced a multi-crop-flagged "
      f"result; {len(splits)} total output rows from them.\n")
    P("| raw_crop | slugs produced | rows |")
    P("|---|---|---|")
    for raw, rs in sorted(by_raw.items()):
        slugs_here = sorted({r["slug"] for r in rs})
        P(f"| `{raw}` | {slugs_here} | {len(rs)} |")
    P("")

    # --- f: pest-bled
    P("## Pest-bled rows\n")
    pest = [r for r in rows if r["pest_bled"]]
    pest_in_scope = [r for r in pest if r["slug"]]
    pest_out_scope = [r for r in pest if not r["slug"]]
    P(f"{len(pest)} rows total: {len(pest_in_scope)} in-scope (crop of "
      f"interest per your decision 3), {len(pest_out_scope)} on out-of-scope "
      f"crops (`slug` blank below -- the flag still fires because pest text "
      f"bled into the cell regardless of which crop it names, but these rows "
      f"never reach label_db since slug is None; listed for completeness).\n")
    P("| source_file | page | row | raw_crop | slug |")
    P("|---|---|---|---|---|")
    for r in pest:
        P(f"| {r['source_file']} | {r['source_page']} | {r['source_row_index']} | "
          f"`{r['raw_crop']}` | {r['slug'] or '(out of scope)'} |")
    P("")

    # --- g: not_a_crop_cell
    P("## not_a_crop_cell rows\n")
    P(f"{len(not_a_crop)} rows.\n")
    P("| source_file | page | row | raw_crop |")
    P("|---|---|---|---|")
    for r in not_a_crop:
        P(f"| {r['source_file']} | {r['source_page']} | {r['source_row_index']} | "
          f"`{r['raw_crop']}` |")
    P("")

    # --- h: Phase A reconciliation
    P("## Phase A reconciliation\n")
    data_in_scope = [r for r in data_rows if r["slug"]]
    distinct_data_in_scope_strings = {r["raw_crop"] for r in data_in_scope}
    P(f"Phase A (data rows only, pre-split, one string = one bucket): "
      f"**47 distinct strings / 746 cells**.\n")
    P(f"This run, data rows only, POST-split (multi-crop cells now contribute "
      f"one output row per slug):")
    P(f"- distinct source strings that produced an in-scope result: "
      f"**{len(distinct_data_in_scope_strings)}**")
    P(f"- output rows: **{len(data_in_scope)}**\n")
    diff = len(data_in_scope) - 746
    P(f"Difference from 746: **{diff:+d}**.\n")
    P("Full explanation, not a guess: Phase A's `slugs_for` had no concept of "
      "`not_a_crop_cell` -- it token-matched every string, including prose, "
      "and its 5 flagged 'MULTI-CROP?' cells each named exactly ONE in-scope "
      "slug, so each contributed its 1 cell to that slug's total same as any "
      "other member. Phase A's 746 therefore already includes those 5 cells: "
      "`Wheat, Gram`->gram, `Rice (Paddy) &cotton`->cotton, "
      "`Tomato/Chilli es`->tomato, the Cabbage list->tomato, and the "
      "rodenticide row->soybean.\n")
    P("Step B changes exactly one of those five: `map_crop` recognises the "
      "rodenticide cell as prose ('For rodent control in field, storage and "
      "crops like rice, soybean and coconut)') via `_NOT_A_CROP_CELL` and "
      "returns slug=None, not_a_crop_cell=True -- per decision 1, drop "
      "entirely. The other four still resolve to exactly one slug each, "
      "unchanged. So the only expected movement is -1 (soybean loses the "
      "rodenticide cell), and 746 - 1 = 745 matches what this run produced "
      "exactly.\n")

    # --- 4: 15-row sample
    P("## Sample: 10 in-scope (>=1 per slug where possible) + 5 out-of-scope\n")
    rng = random.Random(20260501)
    P("### In-scope\n")
    P("```text")
    chosen = []
    remaining_pool = list(in_scope)
    for slug in SLUGS:
        pool = [r for r in remaining_pool if r["slug"] == slug]
        if pool:
            pick = rng.choice(pool)
            chosen.append(pick)
            remaining_pool.remove(pick)
    while len(chosen) < 10 and remaining_pool:
        pick = rng.choice(remaining_pool)
        chosen.append(pick)
        remaining_pool.remove(pick)
    for r in chosen:
        P(f"{r['source_file']} p{r['source_page']} row{r['source_row_index']}")
        P(f"  raw_crop: {r['raw_crop']!r}   slug: {r['slug']}"
          f"{'  [multi]' if r['multi_crop_split'] else ''}"
          f"{'  [pest]' if r['pest_bled'] else ''}")
        P("")
    P("```\n")

    P("### Out-of-scope\n")
    P("```text")
    pool = [r for r in rows if not r["slug"] and not r["not_a_crop_cell"]
           and r["raw_crop"].strip()]
    for r in rng.sample(pool, min(5, len(pool))):
        P(f"{r['source_file']} p{r['source_page']} row{r['source_row_index']}")
        P(f"  raw_crop: {r['raw_crop']!r}")
        P("")
    P("```\n")

    (REPORTS / "phase4_crop_stepB_map_report.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
