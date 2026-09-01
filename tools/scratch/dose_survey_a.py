"""Phase A survey: which dose surface patterns actually occur.

Read-only. Classifies every DISTINCT dose-bearing cell string from the four
in-scope raw CSVs into a named surface pattern. No parsing, no Dose objects,
no schema import. The pattern names here are the vocabulary Phase B will map
onto Basis values.

Structure: a few explicit pre-checks (prose, unsupported unit, compound,
multi-basis) run before the ordered regex table, because those decisions are
about CONTENT, not about string shape, and burying them in regex precedence
made it impossible to say why a string landed where it did.
"""
import csv, json, re, collections

FILES = ["insecticides", "fungicides", "bio_insecticides", "bio_fungicides"]
DOSE_COLS = ["dose_ai", "dose_formulation", "dilution_water"]
DATA_KINDS = {"ordinal_6", "fallback_subset"}


def sp(word):
    """Word regex tolerant of OCR-injected spaces: 'seed' also matches 'see d'."""
    return r"\s*".join(re.escape(c) for c in word)


N = r"\d+(?:\s?\d+)*(?:\s?\.\s?\d+(?:\s?\d+)*)?"   # tolerates '1 .00', '500-1 000'
D = r"(?:-+|–|—|to)"
RNG = rf"{N}\s*{D}\s*{N}"
G = r"(?:g|gm|gms|gram|grams|gs)"
ML = r"(?:ml|mls)"
KG = r"(?:kg|kgs)"
LT = rf"(?:{sp('litres')}|{sp('litre')}|{sp('liters')}|{sp('liter')}|lts?|ltrs?|lit|l)"
MV = rf"(?:{G}|{KG}|{ML}|{LT})\.?"
AI = r"(?:\(?\s*a\.?\s?i\.?\s*\)?|formulation|form\.?)?"
UNITBLOB = rf"(?:\s*{AI}\s*{MV}\s*{AI}|\s*{AI})"   # unit and 'a.i.' in either order
FOOT = r"[*^]*"
SEED = (rf"(?:{sp('seedlings')}|{sp('seedling')}|{sp('seeds')}|{sp('seed')}|"
        rf"{sp('tubers')}|{sp('tuber')})")
WATER = rf"(?:{sp('water')}|{sp('wtr')})"

# ---------------------------------------------------------------- pre-checks

# Leading prose. These strings very often contain a '%' that is the PRODUCT
# STRENGTH ("Trichoderma viride 1.0% WP"), not a dose concentration. Reading
# that '%' as a dose is the most dangerous misparse available in this corpus.
PROSE_LEAD = re.compile(
    r"^(?:seed(?:ling)?s?[\s-]*(?:root\s*dip\s*)?treatment|soil[\s-]*treatment|"
    r"foliar\s*spr[ay]y?|spray|mix|dissolve|use|apply|available|it\s+is|"
    r"seeds?\s+are|broadcas\w*|braoad\w*|air\s*tight|sufficient|this\s+is|"
    r"as\s+required|as\s+per|at\s+pod|based\s+on|depend\w*|direct|disease|from\s+square|"
    r"leaf\s*spot|slurry|one\s+tablet|dosage|not\s+required|seed\s+dresser|"
    r"whorl|are\s+dried|splash|treatment|water$|seed$)\b", re.I)

# Units the frozen schema's Unit enum cannot express.
UNSUPPORTED = re.compile(
    r"(?:\d\s*mg\b|\bmg\s*(?:/|per)|\bppm\b|\btablets?\b|\bpouch(?:es)?\b|"
    r"\bburrows?\b|\bspots?\b|\bm3\b|\bmeter3\b|\bcft\b|\bdripper\b|\bbait\b|"
    r"\bdust\b|\bton(?:ne)?s?\b|\bsand\b|\bmanure\b|\bfertili[sz]er\b|"
    r"\binjection\b|\blinseed\b|slurry\s*volume)", re.I)

