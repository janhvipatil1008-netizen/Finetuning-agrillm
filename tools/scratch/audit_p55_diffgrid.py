import pdfplumber, camelot, re
PDF = r"C:\Users\J\OneDrive\Desktop\Fine-Tuning project\agri-llm\data\raw\cibrc\insecticides_20260331.pdf"
ROWY = [72.50,102.60,132.50,156.65,180.85,216.35,252.05,277.85,300.05,326.20,
        347.35,368.35,383.45,419.35,455.25,476.55,535.25,559.00,582.55,734.50]
COLX = [36.2,112.8,262.5,353.0,422.5,507.0,590.1]

with pdfplumber.open(PDF) as d:
    p = d.pages[54]
    words = p.extract_words()

grid = [["" for _ in range(6)] for _ in range(19)]
unplaced = []
for w in words:
    cy = (w["top"] + w["bottom"]) / 2
    cx = (w["x0"] + w["x1"]) / 2
    r = c = None
    for i in range(19):
        if ROWY[i] <= cy <= ROWY[i+1]: r = i; break
    for j in range(6):
        if COLX[j] <= cx <= COLX[j+1]: c = j; break
    if r is None or c is None:
        unplaced.append((w["text"], round(cx,1), round(cy,1))); continue
    grid[r][c] = (grid[r][c] + " " + w["text"]).strip()

print("unplaced words (outside grid):", unplaced)

t = camelot.read_pdf(PDF, pages="55", flavor="lattice")[0].df
norm = lambda s: re.sub(r"\s+", " ", str(s)).strip()
diffs = 0
for r in range(19):
    for c in range(6):
        a, b = norm(grid[r][c]), norm(t.iat[r, c])
        if a != b:
            diffs += 1
            print(f"DIFF r{r} c{c}:\n   geometry: {a!r}\n   camelot : {b!r}")
print("total differing cells:", diffs, "of 114")

# per-claim reconciliation: data rows = rows with >=4 populated cells
claims = [r for r in range(19) if sum(1 for c in range(6) if norm(grid[r][c])) >= 4]
print("\ngeometry data(claim) rows:", claims, "count:", len(claims))
for r in claims:
    print(f"  L{r}: " + " | ".join(norm(grid[r][c]) for c in range(6))[:160])
hdrs = [r for r in range(19) if r not in claims]
print("non-claim rows (headings/notes/subheader):", hdrs, "count:", len(hdrs))
for r in hdrs:
    print(f"  L{r}: " + " | ".join(norm(grid[r][c]) for c in range(6))[:110])
