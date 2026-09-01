"""Line-level loss audit, all 231 pages, both flavours.

Char-multiset comparison is confounded: stream emits overlapping/duplicated
rows, so surplus copies of a character cancel out genuine losses of the same
character elsewhere on the page. This audit is immune to that: for every
line of the page's raw text layer, ask "does the normalised line appear as a
substring of the concatenation of this flavour's cells?".

Reports, per page:
  lat_only_lost  = lines lost by lattice but PRESERVED by stream  <-- counterexamples
  str_only_lost  = lines lost by stream but preserved by lattice
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
    blobs = {}
    for fl in ("lattice", "stream"):
        by = {}
        for t in camelot.read_pdf(path, pages=f"1-{n}", flavor=fl):
            by[t.page] = by.get(t.page, "") + "\u241f".join(
                norm(c) for r in t.df.values.tolist() for c in r)
        blobs[fl] = by
        print(f"{fn} {fl} done", flush=True)

    for p in range(1, n + 1):
        lines = [l for l in texts[p].splitlines()
                 if l.strip() and not re.fullmatch(r"\s*\(?\d{1,4}\)?\s*", l)]
        lat, st = blobs["lattice"].get(p, ""), blobs["stream"].get(p, "")
        latlost = [l for l in lines if norm(l) and norm(l) not in lat]
        stlost = [l for l in lines if norm(l) and norm(l) not in st]
        lat_only = [l for l in latlost if l not in stlost]
        st_only = [l for l in stlost if l not in latlost]
        rows.append({"file": fn, "page": p, "nlines": len(lines),
                     "lat_lost": len(latlost), "st_lost": len(stlost),
                     "lat_only": lat_only, "st_only": st_only,
                     "lat_only_chars": sum(len(norm(l)) for l in lat_only),
                     "st_only_chars": sum(len(norm(l)) for l in st_only)})

json.dump(rows, open(os.path.join(OUT, "linelevel.json"), "w", encoding="utf-8"),
          ensure_ascii=False)

print("\n" + "=" * 90)
print("PAGES WHERE LATTICE LOST WHOLE LINES THAT STREAM PRESERVED")
bad = sorted([r for r in rows if r["lat_only"]], key=lambda r: -r["lat_only_chars"])
print(f"count = {len(bad)} of {len(rows)} pages\n")
for r in bad:
    print(f"--- {r['file']} p{r['page']}  ({r['lat_only_chars']} chars, "
          f"{len(r['lat_only'])} lines lost by lattice only)")
    for l in r["lat_only"]:
        print(f"      LATTICE LOST: {l!r}")

print("\n" + "=" * 90)
print("summary per file: pages where lattice-only-loss occurred / stream-only-loss")
for fn in FILES:
    rs = [r for r in rows if r["file"] == fn]
    print(f"{fn:34s} pages={len(rs):4d}  "
          f"lat_only_pages={sum(1 for r in rs if r['lat_only']):4d} "
          f"lat_only_chars={sum(r['lat_only_chars'] for r in rs):6d}  |  "
          f"str_only_pages={sum(1 for r in rs if r['st_only']):4d} "
          f"str_only_chars={sum(r['st_only_chars'] for r in rs):6d}")
