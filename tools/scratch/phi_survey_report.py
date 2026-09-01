"""Phase 4 PHI Step A — report generator. Read-only."""
from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools" / "scratch"))
sys.path.insert(0, str(ROOT / "src"))

from phi_survey_a import (classify, collect, kind_of, norm,  # noqa: E402
                          run_existing)

PROPOSED = {
    "BARE_NUMBER": "int (days)", "BARE_RANGE": "int (max of range)",
    "NUM_DAYS": "int (days)", "RANGE_DAYS": "int (max)",
    "NUM_WEEKS": "int (x7)", "NUM_MONTHS": "int (x30)",
    "RANGE_MONTHS": "int (max x30)",
    "BLANK": "None", "NULL_MARKER": "None", "NULL_MARKER_QUALIFIED": "None",
    "SEED_TREATMENT_PROSE": "None", "NOT_REQUIRED_PROSE": "None",
    "PROSE_NO_NUMBER": "None", "GROWTH_STAGE": "None",
    "NUM_HOURS": "DECISION", "MIXED_UNITS": "raise/quarantine",
    "RESIDUE_CONDITION": "DECISION", "DEFECT_STANDARD_REF": "raise/quarantine",
    "DEFECT_DILUTION_TEXT": "raise/quarantine",
    "DEFECT_DOSE_TEXT": "raise/quarantine",
    "DEFECT_COLUMN_COLLAPSE": "raise/quarantine", "UNCLASSIFIED": "DECISION",
}


def main() -> None:
    dist = collect()
    buckets = collections.defaultdict(list)
    for s in dist:
        buckets[classify(s)].append(s)
    total = sum(d["rows"] for d in dist.values())

    L: list[str] = []
    W = L.append

    W("# Phase 4 (PHI) Step A — waiting_period_phi surface survey\n")
    W("Source: the four in-scope raw CSVs in `data/interim/`, data rows only")
    W("(`assignment_kind` in {`ordinal_6`, `fallback_subset`}). Column:")
    W("`waiting_period_phi`. Read-only; no parser written.\n")

    W("## 1. Totals\n")
    W(f"- **Distinct strings: {len(dist)}** (227 non-empty + the empty string)")
    W(f"- Cells: {total}\n")

    W("## 2. Surface patterns\n")
    W("`disposition` is a PROPOSAL for the parser step, not a fact about the data.\n")
    W("| pattern | distinct | cells | class | proposed disposition |")
    W("|---|---|---|---|---|")
    order = sorted(buckets.items(),
                   key=lambda kv: -sum(dist[s]["rows"] for s in kv[1]))
    for name, ss in order:
        c = sum(dist[s]["rows"] for s in ss)
        W(f"| `{name}` | {len(ss)} | {c} | {kind_of(name)} | "
          f"{PROPOSED.get(name, '?')} |")
    W("")

    W("## 3. Examples, verbatim\n")
    for name, ss in order:
        c = sum(dist[s]["rows"] for s in ss)
        W(f"### `{name}` — {len(ss)} distinct / {c} cells\n")
        W("```text")
        for s in sorted(ss, key=lambda x: -dist[x]["rows"])[:5]:
            status, val = run_existing(s)
            got = f"RAISES" if status == "raises" else repr(val)
            W(f"{norm(s)[:96]!r}")
            W(f"    x{dist[s]['rows']:<4} committed parse_phi -> {got}")
        W("```\n")

    W("## 4. Blank vs explicitly absent\n")
    W("The frozen schema cannot tell these apart — see section 7.\n")
    W("| category | distinct | cells |")
    W("|---|---|---|")
    W(f"| blank cell (`''`) | 1 | {sum(dist[s]['rows'] for s in buckets['BLANK'])} |")
    exp = ["NULL_MARKER", "NULL_MARKER_QUALIFIED", "NOT_REQUIRED_PROSE",
           "SEED_TREATMENT_PROSE", "PROSE_NO_NUMBER", "GROWTH_STAGE"]
    sub = 0
    for k in exp:
        c = sum(dist[s]["rows"] for s in buckets.get(k, []))
        sub += c
        W(f"| `{k}` | {len(buckets.get(k, []))} | {c} |")
    blank = sum(dist[s]["rows"] for s in buckets["BLANK"])
    W(f"| **explicitly-absent subtotal** | | **{sub}** |")
    W(f"| **blank + explicit** | | **{blank + sub}** of {total} "
      f"({100*(blank+sub)/total:.1f}%) |\n")
    W(f"`NULL_MARKER` tokens seen: {sorted(buckets['NULL_MARKER'])}\n")

    W("## 5. Ranges\n")
    DASH = r"(?:-|–|—)"
    rng = [s for s in dist if re.search(rf"\d\s*{DASH}\s*\d", norm(s))]
    rc = sum(dist[s]["rows"] for s in rng)
    W(f"**{rc} cells / {len(rng)} distinct strings** contain a numeric range.\n")
    W("**Rule (confirmed): a range collapses to the LARGER value.** Longer wait")
    W("= safer for the farmer, so this is the opposite of the dose rule (which")
    W("takes the lower bound) and the same safe direction. The committed")
    W("`parse_phi` already implements this via `max(nums)`.\n")
    for k in ("BARE_RANGE", "RANGE_MONTHS"):
        vals = [norm(s) for s in sorted(buckets.get(k, []))]
        W(f"- `{k}` — {len(vals)} distinct: {vals}")
    W("")

    (ROOT / "reports" / "phase4_phi_stepA_survey.md").write_text(
        "\n".join(L), encoding="utf-8")
    print(f"wrote reports/phase4_phi_stepA_survey.md ({len(L)} lines)")


if __name__ == "__main__":
    main()
