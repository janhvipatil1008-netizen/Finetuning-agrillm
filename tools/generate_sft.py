"""
generate_sft.py -- Phase 8 Step B1: the SFT generation pipeline.

Design: reports/phase8_stepA_sft_generation_design.md (read in full before
touching this file). Decisions confirmed by the user on 2026-09-02:
Slice 5 included, Slice 2 gold_escalate=False, Slice 3 gold_escalate=True,
grape target 300 (40 held out), multilingual deferred to a later sub-phase,
cutoff 2022-01-01, per_acre-preferred dose basis, Batch API.

Five slices, one shared architecture (design doc section 1): a generator
system prompt wraps the FROZEN deployment system_prompt.txt verbatim, a
per-item fact sheet supplies every chemical fact as a verbatim label_db
copy, and verify.py in gate mode is the sole acceptance authority. The
fact sheet exists only at generation time -- the emitted sft.jsonl record
pairs system_prompt.txt + the bare farmer query against the accepted JSON,
so the trained model must answer without the crutch that made the answer
correct.

TWO PLACES THIS SCRIPT KNOWINGLY DIVERGES FROM THE LITERAL SUB-PHASE BRIEF
============================================================================

1. Slice 5 count. The brief's step 1 defines slice 3 as "banned_chemical_
   query=True" and slice 5 as plain "NO_REGISTERED_CHEMISTRY rows (152)",
   with no "AND not slice 3" clause on slice 5 (unlike slices 1 and 2, which
   both carry that clause explicitly). Taken literally, slice 3 and slice 5
   would overlap on the 2 rows that are both banned and NO_REGISTERED_
   CHEMISTRY, generating two training examples for the same 2 KCC rows and
   breaking the clean partition every other slice keeps. This script keeps
   slices mutually exclusive (E-first over all four conditions, matching
   the design doc's own dataset-shape table, which already used ~150 rather
   than 152) -- so the dry run prints slice 5 = 150, not 152. Sum across
   slices 1/2/3/5 equals len(kcc_tagged) exactly, which is the invariant
   that matters; the discrepancy is called out again at the count-check
   below rather than silently "fixed" to match a number that was itself an
   arithmetic slip in section 0 of the design doc.

2. "scope.py non-chemical measures for this pest" (slice 5). scope.py has
   no such data structure -- TARGETS only carries `canonical`/`type`/`chem`.
   `build_slice5_fact_sheet()` uses those three fields (when the pest is a
   scope.py target) plus an explicit "no gradeable label_db chemistry
   exists" note, and leaves the actual non-chemical measures to the
   generator's agronomic knowledge instead of fabricating a scope.py field
   that was never populated. NO_REGISTERED_CHEMISTRY is in any case a
   property of THIS project's label_db extraction coverage (expected_
   answerable() in verify.py), not necessarily scope.py's chem="none"
   literature judgement about vector-borne virals -- the two overlap for
   most of these 152 rows but are not the same claim, and the fact sheet
   says only what verify() will actually check.

Multi-pest handling (design doc section 2c) is implemented per spec but is
DEAD CODE on this corpus: every ANSWERABLE/NO_REGISTERED_CHEMISTRY row's
`pest_string` resolves to exactly one canonical (measured directly against
kcc_tagged.parquet before writing this file -- no "X and Y" pest_string
survived Phase 7's extraction). Kept for design fidelity and for any future
corpus where it does fire.

Multilingual augmentation (design doc section 5b) is NOT built here --
it is gated on native-speaker review of the transliterations and belongs
in its own sub-phase once that review exists.

ADDED DURING B2 TESTING, NOT IN THE ORIGINAL BRIEF: an off-topic pre-filter
on the PEST_UNKNOWN pool (slices 2 and 3's PEST_UNKNOWN sub-case). Inspecting
a real rendered prompt during the dry run showed PEST_UNKNOWN is not a clean
"vague pest query" bucket -- 367 of 4,069 rows (9%) are fertilizer/weed/
nutrient/price questions with zero pest vocabulary (e.g. "fertilizer dose of
cotton crop"), which system_prompt.txt's own out-of-scope rule covers
explicitly but which the original CLARIFY design would have forced through a
pest-diagnostic clarifying-question template regardless. verify() cannot
catch this on its own -- it grades label_db facts, never topical relevance --
so a topically-wrong CLARIFY answer still gates at 1.0. `is_offtopic_query()`
routes these to a new Kind.OFFTOPIC (in_scope=false, matching system_prompt's
weeds/fertilizer/price/credit/insurance/schemes rule) before they ever reach
the CLARIFY task. Confirmed with the user 2026-09-02. A further ~23% of the
pool matches neither the off-topic nor the pest-ish regex and is left as
CLARIFY -- a miss there is a false negative (an ambiguous question still gets
a defensible vague clarifying question), not a wrong answer, so it was not
worth chasing further with regex.

Structured outputs (--structured-output) build a best-effort strict
json_schema from Advisory.model_json_schema() but this has NEVER been
validated against a live API call (sub-phase B1 explicitly forbids live
calls). Default OFF. Validate with one real request before trusting it in
a production batch run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO_ROOT / ".env")

import scope  # noqa: E402
from application_method import extract_method  # noqa: E402
from pest_matcher import MatchResult, SynonymTable, match_all, match_pest  # noqa: E402
from restricted_ai import Restriction, normalise_ai_name  # noqa: E402
from schema import Advisory, Cause, ChemicalOption, Dose  # noqa: E402
from verify import (  # noqa: E402
    CHECK_WEIGHTS,
    VerifyContext,
    VerifyResources,
    normalise_ai,
    verify,
)

KCC_PATH = REPO_ROOT / "data" / "interim" / "kcc_tagged.parquet"
SYSTEM_PROMPT_PATH = REPO_ROOT / "src" / "system_prompt.txt"
OUT_DIR_DEFAULT = REPO_ROOT / "data" / "final"

CUTOFF_DATE = "2022-01-01"
MAX_ATTEMPTS = 3                 # 1 initial try + up to 2 retries
# Anthropic's real Message Batches limit is 100,000 requests OR 256MB per
# batch, whichever comes first (confirmed against current docs 2026-09-03 --
# not the 1,000 figure this sub-phase's brief assumed). This corpus's full
# slice 1/3/4/5 run is ~1,900 items, so BATCH_CHUNK never actually splits it;
# the headroom below 100k is just margin against the 256MB size cap.
BATCH_CHUNK = 90_000
DEFAULT_POLL_SECONDS = 60
GRAPE_TARGET = 300
GRAPE_HOLDOUT = 40
GENERATOR_MODEL = "claude-sonnet-4-6"
GROQ_DEFAULT_MODEL = "qwen/qwen3.6-27b"  # llama-3.1-70b-versatile was decommissioned by
                                          # Groq (confirmed via a live 400 model_decommissioned
                                          # error and client.models.list(), 2026-09-03 --
                                          # no Llama model remains on Groq's catalog at all).
                                          # qwen/qwen3.6-27b chosen 2026-09-03 after a smoke
                                          # test comparison against openai/gpt-oss-120b.
GROQ_MIN_INTERVAL_S = 2.0         # 30 req/min free-tier ceiling -> 1 req / 2s

__all__ = ["main"]


# ==========================================================================
# item kinds
# ==========================================================================

class Kind:
    DOSE = "dose"
    CLARIFY = "clarify"
    REFUSAL_DOSE = "refusal_dose"
    REFUSAL_CLARIFY = "refusal_clarify"
    REFUSAL_NOCHEM = "refusal_nochem"
    NOCHEM = "nochem"
    OFFTOPIC = "offtopic"
    QUERY_WRITER = "query_writer"


DOSE_LIKE = {Kind.DOSE, Kind.REFUSAL_DOSE}
CLARIFY_LIKE = {Kind.CLARIFY, Kind.REFUSAL_CLARIFY}
NOCHEM_LIKE = {Kind.NOCHEM, Kind.REFUSAL_NOCHEM}


# Off-topic pre-filter for the PEST_UNKNOWN pool (slices 2 and 3's PEST_UNKNOWN
# sub-case). Measured against kcc_tagged.parquet before adding this filter: of
# 4,069 PEST_UNKNOWN rows, 367 (9%) match OFFTOPIC_RX with no PEST_ISH_RX hit at
# all (fertilizer/weed/nutrient/price questions with zero pest vocabulary), and
# a further 931 (23%) match neither regex (short/ambiguous, left as CLARIFY --
# a keyword miss there is a false negative, not a wrong answer, since a vague
# clarifying question is still a defensible response to an unclassifiable
# query). Without this filter every PEST_UNKNOWN row -- including "fertilizer
# dose of cotton crop" -- was forced through the pest-diagnostic clarifying-
# question template, which system_prompt.txt's own out-of-scope rule (weeds,
# fertilizer, price, credit, insurance, schemes -> in_scope=false) contradicts.
# verify() cannot detect this on its own: it grades label_db facts, never
# topical relevance, so a topically-wrong CLARIFY answer still gates at 1.0.
_OFFTOPIC_RX = re.compile(
    r"fertili[sz]er|nutrient|urea|dap\b|potash|manure|irrigation|water\s?management|"
    r"variety|seed rate|sowing|planting|price|market|msp|subsidy|loan|credit|"
    r"scheme|insurance|weather|rainfall|soil test|spacing|yield|weed", re.I)
_PESTISH_RX = re.compile(
    r"pest|disease|insect|fung|blight|rot|wilt|mildew|rust|virus|mosaic|spot|"
    r"borer|fly|mite|thrips|aphid|whitefly|caterpillar|worm|beetle|attack|infest|"
    r"damage|yellow|wilting|leaf|fruit|pod|stem|root|spray|control|treatment", re.I)


def is_offtopic_query(query_text: str) -> bool:
    text = query_text or ""
    return bool(_OFFTOPIC_RX.search(text)) and not bool(_PESTISH_RX.search(text))


# ==========================================================================
# 1. load, slice, split
# ==========================================================================

def load_kcc(path: Path = KCC_PATH) -> pd.DataFrame:
    k = pd.read_parquet(path)
    k = k.reset_index(drop=True)
    k["kcc_row_id"] = k.index.astype(str)
    return k


def assign_slices(k: pd.DataFrame) -> pd.DataFrame:
    """Mutually exclusive partition, E-first. See module docstring point 1."""
    k = k.copy()
    banned = k["banned_chemical_query"].fillna(False).astype(bool)
    answ = k["answerability"]
    conditions = [
        banned,
        (~banned) & answ.eq("NO_REGISTERED_CHEMISTRY"),
        (~banned) & answ.eq("ANSWERABLE"),
        (~banned) & answ.eq("PEST_UNKNOWN"),
    ]
    k["slice"] = np.select(conditions, [3, 5, 1, 2], default=0)
    return k


def normalize_text(s: object) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        s = ""
    return re.sub(r"\s+", " ", str(s).strip().lower())


def split_kcc(k: pd.DataFrame, cutoff: str = CUTOFF_DATE) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Date-based split. Drops cross-boundary exact-text repeats from TEST.

    See reports/phase8_stepA_sft_generation_design.md section 7. Measured
    16 exact-normalised-text repeats crossing 2022-01-01 despite Phase C's
    semantic dedup; dropping them from the test side (never train) keeps
    train volume and costs the eventual benchmark about 1% of items.
    """
    k = k.copy()
    k["dt"] = pd.to_datetime(k["CreatedOn"], format="ISO8601")
    k["_norm"] = k["QueryText"].map(normalize_text)
    cutoff_ts = pd.Timestamp(cutoff)
    train = k[k["dt"] < cutoff_ts].copy()
    test = k[k["dt"] >= cutoff_ts].copy()
    train_norm = set(train["_norm"])
    dup_mask = test["_norm"].isin(train_norm)
    dropped = int(dup_mask.sum())
    test = test[~dup_mask].copy()
    return train, test, dropped


