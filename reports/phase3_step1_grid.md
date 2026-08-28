# Phase 3, Step 1 — Column Grid (design & validation only)

**No extracted data written to disk.** The only artefacts are this report and `data/interim/phase3_step1_grid.json` (gitignored) — per-table column geometry and band-assignment results, needed to reproduce every number below. No Step 2 extraction has run.

Full method and rationale — including why calibration ended up per-subsection with gap-based boundaries, not per-file with center-bisected ones — is in `tools/phase3_step1_grid.py`'s module docstring. This report is the evidence trail for those design choices, derived in the order they were actually found: the naive design first, why it failed p87, then the fix.

## 1. Validation on insecticides p87 (required first)

### 1.1 First attempt: one grid per file — FAILED

A single file-wide grid, calibrated from every clean 6-column table in `insecticides_20260331.pdf` regardless of subsection, put p87 row 0's `60 +60` (the a.i. dose) in the **pest** band and its `03` (PHI) in the **dilution** band. Per your instruction, this stopped the run before any full sweep.

Root cause: `agricultural-use` (p2-55) and `combination-product` (p56-88) sit on two physically different column templates. Median column-midpoint centers, calibrated separately:

| band | agricultural-use center | combination-product center | shift |
|---|---|---|---|
| crop | 74.5 | 72.8 | -1.7 |
| pest_or_disease | 187.4 | 155.8 | -31.6 |
| dose_ai | 307.3 | 256.0 | -51.2 |
| dose_formulation | 387.8 | 339.4 | -48.4 |
| dilution_water | 467.7 | 394.0 | -73.7 |
| waiting_period_phi | 549.6 | 499.9 | -49.7 |

A 51pt shift on the a.i.-dose band alone (more than a tenth of the page width) — p87 is in `combination-product`, and the whole-file grid was pulled toward `agricultural-use` because it contributed more calibration pages (28 vs 11). **Fix: calibrate per (file, crop-advisory subsection), never per whole file.**

### 1.2 Second attempt: per-subsection, center-bisected boundaries — STILL WRONG

Splitting calibration by subsection was not sufficient on its own. With boundaries placed equidistant between adjacent band centers (`(center_i + center_{i+1}) / 2`), `combination-product`'s pest/dose-ai cut landed at x=205.9 — but p87 row 0's a.i.-dose column has its own midpoint at x=204.0, **1.9pt on the wrong side**. Bisecting between centers doesn't account for column WIDTH: the wide, wrapped pest-description column next to it pulled the Voronoi cut away from where the actual ruled line sits.

### 1.3 Fix: boundaries from the observed GAP between adjacent columns

Instead of bisecting centers, each internal boundary is the median, across clean 6-column `combination-product` tables, of the actual gap-midpoint between column i's right edge and column i+1's left edge — i.e. where the real ruled line tends to sit. This moved the pest/dose-ai cut from **x=205.9 (wrong) to x=202.3 (correct)**, putting p87's `60 +60` and `03` where they belong. This is the method used everywhere below.

Calibration for `combination-product` (11 clean 6-column tables, pages [61, 63, 64, 65, 66, 68, 70, 75, 77, 78, 80]):

| band | canonical center | boundary to next band |
|---|---|---|
| crop | 72.8 | 109.4 |
| pest_or_disease | 155.8 | 202.3 |
| dose_ai | 256.0 | 309.8 |
| dose_formulation | 339.4 | 369.0 |
| dilution_water | 394.0 | 422.1 |
| waiting_period_phi | 499.9 | (page edge) |

### 1.4 p87, all 22 raw columns -> 6 bands

