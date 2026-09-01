import os, sys, re
import pdfplumber, camelot
RAW = r"c:\Users\J\OneDrive\Desktop\Fine-Tuning project\agri-llm\data\raw\cibrc"
fn, pg = sys.argv[1], sys.argv[2]
path = os.path.join(RAW, fn)
with pdfplumber.open(path) as pdf:
    print("=== RAW TEXT LAYER ===")
    print(pdf.pages[int(pg) - 1].extract_text() or "")
for fl in ("lattice", "stream"):
    tl = camelot.read_pdf(path, pages=pg, flavor=fl)
    print(f"=== {fl}: {len(tl)} tables ===")
    for i, t in enumerate(tl):
        print(f"table[{i}] shape={t.df.shape}")
        for r, row in enumerate(t.df.values.tolist()):
            print("  r%-3d| %s" % (r, " || ".join(c.replace("\n", "\u21b5") for c in row)))