# ==========================================================================
# 2. label_db fact sheets
# ==========================================================================

def _num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
        return None
    f = float(v)
    return int(f) if f.is_integer() else f


def _str_or_none(v) -> Optional[str]:
    if v is None or pd.isna(v):
        return None
    return str(v)


def label_db_fact_rows(resources: VerifyResources, crop_slug: str,
                        canonical: Optional[str],
                        application_method: Optional[str]) -> list[dict]:
    """Gradeable, trainable, ban-filtered label_db rows for (crop, pest).

    Design doc section 2a. Every field here may be copied verbatim into a
    ChemicalOption by the generator; nothing here may be computed by it.
    Each dict carries a private '_ai' key (the normalised a.i. component
    frozenset) used internally for multi-pest intersection and the
    free-text-dose lexical check -- strip it before it reaches a prompt.
    """
    if not canonical:
        return []
    rows = resources.label_db.for_pair(crop_slug, canonical)
    rows = [r for r in rows if r.trainable and not r.defective and not r.contradiction]
    rows = [r for r in rows if not resources.restricted.check(r.ai_components, crop_slug)]
    if application_method:
        narrowed = [r for r in rows if r.application_method == application_method]
        rows = narrowed or rows  # a method matching nothing is not evidence every row is wrong
    df = resources.label_db.df
    out = []
    for r in rows:
        row = df.loc[r.index]
        # NOTE: no 'pest_as_printed' field. r.pest_surface_forms is the row's FULL
        # multi-pest cell (CIB&RC often registers one product against several pests
        # in one row), not specifically the surface form for `canonical` -- _Row
        # discards that pairing (see LabelDB.__init__), so any single surface form
        # picked from it can show a DIFFERENT pest than the one this row is being
        # returned for, even though the row genuinely IS registered for `canonical`
        # (guaranteed by for_pair()'s own indexing). Showing it would be misleading,
        # not merely uninformative, so it is omitted rather than best-guessed.
        out.append({
            "ai": str(row["active_ingredient"]),
            "_ai": r.ai_components,
            "dose_basis": _str_or_none(row["dose_formulation_basis"]),
            "dose_min": _num(row["dose_formulation_value_min"]),
            "dose_max": _num(row["dose_formulation_value_max"]),
            "dose_unit": _str_or_none(row["dose_formulation_unit"]),
            "dose_per_acre_min": _num(row["dose_formulation_per_acre_min"]),
            "dose_per_acre_max": _num(row["dose_formulation_per_acre_max"]),
            "dose_raw": _str_or_none(row["dose_formulation_raw"]),
            "phi_days": _num(row["phi_days"]),
            "phi_not_applicable": bool(row["phi_not_applicable"]),
            "phi_raw": _str_or_none(row["phi_raw"]),
            "application_method": r.application_method or None,
            "biological": r.biological,
        })
    return out


def _public(d: dict) -> dict:
    return {k: v for k, v in d.items() if not k.startswith("_")}


def build_scope_context(crop_slug: str) -> dict:
    targets = scope.TARGETS.get(crop_slug, [])
    names = {t["canonical"] for t in targets}
    confusable = [p for p in scope.CONFUSABLE_PAIRS if p[0] == crop_slug or p[2] == crop_slug]
    synonyms = {k: v for k, v in scope.SYNONYMS.items() if v in names}
    return {
        "crop": crop_slug,
        "possible_targets": targets,
        "confusable_pairs": confusable,
        "synonym_hints": synonyms,
    }


def build_slice5_fact_sheet(crop_slug: str, pest_canonical: Optional[str]) -> dict:
    """See module docstring point 2 -- scope.py carries no measures list."""
    targets = scope.TARGETS.get(crop_slug, [])
    match = next((t for t in targets if t["canonical"] == pest_canonical), None)
    return {
        "crop": crop_slug,
        "pest_canonical": pest_canonical,
        "scope_type": match["type"] if match else None,
        "scope_chem_richness": match["chem"] if match else None,
        "note": ("No verifiable registered chemistry exists in label_db for "
                 "this crop x pest pair. Do not invent a chemical or a dose."),
    }


def resolve_restricted_hit(resources: VerifyResources, crop_slug: str,
                            kcc_row: pd.Series) -> Optional[Restriction]:
    detail = str(kcc_row.get("banned_chemical_detail") or "")
    m = re.match(r"^(.+)\[(\w+)\]$", detail.strip())
    name = m.group(1).strip() if m else None
    comps: set[str] = set()
    for col in ("chemicals_in_answer", "chemicals_in_query"):
        v = str(kcc_row.get(col) or "")
        comps.update(x.strip() for x in v.split(";") if x.strip())
    if name:
        comps.add(name)
    if not comps:
        return None
    hits = resources.restricted.check(comps, crop_slug)
    if not hits:
        return None
    if name:
        exact = [h for h in hits if normalise_ai_name(h.active_ingredient) == normalise_ai_name(name)]
        if exact:
            return exact[0]
    return hits[0]


# ==========================================================================
# 3. GenItem
# ==========================================================================

@dataclass
class GenItem:
    slice: int
    kind: str
    row_id: str
    split: str                       # "train" | "test"
    crop_slug: str
    query_text: str
    pest_queries: list[str] = field(default_factory=list)
    canonicals: list[str] = field(default_factory=list)
    application_method: Optional[str] = None
    gold_escalate: Optional[bool] = None
    fact_rows: list[dict] = field(default_factory=list)
    common_ai: Optional[frozenset] = None
    scope_context: Optional[dict] = None
    restricted_hit: Optional[Restriction] = None
    attempt: int = 0
    prior_failures: list[str] = field(default_factory=list)

    def key(self) -> str:
        return f"S{self.slice}_{self.row_id}"


def _prefilter_log(row_id, slice_n, crop, canon, reason) -> dict:
    return {"row_id": row_id, "slice": slice_n, "crop_slug": crop,
            "canonical_pest": canon or "", "attempts": 0,
            "final_verify_score": 0.0, "outcome_reason": reason}


def _build_dose_item(resources, table, crop, row_id, split_name, query_text,
                      pest_str, method, kind, gold_escalate, restricted_hit,
                      slice_n) -> tuple[Optional[GenItem], Optional[dict]]:
    matches = match_all(crop, pest_str, table) if pest_str else []
    matched = [m for m in matches if m.matched]
    seen: list[str] = []
    for m in matched:
        if m.canonical_name not in seen:
            seen.append(m.canonical_name)
    if not seen:
        mp = match_pest(crop, pest_str, table) if pest_str else None
        if mp is not None and mp.matched:
            seen = [mp.canonical_name]
            matched = [mp]
        else:
            return None, _prefilter_log(row_id, slice_n, crop, None,
                                         f"pest {pest_str!r} did not resolve to a canonical")

    if len(seen) == 1:
        canon = seen[0]
        surface = matched[0].matched_surface_form or pest_str
        fact_rows = label_db_fact_rows(resources, crop, canon, method)
        if not fact_rows:
            return None, _prefilter_log(row_id, slice_n, crop, canon,
                                         "no gradeable label_db rows survived filtering "
                                         "(trainable/defective/contradiction/ban-list)")
        item = GenItem(slice=slice_n, kind=kind, row_id=row_id, split=split_name,
                        crop_slug=crop, query_text=query_text, pest_queries=[surface],
                        canonicals=[canon], application_method=method,
                        gold_escalate=gold_escalate, fact_rows=fact_rows,
                        restricted_hit=restricted_hit)
        return item, None

    # Multi-canonical branch (design doc 2c) -- unreached on this corpus,
    # kept for fidelity. See module docstring.
    per = {c: label_db_fact_rows(resources, crop, c, method) for c in seen}
    if any(not v for v in per.values()):
        canon = seen[0]
        surface = matched[0].matched_surface_form or pest_str
        fact_rows = per.get(canon) or label_db_fact_rows(resources, crop, canon, method)
        if not fact_rows:
            return None, _prefilter_log(row_id, slice_n, crop, canon,
                                         "no gradeable rows for fallback canonical of a multi-pest query")
        item = GenItem(slice=slice_n, kind=kind, row_id=row_id, split=split_name,
                        crop_slug=crop, query_text=query_text, pest_queries=[surface],
                        canonicals=[canon], application_method=method,
                        gold_escalate=gold_escalate, fact_rows=fact_rows,
                        restricted_hit=restricted_hit)
        return item, None

    ai_sets = [{r["_ai"] for r in rows} for rows in per.values()]
    common = set.intersection(*ai_sets) if ai_sets else set()
    if common:
        fact_rows = [r for rows in per.values() for r in rows if r["_ai"] in common]
        surfaces = [(m.matched_surface_form or pest_str) for m in matched if m.canonical_name in seen]
        item = GenItem(slice=slice_n, kind=kind, row_id=row_id, split=split_name,
                        crop_slug=crop, query_text=query_text, pest_queries=surfaces,
                        canonicals=seen, application_method=method,
                        gold_escalate=gold_escalate, fact_rows=fact_rows,
                        common_ai=frozenset(common), restricted_hit=restricted_hit)
        return item, None

    canon = seen[0]
    surface = matched[0].matched_surface_form or pest_str
    fact_rows = per[canon]
    item = GenItem(slice=slice_n, kind=kind, row_id=row_id, split=split_name,
                    crop_slug=crop, query_text=query_text, pest_queries=[surface],
                    canonicals=[canon], application_method=method,
                    gold_escalate=gold_escalate, fact_rows=fact_rows,
                    restricted_hit=restricted_hit)
    return item, None


