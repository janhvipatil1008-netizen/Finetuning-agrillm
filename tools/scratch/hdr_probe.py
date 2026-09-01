import csv, re, sys

FILES = ['insecticides_20260331.pdf','fungicides_20260331.pdf',
         'bio_insecticides_20260331.pdf','bio_fungicides_20260331.pdf']

VOCAB = re.compile(
    r'crop|pest|insect|disease|organism|dosage|dose|formulation|dilution|'
    r'waiting|period|phi\b|method|application|usage|habitat|location|place|'
    r'surface|technical|target|requirement|interval|exposure|concentration|'
    r'quantity|instruction|deposit|volume|infestation|breeding|regime|'
    r'name of|common name|type of|how to apply|manner of|spray solution|'
    r'spray fluid|water\s*\(|water volume|a\.?\s*i\.?\s*[.(/]|pheromone|'
    r'recommended\s*area', re.I)

# a segment carrying a real measured value is data, not a label
NUMERIC_VALUE = re.compile(r'(?<![a-z0-9])\d')

def norm(s): return re.sub(r'\s+', ' ', str(s or '')).strip()

def label_like(seg):
    n = norm(seg)
    if not n or n == '-':
        return None            # neutral: neither label nor data
    if len(n) > 60:
        return False
    if NUMERIC_VALUE.search(n):
        # allow unit-bearing labels like "a.i. (gm)", "Dosage/m2", "PHI (Days)"
        if not re.search(r'\((g|gm|ml|kg|l|lit|liter|litre|days?|ha|m2|m3|'
                         r'g/ml|gm/ml|g/ha|ml/ha|kg\.|ltr\.?|liters?)\W*\)|'
                         r'/\s*(m2|m3|ha|sq|1000)', n, re.I):
            return False
    return bool(VOCAB.search(n))

def classify(raw_row_text):
    segs = [s for s in raw_row_text.split(' || ') if norm(s)]
    verdicts = [label_like(s) for s in segs]
    real = [v for v in verdicts if v is not None]
    if len(real) < 2:
        return False, 0, len(real)
    n_lbl = sum(1 for v in real if v)
    return (n_lbl >= 2 and n_lbl / len(real) >= 0.6), n_lbl, len(real)

if __name__ == '__main__':
    flagged, near = [], []
    for fn in FILES:
        with open('data/interim/' + fn.replace('.pdf', '_raw.csv'), encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            hit, n_lbl, n_real = classify(r['raw_row_text'])
            rec = (fn, r['source_page'], r['source_row_index'], r['section'],
                   r['assignment_kind'], f'{n_lbl}/{n_real}', r['raw_row_text'][:105])
            if hit:
                flagged.append(rec)
            elif n_lbl >= 1 and n_real >= 2 and n_lbl / n_real >= 0.4:
                near.append(rec)
    print('FLAGGED:', len(flagged))
    for f in flagged: print('  ', f)
    print()
    print('NEAR-MISS (manual review):', len(near))
    for f in near: print('  ', f)
