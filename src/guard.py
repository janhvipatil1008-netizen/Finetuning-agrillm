"""guard.py -- Phase 14 Step 6: a deterministic post-generation guardrail.

    guard(response_text, query_text, resources) -> (output_text, actions)

Removes chemical options the label does not support and forces escalation
where the label cannot vouch for an answer. It never adds a chemical, never
changes a dose, never edits free text: the output's chemical_options are a
subsequence of the input's, and the only other field it can change is
escalate_to_expert, false -> true. Pure; no I/O beyond what `resources`
already holds.

KEY
===

Crop, pest and application method come ONLY from
retrieval.resolve_key(query_text) -- the live resolver Phase 12 Arm B used.
Nothing here reads a benchmark item; tests/test_guard.py asserts it.

REFERENCE ROWS
==============

retrieval.retrieve(crop, pest, resources, method, max_rows=None): the
uncapped Phase 8 filter chain (trainable, not defective, not contradicted,
not on the crop-scoped ban list, application-method narrowing). Pest
unresolved: retrieve() returns nothing for a None pest, so the reference is
the union of retrieve() over every canonical pest label_db carries on the
crop -- the same chain, pair by pair. (The 20 label_db rows with no canonical
pest, 7 of them usable, are therefore never reference rows.) Crop
unresolved: no reference at all.

GUARDABLE
=========

An answer is guardable if it is schema-valid, OR its ONLY schema error is
the unknown-PHI escalation invariant (PHI_MSG) -- the Phase 12 Step 5.A
criterion, and the one case the guard's own rule (c) repairs. Everything
else -- not JSON, not an object, any other schema error -- comes back
unchanged with action "unparseable": no unwrapping, no format repair. The
guarded result must pass the schema, or the ORIGINAL comes back unchanged
with action "guard_failed".

RULES
=====

Per option, in order (crop resolved):
  a. removed_unregistered -- the option's a.i. components match no
     reference row's (verify's G5 comparison: normalise_ai against the
     row's ai_components). Crop + pest resolved but the pair has no rows:
     every option is removed this way, with an extra "no_label_rows" note,
     because resolver errors surface exactly there.
  b. removed_dose -- check_dose() says HIGH or LOW: outside the matched
     label range by more than BAND (8%). UNIT_MISMATCH, BASIS_MISMATCH,
     UNVERIFIABLE and an a.i. registered but no product row to compare
     against ("dose_unmatched") are noted and never acted on.
Then on what is kept:
  c. forced_escalation -- a kept option with phi_days null and
     phi_not_applicable false.
     all_removed_escalation -- every option was removed.
     unvalidated_escalation -- crop unresolved and options present; rules
     a and b cannot run, so the options stay and the answer escalates.
Escalation actions are recorded only when they flip escalate_to_expert from
false; a guard that changes nothing returns the input text byte for byte.

MOVED FROM tools/phase12_step5_validator_replay.py (Phase 14 Step 6)
====================================================================

BAND, PHI_MSG, ESC_FALSE, norm_name, repair, candidate_rows, to_base,
row_bounds and judge, verbatim except that verify's helpers are imported
here instead of passed in as `v`. check_dose is the per-option core of the
replay's validate() (match, judge every candidate row, accept if ANY fits);
validate() now calls it. The replay imports all of these from here and
still reproduces its Step 5 output byte for byte, so the replay and the
guard cannot drift.

SHARED WITH verify.py: normalise_ai, formulation_key and _to_base
(imported), and label_db itself -- through VerifyResources, which
retrieval.retrieve filters. The guard and the scorer read the same table, so
the scorer agreeing with a removal is not independent evidence.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from pydantic import ValidationError

from retrieval import resolve_key, retrieve
from schema import Advisory
from verify import VerifyResources, _to_base, formulation_key, normalise_ai

__all__ = [
    "BAND", "PHI_MSG", "GuardResult", "guard", "guard_detailed",
    "reference_rows", "check_dose", "candidate_rows", "row_bounds", "judge",
    "repair", "norm_name", "to_base",
]

BAND = 0.08
PHI_MSG = "unknown PHI requires escalate_to_expert=True"
ESC_FALSE = '"escalate_to_expert":false'

# check_dose verdicts that are counted, never acted on.
NOTED = {"UNIT_MISMATCH": "unit_mismatch", "BASIS_MISMATCH": "basis_mismatch",
         "UNVERIFIABLE": "unverifiable", "NOT_IN_SHEET": "dose_unmatched"}


# --------------------------------------------------------------------------
# moved verbatim from tools/phase12_step5_validator_replay.py
# --------------------------------------------------------------------------

def norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9.]", "", str(s).lower())


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


def candidate_rows(opt: dict, sheet: list[dict], method):
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
        comps = normalise_ai(opt.get("active_ingredient"))
        fk = formulation_key(opt.get("active_ingredient"))
        rows = [r for r in sheet if normalise_ai(r["ai"]) == comps and formulation_key(r["ai"]) == fk]
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


def to_base(value, unit):
    if value is None:
        return None, None
    return _to_base(value, unit)


def row_bounds(row: dict, basis: str):
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
    lo_b, dim = to_base(lo, unit)
    hi_b, _ = to_base(hi, unit)
    if lo_b is None:
        return None, None, None, f"sheet unit {unit!r} not convertible"
    return lo_b, hi_b, dim, None


def judge(opt: dict, row: dict) -> dict:
    d = opt.get("dose") or {}
    basis, unit = d.get("basis"), d.get("unit")
    if basis in (None, "unstated") or d.get("value_min") is None:
        return {"verdict": "NO_STATED_DOSE"}
    lo, hi, dim, why = row_bounds(row, basis)
    if why:
        return {"verdict": "BASIS_MISMATCH" if why.startswith("basis") else "UNVERIFIABLE", "note": why}
    vmin, mdim = to_base(d["value_min"], unit)
    vmax, _ = to_base(d.get("value_max"), unit)
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


def check_dose(opt: dict, rows: list[dict], method):
    """The per-option core of the replay's validate(): match the option to
    its rows, judge every candidate, and accept if the dose fits ANY of them
    (the lenient reading); otherwise the first candidate's verdict.

    Returns (verdict, candidates, tier, multi); verdict NOT_IN_SHEET and no
    candidates when no row names this product.
    """
    cands, tier, multi = candidate_rows(opt, rows, method)
    if not cands:
        return {"verdict": "NOT_IN_SHEET"}, [], None, False
    js = [judge(opt, r) for r in cands]
    ok = [j for j in js if j["verdict"] == "OK"]
    return (ok[0] if ok else js[0]), cands, tier, multi


# --------------------------------------------------------------------------
# the guard
# --------------------------------------------------------------------------

@dataclass
class GuardResult:
    output: str
    actions: list[dict] = field(default_factory=list)
    crop: Optional[str] = None
    pest: Optional[str] = None
    method: Optional[str] = None
    guardable: bool = False
    changed: bool = False


def reference_rows(crop: Optional[str], pest: Optional[str], method: Optional[str],
                   resources: VerifyResources) -> list[dict]:
    """Uncapped retrieve() rows for the key; crop-wide when pest is None."""
    if not crop:
        return []
    if pest:
        return retrieve(crop, pest, resources, method, max_rows=None).rows
    canonicals = sorted({c for r in resources.label_db.rows if r.crop_slug == crop
                         for c in r.canonicals})
    out, seen = [], set()
    for canon in canonicals:
        for row in retrieve(crop, canon, resources, method, max_rows=None).rows:
            key = json.dumps({k: v for k, v in row.items() if k != "_ai"}, sort_keys=True)
            if key not in seen:
                seen.add(key)
                out.append(row)
    return out


def _guardable(text) -> Optional[tuple[dict, bool]]:
    """(payload, escalate_to_expert as the schema reads it), or None."""
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        return payload, Advisory.model_validate(payload).escalate_to_expert
    except ValidationError as e:
        errs = e.errors()
        # The invariant only fires when escalate_to_expert is false.
        if len(errs) == 1 and PHI_MSG in errs[0]["msg"]:
            return payload, False
        return None


def _unknown_phi(opt: dict) -> bool:
    return opt.get("phi_days") is None and not opt.get("phi_not_applicable", False)


def guard_detailed(response_text: str, query_text: str,
                   resources: VerifyResources) -> GuardResult:
    crop, pest, method = resolve_key(query_text, resources)
    key = {"crop": crop, "pest": pest, "method": method}

    parsed = _guardable(response_text)
    if parsed is None:
        return GuardResult(response_text, [{"action": "unparseable"}], **key)
    adv, escalated = parsed
    options = adv.get("chemical_options") or []
    actions: list[dict] = []

    keep = list(options)
    if crop:
        rows = reference_rows(crop, pest, method, resources)
        if pest and not rows and options:
            actions.append({"action": "no_label_rows"})
        keep = []
        for k, opt in enumerate(options):
            ai = opt.get("active_ingredient")
            comps = normalise_ai(ai)
            if not (comps and any(r["_ai"] == comps for r in rows)):
                actions.append({"action": "removed_unregistered", "option": k, "active_ingredient": ai})
                continue
            verdict, *_ = check_dose(opt, rows, method)
            v = verdict["verdict"]
            if v in ("HIGH", "LOW"):
                actions.append({"action": "removed_dose", "option": k, "active_ingredient": ai,
                                "verdict": v, "pct": round(verdict["pct"], 2)})
                continue
            if v in NOTED:
                actions.append({"action": NOTED[v], "option": k, "active_ingredient": ai,
                                "note": verdict.get("note")})
            keep.append(opt)

    reasons = []
    if any(_unknown_phi(o) for o in keep):
        reasons.append("forced_escalation")
    if options and not keep:
        reasons.append("all_removed_escalation")
    if not crop and options:
        reasons.append("unvalidated_escalation")
    flip = bool(reasons) and not escalated
    if flip:
        actions += [{"action": r} for r in reasons]
    removed = len(keep) < len(options)
    if not removed and not flip:
        return GuardResult(response_text, actions, **key, guardable=True)

    if removed:
        out = dict(adv, chemical_options=keep)
        if flip:
            out["escalate_to_expert"] = True
        text = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    else:
        try:
            text = repair(response_text)
        except AssertionError:   # ESC_FALSE also inside a string value
            text = json.dumps(dict(adv, escalate_to_expert=True),
                              ensure_ascii=False, separators=(",", ":"))
    try:
        Advisory.model_validate(json.loads(text))
    except ValidationError as e:
        return GuardResult(response_text, actions + [{"action": "guard_failed",
                                                      "error": e.errors()[0]["msg"]}],
                           **key, guardable=True)
    return GuardResult(text, actions, **key, guardable=True, changed=True)


def guard(response_text: str, query_text: str,
          resources: VerifyResources) -> tuple[str, list[dict]]:
    r = guard_detailed(response_text, query_text, resources)
    return r.output, r.actions
