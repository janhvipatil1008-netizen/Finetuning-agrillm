"""How much does LATTICE lose in absolute terms (regardless of stream)?
Same robust token-containment test. Plus a look at the three residual
non-p1 counterexample pages.
"""
import json, os, re
import pdfplumber, camelot

RAW = r"c:\Users\J\OneDrive\Desktop\Fine-Tuning project\agri-llm\data\raw\cibrc"
FILES = ["insecticides_20260331.pdf", "fungicides_20260331.pdf",
         "bio_insecticides_20260331.pdf", "bio_fungicides_20260331.pdf"]
WS = re.compile(r"\s+")
norm = lambda s: WS.sub("", (s or "")).casefold()

allrows = []
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
    for p in range(1, n + 1):
        lines = [l for l in texts[p].splitlines()
                 if l.strip() and not re.fullmatch(r"\s*\(?\d{1,4}\)?\s*", l)]
        toks = [t for l in lines for t in l.split() if norm(t)]
        for fl in ("lattice", "stream"):
            lost = [t for t in toks if norm(t) not in blob[fl].get(p, "")]
            allrows.append({"file": fn, "page": p, "flavour": fl,
                            "ntok": len(toks), "lost": lost,
                            "num": [t for t in lost if any(c.isdigit() for c in t)]})
    print(f"{fn} done", flush=True)

print("\n=== ABSOLUTE token loss (each flavour vs the page's own text layer) ===")
for fn in FILES:
    for fl in ("lattice", "stream"):
        rs = [r for r in allrows if r["file"] == fn and r["flavour"] == fl]
        tot = sum(r["ntok"] for r in rs)
        lost = sum(len(r["lost"]) for r in rs)
        num = sum(len(r["num"]) for r in rs)
        print(f"{fn:32s} {fl:8s} tokens={tot:6d} lost={lost:5d} "
              f"({100*lost/tot:5.2f}%) numeric_lost={num:4d} "
              f"pages_with_loss={sum(1 for r in rs if r['lost']):4d}/{len(rs)}")

print("\n=== worst LATTICE absolute-loss pages (top 12) ===")
lat = sorted([r for r in allrows if r["flavour"] == "lattice"],
             key=lambda r: -len(r["lost"]))[:12]
for r in lat:
    st = next(x for x in allrows if x["file"] == r["file"]
              and x["page"] == r["page"] and x["flavour"] == "stream")
    print(f"  {r['file']} p{r['page']}: lattice lost {len(r['lost'])} "
          f"({len(r['num'])} numeric) | stream lost {len(st['lost'])} "
          f"({len(st['num'])} numeric)")
    print(f"      lattice lost -> {r['lost'][:26]}")

print("\n=== residual non-p1 counterexamples, in context ===")
for fn, pg in [("fungicides_20260331.pdf", 38), ("insecticides_20260331.pdf", 6),
               ("bio_fungicides_20260331.pdf", 20)]:
    path = os.path.join(RAW, fn)
    with pdfplumber.open(path) as pdf:
        txt = pdf.pages[pg - 1].extract_text() or ""
    print(f"\n--- {fn} p{pg} text layer (last 8 lines) ---")
    for l in txt.splitlines()[-8:]:
        print("   ", repr(l))