def build_item_for_row(row: pd.Series, split_name: str, resources: VerifyResources,
                        table: SynonymTable) -> tuple[Optional[GenItem], Optional[dict]]:
    slice_n = int(row["slice"])
    crop = str(row["crop_slug"])
    row_id = str(row["kcc_row_id"])
    query_text = str(row["QueryText"] or "")
    pest_str = (str(row["pest_string"] or "").strip()
                or str(row["pest_canonical"] or "").strip())
    method = extract_method(query_text)

    if slice_n == 1:
        return _build_dose_item(resources, table, crop, row_id, split_name, query_text,
                                 pest_str, method, Kind.DOSE, None, None, slice_n=1)

    if slice_n == 2:
        if is_offtopic_query(query_text):
            item = GenItem(slice=2, kind=Kind.OFFTOPIC, row_id=row_id, split=split_name,
                            crop_slug=crop, query_text=query_text, pest_queries=[],
                            application_method=method, gold_escalate=False)
            return item, None
        ctx = build_scope_context(crop)
        item = GenItem(slice=2, kind=Kind.CLARIFY, row_id=row_id, split=split_name,
                        crop_slug=crop, query_text=query_text,
                        pest_queries=[pest_str] if pest_str else [],
                        application_method=method, gold_escalate=False,
                        scope_context=ctx)
        return item, None

    if slice_n == 5:
        canon = str(row["pest_canonical"] or "") or None
        fs = build_slice5_fact_sheet(crop, canon)
        item = GenItem(slice=5, kind=Kind.NOCHEM, row_id=row_id, split=split_name,
                        crop_slug=crop, query_text=query_text,
                        pest_queries=[pest_str or (canon or "")],
                        canonicals=[canon] if canon else [],
                        application_method=method, gold_escalate=True,
                        scope_context=fs)
        return item, None

    if slice_n == 3:
        rh = resolve_restricted_hit(resources, crop, row)
        answ = str(row["answerability"])
        if answ == "ANSWERABLE":
            return _build_dose_item(resources, table, crop, row_id, split_name, query_text,
                                     pest_str, method, Kind.REFUSAL_DOSE, True, rh, slice_n=3)
        if answ == "NO_REGISTERED_CHEMISTRY":
            canon = str(row["pest_canonical"] or "") or None
            fs = build_slice5_fact_sheet(crop, canon)
            item = GenItem(slice=3, kind=Kind.REFUSAL_NOCHEM, row_id=row_id, split=split_name,
                            crop_slug=crop, query_text=query_text,
                            pest_queries=[pest_str or (canon or "")],
                            canonicals=[canon] if canon else [],
                            application_method=method, gold_escalate=True,
                            scope_context=fs, restricted_hit=rh)
            return item, None
        if is_offtopic_query(query_text):
            # gold_escalate=True (not False, unlike the plain slice-2 OFFTOPIC case):
            # a restricted-chemical mention still warrants expert follow-up even when
            # the underlying question itself is out of scope. Matches Slice 3's
            # blanket escalate=True policy (design doc section 4).
            item = GenItem(slice=3, kind=Kind.OFFTOPIC, row_id=row_id, split=split_name,
                            crop_slug=crop, query_text=query_text, pest_queries=[],
                            application_method=method, gold_escalate=True,
                            restricted_hit=rh)
            return item, None
        ctx = build_scope_context(crop)
        item = GenItem(slice=3, kind=Kind.REFUSAL_CLARIFY, row_id=row_id, split=split_name,
                        crop_slug=crop, query_text=query_text,
                        pest_queries=[pest_str] if pest_str else [],
                        application_method=method, gold_escalate=True,
                        scope_context=ctx, restricted_hit=rh)
        return item, None

    return None, _prefilter_log(row_id, slice_n, crop, None, f"unhandled slice {slice_n}")


def build_items_for_df(df: pd.DataFrame, split_name: str, resources: VerifyResources,
                        table: SynonymTable) -> tuple[list[GenItem], list[dict]]:
    items, prelog = [], []
    for _, row in df[df["slice"].isin([1, 2, 3, 5])].iterrows():
        item, log_row = build_item_for_row(row, split_name, resources, table)
        if item is not None:
            items.append(item)
        if log_row is not None:
            prelog.append(log_row)
    return items, prelog


# ==========================================================================
# 4. prompts
# ==========================================================================

DEPLOYMENT_SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

GENERATOR_PREAMBLE = """You are generating supervised fine-tuning data for a plant-protection \
advisory model. Below, inside <deployment_system_prompt>, is the exact system prompt that \
model will be deployed with. Produce the single JSON object that model SHOULD have emitted \
for the farmer query given to you, following every rule in that prompt.

You will also be given a <fact_sheet> and/or <scope_context> block. Those are your ONLY \
source of chemical facts, registered targets, or dose/PHI numbers -- you may select from \
them and write prose around them, but you may never compute, convert, recall, or invent a \
number, an active ingredient, or a registered pest that is not present in what you were \
given."""

OUTPUT_CONTRACT_TEXT = """<output_contract>
Output a single JSON object matching this shape exactly (Python/pydantic names shown):

  Advisory: in_scope(bool), query_understood(bool),
            clarifying_question(str|null), likely_causes(list[Cause]),
            non_chemical_first(list[str]), chemical_options(list[ChemicalOption]),
            safety(list[str]), escalate_to_expert(bool)
  Cause: name(str), type("pest"|"disease"|"nutrient"|"abiotic"|"weed"),
         confidence(0..1), evidence(str)
  ChemicalOption: active_ingredient(str), formulation(str), dose(Dose),
         spray_volume_min_l_per_acre(int|null), spray_volume_max_l_per_acre(int|null),
         phi_days(int|null), phi_not_applicable(bool), caution(str)
  Dose: basis("per_acre"|"per_ha"|"per_tree"|"per_plant"|"per_kg_seed"|"per_sq_m"|
              "concentration_pct"|"per_litre_water"|"free_text"|"unstated"),
        value_min(number|null), value_max(number|null),
        unit("g"|"ml"|"kg"|"l"|"%"|null), raw(str)

Hard invariants:
  - out-of-scope (in_scope=false) or an ununderstood query (query_understood=false)
    carries an EMPTY chemical_options.
  - a ChemicalOption with phi_days=null and phi_not_applicable=false forces
    escalate_to_expert=true on the whole Advisory.
  - phi_not_applicable=true can never sit beside a phi_days number.
  - a numeric dose basis (anything but free_text/unstated) requires value_min and unit.

Output: the JSON object only. First byte "{", last byte "}". No markdown fences, no \
prose before or after, no trailing commentary.
</output_contract>"""

TASK_TEXT: dict[str, str] = {
    Kind.DOSE: """Using ONLY the rows in <fact_sheet>, write the Advisory JSON for this \
farmer's query.
- in_scope=true, query_understood=true.
- CRITICAL: likely_causes[0].name must be EXACTLY the name given in <resolved_pest> if that \
block is present -- copy it verbatim, do not substitute a different (even closely related) \
pest name from your own knowledge. A farmer's phrase like "fruit borer" can genuinely mean \
more than one organism depending on crop and region; <resolved_pest> is this dataset's \
already-resolved answer, not a suggestion. If <resolved_pest> is absent, use the bare common \
name only (e.g. 'Aphid', 'Leaf miner', 'Wilt', 'Powdery mildew', 'Pink bollworm'). Either \
way: NO scientific/Latin binomials, NO parentheses, NO Aphididae-style family names -- put \
species detail in the evidence field instead.
- likely_causes: the matched pest first, confidence >= 0.8.
- chemical_options: choose 2-4 rows. Copy active_ingredient and every dose/PHI field \
VERBATIM from the chosen row -- never compute, convert, or invent a number. Prefer rows \
with phi_days set or phi_not_applicable=true over rows with an unknown PHI; only fall back \
to an unknown-PHI row if nothing else survives.
- Prefer dose_per_acre_min/max when non-null (state basis "per_acre"); otherwise use \
dose_min/max with the row's own dose_basis. Copy dose_raw into Dose.raw exactly either way.
- If dose_min is null and dose_basis is "free_text", you may still recommend the row: set \
Dose.basis="free_text", leave value_min/value_max/unit null, and copy dose_raw into \
Dose.raw CHARACTER FOR CHARACTER -- do not add a number of your own.
- spray_volume_min/max_l_per_acre: leave null (no ground truth exists for this).
- non_chemical_first: at least 2 concrete, specific cultural or mechanical measures.
- escalate_to_expert: false when every chosen option has a known PHI or phi_not_applicable; \
true only if you had to pick an unknown-PHI row because nothing else was available.""",

    Kind.REFUSAL_DOSE: """The farmer named a chemical that is restricted -- see \
<restricted_ai>. In `safety`, state plainly that this specific chemical must not be used, \
naming its tier and the instrument/date restricting it. Then, using ONLY <fact_sheet> \
(which already excludes the restricted chemical), recommend 2-4 legal registered \
alternatives for the SAME crop and pest, following the same verbatim-copy rules as a normal \
dose answer.
- in_scope=true, query_understood=true, chemical_options=2-4 legal alternatives.
- CRITICAL: likely_causes[0].name must be EXACTLY the name given in <resolved_pest> if that \
block is present -- copy it verbatim, do not substitute a different (even closely related) \
pest name from your own knowledge. If <resolved_pest> is absent, use the bare common name \
only (e.g. 'Aphid', 'Leaf miner', 'Wilt', 'Powdery mildew', 'Pink bollworm'). Either way: NO \
scientific/Latin binomials, NO parentheses, NO Aphididae-style family names -- put species \
detail in the evidence field instead.
- likely_causes: the matched pest first, confidence >= 0.8.
- escalate_to_expert=true always (a farmer holding or intending to use a restricted \
chemical needs expert follow-up regardless of the legal alternative given).""",

    Kind.CLARIFY: """The farmer's description is too vague to diagnose. Using \
<scope_context>, decide which of the listed possible_targets could plausibly explain it.
- in_scope=true, query_understood=false, chemical_options=[] (empty).
- likely_causes: 0-3 candidates drawn from possible_targets, each confidence <= 0.4.
- clarifying_question: ONE question that would let you tell the candidates apart -- ask \
about the specific plant part affected, the symptom's appearance, or the crop growth \
stage. Do NOT ask a generic question such as "can you provide more details" or "what \
symptoms do you see" -- name a concrete thing to look for.
- escalate_to_expert=false (a clarifying question is a continuation of the conversation, \
not a terminal answer).""",

    Kind.REFUSAL_CLARIFY: """The farmer named a chemical that is restricted -- see \
<restricted_ai> -- but the pest/disease described is too vague to diagnose. State the \
chemical's restricted status plainly in `safety`. Then, using <scope_context>, ask ONE \
specific clarifying question exactly as you would for an ordinary vague query -- see the \
plant-part/symptom/stage guidance above. Do not ask a generic question.
- in_scope=true, query_understood=false, chemical_options=[].
- escalate_to_expert=true always (restricted-chemical exposure needs expert follow-up).""",

    Kind.NOCHEM: """No verifiable registered chemistry exists in label_db for this crop x \
pest pair -- see the note in the fact block. Give genuine, specific cultural, mechanical, or \
biological control measures in non_chemical_first (at least 2). Do not invent a chemical.
- CRITICAL: likely_causes[0].name must be EXACTLY the name given in <resolved_pest> if that \
block is present -- copy it verbatim, do not substitute a different pest name from your own \
knowledge. If <resolved_pest> is absent, use the bare common name only. Either way: NO \
scientific/Latin binomials, NO parentheses -- put species detail in evidence instead.
- in_scope=true, query_understood=true, chemical_options=[].
- escalate_to_expert=true always.""",

    Kind.REFUSAL_NOCHEM: """The farmer named a chemical that is restricted -- see \
<restricted_ai>. State its restricted status plainly in `safety`. No registered chemistry \
exists for this crop x pest pair either way (see the note); give genuine non_chemical_first \
measures instead (at least 2). Do not invent a chemical.
- in_scope=true, query_understood=true, chemical_options=[].
- escalate_to_expert=true always.""",

    Kind.OFFTOPIC: """This query is not about pest or disease management on the eight \
covered crops -- it concerns fertilizer, weed control, irrigation, variety selection, \
market price, credit, insurance, or a similar topic outside scope.
- in_scope=false, query_understood=true, clarifying_question=null.
- likely_causes=[], non_chemical_first=[], chemical_options=[].
- safety: one sentence stating what you DO cover -- pest and disease management on \
cotton, soybean, tur, gram, onion, tomato, grape, and pomegranate -- so the farmer knows \
where to ask again. If <restricted_ai> is present, still name that chemical's restricted \
status first.
- escalate_to_expert=false, UNLESS <restricted_ai> is present, in which case true (a \
restricted-chemical mention needs expert follow-up regardless of the rest of the question).""",
}

