"""retrieval.py -- Phase 12 Step 1: label_db retrieval for the RAG ablation.

The ablation holds everything fixed -- trained adapter, data/final/bench.jsonl,
verify.py -- and varies ONE thing: whether label_db rows are injected into the
user message. The Phase 8 generator already builds such a fact sheet (it is
what reached 93-95% acceptance), so this module reproduces that formatter
rather than designing a new one. A formatting difference between the two
would otherwise be a second variable in a one-variable experiment.

WHY THIS IS A COPY, NOT AN IMPORT
=================================

tools/generate_sft.py builds the fact sheet from `label_db_fact_rows()` plus
three inline lines inside `build_user_message()`. There is no standalone
formatter to import, and src/ must not depend on tools/. So the row-shaping
and serialisation code is copied here verbatim, generate_sft.py is left
untouched (it is the code that produced the training set), and
tests/test_retrieval.py pins the copy against the generator itself -- it
calls generate_sft.label_db_fact_rows and cuts the <fact_sheet> block out of
generate_sft.build_user_message, then asserts byte equality. If either side
drifts, that test fails.

Serialisation facts that byte-identity depends on: product dose only
(dose_formulation_*, never dose_ai_*); `_num` turns whole floats into ints;
one-line json.dumps with default separators and ensure_ascii=False; rows in
label_db index order; no pest name in any row (see the NOTE in
fact_rows_for_pair).

ABLATION-FAIRNESS DECISIONS
===========================

1. No <resolved_pest> by default. Phase 8 Fix A injected the tagger's
   canonical pest name at generation time so the generator would name the
   pest the tagger expected. That was a generation-time crutch; at inference
   the model only has the farmer's query. `build_rag_user_message` therefore
   takes `resolved_pest=None` and omits the block entirely when it is None.
   Passing a value exists only so a diagnostic run can measure the crutch
   separately; the ablation arms must not pass it.

2. No <restricted_ai> and no <task>. Both are generator instructions (a
   ban-list lookup result and the per-kind task text, which itself refers to
   <resolved_pest>). Neither exists at inference, so neither is emitted.

3. Retrieval-miss policy -- NEW TEXT, NOT PHASE 8 REUSE. An empty
   retrieval emits one of two lines inside <fact_sheet>, chosen by WHY it
   is empty (`format_fact_sheet(rows, miss_reason=...)`):

     MISS_NO_ROWS    crop AND pest resolved, zero rows survived the chain
                     -> "No registered chemistry found for this crop and
                         pest in CIB&RC."
     MISS_UNRESOLVED crop or pest did not resolve
                     -> "Retrieval could not identify a specific crop and
                         pest from this query. No fact sheet available."

   The split matters because MISS_NO_ROWS is a claim about CIB&RC, and it
   is true only when there was a key to look up. Emitting it for an
   unresolved key (every CLARIFY and OFFTOPIC item in Arm A -- 186 items --
   plus Arm B's resolution misses) feeds the model a false premise, and one
   that would suppress legitimate answers: "azadirachtin dosage in cotton"
   told "nothing is registered" is being lied to. There is no default: an
   empty `rows` without a `miss_reason` raises, so no caller can fall back
   to the CIB&RC claim by omission.

   Phase 8 had no miss line at all -- a DOSE item with no surviving rows was
   dropped before generation, and the closest wording is the slice-5 note in
   build_slice5_fact_sheet, which neither line reproduces -- so neither
   wording breaks byte-identity; the non-empty path is unchanged.

   This is still the one place the ablation number can be INFLATED: on
   NOCHEM / REFUSAL_NOCHEM items MISS_NO_ROWS tells the model the answer
   shape outright (chemical_options=[]). Report RAG-arm scores split by
   fact-sheet kind (rows / no_rows / unresolved) so the effect of each line
   is visible on its own.

CONFOUNDS THE ABLATION DOES NOT REMOVE
======================================

A. Oracle-keyed vs live retrieval.
   Arm A keys retrieval on the bench item's gold (crop_slug, canonical_pest).
   The rows returned are specific to that pest, so even with <resolved_pest>
   omitted the fact sheet leaks the pest identity (e.g. a sheet of
   bollworm-only chemistry tells the model it is a bollworm). Arm A is an
   upper bound on what retrieval can give. Arm B resolves the key from the
   query text alone via `resolve_key(query_text, resources, crop_hint=None)`;
   its misses and wrong resolutions are part of the measurement. Note that
   resolve_key follows the same steps as the Phase 7 tagger that produced
   the KCC gold labels (tools/phase7_stepD_kcc_quality_tags.py flag C), so
   on KCC-sourced bench items Arm B will agree with the gold key far more
   often than an independent resolver would -- Arm B measures "retrieval
   with this project's own resolver", not retrieval in general.

B. Input-shape novelty.
   The adapter was trained with the user turn set to the BARE query
   (generate_sft._advisory_record). It has never seen the
   <query crop="...">...</query> wrapper or a <fact_sheet> block. Any change
   in score between the no-RAG arm and either RAG arm is therefore
   confounded with the effect of the new input shape itself. Neither Arm A
   nor Arm B controls for this; an Arm C (same wrapper, empty or shuffled
   fact sheet) would, if run.
"""
from __future__ import annotations

