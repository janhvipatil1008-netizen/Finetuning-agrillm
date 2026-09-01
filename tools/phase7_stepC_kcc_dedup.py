"""
phase7_stepC_kcc_dedup.py -- three-pass dedup of the KCC query pool:
exact (normalized-hash), near-duplicate (MinHash LSH), semantic (embedding
similarity), then a final quality check.

All three dedup passes are CROP-SCOPED: the dedup key/cluster search never
crosses a crop_slug boundary. This followed a review finding on the first
Phase A run -- a crop-blind version hashed on QueryText alone, and a query
like "attack of sucking pest" (the crop named nowhere in the text itself,
only in the separate Crop column) collapsed onion/tomato/cotton copies of
the same phrasing down to a single surviving row. "Attack of sucking pest"
on cotton and the same text on tomato are different training examples --
different crop means a different Advisory output -- so every pass here
partitions by crop_slug first and dedups within each partition
independently.

Input: data/raw/kcc/kcc_filtered.parquet (18,840 rows, Phase 7 Step B).
Output: data/interim/kcc_deduped.parquet (final, after all 3 passes).
Per-phase checkpoints also written for auditability.

REVISION (Phase C v2): Phase A and B are unchanged and re-loaded from their
existing checkpoints rather than recomputed. Phase C changed two ways after
review of the v1 (threshold=0.92) run found it collapsing genuinely
different pest targets (red mites, mealybug, wilt, flowering all merged
into one cotton cluster of 156):

1. threshold raised 0.92 -> 0.97.
2. a pest-name guard: cosine-similarity clusters are formed exactly as
   before, then each candidate cluster is checked with
   src/pest_matcher.py before it's allowed to collapse -- if two members
   resolve to different canonical pest names (crop_slug as context), the
   cluster is split so they never merge. Members naming no pest (generic
   queries -- "Asked about plant protection") remain freely clusterable.
   pest_matcher.match_pest() resolves a pest NAME, not a sentence, so this
   file's extract_pest_tag() first scans each QueryText for any curated
   surface form from data/final/pest_synonym_table.csv appearing as a
   whole word/phrase, then resolves the longest hit through match_pest().
   A query naming no recognisable pest term returns None and never blocks
   a merge.

Also: two known-defect exclusions were added before Phase C runs, per
review of the v1 run's 20-row spot check. What was reported as "the
mojibake row" and "the 2 crop-mismatch rows" turned out, on a systematic
re-check across all 7,116 Phase-B rows (not just the one 20-row sample),
to be a much larger class -- see exclude_known_defects() below and the
report for the corrected counts.
"""
from __future__ import annotations

import re
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
from pest_matcher import load_table, match_pest  # noqa: E402

IN_PARQUET = REPO_ROOT / "data" / "raw" / "kcc" / "kcc_filtered.parquet"
INTERIM_DIR = REPO_ROOT / "data" / "interim"
PHASE_A_OUT = INTERIM_DIR / "kcc_dedup_phaseA_exact.parquet"
PHASE_B_OUT = INTERIM_DIR / "kcc_dedup_phaseB_minhash.parquet"
PHASE_C_OUT = INTERIM_DIR / "kcc_dedup_phaseC_semantic.parquet"
FINAL_OUT = INTERIM_DIR / "kcc_deduped.parquet"

MOJIBAKE_RE = re.compile(r"\?{4,}")

# The two mismatches flagged by hand in the v1 20-row spot check, expanded
# after a systematic re-check found the SAME QueryText recurs under
# multiple crop_slug values -- some correct, some not. Excluding by exact
# (QueryText, crop_slug) pair rather than by row position, so this is
# robust to the pipeline re-running. The soybean-tagged instance of the
# "soyabean...flower drop" text is deliberately NOT here -- that one's
# crop_slug is correct.
KNOWN_CROP_MISMATCHES = {
    ("Farmer wants to know about control measures of red spider in Bottleguard plant?", "tomato"),
    ("How to control flower drop problem in soyabean crop?", "gram"),
    ("How to control flower drop problem in soyabean crop?", "tomato"),
}

