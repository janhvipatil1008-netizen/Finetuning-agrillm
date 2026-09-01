import sys, pdfplumber
PDF = r"C:\Users\J\OneDrive\Desktop\Fine-Tuning project\agri-llm\data\raw\cibrc\insecticides_20260331.pdf"
with pdfplumber.open(PDF) as d:
    print("TOTAL PAGES:", len(d.pages))
    p = d.pages[54]  # 0-indexed page 55
    print("PAGE bbox:", p.width, p.height)
    print("=== pdfplumber extract_text (layout=True) ===")
    t = p.extract_text(layout=True)
    print(t)
    print("=== END ===")
    print("=== words with x0 sorted by top ===")
    ws = p.extract_words(use_text_flow=False, keep_blank_chars=False)
    ws.sort(key=lambda w: (round(w['top'],1), w['x0']))
    # group into lines by top
    lines = []
    for w in ws:
        if lines and abs(w['top'] - lines[-1][0]) < 3:
            lines[-1][1].append(w)
        else:
            lines.append([w['top'], [w]])
    for top, wl in lines:
        print(f"{top:7.1f} | " + " ".join(f"{w['text']}@{w['x0']:.0f}" for w in wl))
    print("NUM TEXT LINES:", len(lines))
    print("=== rects/lines count (for lattice) ===")
    print("lines:", len(p.lines), "rects:", len(p.rects), "edges:", len(p.edges), "curves:", len(p.curves))
