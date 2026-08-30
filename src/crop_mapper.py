"""
crop_mapper.py — a raw CIB&RC crop cell -> scope.py slugs.

Pure. No I/O, no dependency on the surrounding row. Dose parsing, PHI
resolution and label_db assembly are separate steps and deliberately absent.


WHY TOKENS AND NOT SUBSTRINGS
=============================

This is the whole design. Substring matching over this vocabulary is not
merely imprecise, it is wrong in both directions, and it was tried first:

    'Turmeric'                          contains 'tur'   -> NOT tur
    'Floriculture (Carnation & Gerbera)' contains 'tur'  -> NOT tur
    'Black gram'                        contains 'gram'  -> urad, NOT gram
    'Green gram'                        contains 'gram'  -> moong, NOT gram
    'Cow pea' / 'Green pea'             contain  'pea'   -> NOT tur
    'Pigeonpea'                         contains no space -> IS tur
    'Chickpea'                          contains no space -> IS gram

so the module tokenises, splits the glued compounds CIB&RC prints both ways
('Pigeonpea'/'Pigeon pea', 'Blackgram'/'Black gram'), consumes two-word crop
names BEFORE any single-word rule, and only then matches bare words. 'Red
gram' is consumed as tur before the bare 'gram' rule can ever see the word.

Getting one of these backwards puts a label claim for the wrong crop in front
of a farmer. `reports/phase3_fallback_diagnosis.md` already flagged the
gram/tur overlap as unresolved; this module is where it gets resolved, and
tests/test_crop_mapper.py pins every near miss individually.


RETURN TYPE — a deviation from the task spec, stated deliberately
=================================================================

The spec asked for `map_crop(raw: str) -> CropResult` and, in the same
breath, that multi-crop cells return a LIST of CropResults. Those cannot both
hold. Returning `CropResult | list[CropResult]` would push an isinstance
check into every caller and guarantee that someone eventually forgets it.

So `map_crop` ALWAYS returns a list:

    'Cotton'        -> [CropResult(slug='cotton', ...)]
    'Wheat, Gram'   -> [CropResult(slug='gram', multi_crop_split=True, ...)]
    'Brinjal'       -> [CropResult(slug=None, ...)]      # out of scope
    ''              -> [CropResult(slug=None, ...)]      # blank

One element is the common case; a caller wanting the single slug reads
`results[0].slug`. Nothing silently disappears: an out-of-scope or blank cell
still returns one result carrying slug=None, so a caller iterating results
cannot mistake "no crop" for "nothing happened".


DECISIONS ENCODED HERE (from the Step A review)
================================================

1. MULTI-CROP CELLS split into one result per IN-SCOPE crop. Out-of-scope
   crops named in the same cell get no result — 'Rice (Paddy) &cotton' yields
   cotton only, not rice. Each result carries multi_crop_split=True so Step 5
   knows the cell was not crop-exclusive.

2. SYNONYM STACKING IS NOT MULTI-CROP. 'Pigeon pea or Red gram (Arhar/Tur)'
   names one crop four ways and resolves to a single tur result with
   multi_crop_split=False. The separator characters in it are not a signal.

3. PEST-BLED CELLS map their crop normally and set pest_bled=True. The crop
   is unambiguous ('Pigeon Pea Helicoverpa armiger' is still tur); it is the
   row's pest_or_disease field that is suspect. This module does not touch
   that field — Step 5 verifies it.

4. GENERIC CATEGORIES ARE OUT OF SCOPE. 'Vegetables', 'Pulses', 'Cucurbits',
   'Dry Fruits, Nuts Spices & Oil Seeds' name no specific crop and are not
   expanded into the slugs they might cover.

5. BLANK CELLS return slug=None. 219 of them exist; they are excluded from
   label_db, not investigated further.

6. PROSE CELLS THAT MERELY MENTION A CROP are not label claims. 'For rodent
   control in field, storage and crops like rice, soybean and coconut)' is a
   rodenticide row whose crop column holds a sentence; it names soybean but
   makes no soybean claim. Flagged not_a_crop_cell=True and given slug=None
   so it drops out rather than manufacturing a soybean recommendation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from scope import CROPS

__all__ = ["map_crop", "CropResult", "SLUGS"]

SLUGS = tuple(CROPS)


@dataclass(frozen=True)
class CropResult:
    """One crop a cell resolved to. slug is None for out-of-scope or blank."""
    slug: Optional[str]
    raw: str
    multi_crop_split: bool = False
    pest_bled: bool = False
    not_a_crop_cell: bool = False

    @property
    def in_scope(self) -> bool:
        return self.slug is not None


# --------------------------------------------------------------------------
# tokenisation
# --------------------------------------------------------------------------

# Compounds CIB&RC prints both glued and spaced. Split so token matching sees
# the same two words either way. Every entry here is load-bearing: without
# the 'blackgram' split, 'Blackgram' would tokenise to one unknown word and
# fall through to out-of-scope by luck rather than by rule — and without the
# 'pigeonpea' split, a real tur row would be dropped.
_GLUED = {
    "pigeonpea": "pigeon pea", "pigeonpeas": "pigeon pea",
    "blackgram": "black gram", "blackgrams": "black gram",
    "greengram": "green gram", "greengrams": "green gram",
    "redgram": "red gram", "bengalgram": "bengal gram",
    "chickpea": "chick pea", "chickpeas": "chick pea",
    "soyabean": "soya bean", "soybean": "soya bean",
    "soyabeans": "soya bean", "soybeans": "soya bean",
    "urdbean": "urd bean", "urdbeans": "urd bean",
    "mungbean": "mung bean", "mungbeans": "mung bean",
    "cowpea": "cow pea", "cowpeas": "cow pea",
    "greenpea": "green pea", "greenpeas": "green pea",
    "frenchbean": "french bean", "frenchbeans": "french bean",
    "kidneybean": "kidney bean", "kidneybeans": "kidney bean",
    "clusterbean": "cluster bean", "clusterbeans": "cluster bean",
    "horsegram": "horse gram", "pearlmillet": "pearl millet",
    "sugarbeet": "sugar beet",
}


def _tokens(raw: str) -> list[str]:
    """Lowercase alphabetic tokens, OCR-repaired and compound-split."""
    words = re.sub(r"[^a-z]+", " ", (raw or "").lower()).split()

    # OCR splits the leading capital off its word: 'T omato', 'G rapes',
    # 'B anana'. A one-letter token followed by another token is that.
    merged: list[str] = []
    i = 0
    while i < len(words):
        if len(words[i]) == 1 and i + 1 < len(words):
            merged.append(words[i] + words[i + 1])
            i += 2
        else:
            merged.append(words[i])
            i += 1

    out: list[str] = []
    for tok in merged:
        out.extend(_GLUED.get(tok, tok).split())
    return out


# --------------------------------------------------------------------------
# matching rules
# --------------------------------------------------------------------------

# Two-word crop names, consumed before any single-word rule. A None target is
# a real crop that is simply out of scope; matching it still CONSUMES the
# words, which is the entire point — it is what stops the bare 'gram' rule
# from claiming the 'gram' in 'Black gram'.
_PHRASES: tuple[tuple[tuple[str, ...], Optional[str]], ...] = (
    # --- excluded pulses that collide with in-scope names
    (("black", "gram"), None),      # urad
    (("green", "gram"), None),      # moong
    (("horse", "gram"), None),      # kulthi
    (("cow", "gram"), None),
    (("urd", "bean"), None),
    (("mung", "bean"), None),
    (("cow", "pea"), None),
    (("green", "pea"), None),
    (("french", "bean"), None),
    (("kidney", "bean"), None),
    (("cluster", "bean"), None),
    (("pearl", "millet"), None),
    (("sugar", "beet"), None),
    # --- in-scope two-word names
    (("red", "gram"), "tur"),
    (("pigeon", "pea"), "tur"),
    (("bengal", "gram"), "gram"),
    (("chick", "pea"), "gram"),
    (("soya", "bean"), "soybean"),
)

# Single words, applied only to tokens no phrase consumed.
_WORDS: dict[str, str] = {
    "cotton": "cotton", "kapas": "cotton",
    "tur": "tur", "toor": "tur", "arhar": "tur",
    "gram": "gram", "chana": "gram",
    "onion": "onion", "onions": "onion", "kanda": "onion",
    "tomato": "tomato", "tomatoes": "tomato", "tamatar": "tomato",
    "grape": "grape", "grapes": "grape", "grapevine": "grape",
    "draksha": "grape",
    "pomegranate": "pomegranate", "pomegranates": "pomegranate",
    "anar": "pomegranate", "dalimb": "pomegranate",
}

# Crop head-words that are NOT in scope, used only to tell a genuinely
# multi-crop cell ('Wheat, Gram') from synonym stacking ('Red gram (Tur or
# Arhar)'). Curated from the out-of-scope population of the corpus; being
# incomplete makes a cell look single-crop, never mis-slugs it.
_OTHER_CROPS = frozenset("""
    apple apples bajra bamboo banana barley barely beans bean beet betel bhindi
    brinjal cabbage capsicum cardamom carnation carnations carrot cashew caster
    castor cauliflower cherries cherry chili chilies chilli chillies chilly
    citrus coconut coffee coriander corn cucumber cucurbits cumin garlic gerbera
    gherkin gherkins ginger gourd groundnut guar guava jowar jute lime maize
    mandarin mandarins mango millet millets moong mustard okra opium ornamental
    paddy papaya pea peach peaches pear peas pepper plum potato pulses ragi
    rapeseed rice rose roses rubber safflower sesamum sorghum sugarcane
    sunflower tapioca tea teak tobacco tuber tuberose turmeric urid urd
    vegetables walnut watermelon wheat
