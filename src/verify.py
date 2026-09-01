"""verify.py — score a model advisory against label_db.

ONE implementation, three modes. The alternative — a training filter, an eval
scorer and an inference gate written separately — guarantees they drift, and
the day they drift is the day a chemical the training filter rejected reaches
a farmer because the inference gate spelled a check differently.

    gate    training-data filter. Passes only on total == 1.0.
    score   evaluation. Partial credit over the graded checks.
    filter  inference. G1-G8 plus C1 (dose) and C2 (PHI), at zero tolerance:
            a blocking check scoring below 1.0 blocks the answer.

Gates are absolute: any gate failure sets total to 0.0 in every mode. Graded
checks move the score and never rescue a gate.


WHY FILTER MODE IS NOT GATES-ONLY
==================================

It was, and that was wrong. Gates catch banned molecules, unregistered
crop/pest/chemical triples and malformed output — but every dose and PHI
comparison lives in the graded tier, so a gates-only filter passed a 3x
overdose, a basis relabel and a wrong pre-harvest interval. That inverts the
priority: filter mode is the inference-time safety net, and the reason it
exists is that a fine-tuned 4B will occasionally emit a wrong dose no matter
how well it trains.

So C1 and C2 are BLOCKING in filter mode (`FILTER_BLOCKING_CHECKS`), scored
pass/fail with no partial credit. C3-C6 stay eval-only: a missing
non-chemical option or a wrong formulation string is a quality miss, not a
hazard. Cost is a dataframe lookup that already happened; speed was never
the constraint.


G3 AND G6 ARE CURRENTLY UNREACHABLE, AND KEPT ANYWAY
=====================================================

`Advisory._invariants` in the frozen schema rejects all three shapes these
gates exist to catch — out-of-scope-with-options, ununderstood-with-options,
and unknown-PHI-without-escalation — so G2 fails first and `verify()` returns
before G3 or G6 can run. They are retained as defence against a future
relaxation of those invariants, and because a generation path that bypasses
pydantic would need them. tests/test_verify.py pins the rejection at the
pydantic layer instead, which is where it currently happens.


WHY UNCERTAINTY IS AN EXCLUSION, NOT LENIENCY
==============================================

When ground truth is shaky — a row flagged `flag_pest_bled`, a multi-crop
split, a pest cell that is a known-damaged fragment — the item is DROPPED
(`excluded=True`), not softened. Loosening a check because label_db is
unsure is how a verifier learns to approve things it cannot actually check.
Dropping costs a training example; softening costs the guarantee.


THE ARITHMETIC THAT KILLS PEOPLE
=================================

Three places where the obvious implementation is the dangerous one, each
pinned by a test:

1. A point dose is not an open-ended range. 433 of the 612 rows carrying a
   per-acre value have a min and NO max. Deciding "is this a range?" on
   `value_min is not None` turns every one of them into `[min, inf)` and lets
   a 3x overdose score CORRECT. C1 branches on `value_max`.

2. `phi_days == 0` is a real same-day-harvest interval; `phi_days is None` is
   "we do not know". Truthiness collapses them. Every PHI comparison here is
   an explicit `is None` test.

3. `phi_not_applicable` is True on 16 rows where the label POSITIVELY states
   no interval applies (seed dressers). Those are complete answers. The other
   184 `not_applicable` rows print '-' / blank / 'Nil' and are genuinely
   unknown. G6 forces escalation on the second group only.


READING THE PARQUET IS NOT A PREFERENCE
========================================

`phi_days` survives as nullable Int64 in parquet and degrades to float64
through CSV, where None becomes NaN and the 0-vs-None distinction that
parse_phi.py exists to preserve is gone. `load_label_db` refuses a .csv path.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Literal, Optional

import pandas as pd
from pydantic import ValidationError

import scope
from formulation_resolver import CODE_CLASS
from pest_matcher import (
    MatchResult,
    SynonymTable,
    load_table,
    match_all,
    match_pest,
)
from restricted_ai import RestrictedAI, load_restricted_ai
from schema import Advisory

# The ban list is loaded HERE, at import. Its absence raises
# MissingBanListError and makes this module un-importable, deliberately: see
# restricted_ai.py. Do not wrap this in a try/except.
RESTRICTED_AI: RestrictedAI = load_restricted_ai()

__all__ = [
    "Answerability",
    "LabelDB",
    "Mode",
    "VerifyContext",
    "VerifyResources",
    "VerifyResult",
    "CHECK_WEIGHTS",
    "DOSE_TOLERANCE",
    "FILTER_BLOCKING_CHECKS",
    "GATE_NAMES",
    "TRAINABLE_BRANCHES",
    "expected_answerable",
    "load_label_db",
    "normalise_ai",
    "verify",
]

Mode = Literal["gate", "score", "filter"]

# reports/phase6_stepA_verifier_design.md section 7. Tolerance exists to
# accept field rounding (404.7 -> 400), nothing else. It widens a POINT dose
# only; a printed range is authorised end to end and needs no widening.
DOSE_TOLERANCE = 0.05

# dose_parser.ParseResult.ok, as a column predicate.
TRAINABLE_BRANCHES: frozenset[str] = frozenset({"numeric", "free_text"})

# Bases that denote an area and so convert between ha and acre. Any other
# pair of bases must match exactly.
_AREA_BASES: frozenset[str] = frozenset({"per_ha", "per_acre"})

# Scale to a base unit so 1.5 kg and 1500 g compare equal. Mass and volume
# stay separate: g vs ml is a real error, not a unit spelling.
_UNIT_SCALE: dict[str, tuple[float, str]] = {
    "g": (1.0, "mass"), "kg": (1000.0, "mass"),
    "ml": (1.0, "volume"), "l": (1000.0, "volume"),
    "%": (1.0, "percent"),
}

GATE_NAMES = (
    "G1_json", "G2_schema", "G3_empty_when_not_answering", "G4_restricted_ai",
    "G5_triple_registered", "G6_unknown_phi_escalates", "G7_trainable_row",
    "G8_dose_basis", "G9_unstated_dose_earned",
)

# Graded checks. Weights apply only to checks that were APPLICABLE on this
# item; inapplicable ones leave the denominator rather than scoring zero, so a
# model is never punished for a gap in label_db (design section 2).
CHECK_WEIGHTS: dict[str, float] = {
    "C1_dose": 0.30,
    "C2_phi": 0.25,
    "C3_formulation": 0.10,
    "C4_escalation": 0.15,
    "C5_causes_top1": 0.10,
    "C6_non_chemical": 0.10,
}
# Reported for eval, never weighted: a diagnostic beside C5_causes_top1.
UNWEIGHTED_CHECKS = ("C5_causes_top3",)

# Checks that BLOCK in filter mode, scored pass/fail with no partial credit.
# Dose and PHI are the two numbers that hurt a farmer if they are wrong; the
# rest are quality. A check absent from `checks` (no numeric ground truth on
# the matched row) cannot block — there is nothing to have got wrong.
FILTER_BLOCKING_CHECKS = ("C1_dose", "C2_phi")


class Answerability(Enum):
    OUT_OF_SCOPE_CROP = "OUT_OF_SCOPE_CROP"
    PEST_UNKNOWN = "PEST_UNKNOWN"
    NO_REGISTERED_CHEMISTRY = "NO_REGISTERED_CHEMISTRY"
    ANSWERABLE = "ANSWERABLE"


# --------------------------------------------------------------------------
# active-ingredient normalisation
# --------------------------------------------------------------------------

def normalise_ai(name: Optional[str]) -> frozenset[str]:
    """'Imidacloprid 17.8% SL' -> {'imidacloprid'}; a mixture keeps both parts.

    Set equality, not string equality: the model says "Imidacloprid" and
    label_db says "Imidacloprid 17.8% SL". A co-formulation matches only if
    the model names every component — half of a mixture is a different
    registered product with a different dose.
    """
    out: set[str] = set()
    for part in re.split(r"\+", str(name or "")):
        head = re.split(r"\s*\d", part, maxsplit=1)[0]
        head = re.sub(r"[^A-Za-z\- ]", " ", head)
        head = re.sub(r"\s+", " ", head).strip().lower()
        if head:
            out.add(head)
    return frozenset(out)


_CODE_RX = re.compile(
    r"(?<![A-Z])(" + "|".join(sorted(CODE_CLASS, key=len, reverse=True)) + r")(?![A-Z])"
)
_STRENGTH_RX = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def formulation_key(text: Optional[str]) -> tuple[Optional[str], Optional[float]]:
    """('Chlorantraniliprole 18.50% SC') -> ('SC', 18.5).

    Strength to one decimal so '18.5% SC' matches '18.50% SC' but not
    '35% WG' — a different product with a different label rate.
    """
    if not text:
        return None, None
    up = str(text).upper()
    codes = _CODE_RX.findall(up)
    code = codes[-1] if codes else None
    m = _STRENGTH_RX.search(up)
    strength = round(float(m.group(1)), 1) if m else None
    return code, strength


# --------------------------------------------------------------------------
# label_db
# --------------------------------------------------------------------------

def load_label_db(path: Path | str) -> pd.DataFrame:
    """Load label_db from parquet. Refuses a CSV path.

    Raises:
        ValueError: the path is not .parquet. `phi_days` degrades from
            nullable Int64 to float64 through CSV, turning None into NaN and
            collapsing it with a genuine 0 — the exact confusion parse_phi.py
            was written to prevent. A verifier reading that file would force
            escalation on a same-day-harvest label and accept an unknown one.
    """
    path = Path(path)
    if path.suffix.lower() != ".parquet":
        raise ValueError(
            f"label_db must be read from parquet, got {path.name!r}. "
            f"phi_days degrades from nullable Int64 to float64 through CSV, "
            f"which collapses the 0-vs-None distinction parse_phi.py exists "
            f"to preserve. Use data/final/label_db.parquet."
        )
    return pd.read_parquet(path)


@dataclass(frozen=True)
class _Row:
    """One label_db row, pre-resolved for lookup."""
    index: int
    crop_slug: str
    ai_components: frozenset[str]
    active_ingredient: str
    pest_surface_forms: tuple[str, ...]
    canonicals: frozenset[str]
    trainable: bool
    defective: bool
    biological: bool
    application_method: str


class LabelDB:
    """label_db plus the indexes the verifier joins on.

    Built once per process. Resolving every pest cell through `match_all`
    costs a pass over 740 rows and must not happen per item.
    """

    def __init__(self, df: pd.DataFrame, table: SynonymTable):
        self.df = df
        self.table = table
        self.rows: list[_Row] = []
        self._by_crop_pest: dict[tuple[str, str], list[int]] = {}
        self._by_triple: dict[tuple[str, str, frozenset[str]], list[int]] = {}

        for i, r in df.iterrows():
            crop = str(r["crop_slug"])
            cell = r["pest_or_disease"]
            # 335 of 729 non-empty pest cells name more than one pest.
            results = [] if pd.isna(cell) else match_all(crop, cell, table)
            canon = frozenset(m.canonical_name for m in results if m.matched)
            surfaces = tuple(
                m.matched_surface_form or "" for m in results if m.matched)
            row = _Row(
                index=int(i),
                crop_slug=crop,
                ai_components=normalise_ai(r["active_ingredient"]),
                active_ingredient=str(r["active_ingredient"]),
                pest_surface_forms=surfaces,
                canonicals=canon,
                trainable=(
                    str(r["dose_ai_branch"]) in TRAINABLE_BRANCHES
                    and str(r["dose_formulation_branch"]) in TRAINABLE_BRANCHES
                ),
                defective=bool(r["flag_pest_bled"]) or bool(r["crop_multi_crop_split"]),
                biological=str(r["source_file"]).startswith("bio_"),
                application_method=str(r.get("application_method", "") or ""),
            )
            self.rows.append(row)
            for c in canon:
                self._by_crop_pest.setdefault((crop, c), []).append(row.index)
                self._by_triple.setdefault(
                    (crop, c, row.ai_components), []).append(row.index)

    def row(self, index: int) -> _Row:
        return self.rows[index]

    def for_pair(self, crop_slug: str, canonical: Optional[str]) -> list[_Row]:
        if not canonical:
            return []
        return [self.rows[i]
                for i in self._by_crop_pest.get((crop_slug, canonical), [])]

    def for_triple(self, crop_slug: str, canonical: Optional[str],
                   ai_components: frozenset[str]) -> list[_Row]:
        if not canonical:
            return []
        return [self.rows[i] for i in
                self._by_triple.get((crop_slug, canonical, ai_components), [])]

    def surface_forms_for(self, crop_slug: str, canonical: str) -> list[str]:
        """What CIB&RC actually prints for this pest, for failure messages."""
        seen: list[str] = []
        for r in self.for_pair(crop_slug, canonical):
            for s in r.pest_surface_forms:
                if s and s not in seen:
                    seen.append(s)
        return seen


def expected_answerable(crop_slug: str, pest_canonical: Optional[str],
                        label_db: LabelDB) -> Answerability:
    """The single source of truth for the refusal slice.

    Generation, verification and benchmark construction all call this, so
    "there is nothing registered for this" means one thing across the project
    instead of three subtly different things.

    ANSWERABLE iff at least one TRAINABLE row exists for the pair. A pair
    whose only rows are untrainable has ground truth too damaged to grade a
    dose against, so it is not answerable even though CIB&RC prints something.
    """
    if (crop_slug or "").strip().lower() not in scope.CROPS:
        return Answerability.OUT_OF_SCOPE_CROP
    if not pest_canonical:
        return Answerability.PEST_UNKNOWN
    rows = label_db.for_pair(crop_slug, pest_canonical)
    if any(r.trainable for r in rows):
        return Answerability.ANSWERABLE
    return Answerability.NO_REGISTERED_CHEMISTRY


# --------------------------------------------------------------------------
# context and result
# --------------------------------------------------------------------------

@dataclass
class VerifyResources:
    """Process-level, immutable, expensive. Build once with .load()."""
    label_db: LabelDB
    table: SynonymTable
    restricted: RestrictedAI

    @classmethod
    def load(cls, label_db_path: Path | str | None = None,
             synonym_table_path: Path | str | None = None) -> "VerifyResources":
        root = Path(__file__).resolve().parents[1]
        df = load_label_db(label_db_path
                           or root / "data" / "final" / "label_db.parquet")
        table = load_table(synonym_table_path) if synonym_table_path else load_table()
        return cls(label_db=LabelDB(df, table), table=table,
                   restricted=RESTRICTED_AI)


@dataclass
class VerifyContext:
    """Per-item: the question this output is answering, plus the resources."""
    resources: VerifyResources
    crop_slug: str
    pest_query: str                       # the farmer's surface form
    # Which application the farmer is asking about: 'soil_drench', 'foliar',
    # 'seed_treatment', 'nursery', or None. It narrows the candidate rows.
    #
    # It comes from the QUESTION, not the answer, because ChemicalOption has
    # no field to carry it and schema.py is frozen. Where the query does not
    # say, both a foliar and a drench claim stay in the candidate set and the
    # item resolves AMBIGUOUS -- which is the safe outcome, not a gap.
    application_method: Optional[str] = None
    gold_escalate: Optional[bool] = None  # override; else derived from label_db

    @property
    def table(self) -> SynonymTable:
        return self.resources.table

    @property
    def label_db(self) -> LabelDB:
        return self.resources.label_db

    def pest_match(self) -> MatchResult:
        return match_pest(self.crop_slug, self.pest_query, self.table)


@dataclass
class VerifyResult:
    passed: bool
    total: float
    gates: dict[str, bool]
    checks: dict[str, float]
    failures: list[str]
    # Additive beyond the stated contract: "drop the item" has to be
    # distinguishable from "the item failed", and there is no contract field
    # that can carry it. Defaults keep the five contract fields unchanged.
    excluded: bool = False
    exclusion_reason: str = ""
    # Checks that could not be graded because the candidate label_db rows
    # disagreed. Reported separately in score mode so ambiguous ground truth
    # -- our defect, not the model's -- neither depresses nor inflates the
    # metric. Never a check score of 0.0.
    ambiguous: list[str] = field(default_factory=list)
    answerability: Optional[Answerability] = None
    advisory: Optional[Advisory] = field(default=None, repr=False)


def _fail(failures: list[str], msg: str) -> None:
    failures.append(msg)


def _narrow_candidates(rows: list["_Row"], formulation: Optional[str],
                       application_method: Optional[str] = None) -> list["_Row"]:
    """Narrow the candidate rows. Returns the SURVIVORS, never one pick.

    Two narrowing stages, in order of how much they separate:

    1. APPLICATION METHOD. CIB&RC registers foliar and soil-drench use as
       separate claims — cotton/Jassids under Clothianidin 50% WDG is 30-40
       g/ha at PHI 20 foliar and 200-250 g/ha at PHI 76 as a drench, a 6x dose
       gap and 56 days. The method comes from the QUERY (what the farmer wants
       to do), not the answer: `ChemicalOption` has no field for it. See the
       note in VerifyContext.
    2. FORMULATION (design section 5, stage 3). Resolves 107 of the 142
       multi-row triples; 35 have rows sharing a code and strength.

    Each stage only narrows when it leaves something: a method that matches no
    candidate is not evidence that every candidate is wrong.
    """
    if len(rows) <= 1:
        return rows
    if application_method:
        hits = [r for r in rows if r.application_method == application_method]
        rows = hits or rows
    else:
        # An unqualified query cannot silently pick the unqualified row: a
        # farmer who did not say "soil drench" may still mean one.
        pass
    if len(rows) <= 1 or not formulation:
        return rows
    want = formulation_key(formulation)
    if want == (None, None):
        return rows
    hits = [r for r in rows if formulation_key(r.active_ingredient) == want]
    return hits or rows


AMBIGUOUS = "AMBIGUOUS"


def _consensus(verdicts: list[Optional[bool]]):
    """Fold per-candidate verdicts into one answer, or report ambiguity.

    An answer consistent with EVERY candidate is correct — the candidates
    disagree about which product was meant, not about whether this answer is
    right, so there is nothing to be ambiguous about. An answer consistent
    with NONE is wrong under every reading, and ambiguity must not rescue it.
    Only a mixture is genuinely ungradeable.

    Returns True, False, AMBIGUOUS, or None when no candidate had ground
    truth to compare against.
    """
    vs = [v for v in verdicts if v is not None]
    if not vs:
        return None
    if all(vs):
        return True
    if not any(vs):
        return False
    return AMBIGUOUS


def _result(gates, checks, failures, mode, excluded=False, reason="",
            answerability=None, advisory=None,
            ambiguous=None) -> VerifyResult:
    """Fold gates, checks and ambiguity into one verdict.

    AMBIGUOUS resolves differently in each mode, deliberately:

        gate    EXCLUDE. Ground truth too ambiguous to grade against must not
                become a training example — but an exclusion is not a failure
                and the two must stay distinguishable.
        score   Leave it out of the metric and report the count. The
                ambiguity is a defect in our ground truth, not in the answer.
        filter  BLOCK. "I cannot determine the correct interval for this
                recommendation" is exactly when a farmer should not get it.
    """
    ambiguous = sorted(set(ambiguous or ()))
    gates_ok = all(gates.values())
    blocked = [k for k in FILTER_BLOCKING_CHECKS if checks.get(k, 1.0) < 1.0]

    if ambiguous and not excluded:
        if mode == "gate":
            excluded = True
            reason = reason or (
                "ambiguous ground truth: " + ", ".join(ambiguous) +
                " — the CIB&RC rows this answer could refer to disagree")
        elif mode == "filter":
            blocked = blocked + ambiguous

    if not gates_ok:
        total = 0.0
    elif mode == "filter":
        total = 0.0 if blocked else 1.0
    else:
        num = sum(CHECK_WEIGHTS[k] * v for k, v in checks.items()
                  if k in CHECK_WEIGHTS)
        den = sum(CHECK_WEIGHTS[k] for k in checks if k in CHECK_WEIGHTS)
        total = (num / den) if den else 1.0

    if mode == "gate":
        passed = gates_ok and total == 1.0
    elif mode == "filter":
        passed = gates_ok and not blocked
    else:
        passed = gates_ok
    if excluded:
        passed = False
    return VerifyResult(passed=passed, total=round(total, 6), gates=gates,
                        checks=checks, failures=failures, excluded=excluded,
                        exclusion_reason=reason, answerability=answerability,
                        advisory=advisory, ambiguous=ambiguous)


# --------------------------------------------------------------------------
# dose comparison
# --------------------------------------------------------------------------

def _to_base(value: Optional[float], unit: Optional[str]):
    if value is None or unit is None:
        return None, None
    scale, dim = _UNIT_SCALE.get(unit, (None, None))
    if scale is None:
        return None, None
    return float(value) * scale, dim


def _basis_compatible(model_basis: str, label_basis: str) -> bool:
    if model_basis == label_basis:
        return True
    return model_basis in _AREA_BASES and label_basis in _AREA_BASES


def _label_dose_bounds(df_row: pd.Series, model_basis: str):
    """Return (lo, hi, unit) in the basis the model used.

    hi is None for a POINT dose. That is the distinction C1 turns on, and it
    comes from `value_max`/`per_acre_max` — never from whether min is set.
    """
    if model_basis == "per_acre":
        lo = df_row["dose_formulation_per_acre_min"]
        hi = df_row["dose_formulation_per_acre_max"]
    else:
        lo = df_row["dose_formulation_value_min"]
        hi = df_row["dose_formulation_value_max"]
    unit = df_row["dose_formulation_unit"] or None
    lo = None if pd.isna(lo) else float(lo)
    hi = None if pd.isna(hi) else float(hi)
    return lo, hi, unit


def _dose_value_ok(pred: float, lo: float, hi: Optional[float]) -> bool:
    """hi is None -> POINT dose, tolerance band. hi set -> RANGE, containment.

    The range arm never touches a midpoint: the label authorises the whole
    interval, and scoring against its centre would reject the label's own
    endpoints.
    """
    if hi is None:
        return abs(pred - lo) / lo <= DOSE_TOLERANCE if lo else pred == lo
    return lo <= pred <= hi


# --------------------------------------------------------------------------
# the verifier
# --------------------------------------------------------------------------

def verify(output: str, ctx: VerifyContext,
           mode: Mode = "score") -> VerifyResult:
    """Score one model output. See the module docstring for the three modes."""
    gates: dict[str, bool] = {}
    checks: dict[str, float] = {}
    failures: list[str] = []

    # ---- G1: parses as JSON -------------------------------------------
    try:
        payload = json.loads(output) if isinstance(output, str) else output
        gates["G1_json"] = True
    except (json.JSONDecodeError, TypeError) as e:
        gates["G1_json"] = False
        _fail(failures, f"G1: output is not JSON ({e})")
        return _result(gates, checks, failures, mode)

    # ---- G2: validates against Advisory --------------------------------
    try:
        adv = Advisory.model_validate(payload)
        gates["G2_schema"] = True
    except ValidationError as e:
        gates["G2_schema"] = False
        _fail(failures, f"G2: does not validate against Advisory — "
                        f"{e.error_count()} error(s): "
                        f"{'; '.join(x['msg'] for x in e.errors()[:3])}")
        return _result(gates, checks, failures, mode)

    gold = ctx.pest_match()
    answerability = expected_answerable(
        ctx.crop_slug, gold.canonical_name, ctx.label_db)

    # ---- exclusion: shaky ground truth is dropped, never softened ------
    if gold.matched_surface_form is not None and not gold.matched:
        return _result(gates, checks, failures, mode, excluded=True,
                       reason=(f"pest {ctx.pest_query!r} is a known-damaged "
                               f"label_db fragment ({gold.notes})"),
                       answerability=answerability, advisory=adv)
    gold_rows = ctx.label_db.for_pair(ctx.crop_slug, gold.canonical_name)
    if gold_rows and all(r.defective for r in gold_rows):
        return _result(gates, checks, failures, mode, excluded=True,
                       reason=(f"every label_db row for {ctx.pest_query!r} on "
                               f"{ctx.crop_slug} carries an extraction defect"),
                       answerability=answerability, advisory=adv)

    # ---- G3: not answering means recommending nothing -------------------
    # UNREACHABLE while Advisory._invariants stands: it rejects both shapes,
    # so G2 fails first and this never runs. Kept as defence against a future
    # relaxation of those invariants, and for any path that bypasses pydantic.
    not_answering = (not adv.in_scope) or (not adv.query_understood)
    gates["G3_empty_when_not_answering"] = (
        not not_answering) or not adv.chemical_options
    if not gates["G3_empty_when_not_answering"]:
        why = "in_scope=False" if not adv.in_scope else "query_understood=False"
        _fail(failures, f"G3: {why} but {len(adv.chemical_options)} chemical "
                        f"option(s) recommended")

    options = adv.chemical_options
    matched: list[tuple[Any, list[_Row]]] = []
    ambiguous: list[str] = []

    # ---- G4: restricted active ingredients ------------------------------
    g4 = True
    for opt in options:
        comps = normalise_ai(opt.active_ingredient)
        hits = ctx.resources.restricted.check(comps, ctx.crop_slug)
        for h in hits:
            g4 = False
            _fail(failures,
                  f"G4: recommended {opt.active_ingredient!r} — {h.describe()}")
    gates["G4_restricted_ai"] = g4

    # ---- G5: the (crop, pest, a.i.) triple is registered -----------------
    g5 = True
    for opt in options:
        comps = normalise_ai(opt.active_ingredient)
        rows = ctx.label_db.for_triple(ctx.crop_slug, gold.canonical_name, comps)
        if rows:
            matched.append((opt, _narrow_candidates(
                rows, opt.formulation, ctx.application_method)))
            continue
        g5 = False
        matched.append((opt, []))
        on_crop = any(comps == r.ai_components
                      for r in ctx.label_db.rows if r.crop_slug == ctx.crop_slug)
        printed = ctx.label_db.surface_forms_for(
            ctx.crop_slug, gold.canonical_name or "")
        if on_crop:
            # The dangerous shape: real chemical, real crop, wrong target.
            _fail(failures,
                  f"G5: {opt.active_ingredient!r} is registered on "
                  f"{ctx.crop_slug} but not for {ctx.pest_query!r}"
                  + (f" (CIB&RC prints {printed[:3]} for that pest)"
                     if printed else ""))
        else:
            _fail(failures,
                  f"G5: no CIB&RC claim for {opt.active_ingredient!r} on "
                  f"{ctx.crop_slug} / {ctx.pest_query!r}")
    gates["G5_triple_registered"] = g5

    # ---- G6: an unknown PHI forces escalation ---------------------------
    # Verifies the model's phi_not_applicable claim in BOTH directions. Where
    # the candidates disagree about whether an interval applies, the claim is
    # ungradeable rather than wrong: recorded as ambiguous, not failed.
    g6 = True
    for opt, rows in matched:
        na_states = {bool(ctx.label_db.df.at[r.index, "phi_not_applicable"])
                     for r in rows}
        if len(na_states) > 1:
            ambiguous.append("G6_phi_applicability")
            _fail(failures,
                  f"AMBIGUOUS: {opt.active_ingredient!r} matches "
                  f"{len(rows)} CIB&RC rows that disagree on whether a "
                  f"pre-harvest interval applies — cannot grade the claim")
            continue
        positively_na = bool(na_states.pop()) if na_states else False

        if opt.phi_not_applicable and rows and not positively_na:
            g6 = False
            _fail(failures,
                  f"G6: claimed no pre-harvest interval applies to "
                  f"{opt.active_ingredient!r}, but CIB&RC does not say that "
                  f"(phi_raw={ctx.label_db.df.at[rows[0].index, 'phi_raw']!r}) "
                  f"— the interval is unknown, not absent")
            continue
        if not opt.phi_not_applicable and positively_na and opt.phi_days is None:
            g6 = False
            _fail(failures,
                  f"G6: CIB&RC states no interval applies to "
                  f"{opt.active_ingredient!r} "
                  f"(phi_raw={ctx.label_db.df.at[rows[0].index, 'phi_raw']!r}), "
                  f"but the answer leaves it unknown instead of saying so")
            continue

        if opt.phi_days is not None:      # never truthiness: 0 is a real value
            continue
        if opt.phi_not_applicable:
            continue                       # complete answer, no escalation owed
        if not adv.escalate_to_expert:
            g6 = False
            _fail(failures,
                  f"G6: phi_days is unknown for {opt.active_ingredient!r} and "
                  f"the label does not state that no interval applies, but "
                  f"escalate_to_expert is False")
    gates["G6_unknown_phi_escalates"] = g6

    # ---- G7: the referenced row is in the trainable set ------------------
    g7 = True
    for opt, rows in matched:
        if rows and not any(r.trainable for r in rows):
            g7 = False
            _fail(failures,
                  f"G7: the CIB&RC row for {opt.active_ingredient!r} on "
                  f"{ctx.crop_slug} / {ctx.pest_query!r} is outside the "
                  f"trainable set (its dose cell did not parse)")
    gates["G7_trainable_row"] = g7

    # ---- G8: dose basis. A right number on the wrong basis is worse -----
    # than a wrong number, so this gates rather than grading (C1 spec).
    g8 = True
    for opt, rows in matched:
        verdicts = []
        for r in rows:
            label_basis = str(
                ctx.label_db.df.at[r.index, "dose_formulation_basis"])
            verdicts.append(None if not label_basis
                            else _basis_compatible(opt.dose.basis, label_basis))
        got = _consensus(verdicts)
        if got is AMBIGUOUS:
            ambiguous.append("G8_dose_basis")
            _fail(failures,
                  f"AMBIGUOUS: {opt.active_ingredient!r} matches CIB&RC rows "
                  f"stating the dose on different bases — cannot grade "
                  f"{opt.dose.basis}")
        elif got is False:
            g8 = False
            bases = sorted({str(ctx.label_db.df.at[r.index,
                                                   "dose_formulation_basis"])
                            for r in rows})
            _fail(failures,
                  f"G8: {opt.active_ingredient!r} dose stated "
                  f"{opt.dose.basis} but CIB&RC states it {'/'.join(bases)}")
    gates["G8_dose_basis"] = g8

    # ---- G9: a dose basis of 'unstated' has to be earned ----------------
    # 'unstated' is the schema's refuse-to-guess shape, added 2026-09-01. It
    # is legitimate only where label_db genuinely has no parseable product
    # dose (42 rows). Claiming it on a row that DOES carry a dose is a
    # refusal to answer something answerable -- the failure mode a
    # refuse-to-guess affordance invites, so it gates rather than grades.
    g9 = True
    for opt, rows in matched:
        if opt.dose.basis != "unstated":
            continue
        if not adv.escalate_to_expert:
            g9 = False
            _fail(failures,
                  f"G9: {opt.active_ingredient!r} has an unstated dose but "
                  f"escalate_to_expert is False")
        verdicts = [str(ctx.label_db.df.at[r.index, "dose_formulation_branch"])
                    not in TRAINABLE_BRANCHES for r in rows]
        got = _consensus(verdicts)
        if got is AMBIGUOUS:
            ambiguous.append("G9_unstated_dose_earned")
            _fail(failures,
                  f"AMBIGUOUS: some CIB&RC rows for "
                  f"{opt.active_ingredient!r} carry a dose and some do not — "
                  f"cannot grade an 'unstated' claim")
        elif got is False:
            g9 = False
            _fail(failures,
                  f"G9: {opt.active_ingredient!r} dose declared 'unstated', "
                  f"but CIB&RC gives one — "
                  f"{ctx.label_db.df.at[rows[0].index, 'dose_formulation_raw']!r}. "
                  f"Refusing an answerable question.")
    gates["G9_unstated_dose_earned"] = g9

    # ================= graded checks ====================================
    # C1 and C2 run in EVERY mode: they are the blocking pair at inference
    # (FILTER_BLOCKING_CHECKS), not merely graded.
    _check_dose(ctx, matched, checks, failures, ambiguous)
    _check_phi(ctx, matched, checks, failures, ambiguous)

    if mode == "filter":
        return _result(gates, checks, failures, mode,
                       answerability=answerability, advisory=adv,
                       ambiguous=ambiguous)

    _check_formulation(ctx, matched, checks, failures)
    _check_escalation(ctx, adv, matched, answerability, checks, failures)
    _check_causes(ctx, adv, gold, checks, failures)
    _check_non_chemical(ctx, adv, gold, answerability, checks, failures)

    return _result(gates, checks, failures, mode,
                   answerability=answerability, advisory=adv,
                   ambiguous=ambiguous)


# --------------------------------------------------------------------------
# graded checks
# --------------------------------------------------------------------------

def _check_dose(ctx, matched, checks, failures, ambiguous) -> None:
    """C1 — (value, unit, basis) as a triple. Basis already gated by G8."""
    scored: list[float] = []
    for opt, rows in matched:
        verdicts: list[Optional[bool]] = []
        for row in rows:
            r = ctx.label_db.df.loc[row.index]
            lo, hi, label_unit = _label_dose_bounds(r, opt.dose.basis)
            if lo is None or label_unit is None:
                verdicts.append(None)
                continue
            pred_lo, pred_dim = _to_base(opt.dose.value_min, opt.dose.unit)
            label_lo, label_dim = _to_base(lo, label_unit)
            label_hi, _ = _to_base(hi, label_unit)
            if pred_lo is None or label_lo is None:
                verdicts.append(None)
                continue
            if pred_dim != label_dim:
                verdicts.append(False)
                continue
            ok = _dose_value_ok(pred_lo, label_lo, label_hi)
            # A model range must sit inside the authorisation at both ends.
            if ok and opt.dose.value_max is not None:
                pred_hi, _ = _to_base(opt.dose.value_max, opt.dose.unit)
                ok = pred_hi is not None and _dose_value_ok(
                    pred_hi, label_lo, label_hi)
            verdicts.append(ok)

        got = _consensus(verdicts)
        if got is None:
            continue                       # no numeric ground truth: unscored
        if got is AMBIGUOUS:
            ambiguous.append("C1_dose")
            bands = sorted({_band_text(ctx, r, opt.dose.basis) for r in rows})
            _fail(failures,
                  f"AMBIGUOUS: {opt.active_ingredient!r} dose "
                  f"{opt.dose.value_min}{opt.dose.unit} matches some but not "
                  f"all of the CIB&RC rows it could refer to "
                  f"({'; '.join(bands)}) — ground truth cannot grade it")
            continue
        scored.append(1.0 if got else 0.0)
        if not got:
            bands = sorted({_band_text(ctx, r, opt.dose.basis) for r in rows})
            _fail(failures,
                  f"C1: {opt.active_ingredient!r} dose {opt.dose.value_min}"
                  f"{opt.dose.unit} {opt.dose.basis}; CIB&RC states "
                  f"{'; '.join(bands)}")
    if scored:
        checks["C1_dose"] = sum(scored) / len(scored)


def _band_text(ctx, row, basis) -> str:
    r = ctx.label_db.df.loc[row.index]
    lo, hi, unit = _label_dose_bounds(r, basis)
    if lo is None:
        return "no parseable dose"
    shape = f"{lo}" if hi is None else f"{lo}-{hi}"
    return f"{shape} {unit} ({r['dose_formulation_raw']!r})"


def _check_phi(ctx, matched, checks, failures, ambiguous) -> None:
    """C2 — exact match, no tolerance. 0 and None stay distinct."""
    scored: list[float] = []
    for opt, rows in matched:
        verdicts: list[Optional[bool]] = []
        for row in rows:
            raw = ctx.label_db.df.at[row.index, "phi_days"]
            label_phi = None if pd.isna(raw) else int(raw)
            pred = opt.phi_days
            if label_phi is None and pred is None:
                verdicts.append(True)
            elif label_phi is None:
                verdicts.append(None)      # unknown ground truth
            else:
                verdicts.append(pred is not None and int(pred) == label_phi)

        got = _consensus(verdicts)
        if got is None:
            continue
        phis = sorted({str(ctx.label_db.df.at[r.index, "phi_days"])
                       for r in rows})
        if got is AMBIGUOUS:
            ambiguous.append("C2_phi")
            _fail(failures,
                  f"AMBIGUOUS: {opt.active_ingredient!r} pre-harvest interval "
                  f"{opt.phi_days} matches some but not all of the CIB&RC "
                  f"rows it could refer to (they state {'/'.join(phis)} days) "
                  f"— ground truth cannot grade it")
            continue
        scored.append(1.0 if got else 0.0)
        if not got:
            shown = "None (unknown)" if opt.phi_days is None else opt.phi_days
            _fail(failures,
                  f"C2: {opt.active_ingredient!r} pre-harvest interval "
                  f"{shown}, CIB&RC states {'/'.join(phis)} day(s)")
    if scored:
        checks["C2_phi"] = sum(scored) / len(scored)


def _check_formulation(ctx, matched, checks, failures) -> None:
    """C3 — the model's formulation string against the matched label rows.

    Any candidate matching is enough: the candidates ARE the rows the stated
    formulation could not distinguish, so it matches all of them or none.
    """
    scored: list[float] = []
    for opt, rows in matched:
        wants = [formulation_key(r.active_ingredient) for r in rows]
        wants = [w for w in wants if w != (None, None)]
        if not wants:
            continue
        got = formulation_key(opt.formulation)
        ok = got in wants
        scored.append(1.0 if ok else 0.0)
        if not ok:
            _fail(failures,
                  f"C3: {opt.active_ingredient!r} formulation "
                  f"{opt.formulation!r}; CIB&RC registers "
                  f"{sorted({r.active_ingredient for r in rows})}")
    if scored:
        checks["C3_formulation"] = sum(scored) / len(scored)


def _check_escalation(ctx, adv, matched, answerability, checks, failures) -> None:
    """C4 — both directions. Over-escalation is a failure, not a safe default.

    A model that escalates on everything never trips a safety gate and is
    useless; the score has to price that.
    """
    if ctx.gold_escalate is not None:
        gold = ctx.gold_escalate
    else:
        gold = False
        for opt, rows in matched:
            for row in rows:
                raw = ctx.label_db.df.at[row.index, "phi_days"]
                positively_na = bool(
                    ctx.label_db.df.at[row.index, "phi_not_applicable"])
                if pd.isna(raw) and not positively_na:
                    gold = True
        if answerability is Answerability.PEST_UNKNOWN:
            gold = True

    ok = (adv.escalate_to_expert == gold)
    checks["C4_escalation"] = 1.0 if ok else 0.0
    if not ok:
        if adv.escalate_to_expert:
            _fail(failures,
                  f"C4: escalated to an expert, but CIB&RC gives a complete "
                  f"answer for {ctx.pest_query!r} on {ctx.crop_slug} — "
                  f"over-escalation")
        else:
            _fail(failures,
                  f"C4: did not escalate, but the answer for "
                  f"{ctx.pest_query!r} on {ctx.crop_slug} needs it")


def _check_causes(ctx, adv, gold, checks, failures) -> None:
    """C5 — top-1 and top-3, compared on canonical, reported on surface."""
    if not adv.likely_causes or not gold.matched:
        return
    ranked = sorted(adv.likely_causes, key=lambda c: -c.confidence)
    resolved = [match_pest(ctx.crop_slug, c.name, ctx.table) for c in ranked]
    canon = [m.canonical_name for m in resolved]

    checks["C5_causes_top1"] = 1.0 if canon[:1] == [gold.canonical_name] else 0.0
    checks["C5_causes_top3"] = 1.0 if gold.canonical_name in canon[:3] else 0.0

    if checks["C5_causes_top1"] == 0.0:
        printed = ctx.label_db.surface_forms_for(
            ctx.crop_slug, gold.canonical_name)
        _fail(failures,
              f"C5: top cause {ranked[0].name!r}; the query was about "
              f"{ctx.pest_query!r}"
              + (f", which CIB&RC prints as {printed[:3]}" if printed else ""))


def _check_non_chemical(ctx, adv, gold, answerability, checks, failures) -> None:
    """C6 — an empty everything is not a correct refusal.

    Enforced where we have ground truth for it: when nothing is registered,
    and when CIB&RC itself lists a biological option for the pair.
    """
    must = answerability is Answerability.NO_REGISTERED_CHEMISTRY
    bio = any(r.biological
              for r in ctx.label_db.for_pair(ctx.crop_slug, gold.canonical_name))
    if not (must or bio):
        return                              # no ground truth: unscored
    ok = bool(adv.non_chemical_first)
    checks["C6_non_chemical"] = 1.0 if ok else 0.0
    if not ok:
        why = ("no chemical is registered for "
               f"{ctx.pest_query!r} on {ctx.crop_slug}" if must
               else f"CIB&RC lists a biological option for {ctx.pest_query!r}")
        _fail(failures, f"C6: non_chemical_first is empty, but {why}")
