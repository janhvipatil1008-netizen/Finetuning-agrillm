"""Tests for src/dose_parser.py.

Every real-data string below is copied verbatim (unicode dashes and all) from
reports/phase4_stepA_dose_survey.md, so a test failure here means the parser
disagrees with the Phase A survey, not that a string was invented to make the
parser look good.

Basis coverage note: `per_acre` is not tested against parse_dose. CIB&RC
prints per-hectare only; nothing in this corpus is per-acre; and
dose_parser.py's rule 10 makes that a DESIGN choice, not a gap — per_acre is
"already converted from per_ha by label_db" per schema.py's own comment, so
the conversion belongs in a later step, and parse_dose never emits it. The
per_acre test below constructs a Dose directly through schema.Dose to confirm
the frozen schema still accepts that basis; it does not call parse_dose.

schema.Unit is `Literal["g", "ml", "kg", "l", "%"]`, not an enum class, so
`default_unit="g"` (a plain string) is used throughout rather than `Unit.g`.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dose_parser import DoseParseBug, _build, parse_dose  # noqa: E402
from schema import Dose  # noqa: E402


def assert_numeric(raw, *, default_unit=None, basis, value_min, value_max=None,
                    unit):
    r = parse_dose(raw, default_unit=default_unit)
    assert r.branch == "numeric", f"{raw!r} -> {r.branch} ({r.pattern}, {r.code})"
    assert r.dose is not None
    assert r.dose.basis == basis
    assert r.dose.value_min == pytest.approx(value_min)
    if value_max is None:
        assert r.dose.value_max is None
    else:
        assert r.dose.value_max == pytest.approx(value_max)
    assert r.dose.unit == unit
    assert r.dose.raw == raw
    return r


def assert_free_text(raw, *, default_unit=None):
    r = parse_dose(raw, default_unit=default_unit)
    assert r.branch == "free_text", f"{raw!r} -> {r.branch} ({r.pattern}, {r.code})"
    assert r.dose is not None
    assert r.dose.basis == "free_text"
    assert r.dose.raw == raw
    return r


def assert_unparseable(raw, *, default_unit=None, code=None):
    r = parse_dose(raw, default_unit=default_unit)
    assert r.branch == "unparseable", f"{raw!r} -> {r.branch} (dose={r.dose})"
    assert r.dose is None
    if code is not None:
        assert r.code == code, f"{raw!r} -> code={r.code}, expected {code}"
    return r


def assert_empty(raw):
    r = parse_dose(raw)
    assert r.branch == "empty", f"{raw!r} -> {r.branch}"
    assert r.dose is None
    return r


# ---------------------------------------------------------------------------
# 1. One case per Basis enum value actually emitted by the parser
# ---------------------------------------------------------------------------

class TestBasisCoverage:
    def test_per_ha(self):
        assert_numeric("500", default_unit="g", basis="per_ha", value_min=500, unit="g")

    def test_concentration_pct(self):
        assert_numeric("0.1%", basis="concentration_pct", value_min=0.1, unit="%")

    def test_per_litre_water(self):
        assert_numeric("2.5 ml per lit of water", basis="per_litre_water",
                        value_min=2.5, unit="ml")

    def test_per_kg_seed(self):
        assert_numeric("2-2.5 gm/  kg seed", basis="per_kg_seed",
                        value_min=2.0, value_max=2.5, unit="g")

    def test_per_tree(self):
        assert_numeric("10 lit/tree", basis="per_tree", value_min=10.0, unit="l")

    def test_per_plant(self):
        assert_numeric("1.2 L/ Plant", basis="per_plant", value_min=1.2, unit="l")

    def test_per_sq_m(self):
        assert_numeric("250  ml/sq.mtr", basis="per_sq_m", value_min=250.0, unit="ml")

    def test_free_text_is_a_basis_too(self):
        r = assert_free_text("30 + 15")
        assert r.dose.basis == "free_text"

    def test_per_acre_is_schema_valid_but_never_emitted_by_parse_dose(self):
        """per_acre is unreachable from this corpus (CIB&RC prints per-hectare
        only) and unreachable from this parser by design (rule 10: label_db
        converts per_ha -> per_acre later, not here). This constructs a Dose
        directly to confirm the frozen schema still accepts the basis; it is
        the one case in this file that does not call parse_dose."""
        d = Dose(basis="per_acre", value_min=1.0, value_max=1.5, unit="kg",
                  raw="SYNTHETIC: 1.0-1.5 kg/acre — not a real label string")
        assert d.basis == "per_acre"
        assert d.value_min == 1.0 and d.value_max == 1.5

        # And confirm the negative: no real dose string drives parse_dose to
        # basis='per_acre'. PER_HA_EXPLICIT is the closest pattern (explicit
        # area basis) and it always resolves to per_ha.
        r = parse_dose("2.5 kg/ha")
        assert r.dose.basis == "per_ha"


# ---------------------------------------------------------------------------
# 2. The 57 in-scope percentage / per-litre rows
#    (reports/phase4_stepA_dose_survey.md section 4.2, rows 1-78; the 57 is a
#    ROW count, not a distinct-string count — 78 distinct strings back it)
# ---------------------------------------------------------------------------

class TestPercentAndPerLitreGroup:
    # PCT_WITH_EQUIV -- the Kitazin family: '%' stated with its own mass-in-
    # water equivalent. One dose, stated twice. >=5 required.
    @pytest.mark.parametrize("raw,value_min", [
        ("0.10% or100  Gram in  100lit.  Of water", 0.10),   # Kitazin 48% EC itself
        ("0.20%or  200mlin  200lt. of  water", 0.20),        # its formulation half
        ("0.21%or  210  g/100Ltr.  water", 0.21),
        ("0.30%or300  gram/100Ltr.  water", 0.30),
        ("0.03% or 0.3 g/l", 0.03),
        ("0.046%  or 46 g /100  lit. water", 0.046),
    ])
    def test_pct_with_equiv(self, raw, value_min):
        assert_numeric(raw, basis="concentration_pct", value_min=value_min, unit="%")

    # PCT_SINGLE: >=3 required.
    @pytest.mark.parametrize("raw,value_min", [
        ("0.1%", 0.1),
        ("0.28 % w/w", 0.28),
        ("1 %", 1.0),
        ("0.08%", 0.08),
        ("0.023%", 0.023),
    ])
    def test_pct_single(self, raw, value_min):
        assert_numeric(raw, basis="concentration_pct", value_min=value_min, unit="%")

    # PER_LITRE: >=3 required.
    @pytest.mark.parametrize("raw,value_min,unit", [
        ("0.15 gm per  lit", 0.15, "g"),
        ("2.5 ml per lit of  water", 2.5, "ml"),
        ("0.75 ml/L  water", 0.75, "ml"),
        ("0.2 ml/Ltr.", 0.2, "ml"),
    ])
    def test_per_litre(self, raw, value_min, unit):
        assert_numeric(raw, basis="per_litre_water", value_min=value_min, unit=unit)

    def test_per_litre_with_ocr_split_word(self):
        # 'litres' broken across the OCR line as 'lit res' -- still matches.
        assert_numeric("10gm/lit res of  water", basis="per_litre_water",
                        value_min=10.0, unit="g")

    # PER_N_LITRE: >=3 required. These divide by the stated water quantity
    # (requirement 5 also covers this from the normalisation angle).
    @pytest.mark.parametrize("raw,value_min,unit", [
        ("50ml/100Ltr.  water", 0.5, "ml"),
        ("0.90/10 Lit water", 0.09, "g"),
        ("15ml/100  ltr water", 0.15, "ml"),
    ])
    def test_per_n_litre(self, raw, value_min, unit):
        assert_numeric(raw, default_unit="g", basis="per_litre_water",
                        value_min=value_min, unit=unit)

    def test_per_n_litre_range_divides_both_ends(self):
        r = parse_dose("70-87.5/100 l of  water", default_unit="g")
        assert r.branch == "numeric"
        assert r.dose.basis == "per_litre_water"
        assert r.dose.value_min == pytest.approx(0.70)
        assert r.dose.value_max == pytest.approx(0.875)

    # PCT_EQUIV_FIRST: mass/volume equivalent stated before its '%'. >=3 required.
    @pytest.mark.parametrize("raw,value_min", [
        ("75 (0.0075%)", 0.0075),
        ("750  (0.075%)", 0.075),
        ("90 (0.009%)", 0.009),
        ("900  (0.09%)", 0.09),
        ("2000gor  0.4%", 0.4),
        ("2500gor  0.5%", 0.5),
        ("2.25 kg  (0.3%)", 0.3),
    ])
    def test_pct_equiv_first(self, raw, value_min):
        assert_numeric(raw, basis="concentration_pct", value_min=value_min, unit="%")

    # PCT_RANGE: >=2 required.
    @pytest.mark.parametrize("raw,lo,hi", [
        ("0.00048-  0.00096%", 0.00048, 0.00096),
        ("0.025- 0.050%", 0.025, 0.050),
    ])
    def test_pct_range(self, raw, lo, hi):
        assert_numeric(raw, basis="concentration_pct", value_min=lo, value_max=hi,
                        unit="%")

    # PCT_RANGE_BOTH: >=2 required. One resolves (has an operator), one is the
    # AMBIGUOUS_PAIR case from decision 7 -- both are real PCT_RANGE_BOTH-shaped
    # strings from the survey, so both belong here.
    def test_pct_range_both_numeric(self):
        assert_numeric("0.025% -0.05%", basis="concentration_pct",
                        value_min=0.025, value_max=0.05, unit="%")

    def test_pct_range_both_ambiguous(self):
        # '0.005%  0.05%' -- two percentages, nothing joins them. Guessing
        # whether that's a range or two unrelated readings is exactly what
        # rule 9 (no silent failures) forbids.
        assert_unparseable("0.005%  0.05%", code="AMBIGUOUS_PAIR")

    # The Kitazin cell itself, both columns, verified end to end.
    def test_kitazin_48_ec_pomegranate(self):
        ai = assert_numeric("0.10%  or100  Gram in  100lit.  Of water",
                             basis="concentration_pct", value_min=0.10, unit="%")
        formulation = assert_numeric("0.20%or  200mlin  200lit. of  water",
                                      basis="concentration_pct", value_min=0.20,
                                      unit="%")
        assert ai.dose.raw == "0.10%  or100  Gram in  100lit.  Of water"
        assert formulation.dose.raw == "0.20%or  200mlin  200lit. of  water"


# ---------------------------------------------------------------------------
# 3. Compound / seed-treatment rates -> free_text
# ---------------------------------------------------------------------------

class TestCompoundRoutesToFreeText:
    # COMPOUND_SUM (Phase A name): >=3 required.
    @pytest.mark.parametrize("raw", ["124.5+1000", "82.5+137.25", "50+100", "50+50"])
    def test_compound_sum(self, raw):
        assert_free_text(raw)

    # COMPOUND_RANGE (Phase A name): a compound rate stated as a range.
    def test_compound_range(self):
        assert_free_text("43.31 +37.13-  45.94 +39.38")

    # COMPOUND_NAMED (Phase A name): named ready-mix breakdown.
    def test_compound_named(self):
        assert_free_text("27 (Emamectin  benzoate  3.0+Lufenuron 24.0)")

    def test_compound_named_kitazin_neighbour(self):
        # Same fungicides file as Kitazin, a different chemical: a named
        # ready-mix on the same page-range this survey drew from.
        assert_free_text("1.58 (Cyantraniliprole  0.79 + Thiamethoxam  0.79)")

    def test_seed_treatment_prose_is_free_text_not_a_dose(self):
        # Rule 5: the '%' here is product strength, not a dose concentration.
        raw = ("Seed Treatment:  Mix required quantity of the seeds with the "
               "required quantity of  Trichoderma viride 1.0%  WP and ensure "
               "uniform coating, shade dry and sow")
        r = assert_free_text(raw)
        assert r.pattern == "PROSE_METHOD"


# ---------------------------------------------------------------------------
# 4. Ranges: both ends populated; the lower-bound rule is documented, not
#    enforced here (there is no downstream consumer yet to test against).
# ---------------------------------------------------------------------------

class TestRangesKeepBothEnds:
    def test_range_populates_both_bounds(self):
        r = assert_numeric("500-750", default_unit="g", basis="per_ha",
                            value_min=500, value_max=750, unit="g")
        assert r.dose.value_min < r.dose.value_max

    def test_range_with_unicode_en_dash(self):
        assert_numeric("500 –1000", default_unit="g", basis="per_ha",
                        value_min=500, value_max=1000, unit="g")

    def test_reversed_range_is_rejected_not_silently_swapped(self):
        # '750-500' printed backwards is a defect, not a range whose ends the
        # parser should quietly reorder.
        assert_unparseable("750-500", default_unit="g", code="REVERSED_RANGE")

    def test_lower_bound_rule_is_documented_in_the_module(self):
        """Confirms design rule 2 (dose ranges resolve to the LOWER bound when
        a single value is needed downstream -- the opposite of PHI, which
        resolves to the larger) is written into dose_parser's own docstring,
        per the instruction to document it there rather than only in a
        comment. There is no downstream single-value consumer yet to exercise
        the rule against; this test only guards against the rule silently
        disappearing from the docs."""
        import dose_parser
        doc = dose_parser.__doc__
        assert "LOWER bound" in doc
        assert "PHI" in doc


# ---------------------------------------------------------------------------
# 5. Normalisation (division) cases
# ---------------------------------------------------------------------------

class TestNormalisationByDivision:
    def test_per_n_kg_seed_divides(self):
        # '38.75 g/10 kg seeds' -> 3.875 g per kg seed
        assert_numeric("38.75 g/10 kg  seeds", basis="per_kg_seed",
                        value_min=3.875, unit="g")

    def test_per_n_litre_divides(self):
        # '50ml/100Ltr. water' -> 0.5 ml per litre
        assert_numeric("50ml/100Ltr.  water", basis="per_litre_water",
                        value_min=0.5, unit="ml")

    def test_per_n_sq_m_divides(self):
        # '1 litre/30 m2' -> ~0.0333 l per sq m
        r = parse_dose("1 litre/30 m2")
        assert r.branch == "numeric"
        assert r.dose.basis == "per_sq_m"
        assert r.dose.value_min == pytest.approx(1 / 30)
        assert r.dose.unit == "l"

    def test_division_preserves_the_verbatim_string_in_raw(self):
        raw = "38.75 g/10 kg  seeds"
        r = parse_dose(raw)
        # The printed figure (38.75) no longer appears in value_min (3.875),
        # so raw is the only place the original label text survives.
        assert r.dose.raw == raw
        assert "38.75" in r.dose.raw
        assert r.dose.value_min != 38.75

    def test_range_normalisation_divides_both_ends(self):
        # '0.75-1.0/100kg seed' has no unit token of its own -- '100kg' is the
        # seed-weight denominator, not the numerator's unit -- so this needs
        # the column's default_unit, same as a bare number would.
        r = parse_dose("0.75-  1.0/100kg  seed", default_unit="g")
        assert r.branch == "numeric"
        assert r.dose.basis == "per_kg_seed"
        assert r.dose.value_min == pytest.approx(0.0075)
        assert r.dose.value_max == pytest.approx(0.01)


# ---------------------------------------------------------------------------
# 6. Deliberately malformed / adversarial strings -> unparseable
# ---------------------------------------------------------------------------

class TestMalformedStringsAreRejected:
    def test_time_value_disguised_as_dose(self):
        assert_unparseable("48 hrs.", code="TIME_VALUE")

    def test_active_ingredient_name_in_dose_cell(self):
        assert_unparseable("Kresoxim-methyl-  150 &  Chlorothalonil- 560",
                            code="AI_NAME")

    def test_truncated_string(self):
        assert_unparseable("594 +59.4 –", code="TRUNCATED")

    def test_ratio(self):
        assert_unparseable("37:3", code="RATIO_OR_INEQUALITY")

    def test_inequality(self):
        assert_unparseable(">140", code="RATIO_OR_INEQUALITY")

    def test_empty_string(self):
        assert_empty("")

    def test_whitespace_only_string(self):
        assert_empty("   ")

    def test_column_collapse(self):
        # Several independent numbers with no operator: columns merged into
        # one cell during extraction, not a dose.
        assert_unparseable("30-37.5    0.03-  0.0375%", code="COLUMN_COLLAPSE")

    def test_none_input_does_not_raise(self):
        r = parse_dose(None)
        assert r.branch == "unparseable"
        assert r.dose is None


# ---------------------------------------------------------------------------
# 7. The three judgement-call cases
# ---------------------------------------------------------------------------

class TestJudgementCalls:
    def test_ambiguous_pair_unparseable(self):
        assert_unparseable("0.005%  0.05%", code="AMBIGUOUS_PAIR")

    def test_pct_with_foreign_basis_is_free_text(self):
        # '1.8 g a.i/vine or 0.09%' names two different bases (per-vine and
        # concentration) with no rule for choosing between them.
        r = assert_free_text("1.8ga.i/vine  or0.09%")
        assert r.pattern == "PCT_WITH_FOREIGN_BASIS"

    def test_second_foreign_basis_case(self):
        assert_free_text("2.5gm/vine  or0.125%")

    def test_dose_parse_bug_raises_on_schema_violation(self):
        # concentration_pct MUST carry unit='%' (schema.py's own comment:
        # "the real hazard is ... 0.025 labelled per_acre with unit '%'").
        # This constructs the mirror-image invalid combination directly
        # through dose_parser._build, the same constructor parse_dose uses
        # internally, to confirm a schema violation raises loudly rather than
        # being downgraded to free_text or silently coerced.
        with pytest.raises(DoseParseBug):
            _build(("concentration_pct", 1.0, None, "kg"), "synthetic: bad basis/unit pair")

    def test_dose_parse_bug_message_names_the_offending_values(self):
        with pytest.raises(DoseParseBug) as exc_info:
            _build(("per_ha", 1.0, None, "%"), "synthetic: mass basis with '%' unit")
        msg = str(exc_info.value)
        assert "per_ha" in msg
        assert "%" in msg

    def test_dose_parse_bug_is_not_a_plain_exception_swallowed_elsewhere(self):
        # parse_dose itself must never produce a combination that trips this,
        # for any of the real strings this file exercises above. If it did,
        # the earlier tests in this file would already have raised instead of
        # returning a ParseResult. This test documents that guarantee
        # explicitly rather than leaving it implicit in "the other tests
        # didn't crash".
        for raw in ["0.1%", "500-750", "38.75 g/10 kg  seeds", "10 lit/tree"]:
            parse_dose(raw, default_unit="g")  # must not raise


# ---------------------------------------------------------------------------
# 8. The empty branch
# ---------------------------------------------------------------------------

class TestEmptyBranch:
    @pytest.mark.parametrize("raw", ["-", "--", "---", "NA", "N/A", "Not applicable",
                                     "nil"])
    def test_null_markers_are_empty_not_free_text(self, raw):
        r = assert_empty(raw)
        assert r.pattern == "NULL_MARKER"

    def test_empty_dose_is_none_not_a_free_text_placeholder(self):
        r = parse_dose("-")
        assert r.dose is None
        # An empty cell must not be indistinguishable from a genuine free_text
        # dose ('30 + 15') by checking dose is None alone -- also check branch.
        assert r.branch != "free_text"


# ---------------------------------------------------------------------------
# 9. NUM_WITH_METHOD split
# ---------------------------------------------------------------------------

class TestNumWithMethodSplit:
    def test_single_value_with_method_is_numeric(self):
        r = assert_numeric("750  (Soil drench)", default_unit="g", basis="per_ha",
                            value_min=750, unit="g")
        assert r.pattern == "NUM_WITH_METHOD"
        assert r.dose.raw == "750  (Soil drench)"  # method text preserved in raw

    def test_second_quantity_is_free_text(self):
        r = assert_free_text("500  20 ltr/ha (via  drone  application)",
                              default_unit="l")
        assert r.pattern == "NUM_WITH_SECOND_QUANTITY"

    def test_root_feeding_method_numeric(self):
        assert_numeric("0.50 gm/tree (Root  feeding)", basis="per_tree",
                        value_min=0.50, unit="g")

    def test_alternative_via_knapsack_or_drone_is_free_text(self):
        assert_free_text("500 (via Knapsack  sprayer)  20 (via Drone  application )",
                          default_unit="l")


# ---------------------------------------------------------------------------
# 10. default_unit behaviour
# ---------------------------------------------------------------------------

class TestDefaultUnit:
    def test_bare_number_with_default_unit(self):
        r = parse_dose("500", default_unit="g")
        assert r.branch == "numeric"
        assert r.dose.unit == "g"
        assert r.dose.value_min == 500.0

    def test_bare_number_without_default_unit_needs_unit(self):
        r = parse_dose("500")
        assert r.branch == "unparseable"
        assert r.code == "NEEDS_UNIT"
        assert r.dose is None

    def test_explicit_unit_in_string_wins_over_default_unit(self):
        # '500gm' states its own unit; a caller-supplied default must not
        # override what the label actually printed.
        r = parse_dose("500gm", default_unit="l")
        assert r.dose.unit == "g"

    def test_default_unit_of_percent_on_a_mass_basis_is_rejected(self):
        # A caller passing default_unit='%' for a bare-number (per_ha) cell
        # is a caller bug, not a dose. Must not silently mint an invalid Dose.
        r = parse_dose("500", default_unit="%")
        assert r.branch == "unparseable"
        assert r.dose is None


# ---------------------------------------------------------------------------
# Cross-cutting: raw is preserved verbatim on every numeric/free_text result
# ---------------------------------------------------------------------------

class TestRawPreservation:
    @pytest.mark.parametrize("raw,kw", [
        ("500-750", dict(default_unit="g")),
        ("0.10%  or100  Gram in  100lit.  Of water", dict()),
        ("124.5+1000", dict()),
        ("38.75 g/10 kg  seeds", dict()),
    ])
    def test_raw_matches_input_exactly(self, raw, kw):
        r = parse_dose(raw, **kw)
        assert r.dose is not None
        assert r.dose.raw == raw
