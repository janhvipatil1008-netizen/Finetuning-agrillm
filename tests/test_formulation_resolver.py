"""Tests for src/formulation_resolver.py.

Every active_ingredient string below is copied verbatim from label_db.csv
(Phase 5 formulation-code survey), same convention as test_dose_parser.py:
a failure here means the resolver disagrees with the corpus, not that a
string was invented to make it look good.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from formulation_resolver import CODE_CLASS, resolve_formulation_unit  # noqa: E402

# --------------------------------------------------------------------------
# one real-corpus string per vocabulary code, expected unit written as a
# literal (not looked up from CODE_CLASS) so a wrong CODE_CLASS entry would
# also be caught.
# --------------------------------------------------------------------------

PER_CODE_CASES = [
    # liquid -> ml
    ("SC", "Amisulbrom 20% SC", "ml"),
    ("EC", "Abamectin 01.90 % EC", "ml"),
    ("AS", "Bacillus subtilis 1.50% AS ( MTCC Accession no. 5786)", "ml"),
    ("FS", "AZOXYSTROBIN 2.5% + THIOPHANATE METHYL 11.25% + THIAMETHOXAM 25% FS", "ml"),
    ("ZC", "Chlorantraniliprole 09.30%+Lambda-cyhalothrin 04.60% ZC", "ml"),
    ("SE", "Azoxystrobin 20% + Boscalid 25% SE", "ml"),
    ("OD", "Cyantraniliprole 10.26% OD", "ml"),
    ("SL", "DIMPROPYRIDAZ 120 g/l SL", "ml"),
    ("CS", "Lambda-cyhalothrin 04.90%CS", "ml"),
    ("DC", "Isocycloseram 9.2% W/W Dc (10% W/V) DC", "ml"),
    ("AF", "Quinalphos 20% AF", "ml"),
    ("ES", "Metalaxyl-M 31.8% ES", "ml"),
    ("EW", "Pyriproxyfen 10% EW", "ml"),
    ("LF", "Ampelomyces quisqualis 1.5% % LF (CFU count: 2x10^6 /ml Min.) "
           "StrainT Stanes Aq-1; Accession number  MTCC-5683", "ml"),
    ("ME", "Flonicamid 15% + Pyriproxyfen 12% + Acetamiprid 2% ME", "ml"),
    ("OS", "Mancozeb 40% +  Azoxystrobin 7% OS", "ml"),
    ("WSL", "Bacillus thuringiensis var. kurstaki 10% WSL (CFU: 2x109 /gm min.) "
            "Strain- NBAIR-BtG4,  Accession no- JN120763, JN120765, "
            "Potency- 14245 IU/ml min.", "ml"),
    # solid -> g
    ("WP", "Ampelomyces quisqualis 2.0% WP", "g"),
    ("WG", "Acetamiprid 20% + Chlorantraniliprole 20% WG", "g"),
    ("WS", "Captan 75% WS", "g"),
    ("WDG", "Acephate 50% +Bifenthrin 10% WDG", "g"),
    ("SP", "Acetamiprid 20% SP", "g"),
    ("SG", "Dinotefuran 20% SG", "g"),
    ("DP", "Chlorpyrifos 01.50% DP", "g"),
    ("DF", "Acephate 97%DF", "g"),
    ("GR", "Fluensulfone 2% GR", "g"),
    ("CG", "Carbofuran 03%CG", "g"),
    ("WSP", "Azadirachtin 00.03% WSP (300 PPM) Neem Oil Based", "g"),
    ("CB", "Bromadiolone 00.25% CB", "g"),
    ("DS", "Carbosulfan 25% DS", "g"),
    ("RB", "Bromadiolone 00.005% RB", "g"),
]


@pytest.mark.parametrize("code,ai,expected", PER_CODE_CASES,
                          ids=[c for c, _, _ in PER_CODE_CASES])
def test_vocabulary_code(code, ai, expected):
    assert resolve_formulation_unit(ai) == expected


def test_all_codes_covered_by_a_case():
    tested = {code for code, _, _ in PER_CODE_CASES}
    assert tested == set(CODE_CLASS)


def test_code_class_has_no_unexpected_entries():
    assert set(CODE_CLASS) == {
        "SC", "EC", "AS", "FS", "ZC", "SE", "OD", "SL", "CS", "DC", "AF",
        "ES", "EW", "LF", "ME", "OS", "WSL",
        "WP", "WG", "WS", "WDG", "SP", "SG", "DP", "DF", "GR", "CG", "WSP",
        "CB", "DS", "RB",
    }


# --------------------------------------------------------------------------
# spelled-out formulation words
# --------------------------------------------------------------------------

def test_spelled_liquid_formulation():
    assert resolve_formulation_unit(
        "Beauveria bassiana 1.5% Liquid  Formulation (CFU count 10X108) "
        "Accession  No.MTCC-5171"
    ) == "ml"


def test_spelled_liquid_formulation_with_second_marker():
    assert resolve_formulation_unit(
        "Verticillium Lecanii 1.50% Liquid Formulation, (1x108 CFU/ml. min.) "
        "Strain – T Stanes VI-1,  Accession No – MTCC-5172"
    ) == "ml"


def test_spelled_l_dot_f():
    assert resolve_formulation_unit(
        "Bacillus subtilis 1.50% L.F (T Stanes Bs-1 Strain MTCC 25072)"
    ) == "ml"


def test_spelled_tablet():
    assert resolve_formulation_unit("Deltamethrin 25%Tablet") == "g"


# --------------------------------------------------------------------------
# hazard 1: chemical-name fragments that are not formulation codes
# --------------------------------------------------------------------------

def test_al_excluded_fosetyl():
    assert resolve_formulation_unit("Fenamidone 4.44%+ Fosetyl-AL 66.7%WDG") == "g"


def test_al_excluded_pyraclostrobin():
    assert resolve_formulation_unit("PYRACLOSTROBIN AL 80% WP") == "g"


# --------------------------------------------------------------------------
# hazard 2: strain/accession/potency tail outranking the real code
# --------------------------------------------------------------------------

def test_strain_tail_does_not_outrank_real_code():
    assert resolve_formulation_unit(
        "Verticillium lecanii 1.15%WP, (1x108  CFU/gm min) Strain – AS "
        "MEGH-VL Accession No – MCC-1028"
    ) == "g"  # WP, not AS


def test_potency_tail_does_not_outrank_real_code():
    assert resolve_formulation_unit(
        "Bacillus thuringiensis serovar kurstaki (3a, 3b, 3c) 5.0% WP "
        "Potency 55000 SU (Spodoptera unit based)  (5x107 spore/mg)"
    ) == "g"  # WP, not SU


def test_ltd_tail_does_not_outrank_real_code():
    assert resolve_formulation_unit(
        "Trichoderma viride 1.0% WP (Strain T-14 in house isolate of M/s "
        "Indore Biotech Inputs & Research (P) Ltd.,  Indore)"
    ) == "g"  # WP, not P


# --------------------------------------------------------------------------
# hazard 4: codes glued to '%' with no separating space
# --------------------------------------------------------------------------

def test_glued_percent_sp():
    assert resolve_formulation_unit("Acephate 75%SP") == "g"


def test_glued_percent_ec():
    assert resolve_formulation_unit("Alphacypermethrin10.00%EC") == "ml"


# --------------------------------------------------------------------------
# hazard 5: 'g/L' formulation glue swallowing the code's leading letter
# --------------------------------------------------------------------------

def test_glued_g_per_l_lsc():
    assert resolve_formulation_unit("Chlorfenapyr 240 g/LSC") == "ml"


def test_glued_g_per_l_ldc():
    assert resolve_formulation_unit("Afidopyropen50g/LDC") == "ml"


# --------------------------------------------------------------------------
# mixed case
# --------------------------------------------------------------------------

def test_mixed_case_dc():
    assert resolve_formulation_unit(
        "Isocycloseram 9.2% W/W Dc (10% W/V) DC"
    ) == "ml"


# --------------------------------------------------------------------------
# code-less strings -> None (do not guess)
# --------------------------------------------------------------------------

def test_bare_bt_name_returns_none():
    assert resolve_formulation_unit("Bacillus thuringiensis var. kurstaki") is None


def test_bare_chemical_name_returns_none():
    assert resolve_formulation_unit("Dazomet") is None


def test_pheromone_rope_returns_none():
    assert resolve_formulation_unit("PB Rope L") is None


def test_okra_extraction_defect_returns_none():
    assert resolve_formulation_unit("(Okra)") is None


def test_empty_string_returns_none():
    assert resolve_formulation_unit("") is None


def test_none_input_returns_none():
    assert resolve_formulation_unit(None) is None


def test_whitespace_only_returns_none():
    assert resolve_formulation_unit("   ") is None
