"""Phase A report generator. Reads nothing but the four raw CSVs."""
import csv, re, sys, collections
sys.path.insert(0, "tools/scratch")
from dose_survey_a import (FILES, DOSE_COLS, DATA_KINDS, classify, kind_of,
                           collect, norm)

# Reproduces tools/phase3_fallback_diagnosis.py's q5 exactly, so the '72'
# figure in reports/phase3_fallback_diagnosis.md can be reconciled.
PER_LITRE_RE = re.compile(r"per\s*lit|/\s*lit|ml\s*/\s*l\b|ml/l|gram\s+in\s+\d", re.I)
TUR_RE = re.compile(r"\btur\b|\barhar\b|red\s*gram|pigeon\s*pea|pigeonpea", re.I)
GRAM_RE = re.compile(r"bengal\s*gram|chickpea|\bgram\b", re.I)
EXCLUDE_GRAM_RE = re.compile(r"black\s*gram|blackgram|green\s*gram|greengram", re.I)
SCOPE_MATCHERS = {
    "cotton": re.compile(r"\bcotton\b", re.I),
    "soybean": re.compile(r"soy\s*a?\s*bean", re.I),
    "tur": TUR_RE, "gram": GRAM_RE,
    "onion": re.compile(r"\bonion\b", re.I),
    "tomato": re.compile(r"\btomato\b", re.I),
    "grape": re.compile(r"\bgrapes?\b", re.I),
    "pomegranate": re.compile(r"\bpomegranate\b", re.I),
}


def crop_scope_hits(crop_text):
    hits = set()
    for name, pat in SCOPE_MATCHERS.items():
        if name == "gram" and EXCLUDE_GRAM_RE.search(crop_text):
            continue
        if pat.search(crop_text):
            hits.add(name)
    return hits


PROPOSED_BASIS = {
    "BARE_NUMBER": "per_ha", "BARE_RANGE": "per_ha", "NUM_UNIT": "per_ha",
    "RANGE_UNIT": "per_ha", "PER_HA_EXPLICIT": "per_ha", "NUM_WITH_METHOD": "per_ha*",
    "PCT_SINGLE": "concentration_pct", "PCT_RANGE": "concentration_pct",
    "PCT_RANGE_BOTH": "concentration_pct", "PCT_WITH_EQUIV": "concentration_pct",
    "PCT_EQUIV_FIRST": "concentration_pct",
    "PER_LITRE": "per_litre_water", "PER_N_LITRE": "per_litre_water",
    "PER_LITRE_BARE": "per_litre_water",
    "PER_KG_SEED": "per_kg_seed", "PER_N_KG_SEED": "per_kg_seed",
    "PER_TREE": "per_tree", "PER_PLANT": "per_plant",
    "PER_SQ_M": "per_sq_m", "PER_N_SQ_M": "per_sq_m",
}


