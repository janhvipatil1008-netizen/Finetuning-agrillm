"""phase12_step4c_merge_score.py — merge Arm B's three generation passes,
score the merge, and build the four-column comparison
(baseline / SFT / RAG-B 1200 / RAG-B merged).

Passes, all on data/interim/rag_prompts_B.jsonl, unchanged:
    1  rag_B_responses.jsonl         500 items, max_new_tokens 1200
    2  rag_B_rerun_responses.jsonl    75 items, max_new_tokens 2048
    3  rag_B_rerun3_responses.jsonl   39 items, max_new_tokens 3072

Merge rule: each item takes the response from the highest pass in which
it appears AND parses as JSON.

Reuses tools/phase12_stepA_score_rag.py (and through it the Phase 10
harness) without modifying it. Asserts, before anything is written: the
Phase 10 convention reproduces trained_scores.json field for field
(0.5203) and baseline_scores_v2.json; re-scoring pass 1 reproduces
rag_B_scores.json field for field; every merged response parses.

Writes (refusing to overwrite without --force):
    data/final/eval/rag_B_merged_responses.jsonl
    data/final/eval/rag_B_merged_scores.json

Usage:
    python tools/phase12_step4c_merge_score.py --md <tables.md> [--force]
"""

from __future__ import annotations

import argparse
import json
import re
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import phase12_stepA_score_rag as s12  # noqa: E402

p10 = s12.p10
EVAL = p10.EVAL
PASSES = {
    1: (EVAL / "rag_B_responses.jsonl", 1200),
    2: (EVAL / "rag_B_rerun_responses.jsonl", 2048),
    3: (EVAL / "rag_B_rerun3_responses.jsonl", 3072),
}
MERGED_RESP = EVAL / "rag_B_merged_responses.jsonl"
MERGED_SCORES = EVAL / "rag_B_merged_scores.json"
ARMS = ("baseline", "sft", "rag_b", "rag_m")
LABEL = {"baseline": "baseline", "sft": "SFT", "rag_b": "RAG-B (1200)",
         "rag_m": "RAG-B (merged)"}
PASS1_META = ("fact_sheet_rows", "fact_sheet_bucket", "rows_available", "rows_included",
              "truncated", "retrieval_status", "prompt_tokens")
# label_db row behind B1_36: raw "0.04" stored as a per-hectare rate
# (reports/phase10_stepB_posttrain_audit.md section 2.2a).
LABEL_DEFECT = {("B1_36", "Lambda-cyhalothrin 05% EC")}


# --------------------------------------------------------------------------
# merge
# --------------------------------------------------------------------------

def load_passes(bench: dict) -> dict[int, dict[str, dict]]:
    out = {}
    for k, (path, _cap) in PASSES.items():
        rows = p10.jsonl(path)
        ids = [r["item_id"] for r in rows]
        assert len(ids) == len(set(ids)), f"pass {k}: duplicate ids"
        assert not [i for r, i in zip(rows, ids) if "__ERROR__" in str(r.get("raw_response", ""))], \
            f"pass {k}: __ERROR__ rows"
        out[k] = {r["item_id"]: r for r in rows}
    assert set(out[1]) == set(bench), "pass 1 ids != bench ids"
    assert set(out[3]) <= set(out[2]) <= set(out[1]), "passes are not nested"
    return out


def merge(passes: dict, prompts: dict, bench: dict) -> list[dict]:
    merged = []
    for iid in bench:
        k = max(p for p in passes if iid in passes[p] and s12.is_json(passes[p][iid]["raw_response"]))
        r = passes[k][iid]
        row = {"item_id": iid, "raw_response": r["raw_response"], "source_pass": k,
               "max_new_tokens": PASSES[k][1], "output_tokens": r.get("output_tokens")}
        row.update({f: prompts[iid][f] for f in PASS1_META})
        merged.append(row)
    assert len(merged) == len({m["item_id"] for m in merged}) == 500
    assert all(s12.is_json(m["raw_response"]) for m in merged)
    return merged


