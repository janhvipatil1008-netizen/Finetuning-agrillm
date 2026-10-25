"""phase12_step5_validator_replay.py — offline replay of two inference-time
validators over the merged Arm B answers. No model, no GPU.

  A. Escalation repair. For every merged answer that fails G2 ONLY on the
     schema invariant "unknown PHI requires escalate_to_expert=True", set
     escalate_to_expert=true on a copy and re-score with the unchanged
     harness. The repaired answers are NOT model output and are never
     written to data/.

  B. Dose validator. Match every chemical option in every merged answer,
     including the schema-invalid ones verify() never dose-grades, to its
     fact-sheet row and compare the stated dose to that row at +/-8%, after
     per_ha / per_acre conversion. The fact sheet is the reference because
     it is what a deployed validator would have in hand.

Reads data/final/eval/rag_B_merged_responses.jsonl, rag_B_merged_scores.json,
trained_responses.jsonl and data/interim/rag_prompts_B.jsonl. Writes only
the --md tables. Asserts first that the harness still reproduces
trained_scores.json (0.5203) and rag_B_merged_scores.json field for field.

Usage:
    python tools/phase12_step5_validator_replay.py --md <tables.md>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import phase12_stepA_score_rag as s12  # noqa: E402

p10 = s12.p10
EVAL = p10.EVAL
MERGED_RESP = EVAL / "rag_B_merged_responses.jsonl"
MERGED_SCORES = EVAL / "rag_B_merged_scores.json"
PHI_MSG = "unknown PHI requires escalate_to_expert=True"
ESC_FALSE = '"escalate_to_expert":false'
BAND = 0.08
HA_PER_ACRE = 2.4711
# The 9 genuine overdose items of Step 4c (4c.6) plus S1_528, found only by
# the sheet check because its answer never reached C1.
KNOWN_OVERDOSE = {"B3_3": "CHLORANTRANILIPROLE 47.85 % w/w SC", "B4c_2": "Fipronil 80% WG",
                  "S1_201": "Fipronil 80% WG", "S1_352": "Fipronil 80% WG",
                  "S1_482": "Fipronil 80% WG", "S1_546": "Fipronil 80% WG",
                  "S1_5606": "Fipronil 80% WG", "S1_580": "Fipronil 80% WG",
                  "S1_718": "Fipronil 80% WG", "S1_528": "Deltamethrin 11% w/w EC"}
KNOWN_PER_HA = {"S1_199", "S1_5272", "S1_486", "B3_3", "B4b_3"}
ARMS = ("baseline", "sft", "rag_m", "rag_r")
LABEL = {"baseline": "baseline", "sft": "SFT", "rag_m": "RAG-B (merged)",
         "rag_r": "RAG-B (merged + escalation repair) — repaired, not model output"}
SHORT = {"baseline": "baseline", "sft": "SFT", "rag_m": "RAG-B merged", "rag_r": "repaired†"}

fmt, delta = s12.fmt, s12.delta


def norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9.]", "", str(s).lower())


# --------------------------------------------------------------------------
# A. escalation repair
# --------------------------------------------------------------------------

def repair(raw: str) -> str:
    """The one-field copy: escalate_to_expert false -> true, nothing else."""
    if raw.count(ESC_FALSE) == 1:
        out = raw.replace(ESC_FALSE, '"escalate_to_expert":true')
    else:
        adv = json.loads(raw)
        adv["escalate_to_expert"] = True
        out = json.dumps(adv, ensure_ascii=False, separators=(",", ":"))
    a, b = json.loads(raw), json.loads(out)
    assert a.pop("escalate_to_expert") is False and b.pop("escalate_to_expert") is True
    assert a == b, "repair changed more than escalate_to_expert"
    return out


# --------------------------------------------------------------------------
# B. dose validator
# --------------------------------------------------------------------------

def candidate_rows(v, opt: dict, sheet: list[dict], method):
    """Sheet rows for this option's product, most specific match first.

    Tier 1: the option names the sheet row exactly (case/space-insensitive).
    Tier 2: same molecule set, formulation code and first strength
            (verify.formulation_key) — catches 'Clothianidin 50 %WDG' vs
            'Clothianidin 50% WDG', and also an altered second strength.
    Then: the query's application method where stated, and the option's
    own PHI, to separate foliar from drench claims of one product.
    """
    name = norm_name(opt.get("active_ingredient"))
    rows = [r for r in sheet if norm_name(r["ai"]) == name]
    tier = "exact name" if rows else None
    if not rows:
        comps = v.normalise_ai(opt.get("active_ingredient"))
        fk = v.formulation_key(opt.get("active_ingredient"))
        rows = [r for r in sheet if v.normalise_ai(r["ai"]) == comps and v.formulation_key(r["ai"]) == fk]
        tier = "formulation key" if rows else None
    if not rows:
        return [], None, False
    if method:
        hits = [r for r in rows if r["application_method"] == method]
        rows = hits or rows
    if len(rows) > 1:
        hits = [r for r in rows if r["phi_days"] == opt.get("phi_days")]
        rows = hits or rows
    return rows, tier, len(rows) > 1


def to_base(v, value, unit):
    if value is None:
        return None, None
    return v._to_base(value, unit)


def row_bounds(v, row: dict, basis: str):
    """(lo, hi, dim) in the option's basis and base unit, or a reason."""
    rb, unit = row["dose_basis"], row["dose_unit"] or None
    if rb in (None, "free_text", "unstated"):
        return None, None, None, f"sheet dose is {rb or 'missing'} ({row['dose_raw']!r})"
    if basis == "per_acre" and rb == "per_ha":
        lo, hi = row["dose_per_acre_min"], row["dose_per_acre_max"]
    elif basis == "per_ha" and rb == "per_ha":
        lo, hi = row["dose_min"], row["dose_max"]
    elif basis == rb:
        lo, hi = row["dose_min"], row["dose_max"]
    else:
        return None, None, None, f"basis {basis} vs sheet {rb}"
    if lo is None:
        return None, None, None, "sheet row has no number"
    lo_b, dim = to_base(v, lo, unit)
    hi_b, _ = to_base(v, hi, unit)
    if lo_b is None:
        return None, None, None, f"sheet unit {unit!r} not convertible"
    return lo_b, hi_b, dim, None


