"""Phase 4 PHI Step A — survey the real waiting_period_phi inputs.

Read-only. Classifies every DISTINCT waiting_period_phi cell from the four
in-scope raw CSVs into a named surface pattern, then runs the ALREADY
COMMITTED src/parse_phi.py over each one and records what it returns or
raises. No parser is written here.
"""
from __future__ import annotations

import collections
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from parse_phi import PHIParseError, parse_phi  # noqa: E402

FILES = ["insecticides", "fungicides", "bio_insecticides", "bio_fungicides"]
DATA_KINDS = {"ordinal_6", "fallback_subset"}
COL = "waiting_period_phi"


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


NUM = r"\d+(?:\.\d+)?"
FRAC = r"\d+(?:\s?[½¼¾])?(?:\.\d+)?"   # '3½'
DASH = r"(?:-+|–|—|to)"

# ---------------------------------------------------------------- pre-checks

# Content that is not a waiting period at all but landed in the column.
# Ordered first because each one contains digits that a digit-scraping parser
# would happily return as a day count.
FOREIGN = [
    ("DEFECT_STANDARD_REF", re.compile(r"\bIS\s*:\s*\d", re.I)),
    ("DEFECT_DILUTION_TEXT", re.compile(r"dilution\s+in\s+water", re.I)),
    ("DEFECT_DOSE_TEXT", re.compile(r"\bkg\s+seed\b|\bliter/ha\b|\blit/ha\b", re.I)),
    ("RESIDUE_CONDITION", re.compile(r"residues?\b", re.I)),
    ("GROWTH_STAGE", re.compile(
        r"emergence|earhead|petal\s*fall|whit\s*bud|bud\s*break|dormant"
        r"|end\s+of\s+the\s+harvest|bloom|flowering|sowing|transplant", re.I)),
]

# Prose meaning "the question does not arise: this is a seed treatment".
SEED_TREATMENT = re.compile(
    r"seed\s*dresse?r|seed\s+treatment|seed\s*/\s*tuber\s+treatment"
    r"|wet\s+slurry\s+treatment|being\s+seed|single\s+application\s+by\s+seed",
    re.I)

NOT_REQUIRED = re.compile(r"\b(?:waiting\s+)?not\s+required\b|not\s+applicable", re.I)

NULLISH = re.compile(r"^(?:-+|–+|nil|none|n\.?\s?/?\s?a\.?)$", re.I)
NULLISH_QUALIFIED = re.compile(r"^n\.?\s?/?\s?a\.?\s*\(", re.I)

UNIT_WORD = re.compile(r"\b(days?|weeks?|months?|years?|hours?|hrs?)\b", re.I)

PATTERNS = [
    ("BARE_NUMBER", rf"^{NUM}$"),
    ("BARE_RANGE", rf"^{NUM}\s*{DASH}\s*{NUM}$"),
    ("NUM_DAYS", rf"^{NUM}\s*days?\.?$"),
    ("RANGE_DAYS", rf"^{NUM}\s*{DASH}\s*{NUM}\s*days?\.?$"),
    ("NUM_WEEKS", rf"^(?:not\s+less\s+than\s*)?{NUM}\s*weeks?\.?$"),
    ("NUM_MONTHS", rf"^(?:about\s*)?{NUM}\s*months?\.?$"),
    ("RANGE_MONTHS", rf"^{FRAC}\s*{DASH}\s*{FRAC}\s*months?\b.*$"),
    ("NUM_HOURS", rf"^{NUM}\s*(?:hours?|hrs?)\.?$"),
]
COMPILED = [(n, re.compile(p, re.I)) for n, p in PATTERNS]