# A waiting-period value that landed in a dose column. Anchored: the WHOLE
# cell must be a time expression. A prose method that merely mentions "days"
# is prose, not a stray PHI.
TIME_VALUE = re.compile(
    r"^(?:\d[\d\s.–-]*(?:to)?\s*\d*\s*(?:hrs?|hours?|days?)\.?\s*"
    r"(?:waiting\s*period\s*)?)+$", re.I)

# An active-ingredient name fragment that landed in a dose column.
AI_NAME = re.compile(r"^[A-Z][a-z]{4,}[a-z\-]*\s*[-–]?\s*\d[\d.]*\s*"
                     r"(?:%\s*\(?w/[wv]\)?)?\s*(?:&|\+)")

# '+' joining two numbers = ready-mix product, components stated separately.
NUMTOK = re.compile(r"\d+(?:\s?\.\s?\d+)?")


def is_compound(t):
    """A '+' inside a cell that also holds two or more numbers means the label
    states a ready-mix product's components separately."""
    return "+" in t and len(NUMTOK.findall(t)) >= 2

# Basis anchors, used to detect a cell holding more than one dose expression.
ANCHORS = [
    ("ha",    re.compile(r"(?:/|per)\s*(?:ha\b|hect\w*|acre)", re.I)),
    ("seed",  re.compile(rf"(?:/|per|for)\s*(?:{N}\s*)?{KG}\.?\s*(?:of\s*)?"
                         rf"(?:\w+\s+)*{SEED}", re.I)),
    ("water", re.compile(rf"(?:/|per|in)\s*(?:{N}\s*)?{LT}\.?\s*(?:of\s*)?{WATER}?",
                         re.I)),
    ("tree",  re.compile(rf"(?:/|per)\s*(?:{N}\s*)?{sp('tree')}", re.I)),
    ("plant", re.compile(rf"(?:/|per)\s*(?:{N}\s*)?"
                         rf"(?:{sp('plant')}|{sp('sucker')}|{sp('vine')})", re.I)),
    ("sqm",   re.compile(r"(?:/|per)\s*(?:\d+\s*)?(?:sq\.?\s*m|m2)", re.I)),
]

PCT = re.compile(r"\d\s*%")

# '250 (2 application) or 500 (Single application)',
# '500 (via Knapsack sprayer) 20 (via Drone application)' -- one cell,
# two doses selected by application method. Not a range, not one dose.
ALTERNATIVES = re.compile(
    r"\d[^\d]{0,40}\((?:[^)]*(?:application|spray|knap|drone|dry|soaked|single|foliar|drench)[^)]*)\)[^\d]{0,20}(?:or\s*)?\d", re.I)


def anchor_kinds(t):
    return {k for k, rx in ANCHORS if rx.search(t)}


# ------------------------------------------------- ordered shape patterns

