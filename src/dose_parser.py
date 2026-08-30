"""
dose_parser.py — CIB&RC dose cell -> schema.Dose.

Pure. One function, `parse_dose`, no I/O, no globals mutated, no dependency on
the surrounding row. Crop mapping, PHI resolution and label_db assembly are
later steps and deliberately absent here.


DESIGN RULES
============

These are rules, not implementation notes. Changing one changes what the model
is taught, so each is stated rather than left implicit in a regex.

1. dilution_water is not a dose column.
   Its CIB&RC header is "Dilution in Water (Liter)". That is spray volume,
   which the schema carries as ChemicalOption.spray_volume_min/max_l_per_acre,
   not as a Dose. This parser is for `dose_ai` and `dose_formulation`. It does
   not refuse a dilution_water string — a column-shifted row can drop a real
   dose into that column — but the caller decides what to feed it, and feeding
   it the whole dilution_water column would mint per_ha Doses out of spray
   volumes.

2. A range keeps both ends.
   Dose has value_min and value_max, so "500-750" is stored whole. Where a
   single number is required downstream, take the LOWER bound. This is the
   opposite of PHI, which takes the larger of a range, and both choices point
   the same way: for a waiting period the longer wait is the safe answer, for
   an application rate the smaller dose is. That asymmetry is intentional.
   This parser never collapses a range itself; it only refuses to lose an end.

3. Percentages and per-litre dilutions are never area-converted.
   0.025% is concentration_pct with unit '%'. 2.5 ml/l is per_litre_water.
   Converting either to a per-hectare figure requires a spray volume this
   parser does not have, and a wrong one is a dosing error in the field.

4. "N unit per M litres" and "N unit per M kg seed" are normalised by dividing.
   '38.75 g/10 kg seed' becomes 3.875 g per kg seed; '25 ml/100 lit' becomes
   0.25 ml per litre. The division is exact (Decimal, not float), and the
   verbatim cell is preserved in Dose.raw so the printed figure is never lost.

5. A '%' inside prose is a formulation strength, not a dose.
   "Trichoderma viride 1.0% WP" names the product. Reading that 1.0% as a dose
   concentration is the most damaging misparse available in this corpus, so
   any cell whose leading token is a method verb or treatment noun goes to the
   free_text branch before any percentage handling runs.

6. A '%' beside a foreign basis is two doses, not one.
   '0.10% or 100 gram in 100 lit water' is one dose stated twice — the mass in
   water IS the percentage — so it parses as concentration_pct. But
   '1.8 g a.i/vine or 0.09%' names two different bases with no rule for
   choosing between them, so it goes to free_text. The test is whether the
   non-percentage half is expressed per unit of WATER (same dose) or per tree,
   plant, vine, sucker, seed or area (different dose).

7. Compound / ready-mix rates go to free_text.
   '30 + 15' and '1.58 (Cyantraniliprole 0.79 + Thiamethoxam 0.79)' state a
   product's components separately. Summing them silently would invent a
   single-active dose that no label authorises.

8. A number with no unit anywhere is not a dose.
   'dose_ai' cells are grams by column header, but this function will not
   assume that on its own. The caller passes `default_unit`; without it a bare
   number returns unparseable with code NEEDS_UNIT. `dose_formulation`'s header
   is "(g/ml)" — genuinely ambiguous between mass and volume until the
   formulation type is known — so those bare numbers are expected to come back
   NEEDS_UNIT until a later step resolves them. That is the correct answer,
   not a coverage failure.

9. No silent failures.
   Every input returns an explicit branch. A string this parser does not
   recognise returns branch='unparseable' with a reason code; it never returns
   a plausible-looking Dose. A parse that would violate a schema.py validator
   raises DoseParseBug rather than being downgraded or bypassed — the validator
   is right and the parse is wrong.

10. per_acre is unreachable from this corpus.
    CIB&RC prints per hectare. schema.py's comment says per_acre is "already
    converted from per_ha by label_db", so the conversion belongs there, not
    here. This parser never emits per_acre.


BRANCHES
========

    numeric      a Dose on one of the numeric bases
    free_text    a Dose with basis='free_text' — real content, not numerically
                 expressible (prose, compound rate, two bases in one cell)
    empty        no dose stated at all ('-', 'NA'). dose is None. This is a
                 fourth branch on purpose: minting a free_text Dose for a
                 dash would put a meaningless object into label_db, and 422 of
                 the 7130 surveyed cells are dashes.
    unparseable  recognised as broken, or not recognised. dose is None,
                 `code` says which.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal, Optional

from schema import Basis, Dose, Unit

__all__ = ["parse_dose", "ParseResult", "Branch", "ReasonCode", "DoseParseBug"]


class DoseParseBug(Exception):
    """A parse that schema.py rejected. The parse is wrong, not the schema."""


Branch = Literal["numeric", "free_text", "empty", "unparseable"]

ReasonCode = Literal[
    "NEEDS_UNIT",           # no unit in the string and no default_unit given
    "AMBIGUOUS_PAIR",       # two values, no operator joining them
    "REVERSED_RANGE",       # value_max < value_min as printed
    "COLUMN_COLLAPSE",      # several columns merged into one cell
    "TIME_VALUE",           # a waiting period landed in a dose column
    "AI_NAME",              # an active-ingredient name landed in a dose column
    "TRUNCATED",            # cell visibly cut off mid-token
    "RATIO_OR_INEQUALITY",  # '37:3', '>140'
    "UNRECOGNISED",         # no pattern claimed it
]


@dataclass(frozen=True)
class ParseResult:
    """What parse_dose returns. `pattern` is the surface pattern that claimed
    the string — the Phase A vocabulary — and is stable enough to group on."""
    branch: Branch
    pattern: str
    dose: Optional[Dose] = None
    code: Optional[ReasonCode] = None
    detail: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.branch in ("numeric", "free_text")


# --------------------------------------------------------------------------
# text primitives
# --------------------------------------------------------------------------

def _sp(word: str) -> str:
    """Word regex tolerant of OCR-injected spaces: 'seed' also matches 'see d'."""
    return r"\s*".join(re.escape(c) for c in word)


# A number. Space is tolerated only around the decimal point ('1 .00', '0 .63'),
# never between digit groups: joining '25 50' into 2550 would be a guess, and
# strings like that are meant to fall through to COLUMN_COLLAPSE instead.
NUM = r"\d+(?:\s?\.\s?\d+)?"
DASH = r"(?:-+|–|—|to)"
RANGE = rf"{NUM}\s*{DASH}\s*{NUM}"
FOOT = r"[*^]*"                      # footnote markers glued to a value

_G = r"(?:gms?|gm|grams?|gs|g)"
_KG = r"(?:kgs?|kg)"
_ML = r"(?:mls?|ml)"
_LT = (rf"(?:{_sp('litres')}|{_sp('litre')}|{_sp('liters')}|{_sp('liter')}"
       rf"|ltrs?|lts?|lit|l)")
MV = rf"(?:{_G}|{_KG}|{_ML}|{_LT})\.?"
AI = r"(?:\(?\s*a\.?\s?i\.?\s*\)?|formulation|form\.?)?"
# unit and an 'a.i.' marker in either order, both optional
UNITS = rf"(?:\s*{AI}\s*(?P<unit>{MV})\s*{AI}|\s*{AI})"
SEED = (rf"(?:{_sp('seedlings')}|{_sp('seedling')}|{_sp('seeds')}|{_sp('seed')}"
        rf"|{_sp('tubers')}|{_sp('tuber')})")
WATER = rf"(?:{_sp('water')}|{_sp('wtr')})"

_UNIT_MAP = {
    "g": "g", "gm": "g", "gms": "g", "gs": "g", "gram": "g", "grams": "g",
    "kg": "kg", "kgs": "kg",
    "ml": "ml", "mls": "ml",
    "l": "l", "lt": "l", "lts": "l", "ltr": "l", "ltrs": "l", "lit": "l",
    "litre": "l", "litres": "l", "liter": "l", "liters": "l",
}


def _unit(tok: Optional[str]) -> Optional[Unit]:
    """Normalise a unit token to the schema's Unit enum, or None."""
    if not tok:
        return None
    key = re.sub(r"[\s.]", "", tok).lower()
    return _UNIT_MAP.get(key)