def judge(v, opt: dict, row: dict) -> dict:
    d = opt.get("dose") or {}
    basis, unit = d.get("basis"), d.get("unit")
    if basis in (None, "unstated") or d.get("value_min") is None:
        return {"verdict": "NO_STATED_DOSE"}
    lo, hi, dim, why = row_bounds(v, row, basis)
    if why:
        return {"verdict": "BASIS_MISMATCH" if why.startswith("basis") else "UNVERIFIABLE", "note": why}
    vmin, mdim = to_base(v, d["value_min"], unit)
    vmax, _ = to_base(v, d.get("value_max"), unit)
    if vmin is None:
        return {"verdict": "UNVERIFIABLE", "note": f"stated unit {unit!r}"}
    if mdim != dim:
        return {"verdict": "UNIT_MISMATCH", "note": f"stated {unit}, sheet {row['dose_unit']}"}
    top = hi if hi is not None else lo
    ends = [x for x in (vmin, vmax) if x is not None]
    over = max(ends) / top - 1.0
    under = min(ends) / lo - 1.0
    if over > BAND:
        return {"verdict": "HIGH", "pct": over * 100, "stated": ends, "sheet": (lo, hi)}
    if under < -BAND:
        return {"verdict": "LOW", "pct": under * 100, "stated": ends, "sheet": (lo, hi)}
    return {"verdict": "OK", "pct": over * 100, "stated": ends, "sheet": (lo, hi)}


