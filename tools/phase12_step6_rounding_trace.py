"""phase12_step6_rounding_trace.py — (1) scope the per-acre rounding defect
in verify()'s C1, (2) trace two wrong dose numbers back to the training data.

1. C1's RANGE test is exact containment (lo <= pred <= hi) on 4-decimal
   numbers. label_db rounds per-acre bounds in the label's unit, the model
   rounds in its own; when those differ (1.0 kg/ha -> label 0.4047 kg, model
   404.6781 g) a correct dose can miss the range by a few parts per million.
   This script rebuilds C1 per option exactly as _check_dose does — same
   candidate rows (for_triple then _narrow_candidates), same basis filter,
   same _dose_value_ok, same consensus — and asserts it reproduces every
   per-option verdict verify() emitted. It then re-runs the comparison with
   a 0.1% tolerance at each range bound (point doses keep their 5%), and
   reports what flips. Unrounded bounds (per-ha / 2.4711) are also tried and
   reported: they are NOT a fix, because the model and label_db usually
   round identically and exact bounds break that agreement.
   The score effect is an ESTIMATE: checks are re-folded with the corrected
   C1; verify() itself is not changed or re-run.

2. Searches data/final/sft_train.jsonl and sft_test.jsonl for the two wrong
   numbers (Fipronil 80% WG on onion at 303.509 g/acre; Acetamiprid 20% SP on
   cotton at 40.4678 g/acre) and attributes every option to its crop and pest
   through data/final/sft_generation_log.csv.

Read only. Writes only the --md tables.

Usage:
    python tools/phase12_step6_rounding_trace.py --md <tables.md>
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import phase12_stepA_score_rag as s12  # noqa: E402
import phase12_step5_validator_replay as s5  # noqa: E402

p10 = s12.p10
EVAL = p10.EVAL
HA_PER_ACRE = 2.4711
EDGE = 1e-3
RUNS = ("baseline", "sft", "rag_m", "rag_r")
LABEL = {"baseline": "baseline", "sft": "SFT", "rag_m": "RAG-B merged",
         "rag_r": "RAG-B merged + escalation repair† (not model output)"}


def nan(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


# --------------------------------------------------------------------------
# 1. C1, rebuilt per option
# --------------------------------------------------------------------------

def candidates(v, ctx, opt):
    gold = ctx.pest_match()
    rows = ctx.label_db.for_triple(ctx.crop_slug, gold.canonical_name,
                                   v.normalise_ai(opt.active_ingredient))
    return v._narrow_candidates(rows, opt.formulation, ctx.application_method) if rows else []


def option_c1(v, ctx, opt, rows, exact: bool = False, tol: float = 0.0):
    """_check_dose's per-option consensus. exact=True swaps the stored
    per-acre bounds for per-ha / 2.4711 on per_ha label rows; tol widens a
    RANGE by that fraction at each end (tol=0, exact=False is verify())."""
    df = ctx.label_db.df

    def value_ok(pred, lo, hi):
        if hi is None or tol == 0.0:
            return v._dose_value_ok(pred, lo, hi)
        return lo * (1 - tol) <= pred <= hi * (1 + tol)
    same_basis = [r for r in rows if v._basis_compatible(
        opt.dose.basis, str(df.at[r.index, "dose_formulation_basis"]))]
    verdicts, bounds = [], []
    for row in (same_basis or rows):
        r = df.loc[row.index]
        lo, hi, label_unit = v._label_dose_bounds(r, opt.dose.basis)
        if exact and opt.dose.basis == "per_acre" and str(r["dose_formulation_basis"]) == "per_ha":
            vmin, vmax = r["dose_formulation_value_min"], r["dose_formulation_value_max"]
            lo = None if nan(vmin) else float(vmin) / HA_PER_ACRE
            hi = None if nan(vmax) else float(vmax) / HA_PER_ACRE
        if lo is None or label_unit is None:
            verdicts.append(None)
            continue
        pred_lo, pred_dim = v._to_base(opt.dose.value_min, opt.dose.unit)
        label_lo, label_dim = v._to_base(lo, label_unit)
        label_hi, _ = v._to_base(hi, label_unit)
        if pred_lo is None or label_lo is None:
            verdicts.append(None)
            continue
        bounds.append((row.index, label_lo, label_hi, label_dim, r["dose_formulation_raw"]))
        if pred_dim != label_dim:
            verdicts.append(False)
            continue
        ok = value_ok(pred_lo, label_lo, label_hi)
        if ok and opt.dose.value_max is not None:
            pred_hi, _ = v._to_base(opt.dose.value_max, opt.dose.unit)
            ok = pred_hi is not None and value_ok(pred_hi, label_lo, label_hi)
        verdicts.append(ok)
    return v._consensus(verdicts), bounds


def tag(v, got) -> str:
    if got is False:
        return "False"
    if got == v.AMBIGUOUS:
        return "AMBIGUOUS"
    return "True" if got is True else "unscored"


_C1_LINE = re.compile(r"^(C1|AMBIGUOUS): '(.+?)' dose (-?[\d.e+-]+)")


def verifier_option_view(result, opt) -> str:
    for f in result.failures:
        m = _C1_LINE.match(f)
        if m and m.group(2) == opt.active_ingredient and abs(float(m.group(3)) - float(opt.dose.value_min)) < 1e-9:
            return "False" if m.group(1) == "C1" else "AMBIGUOUS"
    return "pass_or_unscored"


def refold(v, checks: dict, c1_new) -> float:
    ch = {k: x for k, x in checks.items() if k in v.CHECK_WEIGHTS}
    if c1_new is None:
        ch.pop("C1_dose", None)
    else:
        ch["C1_dose"] = c1_new
    den = sum(v.CHECK_WEIGHTS[k] for k in ch)
    return round(sum(v.CHECK_WEIGHTS[k] * x for k, x in ch.items()) / den, 6) if den else 1.0


def scan_run(v, res, bench, results) -> dict:
    """Every dose-graded option under three comparisons: verify()'s own
    (stored bounds, exact containment), 0.1% edge tolerance, and unrounded
    bounds. Plus the brief's literal criterion: C1 objects AND a stated end
    is within 0.1% of an exact per-ha/2.4711 bound of the same dimension."""
    recs, mismatches = [], []
    per_item = {}
    for iid, r in results.items():
        if r.excluded or not r.gates.get("G2_schema") or r.advisory is None:
            continue
        if not r.advisory.chemical_options:
            continue
        ctx = p10.ctx_for(v, res, bench[iid])
        scored = {"stored": [], "tol": [], "exact": []}
        for k, opt in enumerate(r.advisory.chemical_options):
            rows = candidates(v, ctx, opt)
            if not rows:
                continue
            got = {"stored": option_c1(v, ctx, opt, rows)[0],
                   "tol": option_c1(v, ctx, opt, rows, tol=EDGE)[0]}
            got["exact"], bnd_e = option_c1(v, ctx, opt, rows, exact=True)
            vs = "False" if got["stored"] is False else (
                "AMBIGUOUS" if got["stored"] == v.AMBIGUOUS else "pass_or_unscored")
            seen = verifier_option_view(r, opt)
            if vs != seen:
                mismatches.append((iid, k, opt.active_ingredient, vs, seen))
            for mode, g in got.items():
                if g is not None and g != v.AMBIGUOUS:
                    scored[mode].append(1.0 if g else 0.0)
            ends = [(b, d) for b, d in (v._to_base(x, opt.dose.unit)
                                        for x in (opt.dose.value_min, opt.dose.value_max)) if b is not None]
            near = any(b and dim == d and abs(e / b - 1) < EDGE
                       for e, d in ends for (_i, lo, hi, dim, _raw) in bnd_e for b in (lo, hi))
            same_number_other_unit = any(b and dim != d and abs(e / b - 1) < EDGE
                                         for e, d in ends for (_i, lo, hi, dim, _raw) in bnd_e for b in (lo, hi))
            recs.append({"item_id": iid, "k": k, "ai": opt.active_ingredient,
                         "dose": (opt.dose.value_min, opt.dose.value_max, opt.dose.unit, opt.dose.basis),
                         "stored": tag(v, got["stored"]), "tol": tag(v, got["tol"]),
                         "exact": tag(v, got["exact"]), "near_exact_bound": near,
                         "same_number_other_unit": same_number_other_unit,
                         "bounds_exact": [(lo, hi) for (_i, lo, hi, _d, _r) in bnd_e]})
        c1 = {m: (sum(x) / len(x) if x else None) for m, x in scored.items()}
        if r.checks.get("C1_dose") is not None:
            assert c1["stored"] is not None and abs(c1["stored"] - r.checks["C1_dose"]) < 1e-9, iid
        per_item[iid] = c1
    return {"recs": recs, "mismatches": mismatches, "per_item": per_item}


# --------------------------------------------------------------------------
# 2. training-data trace
# --------------------------------------------------------------------------

def sft_options(path: Path, log: dict) -> list[dict]:
    out = []
    for line in open(path, encoding="utf-8"):
        ex = json.loads(line)
        adv, user = None, ""
        for m in ex["messages"]:
            if m["role"] == "assistant":
                try:
                    adv = json.loads(m["content"])
                except json.JSONDecodeError:
                    adv = None
            elif m["role"] == "user":
                user = m["content"]
        if not isinstance(adv, dict):
            continue
        meta = log.get(ex["id"], {})
        for o in adv.get("chemical_options") or []:
            d = o.get("dose") or {}
            out.append({"id": ex["id"], "crop": meta.get("crop_slug"), "pest": meta.get("canonical_pest"),
                        "ai": o.get("active_ingredient"), "vmin": d.get("value_min"), "vmax": d.get("value_max"),
                        "unit": d.get("unit"), "basis": d.get("basis"), "raw": d.get("raw"), "query": user})
    return out


def key(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", type=Path, required=True)
    args = ap.parse_args()

    v = p10.load_verify()
    res = v.VerifyResources.load()
    bench, trained, baseline, tscores, bscores = p10.load_all()
    _pass1, prompts = s12.load_rag_b(bench)
    merged = {r["item_id"]: r["raw_response"] for r in p10.jsonl(s5.MERGED_RESP)}

    rep = p10.reproduce(v, res, bench, trained, tscores)
    assert all(n == 0 for n in rep["diffs"].values()) and round(rep["mean_nonexcluded"], 4) == 0.5203
    R = {"sft": rep.pop("results"),
         "baseline": s12.reproduce_baseline(v, res, bench, baseline, bscores),
         "rag_m": p10.rescore(v, res, bench, merged)}
    saved = {r["item_id"]: r for r in json.loads(s5.MERGED_SCORES.read_text(encoding="utf-8"))}
    assert all(R["rag_m"][i].total == saved[i]["total"] and R["rag_m"][i].checks == saved[i]["checks"]
               for i in bench)
    repaired = dict(merged)
    for i in bench:
        r = R["rag_m"][i]
        if r.gates.get("G2_schema") is False and r.failures[0].endswith(s5.PHI_MSG):
            repaired[i] = s5.repair(merged[i])
    R["rag_r"] = p10.rescore(v, res, bench, repaired)

    ALL = list(bench)
    pass1_ex = {r["item_id"]: r["excluded"] for r in json.loads((EVAL / "rag_B_scores.json").read_text(encoding="utf-8"))}
    nocrop40 = {i for i in ALL if prompts[i]["retrieval_status"] == "no_crop" and bench[i]["kind"] in s12.DOSE_KINDS}
    defects = {i for i in ALL if prompts[i]["known_bench_defect"]}
    head = [i for i in ALL if not R["baseline"][i].excluded and not R["sft"][i].excluded and not pass1_ex[i]
            and i not in nocrop40 and i not in defects]
    assert len(head) == 448

    md = []
    w = md.append

    # ================= 1 ===================================================
    w("## 1. The per-acre rounding defect\n")
    scans = {a: scan_run(v, res, bench, R[a]) for a in RUNS}
    w("| run | dose-graded options | replica == verify() | C1 objections | literal criterion† | of which the right number in the wrong unit‡ | rounding casualties: ✗ → ✓ at 0.1% edge tolerance | unrounded bounds instead: ✓ → ✗ | ✗ → ✓ |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for a in RUNS:
        sc = scans[a]
        recs = sc["recs"]
        assert not sc["mismatches"], (a, sc["mismatches"][:5])
        obj = [r for r in recs if r["stored"] == "False"]
        lit = [r for r in obj if r["near_exact_bound"]]
        unit = [r for r in obj if r["same_number_other_unit"] and not r["near_exact_bound"]]
        cas = [r for r in obj if r["tol"] == "True"]
        ex_break = [r for r in recs if r["stored"] == "True" and r["exact"] == "False"]
        ex_fix = [r for r in obj if r["exact"] == "True"]
        w(f"| {LABEL[a]} | {len(recs)} | {len(recs) - len(sc['mismatches'])}/{len(recs)} | {len(obj)} | "
          f"{len(lit)} opt / {len({r['item_id'] for r in lit})} items | {len(unit)} | "
          f"**{len(cas)} opt / {len({r['item_id'] for r in cas})} items** | {len(ex_break)} | {len(ex_fix)} |")
    w("\n† C1 objects AND a stated end is within 0.1% of an exact per-ha/2.4711 label bound, same dimension.")
    w("‡ the stated number is within 0.1% of a label bound but in g where the label says ml, or vice versa.\n")
    for a in RUNS:
        recs = scans[a]["recs"]
        obj = [r for r in recs if r["stored"] == "False"]
        lit = [r for r in obj if r["near_exact_bound"]]
        if lit:
            w(f"**{LABEL[a]}**, literal-criterion options and why C1 objects:")
            for r in lit:
                why = ("ROUNDING CASUALTY — passes with a 0.1% edge tolerance" if r["tol"] == "True"
                       else "not rounding — the other end of the stated range breaks the label (range-top overdose or underdose)")
                w(f"- {r['item_id']} {r['ai']} stated {r['dose']} | exact bounds "
                  f"{[(round(lo, 4) if lo else lo, round(hi, 4) if hi else hi) for lo, hi in r['bounds_exact']]} | {why}")
            w("")
        unit = [r for r in obj if r["same_number_other_unit"] and not r["near_exact_bound"]]
        if unit:
            w(f"**{LABEL[a]}**, right number in the wrong unit (not rounding): "
              + "; ".join(f"{r['item_id']} {r['ai']} {r['dose'][0]}{r['dose'][2]}" for r in unit))
            w("")
        cas = [r for r in obj if r["tol"] == "True"]
        for r in cas:
            w(f"- **casualty** {LABEL[a]}: {r['item_id']} {r['ai']} stated {r['dose']} | exact label bounds "
              f"{[(round(lo, 6) if lo else lo, round(hi, 6) if hi else hi) for lo, hi in r['bounds_exact']]}")
        ex_break = [r for r in recs if r["stored"] == "True" and r["exact"] == "False"]
        if ex_break:
            w(f"- {LABEL[a]}: switching to unrounded bounds would newly FAIL {len(ex_break)} options that match "
              f"label_db's 4-decimal value, e.g. " + "; ".join(
                  f"{r['item_id']} {r['ai']} {r['dose'][:2]} vs {[(round(lo, 6), round(hi, 6) if hi else hi) for lo, hi in r['bounds_exact']][:1]}"
                  for r in ex_break[:2]))

    w("\n### score effect of a 0.1% edge tolerance — ESTIMATE (checks re-folded with the corrected C1; verify() not re-run)\n")
    w("| run | items whose C1 changes | 448 headline: observed | estimate | Δ | all 500: observed | estimate | Δ |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|")
    est = {}
    for a in RUNS:
        new = {}
        for i in ALL:
            r = R[a][i]
            c1 = scans[a]["per_item"].get(i)
            if c1 is None or r.excluded or not all(r.gates.values()):
                new[i] = r.total
                continue
            c1_s, c1_t = c1["stored"], c1["tol"]
            new[i] = r.total if c1_t == c1_s else refold(v, r.checks, c1_t)
        changed = [i for i in ALL if new[i] != R[a][i].total]
        est[a] = new
        oh, eh = p10.mean(R[a][i].total for i in head), p10.mean(new[i] for i in head)
        oa, ea = p10.mean(R[a][i].total for i in ALL), p10.mean(new[i] for i in ALL)
        w(f"| {LABEL[a]} | {len(changed)} {sorted(changed)} | {oh:.4f} | {eh:.4f} | {eh - oh:+.4f} | {oa:.4f} | {ea:.4f} | {ea - oa:+.4f} |")
        for i in changed:
            w(f"  - {i}: total {R[a][i].total:.4f} → {new[i]:.4f} "
              f"(C1 {scans[a]['per_item'][i]['stored']:.4f} → {scans[a]['per_item'][i]['tol']:.4f})")
    d_obs = p10.mean(R["rag_m"][i].total for i in head) - p10.mean(R["sft"][i].total for i in head)
    d_est = p10.mean(est["rag_m"][i] for i in head) - p10.mean(est["sft"][i] for i in head)
    w(f"\nSFT-vs-RAG-B (merged) gap on 448: observed {d_obs:+.4f}, with the correction applied to both {d_est:+.4f}")

    # kg-unit exposure: how many label rows could trip this at all
    df = res.label_db.df
    kg_range = df[(df["dose_formulation_unit"].isin(["kg", "l"])) & (df["dose_formulation_basis"] == "per_ha")]
    w(f"\nlabel_db per_ha rows stated in kg or l (4-decimal per-acre storage = 0.1 g/ml resolution): {len(kg_range)} "
      f"of {len(df)}; of which ranges {int(kg_range['dose_formulation_value_max'].notna().sum())}")
    worst = []
    for _, row in df[df["dose_formulation_basis"] == "per_ha"].iterrows():
        for col_s, col_h in (("dose_formulation_per_acre_min", "dose_formulation_value_min"),
                             ("dose_formulation_per_acre_max", "dose_formulation_value_max")):
            if nan(row[col_s]) or nan(row[col_h]) or not row[col_h]:
                continue
            exact = float(row[col_h]) / HA_PER_ACRE
            worst.append(abs(float(row[col_s]) / exact - 1))
    w(f"stored vs exact per-acre, every per_ha bound: max relative error {max(worst):.2e}, "
      f"bounds off by >1e-5: {sum(x > 1e-5 for x in worst)} of {len(worst)}")

    # ================= 2 ===================================================
    w("\n## 2. Where the wrong numbers came from\n")
    log = {f"S{r['slice']}_{r['row_id']}": r for r in csv.DictReader(
        open(ROOT / "data" / "final" / "sft_generation_log.csv", encoding="utf-8"))}
    for split in ("sft_train", "sft_test"):
        path = ROOT / "data" / "final" / f"{split}.jsonl"
        raw = path.read_text(encoding="utf-8")
        opts = sft_options(path, log)
        w(f"### {split} ({sum(1 for _ in open(path, encoding='utf-8'))} examples, {len(opts)} chemical options)\n")
        w(f"- raw string counts: '303.509' {raw.count('303.509')}, '303.5086' {raw.count('303.5086')}, "
          f"'30.3509' {raw.count('30.3509')}, '40.4678' {raw.count('40.4678')}, '20.2339' {raw.count('20.2339')}")
        fip = [o for o in opts if key(o["ai"]).startswith("fipronil80")]
        w(f"- Fipronil 80% WG options by (crop, value_min, unit, basis): "
          f"{dict(Counter((o['crop'], o['vmin'], o['unit'], o['basis']) for o in fip))}")
        w(f"- Fipronil 80% WG at ~303.5 anywhere: {sum(1 for o in fip if o['vmin'] and abs(o['vmin'] - 303.509) < 0.01)}")
        ace = [o for o in opts if key(o["ai"]).startswith("acetamiprid20")]
        w(f"- Acetamiprid 20% SP options by (crop, pest, value_min, basis): "
          f"{dict(Counter((o['crop'], o['pest'], o['vmin'], o['basis']) for o in ace))}")
        w(f"- Acetamiprid 20% SP at 40.4678 on cotton by pest: "
          f"{dict(Counter(o['pest'] for o in ace if o['crop'] == 'cotton' and o['vmin'] == 40.4678))}")
        for label, pick in (("Fipronil 80% WG, onion", [o for o in fip if o["crop"] == "onion"][:2]),
                            ("Acetamiprid 20% SP, cotton whitefly", [o for o in ace if o["crop"] == "cotton" and o["pest"] == "Whitefly"][:2]),
                            ("Acetamiprid 20% SP, cotton jassid/aphid", [o for o in ace if o["crop"] == "cotton" and o["pest"] in ("Jassid", "Aphid")][:2])):
            for o in pick:
                w(f"  - example [{label}] {o['id']}: query {o['query'][:60]!r} → {o['ai']} "
                  f"{o['vmin']}{'-' + str(o['vmax']) if o['vmax'] else ''} {o['unit']} {o['basis']} (raw {o['raw']!r})")
        w("")

    # model runs, same products
    def run_opts(raws):
        out = []
        for i, s in raws.items():
            try:
                a = json.loads(s)
            except (json.JSONDecodeError, TypeError):
                continue
            for o in a.get("chemical_options") or []:
                out.append((i, bench[i]["crop_slug"], bench[i]["canonical_pest"], o["active_ingredient"],
                            (o.get("dose") or {}).get("value_min")))
        return out
    for name, raws in (("SFT run", trained), ("RAG-B merged run", merged)):
        ro = run_opts(raws)
        w(f"- {name}: Fipronil 80% WG by (crop, value_min): "
          f"{dict(Counter((c, x) for _i, c, _p, a, x in ro if key(a).startswith('fipronil80')))}")
        w(f"- {name}: Acetamiprid 20% SP on cotton by (pest, value_min): "
          f"{dict(Counter((p, x) for _i, c, p, a, x in ro if key(a).startswith('acetamiprid20') and c == 'cotton'))}")
    lab = df[df["active_ingredient"].str.contains("Acetamiprid 20% SP", na=False) & (df["crop_slug"] == "cotton")]
    w("- label_db Acetamiprid 20% SP on cotton: " + "; ".join(
        f"{r['pest_or_disease']!r} {r['dose_formulation_value_min']:g} g/ha = {r['dose_formulation_per_acre_min']} g/acre"
        for _, r in lab.iterrows()))
    fl = df[df["active_ingredient"].str.contains("Fipronil 80% WG", na=False)]
    w("- label_db Fipronil 80% WG: " + "; ".join(
        f"{r['crop_slug']} {r['dose_formulation_raw']!r} → {r['dose_formulation_per_acre_min']}"
        f"{'-' + str(r['dose_formulation_per_acre_max']) if not nan(r['dose_formulation_per_acre_max']) else ''} g/acre"
        for _, r in fl.iterrows()))
    w(f"- 75 g/ha / 2.4711 = {75 / HA_PER_ACRE:.6f}; ×10 = {750 / HA_PER_ACRE:.6f}; 10 × 30.3509 = {10 * 30.3509:.4f}")

    args.md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print("wrote", args.md)


if __name__ == "__main__":
    main()
