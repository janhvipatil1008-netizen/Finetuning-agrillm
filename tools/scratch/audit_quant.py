import os, collections
import camelot

RAW = r"c:/Users/J/OneDrive/Desktop/Fine-Tuning project/agri-llm/data/raw/cibrc"
FILES = ["insecticides_20260331.pdf", "fungicides_20260331.pdf",
         "bio_insecticides_20260331.pdf", "bio_fungicides_20260331.pdf"]

for fn in FILES:
    path = os.path.join(RAW, fn)
    tables = camelot.read_pdf(path, pages="2-end", flavor="lattice")
    n_tab = 0
    tab_multi_dose = 0          # tables where the 3rd-filled index varies across 6-value rows
    tab_stable = 0
    dose_idx_counts = []
    rows6 = 0
    rows_not6 = 0
    allblank_dropped_total = 0
    tab_zero_allblank = 0
    worst = []
    for t in tables:
        df = t.df
        nr, nc = df.shape
        n_tab += 1
        nonblank = [(df.iloc[:, c].str.strip() != "").sum() for c in range(nc)]
        nzero = sum(1 for v in nonblank if v == 0)
        allblank_dropped_total += nzero
        if nzero == 0:
            tab_zero_allblank += 1
        dose_idx = set()
        pat = collections.Counter()
        for r in range(nr):
            filled = [c for c in range(nc) if df.iat[r, c].strip() != ""]
            if len(filled) < 4:
                continue
            if len(filled) == 6:
                rows6 += 1
                dose_idx.add(filled[2])
                pat[tuple(filled)] += 1
            else:
                rows_not6 += 1
        if len(dose_idx) > 1:
            tab_multi_dose += 1
            worst.append((t.page, nc, sorted(dose_idx), len(pat)))
        elif len(dose_idx) == 1:
            tab_stable += 1
        dose_idx_counts.append(len(dose_idx))
    worst.sort(key=lambda x: -len(x[2]))
    print(f"=== {fn}")
    print(f"  lattice tables: {n_tab}")
    print(f"  tables with >1 distinct dose(3rd-filled) index: {tab_multi_dose}")
    print(f"  tables with exactly 1 distinct dose index      : {tab_stable}")
    print(f"  data rows with exactly 6 filled cells: {rows6}; with !=6 (>=4 filled): {rows_not6}")
    print(f"  total all-blank columns available to drop across all tables: {allblank_dropped_total}")
    print(f"  tables where 0 columns are all-blank (drop is a no-op): {tab_zero_allblank}/{n_tab}")
    print(f"  worst 12 pages (page, ncols, distinct dose idx, distinct filled-patterns):")
    for w in worst[:12]:
        print(f"    p{w[0]:<4} nc={w[1]:<3} dose_idx={w[2]} patterns={w[3]}")
    print()
