"""Is the p2 heading inside or outside the ruled table box / camelot bbox?"""
import fitz
import pdfplumber
import camelot

PDF = (r"c:\Users\J\OneDrive\Desktop\Fine-Tuning project\agri-llm"
       r"\data\raw\cibrc\insecticides_20260331.pdf")

doc = fitz.open(PDF)
p = doc[1]
print("PyMuPDF rect:", p.rect, "mediabox:", p.mediabox,
      "cropbox:", p.cropbox, "rotation:", p.rotation)

with pdfplumber.open(PDF) as pdf:
    pg = pdf.pages[1]
    print("pdfplumber bbox:", pg.bbox, "mediabox:", pg.mediabox,
          "cropbox:", pg.cropbox, "h=", pg.height)
    # ruled lines: topmost horizontal rule of the table
    hs = sorted({round(l["top"], 2) for l in pg.lines
                 if abs(l["y0"] - l["y1"]) < 0.5})
    rects = sorted({round(r["top"], 2) for r in pg.rects
                    if r["height"] < 2})
    print("horizontal LINE tops (pdfplumber top-down):", hs[:8])
    print("thin RECT tops (pdfplumber top-down):", rects[:8])
    top_rule = min(hs + rects) if (hs or rects) else None
    print("topmost horizontal rule, top-down y =", top_rule)

    # heading words
    heading = [w for w in pg.extract_words() if w["top"] < 90]
    for w in heading:
        print("  heading word", repr(w["text"]),
              "top=%.2f bottom=%.2f" % (w["top"], w["bottom"]))
    hb = max(w["bottom"] for w in heading)
    print("heading lowest edge (top-down) =", hb)

    # 'Agricultural Use' -- the first row lattice DOES return
    ag = [w for w in pg.extract_words() if w["text"] in ("Agricultural", "Use")]
    for w in ag:
        print("  agri word", repr(w["text"]),
              "top=%.2f bottom=%.2f" % (w["top"], w["bottom"]))

H = pg.height  # 842.5
tbl = camelot.read_pdf(PDF, pages="2", flavor="lattice")[0]
bx = tbl._bbox
print()
print("camelot bbox (pdfminer, y from BOTTOM):", bx)
print("camelot bbox converted to top-down: top=%.2f bottom=%.2f"
      % (H - bx[3], H - bx[1]))
print()
for w in heading:
    y0b = H - w["bottom"]   # bottom-up y of glyph bottom
    y1b = H - w["top"]
    inside = (bx[0] <= w["x0"] <= bx[2]) and (bx[1] <= y0b and y1b <= bx[3])
    print("word %-14s bottom-up y=[%.2f,%.2f]  inside camelot bbox? %s"
          % (repr(w["text"]), y0b, y1b, inside))
print()
print("gap between heading bottom edge and top of camelot box: %.2f pt"
      % ((H - bx[3]) - hb))