def _dec(tok: str) -> Decimal:
    return Decimal(re.sub(r"\s", "", tok))


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def _repair(t: str) -> str:
    """Undo OCR damage that is unambiguous. Decimal points only."""
    t = re.sub(r"(\d)\s+\.\s*(\d)", r"\1.\2", t)
    t = re.sub(r"(\d)\.\s+(\d)", r"\1.\2", t)
    return t


# A parenthesised unit expression belongs inline: '3.00 (ml/kg seed)' states
# the same thing as '3.00 ml/kg seed'. Only unwrapped when the parenthesised
# content is itself a unit-over-basis expression, never for '(Soil drench)'.
_PAREN_UNIT = re.compile(
    rf"^(?P<head>{NUM}(?:\s*{DASH}\s*{NUM})?)\s*\(\s*(?P<body>{MV}\s*/[^)]*)\)\s*$",
    re.I)


def _unwrap_unit_parens(t: str) -> str:
    m = _PAREN_UNIT.match(t)
    return f"{m.group('head')} {m.group('body')}" if m else t


# --------------------------------------------------------------------------
# content pre-checks
#
# These decide by what the cell CONTAINS, not by its shape, and run before the
# shape table so that the reason a string was routed somewhere stays legible.
# --------------------------------------------------------------------------

