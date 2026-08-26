"""
test_phi_parse.py — pins the PHI-cell parsing contract ahead of Phase 3.

Motivated by reports/phase2b_full_audit.md: the CIB&RC "Waiting Period
(days)" column mixes a genuine zero-day interval with placeholder tokens
that mean "the label prints no number" ('-', 'N/A'). The two must never
collapse into each other — src/schema.py's `ChemicalOption.phi_days` doc and
`Advisory._invariants` (which requires `escalate_to_expert=True` exactly
when `phi_days is None`) both depend on that distinction holding.

    pytest tests/test_phi_parse.py -q
"""

from parse_phi import parse_phi


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