import json
import re
from typing import Optional, Sequence, Union

import pandas as pd

import scope
from application_method import extract_method
from crop_mapper import map_crop
from pest_matcher import normalise_pest, match_pest
# Private, imported deliberately (as the Phase 7 tagger does): these are the
# head nouns and modifiers pest_matcher itself uses to recognise a pest
# phrase. Copying them would let them drift from the module they mirror.
from pest_matcher import _HEADS, _MODIFIERS
from verify import VerifyResources

__all__ = [
    "NO_CHEMISTRY_LINE",
    "UNRESOLVED_LINE",
    "MISS_NO_ROWS",
    "MISS_UNRESOLVED",
    "miss_reason_for",
    "resolve_key",
    "retrieve_rows",
    "format_fact_sheet",
    "build_rag_user_message",
]

MISS_NO_ROWS = "no_rows"
MISS_UNRESOLVED = "unresolved"
NO_CHEMISTRY_LINE = "No registered chemistry found for this crop and pest in CIB&RC."
UNRESOLVED_LINE = ("Retrieval could not identify a specific crop and pest from this "
                   "query. No fact sheet available.")
_MISS_LINES = {MISS_NO_ROWS: NO_CHEMISTRY_LINE, MISS_UNRESOLVED: UNRESOLVED_LINE}


def miss_reason_for(crop_slug: Optional[str], canonical_pest: Optional[str]) -> str:
    """Which miss line an empty retrieval on this key earns (decision 3)."""
    return MISS_NO_ROWS if crop_slug and canonical_pest else MISS_UNRESOLVED


# --------------------------------------------------------------------------
# row shaping -- verbatim copy of generate_sft.label_db_fact_rows and helpers
# --------------------------------------------------------------------------

def _num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
        return None
    f = float(v)
    return int(f) if f.is_integer() else f


def _str_or_none(v) -> Optional[str]:
    if v is None or pd.isna(v):
        return None
    return str(v)


def _public(d: dict) -> dict:
    return {k: v for k, v in d.items() if not k.startswith("_")}


def retrieve_rows(crop_slug: Optional[str], canonical_pest: Optional[str],
                  resources: VerifyResources,
                  application_method: Optional[str] = None) -> list[dict]:
    """Gradeable, trainable, ban-filtered label_db rows for (crop, pest).

    Same filter chain as generate_sft.label_db_fact_rows, in the same order:
    for_pair -> trainable -> not defective -> not contradicted -> not on the
    crop-scoped ban list -> application-method narrowing (falling back to the
    un-narrowed set when the method matches nothing). Globally that chain
    leaves 610 of 740 label_db rows.

    Returns [] when crop or pest is None or nothing survives -- never raises
    on a miss. Each dict carries a private '_ai' key exactly as the generator
    does; format_fact_sheet strips it.
    """
    if not crop_slug or not canonical_pest:
        return []
    rows = resources.label_db.for_pair(crop_slug, canonical_pest)
    rows = [r for r in rows if r.trainable and not r.defective and not r.contradiction]
    rows = [r for r in rows if not resources.restricted.check(r.ai_components, crop_slug)]
    if application_method:
        narrowed = [r for r in rows if r.application_method == application_method]
        rows = narrowed or rows  # a method matching nothing is not evidence every row is wrong
    df = resources.label_db.df
    out = []
    for r in rows:
        row = df.loc[r.index]
        # NOTE: no pest field -- r.pest_surface_forms is the row's FULL
        # multi-pest cell, not the surface form for canonical_pest. See the
        # matching note in generate_sft.label_db_fact_rows.
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


# --------------------------------------------------------------------------
# formatting
# --------------------------------------------------------------------------

def format_fact_sheet(rows: Sequence[dict], miss_reason: Optional[str] = None) -> str:
    """The <fact_sheet> block. Byte-identical to generate_sft for non-empty
    rows (miss_reason is ignored there). Empty rows REQUIRE miss_reason --
    MISS_NO_ROWS or MISS_UNRESOLVED, see module docstring decision 3 -- and
    raise ValueError without one."""
    if not rows:
        if miss_reason not in _MISS_LINES:
            raise ValueError(
                f"empty retrieval needs miss_reason in {sorted(_MISS_LINES)}, got "
                f"{miss_reason!r}; use miss_reason_for(crop, pest)")
        return f"<fact_sheet>\n{_MISS_LINES[miss_reason]}\n</fact_sheet>"
    pub = [_public(d) for d in rows]
    return f"<fact_sheet>\n{json.dumps(pub, ensure_ascii=False)}\n</fact_sheet>"


