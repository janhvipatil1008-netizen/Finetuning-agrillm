import os, re, sys
from collections import Counter
import pdfplumber, camelot

RAW = r"c:\Users\J\OneDrive\Desktop\Fine-Tuning project\agri-llm\data\raw\cibrc"
WS = re.compile(r"\s+")
norm = lambda s: WS.sub("", (s or "")).casefold()

TARGETS = [
    ("fungicides_20260331.pdf", 83),
    ("insecticides_20260331.pdf", 1),
    ("fungicides_20260331.pdf", 1),
    ("bio_insecticides_20260331.pdf", 1),
    ("bio_fungicides_20260331.pdf", 1),
    ("fungicides_20260331.pdf", 38),
    ("insecticides_20260331.pdf", 6),
    ("bio_fungicides_20260331.pdf", 20),
]

for fn, pg in TARGETS:
    path = os.path.join(RAW, fn)
    with pdfplumber.open(path) as pdf:
        txt = pdf.pages[pg - 1].extract_text() or ""
    print("=" * 100)
    print(f"### {fn} p{pg}")
    print("--- RAW TEXT LAYER ---")
    print(txt)
    for flavour in ("lattice", "stream"):
        tl = camelot.read_pdf(path, pages=str(pg), flavor=flavour)
        print(f"--- {flavour}: {len(tl)} tables ---")
        cc = Counter()
        for i, t in enumerate(tl):
            print(f"  table[{i}] shape={t.df.shape}")
            for r, row in enumerate(t.df.values.tolist()):
                print("   r%-3d| %s" % (r, " || ".join(c.replace("\n", "\u21b5") for c in row)))
                for c in row:
                    cc.update(norm(c))
        lines = txt.splitlines()
        kept = [l for l in lines if not re.fullmatch(r"\s*\(?\d{1,4}\)?\s*", l or "")]
        tc = Counter(norm("".join(kept)))
        miss = tc - cc
        print(f"  MISSING {sum(miss.values())} chars: {dict(miss.most_common(40))}")
    print()
