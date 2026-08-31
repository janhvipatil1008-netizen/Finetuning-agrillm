"""formulation_resolver.py — resolves dose_formulation's missing unit from
the formulation code printed in active_ingredient.

CONTEXT (see reports/phase5_stepA_formulation_survey.md for the full survey
this module implements): dose_formulation's header is "(g/ml)" — genuinely
ambiguous between mass and volume until the formulation type is known
(dose_parser.py rule 8). parse_dose() correctly refuses to guess and returns
NEEDS_UNIT for every bare number in that column. The formulation type itself
— printed as a CIB&RC code such as "SC" or "WP" at the tail of
active_ingredient — resolves the ambiguity: liquid formulations dose in ml,
solid formulations dose in g. This module extracts that code and classifies
it. It does not parse doses; dose_parser.parse_dose still does that, called
afterwards with the unit this module returns as default_unit.

FIVE HAZARDS the extraction has to survive (each is real, found in-corpus):

1. Chemical-name fragments that look like codes. "Fosetyl-AL" and
   "PYRACLOSTROBIN AL" are not formulation code AL — AL never appears as a
   CIB&RC formulation code in this corpus, and the true code sits later in
   the same string ("WDG", "WP"). AL is simply excluded from the vocabulary.

2. Strain/accession/potency tails outrank the real code if you take the last
   uppercase run naively. 'Verticillium lecanii 1.15%WP, (1x108 CFU/gm min)
   Strain – AS MEGH-VL Accession No – MCC-1028' — the actual code is WP;
   'AS' further right is part of a strain designation, not a rate. The tail
   is cut off (at the first strain/accession/CFU/potency/serotype marker)
   before code extraction runs.

3. Bare single letters are noise, not codes. 'g/L' ('grams per litre'), '(P)
   Ltd', 'Polyoxin D', 'Spodoptera Unit' each contain a lone letter that is
   never itself a CIB&RC formulation code, so single-letter tokens are
   simply never in the vocabulary.

4. Codes glue to '%' and to the numeral with no separating space ('75%SP',
   '10.00%EC'), so the boundary condition is "not a letter", not "start of
   word" — a code is only accepted where neither neighbouring character is
   itself a letter.

5. 'g/L' formulation glue: 'Chlorfenapyr 240 g/LSC' and 'Afidopyropen50g/LDC'
   print the concentration ('240 g/L', '50 g/L') fused directly onto the
   code ('SC', 'DC'), so the code's own leading letter is swallowed by the
   'L' of 'g/L' and the boundary check in (4) can never see it. Rather than
   loosen the boundary rule — which would let real code fragments bleed into
   neighbouring text — 'g/L' immediately after a number is treated as
   liquid-formulation evidence on its own, independent of whatever code
   follows it.

Mixed case ('Dc', 'W/W') is normalised away by uppercasing before any of the
above runs.
"""

from __future__ import annotations

import re
from typing import Optional

from schema import Unit

__all__ = ["resolve_formulation_unit", "CODE_CLASS"]

# --------------------------------------------------------------------------
# vocabulary — exactly the codes confirmed by the Phase A survey. Nothing
# else is ever accepted, so a code invented by a future PDF revision comes
# back None (safe) rather than being silently guessed.
# --------------------------------------------------------------------------

_LIQUID_CODES = {
    "SC", "EC", "AS", "FS", "ZC", "SE", "OD", "SL", "CS", "DC",
    "AF", "ES", "EW", "LF", "ME", "OS", "WSL",
}
_SOLID_CODES = {
    "WP", "WG", "WS", "WDG", "SP", "SG", "DP", "DF", "GR", "CG",
    "WSP", "CB", "DS", "RB",
}

CODE_CLASS: dict[str, Unit] = {
    **{c: "ml" for c in _LIQUID_CODES},
    **{c: "g" for c in _SOLID_CODES},
}

# Longest codes first so a short code cannot pre-empt a longer one at the
# same start position before the boundary check gets a chance to run.
_VOCAB_RX = re.compile(
    r"(?<![A-Z])(" + "|".join(sorted(CODE_CLASS, key=len, reverse=True)) + r")(?![A-Z])"
)

# Hazard 2: strain/accession/potency tails. Cut here before scanning for a
# code so a designation like "Strain – AS MEGH-VL" never outranks the real
# code earlier in the string.
_TAIL_RX = re.compile(
    r"\b(strain|accession|cfu|potency|serotype|in\s+house|spore/|pob|iu/|ltd)\b",
    re.IGNORECASE,
)

# Hazard 5: "<number> g/L" glued straight onto a code swallows the code's
# leading letter ('LSC', 'LDC'). The g/L notation is itself liquid evidence,
# so it is checked before — and independently of — the vocabulary scan.
_G_PER_L_RX = re.compile(r"\d\s*G\s*/\s*L")

# Spelled-out formulation words that never abbreviate to a bare code in this
# corpus ("Liquid Formulation", "L.F", "Tablet").
_SPELLED_LIQUID_RX = re.compile(r"LIQUID\s+FORMULATION|\bL\.F\b")
_SPELLED_SOLID_RX = re.compile(r"\bTABLET\b")


def resolve_formulation_unit(active_ingredient: Optional[str]) -> Optional[Unit]:
    """Return 'ml' for a liquid formulation, 'g' for a solid one, or None if
    no CIB&RC formulation code can be confidently identified in the string.

    None is the correct answer for a genuinely code-less active_ingredient
    (a bare AI name, a pheromone rope, a PDF extraction defect) — the caller
    must not guess a unit for those; the dose stays NEEDS_UNIT.
    """
    if not active_ingredient or not active_ingredient.strip():
        return None

    text = active_ingredient.upper()

    tail = _TAIL_RX.search(text)
    head = text[: tail.start()] if tail else text

    if _G_PER_L_RX.search(head):
        return "ml"

    hits = _VOCAB_RX.findall(head)
    if hits:
        return CODE_CLASS[hits[-1]]

    if _SPELLED_LIQUID_RX.search(head):
        return "ml"
    if _SPELLED_SOLID_RX.search(head):
        return "g"

    return None