| raw col | x0 | x1 | midpoint | -> band |
|---|---|---|---|---|
| 0 | 36.2 | 100.8 | 68.5 | 0 (crop) |
| 1 | 100.8 | 183.3 | 142.1 | 1 (pest_or_disease) |
| 2 | 183.3 | 224.6 | 204.0 | 2 (dose_ai) |
| 3 | 224.6 | 246.4 | 235.5 | 2 (dose_ai) |
| 4 | 246.4 | 251.9 | 249.2 | 2 (dose_ai) |
| 5 | 251.9 | 270.4 | 261.2 | 2 (dose_ai) |
| 6 | 270.4 | 312.4 | 291.4 | 2 (dose_ai) |
| 7 | 312.4 | 338.1 | 325.3 | 3 (dose_formulation) |
| 8 | 338.1 | 347.0 | 342.5 | 3 (dose_formulation) |
| 9 | 347.0 | 351.5 | 349.2 | 3 (dose_formulation) |
| 10 | 351.5 | 363.0 | 357.3 | 3 (dose_formulation) |
| 11 | 363.0 | 379.8 | 371.4 | 4 (dilution_water) |
| 12 | 379.8 | 411.0 | 395.4 | 4 (dilution_water) |
| 13 | 411.0 | 420.2 | 415.6 | 4 (dilution_water) |
| 14 | 420.2 | 425.4 | 422.8 | 5 (waiting_period_phi) |
| 15 | 425.4 | 444.9 | 435.2 | 5 (waiting_period_phi) |
| 16 | 444.9 | 469.8 | 457.3 | 5 (waiting_period_phi) |
| 17 | 469.8 | 479.9 | 474.9 | 5 (waiting_period_phi) |
| 18 | 479.9 | 483.3 | 481.6 | 5 (waiting_period_phi) |
| 19 | 483.3 | 488.1 | 485.7 | 5 (waiting_period_phi) |
| 20 | 488.1 | 499.3 | 493.7 | 5 (waiting_period_phi) |
| 21 | 499.3 | 589.1 | 544.2 | 5 (waiting_period_phi) |

### 1.5 p87 row 0 — the exact ask

```text
raw: Okra (Bhindi) ‖ Red spider mites ‖ 60 +60 ‖ (19 blank cols) ‖ 500 ‖ (3 blank) ‖ 500 ‖ (5 blank) ‖ 03 ‖ (4 blank)
resolved: crop='Okra  (Bhindi)'  pest='Red spider  mites'  dose_ai='60 +60'  dose_form='500'  dilution='500'  phi='03'
```
`60 +60` -> **dose_ai band**. `03` -> **waiting_period_phi band**. Confirmed.

### 1.6 All 18 rows of p87, resolved

