"""
Phase 4, Step D — run parse_dose over the real dataset.

Reads the four in-scope raw CSVs from data/interim/. Runs parse_dose on every
dose_ai and dose_formulation cell (dilution_water is spray volume, not dose,
per dose_parser.py's own design rule 1 — it is not touched here).

Writes data/interim/dose_parse_report.csv, one row per (file, row, column).
Prints the coverage report to stdout and also saves it to
reports/phase4_stepD_dose_parse_report.md.

Read-only against dose_parser.py and schema.py. Does not commit anything.
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

from dose_parser import parse_dose  # noqa: E402

FILES = ["insecticides", "fungicides", "bio_insecticides", "bio_fungicides"]
COLUMNS = ["dose_ai", "dose_formulation"]

# dose_ai's CIB&RC header is "a.i (gm)" -- a real unit the column licenses.
# dose_formulation's header is "Formulation (g/ml)" -- ambiguous between mass
# and volume until the formulation type (EC/SC vs WP/WG) is known, so it gets
# no default_unit and bare numbers are expected to come back NEEDS_UNIT.
DEFAULT_UNIT = {"dose_ai": "g", "dose_formulation": None}

OUT_COLUMNS = [
    "source_file", "source_page", "source_row_index", "column", "raw_string",
    "branch", "pattern", "parsed_basis", "parsed_value_min", "parsed_value_max",
    "parsed_unit", "code", "detail",
]


def load(fn: str) -> list[dict]:
    with open(INTERIM / f"{fn}_20260331_raw.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    rows_out: list[dict] = []

    for fn in FILES:
        for row in load(fn):
            for col in COLUMNS:
                raw = row[col]
                if raw is None or raw == "":
                    # An empty cell is still "every cell" -- record it as the
                    # empty branch rather than skipping it, so the report
                    # accounts for 100% of cells in both columns.
                    rows_out.append({
                        "source_file": row["source_file"],
                        "source_page": row["source_page"],
                        "source_row_index": row["source_row_index"],
                        "column": col,
                        "raw_string": raw or "",
                        "branch": "empty",
                        "pattern": "EMPTY",
                        "parsed_basis": "", "parsed_value_min": "",
                        "parsed_value_max": "", "parsed_unit": "",
                        "code": "", "detail": "",
                    })
                    continue

                r = parse_dose(raw, default_unit=DEFAULT_UNIT[col])
                d = r.dose
                rows_out.append({
                    "source_file": row["source_file"],
                    "source_page": row["source_page"],
                    "source_row_index": row["source_row_index"],
                    "column": col,
                    "raw_string": raw,
                    "branch": r.branch,
                    "pattern": r.pattern,
                    "parsed_basis": d.basis if d else "",
                    "parsed_value_min": d.value_min if d and d.value_min is not None else "",
                    "parsed_value_max": d.value_max if d and d.value_max is not None else "",
                    "parsed_unit": d.unit if d and d.unit is not None else "",
                    "code": r.code or "",
                    "detail": r.detail or "",
                })

    out_path = INTERIM / "dose_parse_report.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_COLUMNS)
        w.writeheader()
        w.writerows(rows_out)

    report(rows_out, out_path)


def report(rows: list[dict], out_path: Path) -> None:
    L: list[str] = []

    def P(*a):
        s = " ".join(str(x) for x in a)
        print(s)
        L.append(s)

    total = len(rows)
    P(f"# Phase 4 Step D — dose_parse_report\n")
    P(f"Wrote {out_path} ({total} rows: every dose_ai and dose_formulation "
      f"cell across the 4 in-scope files)\n")

    # --- 4a. coverage by branch, per column
    P("## 4a. Coverage by branch\n")
    branches = ["numeric", "free_text", "empty", "unparseable"]
    by_col: dict[str, dict[str, int]] = {c: {b: 0 for b in branches} for c in COLUMNS}
    for r in rows:
        by_col[r["column"]][r["branch"]] += 1

    P("| column | branch | count | % of column |")
    P("|---|---|---|---|")
    for c in COLUMNS:
        col_total = sum(by_col[c].values())
        for b in branches:
            n = by_col[c][b]
            P(f"| `{c}` | {b} | {n} | {100*n/col_total:.1f}% |")
    P("")
    P("| branch | count (both columns) | % of all cells |")
    P("|---|---|---|")
    overall = {b: sum(by_col[c][b] for c in COLUMNS) for b in branches}
    for b in branches:
        P(f"| {b} | {overall[b]} | {100*overall[b]/total:.1f}% |")
    P("")

    # --- 4b. unparseable, full distinct list
    P("## 4b. Unparseable — full distinct (raw_string, code) list\n")
    unp = [r for r in rows if r["branch"] == "unparseable"]

    def distinct_table(subset):
        distinct = {}
        for r in subset:
            key = (r["raw_string"], r["code"])
            if key not in distinct:
                distinct[key] = {"count": 0, "cols": set(), "files": set()}
            distinct[key]["count"] += 1
            distinct[key]["cols"].add(r["column"])
            distinct[key]["files"].add(r["source_file"])
        return distinct

    needs_unit_rows = [r for r in unp if r["code"] == "NEEDS_UNIT"]
    other_rows = [r for r in unp if r["code"] != "NEEDS_UNIT"]

    P(f"{len(unp)} unparseable cells total, {len(distinct_table(unp))} distinct "
      f"(raw_string, code) pairs. Split below because NEEDS_UNIT is the "
      f"expected, correct outcome for a bare dose_formulation number (rule 8 "
      f"— see section 5) and would otherwise bury the small number of "
      f"genuinely actionable rows.\n")

    P(f"### 4b.1 NEEDS_UNIT — {len(needs_unit_rows)} cells, "
      f"{len(distinct_table(needs_unit_rows))} distinct raw strings — "
      f"expected, not shown here (see section 5)\n")

    P(f"### 4b.2 Everything else — {len(other_rows)} cells, "
      f"{len(distinct_table(other_rows))} distinct pairs — the actionable list\n")
    other_distinct = distinct_table(other_rows)
    P("| raw_string | code | occurrences | columns | files |")
    P("|---|---|---|---|---|")
    for (raw, code), info in sorted(other_distinct.items(), key=lambda kv: -kv[1]["count"]):
        cols = ",".join(sorted(info["cols"]))
        files = ",".join(sorted(f.replace("_20260331.pdf", "") for f in info["files"]))
        P(f"| `{raw}` | {code} | {info['count']} | {cols} | {files} |")
    P("")

    # --- 4c. numeric basis frequency
    P("## 4c. Numeric — parsed_basis frequency\n")
    num = [r for r in rows if r["branch"] == "numeric"]
    basis_freq: dict[str, int] = {}
    for r in num:
        basis_freq[r["parsed_basis"]] = basis_freq.get(r["parsed_basis"], 0) + 1
    P(f"{len(num)} numeric cells.\n")
    P("| basis | count | % of numeric |")
    P("|---|---|---|")
    for basis, n in sorted(basis_freq.items(), key=lambda kv: -kv[1]):
        P(f"| {basis} | {n} | {100*n/len(num):.1f}% |")
    P("")

    # --- 4d. 20-row random sample, 5 per branch
    P("## 4d. Random sample (5 per branch, seed=20260404)\n")
    rng = random.Random(20260404)
    for b in branches:
        pool = [r for r in rows if r["branch"] == b]
        k = min(5, len(pool))
        sample = rng.sample(pool, k)
        P(f"### {b} ({k} of {len(pool)})\n")
        P("```text")
        for r in sample:
            P(f"{r['source_file']} p{r['source_page']} row{r['source_row_index']} "
              f"[{r['column']}]")
            P(f"  raw:     {r['raw_string']!r}")
            P(f"  pattern: {r['pattern']}   code: {r['code'] or '-'}")
            if r["parsed_basis"]:
                P(f"  parsed:  basis={r['parsed_basis']} "
                  f"min={r['parsed_value_min']} max={r['parsed_value_max']} "
                  f"unit={r['parsed_unit']}")
            P("")
        P("```\n")

    # --- 5. NEEDS_UNIT count for dose_formulation
    P("## 5. dose_formulation NEEDS_UNIT count\n")
    needs_unit = [r for r in rows if r["column"] == "dose_formulation"
                  and r["code"] == "NEEDS_UNIT"]
    form_total = sum(by_col["dose_formulation"].values())
    P(f"**{len(needs_unit)}** of {form_total} dose_formulation cells "
      f"({100*len(needs_unit)/form_total:.1f}%) returned NEEDS_UNIT — a bare "
      f"number with no unit in the cell and default_unit=None, exactly as "
      f"expected per dose_parser.py rule 8. These need the formulation-type "
      f"lookup (EC/SC -> ml, WP/WG -> g) as a later step; this run does not "
      f"attempt to resolve them.\n")

    (REPORTS / "phase4_stepD_dose_parse_report.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
