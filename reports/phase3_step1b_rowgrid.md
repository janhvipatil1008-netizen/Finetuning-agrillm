# Phase 3, Step 1b — Row-Local Grid (design & validation only)

**No extracted data written to disk.** The only artefacts are this report and `data/interim/phase3_step1b_rowgrid.json` (gitignored) — per-row segment geometry and assignment results. No Step 2 extraction has run.

Full method — including two rejected versions of the `source_column_merged` check and why each was rejected — is in `tools/phase3_step1b_rowgrid.py`'s module docstring. This report is the validation trail.

## 1. Validation on the 8 failing rows of insecticides p87

Step 1 flagged rows 6, 7, 11, 12, 14-17 of p87: a dilution value (`500` or `NA`) was landing in the PHI band alongside the real PHI value, because these rows' a.i./formulation doses are compound expressions that physically widen the row past where the static `combination-product` boundary expected the later fields to sit.

The fix: merge raw camelot cells using each cell's own `right` border flag (`True` = a real ruled line was detected there) instead of the file-wide calibrated x-boundary. Each row's OWN rule positions, compared against the calibrated grid:

Calibrated `combination-product` boundaries (Step 1): crop/pest_or_disease @ 109.4, pest_or_disease/dose_ai @ 202.3, dose_ai/dose_formulation @ 309.8, dose_formulation/dilution_water @ 369.0, dilution_water/waiting_period_phi @ 422.1

**Row 6** — this row's own real-rule segments (x0, x1, text):