NULLISH = re.compile(r"^(?:-+|–+|nil|n\.?\s?/?\s?a\.?|not\s*applicable"
                     r"|not\s*app\w*)\.?$", re.I)

# Rule 5: a leading method verb or treatment noun means the cell is prose.
PROSE_LEAD = re.compile(
    r"^(?:seed(?:ling)?s?[\s-]*(?:root\s*dip\s*)?treatment|soil[\s-]*treatment"
    r"|treatment|foliar\s*spr[ay]y?|spray|mix|dissolve|use|apply|available"
    r"|it\s+is|seeds?\s+are|broadcas\w*|braoad\w*|air\s*tight|sufficient"
    r"|this\s+is|as\s+required|as\s+per|at\s+pod|based\s+on|depend\w*|direct"
    r"|disease|from\s+square|leaf\s*spot|slurry|one\s+tablet|dosage|splash"
    r"|not\s+required|seed\s+dresser|whorl|are\s+dried|water$|seed$)\b", re.I)

# Units schema.Unit cannot express. Not a defect — the label really does say
# this — so these are free_text, not unparseable.
UNSUPPORTED_UNIT = re.compile(
    r"(?:\d\s*mg\b|\bmg\s*(?:/|per)|\bppm\b|\btablets?\b|\bpouch(?:es)?\b"
    r"|\bburrows?\b|\bspots?\b|\bm3\b|\bmeter3\b|\bcft\b|\bdripper\b|\bbait\b"
    r"|\bdust\b|\bton(?:ne)?s?\b|\bsand\b|\bmanure\b|\bfertili[sz]er\b"
    r"|\binjection\b|\blinseed\b|slurry\s*volume)", re.I)

# The whole cell is a waiting period: a PHI value in the wrong column.
TIME_ONLY = re.compile(
    r"^(?:\d[\d\s.–-]*(?:to)?\s*\d*\s*(?:hrs?|hours?|days?)\.?\s*"
    r"(?:waiting\s*period\s*)?)+$", re.I)

