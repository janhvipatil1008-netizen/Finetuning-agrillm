"""What exactly does lattice lose on insecticides p6 and fungicides p35?"""
import re
from collections import Counter

import camelot
import pdfplumber

RAW = (r"c:\Users\J\OneDrive\Desktop\Fine-Tuning project\agri-llm"
       r"\data\raw\cibrc")


def norm(s):
    return re.sub(r"\s+", "", str(s or "")).lower()


for name, pg in [("insecticides_20260331.pdf", 6),
                 ("fungicides_20260331.pdf", 35),
                 ("insecticides_20260331.pdf", 109)]:
    path = RAW + "\\" + name
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[pg - 1]
        raw = page.extract_text() or ""
        words = page.extract_words()
        H = page.height
    tabs = camelot.read_pdf(path, pages=str(pg), flavor="lattice")

    lat_words = Counter()
    for t in tabs:
        for _, row in t.df.iterrows():
            for cell in row.tolist():
                for w in re.split(r"\s+", str(cell)):
                    if w:
                        lat_words[norm(w)] += 1
    raw_words = Counter(norm(w["text"]) for w in words)
    miss = raw_words - lat_words

    print("=" * 78)
    print("%s p%d   lattice tables=%d shapes=%s"
          % (name, pg, len(tabs), [t.df.shape for t in tabs]))
    print("=" * 78)
    print("words present in text layer, absent from every lattice cell:")
    need = Counter(miss)
    for w in words:
        k = norm(w["text"])
        if need.get(k):
            need[k] -= 1
            print("   %-22s x0=%7.2f x1=%7.2f  y_bottomup=[%.2f,%.2f]"
                  % (repr(w["text"]), w["x0"], w["x1"],
                     H - w["bottom"], H - w["top"]))
    for t in tabs:
        print("   camelot bbox:", t._bbox)
    # show the raw lines containing the missing tokens
    print("--- raw text lines mentioning the missing tokens ---")
    toks = {w for w in miss}
    for ln in raw.split("\n"):
        if any(t and t in norm(ln) for t in toks):
            print("   |", ln)
    print()
