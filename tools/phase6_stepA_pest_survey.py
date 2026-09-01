"""phase6_stepA_pest_survey.py — SURVEY ONLY. Builds no synonym table.

Splits label_db's pest_or_disease cells into individual pest mentions and
reports the vocabulary, so the canonical grouping can be reviewed before any
table is written. Read-only: writes nothing to data/.

The splitter here is deliberately mechanical. Every judgement call about
"are these the same organism" is left to the report, not encoded here.
"""

from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import scope  # noqa: E402

LABEL_DB = ROOT / "data" / "final" / "label_db.csv"


# --------------------------------------------------------------------------
# 1. whitespace / OCR normalisation (surface only - no biology yet)
# --------------------------------------------------------------------------

# Split-word OCR artifacts: the PDF broke a word across a column boundary.
_GLUE = [
    (r"Stemphyliu\s+m", "Stemphylium"),
    (r"Myrotheciu\s+m", "Myrothecium"),
    (r"oxyspor\s+um", "oxysporum"),
    (r"Plasmoparavitic\s+ola", "Plasmopara viticola"),
    (r"Amrascabiguttulla", "Amrasca biguttula"),
    (r"Bemisiatabaci", "Bemisia tabaci"),
    (r"Pectinophoragos\s*sypiella", "Pectinophora gossypiella"),
    (r"Helicoverpaarmig\s*era", "Helicoverpa armigera"),
    (r"Eariasvitelli", "Earias vitelli"),
    (r"WhitefliesandRedspidermites", "Whiteflies and Red spider mites"),
    (r"\bB\s+acterial\b", "Bacterial"),
    (r"\bFruitborer\b", "Fruit borer"),
    (r"\bPodborer\b", "Pod borer"),
    (r"\bPodfly\b", "Pod fly"),
    (r"\bLeafspot\b", "Leaf spot"),
]


# Three cells state the scientific name after a colon or dash instead of in
# parentheses ('Fruit borer: Helicoverpa armigera Leaf miner: Liriomyza
# trifolii'). Rewritten to the parenthetical form so one splitter handles all.
_COLON_SCI = re.compile(r"\s*[:\-]\s*([A-Z][a-z]+\s+[a-z]+)(?=\s|$)")


