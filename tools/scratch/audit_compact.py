import os, re, collections
import camelot

RAW = r"c:/Users/J/OneDrive/Desktop/Fine-Tuning project/agri-llm/data/raw/cibrc"
FILES = ["insecticides_20260331.pdf", "fungicides_20260331.pdf",
         "bio_insecticides_20260331.pdf", "bio_fungicides_20260331.pdf"]

# a dose-ish cell: mostly digits/operators, few letters
def doselike(s):
    s = s.replace("\n", " ").strip()
    if s in ("-", "--", "---", "NA", "na", "N.A."):
        return True
    if not re.search(r"\d", s):
        return False
    letters = sum(ch.isalpha() for ch in s)
    digits = sum(ch.isdigit() for ch in s)
    return digits >= letters

def show(s):
    return s.replace("\n", "\u21b5")

for fn in FILES:
    path = os.path.join(RAW, fn)
    tables = camelot.read_pdf(path, pages="2-end", flavor="lattice")
    tot = 0
    n6 = 0
    bad_compact = []
    n_not6 = 0
    # also: raw positional row[2] correctness
    raw2_ok = 0
    raw2_blank = 0
    raw2_wrong = 0
    for t in tables:
        df = t.df
        nr, nc = df.shape
        for r in range(nr):
            cells = [df.iat[r, c].strip() for c in range(nc)]
            filled = [c for c in range(nc) if cells[c] != ""]
            if len(filled) < 4:
                continue
            tot += 1
            # ---- raw positional index 2
            if nc > 2:
                v2 = cells[2]
                if v2 == "":
                    raw2_blank += 1
                elif doselike(v2):
                    raw2_ok += 1
                else:
                    raw2_wrong += 1
            # ---- compaction
            if len(filled) == 6:
                n6 += 1
                c2 = cells[filled[2]]
                if not doselike(c2):
                    bad_compact.append((t.page, r, len(filled), show(c2)))
            else:
                n_not6 += 1
    print(f"=== {fn}")
    print(f"  candidate data rows (>=4 filled): {tot}")
    print(f"  RAW positional row[2]:  dose-like {raw2_ok}  BLANK {raw2_blank}  NON-DOSE TEXT {raw2_wrong}"
          f"   -> wrong/blank = {raw2_blank + raw2_wrong}/{tot} = {(raw2_blank+raw2_wrong)/max(tot,1)*100:.1f}%")
    print(f"  COMPACTED (drop blanks per row, read index 2): rows with exactly 6 filled {n6}; "
          f"rows with !=6 filled (compaction undefined) {n_not6} = {n_not6/max(tot,1)*100:.1f}%")
    print(f"  of the 6-filled rows, compacted index2 is NOT dose-like: {len(bad_compact)}")
    for b in bad_compact[:10]:
        print(f"     p{b[0]} r{b[1]} filled={b[2]} compacted[2]={b[3]!r}")
    print()
