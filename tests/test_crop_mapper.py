"""
test_crop_mapper.py — pins the CIB&RC crop-string -> scope.py slug contract.

Every string here is verbatim from the corpus unless a test says otherwise;
the distinct-string census is reports/phase4_crop_stepA_survey.md.

The near-miss class is the reason this file is long. 'Black gram' is urad,
'Green gram' is moong, 'Cow pea' and 'Green pea' are not pigeon pea, and none
of the beans is soybean — but each contains a word that an in-scope rule
wants. Folding any of them into an in-scope slug would attach a label claim
to the wrong crop, which is the one failure in this project that reaches a
farmer as a wrong answer rather than a missing one. Each is pinned
individually rather than as a loop so a regression names the crop it broke.

    pytest tests/test_crop_mapper.py -q
"""

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from crop_mapper import SLUGS, CropResult, map_crop  # noqa: E402


def slugs(raw):
    return [r.slug for r in map_crop(raw)]


def only(raw):
    """The single result for a cell expected to resolve to exactly one crop."""
    results = map_crop(raw)
    assert len(results) == 1, f"{raw!r} produced {len(results)} results: {results}"
    return results[0]


# ---------------------------------------------------------------------------
# Contract shape
# ---------------------------------------------------------------------------

class TestReturnShape:
    def test_always_returns_a_list(self):
        """map_crop always returns a list, never a bare CropResult — see the
        module docstring for why the task spec's signature could not hold."""
        for raw in ["Cotton", "Brinjal", "", "Wheat, Gram"]:
            assert isinstance(map_crop(raw), list)
            assert all(isinstance(r, CropResult) for r in map_crop(raw))

    def test_out_of_scope_still_returns_one_result(self):
        """Nothing silently disappears: an out-of-scope cell returns a result
        carrying slug=None, so a caller cannot confuse 'no crop' with
        'nothing happened'."""
        results = map_crop("Brinjal")
        assert len(results) == 1
        assert results[0].slug is None
        assert results[0].raw == "Brinjal"

    def test_raw_preserved_verbatim(self):
        raw = "Pigeon pea or Red gram (Arhar/Tur)"
        assert all(r.raw == raw for r in map_crop(raw))

    def test_in_scope_property(self):
        assert only("Cotton").in_scope is True
        assert only("Brinjal").in_scope is False

    def test_every_slug_emitted_is_a_scope_slug(self):
        for raw in ["Cotton", "Soybean", "Pigeon pea", "Chickpea", "Onion",
                    "Tomato", "Grapes", "Pomegranate"]:
            for r in map_crop(raw):
                assert r.slug in SLUGS


# ---------------------------------------------------------------------------
# One test per scope slug, >=2 real CIB&RC strings each
# ---------------------------------------------------------------------------

class TestSlugCoverage:
    @pytest.mark.parametrize("raw", ["Cotton", "Cotton (Soil  drench)"])
    def test_cotton(self, raw):
        assert only(raw).slug == "cotton"

    @pytest.mark.parametrize("raw", [
        "Soybean", "Soya bean", "Soyabean", "soybean", "Soybean  (Seed  Treatment)"])
    def test_soybean(self, raw):
        assert only(raw).slug == "soybean"

    @pytest.mark.parametrize("raw", [
        "Pigeon pea", "Pigeonpea", "Pigeon Pea", "Red gram", "Red Gram",
        "Red Gram  (Tur or  Arhar)", "Pigeon pea  (Tur/Arhar)"])
    def test_tur(self, raw):
        """Tur == pigeon pea == arhar == red gram. Note the corpus never
        prints a bare 'Tur' or 'Arhar' — they appear only inside
        parentheticals — so CIB&RC's primary names are the ones that matter.
        """
        assert only(raw).slug == "tur"

    @pytest.mark.parametrize("raw", [
        "Gram", "Bengal gram", "Bengal  gram", "Chickpea", "Chick pea",
        "Bengal  Gram  (Gram or  Chickpea)"])
    def test_gram(self, raw):
        """Gram == Bengal gram == chickpea == chana. NOT black/green/horse
        gram — see TestNearMissExclusions."""
        assert only(raw).slug == "gram"

    @pytest.mark.parametrize("raw", ["Onion", "onion", "ONION"])
    def test_onion(self, raw):
        """Onion has exactly one surface form in the corpus; the case
        variants here are synthetic, pinning case-insensitivity."""
        assert only(raw).slug == "onion"

    @pytest.mark.parametrize("raw", [
        "Tomato", "T omato", "Tomato  nursery", "Tomato  seedlings",
        "Tomato   Soil drench", "Tomato  Foliar  application"])
    def test_tomato(self, raw):
        assert only(raw).slug == "tomato"

    @pytest.mark.parametrize("raw", [
        "Grape", "Grapes", "G rapes", "Grapes (Soil  drench)",
        "Grapes –", "Grapes –Soil  drench"])
    def test_grape(self, raw):
        assert only(raw).slug == "grape"

    @pytest.mark.parametrize("raw", ["Pomegranate", "Pomegranate  Alternaria fruit"])
    def test_pomegranate(self, raw):
        assert only(raw).slug == "pomegranate"

    def test_all_eight_slugs_are_reachable(self):
        """Guards against a slug quietly becoming unmatchable."""
        reached = set()
        for raw in ["Cotton", "Soybean", "Pigeon pea", "Chickpea", "Onion",
                    "Tomato", "Grapes", "Pomegranate"]:
            reached.update(r.slug for r in map_crop(raw))
        assert reached == set(SLUGS)