def classify(raw: str) -> str:
    t = norm(raw)
    if t == "":
        return "BLANK"
    if NULLISH.match(t):
        return "NULL_MARKER"
    if NULLISH_QUALIFIED.match(t):
        return "NULL_MARKER_QUALIFIED"

    for name, rx in FOREIGN:
        if rx.search(t):
            return name

    if NOT_REQUIRED.search(t):
        return "NOT_REQUIRED_PROSE"
    if SEED_TREATMENT.search(t):
        return "SEED_TREATMENT_PROSE"

    units = {u.lower().rstrip("s") for u in UNIT_WORD.findall(t)}
    units = {"hour" if u in ("hr", "hour") else u for u in units}
    if len(units) > 1:
        return "MIXED_UNITS"

    for name, rx in COMPILED:
        if rx.match(t):
            return name

    if not re.search(r"\d", t):
        return "PROSE_NO_NUMBER"
    # several bare numbers, nothing joining them
    if re.match(rf"^{NUM}(?:\s+{NUM})+$", t):
        return "DEFECT_COLUMN_COLLAPSE"
    return "UNCLASSIFIED"


# Which patterns can legitimately yield a number, vs mean "no number", vs
# are broken. This is a PROPOSAL for the parser step, not a fact.
RESOLVES = {"BARE_NUMBER", "BARE_RANGE", "NUM_DAYS", "RANGE_DAYS", "NUM_WEEKS",
            "NUM_MONTHS", "RANGE_MONTHS"}
MEANS_NO_NUMBER = {"BLANK", "NULL_MARKER", "NULL_MARKER_QUALIFIED",
                   "SEED_TREATMENT_PROSE", "NOT_REQUIRED_PROSE",
                   "PROSE_NO_NUMBER", "GROWTH_STAGE"}
BROKEN = {"DEFECT_STANDARD_REF", "DEFECT_DILUTION_TEXT", "DEFECT_DOSE_TEXT",
          "DEFECT_COLUMN_COLLAPSE", "MIXED_UNITS", "NUM_HOURS",
          "RESIDUE_CONDITION", "UNCLASSIFIED"}


def kind_of(name: str) -> str:
    if name in RESOLVES:
        return "resolves"
    if name in MEANS_NO_NUMBER:
        return "no-number"
    if name in BROKEN:
        return "needs-decision"
    return "???"


def run_existing(raw: str):
    """What the COMMITTED src/parse_phi.py does with this cell."""
    try:
        return ("ok", parse_phi(raw))
    except PHIParseError as e:
        return ("raises", str(e)[:70])
    except Exception as e:                      # noqa: BLE001
        return ("CRASH", f"{type(e).__name__}: {e}"[:70])


def collect():
    dist = collections.defaultdict(
        lambda: {"rows": 0, "files": collections.Counter(), "pages": set()})
    for f in FILES:
        p = ROOT / "data" / "interim" / f"{f}_20260331_raw.csv"
        for r in csv.DictReader(open(p, encoding="utf-8")):
            if r["assignment_kind"] not in DATA_KINDS:
                continue
            v = r[COL] or ""
            d = dist[v]
            d["rows"] += 1
            d["files"][f] += 1
            d["pages"].add((f, r["source_page"]))
    return dist


if __name__ == "__main__":
    dist = collect()
    buckets = collections.defaultdict(list)
    for s in dist:
        buckets[classify(s)].append(s)

    total_cells = sum(d["rows"] for d in dist.values())
    print(f"DISTINCT: {len(dist)}   CELLS: {total_cells}\n")
    for name, ss in sorted(buckets.items(),
                           key=lambda kv: -sum(dist[s]["rows"] for s in kv[1])):
        cells = sum(dist[s]["rows"] for s in ss)
        print(f"{len(ss):4d} distinct /{cells:6d} cells  [{kind_of(name):14s}] {name}")
    print()

    # cross-check the committed parser
    print("=== committed parse_phi behaviour, by pattern ===")
    for name, ss in sorted(buckets.items()):
        outs = collections.Counter()
        for s in ss:
            status, val = run_existing(s)
            outs[(status, val if status != "ok" else type(val).__name__)] += 1
        print(f"{name}: {dict(outs)}")