WORKED_EXAMPLE = """<worked_example kind="dose">
resolved_pest is ["Jassid"]. fact_sheet contains one row: {"ai": "Acephate 75% SP", "dose_basis": "per_ha", \
"dose_min": 300, "dose_max": null, "dose_unit": "g", "dose_per_acre_min": 121.4, \
"dose_per_acre_max": null, "dose_raw": "300 g/ha", "phi_days": 15, \
"phi_not_applicable": false, "phi_raw": "15", "biological": false}
Correct output (abbreviated):
{"in_scope": true, "query_understood": true,
 "likely_causes": [{"name": "Jassid", "type": "pest", "confidence": 0.9, "evidence": "..."}],
 "non_chemical_first": ["Use yellow sticky traps to monitor.", "Avoid excess nitrogen, which favours sucking pests."],
 "chemical_options": [{"active_ingredient": "Acephate 75% SP", "formulation": "Acephate 75% SP",
   "dose": {"basis": "per_acre", "value_min": 121.4, "value_max": null, "unit": "g", "raw": "300 g/ha"},
   "spray_volume_min_l_per_acre": null, "spray_volume_max_l_per_acre": null,
   "phi_days": 15, "phi_not_applicable": false, "caution": "Wear gloves and a mask during application."}],
 "safety": ["Keep people and livestock away from the treated field until the PHI has passed."],
 "escalate_to_expert": false}
</worked_example>"""


def build_system_message() -> str:
    return "\n\n".join([GENERATOR_PREAMBLE,
                         f"<deployment_system_prompt>\n{DEPLOYMENT_SYSTEM_PROMPT}\n</deployment_system_prompt>",
                         OUTPUT_CONTRACT_TEXT,
                         WORKED_EXAMPLE])


SYSTEM_MESSAGE = build_system_message()


def build_user_message(item: GenItem) -> str:
    parts = [f'<query crop="{item.crop_slug}">\n{item.query_text}\n</query>']
    if item.restricted_hit is not None:
        rh = item.restricted_hit
        parts.append("<restricted_ai>\n" + json.dumps({
            "active_ingredient": rh.active_ingredient, "tier": rh.tier,
            "instrument": rh.instrument, "date": rh.date, "notes": rh.notes,
        }, ensure_ascii=False) + "\n</restricted_ai>")
    if item.canonicals:
        # Fix A (pre-Slice2): the fact_sheet deliberately carries no pest name
        # (see label_db_fact_rows docstring), so without this the model must
        # guess the canonical purely from ambiguous farmer text -- measured
        # failure mode: "fruit borer" on cotton is genuinely ambiguous between
        # Helicoverpa armigera (this corpus's tagged gold, and the synonym
        # table's own mapping) and Pink bollworm (an equally common colloquial
        # reading), and the model guessed the latter on 6 real rows in the
        # full run. This block is the SAME crutch pattern as fact_sheet: it
        # exists only at generation time and is never written into the
        # emitted sft.jsonl record, so the trained model still has to name the
        # pest from the bare query with no ground-truth hint at inference time.
        parts.append("<resolved_pest>\n" + json.dumps(item.canonicals, ensure_ascii=False) +
                      "\n</resolved_pest>")
    if item.fact_rows:
        pub = [_public(d) for d in item.fact_rows]
        parts.append(f"<fact_sheet>\n{json.dumps(pub, ensure_ascii=False)}\n</fact_sheet>")
        if item.common_ai:
            parts.append("<allowed_active_ingredients>\nThis query names more than one "
                          "organism. List each in likely_causes. Recommend chemical_options "
                          "ONLY for active ingredients registered for EVERY organism you "
                          "listed.\n</allowed_active_ingredients>")
    if item.scope_context:
        parts.append(f"<scope_context>\n{json.dumps(item.scope_context, ensure_ascii=False)}\n</scope_context>")
    parts.append(f"<task>\n{TASK_TEXT[item.kind]}\n</task>")
    if item.prior_failures:
        fb = "\n".join(f"- {f}" for f in item.prior_failures[:8])
        parts.append("<previous_attempt_failures>\nYour previous attempt failed these "
                      f"checks. Fix them exactly; do not introduce new problems:\n{fb}\n"
                      "</previous_attempt_failures>")
    return "\n\n".join(parts)


def build_query_writer_prompt(crop_slug: str, canonical: str, pest_type: str,
                               style_samples: list[str], n: int) -> tuple[str, str]:
    system = ("You write realistic Kisan Call Centre (KCC) farmer-query text for a plant-"
              "protection training set. KCC operators write short, often ALL-CAPS, "
              "grammatically loose English summaries of a farmer's phone call. Match that "
              "register exactly -- do not write polished prose.")
    samples = "\n".join(f"- {s}" for s in style_samples[:15])
    user = (f'Write {n} short KCC-style query summaries about "{canonical}" ({pest_type}) '
            f'on {crop_slug} in Maharashtra. Vary crop growth stage, month, phrasing, and '
            f'register (some ALL CAPS, some lowercase, some with typos like real operator '
            f'notes). Every query must be clearly about {canonical} on {crop_slug} -- do '
            f'not name a different pest or crop.\n\nStyle examples from the real corpus '
            f'(topic differs, match only the REGISTER):\n{samples}\n\n'
            f'Output a JSON array of exactly {n} strings. No markdown, no numbering, no '
            f'prose outside the array.')
    return system, user


def _parse_query_writer_response(text: Optional[str]) -> list[str]:
    if not text:
        return []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
    except json.JSONDecodeError:
        pass
    return [ln.strip("-* \t") for ln in text.splitlines() if ln.strip()]


# ==========================================================================
# 5. structured-output schema (EXPERIMENTAL, unvalidated -- see module docstring)
# ==========================================================================

def build_output_schema() -> dict:
    raw = Advisory.model_json_schema()
    defs = raw.pop("$defs", {})

    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"].rsplit("/", 1)[-1]
                return resolve(dict(defs[ref]))
            out = {k: resolve(v) for k, v in node.items() if k not in ("title", "default")}
            if out.get("type") == "object" and "properties" in out:
                out["additionalProperties"] = False
                out["required"] = list(out["properties"].keys())
            return out
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    return resolve(raw)


# ==========================================================================
# 6. backends
# ==========================================================================

@dataclass
class BatchRequest:
    custom_id: str
    system: str
    user: str
    max_tokens: int = 2000


class GenerationBackend:
    def generate(self, requests: list[BatchRequest],
                  items: Optional[dict[str, GenItem]] = None) -> dict[str, Optional[str]]:
        raise NotImplementedError


def _cached_system_param(text: str) -> list[dict]:
    """Wrap a system prompt string as a single cache_control-tagged content block.

    Fix C (pre-Slice2): SYSTEM_MESSAGE and the query-writer system string are
    each byte-identical across EVERY request that uses them in a run (no
    per-item variation) -- see build_system_message() and
    build_query_writer_prompt(). That makes the whole string a clean ephemeral
    cache candidate: only the first request in a run pays full input price for
    it, every later request within the cache TTL pays the ~10%-of-base
    cache-read rate. Only applies to Anthropic backends -- OllamaBackend has no
    such concept and ignores cache_control silently (it isn't a real request
    field there). Note SYSTEM_MESSAGE (~1.6K tokens) clears Anthropic's
    minimum-cacheable-prefix floor; the shorter query-writer system string may
    not, in which case this is a harmless no-op (normal input pricing, no
    error) rather than a failure.
    """
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


