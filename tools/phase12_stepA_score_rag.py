"""phase12_stepA_score_rag.py — score Phase 12 Arm B (SFT adapter + capped
live-retrieval fact sheet) and compare baseline / SFT / SFT+RAG(B). Numbers
for reports/phase12_stepA_rag_ablation.md.

Imports src/verify.py and src/retrieval.py read-only and never modifies
them, bench.jsonl, or any existing data file. Reuses
tools/phase10_stepB_audit.py for the scoring convention, the dose classifier
and the G5 classifier, and asserts that convention still reproduces
trained_scores.json field for field (0.5203) and baseline_scores_v2.json
(0.1719) before Arm B is scored.

Two outputs are written only when explicitly asked for (Step 4b):

    --write-scores     data/final/eval/rag_B_scores.json, the Arm B per-item
                       verdicts in trained_scores.json's schema.
    --write-rerun-ids  data/interim/rag_B_rerun_ids.json, the item_ids whose
                       generation hit max_new_tokens and must be re-run.

Both refuse to overwrite an existing file without --force, because an Arm B
score file is evidence about one generation run.

Usage:
    python tools/phase12_stepA_score_rag.py --md <tables.md> [--json <dump>]
                                            [--no-tokenizer]
                                            [--write-scores] [--write-rerun-ids]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import phase10_stepB_audit as p10  # noqa: E402

RAG_B_RESP = p10.EVAL / "rag_B_responses.jsonl"
RAG_B_PROMPTS = ROOT / "data" / "interim" / "rag_prompts_B.jsonl"
RAG_B_SCORES = p10.EVAL / "rag_B_scores.json"
RERUN_IDS = ROOT / "data" / "interim" / "rag_B_rerun_ids.json"
# max_new_tokens of the Kaggle generation cell (reports/phase10_stepA_baseline.md).
GEN_CAP_TOKENS = 1200
TOKENIZER_ID = "Qwen/Qwen2.5-7B-Instruct"
DOSE_KINDS = {"DOSE", "REFUSAL_DOSE"}
ARMS = ("baseline", "sft", "rag_b")
ARM_LABEL = {"baseline": "baseline", "sft": "SFT", "rag_b": "SFT+RAG(B)"}
GATES = ["G1_json", "G2_schema", "G3_empty_when_not_answering", "G4_restricted_ai",
         "G5_triple_registered", "G6_unknown_phi_escalates", "G7_trainable_row",
         "G8_dose_basis", "G9_unstated_dose_earned"]
SLICE_LABEL = {1: "1 DOSE", 2: "2 CLARIFY", 3: "3 REFUSAL", 5: "5 NOCHEM"}
OVERDOSE = {"WRONG_HIGH", "WRONG_HIGH_RANGE_TOP"}
SFT_OVERDOSE_ITEMS = {"B1_32", "S1_135", "S1_5524", "S1_67", "S1_512"}  # Phase 10 section 2.2
REFUSAL_LINE = "C1/C2/C3: no chemical option"


# --------------------------------------------------------------------------
# load + integrity
# --------------------------------------------------------------------------

def load_rag_b(bench: dict) -> tuple[dict, dict]:
    raw = p10.jsonl(RAG_B_RESP)
    ids = [r["item_id"] for r in raw]
    errors = [r["item_id"] for r in raw if "__ERROR__" in str(r.get("raw_response", ""))]
    assert len(ids) == len(set(ids)) == len(bench), (len(ids), len(set(ids)))
    assert set(ids) == set(bench), "Arm B ids != bench ids"
    assert not errors, f"__ERROR__ rows: {errors}"
    prompts = {r["item_id"]: r for r in p10.jsonl(RAG_B_PROMPTS)}
    for r in raw:
        p = prompts[r["item_id"]]
        for k in ("rows_available", "rows_included", "truncated", "retrieval_status",
                  "prompt_tokens", "fact_sheet_bucket"):
            assert r[k] == p[k], (r["item_id"], k)
    return {r["item_id"]: r["raw_response"] for r in raw}, prompts


def reproduce_baseline(v, res, bench, baseline, bscores) -> dict:
    got = p10.rescore(v, res, bench, baseline)
    diffs = sum(1 for iid in bench
                if round(got[iid].total, 6) != round(bscores[iid]["total"], 6)
                or got[iid].checks != bscores[iid]["checks"]
                or got[iid].gates != bscores[iid]["gates"]
                or got[iid].excluded != bscores[iid]["excluded"])
    assert diffs == 0, f"baseline re-score differs on {diffs} items"
    m = p10.mean(g.total for g in got.values())
    assert round(m, 4) == 0.1719, m
    return got


def is_json(s: str) -> bool:
    try:
        json.loads(s)
        return True
    except (json.JSONDecodeError, TypeError):
        return False


def _json_err(s: str) -> str:
    try:
        json.loads(s)
        return "parses"
    except json.JSONDecodeError as e:
        return e.msg
    except TypeError:
        return "not a string"


_FS = re.compile(r"<fact_sheet>\n(.*?)\n</fact_sheet>", re.S)


def sheet_rows(user_message: str) -> list[dict]:
    body = _FS.search(user_message).group(1)
    first = body.split("\n", 1)[0]
    return json.loads(first) if first.startswith("[") else []


# --------------------------------------------------------------------------
# aggregation helpers
# --------------------------------------------------------------------------

def fmt(x: float) -> str:
    return "—" if x != x else f"{x:.4f}"


def delta(a: float, b: float) -> str:
    return "—" if a != a or b != b else f"{a - b:+.4f}"


def score_table(title: str, groups: list[tuple[str, list[str]]], R: dict,
                extra: dict | None = None) -> str:
    head = "| " + title + " | n | baseline | SFT | SFT+RAG(B) | Δ B−SFT |"
    sep = "|---|---:|---:|---:|---:|---:|"
    if extra:
        head += " " + " | ".join(extra) + " |"
        sep += "---:|" * len(extra)
    lines = [head, sep]
    for name, ids in groups:
        m = {a: p10.mean(R[a][i].total for i in ids) for a in ARMS}
        row = (f"| {name} | {len(ids)} | {fmt(m['baseline'])} | {fmt(m['sft'])} | "
               f"{fmt(m['rag_b'])} | {delta(m['rag_b'], m['sft'])} |")
        if extra:
            row += " " + " | ".join(str(fn(ids)) for fn in extra.values()) + " |"
        lines.append(row)
    return "\n".join(lines)


def group_by(ids, key) -> list[tuple[str, list[str]]]:
    g = defaultdict(list)
    for i in ids:
        g[key(i)].append(i)
    return sorted(g.items(), key=lambda kv: (-len(kv[1]), str(kv[0])))


def gate_table(R: dict, ids: list[str]) -> str:
    lines = ["| gate | baseline | SFT | SFT+RAG(B) |", "|---|---:|---:|---:|"]
    for g in GATES:
        cells = []
        for a in ARMS:
            ev = [R[a][i].gates[g] for i in ids if g in R[a][i].gates]
            cells.append(f"{sum(ev)}/{len(ev)}" + (f" ({sum(ev)/len(ev):.1%})" if ev else ""))
        lines.append(f"| {g} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def check_table(v, R: dict, ids: list[str]) -> str:
    names = list(v.CHECK_WEIGHTS) + list(v.UNWEIGHTED_CHECKS)
    lines = ["| check | weight | baseline | SFT | SFT+RAG(B) | Δ B−SFT |",
             "|---|---:|---|---|---|---:|"]
    for c in names:
        cells, means = [], {}
        for a in ARMS:
            xs = [R[a][i].checks[c] for i in ids if c in R[a][i].checks]
            means[a] = p10.mean(xs)
            cells.append(f"{fmt(means[a])} (n={len(xs)})" if xs else "n=0")
        w = v.CHECK_WEIGHTS.get(c)
        lines.append(f"| {c} | {w:.2f} | " if w else f"| {c} | — | ")
        lines[-1] += " | ".join(cells) + f" | {delta(means['rag_b'], means['sft'])} |"
    return "\n".join(lines)


def paired_check_table(v, R: dict, ids: list[str]) -> str:
    """Check means on the items where BOTH SFT and B carry the check, so the
    delta is not a change in which items got graded."""
    lines = ["| check | n (both graded) | SFT | SFT+RAG(B) | Δ B−SFT |", "|---|---:|---:|---:|---:|"]
    for c in list(v.CHECK_WEIGHTS) + list(v.UNWEIGHTED_CHECKS):
        both = [i for i in ids if c in R["sft"][i].checks and c in R["rag_b"][i].checks]
        s = p10.mean(R["sft"][i].checks[c] for i in both)
        b = p10.mean(R["rag_b"][i].checks[c] for i in both)
        lines.append(f"| {c} | {len(both)} | {fmt(s)} | {fmt(b)} | {delta(b, s)} |")
    return "\n".join(lines)


def answer_shape(raw: str) -> str:
    try:
        a = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return "cut off at 1,200 tokens"
    if not isinstance(a, dict):
        return "not an object"
    if a.get("chemical_options"):
        return "names chemicals"
    if a.get("query_understood") is False:
        return "refuses: query_understood=false + clarify"
    if a.get("non_chemical_first"):
        return "refuses: non-chemical only"
    return "refuses: nothing offered"


def refusals(v, R: dict, bench: dict, ids) -> dict:
    """Schema-valid ANSWERABLE items with empty chemical_options, as in
    phase10 refusal_audit; 'wrongful' = the gold advisory names a chemical."""
    out = {}
    for a in ARMS:
        ans = empty = wrong = 0
        for i in ids:
            r = R[a][i]
            if r.answerability is not v.Answerability.ANSWERABLE or not r.gates.get("G2_schema"):
                continue
            ans += 1
            if r.advisory is not None and not r.advisory.chemical_options:
                empty += 1
                wrong += bool(bench[i]["gold_advisory"]["chemical_options"])
        out[a] = (ans, empty, wrong)
    return out


# --------------------------------------------------------------------------
# failure reasons
# --------------------------------------------------------------------------

_REASONS = [
    (r"^G1:", "G1 output is not JSON"),
    (r"^G2:", "G2 does not validate against Advisory"),
    (r"^G5: no CIB&RC claim", "G5 a.i. has no CIB&RC claim on this crop/pest"),
    (r"^G5: .* is registered on .* but not for", "G5 a.i. on this crop, but not for this pest"),
    (r"^G5: .*dose stated", "G5/G8 dose basis differs from label"),
    (r"^C1/C2/C3: no chemical option", "C1/C2/C3 refused an answerable question"),
    (r"^C1: ", "C1 dose outside the label"),
    (r"^C2: ", "C2 PHI differs from the label"),
    (r"^C3: ", "C3 formulation not the registered one"),
    (r"^C4: did not escalate", "C4 did not escalate when gold does"),
    (r"^C4: escalated", "C4 escalated when CIB&RC gives a complete answer"),
    (r"^C5: top cause", "C5 top cause is not the queried pest"),
    (r"^C6: non_chemical_first is empty, but CIB&RC lists a biological",
     "C6 no non-chemical step; a biological is registered"),
    (r"^C6: non_chemical_first is empty, but no chemical",
     "C6 no non-chemical step; no chemistry registered"),
    (r"^AMBIGUOUS:", "AMBIGUOUS ground truth (not scored)"),
]


def reason_of(f: str) -> str:
    for rx, label in _REASONS:
        if re.search(rx, f):
            return label
    head = f.split(":", 1)[0]
    body = re.sub(r"'[^']*'", "<q>", f.split(":", 1)[-1])
    return f"{head}:{body[:50]}"


def write_json(path: Path, payload, force: bool, label: str) -> None:
    if path.exists() and not force:
        raise SystemExit(f"{label}: {path} exists; pass --force to replace it")
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)} ({label})")


def scores_payload(bench: dict, results: dict, ids: list[str]) -> list[dict]:
    """trained_scores.json's schema, key for key and in its key order."""
    out = []
    for i in ids:
        r, b = results[i], bench[i]
        out.append({"item_id": i, "slice": b["slice"], "crop": b["crop_slug"],
                    "difficulty": b["difficulty"], "total": r.total, "passed": r.passed,
                    "gates": r.gates, "checks": r.checks, "excluded": r.excluded,
                    "failures": r.failures})
    return out