# ---------------------------------------------------------------------------
# Near misses — the dangerous class
# ---------------------------------------------------------------------------

class TestNearMissExclusions:
    """Each contains a word an in-scope rule wants, and is a different crop.

    A false positive here is worse than a miss: it attaches a registered
    label claim for chickpea, pigeon pea or soybean to urad, moong, cowpea or
    a garden pea, and a farmer acts on it.
    """

    @pytest.mark.parametrize("raw", ["Black gram", "Black Gram", "Blackgram"])
    def test_black_gram_is_urad_not_gram(self, raw):
        assert only(raw).slug is None

    @pytest.mark.parametrize("raw", ["Green gram", "Greengram", "Green gram  Whitefly"])
    def test_green_gram_is_moong_not_gram(self, raw):
        assert only(raw).slug is None

    def test_horse_gram_is_kulthi_not_gram(self):
        """Synthetic — horse gram does not appear in this corpus, pinned so a
        future document revision cannot introduce it as a silent gram."""
        assert only("Horse gram").slug is None

    @pytest.mark.parametrize("raw", ["Cow Pea", "Cowpea"])
    def test_cowpea_is_not_pigeon_pea(self, raw):
        assert only(raw).slug is None

    @pytest.mark.parametrize("raw", ["Pea", "Peas", "Green Pea", "Green pea",
                                     "Pea   (Seed  Treatment)"])
    def test_garden_pea_is_not_pigeon_pea(self, raw):
        assert only(raw).slug is None

    @pytest.mark.parametrize("raw", ["Urd bean", "French bean", "Kidney bean",
                                     "Cluster Beans", "Beans"])
    def test_no_other_bean_is_soybean(self, raw):
        assert only(raw).slug is None

    def test_mung_bean_is_not_soybean(self):
        assert only("Pulses  (Cowpea,  Mung bean,  Urdbean)").slug is None

    def test_combined_excluded_pulses(self):
        assert only("Pulses  (Black gram  /Greengram)").slug is None
        assert only("Beans  (Cowpea,  moong, Urd)").slug is None

    def test_turmeric_is_not_tur(self):
        """'tur' is a substring of 'Turmeric'. This is why matching is
        token-based; a substring matcher returned tur here."""
        assert only("Turmeric").slug is None

    def test_floriculture_is_not_tur(self):
        assert only("Floriculture  (Carnation &  Gerbera)").slug is None

    def test_tuberose_is_not_tur(self):
        assert only("Tuberose").slug is None

    @pytest.mark.parametrize("raw", ["Vegetables", "Cucurbits", "Pulses",
                                     "Dry Fruits,  Nuts Spices  & Oil Seeds"])
    def test_generic_categories_are_out_of_scope(self, raw):
        """A generic category names no specific crop and is not expanded into
        the slugs it might cover."""
        assert only(raw).slug is None

    def test_citrus_vegetables_list_is_out_of_scope(self):
        assert only("Citrus,  Rubber,  Paddy  (Rice),Tea,  Vegetables").slug is None


# ---------------------------------------------------------------------------
# Multi-crop splitting
# ---------------------------------------------------------------------------

class TestMultiCropSplit:
    """One label row covering several crops splits into one result per
    IN-SCOPE crop. Out-of-scope crops in the same cell get no result."""

    def test_wheat_gram_yields_gram_only(self):
        results = map_crop("Wheat, Gram")
        assert [r.slug for r in results] == ["gram"]
        assert results[0].multi_crop_split is True

    def test_rice_and_cotton_yields_cotton_only(self):
        results = map_crop("Rice (Paddy)  &cotton")
        assert [r.slug for r in results] == ["cotton"]
        assert results[0].multi_crop_split is True

    def test_tomato_chilli_yields_tomato_only(self):
        results = map_crop("Tomato/Chilli es")
        assert [r.slug for r in results] == ["tomato"]
        assert results[0].multi_crop_split is True

    def test_six_crop_list_yields_tomato_only(self):
        raw = "Cabbage/  Cauliflower,  Tomato,  Brinjal,  Chillies,  Beans,  Ornamental"
        results = map_crop(raw)
        assert [r.slug for r in results] == ["tomato"]
        assert results[0].multi_crop_split is True

    def test_two_in_scope_crops_produce_two_results(self):
        """Synthetic: no cell in this corpus names two in-scope crops, but the
        splitting rule must work when one does."""
        results = map_crop("Cotton and Tomato")
        assert sorted(r.slug for r in results) == ["cotton", "tomato"]
        assert all(r.multi_crop_split for r in results)


