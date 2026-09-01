"""
phase7_stepB_kcc_download_filter.py -- download the KCC mirror, explore it,
and produce a first-pass filtered query pool for SFT pairing against
label_db.

Source: Omegaindebt/Kisan_Call_Centre_Transcripts on HuggingFace, chosen
after Phase 7 Step A found data.gov.in's own KCC resource has no working
API. Full provenance and GODL-India attribution recorded in
data/raw/kcc/SOURCES.md.

Reuses crop_mapper.map_crop() for crop matching -- same token-based logic
built for CIB&RC crop cells, on the theory that KCC's "Crop" column is the
same kind of free-text-ish cell crop_mapper was built to parse. This mostly
held. One collision it does NOT handle, found by inspecting every matched
raw value by hand rather than trusting the match:

    'Moth Bean (kidney bean/ deww gram)' -> tokenises to include a bare
    'gram' token ('deww gram', moth bean's Hindi name) that the bare-word
    rule in crop_mapper._WORDS claims as our 'gram' (Bengal gram/chickpea).
    Moth bean (Vigna aconitifolia) is a different pulse entirely. This cell
    was NEVER a defect crop_mapper could have hit against CIB&RC, whose
    crop vocabulary doesn't include moth bean at all -- KCC's vocabulary is
    wider than the corpus crop_mapper was tuned against, and this script
    excludes the 514 rows by name (_KCC_CROP_FALSE_POSITIVES) rather than
    patching the frozen-by-convention, 108-test module for a single-source
    KCC quirk. If Phase 7 finds more of these, crop_mapper itself needs a
    hardening pass with new pinned tests, not more patches here.

STOP after this script per the Phase 7 Step B brief: download, explore,
filter, save, report. No deduplication, no train/test split, no pairing
against label_db yet.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from crop_mapper import map_crop  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "raw" / "kcc"
OUT_PARQUET = OUT_DIR / "kcc_filtered.parquet"
SOURCES_MD = OUT_DIR / "SOURCES.md"
REPORT_MD = REPO_ROOT / "reports" / "phase7_stepB_kcc_download_filter.md"

HF_DATASET = "Omegaindebt/Kisan_Call_Centre_Transcripts"
DOWNLOAD_DATE = "2026-09-01"

STATES = ["MAHARASHTRA", "KARNATAKA", "TELANGANA", "GUJARAT", "MADHYA PRADESH"]
CROPS = ["cotton", "soybean", "tur", "gram", "onion", "tomato", "grape", "pomegranate"]

# QueryType is where KCC actually encodes topic (Category is crop-family:
# Cereals/Vegetables/Oilseeds/... -- a common early misread of this schema).
# 'Plant Protection' (200,142 of 1M rows nationwide) plus 'Disease
# Management' (2,158) -- scope.py's targets are pest+disease, and review of
# the first pass (reports/phase7_stepB_kcc_download_filter.md v1) decided
# to include both rather than risk dropping real disease-query volume.
# 'Bio-Pesticides and Bio-Fertilizers' (5,177) stays out -- it's a
# treatment-method bucket, not obviously a plant-protection query topic.
QUERY_TYPES = ["Plant Protection", "Disease Management"]

# Unicode block ranges for script detection (block detection, not a
# language model -- Marathi and Hindi both render in Devanagari and are
# indistinguishable at this level, which is fine: we need script, not
# language, to decide how to handle non-English KccAns downstream).
_SCRIPT_RANGES = {
    "latin": [(0x0041, 0x005A), (0x0061, 0x007A), (0x00C0, 0x024F)],
    "devanagari": [(0x0900, 0x097F)],
    "telugu": [(0x0C00, 0x0C7F)],
    "kannada": [(0x0C80, 0x0CFF)],
}


def detect_script(text: object) -> str:
    """Dominant Unicode script among a text's letters. 'other' covers
    Gujarati, Tamil, Punjabi, etc. (present in this corpus per the dataset
    card) plus anything with no lettered characters at all.
    """
    if not isinstance(text, str) or not text:
        return "other"
    counts = {name: 0 for name in _SCRIPT_RANGES}
    for ch in text:
        cp = ord(ch)
        for name, ranges in _SCRIPT_RANGES.items():
            if any(lo <= cp <= hi for lo, hi in ranges):
                counts[name] += 1
                break
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else "other"

# See module docstring: 'deww gram' (moth bean's Hindi name) trips the bare
# 'gram' token rule in crop_mapper. Not a real chickpea/Bengal-gram row.
_KCC_CROP_FALSE_POSITIVES = {"Moth Bean (kidney bean/ deww gram)"}


def log(msg: str) -> None:
    print(msg, flush=True)


def load_raw() -> pd.DataFrame:
    from datasets import load_dataset

    log(f"Downloading {HF_DATASET} ...")
    ds = load_dataset(HF_DATASET)["train"]
    df = ds.to_pandas()
    log(f"Loaded {len(df):,} rows.")
    return df


def crop_slug_map(raw_crop_values: pd.Series) -> dict[str, str]:
    """raw KCC Crop string -> our slug, for every distinct value that matches
    exactly one in-scope slug. Excludes known false positives.
    """
    out: dict[str, str] = {}
    for raw in raw_crop_values.dropna().unique():
        if raw in _KCC_CROP_FALSE_POSITIVES:
            continue
        results = map_crop(raw)
        slugs = sorted({r.slug for r in results if r.slug})
        if len(slugs) == 1:
            out[raw] = slugs[0]
        # len(slugs) > 1 never occurs for a single KCC Crop cell in practice
        # (checked by hand in exploration) -- KCC's Crop column names one
        # crop per row, unlike CIB&RC's prose cells crop_mapper was built for.
    return out


def explore(df: pd.DataFrame) -> None:
    log("\n" + "=" * 70)
    log("EXPLORATION")
    log("=" * 70)

    log(f"\nTotal rows: {len(df):,}")
    log(f"CreatedOn range: {df['CreatedOn'].min()} .. {df['CreatedOn'].max()}")
    log(f"year range: {df['year'].min()} .. {df['year'].max()}")
    log("year value counts:\n" + df["year"].value_counts().sort_index().to_string())

    log("\nDistinct StateName: %d" % df["StateName"].nunique())
    in_scope_states = df[df["StateName"].isin(STATES)]["StateName"].value_counts()
    log("Our 5 target states:\n" + in_scope_states.to_string())
    assert "MAHARASHTRA" in df["StateName"].values, "Maharashtra not present!"

    log("\nDistinct Sector: %d" % df["Sector"].nunique())
    log(df["Sector"].value_counts().to_string())

    log("\nDistinct Category: %d (this is crop-FAMILY, not query topic)" % df["Category"].nunique())
    log(df["Category"].value_counts().to_string())

    log("\nDistinct QueryType: %d (this is where query topic actually lives)" % df["QueryType"].nunique())
    qt = df["QueryType"].value_counts()
    log(qt.head(15).to_string())
    log(f"\n'Plant Protection' QueryType rows (nationwide): {qt.get('Plant Protection', 0):,}")
    log(f"'Disease Management' QueryType rows (nationwide): {qt.get('Disease Management', 0):,}")
    log(f"'Bio-Pesticides and Bio-Fertilizers' rows (nationwide): {qt.get('Bio-Pesticides and Bio-Fertilizers', 0):,}")

    cmap = crop_slug_map(df["Crop"])
    log(f"\nDistinct Crop values: {df['Crop'].nunique()}")
    log("Raw KCC Crop values matching our 8 slugs:")
    for raw, slug in sorted(cmap.items(), key=lambda kv: kv[1]):
        cnt = (df["Crop"] == raw).sum()
        log(f"  {slug:12s} <- {raw!r}  ({cnt:,} rows)")
    if "Moth Bean (kidney bean/ deww gram)" in df["Crop"].values:
        cnt = (df["Crop"] == "Moth Bean (kidney bean/ deww gram)").sum()
        log(f"  EXCLUDED false positive: 'Moth Bean (kidney bean/ deww gram)' "
            f"({cnt:,} rows) -- crop_mapper's bare 'gram' rule misfires on "
            f"'deww gram', moth bean's Hindi name. Not chickpea/Bengal gram.")

    df["_crop_slug"] = df["Crop"].map(cmap)
    sample = df[
        (df["StateName"] == "MAHARASHTRA")
        & (df["QueryType"] == "Plant Protection")
        & (df["_crop_slug"].notna())
    ]
    log(f"\nMaharashtra + Plant Protection + one of our 8 crops: {len(sample):,} rows")
    log("Sample 5:")
    for _, row in sample.sample(min(5, len(sample)), random_state=0).iterrows():
        log("-" * 70)
        log(f"  Crop: {row['Crop']} -> {row['_crop_slug']}   District: {row['DistrictName']}   Date: {row['CreatedOn']}")
        log(f"  Q: {row['QueryText']}")
        log(f"  A: {row['KccAns']}")
    df.drop(columns=["_crop_slug"], inplace=True)


def filter_pipeline(df: pd.DataFrame) -> tuple[pd.DataFrame, list[tuple[str, int]]]:
    steps: list[tuple[str, int]] = [("raw", len(df))]

    cur = df[df["StateName"].isin(STATES)].copy()
    steps.append((f"state in {STATES}", len(cur)))

    cur = cur[cur["QueryType"].isin(QUERY_TYPES)]
    steps.append((f"query_type in {QUERY_TYPES}", len(cur)))

    cmap = crop_slug_map(cur["Crop"])
    cur["crop_slug"] = cur["Crop"].map(cmap)
    cur = cur[cur["crop_slug"].notna()]
    steps.append((f"crop in {CROPS} (via crop_mapper, false positives excluded)", len(cur)))

    cur = cur[cur["QueryText"].fillna("").str.split().str.len() >= 4]
    steps.append(("QueryText >= 4 words", len(cur)))

    cur = cur[cur["KccAns"].fillna("").str.len() >= 15]
    steps.append(("KccAns >= 15 chars", len(cur)))

    cur["query_script"] = cur["QueryText"].map(detect_script)
    cur["answer_script"] = cur["KccAns"].map(detect_script)

    return cur, steps


def write_sources_md(row_count: int) -> None:
    SOURCES_MD.parent.mkdir(parents=True, exist_ok=True)
    SOURCES_MD.write_text(
        f"""# data/raw/kcc/ -- source and attribution

