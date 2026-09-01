"""Strict numeric-token MULTISET test.

Substring-containment can produce false negatives for short tokens ('500'
matches almost any blob). Lattice emits exactly one table per page (no
overlapping duplicates), so a multiset comparison is clean for lattice.
Question: does lattice ever drop a *count* of a dose value the page has?
"""
import os, re
from collections import Counter
import pdfplumber, camelot

RAW = r"c:\Users\J\OneDrive\Desktop\Fine-Tuning project\agri-llm\data\raw\cibrc"
FILES = ["insecticides_20260331.pdf", "fungicides_20260331.pdf",
         "bio_insecticides_20260331.pdf", "bio_fungicides_20260331.pdf"]
NUM = re.compile(r"[0-9][0-9.,%/+\-]*")

tot_pages = 0
flagged = []
for fn in FILES:
    path = os.path.join(RAW, fn)
    with pdfplumber.open(path) as pdf:
        n = len(pdf.pages)
        texts = {i + 1: (pdf.pages[i].extract_text() or "") for i in range(n)}
    lat, st = {}, {}
    for fl, d in (("lattice", lat), ("stream", st)):
        for t in camelot.read_pdf(path, pages=f"1-{n}", flavor=fl):
            d.setdefault(t.page, []).append(t)
    for p in range(1, n + 1):
        tot_pages += 1
        lines = [l for l in texts[p].splitlines()
                 if l.strip() and not re.fullmatch(r"\s*\(?\d{1,4}\)?\s*", l)]
        want = Counter(NUM.findall(" ".join(lines)))
        got = {}
        for fl, d in (("lattice", lat), ("stream", st)):
            # NO dedupe (conservative: favours stream)
            seen = None
            buf = []
            for t in d.get(p, []):
                for row in t.df.values.tolist():
                    key = tuple(row)
                    if False:
                        continue
                    pass
                    buf.append(" ".join(row))
            got[fl] = Counter(NUM.findall(" ".join(buf)))
        dl, ds = want - got["lattice"], want - got["stream"]
        if sum(dl.values()):
            flagged.append((fn, p, sum(dl.values()), dict(dl.most_common(8)),
                            sum(ds.values())))
    print(f"{fn} done", flush=True)

print(f"\n=== pages ({tot_pages} tested) where LATTICE is short numeric tokens ===")
for fn, p, nl, det, ns in sorted(flagged, key=lambda x: -x[2]):
    tag = "  <-- STREAM BETTER" if nl > ns else ""
    print(f"{fn:32s} p{p:<4d} lattice_short={nl:3d} stream_short={ns:3d} "
          f"{det}{tag}")
print(f"\ntotal pages where lattice short: {len(flagged)}")
print("pages where lattice short AND stream not short (or less):",
      sum(1 for f in flagged if f[2] > f[4]))