class AnthropicBatchBackend(GenerationBackend):
    """Real backend. NOT exercised by --mode dry-run. See module docstring."""

    def __init__(self, model: str = GENERATOR_MODEL, structured_output: bool = False,
                 poll_seconds: int = DEFAULT_POLL_SECONDS):
        import anthropic  # deferred: dry-run must never require this import to succeed
        self.client = anthropic.Anthropic()
        self.model = model
        self.structured_output = structured_output
        self.poll_seconds = poll_seconds
        self._schema = build_output_schema() if structured_output else None

    def generate(self, requests: list[BatchRequest],
                  items: Optional[dict[str, GenItem]] = None) -> dict[str, Optional[str]]:
        from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
        from anthropic.types.messages.batch_create_params import Request

        batch_ids: list[str] = []
        for i in range(0, len(requests), BATCH_CHUNK):
            chunk = requests[i:i + BATCH_CHUNK]
            reqs = []
            for r in chunk:
                params = dict(model=self.model, max_tokens=r.max_tokens,
                              system=_cached_system_param(r.system),
                              messages=[{"role": "user", "content": r.user}])
                if self.structured_output:
                    params["output_config"] = {"format": {"type": "json_schema", "schema": self._schema}}
                reqs.append(Request(custom_id=r.custom_id,
                                     params=MessageCreateParamsNonStreaming(**params)))
            batch = self.client.messages.batches.create(requests=reqs)
            batch_ids.append(batch.id)

        pending = set(batch_ids)
        while pending:
            time.sleep(self.poll_seconds)
            for bid in list(pending):
                b = self.client.messages.batches.retrieve(bid)
                if b.processing_status == "ended":
                    pending.discard(bid)

        results: dict[str, Optional[str]] = {}
        for bid in batch_ids:
            for result in self.client.messages.batches.results(bid):
                if result.result.type == "succeeded":
                    msg = result.result.message
                    text = next((b.text for b in msg.content if b.type == "text"), None)
                    results[result.custom_id] = text
                else:
                    results[result.custom_id] = None
        return results


class AnthropicLiveBackend(GenerationBackend):
    """Synchronous, non-batch backend -- one request per item, in order.

    Added for Fix B (pre-Slice2): validating --structured-output needs a
    single real response back in seconds, not a batch job that may take up
    to the Batches API's ~1 hour typical turnaround. NOT used for the
    production generation run (that stays on AnthropicBatchBackend for the
    50% batch discount) -- this exists for smoke-testing one or a handful of
    items against the real API. No retry/backoff beyond what the SDK already
    does by default (max_retries=2 on 408/409/429/5xx).
    """

    def __init__(self, model: str = GENERATOR_MODEL, structured_output: bool = False):
        import anthropic  # deferred: dry-run must never require this import to succeed
        self.client = anthropic.Anthropic()
        self.model = model
        self.structured_output = structured_output
        self._schema = build_output_schema() if structured_output else None

    def generate(self, requests: list[BatchRequest],
                  items: Optional[dict[str, GenItem]] = None) -> dict[str, Optional[str]]:
        results: dict[str, Optional[str]] = {}
        for r in requests:
            params = dict(model=self.model, max_tokens=r.max_tokens,
                          system=_cached_system_param(r.system),
                          messages=[{"role": "user", "content": r.user}])
            if self.structured_output:
                params["output_config"] = {"format": {"type": "json_schema", "schema": self._schema}}
            try:
                msg = self.client.messages.create(**params)
            except Exception as exc:  # noqa: BLE001 -- surfaced to the caller via None + logged by caller
                print(f"  AnthropicLiveBackend error for {r.custom_id}: {exc}")
                results[r.custom_id] = None
                continue
            text = next((b.text for b in msg.content if b.type == "text"), None)
            results[r.custom_id] = text
        return results


class GroqBackend(GenerationBackend):
    """Slice 2 backend: Groq's OpenAI-compatible API (no Anthropic spend).

    Sequential, one request per item -- Groq's free tier is rate-limited
    (30 req/min, 6,000 tokens/min), so there's nothing to parallelize
    against; the pacing IS the throughput ceiling. _pace() enforces a
    minimum GROQ_MIN_INTERVAL_S gap between consecutive REQUEST STARTS
    (not a blind post-call sleep, so a slow completion doesn't stack an
    extra wait on top of its own latency). Only the 30 req/min bound is
    actively enforced; the 6,000 tok/min bound is not separately tracked --
    at 30 req/min that would require averaging >200 tokens/request, which
    the fact_sheet-bearing dose prompts can exceed, so a 429 is still
    possible in principle. A 429 or any other API error returns None for
    that custom_id (same "no response" contract every backend uses) and
    the caller's normal retry-round logic handles it -- no special-cased
    backoff here.

    Response text is returned as-is, valid JSON or not: this backend does
    no JSON parsing/validation itself. A malformed response reaches
    verify_item() exactly like a malformed response from any other
    backend and fails there as G1 ("output is not JSON").

    reasoning_format="hidden" and reasoning_effort="none" (both Groq/Qwen-
    specific, sent via extra_body -- the openai SDK's typed .create()
    rejects unknown kwargs otherwise) are not cosmetic, and reasoning_effort
    is the load-bearing one. Measured live against qwen/qwen3.6-27b (the
    current GROQ_DEFAULT_MODEL -- llama-3.1-70b-versatile is decommissioned,
    see that constant's comment):
      - neither set: <think>...</think> wraps the JSON in the visible
        content, failing json.loads() 100% of the time (G1, 20/20 rows).
      - reasoning_format="hidden" alone: the trace is hidden from the
        response text, but the model still SPENDS max_tokens on it
        internally -- completion_tokens_details.reasoning_tokens hit 2000/
        2000, finish_reason="length", content=="" (18/20 rows empty).
      - reasoning_format="hidden" + reasoning_effort="none": ~2s/call,
        finish_reason="stop", clean JSON. This is the combination that
        actually works.
    Pass reasoning_format=None / reasoning_effort=None for a non-reasoning
    model that doesn't recognise these parameters.
    """

    def __init__(self, model: str = GROQ_DEFAULT_MODEL, api_key: Optional[str] = None,
                 min_interval_s: float = GROQ_MIN_INTERVAL_S,
                 reasoning_format: Optional[str] = "hidden",
                 reasoning_effort: Optional[str] = "none"):
        from openai import OpenAI  # deferred: dry-run must never require this import to succeed
        key = api_key or os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError(
                "GroqBackend needs a Groq API key: pass --groq-api-key or set GROQ_API_KEY")
        self.client = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
        self.model = model
        self.min_interval_s = min_interval_s
        self.reasoning_format = reasoning_format
        self.reasoning_effort = reasoning_effort
        self._last_call_ts: Optional[float] = None

    def _pace(self) -> None:
        if self._last_call_ts is not None:
            wait = self.min_interval_s - (time.monotonic() - self._last_call_ts)
            if wait > 0:
                time.sleep(wait)
        self._last_call_ts = time.monotonic()

    def generate(self, requests: list[BatchRequest],
                  items: Optional[dict[str, GenItem]] = None) -> dict[str, Optional[str]]:
        results: dict[str, Optional[str]] = {}
        extra_body = {}
        if self.reasoning_format:
            extra_body["reasoning_format"] = self.reasoning_format
        if self.reasoning_effort:
            extra_body["reasoning_effort"] = self.reasoning_effort
        for r in requests:
            self._pace()
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=r.max_tokens,
                    extra_body=extra_body or None,
                    messages=[{"role": "system", "content": r.system},
                              {"role": "user", "content": r.user}],
                )
                text = resp.choices[0].message.content
            except Exception as exc:  # noqa: BLE001 -- surfaced via None + logged, same as other backends
                print(f"  GroqBackend error for {r.custom_id}: {exc}")
                text = None
            results[r.custom_id] = text
        return results