def validate(v, raw: dict, prompts: dict, bench: dict) -> list[dict]:
    out = []
    for iid, s in raw.items():
        adv = json.loads(s)
        sheet = s12.sheet_rows(prompts[iid]["user_message"])
        method = prompts[iid]["method_used"]
        for k, opt in enumerate(adv.get("chemical_options") or []):
            rec = {"item_id": iid, "k": k, "ai": opt.get("active_ingredient"), "crop": bench[iid]["crop_slug"],
                   "dose": opt.get("dose"), "phi_days": opt.get("phi_days"), "sheet_rows": len(sheet)}
            if not sheet:
                rec.update(verdict="NO_SHEET", tier=None)
                out.append(rec)
                continue
            rows, tier, multi = candidate_rows(v, opt, sheet, method)
            rec["tier"] = tier
            if not rows:
                rec.update(verdict="NOT_IN_SHEET")
                out.append(rec)
                continue
            js = [judge(v, opt, r) for r in rows]
            # Several surviving rows (same product, same PHI): accept if the
            # dose fits ANY of them, and say so — that is the lenient reading.
            ok = [j for j in js if j["verdict"] == "OK"]
            j = ok[0] if ok else js[0]
            rec.update(j, multi_row=multi, n_rows=len(rows),
                       name_differs=tier == "formulation key",
                       sheet_ai=rows[0]["ai"],
                       sheet_per_acre=(rows[0]["dose_per_acre_min"], rows[0]["dose_per_acre_max"]),
                       sheet_unit=rows[0]["dose_unit"])
            out.append(rec)
    return out


_C1_LINE = re.compile(r"^(C1|AMBIGUOUS): '(.+?)' dose (-?[\d.]+)")
_G8_LINE = re.compile(r"^G8: '(.+?)' dose stated")


def verifier_view(result, opt: dict) -> str:
    """verify()'s verdict on ONE option's dose.

    Keyed by (a.i., value_min), not a.i. alone: a response can list one
    product twice (foliar and drench claims), and only one of the two may
    draw the objection. G8 counts — a basis the label does not use is the
    verifier objecting to the dose, at the gate instead of at C1.
    """
    if "C1_dose" not in result.checks and not any(f.startswith("G8:") for f in result.failures):
        return "not graded"
    ai = opt.get("active_ingredient")
    vmin = (opt.get("dose") or {}).get("value_min")
    for f in result.failures:
        g = _G8_LINE.match(f)
        if g and g.group(1) == ai:
            return "objects (G8)"
        m = _C1_LINE.match(f)
        if m and m.group(2) == ai and vmin is not None and abs(float(m.group(3)) - float(vmin)) < 1e-6:
            return "objects" if m.group(1) == "C1" else "ambiguous"
    return "no objection"


# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", type=Path, required=True)
    args = ap.parse_args()

    v = p10.load_verify()
    res = v.VerifyResources.load()
    bench, trained, baseline, tscores, bscores = p10.load_all()
    _pass1, prompts = s12.load_rag_b(bench)
    merged = {r["item_id"]: r for r in p10.jsonl(MERGED_RESP)}
    assert set(merged) == set(bench) and len(merged) == 500
    rag_m = {i: merged[i]["raw_response"] for i in bench}
    src = {i: merged[i]["source_pass"] for i in bench}

    rep = p10.reproduce(v, res, bench, trained, tscores)
    assert all(n == 0 for n in rep["diffs"].values()) and round(rep["mean_nonexcluded"], 4) == 0.5203
    R = {"sft": rep.pop("results"),
         "baseline": s12.reproduce_baseline(v, res, bench, baseline, bscores),
         "rag_m": p10.rescore(v, res, bench, rag_m)}
    saved = {r["item_id"]: r for r in json.loads(MERGED_SCORES.read_text(encoding="utf-8"))}
    for i in bench:
        g, w = R["rag_m"][i], saved[i]
        assert (g.total, g.passed, g.gates, g.checks, g.excluded, g.failures) == \
               (w["total"], w["passed"], w["gates"], w["checks"], w["excluded"], w["failures"]), i

    ALL = list(bench)
    nonex3 = [i for i in ALL if not R["baseline"][i].excluded and not R["sft"][i].excluded
              and not saved_pass1_excluded(i)]
    nocrop40 = {i for i in ALL if prompts[i]["retrieval_status"] == "no_crop"
                and bench[i]["kind"] in s12.DOSE_KINDS}
    defects = {i for i in ALL if prompts[i]["known_bench_defect"]}
    head = [i for i in nonex3 if i not in nocrop40 and i not in defects]
    assert len(head) == 448, len(head)
    H = set(head)

    md = []
    w = md.append

    # ================= A ===================================================
    g2 = [i for i in ALL if R["rag_m"][i].gates.get("G2_schema") is False]
    only_phi = [i for i in g2 if R["rag_m"][i].failures[0].endswith(PHI_MSG)
                and "1 error(s)" in R["rag_m"][i].failures[0]]
    rag_r = dict(rag_m)
    for i in only_phi:
        rag_r[i] = repair(rag_m[i])
    R["rag_r"] = p10.rescore(v, res, bench, rag_r)
    for i in ALL:
        if i not in set(only_phi):
            assert R["rag_r"][i].total == R["rag_m"][i].total, i
    still = [i for i in only_phi if not R["rag_r"][i].gates.get("G2_schema")]

    w("## A. Escalation repair — repaired, not model output\n")
    w(f"- merged G2 failures: {len(g2)}; failing ONLY on '{PHI_MSG}': {len(only_phi)}; "
      f"repaired by the one-field copy; still failing G2 after repair: {still}")
    w(f"- repaired items inside the 448: {sum(i in H for i in only_phi)}; by source pass "
      f"{dict(sorted(Counter(src[i] for i in only_phi).items()))}\n")
    lines = ["| item set | n | " + " | ".join(SHORT[a] for a in ARMS) + " | Δ repaired−SFT | Δ repaired−merged |",
             "|---|---:|" + "---:|" * (len(ARMS) + 2)]
    for name, ids in (("**448 headline**", head), ("all 500", ALL),
                      ("the 44 repaired (all)", only_phi),
                      ("the repaired inside 448", [i for i in only_phi if i in H])):
        m = {a: p10.mean(R[a][i].total for i in ids) for a in ARMS}
        lines.append(f"| {name} | {len(ids)} | " + " | ".join(fmt(m[a]) for a in ARMS) +
                     f" | {delta(m['rag_r'], m['sft'])} | {delta(m['rag_r'], m['rag_m'])} |")
    w("\n".join(lines))
    up = sum(R["rag_r"][i].total > R["sft"][i].total for i in head)
    dn = sum(R["rag_r"][i].total < R["sft"][i].total for i in head)
    w(f"\npaired repaired vs SFT on 448: up {up}, down {dn}, equal {len(head) - up - dn}")
    w(f"at 1.0 on 448: " + ", ".join(f"{SHORT[a]} {sum(R[a][i].total == 1.0 for i in head)}" for a in ARMS))
    w(f"at 0.0 on 448: " + ", ".join(f"{SHORT[a]} {sum(R[a][i].total == 0.0 for i in head)}" for a in ARMS))

    # C4 side effects
    gold = {i: bool(bench[i]["gold_advisory"]["escalate_to_expert"]) for i in ALL}
    c4_0 = [i for i in only_phi if R["rag_r"][i].checks.get("C4_escalation") == 0.0]
    w(f"\n**C4 side effect:** gold escalates on {sum(gold[i] for i in only_phi)}/{len(only_phi)} repaired items; "
      f"C4 = 0 (over-escalation) on {len(c4_0)}: {sorted(c4_0)}")
    over_msgs = sum(any("over-escalation" in f for f in R["rag_r"][i].failures) for i in only_phi)
    w(f"over-escalation messages on repaired items: {over_msgs}")
    w(f"C4 mean on the repaired items: {fmt(p10.mean(R['rag_r'][i].checks['C4_escalation'] for i in only_phi))}; "
      f"C4 over all 500: merged {fmt(p10.mean(R['rag_m'][i].checks['C4_escalation'] for i in ALL if 'C4_escalation' in R['rag_m'][i].checks))} "
      f"(n={sum('C4_escalation' in R['rag_m'][i].checks for i in ALL)}), repaired "
      f"{fmt(p10.mean(R['rag_r'][i].checks['C4_escalation'] for i in ALL if 'C4_escalation' in R['rag_r'][i].checks))} "
      f"(n={sum('C4_escalation' in R['rag_r'][i].checks for i in ALL)})")
    w(f"C4 over-escalation failures, all 500: merged "
      f"{sum(any('over-escalation' in f for f in R['rag_m'][i].failures) for i in ALL)}, repaired "
      f"{sum(any('over-escalation' in f for f in R['rag_r'][i].failures) for i in ALL)}")
    w("\ngates after repair on the 44: " + str(dict(Counter(g for i in only_phi for g, ok in R['rag_r'][i].gates.items() if not ok))))
    w("")
    w("| item | pass | in 448 | options | gold escalates | SFT | merged | repaired | C1 | C2 | C3 | C4 | C5 | C6 | failing gates after repair |")
    w("|---|---:|:-:|---:|:-:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for i in sorted(only_phi, key=lambda i: (-R["rag_r"][i].total, i)):
        r = R["rag_r"][i]
        c = lambda k: f"{r.checks[k]:.2f}" if k in r.checks else "—"
        n_opt = len(json.loads(rag_m[i]).get("chemical_options") or [])
        w(f"| {i} | {src[i]} | {'✓' if i in H else ''} | {n_opt} | {'yes' if gold[i] else 'no'} | "
          f"{R['sft'][i].total:.3f} | {R['rag_m'][i].total:.3f} | {r.total:.3f} | {c('C1_dose')} | {c('C2_phi')} | "
          f"{c('C3_formulation')} | {c('C4_escalation')} | {c('C5_causes_top1')} | {c('C6_non_chemical')} | "
          f"{', '.join(g for g, ok in r.gates.items() if not ok) or '—'} |")
    gate_fail_after = Counter(g for i in only_phi for g, ok in R["rag_r"][i].gates.items() if not ok)
    w(f"\nrepaired items scoring 0.0 after repair: {sum(R['rag_r'][i].total == 0.0 for i in only_phi)}; "
      f"their failing gates {dict(gate_fail_after)}")
    w(f"S1_237 after repair: total {R['rag_r']['S1_237'].total}, gates failing "
      f"{[g for g, ok in R['rag_r']['S1_237'].gates.items() if not ok]}, checks {R['rag_r']['S1_237'].checks}")
    w(f"S1_237 failures after repair mentioning Fipronil/Lambda: "
      f"{[f for f in R['rag_r']['S1_237'].failures if 'ipronil' in f.lower() or 'lambda' in f.lower()]}")
    w("")

    # ================= B ===================================================
    recs = validate(v, rag_m, prompts, bench)
    w("## B. Dose validator replay (fact sheet, ±8%)\n")
    n_opt = len(recs)
    w(f"- options checked: {n_opt} across {len({r['item_id'] for r in recs})} items "
      f"(includes the {len(g2)} G2-failed answers: "
      f"{sum(1 for r in recs if r['item_id'] in set(g2))} options)")
    w(f"- verdicts: {dict(Counter(r['verdict'] for r in recs).most_common())}")
    w(f"- match tier: {dict(Counter(r.get('tier') for r in recs if r['verdict'] not in ('NO_SHEET',)))}")
    w(f"- options matching >1 sheet row after method + PHI narrowing (accepted if any fits): "
      f"{sum(1 for r in recs if r.get('multi_row'))}")
    flagged = [r for r in recs if r["verdict"] in ("HIGH", "LOW", "UNIT_MISMATCH", "BASIS_MISMATCH")]
    w(f"- flagged (HIGH / LOW / UNIT / BASIS): {len(flagged)} options on {len({r['item_id'] for r in flagged})} items; "
      f"HIGH {sum(r['verdict'] == 'HIGH' for r in recs)} options on "
      f"{len({r['item_id'] for r in recs if r['verdict'] == 'HIGH'})} items")
    w(f"- names that differ from their sheet row (matched only by formulation key): "
      f"{[(r['item_id'], r['ai'], r['sheet_ai']) for r in recs if r.get('name_differs') and norm_name(r['ai']).replace('.', '') != norm_name(r['sheet_ai']).replace('.', '')][:20]}")

    # known overdoses
    w("\n### the 10 known overdoses\n")
    w("| item | pass | a.i. | validator | stated | sheet per-acre | delta |")
    w("|---|---:|---|---|---|---|---:|")
    caught = 0
    for i, ai in KNOWN_OVERDOSE.items():
        hits = [r for r in recs if r["item_id"] == i and norm_name(r["ai"]) == norm_name(ai)]
        r = hits[0] if hits else None
        caught += bool(r and r["verdict"] == "HIGH")
        st_ = r["dose"] if r else {}
        w(f"| {i} | {src[i]} | {ai} | {r['verdict'] if r else 'NOT FOUND'} | "
          f"{st_.get('value_min')}{'-' + str(st_.get('value_max')) if st_.get('value_max') else ''} "
          f"{st_.get('unit')} {st_.get('basis')} | {r.get('sheet_per_acre') if r else ''} {r.get('sheet_unit') if r else ''} | "
          f"{format(r['pct'], '+.1f') + '%' if r and r.get('pct') is not None else '—'} |")
    w(f"\ncaught {caught}/10")
    ph = [r for r in recs if r["item_id"] in KNOWN_PER_HA and r["verdict"] == "HIGH"]
    w(f"per-ha-as-per-acre items {sorted(KNOWN_PER_HA)}: HIGH options there {len(ph)}: "
      + "; ".join(f"{r['item_id']} {r['ai']} {r['pct']:+.0f}%" for r in ph))

    # agreement with the verifier, on the repaired run (every answer now dose-graded)
    w("\n### agreement with verify(), per option, on the repaired run (so the 44 are dose-graded too)\n")
    agree = Counter()
    fp, fn = [], []
    view_of = {}
    for r in recs:
        opt = {"active_ingredient": r["ai"], "dose": r["dose"]}
        view = verifier_view(R["rag_r"][r["item_id"]], opt)
        view_of[(r["item_id"], r["k"])] = view
        if view == "not graded" or r["verdict"] in ("NO_SHEET", "NOT_IN_SHEET", "NO_STATED_DOSE"):
            continue
        val = "flag" if r["verdict"] in ("HIGH", "LOW", "UNIT_MISMATCH", "BASIS_MISMATCH") else r["verdict"].lower()
        agree[(view, val)] += 1
        if val == "flag" and view == "no objection":
            fp.append(r)
        if view.startswith("objects") and val != "flag":
            fn.append(r)
    w("| verify() | validator | options |")
    w("|---|---|---:|")
    for (a, b), n in sorted(agree.items(), key=lambda kv: -kv[1]):
        w(f"| {a} | {b} | {n} |")
    w(f"\nvalidator flags the verifier did not object to: {len(fp)}")
    for r in fp:
        w(f"  - {r['item_id']} (pass {src[r['item_id']]}) {r['ai']} | {r['verdict']} {r.get('pct', 0) or 0:+.1f}% | "
          f"stated {r['dose']} | sheet {r.get('sheet_ai')} per-acre {r.get('sheet_per_acre')} {r.get('sheet_unit')} | "
          f"phi {r['phi_days']} | rows {r.get('n_rows')} | note {r.get('note', '')}")
    w(f"\nverifier objections the validator passed or could not check: {len(fn)}")
    for r in fn:
        res_i = R["rag_r"][r["item_id"]]
        line = next((f for f in res_i.failures if f.startswith(f"C1: '{r['ai']}'")
                     and _C1_LINE.match(f) and abs(float(_C1_LINE.match(f).group(3)) - float(r["dose"]["value_min"])) < 1e-6), "")
        w(f"  - {r['item_id']} {r['ai']} | validator {r['verdict']} "
          f"{'' if r.get('pct') is None else format(r['pct'], '+.3f') + '%'} | stated {r['dose']} | {line[:170]}")

    # Rounding edges inside verify(): a RANGE objection where the end that
    # breaks the range sits within 0.1% of the bound it breaks. Point doses
    # carry a 5% tolerance, so they cannot fail on a 0.1% edge.
    w("\n### C1 range objections failing by under 0.1% (rounding edges), every C1 line\n")
    for a in ("sft", "rag_m", "rag_r"):
        edges = []
        for c in s12.c1_objections(R[a], bench, only_zero=False):
            if c["label_hi"] is None:
                continue
            mv, mdim = v._to_base(c["model_value"], c["model_unit"])
            mx = v._to_base(c["model_value_max"], c["model_unit"])[0] if c["model_value_max"] else mv
            lo, ldim = v._to_base(c["label_lo"], c["label_unit"])
            hi, _ = v._to_base(c["label_hi"], c["label_unit"])
            if mv is None or lo is None or mdim != ldim:
                continue
            low_edge = mv < lo and mv / lo > 0.999
            high_edge = mx > hi and mx / hi < 1.001
            if (low_edge or high_edge) and not (mv < lo * 0.999 or mx > hi * 1.001):
                edges.append(c)
        w(f"- {SHORT[a]}: {len(edges)} — " + "; ".join(
            f"{c['item_id']} {c['ai']} {c['model_value']:g}{c['model_unit']} vs {c['label_lo']:g}"
            f"{'-' + format(c['label_hi'], 'g') if c['label_hi'] else ''}{c['label_unit']} ({c['classification']})"
            for c in edges))
    nis = [r for r in recs if r["verdict"] == "NOT_IN_SHEET"]
    w(f"\noptions whose product is not on the item's fact sheet: {len(nis)} on {len({r['item_id'] for r in nis})} items: "
      + "; ".join(f"{r['item_id']} {r['ai']}" for r in nis[:15]))
    ns = [r for r in recs if r["verdict"] == "NO_SHEET"]
    w(f"options on items with an empty fact sheet: {len(ns)} on {len({r['item_id'] for r in ns})} items")
    other = [r for r in recs if r["verdict"] in ("UNVERIFIABLE", "NO_STATED_DOSE")]
    w(f"unverifiable / no stated dose: {len(other)} — " + "; ".join(
        f"{r['item_id']} {r['ai'][:30]} {r['verdict']} {r.get('note', '')}" for r in other[:10]))

    # all flags list
    w("\n### every flagged option\n")
    w("| item | pass | G2 in merged | a.i. | verdict | stated | sheet per-acre | delta | verify() C1 (repaired run) |")
    w("|---|---:|:-:|---|---|---|---|---:|---|")
    for r in sorted(flagged, key=lambda r: (r["verdict"], -(r.get("pct") or 0), r["item_id"])):
        d = r["dose"] or {}
        view = view_of[(r["item_id"], r["k"])]
        w(f"| {r['item_id']} | {src[r['item_id']]} | {'✓' if R['rag_m'][r['item_id']].gates.get('G2_schema') else '✗'} | "
          f"{r['ai']} | {r['verdict']} | {d.get('value_min')}{'-' + str(d.get('value_max')) if d.get('value_max') else ''} "
          f"{d.get('unit')} {d.get('basis')} | {r.get('sheet_per_acre')} {r.get('sheet_unit') or ''} | "
          f"{format(r['pct'], '+.1f') + '%' if r.get('pct') is not None else '—'} | {view} |")

    # Fipronil onion
    w("\n### Fipronil 80% WG on onion, every option\n")
    w("| item | pass | stated | raw | sheet per-acre (per-ha) | validator | verify() C1 (repaired run) |")
    w("|---|---:|---|---|---|---|---|")
    for r in recs:
        if norm_name(r["ai"]).startswith("fipronil80") and r["crop"] == "onion":
            d = r["dose"]
            row = next(x for x in s12.sheet_rows(prompts[r["item_id"]]["user_message"])
                       if norm_name(x["ai"]) == norm_name(r["sheet_ai"]))
            view = view_of[(r["item_id"], r["k"])]
            w(f"| {r['item_id']} | {src[r['item_id']]} | {d['value_min']} {d['unit']} {d['basis']} | {d.get('raw')!r} | "
              f"{row['dose_per_acre_min']} ({row['dose_min']} per ha) {row['dose_unit']} | {r['verdict']} "
              f"{format(r['pct'], '+.1f') + '%' if r.get('pct') is not None else ''} | {view} |")

    # ================= adjacency check for the report ======================
    w("\n## C. Adjacency checks (for the S1_237 / Flubendiamide wording)\n")
    for i in ("S1_5272", "S1_486", "B3_3", "B4b_3"):
        names = [x["ai"] for x in s12.sheet_rows(prompts[i]["user_message"])]
        sc = [k for k, n in enumerate(names) if "flubendiamide39" in norm_name(n).replace("%", "")]
        wg = [k for k, n in enumerate(names) if "flubendiamide20" in norm_name(n).replace("%", "")]
        w(f"- {i}: Flubendiamide 39.35% SC at sheet rows {[k + 1 for k in sc]}, 20% WG at {[k + 1 for k in wg]}")

    args.md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print("wrote", args.md)


_PASS1_SCORES = None


def saved_pass1_excluded(i: str) -> bool:
    global _PASS1_SCORES
    if _PASS1_SCORES is None:
        _PASS1_SCORES = {r["item_id"]: r["excluded"] for r in
                         json.loads((EVAL / "rag_B_scores.json").read_text(encoding="utf-8"))}
    return _PASS1_SCORES[i]


if __name__ == "__main__":
    main()