def prefix_divergence(a: dict, b: dict) -> list[int | None]:
    out = []
    for i in b:
        x, y = a[i]["raw_response"], b[i]["raw_response"]
        out.append(None if y.startswith(x) else
                   next((k for k, (p, q) in enumerate(zip(x, y)) if p != q), min(len(x), len(y))))
    return out


# --------------------------------------------------------------------------
# four-column tables
# --------------------------------------------------------------------------

fmt, delta = s12.fmt, s12.delta


def t4(title: str, groups, R: dict, extra: dict | None = None) -> str:
    cols = [LABEL[a] for a in ARMS]
    head = f"| {title} | n | " + " | ".join(cols) + " | Δ merged−SFT | Δ merged−1200 |"
    sep = "|---|---:|" + "---:|" * (len(ARMS) + 2)
    if extra:
        head += " " + " | ".join(extra) + " |"
        sep += "---:|" * len(extra)
    lines = [head, sep]
    for name, ids in groups:
        m = {a: p10.mean(R[a][i].total for i in ids) for a in ARMS}
        row = (f"| {name} | {len(ids)} | " + " | ".join(fmt(m[a]) for a in ARMS) +
               f" | {delta(m['rag_m'], m['sft'])} | {delta(m['rag_m'], m['rag_b'])} |")
        if extra:
            row += " " + " | ".join(str(fn(ids)) for fn in extra.values()) + " |"
        lines.append(row)
    return "\n".join(lines)


