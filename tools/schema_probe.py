"""Why does the column count vary? Characterise each distinct page schema.

The shape census showed the 6-column crop table is only the *dominant* schema,
not the universal one. This groups pages by lattice column count and prints the
first row of each, so every off-mode schema can be named rather than guessed at.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CENSUS = ROOT / "data" / "interim" / "phase2_census.json"

census = json.loads(CENSUS.read_text(encoding="utf-8"))

for rec in census:
    print("=" * 100)
    print(f"{rec['file']}  ({rec['pages']} pages)  — LATTICE schemas by column count")
    by_cols: dict[int, list[dict]] = defaultdict(list)
    for t in rec["flavours"]["lattice"]["tables"]:
        by_cols[t["cols"]].append(t)

    for ncols in sorted(by_cols):
        ts = by_cols[ncols]
        pages = [t["page"] for t in ts]
        print(f"\n--- {ncols} cols : {len(ts)} pages -> {pages[:40]}"
              f"{' ...' if len(pages) > 40 else ''}")
        # show up to 3 exemplar first-rows
        for t in ts[:3]:
            fr = " ‖ ".join(
                c.replace("\n", "↵")[:46] for c in t["first_row"]
            )
            print(f"    p{t['page']:<4} first_row: {fr}")