AI_NAME_LEAD = re.compile(r"^[A-Z][a-z]{4,}[a-z\-]*\s*[-–]?\s*\d[\d.]*\s*"
                          r"(?:%\s*\(?w/[wv]\)?)?\s*(?:&|\+)")

TRUNCATED = re.compile(r"^(?:.*[+–-]\s*$|.*\((?:for|no)\b[^)]*$"
                       r"|[^(]*\)$|.*\bof\s*$)", re.S)

RATIO_OR_INEQ = re.compile(r"^\s*(?:[<>]\s*\d.*|\d+\s*:\s*\d+)\s*$")

HAS_PCT = re.compile(r"\d\s*%")

# Rule 7: a '+' in a cell holding two or more numbers = ready-mix components.
_NUMTOK = re.compile(r"\d+(?:\s?\.\s?\d+)?")


def _is_compound(t: str) -> bool:
    return "+" in t and len(_NUMTOK.findall(t)) >= 2


# Rule 6: bases that are NOT interchangeable with a percentage. Water is
# absent on purpose — a mass in water IS the percentage.
FOREIGN_BASIS = re.compile(
    rf"(?:/|per)\s*(?:{NUM}\s*)?(?:{_sp('tree')}|{_sp('plant')}|{_sp('vine')}"
    rf"|{_sp('sucker')}|bushe?s?|hills?|{_KG}\.?\s*(?:of\s*)?{SEED}"
    rf"|ha\b|hect\w*|acre|sq\.?\s*m|m2)", re.I)

# Basis anchors, used to spot a cell holding more than one dose expression.
ANCHORS = (
    ("ha", re.compile(r"(?:/|per)\s*(?:ha\b|hect\w*|acre)", re.I)),
    ("seed", re.compile(rf"(?:/|per|for)\s*(?:{NUM}\s*)?{_KG}\.?\s*(?:of\s*)?"
                        rf"(?:\w+\s+)*{SEED}", re.I)),
    ("water", re.compile(rf"(?:/|per|in)\s*(?:{NUM}\s*)?{_LT}\.?\s*(?:of\s*)?"
                         rf"{WATER}?", re.I)),
    ("tree", re.compile(rf"(?:/|per)\s*(?:{NUM}\s*)?{_sp('tree')}", re.I)),
    ("plant", re.compile(rf"(?:/|per)\s*(?:{NUM}\s*)?(?:{_sp('plant')}"
                         rf"|{_sp('sucker')}|{_sp('vine')})", re.I)),
    ("sqm", re.compile(r"(?:/|per)\s*(?:\d+\s*)?(?:sq\.?\s*m|m2)", re.I)),
)

# One cell, two doses chosen by application method.
ALTERNATIVES = re.compile(
    r"\d[^\d]{0,40}\((?:[^)]*(?:application|spray|knap|drone|dry|soaked"
    r"|single|foliar|drench)[^)]*)\)[^\d]{0,20}(?:or\s*)?\d", re.I)


# --------------------------------------------------------------------------
# shape table
#
# Ordered; first full-string match wins. Named groups: lo, hi (range ends),
# unit, div (the divisor in 'per N litres' / 'per N kg seed').
# --------------------------------------------------------------------------

