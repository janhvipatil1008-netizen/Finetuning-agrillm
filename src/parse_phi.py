"""parse_phi.py — one narrowly-scoped utility: a raw CIB&RC PHI cell -> Optional[int].

This is NOT the Phase 3 extraction pipeline (no camelot, no table iteration,
no writes to data/final/). It is a single pure function, written and pinned
by tests ahead of Phase 3, because the phase2b full-file audit
(reports/phase2b_full_audit.md) exists specifically to catch the bug this
function must not have.

The "Waiting Period (days)" / PHI column mixes two things that look similar
in a spreadsheet but mean opposite things for safety:

  * a genuine zero-day interval — the label itself prints '0' (confirmed:
    fungicides_20260331.pdf p23, Polyoxin D Zinc Salt 5% SC, Grape / Powdery
    Mildew — see reports/phase2b_full_audit.md). The crop may be harvested
    the same day as application.
  * a placeholder meaning the label prints no number at all — '-', 'N/A',
    'NA', an empty cell.

src/schema.py (frozen, Act 2) already encodes why these must never collapse
into each other: `ChemicalOption.phi_days: Optional[int]`, and
`Advisory._invariants` raises unless `escalate_to_expert=True` whenever any
`phi_days is None`. A parser that maps '0' -> None manufactures an
unwarranted escalation; a parser that maps '-' / 'N/A' -> 0 does the opposite
and more dangerous thing: it tells a farmer the crop is safe to harvest today
when the label makes no such claim.

The failure mode this guards against is not hypothetical — it is the exact
shape of bug a caller reaches for first: `int(raw) if raw else None`, or
downstream code that narrows with `parsed or None`. Both silently turn a
parsed 0 into None because 0 is falsy in Python; neither raises; neither
shows up unless something explicitly checks a known zero case against `is
not None`.

Unit conversion (added Phase 3 pre-work)
-----------------------------------------
The column header everywhere in these files reads "(days)", but the header
is not load-bearing on every row: `insecticides_20260331.pdf` p94, the
Temephos 1% granules sub-table (public-health section), prints `'2 weeks'`
and `'4 weeks'` in the structural position of the waiting-period column. A
parser keyed only on `_NUM.findall` would read the digit and silently return
`2`/`4` — six and seven times too short. Recognised units convert to days
(`week(s)` x7, `month(s)` x30, `day(s)` x1 / no unit at all, the historical
default). A unit this parser does NOT know how to convert (`year(s)`) — or a
cell mixing two different convertible units at once, which number goes with
which unit — raises `PHIParseError` rather than guessing. That is the "or
fail loudly to quarantine" half of the contract: Phase 3 must catch this and
route the row to quarantine, never fall through to a bare `int(raw)` on the
digits it can see.

Phase 4 corrections (grounded in reports/phase4_phi_stepA_survey.md)
---------------------------------------------------------------------
The Phase 4 survey ran this module over all 228 distinct PHI cells in the
corpus and found four gaps. Each fix below is a strict extension: no input
that already parsed correctly changes its answer.

1. GLUED UNITS. `_UNIT_WORD_RE` used to require `\b` BEFORE the unit word.
   A word boundary needs a non-word character there, so when OCR glued the
   digit to the unit — `'3½-4months'`, verbatim from fungicides p19-20,
   the Metalaxyl WS/ES seed-treatment rows on maize, bajra, sorghum and
   mustard — the unit was invisible, the multiplier silently defaulted to 1,
   and the bare digit came back as days. `parse_phi('3½-4months …')` returned
   **4**. The label says four MONTHS: 120 days. That is the same class of
   silent 30x understatement this module's own docstring says it exists to
   prevent, guarded for `'2 weeks'` and missed for `'4months'`. The leading
   `\b` is now `(?<![A-Za-z])`, which still refuses to match inside a word
   ("Sunday" does not contain a unit) but accepts a digit immediately before.

2. VULGAR FRACTIONS. `'3½'` parsed as `3`. Fractions are now expanded to
   decimals before anything else looks at the string. Only U+00BD appears in
   this corpus; a quarter and three-quarters are handled too rather than
   waiting for the next document revision to introduce one silently.

3. CONTENT THAT IS NOT A PHI AT ALL. The column also holds ISI standard
   references (`'IS:6313-2001 (Part-2)'`), dilution volumes
   (`'Dilution in water- 500 liter/ha'`), residue limits, fumigant re-entry
   periods and application schedules. Every one of them used to return a
   confident integer — 6313, 500, 25 — because they contain digits. They now
   raise `PHIParseError` for quarantine. A cell with NO digits cannot produce
   a wrong number, so prose alone still returns None (see 4).

4. HOURS. `'12 hrs'` and `'24 hours'` used to raise. A sub-day interval is a
   real thing on fumigant labels, so hours now convert to days and round UP:
   a partial day of waiting is still a day the crop must not be harvested.
   `math.ceil`, floored at 1, so 12 hrs -> 1 and 48 hrs -> 2. Rounding DOWN
   here would produce a zero-day PHI out of a label that demands a wait,
   which is the dangerous direction.

Not-applicable vs unknown
--------------------------
33 seed-treatment rows, 10 "not required" rows and the numberless growth-stage
rows all mean "a pre-harvest interval does not apply to this row", which is
not the same as "we do not know it". `schema.ChemicalOption.phi_days` is
`Optional[int]` and cannot express the difference, so this function returns
None for all of them and the DISTINCTION IS THE CALLER'S TO RECORD —
label_db (Step 5) carries a `phi_not_applicable` flag alongside phi_days.
This module deliberately does not raise for that prose: it is not a defect,
it is a label that legitimately has no PHI to state.
"""

