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
    """A unit this parser cannot convert (years) must never fall through to
    'take the digit as days' — that would silently understate the PHI by
    365x. Quarantine instead.

    Phase 4 note: this test used to assert the same for hours. Hours are now
    CONVERTED (see TestHoursConvertToDays below) because a sub-day interval
    is real on fumigant labels; years remain unconvertible because nothing in
    the corpus prints one and a 365x multiplier is not worth guessing at.
    """
    with pytest.raises(PHIParseError):
        parse_phi("5 years")


# ===========================================================================
# Phase 4 fixes. Every string below is verbatim from the corpus unless the
# test says otherwise; provenance is in reports/phase4_phi_stepA_survey.md.
# ===========================================================================


class TestGluedUnitRegression:
    """The Phase 4 survey's headline finding.

    `_UNIT_WORD_RE` required a word boundary before the unit, so OCR that
    glued the digit to the unit ('4months') hid the unit entirely, the
    multiplier defaulted to 1, and the bare digit came back as days. These
    cells are the whole population of the bug in this corpus:
    fungicides_20260331.pdf p19-20, the Metalaxyl WS/ES seed-treatment rows.

    Before the fix these returned 4, 4, 4 and 3 days. The labels say months.
    Telling a farmer to wait four DAYS when the label says four MONTHS is a
    30x understatement of a pre-harvest interval.
    """

    @pytest.mark.parametrize("raw,expected_days,crop", [
        ("3½-4months  Depending on  the variety", 120, "Maize"),
        ("3½-4months  Depending  on  the  variety", 120, "Sorghum"),
        ("3½-4months  Depending  on the  variety", 120, "Mustard"),
        ("3-3½months  Depending  on the variety", 105, "Bajra"),
        ("3.5-4  months", 120, "Maize (Metalaxyl-M 31.8% ES)"),
    ])
    def test_glued_month_cells_convert(self, raw, expected_days, crop):
        assert parse_phi(raw) == expected_days

    def test_the_space_separated_variant_was_always_correct(self):
        """'3.5-4  months' has the space and so parsed correctly even before
        the fix — pinned to prove the fix did not disturb it."""
        assert parse_phi("3.5-4  months") == 120

    def test_glued_unit_does_not_match_inside_a_word(self):
        """The lookbehind must still refuse a unit embedded in a real word,
        or 'Sunday' would register as a day and change the multiplier."""
        assert parse_phi("Sunday") is None
        assert parse_phi("3 Sunday") == 3

    def test_glued_weeks_and_days_also_convert(self):
        assert parse_phi("2weeks") == 14
        assert parse_phi("10days") == 10


class TestVulgarFractions:
    def test_half_is_expanded(self):
        assert parse_phi("3½ months") == 105

    def test_bare_half_becomes_zero_point_five(self):
        assert parse_phi("½ month") == 15

    def test_quarter_and_three_quarters(self):
        """Neither appears in the corpus; handled so the next document
        revision cannot introduce one silently."""
        assert parse_phi("2¼ weeks") == 15
        assert parse_phi("1¾ months") == 52

    def test_fraction_does_not_disturb_plain_decimals(self):
        assert parse_phi("3.5 months") == 105


class TestHoursConvertToDays:
    """Decision 4: hours convert and round UP. A partial day of waiting is
    still a day on which the crop must not be harvested; rounding down would
    manufacture a zero-day PHI from a label that demands a wait."""

    def test_twelve_hours_rounds_up_to_one_day(self):
        assert parse_phi("12 hrs") == 1

    def test_twenty_four_hours_is_one_day(self):
        assert parse_phi("24 hours") == 1

    def test_forty_eight_hours_is_two_days(self):
        assert parse_phi("48 hours") == 2

    def test_hours_never_round_down_to_zero(self):
        assert parse_phi("1 hour") == 1