PATTERNS = [
    ("NULL_MARKER",
     r"^(?:-+|–+|nil|n\.?\s?/?\s?a\.?|not\s*applicable|not\s*app\w*)\.?$"),

    # ---------- percentage family -> concentration_pct ----------
    ("PCT_SINGLE",
     rf"^{N}\s*%{FOOT}\s*(?:w/[wv]|sol(?:ution|\.)?|conc\.?)?\.?$"),
    ("PCT_RANGE",
     rf"^{RNG}\s*%{FOOT}\s*(?:sol(?:ution|\.)?)?\.?$"),
    ("PCT_RANGE_BOTH",
     rf"^{N}\s*%\s*{D}?\s*{N}\s*%{FOOT}\s*(?:sol(?:ution|\.)?)?\.?$"),
    # '0.10% or 100 g/100 lit water', '0.005% (5g/100 lit)'  -- % stated first
    ("PCT_WITH_EQUIV",
     rf"^\(?{N}(?:\s*{D}\s*{N})?\s*%\)?(?:\s*{D}\s*{N}\s*%)?\s*(?:or|:|\()?\s*\(?{N}.*$"),
    # '2000 g or 0.4%', '25 (0.25%)'  -- mass equivalent stated first
    ("PCT_EQUIV_FIRST",
     rf"^{N}(?:\s*{D}\s*{N})?{UNITBLOB}\s*(?:/\s*\w+\s*)?(?:or|\()\s*\(?{N}\s*%.*$"),

    # ---------- per-litre dilution -> per_litre_water ----------
    ("PER_N_LITRE",
     rf"^{N}(?:\s*{D}\s*{N})?{UNITBLOB}\s*(?:/|per|in|for)\s*{N}\s*"
     rf"{LT}\.?\s*(?:of\s*)?(?:{WATER})?\.?\s*(?:\(.*\))?$"),
    ("PER_LITRE",
     rf"^{N}(?:\s*{D}\s*{N})?{UNITBLOB}\s*(?:/|per)\s*"
     rf"{LT}\.?\s*(?:of\s*)?(?:{WATER})?\.?$"),
    ("PER_LITRE_BARE",              # '10 lit. water' appearing in a dilution cell
     rf"^{N}\s*{LT}\.?\s*{WATER}\.?$"),

    # ---------- per kg seed -> per_kg_seed ----------
    ("PER_N_KG_SEED",
     rf"^{N}(?:\s*{D}\s*{N})?{UNITBLOB}\s*(?:/|per|for)\s*{N}\s*"
     rf"{KG}\.?\s*(?:of\s*)?(?:\w+\s+)*(?:{SEED})?\.?$"),
    ("PER_KG_SEED",
     rf"^{N}(?:\s*{D}\s*{N})?{UNITBLOB}\s*(?:/|p\s*er)\s*"
     rf"{KG}\.?\s*(?:of\s*)?(?:{SEED})?\.?$"),

    # ---------- per tree / plant / sq m ----------
    ("PER_TREE",
     rf"^{N}(?:\s*{D}\s*{N})?{UNITBLOB}\s*(?:{WATER})?\s*(?:/|per)\s*"
     rf"(?:{N}\s*)?{sp('tree')}s?\.?$"),
    ("PER_PLANT",
     rf"^{N}(?:\s*{D}\s*{N})?{UNITBLOB}\s*(?:/|per)\s*(?:{N}\s*)?"
     rf"(?:{sp('plant')}s?|{sp('sucker')}s?|{sp('vine')}s?|bushe?s?|hills?)\.?$"),
    ("PER_N_SQ_M",
     rf"^{N}(?:\s*{D}\s*{N})?{UNITBLOB}\s*(?:/|per)\s*{N}\s*"
     rf"(?:sq\.?\s*m(?:tr|eter|etre)?s?|m2)\.?$"),
    ("PER_SQ_M",
     rf"^{N}(?:\s*{D}\s*{N})?{UNITBLOB}\s*(?:/|per)\s*"
     rf"(?:sq\.?\s*m(?:tr|eter|etre)?s?|m2)\.?$"),

    # ---------- explicit area basis ----------
    ("PER_HA_EXPLICIT",
     rf"^{N}(?:\s*{D}\s*{N})?{UNITBLOB}\s*(?:/|per)\s*"
     rf"(?:ha|hect\w*|acre)\.?\s*\.?$"),

    # ---------- plain numeric, unit implied by the column header ----------
    ("BARE_NUMBER",  rf"^\(?{N}{FOOT}\)?\.?$"),
    ("BARE_RANGE",   rf"^{RNG}{FOOT}\.?$"),
    ("NUM_UNIT",     rf"^{N}\s*{MV}\s*(?:{MV})?{FOOT}\.?$"),
    ("RANGE_UNIT",   rf"^{N}\s*(?:{MV})?\s*{D}\s*{N}\s*{MV}{FOOT}\.?$"),

    # ---------- numeric carrying a prose / method qualifier ----------
    ("NUM_WITH_METHOD",
     rf"^(?:{RNG}|{N})\s*(?:{MV})?\s*(?:{AI})?\s*"
     rf"(?:\(?\s*(?:/|per)\s*(?:ha|hect\w*|acre|{KG}\.?\s*(?:of\s*)?(?:{SEED})?|"
     rf"{LT}\.?\s*(?:{WATER})?|{sp('tree')}s?)\s*\)?)?\s*[\(,;./]?\s*[A-Za-z(].*$"),

    # several independent numbers, no operator: columns collapsed into one cell
    ("DEFECT_COLUMN_COLLAPSE",
     rf"^(?:{N}|{RNG})\s*/\s*{N}\s*respectively\.?$"),
    ("DEFECT_COLUMN_COLLAPSE",
     rf"^(?:{N}|{RNG})\s*(?:%|{MV})?(?:\s+(?:{N}|{RNG})\s*(?:%|{MV})?){{1,3}}\.?$"),
]

