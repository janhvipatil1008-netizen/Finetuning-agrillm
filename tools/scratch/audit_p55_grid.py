import pdfplumber, collections
PDF = r"C:\Users\J\OneDrive\Desktop\Fine-Tuning project\agri-llm\data\raw\cibrc\insecticides_20260331.pdf"
with pdfplumber.open(PDF) as d:
    p = d.pages[54]
    H = p.height
    # horizontal edges = candidate row separators
    hz = [e for e in p.edges if e["orientation"] == "h"]
    vt = [e for e in p.edges if e["orientation"] == "v"]
    print("h edges:", len(hz), "v edges:", len(vt))
    ytol = 2
    ys = sorted({round(e["top"], 1) for e in hz})
    merged = []
    for y in ys:
        if merged and y - merged[-1][-1] <= ytol:
            merged[-1].append(y)
        else:
            merged.append([y])
    rowlines = [sum(g) / len(g) for g in merged]
    print("distinct horizontal rule y-positions (merged, tol=2):", len(rowlines))
    for y in rowlines:
        # widest span at this y
        segs = [e for e in hz if abs(e["top"] - y) <= ytol]
        x0 = min(s["x0"] for s in segs); x1 = max(s["x1"] for s in segs)
        print(f"  y={y:7.2f} nsegs={len(segs):3d} x={x0:6.1f}-{x1:6.1f} width={x1-x0:6.1f}")
    print("=> implied full-width row bands:", len(rowlines) - 1)
    xs = sorted({round(e["x0"], 1) for e in vt})
    m2 = []
    for x in xs:
        if m2 and x - m2[-1][-1] <= ytol:
            m2[-1].append(x)
        else:
            m2.append([x])
    print("distinct vertical rule x-positions:", len(m2), [round(sum(g)/len(g),1) for g in m2])
    # words per grid band
    words = p.extract_words()
    bands = collections.defaultdict(list)
    for w in words:
        c = (w["top"] + w["bottom"]) / 2
        idx = None
        for i in range(len(rowlines) - 1):
            if rowlines[i] <= c <= rowlines[i + 1]:
                idx = i; break
        bands[idx].append(w["text"])
    print("\nwords grouped into ruled bands:")
    for i in sorted(bands, key=lambda z: (z is None, z)):
        lo = rowlines[i] if i is not None else -1
        hi = rowlines[i+1] if i is not None else -1
        print(f" band {i} y {lo:.1f}-{hi:.1f}: {' '.join(bands[i])[:150]}")