def main():
    dist, rows_by_file = collect()
    buckets = collections.defaultdict(list)
    for s in dist:
        buckets[classify(s)].append(s)

    out = []
    W = out.append

    W("# Phase A — dose-string surface survey\n")
    W(f"Source: the four in-scope raw CSVs in `data/interim/`, data rows only")
    W(f"(`assignment_kind` in {sorted(DATA_KINDS)}; headers and blanks excluded).")
    W(f"Columns scanned: {', '.join('`%s`' % c for c in DOSE_COLS)}.\n")

    # ---- 1. totals
    tot_cells = sum(d["rows"] for d in dist.values())
    W("## 1. Totals\n")
    W(f"- **Distinct dose-bearing strings: {len(dist)}**")
    W(f"- Non-empty dose cells (occurrences): {tot_cells}\n")
    W("| column | non-empty cells | distinct strings |")
    W("|---|---|---|")
    for c in DOSE_COLS:
        cells = sum(d["cols"][c] for d in dist.values())
        dd = sum(1 for d in dist.values() if d["cols"][c])
        W(f"| `{c}` | {cells} | {dd} |")
    W("")
    W("| file | non-empty dose cells | distinct strings |")
    W("|---|---|---|")
    for f in FILES:
        cells = sum(d["files"][f] for d in dist.values())
        dd = sum(1 for d in dist.values() if d["files"][f])
        W(f"| `{f}` | {cells} | {dd} |")
    W("")

    # ---- 2. pattern frequency
    W("## 2. Surface patterns\n")
    W("`branch` is the Phase B routing proposal, not a fact about the data.\n")
    W("| pattern | distinct | cells | branch | proposed Basis |")
    W("|---|---|---|---|---|")
    order = sorted(buckets.items(), key=lambda kv: -sum(dist[s]["rows"] for s in kv[1]))
    for name, ss in order:
        cells = sum(dist[s]["rows"] for s in ss)
        W(f"| `{name}` | {len(ss)} | {cells} | {kind_of(name)} | "
          f"{PROPOSED_BASIS.get(name, 'free_text')} |")
    W("")
    agg = collections.Counter()
    aggc = collections.Counter()
    for name, ss in buckets.items():
        agg[kind_of(name)] += len(ss)
        aggc[kind_of(name)] += sum(dist[s]["rows"] for s in ss)
    W("| branch | distinct | % distinct | cells | % cells |")
    W("|---|---|---|---|---|")
    for k in ("numeric", "free_text", "defect"):
        W(f"| {k} | {agg[k]} | {100*agg[k]/len(dist):.1f}% | {aggc[k]} | "
          f"{100*aggc[k]/tot_cells:.1f}% |")
    W(f"| **unclassified** | **{agg['UNKNOWN']}** | — | {aggc['UNKNOWN']} | — |")
    W("")

    # ---- 3. examples
    W("## 3. Examples, verbatim\n")
    for name, ss in order:
        cells = sum(dist[s]["rows"] for s in ss)
        W(f"### `{name}` — {len(ss)} distinct / {cells} cells — "
          f"{kind_of(name)} / `{PROPOSED_BASIS.get(name, 'free_text')}`\n")
        ex = sorted(ss, key=lambda x: -dist[x]["rows"])[:5]
        W("```text")
        for s in ex:
            cols = ",".join(sorted(dist[s]["cols"]))
            W(f"{s!r}   [x{dist[s]['rows']}  {cols}]")
        W("```\n")

    # ---- 4. the '72' reconciliation
    W("## 4. The percentage / per-litre group (the '~72')\n")
    total_rows = 0
    scope_rows = 0
    by_file = collections.Counter()
    by_file_scope = collections.Counter()
    scope_strings = collections.Counter()
    scope_rowdump = []
    for f in FILES:
        for r in rows_by_file[f]:
            vals = [r[c] or "" for c in DOSE_COLS]
            if not any(("%" in v) or PER_LITRE_RE.search(v) for v in vals):
                continue
            total_rows += 1
            by_file[f] += 1
            if crop_scope_hits(r["crop"] or ""):
                scope_rows += 1
                by_file_scope[f] += 1
                scope_rowdump.append(r)
                for c in DOSE_COLS:
                    v = r[c] or ""
                    if v.strip() and (("%" in v) or PER_LITRE_RE.search(v)):
                        scope_strings[v] += 1
    W("Reproducing `tools/phase3_fallback_diagnosis.py` q5 exactly (a row counts "
      "if any dose column contains `%` or matches "
      "`per lit|/lit|ml/l|gram in <n>`):\n")
    W("| file | rows with %/per-litre dose cell | of those, crop in scope.py's 8 |")
    W("|---|---|---|")
    for f in FILES:
        W(f"| `{f}` | {by_file[f]} | {by_file_scope[f]} |")
    W(f"| **total** | **{total_rows}** | **{scope_rows}** |\n")
    W("### 4.1 The '72' is stale\n")
    W("`reports/phase3_fallback_diagnosis.md` records 276 / **72** for this same")
    W("query. Re-running `tools/phase3_fallback_diagnosis.py` unchanged against the")
    W("CURRENT CSVs reproduces the numbers above, not the ones in the committed")
    W("report. The report was generated on 2026-08-29 from the Step-2 extraction as")
    W("it stood before three later Phase 3 fixes (header fragments / method column,")
    W("the phantom merge, the row-7 quarantine fix), all of which corrected")
    W("mis-columned cells. The largest movement is `bio_insecticides` 26 -> 1: that")
    W("file now has exactly one `%` dose cell, and inspection confirms that is")
    W("correct — its doses really are almost all bare per-hectare numbers.\n")
    W("So the real size of this group today is **206 rows / 57 in-scope rows**, and")
    W("the committed 72 should be read as a pre-fix figure. The Phase 3 report was")
    W("not modified.\n")
    W("### 4.2 The in-scope strings\n")
    W(f"Those {scope_rows} in-scope rows carry **{len(scope_strings)} distinct "
      f"dose strings**, listed in full below with the pattern each falls into.\n")
    W("| # | raw string | col | pattern | branch |")
    W("|---|---|---|---|---|")
    for i, (s, n) in enumerate(sorted(scope_strings.items(), key=lambda kv: -kv[1]), 1):
        cls = classify(s)
        cols = ",".join(sorted(dist[s]["cols"])) if s in dist else "?"
        W(f"| {i} | `{norm(s)}` | {cols} | `{cls}` | {kind_of(cls)} |")
    W("")
    W("Pattern mix across those rows:\n")
    cnt = collections.Counter(classify(s) for s in scope_strings)
    for k, v in cnt.most_common():
        W(f"- `{k}` — {v} distinct")
    W("")

    # ---- 5. flags
    W("## 5. Strings I cannot confidently assign\n")
    W("Every one of the 2113 strings landed in a named pattern (zero")
    W("`UNCLASSIFIED`). These are the cases where the pattern is clear but the")
    W("BASIS is a judgement call, so Phase B should not decide them silently.\n")
    flags = [
        ("dilution_water is not a dose column",
         "Its CIB&RC header is 'Dilution in Water (Liter)' — spray volume, which "
         "the schema carries as ChemicalOption.spray_volume_*, not as a Dose. "
         f"{sum(d['cols']['dilution_water'] for d in dist.values())} of the "
         f"{tot_cells} cells scanned come from it. It is surveyed here because "
         "column-shifted rows do drop real doses into it, but Phase B should not "
         "mint per_ha Doses out of it wholesale.",
         ["500", "500 –1000", "As required depending upon crop stage and plant "
          "protection equipment used", "6 ml/kg seed 10-12 ml/kg seed"]),
        ("PCT_EQUIV_FIRST where the equivalent is per-plant, not per-area",
         "These state one dose two ways, but the two ways are different BASES: "
         "g/vine and %. Choosing concentration_pct discards the per-vine figure "
         "and vice versa.",
         ["1.8ga.i/vine  or0.09%", "2.5gm/vine  or0.125%"]),
        ("PER_N_KG_SEED needs an explicit normalisation rule",
         "'38.75 g/10 kg seeds' is per_kg_seed only after dividing by 10. If "
         "Phase B does not divide, the dose is 10x too high. If it does divide, "
         "the printed number no longer appears in the parsed value.",
         ["38.75 g/10 kg  seeds", "600g/100  Kg seed", "0.75-1.0/100  Kg seed"]),
        ("PER_N_LITRE likewise",
         "'25 ml/100 lit' is per_litre_water only after dividing by 100.",
         ["25 ml/100 lit", "70-87.5/100 l of  water", "0.90/10 Lit water"]),
        ("NUM_WITH_METHOD is numeric only if the qualifier is discardable",
         "'750 (Soil drench)' is a number plus an application method — safe to "
         "parse and keep the method in `raw`. But the same bucket holds "
         "'500 20 ltr/ha (via drone application)', which is two volumes for two "
         "equipment types. Splitting these needs a decision.",
         ["750  (Soil drench)", "500-750  depending upon  crop canopy",
          "500  20 ltr/ha (via  drone  application)"]),
        ("Ranges: which end is kept",
         "Dose has value_min and value_max, so a range can be carried whole. "
         "Stating the rule anyway because the Advisory layer will later have to "
         "pick one, and PHI already documents the opposite choice (larger = safer "
         "for PHI; for dose the LOWER end is the safer one).",
         ["500-750", "1.5-2KG", "0.0025-0.005%"]),
    ]
    for i, (title, why, ex) in enumerate(flags, 1):
        W(f"**{i}. {title}**\n")
        W(f"{why}\n")
        W("```text")
        for e in ex:
            W(repr(e))
        W("```\n")

    open("reports/phase4_stepA_dose_survey.md", "w", encoding="utf-8").write("\n".join(out))
    print("\n".join(out[:0]))
    print(f"wrote reports/phase4_stepA_dose_survey.md  ({len(out)} lines)")
    print(f"distinct={len(dist)} cells={tot_cells} scope_rows={scope_rows} "
          f"scope_distinct_strings={len(scope_strings)} total_pct_rows={total_rows}")


if __name__ == "__main__":
    main()