class TestNonPhiContentRaises:
    """Decision 3: the PHI column also carries content that is not a waiting
    period. Every one of these returned a confident integer before Phase 4
    because it contains digits."""

    @pytest.mark.parametrize("raw,was_returning", [
        ("IS:6313- 2001  (Part-2)", 6313),
        ("IS:6313-2001  (Part-3)", 6313),
        ("Dilution in  water- 500  liter/ha", 500),
        ("500 lit per ha", 500),
        ("As when  residues not  to exceed 25  ppm", 25),
        ("90 %  Emergence  of earhead", 90),
        ("February  followed by  2 dusting in  summer", 2),
        ("Only one  application  before the  buds swell, 3 pre harvest application", 3),
        ("3  applications  after petal  fall , 2 weeks later & after harvest", 21),
        ("800 kg seed  tubers of  potato are  dipped in the solutions", 800),
    ])
    def test_non_phi_content_raises_instead_of_returning_a_number(
            self, raw, was_returning):
        with pytest.raises(PHIParseError):
            parse_phi(raw)

    def test_collapsed_columns_raise(self):
        """'0 7' is two merged table columns, not a 7-day PHI. Picking either
        number would be a guess."""
        for raw in ["0 7", "1 0", "2 1", "77    77"]:
            with pytest.raises(PHIParseError):
                parse_phi(raw)

    def test_fumigant_reentry_period_raises(self):
        with pytest.raises(PHIParseError):
            parse_phi("03 (day) or 48 (Hrs) Re-  entry period after each  application")
        with pytest.raises(PHIParseError):
            parse_phi("Aeration is waiting  Period 07 days to  be checked PH3 "
                      "detector strips.")

    def test_error_message_says_what_the_cell_actually_is(self):
        """A quarantine reviewer should not have to re-derive why the cell was
        rejected."""
        with pytest.raises(PHIParseError, match="ISI standard reference"):
            parse_phi("IS:6313- 2001  (Part-2)")
        with pytest.raises(PHIParseError, match="dilution volume"):
            parse_phi("Dilution in  water- 500  liter/ha")


class TestNotApplicableProseReturnsNoneNotRaise:
    """Decision 5. Seed-treatment and 'not required' prose mean a PHI does not
    apply to the row — that is a property of the label, not an extraction
    defect, so it must not be quarantined. schema.ChemicalOption.phi_days
    cannot express "not applicable" separately from "unknown"; label_db
    (Step 5) carries a phi_not_applicable flag and the caller sets it.
    """

    @pytest.mark.parametrize("raw", [
        "This is used as  seed dresser",
        "Used as  seed  treatment",
        "Only one  time seed  Treatment  required",
        "Being  seed  treatment  waiting  not  required",
        "Not applicable for seed  treatment",
        "waiting  not  required",
        "Use as a  seed  treatment,  hence  waiting  period is  not  applicable",
        "N.A (Seed  Dresser)",
        "NA (Seed  dresser)",
        "Single application by seed  treatment before sowing.",
        "(wet slurry  treatment)",
    ])
    def test_seed_treatment_prose_returns_none(self, raw):
        assert parse_phi(raw) is None

    @pytest.mark.parametrize("raw", [
        "At the end of the  Harvest",
        "At whit bud,  Petal fall",
        "Delayed  dormant  spray",
    ])
    def test_numberless_growth_stage_returns_none_not_raise(self, raw):
        """A growth-stage phrase with NO digits cannot produce a wrong number,
        so it returns None rather than being quarantined. This is the line
        between decision 3 (numbered growth stages raise) and decision 5
        (numberless ones are just 'no PHI stated')."""
        assert parse_phi(raw) is None

    def test_numbered_growth_stage_does_raise(self):
        """The other side of that line, pinned so the two decisions cannot
        drift into each other."""
        with pytest.raises(PHIParseError):
            parse_phi("90 %  Emergence  of earhead")


class TestPhaseFourDidNotDisturbPhaseThree:
    """Every behaviour the module already had, re-pinned. The Phase 4 changes
    were meant to be strict extensions."""

    def test_zero_still_parses_to_zero(self):
        assert parse_phi("0") == 0
        assert parse_phi("0") is not None

    def test_placeholders_still_none(self):
        for raw in ["-", "--", "----", "NA", "N/A", "NIL", "Nil", "", "  "]:
            assert parse_phi(raw) is None

    def test_range_still_takes_the_larger_value(self):
        """Opposite of the dose rule (lower bound), same safe direction:
        more waiting and less chemical are both the cautious side."""
        assert parse_phi("14-21") == 21
        assert parse_phi("35-89") == 89
        assert parse_phi("7-10") == 10

    def test_weeks_and_months_still_convert(self):
        assert parse_phi("Not less than 21 weeks") == 147
        assert parse_phi("Not less than7  weeks") == 49
        assert parse_phi("2 weeks") == 14
        assert parse_phi("3 months") == 90

    def test_plain_day_cells_unchanged(self):
        assert parse_phi("7") == 7
        assert parse_phi("10 days") == 10
        assert parse_phi("90day s") == 90

    def test_none_input_still_none(self):
        assert parse_phi(None) is None
