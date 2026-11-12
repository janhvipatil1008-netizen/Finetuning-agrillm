"""apply_guard.py -- Phase 14 Step 6: run src/guard.py over every arm, and
the before/after numbers for reports/phase14_guardrail.md. No GPU.

  --write  guard R0, R3, R2 (raw) and R4 and write
           data/final/eval/guarded/<arm>_responses.jsonl -- 500 rows each:
           item_id, raw_response (the guarded text), changed, guardable,
           guard_key {crop, pest, method}, guard_actions. Refuses to replace
           an existing file without --force.
  --md     before/after tables. Needs scores_<arm>_guarded.json from
           tools/score.py, and asserts every guarded file still equals a
           fresh guard run, so the tables describe the committed files.

The guard is given the bench item's query_text -- the input the model
answered -- and nothing else from the item. For R2/R4 the script asserts that
query is the one inside the prompt the model saw. Everything gold
(crop_slug, the gold pest, gold_advisory) is read HERE, after the fact, only
to judge the guard.

Definitions, all from the Phase 10/12 audits, all on the 498 items:

  audit view   verify() against the gold key, on the answer as given -- or,
               when its ONLY schema error is the unknown-PHI invariant, on
               the one-field escalation copy (guard.repair, Phase 12 Step
               5.A), so its options are G5/C1-graded too. Without that, an
               answer the guard makes schema-valid would show its overdoses
               for the first time AFTER guarding.
  overdose     a C1 objection (phase12_stepA_score_rag.c1_objections, every
               C1 line) classed WRONG_HIGH or WRONG_HIGH_RANGE_TOP; per-ha
               numbers declared per_acre (PER_HA_NUMBER_LABELLED_PER_ACRE)
               are counted beside them.
  unregistered an option failing G5 (phase10 g5_audit).
  unknown-PHI  an option with phi_days null and phi_not_applicable false in
               a JSON answer with escalate_to_expert false.
  false        a removed option that verify() grades correct against the
  positive     gold label: removed_unregistered where G5 passes for it
               (for_triple on the gold crop and pest) and neither G4 nor G7
               names it; removed_dose where C1 does not object to it (Phase
               12 verifier_view).
  residual     an unsafe option still present after guarding, attributed to
               why the guard let it through: answer not guardable, crop
               unresolved (escalated only), guard key != gold key, or the
               same key (the guard's row match and verify's disagree).

Usage:
    python tools/apply_guard.py --write [--force]
    python tools/score.py data/final/eval/guarded/<arm>_responses.jsonl --label <arm>_guarded
    python tools/apply_guard.py --md <tables.md> [--json <dump>]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import phase10_stepB_audit as p10  # noqa: E402
import phase12_stepA_score_rag as s12  # noqa: E402
import phase12_step5_validator_replay as r5  # noqa: E402
import score as sc  # noqa: E402
import guard as G  # noqa: E402
from pydantic import ValidationError  # noqa: E402
from schema import Advisory  # noqa: E402

EVAL = p10.EVAL
GUARDED = EVAL / "guarded"
PROMPTS_DIR = ROOT / "data" / "final" / "prompts"
RAG_PROMPTS_B = ROOT / "data" / "interim" / "rag_prompts_B.jsonl"

# label -> (responses file, prompt file the model saw, if recorded)
ARMS = {
    "R0_baseline": ("baseline_responses.jsonl", None),
    "R3_sft": ("trained_responses.jsonl", None),
    "R2_base_rag": ("R2_responses.jsonl", "prompts_R2.jsonl"),
    "R4_sft_rag": ("R4_responses.jsonl", "prompts_R4.jsonl"),
}
REMOVALS = ("removed_unregistered", "removed_dose")
ITEM_ACTIONS = ("unparseable", "guard_failed", "no_label_rows", "forced_escalation",
                "all_removed_escalation", "unvalidated_escalation")
OPTION_ACTIONS = ("removed_unregistered", "removed_dose", "unit_mismatch", "basis_mismatch",
                  "unverifiable", "dose_unmatched")


def guarded_path(label: str) -> Path:
    return GUARDED / f"{label}_responses.jsonl"


def run_guard(res, bench: dict, label: str) -> tuple[dict, dict]:
    """(responses, {item_id: GuardResult}) for one arm, all 500 items."""
    resp_file, prompt_file = ARMS[label]
    raw = sc.load_responses(EVAL / resp_file)
    if prompt_file:
        users = {r["item_id"]: r["user"] for r in p10.jsonl(PROMPTS_DIR / prompt_file)}
        for i, it in bench.items():
            assert f"\n{it['query_text']}\n</query>" in users[i], f"{label} {i}: query not in prompt"
    return raw, {i: G.guard_detailed(raw[i], it["query_text"], res) for i, it in bench.items()}


def write(res, bench: dict, force: bool) -> None:
    GUARDED.mkdir(parents=True, exist_ok=True)
    for label in ARMS:
        out = guarded_path(label)
        if out.exists() and not force:
            raise SystemExit(f"{out.relative_to(ROOT)} exists; pass --force to replace it")
        _, gr = run_guard(res, bench, label)
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            for i, g in gr.items():
                fh.write(json.dumps({"item_id": i, "raw_response": g.output, "changed": g.changed,
                                     "guardable": g.guardable,
                                     "guard_key": {"crop": g.crop, "pest": g.pest, "method": g.method},
                                     "guard_actions": g.actions}, ensure_ascii=False) + "\n")
        print(f"wrote {out.relative_to(ROOT).as_posix()} ({sum(g.changed for g in gr.values())} changed)")


# --------------------------------------------------------------------------
# audit view and unsafe counts
# --------------------------------------------------------------------------

def phi_only(s: str) -> bool:
    try:
        Advisory.model_validate(json.loads(s))
        return False
    except ValidationError as e:
        errs = e.errors()
        return len(errs) == 1 and G.PHI_MSG in errs[0]["msg"]
    except (json.JSONDecodeError, TypeError):
        return False


def audit(v, res, bench: dict, responses: dict, items: list[str]) -> dict:
    out = {}
    for i in items:
        s = responses[i]
        if phi_only(s):
            try:
                s = G.repair(s)
            except AssertionError:
                s = json.dumps(dict(json.loads(s), escalate_to_expert=True),
                               ensure_ascii=False, separators=(",", ":"))
        out[i] = v.verify(s, p10.ctx_for(v, res, bench[i]), "score")
    return out


def unknown_phi(s: str) -> int:
    try:
        a = json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return 0
    if not isinstance(a, dict) or a.get("escalate_to_expert"):
        return 0
    opts = a.get("chemical_options")
    return sum(1 for o in opts if isinstance(o, dict) and o.get("phi_days") is None
               and not o.get("phi_not_applicable", False)) if isinstance(opts, list) else 0


def unsafe(v, res, bench: dict, responses: dict, A: dict, items: list[str]) -> dict:
    lines = s12.c1_objections({i: A[i] for i in items}, bench, only_zero=False)
    od = [r for r in lines if r["classification"] in s12.OVERDOSE]
    ph = [r for r in lines if r["classification"] == "PER_HA_NUMBER_LABELLED_PER_ACRE"]
    g5 = p10.g5_audit(v, res, bench, {i: A[i] for i in items})["failures"]
    phi = {i: unknown_phi(responses[i]) for i in items}
    pair = lambda recs: (len(recs), len({r["item_id"] for r in recs}))
    return {"overdose": pair(od), "per_ha_as_per_acre": pair(ph), "unregistered": pair(g5),
            "unknown_phi": (sum(phi.values()), sum(1 for n in phi.values() if n))}


# --------------------------------------------------------------------------
# false positives
# --------------------------------------------------------------------------

def judge_removals(v, res, bench: dict, responses: dict, gr: dict, A: dict,
                   items: list[str]) -> list[dict]:
    out = []
    for i in items:
        g = gr[i]
        acts = [a for a in g.actions if a["action"] in REMOVALS]
        if not acts:
            continue
        opts = json.loads(responses[i])["chemical_options"]
        gold_crop = bench[i]["crop_slug"]
        gold_pest = p10.ctx_for(v, res, bench[i]).pest_match().canonical_name
        no_rows = any(a["action"] == "no_label_rows" for a in g.actions)
        for a in acts:
            opt = opts[a["option"]]
            if a["action"] == "removed_unregistered":
                if "G5_triple_registered" not in A[i].gates:
                    call = "unjudged"
                else:
                    ai = opt["active_ingredient"]
                    reg = res.label_db.for_triple(gold_crop, gold_pest, v.normalise_ai(ai))
                    # verify() accepts an option's registration only if G5
                    # finds the triple AND neither G4 (ban list) nor G7 (row
                    # outside the trainable set) names the option.
                    objected = any(f.startswith((f"G4: recommended {ai!r}",
                                                 f"G7: the CIB&RC row for {ai!r}"))
                                   for f in A[i].failures)
                    call = "FP" if reg and not objected else "TP"
            else:
                view = r5.verifier_view(A[i], opt)
                call = {"no objection": "FP", "objects": "TP", "objects (G8)": "TP"}.get(view, "unjudged")
            out.append({"item_id": i, "rule": a["action"], "verdict": a.get("verdict"),
                        "ai": opt["active_ingredient"], "call": call,
                        "key_crop": g.crop, "key_pest": g.pest,
                        "gold_crop": gold_crop, "gold_pest": gold_pest,
                        "key_matches_gold": g.crop == gold_crop and g.pest == gold_pest,
                        "no_label_rows": no_rows})
    return out


# --------------------------------------------------------------------------
# tables
# --------------------------------------------------------------------------

def f4(x) -> str:
    return "n/a" if x is None else f"{x:.4f}"


def md_tables(v, res, bench: dict) -> tuple[str, dict]:
    items = list(sc.scored_items(bench))
    L, dump = [], {}
    w = L.append
    G_, R_, A_, AG_, S_ = {}, {}, {}, {}, {}
    for label in ARMS:
        raw, gr = run_guard(res, bench, label)
        on_disk = {r["item_id"]: r for r in p10.jsonl(guarded_path(label))}
        assert all(on_disk[i]["raw_response"] == gr[i].output and on_disk[i]["guard_actions"] == gr[i].actions
                   for i in bench), f"{label}: guarded file differs from a fresh guard run"
        after = {i: gr[i].output for i in bench}
        R_[label], G_[label] = raw, gr
        A_[label] = audit(v, res, bench, raw, items)
        AG_[label] = audit(v, res, bench, after, items)
        S_[label] = {}
        for tag, name in (("before", label), ("after", f"{label}_guarded")):
            s = json.loads((EVAL / f"scores_{name}.json").read_text(encoding="utf-8"))
            want = ARMS[label][0] if tag == "before" else guarded_path(label).relative_to(EVAL).as_posix()
            assert s["summary"]["responses"] == f"data/final/eval/{want}", (name, s["summary"]["responses"])
            S_[label][tag] = s

    # ---- actions -----------------------------------------------------------
    w("## 1. Guard actions (498 items)\n")
    w("| arm | items changed | unparseable | guard_failed | removed_unregistered (opt / items) | "
      "… key had no label rows (items) | removed_dose HIGH / LOW (opt) | forced_escalation | "
      "all_removed_escalation | unvalidated_escalation | unit / basis / unverifiable / dose_unmatched (opt) |")
    w("|---|---:|---:|---:|---|---:|---|---:|---:|---:|---|")
    acts = {}
    for label, gr in G_.items():
        c = Counter()
        it = Counter()
        hl = Counter()
        for i in items:
            seen = set()
            for a in gr[i].actions:
                c[a["action"]] += 1
                seen.add(a["action"])
                if a["action"] == "removed_dose":
                    hl[a["verdict"]] += 1
            it.update(seen)
        acts[label] = {"options": dict(c), "items": dict(it), "dose": dict(hl),
                       "changed": sum(gr[i].changed for i in items)}
        w(f"| {label} | {acts[label]['changed']} | {it['unparseable']} | {it['guard_failed']} | "
          f"{c['removed_unregistered']} / {it['removed_unregistered']} | {it['no_label_rows']} | "
          f"{hl['HIGH']} / {hl['LOW']} | {it['forced_escalation']} | {it['all_removed_escalation']} | "
          f"{it['unvalidated_escalation']} | {c['unit_mismatch']} / {c['basis_mismatch']} / "
          f"{c['unverifiable']} / {c['dose_unmatched']} |")
    dump["actions"] = acts
    nocrop = {label: [i for i in items if G_[label][i].guardable and G_[label][i].crop is None
                      and json.loads(R_[label][i]).get("chemical_options")] for label in ARMS}
    w("\nCrop unresolved, guardable, options present (validated by nothing, escalated only): " +
      "; ".join(f"{k} {len(x)} items ({sum(not any(a['action'] == 'unvalidated_escalation' for a in G_[k][i].actions) for i in x)} already escalated)"
                for k, x in nocrop.items()) + ".\n")

    # ---- scores ------------------------------------------------------------
    w("## 2. Scores before / after (498-item denominator)\n")
    C = list(next(iter(S_.values()))["before"]["summary"]["checks"])
    w("| arm | | mean | scored / excl / missing | G2 % | " + " | ".join(C) + " |")
    w("|---|---|---:|---|---:|" + "---:|" * len(C))
    for label in ARMS:
        for tag in ("before", "after"):
            s = S_[label][tag]["summary"]
            w(f"| {label if tag == 'before' else ''} | {tag} | **{f4(s['mean'])}** | "
              f"{s['n_scored']} / {s['n_excluded']} / {s['n_missing']} | {s['g2_schema_pct']:.1f} | "
              + " | ".join(f"{f4(s['checks'][c]['mean'])} ({s['checks'][c]['n']})" for c in C) + " |")
    w("\nScore cost, paired on items scored in both (after − before):\n")
    w("| arm | n | mean before | mean after | Δ | items up / down / same |")
    w("|---|---:|---:|---:|---:|---|")
    cost = {}
    for label in ARMS:
        b = {r["item_id"]: r["score"] for r in S_[label]["before"]["items"] if not r["excluded"]}
        a = {r["item_id"]: r["score"] for r in S_[label]["after"]["items"] if not r["excluded"]}
        both = [i for i in items if i in a and i in b]
        d = [a[i] - b[i] for i in both]
        up, dn = sum(x > 0 for x in d), sum(x < 0 for x in d)
        mb, ma = p10.mean(b[i] for i in both), p10.mean(a[i] for i in both)
        cost[label] = {"n": len(both), "before": mb, "after": ma, "delta": ma - mb, "up": up, "down": dn}
        w(f"| {label} | {len(both)} | {f4(mb)} | {f4(ma)} | **{ma - mb:+.4f}** | {up} / {dn} / {len(both) - up - dn} |")
    dump["cost"] = cost

    # ---- unsafe ------------------------------------------------------------
    w("\n## 3. Unsafe counts before / after (audit view, 498 items; options / items)\n")
    w("| arm | | overdose (WRONG_HIGH, RANGE_TOP) | per-ha as per-acre | unregistered (G5) | unknown-PHI, not escalated |")
    w("|---|---|---|---|---|---|")
    uns = {}
    for label in ARMS:
        uns[label] = {"before": unsafe(v, res, bench, R_[label], A_[label], items),
                      "after": unsafe(v, res, bench, {i: G_[label][i].output for i in bench}, AG_[label], items)}
        for tag in ("before", "after"):
            u = uns[label][tag]
            w(f"| {label if tag == 'before' else ''} | {tag} | " + " | ".join(
                f"{u[k][0]} / {u[k][1]}" for k in ("overdose", "per_ha_as_per_acre", "unregistered", "unknown_phi")) + " |")
    dump["unsafe"] = uns

    w("\nWhat is left after guarding, by why the guard let it through (options):\n")
    w("| arm | kind | not guardable | crop unresolved (escalated only) | pest unresolved (crop-level check) | "
      "guard key ≠ gold key | same key: dose not comparable | same key: guard's row accepted it |")
    w("|---|---|---:|---:|---:|---:|---:|---:|")
    noted = set(G.NOTED.values())
    resid = {}
    for label in ARMS:
        AG, gr = AG_[label], G_[label]
        lines = s12.c1_objections({i: AG[i] for i in items}, bench, only_zero=False)
        kinds = {"overdose / per-ha": [r for r in lines if r["classification"] in s12.OVERDOSE
                                       or r["classification"] == "PER_HA_NUMBER_LABELLED_PER_ACRE"],
                 "unregistered (G5)": p10.g5_audit(v, res, bench, {i: AG[i] for i in items})["failures"],
                 "unknown-PHI": [{"item_id": i} for i in items for _ in range(unknown_phi(gr[i].output))]}
        resid[label] = {}
        for kind, recs in kinds.items():
            c = Counter()
            for r in recs:
                g, it = gr[r["item_id"]], bench[r["item_id"]]
                gold_pest = p10.ctx_for(v, res, it).pest_match().canonical_name
                if not g.guardable:
                    why = "not guardable"
                elif g.crop is None:
                    why = "crop unresolved"
                elif (g.crop, g.pest) != (it["crop_slug"], gold_pest):
                    why = "key differs"
                elif g.pest is None:
                    why = "pest unresolved"
                elif any(a["action"] in noted and a.get("active_ingredient") == r.get("ai") for a in g.actions):
                    why = "not comparable"
                else:
                    why = "accepted"
                c[why] += 1
            resid[label][kind] = dict(c)
            if recs:
                w(f"| {label} | {kind} | {c['not guardable']} | {c['crop unresolved']} | "
                  f"{c['pest unresolved']} | {c['key differs']} | {c['not comparable']} | {c['accepted']} |")
    dump["residual"] = resid

    # ---- false positives -------------------------------------------------------
    w("\n## 4. Removed options judged by verify() against the gold label\n")
    w("| arm | rule | removed | … under guard key ≠ gold key | TP (verify agrees) | FP (verify grades it correct) | unjudged | FP with guard key ≠ gold key | FP on no-label-rows items |")
    w("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    fps = {}
    for label in ARMS:
        recs = judge_removals(v, res, bench, R_[label], G_[label], A_[label], items)
        fps[label] = recs
        for rule in REMOVALS:
            rr = [r for r in recs if r["rule"] == rule]
            cnt = Counter(r["call"] for r in rr)
            fp = [r for r in rr if r["call"] == "FP"]
            w(f"| {label} | {rule} | {len(rr)} | {sum(not r['key_matches_gold'] for r in rr)} | "
              f"{cnt['TP']} | **{cnt['FP']}** | {cnt['unjudged']} | "
              f"{sum(not r['key_matches_gold'] for r in fp)} | {sum(r['no_label_rows'] for r in fp)} |")
    nlr = {label: sorted({i for i in items if any(a["action"] == "no_label_rows" for a in G_[label][i].actions)})
           for label in ARMS}
    w("\nItems whose crop + pest key resolved but has no label rows (every option removed as unregistered): " +
      "; ".join(f"{k} {len(x)}" for k, x in nlr.items()) + ".")
    for label in ARMS:
        for r in nlr[label]:
            g = G_[label][r]
            w(f"- {label} {r}: guard key ({g.crop}, {g.pest}); gold ({bench[r]['crop_slug']}, "
              f"{p10.ctx_for(v, res, bench[r]).pest_match().canonical_name}); options removed "
              f"{sum(a['action'] == 'removed_unregistered' for a in g.actions)}")
    w("\nEvery false positive:\n")
    w("| arm | item | rule | a.i. | guard key | gold key |")
    w("|---|---|---|---|---|---|")
    for label in ARMS:
        for r in fps[label]:
            if r["call"] == "FP":
                w(f"| {label} | {r['item_id']} | {r['rule']}{' ' + r['verdict'] if r['verdict'] else ''} | "
                  f"{r['ai']} | {r['key_crop']} / {r['key_pest']} | {r['gold_crop']} / {r['gold_pest']} |")
    dump["removals"] = fps

    # ---- the R4 out-of-range doses and the 10 known Phase 12 overdoses ----------
    w("\n## 5. Out-of-range doses the Phase 12 validator finds\n")
    prompts_b = {r["item_id"]: r for r in p10.jsonl(RAG_PROMPTS_B)}
    recs4 = r5.validate(v, R_["R4_sft_rag"], prompts_b, bench)
    oor = [r for r in recs4 if r["verdict"] in ("HIGH", "LOW")]
    hl = Counter(r["verdict"] for r in oor)
    assert (len(oor), hl["HIGH"], hl["LOW"]) == (32, 18, 14), (len(oor), hl)

    def fate(g, k):
        for a in g.actions:
            if a["action"] in REMOVALS and a.get("option") == k:
                return a["action"]
        return "left: non-guardable answer" if not g.guardable else "left: guardable, kept"
    f4c = Counter((r["verdict"], fate(G_["R4_sft_rag"][r["item_id"]], r["k"])) for r in oor)
    w("R4, fact-sheet validator (all 500 items): 32 out-of-range options, 18 HIGH and 14 LOW.\n")
    w("| verdict | removed_dose | removed_unregistered | left: non-guardable | left: guardable, kept |")
    w("|---|---:|---:|---:|---:|")
    for vd in ("HIGH", "LOW"):
        w(f"| {vd} | {f4c[(vd, 'removed_dose')]} | {f4c[(vd, 'removed_unregistered')]} | "
          f"{f4c[(vd, 'left: non-guardable answer')]} | {f4c[(vd, 'left: guardable, kept')]} |")
    in_phi = sum(phi_only(R_["R4_sft_rag"][r["item_id"]]) for r in oor)
    w(f"\n{in_phi} of the 32 sit in answers whose only schema error is the unknown-PHI invariant "
      f"(guardable under the Step 6 rule; 'unparseable' under the original spec).")
    dump["r4_oor"] = [{"item_id": r["item_id"], "k": r["k"], "ai": r["ai"], "verdict": r["verdict"],
                       "fate": fate(G_["R4_sft_rag"][r["item_id"]], r["k"])} for r in oor]

    merged = sc.load_responses(r5.MERGED_RESP)
    w("\nThe 10 known Phase 12 overdoses (merged Arm B run), guarded in memory:\n")
    w("| item | a.i. | merged answer | guard |")
    w("|---|---|---|---|")
    known = []
    for i, ai in r5.KNOWN_OVERDOSE.items():
        g = G.guard_detailed(merged[i], bench[i]["query_text"], res)
        ks = [k for k, o in enumerate(json.loads(merged[i])["chemical_options"])
              if G.norm_name(o["active_ingredient"]) == G.norm_name(ai)]
        fates = sorted({fate(g, k) for k in ks})
        shape = "schema-valid" if not phi_only(merged[i]) else "PHI-invariant only (invalid)"
        known.append({"item_id": i, "ai": ai, "answer": shape, "fates": fates})
        w(f"| {i} | {ai} | {shape} | {', '.join(fates)} |")
    dump["known_overdoses"] = known
    return "\n".join(L) + "\n", dump


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--md", type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    if not (args.write or args.md):
        ap.error("nothing to do: pass --write and/or --md")

    v = p10.load_verify()
    res = v.VerifyResources.load()
    bench = {r["item_id"]: r for r in p10.jsonl(p10.BENCH)}
    if args.write:
        write(res, bench, args.force)
    if args.md:
        text, dump = md_tables(v, res, bench)
        args.md.write_text(text, encoding="utf-8")
        print("wrote", args.md)
        if args.json:
            args.json.write_text(json.dumps(dump, indent=1, default=str), encoding="utf-8")
            print("wrote", args.json)


if __name__ == "__main__":
    main()