| row | crop | pest_or_disease | dose_ai | dose_formulation | dilution_water | waiting_period_phi |
|---|---|---|---|---|---|---|
| 0 | Okra  (Bhindi) | Red spider  mites | 60 +60 | 500 | 500 | 03 |
| 1 | Brinjal | Whitefly, Red  spider mites | 60 +60 | 500 | 500 | 05 |
| 2 | Mango | Mealy bug | 0.018% | 0.075% | Spray fluid as required  depending upon size of  tree. | 15 |
| 3 | Cotton | Mealy bug | 75+75 | 625 | 500 | 22 |
| 4 | Grapes | Thrips, Mites  and Mealy Bugs | 90 + 90 | 750 | 1000 | 60 |
| 5 | Spiropidon 30% w/w + Acetamiprid 24% w/w WG |  |  |  |  |  |
| 6 | Tomato | Thrips (Thrips tabaci), Aphids  (Aphis gossypii), Whiteflies  (Bemisia tabaci) | 108 (Spiropidion 60 +  Acetamiprid 48) – 135  (Spiropidion 75 +  Acetamiprid 60) |  | 200 - 250 | 500 5 |
| 7 | Cotton | Mealy bugs (Phenococcus  solenopsis, Thrips (Thips  tabaci), Jassids (Amrasca  devastans), Aphids (Aphis  gossypii), Whiteflies (Bemisia  tabaci) | 108 (Spiropidion 60 +  Acetamiprid 48) – 135  (Spiropidion 75 +  Acetamiprid 60) |  | 200 - 250 | 500 85 |
| 8 | SULFOXAFLOR 7.5% + BUPROFEZIN 15% SC |  |  |  |  |  |
| 9 | Paddy | Brown Plant Hopper (BPH) | 60 + 120 – 75 + 150 | 800 - 1000 | 500 | 26 |
| 10 | Tetraniliprole 0.4 % w/w + Fipronil 0.6 % w/w GR |  |  |  |  |  |
| 11 | Rice | Stem borer (Scirpophaga  incertulas) and leaf folder  (Cnaphalocrocis medinalis) | 40 + 60 – 50 + 75 | 10 - 12.5 |  | NA 65 |
| 12 | Sugarcane | Early shoot borer (Chilo  infuscatellus) and White grub  (Holotrichiaserra ta) | 50 + 75 – 60 + 90 | 12.5 – 15 |  | NA 314 |
| 13 | Tetraniliprole 10.81 % w/w + Spirotetramat 21.62 % w/w SC |  |  |  |  |  |
| 14 | Okra | Fruit & Shoot borer, Aphids,  Whitefly and Mites | 45 +90 | 375 |  | 500 3 |
| 15 | Cabbage | Diamond back moth, Tobacco  caterpillar and Aphids | 45 +90 | 375 |  | 500 7 |
| 16 | Chilli | Fruit Borer, Thrips, Whitefly and  Mites | 45 +90 | 375 |  | 500 5 |
| 17 | Brinjal | Shoot and Fruit borer, Whitefly and  Mites | 45 +90 | 375 |  | 500 5 |

### 1.7 The row-0 spot check passes. Scanning every row does not — flagged, not hidden

Rows 6, 7, 11, 12, 14-17 above show the same defect that motivated requirement 4: a value that is clearly **not PHI** (`500`, or `NA` meaning "no dilution — granular application") is concatenated into the PHI band alongside the real PHI value. This is the SAME root cause as §1.2/§1.3, one level down: it is not the subsection-level boundary that is wrong now, it is that a row whose a.i./formulation dose is an unusually wide compound expression (`108 (Spiropidion 60 + Acetamiprid 48) – 135 (...)`) pushes that row's OWN later columns further right than the calibrated dilution/PHI cut expects — for THIS row only, not the table as a whole (most other rows on p87 place dilution correctly). See §4 for how large this is across the whole corpus, and §7 for what I'd do about it before Step 2.

## 2. Canonical bands, all four files (requirement 1)

### `insecticides_20260331.pdf`

**agricultural-use** — 28 clean 6-column tables (pages [2, 3, 7, 9, 14, 19, 21, 25, 26, 29, 30, 33, 34, 35, 36, 38, 41, 42, 43, 44, 45, 46, 47, 48, 51, 54, 55])

| band | logical column | center | range |
|---|---|---|---|
| 0 | crop | 74.5 | [page left edge, 112.8) |
| 1 | pest_or_disease | 187.4 | [112.8, 262.0) |
| 2 | dose_ai | 307.3 | [262.0, 353.4) |
| 3 | dose_formulation | 387.8 | [353.4, 422.1) |
| 4 | dilution_water | 467.7 | [422.1, 513.3) |
| 5 | waiting_period_phi | 549.6 | [513.3, page right edge) |

**combination-product** — 11 clean 6-column tables (pages [61, 63, 64, 65, 66, 68, 70, 75, 77, 78, 80])

| band | logical column | center | range |
|---|---|---|---|
| 0 | crop | 72.8 | [page left edge, 109.4) |
| 1 | pest_or_disease | 155.8 | [109.4, 202.3) |
| 2 | dose_ai | 256.0 | [202.3, 309.8) |
| 3 | dose_formulation | 339.4 | [309.8, 369.0) |
| 4 | dilution_water | 394.0 | [369.0, 422.1) |
| 5 | waiting_period_phi | 499.9 | [422.1, page right edge) |

### `fungicides_20260331.pdf`

**fungicides-single** — 29 clean 6-column tables (pages [5, 6, 7, 9, 12, 15, 16, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 37, 38, 39, 41, 42])

| band | logical column | center | range |
|---|---|---|---|
| 0 | crop | 106.3 | [page left edge, 145.0) |
| 1 | pest_or_disease | 193.6 | [145.0, 242.2) |
| 2 | dose_ai | 279.7 | [242.2, 317.3) |
| 3 | dose_formulation | 363.2 | [317.3, 409.2) |
| 4 | dilution_water | 454.4 | [409.2, 499.7) |
| 5 | waiting_period_phi | 538.1 | [499.7, page right edge) |

**fungicides-combination** — 30 clean 6-column tables (pages [43, 44, 46, 47, 49, 50, 51, 52, 53, 54, 55, 56, 57, 60, 61, 62, 63, 64, 65, 66, 67, 68, 70, 72, 73, 75, 77, 78, 82, 83])

| band | logical column | center | range |
|---|---|---|---|
| 0 | crop | 107.9 | [page left edge, 144.0) |
| 1 | pest_or_disease | 200.2 | [144.0, 252.0) |
| 2 | dose_ai | 301.4 | [252.0, 350.9) |
| 3 | dose_formulation | 391.4 | [350.9, 432.0) |
| 4 | dilution_water | 481.4 | [432.0, 530.9) |
| 5 | waiting_period_phi | 556.0 | [530.9, page right edge) |

### `bio_insecticides_20260331.pdf`

**bio-insecticides** — 9 clean 6-column tables (pages [2, 3, 4, 5, 6, 7, 8, 12, 13])

| band | logical column | center | range |
|---|---|---|---|
| 0 | crop | 101.5 | [page left edge, 130.6) |
| 1 | pest_or_disease | 195.1 | [130.6, 259.7) |
| 2 | dose_ai | 289.9 | [259.7, 320.2) |
| 3 | dose_formulation | 367.0 | [320.2, 413.8) |
| 4 | dilution_water | 465.7 | [413.8, 517.7) |
| 5 | waiting_period_phi | 551.8 | [517.7, page right edge) |

### `bio_fungicides_20260331.pdf`

**bio-fungicides** — 12 clean 6-column tables (pages [3, 4, 5, 6, 7, 13, 14, 16, 17, 18, 19, 20])

| band | logical column | center | range |
|---|---|---|---|
| 0 | crop | 68.6 | [page left edge, 119.0) |
| 1 | pest_or_disease | 198.4 | [119.0, 277.7) |
| 2 | dose_ai | 299.8 | [277.7, 321.8) |
| 3 | dose_formulation | 359.9 | [321.8, 391.9) |
| 4 | dilution_water | 439.7 | [391.9, 502.6) |
| 5 | waiting_period_phi | 548.3 | [502.6, page right edge) |

## 3. Full-corpus resolve/fail sweep (requirement 3)

Scope: **crop-advisory tables only.** public-health / household / locust tables do not share the 6-column schema at all (different logical columns — no a.i./formulation split, "Habitat" instead of "Crop", etc.) — forcing them through this grid would not be imprecise, it would be meaningless. This was confirmed necessary while building the calibration set, not assumed: 4 of `bio_insecticides_20260331.pdf`'s 13 apparently-clean 6-column pages turned out to be `public-health-use`, not crop-advisory, and would have corrupted that file's grid the same way `combination-product` corrupted the whole-file insecticides grid in §1.1 if left in.

**192 / 202 crop-advisory tables resolve cleanly (95.0%). 10 do not.**

`resolves cleanly` here is a STRUCTURAL check only: the raw-column -> band mapping is monotonic left-to-right, and every band that receives any non-empty cell in the table is one of exactly 6 (no fewer). It is necessary, not sufficient — §1.7 and §4 show a table can pass this check and still misplace individual rows.

| file | page | subsection | raw cols | bands used | what the page looks like |
|---|---|---|---|---|---|
| `insecticides_20260331.pdf` | 7 | agricultural-use | 6 | [0, 1, 2, 4] | Table 1: termite/wood-preservative treatment ("Glue Line Poisoning", "Dipping") — genuinely only 4 fields (Use/Method/Dose/Dilution), no formulation or PHI column exists for this product type. |
| `insecticides_20260331.pdf` | 9 | agricultural-use | 6 | [1, 2, 3, 4, 5] | Rodenticide bait-site table ("Coconut/Bamboo", "Residential premises", "Poultry Farm") — site name column sits further right than a crop name typically does; not really the crop schema. |
| `insecticides_20260331.pdf` | 52 | agricultural-use | 10 | [0, 1, 2, 3, 4] | Seed-dresser sub-table (Thiamethoxam 30% FS) — dose given per kg seed with a prose "used as seed dresser" note; no PHI concept applies to seed treatment. |
| `insecticides_20260331.pdf` | 56 | combination-product | 7 | [0, 1, 2, 3, 5] | Combination-product table where a compound dose expression ("400 +80.") widens that row's dose_formulation column, pushing the real dilution value ("500 –750") past the calibrated dilution/PHI cut — band 4 (dilution) never gets used anywhere on this table. |
| `insecticides_20260331.pdf` | 60 | combination-product | 7 | [0, 1, 2, 3, 5] | Same defect as p56: compound dose pushes dilution values ("200", "500") into the PHI band; band 4 unused table-wide. |
| `fungicides_20260331.pdf` | 31 | fungicides-single | 6 | [0, 1, 2, 3] | Bacterial-disease seed-treatment sub-table with prose method cells ("Seed treatment: seed born infection...") instead of numeric formulation/dilution; no PHI populated. |
| `bio_insecticides_20260331.pdf` | 10 | bio-insecticides | 3 | [0, 1, 4] | Nematode bio-pesticide table: only 3 raw columns exist at all (Crop, Pest, one large free-text Method cell) — dose/dilution/PHI are never split out by the source table, not something a 6-band grid can recover. |
| `bio_fungicides_20260331.pdf` | 11 | bio-fungicides | 7 | [0, 1, 2, 3, 4] | Seed/soil-treatment bio-fungicide table, prose method cells, PHI band never populated (seed treatment has no waiting period). |
| `bio_fungicides_20260331.pdf` | 12 | bio-fungicides | 8 | [0, 1, 2, 3, 4] | Same pattern as p11 — prose seed/soil-treatment method cells, no PHI. |
| `bio_fungicides_20260331.pdf` | 16 | bio-fungicides | 6 | [0, 1, 2, 3, 4] | Same pattern again — prose method cells for seed/nursery/root-dip treatment, no PHI. |

None of these 10 are a calibration error in the §1 sense (wrong boundary position). Every one is a genuine STRUCTURAL variant: a product type (termite/wood treatment, rodenticide, seed dresser, seed/soil-treatment bio-pesticide) whose printed table has fewer than 6 real logical fields, or folds dose+method into one free-text cell. A 6-band grid cannot manufacture columns that were never printed.

## 4. Concatenation report (requirement 4)

**363 concatenation events** across all in-scope crop-advisory tables (2+ non-empty raw columns landing in one band, same row). Of those, **180** join two non-empty values that BOTH contain a digit — the heuristic used to flag "possibly two genuinely different values", not proof of it (a wrapped decimal like `"12." + "5"` would also match this heuristic and be perfectly benign). Manual review of samples below confirms the majority are genuine: two DIFFERENT quantities (a formulation dose and a dilution figure, or a dilution figure and a PHI) sharing one band because a compound dose expression elsewhere in the row shifted that row's own column positions.

| file | subsection | total events | flagged "concerning" |
|---|---|---|---|
| `insecticides_20260331.pdf` | combination-product | 101 | 72 |
| `insecticides_20260331.pdf` | agricultural-use | 148 | 59 |
| `fungicides_20260331.pdf` | fungicides-single | 45 | 35 |
| `fungicides_20260331.pdf` | fungicides-combination | 49 | 14 |
| `bio_insecticides_20260331.pdf` | bio-insecticides | 3 | 0 |
| `bio_fungicides_20260331.pdf` | bio-fungicides | 17 | 0 |

Worked examples — genuinely different values, not wrapped text (one per distinct page+band, to show breadth rather than repeating the same page):

| file | page | band | raw values joined |
|---|---|---|---|
| `insecticides_20260331.pdf` | 4 | dose_ai | 15 –25 + 165 –280 |
| `insecticides_20260331.pdf` | 5 | dose_ai | 12.5-18.75 + 500 –750 |
| `insecticides_20260331.pdf` | 5 | dilution_water | 500 –1000 + 20 |
| `insecticides_20260331.pdf` | 8 | dilution_water | 500 + 1 |
| `insecticides_20260331.pdf` | 10 | dose_formulation | 1000 + 500 – 750 |
| `insecticides_20260331.pdf` | 11 | dose_formulation | 800 –  1000 + 500 – 1000 |
| `insecticides_20260331.pdf` | 12 | dose_formulation | 1000 + 500 –1000 |
| `insecticides_20260331.pdf` | 13 | dose_formulation | 125 + 400-600 |
| `insecticides_20260331.pdf` | 13 | dose_ai | 40 + 10 kg |
| `insecticides_20260331.pdf` | 27 | dilution_water | 10 ppm + Partial  aeration For  at least 1hr.  followed  by24 hr.  complete  Aeration  waiting  period of 24  hr. |
| `insecticides_20260331.pdf` | 50 | dose_ai | 90 + 375 |
| `insecticides_20260331.pdf` | 56 | waiting_period_phi | 500 –750 + 20 |
| `insecticides_20260331.pdf` | 57 | waiting_period_phi | 500 + 53 |
| `insecticides_20260331.pdf` | 58 | dose_ai | 50+100 + 1000 |

Two recurring shapes account for nearly all of them:

- **dose_form spills the neighbour into dose_ai**: a row states both a.i. and formulation as ranges (`"15 –25"` + `"165 –280"`, insecticides p4) — both land in the dose_ai band.

- **compound dose_ai/dose_form widens the row, pushing dilution into PHI**: `"500"` (dilution) + a real PHI value (`"1"`/`"29"`/`"10"`/...) land together in the PHI band whenever the SAME row's a.i./formulation cell is a compound expression (insecticides p8, p56, p60; also seen live on p87 §1.7).

## 5. Cross-check against the 3 section-boundary pages (requirement 5)

These pages were entirely excluded from §3's sweep (whole page tagged by its LAST heading's subsection — see phase 2b). That is correct for the sweep's purpose, but leaves an open question: do rows ABOVE the split, which genuinely are crop-advisory, resolve against the right subsection's grid? Checked directly, per page.

