"""
Phase 4 (PHI), Step C — run parse_phi over the real dataset.

Reads the four in-scope raw CSVs from data/interim/. Runs parse_phi on every
waiting_period_phi cell (every row, including chemical/column-header rows,
whose PHI cells are legitimately blank — same convention as the Phase D dose
run).

Writes data/interim/phi_parse_report.csv, one row per (file, row). Prints the
coverage report to stdout and saves it to
reports/phase4_phi_stepC_parse_report.md.

Read-only against parse_phi.py and schema.py. Does not commit anything.
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

from parse_phi import PHIParseError, parse_phi  # noqa: E402

FILES = ["insecticides", "fungicides", "bio_insecticides", "bio_fungicides"]
COL = "waiting_period_phi"

OUT_COLUMNS = [
    "source_file", "source_page", "source_row_index", "raw_string",
    "outcome", "value", "error_detail",
]

# The five cells decision 1 (glued-unit fix) was written for. Verbatim from
# reports/phase4_phi_stepA_survey.md / the Phase B report. Real crops are
# Maize/Sorghum/Mustard/Bajra, not grape -- corrected in the Phase B report.
REGRESSION_CELLS = [
    ("3½-4months  Depending on  the variety", 120),
    ("3½-4months  Depending  on  the  variety", 120),
    ("3½-4months  Depending  on the  variety", 120),
    ("3-3½months  Depending  on the variety", 105),
    ("3.5-4  months", 120),
]


def load(fn: str) -> list[dict]:
    with open(INTERIM / f"{fn}_20260331_raw.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    rows_out: list[dict] = []

    for fn in FILES:
        for row in load(fn):
            raw = row[COL] or ""
            try:
                value = parse_phi(raw)
            except PHIParseError as e:
                rows_out.append({
                    "source_file": row["source_file"],
                    "source_page": row["source_page"],
                    "source_row_index": row["source_row_index"],
                    "raw_string": raw,
                    "outcome": "raised",
                    "value": "",
                    "error_detail": str(e),
                })
                continue

            outcome = "resolved" if value is not None else "not_applicable"
            rows_out.append({
                "source_file": row["source_file"],
                "source_page": row["source_page"],
                "source_row_index": row["source_row_index"],
                "raw_string": raw,
                "outcome": outcome,
                "value": value if value is not None else "",
                "error_detail": "",
            })

    out_path = INTERIM / "phi_parse_report.csv"
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
    P(f"# Phase 4 (PHI) Step C — phi_parse_report\n")
    P(f"Wrote {out_path} ({total} rows: every waiting_period_phi cell across "
      f"the 4 in-scope files, all row kinds including headers)\n")

    # --- coverage
    P("## Coverage\n")
    outcomes = ["resolved", "not_applicable", "raised"]
    counts = {o: sum(1 for r in rows if r["outcome"] == o) for o in outcomes}
    P("| outcome | count | % |")
    P("|---|---|---|")
    for o in outcomes:
        P(f"| {o} | {counts[o]} | {100*counts[o]/total:.1f}% |")
    P("")

    # --- full list of raised strings
    P("## Raised — full distinct list\n")
    raised = [r for r in rows if r["outcome"] == "raised"]
    distinct: dict[str, dict] = {}
    for r in raised:
        key = r["raw_string"]
        if key not in distinct:
            distinct[key] = {"count": 0, "detail": r["error_detail"],
                             "files": set()}
        distinct[key]["count"] += 1
        distinct[key]["files"].add(r["source_file"])
    P(f"{len(raised)} raised cells, {len(distinct)} distinct raw strings.\n")
    P("| raw_string | occurrences | files | error_detail |")
    P("|---|---|---|---|")
    for raw, info in sorted(distinct.items(), key=lambda kv: -kv[1]["count"]):
        files = ",".join(sorted(f.replace("_20260331.pdf", "") for f in info["files"]))
        P(f"| `{raw}` | {info['count']} | {files} | {info['detail'][:100]} |")
    P("")

    # --- 15-row sample across resolved / not_applicable
    P("## Sample (resolved + not_applicable, seed=20260415)\n")
    rng = random.Random(20260415)
    for o in ("resolved", "not_applicable"):
        pool = [r for r in rows if r["outcome"] == o]
        k = min(8 if o == "resolved" else 7, len(pool))
        sample = rng.sample(pool, k)
        P(f"### {o} ({k} of {len(pool)})\n")
        P("```text")
        for r in sample:
            P(f"{r['source_file']} p{r['source_page']} row{r['source_row_index']}")
            P(f"  raw:   {r['raw_string']!r}")
            P(f"  value: {r['value']}")
            P("")
        P("```\n")

    # --- regression confirmation
    P("## Regression check — the glued-unit fix cells\n")
    by_raw = {}
    for r in rows:
        by_raw.setdefault(r["raw_string"], []).append(r)
    all_ok = True
    P("| raw_string | expected | actual | rows | ok? |")
    P("|---|---|---|---|---|")
    for raw, expected in REGRESSION_CELLS:
        matches = by_raw.get(raw, [])
        actual_vals = {m["value"] for m in matches}
        actual = next(iter(actual_vals)) if len(actual_vals) == 1 else actual_vals
        ok = actual_vals == {expected}
        all_ok = all_ok and ok
        P(f"| `{raw}` | {expected} | {actual} | {len(matches)} | "
          f"{'YES' if ok else 'NO'} |")
    P("")
    P(f"**All five regression cells correct: {all_ok}**\n")

    (REPORTS / "phase4_phi_stepC_parse_report.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
