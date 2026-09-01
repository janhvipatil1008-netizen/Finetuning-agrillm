"""Independent re-derivation: what exactly are the 36 chars lattice misses on
insecticides p2?  No trust in reports/phase2_inspect.md.
"""
import re
from collections import Counter

import camelot
import pdfplumber

PDF = (r"c:\Users\J\OneDrive\Desktop\Fine-Tuning project\agri-llm"
       r"\data\raw\cibrc\insecticides_20260331.pdf")
PG = 2


def norm(s):
    return re.sub(r"\s+", "", str(s or "")).lower()


# ---------- 1. raw text layer ----------
with pdfplumber.open(PDF) as pdf:
    page = pdf.pages[PG - 1]
    raw = page.extract_text() or ""
    pw, ph = page.width, page.height
    words = page.extract_words(use_text_flow=False)

print("=" * 78)
print("RAW TEXT LAYER, insecticides p2  (page %.1f x %.1f)" % (pw, ph))
print("=" * 78)
print(raw)
print("-" * 78)
ref = Counter(norm(raw))
print("raw normalised chars:", sum(ref.values()))

# discount the bare page-number footer exactly as the report script does
for ch in norm(str(PG)):
    if ref[ch]:
        ref[ch] -= 1
print("after discounting page-number '2':", sum(ref.values()))

# ---------- 2. lattice cells ----------
tables = camelot.read_pdf(PDF, pages=str(PG), flavor="lattice")
got = Counter()
ncells = 0
for t in tables:
    for _, row in t.df.iterrows():
        for cell in row.tolist():
            got.update(norm(cell))
            ncells += 1
print("lattice tables:", len(tables),
      "shapes:", [t.df.shape for t in tables])
print("lattice normalised chars:", sum(got.values()))

missing = ref - got
extra = got - ref
print()
print("MISSING count  =", sum(missing.values()))
print("EXTRA   count  =", sum(extra.values()))
print("missing multiset (sorted):", "".join(sorted(missing.elements())))
print("missing Counter:", dict(sorted(missing.items())))
print("extra   multiset (sorted):", "".join(sorted(extra.elements())))

# ---------- 3. the hypothesis under audit ----------
HYPO = "Approved Uses of Registered Insecticides"
h = Counter(norm(HYPO))
print()
print("=" * 78)
print("HYPOTHESIS TEST")
print("=" * 78)
print("heading      :", repr(HYPO))
print("normalised   :", norm(HYPO), "len =", len(norm(HYPO)))
print("heading Counter:", dict(sorted(h.items())))
print("EQUAL to missing multiset? ->", h == missing)
print("missing - heading =", dict(sorted((missing - h).items())),
      "total", sum((missing - h).values()))
print("heading - missing =", dict(sorted((h - missing).items())),
      "total", sum((h - missing).values()))

# ---------- 4. is that heading string even present in the raw layer? ----------
flat = norm(raw)
print()
print("is 'approvedusesofregisteredinsecticides' a substring of raw layer? ->",
      norm(HYPO) in flat)
for probe in ["approved", "registered", "agriculturaluse", "insecticides"]:
    print("  probe %-16s occurrences in raw layer: %d"
          % (probe, flat.count(probe)))

# ---------- 5. reconstruct what the missing text ACTUALLY is ----------
# subtract every lattice cell string from the raw text word by word.
lat_words = Counter()
for t in tables:
    for _, row in t.df.iterrows():
        for cell in row.tolist():
            for w in re.split(r"\s+", str(cell)):
                if w:
                    lat_words[norm(w)] += 1

raw_words = Counter()
for w in words:
    raw_words[norm(w["text"])] += 1

miss_words = raw_words - lat_words
print()
print("=" * 78)
print("WORD-LEVEL: words in raw text layer that lattice never returned")
print("=" * 78)
for w, c in sorted(miss_words.items()):
    print("   %-30s x%d  (chars %d)" % (repr(w), c, len(w) * c))
print("total missing-word chars:", sum(len(w) * c for w, c in miss_words.items()))

# with coordinates, so we can test inside/outside bbox
print()
print("positions of those words on the page (x0,top,x1,bottom):")
need = Counter(miss_words)
for w in words:
    k = norm(w["text"])
    if need.get(k):
        need[k] -= 1
        print("   %-28s x0=%7.2f x1=%7.2f top=%7.2f bottom=%7.2f"
              % (repr(w["text"]), w["x0"], w["x1"], w["top"], w["bottom"]))

# ---------- 6. camelot's detected table bbox for p2 ----------
print()
print("=" * 78)
print("CAMELOT lattice bbox(es) for p2   (PDF coords, y from bottom)")
print("=" * 78)
for i, t in enumerate(tables):
    pr = t.parsing_report
    print("table[%d] report=%s" % (i, pr))
    print("   _bbox =", getattr(t, "_bbox", None))
    print("   cols  =", t.cols[:3], "...")
    print("   rows  =", t.rows[:3], "...")
    xs = [c[0] for c in t.cols] + [c[1] for c in t.cols]
    ys = [r[0] for r in t.rows] + [r[1] for r in t.rows]
    print("   derived bbox x:[%.2f,%.2f] y:[%.2f,%.2f]"
          % (min(xs), max(xs), min(ys), max(ys)))