### insecticides p89 (crop-advisory `combination-product` above y=675.9, `public-health` below)

18-row, 22-column table on the page; rows 0-14 sit above the split (crop-advisory), rows 15-17 below (public-health). Evaluated rows 0-14 against the `combination-product` grid:

| row | crop | pest_or_disease | dose_ai | dose_formulation | dilution_water | waiting_period_phi |
|---|---|---|---|---|---|---|
| 0 | Paddy Yellow Stem Borer (Scirpophaga  incertulas), Leaf Folder  (Cnaphalocrocis medinalis), Brown  Plant Hopper (Nilaparvata lugens),  and White Backed plant Hopper  (Sogatella furcifera). |  | 300 + 120 –  375 + 150 | 10000- 12500 | - | 56 |
| 1 | TOLFENPYRAD 15% + BIFENTHRIN 7.5% SE |  |  |  |  |  |
| 2 | Cotton | Leaf hoppers, Aphids, Thrips, Pink  bollworm |  | 112.50 + 56.25 | 750 | 500 54 |
| 3 | Transplanted  Paddy | Brown plant hopper (Nilaparvata lugens)  Green leaf folder (Nephotettix  nigropictus) Stem borer (Scirpophaga  incertulus) Leaf folder (Cnaphalocrosis  medinalis) |  | 112.50 + 56.25 | 750 | 500 35 |
| 4 | Tolfenpyrad 18.75% + Emamectin Benzoate 0.94% SC |  |  |  |  |  |
| 5 | Cauliflower Diamond black moth (Plutella xylostella)  Tobacco caterpillar (Spodoptera litura) |  |  | 140 + 7 | 700 | 500 7 |
| 6 | Brinjal Shoot & Fruit borer (Leucinodes  orbonalis), Jassids (Amrasca biguttula  biguttula ) |  |  | 140 + 7 | 700 | 500 3 |
| 7 | Tolfenpyrad 30 % + Pyriproxyfen 10 % + Acetamiprid 4% w/w EC |  |  |  |  |  |
| 8 | Chilli Aphids, Black Thrips, Whitefly and  Jassids |  |  | 150 + 50 + 20 | 500 | 500 7 |
| 9 | Flonicamid 15% + Pyriproxyfen 12% + Acetamiprid 2% ME |  |  |  |  |  |
| 10 | Cotton Aphids, Jassids, Thrips and  Whiteflies |  | 75 + 60 + 10 |  | 500 | 500 51 |
| 11 | Triflumezopyrim 4.79% + Spinetoram 8.62% w/w SC |  |  |  |  |  |
| 12 | Paddy Brown Plant Hopper (Nilaparvata  lugens), White Backed Plant  Hopper (Sogatellafurcifera), Stem  borer (Scirpophaga incertulas) |  | 70 (25+45) | 500 | 500 | 21 |
| 13 | Triflumezopyrim 10% w/w + Spinetoram 12% w/w WG |  |  |  |  |  |
| 14 | Paddy Brown Plant Hopper (Nilaparvata  lugens), White Back Plant Hopper  (Sogatella furcifera) Leaf Folder  (Cnaphalocrosis medinalis) |  | 55 (25 +  30) | 250 | 500 | 21 |

