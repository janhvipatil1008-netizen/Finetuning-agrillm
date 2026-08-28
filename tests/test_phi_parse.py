"""
test_phi_parse.py — pins the PHI-cell parsing contract ahead of Phase 3.

Motivated by reports/phase2b_full_audit.md: the CIB&RC "Waiting Period
(days)" column mixes a genuine zero-day interval with placeholder tokens
that mean "the label prints no number" ('-', 'N/A'). The two must never
collapse into each other — src/schema.py's `ChemicalOption.phi_days` doc and
`Advisory._invariants` (which requires `escalate_to_expert=True` exactly
when `phi_days is None`) both depend on that distinction holding.

Also pins unit conversion, added as Phase 3 pre-work: the column header says
"(days)" but is not always true on the row. `insecticides_20260331.pdf` p94
(Temephos 1% granules, public-health section) prints `'2 weeks'` and
`'4 weeks'` in the waiting-period column position — a parser that only reads
the digit would return 2/4 instead of 14/28.

    pytest tests/test_phi_parse.py -q
"""

import pytest

from parse_phi import PHIParseError, parse_phi


def test_polyoxin_d_zero_phi_parses_to_int_zero():
    """fungicides_20260331.pdf p23, Polyoxin D Zinc Salt 5% SC, Grape /
    Powdery Mildew: the printed PHI cell is a bare '0' (verbatim in
    reports/phase2b_full_audit.md). A parser that treats a falsy-looking
    string as "missing" would return None here, silently forcing an
    unwarranted escalate_to_expert=True for a label that already answers
    the question.
    """
    assert parse_phi("0") == 0
    assert parse_phi("0") is not None


def test_placeholder_tokens_parse_to_none_not_zero():
    """'-' and 'N/A' mean the label prints no PHI at all. The opposite
    failure mode is worse than the first: a parser that maps these to 0
    would tell a farmer it is safe to harvest today, when the label makes
    no such claim.
    """
    assert parse_phi("-") is None
    assert parse_phi("N/A") is None


# --- unit conversion (Phase 3 pre-work) -------------------------------------

def test_weeks_convert_to_days():
    """'Not less than 21 weeks' is not a 21-day PHI — it is 147 days. A
    parser that only extracts the digit would silently understate this PHI
    by a factor of 7."""
    assert parse_phi("Not less than 21 weeks") == 147


def test_months_convert_to_days():
    assert parse_phi("3 months") == 90


def test_real_corpus_week_cells_convert():
    """insecticides_20260331.pdf p94, Temephos 1% granules: the waiting-period
    column literally contains '2 weeks' / '4 weeks' despite the column header
    reading '(days)'. Grounded in a real cell, not a hypothetical."""
    assert parse_phi("2 weeks") == 14
    assert parse_phi("4 weeks") == 28


def test_range_without_unit_takes_max_in_days():
    """'14-21' has no unit word at all — treated as already-days (the
    historical default), and the range resolves to the larger figure."""
    assert parse_phi("14-21") == 21


def test_unsupported_time_unit_raises_not_silently_parses():
    """A unit this parser cannot convert (year/hour) must never fall through
    to 'take the digit as days' — that would silently understate or overstate
    the PHI by whatever the true year/hour-to-day ratio is. Quarantine
    instead."""
    with pytest.raises(PHIParseError):
        parse_phi("5 years")
    with pytest.raises(PHIParseError):
        parse_phi("10 hours")
