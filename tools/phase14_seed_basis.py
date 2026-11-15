"""phase14_seed_basis.py -- Phase 14: the seed-treatment dose-basis error in
label_db -- scope, affected items and score sensitivity. No GPU.

READ ONLY on every frozen file (label_db, bench.jsonl, verify.py, SFT data,
existing responses and scores). Writes only data/final/eval/seedexcl_items.json
(--write-items) and the --md tables.

THE ERROR. CIB&RC's tables head the dose column "Dosage/ha (Formulation)"
(fungicides p.43). For seed-treatment products the number in that column is
usually per kg (or per 10 / 100 kg) of SEED. Where the cell says so, label_db
records per_kg_seed correctly. Where the cell is a bare number, the parser
took the header literally and recorded per_ha -- and verify() then derives a
per-acre figure and accepts per-acre answers against it.

ROWS. Every label_db row whose verify.formulation_key code is a seed-treatment
code (FS, ES, WS, DS -- LS is not in the repo's vocabulary): 38 rows. Each was
classified by reading its PDF page; the review is the ROW_REVIEW table below,
and the script asserts it covers exactly those 38 rows.

  CORRECT       the recorded basis is what the label prints
  WRONG_BASIS   a bare number recorded per_ha, where the page ties that
                product's dose to SEED (per kg / 10 kg / 100 kg of seed,
                "seed dresser", a per-kg-seed slurry)
  UNCLEAR       a bare number under the per-ha header with no seed statement
                for that product on the page -- a seed-treatment code alone
                is not taken as proof
  NOT_RECORDED  no dose recorded at all (the parser refused): nothing to grade

AFFECTED. An option "uses" a row if verify() would grade it against that row:
label_db.for_triple on (crop, pest, a.i.), then verify's _narrow_candidates
(formulation; application_method None, the scoring convention). Bench items:
the gold advisory, with the gold key. SFT examples: the assistant answer,
with the generation log's crop and pest.

Usage:
    python tools/phase14_seed_basis.py --write-items [--force]
    python tools/score.py <responses> --label <arm>_seedexcl --exclude-items data/final/eval/seedexcl_items.json
    python tools/phase14_seed_basis.py --md <tables.md>
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import pandas as pd  # noqa: E402

import phase10_stepB_audit as p10  # noqa: E402
import phase14_step5_eval as s5  # noqa: E402
import score as sc  # noqa: E402

EVAL = p10.EVAL
ITEMS_FILE = EVAL / "seedexcl_items.json"
SEED_CODES = {"FS", "ES", "WS", "DS"}

_DRESSER_PHI = "possible: 'seed dresser' printed in the dilution column; the block has no PHI column"
_NA_PHI = "possible: PHI printed 'NA' (not applicable, or not available)"
# row -> (class, what the label page shows, PHI flag)
ROW_REVIEW: dict[int, tuple[str, str, str | None]] = {
    32: ("CORRECT", "cell '60 gm/kg seed'", None),
    150: ("WRONG_BASIS", "product header 'dosage per 100 kg of seeds'", None),
    151: ("WRONG_BASIS", "product header 'dosage per 100 kg of seeds'", None),
    152: ("WRONG_BASIS", "product header 'dosage per 100 kg of seeds'; 0.25 per 100 kg is implausibly small, so the scale is uncertain too", None),
    153: ("UNCLEAR", "bare number under the per-ha header; no seed statement for this product (its size matches the per-100-kg rows above)", None),
    248: ("WRONG_BASIS", "row 'This is used as seed dresser'; the product's explicit cotton row prints 8-10 ml/kg seed", _DRESSER_PHI),
    249: ("WRONG_BASIS", "row 'This is used as seed dresser'; the product's explicit soybean rows print 4-6 ml/kg seed", _DRESSER_PHI),
    250: ("CORRECT", "cell '8-10 ml/kg seed'", None),
    251: ("NOT_RECORDED", "page prints '4 ml/kg seed'; extraction shifted it to the dilution column", None),
    252: ("NOT_RECORDED", "page prints '6 ml/kg seed'; extraction shifted it to the dilution column", None),
    253: ("CORRECT", "cell '8-10 ml/kg seed'", None),
    254: ("CORRECT", "cell '4 ml/kg seed'", None),
    255: ("CORRECT", "cell '6 ml/kg seed'", None),
    256: ("WRONG_BASIS", "row 'Use as seed dresser at the time of sowing'; seed quantity not printed", _DRESSER_PHI),
    257: ("WRONG_BASIS", "row 'Use as seed dresser at the time of sowing'; seed quantity not printed", _DRESSER_PHI),
    275: ("UNCLEAR", "bare '100'; dilution and PHI 'NA'; no seed statement for this product", _NA_PHI),
    385: ("CORRECT", "cell '20-30gm Per kg seed'", None),
    412: ("CORRECT", "cell '1.0 ml/kg seed'", None),
    413: ("CORRECT", "cell '1.5 ml/kg seed'", None),
    438: ("NOT_RECORDED", "'2.0' spans the formulation and dilution columns; no dose recorded", None),
    474: ("CORRECT", "cell '4.0 ml/10 Kg of seed', recorded 0.4 per kg", None),
    491: ("UNCLEAR", "bare '25-30gm' under the per-ha header; PHI 7-10; no seed statement", None),
    504: ("UNCLEAR", "bare '100' directly under the 'Dosage/ha (Formulation)' header; no seed statement", None),
    528: ("UNCLEAR", "bare '100' under the per-ha header; no seed statement", None),
    541: ("WRONG_BASIS", "product block prints '(for 10 kg seed)' and '30-35/10 kg seed' on its groundnut row; same a.i. 7.5+15", None),
    542: ("WRONG_BASIS", "product block prints '(for 10 kg seed)' and '30-35/10 kg seed' on its groundnut row; same a.i. 7.5+15", None),
    543: ("WRONG_BASIS", "product block prints '(for 10 kg seed)' and '30-35/10 kg seed' on its groundnut row; same a.i. 7.5+15", None),
    544: ("CORRECT", "cell '3.0gm/Kg seed'", None),
    545: ("NOT_RECORDED", "continuation line of the soybean row ('diseases' / 'waiting not required'); no dose", None),
    546: ("CORRECT", "cell '3.5gm/Kg seed'", None),
    547: ("CORRECT", "cell '4.0gm/Kg seed'", None),
    616: ("UNCLEAR", "bare '80 - 100'; only the product's rice row describes a per-kg-seed slurry, at another scale", None),
    617: ("UNCLEAR", "bare '80 - 100'; only the product's rice row describes a per-kg-seed slurry, at another scale", None),
    620: ("CORRECT", "cell '3.0 ml/10 kg seeds', recorded 0.3 per kg", None),
    629: ("WRONG_BASIS", "bare '4.0'; the same claim as #630 (4.0 ml carrying 1.25 g a.i. on cotton), whose block prints 'slurry volume ... 10-12 ml/kg cotton seeds'; its dilution '10' is that slurry", None),
    630: ("WRONG_BASIS", "bare '4.0'; block prints 'slurry volume ... 10-12 ml/kg cotton seeds' and doses in 'ml/kg seed'",
          "explicit: merged PHI cell 'Seed treatment is done at the time of sowing, hence waiting period is not applicable'"),
    643: ("CORRECT", "cell '2 ml/kg seed'", _NA_PHI),
    672: ("NOT_RECORDED", "a foliar Bt product: 'ES' here is not a seed treatment; dose cell not parsed", None),
}

# label -> (responses file under data/final/eval, --unwrap-advisory)
ARMS = {
    "R0_baseline": ("baseline_responses.jsonl", False),
    "R3_sft": ("trained_responses.jsonl", False),
    "R2_base_rag": ("R2_responses.jsonl", False),
    "R2_base_rag_unwrapped": ("R2_responses.jsonl", True),
    "R4_sft_rag": ("R4_responses.jsonl", False),
    "R4_sft_rag_guarded": ("guarded/R4_sft_rag_responses.jsonl", False),
}


def seed_rows(v, res) -> list[int]:
    df = res.label_db.df
    rows = [int(i) for i in df.index if v.formulation_key(df.at[i, "active_ingredient"])[0] in SEED_CODES]
    assert set(rows) == set(ROW_REVIEW), ("ROW_REVIEW out of date", sorted(set(rows) ^ set(ROW_REVIEW)))
    return rows


def by_class(cls: str) -> set[int]:
    return {r for r, (c, _, _) in ROW_REVIEW.items() if c == cls}


def graded_rows(v, res, crop, canon, adv) -> set[int]:
    """label_db rows verify() would grade this answer's options against."""
    out = set()
    opts = adv.get("chemical_options") if isinstance(adv, dict) else None
    for o in opts if isinstance(opts, list) else []:
        if not isinstance(o, dict):
            continue
        rows = res.label_db.for_triple(crop, canon, v.normalise_ai(o.get("active_ingredient")))
        if rows:
            out |= {r.index for r in v._narrow_candidates(rows, o.get("formulation"), None)}
    return out


