"""Pins for the frozen benchmark, data/final/bench.jsonl (phase 9).

The benchmark is 500 items: 379 sampled from sft_test.jsonl (date-split,
never trained on) and 121 constructed from label_db. Built by
tools/build_benchmark.py + tools/build_benchmark_constructed.py; design in
reports/phase9_stepA_benchmark_design.md.

The disjointness test is the freeze guarantee: every sourced bench item id
is a (slice, row_id) pair in the S{slice}_{row_id} scheme -- the same scheme
sft_train.jsonl uses -- so id-set disjointness IS pair disjointness.
Constructed ids use B prefixes, which no train id can carry.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "data" / "final" / "bench.jsonl"
TRAIN = ROOT / "data" / "final" / "sft_train.jsonl"

SCOPE_CROPS = {"cotton", "soybean", "tur", "gram", "onion", "tomato",
               "grape", "pomegranate"}


@pytest.fixture(scope="module")
def bench():
    with open(BENCH, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def test_bench_has_exactly_500_items(bench):
    assert len(bench) == 500


def test_bench_disjoint_from_train(bench):
    """Every bench (slice, row_id) pair is absent from sft_train.jsonl."""
    with open(TRAIN, encoding="utf-8") as f:
        train_ids = {json.loads(line)["id"] for line in f}
    assert len(train_ids) == 4493
    for item in bench:
        if item["constructed"]:
            assert item["item_id"].startswith("B"), item["item_id"]
        else:
            assert item["item_id"] not in train_ids, item["item_id"]


def test_all_eight_scope_crops_present(bench):
    crops = {i["crop_slug"] for i in bench}
    assert SCOPE_CROPS <= crops


def test_item_ids_unique(bench):
    ids = [i["item_id"] for i in bench]
    assert len(ids) == len(set(ids))


def test_constructed_flag_consistent_with_source(bench):
    for item in bench:
        assert not (item["constructed"] and item["source"] == "sft_test"), \
            item["item_id"]
        # and the mirror image: a sourced row must say so
        if not item["constructed"]:
            assert item["source"] == "sft_test", item["item_id"]


def test_difficulty_values(bench):
    allowed = {"standard", "hard", "edge_case"}
    for item in bench:
        assert item["difficulty"] in allowed, item["item_id"]


def test_composition_pins(bench):
    """The frozen composition. A change here is a re-freeze, not a drift."""
    from collections import Counter
    assert Counter(i["difficulty"] for i in bench) == {
        "standard": 320, "hard": 107, "edge_case": 73}
    assert sum(1 for i in bench if i["constructed"]) == 121
    crops = Counter(i["crop_slug"] for i in bench)
    for crop in SCOPE_CROPS:
        assert crops[crop] >= 20, f"{crop} below the 20-item floor"
