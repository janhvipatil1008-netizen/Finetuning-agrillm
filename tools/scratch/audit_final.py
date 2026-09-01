import os
import camelot, pdfplumber

RAW = r"c:/Users/J/OneDrive/Desktop/Fine-Tuning project/agri-llm/data/raw/cibrc"

print("### A. rows where the PEST cell itself lands at physical index 2 (row[2] returns pest text)")
for fn in ["insecticides_20260331.pdf", "fungicides_20260331.pdf"]:
    tables = camelot.read_pdf(os.path.join(RAW, fn), pages="2-end", flavor="lattice")
    pest_at2 = 0
    tot = 0
    pages = set()
    for t in tables:
        df = t.df
        nr, nc = df.shape
        for r in range(nr):
            cells = [df.iat[r, c].strip() for c in range(nc)]
            filled = [c for c in range(nc) if cells[c] != ""]
            if len(filled) < 4:
                continue
            tot += 1
            if filled[0] == 0 and len(filled) > 1 and filled[1] == 2:
                pest_at2 += 1
                pages.add(t.page)
    print(f"  {fn}: {pest_at2}/{tot} data rows have crop@0 and pest@2 -> row[2] IS THE PEST NAME")
    print(f"    on {len(pages)} pages, e.g. {sorted(pages)[:15]}")

print()
print("### B. all-blank-column drop is a no-op on the assigned pages")
for fn, pages in [("insecticides_20260331.pdf", [87, 89, 84, 24, 58, 73]),
                  ("fungicides_20260331.pdf", [76, 81])]:
    for p in pages:
        t = camelot.read_pdf(os.path.join(RAW, fn), pages=str(p), flavor="lattice")[0]
        df = t.df
        nc = df.shape[1]
        nz = [c for c in range(nc) if (df.iloc[:, c].str.strip() != "").sum() == 0]
        print(f"  {fn.split('_')[0]} p{p}: {nc} cols, all-blank cols={nz} -> after drop {nc-len(nz)} cols")

print()
print("### C. PDF-level x-coordinate proof (insecticides p87): x0 of each a.i.-dose string")
targets = ["60 +60", "0.018%", "75+75", "90 + 90", "108", "60 + 120", "40 + 60", "45 +90", "50 + 75"]
with pdfplumber.open(os.path.join(RAW, "insecticides_20260331.pdf")) as pdf:
    pg = pdf.pages[86]
    # vertical ruling lines
    xs = sorted({round(e["x0"], 1) for e in pg.vertical_edges})
    print(f"  vertical ruling-line x positions ({len(xs)}): {xs}")
    for w in pg.extract_words():
        if w["text"] in ("60", "0.018%", "75+75", "90", "108", "40", "45", "50", "112.50"):
            print(f"    word {w['text']!r:10} x0={w['x0']:.1f} top={w['top']:.1f}")
