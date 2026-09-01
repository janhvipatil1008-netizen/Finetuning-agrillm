"""Definitive loss audit, all 231 pages, both flavours.

Two earlier methods were confounded:
  * character multiset  -> stream's overlapping/duplicated tables inflate its
    per-character counts and cancel out genuine losses.
  * whole-line matching -> rewards a flavour for dumping an entire visual row
    into ONE cell (stream's 57x1 junk tables on insecticides p7), and punishes
    the flavour that correctly splits the row into cells.

This test is immune to both: a token from the page's text layer counts as
PRESERVED if its whitespace-stripped casefolded form appears anywhere in the
whitespace-stripped concatenation of that flavour's cells for that page.
Cell splitting is irrelevant; duplication cannot mask anything.
"""
import json, os, re
import pdfplumber, camelot

RAW = r"c:\Users\J\OneDrive\Desktop\Fine-Tuning project\agri-llm\data\raw\cibrc"
OUT = r"c:\Users\J\OneDrive\Desktop\Fine-Tuning project\agri-llm\tools\scratch"
FILES = ["insecticides_20260331.pdf", "fungicides_20260331.pdf",
         "bio_insecticides_20260331.pdf", "bio_fungicides_20260331.pdf"]
WS = re.compile(r"\s+")
norm = lambda s: WS.sub("", (s or "")).casefold()

rows = []
for fn in FILES:
    path = os.path.join(RAW, fn)
    with pdfplumber.open(path) as pdf:
        n = len(pdf.pages)
        texts = {i + 1: (pdf.pages[i].extract_text() or "") for i in range(n)}
    blob = {}
    for fl in ("lattice", "stream"):
        by = {}
        for t in camelot.read_pdf(path, pages=f"1-{n}", flavor=fl):
            by[t.page] = by.get(t.page, "") + norm(
                "".join(c for r in t.df.values.tolist() for c in r))
        blob[fl] = by
        print(f"{fn} {fl} done", flush=True)

    for p in range(1, n + 1):
        lines = [l for l in texts[p].splitlines()
                 if l.strip() and not re.fullmatch(r"\s*\(?\d{1,4}\)?\s*", l)]
        toks = [t for l in lines for t in l.split() if norm(t)]
        lat, st = blob["lattice"].get(p, ""), blob["stream"].get(p, "")
        latlost = [t for t in toks if norm(t) not in lat]
        stlost = [t for t in toks if norm(t) not in st]
        # tokens lattice dropped that stream kept, and vice versa
        lat_only = [t for t in latlost if norm(t) in st]
        st_only = [t for t in stlost if norm(t) in lat]
        rows.append({
            "file": fn, "page": p, "ntok": len(toks),
            "lat_lost": len(latlost), "st_lost": len(stlost),
            "lat_only": lat_only, "st_only": st_only,
            "lat_only_num": [t for t in lat_only if any(c.isdigit() for c in t)],
            "st_only_num": [t for t in st_only if any(c.isdigit() for c in t)],
        })

json.dump(rows, open(os.path.join(OUT, "token.json"), "w", encoding="utf-8"),
          ensure_ascii=False)

print("\n" + "=" * 92)
print("A) PAGES WHERE LATTICE DROPPED TOKENS THAT STREAM PRESERVED  (counterexamples)")
bad = sorted([r for r in rows if r["lat_only"]], key=lambda r: -len(r["lat_only"]))
print(f"   pages = {len(bad)} of {len(rows)}   total tokens = "
      f"{sum(len(r['lat_only']) for r in rows)}\n")
for r in bad:
    print(f"--- {r['file']} p{r['page']}  ({len(r['lat_only'])} tokens, "
          f"{len(r['lat_only_num'])} numeric)")
    print(f"      LATTICE DROPPED / STREAM KEPT: {r['lat_only']}")

print("\n" + "=" * 92)
print("B) reverse direction, for scale: pages where STREAM dropped tokens lattice kept")
sb = [r for r in rows if r["st_only"]]
print(f"   pages = {len(sb)} of {len(rows)}   total tokens = "
      f"{sum(len(r['st_only']) for r in rows)}")
for r in sorted(sb, key=lambda r: -len(r["st_only"]))[:8]:
    print(f"   {r['file']} p{r['page']}: {len(r['st_only'])} tokens "
          f"({len(r['st_only_num'])} numeric) e.g. {r['st_only'][:12]}")

print("\n" + "=" * 92)
print("C) per-file summary")
for fn in FILES:
    rs = [r for r in rows if r["file"] == fn]
    print(f"{fn:34s} pages={len(rs):4d}  "
          f"LAT-only-loss: pages={sum(1 for r in rs if r['lat_only']):3d} "
          f"tok={sum(len(r['lat_only']) for r in rs):5d} "
          f"numeric={sum(len(r['lat_only_num']) for r in rs):4d}   |   "
          f"STREAM-only-loss: pages={sum(1 for r in rs if r['st_only']):3d} "
          f"tok={sum(len(r['st_only']) for r in rs):5d} "
          f"numeric={sum(len(r['st_only_num']) for r in rs):4d}")
