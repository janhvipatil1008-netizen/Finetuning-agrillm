"""application_method.py — the method qualifier CIB&RC prints in the crop cell.

CIB&RC registers foliar and soil-drench use of the same product on the same
crop for the same pest as SEPARATE claims, with different doses and different
waiting periods. It marks the distinction inside the crop cell:

    'Cotton'                    Jassids   30-40 g/ha    PHI 20
    'Cotton (Soil  drench)'     Jassids   200-250 g/ha  PHI 76

`crop_mapper` tokenises the cell and drops every word that is not a crop name,
by design — it answers "which of the eight crops is this?" and nothing else.
That is correct for its job and wrong for the claim: the qualifier is a
property of the REGISTRATION, not of the crop, and dropping it collapsed those
two Clothianidin rows into one candidate set differing by 6x on dose and 56
days on interval (reports/phase6_stepC_ambiguity_investigation.md, class b1).

So the qualifier gets its own nullable column rather than being folded into
crop_slug. Eight rows carry one today; four of those were already colliding
and four are latent, waiting for a second registration to arrive.

VOCABULARY
==========

Closed, four values, mapped from the phrasings actually in the corpus:

    soil_drench     'Cotton (Soil  drench)', 'Tomato   Soil drench',
                    'Grapes -Soil  drench', 'Grapes (Soil  drench)'
    foliar          'Tomato  Foliar  application'
    seed_treatment  'Soybean  (Seed  Treatment)'
    nursery         'Tomato  nursery', 'Tomato  seedlings'

None means the cell named a crop and nothing else — the ordinary field
application. It is NOT a synonym for foliar: an unqualified row is whatever
the label's default is, and asserting foliar would be inventing a claim.

`nursery` covers both 'nursery' and 'seedlings': both denote application at
the nursery stage before transplanting, and the two rows carrying them are
different products that cannot collide. If a future revision registers both
phrasings for one product, split them then — with evidence.
"""

from __future__ import annotations

import re
from typing import Optional

__all__ = ["METHODS", "extract_method"]

METHODS: tuple[str, ...] = ("soil_drench", "foliar", "seed_treatment", "nursery")

# Ordered: the first pattern to match wins. 'seed treatment' is checked before
# 'seedling' so 'Seed Treatment' cannot be read as a nursery application.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("soil_drench", re.compile(r"soil\s*drench|\bdrench\b", re.I)),
    ("seed_treatment", re.compile(r"seed\s*(?:treatment|dress\w*)", re.I)),
    ("foliar", re.compile(r"foliar", re.I)),
    ("nursery", re.compile(r"\bnursery\b|\bseedlings?\b", re.I)),
]


def extract_method(crop_raw: Optional[str]) -> Optional[str]:
    """Return the canonical application method, or None if the cell has none.

    None means "not stated", never "foliar by default". Inventing a default
    would assert a claim the label does not make — the same failure this
    module exists to undo.
    """
    if not crop_raw:
        return None
    text = re.sub(r"\s+", " ", str(crop_raw))
    for method, rx in _PATTERNS:
        if rx.search(text):
            return method
    return None
