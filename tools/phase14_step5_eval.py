"""phase14_step5_eval.py -- Phase 14 Step 5: the clean R2/R4 evaluation.
Numbers for reports/phase14_clean_eval.md. No GPU.

READ ONLY. Imports verify.py through phase10_stepB_audit and scores through
tools/score.py; writes only the --md tables (and --json if asked). Before
reporting anything it asserts, rather than assumes:

  A  integrity of R2/R4_responses.jsonl and their manifests -- 500 unique
     bench item_ids, no torn lines, no __ERROR__ rows, every prompt_sha256
     equal to prompts_R2/R4.jsonl, max_new_tokens 3072, repetition_penalty
     1.05, greedy, adapter on R4 only.
  -  every scores_<label>.json re-scores to the same per-item verdicts, so
     the table is the committed files, not a fresh guess.
  -  Phase 12's 448-item set reproduces SFT 0.5467, pass 1 0.5443 and merged
     0.6143 before R4 is reported on it.

Sections:
  D  noise floor -- R4 against Phase 12 pass 1 (rag_B_responses.jsonl), the
     same prompts: IDENTICAL / PREFIX (pass 1 was cut off at 1,200 tokens and
     R4 continues it) / DIFFERENT, and the score differences that follow.
  E  canonical table on the 498-item denominator, the all-arms intersection,
     and paired comparisons: mean difference, wins / losses / ties, two-sided
     exact sign test (ties dropped), percentile bootstrap 95% CI of the mean
     difference (10,000 resamples of items, numpy default_rng(0), fresh per
     comparison).

hit_limit: R2/R4 from the recorded field. R0/R3 were 1,200-token runs that
recorded none; there it is a response that does not parse and re-encodes to
>= 1,199 Qwen tokens (decode/re-encode can shift the count by one).

Usage:
    python tools/phase14_step5_eval.py --md <tables.md> [--json <dump>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import phase10_stepB_audit as p10  # noqa: E402
import score as sc  # noqa: E402
from run_rag_eval import DOSE_KINDS, load_tokenizer  # noqa: E402

EVAL = p10.EVAL
PROMPTS_DIR = ROOT / "data" / "final" / "prompts"
RAG_PROMPTS_B = ROOT / "data" / "interim" / "rag_prompts_B.jsonl"
RERUN_IDS = ROOT / "data" / "interim" / "rag_B_rerun_ids.json"
PASS1 = EVAL / "rag_B_responses.jsonl"
MERGED = EVAL / "rag_B_merged_responses.jsonl"

# label -> (responses file, max_new_tokens of the run, --unwrap-advisory)
ARMS = {
    "R0_baseline": ("baseline_responses.jsonl", 1200, False),
    "R3_sft": ("trained_responses.jsonl", 1200, False),
    "R2_base_rag": ("R2_responses.jsonl", 3072, False),
    "R2_base_rag_unwrapped": ("R2_responses.jsonl", 3072, True),
    "R4_sft_rag": ("R4_responses.jsonl", 3072, False),
}
# run -> (prompt file, adapter expected)
RUNS = {"R2": ("prompts_R2.jsonl", False), "R4": ("prompts_R4.jsonl", True)}
PAIRS = [("R4_sft_rag", "R2_base_rag"), ("R4_sft_rag", "R2_base_rag_unwrapped"),
         ("R4_sft_rag", "R3_sft"), ("R2_base_rag_unwrapped", "R0_baseline")]
OLD_CAP = 1200
N_BOOT = 10_000


def jsonl(path: Path) -> list[dict]:
    return p10.jsonl(path)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_json(s: str) -> bool:
    try:
        json.loads(s)
        return True
    except (json.JSONDecodeError, TypeError):
        return False


# --------------------------------------------------------------------------
# A -- integrity
# --------------------------------------------------------------------------

def integrity(bench_ids: list[str]) -> dict:
    out = {}
    for run, (pfile, adapter) in RUNS.items():
        path = EVAL / f"{run}_responses.jsonl"
        raw = path.read_bytes()
        assert raw.endswith(b"\n"), f"{run}: final line is torn"
        rows = [json.loads(line) for line in raw.decode("utf-8").split("\n") if line.strip()]
        ids = [r["item_id"] for r in rows]
        assert len(rows) == 500 and len(set(ids)) == 500, (run, len(rows), len(set(ids)))
        assert set(ids) == set(bench_ids), f"{run}: item_ids != bench"
        errors = [r["item_id"] for r in rows if str(r["raw_response"]).startswith("__ERROR__")]
        assert not errors, f"{run}: __ERROR__ rows {errors[:10]}"
        want = {r["item_id"]: r["prompt_sha256"] for r in jsonl(PROMPTS_DIR / pfile)}
        bad = [r["item_id"] for r in rows if r["prompt_sha256"] != want[r["item_id"]]]
        assert not bad, f"{run}: prompt_sha256 mismatch {bad[:10]}"

        m = json.loads((EVAL / f"{run}_responses.jsonl.manifest.json").read_text(encoding="utf-8"))
        g = m["generate_kwargs"]
        assert m["max_new_tokens"] == g["max_new_tokens"] == 3072, run
        assert g["repetition_penalty"] == 1.05, run
        assert g["do_sample"] is False and g["num_beams"] == 1 and m["batch_size"] == 1, run
        assert (m["adapter_sha256"] is not None) is adapter, run
        assert (m["args"]["adapter"] is not None) is adapter, run
        assert m["prompts_sha256"] == sha256(PROMPTS_DIR / pfile), run
        sessions = [m] + m.get("resumes", [])
        out[run] = {"rows": {r["item_id"]: r for r in rows},
                    "hit_limit": sum(bool(r["hit_limit"]) for r in rows),
                    "max_output_tokens": max(r["output_tokens"] for r in rows),
                    "sessions": [{"started_utc": s["started_utc"], "gpu": s["gpu"],
                                  "versions": s["versions"]} for s in sessions],
                    "max_seq_length": m["max_seq_length"],
                    "adapter_sha256": m["adapter_sha256"]}
    return out


def version_diffs(ig: dict) -> dict:
    """Package -> (R2, R4) where the two runs differ, plus any drift inside
    a run across its resumed sessions."""
    def per_run(run):
        vs = [s["versions"] for s in ig[run]["sessions"]]
        return vs[0], [k for k in vs[0] if any(v[k] != vs[0][k] for v in vs[1:])]
    v2, drift2 = per_run("R2")
    v4, drift4 = per_run("R4")
    keys = sorted(set(v2) | set(v4))
    return {"between": {k: (v2.get(k), v4.get(k)) for k in keys if v2.get(k) != v4.get(k)},
            "same": {k: v2.get(k) for k in keys if v2.get(k) == v4.get(k)},
            "within": {"R2": drift2, "R4": drift4},
            "gpu": {run: sorted({s["gpu"] for s in ig[run]["sessions"]}) for run in ig}}


# --------------------------------------------------------------------------
# scores
# --------------------------------------------------------------------------

def load_and_check_scores(v, res, bench: dict) -> dict:
    """label -> {item_id: score row}, from scores_<label>.json, asserted equal
    to a fresh score.py run on the same responses."""
    out = {}
    for label, (resp, _cap, unwrap) in ARMS.items():
        saved = json.loads((EVAL / f"scores_{label}.json").read_text(encoding="utf-8"))
        s = saved["summary"]
        assert s["convention"] == "bench_minus_known_defects", label
        assert s["responses"] == f"data/final/eval/{resp}", (label, s["responses"])
        assert s.get("unwrap_advisory", False) is unwrap, label
        fresh = sc.score(v, res, bench, sc.load_responses(EVAL / resp), unwrap=unwrap)
        for a, b in zip(saved["items"], fresh["items"]):
            assert (a["item_id"], a["score"], a["excluded"], a["checks"]) == \
                   (b["item_id"], b["score"], b["excluded"], b["checks"]), (label, a["item_id"])
        out[label] = {"summary": s, "items": {r["item_id"]: r for r in saved["items"]}}
    return out


def hit_limits(ig: dict, items: list[str], tok) -> dict:
    out = {}
    for label, (resp, cap, _u) in ARMS.items():
        run = resp.split("_")[0]
        if run in ig:
            out[label] = sum(bool(ig[run]["rows"][i]["hit_limit"]) for i in items)
            continue
        raw = sc.load_responses(EVAL / resp)
        out[label] = sum(1 for i in items if not is_json(raw[i])
                         and len(tok.encode(raw[i], add_special_tokens=False)) >= cap - 1)
    return out


def scored(arm: dict) -> dict[str, float]:
    return {i: r["score"] for i, r in arm["items"].items() if not r["excluded"]}


# --------------------------------------------------------------------------
# E -- comparisons
# --------------------------------------------------------------------------

def sign_test_p(wins: int, losses: int) -> float:
    """Two-sided exact binomial sign test, ties already dropped."""
    n = wins + losses
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(wins, losses) + 1))
    return min(1.0, 2 * tail / 2 ** n)


def bootstrap_ci(d: np.ndarray) -> tuple[float, float]:
    rng = np.random.default_rng(0)
    idx = rng.integers(0, len(d), size=(N_BOOT, len(d)))
    lo, hi = np.percentile(d[idx].mean(axis=1), [2.5, 97.5])
    return float(lo), float(hi)


def paired(a: dict[str, float], b: dict[str, float], order: list[str]) -> dict:
    common = [i for i in order if i in a and i in b]
    d = np.array([a[i] - b[i] for i in common])
    wins, losses = int((d > 0).sum()), int((d < 0).sum())
    return {"n": len(common), "mean_a": float(np.mean([a[i] for i in common])),
            "mean_b": float(np.mean([b[i] for i in common])), "mean_diff": float(d.mean()),
            "wins": wins, "losses": losses, "ties": len(common) - wins - losses,
            "p_sign": sign_test_p(wins, losses), "ci95": bootstrap_ci(d)}


# --------------------------------------------------------------------------
# D -- noise floor
# --------------------------------------------------------------------------

def noise_floor(v, res, bench: dict, r4_rows: dict, S: dict) -> dict:
    pass1 = sc.load_responses(PASS1)
    hit = set(json.loads(RERUN_IDS.read_text(encoding="utf-8"))["item_ids"])
    # The rerun list IS pass 1's cut-offs: assert, so "hit its limit" means
    # exactly what Phase 12 regenerated.
    assert hit == {i for i, s in pass1.items() if not is_json(s)}, "rerun ids != pass-1 cut-offs"

    klass = {}
    for i in bench:
        old, new = pass1[i], r4_rows[i]["raw_response"]
        if new == old:
            klass[i] = "IDENTICAL"
        elif i in hit and new.startswith(old):
            klass[i] = "PREFIX"
        else:
            klass[i] = "DIFFERENT"
    counts = {"all": Counter(klass.values()),
              "pass1_not_hit": Counter(k for i, k in klass.items() if i not in hit),
              "pass1_hit": Counter(k for i, k in klass.items() if i in hit)}

    p1 = sc.score(v, res, bench, pass1)
    p1_scores = {r["item_id"]: r["score"] for r in p1["items"] if not r["excluded"]}
    r4 = scored(S["R4_sft_rag"])

    def diffs(ids):
        both = [i for i in ids if i in p1_scores and i in r4]
        d = np.array([r4[i] - p1_scores[i] for i in both])
        return {"n": len(both), "n_differ": int((d != 0).sum()) if len(d) else 0,
                "mean_abs": float(np.abs(d).mean()) if len(d) else float("nan"),
                "mean_signed": float(d.mean()) if len(d) else float("nan"),
                "mean_r4": float(np.mean([r4[i] for i in both])) if both else float("nan"),
                "mean_pass1": float(np.mean([p1_scores[i] for i in both])) if both else float("nan")}

    ids = list(p1_scores)
    sets = {"scored in both": ids,
            "pass 1 did not hit its limit": [i for i in ids if i not in hit],
            "  of which IDENTICAL": [i for i in ids if i not in hit and klass[i] == "IDENTICAL"],
            "  of which DIFFERENT": [i for i in ids if i not in hit and klass[i] == "DIFFERENT"],
            "pass 1 hit its limit": [i for i in ids if i in hit]}
    score_d = {k: diffs(v_) for k, v_ in sets.items()}
    assert score_d["  of which IDENTICAL"]["n_differ"] == 0, "identical text, different score"
    return {"counts": counts, "score_diffs": score_d, "n_hit": len(hit),
            "p1_summary": p1["summary"], "klass": klass}


def set_448(v, res, bench: dict, r4_items: dict) -> dict:
    """Phase 12's headline set, rebuilt by its own rule
    (phase12_step4c_merge_score.py): non-excluded in baseline, SFT and pass 1
    under the 500-item convention, minus the no_crop DOSE items and the two
    known defects. Reproduces the recorded means before scoring R4 on it."""
    _, trained, baseline, _, _ = p10.load_all()
    prompts = {r["item_id"]: r for r in jsonl(RAG_PROMPTS_B)}
    R = {"baseline": p10.rescore(v, res, bench, baseline),
         "sft": p10.rescore(v, res, bench, trained),
         "pass1": p10.rescore(v, res, bench, sc.load_responses(PASS1)),
         "merged": p10.rescore(v, res, bench, sc.load_responses(MERGED))}
    inter3 = [i for i in bench if not any(R[a][i].excluded for a in ("baseline", "sft", "pass1"))]
    nocrop = {i for i in bench if prompts[i]["retrieval_status"] == "no_crop"
              and bench[i]["kind"] in DOSE_KINDS}
    defects = {i for i in bench if prompts[i]["known_bench_defect"]}
    head = [i for i in inter3 if i not in nocrop and i not in defects]
    assert len(head) == 448, len(head)
    means = {a: p10.mean(R[a][i].total for i in head) for a in R}
    for a, want in (("sft", 0.5467), ("pass1", 0.5443), ("merged", 0.6143)):
        assert round(means[a], 4) == want, (a, means[a])
    r4_ex = [i for i in head if r4_items[i]["excluded"]]
    r4 = {i: r4_items[i]["score"] for i in head if not r4_items[i]["excluded"]}
    merged = {i: R["merged"][i].total for i in head}
    return {"n": len(head), "means": means, "r4_mean": p10.mean(r4.values()),
            "r4_n": len(r4), "r4_excluded": r4_ex,
            "r4_vs_merged": paired(r4, merged, head)}


# --------------------------------------------------------------------------
# markdown
# --------------------------------------------------------------------------

def f4(x) -> str:
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.4f}"


def fp(p: float) -> str:
    return f"{p:.2e}" if p < 1e-3 else f"{p:.3f}"


def md(ig, vd, S, hl, inter, pairs, nf, s448) -> str:
    C = list(next(iter(S.values()))["summary"]["checks"])
    L = []
    w = L.append
    w("## A. Integrity\n")
    w("| run | rows | hit_limit | max output tokens | max_seq_length | sessions |")
    w("|---|---:|---:|---:|---:|---:|")
    for run in RUNS:
        x = ig[run]
        w(f"| {run} | 500 | {x['hit_limit']} | {x['max_output_tokens']:,} | "
          f"{x['max_seq_length']:,} | {len(x['sessions'])} |")
    w("\nLibrary versions, R2 vs R4 (first session of each run):\n")
    w("| package | R2 | R4 |")
    w("|---|---|---|")
    for k, (a, b) in vd["between"].items():
        w(f"| {k} | {a} | {b} |")
    w(f"\nIdentical in both: {', '.join(f'{k} {v_}' for k, v_ in vd['same'].items())}. "
      f"GPU: R2 {vd['gpu']['R2']}, R4 {vd['gpu']['R4']}. Drift across resumed "
      f"sessions within a run: R2 {vd['within']['R2'] or 'none'}, R4 {vd['within']['R4'] or 'none'}.\n")

    w("## E1. Canonical table (498-item denominator)\n")
    w("| arm | cap | mean | scored / excl / missing | G1 % | G2 % | "
      + " | ".join(C) + " | hit_limit |")
    w("|---|---:|---:|---|---:|---:|" + "---:|" * len(C) + "---:|")
    for label, a in S.items():
        s = a["summary"]
        w(f"| {label} | {ARMS[label][1]:,} | **{f4(s['mean'])}** | "
          f"{s['n_scored']} / {s['n_excluded']} / {s['n_missing']} | "
          f"{s['g1_json_pct']:.1f} | {s['g2_schema_pct']:.1f} | "
          + " | ".join(f4(s["checks"][c]["mean"]) for c in C) + f" | {hl[label]} |")
    w("\nCheck n (items carrying the check):\n")
    w("| arm | " + " | ".join(C) + " |")
    w("|---|" + "---:|" * len(C))
    for label, a in S.items():
        w(f"| {label} | " + " | ".join(str(a["summary"]["checks"][c]["n"]) for c in C) + " |")

    w(f"\n## E2. Sensitivity: items scored by all five arms (n = {inter['n']})\n")
    w("| arm | mean |")
    w("|---|---:|")
    for label, m in inter["means"].items():
        w(f"| {label} | {f4(m)} |")

    w("\n## E3. Paired comparisons (items scored in both arms)\n")
    w("| A vs B | n | mean A | mean B | Δ (A−B) | 95% CI | wins / losses / ties | sign test p |")
    w("|---|---:|---:|---:|---:|---|---|---:|")
    for (a, b), r in pairs.items():
        w(f"| {a} vs {b} | {r['n']} | {f4(r['mean_a'])} | {f4(r['mean_b'])} | "
          f"**{r['mean_diff']:+.4f}** | [{r['ci95'][0]:+.4f}, {r['ci95'][1]:+.4f}] | "
          f"{r['wins']} / {r['losses']} / {r['ties']} | {fp(r['p_sign'])} |")

    w("\n## D. Noise floor: R4 vs Phase 12 pass 1 (same prompts)\n")
    w("| set | n | IDENTICAL | PREFIX | DIFFERENT |")
    w("|---|---:|---:|---:|---:|")
    for name, key in (("all items", "all"), ("pass 1 did not hit 1,200", "pass1_not_hit"),
                      ("pass 1 hit 1,200", "pass1_hit")):
        c = nf["counts"][key]
        w(f"| {name} | {sum(c.values())} | {c['IDENTICAL']} | {c['PREFIX']} | {c['DIFFERENT']} |")
    w("\nScore differences, R4 − pass 1, on items scored in both (498 denominator):\n")
    w("| subset | n | scores differ | mean |Δ| | mean Δ | mean R4 | mean pass 1 |")
    w("|---|---:|---:|---:|---:|---:|---:|")
    for name, d in nf["score_diffs"].items():
        w(f"| {name} | {d['n']} | {d['n_differ']} | {f4(d['mean_abs'])} | "
          f"{d['mean_signed']:+.4f} | {f4(d['mean_r4'])} | {f4(d['mean_pass1'])} |")

    w(f"\n## D2. R4 on Phase 12's 448-item set\n")
    m = s448["means"]
    w("| arm (on the 448) | mean |")
    w("|---|---:|")
    w(f"| baseline (R0) | {f4(m['baseline'])} |")
    w(f"| SFT (R3) | {f4(m['sft'])} |")
    w(f"| Phase 12 pass 1 (1,200 cap) | {f4(m['pass1'])} |")
    w(f"| Phase 12 merged (the 0.6143) | {f4(m['merged'])} |")
    w(f"| **R4_sft_rag** (n = {s448['r4_n']}) | **{f4(s448['r4_mean'])}** |")
    r = s448["r4_vs_merged"]
    w(f"\nR4 − merged, paired on {r['n']}: {r['mean_diff']:+.4f} "
      f"[{r['ci95'][0]:+.4f}, {r['ci95'][1]:+.4f}], {r['wins']} / {r['losses']} / {r['ties']}, "
      f"sign test p {fp(r['p_sign'])}. R4 exclusions inside the 448: {s448['r4_excluded'] or 'none'}.")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", type=Path, required=True)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    v = p10.load_verify()
    res = v.VerifyResources.load()
    bench = {r["item_id"]: r for r in jsonl(p10.BENCH)}
    order498 = list(sc.scored_items(bench))

    ig = integrity(list(bench))
    vd = version_diffs(ig)
    S = load_and_check_scores(v, res, bench)
    hl = hit_limits(ig, order498, load_tokenizer())

    sets = {label: scored(a) for label, a in S.items()}
    common = [i for i in order498 if all(i in s for s in sets.values())]
    inter = {"n": len(common),
             "means": {label: float(np.mean([s[i] for i in common])) for label, s in sets.items()}}
    pairs = {(a, b): paired(sets[a], sets[b], order498) for a, b in PAIRS}
    nf = noise_floor(v, res, bench, ig["R4"]["rows"], S)
    s448 = set_448(v, res, bench, S["R4_sft_rag"]["items"])

    args.md.write_text(md(ig, vd, S, hl, inter, pairs, nf, s448), encoding="utf-8")
    print(f"wrote {args.md}")
    if args.json:
        dump = {"version_diffs": vd, "hit_limit": hl, "intersection": inter,
                "pairs": {f"{a} vs {b}": r for (a, b), r in pairs.items()},
                "noise_floor": {k: val for k, val in nf.items() if k != "p1_summary"},
                "set_448": s448}
        args.json.write_text(json.dumps(dump, indent=1, default=str), encoding="utf-8")
        print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
