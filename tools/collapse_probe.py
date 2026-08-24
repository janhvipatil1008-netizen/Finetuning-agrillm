"""Is lattice's column-count instability sparse padding, or real schema variety?

Hypothesis: on many pages lattice finds extra vertical ruling lines and emits
mostly-empty filler columns. If so, dropping columns that are empty for EVERY
row of a table should collapse the count back to the 6-column crop schema.

If the hypothesis holds, Phase 3 can normalise columns per table instead of
trusting positional indices. If it does not hold, the file genuinely contains
many schemas and each needs its own mapping.

Reports, per file: the column-count histogram before and after collapsing, and
the pages that still differ from 6 afterwards (those are the genuinely different
tables — fumigants, rodenticides, public health, household, locust).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import camelot

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "cibrc"

FILES = [
    "insecticides_20260331.pdf",
    "fungicides_20260331.pdf",
    "bio_insecticides_20260331.pdf",
    "bio_fungicides_20260331.pdf",
]


def collapse(df):
    """Drop columns that are blank in every row."""
    keep = [
        c for c in df.columns
        if any(str(v).strip() for v in df[c].tolist())
    ]
    return df[keep]


for name in FILES:
    path = RAW / name
    tables = camelot.read_pdf(str(path), pages="2-end", flavor="lattice")
    before, after = Counter(), Counter()
    still_off: dict[int, list] = defaultdict(list)
    for t in tables:
        b = t.df.shape[1]
        c = collapse(t.df)
        a = c.shape[1]
        before[b] += 1
        after[a] += 1
        if a != 6:
            first = " ‖ ".join(
                str(x).replace("\n", "↵")[:34] for x in c.iloc[0].tolist()
            )
            still_off[a].append((int(t.page), first))

    print("=" * 100)
    print(name)
    print(f"  cols BEFORE collapse: {dict(sorted(before.items()))}")
    print(f"  cols AFTER  collapse: {dict(sorted(after.items()))}")
    n6 = after.get(6, 0)
    print(f"  -> {n6}/{sum(after.values())} tables land on exactly 6 columns "
          f"({100 * n6 / max(1, sum(after.values())):.0f}%)")
    for ncols in sorted(still_off):
        entries = still_off[ncols]
        print(f"  -- still {ncols} cols: {len(entries)} tables, "
              f"pages {[p for p, _ in entries][:30]}")
        for p, first in entries[:4]:
            print(f"       p{p:<4} {first}")
