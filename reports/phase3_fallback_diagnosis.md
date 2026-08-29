# Phase 3 — Fallback and Unit Diagnosis

**Diagnosis only.** No raw CSVs modified, no re-extraction run, `schema.py` untouched. All numbers below are read from the existing `data/interim/*_raw.csv` (Step 2's output) and from `tools/phase3_step1b_rowgrid.py` / `tools/phase3_step2_extract.py`'s actual code — nothing here required regenerating anything.

Manual verification of the 25-row sample is confirmed 25/25 correct on attribution, including both cross-page inheritance cases. This report is about the one remaining defect class the sample surfaced (fallback_subset column placement) plus one separately-reported unit issue (Kitazin).

## 1. `assignment_kind=fallback_subset` counts

| assignment_kind | rows (all 4 files) |
|---|---|
| `ordinal_6` | 2136 |
| `chemical_header` | 921 |
| `fallback_subset` | 704 |
| `blank` | 1 |

**`fallback_subset` total: 704 of 3762 rows.**

| file | fallback_subset rows |
|---|---|
| `insecticides_20260331.pdf` | 429 |
| `fungicides_20260331.pdf` | 137 |
| `bio_insecticides_20260331.pdf` | 67 |
| `bio_fungicides_20260331.pdf` | 71 |
| **total** | **704** |

By segment count (all 4 files):

| segments | rows |
|---|---|
| 1 | 58 |
| 2 | 121 |
| 3 | 122 |
| 4 | 119 |
| 5 | 284 |

Requirement asked for 2/3/4/5 specifically — **1-segment rows exist too (58 of them)** and are worth flagging: these are rows where the single populated segment is NOT at position 0 (crop blank, one lone value elsewhere — e.g. a wrapped pest/dose fragment continuing from the row above). They go through the same `best_subset_assignment` path as every other fallback_subset row; they are not a distinct code path, just the k=1 case.

By file x segment count:

| file | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| `insecticides_20260331.pdf` | 28 | 110 | 54 | 84 | 153 |
| `fungicides_20260331.pdf` | 13 | 2 | 3 | 18 | 101 |
| `bio_insecticides_20260331.pdf` | 5 | 6 | 37 | 3 | 16 |
| `bio_fungicides_20260331.pdf` | 12 | 3 | 28 | 14 | 14 |

## 2. Column-assignment rule for `fallback_subset` — the code path

`tools/phase3_step2_extract.py`, the `fallback_subset` branch (line ~437):

```python
elif kind == "fallback_subset" and is_crop_advisory:
    assign = best_subset_assignment(
        resolved_or_content, grid_subs[subsection]["centers"]) \
        if subsection in grid_subs else None
    if assign is not None:
        for seg, b in zip(resolved_or_content, assign):
            resolved6[b] = seg["text"]
```
which calls `tools/phase3_step1b_rowgrid.py::best_subset_assignment`:

```python
def best_subset_assignment(segments, centers):
    n = len(centers)          # 6 — the calibrated band centers
    k = len(segments)          # < 6, the row's real segment count
    ...
    mids = [(s["x0"] + s["x1"]) / 2.0 for s in segments]
    for combo in itertools.combinations(range(n), k):
        cost = sum(abs(mids[i] - centers[combo[i]]) for i in range(k))
        if best_cost is None or cost < best_cost:
            best_cost, best_combo = cost, combo
    return list(best_combo)
```
**Answer: purely positional, over a shortened list.** For k segments, every strictly-increasing k-combination of the 6 band indices is tried; the combination minimising total `|segment midpoint - calibrated band center|` wins. Nothing about the SEGMENT'S OWN CONTENT — whether it's a number, a unit, a full sentence, a placeholder — enters this function at all. Column identity comes entirely from where the segment's x-midpoint sits relative to the file/subsection's calibrated geometry, carried forward unchanged from Step 1b (built and validated to fix ROW-SHIFT — a compound dose widening a row's columns — never to check what KIND of value a segment holds).

### 2.1 Grounded against the reported defect (bio_insecticides p10, Gerbera)

Table page 10, row 9 — 3 real segments (this table has only 3 raw columns at all; see Q4):

| segment | x0 | x1 | midpoint | text |
|---|---|---|---|---|
| 0 | 72.5 | 153.4 | 112.9 | Gerbera |
| 1 | 153.4 | 272.2 | 212.8 | Meloidogyne incognita |
| 2 | 272.2 | 585.8 | 429.0 | Apply the Nemastin @ 50 gm/sq.m at the time of planting |

Calibrated `bio-insecticides` centers: [101.5, 195.1, 289.9, 367.0, 465.7, 551.8]

| segment | assigned band | distance to that band's center |
|---|---|---|
| Gerbera | crop | 11.4 |
| Meloidogyne incognita | pest_or_disease | 17.6 |
| Apply the Nemastin @ 50 gm/sq.m at the t | dilution_water | 36.7 |

Segment 2 ("Apply the Nemastin @ 50 gm/sq.m at the time of planting") spans x=272.2 to 585.8 — this table's ENTIRE method column, all in one raw cell, because the source table itself only has 3 columns (crop, pest, one big method column; see Q4). Its midpoint (429.0) happens to sit closest to `dilution_water`'s calibrated center (465.7) among the 4 remaining bands once crop/pest are assigned — that is the entire reason it landed there. The algorithm has no way to know this segment is prose rather than a water volume; nothing checks.

## 3. Non-numeric, sentence-length values in dose_ai / dose_formulation / dilution_water

Heuristic (stated, not exact — there is no clean syntactic line between "a dose expression with words in it" and "a sentence"): >=4 words AND contains one of a curated list of instructional verbs/phrases (apply, mix, treat, spray, dip, drench, "used as", "seed dresser", "method of", "depending", etc.) unlikely to appear in a genuine dose figure. A looser version (any of `the/at/of/to/and` as the only signal) also matched legitimate ranges like `"0.02 g/plant & 160 to 200 g/ha"` — rejected as counting real doses as prose.

**122 fallback_subset rows** carry a prose-shaped value in at least one dose/dilution column, by this heuristic — the rejected looser version (weak connectors only) counts 133, which is why this number is reported as heuristic-dependent rather than exact.

| file | rows |
|---|---|
| `insecticides_20260331.pdf` | 27 |
| `fungicides_20260331.pdf` | 8 |
| `bio_insecticides_20260331.pdf` | 32 |
| `bio_fungicides_20260331.pdf` | 55 |
| **total** | **122** |

10 samples:

| file | page | crop | column | value |
|---|---|---|---|---|
| `insecticides_20260331.pdf` | 53 | Wheat | dilution_water | Use as seed  dresser at the  time of sowing |
| `bio_fungicides_20260331.pdf` | 5 | Grapes | dilution_water | Bacillus subtilis 1.50%  AS is applied as foliar  spray and soil spray @  2 |
| `bio_fungicides_20260331.pdf` | 15 | Okra | dilution_water | Treat the seed with Trichoderma viride 1.5% WP @ 20 gm/kg  of seeds and app |
| `bio_fungicides_20260331.pdf` | 14 | Chickpea | dilution_water | Seed  Treatment:  Make slurry  of required  quantity of  Trichoderm a virid |
| `bio_fungicides_20260331.pdf` | 11 | Wheat | dilution_water | Seed Treatment:  Mix required  quantity of seeds  with the required  quanti |
| `insecticides_20260331.pdf` | 52 | Soybean | dilution_water | This is used as  seed dresser |
| `fungicides_20260331.pdf` | 33 | Paddy (Rice) | dose_formulation | the vascular  bundles  insides the  seedlings.  Spray:  Spray  streptocycli |
| `insecticides_20260331.pdf` | 53 | Tomato | dilution_water | Use as seed  dresser at the  time of sowing |
| `bio_insecticides_20260331.pdf` | 12 | Tomato | dilution_water | Treat  the  seeds  with  Verticillium  chlamydosporium 1.0%  WP  @  20  gm/ |
| `bio_insecticides_20260331.pdf` | 11 | Okra | dilution_water | Treat the seed with Trichoderma harzianum 1.5% WP @  20  gm/kg  of  seeds   |

## 4. Rows under a free-text-method-shape header

Structural definition: a chemical block (grouped by `active_ingredient`) where EVERY data row has BOTH `dose_ai` and `dose_formulation` blank — the source table folds a.i., formulation, dilution and method into one free-text cell instead of the standard 6-column split.

| file | blocks | rows |
|---|---|---|
| `insecticides_20260331.pdf` | 0 | 0 |
| `fungicides_20260331.pdf` | 0 | 0 |
| `bio_insecticides_20260331.pdf` | 5 | 30 |
| `bio_fungicides_20260331.pdf` | 6 | 17 |
| **total** | **11** | **47** |

**`bio_insecticides_20260331.pdf`**

| chemical | rows | pages |
|---|---|---|
| Pseudomonas fluorescens 1.0% WP (Strain No. IIHR-PF-2, Accession No. I | 4 | [9, 10] |
| Trichoderma harzianum 1.0% WP (Strain No. IIHR-TH-2 Accessions No. ITC | 12 | [10, 11] |
| Trichoderma harzianum 1.5% WP (Strain No. IIHR-TV-5 Accessions No. ITC | 5 | [11] |
| Trichoderma viride 1.5% WP (Strain No. IIHR-TV-5 Accessions No. ITCC 6 | 5 | [11, 12] |
| Verticillium chlamydosporium 1.0% WP, (2x106 CFU/gm min) Strain – IIHR | 4 | [12] |

**`bio_fungicides_20260331.pdf`**

| chemical | rows | pages |
|---|---|---|
| Pseudomonas fluorescens 1.0% WP (Strain No. IIHR-PF-2 Accession No. IT | 4 | [8] |
| Pseudomonas fluorescens 1.5% AS CFU 1 x 10 8/mL min.; AMMFA-TH1 strain | 3 | [8, 9] |
| Trichoderma harzianum 1.0% WP (Strain No. IIHR-TH-2 Accessions No. ITC | 4 | [9] |
| Trichoderma harzianum 1.0% WP (Strain no. Th3 Accession no. 5593) | 1 | [9] |
| Trichoderma harzianum 1.5% AS (CFU 2 x 10 ⁶/mL min.; (AMMFA-TH1 strain | 1 | [9] |
| Trichoderma viride 1.5% WP (Strain No. IIHR-TV-5, Accession No. ITCC 6 | 4 | [15] |

**Excluded as a false positive**: `insecticides_20260331.pdf`, `Ethylene dichloride + Carbon tetrachloride (3:1)` (1 row, p28) — passes the blank-dose test on a technicality but is a wrapped CONTINUATION fragment of the Aluminum-Phosphide fumigation table (the same 7-field schema whose other rows are already quarantined `cols_unresolved` on p27 — Step 1b/Step 2), not a genuine free-text-method chemical block. Its own 2 segments (`Beetle, Rust  red flour  beetle, Pulse  ` and `24 hr. complete  Aeration  waiting perio`) simply don't happen to include a dose figure — checked by hand, not assumed.

### 4.1 Metarhizium anisopliae 10% GR (bio_insecticides p9) — related but DIFFERENT defect

Not counted above: this block fails the "every row blank" test because one row (Potato/White grub) has `dose_ai="60kg."` populated. Inspecting all 3 non-header rows under this chemical shows why — it is not cleanly free-text-shaped, it has its OWN two-tier column-label header ("Crop | Common name of the target organism | Dosage/ha/application | Formulation | Method of application") that was extracted as if it were data, because `chemical_header` detection only fires on a row with exactly ONE non-blank segment — this header has three:

```text
crop='Crop' | pest='Common name of the target organism' | dose_form='Dosage /ha/application'
crop='Crop' | dose_ai='Formulation' | dilution='Method of application'
crop='Potato' | pest='White grub' | dose_ai='60kg.' | dilution='Mix Metarhizium anisopliae (Grub-X 10% GR) with FYM...'
```
2 of its 3 rows are literal column-label text sitting in the `crop`/`pest_or_disease`/`dose_formulation`/`dilution_water` fields as if they were farm data (`crop='Crop'` is not a crop). The 3rd row is genuine data, itself carrying the same prose-in-`dilution_water` shape as Q3/Q4's other cases. This is a second, distinct failure mode from the clean free-text blocks above: a two-tier header this corpus's `chemical_header` check does not recognise, not a table that was always unstructured.

**Combined total (clean free-text blocks + Metarhizium): 47 + 3 = 50 rows.**

### 4.2 insecticides / fungicides — checked directly, not assumed

Zero genuine free-text-shape blocks in either file, by the structural test above. A phrase search for "method of application" / "target organism" anywhere in the extracted text (not just blank-dose blocks) finds:

| file | rows | context |
|---|---|---|
| `insecticides_20260331.pdf` | 0 | — |
| `fungicides_20260331.pdf` | 1 | p71, Rice/"Brown leaf spot, Sheath blight", `Penflufen 13.28% + Trifloxystrobin 13.28% FS` — **`assignment_kind=ordinal_6`**, a normal, correctly-resolved 6-column row whose `dilution_water` cell happens to BE a seed-treatment method paragraph that starts with the words "Method of application". Not a different table template — the same Q3 phenomenon (prose in a dose/dilution cell), landed via the normal path because this row genuinely has 6 real segments. |
| `bio_insecticides_20260331.pdf` | 2 | the Metarhizium header-echo rows above |

**Answer: the free-text-method-shape TABLE TEMPLATE (a distinct header wording, not just prose-in-a-cell) is confirmed only in the two bio files.** insecticides and fungicides both carry the Q3 prose-in-cell phenomenon on ordinary 6-column rows, but neither has a block whose header itself uses this alternate shape.

## 5. Percent-concentration / per-litre dose cells (separate issue)

Counting only — no parsing, no classification, per instruction. A row counts if `dose_ai`, `dose_formulation` or `dilution_water` contains a literal `%`, or matches a per-litre pattern (`per lit`, `/lit`, `ml/l`, or `<number> gram in <number> lit`, covering the exact Kitazin wording).

Crop-scope matching caveat: `scope.py`'s `"gram"` and `"tur"` overlap heavily in CIB&RC's own crop names — "Red Gram" / "Pigeon pea" / "Arhar" all mean tur; "Bengal Gram" means gram (chickpea); but "Black Gram" and "Green Gram" are DIFFERENT crops (urad, moong) that a bare substring match on "gram" would wrongly pull in. Excluded explicitly here. This is the same crop-string reconciliation `scope.py`'s own header comment already flags as unresolved against the CIB&RC register — surfaced again here because it directly affects this count, not fixed.

| file | rows with %/per-litre dose cell | of those, crop in scope.py's 8 |
|---|---|---|
| `insecticides_20260331.pdf` | 46 | 4 |
| `fungicides_20260331.pdf` | 138 | 44 |
| `bio_insecticides_20260331.pdf` | 26 | 5 |
| `bio_fungicides_20260331.pdf` | 66 | 19 |
| **total** | **276** | **72** |

### 5.1 The reported case, verified

`fungicides_20260331.pdf` p15, Pomegranate / Anthracnose, Kitazin 48% EC:

```text
dose_ai:           0.10%  or100  Gram in  100lit.  Of water
dose_formulation:  0.20%or  200mlin  200lt. of  water
assignment_kind:   ordinal_6
```
**This row's column assignment is CORRECT** — `ordinal_6`, a clean 6-segment row, dose_ai and dose_formulation are exactly where the schema says they should be. The defect here is different in kind from Q1-4: it is not a column-placement error, it is that the CONTENT of a correctly-placed cell mixes two incompatible units (a `%` concentration and a per-litre dilution instruction) under a header that claims a per-hectare a.i. figure. This is a Phase 4 dose-parsing problem, not a Phase 3 extraction defect — flagged here because it is live in-scope data (Pomegranate/Anthracnose is one of your 40 targets), not because Step 2 placed it wrong.

## Summary, for the remedy decision

- **Q1-3 (column misplacement)**: `fallback_subset` rows are assigned by pure x-coordinate distance to the file/subsection's calibrated band centers — no check on segment content. This is correct for its designed purpose (Step 1b: recovering a genuinely-missing field's position among fewer-than-6 real segments) but has no way to notice a segment is prose rather than a number. 122-133 rows (heuristic-dependent) carry a sentence-length value in a dose/dilution column as a result.
- **Q4 (table template)**: 11 chemical blocks / 47 rows are genuinely free-text-shaped (no numeric dose_ai/dose_formulation exists to misplace — the source table itself only has crop/pest/method columns), all in the two bio files. Metarhizium anisopliae 10% GR adds a distinct, second failure mode: a two-tier header not recognised as a header at all.
- **Q5 (unit ambiguity)**: a separate class entirely — correct column placement, ambiguous content. 276 rows corpuswide, 72 of them on one of your 8 scope crops. Not a Step 2 defect.

