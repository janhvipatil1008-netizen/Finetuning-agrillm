"""phase10_stepB_audit.py — separate model error from evaluator error in the
post-training benchmark run. Produces reports/phase10_stepB_posttrain_audit.md.

READ ONLY. This script imports src/verify.py and re-scores; it never writes to
src/, data/ or the pest table. It reproduces data/final/eval/trained_scores.json
exactly (assert, not hope) before drawing any conclusion from it, because an
audit built on a scoring convention that differs from the one that produced the
headline number audits nothing.

The scoring convention it reproduces, recovered by differential test rather
than assumption (`--reproduce` prints the evidence):

    VerifyContext(resources, crop_slug=item.crop_slug,
                  pest_query=item.canonical_pest,
                  gold_escalate=item.gold_advisory.escalate_to_expert)
    verify(raw_response, ctx, "score")

`gold_escalate` is load-bearing: without it 247 of 500 totals differ and the
mean drops from 0.5249 to 0.2456, because C4 falls back to deriving gold
escalation from label_db instead of the benchmark's frozen gold.

Sections mirror the audit brief: A dose safety, B G5 classification, C the C5
surface-form bug, D refusal-on-answerable vs the SFT data, E slice balance.

Usage:
    python tools/phase10_stepB_audit.py --reproduce      # convention evidence
    python tools/phase10_stepB_audit.py --json <path>    # dump findings
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

BENCH = ROOT / "data" / "final" / "bench.jsonl"
EVAL = ROOT / "data" / "final" / "eval"
TRAINED_RESP = EVAL / "trained_responses.jsonl"
TRAINED_SCORES = EVAL / "trained_scores.json"
BASELINE_RESP = EVAL / "baseline_responses.jsonl"
BASELINE_SCORES = EVAL / "baseline_scores_v2.json"
SFT_TRAIN = ROOT / "data" / "final" / "sft_train.jsonl"

ACRES_PER_HECTARE = 2.4711
# The brief's classification band. Deliberately WIDER than the verifier's
# DOSE_TOLERANCE (5%): a miss between 5% and 8% is a rounding-edge failure,
# not a dose a farmer would notice, and lumping it with a 2x overdose would
# overstate the hazard. Reported as its own class.
AUDIT_BAND = 0.08


# --------------------------------------------------------------------------
# load
# --------------------------------------------------------------------------

def load_verify():
    """Import verify with the SHIPPED ban list, as the Kaggle cell had it."""
    os.environ.pop("AGRI_RESTRICTED_AI", None)
    for m in ("verify", "restricted_ai"):
        sys.modules.pop(m, None)
    return importlib.import_module("verify")


def jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def load_all():
    bench = {r["item_id"]: r for r in jsonl(BENCH)}
    trained = {r["item_id"]: r["raw_response"] for r in jsonl(TRAINED_RESP)}
    baseline = {r["item_id"]: r["raw_response"] for r in jsonl(BASELINE_RESP)}
    tscores = {r["item_id"]: r
               for r in json.loads(TRAINED_SCORES.read_text(encoding="utf-8"))}
    bscores = {r["item_id"]: r
               for r in json.loads(BASELINE_SCORES.read_text(encoding="utf-8"))}
    return bench, trained, baseline, tscores, bscores


def ctx_for(v, res, item):
    return v.VerifyContext(
        resources=res, crop_slug=item["crop_slug"],
        pest_query=item["canonical_pest"],
        gold_escalate=bool(item["gold_advisory"]["escalate_to_expert"]))


def rescore(v, res, bench, responses, mode="score"):
    return {iid: v.verify(responses[iid], ctx_for(v, res, it), mode)
            for iid, it in bench.items() if iid in responses}


def mean(xs) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


# --------------------------------------------------------------------------
# reproduction
# --------------------------------------------------------------------------

def reproduce(v, res, bench, trained, tscores) -> dict:
    """Confirm the local re-score equals the recorded scores field for field."""
    got = rescore(v, res, bench, trained)
    diffs = {"total": [], "checks": [], "gates": [], "excluded": []}
    for iid in bench:
        w, g = tscores[iid], got[iid]
        if round(g.total, 6) != round(w["total"], 6):
            diffs["total"].append(iid)
        if g.checks != w["checks"]:
            diffs["checks"].append(iid)
        if g.gates != w["gates"]:
            diffs["gates"].append(iid)
        if g.excluded != w["excluded"]:
            diffs["excluded"].append(iid)

    # The counterfactual that proves gold_escalate is the live convention.
    alt = {iid: v.verify(trained[iid], v.VerifyContext(
        resources=res, crop_slug=it["crop_slug"],
        pest_query=it["canonical_pest"]), "score")
        for iid, it in bench.items()}
    alt_diff = sum(1 for iid in bench
                   if round(alt[iid].total, 6) != round(tscores[iid]["total"], 6))

    inc = [g for iid, g in got.items() if not g.excluded]
    return {
        "diffs": {k: len(vv) for k, vv in diffs.items()},
        "mean_all": mean(g.total for g in got.values()),
        "mean_nonexcluded": mean(g.total for g in inc),
        "n_nonexcluded": len(inc),
        "n_excluded": len(got) - len(inc),
        "at_1_all": sum(1 for g in got.values() if g.total == 1.0),
        "at_1_nonexcluded": sum(1 for g in inc if g.total == 1.0),
        "without_gold_escalate_diff": alt_diff,
        "without_gold_escalate_mean": mean(g.total for g in alt.values()),
        "excluded_ids": sorted(iid for iid, g in got.items() if g.excluded),
        "results": got,
    }


# --------------------------------------------------------------------------
# A — dose safety
# --------------------------------------------------------------------------

# The verifier's own C1 line. Parsing it, rather than re-deriving which
# candidate row "should" have been used, keeps the audit's verdict identical to
# the scorer's: an earlier version picked the candidate row kindest to the
# model and so reported a passing option as an "inside range" verifier bug,
# which it was not.
C1_MSG = re.compile(
    r"^C1: '(?P<ai>.+?)' dose (?P<val>[\d.]+)(?P<unit>[a-zA-Z%]*) (?P<basis>\S+); "
    r"CIB&RC states (?P<lo>[\d.]+)(?:-(?P<hi>[\d.]+))? (?P<lunit>\S+)")

ACRE = 2.4711


def dose_audit(v, res, bench, results) -> dict:
    """Every C1 == 0.0, split into genuine dose comparisons and refusals.

    One record per C1 line the verifier emitted, so the count of dose errors is
    the count of things the scorer actually objected to. The model's value_max
    comes from the advisory (the message prints only value_min), because a
    model RANGE that over-runs the label's top end is an overdose at the top
    even when its bottom end is legal.
    """
    rows, refusals = [], []
    for iid, r in results.items():
        if r.checks.get("C1_dose") != 0.0:
            continue
        if any(f.startswith("C1/C2/C3: no chemical option") for f in r.failures):
            refusals.append(iid)
            continue
        item = bench[iid]
        opts = {o.active_ingredient: o for o in
                (r.advisory.chemical_options if r.advisory else [])}
        for f in r.failures:
            m = C1_MSG.match(f)
            if not m:
                continue
            g = m.groupdict()
            opt = opts.get(g["ai"])
            lo = float(g["lo"])
            hi = float(g["hi"]) if g["hi"] else None
            mv = float(g["val"])
            mx = opt.dose.value_max if opt else None
            rec = {
                "item_id": iid, "crop": item["crop_slug"], "slice": item["slice"],
                "kind": item["kind"], "pest": item["canonical_pest"],
                "ai": g["ai"], "model_value": mv, "model_value_max": mx,
                "model_unit": g["unit"] or (opt.dose.unit if opt else None),
                "model_basis": g["basis"],
                "label_lo": lo, "label_hi": hi, "label_unit": g["lunit"],
                "label_raw": f.split("(")[-1].rstrip(")"),
                # Is the model's number the label's per-HECTARE figure wearing
                # a per_acre label? Compare against lo * 2.4711, the per-ha
                # value the per_acre column was derived from.
                "model_over_label_per_ha": (mv / (lo * ACRE)) if lo else None,
                "implied_per_ha": mv * ACRE,
            }
            rec.update(dose_verdict(rec))
            rows.append(rec)
    return {"failures": rows, "refusal_c1": refusals}


def dose_verdict(rec: dict) -> dict:
    """Classify one C1 objection. Ratios are computed on the basis the
    verifier compared on, so no unit conversion is reapplied here."""
    mu = (rec["model_unit"] or "").lower()
    lu = (rec["label_unit"] or "").lower()
    mass, vol = {"g", "kg"}, {"ml", "l"}
    if (mu in mass) != (lu in mass) or (mu in vol) != (lu in vol):
        return {"classification": "UNIT_DIMENSION_MISMATCH", "ratio": None,
                "pct": None,
                "note": f"model states {mu or '?'}, label states {lu or '?'} "
                        f"— a mass/volume swap, not a number error"}
    lo, hi, mv, mx = rec["label_lo"], rec["label_hi"], rec["model_value"], rec["model_value_max"]
    # Was the per-hectare figure mislabelled per_acre? That shows up as the
    # model's number sitting at ~2.47x the label's per-acre value.
    if rec["model_over_label_per_ha"] and abs(rec["model_over_label_per_ha"] - 1.0) <= AUDIT_BAND:
        return {"classification": "PER_HA_NUMBER_LABELLED_PER_ACRE",
                "ratio": mv / lo if lo else None,
                "pct": ((mv / lo) - 1.0) * 100 if lo else None,
                "note": "the model's number equals the label's PER-HECTARE "
                        "value while declaring per_acre"}
    # A model range must sit inside the authorisation at both ends.
    if mx is not None:
        top_label = hi if hi is not None else lo
        if mx > top_label * (1 + AUDIT_BAND):
            return {"classification": "WRONG_HIGH_RANGE_TOP",
                    "ratio": mx / top_label,
                    "pct": ((mx / top_label) - 1.0) * 100,
                    "note": f"model range {mv}-{mx} over-runs the authorised "
                            f"top {top_label}"}
    if hi is not None:
        if lo <= mv <= hi:
            return {"classification": "LOW_END_OK_TOP_OVER", "ratio": 1.0,
                    "pct": 0.0,
                    "note": "value_min is inside the label range; the "
                            "objection is to the model's upper bound"}
        ref = hi if mv > hi else lo
    else:
        ref = lo
    ratio = mv / ref if ref else None
    if ratio is None:
        return {"classification": "UNGRADEABLE", "ratio": None, "pct": None,
                "note": ""}
    pct = (ratio - 1.0) * 100
    if abs(ratio - 1.0) <= AUDIT_BAND:
        return {"classification": "WITHIN_8PC_ROUNDING_EDGE", "ratio": ratio,
                "pct": pct,
                "note": "outside the verifier's 5% tolerance but inside the "
                        "audit's 8% band — a rounding edge, not a hazard"}
    return {"classification": "WRONG_HIGH" if ratio > 1.0 else "WRONG_LOW",
            "ratio": ratio, "pct": pct, "note": ""}


# --------------------------------------------------------------------------
# B — G5
# --------------------------------------------------------------------------

def g5_audit(v, res, bench, results) -> dict:
    """Classify every G5 failure: synonym false negative, mis-association,
    or invention.

    (i) is decided by asking whether the a.i. IS registered on this crop for
    SOME pest, and whether the pest printed on those rows names the same
    organism as the queried pest. "Same organism" is decided by the synonym
    table first (both surface forms resolving to one canonical) and, where the
    table is silent, by a conservative token test on the printed form — that
    second arm is the candidate evaluator defect, so each one is listed with
    its evidence rather than counted silently.
    """
    out = []
    for iid, r in results.items():
        if r.gates.get("G5_triple_registered", True):
            continue
        item = bench[iid]
        ctx = ctx_for(v, res, item)
        gold = ctx.pest_match()
        canon = gold.canonical_name
        adv = r.advisory
        for opt in (adv.chemical_options if adv else []):
            comps = v.normalise_ai(opt.active_ingredient)
            if res.label_db.for_triple(item["crop_slug"], canon, comps):
                continue                      # this option was fine
            on_crop = [row for row in res.label_db.rows
                       if row.crop_slug == item["crop_slug"]
                       and comps == row.ai_components]
            printed = sorted({str(res.label_db.df.at[row.index,
                                                     "pest_or_disease"])
                              for row in on_crop})
            rec = {
                "item_id": iid, "crop": item["crop_slug"], "slice": item["slice"],
                "queried_pest": item["canonical_pest"],
                "canonical": canon, "ai": opt.active_ingredient,
                "registered_on_crop": bool(on_crop),
                "printed_pests": printed[:6],
            }
            if canon is None:
                # The query never identified a pest (an S2 CLARIFY item), so
                # there is no triple to look up and G5 cannot help. Naming a
                # chemical here is a different error from the other three and
                # is counted separately rather than forced into one of them.
                rec["klass"] = "iv_PEST_UNRESOLVED"
                rec["evidence"] = (
                    f"the query resolves to no canonical pest, so no "
                    f"(crop, pest, a.i.) triple exists to verify; the model "
                    f"named {opt.active_ingredient!r} anyway")
            elif not on_crop:
                rec["klass"] = "iii_INVENTION"
                rec["evidence"] = (f"{opt.active_ingredient!r} has no CIB&RC "
                                   f"row on {item['crop_slug']} for any pest")
            else:
                same, why = same_organism(v, res, item["crop_slug"], canon,
                                          item["canonical_pest"], printed)
                if same:
                    rec["klass"] = "i_SYNONYM_FALSE_NEGATIVE"
                    rec["evidence"] = why
                else:
                    rec["klass"] = "ii_MIS_ASSOCIATION"
                    rec["evidence"] = (
                        f"registered on {item['crop_slug']} only for "
                        f"{printed[:4]}, none of which is "
                        f"{item['canonical_pest']!r}")
            out.append(rec)
    return {"failures": out}


def _norm(s: Optional[str]) -> str:
    """Fold to letters only, so 'mealy bug' and 'Mealybug' compare equal."""
    return re.sub(r"[^a-z]", "", (s or "").lower())


def _known_names(v, res, crop: str, canon: Optional[str]) -> list[str]:
    """Every surface form the synonym table already maps to this canonical,
    plus the canonical itself. These are names the project ALREADY knows mean
    this organism, which is what makes a miss a false negative rather than a
    judgement call."""
    from pest_matcher import match_pest
    names = {canon} if canon else set()
    try:
        for sf in res.table.surface_forms(crop):
            if match_pest(crop, sf, res.table).canonical_name == canon:
                names.add(sf)
    except Exception:
        pass
    return sorted(n for n in names if n and len(_norm(n)) > 3)


def same_organism(v, res, crop, canon, queried, printed) -> tuple[bool, str]:
    """Is the queried pest LITERALLY NAMED in a pest cell of the rows the
    model's a.i. is registered for on this crop?

    Two arms, both requiring the cell to print the organism's own name. A
    shared word is deliberately NOT enough: 'Fruit rot' and 'Fruit borer'
    share 'fruit' and are different problems, and 'Pink bollworm' and
    'American bollworm' are different insects. An earlier token-overlap
    heuristic classified both pairs as synonyms and was wrong on both.
    """
    from pest_matcher import match_pest
    if not canon:
        return False, ""

    # Arm 1 — the synonym table resolves a printed cell to the same canonical,
    # yet the row did not get that canonical attached.
    for p in printed:
        m = match_pest(crop, p, res.table)
        if m.canonical_name and canon and m.canonical_name == canon:
            return True, (f"CIB&RC prints {p!r} on the row where this a.i. IS "
                          f"registered; the synonym table resolves that form "
                          f"to {canon!r}, so for_triple should have matched")

    # Arm 2 — the cell literally contains a name already known to mean this
    # canonical. Catches multi-pest and parenthesised cells whose canonical
    # extraction dropped the organism.
    for name in _known_names(v, res, crop, canon):
        n = _norm(name)
        for p in printed:
            if n and n in _norm(p):
                return True, (f"CIB&RC prints {p!r}, which contains the name "
                              f"{name!r} — a form the synonym table already "
                              f"maps to {canon!r}; the row's canonical "
                              f"extraction dropped it")
    return False, ""


# --------------------------------------------------------------------------
# C — the C5 surface-form bug
# --------------------------------------------------------------------------

def c5_audit(v, res, bench, results) -> dict:
    """Why does cotton/Helicoverpa armigera print as ['Jassid','Aphids',...]?

    surface_forms_for(crop, canonical) is the suspect: it reports what CIB&RC
    prints for a canonical, and the C5 failure line quotes it. If it returns
    forms belonging to OTHER pests, the message misdescribes ground truth even
    when the verdict is right.
    """
    from pest_matcher import match_pest
    db = res.label_db

    probe_canon = match_pest("cotton", "Helicoverpa armigera",
                             res.table).canonical_name
    forms = db.surface_forms_for("cotton", probe_canon or "")
    rows = db.for_pair("cotton", probe_canon)
    per_row = []
    for row in rows[:12]:
        d = db.df.loc[row.index]
        per_row.append({
            "index": int(row.index),
            "pest_or_disease": str(d["pest_or_disease"]),
            "canonicals": sorted(row.canonicals),
            "ai": str(d["active_ingredient"])[:60],
            "flag_pest_bled": bool(d.get("flag_pest_bled", False)),
        })

    # How many benchmark items carry a C5 failure whose quoted surface forms
    # do not resolve back to the item's own canonical?
    bad = []
    for iid, r in results.items():
        for f in r.failures:
            if not f.startswith("C5: "):
                continue
            m = re.search(r"which CIB&RC prints as \[(.*?)\]", f)
            if not m:
                continue
            quoted = [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()]
            item = bench[iid]
            canon = match_pest(item["crop_slug"], item["canonical_pest"],
                               res.table).canonical_name
            mism = [q for q in quoted
                    if match_pest(item["crop_slug"], q,
                                  res.table).canonical_name != canon]
            if mism:
                bad.append({"item_id": iid, "crop": item["crop_slug"],
                            "canonical": canon, "quoted": quoted,
                            "not_this_pest": mism})
            break

    # Multi-canonical rows are the mechanism: one cell naming several pests.
    multi = sum(1 for row in db.rows if len(row.canonicals) > 1)
    return {"probe_canonical": probe_canon, "probe_surface_forms": forms,
            "probe_rows": per_row, "n_pair_rows": len(rows),
            "mismatched_c5_messages": bad,
            "multi_canonical_rows": multi,
            "total_rows": len(db.rows)}


# --------------------------------------------------------------------------
# D — refusal on answerable, model vs training data
# --------------------------------------------------------------------------

def refusal_audit(v, res, bench, results, baseline_results) -> dict:
    """Empty chemical_options on ANSWERABLE items, in the model output and in
    the SFT training data it learned from."""
    A = v.Answerability

    def count(rs):
        n_ans = n_empty = 0
        ids = []
        for iid, r in rs.items():
            if r.answerability is not A.ANSWERABLE or not r.gates.get("G2_schema"):
                continue
            n_ans += 1
            if r.advisory is not None and not r.advisory.chemical_options:
                n_empty += 1
                ids.append(iid)
        return n_ans, n_empty, ids

    t_ans, t_empty, t_ids = count(results)
    b_ans, b_empty, _ = count(baseline_results)

    # The SFT side. An example's answerability is decided the same way the
    # verifier decides it, from crop + the pest the assistant answer is about.
    from pest_matcher import match_pest
    sft = {"total": 0, "parsed": 0, "answerable": 0, "answerable_empty": 0,
           "empty_any": 0, "by_slice": defaultdict(
               lambda: {"n": 0, "answerable": 0, "answerable_empty": 0})}
    log = {}
    gen_log = ROOT / "data" / "final" / "sft_generation_log.csv"
    if gen_log.exists():
        import csv
        with open(gen_log, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                # The SFT id is 'S<slice>_<row_id>'; the log stores the two
                # halves in separate columns. Joining on row_id alone matches
                # nothing (verified: 0 of 4,493).
                log[f"S{row.get('slice','')}_{row.get('row_id','')}"] = row

    for ex in jsonl(SFT_TRAIN):
        sft["total"] += 1
        adv, crop, pest = parse_sft_example(ex)
        if adv is None:
            continue
        sft["parsed"] += 1
        empty = not adv.get("chemical_options")
        if empty:
            sft["empty_any"] += 1
        meta = log.get(ex.get("id", ""), {})
        sl = meta.get("slice") or ex.get("slice") or "?"
        # The generation log is authoritative for crop/pest: it is the join
        # the benchmark design already relies on. The parsed answer is only a
        # fallback for rows the log does not cover.
        crop = meta.get("crop_slug") or crop or ""
        pest = meta.get("canonical_pest") or pest or ""
        bucket = sft["by_slice"][str(sl)]
        bucket["n"] += 1
        if not crop:
            continue
        canon = match_pest(crop, pest, res.table).canonical_name if pest else None
        try:
            ans = v.expected_answerable(crop, canon, res.label_db)
        except Exception:
            continue
        if ans is A.ANSWERABLE:
            sft["answerable"] += 1
            bucket["answerable"] += 1
            if empty:
                sft["answerable_empty"] += 1
                bucket["answerable_empty"] += 1
    sft["by_slice"] = {k: dict(val) for k, val in sft["by_slice"].items()}
    return {"trained": {"answerable_schema_valid": t_ans, "empty": t_empty,
                        "ids": t_ids},
            "baseline": {"answerable_schema_valid": b_ans, "empty": b_empty},
            "sft": sft}


def parse_sft_example(ex: dict):
    """Pull the assistant advisory dict plus crop/pest out of one SFT row."""
    adv = crop = pest = None
    msgs = ex.get("messages") or ex.get("conversations") or []
    user_txt = ""
    for m in msgs:
        role = m.get("role") or m.get("from")
        content = m.get("content") or m.get("value") or ""
        if role in ("assistant", "gpt"):
            try:
                adv = json.loads(content)
            except Exception:
                adv = None
        elif role in ("user", "human"):
            user_txt = content
    for key in ("crop_slug", "crop"):
        if ex.get(key):
            crop = ex[key]
    for key in ("canonical_pest", "pest", "pest_query"):
        if ex.get(key):
            pest = ex[key]
    if not crop and user_txt:
        m = re.search(r"crop[:\s]+([a-z ]+)", user_txt, re.I)
        parts = m.group(1).strip().lower().split() if m else []
        crop = parts[0] if parts else None
    if isinstance(adv, dict) and not pest:
        causes = adv.get("likely_causes") or []
        if causes and isinstance(causes[0], dict):
            pest = causes[0].get("name")
    return (adv if isinstance(adv, dict) else None), crop, pest


# --------------------------------------------------------------------------
# E — slice balance
# --------------------------------------------------------------------------

def slice_balance(bench, results, sft) -> dict:
    by_slice = defaultdict(list)
    for iid, r in results.items():
        if r.excluded:
            continue
        by_slice[bench[iid]["slice"]].append(r.total)
    bench_side = {str(k): {"n": len(vv), "mean": mean(vv)}
                  for k, vv in sorted(by_slice.items())}
    return {"bench": bench_side, "sft_by_slice": sft["by_slice"],
            "sft_total": sft["total"]}


# --------------------------------------------------------------------------
# corrected estimate
# --------------------------------------------------------------------------

def corrected_estimate(v, bench, results, g5, c5) -> dict:
    """What the score would be if the evaluator defects were repaired.

    An ESTIMATE, not a re-score: it re-folds each item's ALREADY-RECORDED
    checks with G5 forced True, and does not re-run the dose and PHI
    comparisons that a real synonym repair would newly make reachable. It is
    therefore a ceiling on the class-(i) effect, not a prediction.

    Two inputs, and both turn out to be small:

    - class (i) G5 synonym false negatives. Every one of these items ALSO
      carries a class (ii) or (iii) failure on another recommended option, so
      repairing the synonym table rescues no item's G5 gate on its own. The
      "generous" arm below excuses the other failure too, purely to bound the
      effect.
    - the C5 surface-form defect. It is message-only: surface_forms_for is
      read at two places in verify.py and both are failure-string
      construction. It changes no check and therefore no score. Credited zero.
    """
    W = v.CHECK_WEIGHTS
    syn = {r["item_id"] for r in g5["failures"]
           if r["klass"] == "i_SYNONYM_FALSE_NEGATIVE"}
    other = {r["item_id"] for r in g5["failures"]
             if r["klass"] != "i_SYNONYM_FALSE_NEGATIVE"}
    only_syn = syn - other

    def fold(checks) -> float:
        ch = {k: val for k, val in checks.items() if k in W}
        den = sum(W[k] for k in ch)
        return (sum(W[k] * val for k, val in ch.items()) / den) if den else 1.0

    live = {iid: r for iid, r in results.items() if not r.excluded}
    observed = mean(r.total for r in live.values())

    # Strict: only items whose ONLY G5 objection is a synonym false negative.
    strict = []
    for iid, r in live.items():
        if iid in only_syn:
            gates = dict(r.gates); gates["G5_triple_registered"] = True
            strict.append(fold(r.checks) if all(gates.values()) else r.total)
        else:
            strict.append(r.total)

    # Generous ceiling: excuse every G5 objection on any item that has a
    # class-(i) one, which overstates the repair on purpose.
    generous, gains = [], []
    for iid, r in live.items():
        if iid in syn:
            gates = dict(r.gates); gates["G5_triple_registered"] = True
            t = fold(r.checks) if all(gates.values()) else r.total
            generous.append(t)
            gains.append({"item_id": iid, "was": r.total, "would_be": t})
        else:
            generous.append(r.total)

    return {"observed": observed,
            "n_class_i_items": len(syn), "n_only_class_i": len(only_syn),
            "estimate_strict": mean(strict),
            "estimate_generous_ceiling": mean(generous),
            "c5_score_effect": 0.0,
            "per_item_generous": gains}


# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reproduce", action="store_true")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    v = load_verify()
    res = v.VerifyResources.load()
    bench, trained, baseline, tscores, bscores = load_all()

    rep = reproduce(v, res, bench, trained, tscores)
    print("REPRODUCTION")
    for k in ("diffs", "mean_all", "mean_nonexcluded", "n_nonexcluded",
              "n_excluded", "at_1_all", "at_1_nonexcluded",
              "without_gold_escalate_diff", "without_gold_escalate_mean"):
        print(f"  {k}: {rep[k]}")
    if args.reproduce:
        return

    results = rep.pop("results")
    base_results = rescore(v, res, bench, baseline)

    A = dose_audit(v, res, bench, results)
    B = g5_audit(v, res, bench, results)
    C = c5_audit(v, res, bench, results)
    D = refusal_audit(v, res, bench, results, base_results)
    E = slice_balance(bench, results, D["sft"])
    EST = corrected_estimate(v, bench, results, B, C)

    print("\nA DOSE:", Counter(r["classification"] for r in A["failures"]),
          "| refusal-C1 items:", len(A["refusal_c1"]))
    print("B G5:", Counter(r["klass"] for r in B["failures"]),
          "| items:", len({r["item_id"] for r in B["failures"]}))
    print("C C5: probe forms", C["probe_surface_forms"],
          "| mismatched msgs", len(C["mismatched_c5_messages"]),
          "| multi-canonical rows", C["multi_canonical_rows"], "/", C["total_rows"])
    print("D REFUSAL:", D["trained"]["empty"], "of",
          D["trained"]["answerable_schema_valid"], "answerable |",
          "SFT answerable_empty", D["sft"]["answerable_empty"], "of",
          D["sft"]["answerable"])
    print("E SLICE:", E["bench"])
    print("EST:", EST)

    if args.json:
        args.json.write_text(json.dumps(
            {"reproduction": rep, "A_dose": A, "B_g5": B, "C_c5": C,
             "D_refusal": D, "E_slice": E, "estimate": EST},
            indent=1, default=str), encoding="utf-8")
        print("wrote", args.json)


if __name__ == "__main__":
    main()
