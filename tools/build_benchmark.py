"""Phase 9 Step B -- sample the sourced benchmark buckets from sft_test.jsonl.

Design: reports/phase9_stepA_benchmark_design.md (approved 2026-09-03).

Samples the four sourced buckets (S1 DOSE 180, S2 CLARIFY 150, S5 NOCHEM 25,
OFFTOPIC 25) into data/interim/bench_sourced.jsonl. Constructed items
(S1 grape/pomegranate, S3, S5 viral, HARD) are Phase 9 Step C and are NOT
built here.

Every quota is a *ceiling*: where a crop's pool is smaller than its quota the
whole pool is taken and the shortfall reported, never padded from another
crop. Sampling is deterministic (seed 42, candidates sorted by row_id before
any draw).

Kind reconstruction mirrors the Phase 9 Step 1 survey: slice from the id
prefix, crop/pest from the sft_generation_log.csv join, kind from slice +
gold output shape (in_scope=false -> OFFTOPIC; slice 2 in-scope -> CLARIFY;
slice 5 -> NOCHEM; slice 1 in-scope -> DOSE). Slice 3's six rows are not
sampled -- benchmark S3 is constructed in Step C.
"""

from __future__ import annotations

import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import scope  # noqa: E402  (CONFUSABLE_PAIRS)

TEST_PATH = ROOT / "data" / "final" / "sft_test.jsonl"
TRAIN_PATH = ROOT / "data" / "final" / "sft_train.jsonl"
LOG_PATH = ROOT / "data" / "final" / "sft_generation_log.csv"
OUT_PATH = ROOT / "data" / "interim" / "bench_sourced.jsonl"

SEED = 42

S1_QUOTA = {"cotton": 65, "soybean": 27, "tomato": 27, "gram": 20,
            "onion": 18, "tur": 18, "pomegranate": 4, "grape": 1}
S1_HARD_PER_CROP = 5
S1_EDGE_PER_CROP = 2

S2_QUOTA = {"cotton": 47, "soybean": 21, "tur": 19, "onion": 16,
            "tomato": 15, "gram": 15, "pomegranate": 14, "grape": 3}
S2_HARD_TOTAL = 20

S5_QUOTA = {"cotton": 5, "soybean": 6, "onion": 7, "tur": 2,
            "gram": 2, "pomegranate": 3}

OFFTOPIC_TOTAL = 25
OFFTOPIC_MANDATORY = ("S1_9", "S1_1613")  # groundnut, wheat -- out-of-scope crops