_P = [
    # ---- percentage family -> concentration_pct -------------------------
    ("PCT_SINGLE", "pct",
     rf"^(?P<lo>{NUM})\s*%{FOOT}\s*(?:w/[wv]|sol(?:ution|\.)?|conc\.?)?\.?$"),
    ("PCT_RANGE", "pct",
     rf"^(?P<lo>{NUM})\s*{DASH}\s*(?P<hi>{NUM})\s*%{FOOT}\s*"
     rf"(?:sol(?:ution|\.)?)?\.?$"),
    # '0.025% -0.05%' is a range; '0.005% 0.05%' has no operator and is not.
    ("PCT_RANGE_BOTH", "pct_pair",
     rf"^(?P<lo>{NUM})\s*%\s*(?P<sep>{DASH})?\s*(?P<hi>{NUM})\s*%{FOOT}\s*"
     rf"(?:sol(?:ution|\.)?)?\.?$"),
    # '0.10% or 100 Gram in 100 lit water' -- percentage stated first
    ("PCT_WITH_EQUIV", "pct",
     rf"^\(?(?P<lo>{NUM})(?:\s*{DASH}\s*(?P<hi>{NUM}))?\s*%\)?"
     rf"(?:\s*{DASH}\s*{NUM}\s*%)?\s*(?:or|:|\()?\s*\(?{NUM}.*$"),
    # '2000 g or 0.4%', '75 (0.0075%)' -- mass equivalent stated first
    ("PCT_EQUIV_FIRST", "pct",
     rf"^{NUM}(?:\s*{DASH}\s*{NUM})?{UNITS}\s*(?:(?:/|per)\s*[\w\s.]*?)?"
     rf"(?:or|\()\s*\(?(?P<lo>{NUM})\s*%.*$"),

    # ---- per-litre dilution -> per_litre_water ---------------------------
    ("PER_N_LITRE", "litre",
     rf"^(?P<lo>{NUM})(?:\s*{DASH}\s*(?P<hi>{NUM}))?{UNITS}\s*(?:/|per|in|for)"
     rf"\s*(?P<div>{NUM})\s*{_LT}\.?\s*(?:of\s*)?(?:{WATER})?\.?\s*"
     rf"(?:\([^)]*\))?$"),
    ("PER_LITRE", "litre",
     rf"^(?P<lo>{NUM})(?:\s*{DASH}\s*(?P<hi>{NUM}))?{UNITS}\s*(?:/|per)\s*"
     rf"{_LT}\.?\s*(?:of\s*)?(?:{WATER})?\.?$"),
    ("PER_LITRE_BARE", "litre",
     rf"^(?P<lo>{NUM})\s*(?P<unit>{_LT})\.?\s*{WATER}\.?$"),

    # ---- per kg seed -> per_kg_seed --------------------------------------
    ("PER_N_KG_SEED", "seed",
     rf"^(?P<lo>{NUM})(?:\s*{DASH}\s*(?P<hi>{NUM}))?{UNITS}\s*(?:/|per|for)\s*"
     rf"(?P<div>{NUM})\s*{_KG}\.?\s*(?:of\s*)?(?:\w+\s+)*(?:{SEED})?\.?$"),
    ("PER_KG_SEED", "seed",
     rf"^(?P<lo>{NUM})(?:\s*{DASH}\s*(?P<hi>{NUM}))?{UNITS}\s*(?:/|p\s*er)\s*"
     rf"{_KG}\.?\s*(?:of\s*)?(?:{SEED})?\.?$"),

    # ---- per tree / plant / sq m ----------------------------------------
    ("PER_TREE", "tree",
     rf"^(?P<lo>{NUM})(?:\s*{DASH}\s*(?P<hi>{NUM}))?{UNITS}\s*(?:{WATER})?\s*"
     rf"(?:/|per)\s*(?:{NUM}\s*)?{_sp('tree')}s?\.?$"),
    ("PER_PLANT", "plant",
     rf"^(?P<lo>{NUM})(?:\s*{DASH}\s*(?P<hi>{NUM}))?{UNITS}\s*(?:/|per)\s*"
     rf"(?:{NUM}\s*)?(?:{_sp('plant')}s?|{_sp('sucker')}s?|{_sp('vine')}s?"
     rf"|bushe?s?|hills?)\.?$"),
    ("PER_N_SQ_M", "sqm",
     rf"^(?P<lo>{NUM})(?:\s*{DASH}\s*(?P<hi>{NUM}))?{UNITS}\s*(?:/|per)\s*"
     rf"(?P<div>{NUM})\s*(?:sq\.?\s*m(?:tr|eter|etre)?s?|m2)\.?$"),
    ("PER_SQ_M", "sqm",
     rf"^(?P<lo>{NUM})(?:\s*{DASH}\s*(?P<hi>{NUM}))?{UNITS}\s*(?:/|per)\s*"
     rf"(?:sq\.?\s*m(?:tr|eter|etre)?s?|m2)\.?$"),

    # ---- explicit area basis --------------------------------------------
    ("PER_HA_EXPLICIT", "area",
     rf"^(?P<lo>{NUM})(?:\s*{DASH}\s*(?P<hi>{NUM}))?{UNITS}\s*(?:/|per)\s*"
     rf"(?:ha|hect\w*|acre)\.?\s*\.?$"),

    # ---- plain numeric, unit implied by the column header ----------------
    ("BARE_NUMBER", "area", rf"^\(?(?P<lo>{NUM}){FOOT}\)?\.?$"),
    ("BARE_RANGE", "area",
     rf"^(?P<lo>{NUM})\s*{DASH}\s*(?P<hi>{NUM}){FOOT}\.?$"),
    ("NUM_UNIT", "area", rf"^(?P<lo>{NUM})\s*(?P<unit>{MV})\s*(?:{MV})?{FOOT}\.?$"),
    ("RANGE_UNIT", "area",
     rf"^(?P<lo>{NUM})\s*(?:{MV})?\s*{DASH}\s*(?P<hi>{NUM})\s*(?P<unit>{MV})"
     rf"{FOOT}\.?$"),

    # ---- several independent numbers, no operator ------------------------
    # Ordered BEFORE NUM_WITH_METHOD: a cell that is nothing but numbers has
    # had columns merged into it, which is an extraction defect worth
    # flagging, not a dose with a method descriptor.
    ("COLUMN_COLLAPSE", "defect:COLUMN_COLLAPSE",
     rf"^(?:{NUM}|{RANGE})\s*/\s*{NUM}\s*respectively\.?$"),
    ("COLUMN_COLLAPSE", "defect:COLUMN_COLLAPSE",
     rf"^(?:{NUM}|{RANGE})\s*(?:%|{MV})?"
     rf"(?:\s+(?:{NUM}|{RANGE})\s*(?:%|{MV})?){{1,3}}\.?$"),

    # ---- one value plus an application method ----------------------------
    # `rest` deliberately admits a leading digit so that a cell holding a
    # SECOND quantity is caught here and routed to free_text by _method,
    # rather than falling off the end of the table as UNRECOGNISED.
    ("NUM_WITH_METHOD", "method",
     rf"^(?P<lo>{NUM})(?:\s*{DASH}\s*(?P<hi>{NUM}))?\s*(?P<unit>{MV})?\s*{AI}\s*"
     rf"(?:\(?\s*(?:/|per)\s*(?P<basis>ha|hect\w*|acre"
     rf"|{_KG}\.?\s*(?:of\s*)?(?:{SEED})?|{_LT}\.?\s*(?:{WATER})?"
     rf"|{_sp('tree')}s?)\s*\)?)?\s*[\(,;./]?\s*(?P<rest>[A-Za-z(\d].*)$"),
]