def rerun_payload(bench: dict, prompts: dict, rag_b: dict, ids: list[str],
                  tok_counts: dict | None) -> dict:
    """The cut-off item_ids, with the evidence that each one is a cut-off."""
    ev = []
    for i in ids:
        s = rag_b[i].rstrip()
        try:
            json.loads(s)
            raise AssertionError(f"{i} parses as JSON; not a cut-off")
        except json.JSONDecodeError as e:
            err = str(e)
        ev.append({"item_id": i, "response_tokens": (tok_counts or {}).get(i),
                   "response_chars": len(rag_b[i]), "json_error": err,
                   "ends_with": s[-40:], "closes_json": s.endswith("}"),
                   "open_braces": s.count("{") - s.count("}"),
                   "options_started": s.count('"active_ingredient"'),
                   "fact_sheet_rows": prompts[i]["fact_sheet_rows"],
                   "rows_available": prompts[i]["rows_available"],
                   "truncated_sheet": prompts[i]["truncated"],
                   "prompt_tokens": prompts[i]["prompt_tokens"],
                   "slice": bench[i]["slice"], "kind": bench[i]["kind"],
                   "crop": bench[i]["crop_slug"]})
    assert not any(e["closes_json"] for e in ev), "a cut-off closes its JSON"
    assert all(e["open_braces"] > 0 for e in ev), "a cut-off has balanced braces"
    return {
        "generated_by": "tools/phase12_stepA_score_rag.py --write-rerun-ids",
        "source": "data/final/eval/rag_B_responses.jsonl",
        "reason": ("generation hit max_new_tokens=1200; the response stops mid-JSON "
                   "and fails G1, scoring 0.0. Re-generate these items only, with a "
                   "larger max_new_tokens, and leave every prompt unchanged."),
        "prompts": "data/interim/rag_prompts_B.jsonl (unchanged; re-use the same user_message)",
        "generation_token_limit": GEN_CAP_TOKENS,
        "max_prompt_tokens_in_set": max(prompts[i]["prompt_tokens"] for i in ids),
        "count": len(ids),
        "item_ids": ids,
        "evidence": ev,
    }