def load_pool():
    """Join sft_test.jsonl with the generation log; derive kind per row."""
    log = {}
    with open(LOG_PATH, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            log[(r["slice"], r["row_id"])] = r

    pool = []
    with open(TEST_PATH, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            prefix, row_id = rec["id"].rsplit("_", 1)
            slice_n = int(prefix[1:])
            meta = log[(prefix[1:], row_id)]
            adv = json.loads(rec["messages"][-1]["content"])
            user_turns = [m for m in rec["messages"] if m["role"] == "user"]
            if not adv["in_scope"]:
                kind = "OFFTOPIC"
            elif slice_n == 1:
                kind = "DOSE"
            elif slice_n == 2:
                kind = "CLARIFY"
            elif slice_n == 5:
                kind = "NOCHEM"
            else:  # slice 3 -- not sampled (benchmark S3 is constructed)
                kind = "REFUSAL"
            pool.append({
                "item_id": rec["id"],
                "slice": slice_n,
                "row_id": row_id,
                "kind": kind,
                "crop_slug": meta["crop_slug"],
                "canonical_pest": meta["canonical_pest"] or None,
                "query_text": user_turns[-1]["content"],
                "gold_advisory": adv,
            })
    # Deterministic base order regardless of file order.
    pool.sort(key=lambda r: (r["slice"], int(r["row_id"])))
    return pool


def s1_difficulty(adv):
    """edge > hard > standard, per the approved tier definitions."""
    phi_unknown = any(
        co.get("phi_days") is None and not co.get("phi_not_applicable")
        for co in adv["chemical_options"])
    if adv["escalate_to_expert"] and phi_unknown:
        return "edge_case"
    range_dose = any(
        isinstance(co.get("dose"), dict)
        and co["dose"].get("value_max") is not None
        and co["dose"]["value_max"] != co["dose"].get("value_min")
        for co in adv["chemical_options"])
    if range_dose or len(adv["likely_causes"]) > 1:
        return "hard"
    return "standard"


def confusable_keywords():
    """crop -> lowercase keywords from scope.CONFUSABLE_PAIRS."""
    kw = {}
    for crop_a, pest_a, crop_b, pest_b in scope.CONFUSABLE_PAIRS:
        for crop, pest in ((crop_a, pest_a), (crop_b, pest_b)):
            words = kw.setdefault(crop, set())
            words.add(pest.lower())
            words.add(pest.lower().split()[-1])  # blight, mildew, thrips, ...
    return kw


def sample_s1(pool, rng, report):
    out = []
    for crop, quota in S1_QUOTA.items():
        cands = [r for r in pool
                 if r["slice"] == 1 and r["kind"] == "DOSE"
                 and r["crop_slug"] == crop]
        if len(cands) < quota:
            report["shortfalls"].append(
                f"S1 {crop}: pool {len(cands)} < quota {quota}")
        take = min(quota, len(cands))
        by_tier = {"edge_case": [], "hard": [], "standard": []}
        for r in cands:
            by_tier[s1_difficulty(r["gold_advisory"])].append(r)

        picked = []
        picked += rng.sample(by_tier["edge_case"],
                             min(S1_EDGE_PER_CROP, len(by_tier["edge_case"]),
                                 take))
        picked += rng.sample(by_tier["hard"],
                             min(S1_HARD_PER_CROP, len(by_tier["hard"]),
                                 take - len(picked)))
        # Fill with standard first, then whatever remains, tier label kept.
        rest = take - len(picked)
        remaining_std = [r for r in by_tier["standard"] if r not in picked]
        fill = rng.sample(remaining_std, min(rest, len(remaining_std)))
        picked += fill
        rest = take - len(picked)
        if rest:
            leftovers = [r for r in cands if r not in picked]
            picked += rng.sample(leftovers, rest)
        for r in picked:
            out.append(make_record(r, s1_difficulty(r["gold_advisory"])))
    return out


def sample_s2(pool, rng, report):
    kw = confusable_keywords()
    crop_cands = {}
    for crop in S2_QUOTA:
        crop_cands[crop] = [r for r in pool
                            if r["slice"] == 2 and r["kind"] == "CLARIFY"
                            and r["crop_slug"] == crop]
        if len(crop_cands[crop]) < S2_QUOTA[crop]:
            report["shortfalls"].append(
                f"S2 {crop}: pool {len(crop_cands[crop])} "
                f"< quota {S2_QUOTA[crop]}")

    # Hard tier: round-robin one confusable-keyword row per crop until the
    # global cap, so no single crop swallows the tier.
    hard_pools = {
        crop: rng.sample(
            [r for r in cands
             if any(k in r["query_text"].lower() for k in kw.get(crop, ()))],
            k=len([r for r in cands
                   if any(k in r["query_text"].lower()
                          for k in kw.get(crop, ()))]))
        for crop, cands in crop_cands.items()}
    picked = {crop: [] for crop in S2_QUOTA}
    hard_n = 0
    while hard_n < S2_HARD_TOTAL:
        progressed = False
        for crop in S2_QUOTA:
            if hard_n >= S2_HARD_TOTAL:
                break
            if hard_pools[crop] and len(picked[crop]) < S2_QUOTA[crop]:
                picked[crop].append(hard_pools[crop].pop())
                hard_n += 1
                progressed = True
        if not progressed:
            break
    report["s2_hard_achieved"] = hard_n

    out = []
    for crop, quota in S2_QUOTA.items():
        hard_ids = {r["item_id"] for r in picked[crop]}
        rest = [r for r in crop_cands[crop] if r["item_id"] not in hard_ids]
        need = min(quota, len(crop_cands[crop])) - len(picked[crop])
        fill = rng.sample(rest, min(need, len(rest)))
        out += [make_record(r, "hard") for r in picked[crop]]
        out += [make_record(r, "standard") for r in fill]
    return out


def sample_s5(pool, rng, report):
    out = []
    for crop, quota in S5_QUOTA.items():
        cands = [r for r in pool
                 if r["slice"] == 5 and r["kind"] == "NOCHEM"
                 and r["crop_slug"] == crop]
        if len(cands) < quota:
            report["shortfalls"].append(
                f"S5 {crop}: pool {len(cands)} < quota {quota}")
        out += [make_record(r, "standard")
                for r in rng.sample(cands, min(quota, len(cands)))]
    return out


def sample_offtopic(pool, rng, report):
    cands = [r for r in pool if r["kind"] == "OFFTOPIC"]
    by_id = {r["item_id"]: r for r in cands}
    missing = [i for i in OFFTOPIC_MANDATORY if i not in by_id]
    if missing:
        raise SystemExit(f"mandatory OFFTOPIC rows missing from pool: {missing}")
    picked = [by_id[i] for i in OFFTOPIC_MANDATORY]
    rest = [r for r in cands if r["item_id"] not in OFFTOPIC_MANDATORY]
    picked += rng.sample(rest, OFFTOPIC_TOTAL - len(picked))
    report["offtopic_pool"] = len(cands)
    return [make_record(r, "standard") for r in picked]


def make_record(r, difficulty):
    return {
        "item_id": r["item_id"],
        "slice": r["slice"],
        "kind": r["kind"],
        "crop_slug": r["crop_slug"],
        "canonical_pest": r["canonical_pest"],
        "query_text": r["query_text"],
        "gold_advisory": r["gold_advisory"],
        "difficulty": difficulty,
        "source": "sft_test",
        "constructed": False,
    }


def main():
    rng = random.Random(SEED)
    pool = load_pool()
    report = {"shortfalls": []}

    items = (sample_s1(pool, rng, report)
             + sample_s2(pool, rng, report)
             + sample_s5(pool, rng, report)
             + sample_offtopic(pool, rng, report))

    ids = [i["item_id"] for i in items]
    assert len(ids) == len(set(ids)), "duplicate item_id sampled"

    # Disjointness against train -- id equality IS (slice, row_id) equality.
    with open(TRAIN_PATH, encoding="utf-8") as f:
        train_ids = {json.loads(line)["id"] for line in f}
    overlap = set(ids) & train_ids
    assert not overlap, f"bench rows appear in sft_train.jsonl: {sorted(overlap)[:5]}"

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    # ---- report ----
    print(f"wrote {len(items)} items -> {OUT_PATH.relative_to(ROOT)}")
    print(f"train overlap: {len(overlap)} (must be 0)")
    bucket = Counter(i["kind"] for i in items)
    print(f"\nby bucket: {dict(bucket)}")
    for kind in ("DOSE", "CLARIFY", "NOCHEM", "OFFTOPIC"):
        crops = Counter(i["crop_slug"] for i in items if i["kind"] == kind)
        print(f"  {kind}: {dict(sorted(crops.items()))}")
    tiers = Counter((i["kind"], i["difficulty"]) for i in items)
    print("\ntiers:")
    for (kind, tier), n in sorted(tiers.items()):
        print(f"  {kind:9s} {tier:9s} {n}")
    print(f"\nS2 hard achieved: {report.get('s2_hard_achieved')} / {S2_HARD_TOTAL}")
    print(f"OFFTOPIC pool size: {report.get('offtopic_pool')}")
    if report["shortfalls"]:
        print("\nshortfalls (pool exhaustion):")
        for s in report["shortfalls"]:
            print(f"  {s}")
    else:
        print("\nno shortfalls")


if __name__ == "__main__":
    main()
