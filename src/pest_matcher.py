"""pest_matcher.py — resolve a pest name to a canonical organism, per crop.

Stage 4 of the Phase 6 verifier lookup. Given a crop slug and whatever the
model called the pest, return the canonical group label_db's
`pest_or_disease` column is talking about — or return unmatched. It never
guesses.


WHY THE KEY IS (crop_slug, surface_form) AND NOT surface_form
==============================================================

Nine English pest names in this corpus denote different organisms on
different crops (reports/phase6_stepA_pest_survey.md, section 7). The one
that forces the design:

    tomato      "Fruit borer"  ->  Helicoverpa armigera
    pomegranate "Fruit borer"  ->  Deudorix isocrates

and it is not recoverable from the string. 20 of tomato's 46 `fruit borer`
mentions carry `(Helicoverpa armigera)` in the cell; all three of
pomegranate's carry no scientific name at all. Only the crop separates them.
A flat surface_form -> canonical table would license a pomegranate
Deudorix answer against a tomato Helicoverpa row, which is precisely the
OFF_LABEL_PEST failure the verifier exists to catch.

The other eight: `Alternaria leaf spot` (Alternaria macrospora on cotton,
A. solani = early blight on tomato), `Bacterial blight` (Xanthomonas citri
pv. malvacearum on cotton, X. axonopodis pv. punicae on pomegranate),
`Jassid` (Empoasca kerri on tur, Amrasca elsewhere), `Whitefly`, `Aphid`,
`Thrips`, `Downy mildew`, `Anthracnose`.

Some of those differ only in species under a shared canonical — Thrips is
Thrips whichever species it is — so the table carries a per-crop
`scientific_name` alongside a shared `canonical_name`. Where the CANONICAL
itself differs (Fruit borer, Alternaria leaf spot, Bacterial blight), the
crop is load-bearing and the crop-independent fallback below refuses to fire.


THE CROP-INDEPENDENT FALLBACK
==============================

A model may name a pest that is real but not attested on the queried crop, or
name it in a form label_db happens not to print for that crop. Falling back to
a crop-agnostic lookup is safe for exactly one class of name: those mapping to
a single canonical across EVERY crop in the table. That set is computed from
the table at load time, not hand-listed, so a future table edit that makes a
name ambiguous withdraws it from the fallback automatically.


CONFIDENCE, in descending order of how the match was made
=========================================================

    exact       the surface form matched verbatim for this crop, needing only
                case folding and whitespace collapse
    normalized  matched for this crop after fuller normalisation - hyphens,
                punctuation, and the in-corpus misspelling corrections
    synonym     matched only through the crop-independent index above
    unmatched   nothing matched; canonical_name is None

`source` (label_db / scope_synonyms / manual) travels separately on the
result, so a caller can tell a CIB&RC surface form from a farmer-facing alias
without conflating that with how the lookup succeeded.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Optional

__all__ = [
    "MatchResult",
    "SynonymTable",
    "load_table",
    "match_pest",
    "match_all",
    "normalise_pest",
    "split_pest_cell",
    "DEFAULT_TABLE_PATH",
]

DEFAULT_TABLE_PATH = Path(__file__).resolve().parents[1] / "data" / "final" / "pest_synonym_table.csv"

Confidence = Literal["exact", "normalized", "synonym", "unmatched"]

PestType = Literal["pest", "disease", "nematode", "mite", "rodent", "weed"]

# schema.Cause.type has no mite/nematode/rodent member. A caller populating a
# Cause maps through this; the table keeps the finer distinction because the
# verifier's eval breakdown wants it.
CAUSE_TYPE = {
    "pest": "pest",
    "disease": "disease",
    "nematode": "pest",
    "mite": "pest",
    "rodent": "pest",
    "weed": "weed",
}


# --------------------------------------------------------------------------
# normalisation
# --------------------------------------------------------------------------

# Column-break artifacts: the PDF split a word across a cell boundary. Applied
# before anything else so 'Stemphyliu m blight' can reach 'stemphylium blight'.
_GLUE = [
    (r"stemphyliu\s+m", "stemphylium"),
    (r"myrotheciu\s+m", "myrothecium"),
    (r"oxyspor\s+um", "oxysporum"),
    (r"plasmoparavitic\s*ola", "plasmopara viticola"),
    (r"pectinophoragos\s*sypiella", "pectinophora gossypiella"),
    (r"helicoverpaarmig\s*era", "helicoverpa armigera"),
    (r"amrascabiguttulla", "amrasca biguttula"),
    (r"bemisiatabaci", "bemisia tabaci"),
    (r"eariasvitelli", "earias vitelli"),
    (r"whitefliesandredspidermites", "whiteflies and red spider mites"),
    (r"\bb\s+acterial\b", "bacterial"),
    (r"\bfruitborer\b", "fruit borer"),
    (r"\bpodborer\b", "pod borer"),
    (r"\bpodfly\b", "pod fly"),
    (r"\bleafspot\b", "leaf spot"),
]

# Token-level corrections for the misspellings catalogued in the Step A
# survey. Every one of these ALSO sits in the table as a surface form, so a
# label_db string still matches `exact`; these exist so a model reproducing
# the same slip, or a farmer typing it, still resolves.
_MISSPELL = {
    "downey": "downy",
    "gridle": "girdle",
    "anthraconase": "anthracnose",
    "bight": "blight",
    "armiger": "armigera",
    "amigera": "armigera",
    "heliothis": "helicoverpa",
    "gossipiella": "gossypiella",
    "gossipy": "gossypii",
    "gossypi": "gossypii",
    "gosypii": "gossypii",
    "bemesia": "bemisia",
    "bemmissia": "bemisia",
    "thips": "thrips",
    "chrysodexis": "chrysodeixis",
    "amarasca": "amrasca",
    "bigutella": "biguttula",
    "bigutulla": "biguttula",
    "biguttulla": "biguttula",
    "porii": "porri",
    "obereopsis": "oberea",
    "phenococcus": "phenacoccus",
    "minor": "miner",
}

_WS = re.compile(r"\s+")


def _fold(s: str) -> str:
    """Case fold and collapse whitespace. Nothing else — this is the key an
    `exact` match is made on."""
    s = str(s).replace("\xa0", " ").replace("­", "")
    return _WS.sub(" ", s).strip().lower()


def normalise_pest(s: str) -> str:
    """Full normalisation: fold, repair column-break glue, drop punctuation,
    fold hyphens to spaces, then correct known misspellings token by token."""
    s = _fold(s)
    for pat, rep in _GLUE:
        s = re.sub(pat, rep, s)
    s = s.replace("-", " ").replace("/", " ")
    s = re.sub(r"[^\w\s.]", " ", s)
    s = re.sub(r"\.(?!\s*sp)", " ", s)  # keep 'spp.' / 'sp.', drop other dots
    s = _WS.sub(" ", s).strip(" .")
    if not s:
        return ""
    s = " ".join(_MISSPELL.get(tok, tok) for tok in s.split())
    return _WS.sub(" ", s).strip()


# --------------------------------------------------------------------------
# splitting a compound CIB&RC cell into individual mentions
# --------------------------------------------------------------------------

_PAREN = re.compile(r"\(([^()]*)\)")
_ABBREV = re.compile(r"\b(spp|sp|var|subsp|f|H|F)\.", re.IGNORECASE)
_DELIM = re.compile(r"\s*(?:,|;|&|/|\band\b)\s*", re.IGNORECASE)
_AFTER_PAREN = re.compile(r"(\x00\d+\x00)\s+(?=[A-Za-z])")
_COLON_SCI = re.compile(r"\s*[:\-]\s*([A-Z][a-z]+\s+[a-z]+)(?=\s|$)")

# Bare modifiers that borrow a head noun from a sibling: CIB&RC writes
# 'Early & Late blight', and a splitter that ignores it emits 'Early'.
_MODIFIERS = {
    "early", "late", "leaf", "fruit", "pod", "spotted", "spiny", "pink",
    "american", "egyptian", "green", "downy", "downey", "powdery", "purple",
    "red", "seed", "root", "collar", "charcoal", "stem", "grey", "gray",
    "alternaria", "cercospora", "myrothecium", "bacterial", "angular", "black",
}
_HEADS = (
    "bollworm", "boll worm", "blight", "spot", "mildew", "rot", "borer",
    "worm", "beetle", "fly", "mite", "mites", "looper", "nematode",
    "nematodes", "caterpillar", "weevil", "bug", "bugs", "blotch", "wilt",
    "rust", "hopper", "hoppers", "miner", "grub", "thrips",
)


def _expand_shared_head(parts: list[str]) -> list[str]:
    heads = []
    for p in parts:
        low = p.lower()
        heads.append(next((h for h in _HEADS if low.endswith(h)), None))
    out = []
    for i, p in enumerate(parts):
        bare = _PAREN.sub("", p).strip().lower()
        if bare in _MODIFIERS and heads[i] is None:
            donor = next((heads[j] for j in range(i + 1, len(parts)) if heads[j]), None)
            out.append(f"{p} {donor}" if donor else p)
        else:
            out.append(p)
    return out


def split_pest_cell(cell: str) -> list[str]:
    """Split a CIB&RC pest cell into individual pest mentions.

    335 of label_db's 729 non-empty pest cells name more than one pest, so
    this is not an edge case. Scientific names inside parentheses are masked
    first, or 'Damping off (Pythium aphanidermatum, Rhizoctonia solani)'
    splits on the comma that belongs to the binomial pair.
    """
    if cell is None:
        return []
    s = str(cell).replace("\xa0", " ")
    s = _WS.sub(" ", s).strip().strip('"').strip()
    if not s:
        return []
    # Glue repair has to run before splitting, or a cell the PDF ran together
    # ('WhitefliesandRedspidermites') survives as one mention instead of two.
    for pat, rep in _GLUE:
        s = re.sub(pat, rep, s, flags=re.IGNORECASE)
    if ":" in s or re.search(r"\w-\s", s):
        s = _COLON_SCI.sub(lambda m: f" ({m.group(1)})", s)

    s = _ABBREV.sub(lambda m: m.group(1) + "\x01", s)
    stash: list[str] = []

    def take(m):
        stash.append(m.group(1))
        return f"\x00{len(stash) - 1}\x00"

    masked = _PAREN.sub(take, s)
    masked = _AFTER_PAREN.sub(lambda m: m.group(1) + "\x02", masked)
    masked = masked.replace(".", "\x02")

    parts: list[str] = []
    for chunk in masked.split("\x02"):
        parts.extend(p for p in _DELIM.split(chunk) if p.strip())

    def unmask(x: str) -> str:
        return re.sub(r"\x00(\d+)\x00", lambda m: f"({stash[int(m.group(1))]})", x)

    parts = [unmask(p).replace("\x01", ".").strip(" .,;&") for p in parts]
    parts = _expand_shared_head([p for p in parts if p.strip()])
    return [_WS.sub(" ", p).strip() for p in parts if p.strip()]


def strip_scientific(mention: str) -> tuple[str, Optional[str]]:
    """'Fruit borer (Helicoverpa armigera)' -> ('Fruit borer', 'Helicoverpa armigera')."""
    m = _PAREN.search(mention)
    sci = m.group(1).strip() if m else None
    common = _PAREN.sub("", mention).strip(" .,;&:-")
    return _WS.sub(" ", common).strip(), sci


# --------------------------------------------------------------------------
# the table
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class MatchResult:
    canonical_name: Optional[str]
    pest_type: Optional[str]
    scientific_name: Optional[str]
    confidence: Confidence
    matched_surface_form: Optional[str]
    source: Optional[str] = None
    crop_slug: Optional[str] = None
    notes: str = ""

    @property
    def matched(self) -> bool:
        return self.canonical_name is not None


UNMATCHED = MatchResult(None, None, None, "unmatched", None)

# Fragment rows carry this canonical sentinel in the CSV. They are real
# label_db text - truncated cells, dropped delimiters, generic categories like
# 'sucking insects' - deliberately NOT canonicalised, so the verifier can
# refuse to produce a WRONG verdict against a pest cell already known damaged.
UNMATCHABLE = "UNMATCHABLE"


@dataclass(frozen=True)
class _Row:
    crop_slug: str
    surface_form: str
    canonical_name: str
    pest_type: str
    scientific_name: str
    source: str
    notes: str


class SynonymTable:
    """(crop_slug, surface_form) -> canonical, with a computed crop-independent
    index for the names that are unambiguous everywhere."""

    def __init__(self, rows: Iterable[dict]):
        self.rows: list[_Row] = [
            _Row(
                crop_slug=r["crop_slug"].strip(),
                surface_form=r["surface_form"].strip(),
                canonical_name=r["canonical_name"].strip(),
                pest_type=r["pest_type"].strip(),
                scientific_name=(r.get("scientific_name") or "").strip(),
                source=(r.get("source") or "").strip(),
                notes=(r.get("notes") or "").strip(),
            )
            for r in rows
        ]

        self._exact: dict[tuple[str, str], _Row] = {}
        self._norm: dict[tuple[str, str], _Row] = {}
        for r in self.rows:
            self._exact.setdefault((r.crop_slug, _fold(r.surface_form)), r)
            key = normalise_pest(r.surface_form)
            if key:
                self._norm.setdefault((r.crop_slug, key), r)

        # A name is safe to resolve without a crop only if it means one thing
        # everywhere. Computed, never hand-listed, so the nine crop-dependent
        # names drop out on their own — and so does any name a later table
        # edit makes ambiguous.
        by_form: dict[str, set[str]] = {}
        first: dict[str, _Row] = {}
        for r in self.rows:
            key = normalise_pest(r.surface_form)
            if not key:
                continue
            by_form.setdefault(key, set()).add(r.canonical_name)
            first.setdefault(key, r)
        self._any_crop: dict[str, _Row] = {
            k: first[k] for k, v in by_form.items() if len(v) == 1
        }
        self.ambiguous_forms: frozenset[str] = frozenset(
            k for k, v in by_form.items() if len(v) > 1
        )

    # -- introspection used by the verifier and the tests ------------------

    @property
    def crops(self) -> set[str]:
        return {r.crop_slug for r in self.rows}

    def canonicals(self, crop_slug: Optional[str] = None) -> set[str]:
        return {
            r.canonical_name
            for r in self.rows
            if r.canonical_name != UNMATCHABLE
            and (crop_slug is None or r.crop_slug == crop_slug)
        }

    def surface_forms(self, crop_slug: str) -> set[str]:
        return {r.surface_form for r in self.rows if r.crop_slug == crop_slug}


def load_table(path: Path | str = DEFAULT_TABLE_PATH) -> SynonymTable:
    with open(path, newline="", encoding="utf-8") as fh:
        return SynonymTable(list(csv.DictReader(fh)))


# --------------------------------------------------------------------------
# matching
# --------------------------------------------------------------------------


def _result(row: _Row, confidence: Confidence) -> MatchResult:
    if row.canonical_name == UNMATCHABLE:
        return MatchResult(
            canonical_name=None,
            pest_type=None,
            scientific_name=None,
            confidence="unmatched",
            matched_surface_form=row.surface_form,
            source=row.source,
            crop_slug=row.crop_slug,
            notes=row.notes or "unmatchable fragment",
        )
    return MatchResult(
        canonical_name=row.canonical_name,
        pest_type=row.pest_type,
        scientific_name=row.scientific_name or None,
        confidence=confidence,
        matched_surface_form=row.surface_form,
        source=row.source,
        crop_slug=row.crop_slug,
        notes=row.notes,
    )


def match_pest(
    crop_slug: str,
    pest_string: str,
    synonym_table: SynonymTable,
    *,
    allow_crop_independent: bool = True,
) -> MatchResult:
    """Resolve one pest name on one crop. Returns UNMATCHED rather than guessing.

    Order: exact for this crop, then normalised for this crop, then — only for
    names that mean one thing on every crop — the crop-independent index.
    """
    if pest_string is None:
        return UNMATCHED
    crop = (crop_slug or "").strip().lower()
    # A blank crop is a caller bug, not a crop-agnostic query. The fallback
    # below is for a real crop whose table happens not to print this name; it
    # is not a way to look pests up with no crop at all.
    if not crop:
        return UNMATCHED
    raw = _fold(pest_string)
    if not raw:
        return UNMATCHED

    row = synonym_table._exact.get((crop, raw))
    if row is not None:
        return _result(row, "exact")

    key = normalise_pest(pest_string)
    if key:
        row = synonym_table._norm.get((crop, key))
        if row is not None:
            return _result(row, "normalized")

    if allow_crop_independent and key:
        row = synonym_table._any_crop.get(key)
        if row is not None:
            return _result(row, "synonym")

    return UNMATCHED


def match_all(
    crop_slug: str,
    pest_cell: str,
    synonym_table: SynonymTable,
    *,
    allow_crop_independent: bool = True,
) -> list[MatchResult]:
    """Split a compound cell, then match every mention in it.

    'Rice weevil, Lesser grain Borer, Khapra Beetle' returns three results —
    three unmatched ones, since none is registered on these eight crops.
    Unmatched mentions are kept, not dropped: the caller needs to see that a
    pest was named and could not be resolved.
    """
    out: list[MatchResult] = []
    for mention in split_pest_cell(pest_cell):
        common, sci = strip_scientific(mention)
        r = match_pest(
            crop_slug, common or mention, synonym_table,
            allow_crop_independent=allow_crop_independent,
        )
        if not r.matched and sci:
            # Retry on the parenthesised binomial — but keep the first result
            # unless the retry actually resolves. A known-unmatchable fragment
            # ('Defoliators (Helicoverpa armigera, Spodoptera litura and
            # Semilooper)') carries a table row and its note; discarding that
            # for a failed retry would lose the fact that we recognise the
            # string at all.
            alt = match_pest(
                crop_slug, sci, synonym_table,
                allow_crop_independent=allow_crop_independent,
            )
            if alt.matched:
                r = alt
        out.append(r)
    return out