def reason_counts(R: dict, ids) -> dict:
    """Items affected per reason (an item counts once per reason)."""
    return {a: Counter(r for i in ids for r in {reason_of(f) for f in R[a][i].failures})
            for a in ARMS}


# --------------------------------------------------------------------------
# dose: the Phase 10 rule, and the wider scan it skipped
# --------------------------------------------------------------------------

def c1_objections(results: dict, bench: dict, only_zero: bool) -> list[dict]:
    """Every C1 line, classified with phase10 dose_verdict. only_zero=True is
    phase10 dose_audit's item filter (C1_dose == 0.0); False also reads the
    C1 lines on items whose C1 is a fractional mean over several options."""
    rows = []
    for iid, r in results.items():
        c1 = r.checks.get("C1_dose")
        if c1 is None or c1 == 1.0 or (only_zero and c1 != 0.0):
            continue
        if any(f.startswith(REFUSAL_LINE) for f in r.failures):
            continue
        opts = {o.active_ingredient: o for o in (r.advisory.chemical_options if r.advisory else [])}
        for f in r.failures:
            m = p10.C1_MSG.match(f)
            if not m:
                continue
            g = m.groupdict()
            opt = opts.get(g["ai"])
            lo = float(g["lo"])
            mv = float(g["val"])
            rec = {"item_id": iid, "crop": bench[iid]["crop_slug"], "ai": g["ai"],
                   "model_value": mv, "model_value_max": opt.dose.value_max if opt else None,
                   "model_unit": g["unit"] or (opt.dose.unit if opt else None),
                   "model_basis": g["basis"], "label_lo": lo,
                   "label_hi": float(g["hi"]) if g["hi"] else None, "label_unit": g["lunit"],
                   "model_over_label_per_ha": (mv / (lo * p10.ACRE)) if lo else None,
                   "c1_item": c1}
            rec.update(p10.dose_verdict(rec))
            rows.append(rec)
    return rows


# --------------------------------------------------------------------------
# truncation cost (task 8)
# --------------------------------------------------------------------------