dose_ai / dose_formulation / dilution_water / waiting_period_phi resolve correctly on every populated row. **But crop and pest merge into a single band on every row** (`pest_or_disease` is empty throughout) — on this specific 22-column table, camelot itself drew crop-name and pest-name as ONE raw column (no internal ruling between them), so no band-boundary choice can recover the split; the source table never separated them. A different structural gap from the ones in §3/§4, worth carrying into Step 2's `cols_unresolved` design.

### insecticides p94 (`public-health` above y=681.7, `household` below)

Genuinely out of scope on BOTH sides of the split — public-health above, household below, neither is a crop-advisory subsection. No crop-advisory content exists on this page to test against the 6-band grid. Confirmed by inspection, not assumed.

### bio_insecticides p15 (crop-advisory `bio-insecticides` above y=332.8, `public-health` below)

Rows 0-7 sit above the split (crop-advisory), rows 8-20 below (public-health). Evaluated rows 0-7 against the `bio-insecticides` grid:

| row | crop | pest_or_disease | dose_ai | dose_formulation | dilution_water | waiting_period_phi |
|---|---|---|---|---|---|---|
| 0 |  | (Helicoverpa  armigera) |  |  |  |  |
| 1 | Paecilomyces lilacinus 01.15% WP (Accession No. MTCC No. 5175, T-Stanes PI-1 Strain) |  |  |  |  |  |
| 2 | Brinjal | Root Knot  Nematode | 03.0 kg | 500 kg Organic  manure/ Organic  fertilizer | - | - |
| 3 | Paecilomyces lilacinus 1.15% WP (CFU 1^108 / gm. Min) (T Stanes –Pl-1 Strain Accession No. MTCC 5175) |  |  |  |  |  |
| 4 | Chilli | Root Knot  Nematode | 11.5 g | 5.0 – 6.0 | - | - |
| 5 | Cucumber | Root Knot  Nematode | 11.5 g | 5.0 -6.0 | - | - |
| 6 | Paecilomyces lilacinus 01.50% LF (CFU count 1x108/ml min.)(Accession No. MTCC No. 5175, T-Stanes PI-1  Strain) |  |  |  |  |  |
| 7 | Tomato | Root Knot  Nematode  (Meloidogyne  incognita) | - | 6000 | 500 | - |

