"""tests for src/retrieval.py -- Phase 12 Step 1 (RAG ablation).

The byte-identity tests compare against tools/generate_sft.py ITSELF --
label_db_fact_rows() and the <fact_sheet> block cut out of
build_user_message() -- never against a copied string, so a drift on either
side fails here.

Resources are loaded against the REAL ban list (data/final/restricted_ai.csv),
pinned explicitly: test_verify.py swaps in a fixture list by re-importing
`verify`, and the ban-list exclusion test below must not depend on test order.
"""
from __future__ import annotations

import importlib
import json
import os
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
LABEL_DB = REPO / "data" / "final" / "label_db.parquet"
REAL_BAN_LIST = REPO / "data" / "final" / "restricted_ai.csv"
BENCH = REPO / "data" / "final" / "bench.jsonl"

# (crop, canonical, application_method) -- one or more per crop, all 8 crops.
# The tomato soil_drench pair exercises method narrowing.
BYTE_IDENTITY_PAIRS = [
    ("cotton", "Whitefly", None),
    ("cotton", "Wilt", None),
    ("soybean", "Jassid", None),
    ("tomato", "Whitefly", None),
    ("tomato", "Whitefly", "soil_drench"),
    ("gram", "Helicoverpa armigera", None),
    ("onion", "Thrips", None),
    ("tur", "Helicoverpa armigera", None),
    ("pomegranate", "Thrips", None),
    ("grape", "Downy mildew", None),
]

# Bench items whose query names an in-scope crop and a pest the synonym table
# resolves to the gold canonical (measured 220/268 DOSE+REFUSAL_DOSE items).
LIVE_HITS = ["S1_140", "S1_604", "S1_512", "S1_1261", "S1_1827",
             "S1_5589", "S1_653", "S1_726"]
# Bench items where live resolution finds the crop but no pest: Hinglish
# 'keeda'/'deemak' phrasing the synonym table does not carry.
LIVE_PEST_MISSES = ["B3_4", "B3_6", "B3_13", "B3_24"]


@pytest.fixture(scope="module")
def resources():
    if not LABEL_DB.exists():
        pytest.skip("label_db.parquet not built (gitignored)")
    if not REAL_BAN_LIST.exists():
        pytest.skip("restricted_ai.csv not built")
    prev = os.environ.get("AGRI_RESTRICTED_AI")
    os.environ["AGRI_RESTRICTED_AI"] = str(REAL_BAN_LIST)
    for name in ("verify", "restricted_ai"):
        sys.modules.pop(name, None)
    verify = importlib.import_module("verify")
    res = verify.VerifyResources.load()
    if prev is None:
        os.environ.pop("AGRI_RESTRICTED_AI", None)
    else:
        os.environ["AGRI_RESTRICTED_AI"] = prev
    return res


