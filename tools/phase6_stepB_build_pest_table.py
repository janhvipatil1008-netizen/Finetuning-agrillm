"""phase6_stepB_build_pest_table.py — writes data/final/pest_synonym_table.csv.

Source of truth for the canonical grouping decided in
reports/phase6_stepA_pest_survey.md and the Phase B decision list. Run it to
regenerate the table; it asserts that every label_db surface form is accounted
for, so a future label_db revision that introduces a new pest name fails the
build rather than silently going unmatched.

Columns: crop_slug, surface_form, canonical_name, pest_type, scientific_name,
source, notes.  One row per (crop_slug, surface_form).
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import scope  # noqa: E402
from pest_matcher import (  # noqa: E402
    UNMATCHABLE,
    _fold,
    normalise_pest,
    split_pest_cell,
    strip_scientific,
)

LABEL_DB = ROOT / "data" / "final" / "label_db.csv"
OUT = ROOT / "data" / "final" / "pest_synonym_table.csv"

# --------------------------------------------------------------------------
# canonical groups: name -> (pest_type, default scientific name)
# --------------------------------------------------------------------------

CANON: dict[str, tuple[str, str]] = {
    # insects
    "Thrips": ("pest", "Thrips tabaci"),
    "Jassid": ("pest", "Amrasca biguttula biguttula"),
    "Whitefly": ("pest", "Bemisia tabaci"),
    "Aphid": ("pest", "Aphis gossypii"),
    "Mealybug": ("pest", "Phenacoccus solenopsis"),
    "Scale insect": ("pest", ""),
    "Red cotton bug": ("pest", "Dysdercus koenigii"),
    "Helicoverpa armigera": ("pest", "Helicoverpa armigera"),
    "Bollworm complex": ("pest", "Helicoverpa armigera / Earias vitella / Pectinophora gossypiella"),
    "Pink bollworm": ("pest", "Pectinophora gossypiella"),
    "Spotted bollworm": ("pest", "Earias vitella"),
    "Spotted pod borer": ("pest", "Maruca vitrata"),
    "Pomegranate fruit borer": ("pest", "Deudorix isocrates"),
    "Tobacco caterpillar": ("pest", "Spodoptera litura"),
    "Semilooper": ("pest", "Chrysodeixis acuta"),
    "Bihar hairy caterpillar": ("pest", "Spilosoma obliqua"),
    "Cutworm": ("pest", "Agrotis spp."),
    "Tomato pinworm": ("pest", "Tuta absoluta"),
    "Leaf miner": ("pest", "Liriomyza trifolii"),
    "Stem fly": ("pest", "Melanagromyza sojae"),
    "Pod fly": ("pest", "Melanagromyza obtusa"),
    "Girdle beetle": ("pest", "Oberea brevis"),
    "Flea beetle": ("pest", "Scelodonta strigicollis"),
    "Grey weevil": ("pest", "Myllocerus spp."),
    "White grub": ("pest", "Holotrichia spp."),
    "Termite": ("pest", "Odontotermes spp."),
    "Red spider mite": ("mite", "Tetranychus urticae"),
    "Root-knot nematode": ("nematode", "Meloidogyne incognita"),
    "Field rat": ("rodent", "Bandicota bengalensis"),
    "House rat": ("rodent", "Rattus rattus"),
    # diseases
    "Powdery mildew": ("disease", "Erysiphe necator"),
    "Downy mildew": ("disease", "Plasmopara viticola"),
    "Grey mildew": ("disease", "Ramularia areola"),
    "Early blight": ("disease", "Alternaria solani"),
    "Late blight": ("disease", "Phytophthora infestans"),
    "Purple blotch": ("disease", "Alternaria porri"),
    "Stemphylium blight": ("disease", "Stemphylium vesicarium"),
    "Bacterial blight (cotton)": ("disease", "Xanthomonas citri pv. malvacearum"),
    "Bacterial blight (pomegranate)": ("disease", "Xanthomonas axonopodis pv. punicae"),
    "Stem blight": ("disease", ""),
    "Alternaria leaf spot": ("disease", "Alternaria spp."),
    "Cercospora leaf spot": ("disease", "Cercospora kikuchii"),
    "Frog eye leaf spot": ("disease", "Cercospora sojina"),
    "Myrothecium leaf spot": ("disease", "Myrothecium roridum"),
    "Target leaf spot": ("disease", "Corynespora cassiicola"),
    "Septoria leaf spot": ("disease", "Septoria lycopersici"),
    "Bacterial leaf spot": ("disease", "Xanthomonas spp."),
    "Leaf spot (unspecified)": ("disease", ""),
    "Cotyledonary spot": ("disease", ""),
    "Grey leaf mould": ("disease", "Fulvia fulva"),
    "Anthracnose": ("disease", "Colletotrichum spp."),
    "Wilt": ("disease", "Fusarium oxysporum"),
    "Root rot": ("disease", "Rhizoctonia solani"),
    "Dry root rot": ("disease", "Macrophomina phaseolina"),
    "Collar rot": ("disease", "Sclerotium rolfsii"),
    "Fusarium root rot": ("disease", "Fusarium spp."),
    "Phytophthora root rot": ("disease", "Phytophthora sojae"),
    "Rhizoctonia seedling blight": ("disease", "Rhizoctonia solani"),
    "Pythium seedling blight": ("disease", "Pythium spp."),
    "Damping off": ("disease", "Pythium aphanidermatum"),
    "Seed and seedling rot": ("disease", ""),
    "Rust": ("disease", "Phakopsora pachyrhizi"),
    "Buckeye rot": ("disease", "Phytophthora nicotianae"),
    "Ring rot": ("disease", ""),
    "Fruit rot": ("disease", ""),
    "Fruit spot": ("disease", "Alternaria alternata"),
    "Boll rot complex": ("disease", ""),
    "Post-harvest rot": ("disease", "Aspergillus niger / Botrytis allii"),
    # scope.TARGETS entry with no label_db ground truth (decision 4)
    "Basal rot": ("disease", "Fusarium oxysporum f.sp. cepae"),
    # scope.TARGETS chem="none" viral targets (phase 9): no label_db rows by
    # definition -- no chemistry is registered against the pathogen. Added so
    # the benchmark's refusal items resolve and C6 grades them.
    "Yellow mosaic": ("disease", "Bean yellow mosaic virus / Mungbean yellow mosaic virus"),
    "Sterility mosaic": ("disease", "Pigeonpea sterility mosaic virus"),
    "Leaf curl virus": ("disease", "Tomato leaf curl virus"),
}

# --------------------------------------------------------------------------
# surface form -> canonical, crop-independent default
# --------------------------------------------------------------------------

BASE: dict[str, str] = {}
# fold-key -> (normalised key, canonical): keeps misspellings as their own
# surface_form rows in the CSV instead of collapsing them into the correction.
RAW_FORMS: dict[str, tuple[str, str]] = {}


def _add(canonical: str, *forms: str) -> None:
    """Register surface forms under a canonical.

    Several forms collapse to one key once normalise_pest corrects a
    misspelling ('helicoverpa armiger' -> 'helicoverpa armigera',
    'heliothis' -> 'helicoverpa'). That is the point of the correction, so a
    repeat is fine as long as it agrees; a repeat that disagrees is a real
    conflict and must fail the build.
    """
    for f in forms:
        key = normalise_pest(f)
        prior = BASE.get(key)
        assert prior in (None, canonical), (
            f"surface form {f!r} -> {key!r} claimed by both {prior!r} and {canonical!r}"
        )
        BASE[key] = canonical
        RAW_FORMS.setdefault(_fold(f), (key, canonical))


# Binomials are registered here rather than left to the in-cell harvest below,
# so a model answering in scientific names resolves on every crop the canonical
# occurs on — not only the crops where CIB&RC happened to print the binomial.
_add("Thrips", "thrips", "thrips tabaci", "scirtothrips dorsalis", "thrips palmi")
_add("Jassid", "jassids", "jassid", "leaf hoppers", "leaf hopper", "leafhopper",
     "amrasca biguttula biguttula", "amrasca biguttula", "amrasca devastans",
     "empoasca kerri")
_add("Whitefly", "whitefly", "whiteflies", "white fly", "white flies",
     "bemisia tabaci", "siphoninus phillyreae")
_add("Aphid", "aphids", "aphid", "aphis", "aphis gossypii", "aphis punicae")
_add("Mealybug", "mealy bug", "mealy bugs", "cotton mealy bug", "mealybug",
     "phenacoccus solenopsis", "phenacoccus spp.")
_add("Scale insect", "scales", "scale insect")
_add("Red cotton bug", "red cotton bug")
_add("Red spider mite", "mites", "mite", "red spider mite", "red spider mites",
     "two spotted spider mite", "spider mite", "two spotted spider mites",
     "tetranychus urticae", "tetranychus spp.")
_add("Helicoverpa armigera",
     "helicoverpa armigera", "helicoverpa armiger", "helicoverpa",
     "heliothis armigera", "heliothis sp", "heliothis", "american bollworm",
     "american boll worm", "pod borer", "pod borers", "gram pod borer",
     "chick pea pod borer", "pod borer complex", "tomato fruit borer",
     "helicoverpa armigera maruca testulalis", "fruit borer", "fruit borers",
     "gram pod borer complex", "american bollworms",
     "h. armigera", "h armigera")
_add("Bollworm complex",
     "bollworms", "bollworm", "boll worms", "boll worm", "bollworm complex",
     "boll worm complex", "boll worms complex", "ball worm")
_add("Pink bollworm", "pink bollworm", "pink boll worm", "pectinophora gossypiella")
_add("Spotted bollworm", "spotted bollworm", "spotted boll worm", "earias vitella",
     "spiny bollworm", "egyptian bollworm", "earias vitelli", "earias insulana")
_add("Spotted pod borer", "spotted pod borer", "maruca vitrata", "maruca spp.")
_add("Pomegranate fruit borer", "pomegranate butterfly", "anar butterfly",
     "deudorix isocrates", "deudorix gossypi")
_add("Tobacco caterpillar", "tobacco caterpillar", "spodoptera litura",
     "spodoptera", "spodoptera spp.", "leaf eating caterpillar",
     "tobacco leaf eating caterpillar", "leaf worm", "tobacco leaf eating caterpillars")
_add("Semilooper", "semilooper", "semi looper", "green semilooper",
     "green semi looper", "chrysodeixis acuta")
_add("Bihar hairy caterpillar", "spilosoma", "spilosoma 6rustak", "spilosoma obliqua")
_add("Cutworm", "cut worm", "cutworm", "agrotis spp.")
_add("Tomato pinworm", "tomato pinworm", "tuta absoluta",
     "tomato pinworm (tuta absoluta)")
_add("Leaf miner", "leaf miner", "liriomyza trifolii", "leafminer",
     "leaf miner (liriomyza trifolii)")
_add("Stem fly", "stem fly", "shoot fly", "melanagromyza sojae", "stemfly")
_add("Pod fly", "pod fly", "melanagromyza obtusa", "melanogromyza obtusa",
     "melanagromyza spp.", "melanogromyza spp.", "melanagromyza sp.")
_add("Girdle beetle", "girdle beetle", "oberea brevis")
_add("Flea beetle", "flea beetle", "scelodonta strigicollis")
_add("Grey weevil", "grey weevil", "leaf weevil", "myllocerus spp.")
_add("White grub", "white grub", "root grub", "holotrichia spp.")
_add("Termite", "termite", "termites", "odontotermes spp.")
_add("Root-knot nematode", "root knot nematode", "root knot nematodes",
     "meloidogyne incognita", "meloidogyne spp.")
_add("Field rat", "field rat", "bandicota bengalensis")
_add("House rat", "indian house rat", "house rat", "rattus rattus")

_add("Powdery mildew", "powdery mildew", "erysiphe necator", "uncinula necator")
_add("Downy mildew", "downy mildew", "plasmopara viticola", "peronospora destructor")
_add("Grey mildew", "grey mildew", "gray mildew", "ramularia areola")
_add("Early blight", "early blight", "alternaria blight", "alternaria solani")
_add("Late blight", "late blight", "tomato late blight", "light blight",
     "phytophthora infestans")
_add("Purple blotch", "purple blotch", "alternaria porri")
_add("Stemphylium blight", "stemphylium blight", "stemphylium leaf blight",
     "stemphylium vesicarium")
_add("Bacterial blight (cotton)", "bacterial leaf blight",
     "angular leaf spot or black arm disease", "black arm",
     "xanthomonas citri pv. malvacearum")
_add("Bacterial blight (pomegranate)", "oily spot", "telya",
     "xanthomonas axonopodis pv. punicae")
_add("Stem blight", "stem blight")
_add("Alternaria leaf spot", "alternaria leaf spot", "alternaria leaf",
     "alternaria leaf blight", "alternaria spp.")
_add("Cercospora leaf spot", "cercospora leaf spot", "cercospora kikuchii",
     "cercospora")
_add("Frog eye leaf spot", "frog eye leaf spot", "cercospora sojina")
_add("Myrothecium leaf spot", "myrothecium leaf spot", "myrothecium roridum")
_add("Target leaf spot", "target leaf spot", "corynespora cassiicola")
_add("Septoria leaf spot", "septoria leaf spot", "septoria leaf blight",
     "septoria lycopersici")
_add("Bacterial leaf spot", "bacterial leaf spot", "bacterial leafspot")
_add("Leaf spot (unspecified)", "leaf spot", "leaf spots", "leaf spot (unspecified)")
_add("Cotyledonary spot", "cotyledonary spot")
_add("Grey leaf mould", "grey leaf mould", "fulvia fulva")
_add("Anthracnose", "anthracnose", "anthracnose disease", "pod blight", "karpa",
     "elsinoe ampelina", "colletotrichum spp.")
_add("Wilt", "wilt", "fusarium wilt", "wilt of tomato", "fungal wilt",
     "seedling wilt", "bacterial wilt", "mar rog", "fusarium oxysporum",
     "ralstonia solanacearum", "fusarium spp.")
_add("Root rot", "root rot", "rhizoctonia root rot", "rhizoctonia solani",
     "rhizoctonia spp.")
_add("Dry root rot", "dry root rot", "charcoal rot", "macrophomina phaseolina")
_add("Collar rot", "collar rot", "sclerotium rolfsii")
_add("Fusarium root rot", "fusarium root rot")
_add("Phytophthora root rot", "phytophthora root rot", "phytophthora sojae")
_add("Rhizoctonia seedling blight", "rhizoctonia seedling blight")
_add("Pythium seedling blight", "pythium seedling blight", "pythium spp.")
_add("Damping off", "damping off", "pythium aphanidermatum")
_add("Seed and seedling rot", "seed rot", "seedling rot", "seedling rot disease",
     "seed born disease", "seedling disease", "seedling blight", "stem rot",
     "seed and seedling rot")
_add("Rust", "rust", "phakopsora pachyrhizi")
_add("Buckeye rot", "buckeye rot", "buck eye rot", "phytophthora nicotianae")
_add("Ring rot", "ring rot")
_add("Fruit rot", "fruit rot", "phytophthora fruit rot")
_add("Fruit spot", "fruit spot", "fruit spots", "alternaria fruit spot",
     "alternaria alternata")
_add("Boll rot complex", "boll rot complex")
_add("Post-harvest rot", "post harvest diseases", "post harvest rot")
_add("Basal rot", "basal rot")

# --------------------------------------------------------------------------
# per-crop overrides — the nine names that mean different organisms by crop
# --------------------------------------------------------------------------

# canonical differs by crop: the crop is load-bearing, and the crop-independent
# fallback in pest_matcher withdraws these automatically.
CROP_CANON: dict[tuple[str, str], str] = {
    ("pomegranate", "fruit borer"): "Pomegranate fruit borer",
    ("pomegranate", "fruit borers"): "Pomegranate fruit borer",
    ("tomato", "alternaria leaf spot"): "Early blight",
    ("tomato", "alternaria leaf"): "Early blight",
    ("cotton", "bacterial blight"): "Bacterial blight (cotton)",
    ("cotton", "bacterial bight"): "Bacterial blight (cotton)",
    ("cotton", "angular leaf spot"): "Bacterial blight (cotton)",
    ("pomegranate", "bacterial blight"): "Bacterial blight (pomegranate)",
}

# canonical is shared, only the species differs by crop.
CROP_SCI: dict[tuple[str, str], str] = {
    ("tur", "Jassid"): "Empoasca kerri",
    ("pomegranate", "Whitefly"): "Siphoninus phillyreae",
    ("pomegranate", "Aphid"): "Aphis punicae",
    ("grape", "Thrips"): "Scirtothrips dorsalis",
    ("pomegranate", "Thrips"): "Scirtothrips dorsalis",
    ("onion", "Downy mildew"): "Peronospora destructor",
    ("grape", "Anthracnose"): "Elsinoe ampelina",
    ("soybean", "Anthracnose"): "Colletotrichum truncatum",
    ("pomegranate", "Anthracnose"): "Colletotrichum gloeosporioides",
    ("tomato", "Anthracnose"): "Colletotrichum coccodes",
    ("cotton", "Alternaria leaf spot"): "Alternaria macrospora",
    ("tomato", "Wilt"): "Fusarium oxysporum f.sp. lycopersici",
    ("soybean", "Cercospora leaf spot"): "Cercospora kikuchii",
}

# species stated on one surface form only.
FORM_SCI: dict[tuple[str, str], str] = {
    ("tomato", "bacterial wilt"): "Ralstonia solanacearum",
    ("tomato", "ralstonia solanacearum"): "Ralstonia solanacearum",
    ("tur", "leaf hopper"): "Empoasca kerri",
    ("cotton", "alternaria leaf blight"): "Alternaria macrospora",
}

CROP_DEPENDENT_NAMES = [
    "Fruit borer", "Alternaria leaf spot", "Bacterial blight", "Jassid",
    "Whitefly", "Aphid", "Thrips", "Downy mildew", "Anthracnose",
]

# --------------------------------------------------------------------------
# fragments — real label_db text that is not a pest name (decision 6)
# --------------------------------------------------------------------------

FRAGMENTS: dict[str, str] = {
    # truncated cells
    "diseases": "truncated cell",
    "seedling": "truncated cell",
    "rot": "truncated cell",
    "spot": "truncated cell",
    "seed": "truncated cell",
    "leaf": "truncated cell",
    "other seedling": "truncated cell",
    "armigera)": "truncated cell",
    "blight": "bare head noun, no pathogen named",
    "stemphylium": "bare genus, no disease named",
    # dropped delimiters in the source PDF
    "whitefly aphids": "missing delimiter",
    "aphids jassids white fly": "missing delimiter",
    "thrips white fly": "missing delimiter",
    "stem fly girdle beetle": "missing delimiter",
    "stem fly girdle beetle whitefly": "missing delimiter",
    "downy mildew anthracnose": "missing delimiter",
    "bacterial blight alternaria": "missing delimiter",
    "spodoptera spp. semilooper": "missing delimiter",
    "pink american": "missing delimiter (Pink, American bollworm)",
    "spodoptera litura helicoverpa armigera early blight leaf spot": "missing delimiter",
    "mealy bugs (phenococcus solenopsis": "unbalanced parenthesis",
    # generic categories, not organisms
    "sucking insects": "generic category, not an organism",
    "sucking pest": "generic category, not an organism",
    "defoliators": "generic category, not an organism",
}

# decision 6: flag for manual check, do not map. Angular leaf spot is a cotton
# disease; the cell also names downy mildew and anthracnose, which are grape
# diseases, so this looks like a bled row rather than a real grape claim.
SUSPECT: dict[tuple[str, str], str] = {
    ("grape", "angular leaf spot"):
        "SUSPECT: angular leaf spot is not a grape disease; likely bled cell, "
        "check source_page before treating as grape ground truth",
}

# --------------------------------------------------------------------------
# scope.SYNONYMS -> canonical, and the crops each alias is valid on
# --------------------------------------------------------------------------

SYN_CROPS: dict[str, list[str]] = {
    "gulabi bondhali": ["cotton"],
    "pink bollworm": ["cotton"],
    "pandhri mashi": ["cotton", "tomato", "soybean", "pomegranate"],
    "safed makkhi": ["cotton", "tomato", "soybean", "pomegranate"],
    "tudtude": ["cotton", "tomato", "soybean", "tur", "grape"],
    "leafhopper": ["cotton", "tomato", "soybean", "tur", "grape"],
    "hopper burn": ["cotton", "tomato", "soybean", "tur", "grape"],
    "mava": ["cotton", "tomato", "soybean", "pomegranate"],
    "phulkide": ["cotton", "onion", "tomato", "grape", "pomegranate"],
    "thrips": ["cotton", "onion", "tomato", "grape", "pomegranate"],
    "bhuri": ["grape", "tomato"],
    "davnya": ["grape", "onion"],
    "karpa": ["grape", "pomegranate", "soybean", "tomato"],
    "telya": ["pomegranate"],
    "oily spot": ["pomegranate"],
    "helicoverpa": ["cotton", "tur", "gram", "tomato", "soybean"],
    "ghatee ali": ["tur", "gram", "tomato"],
    "mar rog": ["gram", "tur", "tomato", "cotton"],
    "anar butterfly": ["pomegranate"],
}

# canonical for each scope.SYNONYMS value, where it differs from the value.
SYN_CANON = {
    "Pod borer": "Helicoverpa armigera",
    "Fruit borer": "Pomegranate fruit borer",   # 'anar butterfly', pomegranate only
    "Bacterial blight": "Bacterial blight (pomegranate)",  # 'telya' / 'oily spot'
}

# scope.TARGETS canonical strings that must resolve even though CIB&RC never
# prints them verbatim.
TARGET_EXTRA: dict[tuple[str, str], tuple[str, str]] = {
    ("cotton", "bacterial blight"): ("Bacterial blight (cotton)", "scope.TARGETS canonical"),
    ("grape", "mealybug"): ("Mealybug", "scope.TARGETS canonical"),
    ("gram", "cutworm"): ("Cutworm", "scope.TARGETS canonical"),
    ("tomato", "leaf miner (liriomyza trifolii)"): ("Leaf miner", "scope.TARGETS canonical"),
    ("tomato", "tomato pinworm (tuta absoluta)"): ("Tomato pinworm", "scope.TARGETS canonical"),
    ("onion", "basal rot"): ("Basal rot", "HARD GAP: scope.TARGETS target with no label_db row; verifier returns UNLISTED"),
    ("onion", "anthracnose"): ("Anthracnose", "HARD GAP: scope.TARGETS target with no label_db row; verifier returns UNLISTED"),
    # Phase A flagged this as needing a call and the Phase B decision list did
    # not cover it. label_db prints 'Cercospora leaf spot' (3 rows) and 'fruit
    # spot' (4) on pomegranate but never the compound name, so this maps to the
    # Cercospora group on the assumption they are one target. Confirm.
    ("pomegranate", "cercospora fruit spot"): (
        "Cercospora leaf spot",
        "ASSUMPTION - NEEDS REVIEW: scope.TARGETS name absent from label_db; "
        "mapped to Cercospora leaf spot, which label_db does print",
    ),
    # scope.TARGETS chem="none" viral targets (phase 9 benchmark): CIB&RC
    # never prints them because nothing is registered against the pathogen.
    # Farmer surface forms included so KCC-register queries resolve.
    ("soybean", "yellow mosaic virus"): ("Yellow mosaic", "scope.py chem=none target; no label_db rows"),
    ("soybean", "yellow mosaic"): ("Yellow mosaic", "scope.py chem=none target; no label_db rows"),
    ("soybean", "pila mosaic"): ("Yellow mosaic", "farmer-facing alias"),
    ("soybean", "YMV"): ("Yellow mosaic", "farmer-facing abbreviation"),
    ("tur", "sterility mosaic virus"): ("Sterility mosaic", "scope.py chem=none target; vector is Aceria cajani mite, not aphid"),
    ("tur", "sterility mosaic"): ("Sterility mosaic", "scope.py chem=none target; vector is Aceria cajani mite, not aphid"),
    ("tur", "SMV"): ("Sterility mosaic", "farmer-facing abbreviation"),
    ("tur", "bandhi marg"): ("Sterility mosaic", "farmer-facing alias"),
    ("tomato", "leaf curl virus"): ("Leaf curl virus", "scope.py chem=none target; whitefly vector"),
    ("tomato", "leaf curl"): ("Leaf curl virus", "scope.py chem=none target; whitefly vector"),
    ("tomato", "patti curl"): ("Leaf curl virus", "farmer-facing alias"),
    ("tomato", "curl virus"): ("Leaf curl virus", "farmer-facing alias"),
}

_BINOMIAL = re.compile(r"^[A-Z][a-z]+(?:\s+(?:[a-z]+|spp\.|sp\.|f\.sp\.|pv\.|var\.)){1,3}$")


# FRAGMENTS is written in readable surface text; resolve() is handed a
# normalised key, so index it the same way.
FRAGMENTS = {normalise_pest(k): v for k, v in FRAGMENTS.items()}
SUSPECT = {(c, normalise_pest(f)): v for (c, f), v in SUSPECT.items()}
CROP_CANON = {(c, normalise_pest(f)): v for (c, f), v in CROP_CANON.items()}
FORM_SCI = {(c, normalise_pest(f)): v for (c, f), v in FORM_SCI.items()}


def resolve(crop: str, form_key: str) -> str | None:
    if (crop, form_key) in SUSPECT:
        return UNMATCHABLE
    if form_key in FRAGMENTS:
        return UNMATCHABLE
    if (crop, form_key) in CROP_CANON:
        return CROP_CANON[(crop, form_key)]
    return BASE.get(form_key)


def sci_for(crop: str, canonical: str, form_key: str) -> str:
    if (crop, form_key) in FORM_SCI:
        return FORM_SCI[(crop, form_key)]
    if (crop, canonical) in CROP_SCI:
        return CROP_SCI[(crop, canonical)]
    return CANON[canonical][1] if canonical in CANON else ""


def main() -> None:
    df = pd.read_csv(LABEL_DB)

    # ---- 1. every (crop, surface form) attested in label_db ---------------
    observed: dict[tuple[str, str], str] = {}   # (crop, key) -> original text
    sci_observed: dict[tuple[str, str], str] = {}
    for _, r in df.iterrows():
        if pd.isna(r.pest_or_disease):
            continue
        crop = r.crop_slug
        for mention in split_pest_cell(r.pest_or_disease):
            common, sci = strip_scientific(mention)
            if common:
                observed.setdefault((crop, _fold(common)), common)
            if sci and _BINOMIAL.match(sci.strip()):
                sci_observed.setdefault((crop, _fold(sci)), sci.strip())

    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def emit(crop, surface, canonical, source, notes=""):
        key = (crop, _fold(surface))
        if key in seen:
            return
        seen.add(key)
        nkey = normalise_pest(surface)
        if canonical == UNMATCHABLE:
            rows.append({
                "crop_slug": crop, "surface_form": surface,
                "canonical_name": UNMATCHABLE, "pest_type": "",
                "scientific_name": "", "source": source, "notes": notes,
            })
            return
        ptype = CANON[canonical][0]
        rows.append({
            "crop_slug": crop, "surface_form": surface,
            "canonical_name": canonical, "pest_type": ptype,
            "scientific_name": sci_for(crop, canonical, nkey),
            "source": source, "notes": notes,
        })

    unmapped = []
    for (crop, _foldkey), original in sorted(observed.items()):
        key = normalise_pest(original)
        canonical = resolve(crop, key)
        if canonical is None:
            unmapped.append((crop, original))
            continue
        note = ""
        if (crop, key) in SUSPECT:
            note = SUSPECT[(crop, key)]
        elif key in FRAGMENTS:
            note = f"unmatchable: {FRAGMENTS[key]}"
        elif (crop, key) in CROP_CANON:
            note = "crop-dependent: canonical differs by crop"
        elif canonical in CANON and (crop, canonical) in CROP_SCI:
            note = "crop-dependent: species differs by crop"
        emit(crop, original, canonical, "label_db", note)

    if unmapped:
        print("UNMAPPED label_db surface forms:")
        for c, o in unmapped:
            print(f"   {c:12s} {o!r}")
        raise SystemExit("build aborted: every label_db form must be mapped")

    # ---- 2. scientific names printed in-cell ------------------------------
    for (crop, _foldkey), original in sorted(sci_observed.items()):
        key = normalise_pest(original)
        canonical = resolve(crop, key)
        if canonical is None or canonical == UNMATCHABLE:
            continue
        emit(crop, original, canonical, "label_db", "scientific name")

    # ---- 3. scope.SYNONYMS ------------------------------------------------
    for alias, value in scope.SYNONYMS.items():
        canonical = SYN_CANON.get(value, value)
        assert canonical in CANON, f"scope.SYNONYMS value {value!r} -> unknown canonical"
        for crop in SYN_CROPS[alias]:
            emit(crop, alias, canonical, "scope_synonyms",
                 "farmer-facing alias from scope.SYNONYMS")

    # ---- 4. scope.TARGETS canonicals CIB&RC never prints ------------------
    for (crop, form), (canonical, note) in TARGET_EXTRA.items():
        emit(crop, form, canonical, "manual", note)

    # ---- 5. every canonical name resolvable on every crop it occurs on ----
    per_crop_canon: dict[str, set[str]] = {}
    for r in rows:
        if r["canonical_name"] != UNMATCHABLE:
            per_crop_canon.setdefault(r["crop_slug"], set()).add(r["canonical_name"])
    for crop, canons in sorted(per_crop_canon.items()):
        for c in sorted(canons):
            emit(crop, c, c, "manual", "canonical name as surface form")

    # ---- 6. cross-crop aliases for unambiguous canonicals -----------------
    # Every base surface form is emitted on every crop where its canonical is
    # already attested, so a model naming a pest in a form CIB&RC happens not
    # to print for that crop still resolves.
    for raw, (key, canonical) in sorted(RAW_FORMS.items()):
        for crop, canons in sorted(per_crop_canon.items()):
            if canonical in canons and resolve(crop, key) == canonical:
                emit(crop, raw, canonical, "manual", "variant form")

    rows.sort(key=lambda r: (r["crop_slug"], r["canonical_name"], r["surface_form"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "crop_slug", "surface_form", "canonical_name", "pest_type",
            "scientific_name", "source", "notes"])
        w.writeheader()
        w.writerows(rows)

    # ---- report -----------------------------------------------------------
    canon_used = {r["canonical_name"] for r in rows if r["canonical_name"] != UNMATCHABLE}
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  rows                     : {len(rows)}")
    print(f"  canonical groups          : {len(canon_used)}")
    print(f"  label_db surface forms    : {len(observed)} (crop,form) pairs")
    print(f"  scientific-name rows      : {sum(1 for r in rows if r['notes'] == 'scientific name')}")
    print(f"  scope_synonyms rows       : {sum(1 for r in rows if r['source'] == 'scope_synonyms')}")
    print(f"  manual rows               : {sum(1 for r in rows if r['source'] == 'manual')}")
    print(f"  UNMATCHABLE rows          : {sum(1 for r in rows if r['canonical_name'] == UNMATCHABLE)}")
    print()
    print("  by source:", dict(Counter(r["source"] for r in rows)))
    print("  by type  :", dict(Counter(r["pest_type"] for r in rows if r["pest_type"])))
    print()
    for crop in scope.CROPS:
        cc = {r["canonical_name"] for r in rows
              if r["crop_slug"] == crop and r["canonical_name"] != UNMATCHABLE}
        n = sum(1 for r in rows if r["crop_slug"] == crop)
        print(f"  {crop:12s} {len(cc):3d} canonical groups, {n:4d} rows")

    unused = sorted(set(CANON) - canon_used)
    if unused:
        print(f"\n  canonical groups defined but never used: {unused}")


if __name__ == "__main__":
    main()
