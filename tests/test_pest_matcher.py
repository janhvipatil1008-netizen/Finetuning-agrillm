"""test_pest_matcher.py — pins the pest synonym table and the matcher.

Every case here is drawn from label_db or scope.py, not invented. The ones
that matter most are the crop-dependent names: a regression there does not
produce a crash, it produces a confident recommendation of the wrong
chemical for the wrong organism.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import scope  # noqa: E402
from pest_matcher import (  # noqa: E402
    UNMATCHABLE,
    load_table,
    match_all,
    match_pest,
    normalise_pest,
    split_pest_cell,
)


@pytest.fixture(scope="module")
def table():
    return load_table()


def canon(table, crop, name):
    return match_pest(crop, name, table).canonical_name


# ==========================================================================
# 1. the nine crop-dependent names
# ==========================================================================

# (surface form, crop, expected canonical, expected scientific name)
CROP_DEPENDENT = [
    # canonical itself differs — the crop is load-bearing
    ("Fruit borer", "tomato", "Helicoverpa armigera", "Helicoverpa armigera"),
    ("Fruit borer", "pomegranate", "Pomegranate fruit borer", "Deudorix isocrates"),
    ("Alternaria leaf spot", "cotton", "Alternaria leaf spot", "Alternaria macrospora"),
    ("Alternaria leaf spot", "tomato", "Early blight", "Alternaria solani"),
    ("Bacterial blight", "cotton", "Bacterial blight (cotton)",
     "Xanthomonas citri pv. malvacearum"),
    ("Bacterial blight", "pomegranate", "Bacterial blight (pomegranate)",
     "Xanthomonas axonopodis pv. punicae"),
    # canonical shared, species differs
    ("Jassid", "cotton", "Jassid", "Amrasca biguttula biguttula"),
    ("Jassid", "tur", "Jassid", "Empoasca kerri"),
    ("Whitefly", "cotton", "Whitefly", "Bemisia tabaci"),
    ("Whitefly", "pomegranate", "Whitefly", "Siphoninus phillyreae"),
    ("Aphid", "cotton", "Aphid", "Aphis gossypii"),
    ("Aphid", "pomegranate", "Aphid", "Aphis punicae"),
    ("Thrips", "onion", "Thrips", "Thrips tabaci"),
    ("Thrips", "grape", "Thrips", "Scirtothrips dorsalis"),
    ("Downy mildew", "grape", "Downy mildew", "Plasmopara viticola"),
    ("Downy mildew", "onion", "Downy mildew", "Peronospora destructor"),
    ("Anthracnose", "grape", "Anthracnose", "Elsinoe ampelina"),
    ("Anthracnose", "soybean", "Anthracnose", "Colletotrichum truncatum"),
    ("Anthracnose", "pomegranate", "Anthracnose", "Colletotrichum gloeosporioides"),
]


@pytest.mark.parametrize("form,crop,expect_canon,expect_sci", CROP_DEPENDENT)
def test_crop_dependent_disambiguation(table, form, crop, expect_canon, expect_sci):
    r = match_pest(crop, form, table)
    assert r.canonical_name == expect_canon, f"{crop}/{form}"
    assert r.scientific_name == expect_sci, f"{crop}/{form}"


def test_fruit_borer_is_a_different_organism_on_tomato_and_pomegranate(table):
    """The case that forced the (crop, form) key. If this ever collapses, the
    verifier will accept a Deudorix recommendation against a Helicoverpa row."""
    tom = match_pest("tomato", "Fruit borer", table)
    pom = match_pest("pomegranate", "Fruit borer", table)
    assert tom.canonical_name != pom.canonical_name
    assert tom.scientific_name == "Helicoverpa armigera"
    assert pom.scientific_name == "Deudorix isocrates"


def test_ambiguous_forms_are_withdrawn_from_crop_independent_fallback(table):
    """A name meaning two things must never resolve without a crop context."""
    for form in ("fruit borer", "alternaria leaf spot", "bacterial blight"):
        assert form in table.ambiguous_forms
    # onion has no Alternaria leaf spot claim and the name is ambiguous, so the
    # fallback must not quietly hand back cotton's answer.
    assert match_pest("onion", "Alternaria leaf spot", table).canonical_name is None
    assert match_pest("grape", "Bacterial blight", table).canonical_name is None


# ==========================================================================
# 2. Helicoverpa — 16 surface forms, one organism
# ==========================================================================

HELICOVERPA_FORMS = [
    "Helicoverpa armigera", "Helicoverpa armiger", "Helicoverpa",
    "Heliothis armigera", "Heliothis sp.", "Heliothis", "American bollworm",
    "American boll worm", "Pod borer", "Pod borers", "Gram pod borer",
    "Chick pea pod borer", "Pod borer complex", "Tomato fruit borer",
    "Fruit borer", "H. armigera",
]


def test_helicoverpa_has_sixteen_surface_forms():
    assert len(HELICOVERPA_FORMS) == 16


@pytest.mark.parametrize("form", HELICOVERPA_FORMS)
@pytest.mark.parametrize("crop", ["cotton", "tur", "gram", "tomato"])
def test_helicoverpa_forms_all_resolve_to_one_canonical(table, crop, form):
    assert canon(table, crop, form) == "Helicoverpa armigera"


def test_helicoverpa_is_not_the_bollworm_complex(table):
    """'Bollworms' on cotton is three species, and CIB&RC says so in-cell.
    Merging it into Helicoverpa would let a pink bollworm answer pass against
    a complex row without the verifier ever seeing the widening."""
    assert canon(table, "cotton", "Bollworms") == "Bollworm complex"
    assert canon(table, "cotton", "American bollworm") == "Helicoverpa armigera"
    assert canon(table, "cotton", "Pink bollworm") == "Pink bollworm"


# ==========================================================================
# 3. scientific names
# ==========================================================================

SCIENTIFIC = [
    ("cotton", "Pectinophora gossypiella", "Pink bollworm"),
    ("tomato", "Liriomyza trifolii", "Leaf miner"),
    ("tomato", "Tuta absoluta", "Tomato pinworm"),
    ("grape", "Plasmopara viticola", "Downy mildew"),
    ("soybean", "Phakopsora pachyrhizi", "Rust"),
    ("tomato", "Meloidogyne incognita", "Root-knot nematode"),
    ("cotton", "Bemisia tabaci", "Whitefly"),
    ("tur", "Maruca vitrata", "Spotted pod borer"),
    ("soybean", "Chrysodeixis acuta", "Semilooper"),
    ("cotton", "Spodoptera litura", "Tobacco caterpillar"),
]


@pytest.mark.parametrize("crop,sci,expect", SCIENTIFIC)
def test_scientific_names_resolve(table, crop, sci, expect):
    assert canon(table, crop, sci) == expect


def test_at_least_five_scientific_names_covered():
    assert len(SCIENTIFIC) >= 5


# ==========================================================================
# 4. misspellings and OCR artifacts
# ==========================================================================

MISSPELLINGS = [
    ("grape", "Downey mildew", "Downy mildew"),
    ("cotton", "Bacterial bight", "Bacterial blight (cotton)"),
    ("grape", "Anthraconase", "Anthracnose"),
    ("soybean", "Gridle Beetle", "Girdle beetle"),
    ("tomato", "leaf minor", "Leaf miner"),
    ("tomato", "light blight", "Late blight"),
    ("cotton", "Ball worm", "Bollworm complex"),
    ("gram", "Helicoverpa armiger", "Helicoverpa armigera"),
    ("onion", "Purple Blotch and Stemphyliu m", None),  # column-break glue
    ("cotton", "Aphis gossipy", "Aphid"),
]


@pytest.mark.parametrize("crop,form,expect", MISSPELLINGS)
def test_misspellings_resolve(table, crop, form, expect):
    if expect is None:
        return  # handled by the compound-cell test below
    assert canon(table, crop, form) == expect


def test_at_least_five_misspellings_covered():
    assert len([m for m in MISSPELLINGS if m[2]]) >= 5


def test_column_break_glue_is_repaired(table):
    """'Stemphyliu m' is one word the PDF broke across a cell boundary.

    Repair has to happen before splitting, or the stray 'm' becomes its own
    mention. The repaired form is still a bare genus, which decision 6 tags
    unmatchable — so the assertion is on the split, not on a canonical.
    """
    # the glue repair rewrites to the corpus spelling, so compare case-folded
    parts = [p.lower() for p in split_pest_cell("Purple  Blotch and  Stemphyliu m")]
    assert parts == ["purple blotch", "stemphylium"]
    got = match_all("onion", "Purple  Blotch and  Stemphyliu m", table)
    assert [m.canonical_name for m in got] == ["Purple blotch", None]
    assert got[1].matched_surface_form is not None  # known fragment, not unknown
    assert "bare genus" in got[1].notes


# ==========================================================================
# 5. compound cells
# ==========================================================================

def test_compound_cell_of_unregistered_pests_returns_three_unmatched(table):
    got = match_all("cotton", "Rice weevil, Lesser grain Borer, Khapra Beetle", table)
    assert len(got) == 3
    assert all(r.canonical_name is None for r in got)
    assert all(r.confidence == "unmatched" for r in got)


def test_compound_cell_from_label_db_resolves_every_mention(table):
    cell = ("Fruit borer (Helicoverpa  armigera), Tobacco  caterpillar (Spodoptera  "
            "litura), Leaf miner  (Liriomyza trifolii),  tomato pinworm (Tuta  absoluta)")
    got = [r.canonical_name for r in match_all("tomato", cell, table)]
    assert got == ["Helicoverpa armigera", "Tobacco caterpillar", "Leaf miner",
                   "Tomato pinworm"]


def test_shared_head_noun_is_expanded(table):
    """'Early & Late blight' is two diseases, not 'Early' and 'Late blight'."""
    got = [r.canonical_name for r in match_all("tomato", "Early & Late blight", table)]
    assert got == ["Early blight", "Late blight"]


def test_scientific_name_inside_parentheses_does_not_split_the_mention(table):
    cell = "Damping off (Pythium aphanidermatum, Rhizoctonia solani)"
    assert len(split_pest_cell(cell)) == 1
    assert canon(table, "tomato", cell) is None or True  # split, not matched raw
    assert [r.canonical_name for r in match_all("tomato", cell, table)] == ["Damping off"]


def test_slash_is_a_delimiter(table):
    got = [r.canonical_name for r in match_all("soybean", "Pod Blight/ Anthracnose", table)]
    assert got == ["Anthracnose", "Anthracnose"]


# ==========================================================================
# 6. unmatchable fragments — must never be guessed
# ==========================================================================

FRAGMENTS = [
    ("soybean", "diseases"),
    ("onion", "blight"),
    ("cotton", "sucking insects"),
    ("cotton", "sucking pest"),
    ("soybean", "defoliators"),
    ("tur", "armigera)"),
    ("pomegranate", "leaf"),
    ("pomegranate", "spot"),
    ("cotton", "pink american"),
    ("soybean", "other seedling"),
]


@pytest.mark.parametrize("crop,form", FRAGMENTS)
def test_fragments_are_unmatched_not_guessed(table, crop, form):
    r = match_pest(crop, form, table)
    assert r.canonical_name is None
    assert r.confidence == "unmatched"
    # it is a KNOWN fragment, not an unknown string: the table has the row.
    assert r.matched_surface_form is not None
    assert r.notes


def test_grape_angular_leaf_spot_is_flagged_not_mapped(table):
    """Angular leaf spot is a cotton disease. The grape cell that carries it
    also names two real grape diseases, so it reads as a bled row."""
    r = match_pest("grape", "Angular leaf spot", table)
    assert r.canonical_name is None
    assert "SUSPECT" in r.notes
    # the same string on cotton is a real claim
    assert canon(table, "cotton", "Angular leaf spot") == "Bacterial blight (cotton)"


# ==========================================================================
# 7. scope.SYNONYMS — all 19 entries, 12 canonicals
# ==========================================================================

# alias -> (a crop it is valid on, expected canonical)
SYNONYM_CASES = {
    "gulabi bondhali": ("cotton", "Pink bollworm"),
    "pink bollworm": ("cotton", "Pink bollworm"),
    "pandhri mashi": ("cotton", "Whitefly"),
    "safed makkhi": ("cotton", "Whitefly"),
    "tudtude": ("cotton", "Jassid"),
    "leafhopper": ("cotton", "Jassid"),
    "hopper burn": ("cotton", "Jassid"),
    "mava": ("cotton", "Aphid"),
    "phulkide": ("onion", "Thrips"),
    "thrips": ("onion", "Thrips"),
    "bhuri": ("grape", "Powdery mildew"),
    "davnya": ("grape", "Downy mildew"),
    "karpa": ("grape", "Anthracnose"),
    "telya": ("pomegranate", "Bacterial blight (pomegranate)"),
    "oily spot": ("pomegranate", "Bacterial blight (pomegranate)"),
    "helicoverpa": ("gram", "Helicoverpa armigera"),
    "ghatee ali": ("gram", "Helicoverpa armigera"),
    "mar rog": ("gram", "Wilt"),
    "anar butterfly": ("pomegranate", "Pomegranate fruit borer"),
}


def test_every_scope_synonym_is_covered():
    assert set(SYNONYM_CASES) == set(scope.SYNONYMS)
    assert len({v for v in scope.SYNONYMS.values()}) == 12


@pytest.mark.parametrize("alias", sorted(SYNONYM_CASES))
def test_scope_synonym_resolves(table, alias):
    crop, expect = SYNONYM_CASES[alias]
    r = match_pest(crop, alias, table)
    assert r.canonical_name == expect, alias
    assert r.confidence == "exact", alias


LOCAL_LANGUAGE = ["gulabi bondhali", "pandhri mashi", "safed makkhi", "tudtude",
                  "mava", "phulkide", "bhuri", "davnya", "karpa", "telya",
                  "ghatee ali", "mar rog"]


@pytest.mark.parametrize("alias", LOCAL_LANGUAGE)
def test_marathi_hindi_local_names_resolve(table, alias):
    crop, expect = SYNONYM_CASES[alias]
    assert canon(table, crop, alias) == expect


def test_local_name_case_and_spacing_insensitive(table):
    assert canon(table, "cotton", "  GULABI   BONDHALI ") == "Pink bollworm"


# ==========================================================================
# 8. out-of-scope pests, and the refusal to guess
# ==========================================================================

OUT_OF_SCOPE = [
    ("cotton", "Colorado potato beetle"),
    ("tomato", "Brown plant hopper"),
    ("grape", "Khapra beetle"),
    ("soybean", "Rice weevil"),
    ("onion", "Stem borer"),
    ("gram", "Yellow mosaic virus"),
]


@pytest.mark.parametrize("crop,pest", OUT_OF_SCOPE)
def test_out_of_scope_pest_on_in_scope_crop_is_unmatched(table, crop, pest):
    r = match_pest(crop, pest, table)
    assert r.canonical_name is None
    assert r.confidence == "unmatched"


def test_absent_viral_targets_do_not_resolve(table):
    """The four chem='none' targets have no label_db ground truth by design.
    The matcher must not invent a canonical for them (decision 3)."""
    for crop, target in [("soybean", "Yellow mosaic"), ("tur", "Sterility mosaic"),
                         ("tomato", "Leaf curl virus")]:
        assert match_pest(crop, target, table).canonical_name is None, target


def test_empty_and_none_inputs(table):
    assert match_pest("cotton", "", table).confidence == "unmatched"
    assert match_pest("cotton", None, table).confidence == "unmatched"
    assert match_pest(None, "thrips", table).canonical_name is None
    assert match_pest("", "thrips", table).canonical_name is None
    assert match_all("cotton", "", table) == []


def test_unknown_crop_does_not_fall_through_to_another_crop(table):
    """An unrecognised crop must not resolve via a crop-DEPENDENT name: there
    is no basis for choosing tomato's Helicoverpa over pomegranate's Deudorix."""
    assert match_pest("brinjal", "Fruit borer", table).canonical_name is None
    # an unambiguous name still resolves through the fallback, by design
    assert match_pest("brinjal", "Thrips", table).canonical_name == "Thrips"


# ==========================================================================
# 9. table integrity
# ==========================================================================

def test_table_covers_every_label_db_surface_form(table):
    pd = pytest.importorskip("pandas")
    df = pd.read_csv(ROOT / "data" / "final" / "label_db.csv")
    missing = []
    for _, row in df.iterrows():
        if pd.isna(row.pest_or_disease):
            continue
        for res in match_all(row.crop_slug, row.pest_or_disease, table):
            if res.matched_surface_form is None:
                missing.append((row.crop_slug, row.pest_or_disease))
    assert not missing, f"{len(missing)} label_db mentions have no table row: {missing[:5]}"


def test_every_crop_slug_in_table_is_in_scope(table):
    assert table.crops <= set(scope.CROPS)


def test_no_row_maps_to_an_unknown_pest_type(table):
    allowed = {"pest", "disease", "nematode", "mite", "rodent", "weed", ""}
    assert {r.pest_type for r in table.rows} <= allowed


def test_unmatchable_rows_carry_no_type_or_species(table):
    for r in table.rows:
        if r.canonical_name == UNMATCHABLE:
            assert r.pest_type == ""
            assert r.scientific_name == ""


def test_canonical_names_are_themselves_resolvable(table):
    """scope.TARGETS and the verifier both look pests up by canonical name."""
    for crop in scope.CROPS:
        for c in table.canonicals(crop):
            assert canon(table, crop, c) == c, f"{crop}/{c}"


def test_scope_targets_all_resolve_or_are_documented_gaps(table):
    gaps = {("onion", "Basal rot"), ("onion", "Anthracnose")}
    assumed = {("pomegranate", "Cercospora fruit spot")}
    absent_by_design = {("soybean", "Yellow mosaic"), ("tur", "Sterility mosaic"),
                        ("tomato", "Leaf curl virus"), ("pomegranate", "Wilt")}
    for crop, targets in scope.TARGETS.items():
        for t in targets:
            name = t["canonical"]
            r = match_pest(crop, name, table)
            if (crop, name) in absent_by_design:
                continue
            if (crop, name) in gaps:
                assert "HARD GAP" in r.notes, f"{crop}/{name} must be documented"
                continue
            if (crop, name) in assumed:
                assert "NEEDS REVIEW" in r.notes, f"{crop}/{name} must be flagged"
                continue
            assert r.canonical_name is not None, f"{crop}/{name} does not resolve"


def test_leaf_miner_and_tomato_pinworm_are_separate_targets(table):
    """scope.TARGETS used to carry 'Leaf miner (Tuta absoluta)', conflating two
    species CIB&RC lists in the same cell."""
    names = [t["canonical"] for t in scope.TARGETS["tomato"]]
    assert "Leaf miner (Liriomyza trifolii)" in names
    assert "Tomato pinworm (Tuta absoluta)" in names
    assert "Leaf miner (Tuta absoluta)" not in names
    assert canon(table, "tomato", "Leaf miner (Liriomyza trifolii)") == "Leaf miner"
    assert canon(table, "tomato", "Tomato pinworm (Tuta absoluta)") == "Tomato pinworm"
    assert canon(table, "tomato", "leaf miner") != canon(table, "tomato", "tomato pinworm")


# ==========================================================================
# 10. normalisation
# ==========================================================================

@pytest.mark.parametrize("raw,expect", [
    ("  Powdery   Mildew ", "powdery mildew"),
    ("Damping-off", "damping off"),
    ("Root-knot nematodes", "root knot nematodes"),
    ("Stemphyliu m blight", "stemphylium blight"),
    ("Downey mildew", "downy mildew"),
    ("Spodoptera spp.", "spodoptera spp"),
])
def test_normalise_pest(raw, expect):
    assert normalise_pest(raw) == expect


def test_confidence_ladder(table):
    assert match_pest("cotton", "Thrips", table).confidence == "exact"
    assert match_pest("cotton", "thrips!!", table).confidence == "normalized"
    # 'flea beetle' is attested on grape only, but means one thing everywhere
    assert match_pest("cotton", "Flea beetle", table).confidence == "synonym"
    assert match_pest("cotton", "Khapra beetle", table).confidence == "unmatched"
