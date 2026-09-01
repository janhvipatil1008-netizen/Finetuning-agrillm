"""Phase 4 (crop) Step A — survey CIB&RC crop strings against scope.py's 8 slugs.

Read-only. Proposes a mapping; writes a report. No mapping module is created.

Matching is TOKEN-based, not substring-based. Substring matching on this
vocabulary is actively dangerous: 'tur' is inside 'Turmeric' and
'Floriculture', 'gram' is inside 'Black gram' (a different crop), and 'pea'
is inside both 'Pigeon pea' (in scope, = tur) and 'Green pea' (not).
"""
from __future__ import annotations

import collections
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

import scope  # noqa: E402

FILES = ["insecticides", "fungicides", "bio_insecticides", "bio_fungicides"]
DATA_KINDS = {"ordinal_6", "fallback_subset"}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


# Compounds CIB&RC prints with and without a space. Split so that token
# matching sees the same two words either way.
GLUED = {
    "pigeonpea": "pigeon pea", "pigeonpeas": "pigeon pea",
    "blackgram": "black gram", "blackgrams": "black gram",
    "greengram": "green gram", "greengrams": "green gram",
    "redgram": "red gram", "bengalgram": "bengal gram",
    "chickpea": "chick pea", "chickpeas": "chick pea",
    "soyabean": "soya bean", "soybean": "soya bean",
    "soyabeans": "soya bean", "soybeans": "soya bean",
    "urdbean": "urd bean", "mungbean": "mung bean",
    "cowpea": "cow pea", "cowpeas": "cow pea",
    "greenpea": "green pea", "frenchbean": "french bean",
    "kidneybean": "kidney bean", "clusterbeans": "cluster bean",
    "pearlmillet": "pearl millet", "sugarbeet": "sugar beet",
    "horsegram": "horse gram",
}


def tokens(s: str) -> list[str]:
    raw = re.sub(r"[^a-z]+", " ", norm(s).lower()).split()
    # OCR splits a leading capital off its word: 'T omato', 'G rapes'.
    merged: list[str] = []
    i = 0
    while i < len(raw):
        if len(raw[i]) == 1 and i + 1 < len(raw):
            merged.append(raw[i] + raw[i + 1])
            i += 2
        else:
            merged.append(raw[i])
            i += 1
    out: list[str] = []
    for t in merged:
        out.extend(GLUED.get(t, t).split())
    return out


# Two-word crop names that must be consumed BEFORE any bare-word rule, so
# that 'Red gram' is tur and 'Black gram' is neither. Value None == a real
# crop that is simply out of scope; matching it removes the words so the bare
# 'gram' rule cannot then claim them.
PHRASES: list[tuple[tuple[str, ...], str | None]] = [
    (("black", "gram"), None),
    (("green", "gram"), None),
    (("horse", "gram"), None),
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
    (("red", "gram"), "tur"),
    (("pigeon", "pea"), "tur"),
    (("bengal", "gram"), "gram"),
    (("chick", "pea"), "gram"),
    (("soya", "bean"), "soybean"),
]

# Single words, applied only to tokens no phrase consumed.
WORDS: dict[str, str] = {
    "cotton": "cotton", "kapas": "cotton",
    "tur": "tur", "toor": "tur", "arhar": "tur",
    "gram": "gram", "chana": "gram",
    "onion": "onion", "onions": "onion", "kanda": "onion",
    "tomato": "tomato", "tomatoes": "tomato", "tamatar": "tomato",
    "grape": "grape", "grapes": "grape", "grapevine": "grape", "draksha": "grape",
    "pomegranate": "pomegranate", "pomegranates": "pomegranate",
    "anar": "pomegranate", "dalimb": "pomegranate",
}

# The crop cell absorbed pest/disease text from the neighbouring column.
PEST_BLEED = re.compile(
    r"helicoverpa|heliothis|bollworm|whitefly|spodoptera|diamond|blast"
    r"|sheath\s*blight|alternaria|thrips|aphid", re.I)