from __future__ import annotations

import math
import re

# Casefolded, dot-stripped tokens that mean "the label prints no PHI number".
# Never add '0' or '00' here — those are the exact values this module exists
# to keep distinct from "unknown".
_NULLISH = {"", "-", "--", "---", "----", "na", "n/a", "nil", "none",
            "not applicable"}

_NUM = re.compile(r"\d+(?:\.\d+)?")

# Recognised units, singular, -> multiplier to days. 'hour' is handled
# separately because it needs a ceiling, not a multiplier.
_UNIT_DAYS = {"day": 1, "week": 7, "month": 30}

# Recognised as a time unit but explicitly not converted — a genuinely
# unresolvable cell, not an ordinary word like "seed" or "spray" that just
# happens to appear in the same cell. ('hour' left this set in Phase 4.)
_UNSUPPORTED_UNITS = {"year"}

# NOTE the lookbehind rather than `\b`: a `\b` here would require a non-word
# character before the unit, which makes the unit in '4months' invisible.
# `(?<![A-Za-z])` still refuses to match inside a word — 'Sunday' does not
# register as a day — but accepts a digit glued directly to the unit.
_UNIT_WORD_RE = re.compile(
    r"(?<![A-Za-z])(days?|weeks?|months?|years?|hours?|hrs?)\b", re.IGNORECASE
)

_SINGULARISE = {"hrs": "hour", "hr": "hour"}

# Vulgar fractions -> decimal tails. '3½' means three and a half, so the
# expansion appends to the preceding digit; a bare '½' becomes '0.5'.
_FRACTIONS = {"½": "5", "¼": "25", "¾": "75"}
_FRACTION_CLASS = "[" + "".join(_FRACTIONS) + "]"
_FRAC_AFTER_DIGIT = re.compile(r"(\d)\s*(" + _FRACTION_CLASS + ")")
_FRAC_BARE = re.compile(_FRACTION_CLASS)

# Content that is not a waiting period at all. Each of these was returning a
# confident integer before Phase 4; the message says what the cell really is
# so a quarantine reviewer does not have to re-derive it.
_NOT_A_PHI = (
    ("an ISI standard reference", re.compile(r"\bIS\s*:\s*\d")),
    ("a dilution volume",
     re.compile(r"dilution\s+in\s+water|\blit(?:re|er)?s?\s*(?:per|/)\s*ha\b",
                re.IGNORECASE)),
    ("a dose / treatment-method sentence",
     re.compile(r"\bkg\s+seed\b|\bseed\s+tubers?\s+of\b", re.IGNORECASE)),
    ("a residue limit",
     re.compile(r"\bresidues?\b", re.IGNORECASE)),
    ("a fumigant re-entry or aeration period",
     re.compile(r"\bre-?\s*entry\b|\baeration\b|detector\s+strips",
                re.IGNORECASE)),
    ("a growth stage or application schedule",
     re.compile(r"%\s*emergence|\bearhead\b|\bdusting\b|\bpetal\s*fall\b"
                r"|\bbuds?\s+swell\b|\bapplications?\b", re.IGNORECASE)),
)

# Two or more bare numbers with nothing joining them: adjacent table columns
# merged into this cell during extraction. '0 7' is not a 7-day PHI.
_COLLAPSED_COLUMNS = re.compile(r"^\d+(?:\s+\d+)+$")