CROPS = ["cotton", "soybean", "tur", "gram", "onion", "tomato", "grape", "pomegranate"]
MIN_VIABLE_ROWS = 30

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")

RANDOM_STATE = 0


def log(msg: str) -> None:
    print(msg, flush=True)


# --------------------------------------------------------------------------
# shared helpers
# --------------------------------------------------------------------------

def normalize(text: object) -> str:
    """lowercase, strip punctuation, collapse whitespace. Unicode-aware
    (\\w matches Devanagari/Telugu/etc. word characters too) since
    QueryText is ~all-Latin but this function must not silently mangle the
    rare non-Latin query.
    """
    s = "" if not isinstance(text, str) else text
    s = s.lower()
    s = _PUNCT_RE.sub(" ", s)
    s = _SPACE_RE.sub(" ", s).strip()
    return s


def normalized_hash(text: object) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


class UnionFind:
    """Tiny disjoint-set for turning pairwise near-duplicate edges into
    clusters. Keys are the DataFrame index values.
    """

    def __init__(self, keys) -> None:
        self.parent = {k: k for k in keys}

    def find(self, x):
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a, b) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb

    def clusters(self) -> dict:
        out: dict = {}
        for k in self.parent:
            out.setdefault(self.find(k), []).append(k)
        return out


def _keep_longest(df: pd.DataFrame, members: list) -> object:
    """Longest QueryText wins; ties broken by earliest CreatedOn for
    determinism (not specified by the brief, but a tie needs SOME rule).
    """
    sub = df.loc[members]
    lengths = sub["QueryText"].fillna("").str.len()
    max_len = lengths.max()
    tied = sub[lengths == max_len]
    if len(tied) == 1:
        return tied.index[0]
    created = pd.to_datetime(tied["CreatedOn"], errors="coerce")
    return created.idxmin() if created.notna().any() else tied.index[0]


# --------------------------------------------------------------------------
# known-defect exclusion (mojibake, crop/QueryText mismatch)
# --------------------------------------------------------------------------

def exclude_known_defects(df: pd.DataFrame) -> pd.DataFrame:
    log("\n" + "=" * 70)
    log("KNOWN-DEFECT EXCLUSION (before Phase C)")
    log("=" * 70)

    before = len(df)

    moji_mask = (
        df["QueryText"].astype(str).str.contains(MOJIBAKE_RE)
        | df["KccAns"].astype(str).str.contains(MOJIBAKE_RE)
    )
    moji_idx = set(df.index[moji_mask])
    log(f"\nMojibake scan (QueryText or KccAns matches {MOJIBAKE_RE.pattern!r}):")
    log(f"  {len(moji_idx):,} rows -- systematic re-check, NOT just the single row spotted")
    log("  by chance in the v1 20-row sample. That row is included in this count.")
    log("  By crop: " + df.loc[list(moji_idx), "crop_slug"].value_counts().to_string().replace("\n", "  "))

    mismatch_mask = df.apply(
        lambda r: (r["QueryText"], r["crop_slug"]) in KNOWN_CROP_MISMATCHES, axis=1
    )
    mismatch_idx = set(df.index[mismatch_mask])
    log(f"\nKnown crop-mismatch text/crop_slug pairs: {len(mismatch_idx):,} rows")
    log("  (this is 3, not 2 -- the 'soyabean...flower drop' text recurs 3x under")
    log("  different crop_slug values; one of the three, tagged 'soybean', is the")
    log("  CORRECT tagging and is kept; the gram- and tomato-tagged copies are not.)")

    exclude_idx = moji_idx | mismatch_idx
    log(f"\nTotal rows excluded: {len(exclude_idx):,} (mojibake ∪ crop-mismatch, "
        f"overlap={len(moji_idx & mismatch_idx)})")

    kept = df.drop(index=list(exclude_idx))
    log(f"Rows before: {before:,}")
    log(f"Rows after:  {len(kept):,}")
    return kept