# An application-method qualifier, not a different crop.
METHOD_QUALIFIER = re.compile(
    r"soil\s*drench|foliar|nursery|seedlings?|seed\s*treatment|on\s+ground",
    re.I)


def slugs_for(s: str) -> set[str]:
    toks = tokens(s)
    hits: set[str] = set()
    i = 0
    consumed = [False] * len(toks)
    for phrase, slug in PHRASES:
        n = len(phrase)
        for i in range(len(toks) - n + 1):
            if any(consumed[i:i + n]):
                continue
            if tuple(toks[i:i + n]) == phrase:
                for j in range(i, i + n):
                    consumed[j] = True
                if slug:
                    hits.add(slug)
    for i, t in enumerate(toks):
        if consumed[i]:
            continue
        if t in WORDS:
            hits.add(WORDS[t])
    return hits


def collect() -> collections.Counter:
    dist: collections.Counter = collections.Counter()
    for f in FILES:
        p = ROOT / "data" / "interim" / f"{f}_20260331_raw.csv"
        for r in csv.DictReader(open(p, encoding="utf-8")):
            if r["assignment_kind"] not in DATA_KINDS:
                continue
            dist[norm(r["crop"])] += 1
    return dist


if __name__ == "__main__":
    dist = collect()
    by_slug = collections.defaultdict(list)
    multi, out_of_scope = [], []
    for s in dist:
        if not s:
            continue
        hits = slugs_for(s)
        if not hits:
            out_of_scope.append(s)
        elif len(hits) == 1:
            by_slug[next(iter(hits))].append(s)
        else:
            multi.append((s, sorted(hits)))

    print(f"distinct crop strings : {len(dist)}")
    print(f"data-row cells        : {sum(dist.values())}")
    print(f"blank crop cells      : {dist['']} (1 distinct string)\n")

    print("=== proposed mapping, by slug ===")
    n_str = n_cell = 0
    for slug in scope.CROPS:
        ss = sorted(by_slug[slug])
        c = sum(dist[s] for s in ss)
        n_str += len(ss)
        n_cell += c
        print(f"\n{slug}  —  {len(ss)} strings / {c} cells")
        for s in ss:
            flags = []
            if PEST_BLEED.search(s):
                flags.append("pest text bled in")
            if METHOD_QUALIFIER.search(s):
                flags.append("method qualifier")
            if re.search(r"[,/&]", s):
                flags.append("MULTI-CROP?")
            tail = ("   <-- " + "; ".join(flags)) if flags else ""
            print(f"    x{dist[s]:<4} {s!r}{tail}")

    print("\n=== strings naming MORE THAN ONE in-scope slug ===")
    for s, hits in sorted(multi):
        print(f"    x{dist[s]:<4} {hits}  {s[:88]!r}")

    print("\n=== totals ===")
    print(f"  in-scope, single slug : {n_str} strings / {n_cell} cells")
    print(f"  multi-slug            : {len(multi)} strings / "
          f"{sum(dist[s] for s, _ in multi)} cells")
    print(f"  out of scope          : {len(out_of_scope)} strings / "
          f"{sum(dist[s] for s in out_of_scope)} cells")
    print(f"  blank                 : 1 string / {dist['']} cells")
    print(f"  check: {n_str + len(multi) + len(out_of_scope) + 1} == {len(dist)}")

    print("\n=== out-of-scope strings mentioning an in-scope-sounding word ===")
    print("    (review these: each must be a genuinely DIFFERENT crop)")
    for s in sorted(out_of_scope):
        if re.search(r"gram|pea\b|bean|vegetable|soy|cotton|tomato|onion|grape"
                     r"|pomegran|tur\b|arhar", s, re.I):
            print(f"    x{dist[s]:<4} {s[:88]!r}")