class TestSynonymStackingIsNotMultiCrop:
    """One crop listed under several names is NOT a multi-crop cell. The
    commas and slashes in these strings are not a signal."""

    @pytest.mark.parametrize("raw", [
        "Pigeon pea or Red gram (Arhar/Tur)",
        "Pigeonpea  (Red  Gram/Arhar /Tur)",
        "Red Gram  (Arhar/Tur)",
        "Red gram (Tur or  Arhar)",
        "Pigeon pea  (Tur/Arhar)",
    ])
    def test_tur_synonym_stacks_resolve_to_one_result(self, raw):
        results = map_crop(raw)
        assert [r.slug for r in results] == ["tur"]
        assert results[0].multi_crop_split is False

    def test_gram_synonym_stack_resolves_to_one_result(self):
        results = map_crop("Bengal  Gram  (Gram or  Chickpea)")
        assert [r.slug for r in results] == ["gram"]
        assert results[0].multi_crop_split is False

    def test_method_qualifier_is_not_multi_crop(self):
        """'(Soil drench)' and 'nursery' describe how the product is applied,
        not a second crop."""
        for raw in ["Cotton (Soil  drench)", "Tomato  nursery",
                    "Grapes –Soil  drench", "Soybean  (Seed  Treatment)"]:
            assert only(raw).multi_crop_split is False


# ---------------------------------------------------------------------------
# Pest-bled cells
# ---------------------------------------------------------------------------

class TestPestBledCells:
    """Phase 3 extraction let pest text into the crop column. The crop is
    still unambiguous; the row's pest_or_disease field is what needs
    verifying, and this module does not touch it."""

    @pytest.mark.parametrize("raw,expected", [
        ("Pigeon Pea Helicoverpa armiger", "tur"),
        ("Pigeon Pea Heliothis sp.", "tur"),
        ("Pigeon pea  Bollworm (Helicoverpa", "tur"),
        ("Pomegranate  Alternaria fruit", "pomegranate"),
    ])
    def test_crop_still_maps_and_is_flagged(self, raw, expected):
        r = only(raw)
        assert r.slug == expected
        assert r.pest_bled is True

    def test_clean_cells_are_not_flagged(self):
        for raw in ["Pigeon pea", "Pomegranate", "Cotton"]:
            assert only(raw).pest_bled is False

    def test_pest_bleed_does_not_trigger_multi_crop(self):
        """A pest name is not a crop name."""
        assert only("Pigeon Pea Helicoverpa armiger").multi_crop_split is False


# ---------------------------------------------------------------------------
# OCR artifacts
# ---------------------------------------------------------------------------

class TestOcrArtifacts:
    @pytest.mark.parametrize("raw,expected", [
        ("T omato", "tomato"),
        ("G rapes", "grape"),
    ])
    def test_leading_letter_split_is_repaired(self, raw, expected):
        assert only(raw).slug == expected

    def test_truncation_artifact_still_maps(self):
        """'Grapes –' is a Phase 3 truncation artifact — trailing en dash,
        nothing after it. The crop is still grape."""
        assert only("Grapes –").slug == "grape"

    def test_glued_compounds_match_the_spaced_form(self):
        assert only("Pigeonpea").slug == only("Pigeon pea").slug == "tur"
        assert only("Chickpea").slug == only("Chick pea").slug == "gram"
        assert only("Blackgram").slug == only("Black gram").slug is None

    def test_case_insensitive(self):
        for variant in ["COTTON", "cotton", "CoTToN"]:
            assert only(variant).slug == "cotton"

    def test_internal_whitespace_collapsed(self):
        assert only("Bengal    gram").slug == "gram"


# ---------------------------------------------------------------------------
# Blank / degenerate input
# ---------------------------------------------------------------------------

class TestBlankAndDegenerate:
    @pytest.mark.parametrize("raw", ["", "   ", "\n", "\t  \n"])
    def test_blank_returns_single_none_result(self, raw):
        r = only(raw)
        assert r.slug is None
        assert r.raw == raw

    def test_none_input_does_not_raise(self):
        r = only(None)
        assert r.slug is None

    def test_punctuation_only(self):
        assert only("-").slug is None
        assert only("()").slug is None

    def test_prose_cell_mentioning_a_crop_is_dropped(self):
        """The rodenticide row names soybean but makes no soybean claim. It
        must not manufacture a soybean recommendation."""
        raw = ("For rodent  control in  field, storage  and crops like  "
               "rice, soybean and coconut)")
        r = only(raw)
        assert r.slug is None
        assert r.not_a_crop_cell is True

    @pytest.mark.parametrize("raw", [
        "Go downs,  Residential Premises,  Public halls",
        "Residential  premises",
        "Post- construction  (Building)",
        "Public health",
    ])
    def test_non_crop_locations_are_out_of_scope(self, raw):
        assert only(raw).slug is None

    def test_ordinary_out_of_scope_crop_is_not_flagged_not_a_crop_cell(self):
        """not_a_crop_cell means 'this cell holds a sentence', not merely
        'out of scope'. Brinjal is a real crop, just not one of the eight."""
        assert only("Brinjal").not_a_crop_cell is False
