import re, collections, camelot, pdfplumber
PDF = r"C:\Users\J\OneDrive\Desktop\Fine-Tuning project\agri-llm\data\raw\cibrc\insecticides_20260331.pdf"

def dump(flavor):
    ts = camelot.read_pdf(PDF, pages="55", flavor=flavor)
    print(f"### flavor={flavor}  n_tables={len(ts)}")
    allrows = []
    for i, t in enumerate(ts):
        print(f"# table[{i}] shape={t.df.shape} page={t.page} order={t.parsing_report.get('order')}")
        for r in range(t.df.shape[0]):
            cells = [str(t.df.iat[r, c]) for c in range(t.df.shape[1])]
            allrows.append(cells)
            print(f"r{r:<3}| " + " || ".join(c.replace("\n", "\u21b5") for c in cells))
    return ts, allrows

lat_t, lat = dump("lattice")
print()
str_t, strm = dump("stream")

def norm(rows):
    s = "".join(re.sub(r"\s+", "", c).lower() for row in rows for c in row)
    return s

L, S = norm(lat), norm(strm)
print("\nlattice normalised chars:", len(L))
print("stream  normalised chars:", len(S))
print("identical string?", L == S)
cl, cs = collections.Counter(L), collections.Counter(S)
print("same multiset?", cl == cs)
print("only in lattice:", "".join(sorted((cl - cs).elements())))
print("only in stream :", "".join(sorted((cs - cl).elements())))

# token-level comparison against raw text layer
with pdfplumber.open(PDF) as d:
    p = d.pages[54]
    words = [w["text"] for w in p.extract_words()]
print("\ntext-layer word count:", len(words))

def toks(rows):
    out = []
    for row in rows:
        for c in row:
            out += re.findall(r"\S+", c)
    return out

tl = toks(lat); ts_ = toks(strm)
print("lattice token count:", len(tl), " stream token count:", len(ts_))
wc = collections.Counter(words)
print("words missing from lattice:", (wc - collections.Counter(tl)))
print("words missing from stream :", (wc - collections.Counter(ts_)))
print("lattice tokens not in text layer:", (collections.Counter(tl) - wc))
print("stream tokens not in text layer:", (collections.Counter(ts_) - wc))
