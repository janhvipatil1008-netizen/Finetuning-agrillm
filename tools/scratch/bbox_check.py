"""Are the tokens lattice drops physically inside the ruled table box?
If they sit outside the lattice table bbox they are overflow/furniture that
lattice is arguably correct to exclude; if inside, lattice truly dropped
in-table content.
"""
import os
import pdfplumber, camelot

RAW = r"c:\Users\J\OneDrive\Desktop\Fine-Tuning project\agri-llm\data\raw\cibrc"
CASES = [("fungicides_20260331.pdf", 38, ["plant", "protection"]),
         ("insecticides_20260331.pdf", 6, ["1."]),
         ("bio_fungicides_20260331.pdf", 20, ["***"]),
         ("fungicides_20260331.pdf", 83, ["****Dose", "Warning:"]),
         ("insecticides_20260331.pdf", 2, ["Approved"])]

for fn, pg, needles in CASES:
    path = os.path.join(RAW, fn)
    tl = camelot.read_pdf(path, pages=str(pg), flavor="lattice")
    boxes = [t._bbox for t in tl]
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[pg - 1]
        H = page.height
        words = page.extract_words()
    print(f"=== {fn} p{pg}  page height={H:.1f}")
    print(f"    lattice table bbox(es) (PDF coords, y from bottom): "
          f"{[tuple(round(v,1) for v in b) for b in boxes]}")
    for w in words:
        if any(nd.lower() in w["text"].lower() for nd in needles):
            # pdfplumber top-origin -> PDF bottom-origin
            y0, y1 = H - w["bottom"], H - w["top"]
            inside = [i for i, b in enumerate(boxes)
                      if b[0] - 2 <= w["x0"] and w["x1"] <= b[2] + 2
                      and b[1] - 2 <= y0 and y1 <= b[3] + 2]
            print(f"    word {w['text']!r:22s} x=({w['x0']:.1f},{w['x1']:.1f}) "
                  f"y=({y0:.1f},{y1:.1f})  inside_lattice_bbox={inside or 'NONE'}")
    print()
