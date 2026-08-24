"""Does stream actually LOSE characters, or only reorder them?

Motivated by bio_fungicides p2, where stream's second table opens with the crop
name rendered `rapes` while lattice has `Grapes`. Claiming character loss is a
strong claim, so test it: compare the character multiset of every cell of every
table each flavour returns for the page, against the page's raw text layer.

Run across the first/middle/last table page of all four in-scope files so the
answer is not a single-page fluke.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import camelot
import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "cibrc"

TARGETS = {
    "insecticides_20260331.pdf": [2, 55, 84],
    "fungicides_20260331.pdf": [2, 42, 82],
    "bio_insecticides_20260331.pdf": [2, 10, 18],
    "bio_fungicides_20260331.pdf": [2, 10, 19],
}


def norm(s: str) -> str:
    return re.sub(r"\s+", "", str(s or "")).lower()


def flavour_chars(path: Path, page: int, flavour: str) -> Counter:
    c = Counter()
    try:
        for t in camelot.read_pdf(str(path), pages=str(page), flavor=flavour):
            for _, row in t.df.iterrows():
                for cell in row.tolist():
                    c.update(norm(cell))
    except Exception as e:  # noqa: BLE001
        print(f"    !! {flavour} p{page}: {e}")
    return c


print(f"{'file':<34}{'pg':>4} {'flavour':<9}{'chars':>7} "
      f"{'missing_vs_textlayer':>21} {'extra':>7}")
print("-" * 92)

for name, pages in TARGETS.items():
    path = RAW / name
    with pdfplumber.open(path) as pdf:
        for pg in pages:
            ref = Counter(norm(pdf.pages[pg - 1].extract_text() or ""))
            # strip the bare page-number footer, which camelot never returns
            for ch in norm(str(pg)):
                if ref[ch]:
                    ref[ch] -= 1
            for flavour in ("lattice", "stream"):
                got = flavour_chars(path, pg, flavour)
                missing = ref - got
                extra = got - ref
                n_missing = sum(missing.values())
                flag = "" if n_missing == 0 else "   <-- LOSS"
                print(
                    f"{name:<34}{pg:>4} {flavour:<9}{sum(got.values()):>7} "
                    f"{n_missing:>21} {sum(extra.values()):>7}{flag}"
                )
                if n_missing:
                    print(f"      missing chars: "
                          f"{''.join(sorted(missing.elements()))[:120]!r}")
