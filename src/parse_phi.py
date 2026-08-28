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
default). A unit this parser does NOT know how to convert (`year(s)`,
`hour(s)`/`hr(s)`) — or a cell mixing two different convertible units at
once, which number goes with which unit — raises `PHIParseError` rather than
guessing. That is the "or fail loudly to quarantine" half of the contract:
Phase 3 must catch this and route the row to quarantine, never fall through
to a bare `int(raw)` on the digits it can see.
"""

from __future__ import annotations

import re

# Casefolded, dot-stripped tokens that mean "the label prints no PHI number".
# Never add '0' or '00' here — those are the exact values this module exists
# to keep distinct from "unknown".
_NULLISH = {"", "-", "--", "na", "n/a", "nil", "none", "not applicable"}

_NUM = re.compile(r"\d+(?:\.\d+)?")

# Recognised units, singular, -> multiplier to days.
_UNIT_DAYS = {"day": 1, "week": 7, "month": 30}

# Recognised as time units but explicitly not converted — a genuinely
# unresolvable cell, not an ordinary word like "seed" or "spray" that just
# happens to appear in the same cell.
_UNSUPPORTED_UNITS = {"year", "hour"}

_UNIT_WORD_RE = re.compile(
    r"\b(days?|weeks?|months?|years?|hours?|hrs?)\b", re.IGNORECASE
)

_SINGULARISE = {"hrs": "hour", "hr": "hour"}


def _singular(word: str) -> str:
    w = word.lower()
    if w in _SINGULARISE:
        return _SINGULARISE[w]
    return w[:-1] if w.endswith("s") else w


class PHIParseError(ValueError):
    """Raised when a PHI cell has a number but its time unit can't be safely
    resolved to days — an unsupported unit (years, hours), or two different
    convertible units in the same cell with no way to tell which number each
    belongs to. Callers must quarantine the row, never fall back to the bare
    digit.
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
            farmer safe if only one is read. A recognised non-day unit
            (week/month) converts to days before that max is taken.
        None: the cell is blank or a placeholder ('-', 'NA', 'N/A', 'nil',
            'none', 'not applicable'). Callers must not coerce this to 0.

    Raises:
        PHIParseError: the cell contains a number and a time-unit word this
            parser does not convert (year/hour), or two different
            convertible units at once. Never silently falls back to treating
            the number as already-days in either case.
    """
    s = str(raw or "").replace("\n", " ").strip()
    key = s.casefold().replace(".", "")
    if key in _NULLISH:
        return None

    units = {_singular(m) for m in _UNIT_WORD_RE.findall(s)}

    if units & _UNSUPPORTED_UNITS:
        raise PHIParseError(
            f"PHI cell {s!r} uses a time unit this parser does not convert "
            f"(year/hour) — quarantine, do not take the digit as days."
        )

    factors = {_UNIT_DAYS[u] for u in units if u in _UNIT_DAYS}
    if len(factors) > 1:
        raise PHIParseError(
            f"PHI cell {s!r} mixes more than one convertible time unit — "
            f"cannot tell which number belongs to which unit."
        )
    factor = factors.pop() if factors else 1

    nums = [float(m) for m in _NUM.findall(s.replace("–", "-").replace("—", "-"))]
    if not nums:
        return None
    return int(max(nums) * factor)


__all__ = ["parse_phi", "PHIParseError"]