def parse_answer(raw: str):
    try:
        adv = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(adv, dict) and list(adv) == ["Advisory"]:
        adv = adv["Advisory"]
    return adv


def affected(v, res, bench: dict) -> dict:
    wrong, unclear = by_class("WRONG_BASIS"), by_class("UNCLEAR")
    gold_pest = {i: p10.ctx_for(v, res, it).pest_match().canonical_name for i, it in bench.items()}
    gold = {i: graded_rows(v, res, it["crop_slug"], gold_pest[i], it["gold_advisory"]) for i, it in bench.items()}
    out = {"gold_wrong": sorted(i for i, g in gold.items() if g & wrong),
           "gold_unclear": sorted(i for i, g in gold.items() if g & unclear),
           "gold_rows": {i: sorted(g & wrong) for i, g in gold.items() if g & wrong},
           "arms": {}}
    for label, (resp, _u) in ARMS.items():
        raw = sc.load_responses(EVAL / resp)
        out["arms"][label] = sorted(i for i, it in bench.items()
                                    if graded_rows(v, res, it["crop_slug"], gold_pest[i], parse_answer(raw[i])) & wrong)
    out["any"] = sorted(set(out["gold_wrong"]).union(*map(set, out["arms"].values())))

    from pest_matcher import match_pest
    log = {f"S{r['slice']}_{r['row_id']}": r for r in
           csv.DictReader(open(ROOT / "data/final/sft_generation_log.csv", encoding="utf-8", newline=""))}
    out["sft"] = {}
    for split in ("sft_train.jsonl", "sft_test.jsonl"):
        c = Counter()
        for ex in p10.jsonl(ROOT / "data/final" / split):
            meta = log[ex["id"]]
            adv = json.loads(next(m["content"] for m in ex["messages"] if m["role"] == "assistant"))
            canon = (match_pest(meta["crop_slug"], meta["canonical_pest"], res.table).canonical_name
                     if meta["canonical_pest"] else None)
            g = graded_rows(v, res, meta["crop_slug"], canon, adv)
            c["n"] += 1
            c["wrong"] += bool(g & wrong)
            c["unclear"] += bool(g & unclear)
        out["sft"][split] = dict(c)
    return out