PATTERNS = [(name, kind, re.compile(rx, re.I | re.S)) for name, kind, rx in _P]


# --------------------------------------------------------------------------
# result builders
# --------------------------------------------------------------------------

def _free(pattern: str, raw: str) -> ParseResult:
    return ParseResult("free_text", pattern, _build(("free_text", None, None, None), raw))


def _bad(code: ReasonCode, pattern: str, detail: str = "") -> ParseResult:
    return ParseResult("unparseable", pattern, None, code, detail or None)


def _build(spec, raw: str) -> Dose:
    """Construct the Dose. A validator rejection is a bug in the parse (rule 9)."""
    basis, lo, hi, unit = spec
    try:
        return Dose(basis=basis, value_min=lo, value_max=hi, unit=unit, raw=raw)
    except Exception as exc:                       # pydantic ValidationError
        raise DoseParseBug(
            f"parse of {raw!r} produced basis={basis!r} value_min={lo!r} "
            f"value_max={hi!r} unit={unit!r}, which schema.py rejects: {exc}"
        ) from exc


def _numeric(pattern: str, basis: Basis, lo: Decimal, hi: Optional[Decimal],
             unit: Unit, raw: str) -> ParseResult:
    if hi is not None and hi < lo:
        return _bad("REVERSED_RANGE", pattern, f"{lo} > {hi}")
    dose = _build((basis, float(lo), None if hi is None else float(hi), unit), raw)
    return ParseResult("numeric", pattern, dose)