class MockBackend(GenerationBackend):
    """Reference-solver test double for --mode dry-run.

    Builds a genuinely correct Advisory from the SAME structured item data
    the real prompt is built from (not by parsing rendered prompt text), so
    verify() is exercised for real. A deterministic fraction of items are
    corrupted to exercise accept / retry-then-succeed / retry-then-reject.
    """

    def __init__(self, seed: int = 42):
        self.seed = seed

    def generate(self, requests: list[BatchRequest],
                  items: Optional[dict[str, GenItem]] = None) -> dict[str, Optional[str]]:
        out: dict[str, Optional[str]] = {}
        for req in requests:
            if req.custom_id.startswith("QW_"):
                out[req.custom_id] = self._mock_query_writer(req.custom_id)
                continue
            base_key = req.custom_id.rsplit("_r", 1)[0]
            item = items[base_key] if items else None
            out[req.custom_id] = self._respond(item) if item is not None else None
        return out

    def _mock_query_writer(self, custom_id: str) -> str:
        # custom_id shape is "QW_grape_{target_idx}_{call_idx}_{take}" -- the pest
        # canonical is deliberately NOT embedded (see build_grape_items docstring
        # note on the batch API's custom_id charset), so this mock has no access
        # to the real target name and uses a generic placeholder instead. That's
        # cosmetic only: downstream code resolves the real canonical via
        # canon_by_id, never by re-parsing this synthetic query text.
        n = int(custom_id.rsplit("_", 1)[-1])
        stages = ["pre-bloom", "berry stage", "veraison", "post-harvest"]
        out = [f"FARMER ASKED ABOUT A GRAPE PEST/DISEASE AT {stages[i % len(stages)].upper()} "
               f"STAGE (VARIANT {i})" for i in range(n)]
        return json.dumps(out)

    def _bucket(self, item: GenItem) -> int:
        h = int(hashlib.sha256(item.key().encode()).hexdigest(), 16)
        return h % 100

    def _respond(self, item: GenItem) -> str:
        bucket = self._bucket(item)
        broken_permanent = bucket < 5
        broken_then_fixed = 5 <= bucket < 10
        adv = self._reference_advisory(item)
        if broken_permanent or (broken_then_fixed and item.attempt == 0):
            return self._corrupt(adv, item)
        return adv.model_dump_json()

    def _reference_advisory(self, item: GenItem) -> Advisory:
        if item.kind in DOSE_LIKE:
            rows = item.fact_rows
            allowed = [r for r in rows if (not item.common_ai) or r["_ai"] in item.common_ai]
            good = [r for r in allowed if r["phi_days"] is not None or r["phi_not_applicable"]]
            pool = good or allowed
            chosen = pool[:4] if len(pool) >= 2 else (allowed[:2] if len(allowed) >= 2 else allowed)
            options = []
            for r in chosen:
                use_per_acre = r["dose_per_acre_min"] is not None
                if r["dose_basis"] == "free_text" or r["dose_min"] is None:
                    dose = Dose(basis="free_text", raw=r["dose_raw"] or "")
                elif use_per_acre:
                    dose = Dose(basis="per_acre", value_min=r["dose_per_acre_min"],
                                value_max=r["dose_per_acre_max"], unit=r["dose_unit"],
                                raw=r["dose_raw"] or "")
                else:
                    dose = Dose(basis=r["dose_basis"], value_min=r["dose_min"],
                                value_max=r["dose_max"], unit=r["dose_unit"],
                                raw=r["dose_raw"] or "")
                options.append(ChemicalOption(
                    active_ingredient=r["ai"], formulation=r["ai"], dose=dose,
                    phi_days=r["phi_days"], phi_not_applicable=r["phi_not_applicable"],
                    caution="Wear protective equipment during application."))
            escalate = any(o.phi_days is None and not o.phi_not_applicable for o in options)
            cause_name = item.pest_queries[0] if item.pest_queries else item.crop_slug
            causes = [Cause(name=cause_name, type="pest", confidence=0.9,
                             evidence="matched fact sheet")]
            safety = ["Wear protective equipment; keep people and livestock away from "
                       "treated areas until the pre-harvest interval has passed."]
            if item.kind == Kind.REFUSAL_DOSE and item.restricted_hit is not None:
                rh = item.restricted_hit
                safety.insert(0, f"{rh.active_ingredient} is {rh.tier} ({rh.instrument} "
                                  f"{rh.date}); do not use it.")
                escalate = True
            return Advisory(
                in_scope=True, query_understood=True, likely_causes=causes,
                non_chemical_first=["Remove and destroy infested plant material.",
                                     "Use yellow/blue sticky traps to monitor pest load."],
                chemical_options=options, safety=safety, escalate_to_expert=escalate)

        if item.kind in CLARIFY_LIKE:
            targets = (item.scope_context or {}).get("possible_targets", [])
            causes = [Cause(name=t["canonical"], type=t["type"], confidence=0.3,
                             evidence="ambiguous description") for t in targets[:2]]
            q = (f"Which part of the {item.crop_slug} plant shows the damage -- leaves, "
                 f"pods/fruit, or stem -- and at what growth stage did it appear?")
            safety = []
            if item.restricted_hit is not None:
                rh = item.restricted_hit
                safety.append(f"{rh.active_ingredient} is {rh.tier}; do not use it.")
            escalate = item.gold_escalate if item.gold_escalate is not None else False
            return Advisory(in_scope=True, query_understood=False, clarifying_question=q,
                             likely_causes=causes, chemical_options=[], safety=safety,
                             escalate_to_expert=escalate)

        if item.kind == Kind.OFFTOPIC:
            safety = ["This system covers pest and disease management on cotton, soybean, "
                       "tur, gram, onion, tomato, grape, and pomegranate -- ask again with "
                       "that kind of question."]
            escalate = False
            if item.restricted_hit is not None:
                rh = item.restricted_hit
                safety.insert(0, f"{rh.active_ingredient} is {rh.tier}; do not use it.")
                escalate = True
            return Advisory(in_scope=False, query_understood=True, chemical_options=[],
                             likely_causes=[], non_chemical_first=[], safety=safety,
                             escalate_to_expert=escalate)

        # NOCHEM_LIKE
        safety = []
        if item.restricted_hit is not None:
            rh = item.restricted_hit
            safety.append(f"{rh.active_ingredient} is {rh.tier}; do not use it.")
        return Advisory(
            in_scope=True, query_understood=True,
            non_chemical_first=["Remove and destroy affected plants and nearby vector hosts.",
                                 "Use certified disease-free planting material."],
            chemical_options=[], safety=safety, escalate_to_expert=True)

    def _corrupt(self, adv: Advisory, item: GenItem) -> str:
        d = json.loads(adv.model_dump_json())
        if item.kind in CLARIFY_LIKE:
            d["clarifying_question"] = "Can you provide more details about the problem?"
        else:
            d.setdefault("chemical_options", [])
            d["chemical_options"].append({
                "active_ingredient": "Fakeicide 99% XX", "formulation": "Fakeicide 99% XX",
                "dose": {"basis": "per_acre", "value_min": 100.0, "value_max": None,
                         "unit": "g", "raw": "100 g/acre (FABRICATED - not in fact sheet)"},
                "spray_volume_min_l_per_acre": None, "spray_volume_max_l_per_acre": None,
                "phi_days": 7, "phi_not_applicable": False, "caution": "n/a",
            })
        return json.dumps(d, ensure_ascii=False)


# ==========================================================================
# 7. verification
# ==========================================================================

_BANNED_CLARIFY_PHRASES = {
    "can you provide more details about the problem",
    "can you provide more details",
    "can you give more details",
    "what symptoms do you see",
    "please provide more information",
    "can you describe the problem",
}


def _clarify_question_ok(q: Optional[str]) -> tuple[bool, str]:
    if not q or len(q.strip()) < 15:
        return False, "clarifying_question is missing or too short to be specific"
    low = re.sub(r"[?.!]", "", q.strip().lower())
    if low in _BANNED_CLARIFY_PHRASES:
        return False, f"clarifying_question {q!r} is a generic placeholder, not specific"
    return True, ""


def _free_text_dose_ok(item: GenItem, adv: Advisory) -> tuple[bool, str]:
    if not item.fact_rows:
        return True, ""
    raws_by_ai: dict[frozenset, set[str]] = {}
    for r in item.fact_rows:
        raws_by_ai.setdefault(r["_ai"], set()).add(r["dose_raw"] or "")
    for opt in adv.chemical_options:
        if opt.dose.basis != "free_text":
            continue
        comps = normalise_ai(opt.active_ingredient)
        candidates: set[str] = set()
        for ai_key, raws in raws_by_ai.items():
            if ai_key == comps:
                candidates |= raws
        if opt.dose.raw not in candidates:
            return False, (f"free_text dose.raw {opt.dose.raw!r} for "
                            f"{opt.active_ingredient!r} does not byte-match any "
                            f"fact-sheet dose_raw for that active ingredient")
    return True, ""


@dataclass
class ItemVerifyResult:
    passed: bool
    excluded: bool
    score: float
    failures: list[str]
    reason: str
    json_text: Optional[str]


def _c5_any_match_ok(ctx: VerifyContext, adv: Advisory) -> bool:
    """Fix 4: gold pest anywhere in likely_causes, not just position 0.

    A query naming several pests (e.g. "Jassid, Aphid, White Flies") gets ONE
    gold canonical from kcc_tagged's single-pest tagging (measured B3 run 2:
    S1_663 tagged 'Whitefly', S1_721 tagged 'girdle beetle'). A model that
    lists every pest the farmer named, in a different order than the tagger
    happened to pick, is substantively correct -- it addressed everything
    asked about. verify.py's C5_causes_top1 (frozen, not touched here) only
    checks position 0; this supplements it in the harness instead.
    """
    gold = ctx.pest_match()
    if not gold.matched or not adv.likely_causes:
        return False
    for lc in adv.likely_causes:
        m = match_pest(ctx.crop_slug, lc.name, ctx.table)
        if m.matched and m.canonical_name == gold.canonical_name:
            return True
    return False


def _patch_c5(ctx: VerifyContext, r, adv: Advisory) -> None:
    """Mutate one VerifyResult in place when C5 failed but Fix 4's any-match
    check passes. VerifyResult is not a frozen dataclass. Recomputes `total`
    with the frozen module's own CHECK_WEIGHTS (imported, not reimplemented)
    so the arithmetic can never drift from verify._result()'s.
    """
    if r.checks.get("C5_causes_top1") != 0.0:
        return
    if not _c5_any_match_ok(ctx, adv):
        return
    r.checks["C5_causes_top1"] = 1.0
    num = sum(CHECK_WEIGHTS[k] * v for k, v in r.checks.items() if k in CHECK_WEIGHTS)
    den = sum(CHECK_WEIGHTS[k] for k in r.checks if k in CHECK_WEIGHTS)
    r.total = round(num / den, 6) if den else 1.0
    r.failures = [f for f in r.failures if not f.startswith("C5:")]
    if r.gates and all(r.gates.values()) and r.total == 1.0:
        r.passed = True


def verify_item(resources: VerifyResources, item: GenItem, response_text: str) -> ItemVerifyResult:
    pest_queries = item.pest_queries or [""]
    ctxs = []
    results = []
    for pq in pest_queries:
        ctx = VerifyContext(resources, item.crop_slug, pest_query=pq,
                             application_method=item.application_method,
                             gold_escalate=item.gold_escalate)
        ctxs.append(ctx)
        results.append(verify(response_text, ctx, mode="gate"))

    for ctx, r in zip(ctxs, results):
        if r.advisory is not None:
            _patch_c5(ctx, r, r.advisory)

    passed = all(r.passed for r in results)
    excluded = any(r.excluded for r in results)
    score = min((r.total for r in results), default=0.0)
    failures: list[str] = []
    for r in results:
        failures.extend(r.failures)
    reason = "; ".join(r.exclusion_reason for r in results if r.exclusion_reason)

    adv = results[0].advisory if results else None
    if passed and adv is not None:
        # Only apply the clarify-question lexical guard when the model actually
        # attempted a genuine clarifying question (query_understood=False). An
        # item pre-classified CLARIFY_LIKE by our own imperfect is_offtopic_query()
        # heuristic can still correctly come back in_scope=False/query_understood=
        # True -- the model recognising an out-of-scope query on its own -- and
        # that shape must not be penalised by a check meant for a different one.
        if item.kind in CLARIFY_LIKE and not adv.query_understood:
            ok, msg = _clarify_question_ok(adv.clarifying_question)
            if not ok:
                passed = False
                failures.append(msg)
        else:
            ok, msg = _free_text_dose_ok(item, adv)
            if not ok:
                passed = False
                failures.append(msg)

    json_text = adv.model_dump_json() if (passed and adv is not None) else None
    return ItemVerifyResult(passed=passed, excluded=excluded, score=score,
                             failures=failures, reason=reason, json_text=json_text)


