"""Sweep EVERY page of all four PDFs for lattice character shortfall.
Tests the report's generalisation, which was based on 3 sampled pages/file.
"""
import re
import sys
from collections import Counter

import camelot
import pdfplumber

RAW = (r"c:\Users\J\OneDrive\Desktop\Fine-Tuning project\agri-llm"
       r"\data\raw\cibrc")
FILES = ["insecticides_20260331.pdf", "fungicides_20260331.pdf",
         "bio_insecticides_20260331.pdf", "bio_fungicides_20260331.pdf"]

DIGITS = set("0123456789")
LABELISH = re.compile(r"[0-9%]")


def norm(s):
    return re.sub(r"\s+", "", str(s or "")).lower()


for name in FILES:
    path = RAW + "\\" + name
    with pdfplumber.open(path) as pdf:
        npages = len(pdf.pages)
        refs, rawtxt = {}, {}
        for i in range(npages):
            t = pdf.pages[i].extract_text() or ""
            rawtxt[i + 1] = t
            c = Counter(norm(t))
            for ch in norm(str(i + 1)):
                if c[ch]:
                    c[ch] -= 1
            refs[i + 1] = c

    tables = camelot.read_pdf(path, pages="1-%d" % npages, flavor="lattice")
    got = {p: Counter() for p in range(1, npages + 1)}
    for t in tables:
        for _, row in t.df.iterrows():
            for cell in row.tolist():
                got[t.page].update(norm(cell))

    print("=" * 78)
    print(name, "-", npages, "pages,", len(tables), "lattice tables")
    print("=" * 78)
    tot_miss = 0
    hits = []
    for p in range(1, npages + 1):
        miss = refs[p] - got[p]
        m = sum(miss.values())
        if m:
            tot_miss += m
            digits = sum(v for k, v in miss.items() if k in DIGITS)
            hits.append((p, m, digits, "".join(sorted(miss.elements()))))
    print("pages with lattice shortfall: %d / %d ; total missing chars %d"
          % (len(hits), npages, tot_miss))
    for p, m, d, s in hits:
        print("  p%-4d missing=%-5d digit_chars=%-4d  %s" % (p, m, d, s[:110]))
    sys.stdout.flush()