# --------------------------------------------------------------------------
# handlers
# --------------------------------------------------------------------------

_BASIS_OF_KIND: dict[str, Basis] = {
    "area": "per_ha",
    "litre": "per_litre_water",
    "seed": "per_kg_seed",
    "tree": "per_tree",
    "plant": "per_plant",
    "sqm": "per_sq_m",
}

_METHOD_BASIS = (
    (re.compile(rf"^{_KG}", re.I), "per_kg_seed"),
    (re.compile(rf"^{_LT}", re.I), "per_litre_water"),
    (re.compile(rf"^{_sp('tree')}", re.I), "per_tree"),
)


def _measured(pattern: str, kind: str, m: re.Match, raw: str,
              default_unit: Optional[Unit]) -> ParseResult:
    """Handle every basis whose value is a mass or volume (rule 3, 4)."""
    unit = _unit(m.groupdict().get("unit")) or default_unit
    if unit is None:
        return _bad("NEEDS_UNIT", pattern,
                    "no unit in the cell and no default_unit supplied")
    if unit == "%":
        # A mass/volume basis cannot carry '%'. schema.py forbids it and so do we.
        return _bad("UNRECOGNISED", pattern, "default_unit '%' on a mass basis")

    lo = _dec(m.group("lo"))
    hi = _dec(m.group("hi")) if m.groupdict().get("hi") else None

    div = m.groupdict().get("div")
    if div:                                        # rule 4: normalise by dividing
        d = _dec(div)
        if d == 0:
            return _bad("UNRECOGNISED", pattern, "division by zero")
        lo = lo / d
        hi = None if hi is None else hi / d

    return _numeric(pattern, _BASIS_OF_KIND[kind], lo, hi, unit, raw)


def _pct(pattern: str, m: re.Match, raw: str, text: str) -> ParseResult:
    """Percentage family. Rule 3 (never area-converted) and rule 6."""
    if FOREIGN_BASIS.search(text):
        # '1.8 g a.i/vine or 0.09%' -- two bases, no rule for choosing.
        return _free("PCT_WITH_FOREIGN_BASIS", raw)
    lo = _dec(m.group("lo"))
    hi = _dec(m.group("hi")) if m.groupdict().get("hi") else None
    return _numeric(pattern, "concentration_pct", lo, hi, "%", raw)


def _pct_pair(pattern: str, m: re.Match, raw: str, text: str) -> ParseResult:
    """'0.025% -0.05%' is a range. '0.005% 0.05%' is two values with nothing
    joining them, and guessing which relation holds is exactly what rule 9
    forbids."""
    if not m.groupdict().get("sep"):
        return _bad("AMBIGUOUS_PAIR", pattern,
                    "two percentages with no operator between them")
    return _pct(pattern, m, raw, text)