def normalise(s: str) -> str:
    s = str(s).replace(" ", " ")
    for pat, rep in _GLUE:
        s = re.sub(pat, rep, s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.strip('"').strip()
    if ":" in s or re.search(r"\w-\s", s):
        s = _COLON_SCI.sub(lambda m: f" ({m.group(1)})", s)
    return s


# --------------------------------------------------------------------------
# 2. splitting a compound cell into individual mentions
# --------------------------------------------------------------------------

# Abbreviations whose '.' must not be read as a sentence break.
_ABBREV = re.compile(r"\b(spp|sp|var|f|subsp|H|F)\.", re.IGNORECASE)
_PAREN = re.compile(r"\(([^()]*)\)")


def _mask_parens(s: str):
    """Replace each (...) with a placeholder so delimiters inside a
    scientific name ('Pythium aphanidermatum, Rhizoctonia solani') do not
    split the mention that owns them."""
    stash = []

    def take(m):
        stash.append(m.group(1))
        return f"\x00{len(stash) - 1}\x00"

    return _PAREN.sub(take, s), stash


def _unmask(s: str, stash: list[str]) -> str:
    return re.sub(r"\x00(\d+)\x00", lambda m: f"({stash[int(m.group(1))]})", s)


_DELIM = re.compile(r"\s*(?:,|;|&|/|\band\b)\s*", re.IGNORECASE)

# A mention ends where a parenthetical closes and new words begin.
_AFTER_PAREN = re.compile(r"(\x00\d+\x00)\s+(?=[A-Za-z])")

# Bare modifiers that need a head noun borrowed from a sibling mention.
_MODIFIERS = {
    "early", "late", "leaf", "fruit", "pod", "spotted", "spiny", "pink",
    "american", "egyptian", "green", "downy", "downey", "powdery", "purple",
    "red", "seed", "root", "collar", "charcoal", "stem", "grey", "gray",
    "alternaria", "cercospora", "myrothecium", "bacterial", "angular",
    "two spotted", "black",
}

_HEADS = (
    "bollworm", "boll worm", "blight", "spot", "mildew", "rot", "borer",
    "worm", "beetle", "fly", "mite", "mites", "looper", "nematode",
    "nematodes", "caterpillar", "weevil", "bug", "bugs", "blotch",
    "wilt", "rust", "hopper", "hoppers", "miner", "grub", "thrips",
)


def _expand_shared_head(parts: list[str]) -> list[str]:
    """'Early & Late blight' -> ['Early blight', 'Late blight'].

    A part that is nothing but a modifier borrows the head noun of the next
    part that has one. CIB&RC coordinates this way constantly and a splitter
    that ignores it emits 'Early' as a pest name.
    """
    heads: list[str | None] = []
    for p in parts:
        low = p.lower()
        heads.append(next((h for h in _HEADS if low.endswith(h)), None))

    out = []
    for i, p in enumerate(parts):
        low = re.sub(r"\s*\(.*?\)", "", p).strip().lower()
        if low in _MODIFIERS and heads[i] is None:
            donor = next((heads[j] for j in range(i + 1, len(parts)) if heads[j]), None)
            out.append(f"{p} {donor}" if donor else p)
        else:
            out.append(p)
    return out


def split_cell(cell: str) -> list[str]:
    s = normalise(cell)
    if not s:
        return []
    s = _ABBREV.sub(lambda m: m.group(1) + "\x01", s)  # protect 'spp.' etc.
    masked, stash = _mask_parens(s)
    masked = _AFTER_PAREN.sub(lambda m: m.group(1) + "\x02", masked)  # boundary after paren
    masked = masked.replace(".", "\x02")  # sentence break = boundary

    parts: list[str] = []
    for chunk in masked.split("\x02"):
        parts.extend(p for p in _DELIM.split(chunk) if p.strip())

    parts = [_unmask(p, stash).replace("\x01", ".").strip(" .,;&") for p in parts]
    parts = [p for p in parts if p]
    parts = _expand_shared_head(parts)
    return [re.sub(r"\s+", " ", p).strip() for p in parts if p.strip()]


def strip_sci(mention: str) -> tuple[str, str | None]:
    """Separate 'Fruit borer (Helicoverpa armigera)' into common + scientific."""
    m = _PAREN.search(mention)
    sci = m.group(1).strip() if m else None
    common = _PAREN.sub("", mention).strip(" .,;&:-")
    common = re.sub(r"\s+", " ", common)
    # trailing 'Fruit borer: Helicoverpa armigera' form
    if ":" in common:
        head, _, tail = common.partition(":")
        if re.match(r"^\s*[A-Z][a-z]+ [a-z]+\s*$", tail):
            sci = sci or tail.strip()
            common = head.strip()
    if "-" in common and sci is None:
        head, _, tail = common.partition("-")
        if re.match(r"^\s*[A-Z][a-z]+ [a-z]+\s*$", tail):
            sci, common = tail.strip(), head.strip()
    return common.strip(), sci


def main() -> None:
    df = pd.read_csv(LABEL_DB)
    cells = df.pest_or_disease

    print("=" * 70)
    print("Q1  DISTINCT pest_or_disease CELLS")
    print("=" * 70)
    print(f"rows                  : {len(df)}")
    print(f"non-null pest cells   : {cells.notna().sum()}")
    print(f"null pest cells       : {cells.isna().sum()}")
    print(f"distinct raw values   : {cells.nunique()}")
    print(f"distinct normalised   : {cells.dropna().map(normalise).nunique()}")

    print()
    print("=" * 70)
    print("Q2  AFTER SPLITTING COMPOUND CELLS")
    print("=" * 70)
    per_row: list[list[str]] = []
    for c in cells:
        per_row.append([] if pd.isna(c) else split_cell(c))
    df["_mentions"] = per_row

    counts = Counter(len(m) for m in per_row)
    print("mentions per cell:")
    for k in sorted(counts):
        print(f"  {k:2d} mention(s): {counts[k]:4d} rows")
    flat = [m for row in per_row for m in row]
    print(f"total mentions        : {len(flat)}")
    print(f"distinct mentions     : {len(set(flat))}")

    surface = Counter()
    for m in flat:
        common, _ = strip_sci(m)
        if common:
            surface[common.lower()] += 1
    print(f"distinct surface forms (common name, case-folded, sci stripped): {len(surface)}")

    print()
    print("--- surface forms by frequency ---")
    for name, n in surface.most_common():
        print(f"{n:4d}  {name}")

    print()
    print("=" * 70)
    print("Q4  PER-CROP SURFACE FORMS")
    print("=" * 70)
    for slug in scope.CROPS:
        sub = df[df.crop_slug == slug]
        c = Counter()
        for row in sub["_mentions"]:
            for m in row:
                common, _ = strip_sci(m)
                if common:
                    c[common.lower()] += 1
        print(f"\n### {slug}  ({len(sub)} rows, {len(c)} distinct surface forms)")
        for name, n in c.most_common():
            print(f"   {n:3d}  {name}")

    print()
    print("=" * 70)
    print("SCIENTIFIC NAMES FOUND IN-CELL")
    print("=" * 70)
    sci_c = Counter()
    for m in flat:
        _, sci = strip_sci(m)
        if sci:
            sci_c[sci.lower()] += 1
    for s, n in sci_c.most_common():
        print(f"{n:4d}  {s}")

    print()
    print("=" * 70)
    print("Q6  scope.SYNONYMS values vs label_db surface forms")
    print("=" * 70)
    keys = set(surface)
    for k, v in scope.SYNONYMS.items():
        hit_k = k.lower() in keys
        hit_v = v.lower() in keys
        print(f"  {k!r:22s} -> {v!r:22s} | key_in_db={hit_k!s:5s} value_in_db={hit_v}")

    print()
    print("=" * 70)
    print("Q8  surface forms with NO scope.SYNONYMS coverage")
    print("=" * 70)
    syn_space = {k.lower() for k in scope.SYNONYMS} | {
        v.lower() for v in scope.SYNONYMS.values()
    }
    missing = sorted(k for k in surface if k not in syn_space)
    print(f"{len(missing)} of {len(surface)} surface forms uncovered")

    print()
    print("=" * 70)
    print("Q5  scope.TARGETS canonical names vs label_db")
    print("=" * 70)
    per_crop_surface: dict[str, set[str]] = defaultdict(set)
    for slug in scope.CROPS:
        for row in df[df.crop_slug == slug]["_mentions"]:
            for m in row:
                common, _ = strip_sci(m)
                if common:
                    per_crop_surface[slug].add(common.lower())
    for crop, targets in scope.TARGETS.items():
        for t in targets:
            can = t["canonical"].lower()
            exact = can in per_crop_surface[crop]
            substr = [s for s in per_crop_surface[crop] if can in s or s in can]
            print(
                f"  {crop:12s} {t['canonical']:28s} chem={t['chem']:5s} "
                f"exact={exact!s:5s} near={substr[:3]}"
            )


if __name__ == "__main__":
    main()