# --------------------------------------------------------------------------
# pest-name guard (Phase C)
# --------------------------------------------------------------------------

_PEST_TABLE = load_table()
_SURFACE_FORMS_CACHE: dict[str, list[str]] = {}


def _surface_forms_for(crop_slug: str) -> list[str]:
    """Curated pest surface forms for this crop, from pest_synonym_table.csv,
    longest first so a more specific phrase ('red spider mites') is tried
    before a shorter one ('mite') that would also match. match_pest()'s own
    crop-independent fallback (see its module docstring) still applies for
    names that mean one thing on every crop -- that's the "it already
    handles the synonym resolution" pest_matcher provides; this function
    only needs to find WHICH substring of the query to hand it.
    """
    if crop_slug not in _SURFACE_FORMS_CACHE:
        forms = _PEST_TABLE.surface_forms(crop_slug)
        _SURFACE_FORMS_CACHE[crop_slug] = sorted(forms, key=len, reverse=True)
    return _SURFACE_FORMS_CACHE[crop_slug]


def extract_pest_tag(crop_slug: str, query_text: object) -> str | None:
    """Scan QueryText for a curated pest surface form and resolve it to a
    canonical name via pest_matcher, crop-scoped. None means no recognisable
    pest name was found -- NOT that the query has no pest, just that this
    heuristic found nothing to guard on, so it stays freely clusterable.
    """
    norm_query = normalize(query_text)
    if not norm_query:
        return None
    for surface in _surface_forms_for(crop_slug):
        norm_surface = normalize(surface)
        if not norm_surface:
            continue
        if re.search(rf"\b{re.escape(norm_surface)}\b", norm_query):
            result = match_pest(crop_slug, surface, _PEST_TABLE)
            if result.matched:
                return result.canonical_name
    return None


def _split_cluster_by_pest_tag(members: list, tags: dict) -> list[list]:
    """A raw cosine cluster splits into one group per distinct non-None pest
    tag among its members, plus (if any) one group for the untagged
    remainder. Untagged members do NOT get folded into a tagged group --
    that would mean guessing which side they belong on, exactly the kind of
    guess this codebase avoids elsewhere (crop_mapper, dose_parser).
    """
    non_none = {tags[m] for m in members if tags[m] is not None}
    if len(non_none) <= 1:
        return [members]
    groups: dict[str, list] = {}
    untagged: list = []
    for m in members:
        t = tags[m]
        (untagged if t is None else groups.setdefault(t, [])).append(m)
    out = list(groups.values())
    if untagged:
        out.append(untagged)
    return out


# --------------------------------------------------------------------------
# Phase A -- exact dedup, crop-scoped
# --------------------------------------------------------------------------

def phase_a_exact_dedup(df: pd.DataFrame) -> pd.DataFrame:
    log("\n" + "=" * 70)
    log("PHASE A -- exact dedup, key = (crop_slug, normalized QueryText hash)")
    log("=" * 70)

    before = len(df)
    df = df.copy()
    df["_norm_hash"] = df["QueryText"].map(normalized_hash)
    df["_key"] = list(zip(df["crop_slug"], df["_norm_hash"]))
    df["_created_dt"] = pd.to_datetime(df["CreatedOn"], errors="coerce")

    group_sizes = df.groupby("_key").size()
    dup_groups = group_sizes[group_sizes > 1]
    log(f"\nDistinct (crop_slug, normalized-QueryText) keys: {df['_key'].nunique():,}")
    log(f"Groups with >1 copy: {len(dup_groups):,} (covering {dup_groups.sum():,} rows)")

    df_sorted = df.sort_values("_created_dt", na_position="last")
    kept = df_sorted.drop_duplicates(subset="_key", keep="first").sort_index()

    after = len(kept)
    removed = before - after
    log(f"\nRows before: {before:,}")
    log(f"Rows after:  {after:,}")
    log(f"Removed:     {removed:,} ({removed / before:.1%})")

    log("\n3 example duplicate groups (same crop, same normalized text):")
    example_keys = dup_groups.sort_values(ascending=False).index[:3]
    for key in example_keys:
        group = df[df["_key"] == key]
        crop, _ = key
        n = len(group)
        example_text = group.iloc[0]["QueryText"]
        log("-" * 70)
        log(f"  {n} copies -- crop={crop}  normalized: {normalize(example_text)!r}")
        for _, row in group.head(4).iterrows():
            log(f"    [{row['CreatedOn']}] {row['StateName']:12s} {row['QueryText']!r}")
        if n > 4:
            log(f"    ... and {n - 4} more")

    return kept.drop(columns=["_norm_hash", "_key", "_created_dt"])