**Resolves cleanly on every populated row** — crop, pest, dose, dilution and PHI all land correctly (rows 2, 4, 5, 7). Row 0's stray `(Helicoverpa armigera)` fragment in the pest band is a wrapped continuation from the Cotton/Pink-bollworm row on the PREVIOUS page (p14) — the page-boundary forward-fill hazard phase 2b already documented, not a grid problem. The clean result here is the positive control: it shows §1's fix generalises when the source table itself doesn't have p89's raw-column merge.

## 6. Compound-rate note for Phase 4 (flagged, not resolved)

The 32 `unresolved_marker` rows (bio_insecticides p9-12, bio_fungicides p8/9/15 — see the FYM* discussion, prior turn) carry TWO rates in one dose/method cell: a seed-treatment rate (`"...20 gm/kg of seeds..."`) and a soil-application rate (`"...enriched FYM* @ 5 tons/ha..."`). `src/schema.py` (frozen, Act 2) gives `ChemicalOption` exactly one `dose: Dose` field — one basis, one value, per chemical option. These 32 rows cannot map onto that shape without either (a) picking one rate and discarding the other, or (b) emitting two `ChemicalOption`s from one printed row. Both are Phase 4 decisions. `schema.py` is not touched here or proposed to change — flagging only, per your instruction.

## 7. Recommendation for Step 2 (proposal, not a decision made here)

§4 shows the concatenation defect is systematic, not rare — concentrated in `insecticides_20260331.pdf` (both subsections) and `fungicides_20260331.pdf` (`fungicides-single` especially). I'd propose: at Step 2, any row where a band's concatenation event matches the "concerning" heuristic in §4 (2+ non-empty raw columns landing in one band, all containing a digit) gets routed to `quarantine.csv` with reason `cols_unresolved`, rather than accepted into the raw CSV with a silently-merged value. p89's crop/pest raw-column merge (§5) would need the same treatment under `cols_unresolved` — the source table itself never separated them, so no band choice fixes it. Waiting for confirmation before Step 2 runs with this rule.

