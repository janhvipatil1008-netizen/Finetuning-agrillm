"""Audit: does lattice ever lose label-claim chars that stream preserves?

Re-derived independently. For EVERY page of the four in-scope files we:
  - read the raw text layer (pdfplumber)
  - run camelot lattice and stream (single multi-page call per flavour)
  - build the character multiset (whitespace stripped, casefolded) of all
    cells each flavour returns
  - missing = Counter(textlayer) - Counter(cells)   (chars the flavour dropped)
Then flag pages where lattice_missing > stream_missing.
"""
import json, os, re, sys, time
from collections import Counter

import pdfplumber
import camelot

RAW = r"c:\Users\J\OneDrive\Desktop\Fine-Tuning project\agri-llm\data\raw\cibrc"
OUT = r"c:\Users\J\OneDrive\Desktop\Fine-Tuning project\agri-llm\tools\scratch"
FILES = [
    "insecticides_20260331.pdf",
    "fungicides_20260331.pdf",
    "bio_insecticides_20260331.pdf",
    "bio_fungicides_20260331.pdf",
]

WS = re.compile(r"\s+")


def norm(s):
    return WS.sub("", (s or "")).casefold()


def page_text_counter(txt):
    """Text layer, minus a bare page-number footer line (report's discount)."""
    lines = [l for l in (txt or "").splitlines()]
    kept = [l for l in lines if not re.fullmatch(r"\s*\(?\d{1,4}\)?\s*", l or "")]
    dropped = [l for l in lines if re.fullmatch(r"\s*\(?\d{1,4}\)?\s*", l or "")]
    return Counter(norm("".join(kept))), dropped


def cells_counter(tables):
    c = Counter()
    n = 0
    for t in tables:
        for row in t.df.values.tolist():
            for cell in row:
                s = norm(cell)
                c.update(s)
                n += len(s)
    return c, n


def run(fn):
    path = os.path.join(RAW, fn)
    with pdfplumber.open(path) as pdf:
        npages = len(pdf.pages)
        texts = {i + 1: (pdf.pages[i].extract_text() or "") for i in range(npages)}

    res = {}
    for flavour in ("lattice", "stream"):
        t0 = time.time()
        tl = camelot.read_pdf(path, pages=f"1-{npages}", flavor=flavour)
        by = {}
        for t in tl:
            by.setdefault(t.page, []).append(t)
        res[flavour] = by
        print(f"  {fn} {flavour}: {len(tl)} tables, pages_with_tables="
              f"{len(by)}/{npages}, {time.time()-t0:.1f}s", flush=True)

    rows = []
    for p in range(1, npages + 1):
        tc, dropped = page_text_counter(texts[p])
        rec = {"file": fn, "page": p, "textchars": sum(tc.values()),
               "footer_dropped": dropped}
        for flavour in ("lattice", "stream"):
            tabs = res[flavour].get(p, [])
            cc, ncells = cells_counter(tabs)
            missing = tc - cc
            extra = cc - tc
            rec[flavour] = {
                "ntables": len(tabs),
                "shapes": [list(t.df.shape) for t in tabs],
                "chars": ncells,
                "missing": sum(missing.values()),
                "extra": sum(extra.values()),
                "missing_detail": dict(missing.most_common(30)),
            }
        rec["lattice_worse_by"] = rec["lattice"]["missing"] - rec["stream"]["missing"]
        rows.append(rec)
    return rows


all_rows = []
for fn in FILES:
    print(f"== {fn}", flush=True)
    all_rows += run(fn)

with open(os.path.join(OUT, "charloss_allpages.json"), "w", encoding="utf-8") as f:
    json.dump(all_rows, f, ensure_ascii=False)

print("\n=== PAGES WHERE LATTICE MISSING > STREAM MISSING ===")
bad = [r for r in all_rows if r["lattice_worse_by"] > 0]
bad.sort(key=lambda r: -r["lattice_worse_by"])
print(f"count = {len(bad)} of {len(all_rows)} pages tested")
for r in bad:
    print(f"{r['file']:34s} p{r['page']:<4d} text={r['textchars']:5d} "
          f"lattice_missing={r['lattice']['missing']:5d} (ntab={r['lattice']['ntables']}) "
          f"stream_missing={r['stream']['missing']:5d} (ntab={r['stream']['ntables']}) "
          f"delta=+{r['lattice_worse_by']}")

print("\n=== pages where lattice returned ZERO tables ===")
for r in all_rows:
    if r["lattice"]["ntables"] == 0:
        print(f"{r['file']} p{r['page']} text={r['textchars']} "
              f"stream_ntab={r['stream']['ntables']} stream_missing={r['stream']['missing']}")

print("\n=== totals per file ===")
for fn in FILES:
    rs = [r for r in all_rows if r["file"] == fn]
    print(f"{fn:34s} pages={len(rs):4d} "
          f"lattice_missing_tot={sum(r['lattice']['missing'] for r in rs):6d} "
          f"stream_missing_tot={sum(r['stream']['missing'] for r in rs):6d} "
          f"pages_lattice_worse={sum(1 for r in rs if r['lattice_worse_by']>0):4d} "
          f"pages_stream_worse={sum(1 for r in rs if r['lattice_worse_by']<0):4d}")