# --------------------------------------------------------------------------
# Phase B -- MinHash LSH near-dup, crop-scoped
# --------------------------------------------------------------------------

def _shingles(text: str, k: int = 3) -> set:
    words = text.split()
    if len(words) < k:
        return {text} if text else set()
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def _minhash_dedup_one_crop(sub: pd.DataFrame, num_perm: int, threshold: float):
    """Cluster one crop's rows by MinHash LSH Jaccard similarity on
    word-3-shingles. Returns (kept_index_list, list_of_cluster_member_lists
    for clusters with >1 member, for reporting).
    """
    from datasketch import MinHash, MinHashLSH

    norms = sub["QueryText"].map(normalize)
    minhashes = {}
    for idx, text in norms.items():
        mh = MinHash(num_perm=num_perm)
        for sh in _shingles(text):
            mh.update(sh.encode("utf-8"))
        minhashes[idx] = mh

    lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
    for idx, mh in minhashes.items():
        lsh.insert(str(idx), mh)

    uf = UnionFind(sub.index)
    for idx, mh in minhashes.items():
        for match_key in lsh.query(mh):
            match_idx = int(match_key)
            if match_idx != idx:
                uf.union(idx, match_idx)

    clusters = uf.clusters()
    kept = []
    multi_clusters = []
    for members in clusters.values():
        if len(members) == 1:
            kept.append(members[0])
        else:
            kept.append(_keep_longest(sub, members))
            multi_clusters.append(members)
    return kept, multi_clusters


def phase_b_minhash_dedup(df: pd.DataFrame, num_perm: int = 128, threshold: float = 0.7) -> pd.DataFrame:
    log("\n" + "=" * 70)
    log(f"PHASE B -- MinHash LSH near-dup (num_perm={num_perm}, threshold={threshold}), crop-scoped")
    log("=" * 70)

    before = len(df)
    all_kept_idx = []
    all_multi_clusters = []  # (crop, members) for reporting
    for crop in CROPS:
        sub = df[df["crop_slug"] == crop]
        if sub.empty:
            continue
        kept_idx, multi_clusters = _minhash_dedup_one_crop(sub, num_perm, threshold)
        all_kept_idx.extend(kept_idx)
        all_multi_clusters.extend((crop, m) for m in multi_clusters)

    kept = df.loc[all_kept_idx].sort_index()
    after = len(kept)
    removed = before - after
    log(f"\nRows before: {before:,}")
    log(f"Rows after:  {after:,}")
    log(f"Removed:     {removed:,} ({removed / before:.1%})")
    log(f"Near-dup clusters found (size > 1): {len(all_multi_clusters):,}")

    log("\n3 example near-duplicate clusters:")
    all_multi_clusters.sort(key=lambda cm: -len(cm[1]))
    for crop, members in all_multi_clusters[:3]:
        log("-" * 70)
        log(f"  crop={crop}  cluster size={len(members)}")
        for idx in members[:5]:
            row = df.loc[idx]
            log(f"    [{row['CreatedOn']}] {row['QueryText']!r}")
        if len(members) > 5:
            log(f"    ... and {len(members) - 5} more")

    return kept


# --------------------------------------------------------------------------
# Phase C -- semantic dedup via embeddings + FAISS, crop-scoped
# --------------------------------------------------------------------------