def gate4(R: dict, ids) -> str:
    lines = ["| gate | " + " | ".join(LABEL[a] for a in ARMS) + " |",
             "|---|" + "---:|" * len(ARMS)]
    for g in s12.GATES:
        cells = []
        for a in ARMS:
            ev = [R[a][i].gates[g] for i in ids if g in R[a][i].gates]
            cells.append(f"{sum(ev)}/{len(ev)}" + (f" ({sum(ev) / len(ev):.1%})" if ev else ""))
        lines.append(f"| {g} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def check4(v, R: dict, ids) -> str:
    lines = ["| check | weight | " + " | ".join(LABEL[a] for a in ARMS) + " | Δ merged−SFT |",
             "|---|---:|" + "---|" * len(ARMS) + "---:|"]
    for c in list(v.CHECK_WEIGHTS) + list(v.UNWEIGHTED_CHECKS):
        cells, means = [], {}
        for a in ARMS:
            xs = [R[a][i].checks[c] for i in ids if c in R[a][i].checks]
            means[a] = p10.mean(xs)
            cells.append(f"{fmt(means[a])} (n={len(xs)})" if xs else "n=0")
        w = v.CHECK_WEIGHTS.get(c)
        lines.append((f"| {c} | {w:.2f} | " if w else f"| {c} | — | ") + " | ".join(cells) +
                     f" | {delta(means['rag_m'], means['sft'])} |")
    return "\n".join(lines)


def paired(v, R: dict, ids, a: str, b: str) -> str:
    lines = [f"| check | n (both graded) | {LABEL[a]} | {LABEL[b]} | Δ |", "|---|---:|---:|---:|---:|"]
    for c in list(v.CHECK_WEIGHTS) + list(v.UNWEIGHTED_CHECKS):
        both = [i for i in ids if c in R[a][i].checks and c in R[b][i].checks]
        x = p10.mean(R[a][i].checks[c] for i in both)
        y = p10.mean(R[b][i].checks[c] for i in both)
        lines.append(f"| {c} | {len(both)} | {fmt(x)} | {fmt(y)} | {delta(y, x)} |")
    return "\n".join(lines)


def refusal4(v, R: dict, bench: dict, ids) -> dict:
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

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", type=Path, required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    v = p10.load_verify()
    res = v.VerifyResources.load()
    bench, trained, baseline, tscores, bscores = p10.load_all()
    pass1_raw, prompts = s12.load_rag_b(bench)
    passes = load_passes(bench)
    merged = merge(passes, prompts, bench)
    rag_m = {m["item_id"]: m["raw_response"] for m in merged}
    src = {m["item_id"]: m["source_pass"] for m in merged}

    # ---- harness reproduction -------------------------------------------
    rep = p10.reproduce(v, res, bench, trained, tscores)
    assert all(n == 0 for n in rep["diffs"].values()), rep["diffs"]
    assert round(rep["mean_nonexcluded"], 4) == 0.5203, rep["mean_nonexcluded"]
    R = {"sft": rep.pop("results"),
         "baseline": s12.reproduce_baseline(v, res, bench, baseline, bscores),
         "rag_b": p10.rescore(v, res, bench, pass1_raw),
         "rag_m": p10.rescore(v, res, bench, rag_m)}
    saved = {r["item_id"]: r for r in json.loads((EVAL / "rag_B_scores.json").read_text(encoding="utf-8"))}
    for i in bench:
        g, w = R["rag_b"][i], saved[i]
        assert (g.total, g.passed, g.gates, g.checks, g.excluded, g.failures) == \
               (w["total"], w["passed"], w["gates"], w["checks"], w["excluded"], w["failures"]), i
    for i in bench:
        if src[i] == 1:
            assert R["rag_m"][i].total == R["rag_b"][i].total and R["rag_m"][i].failures == R["rag_b"][i].failures, i

    # ---- write ------------------------------------------------------------
    if MERGED_RESP.exists() and not args.force:
        raise SystemExit(f"{MERGED_RESP} exists; pass --force to replace it")
    with open(MERGED_RESP, "w", encoding="utf-8", newline="\n") as fh:
        for m in merged:
            fh.write(json.dumps(m, ensure_ascii=False) + "\n")
    print(f"wrote {MERGED_RESP.relative_to(ROOT)} ({len(merged)} rows)")
    s12.write_json(MERGED_SCORES, s12.scores_payload(bench, R["rag_m"], list(bench)),
                   args.force, "merged Arm B per-item scores")

    # ---- sets -------------------------------------------------------------
    ALL = list(bench)
    nonex = {a: {i for i in ALL if not R[a][i].excluded} for a in ARMS}
    inter3 = [i for i in ALL if all(i in nonex[a] for a in ("baseline", "sft", "rag_b"))]
    nocrop40 = {i for i in ALL if prompts[i]["retrieval_status"] == "no_crop"
                and bench[i]["kind"] in s12.DOSE_KINDS}
    defects = {i for i in ALL if prompts[i]["known_bench_defect"]}
    head = [i for i in inter3 if i not in nocrop40 and i not in defects]
    assert len(head) == 448, len(head)
    head_m_ex = [i for i in head if R["rag_m"][i].excluded]
    head4 = [i for i in head if i not in set(head_m_ex)]
    inter4 = [i for i in ALL if all(i in nonex[a] for a in ARMS)]
    regen = [i for i in ALL if src[i] > 1]
    from_col = {"from pass 2/3": lambda ids: sum(src[i] > 1 for i in ids)}

    md = []
    w = md.append

    # ---- A integrity --------------------------------------------------------
    w("## A. Integrity\n")
    for k, (path, cap) in PASSES.items():
        rows = passes[k]
        w(f"- pass {k} ({path.name}, max_new_tokens {cap}): {len(rows)} rows, "
          f"parse {sum(s12.is_json(r['raw_response']) for r in rows.values())}/{len(rows)}, "
          f"__ERROR__ 0")
    w(f"- nesting: pass 3 ⊂ pass 2 ⊂ pass 1 = bench; pass 2 ids == pass 1 non-parsing ids; "
      f"pass 3 ids == pass 2 non-parsing ids")
    for a, b in ((1, 2), (1, 3), (2, 3)):
        same = [i for i in passes[b] if passes[a][i]["raw_response"] == passes[b][i]["raw_response"]]
        d = [x for x in prefix_divergence(passes[a], passes[b]) if x is not None]
        w(f"- pass {a} vs pass {b}: identical responses {len(same)}/{len(passes[b])}; "
          f"earlier pass reproduced as a prefix {len(passes[b]) - len(d)}/{len(passes[b])}"
          + (f"; diverge at char min {min(d)}, median {st.median(d)}, max {max(d)}" if d else ""))
    w(f"- merged: 500 rows, 500 unique, all parse; contributions {dict(sorted(Counter(src.values()).items()))}")
    w(f"- pass 3 output_tokens: min {min(r['output_tokens'] for r in passes[3].values())}, "
      f"max {max(r['output_tokens'] for r in passes[3].values())}")
    w(f"- harness: trained_scores.json diffs {rep['diffs']}, mean {rep['mean_nonexcluded']:.6f}; "
      f"pass 1 re-score == rag_B_scores.json on all 500; pass-1-sourced items identical in merged")
    w(f"- merged exclusions: {sorted(set(ALL) - nonex['rag_m'])}; inside the 448: {head_m_ex}\n")

    # ---- 1 headline ---------------------------------------------------------
    w("## 1. Headline\n")
    lines = ["| item set | n | " + " | ".join(LABEL[a] for a in ARMS) + " | Δ merged−SFT | Δ merged−1200 |",
             "|---|---:|" + "---:|" * (len(ARMS) + 2)]

    def add(name, ids, zero_ex=False):
        m = {a: p10.mean(0.0 if zero_ex and R[a][i].excluded else R[a][i].total for i in ids) for a in ARMS}
        lines.append(f"| {name} | {len(ids)} | " + " | ".join(fmt(m[a]) for a in ARMS) +
                     f" | {delta(m['rag_m'], m['sft'])} | {delta(m['rag_m'], m['rag_b'])} |")
    add("**the 448-item headline set (as before)**", head)
    if head_m_ex:
        add("448 minus merged exclusions", head4)
    add("non-excluded in all four", inter4)
    add("all 500, recorded totals", ALL)
    add("all 500, excluded scored 0.0", ALL, zero_ex=True)
    w("\n".join(lines))
    for a in ARMS:
        ex = sorted(set(ALL) - nonex[a])
        w(f"- {LABEL[a]} exclusions: {len(ex)}")
    at1 = {LABEL[a]: sum(R[a][i].total == 1.0 for i in head) for a in ARMS}
    z = {LABEL[a]: sum(R[a][i].total == 0.0 for i in head) for a in ARMS}
    w(f"\nheadline: at 1.0 {at1}; at 0.0 {z}")
    up = sum(R["rag_m"][i].total > R["sft"][i].total for i in head)
    dn = sum(R["rag_m"][i].total < R["sft"][i].total for i in head)
    w(f"paired merged vs SFT on 448: up {up}, down {dn}, equal {len(head) - up - dn}")
    rh = [i for i in head if src[i] > 1]
    w(f"regenerated items inside 448: {len(rh)} (pass 2 {sum(src[i] == 2 for i in rh)}, "
      f"pass 3 {sum(src[i] == 3 for i in rh)})")
    w("")
    w(t4("regenerated items only", [("all regenerated (in 448)", rh),
                                     ("from pass 2 (2,048)", [i for i in rh if src[i] == 2]),
                                     ("from pass 3 (3,072)", [i for i in rh if src[i] == 3]),
                                     ("not regenerated (in 448)", [i for i in head if src[i] == 1])], R))
    m = {a: p10.mean(R[a][i].total for i in head) for a in ARMS}
    w(f"\n**decomposition on 448:** 1200 − SFT = {m['rag_b'] - m['sft']:+.4f} = "
      f"(merged − SFT {m['rag_m'] - m['sft']:+.4f}) + (1200 − merged {m['rag_b'] - m['rag_m']:+.4f})\n")

    # ---- 2 G1 ------------------------------------------------------------------
    w("## 2. G1 pass rate\n")
    w("| set | " + " | ".join(LABEL[a] for a in ARMS) + " |")
    w("|---|" + "---:|" * len(ARMS))
    for name, ids in (("all 500", ALL), ("448 headline", head)):
        w(f"| {name} | " + " | ".join(
            f"{sum(R[a][i].gates.get('G1_json', False) for i in ids)}/{len(ids)} "
            f"({sum(R[a][i].gates.get('G1_json', False) for i in ids) / len(ids):.1%})" for a in ARMS) + " |")
    w("")

    # ---- 3 gates and checks -------------------------------------------------------
    w("## 3. Gates and checks\n### all 500\n")
    w(gate4(R, ALL))
    w("")
    w(check4(v, R, ALL))
    w("\n### 448 headline\n")
    w(check4(v, R, head))
    w("\n### 448 headline, paired SFT vs merged\n")
    w(paired(v, R, head, "sft", "rag_m"))
    w("\n### refusal on answerable (answerable / empty / gold names a chemical)\n")
    rf_all, rf_head = refusal4(v, R, bench, ALL), refusal4(v, R, bench, head)
    w("| arm | all 500 | 448 |")
    w("|---|---|---|")
    for a in ARMS:
        w(f"| {LABEL[a]} | {rf_all[a][0]} / {rf_all[a][1]} / {rf_all[a][2]} | "
          f"{rf_head[a][0]} / {rf_head[a][1]} / {rf_head[a][2]} |")
    w("\n### failure reasons, items affected, all 500 (top 12 by merged)\n")
    rc = {a: Counter(r for i in ALL for r in {s12.reason_of(f) for f in R[a][i].failures}) for a in ARMS}
    w("| reason | " + " | ".join(LABEL[a] for a in ARMS) + " |")
    w("|---|" + "---:|" * len(ARMS))
    for r, _ in rc["rag_m"].most_common(12):
        w(f"| {r} | " + " | ".join(str(rc[a][r]) for a in ARMS) + " |")
    w("")

    # ---- 4 breakdowns ----------------------------------------------------------------
    def bucket(i):
        p = prompts[i]
        return "truncated (15 shown of 16+)" if p["truncated"] else p["fact_sheet_bucket"]
    border = {"0": 0, "1-5": 1, "6-15": 2, "truncated (15 shown of 16+)": 3}
    order = {"standard": 0, "hard": 1, "edge_case": 2}
    w("## 4. Breakdowns (448 headline)\n")
    w(t4("slice", [(s12.SLICE_LABEL[k], ids) for k, ids in
                   sorted(s12.group_by(head, lambda i: bench[i]["slice"]))], R, from_col))
    w("")
    w(t4("difficulty", sorted(s12.group_by(head, lambda i: bench[i]["difficulty"]),
                              key=lambda kv: order[kv[0]]), R, from_col))
    w("")
    w(t4("crop", s12.group_by(head, lambda i: bench[i]["crop_slug"]), R, from_col))
    w("")
    w(t4("retrieval_status", s12.group_by(head, lambda i: prompts[i]["retrieval_status"]), R, from_col))
    w("")
    w(t4("fact_sheet_bucket", sorted(s12.group_by(head, bucket), key=lambda kv: border[kv[0]]), R, from_col))
    w("")
    w(t4("truncated", s12.group_by(head, lambda i: str(prompts[i]["truncated"])), R, from_col))
    w("")

    # ---- 5 overdoses ---------------------------------------------------------------
    w("## 5. Overdoses, every C1 line\n")
    wide = {a: s12.c1_objections(R[a], bench, only_zero=False) for a in ("sft", "rag_b", "rag_m")}
    w("| C1 objection class | SFT | RAG-B (1200) | RAG-B (merged) |")
    w("|---|---:|---:|---:|")
    for k in sorted({r["classification"] for a in wide for r in wide[a]}):
        w(f"| {k} | " + " | ".join(str(sum(r["classification"] == k for r in wide[a]))
                                   for a in ("sft", "rag_b", "rag_m")) + " |")
    w("| total objections / items | " + " | ".join(
        f"{len(wide[a])} / {len({r['item_id'] for r in wide[a]})}" for a in ("sft", "rag_b", "rag_m")) + " |")
    raws = {"sft": trained, "rag_b": pass1_raw, "rag_m": rag_m}
    for a in ("sft", "rag_b", "rag_m"):
        od = [r for r in wide[a] if r["classification"] in s12.OVERDOSE
              and (r["item_id"], r["ai"]) not in LABEL_DEFECT]
        dropped = [r for r in wide[a] if (r["item_id"], r["ai"]) in LABEL_DEFECT]
        ph = [r for r in wide[a] if r["classification"] == "PER_HA_NUMBER_LABELLED_PER_ACRE"]
        answering = sum(s12.answer_shape(raws[a][i]) == "names chemicals" for i in ALL)
        od_items = {r["item_id"] for r in od}
        dir_items = od_items | {r["item_id"] for r in ph}
        w(f"\n- {LABEL[a]}: genuine overdose items {len(od_items)} ({len(od)} objections); "
          f"label-defect objections dropped {len(dropped)}; per-ha-as-per-acre {len(ph)} objections on "
          f"{len({r['item_id'] for r in ph})} items; items naming chemicals {answering}; "
          f"overdose-direction items {len(dir_items)} ({len(dir_items) / answering:.1%})")
    od_m = [r for r in wide["rag_m"] if r["classification"] in s12.OVERDOSE
            and (r["item_id"], r["ai"]) not in LABEL_DEFECT]
    ph_m = [r for r in wide["rag_m"] if r["classification"] == "PER_HA_NUMBER_LABELLED_PER_ACRE"]
    w("\n### merged: every overdose-direction objection\n")
    w("| item | pass | crop | a.i. | model | label | delta | class | C1 on item | fact sheet per-acre for this a.i. |")
    w("|---|---:|---|---|---|---|---:|---|---:|---|")
    for r in sorted(od_m + ph_m, key=lambda r: (-(r["pct"] or 0), r["item_id"])):
        mv = f"{r['model_value']:g}" + (f"-{r['model_value_max']:g}" if r["model_value_max"] else "")
        lab = f"{r['label_lo']:g}" + (f"-{r['label_hi']:g}" if r["label_hi"] else " point")
        comps = v.normalise_ai(r["ai"])
        hits = [x for x in s12.sheet_rows(prompts[r["item_id"]]["user_message"])
                if v.normalise_ai(x["ai"]) == comps]
        shown = "; ".join(f"{x['dose_per_acre_min']}-{x['dose_per_acre_max']} {x['dose_unit']}"
                          for x in hits) or "not in sheet"
        pct = f"{r['pct']:+.1f}%" if r["pct"] is not None else "—"
        w(f"| {r['item_id']} | {src[r['item_id']]} | {r['crop']} | {r['ai']} | {mv} {r['model_unit']} "
          f"{r['model_basis']} | {lab} {r['label_unit']} | {pct} | {r['classification']} | "
          f"{r['c1_item']:.2f} | {shown} |")
    new_od = sorted({r["item_id"] for r in od_m + ph_m if src[r["item_id"]] > 1})
    w(f"\noverdose-direction items that come from regenerated answers: {new_od}")
    graded = {a: sum(s12.answer_shape(raws[a][i]) == "names chemicals" and R[a][i].gates.get("G2_schema")
                     for i in ALL) for a in ("sft", "rag_b", "rag_m")}
    w(f"items naming chemicals AND passing G2 (so their doses were graded): "
      + ", ".join(f"{LABEL[a]} {graded[a]}" for a in graded))

    # Doses the verifier never graded: G2 stops verify() before C1.
    w("\n### 5b. Doses inside G2-failed answers (not graded by verify; checked against the sheet)\n")
    fip = Counter()
    hidden = []
    for a in ("sft", "rag_m"):
        for i in ALL:
            if R[a][i].gates.get("G2_schema", True) or not s12.is_json(raws[a][i]):
                continue
            adv = json.loads(raws[a][i])
            sh = s12.sheet_rows(prompts[i]["user_message"]) if a == "rag_m" else []
            for o in adv.get("chemical_options") or []:
                d = o.get("dose") or {}
                hits = [x for x in sh if v.normalise_ai(x["ai"]) == v.normalise_ai(o["active_ingredient"])
                        and x["dose_unit"] == d.get("unit")]
                if not hits or d.get("basis") != "per_acre" or d.get("value_min") is None:
                    continue
                top = max((x["dose_per_acre_max"] or x["dose_per_acre_min"]) for x in hits
                          if x["dose_per_acre_min"] is not None) if any(
                    x["dose_per_acre_min"] is not None for x in hits) else None
                if top is None:
                    continue
                hi_val = d.get("value_max") or d["value_min"]
                if hi_val > top * 1.08:
                    hidden.append((a, i, src.get(i), o["active_ingredient"], d["value_min"], d.get("value_max"),
                                   top, (hi_val / top - 1) * 100))
    w(f"- G2-failed answers: SFT {sum(not R['sft'][i].gates.get('G2_schema', True) for i in ALL)}, "
      f"merged {sum(not R['rag_m'][i].gates.get('G2_schema', True) for i in ALL)}")
    w(f"- per-acre options above the sheet's top value by >8%: {len(hidden)} on "
      f"{len({h[1] for h in hidden})} items")
    for h in sorted(hidden, key=lambda h: -h[7]):
        w(f"  - {h[1]} (pass {h[2]}) {h[3]}: {h[4]:g}{'-' + format(h[5], 'g') if h[5] else ''} "
          f"vs sheet top {h[6]:g} ({h[7]:+.1f}%)")
    for i in ALL:
        if not s12.is_json(rag_m[i]):
            continue
        for o in json.loads(rag_m[i]).get("chemical_options") or []:
            if o["active_ingredient"].replace(" ", "").lower().startswith("fipronil80"):
                fip[(bench[i]["crop_slug"], o["dose"].get("value_min"), o["dose"].get("unit"))] += 1
    w(f"- every Fipronil 80% WG option in the merged answers, (crop, value_min, unit) → count: {dict(fip)}")
    w("")

    # ---- 5c G2 ------------------------------------------------------------------
    w("### 5c. G2 failures in the merged run\n")
    g2m = [i for i in ALL if R["rag_m"][i].gates.get("G2_schema") is False]
    w(f"- {len(g2m)} items; by source pass {dict(sorted(Counter(src[i] for i in g2m).items()))}; "
      f"inside 448: {sum(i in set(head) for i in g2m)}")
    w(f"- messages: {dict(Counter(R['rag_m'][i].failures[0].split('error(s): ')[-1] for i in g2m))}")
    nul, cop = 0, 0
    for i in g2m:
        for o in json.loads(rag_m[i])["chemical_options"]:
            if o.get("phi_days") is None and not o.get("phi_not_applicable"):
                nul += 1
                key = re.sub(r"[^a-z0-9]", "", o["active_ingredient"].lower())
                row = next((x for x in s12.sheet_rows(prompts[i]["user_message"])
                            if re.sub(r"[^a-z0-9]", "", x["ai"].lower()) == key), None)
                cop += bool(row and row["phi_days"] is None and not row["phi_not_applicable"])
    w(f"- PHI-unknown options in those answers: {nul}; copied from a sheet row whose PHI is unknown: {cop}")
    w(f"- escalate_to_expert set on G2-failed answers: "
      f"{sum(bool(json.loads(rag_m[i]).get('escalate_to_expert')) for i in g2m)}")
    reg = [i for i in ALL if src[i] > 1]
    has_null = [i for i in reg if any(x["phi_days"] is None and not x["phi_not_applicable"]
                                      for x in s12.sheet_rows(prompts[i]["user_message"]))]
    w(f"- regenerated items whose sheet has a PHI-unknown row: {len(has_null)}/{len(reg)}; "
      f"of those G2-failed {sum(i in set(g2m) for i in has_null)}; "
      f"regenerated answers that escalate {sum(bool(json.loads(rag_m[i]).get('escalate_to_expert')) for i in reg)}")
    sft_null = [i for i in ALL if s12.is_json(trained[i]) and any(
        o.get("phi_days") is None and not o.get("phi_not_applicable")
        for o in json.loads(trained[i]).get("chemical_options") or [])]
    w(f"- SFT answers carrying a PHI-unknown option: {len(sft_null)}, escalated "
      f"{sum(bool(json.loads(trained[i]).get('escalate_to_expert')) for i in sft_null)}")
    rh_ok = [i for i in rh if R["rag_m"][i].gates.get("G2_schema")]
    w("")
    w(t4("regenerated items in 448, by merged G2", [
        ("G2 pass", rh_ok), ("G2 fail (unknown PHI, not escalated)", [i for i in rh if i not in set(rh_ok)])], R))
    w("")

    # ---- 6 diagnostic findings --------------------------------------------------
    w("## 6. Diagnostic findings\n")
    p2 = passes[2]
    r15 = [i for i in p2 if p2[i]["fact_sheet_rows"] == 15]
    fin = [i for i in r15 if not p2[i]["hit_limit"]]
    ran = [i for i in r15 if p2[i]["hit_limit"]]
    nopt = lambda s: len(json.loads(s).get("chemical_options") or [])
    w(f"- pass 2, 15-row sheets: {len(r15)} items; completed {len(fin)} with options "
      f"{sorted(Counter(nopt(p2[i]['raw_response']) for i in fin).items())}; hit 2,048 on {len(ran)}")
    p3 = passes[3]
    w(f"- pass 3 (39): options vs fact_sheet_rows: "
      f"{sorted(Counter((p3[i]['fact_sheet_rows'], nopt(p3[i]['raw_response'])) for i in p3).items())}")
    w(f"- pass 3 options == fact_sheet_rows: {sum(nopt(p3[i]['raw_response']) == p3[i]['fact_sheet_rows'] for i in p3)}/39; "
      f"output_tokens median {st.median(p3[i]['output_tokens'] for i in p3)}")
    w(f"- pass 3 ran out at 2,048 and finished at 3,072: the 35 15-row items now list "
      f"{sorted(Counter(nopt(p3[i]['raw_response']) for i in ran).items())}")
    s237 = json.loads(rag_m["S1_237"])
    fip = [o for o in s237["chemical_options"] if "ipronil" in o["active_ingredient"]]
    sheet237 = [x["ai"] for x in s12.sheet_rows(prompts["S1_237"]["user_message"]) if "IPRONIL" in x["ai"].upper()]
    w(f"- S1_237 (merged, pass {src['S1_237']}): model writes "
      f"{[o['active_ingredient'] for o in fip]} / formulation {[o['formulation'] for o in fip]}; sheet says {sheet237}")
    w(f"  S1_237 merged failures mentioning Fipronil: "
      f"{[f for f in R['rag_m']['S1_237'].failures if 'ipronil' in f or 'IPRONIL' in f]}; "
      f"checks {R['rag_m']['S1_237'].checks}; total {R['rag_m']['S1_237'].total}")
    w(f"- non-determinism: see section A (pass 1 → 2 and pass 2 → 3 prefix reproduction)")

    args.md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print("wrote", args.md)


if __name__ == "__main__":
    main()