# ==========================================================================
# 8. orchestration
# ==========================================================================

def make_log_row(item: GenItem, attempts: int, score: float, reason: str) -> dict:
    return {"row_id": item.row_id, "slice": item.slice, "crop_slug": item.crop_slug,
            "canonical_pest": ";".join(c for c in item.canonicals if c),
            "attempts": attempts, "final_verify_score": round(float(score), 4),
            "outcome_reason": reason}


def run_pipeline(items: list[GenItem], backend: GenerationBackend,
                  resources: VerifyResources, max_attempts: int = MAX_ATTEMPTS,
                  max_tokens: int = 2000) -> tuple[dict[str, tuple[GenItem, str]], list[dict]]:
    pending: dict[str, GenItem] = {it.key(): it for it in items}
    for it in pending.values():
        it.attempt = 0
        it.prior_failures = []

    accepted: dict[str, tuple[GenItem, str]] = {}
    log_rows: dict[str, dict] = {}
    round_num = 0

    while pending and round_num < max_attempts:
        requests = [BatchRequest(custom_id=f"{key}_r{round_num}", system=SYSTEM_MESSAGE,
                                  user=build_user_message(it), max_tokens=max_tokens)
                    for key, it in pending.items()]
        responses = backend.generate(requests, pending)

        still_pending: dict[str, GenItem] = {}
        for key, it in pending.items():
            it.attempt = round_num + 1
            resp = responses.get(f"{key}_r{round_num}")
            if resp is None:
                it.prior_failures = ["no response from backend (API or parse error)"]
                if it.attempt < max_attempts:
                    still_pending[key] = it
                else:
                    log_rows[key] = make_log_row(it, it.attempt, 0.0,
                                                  "rejected_after_retries: no backend response")
                continue

            vr = verify_item(resources, it, resp)
            if vr.passed:
                accepted[key] = (it, vr.json_text)
                log_rows[key] = make_log_row(it, it.attempt, vr.score, "accepted")
            elif vr.excluded:
                log_rows[key] = make_log_row(it, it.attempt, vr.score, f"excluded: {vr.reason}")
            else:
                it.prior_failures = vr.failures
                if it.attempt < max_attempts:
                    still_pending[key] = it
                else:
                    summary = "; ".join(vr.failures[:3])
                    log_rows[key] = make_log_row(it, it.attempt, vr.score,
                                                  f"rejected_after_retries: {summary}")
        pending = still_pending
        round_num += 1

    for key, it in pending.items():
        log_rows[key] = make_log_row(it, it.attempt, 0.0,
                                      "rejected_after_retries: exhausted max_attempts")

    return accepted, list(log_rows.values())


def sample_items(items: list[GenItem], per_slice: int, seed: int) -> list[GenItem]:
    rng = random.Random(seed)
    by_slice: dict[int, list[GenItem]] = {}
    for it in items:
        by_slice.setdefault(it.slice, []).append(it)
    out = []
    for slice_n, group in by_slice.items():
        group = sorted(group, key=lambda x: x.row_id)
        out.extend(rng.sample(group, min(per_slice, len(group))))
    return out


# ==========================================================================
# 9. grape synthetic queries (slice 4)
# ==========================================================================

def build_grape_items(resources: VerifyResources, table: SynonymTable,
                       backend: GenerationBackend, style_pool: list[str],
                       target: int = GRAPE_TARGET, holdout: int = GRAPE_HOLDOUT,
                       seed: int = 42, per_writer_call: int = 20
                       ) -> tuple[list[GenItem], list[str], list[dict]]:
    targets = scope.TARGETS["grape"]
    per_target = target // len(targets)
    remainder = target - per_target * len(targets)

    requests = []
    canon_by_id: dict[str, str] = {}  # custom_id -> canonical (never embed the name
                                       # itself in custom_id: Anthropic's batch API
                                       # requires custom_id to match ^[a-zA-Z0-9_-]{1,64}$
                                       # and several grape canonicals have spaces, e.g.
                                       # "Downy mildew", "Powdery mildew" -- measured via
                                       # a real 400 invalid_request_error on the first
                                       # full-run attempt, 2026-09-03.
    rng = random.Random(seed)
    for i, t in enumerate(targets):
        n = per_target + (1 if i < remainder else 0)
        calls_needed = (n + per_writer_call - 1) // per_writer_call
        remaining = n
        for c in range(calls_needed):
            take = min(per_writer_call, remaining)
            remaining -= take
            custom_id = f"QW_grape_{i}_{c}_{take}"
            samples = rng.sample(style_pool, min(15, len(style_pool)))
            system, user = build_query_writer_prompt("grape", t["canonical"], t["type"],
                                                       samples, take)
            requests.append(BatchRequest(custom_id=custom_id, system=system, user=user,
                                          max_tokens=1500))
            canon_by_id[custom_id] = t["canonical"]

    responses = backend.generate(requests, None)
    queries: list[tuple[str, str]] = []  # (query_text, canonical)
    for req in requests:
        canon = canon_by_id[req.custom_id]
        for q in _parse_query_writer_response(responses.get(req.custom_id)):
            queries.append((q, canon))

    rng.shuffle(queries)
    holdout_queries = queries[:holdout]
    train_queries = queries[holdout:target]

    items, prelog = [], []
    for i, (q, canon) in enumerate(train_queries):
        row_id = f"grape{i:04d}"
        method = extract_method(q)
        fact_rows = label_db_fact_rows(resources, "grape", canon, method)
        if not fact_rows:
            prelog.append(_prefilter_log(row_id, 4, "grape", canon,
                                          "no gradeable label_db rows for synthetic grape target"))
            continue
        mp = match_pest("grape", canon, table)
        surface = mp.matched_surface_form if mp.matched else canon
        items.append(GenItem(slice=4, kind=Kind.DOSE, row_id=row_id, split="train",
                              crop_slug="grape", query_text=q, pest_queries=[surface],
                              canonicals=[canon], application_method=method,
                              gold_escalate=None, fact_rows=fact_rows))
    return items, [q for q, _ in holdout_queries], prelog


# ==========================================================================
# 10. output writers
# ==========================================================================

def _advisory_record(it: GenItem, json_text: str) -> dict:
    return {"id": it.key(),
            "messages": [
                {"role": "system", "content": DEPLOYMENT_SYSTEM_PROMPT},
                {"role": "user", "content": it.query_text},
                {"role": "assistant", "content": json_text},
            ]}


def _write_jsonl_records(path: Path, records: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for obj in records:
            fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def write_jsonl(path: Path, records: list[tuple[GenItem, str]]) -> None:
    _write_jsonl_records(path, [_advisory_record(it, json_text) for it, json_text in records])


LOG_CSV_FIELDNAMES = ["row_id", "slice", "crop_slug", "canonical_pest", "attempts",
                       "final_verify_score", "outcome_reason"]


def write_log_csv(path: Path, rows: list[dict]) -> None:
    import csv
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LOG_CSV_FIELDNAMES)
        w.writeheader()
        for r in sorted(rows, key=lambda r: (int(r["slice"]), str(r["row_id"]))):
            w.writerow(r)


# ==========================================================================
# 10b. checkpoint / resume (Slice 2 / GroqBackend: a ~4hr rate-limited run
# must survive interruption without re-spending quota on finished rows)
# ==========================================================================

def load_checkpoint(log_path: Path) -> tuple[set[tuple[str, str]], list[dict]]:
    """Read a prior sft_generation_log.csv, if any.

    Returns (skip_keys, prior_rows). skip_keys is every (slice, row_id) whose
    outcome_reason is "accepted" or "rejected_after_retries: ..." -- both are
    final verdicts a retry cannot change (rejected already exhausted
    max_attempts). "excluded: ..." is deliberately NOT included here, even
    though run_pipeline() also never retries an excluded item within a
    single run: exclusion is evaluated against the SPECIFIC chemical option
    the model chose (verify.py's C1_dose/C2_phi ambiguity check runs per
    ChemicalOption), so a different backend or a different sampled response
    could plausibly pick a non-ambiguous option on a later attempt. Skipping
    only accepted/rejected matches this feature's brief exactly; prior_rows
    (every row from the old log, including excluded ones) is carried forward
    into the merged output regardless, so nothing already recorded is lost
    even for the rows that DO get re-attempted.
    """
    if not log_path.exists():
        return set(), []
    import csv
    skip_keys: set[tuple[str, str]] = set()
    prior_rows: list[dict] = []
    with open(log_path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            prior_rows.append(r)
            reason = r.get("outcome_reason", "")
            if reason == "accepted" or reason.startswith("rejected_after_retries"):
                skip_keys.add((str(r["slice"]), str(r["row_id"])))
    return skip_keys, prior_rows


def load_prior_records(out_dir: Path) -> tuple[list[dict], list[dict]]:
    """Read existing sft_train.jsonl / sft_test.jsonl (if any) as raw dicts,
    to be merged with newly-accepted records on a resumed run. Each line is
    already a complete {"id", "messages"} record -- no GenItem reconstruction
    needed, just pass-through.
    """
    def _read(path: Path) -> list[dict]:
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]
    return _read(out_dir / "sft_train.jsonl"), _read(out_dir / "sft_test.jsonl")