def truncation_cost(v, retrieval, res, bench, prompts, rag_b_results) -> dict:
    items, opt_loc = [], Counter()
    for iid, p in prompts.items():
        if not p["truncated"]:
            continue
        full = retrieval.retrieve(p["crop_slug_used"], p["canonical_pest_used"], res,
                                  p["method_used"], max_rows=None)
        cap = retrieval.MAX_FACT_SHEET_ROWS
        assert full.rows_available == p["rows_available"], iid
        shown_pub = [{k: x for k, x in d.items() if not k.startswith("_")}
                     for d in full.rows[:cap]]
        assert shown_pub == sheet_rows(p["user_message"]), f"{iid}: shown rows differ"
        shown = [d["_ai"] for d in full.rows[:cap]]
        cut = [d["_ai"] for d in full.rows[cap:]]
        names = [d["ai"] for d in full.rows]
        gold = [v.normalise_ai(o["active_ingredient"])
                for o in bench[iid]["gold_advisory"]["chemical_options"]]
        in_shown = [g for g in gold if g in shown]
        in_cut_only = [g for g in gold if g not in shown and g in cut]
        absent = [g for g in gold if g not in shown and g not in cut]
        if not gold:
            klass = "gold names no chemical"
        elif in_shown:
            klass = "a gold a.i. is in the 15 shown"
        elif in_cut_only:
            klass = "gold a.i. only in the cut rows"
        else:
            klass = "gold a.i. not in this key's rows at all"
        positions = [next(k for k, c in enumerate(shown + cut) if c == g)
                     for g in gold if g in shown or g in cut]
        adv = rag_b_results[iid].advisory
        for o in (adv.chemical_options if adv else []):
            c = v.normalise_ai(o.active_ingredient)
            opt_loc["in shown 15" if c in shown else "only in cut rows" if c in cut
                    else "in neither"] += 1
        items.append({"item_id": iid, "kind": bench[iid]["kind"], "class": klass,
                      "rows_available": p["rows_available"], "n_gold": len(gold),
                      "n_in_shown": len(in_shown), "n_cut_only": len(in_cut_only),
                      "n_absent": len(absent),
                      "first_gold_position": min(positions) if positions else None,
                      "alphabetical": names == sorted(names, key=str.casefold),
                      "key_is_gold": (p["crop_slug_used"] == bench[iid]["crop_slug"]
                                      and p["canonical_pest_used"] == bench[iid]["canonical_pest"])})
    return {"items": items, "model_option_location": dict(opt_loc)}


# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", type=Path, required=True)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--no-tokenizer", action="store_true")
    ap.add_argument("--write-scores", action="store_true",
                    help=f"write {RAG_B_SCORES.relative_to(ROOT)}")
    ap.add_argument("--write-rerun-ids", action="store_true",
                    help=f"write {RERUN_IDS.relative_to(ROOT)}")
    ap.add_argument("--force", action="store_true",
                    help="replace an existing --write-* output")
    args = ap.parse_args()
    if args.write_rerun_ids and args.no_tokenizer:
        raise SystemExit("--write-rerun-ids records response_tokens; drop --no-tokenizer")

    v = p10.load_verify()
    import retrieval  # after load_verify, so it binds the same verify module
    res = v.VerifyResources.load()
    bench, trained, baseline, tscores, bscores = p10.load_all()
    rag_b, prompts = load_rag_b(bench)

    rep = p10.reproduce(v, res, bench, trained, tscores)
    assert all(n == 0 for n in rep["diffs"].values()), rep["diffs"]
    assert round(rep["mean_nonexcluded"], 4) == 0.5203, rep["mean_nonexcluded"]
    R = {"sft": rep.pop("results"),
         "baseline": reproduce_baseline(v, res, bench, baseline, bscores),
         "rag_b": p10.rescore(v, res, bench, rag_b)}

    ALL = list(bench)
    nonex = {a: {i for i in ALL if not R[a][i].excluded} for a in ARMS}
    inter = [i for i in ALL if all(i in nonex[a] for a in ARMS)]
    nocrop40 = {i for i in ALL if prompts[i]["retrieval_status"] == "no_crop"
                and bench[i]["kind"] in DOSE_KINDS}
    defects = {i for i in ALL if prompts[i]["known_bench_defect"]}
    head = [i for i in inter if i not in nocrop40 and i not in defects]
    cutoff = {i for i in ALL if not is_json(rag_b[i])}

    tok_counts = None
    if not args.no_tokenizer:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained(TOKENIZER_ID)
        tok_counts = {i: len(tok.encode(rag_b[i], add_special_tokens=False)) for i in ALL}

    def bucket(i):
        p = prompts[i]
        return "truncated (15 shown of 16+)" if p["truncated"] else p["fact_sheet_bucket"]
    border = {"0": 0, "1-5": 1, "6-15": 2, "truncated (15 shown of 16+)": 3}

    cut_sorted = sorted(cutoff, key=lambda i: (bench[i]["slice"], i))
    if args.write_scores:
        write_json(RAG_B_SCORES, scores_payload(bench, R["rag_b"], ALL),
                   args.force, "Arm B per-item scores")
    if args.write_rerun_ids:
        write_json(RERUN_IDS, rerun_payload(bench, prompts, rag_b, cut_sorted, tok_counts),
                   args.force, "cut-off item_ids to re-generate")

    md = []
    w = md.append

    # ---- reproduction ----------------------------------------------------
    w("## R. Reproduction\n")
    w(f"- trained_scores.json diffs (total/checks/gates/excluded): {rep['diffs']}")
    w(f"- SFT mean over {rep['n_nonexcluded']} non-excluded: {rep['mean_nonexcluded']:.6f}; "
      f"all 500: {rep['mean_all']:.6f}")
    w(f"- without gold_escalate: {rep['without_gold_escalate_diff']} totals differ, mean "
      f"{rep['without_gold_escalate_mean']:.4f}")
    w(f"- baseline_scores_v2.json: 0 diffs, mean {p10.mean(r.total for r in R['baseline'].values()):.6f}")
    w(f"- Arm B: exclusions {len(ALL) - len(nonex['rag_b'])}, ids "
      f"{sorted(set(ALL) - nonex['rag_b'])}")
    w(f"- exclusions SFT {sorted(set(ALL) - nonex['sft'])}")
    w(f"- generation cut-offs (not JSON): {len(cutoff)}")
    w(f"- SFT not-JSON: {sum(1 for i in ALL if not is_json(trained[i]))}")
    w(f"- sets: intersection {len(inter)}, no_crop40 {len(nocrop40)} "
      f"(in inter {len(nocrop40 & set(inter))}), defects {sorted(defects)}, headline {len(head)}\n")

    # ---- cut-offs (Step 4b task A) ---------------------------------------
    w("### R.1 The 1,200-token cut-offs\n")
    w(f"- count {len(cutoff)}; response tokens on cut-offs "
      f"{sorted(Counter(tok_counts[i] for i in cutoff).items()) if tok_counts else '?'}; "
      f"longest response that did parse "
      f"{max((tok_counts[i] for i in ALL if i not in cutoff), default=0) if tok_counts else '?'}"
      f" tokens")
    w(f"- none closes its JSON: {sum(rag_b[i].rstrip().endswith('}') for i in cutoff)}; "
      f"unclosed braces min {min(rag_b[i].count('{') - rag_b[i].count('}') for i in cutoff)}")
    w(f"- json errors: {dict(Counter(_json_err(rag_b[i]) for i in cutoff))}")
    w(f"- options started: {sorted(Counter(rag_b[i].count(chr(34) + 'active_ingredient' + chr(34)) for i in cutoff).items())}")
    for label, key in (("slice", lambda i: SLICE_LABEL[bench[i]["slice"]]),
                       ("kind", lambda i: bench[i]["kind"]),
                       ("crop", lambda i: bench[i]["crop_slug"]),
                       ("difficulty", lambda i: bench[i]["difficulty"]),
                       ("fact_sheet_rows", lambda i: prompts[i]["fact_sheet_rows"]),
                       ("fact_sheet_bucket", lambda i: bucket(i)),
                       ("retrieval_status", lambda i: prompts[i]["retrieval_status"])):
        c = Counter(key(i) for i in cutoff)
        w(f"- by {label}: {dict(sorted(c.items(), key=lambda kv: (-kv[1], str(kv[0]))))}")
    w(f"- prompt_tokens on cut-offs: min {min(prompts[i]['prompt_tokens'] for i in cutoff)}, "
      f"max {max(prompts[i]['prompt_tokens'] for i in cutoff)}")
    w("")

    # ---- 1 headline ------------------------------------------------------
    w("## 1. Headline\n")
    lines = ["| item set | n | baseline | SFT | SFT+RAG(B) | Δ B−SFT |",
             "|---|---:|---:|---:|---:|---:|"]

    def add(name, ids_by_arm, zero_excluded=False):
        m = {}
        for a in ARMS:
            ids = ids_by_arm[a]
            m[a] = p10.mean(0.0 if zero_excluded and R[a][i].excluded else R[a][i].total
                            for i in ids)
        n = {len(ids_by_arm[a]) for a in ARMS}
        nn = str(n.pop()) if len(n) == 1 else "/".join(str(len(ids_by_arm[a])) for a in ARMS)
        lines.append(f"| {name} | {nn} | {fmt(m['baseline'])} | {fmt(m['sft'])} | "
                     f"{fmt(m['rag_b'])} | {delta(m['rag_b'], m['sft'])} |")

    add("**headline: non-excluded in all three, minus no_crop-40 and 2 defects**",
        {a: head for a in ARMS})
    add("non-excluded in all three (intersection)", {a: inter for a in ARMS})
    add("each arm's own non-excluded set", {a: sorted(nonex[a]) for a in ARMS})
    add("all 500, recorded totals", {a: ALL for a in ARMS})
    add("all 500, excluded scored 0.0", {a: ALL for a in ARMS}, zero_excluded=True)
    h_nocut = [i for i in head if i not in cutoff]
    add("headline minus Arm B's 1,200-token cut-offs (conditional, see text)",
        {a: h_nocut for a in ARMS})
    w("\n".join(lines))
    at1 = {a: sum(R[a][i].total == 1.0 for i in head) for a in ARMS}
    zero = {a: sum(R[a][i].total == 0.0 for i in head) for a in ARMS}
    w(f"\nOn the headline set: items at 1.0 {at1}; items at 0.0 {zero}.")
    better = sum(R['rag_b'][i].total > R['sft'][i].total for i in head)
    worse = sum(R['rag_b'][i].total < R['sft'][i].total for i in head)
    w(f"Paired, headline set: B > SFT on {better}, B < SFT on {worse}, "
      f"equal on {len(head) - better - worse}.")
    cut_head = [i for i in head if i in cutoff]
    w(f"Cut-offs inside headline: {len(cut_head)}; SFT mean on those items "
      f"{fmt(p10.mean(R['sft'][i].total for i in cut_head))}, baseline "
      f"{fmt(p10.mean(R['baseline'][i].total for i in cut_head))}.\n")

    # ---- 2 gates and checks ---------------------------------------------
    w("## 2. Gates and checks\n")
    w("### all 500\n")
    w(gate_table(R, ALL))
    w("")
    w(check_table(v, R, ALL))
    w("\n### headline set\n")
    w(gate_table(R, head))
    w("")
    w(check_table(v, R, head))
    w("\n### headline set, paired (items where SFT and B both carry the check)\n")
    w(paired_check_table(v, R, head))
    rf_all, rf_head = refusals(v, R, bench, ALL), refusals(v, R, bench, head)
    w("\n### refusal on answerable (schema-valid ANSWERABLE, empty chemical_options)\n")
    w("| arm | all 500: answerable / empty / gold names a chemical | headline: same |")
    w("|---|---|---|")
    for a in ARMS:
        w(f"| {ARM_LABEL[a]} | {rf_all[a][0]} / {rf_all[a][1]} / {rf_all[a][2]} | "
          f"{rf_head[a][0]} / {rf_head[a][1]} / {rf_head[a][2]} |")
    w("")

    # ---- 3 slices ---------------------------------------------------------
    w("## 3. By slice, kind, difficulty, crop (headline set)\n")
    cut_col = {"B cut-offs": lambda ids: sum(i in cutoff for i in ids)}
    w(score_table("slice", [(SLICE_LABEL[k], ids) for k, ids in
                            sorted(group_by(head, lambda i: bench[i]["slice"]))], R, cut_col))
    w("")
    w(score_table("kind", group_by(head, lambda i: bench[i]["kind"]), R, cut_col))
    w("")
    order = {"standard": 0, "hard": 1, "edge_case": 2}
    w(score_table("difficulty", sorted(group_by(head, lambda i: bench[i]["difficulty"]),
                                       key=lambda kv: order[kv[0]]), R, cut_col))
    w("")
    w(score_table("crop", group_by(head, lambda i: bench[i]["crop_slug"]), R, cut_col))
    w("")

    # ---- 4 retrieval -------------------------------------------------------
    w("## 4. By retrieval (headline set)\n")
    w(score_table("retrieval_status", group_by(head, lambda i: prompts[i]["retrieval_status"]),
                  R, cut_col))
    w("")

    w(score_table("fact_sheet_bucket", sorted(group_by(head, bucket),
                                              key=lambda kv: border[kv[0]]), R, cut_col))
    w("")
    w(score_table("truncated", group_by(head, lambda i: str(prompts[i]["truncated"])), R, cut_col))
    w("")
    w(score_table("fact_sheet_kind", group_by(head, lambda i: prompts[i]["fact_sheet_kind"]),
                  R, cut_col))
    w("")
    w(score_table("fact_sheet_kind × kind",
                  group_by(head, lambda i: f"{prompts[i]['fact_sheet_kind']} / {bench[i]['kind']}"),
                  R, cut_col))
    w("\n### DOSE/REFUSAL_DOSE, headline set, by fact_sheet_kind: dose checks\n")
    w("| fact_sheet_kind | n | C1 SFT | C1 B | C2 SFT | C2 B | C3 SFT | C3 B | empty-on-answerable SFT | B |")
    w("|---|---:|---|---|---|---|---|---|---:|---:|")
    for fk, ids in group_by([i for i in head if bench[i]["kind"] in DOSE_KINDS],
                            lambda i: prompts[i]["fact_sheet_kind"]):
        cells = []
        for c in ("C1_dose", "C2_phi", "C3_formulation"):
            for a in ("sft", "rag_b"):
                xs = [R[a][i].checks[c] for i in ids if c in R[a][i].checks]
                cells.append(f"{fmt(p10.mean(xs))} (n={len(xs)})")
        rf = refusals(v, R, bench, ids)
        w(f"| {fk} | {len(ids)} | " + " | ".join(cells) + f" | {rf['sft'][1]} | {rf['rag_b'][1]} |")
    rows_dose = [i for i in head if bench[i]["kind"] in DOSE_KINDS
                 and prompts[i]["fact_sheet_kind"] == "rows"]
    w(f"\n### answer shape, DOSE/REFUSAL_DOSE with rows in the sheet (headline, n={len(rows_dose)})\n")
    w("| SFT shape → B shape | items |")
    w("|---|---:|")
    for (s, b), n in Counter((answer_shape(trained[i]), answer_shape(rag_b[i]))
                             for i in rows_dose).most_common():
        w(f"| {s} → {b} | {n} |")
    for a, src in (("SFT", trained), ("B", rag_b)):
        w(f"- {a} shapes: {dict(Counter(answer_shape(src[i]) for i in rows_dose))}")
    n_opts = {a: Counter(len(json.loads(src[i])["chemical_options"]) for i in ALL
                         if answer_shape(src[i]) == "names chemicals")
              for a, src in (("SFT", trained), ("B", rag_b))}
    w(f"- options per complete answer, all 500: SFT {sorted(n_opts['SFT'].items())}, "
      f"B {sorted(n_opts['B'].items())}")
    w(f"- options started inside B's cut-offs: "
      f"{sorted(Counter(rag_b[i].count(chr(34) + 'active_ingredient' + chr(34)) for i in cutoff).items())}")
    w("")

    # ---- 5 no_crop-40 and defects ----------------------------------------
    w("## 5. no_crop-40 and the two bench defects\n")
    nc = sorted(nocrop40)
    nc_inter = [i for i in nc if i in set(inter)]
    w(score_table("set", [("no_crop-40, all", nc), ("no_crop-40, non-excluded in all three", nc_inter)],
                  R, cut_col))
    w(f"\nno_crop-40 by kind {dict(Counter(bench[i]['kind'] for i in nc))}, by gold crop "
      f"{dict(Counter(bench[i]['crop_slug'] for i in nc))}")
    rf = refusals(v, R, bench, nc)
    w(f"no_crop-40 empty-on-answerable (answerable/empty/wrongful): "
      + ", ".join(f"{ARM_LABEL[a]} {rf[a]}" for a in ARMS))
    w(f"no_crop-40 sample queries: " + "; ".join(repr(bench[i]['query_text'][:70]) for i in nc[:6]))
    w("\n| item | gold crop/pest | B resolved crop/pest | rows | baseline | SFT | SFT+RAG(B) | B excluded |")
    w("|---|---|---|---:|---:|---:|---:|---|")
    for i in sorted(defects):
        p, b = prompts[i], bench[i]
        w(f"| {i} | {b['crop_slug']} / {b['canonical_pest']} | {p['crop_slug_used']} / "
          f"{p['canonical_pest_used']} | {p['rows_included']} | {R['baseline'][i].total:.4f} | "
          f"{R['sft'][i].total:.4f} | {R['rag_b'][i].total:.4f} | {R['rag_b'][i].excluded} |")
    for i in sorted(defects):
        w(f"\n{i} B failures: {R['rag_b'][i].failures[:4]}")
    w("")

    # ---- 6 failure reasons ----------------------------------------------
    w("## 6. Failure reasons, items affected, all 500\n")
    rc = reason_counts(R, ALL)
    top_b = [r for r, _ in rc["rag_b"].most_common(10)]
    top_s = [r for r, _ in rc["sft"].most_common(10)]
    w("| # | reason | baseline | SFT | SFT+RAG(B) | Δ B−SFT |")
    w("|---:|---|---:|---:|---:|---:|")
    for k, r in enumerate(top_b, 1):
        w(f"| {k} | {r} | {rc['baseline'][r]} | {rc['sft'][r]} | {rc['rag_b'][r]} | "
          f"{rc['rag_b'][r] - rc['sft'][r]:+d} |")
    dropped = [r for r in top_s if r not in top_b]
    for r in dropped:
        w(f"| — | (SFT top 10) {r} | {rc['baseline'][r]} | {rc['sft'][r]} | {rc['rag_b'][r]} | "
          f"{rc['rag_b'][r] - rc['sft'][r]:+d} |")
    w("")

    # ---- 7 G5 and overdoses --------------------------------------------
    w("## 7. G5 and overdoses\n")
    g5 = {}
    for a in ("sft", "rag_b"):
        g5[a] = p10.g5_audit(v, res, bench, R[a])["failures"]
    w("| arm | items failing G5 / evaluated | of which excluded |")
    w("|---|---|---:|")
    for a in ARMS:
        ev = [i for i in ALL if "G5_triple_registered" in R[a][i].gates]
        fl = [i for i in ev if not R[a][i].gates["G5_triple_registered"]]
        w(f"| {ARM_LABEL[a]} | {len(fl)} / {len(ev)} | {sum(R[a][i].excluded for i in fl)} |")
    w("\n| G5 class | SFT options | SFT items | B options | B items |")
    w("|---|---:|---:|---:|---:|")
    for k in sorted({r["klass"] for a in g5 for r in g5[a]}):
        cs = [(sum(1 for r in g5[a] if r["klass"] == k),
               len({r["item_id"] for r in g5[a] if r["klass"] == k})) for a in ("sft", "rag_b")]
        w(f"| {k} | {cs[0][0]} | {cs[0][1]} | {cs[1][0]} | {cs[1][1]} |")

    # G5 option location vs fact sheet, for B
    loc = Counter()
    for r in g5["rag_b"]:
        rows = sheet_rows(prompts[r["item_id"]]["user_message"])
        comps = v.normalise_ai(r["ai"])
        loc[(r["klass"], any(v.normalise_ai(x["ai"]) == comps for x in rows),
             prompts[r["item_id"]]["fact_sheet_kind"])] += 1
    w("\nB G5-failing options: (class, a.i. in the fact sheet?, fact_sheet_kind) → options")
    for k, n in sorted(loc.items(), key=lambda kv: -kv[1]):
        w(f"- {k}: {n}")

    strict = {a: c1_objections(R[a], bench, only_zero=True) for a in ("sft", "rag_b")}
    wide = {a: c1_objections(R[a], bench, only_zero=False) for a in ("sft", "rag_b")}
    p10_sft = p10.dose_audit(v, res, bench, R["sft"])["failures"]
    assert [(r["item_id"], r["ai"], r["classification"]) for r in p10_sft] == \
           [(r["item_id"], r["ai"], r["classification"]) for r in strict["sft"]]
    sft_od = {r["item_id"] for r in strict["sft"] if r["classification"] in OVERDOSE}
    assert sft_od == SFT_OVERDOSE_ITEMS, sft_od
    w("\n| C1 objection class | SFT (Phase 10 rule) | B (Phase 10 rule) | SFT (all C1 lines) | B (all C1 lines) |")
    w("|---|---:|---:|---:|---:|")
    for k in sorted({r["classification"] for a in wide for r in wide[a]}):
        w(f"| {k} | " + " | ".join(str(sum(r["classification"] == k for r in d[a]))
                                   for d in (strict, wide) for a in ("sft", "rag_b")) + " |")
    w(f"| **total objections / items** | " + " | ".join(
        f"{len(d[a])} / {len({r['item_id'] for r in d[a]})}"
        for d in (strict, wide) for a in ("sft", "rag_b")) + " |")
    for a, src in (("sft", trained), ("rag_b", rag_b)):
        answering = sum(answer_shape(src[i]) == "names chemicals" for i in ALL)
        od_items = {r["item_id"] for r in wide[a] if r["classification"] in OVERDOSE
                    or r["classification"] == "PER_HA_NUMBER_LABELLED_PER_ACRE"}
        w(f"- {ARM_LABEL[a]}: items naming >=1 chemical (complete JSON) {answering}; items with an "
          f"overdose-direction C1 line (WRONG_HIGH, RANGE_TOP or PER_HA-as-per-acre, all C1 lines) "
          f"{len(od_items)}: {sorted(od_items)}")
    for a in ("sft", "rag_b"):
        ph = [r for r in wide[a] if r["classification"] == "PER_HA_NUMBER_LABELLED_PER_ACRE"]
        w(f"\n{ARM_LABEL[a]} PER_HA_NUMBER_LABELLED_PER_ACRE (all C1 lines): " + "; ".join(
            f"{r['item_id']} {r['ai']} {r['model_value']:g} {r['model_unit']}/acre vs label "
            f"{r['label_lo']:g}{'-' + format(r['label_hi'], 'g') if r['label_hi'] else ''}"
            for r in ph))
    for a in ("sft", "rag_b"):
        od = [r for r in wide[a] if r["classification"] in OVERDOSE]
        w(f"\n### genuine overdoses, {ARM_LABEL[a]} (all C1 lines): {len(od)} objections, "
          f"{len({r['item_id'] for r in od})} items\n")
        w("| item | crop | a.i. | model | label | delta | class | C1 on item | a.i. in fact sheet: per-acre dose shown |")
        w("|---|---|---|---|---|---:|---|---:|---|")
        for r in sorted(od, key=lambda r: -r["pct"]):
            mv = f"{r['model_value']:g}" + (f"-{r['model_value_max']:g}" if r["model_value_max"] else "")
            lab = f"{r['label_lo']:g}" + (f"-{r['label_hi']:g}" if r["label_hi"] else " point")
            shown = "—"
            if a == "rag_b":
                comps = v.normalise_ai(r["ai"])
                hits = [x for x in sheet_rows(prompts[r["item_id"]]["user_message"])
                        if v.normalise_ai(x["ai"]) == comps]
                shown = "; ".join(f"{x['dose_per_acre_min']}-{x['dose_per_acre_max']} {x['dose_unit']}"
                                  for x in hits) or "not in sheet"
            w(f"| {r['item_id']} | {r['crop']} | {r['ai']} | {mv} {r['model_unit']} {r['model_basis']} | "
              f"{lab} {r['label_unit']} | {r['pct']:+.1f}% | {r['classification']} | "
              f"{r['c1_item']:.2f} | {shown} |")
    w("")

    # ---- 8 truncation cost ------------------------------------------------
    w("## 8. Truncated items: where the gold chemical sat\n")
    tc = truncation_cost(v, retrieval, res, bench, prompts, R["rag_b"])
    tr = tc["items"]
    w(f"truncated items: {len(tr)}; uncapped list alphabetical by a.i.: "
      f"{sum(t['alphabetical'] for t in tr)}/{len(tr)}; Arm B key == gold key: "
      f"{sum(t['key_is_gold'] for t in tr)}/{len(tr)}; rows_available "
      f"min/max {min(t['rows_available'] for t in tr)}/{max(t['rows_available'] for t in tr)}\n")
    w("| class | items | SFT mean | B mean | Δ B−SFT | B cut-offs |")
    w("|---|---:|---:|---:|---:|---:|")
    for k, ids in group_by([t["item_id"] for t in tr],
                           lambda i: next(t["class"] for t in tr if t["item_id"] == i)):
        ms, mb = p10.mean(R["sft"][i].total for i in ids), p10.mean(R["rag_b"][i].total for i in ids)
        w(f"| {k} | {len(ids)} | {fmt(ms)} | {fmt(mb)} | {delta(mb, ms)} | {sum(i in cutoff for i in ids)} |")
    ng = sum(t["n_gold"] for t in tr)
    w(f"\ngold chemicals across truncated items: {ng}; in shown 15: "
      f"{sum(t['n_in_shown'] for t in tr)}; only in cut rows: {sum(t['n_cut_only'] for t in tr)}; "
      f"in neither: {sum(t['n_absent'] for t in tr)}")
    pos = [t["first_gold_position"] for t in tr if t["first_gold_position"] is not None]
    w(f"first gold position (0-based, uncapped list): {sorted(pos)}")
    w(f"by kind: {dict(Counter((t['kind'], t['class']) for t in tr))}")
    w(f"Arm B recommended options on truncated items, by where the a.i. sits: {tc['model_option_location']}")
    tr_ids = [t["item_id"] for t in tr]
    w("")
    w(score_table("truncated items, by B cut-off", [
        ("B completed its answer", [i for i in tr_ids if i not in cutoff]),
        ("B cut off at 1,200 tokens", [i for i in tr_ids if i in cutoff])], R))
    cut_only_ids = [t["item_id"] for t in tr if t["class"] == "gold a.i. only in the cut rows"]
    w(f"cut-only items: {cut_only_ids}")
    w("")

    # ---- confounds -------------------------------------------------------
    w("## C. Confounds\n")
    by_src = defaultdict(lambda: [0, 0, 0])
    for i in ALL:
        p, b = prompts[i], bench[i]
        src = "sft_test (KCC-sourced)" if b["source"] == "sft_test" else "constructed / label_db"
        by_src[src][0] += 1
        by_src[src][1] += p["crop_slug_used"] == b["crop_slug"]
        by_src[src][2] += (p["crop_slug_used"] == b["crop_slug"]
                           and p["canonical_pest_used"] == b["canonical_pest"])
    w("| bench source | n | B crop == gold crop | B (crop, pest) == gold key |")
    w("|---|---:|---:|---:|")
    for s, (n, c, k) in sorted(by_src.items()):
        w(f"| {s} | {n} | {c} ({c/n:.1%}) | {k} ({k/n:.1%}) |")
    w("")
    w(score_table("B key == gold key (headline)",
                  group_by(head, lambda i: str(prompts[i]["crop_slug_used"] == bench[i]["crop_slug"]
                                               and prompts[i]["canonical_pest_used"] == bench[i]["canonical_pest"])),
                  R, cut_col))
    w("")
    w(score_table("cut-offs by bucket (all 500)",
                  sorted(group_by(ALL, bucket), key=lambda kv: border[kv[0]]), R, cut_col))

    args.md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print("wrote", args.md)
    if args.json:
        args.json.write_text(json.dumps({
            "per_item": {i: {a: {"total": R[a][i].total, "excluded": R[a][i].excluded,
                                 "gates": R[a][i].gates, "checks": R[a][i].checks,
                                 "failures": R[a][i].failures} for a in ARMS}
                         for i in ALL},
            "sets": {"headline": head, "intersection": inter, "no_crop40": nc,
                     "defects": sorted(defects), "cutoff": sorted(cutoff)},
            "c1_wide": wide, "g5": g5, "truncation": tc}, indent=1, default=str),
            encoding="utf-8")
        print("wrote", args.json)


if __name__ == "__main__":
    main()