def _semantic_dedup_one_crop(sub: pd.DataFrame, embeddings: np.ndarray, threshold: float, crop_slug: str):
    import faiss

    n = len(sub)
    idx_list = list(sub.index)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings.astype(np.float32))

    k = min(n, 50)
    sims, neighbors = index.search(embeddings.astype(np.float32), k)

    uf = UnionFind(idx_list)
    for i in range(n):
        for sim, j in zip(sims[i], neighbors[i]):
            if j == -1 or j == i:
                continue
            if sim > threshold:
                uf.union(idx_list[i], idx_list[j])

    raw_clusters = uf.clusters()

    tags = {idx: extract_pest_tag(crop_slug, sub.loc[idx, "QueryText"]) for idx in idx_list}

    kept = []
    multi_clusters = []      # (raw_members,) size > 1 before the pest-guard split, for reporting
    split_events = []        # (raw_members, [final_groups]) where the guard actually split something
    for raw_members in raw_clusters.values():
        if len(raw_members) == 1:
            kept.append(raw_members[0])
            continue
        final_groups = _split_cluster_by_pest_tag(raw_members, tags)
        multi_clusters.append(raw_members)
        if len(final_groups) > 1:
            split_events.append((raw_members, final_groups, tags))
        for group in final_groups:
            if len(group) == 1:
                kept.append(group[0])
            else:
                kept.append(_keep_longest(sub, group))
    return kept, multi_clusters, split_events


def phase_c_semantic_dedup(df: pd.DataFrame, model_name: str, threshold: float = 0.97) -> pd.DataFrame:
    log("\n" + "=" * 70)
    log(f"PHASE C -- semantic dedup via embeddings (model={model_name}, cosine>{threshold}), "
        f"crop-scoped, pest-name guarded")
    log("=" * 70)

    from sentence_transformers import SentenceTransformer

    log(f"\nLoading {model_name} ...")
    model = SentenceTransformer(model_name)

    before = len(df)
    all_kept_idx = []
    all_multi_clusters = []
    all_split_events = []
    for crop in CROPS:
        sub = df[df["crop_slug"] == crop]
        if sub.empty:
            continue
        texts = sub["QueryText"].fillna("").tolist()
        emb = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        kept_idx, multi_clusters, split_events = _semantic_dedup_one_crop(sub, emb, threshold, crop)
        all_kept_idx.extend(kept_idx)
        all_multi_clusters.extend((crop, m) for m in multi_clusters)
        all_split_events.extend((crop, raw, groups, tags) for raw, groups, tags in split_events)
        log(f"  {crop:12s} {len(sub):5,} -> {len(kept_idx):5,}  "
            f"({len(multi_clusters)} raw clusters, {len(split_events)} split by pest guard)")

    kept = df.loc[all_kept_idx].sort_index()
    after = len(kept)
    removed = before - after
    log(f"\nRows before: {before:,}")
    log(f"Rows after:  {after:,}")
    log(f"Removed:     {removed:,} ({removed / before:.1%})")
    log(f"\nRaw cosine clusters (size > 1): {len(all_multi_clusters):,}")
    log(f"Clusters the pest guard split apart: {len(all_split_events):,}")

    log("\nLargest raw cluster size: "
        f"{max((len(m) for _, m in all_multi_clusters), default=0)}")

    log("\n3 example clusters the pest guard split apart (largest raw cluster first):")
    all_split_events.sort(key=lambda e: -len(e[1]))
    for crop, raw_members, groups, tags in all_split_events[:3]:
        log("-" * 70)
        log(f"  crop={crop}  raw cluster size={len(raw_members)} -> split into {len(groups)} groups")
        for group in sorted(groups, key=len, reverse=True):
            group_tags = {tags[m] for m in group}
            tag_label = group_tags.pop() if len(group_tags) == 1 else "MIXED/untagged"
            log(f"    group (tag={tag_label!r}, size={len(group)}):")
            for idx in group[:3]:
                row = df.loc[idx]
                log(f"      {row['QueryText']!r}")
            if len(group) > 3:
                log(f"      ... and {len(group) - 3} more")

    return kept


