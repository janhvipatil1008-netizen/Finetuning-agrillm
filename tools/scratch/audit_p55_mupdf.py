import pymupdf, re, collections
PDF = r"C:\Users\J\OneDrive\Desktop\Fine-Tuning project\agri-llm\data\raw\cibrc\insecticides_20260331.pdf"
d = pymupdf.open(PDF)
p = d[54]
print("rotation:", p.rotation, "mediabox:", p.mediabox)
print("images:", len(p.get_images(full=True)), "annots:", len(list(p.annots())))
print("drawings:", len(p.get_drawings()))
txt = p.get_text("text")
toks = re.findall(r"\S+", txt)
print("mupdf token count:", len(toks))
print("--- mupdf text ---")
print(txt)
# render-mode-3 (invisible) text check
rd = p.get_text("rawdict")
spans = [s for b in rd["blocks"] if b["type"] == 0 for l in b["lines"] for s in l["spans"]]
print("spans:", len(spans), "fonts:", set(s["font"] for s in spans))
print("span flags:", collections.Counter(s["flags"] for s in spans))