""".split())

# The crop cell absorbed pest/disease text from the neighbouring column.
_PEST_BLED = re.compile(
    r"helicoverpa|heliothis|bollworm|whitefly|spodoptera|diamond\s*back"
    r"|\bblast\b|sheath\s*blight|alternaria|\bthrips\b|\baphid", re.IGNORECASE)

# The cell holds a sentence, not a crop name. Narrow on purpose: it only has
# to catch prose that would otherwise match an in-scope word.
_NOT_A_CROP_CELL = re.compile(
    r"\brodents?\b|crops\s+like|residential|go\s*downs?|godowns?|premises"
    r"|construction|poultry\s+farm|public\s+health", re.IGNORECASE)


def _slugs(tokens: list[str]) -> tuple[list[str], list[bool]]:
    """Every in-scope slug these tokens name, plus which tokens were used.

    The consumed mask is what keeps the multi-crop test honest. 'pea' and
    'bean' are ordinary out-of-scope crop words, but inside 'Pigeon pea' and
    'Soya bean' they belong to an in-scope name — so the multi-crop test must
    ignore any token an in-scope rule already claimed, or every soybean and
    pigeon-pea cell would flag itself as multi-crop.
    """
    consumed = [False] * len(tokens)
    found: list[str] = []

    def add(slug: str) -> None:
        if slug not in found:
            found.append(slug)

    for phrase, slug in _PHRASES:
        n = len(phrase)
        for i in range(len(tokens) - n + 1):
            if any(consumed[i:i + n]):
                continue
            if tuple(tokens[i:i + n]) == phrase:
                for j in range(i, i + n):
                    consumed[j] = True
                if slug:
                    add(slug)

    for i, tok in enumerate(tokens):
        if not consumed[i] and tok in _WORDS:
            consumed[i] = True
            add(_WORDS[tok])
    return found, consumed


def map_crop(raw: str) -> list[CropResult]:
    """Map one CIB&RC crop cell to scope.py slugs.

    Always returns a list — see the module docstring for why. One element per
    in-scope crop named; a single element with slug=None when the cell is
    blank, out of scope, or prose that merely mentions a crop.

    Never raises. `raw` is preserved verbatim on every result.
    """
    text = raw if isinstance(raw, str) else ("" if raw is None else str(raw))

    if not text.strip():
        return [CropResult(slug=None, raw=text)]

    if _NOT_A_CROP_CELL.search(text):
        # A sentence, not a crop name. Dropped rather than allowed to
        # manufacture a label claim out of a crop it happens to mention.
        return [CropResult(slug=None, raw=text, not_a_crop_cell=True)]

    tokens = _tokens(text)
    slugs, consumed = _slugs(tokens)
    pest_bled = bool(_PEST_BLED.search(text))

    if not slugs:
        return [CropResult(slug=None, raw=text, pest_bled=pest_bled)]

    # A cell is genuinely multi-crop when it names more than one in-scope
    # slug, or names an in-scope slug alongside a LEFTOVER different crop.
    # Synonym stacking trips neither test: 'Red gram (Tur or Arhar)' resolves
    # to one slug and every crop token in it was consumed by that slug.
    names_other = any(
        tok in _OTHER_CROPS for tok, used in zip(tokens, consumed) if not used
    )
    multi = len(slugs) > 1 or names_other

    return [
        CropResult(slug=s, raw=text, multi_crop_split=multi, pest_bled=pest_bled)
        for s in slugs
    ]