# --------------------------------------------------------------------------
# Phase D -- final quality check
# --------------------------------------------------------------------------

def phase_d_final_check(
    original_n: int, after_a: pd.DataFrame, after_b: pd.DataFrame,
    after_defects: pd.DataFrame, after_c: pd.DataFrame,
) -> None:
    log("\n" + "=" * 70)
    log("PHASE D -- final quality check")
    log("=" * 70)

    log("\nFull pipeline cascade:")
    log(f"  {original_n:>10,}  raw (Phase 7 Step B output)")
    log(f"  {len(after_a):>10,}  after Phase A (exact, crop-scoped)")
    log(f"  {len(after_b):>10,}  after Phase B (MinHash LSH, crop-scoped)")
    log(f"  {len(after_defects):>10,}  after known-defect exclusion (mojibake + crop-mismatch)")
    log(f"  {len(after_c):>10,}  after Phase C v2 (semantic, threshold=0.97, pest-guarded)  <- FINAL")

    log("\nPer-crop counts, final:")
    counts = after_c["crop_slug"].value_counts().reindex(CROPS, fill_value=0)
    log(counts.to_string())

    thin = counts[counts < MIN_VIABLE_ROWS]
    if len(thin):
        log(f"\nFLAGGED -- below minimum viable count ({MIN_VIABLE_ROWS}):")
        log(thin.to_string())
    else:
        log(f"\nAll crops >= minimum viable count ({MIN_VIABLE_ROWS}). None flagged.")

    log("\n20-row random sample:")
    sample = after_c.sample(min(20, len(after_c)), random_state=RANDOM_STATE)
    for _, row in sample.iterrows():
        log("-" * 70)
        log(f"  {row['StateName']:14s} {row['crop_slug']:12s} {row['CreatedOn']}")
        log(f"  Q: {row['QueryText']}")
        log(f"  A: {row['KccAns']}")

    log("\nRe-hash check for exact duplicates remaining (crop-scoped key):")
    check_hash = after_c["QueryText"].map(normalized_hash)
    check_key = list(zip(after_c["crop_slug"], check_hash))
    n_dupe_keys = len(check_key) - len(set(check_key))
    log(f"  Exact (crop, normalized-text) duplicates remaining: {n_dupe_keys}")
    if n_dupe_keys == 0:
        log("  CONFIRMED: zero exact duplicates remain.")


def main() -> None:
    # Phase A and B are unchanged per the brief -- reload their existing
    # checkpoints rather than recomputing. original_n and after_a are only
    # needed for the Phase D cascade printout.
    log(f"Loading {IN_PARQUET} (for the cascade's raw count) ...")
    original_n = len(pd.read_parquet(IN_PARQUET))

    log(f"Loading Phase A checkpoint: {PHASE_A_OUT}")
    after_a = pd.read_parquet(PHASE_A_OUT)
    log(f"  {len(after_a):,} rows (unchanged)")

    log(f"Loading Phase B checkpoint: {PHASE_B_OUT}")
    after_b = pd.read_parquet(PHASE_B_OUT)
    log(f"  {len(after_b):,} rows (unchanged)")

    after_defects = exclude_known_defects(after_b)

    after_c = phase_c_semantic_dedup(
        after_defects, model_name="paraphrase-multilingual-MiniLM-L12-v2", threshold=0.97,
    )
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    after_c.to_parquet(PHASE_C_OUT, index=False)
    log(f"\nSaved {len(after_c):,} rows -> {PHASE_C_OUT}")

    phase_d_final_check(original_n, after_a, after_b, after_defects, after_c)

    after_c.to_parquet(FINAL_OUT, index=False)
    log(f"\nSaved final {len(after_c):,} rows -> {FINAL_OUT}")
    log("\nSTOP -- Phase C v2 run (Phase A/B kept as-is). Not committed. Waiting for review.")


if __name__ == "__main__":
    main()