def write_items(aff: dict, force: bool) -> None:
    if ITEMS_FILE.exists() and not force:
        raise SystemExit(f"{ITEMS_FILE.relative_to(ROOT)} exists; pass --force to replace it")
    ITEMS_FILE.write_text(json.dumps({
        "generated_by": "tools/phase14_seed_basis.py --write-items",
        "description": ("Bench items whose gold advisory is graded against a label_db row with the "
                        "seed-treatment basis error (WRONG_BASIS). Consumed by tools/score.py "
                        "--exclude-items for the _seedexcl sensitivity scores."),
        "wrong_basis_rows": sorted(by_class("WRONG_BASIS")),
        "items": aff["gold_wrong"],
        "items_any_arm": aff["any"],
    }, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {ITEMS_FILE.relative_to(ROOT).as_posix()}: {len(aff['gold_wrong'])} items "
          f"({len(aff['any'])} incl. model-side)")


def md(v, res, bench: dict, aff: dict) -> str:
    L = []
    w = L.append
    df = res.label_db.df
    rows = seed_rows(v, res)
    w("## Rows (every seed-treatment-formulation row in label_db)\n")
    w("| row | crop | product | recorded dose / basis | PHI (days / n.a. / raw) | PDF page | cell | class | what the page shows | PHI flag |")
    w("|---:|---|---|---|---|---|---|---|---|---|")
    for i in sorted(rows):
        r = df.loc[i]
        lo, hi = r.dose_formulation_value_min, r.dose_formulation_value_max
        dose = "—" if lo != lo else f"{lo:g}" + ("" if hi != hi else f"-{hi:g}") + f" {r.dose_formulation_unit}"
        phi = f"{'—' if pd.isna(r.phi_days) else int(r.phi_days)} / {bool(r.phi_not_applicable)} / {r.phi_raw!r}"
        cls, why, flag = ROW_REVIEW[i]
        w(f"| {i} | {r.crop_slug} | {r.active_ingredient} | {dose} / {r.dose_formulation_basis or '—'} | {phi} | "
          f"{r.source_file.split('_')[0]} p.{r.source_page} | {r.dose_formulation_raw!r} | **{cls}** | {why} | {flag or ''} |")
    cnt = Counter(c for c, _, _ in ROW_REVIEW.values())
    per_ha = [i for i in rows if df.at[i, "dose_formulation_basis"] == "per_ha"]
    w(f"\n{len(rows)} rows: " + ", ".join(f"{k} {cnt[k]}" for k in ("CORRECT", "WRONG_BASIS", "UNCLEAR", "NOT_RECORDED"))
      + f". Recorded per_ha: {len(per_ha)} ({sum(ROW_REVIEW[i][0] == 'WRONG_BASIS' for i in per_ha)} WRONG_BASIS, "
        f"{sum(ROW_REVIEW[i][0] == 'UNCLEAR' for i in per_ha)} UNCLEAR). "
        f"PHI flags: explicit {sum(1 for _, _, f in ROW_REVIEW.values() if f and f.startswith('explicit'))}, "
        f"possible {sum(1 for _, _, f in ROW_REVIEW.values() if f and f.startswith('possible'))}.\n")

    w("## Affected items and examples\n")
    w(f"- Bench items whose gold advisory uses a WRONG_BASIS row: **{len(aff['gold_wrong'])}** — "
      + ", ".join(f"{i} (rows {aff['gold_rows'][i]})" for i in aff["gold_wrong"]))
    w(f"- Bench items whose gold uses an UNCLEAR row (not excluded): {len(aff['gold_unclear'])} — {', '.join(aff['gold_unclear'])}")
    for label, ids in aff["arms"].items():
        w(f"- {label} answers graded against a WRONG_BASIS row: {len(ids)} — {', '.join(ids) or '—'}")
    w(f"- Gold or any arm: {len(aff['any'])} items")
    for split, c in aff["sft"].items():
        w(f"- {split}: {c['wrong']} of {c['n']} examples use a WRONG_BASIS row; {c['unclear']} use an UNCLEAR row")

    w("\n## Sensitivity: means with the affected items excluded\n")
    excl7, excl_any = set(aff["gold_wrong"]), set(aff["any"])
    w(f"| arm | mean, 498 | mean, excl. {len(excl7)} (gold) | Δ | n scored | mean, excl. {len(excl_any)} (gold or any arm) | Δ |")
    w("|---|---:|---:|---:|---:|---:|---:|")
    sets, changes = {}, {}
    for label, (resp, unwrap) in ARMS.items():
        base = json.loads((EVAL / f"scores_{label}.json").read_text(encoding="utf-8"))
        sx = json.loads((EVAL / f"scores_{label}_seedexcl.json").read_text(encoding="utf-8"))
        assert sx["summary"]["excluded_up_front"] == sorted(excl7), label
        assert sx["summary"]["responses"] == base["summary"]["responses"], label
        scored = {r["item_id"]: r["score"] for r in base["items"] if not r["excluded"]}
        m7 = s5.np.mean([x for i, x in scored.items() if i not in excl7])
        assert round(m7, 6) == round(sx["summary"]["mean"], 6), (label, m7, sx["summary"]["mean"])
        ma = s5.np.mean([x for i, x in scored.items() if i not in excl_any])
        b = base["summary"]["mean"]
        changes[label] = (m7 - b, ma - b)
        sets[label] = scored
        w(f"| {label} | {b:.4f} | {m7:.4f} | {m7 - b:+.4f} | {sx['summary']['n_scored']} | {ma:.4f} | {ma - b:+.4f} |")
    big = max(changes.items(), key=lambda kv: abs(kv[1][0]))
    w(f"\nLargest change, gold exclusion: {big[0]} {big[1][0]:+.4f}. "
      f"Largest, gold-or-any-arm exclusion: "
      f"{max(changes.items(), key=lambda kv: abs(kv[1][1]))[0]} {max(abs(c[1]) for c in changes.values()):.4f} (abs).\n")

    w("## The four paired comparisons, before and after\n")
    w("| A vs B | Δ, 498 [95% CI] | Δ, excl. gold-affected [95% CI] | Δ, excl. gold or any arm [95% CI] | CI sign changes? |")
    w("|---|---|---|---|---|")
    order = list(sc.scored_items(bench))
    for a, b in s5.PAIRS:
        res_ = {}
        for tag, ex in (("all", set()), ("gold", excl7), ("any", excl_any)):
            keep = [i for i in order if i not in ex]
            res_[tag] = s5.paired({i: sets[a][i] for i in keep if i in sets[a]},
                                  {i: sets[b][i] for i in keep if i in sets[b]}, keep)
        sign = lambda r: (r["ci95"][0] > 0) - (r["ci95"][1] < 0)
        flips = "no" if sign(res_["all"]) == sign(res_["gold"]) == sign(res_["any"]) else "**yes**"
        cell = lambda r: f"{r['mean_diff']:+.4f} [{r['ci95'][0]:+.4f}, {r['ci95'][1]:+.4f}] (n {r['n']})"
        w(f"| {a} vs {b} | {cell(res_['all'])} | {cell(res_['gold'])} | {cell(res_['any'])} | {flips} |")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-items", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--md", type=Path)
    args = ap.parse_args()
    if not (args.write_items or args.md):
        ap.error("nothing to do: pass --write-items and/or --md")
    v = p10.load_verify()
    res = v.VerifyResources.load()
    bench = {r["item_id"]: r for r in p10.jsonl(p10.BENCH)}
    seed_rows(v, res)
    aff = affected(v, res, bench)
    if args.write_items:
        write_items(aff, args.force)
    if args.md:
        args.md.write_text(md(v, res, bench, aff), encoding="utf-8")
        print("wrote", args.md)


if __name__ == "__main__":
    main()