## Source

- **Dataset**: Kisan Call Centre (KCC) transcripts -- farmer queries and
  Farm Tele Advisor (FTA) answers, Government of India, Department of
  Agriculture & Farmers Welfare.
- **Mirror used**: HuggingFace dataset
  [`{HF_DATASET}`](https://huggingface.co/datasets/{HF_DATASET})
  (chosen after Phase 7 Step A found data.gov.in's own KCC resource pages
  are unrenderable SPAs with no working public API -- see
  `reports/phase7_stepA_kcc_survey.md`).
- **Download date**: {DOWNLOAD_DATE}
- **Rows in mirror (as downloaded)**: 1,000,000 -- this is a fixed-size
  sample of the underlying ~30 million record KCC archive (2004/2006 to
  present per multiple independent sources), NOT the full archive. The
  sample's own coverage tops out at year=2024 with only 36 rows that year,
  i.e. this mirror is stale by roughly 2.5 years relative to
  {DOWNLOAD_DATE} -- there is effectively no 2024H2-2026 data in it.
- **Filtered rows kept**: {row_count:,} (see
  `reports/phase7_stepB_kcc_download_filter.md` for the full filter
  pipeline and per-step counts).

## License -- Government Open Data License - India (GODL-India)

The underlying KCC data is Government of India content licensed under
GODL-India. Per Phase 7 Step A's survey of the license text:

- Any published artifact using this data (this repo, the training set, any
  paper or model card) must **explicitly publish an attribution statement**
  naming the provider (Department of Agriculture & Farmers Welfare, GoI),
  the source, and the license, **plus a URL/URI/DOI identifying the
  dataset**.
- Suggested attribution line for this project:

  > Contains information from the Kisan Call Centre dataset, Department of
  > Agriculture & Farmers Welfare, Government of India, accessed via
  > https://huggingface.co/datasets/{HF_DATASET}, used under the
  > Government Open Data License - India (GODL-India,
  > https://www.data.gov.in/Godl).

- GODL-India excludes personal information and non-shareable/sensitive data
  from its grant. KCC transcripts are FTA-typed phone call records --
  **any rows carrying a farmer's name or phone number in `QueryText` or
  `KccAns` must be scrubbed before this data ships in a training set.**
  Not yet checked. Do this before Phase 7 Step C.

## Known data-quality caveats (from Step B exploration, not yet resolved)

- `Category` in this schema is a crop-FAMILY field (Cereals, Vegetables,
  Oilseeds, ...), not a query-topic field -- easy to misread given the
  original roadmap's phrasing. Query topic lives in `QueryType`; this
  pipeline filters on `'Plant Protection'` (200,142 of 1,000,000 rows
  nationwide) plus `'Disease Management'` (2,158). `'Bio-Pesticides and
  Bio-Fertilizers'` (5,177) stays out -- a treatment-method bucket, not
  obviously a query-topic match.
- No year cutoff is applied -- all years (2009-2024) are kept. An earlier
  pass filtered to year>=2020 and cut the pool by ~73%; removed after
  review so nothing is lost before dedup/quality decisions happen in
  Step C, where recency can be weighed alongside other signals instead of
  being a hard gate this early.
- `crop_mapper.map_crop()` (built for CIB&RC crop cells) mismatches one KCC
  crop value: `'Moth Bean (kidney bean/ deww gram)'` false-positives as our
  `gram` slug because of the bare `'gram'` token in `'deww gram'` (moth
  bean's Hindi name, unrelated to chickpea/Bengal gram). Excluded by name
  in this script (`_KCC_CROP_FALSE_POSITIVES`); not patched in
  `crop_mapper.py` itself since that module is heavily pinned by
  `tests/test_crop_mapper.py` against CIB&RC vocabulary and a KCC-specific
  fix belongs in a dedicated hardening pass, not a one-off exclusion.
""",
        encoding="utf-8",
    )


def main() -> None:
    df = load_raw()
    explore(df)

    filtered, steps = filter_pipeline(df)

    log("\n" + "=" * 70)
    log("FILTER PIPELINE")
    log("=" * 70)
    for name, count in steps:
        log(f"  {count:>10,}  after: {name}")

    log("\nPer-crop counts after all filters:")
    log(filtered["crop_slug"].value_counts().reindex(CROPS, fill_value=0).to_string())

    log("\nPer-state counts after all filters:")
    log(filtered["StateName"].value_counts().reindex(STATES, fill_value=0).to_string())

    log("\nquery_script distribution:")
    log(filtered["query_script"].value_counts().to_string())

    log("\nanswer_script distribution:")
    log(filtered["answer_script"].value_counts().to_string())

    log("\nquery_script x answer_script cross-tab:")
    log(pd.crosstab(filtered["query_script"], filtered["answer_script"]).to_string())

    log("\n10 sample rows:")
    sample_cols = ["StateName", "crop_slug", "query_script", "answer_script", "QueryText", "KccAns", "CreatedOn"]
    for _, row in filtered[sample_cols].sample(min(10, len(filtered)), random_state=0).iterrows():
        log("-" * 70)
        log(f"  State: {row['StateName']}   Crop: {row['crop_slug']}   Date: {row['CreatedOn']}")
        log(f"  query_script: {row['query_script']}   answer_script: {row['answer_script']}")
        log(f"  Q: {row['QueryText']}")
        log(f"  A: {row['KccAns']}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    filtered.to_parquet(OUT_PARQUET, index=False)
    log(f"\nSaved {len(filtered):,} rows -> {OUT_PARQUET}")

    write_sources_md(len(filtered))
    log(f"Wrote {SOURCES_MD}")


if __name__ == "__main__":
    main()
