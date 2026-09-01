"""Geometric audit: in-table content lattice silently drops.

For every lattice cell on every page, find the text-layer words whose centre
lies inside the cell rectangle. If such a word's text does not appear in that
cell's returned text, lattice dropped in-table content. This is the direct
test - no confound from cell splitting, duplication, or tokenisation.
Then check whether stream preserved the same word.
"""
import os, re
import pdfplumber, camelot

RAW = r"c:\Users\J\OneDrive\Desktop\Fine-Tuning project\agri-llm\data\raw\cibrc"
FILES = ["insecticides_20260331.pdf", "fungicides_20260331.pdf",
         "bio_insecticides_20260331.pdf", "bio_fungicides_20260331.pdf"]
WS = re.compile(r"\s+")
norm = lambda s: WS.sub("", (s or "")).casefold()

hits = []
npages_tested = 0
for fn in FILES:
    path = os.path.join(RAW, fn)
    with pdfplumber.open(path) as pdf:
        n = len(pdf.pages)
        words = {i + 1: (pdf.pages[i].extract_words(), pdf.pages[i].height)
                 for i in range(n)}
    lat, st = {}, {}
    for fl, d in (("lattice", lat), ("stream", st)):
        for t in camelot.read_pdf(path, pages=f"1-{n}", flavor=fl):
            d.setdefault(t.page, []).append(t)
    for p in range(1, n + 1):
        npages_tested += 1
        ws, H = words[p]
        stblob = norm("".join(c for t in st.get(p, [])
                             for r in t.df.values.tolist() for c in r))
        for t in lat.get(p, []):
            for row in t.cells:
                for c in row:
                    ct = norm(c.text)
                    for w in ws:
                        cx = (w["x0"] + w["x1"]) / 2
                        cy = H - (w["top"] + w["bottom"]) / 2
                        if not (c.x1 <= cx <= c.x2 and c.y1 <= cy <= c.y2):
                            continue
                        nw = norm(w["text"])
                        if nw and nw not in ct:
                            hits.append({
                                "file": fn, "page": p, "word": w["text"],
                                "cell_xy": (round(c.x1, 1), round(c.y1, 1),
                                            round(c.x2, 1), round(c.y2, 1)),
                                "cell_text": c.text[:60],
                                "in_stream": nw in stblob})
    print(f"{fn} done", flush=True)

print(f"\n=== {npages_tested} pages tested. "
      f"{len(hits)} words inside a lattice cell but missing from it ===")
print(f"    of which stream DID preserve the word: "
      f"{sum(1 for h in hits if h['in_stream'])}\n")
bypage = {}
for h in hits:
    bypage.setdefault((h["file"], h["page"]), []).append(h)
for (fn, p), hs in sorted(bypage.items(), key=lambda kv: -len(kv[1])):
    print(f"--- {fn} p{p}: {len(hs)} dropped word(s), "
          f"{sum(1 for h in hs if h['in_stream'])} of them kept by stream")
    for h in hs:
        print(f"      {h['word']!r:22s} cell={h['cell_xy']} "
              f"cell_text={h['cell_text']!r:46s} stream_kept={h['in_stream']}")
