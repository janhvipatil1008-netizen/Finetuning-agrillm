"""Corpus-wide bold-fraction probe: is 'row is fully bold' a clean separator
for column-header rows vs data rows?"""
import sys
import camelot
import pdfplumber

FILES = ['insecticides_20260331.pdf', 'fungicides_20260331.pdf',
         'bio_insecticides_20260331.pdf', 'bio_fungicides_20260331.pdf']


def row_bold_fraction(pg, table, r_idx, height):
    cells = table.cells[r_idx]
    y_lo = min(c.y1 for c in cells)
    y_hi = max(c.y2 for c in cells)
    x_lo = min(c.x1 for c in cells)
    x_hi = max(c.x2 for c in cells)
    top_lo, top_hi = height - y_hi, height - y_lo
    chars = [c for c in pg.chars
             if top_lo - 1 <= c['top'] <= top_hi + 1
             and x_lo - 1 <= c['x0'] <= x_hi + 1
             and c['text'].strip()]
    if not chars:
        return None, 0, ''
    bold = sum(1 for c in chars if 'Bold' in c['fontname'])
    return bold / len(chars), len(chars), ''.join(c['text'] for c in chars)


def main():
    hist = {}
    rows_out = []
    for fn in FILES:
        path = 'data/raw/cibrc/' + fn
        with pdfplumber.open(path) as pdf:
            n = len(pdf.pages)
            tables = camelot.read_pdf(path, pages=f'1-{n}', flavor='lattice')
            for t in tables:
                pg = pdf.pages[int(t.page) - 1]
                H = float(pg.height)
                for r_idx in range(len(t.cells)):
                    frac, nchars, txt = row_bold_fraction(pg, t, r_idx, H)
                    if frac is None:
                        continue
                    nseg = len([s for s in
                                [' '.join(c.text.split()) for c in t.cells[r_idx]]
                                if s])
                    bucket = round(frac, 1)
                    hist[bucket] = hist.get(bucket, 0) + 1
                    rows_out.append((fn, int(t.page), r_idx, frac, nseg, txt[:90]))
        print('done', fn, file=sys.stderr)

    print('=== bold-fraction histogram (all rows, all files) ===')
    for k in sorted(hist):
        print(f'  {k:.1f}: {hist[k]}')

    fully = [r for r in rows_out if r[3] >= 0.9]
    multi = [r for r in fully if r[4] >= 2]
    single = [r for r in fully if r[4] < 2]
    print()
    print(f'rows >=0.9 bold: {len(fully)}   of which multi-segment: {len(multi)}, single-segment: {len(single)}')
    print()
    print('=== MULTI-SEGMENT BOLD ROWS (candidate column_header) ===')
    for r in multi:
        print(f'  {r[0][:22]:<22} p{r[1]:<4} r{r[2]:<3} frac={r[3]:.2f} nseg={r[4]} :: {r[5]}')

    mid = [r for r in rows_out if 0.15 < r[3] < 0.9]
    print()
    print(f'=== MIXED-BOLD ROWS (0.15-0.9), manual review: {len(mid)} ===')
    for r in mid[:40]:
        print(f'  {r[0][:22]:<22} p{r[1]:<4} r{r[2]:<3} frac={r[3]:.2f} nseg={r[4]} :: {r[5]}')


main()