COMPILED = [(n, re.compile(p, re.I | re.S)) for n, p in PATTERNS]

# ---------- compound sub-shapes, used only once COMPOUND has already fired ----
COMPOUND_SHAPES = [
    ("COMPOUND_RANGE",
     rf"^\(?{N}\s*(?:{MV})?(?:\s*\+\s*{N}\s*(?:{MV})?)+\)?\s*(?:{MV})?\s*{AI}\s*"
     rf"(?:/\s*\w+\s*)?{D}\s*\(?{N}\s*(?:{MV})?(?:\s*\+\s*{N}\s*(?:{MV})?)+\)?.*$"),
    ("COMPOUND_TOTAL_BREAKDOWN",
     rf"^\(?{N}\)?{FOOT}\s*(?:{MV})?\s*{AI}\s*(?:/\s*\w+\s*)?[\(=]\s*{N}"
     rf"(?:\s*\+\s*{N})+\s*\)?\s*(?:{MV})?\.?$"),
    ("COMPOUND_BREAKDOWN_TOTAL",
     rf"^\(?{N}(?:\s*\+\s*{N})+\)?\s*[\(=]\s*{N}\s*\)?\s*(?:{MV})?\.?$"),
    ("COMPOUND_RANGE_SUM",
     rf"^{RNG}\s*(?:{MV})?(?:\s*\+\s*{RNG}\s*(?:{MV})?)+\.?$"),
    ("COMPOUND_SUM",
     rf"^\(?{N}\s*(?:{MV})?(?:\s*\+\s*{N}\s*(?:{MV})?)+\)?\s*(?:\(?{MV}\)?)?\s*"
     rf"{AI}\s*(?:\(?\s*(?:/|per)\s*[\w\s/.]*\)?)?\.?$"),
]
COMPOUND_COMPILED = [(n, re.compile(p, re.I | re.S)) for n, p in COMPOUND_SHAPES]

NUMERIC = {
    "PCT_SINGLE", "PCT_RANGE", "PCT_RANGE_BOTH", "PCT_WITH_EQUIV", "PCT_EQUIV_FIRST",
    "PER_N_LITRE", "PER_LITRE", "PER_LITRE_BARE", "PER_N_KG_SEED", "PER_KG_SEED",
    "PER_TREE", "PER_PLANT", "PER_SQ_M", "PER_N_SQ_M", "PER_HA_EXPLICIT",
    "BARE_NUMBER", "BARE_RANGE", "NUM_UNIT", "RANGE_UNIT", "NUM_WITH_METHOD",
}
FREE_TEXT = {
    "NULL_MARKER", "PROSE_METHOD", "PROSE_NO_NUMBER", "UNSUPPORTED_UNIT",
    "COMPOUND_RANGE", "COMPOUND_TOTAL_BREAKDOWN", "COMPOUND_BREAKDOWN_TOTAL",
    "COMPOUND_SUM", "COMPOUND_RANGE_SUM", "COMPOUND_OTHER",
    "COMPOUND_NAMED", "MULTI_BASIS", "MULTI_RATE", "ALTERNATIVE_VALUES",
}
DEFECT = {"DEFECT_TIME_VALUE", "DEFECT_AI_NAME", "DEFECT_TRUNCATED",
          "DEFECT_COLUMN_COLLAPSE", "DEFECT_RATIO_OR_INEQUALITY"}


def norm(s):
    return re.sub(r"\s+", " ", s.strip())