def build_rag_user_message(query_text: str, crop_slug: Optional[str],
                           rows: Sequence[dict],
                           resolved_pest: Union[None, str, Sequence[str]] = None,
                           miss_reason: Optional[str] = None) -> str:
    """User message in the Phase 8 shape, minus the generator-only blocks.

    Blocks, joined by a blank line as in generate_sft.build_user_message:
    <query crop="...">, then <resolved_pest> ONLY if resolved_pest is not None
    (ablation arms must leave it None -- decision 1), then <fact_sheet>.
    No <restricted_ai>, no <task> (decision 2). miss_reason is passed to
    format_fact_sheet and is required when rows is empty.

    crop_slug=None (Arm B could not resolve a crop) renders a bare <query>
    tag rather than inventing a crop attribute.
    """
    head = f'<query crop="{crop_slug}">' if crop_slug else "<query>"
    parts = [f"{head}\n{query_text}\n</query>"]
    if resolved_pest is not None:
        names = [resolved_pest] if isinstance(resolved_pest, str) else list(resolved_pest)
        parts.append("<resolved_pest>\n" + json.dumps(names, ensure_ascii=False) +
                     "\n</resolved_pest>")
    parts.append(format_fact_sheet(rows, miss_reason))
    return "\n\n".join(parts)


# --------------------------------------------------------------------------
# live key resolution (Arm B)
# --------------------------------------------------------------------------

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")

# Transliterated Marathi/Hindi keys of scope.SYNONYMS -- the same set the
# Phase 7 tagger's flag C step 2 uses (tools/phase7_stepD_kcc_quality_tags.py
# _LOCAL_PEST_TERMS). Kept in step so Arm B resolves what the tagger resolved.
_LOCAL_PEST_KEYS = frozenset({
    "gulabi bondhali", "pandhri mashi", "safed makkhi", "tudtude", "mava",
    "phulkide", "bhuri", "davnya", "karpa", "telya", "ghatee ali",
    "mar rog", "anar butterfly",
})
_LOCAL_PEST_TERMS = {k: v for k, v in scope.SYNONYMS.items() if k in _LOCAL_PEST_KEYS}


def _normalize(text: object) -> str:
    s = "" if not isinstance(text, str) else text
    s = _PUNCT_RE.sub(" ", s.lower())
    return _SPACE_RE.sub(" ", s).strip()


def _resolve_crop(query_text: str) -> Optional[str]:
    """Exactly one in-scope crop named -> that slug; none or several -> None."""
    slugs = {r.slug for r in map_crop(query_text) if r.slug}
    return next(iter(slugs)) if len(slugs) == 1 else None


def _resolve_pest(crop_slug: str, query_text: str, resources: VerifyResources) -> Optional[str]:
    """Phase 7 flag-C order: known surface form (longest first), then a local
    transliterated term, then the first head-noun pest phrase. Returns None
    rather than guessing when none of those resolves."""
    table = resources.table
    norm = _normalize(query_text)
    if not norm:
        return None

    for surface in sorted(table.surface_forms(crop_slug), key=len, reverse=True):
        ns = _normalize(surface)
        if ns and re.search(rf"\b{re.escape(ns)}\b", norm):
            r = match_pest(crop_slug, surface, table)
            if r.matched:
                return r.canonical_name

    for term, canonical in _LOCAL_PEST_TERMS.items():
        if re.search(rf"\b{re.escape(term)}\b", norm):
            return canonical

    words = norm.split()
    for i, w in enumerate(words):
        if w in _HEADS:
            phrase = f"{words[i - 1]} {w}" if i > 0 and words[i - 1] in _MODIFIERS else w
            r = match_pest(crop_slug, phrase, table)
            return r.canonical_name if r.matched else None
    return None


def resolve_key(query_text: str, resources: VerifyResources,
                crop_hint: Optional[str] = None
                ) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """(crop_slug, canonical_pest, application_method) from the query alone.

    crop_hint exists ONLY so Arm A can pass the bench item's crop_slug; when
    given it wins over whatever the text names. Arm B passes None and the
    crop comes from crop_mapper on the query text -- exactly one in-scope
    crop, or None. With no crop the pest is not looked up (pest resolution is
    keyed on (crop, pest), never pest alone), so the result is (None, None,
    method). Never raises; a miss flows through retrieve_rows as [] and,
    via miss_reason_for, into the UNRESOLVED_LINE fact sheet.
    """
    method = extract_method(query_text)
    crop = crop_hint or _resolve_crop(query_text)
    if not crop:
        return None, None, method
    return crop, _resolve_pest(crop, query_text, resources), method
