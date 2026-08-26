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
"""

from __future__ import annotations

import re

# Casefolded, dot-stripped tokens that mean "the label prints no PHI number".
# Never add '0' or '00' here — those are the exact values this module exists
# to keep distinct from "unknown".
_NULLISH = {"", "-", "--", "na", "n/a", "nil", "none", "not applicable"}

_NUM = re.compile(r"\d+(?:\.\d+)?")


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
            farmer safe if only one is read.
        None: the cell is blank or a placeholder ('-', 'NA', 'N/A', 'nil',
            'none', 'not applicable'). Callers must not coerce this to 0.
    """
    s = str(raw or "").replace("\n", " ").strip()
    key = s.casefold().replace(".", "")
    if key in _NULLISH:
        return None

    nums = [float(m) for m in _NUM.findall(s.replace("–", "-").replace("—", "-"))]
    if not nums:
        return None
    return int(max(nums))


__all__ = ["parse_phi"]
