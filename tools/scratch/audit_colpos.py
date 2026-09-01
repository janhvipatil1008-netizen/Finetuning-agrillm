import sys, os, json
import camelot

RAW = r"c:/Users/J/OneDrive/Desktop/Fine-Tuning project/agri-llm/data/raw/cibrc"

TARGETS = [
    ("insecticides_20260331.pdf", [87, 89, 84, 24, 58, 73]),
    ("fungicides_20260331.pdf", [76, 81]),
]

def show(cell):
    return cell.replace("\n", "\u21b5")

for fn, pages in TARGETS:
    path = os.path.join(RAW, fn)
    for p in pages:
        tables = camelot.read_pdf(path, pages=str(p), flavor="lattice")
        print("=" * 100)
        print(f"### {fn} p{p} lattice -> {len(tables)} table(s)")
        for ti, t in enumerate(tables):
            df = t.df
            nr, nc = df.shape
            print(f"-- table[{ti}] shape=({nr},{nc}) page={t.page}")
            # per-column non-blank counts
            nonblank = [(df.iloc[:, c].str.strip() != "").sum() for c in range(nc)]
            print(f"   nonblank-per-col: {nonblank}")
            for r in range(nr):
                row = [df.iat[r, c].strip() for c in range(nc)]
                filled = [(c, show(v)) for c, v in enumerate(row) if v != ""]
                idxs = [c for c, _ in filled]
                print(f"   r{r:<3} idx={idxs} :: " + " | ".join(f"[{c}]{v}" for c, v in filled))
        sys.stdout.flush()