def _singular(word: str) -> str:
    w = word.lower()
    if w in _SINGULARISE:
        return _SINGULARISE[w]
    return w[:-1] if w.endswith("s") else w


def _expand_fractions(s: str) -> str:
    s = _FRAC_AFTER_DIGIT.sub(lambda m: f"{m.group(1)}.{_FRACTIONS[m.group(2)]}", s)
    return _FRAC_BARE.sub(lambda m: f"0.{_FRACTIONS[m.group(0)]}", s)


class PHIParseError(ValueError):
    """Raised when a PHI cell cannot be safely resolved to a number of days.

    Three causes, all of which must route the row to quarantine rather than
    fall back to the bare digits the cell happens to contain:

      * an unsupported time unit (years), or two different convertible units
        in the same cell with no way to tell which number belongs to which;
      * content that is not a waiting period at all — an ISI standard
        reference, a dilution volume, a residue limit, a fumigant re-entry
        period, a growth stage or an application schedule;
      * adjacent columns merged into the cell during extraction ('0 7').
    """


def parse_phi(raw: object) -> "int | None":
    """Parse one CIB&RC 'Waiting Period (days)' cell.

    Args:
        raw: the cell as returned by camelot (a string; possibly containing
            a wrapped-cell newline, a dash range, or a placeholder token).

    Returns:
        int: a genuine PHI in days. A printed range ("20-30") or compound
            waiting period ("20+7", seen on co-formulation rows) resolves to
            the LARGER figure — the same safety-first policy schema.py
            documents for `Dose`/`Advisory`: when a label prints more than
            one number, the answer used downstream is the one that keeps the
            farmer safe if only one is read. Note this is the OPPOSITE
            direction to a dose range, which resolves to its lower bound, and
            for the same reason: more waiting and less chemical are both the
            safe side. A recognised non-day unit (week/month) converts to
            days before that max is taken; hours convert and round up.
        None: the cell is blank, a placeholder ('-', 'NA', 'N/A', 'nil',
            'none', 'not applicable'), or prose carrying no number at all —
            seed-treatment and "not required" wording, and growth-stage
            phrases like 'Delayed dormant spray'. Callers must not coerce
            this to 0. Callers that need to tell "no PHI applies" apart from
            "PHI unknown" record that themselves; see the module docstring.

    Raises:
        PHIParseError: see that class. Never silently falls back to treating
            a number it can see as already-days.
    """
    s = str(raw or "").replace("\n", " ").strip()
    key = s.casefold().replace(".", "")
    if key in _NULLISH:
        return None

    s = _expand_fractions(s)

    # A cell with no digits cannot yield a wrong number. Everything in this
    # branch is prose that legitimately states no interval — seed treatment,
    # "waiting not required", 'At whit bud, Petal fall'. Checked BEFORE the
    # not-a-PHI patterns below so that numberless growth-stage wording
    # returns None instead of being quarantined: there is nothing to get
    # wrong, and quarantining it would bury 33 seed-treatment rows.
    if not _NUM.search(s):
        return None

    for description, pattern in _NOT_A_PHI:
        if pattern.search(s):
            raise PHIParseError(
                f"PHI cell {s!r} is {description}, not a waiting period — "
                f"quarantine, do not take its digits as days."
            )

    if _COLLAPSED_COLUMNS.match(s):
        raise PHIParseError(
            f"PHI cell {s!r} holds two or more unjoined numbers — adjacent "
            f"columns merged during extraction. Quarantine; picking one "
            f"would be a guess."
        )

    units = {_singular(m) for m in _UNIT_WORD_RE.findall(s)}

    if units & _UNSUPPORTED_UNITS:
        raise PHIParseError(
            f"PHI cell {s!r} uses a time unit this parser does not convert "
            f"(year) — quarantine, do not take the digit as days."
        )

    if len(units) > 1:
        raise PHIParseError(
            f"PHI cell {s!r} mixes more than one convertible time unit — "
            f"cannot tell which number belongs to which unit."
        )

    nums = [float(m) for m in _NUM.findall(s.replace("–", "-").replace("—", "-"))]
    if not nums:
        return None
    biggest = max(nums)

    if units == {"hour"}:
        # Round UP: a partial day of waiting is still a day on which the crop
        # must not be harvested. Rounding down would manufacture a zero-day
        # PHI from a label that demands a wait.
        return max(1, math.ceil(biggest / 24))

    factor = _UNIT_DAYS[units.pop()] if units else 1
    return int(biggest * factor)


__all__ = ["parse_phi", "PHIParseError"]
