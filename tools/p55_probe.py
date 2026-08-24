"""Standalone p55 lattice-vs-stream probe (insecticides).

Independent of the census so it can run while that is in flight. Also pulls the
raw pdftotext-style text layer for the same page via pdfplumber, which is the
neutral referee: it shows how many *logical* label claims the page really holds,
without either camelot flavour's opinion.
"""

from __future__ import annotations

from pathlib import Path

import camelot
import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "data" / "raw" / "cibrc" / "insecticides_20260331.pdf"
PAGE = 55


def is_blank(s) -> bool:
    return not str(s or "").strip()


for flavour in ("lattice", "stream"):
    tabs = list(camelot.read_pdf(str(PDF), pages=str(PAGE), flavor=flavour))
    total = sum(t.df.shape[0] for t in tabs)
    print("=" * 90)
    print(f"FLAVOUR={flavour}  tables={len(tabs)}  total_physical_rows={total}")
    for ti, t in enumerate(tabs):
        df = t.df
        print(f"-- table[{ti}] shape={df.shape}")
        for ri in range(df.shape[0]):
            cells = [str(x) for x in df.iloc[ri].tolist()]
            flag = ""
            pop = [i for i, c in enumerate(cells) if not is_blank(c)]
            if not pop:
                flag = "[EMPTY]"
            elif len(pop) == 1:
                flag = "[FULLWIDTH]"
            elif is_blank(cells[0]):
                flag = "[CONT]"
            elif len(cells) > 1 and not is_blank(cells[1]):
                flag = "[ENTRY]"
            else:
                flag = "[PARTIAL]"
            print(f"  r{ri:<3}{flag:<12}| "
                  + " ‖ ".join(c.replace("\n", "↵") for c in cells))

print("=" * 90)
print("NEUTRAL REFEREE — raw text layer for the same page (pdfplumber):")
with pdfplumber.open(PDF) as pdf:
    print(pdf.pages[PAGE - 1].extract_text())
