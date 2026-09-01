"""Phase A survey: catalogue dose string patterns across raw CIB&RC CSVs.

Scratch/throwaway analysis script — not part of the pipeline.
"""
import csv
import re
import collections
import json

FILES = ["insecticides", "fungicides", "bio_insecticides", "bio_fungicides"]
COLS = ["dose_ai", "dose_formulation", "dilution_water"]

all_cells = []  # (raw_string, source_file, column)
for f in FILES:
    with open(f"data/interim/{f}_20260331_raw.csv", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    data_rows = [x for x in rows if x["assignment_kind"] in ("ordinal_6", "fallback_subset")]
    for row in data_rows:
        for c in COLS:
            v = row[c].strip()
            if v:
                all_cells.append((v, f, c))

distinct_strings = {}
for v, f, c in all_cells:
    distinct_strings.setdefault(v, []).append((f, c))

print("Total non-empty dose cells (with duplicates):", len(all_cells))
print("Total distinct dose strings:", len(distinct_strings))
print()


def classify(s):
    s_norm = s.strip()

    # percentage e.g. "0.025%", "0.025 %"
    if re.fullmatch(r"[\d.]+\s*%", s_norm):
        return "N%"

    # per-litre dilution e.g. "2 ml/l", "2.5 ml/lit water", "1 g/l water"
    if re.search(r"\b(ml|g|gm|gram|kg|l|lit|litre)\s*/\s*(l|lit|litre)\b", s_norm, re.I):
        return "N unit/litre_water"
    if re.search(r"\bin\s+\d", s_norm, re.I) and re.search(r"(lit|litre|water)", s_norm, re.I):
        return "N unit in M lit water"

    # per hectare/acre e.g. "500 g/ha", "1 kg/acre"
    if re.search(r"/\s*(ha|hectare)\b", s_norm, re.I):
        return "N unit/ha"
    if re.search(r"/\s*acre\b", s_norm, re.I):
        return "N unit/acre"

    # per tree / per plant
    if re.search(r"/\s*(tree|plant)\b", s_norm, re.I):
        return "N unit/tree_or_plant"

    # per kg seed
    if re.search(r"/\s*kg\s*seed\b", s_norm, re.I) or re.search(r"\bkg\s*seed\b", s_norm, re.I):
        return "N unit/kg_seed"

    # per sq m
    if re.search(r"/\s*(sq\.?\s*m|m2|m²|square\s*met(er|re))\b", s_norm, re.I):
        return "N unit/sq_m"

    # gm/m3 or similar volumetric fumigant doses
    if re.search(r"/\s*m3\b|/\s*m³\b", s_norm, re.I):
        return "N unit/m3"

    # plain numeric range without unit context obvious, e.g. "500-750"
    if re.fullmatch(r"[\d.]+\s*-\s*[\d.]+", s_norm):
        return "bare_range_no_unit"

    # plain single number no unit
    if re.fullmatch(r"[\d.]+", s_norm):
        return "bare_number_no_unit"

    # compound / multi-part seed treatment or multi-clause text with numbers and "+"
    if "+" in s_norm and re.search(r"\d", s_norm):
        return "compound_multi_ai"

    # contains digits but doesn't match above -> other numeric-ish
    if re.search(r"\d", s_norm):
        return "other_numeric_freeform"

    # no digits at all
    return "free_text_no_number"


pattern_counts = collections.Counter()
pattern_examples = collections.defaultdict(list)
pattern_members = collections.defaultdict(list)

for s in distinct_strings:
    p = classify(s)
    pattern_counts[p] += 1
    pattern_members[p].append(s)
    if len(pattern_examples[p]) < 6:
        pattern_examples[p].append(s)

print("=== Pattern frequency (by distinct string) ===")
for p, cnt in pattern_counts.most_common():
    print(f"{p:30s} {cnt:5d}")

print()
print("=== Examples per pattern ===")
for p, cnt in pattern_counts.most_common():
    print(f"\n--- {p} (n={cnt}) ---")
    for ex in pattern_examples[p]:
        srcs = distinct_strings[ex]
        print(f"  {ex!r}   [{srcs[:2]}]")

# Kitazin-style: percentage-looking OR per-litre dilution cases
kitazin_like = pattern_members["N%"] + pattern_members["N unit/litre_water"] + pattern_members["N unit in M lit water"]
print(f"\n=== Percentage / per-litre dilution total distinct strings: {len(kitazin_like)} ===")
for s in kitazin_like:
    print(" ", repr(s))

# dump full pattern membership to json for inspection
with open("data/interim/dose_pattern_survey.json", "w", encoding="utf-8") as fh:
    json.dump(
        {
            "total_cells": len(all_cells),
            "total_distinct": len(distinct_strings),
            "pattern_counts": dict(pattern_counts),
            "pattern_members": {p: sorted(m) for p, m in pattern_members.items()},
            "string_sources": {s: srcs for s, srcs in distinct_strings.items()},
        },
        fh,
        indent=2,
    )
print("\nWrote data/interim/dose_pattern_survey.json")