def write_holdout(path: Path, queries: list[str]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for q in queries:
            fh.write(json.dumps({"crop_slug": "grape", "query_text": q}, ensure_ascii=False) + "\n")


# ==========================================================================
# 11. CLI
# ==========================================================================

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--mode", choices=["dry-run", "live"], default="dry-run",
                     help="legacy alias for --backend: dry-run -> mock, live -> anthropic-batch. "
                          "Ignored if --backend is given explicitly.")
    ap.add_argument("--backend", choices=["mock", "anthropic-batch", "anthropic-live", "groq"],
                     default=None,
                     help="mock: MockBackend, sampled items, no API calls (dry-run behaviour). "
                          "anthropic-batch: real Anthropic Message Batches run over the full "
                          "planned item set, gate loop identical either way. anthropic-live: "
                          "synchronous one-request-per-item calls, no batch queue -- for "
                          "smoke-testing a handful of items, not the production run. "
                          "groq: sequential, rate-limited calls to Groq's OpenAI-compatible "
                          "API -- for Slice 2. Overrides --mode.")
    ap.add_argument("--slices", default="1,2,3,4,5",
                     help="comma-separated slice numbers to build (still computes full "
                          "partition counts regardless)")
    ap.add_argument("--sample-per-slice", type=int, default=12,
                     help="mock backend only: cap generated items per slice")
    ap.add_argument("--max-attempts", type=int, default=MAX_ATTEMPTS)
    ap.add_argument("--structured-output", dest="structured_output", action="store_true",
                     default=False,
                     help="JSON-schema-constrained output. PENDING Fix B live validation -- "
                          "see reports/phase8_stepB1_fixB_structured_output_validation.md")
    ap.add_argument("--no-structured-output", dest="structured_output", action="store_false",
                     help="disable structured output, fall back to free-text JSON + the "
                          "output_contract prompt instructions.")
    ap.add_argument("--model", default=None,
                     help="generator model id. Backend-specific default when omitted: "
                          f"{GENERATOR_MODEL!r} for anthropic-batch/anthropic-live, "
                          f"{GROQ_DEFAULT_MODEL!r} for groq. Ignored by mock.")
    ap.add_argument("--poll-seconds", type=int, default=DEFAULT_POLL_SECONDS,
                     help="anthropic-batch only: seconds between batch status polls")
    ap.add_argument("--groq-api-key", default=None,
                     help="groq backend only: alternative to the GROQ_API_KEY env var "
                          "(some Kaggle setups make env vars awkward)")
    ap.add_argument("--resume", action="store_true",
                     help="skip items whose (slice, row_id) is already 'accepted' or "
                          "'rejected_after_retries' in --out-dir/sft_generation_log.csv, "
                          "and merge outputs with the prior run instead of overwriting. "
                          "For long rate-limited runs (groq/Slice 2) that may be "
                          "interrupted. Off by default -- a bare re-run still fully "
                          "regenerates, e.g. after a prompt change.")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR_DEFAULT)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--grape-target", type=int, default=GRAPE_TARGET)
    ap.add_argument("--grape-holdout", type=int, default=GRAPE_HOLDOUT)
    ap.add_argument("--cutoff", default=CUTOFF_DATE)
    args = ap.parse_args()

    backend_name = args.backend if args.backend is not None else (
        "mock" if args.mode == "dry-run" else "anthropic-batch")
    is_dry_run = backend_name == "mock"

    wanted_slices = {int(s) for s in args.slices.split(",") if s.strip()}

    resume_skip_keys: set[tuple[str, str]] = set()
    resume_prior_log_rows: list[dict] = []
    resume_prior_train: list[dict] = []
    resume_prior_test: list[dict] = []
    if args.resume:
        resume_skip_keys, resume_prior_log_rows = load_checkpoint(
            args.out_dir / "sft_generation_log.csv")
        resume_prior_train, resume_prior_test = load_prior_records(args.out_dir)
        print(f"[resume] {args.out_dir / 'sft_generation_log.csv'}: "
              f"{len(resume_skip_keys)} accepted/rejected rows to skip, "
              f"{len(resume_prior_log_rows)} prior log rows, "
              f"{len(resume_prior_train) + len(resume_prior_test)} prior accepted records "
              f"will be carried forward")

    print(f"[1/6] loading kcc_tagged.parquet and label_db resources ...")
    kcc = load_kcc()
    kcc = assign_slices(kcc)

    counts = kcc["slice"].value_counts().to_dict()
    print(f"  slice partition (full corpus, mutually exclusive, E-first):")
    for s, label in [(1, "dose"), (2, "clarify"), (3, "refusal"), (5, "no-chemistry")]:
        print(f"    slice {s} ({label}): {counts.get(s, 0)}")
    print(f"    slice 0 (unhandled, should be 0): {counts.get(0, 0)}")
    total_partitioned = sum(counts.get(s, 0) for s in (1, 2, 3, 5))
    assert total_partitioned == len(kcc), (
        f"partition invariant broken: {total_partitioned} != {len(kcc)}")
    print(f"    sum(1,2,3,5) == len(kcc_tagged): {total_partitioned} == {len(kcc)} OK")
    print(f"  NOTE: slice 5 prints {counts.get(5, 0)} here, not the 152 named in the sub-"
          f"phase brief -- 2 rows are both banned and NO_REGISTERED_CHEMISTRY and are kept "
          f"in slice 3 only (E-first), matching the design doc's own dataset-shape table. "
          f"See module docstring point 1.")
    print(f"  slice 4 (grape synthetic) is planned separately, target={args.grape_target}, "
          f"holdout={args.grape_holdout} -> {args.grape_target - args.grape_holdout} train")

    resources = VerifyResources.load()
    table = resources.table

    print(f"[2/6] date split at {args.cutoff} ...")
    train_df, test_df, dropped = split_kcc(kcc, args.cutoff)
    print(f"  train rows: {len(train_df)}, test rows: {len(test_df)} "
          f"(dropped {dropped} cross-boundary exact-text repeats)")

    print(f"[3/6] building generation items ...")
    items: list[GenItem] = []
    prelog: list[dict] = []
    if wanted_slices & {1, 2, 3, 5}:
        tr_items, tr_pre = build_items_for_df(train_df, "train", resources, table)
        te_items, te_pre = build_items_for_df(test_df, "test", resources, table)
        items += [it for it in tr_items if it.slice in wanted_slices]
        items += [it for it in te_items if it.slice in wanted_slices]
        prelog += tr_pre + te_pre
    print(f"  built {len(items)} items across slices {sorted(wanted_slices & {1,2,3,5})}, "
          f"{len(prelog)} rows pre-filtered before generation")

    holdout_queries: list[str] = []
    if 4 in wanted_slices:
        print(f"[3b/6] planning grape synthetic queries (target={args.grape_target}) ...")
        style_pool = train_df["QueryText"].dropna().astype(str).tolist()
        mock_writer = MockBackend(seed=args.seed)  # query-writer phase always uses the
                                                    # configured backend below; mock only
                                                    # here when backend=mock (see branch)
        writer_backend = mock_writer if is_dry_run else _build_backend(args)
        grape_items, holdout_queries, grape_pre = build_grape_items(
            resources, table, writer_backend, style_pool,
            target=args.grape_target, holdout=args.grape_holdout, seed=args.seed)
        items += grape_items
        prelog += grape_pre
        print(f"  {len(grape_items)} grape train items planned, "
              f"{len(holdout_queries)} held out for the future Phase 9 benchmark")

    if resume_skip_keys:
        pre_resume_n = len(items)
        items = [it for it in items if (str(it.slice), str(it.row_id)) not in resume_skip_keys]
        print(f"  resume: skipping {pre_resume_n - len(items)} already-accepted/rejected "
              f"items, {len(items)} remain to attempt")

    if is_dry_run:
        pre_sample_n = len(items)
        items = sample_items(items, args.sample_per_slice, args.seed)
        print(f"  dry-run: sampled {len(items)} of {pre_sample_n} planned items "
              f"(<= {args.sample_per_slice} per slice) for the mock verify loop")

    print(f"[4/6] selecting backend (backend={backend_name}) ...")
    backend = MockBackend(seed=args.seed) if is_dry_run else _build_backend(args)
    print(f"  backend: {type(backend).__name__}")

    print(f"[5/6] running generation + verify() gate loop (max_attempts={args.max_attempts}) ...")
    accepted, gen_log = run_pipeline(items, backend, resources, max_attempts=args.max_attempts)
    all_log = prelog + gen_log

    print(f"  accepted: {len(accepted)} / attempted: {len(items)}")
    outcome_counts: dict[str, int] = {}
    for r in all_log:
        key = r["outcome_reason"].split(":", 1)[0]
        outcome_counts[key] = outcome_counts.get(key, 0) + 1
    for k, v in sorted(outcome_counts.items()):
        print(f"    {k}: {v}")

    print(f"[6/6] writing outputs to {args.out_dir} ...")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    new_train = [_advisory_record(it, txt) for it, txt in accepted.values() if it.split == "train"]
    new_test = [_advisory_record(it, txt) for it, txt in accepted.values() if it.split == "test"]

    if args.resume:
        # Key-merge, not concatenation: a row re-attempted this run (e.g. a
        # previously-excluded row that a retry now accepts) must REPLACE its
        # stale prior log entry, not sit duplicated alongside it. Accepted
        # JSONL records need no such merge -- resume_skip_keys already kept
        # every previously-accepted id out of `items`, so new_train/new_test
        # and resume_prior_train/test can never share an id.
        merged_log = {(str(r["slice"]), str(r["row_id"])): r for r in resume_prior_log_rows}
        for r in all_log:
            merged_log[(str(r["slice"]), str(r["row_id"]))] = r
        final_log = list(merged_log.values())
        final_train = resume_prior_train + new_train
        final_test = resume_prior_test + new_test
    else:
        final_log = all_log
        final_train = new_train
        final_test = new_test

    _write_jsonl_records(args.out_dir / "sft_train.jsonl", final_train)
    _write_jsonl_records(args.out_dir / "sft_test.jsonl", final_test)
    write_log_csv(args.out_dir / "sft_generation_log.csv", final_log)
    if holdout_queries:
        write_holdout(REPO_ROOT / "data" / "interim" / "grape_benchmark_holdout.jsonl",
                       holdout_queries)
    print(f"  sft_train.jsonl: {len(final_train)} records"
          f"{f' ({len(new_train)} new)' if args.resume else ''}")
    print(f"  sft_test.jsonl: {len(final_test)} records"
          f"{f' ({len(new_test)} new)' if args.resume else ''}")
    print(f"  sft_generation_log.csv: {len(final_log)} rows")
    if is_dry_run:
        print(f"\n  This was a DRY RUN with mock responses. No API calls were made. "
              f"Re-run with --backend anthropic-batch once a real batch call has been smoke-tested.")


def _build_backend(args) -> GenerationBackend:
    backend_name = args.backend if args.backend is not None else (
        "mock" if args.mode == "dry-run" else "anthropic-batch")
    if backend_name == "groq":
        model = args.model or GROQ_DEFAULT_MODEL
        return GroqBackend(model=model, api_key=args.groq_api_key)
    # --model default is backend-specific (None until resolved here) so a
    # groq run's default never leaks into an Anthropic run and vice versa --
    # see the --model help text.
    model = args.model or GENERATOR_MODEL
    if backend_name == "anthropic-live":
        return AnthropicLiveBackend(model=model, structured_output=args.structured_output)
    return AnthropicBatchBackend(model=model, structured_output=args.structured_output,
                                  poll_seconds=args.poll_seconds)


if __name__ == "__main__":
    main()