| # | x0 | x1 | text |
|---|---|---|---|
| 0 | 36.2 | 100.8 | Tomato |
| 1 | 100.8 | 246.4 | Thrips (Thrips tabaci), Aphids  (Aphis gossypii), Whiteflies  (Bemisia |
| 2 | 246.4 | 379.8 | 108 (Spiropidion 60 +  Acetamiprid 48) – 135  (Spiropidion 75 +  Aceta |
| 3 | 379.8 | 444.9 | 200 - 250 |
| 4 | 444.9 | 499.3 | 500 |
| 5 | 499.3 | 589.1 | 5 |

-> resolved (ordinal, 6 of 6 segments): crop='Tomato', pest='Thrips (Thrips tabaci), Aphids  (Aphis gossypii), Whiteflies  (Bemisia tabaci)', dose_ai='108 (Spiropidion 60 +  Acetamiprid 48) – 135  (Spiropidion 75 +  Acetamiprid 60)', dose_form='200 - 250', **dilution='500'**, **phi='5'**

**Row 7** — this row's own real-rule segments (x0, x1, text):

| # | x0 | x1 | text |
|---|---|---|---|
| 0 | 36.2 | 100.8 | Cotton |
| 1 | 100.8 | 246.4 | Mealy bugs (Phenococcus  solenopsis, Thrips (Thips  tabaci), Jassids ( |
| 2 | 246.4 | 379.8 | 108 (Spiropidion 60 +  Acetamiprid 48) – 135  (Spiropidion 75 +  Aceta |
| 3 | 379.8 | 444.9 | 200 - 250 |
| 4 | 444.9 | 499.3 | 500 |
| 5 | 499.3 | 589.1 | 85 |

-> resolved (ordinal, 6 of 6 segments): crop='Cotton', pest='Mealy bugs (Phenococcus  solenopsis, Thrips (Thips  tabaci), Jassids (Amrasca  devastans), Aphids (Aphis  gossypii), Whiteflies (Bemisia  tabaci)', dose_ai='108 (Spiropidion 60 +  Acetamiprid 48) – 135  (Spiropidion 75 +  Acetamiprid 60)', dose_form='200 - 250', **dilution='500'**, **phi='85'**

**Row 11** — this row's own real-rule segments (x0, x1, text):

| # | x0 | x1 | text |
|---|---|---|---|
| 0 | 36.2 | 100.8 | Rice |
| 1 | 100.8 | 251.9 | Stem borer (Scirpophaga  incertulas) and leaf folder  (Cnaphalocrocis  |
| 2 | 251.9 | 347.0 | 40 + 60 – 50 + 75 |
| 3 | 347.0 | 425.4 | 10 - 12.5 |
| 4 | 425.4 | 479.9 | NA |
| 5 | 479.9 | 589.1 | 65 |

-> resolved (ordinal, 6 of 6 segments): crop='Rice', pest='Stem borer (Scirpophaga  incertulas) and leaf folder  (Cnaphalocrocis medinalis)', dose_ai='40 + 60 – 50 + 75', dose_form='10 - 12.5', **dilution='NA'**, **phi='65'**

**Row 12** — this row's own real-rule segments (x0, x1, text):

| # | x0 | x1 | text |
|---|---|---|---|
| 0 | 36.2 | 100.8 | Sugarcane |
| 1 | 100.8 | 251.9 | Early shoot borer (Chilo  infuscatellus) and White grub  (Holotrichias |
| 2 | 251.9 | 347.0 | 50 + 75 – 60 + 90 |
| 3 | 347.0 | 425.4 | 12.5 – 15 |
| 4 | 425.4 | 479.9 | NA |
| 5 | 479.9 | 589.1 | 314 |

-> resolved (ordinal, 6 of 6 segments): crop='Sugarcane', pest='Early shoot borer (Chilo  infuscatellus) and White grub  (Holotrichiaserra ta)', dose_ai='50 + 75 – 60 + 90', dose_form='12.5 – 15', **dilution='NA'**, **phi='314'**

**Row 14** — this row's own real-rule segments (x0, x1, text):

| # | x0 | x1 | text |
|---|---|---|---|
| 0 | 36.2 | 100.8 | Okra |
| 1 | 100.8 | 270.4 | Fruit & Shoot borer, Aphids,  Whitefly and Mites |
| 2 | 270.4 | 351.5 | 45 +90 |
| 3 | 351.5 | 420.2 | 375 |
| 4 | 420.2 | 488.1 | 500 |
| 5 | 488.1 | 589.1 | 3 |

-> resolved (ordinal, 6 of 6 segments): crop='Okra', pest='Fruit & Shoot borer, Aphids,  Whitefly and Mites', dose_ai='45 +90', dose_form='375', **dilution='500'**, **phi='3'**

**Row 15** — this row's own real-rule segments (x0, x1, text):

| # | x0 | x1 | text |
|---|---|---|---|
| 0 | 36.2 | 100.8 | Cabbage |
| 1 | 100.8 | 270.4 | Diamond back moth, Tobacco  caterpillar and Aphids |
| 2 | 270.4 | 351.5 | 45 +90 |
| 3 | 351.5 | 420.2 | 375 |
| 4 | 420.2 | 488.1 | 500 |
| 5 | 488.1 | 589.1 | 7 |

-> resolved (ordinal, 6 of 6 segments): crop='Cabbage', pest='Diamond back moth, Tobacco  caterpillar and Aphids', dose_ai='45 +90', dose_form='375', **dilution='500'**, **phi='7'**

**Row 16** — this row's own real-rule segments (x0, x1, text):

| # | x0 | x1 | text |
|---|---|---|---|
| 0 | 36.2 | 100.8 | Chilli |
| 1 | 100.8 | 270.4 | Fruit Borer, Thrips, Whitefly and  Mites |
| 2 | 270.4 | 351.5 | 45 +90 |
| 3 | 351.5 | 420.2 | 375 |
| 4 | 420.2 | 488.1 | 500 |
| 5 | 488.1 | 589.1 | 5 |

-> resolved (ordinal, 6 of 6 segments): crop='Chilli', pest='Fruit Borer, Thrips, Whitefly and  Mites', dose_ai='45 +90', dose_form='375', **dilution='500'**, **phi='5'**

**Row 17** — this row's own real-rule segments (x0, x1, text):

| # | x0 | x1 | text |
|---|---|---|---|
| 0 | 36.2 | 100.8 | Brinjal |
| 1 | 100.8 | 270.4 | Shoot and Fruit borer, Whitefly and  Mites |
| 2 | 270.4 | 351.5 | 45 +90 |
| 3 | 351.5 | 420.2 | 375 |
| 4 | 420.2 | 488.1 | 500 |
| 5 | 488.1 | 589.1 | 5 |

-> resolved (ordinal, 6 of 6 segments): crop='Brinjal', pest='Shoot and Fruit borer, Whitefly and  Mites', dose_ai='45 +90', dose_form='375', **dilution='500'**, **phi='5'**

Every one of the 8 rows has exactly 6 real-rule segments, in the same left-to-right order as the 6 logical fields — no x-coordinate comparison needed at all, since the segment order IS the field order. **`500`/`600` etc. land in `dilution_water`; the correct PHI value lands in `waiting_period_phi`, cleanly separated, on every row.** Confirmed against the raw text layer independently (row 6: "...Tomato... 200 - 250 500 5" — dose_form=200-250, dilution=500, phi=5 — matches). Proceeding to the full corpus.

## 2. Full-corpus re-run: concatenation, old vs new

| assignment kind | rows | can it concatenate two values? |
|---|---|---|
| `ordinal_6` | 2086 | no — exactly 6 real segments, 1:1 to the 6 bands |
| `fallback_subset` | 1222 | no — <6 segments, injective best-fit assignment (each band gets at most one segment) |
| `residual_over6` | 3 | yes — >6 real segments, no defined ordinal target, falls back to nearest-center |
| `blank` | 1 | no — no content on the row |

**3312 total rows across all in-scope crop-advisory tables.** Only `residual_over6` can still concatenate two values into one band — **3 rows**, each contributing exactly 1 merged band (verified below), for **3 total merge events**, down from Step 1's **180** flagged-concerning events under the static grid.

### 2.1 Residual list — the rows still merging

| file | page | row | content segments | merged band |
|---|---|---|---|---|
| `insecticides_20260331.pdf` | 27 | 15 | 7 | 1 band(s) |
| `insecticides_20260331.pdf` | 27 | 16 | 7 | 1 band(s) |
| `insecticides_20260331.pdf` | 27 | 17 | 7 | 1 band(s) |

**`insecticides_20260331.pdf` p27 row 15** (7 real segments, one too many for the 6-field ordinal method): ['Crop', 'Common  name of the  pest Cond.', 'Weight of volume', 'Exposure  period', 'Conc. In air  (ppm)', 'Aeration /  Waiting']

**`insecticides_20260331.pdf` p27 row 16** (7 real segments, one too many for the 6-field ordinal method): ['Stored whole  cereals  Millets Pulses', 'Rice weevil,  Lesser grain  Borer,  Khapra  Beetle, Rust  red flour  beetle, Pulse  beetle, Dried  fruit Beetle Air tight  cover', '300 –400          gm/m3  (230–307 ml)', '48–72 Hr.  for cover  fumigation', '10 ppm', 'Partial  aeration For  at least 1hr.  followed  by24 hr.  complete  Aeration  waiting  period of 24  hr.']

**`insecticides_20260331.pdf` p27 row 17** (7 real segments, one too many for the 6-field ordinal method): ['Go down  fumigation', 'Rice weevil,  Lesser grain  Borer, Khapra Airtight  cover', '150 gm/m3', '07days', '10 ppm', 'Partial aeration  For  at least 1  hr. followed by']

All 3 are on `insecticides_20260331.pdf` p27 — the Aluminum Phosphide FUMIGATION sub-table, whose header ("Sr. No / Name of Commodity / Common name of the pest Cond. / Weight of volume / Exposure period / Conc. in air (ppm) / Aeration Waiting") has **7 real logical fields**, not 6 — this is a genuinely different product-type schema (also seen structurally on insecticides p4's fumigation sub-table in Step 1), not a band-assignment failure. These 3 rows are the right shape for `cols_unresolved` quarantine at Step 2: the row-local method correctly recognises it doesn't have a confident 6-field mapping for them, rather than guessing.

## 3. `source_column_merged` — corrected finding

Requirement 4 named this after Step 1's own §5, which reported that insecticides p89 has camelot drawing crop and pest as one raw column with no recoverable rule. Building the geometric test for this reason code required checking that claim directly against `Cell.right`, and it does not hold up:

```text
insecticides p89, row 0, actual cell borders:
col0 x=(36.2,100.8)  right=True   text='Paddy'
col1 x=(100.8,107.3) right=False  text='Yellow Stem Borer (Scirpophaga'
...
```
A real rule exists at x=100.8, cleanly separating "Paddy" from "Yellow Stem Borer...". **Step 1's finding was itself an artifact of the flawed method it was diagnosing** — nearest-STATIC-band assignment on raw columns put a narrow 6.5pt sliver ("Yellow Stem Borer..."'s own raw grid column) into the crop band purely because its midpoint fell on the wrong side of that method's boundary, not because the source PDF failed to draw a rule.

Two candidate geometric tests were built and rejected before settling on the one used:

| version | rows flagged | why rejected |
|---|---|---|
| segment extends past calibrated crop/pest boundary | 860 | misfired on every chemical-name header row and the two-tier column-label sub-header row |
| + no real rule within 15pt of that boundary | 186 | still misfired on ordinary rows whose crop text is legitimately a little wider than the file median (e.g. "Rose(Ornamental)") |
| + segment must ALSO extend past the pest/dose-ai boundary, tested against segs[0] not content[0] | **0** | zero false positives found; see below |

The middle version's own 7 candidates were checked by hand: every one turned out to be a row whose CROP cell is genuinely blank (forward-filled — the crop stated once, several pest rows listed under it), so `content[0]` (first non-blank segment) was already the pest name, which can be long enough to look like a wide merge on its own. The final version tests the row's true position-0 segment (blank or not), which tells the two cases apart.

**Corrected count: 0 genuine `source_column_merged` rows found across all four files.** insecticides p89's crop-advisory rows (the specific page named in the requirement) all resolve via ordinal assignment, confirmed row by row:

| row | crop | pest_or_disease |
|---|---|---|
| 0 | Paddy | Yellow Stem Borer (Scirpophaga  incertulas), Leaf Folder  (C |
| 2 | Cotton | Leaf hoppers, Aphids, Thrips, Pink  bollworm |
| 3 | Transplanted  Paddy | Brown plant hopper (Nilaparvata lugens)  Green leaf folder ( |
| 5 | Cauliflower | Diamond black moth (Plutella xylostella)  Tobacco caterpilla |
| 6 | Brinjal | Shoot & Fruit borer (Leucinodes  orbonalis), Jassids (Amrasc |
| 8 | Chilli | Aphids, Black Thrips, Whitefly and  Jassids |
| 10 | Cotton | Aphids, Jassids, Thrips and  Whiteflies |
| 12 | Paddy | Brown Plant Hopper (Nilaparvata  lugens), White Backed Plant |
| 14 | Paddy | Brown Plant Hopper (Nilaparvata  lugens), White Back Plant H |

No occurrence of a corrected `cols_unresolved`-worthy crop/pest merge exists in this corpus, under either the loose or strict reading. This is a correction to Step 1's report, not a new finding to act on.

## 4. The 10 structurally-variant tables — corrected, and ABSENT vs PRESENT-EMPTY

4 of Step 1's 10 are corrected by row-local assignment — they were never structural variants, just static-grid misassignments:

| file | page | Step 1 verdict | row-local verdict |
|---|---|---|---|
| `insecticides_20260331.pdf` | 9 | bands_used=[1,2,3,4,5], crop missing | **fully resolved** — crop was a slightly wide raw column ("Coconut/Bamboo" etc.), not absent |
| `insecticides_20260331.pdf` | 56 | bands_used=[0,1,2,3,5], dilution missing | **fully resolved** — dilution recovered via ordinal assignment on every row |
| `insecticides_20260331.pdf` | 60 | bands_used=[0,1,2,3,5], dilution missing | **fully resolved** — same correction as p56 |
| `bio_fungicides_20260331.pdf` | 12 | bands_used=[0,1,2,3,4], PHI missing | **fully resolved** — PHI recovered via ordinal assignment |

The remaining 6 are genuine — confirmed still missing the same band(s) under row-local assignment, and now checked at the ruling level (not just the content level) to answer the ABSENT-vs-PRESENT-AND-EMPTY question:

| file | page | missing band(s) | verdict |
|---|---|---|---|
| `insecticides_20260331.pdf` | 7 | dose_formulation, waiting_period_phi | **ABSENT (both)** |
| `insecticides_20260331.pdf` | 52 | waiting_period_phi | **PRESENT AND EMPTY** |
| `fungicides_20260331.pdf` | 31 | dilution_water, waiting_period_phi | **PRESENT AND EMPTY (both)** |
| `bio_insecticides_20260331.pdf` | 10 | dose_ai, waiting_period_phi | **ABSENT (both)** |
| `bio_fungicides_20260331.pdf` | 11 | waiting_period_phi | **PRESENT AND EMPTY** |
| `bio_fungicides_20260331.pdf` | 16 | waiting_period_phi | **PRESENT AND EMPTY** |

**`insecticides_20260331.pdf` p7** — ABSENT (both). The table's own printed header reads `Use | Method of application | | Dosage (a.i.) | | Dilution` — only 4 real field labels. Two raw-grid edges happen to sit within 25pt of the calibrated dose_formulation/PHI positions, but they are the SAME edges that separate "Dosage" from "Dilution" in this table's real 4-field schema, not dedicated ruled cells for the two extra fields. Wood/termite treatment has no separate formulation figure and no food-crop PHI concept.

**`insecticides_20260331.pdf` p52** — PRESENT AND EMPTY. 10 raw columns, one of them at x=(506.5, 590.3) sits right where PHI should start — a dedicated ruled cell exists. It is simply never filled: every row here is "used as seed dresser", and the label prints no waiting-period value at all for that use — not even a placeholder like "NA".

**`fungicides_20260331.pdf` p31** — PRESENT AND EMPTY (both). This table's raw column grid is an EXACT match to the file's calibrated 6-column structure (edges at 409.2 and 499.7, to one decimal place) — it is structurally a normal 6-column table. The 3 rows on this page are bacterial-disease seed-treatment protocols described entirely in prose within the earlier cells; the dilution and PHI cells are ruled but simply blank.

**`bio_insecticides_20260331.pdf` p10** — ABSENT (both). Only 3 raw columns exist in the whole table: crop, pest, and one huge column (x=272 to 586) holding the entire method description as unstructured prose. There is no ruled subdivision anywhere in that span for a.i. dose, formulation, dilution or PHI — they are not empty cells, there are no cells.

**`bio_fungicides_20260331.pdf` p11** — PRESENT AND EMPTY. 7 raw columns; dose_ai IS present as an explicit `-` placeholder on every row (not absorbed into prose), and a ruled column exists at x=(513.1, 594.1) — right where PHI should be. Seed/soil-treatment bio-fungicide rows simply never populate it.

**`bio_fungicides_20260331.pdf` p16** — PRESENT AND EMPTY. Same pattern as p11: dose_ai present as `-`, a ruled column exists at x=(523.4, 594.1), never populated.

Downstream meaning, as requested: **ABSENT** (p7, bio_insecticides p10) means the source table structurally has no such field for this product category — a Step 4 schema question (does `ChemicalOption` need an optional field, or does this product category map to a different record shape), not a parsing gap. **PRESENT AND EMPTY** (p52, fungicides p31, bio_fungicides p11/p16) means a cell genuinely exists and was correctly read as blank — this is a real value (the label prints nothing), and `parse_phi("")` already returns `None` for it correctly (the `_NULLISH` set includes `""`), no different handling needed at Step 2 beyond extracting the blank as blank.

## 5. Not done here

No CSVs written, no quarantine.csv, no Step 2 extraction. This report only validates the row-local method and corrects two Step 1 findings (p89's merge; p9/p56/p60/bio_fungicides-p12's "structural" status). Step 2 design questions this raises but does not answer: how `residual_over6` rows (p27's 3) and the 6 genuine structural-variant tables should be represented in the raw CSV schema, given `cols_unresolved` quarantine no longer applies to 180 rows — only 3.