def classify(s):
    t = norm(s)

    # --- pre-checks, most-specific first
    if re.match(r"^(?:-+|–+|nil|n\.?\s?/?\s?a\.?|not\s*applicable)\.?$", t, re.I):
        return "NULL_MARKER"
    if not re.search(r"\d", t):
        return "PROSE_NO_NUMBER"
    if re.match(r"^\s*(?:[<>]\s*\d.*|\d+\s*:\s*\d+)\s*$", t):
        return "DEFECT_RATIO_OR_INEQUALITY"
    if TIME_VALUE.search(t):
        return "DEFECT_TIME_VALUE"
    if AI_NAME.match(t):
        return "DEFECT_AI_NAME"
    if PROSE_LEAD.match(t):
        return "PROSE_METHOD"
    if UNSUPPORTED.search(t):
        return "UNSUPPORTED_UNIT"
    if re.match(r"^(?:.*[+–-]\s*$|.*\((?:for|no)\b[^)]*$|[^(]*\)$|.*\bof\s*$)", t, re.S):
        return "DEFECT_TRUNCATED"

    kinds = anchor_kinds(t)
    pct = bool(PCT.search(t))
    compound = is_compound(t)

    # A cell naming two different bases is two doses, not one.
    if len(kinds) >= 2:
        return "MULTI_BASIS"
    if ALTERNATIVES.search(t):
        return "ALTERNATIVE_VALUES"
    # Named ready-mix breakdown: '1.58 (Cyantraniliprole 0.79 + Thiamethoxam 0.79)'
    if compound and re.search(r"[A-Za-z]{4,}", t) and "(" in t:
        return "COMPOUND_NAMED"
    if compound:
        for name, rx in COMPOUND_COMPILED:
            if rx.match(t):
                return name
        return "COMPOUND_OTHER"

    # A '%' plus a separate mass/volume figure is ONE dose stated twice
    # (the Kitazin family) -- handled by the PCT_* patterns, not MULTI_*.
    if not pct and len(kinds) == 1:
        # two separate rates on the same basis, e.g. '6 ml/kg seed 10-12 ml/kg seed'
        rx = dict(ANCHORS)[next(iter(kinds))]
        if len(rx.findall(t)) >= 2:
            return "MULTI_RATE"

    for name, rx in COMPILED:
        if rx.match(t):
            return name
    return "UNCLASSIFIED"


def kind_of(name):
    if name in DEFECT:
        return "defect"
    if name in FREE_TEXT:
        return "free_text"
    if name in NUMERIC:
        return "numeric"
    return "UNKNOWN"


def collect():
    dist = collections.defaultdict(
        lambda: {"cols": collections.Counter(), "files": collections.Counter(), "rows": 0})
    rows_by_file = {}
    for f in FILES:
        rr = list(csv.DictReader(open(f"data/interim/{f}_20260331_raw.csv", encoding="utf-8")))
        rows_by_file[f] = rr
        for r in rr:
            if r["assignment_kind"] not in DATA_KINDS:
                continue
            for c in DOSE_COLS:
                v = r[c] or ""
                if not v.strip():
                    continue
                d = dist[v]
                d["cols"][c] += 1
                d["files"][f] += 1
                d["rows"] += 1
    return dist, rows_by_file


if __name__ == "__main__":
    dist, _ = collect()
    buckets = collections.defaultdict(list)
    for s in dist:
        buckets[classify(s)].append(s)
    print(f"DISTINCT: {len(dist)}   CELLS: {sum(d['rows'] for d in dist.values())}\n")
    tot = collections.Counter()
    totc = collections.Counter()
    for name, ss in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        cells = sum(dist[s]["rows"] for s in ss)
        tot[kind_of(name)] += len(ss)
        totc[kind_of(name)] += cells
        print(f"{len(ss):5d} distinct /{cells:6d} cells  [{kind_of(name):9s}] {name}")
    print("\nby branch (distinct):", dict(tot))
    print("by branch (cells)   :", dict(totc))
    json.dump({k: sorted(v) for k, v in buckets.items()},
              open("tools/scratch/dose_buckets.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
