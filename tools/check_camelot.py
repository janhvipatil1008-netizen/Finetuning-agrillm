"""Toolchain smoke test: can camelot actually run both flavours here?

camelot's lattice flavour historically needed a Ghostscript *binary*; newer
versions render via pdfium instead. No Ghostscript is installed on this machine,
so verify empirically rather than assuming. Runs one page only.
"""

from __future__ import annotations

import traceback
from pathlib import Path

import camelot

RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "cibrc"
PDF = RAW / "insecticides_20260331.pdf"
PAGE = "55"

print("camelot version:", getattr(camelot, "__version__", "?"))
try:
    import cv2

    print("cv2 version:", cv2.__version__)
except Exception as e:
    print("cv2 MISSING:", e)

for flavour in ("lattice", "stream"):
    print("=" * 60)
    print(f"flavour={flavour} page={PAGE}")
    try:
        tables = camelot.read_pdf(str(PDF), pages=PAGE, flavor=flavour)
        print(f"  OK  n_tables={len(tables)}")
        for i, t in enumerate(tables):
            rep = t.parsing_report
            print(
                f"   table[{i}] shape={t.df.shape} "
                f"accuracy={rep.get('accuracy')} whitespace={rep.get('whitespace')}"
            )
    except Exception:
        print("  FAILED:")
        traceback.print_exc()