@pytest.fixture(scope="module")
def gen():
    tools = str(REPO / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    return importlib.import_module("generate_sft")


@pytest.fixture(scope="module")
def retrieval():
    return importlib.import_module("retrieval")


@pytest.fixture(scope="module")
def bench():
    if not BENCH.exists():
        pytest.skip("bench.jsonl not built")
    with open(BENCH, encoding="utf-8") as fh:
        return {r["item_id"]: r for r in map(json.loads, fh)}


def _gen_message(gen, crop, canon, method, rows, query="Q"):
    item = gen.GenItem(slice=1, kind=gen.Kind.DOSE, row_id="t", split="test",
                       crop_slug=crop, query_text=query, canonicals=[canon],
                       application_method=method, fact_rows=rows)
    return gen.build_user_message(item)


def _fact_sheet_block(message: str) -> str:
    m = re.search(r"<fact_sheet>\n.*?\n</fact_sheet>", message, re.S)
    assert m, "generator message carries no <fact_sheet> block"
    return m.group(0)


# --------------------------------------------------------------------------
# byte identity against the generator
# --------------------------------------------------------------------------

@pytest.mark.parametrize("crop,canon,method", BYTE_IDENTITY_PAIRS)
def test_retrieve_rows_equals_generator(resources, gen, retrieval, crop, canon, method):
    ours = retrieval.retrieve_rows(crop, canon, resources, method)
    theirs = gen.label_db_fact_rows(resources, crop, canon, method)
    assert ours, f"no rows for {crop}/{canon} -- pick a pair with chemistry"
    assert ours == theirs


@pytest.mark.parametrize("crop,canon,method", BYTE_IDENTITY_PAIRS)
def test_fact_sheet_byte_identical(resources, gen, retrieval, crop, canon, method):
    rows = gen.label_db_fact_rows(resources, crop, canon, method)
    expected = _fact_sheet_block(_gen_message(gen, crop, canon, method, rows))
    got = retrieval.format_fact_sheet(rows)
    assert got.encode("utf-8") == expected.encode("utf-8")


def test_method_narrowing_changes_the_sheet(resources, retrieval):
    """Guards the narrowing pair above from silently being a no-op."""
    full = retrieval.retrieve_rows("tomato", "Whitefly", resources)
    drench = retrieval.retrieve_rows("tomato", "Whitefly", resources, "soil_drench")
    assert drench and len(drench) < len(full)
    assert all(r["application_method"] == "soil_drench" for r in drench)


def test_method_matching_nothing_falls_back(resources, retrieval):
    full = retrieval.retrieve_rows("cotton", "Whitefly", resources)
    assert retrieval.retrieve_rows("cotton", "Whitefly", resources, "nursery") == full


def test_rag_message_is_phase8_shape_minus_task(resources, gen, retrieval):
    """With resolved_pest passed, the RAG message is exactly the generator's
    message with the <task> block removed."""
    q = "WHITEFLY ATTACK IN COTTON CROP"
    rows = gen.label_db_fact_rows(resources, "cotton", "Whitefly", None)
    theirs = _gen_message(gen, "cotton", "Whitefly", None, rows, query=q)
    theirs = theirs.split("\n\n<task>\n")[0]
    ours = retrieval.build_rag_user_message(q, "cotton", rows, resolved_pest=["Whitefly"])
    assert ours == theirs


# --------------------------------------------------------------------------
# filter chain
# --------------------------------------------------------------------------

def _flagged_row(resources, crop, canon, ai):
    rows = [r for r in resources.label_db.for_pair(crop, canon) if r.active_ingredient == ai]
    assert rows, f"precondition: {ai} is registered for {crop}/{canon} in label_db"
    return rows


def test_contradicted_row_excluded(resources, retrieval):
    ai = "Pyriproxyfen 10%EC"
    rows = _flagged_row(resources, "cotton", "Whitefly", ai)
    assert all(r.contradiction for r in rows), "precondition: row is in known_contradictions"
    assert all(r.trainable and not r.defective for r in rows), \
        "precondition: contradiction is the ONLY reason to drop it"
    out = retrieval.retrieve_rows("cotton", "Whitefly", resources)
    assert out and ai not in {r["ai"] for r in out}


def test_ban_listed_row_excluded(resources, retrieval):
    ai = "Monocrotophos 15%SG"
    rows = _flagged_row(resources, "cotton", "Aphid", ai)
    assert all(r.trainable and not r.defective and not r.contradiction for r in rows), \
        "precondition: the ban list is the ONLY reason to drop it"
    assert all(resources.restricted.check(r.ai_components, "cotton") for r in rows)
    out = retrieval.retrieve_rows("cotton", "Aphid", resources)
    assert out and ai not in {r["ai"] for r in out}


def test_filter_chain_leaves_610_rows(resources):
    """The generation-usable count the chain is documented to produce."""
    kept = [r for r in resources.label_db.rows
            if r.trainable and not r.defective and not r.contradiction
            and not resources.restricted.check(r.ai_components, r.crop_slug)]
    assert len(kept) == 610


def test_private_ai_key_never_reaches_the_sheet(resources, retrieval):
    rows = retrieval.retrieve_rows("cotton", "Whitefly", resources)
    assert all("_ai" in r for r in rows)
    assert '"_ai"' not in retrieval.format_fact_sheet(rows)


# --------------------------------------------------------------------------
# retrieval miss
# --------------------------------------------------------------------------

EXPECTED_NO_ROWS = ("<fact_sheet>\nNo registered chemistry found for this crop and "
                    "pest in CIB&RC.\n</fact_sheet>")
EXPECTED_UNRESOLVED = ("<fact_sheet>\nRetrieval could not identify a specific crop and "
                       "pest from this query. No fact sheet available.\n</fact_sheet>")


def test_empty_rows_no_rows_wording(retrieval):
    assert retrieval.format_fact_sheet([], retrieval.MISS_NO_ROWS) == EXPECTED_NO_ROWS


def test_empty_rows_unresolved_wording(retrieval):
    assert retrieval.format_fact_sheet([], retrieval.MISS_UNRESOLVED) == EXPECTED_UNRESOLVED


@pytest.mark.parametrize("reason", [None, "", "bogus"])
def test_empty_rows_without_reason_raises(retrieval, reason):
    """No silent fallback to the CIB&RC claim."""
    with pytest.raises(ValueError):
        retrieval.format_fact_sheet([], reason)


def test_miss_reason_ignored_when_rows_present(resources, retrieval):
    rows = retrieval.retrieve_rows("cotton", "Whitefly", resources)
    assert (retrieval.format_fact_sheet(rows, retrieval.MISS_UNRESOLVED)
            == retrieval.format_fact_sheet(rows))


@pytest.mark.parametrize("crop,canon,expected", [
    ("cotton", "Powdery mildew", "no_rows"),
    ("cotton", None, "unresolved"),
    (None, "Whitefly", "unresolved"),
    (None, None, "unresolved"),
])
def test_miss_reason_for(retrieval, crop, canon, expected):
    assert retrieval.miss_reason_for(crop, canon) == expected


def test_resolved_key_with_no_rows_gets_cibrc_line(resources, retrieval):
    """A real resolved pair with no surviving chemistry (bench S5_1738)."""
    rows = retrieval.retrieve_rows("cotton", "Powdery mildew", resources)
    assert rows == []
    msg = retrieval.build_rag_user_message(
        "q", "cotton", rows, miss_reason=retrieval.miss_reason_for("cotton", "Powdery mildew"))
    assert msg.endswith(EXPECTED_NO_ROWS)


@pytest.mark.parametrize("crop,canon", [
    ("cotton", None), (None, "Whitefly"), (None, None),
    ("cotton", "Not a real pest"),
])
def test_unresolvable_key_returns_empty(resources, retrieval, crop, canon):
    assert retrieval.retrieve_rows(crop, canon, resources) == []


# --------------------------------------------------------------------------
# resolved_pest
# --------------------------------------------------------------------------

def test_resolved_pest_omitted_by_default(resources, retrieval):
    rows = retrieval.retrieve_rows("cotton", "Whitefly", resources)
    msg = retrieval.build_rag_user_message("q", "cotton", rows)
    assert "<resolved_pest>" not in msg and "Whitefly" not in msg


def test_resolved_pest_included_when_passed(resources, retrieval):
    rows = retrieval.retrieve_rows("cotton", "Whitefly", resources)
    msg = retrieval.build_rag_user_message("q", "cotton", rows, resolved_pest="Whitefly")
    assert '<resolved_pest>\n["Whitefly"]\n</resolved_pest>' in msg


def test_no_task_or_restricted_blocks(resources, retrieval):
    rows = retrieval.retrieve_rows("cotton", "Whitefly", resources)
    msg = retrieval.build_rag_user_message("q", "cotton", rows, resolved_pest="Whitefly")
    assert "<task>" not in msg and "<restricted_ai>" not in msg


def test_unknown_crop_renders_bare_query_tag(retrieval):
    msg = retrieval.build_rag_user_message("q", None, [], miss_reason=retrieval.MISS_UNRESOLVED)
    assert msg == "<query>\nq\n</query>\n\n" + EXPECTED_UNRESOLVED


# --------------------------------------------------------------------------
# resolve_key (Arm B live resolution)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("item_id", LIVE_HITS)
def test_live_resolution_hits_gold(resources, retrieval, bench, item_id):
    b = bench[item_id]
    crop, canon, _method = retrieval.resolve_key(b["query_text"], resources)
    assert (crop, canon) == (b["crop_slug"], b["canonical_pest"])
    assert retrieval.retrieve_rows(crop, canon, resources)


def test_live_hits_span_crops(bench):
    assert len({bench[i]["crop_slug"] for i in LIVE_HITS}) >= 6


@pytest.mark.parametrize("item_id", LIVE_PEST_MISSES)
def test_live_pest_miss_yields_unresolved_line(resources, retrieval, bench, item_id):
    b = bench[item_id]
    crop, canon, method = retrieval.resolve_key(b["query_text"], resources)
    assert crop == b["crop_slug"] and canon is None
    rows = retrieval.retrieve_rows(crop, canon, resources, method)
    assert rows == []
    msg = retrieval.build_rag_user_message(
        b["query_text"], crop, rows, miss_reason=retrieval.miss_reason_for(crop, canon))
    assert msg.endswith(EXPECTED_UNRESOLVED)


def test_crop_hint_overrides_text(resources, retrieval):
    """Arm A passes the gold crop; it wins even when the text names none."""
    assert retrieval.resolve_key("whitefly attack", resources)[0] is None
    crop, canon, _ = retrieval.resolve_key("whitefly attack", resources, crop_hint="cotton")
    assert (crop, canon) == ("cotton", "Whitefly")


def test_no_crop_skips_pest_lookup(resources, retrieval):
    assert retrieval.resolve_key("whitefly attack", resources) == (None, None, None)


def test_method_extracted_from_query(resources, retrieval):
    _, _, method = retrieval.resolve_key("tomato whitefly soil drench dose", resources)
    assert method == "soil_drench"


def test_resolve_key_never_raises_on_junk(resources, retrieval):
    for q in ["", "   ", "???", "fertilizer dose of cotton crop"]:
        crop, canon, _ = retrieval.resolve_key(q, resources)
        assert canon is None