def _method(pattern: str, m: re.Match, raw: str, text: str,
            default_unit: Optional[Unit]) -> ParseResult:
    """Decision 5: one value plus a method descriptor is numeric and keeps the
    method in `raw`; a second quantity in the tail means the cell holds two
    doses and goes to free_text."""
    rest = m.group("rest") or ""
    if re.search(r"\d", rest):
        return _free("NUM_WITH_SECOND_QUANTITY", raw)

    basis: Basis = "per_ha"
    anchor = (m.groupdict().get("basis") or "").strip()
    if anchor:
        for rx, b in _METHOD_BASIS:
            if rx.match(anchor):
                basis = b
                break

    unit = _unit(m.groupdict().get("unit")) or default_unit
    if unit is None:
        return _bad("NEEDS_UNIT", pattern,
                    "no unit in the cell and no default_unit supplied")
    if unit == "%":
        return _bad("UNRECOGNISED", pattern, "default_unit '%' on a mass basis")

    lo = _dec(m.group("lo"))
    hi = _dec(m.group("hi")) if m.groupdict().get("hi") else None
    return _numeric(pattern, basis, lo, hi, unit, raw)


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

def parse_dose(raw: str, *, default_unit: Optional[Unit] = None) -> ParseResult:
    """Parse one CIB&RC dose cell.

    `raw` is the cell verbatim; it is preserved on Dose.raw whatever happens.
    `default_unit` is the unit the COLUMN licenses when the cell itself states
    none — 'g' for dose_ai, whose header reads "a.i (gm)". Pass None for
    dose_formulation, whose header reads "(g/ml)" and so licenses nothing:
    those cells come back NEEDS_UNIT rather than being guessed (rule 8).

    Never raises for bad input. Raises DoseParseBug only when a parse this
    module produced violates schema.py, which is a defect here (rule 9).
    """
    if raw is None:
        return _bad("UNRECOGNISED", "NONE", "input was None")

    text = _repair(_norm(raw))

    if not text:
        return ParseResult("empty", "EMPTY")
    if NULLISH.match(text):
        return ParseResult("empty", "NULL_MARKER")
    if not re.search(r"\d", text):
        return _free("PROSE_NO_NUMBER", raw)

    # --- content pre-checks (rules 5, 6, 7); order is meaningful
    if RATIO_OR_INEQ.match(text):
        return _bad("RATIO_OR_INEQUALITY", "DEFECT_RATIO_OR_INEQUALITY", text)
    if TIME_ONLY.match(text):
        return _bad("TIME_VALUE", "DEFECT_TIME_VALUE", text)
    if AI_NAME_LEAD.match(text):
        return _bad("AI_NAME", "DEFECT_AI_NAME", text)
    if PROSE_LEAD.match(text):
        return _free("PROSE_METHOD", raw)          # rule 5
    if UNSUPPORTED_UNIT.search(text):
        return _free("UNSUPPORTED_UNIT", raw)
    if TRUNCATED.match(text):
        return _bad("TRUNCATED", "DEFECT_TRUNCATED", text)

    text = _unwrap_unit_parens(text)

    kinds = {k for k, rx in ANCHORS if rx.search(text)}
    if len(kinds) >= 2:
        return _free("MULTI_BASIS", raw)
    if ALTERNATIVES.search(text):
        return _free("ALTERNATIVE_VALUES", raw)
    if _is_compound(text):                         # rule 7
        return _free("COMPOUND", raw)
    if not HAS_PCT.search(text) and len(kinds) == 1:
        rx = dict(ANCHORS)[next(iter(kinds))]
        if len(rx.findall(text)) >= 2:
            return _free("MULTI_RATE", raw)

    # --- shape table
    for name, kind, rx in PATTERNS:
        m = rx.match(text)
        if not m:
            continue
        if kind == "pct":
            return _pct(name, m, raw, text)
        if kind == "pct_pair":
            return _pct_pair(name, m, raw, text)
        if kind == "method":
            return _method(name, m, raw, text, default_unit)
        if kind.startswith("defect:"):
            return _bad(kind.split(":", 1)[1], name, text)   # type: ignore[arg-type]
        return _measured(name, kind, m, raw, default_unit)

    return _bad("UNRECOGNISED", "UNRECOGNISED", text)
