# Phase A — dose-string surface survey

Source: the four in-scope raw CSVs in `data/interim/`, data rows only
(`assignment_kind` in ['fallback_subset', 'ordinal_6']; headers and blanks excluded).
Columns scanned: `dose_ai`, `dose_formulation`, `dilution_water`.

## 1. Totals

- **Distinct dose-bearing strings: 2113**
- Non-empty dose cells (occurrences): 7130

| column | non-empty cells | distinct strings |
|---|---|---|
| `dose_ai` | 2409 | 1082 |
| `dose_formulation` | 2387 | 832 |
| `dilution_water` | 2334 | 339 |

| file | non-empty dose cells | distinct strings |
|---|---|---|
| `insecticides` | 3702 | 1037 |
| `fungicides` | 2898 | 1020 |
| `bio_insecticides` | 342 | 94 |
| `bio_fungicides` | 188 | 98 |

## 2. Surface patterns

`branch` is the Phase B routing proposal, not a fact about the data.

| pattern | distinct | cells | branch | proposed Basis |
|---|---|---|---|---|
| `BARE_NUMBER` | 337 | 3364 | numeric | per_ha |
| `BARE_RANGE` | 456 | 1283 | numeric | per_ha |
| `NULL_MARKER` | 7 | 422 | free_text | free_text |
| `COMPOUND_SUM` | 269 | 387 | free_text | free_text |
| `NUM_UNIT` | 170 | 353 | numeric | per_ha |
| `RANGE_UNIT` | 78 | 242 | numeric | per_ha |
| `PER_KG_SEED` | 87 | 123 | numeric | per_kg_seed |
| `PCT_WITH_EQUIV` | 77 | 121 | numeric | concentration_pct |
| `PROSE_NO_NUMBER` | 67 | 108 | free_text | free_text |
| `PCT_SINGLE` | 34 | 87 | numeric | concentration_pct |
| `COMPOUND_RANGE` | 59 | 76 | free_text | free_text |
| `PER_HA_EXPLICIT` | 42 | 68 | numeric | per_ha |
| `PROSE_METHOD` | 47 | 52 | free_text | free_text |
| `PER_LITRE` | 42 | 48 | numeric | per_litre_water |
| `NUM_WITH_METHOD` | 43 | 47 | numeric | per_ha* |
| `PER_N_KG_SEED` | 38 | 47 | numeric | per_kg_seed |
| `COMPOUND_TOTAL_BREAKDOWN` | 25 | 40 | free_text | free_text |
| `PER_TREE` | 32 | 35 | numeric | per_tree |
| `PER_N_LITRE` | 29 | 33 | numeric | per_litre_water |
| `UNSUPPORTED_UNIT` | 27 | 30 | free_text | free_text |
| `PCT_EQUIV_FIRST` | 22 | 23 | numeric | concentration_pct |
| `MULTI_BASIS` | 16 | 20 | free_text | free_text |
| `PER_PLANT` | 17 | 19 | numeric | per_plant |
| `COMPOUND_NAMED` | 17 | 19 | free_text | free_text |
| `MULTI_RATE` | 9 | 11 | free_text | free_text |
| `DEFECT_AI_NAME` | 9 | 11 | defect | free_text |
| `ALTERNATIVE_VALUES` | 8 | 10 | free_text | free_text |
| `DEFECT_TIME_VALUE` | 8 | 9 | defect | free_text |
| `PCT_RANGE` | 8 | 8 | numeric | concentration_pct |
| `COMPOUND_BREAKDOWN_TOTAL` | 6 | 6 | free_text | free_text |
| `COMPOUND_OTHER` | 6 | 6 | free_text | free_text |
| `PCT_RANGE_BOTH` | 5 | 5 | numeric | concentration_pct |
| `PER_SQ_M` | 3 | 3 | numeric | per_sq_m |
| `DEFECT_TRUNCATED` | 3 | 3 | defect | free_text |
| `DEFECT_COLUMN_COLLAPSE` | 3 | 3 | defect | free_text |
| `DEFECT_RATIO_OR_INEQUALITY` | 2 | 3 | defect | free_text |
| `PER_N_SQ_M` | 2 | 2 | numeric | per_sq_m |
| `COMPOUND_RANGE_SUM` | 2 | 2 | free_text | free_text |
| `PER_LITRE_BARE` | 1 | 1 | numeric | per_litre_water |

| branch | distinct | % distinct | cells | % cells |
|---|---|---|---|---|
| numeric | 1523 | 72.1% | 5912 | 82.9% |
| free_text | 565 | 26.7% | 1189 | 16.7% |
| defect | 25 | 1.2% | 29 | 0.4% |
| **unclassified** | **0** | — | 0 | — |

## 3. Examples, verbatim

### `BARE_NUMBER` — 337 distinct / 3364 cells — numeric / `per_ha`

```text
'500'   [x1139  dilution_water,dose_ai,dose_formulation]
'1000'   [x251  dilution_water,dose_ai,dose_formulation]
'750'   [x107  dilution_water,dose_ai,dose_formulation]
'400'   [x85  dilution_water,dose_ai,dose_formulation]
'250'   [x85  dilution_water,dose_ai,dose_formulation]
```

### `BARE_RANGE` — 456 distinct / 1283 cells — numeric / `per_ha`

```text
'500 –1000'   [x122  dilution_water]
'750-1000'   [x85  dilution_water,dose_ai,dose_formulation]
'500-1000'   [x44  dilution_water,dose_formulation]
'500-750'   [x42  dilution_water,dose_formulation]
'500 –750'   [x33  dilution_water,dose_ai,dose_formulation]
```

### `NULL_MARKER` — 7 distinct / 422 cells — free_text / `free_text`

```text
'-'   [x381  dilution_water,dose_ai,dose_formulation]
'NA'   [x26  dilution_water]
'N/A'   [x6  dilution_water]
'Not applicable'   [x5  dilution_water]
'--'   [x2  dilution_water,dose_ai]
```

### `COMPOUND_SUM` — 269 distinct / 387 cells — free_text / `free_text`

```text
'124.5+1000'   [x7  dose_ai]
'82.5+137.25'   [x6  dose_ai]
'50+100'   [x5  dose_ai]
'50+50'   [x5  dose_ai]
'60 +60'   [x5  dose_ai]
```

### `NUM_UNIT` — 170 distinct / 353 cells — numeric / `per_ha`

```text
'500gm'   [x17  dose_ai,dose_formulation]
'125gm'   [x14  dose_ai]
'1250gm'   [x14  dose_ai]
'2.5kg'   [x12  dose_ai,dose_formulation]
'1667gm'   [x10  dose_formulation]
```

### `RANGE_UNIT` — 78 distinct / 242 cells — numeric / `per_ha`

```text
'1.5-2KG'   [x29  dose_formulation]
'750-1000 Lt'   [x29  dilution_water]
'1.125-  1.5KG'   [x27  dose_ai]
'1.5-2kg'   [x12  dose_formulation]
'1.125-1.5  kg'   [x8  dose_ai]
```

### `PER_KG_SEED` — 87 distinct / 123 cells — numeric / `per_kg_seed`

```text
'2-2.5 gm/  kg seed'   [x5  dose_formulation]
'1.5 - 1.875  gm/ kg seed'   [x5  dose_ai]
'6-8 ml/kg  seed'   [x4  dilution_water]
'6 ml/kg seed'   [x3  dose_formulation]
'20-30gm  Per kg seed'   [x3  dose_formulation]
```

### `PCT_WITH_EQUIV` — 77 distinct / 121 cells — numeric / `concentration_pct`

```text
'0.03% or 0.3 g/l'   [x9  dose_ai]
'0.1% or 1 ml /  Litre water'   [x9  dose_formulation]
'0.21%or  210  g/100Ltr.  water'   [x5  dose_ai]
'0.30%or300  gram/100Ltr.  water'   [x5  dose_formulation]
'0.10%  or100  Gram in  100lit.  Of water'   [x4  dose_ai]
```

### `PROSE_NO_NUMBER` — 67 distinct / 108 cells — free_text / `free_text`

```text
'This is used as  seed dresser'   [x9  dilution_water]
'As required'   [x8  dilution_water]
'Broadcasting'   [x4  dilution_water]
'Air tight cover'   [x3  dose_ai]
'Sufficient to  coat the seeds  uniformly'   [x3  dilution_water]
```

### `PCT_SINGLE` — 34 distinct / 87 cells — numeric / `concentration_pct`

```text
'0.025%'   [x9  dose_ai]
'0.05%'   [x8  dose_ai,dose_formulation]
'1 %'   [x8  dose_formulation]
'0.28 % w/w'   [x6  dose_ai]
'0.03%'   [x4  dose_ai]
```

### `COMPOUND_RANGE` — 59 distinct / 76 cells — free_text / `free_text`

```text
'43.31 +37.13-  45.94 +39.38'   [x6  dose_ai]
'125+125 - 150 + 150'   [x5  dose_ai]
'25 +75-  37.5 +112.5'   [x3  dose_ai]
'12.32+12.32-  15.4+15.4'   [x3  dose_ai]
'37.5+37.5 – 50+50'   [x2  dose_ai]
```

### `PER_HA_EXPLICIT` — 42 distinct / 68 cells — numeric / `per_ha`

```text
'2.5 kg/ha'   [x7  dose_formulation]
'0.44-1.10/ha'   [x6  dose_ai]
'2-5 lit/hectare'   [x6  dose_formulation]
'500 L/ha'   [x6  dilution_water]
'1 kg/ha'   [x3  dose_formulation]
```

### `PROSE_METHOD` — 47 distinct / 52 cells — free_text / `free_text`

```text
'Slurry seed  treatment  with  200g/100  Kg seed'   [x4  dose_ai]
'Seed  Treatment:  Mix required  quantity of the  seeds with the  required  quantity of  Trichoderma  viride 1.0%  WP and  ensure  uniform  coating shade  dry and sow'   [x2  dilution_water]
'Seed  Treatment:  Mix  9  kg  of  the  product per kg seed.'   [x2  dilution_water]
'One tablet of 12  gm/burrow'   [x1  dose_formulation]
'Dosage/1000 seedlings'   [x1  dose_ai]
```

### `PER_LITRE` — 42 distinct / 48 cells — numeric / `per_litre_water`

```text
'1.5 g a.i./Ltr.'   [x2  dose_ai]
'2.0 g/Ltr.'   [x2  dose_formulation]
'0.15 gm per  lit'   [x2  dose_ai]
'2.5 ml per lit of  water'   [x2  dose_formulation]
'0.2 ml/Ltr.'   [x2  dose_ai]
```

### `NUM_WITH_METHOD` — 43 distinct / 47 cells — numeric / `per_ha*`

```text
'10 ml/kg (To make  slurry)'   [x5  dilution_water]
'0.50 gm/tree (Root  feeding)'   [x1  dose_ai]
'500-1000/ as per age  of tree'   [x1  dilution_water]
'500-625  (depending    upon stage of                  crop)'   [x1  dose_formulation]
'600  Application  method-Soil  drench (Single  application),  Application  time-At the time  of sowing to  before  transplanting'   [x1  dose_formulation]
```

### `PER_N_KG_SEED` — 38 distinct / 47 cells — numeric / `per_kg_seed`

```text
'0.75-  1.0/100kg  seed'   [x4  dilution_water]
'1Lit./10 kg seed'   [x3  dilution_water]
'600g/100  Kg seed'   [x3  dose_formulation]
'0.24 g/10 Kg  of seed'   [x2  dose_ai]
'3.0 ml/10 kg  seeds'   [x2  dose_formulation]
```

### `COMPOUND_TOTAL_BREAKDOWN` — 25 distinct / 40 cells — free_text / `free_text`

```text
'1.344  (0.144+1.2)'   [x3  dose_ai]
'148 g/ha (91  +57)'   [x3  dose_ai]
'165 (90+75)'   [x3  dose_ai]
'100 (37.50+62.50)'   [x3  dose_ai]
'300 (50 + 250)'   [x2  dose_ai]
```

### `PER_TREE` — 32 distinct / 35 cells — numeric / `per_tree`

```text
'10 lit/tree'   [x2  dilution_water]
'10 Lit./tree'   [x2  dilution_water]
'10Ltr.  Water per tree'   [x2  dilution_water]
'6-7 litre water/  tree'   [x1  dilution_water]
'7.50 ml/tree'   [x1  dose_formulation]
```

### `PER_N_LITRE` — 29 distinct / 33 cells — numeric / `per_litre_water`

```text
'50ml/100Ltr.  water'   [x4  dose_formulation]
'72.8 g a.i./100 lit  water'   [x2  dose_ai]
'15ml/100  ltr water'   [x1  dose_formulation]
'25 ml/100 lit'   [x1  dose_ai]
'0.90/10 Lit water'   [x1  dose_ai]
```

### `UNSUPPORTED_UNIT` — 27 distinct / 30 cells — free_text / `free_text`

```text
'900 g/100 m3'   [x2  dose_ai]
'01 mg per spot'   [x2  dose_ai]
'24-32  gm/m3'   [x2  dose_formulation]
'03 tablets/10 gm per  ton  or  225  gm/100  m3'   [x1  dose_ai]
'14 tablets/1000 m3  or 150gm/ 100 m3 or  4 pouch 10 gms  each/ 1000 CFT or  150 gm/100 m3'   [x1  dose_ai]
```

### `PCT_EQUIV_FIRST` — 22 distinct / 23 cells — numeric / `concentration_pct`

```text
'2500gmor  0.25%'   [x2  dose_formulation]
'60 gm (0.006%  Conc.)'   [x1  dose_ai]
'75 (0.0075%)'   [x1  dose_ai]
'750  (0.075%)'   [x1  dose_formulation]
'90 (0.009%)'   [x1  dose_ai]
```

### `MULTI_BASIS` — 16 distinct / 20 cells — free_text / `free_text`

```text
'400 ml/ha or  0.8 ml/L'   [x3  dose_formulation]
'500 ml/ha 1  ml/lit water'   [x3  dose_formulation]
'0.02g/plant & 444  to 512 g/ha'   [x1  dose_ai]
'1.0 g/plant  & 22.2 to  25.6  Kg/ha'   [x1  dose_formulation]
'0.02 g/plant & 160  to 200 g/ha'   [x1  dose_ai]
```

### `PER_PLANT` — 17 distinct / 19 cells — numeric / `per_plant`

```text
'1.2 L/ Plant'   [x2  dilution_water]
'50-100 ml/Plant'   [x2  dilution_water]
'01 g/ suckers'   [x1  dose_ai]
'33 g/sucker'   [x1  dose_formulation]
'50 g/ suckers'   [x1  dose_ai]
```

### `COMPOUND_NAMED` — 17 distinct / 19 cells — free_text / `free_text`

```text
'27 (Emamectin  benzoate  3.0+Lufenuron 24.0)'   [x2  dose_ai]
'108 (Spiropidion 60 +  Acetamiprid 48) – 135  (Spiropidion 75 +  Acetamiprid 60)'   [x2  dose_ai]
'1.58 (Cyantraniliprole  0.79 + Thiamethoxam  0.79)'   [x1  dose_ai]
'2.38 (Cyantranilip role  1.19 + Thiamethoxa m  1.19)'   [x1  dose_ai]
'27 (Emamectin benzoate  3.0+Lufenuron24.0)'   [x1  dose_ai]
```

### `MULTI_RATE` — 9 distinct / 11 cells — free_text / `free_text`

```text
'100 g/a.i./L or  0.2 g a.i./L'   [x3  dose_ai]
'6 ml/kg seed  10-12 ml/kg seed'   [x1  dilution_water]
'8 ml/kg seed  10-12 ml/kg seed'   [x1  dilution_water]
'4 ml/kg seed  6-8 ml/kg seed'   [x1  dilution_water]
'6 ml/kg seed  6-8 ml/kg seed'   [x1  dilution_water]
```

### `DEFECT_AI_NAME` — 9 distinct / 11 cells — defect / `free_text`

```text
'Flubendamide-  52.5 &  Hexaconazole-  75'   [x2  dose_ai]
'Kresoxim-methyl-  150 &  Chlorothalonil- 560'   [x2  dose_ai]
'Flubendiamide –  43.75 &  Hexaconazole –  62.5'   [x1  dose_ai]
'Ametoctradin  25% (w/w) +  Metalaxyl 20%  (w/w) WDG'   [x1  dose_ai]
'Flubendamide-  35 &  Hexaconazole-  50'   [x1  dose_ai]
```

### `ALTERNATIVE_VALUES` — 8 distinct / 10 cells — free_text / `free_text`

```text
'625  (2  application)    or 1250  (Single  application)'   [x2  dose_formulation]
'500 (via Knap  sack )  20 (via drone  application)'   [x2  dilution_water]
'250  (2 application)  or 500  (Single application)'   [x1  dose_ai]
'250  (2 application)  or  500 (Single  application)'   [x1  dose_ai]
'500  Application  method-Soil  drench (Single  application),  Application  time-8-10days  after  transplanting'   [x1  dose_formulation]
```

### `DEFECT_TIME_VALUE` — 8 distinct / 9 cells — defect / `free_text`

```text
'48 hrs.'   [x2  dose_formulation]
'05 days'   [x1  dose_formulation]
'72 hrs.'   [x1  dose_formulation]
'48 hrs.      24 hrs.'   [x1  dose_formulation]
'07days'   [x1  dose_formulation]
```

### `PCT_RANGE` — 8 distinct / 8 cells — numeric / `concentration_pct`

```text
'0.00048-  0.00096%'   [x1  dose_ai]
'0.025- 0.050%'   [x1  dose_formulation]
'0.03 – 0.05 %'   [x1  dose_ai]
'0.0025-0.005%'   [x1  dose_ai]
'0.01-0.012%'   [x1  dose_ai]
```

### `COMPOUND_BREAKDOWN_TOTAL` — 6 distinct / 6 cells — free_text / `free_text`

```text
'120+25+10  (155)'   [x1  dose_ai]
'122.9 + 18.4  (141.3)'   [x1  dose_ai]
'(9.375 + 11.25 + 33.75)  = 54.375'   [x1  dose_ai]
'0.1+0.1 (0.2)'   [x1  dose_ai]
'125+125(250) g'   [x1  dose_ai]
```

### `COMPOUND_OTHER` — 6 distinct / 6 cells — free_text / `free_text`

```text
'136 (12 + 124) –  153 (13.5 + 139.5)'   [x1  dose_ai]
'136 (12 + 124)  –  153 (13.5 + 139.5)'   [x1  dose_ai]
'0.32  (0.026+0.026+0.27) - 0 .63(0.05+0.05+0.5 3)'   [x1  dose_ai]
'(125 + 812.5) –  937.5 g'   [x1  dose_ai]
'124+496  0.02% + 0.08%'   [x1  dose_ai]
```

### `PCT_RANGE_BOTH` — 5 distinct / 5 cells — numeric / `concentration_pct`

```text
'0.025% -0.05%'   [x1  dose_ai]
'0.005%  0.05%'   [x1  dose_formulation]
'0.005%  0.2%'   [x1  dose_formulation]
'0.02% - 0.03%'   [x1  dose_ai]
'0.056% --0.075%'   [x1  dose_ai]
```

### `PER_SQ_M` — 3 distinct / 3 cells — numeric / `per_sq_m`

```text
'250  ml/sq.mtr'   [x1  dilution_water]
'1 Lit/sq.  meter'   [x1  dilution_water]
'2.0 L/m2'   [x1  dilution_water]
```

### `DEFECT_TRUNCATED` — 3 distinct / 3 cells — defect / `free_text`

```text
'594 +59.4 –'   [x1  dose_ai]
'(7.5+15.0) to  (8.75+17.5) (for'   [x1  dose_ai]
'10 kg seed)'   [x1  dose_ai]
```

### `DEFECT_COLUMN_COLLAPSE` — 3 distinct / 3 cells — defect / `free_text`

```text
'30-37.5    0.03-  0.0375%'   [x1  dose_ai]
'750-1000  750-1000  750-1000'   [x1  dilution_water]
'300/500 respectively'   [x1  dilution_water]
```

### `DEFECT_RATIO_OR_INEQUALITY` — 2 distinct / 3 cells — defect / `free_text`

```text
'37:3'   [x2  dose_ai]
'>140'   [x1  dose_ai]
```

### `PER_N_SQ_M` — 2 distinct / 2 cells — numeric / `per_sq_m`

```text
'1 litre/30 m2'   [x1  dilution_water]
'1.5-2.5  litre/50 m2'   [x1  dilution_water]
```

### `COMPOUND_RANGE_SUM` — 2 distinct / 2 cells — free_text / `free_text`

```text
'60-75 + 40-50'   [x1  dose_ai]
'8 to 10 +0.20 to  0.25'   [x1  dose_ai]
```

### `PER_LITRE_BARE` — 1 distinct / 1 cells — numeric / `per_litre_water`

```text
'10lit. water'   [x1  dilution_water]
```

## 4. The percentage / per-litre group (the '~72')

Reproducing `tools/phase3_fallback_diagnosis.py` q5 exactly (a row counts if any dose column contains `%` or matches `per lit|/lit|ml/l|gram in <n>`):

| file | rows with %/per-litre dose cell | of those, crop in scope.py's 8 |
|---|---|---|
| `insecticides` | 44 | 4 |
| `fungicides` | 135 | 44 |
| `bio_insecticides` | 1 | 0 |
| `bio_fungicides` | 26 | 9 |
| **total** | **206** | **57** |

### 4.1 The '72' is stale

`reports/phase3_fallback_diagnosis.md` records 276 / **72** for this same
query. Re-running `tools/phase3_fallback_diagnosis.py` unchanged against the
CURRENT CSVs reproduces the numbers above, not the ones in the committed
report. The report was generated on 2026-08-29 from the Step-2 extraction as
it stood before three later Phase 3 fixes (header fragments / method column,
the phantom merge, the row-7 quarantine fix), all of which corrected
mis-columned cells. The largest movement is `bio_insecticides` 26 -> 1: that
file now has exactly one `%` dose cell, and inspection confirms that is
correct — its doses really are almost all bare per-hectare numbers.

So the real size of this group today is **206 rows / 57 in-scope rows**, and
the committed 72 should be read as a pre-fix figure. The Phase 3 report was
not modified.

### 4.2 The in-scope strings

Those 57 in-scope rows carry **78 distinct dose strings**, listed in full below with the pattern each falls into.

| # | raw string | col | pattern | branch |
|---|---|---|---|---|
| 1 | `0.10% or100 Gram in 100lit. Of water` | dose_ai | `PCT_WITH_EQUIV` | numeric |
| 2 | `0.20%or 200mlin 200lt. of water` | dose_formulation | `PCT_WITH_EQUIV` | numeric |
| 3 | `0.21%or 210 g/100Ltr. water` | dose_ai | `PCT_WITH_EQUIV` | numeric |
| 4 | `0.30%or300 gram/100Ltr. water` | dose_formulation | `PCT_WITH_EQUIV` | numeric |
| 5 | `0.03% or 0.3 g/l` | dose_ai | `PCT_WITH_EQUIV` | numeric |
| 6 | `0.1% or 1 ml / Litre water` | dose_formulation | `PCT_WITH_EQUIV` | numeric |
| 7 | `0.1%` | dose_formulation | `PCT_SINGLE` | numeric |
| 8 | `0.15 gm per lit` | dose_ai | `PER_LITRE` | numeric |
| 9 | `2.5 ml per lit of water` | dose_formulation | `PER_LITRE` | numeric |
| 10 | `0.28 % w/w` | dose_ai | `PCT_SINGLE` | numeric |
| 11 | `1 %` | dose_formulation | `PCT_SINGLE` | numeric |
| 12 | `0.75 ml/L water` | dose_formulation | `PER_LITRE` | numeric |
| 13 | `75 (0.0075%)` | dose_ai | `PCT_EQUIV_FIRST` | numeric |
| 14 | `750 (0.075%)` | dose_formulation | `PCT_EQUIV_FIRST` | numeric |
| 15 | `90 (0.009%)` | dose_ai | `PCT_EQUIV_FIRST` | numeric |
| 16 | `900 (0.09%)` | dose_formulation | `PCT_EQUIV_FIRST` | numeric |
| 17 | `0.08%` | dose_ai,dose_formulation | `PCT_SINGLE` | numeric |
| 18 | `0.023%` | dose_ai | `PCT_SINGLE` | numeric |
| 19 | `0.005% 0.05%` | dose_formulation | `PCT_RANGE_BOTH` | numeric |
| 20 | `0.25%` | dose_ai | `PCT_SINGLE` | numeric |
| 21 | `0.046% or 46 g /100 lit. water` | dose_ai | `PCT_WITH_EQUIV` | numeric |
| 22 | `0.1%or100 ml/100lit.Wat er` | dose_formulation | `PCT_WITH_EQUIV` | numeric |
| 23 | `0.15%(150 gm/100 Ltr. water)` | dose_ai | `PCT_WITH_EQUIV` | numeric |
| 24 | `0.2%(200gm/ 100L water)` | dose_formulation | `PCT_WITH_EQUIV` | numeric |
| 25 | `0.12%or 120g/100Ltr. water` | dose_ai | `PCT_WITH_EQUIV` | numeric |
| 26 | `0.24%or 240g/100Ltr. water` | dose_formulation | `PCT_WITH_EQUIV` | numeric |
| 27 | `0.12%` | dose_ai | `PCT_SINGLE` | numeric |
| 28 | `0.24%or 240gm/100 ltr. water` | dose_formulation | `PCT_WITH_EQUIV` | numeric |
| 29 | `0.025%or 25 g/100 ltr. water` | dose_ai | `PCT_WITH_EQUIV` | numeric |
| 30 | `0.1%or 100 ml/100 ltr..water.` | dose_formulation | `PCT_WITH_EQUIV` | numeric |
| 31 | `0.025% or 25g/100ltr. water` | dose_ai | `PCT_WITH_EQUIV` | numeric |
| 32 | `0.1%or 100 ml/100 ltr. water.` | dose_formulation | `PCT_WITH_EQUIV` | numeric |
| 33 | `0.0075% or 7.5 g/l00ltr. water` | dose_ai | `PCT_WITH_EQUIV` | numeric |
| 34 | `0.03% or 30ml/100 ltr. of water` | dose_formulation | `PCT_WITH_EQUIV` | numeric |
| 35 | `0.005% (5g/100 lit)` | dose_ai | `PCT_WITH_EQUIV` | numeric |
| 36 | `0.1%or (100ml/100 lit)` | dose_formulation | `PCT_WITH_EQUIV` | numeric |
| 37 | `30-37.5 0.03- 0.0375%` | dose_ai | `DEFECT_COLUMN_COLLAPSE` | defect |
| 38 | `0.10% or100 Gram in 100lit. of water` | dose_ai | `PCT_WITH_EQUIV` | numeric |
| 39 | `0.20%or 200mlin 200lit.of water` | dose_formulation | `PCT_WITH_EQUIV` | numeric |
| 40 | `0.175% or175 gm/100 Lt. water` | dose_ai | `PCT_WITH_EQUIV` | numeric |
| 41 | `0.5%or500 gm/100lt. water` | dose_formulation | `PCT_WITH_EQUIV` | numeric |
| 42 | `0.2 ml/Ltr.` | dose_ai | `PER_LITRE` | numeric |
| 43 | `0.8 ml/Ltr.` | dose_formulation | `PER_LITRE` | numeric |
| 44 | `0.02% or 0.2 ml/Ltr.` | dose_ai | `PCT_WITH_EQUIV` | numeric |
| 45 | `0.08% or 0.8ml/Ltr.` | dose_formulation | `PCT_WITH_EQUIV` | numeric |
| 46 | `0.004%` | dose_ai | `PCT_SINGLE` | numeric |
| 47 | `0.04%` | dose_formulation | `PCT_SINGLE` | numeric |
| 48 | `0.005% or5 gm/100 Ltr. water` | dose_ai | `PCT_WITH_EQUIV` | numeric |
| 49 | `0.165%or 165 g/10Ltr. water` | dose_ai | `PCT_WITH_EQUIV` | numeric |
| 50 | `0.30%or300 ml/100Ltr. water` | dose_formulation | `PCT_WITH_EQUIV` | numeric |
| 51 | `0.0025%` | dose_ai | `PCT_SINGLE` | numeric |
| 52 | `0.010%` | dose_formulation | `PCT_SINGLE` | numeric |
| 53 | `Ametoctradin 25% (w/w) + Metalaxyl 20% (w/w) WDG` | dose_ai | `DEFECT_AI_NAME` | defect |
| 54 | `500 ml/ha 1 ml/lit water` | dose_formulation | `MULTI_BASIS` | free_text |
| 55 | `0.23%` | dose_ai | `PCT_SINGLE` | numeric |
| 56 | `0.30%` | dose_formulation | `PCT_SINGLE` | numeric |
| 57 | `0.11%` | dose_ai | `PCT_SINGLE` | numeric |
| 58 | `0.15%` | dose_formulation | `PCT_SINGLE` | numeric |
| 59 | `2.25 kg (0.3%)` | dose_formulation | `PCT_EQUIV_FIRST` | numeric |
| 60 | `0.05%` | dose_ai,dose_formulation | `PCT_SINGLE` | numeric |
| 61 | `0.17% or 1700 gm` | dose_ai | `PCT_WITH_EQUIV` | numeric |
| 62 | `0.25% or 2500 gm` | dose_formulation | `PCT_WITH_EQUIV` | numeric |
| 63 | `0.17% or 1.7 g a.i./L water` | dose_ai | `PCT_WITH_EQUIV` | numeric |
| 64 | `0.25% or 2.5 g /L water` | dose_formulation | `PCT_WITH_EQUIV` | numeric |
| 65 | `0.073% or 364 g` | dose_ai | `PCT_WITH_EQUIV` | numeric |
| 66 | `0.2% or 1000 ml` | dose_formulation | `PCT_WITH_EQUIV` | numeric |
| 67 | `2 ml/l of water` | dose_formulation | `PER_LITRE` | numeric |
| 68 | `2000gor 0.4%` | dose_ai | `PCT_EQUIV_FIRST` | numeric |
| 69 | `2500gor 0.5%` | dose_formulation | `PCT_EQUIV_FIRST` | numeric |
| 70 | `3 kg per ha (06 g/litre water) (Foliar spray)` | dose_formulation | `MULTI_BASIS` | free_text |
| 71 | `2 ml/litre water` | dose_formulation | `PER_LITRE` | numeric |
| 72 | `Seed Treatment: Mix required quantity of the seeds with the required quantity of Pseudomonas fluorescens0.5% WP and ensure uniform coating, shade dry and sow` | dilution_water | `PROSE_METHOD` | free_text |
| 73 | `Seed treatment- Mix required quantity of the seeds with the required quantity of Pseudomonas fluorescens WP and ensure uniform coating with 0.2% Foliar spray, shade dry and sow` | dilution_water | `PROSE_METHOD` | free_text |
| 74 | `Seed Treatment: Make a thin paste of required quantity of Pseudomonas fluorescens 1.0% WP with the minimum volume of water & coat the seed uniformly, shade dry the seed just before sowing.` | dilution_water | `PROSE_METHOD` | free_text |
| 75 | `10gm/lit res of water` | dose_formulation | `PER_LITRE` | numeric |
| 76 | `Seed Treatment- Mix the required quantity of seeds with the required quantity of Trichoderma viride 0.50% WP and ensure uniform coating, Shade dry and sow.` | dilution_water | `PROSE_METHOD` | free_text |
| 77 | `5ml/ kg s eed + 5 ml/ lit wat er + 3000 ml/ha` | dose_formulation | `MULTI_BASIS` | free_text |
| 78 | `Seed Treatment: Mix required quantity of the seeds with the required quantity of Trichoderma viride 1.0% WP and ensure uniform coating, shade dry and sow` | dilution_water | `PROSE_METHOD` | free_text |

Pattern mix across those rows:

- `PCT_WITH_EQUIV` — 36 distinct
- `PCT_SINGLE` — 16 distinct
- `PER_LITRE` — 8 distinct
- `PCT_EQUIV_FIRST` — 7 distinct
- `PROSE_METHOD` — 5 distinct
- `MULTI_BASIS` — 3 distinct
- `PCT_RANGE_BOTH` — 1 distinct
- `DEFECT_COLUMN_COLLAPSE` — 1 distinct
- `DEFECT_AI_NAME` — 1 distinct

## 5. Strings I cannot confidently assign

Every one of the 2113 strings landed in a named pattern (zero
`UNCLASSIFIED`). These are the cases where the pattern is clear but the
BASIS is a judgement call, so Phase B should not decide them silently.

**1. dilution_water is not a dose column**

Its CIB&RC header is 'Dilution in Water (Liter)' — spray volume, which the schema carries as ChemicalOption.spray_volume_*, not as a Dose. 2334 of the 7130 cells scanned come from it. It is surveyed here because column-shifted rows do drop real doses into it, but Phase B should not mint per_ha Doses out of it wholesale.

```text
'500'
'500 –1000'
'As required depending upon crop stage and plant protection equipment used'
'6 ml/kg seed 10-12 ml/kg seed'
```

**2. PCT_EQUIV_FIRST where the equivalent is per-plant, not per-area**

These state one dose two ways, but the two ways are different BASES: g/vine and %. Choosing concentration_pct discards the per-vine figure and vice versa.

```text
'1.8ga.i/vine  or0.09%'
'2.5gm/vine  or0.125%'
```

**3. PER_N_KG_SEED needs an explicit normalisation rule**

'38.75 g/10 kg seeds' is per_kg_seed only after dividing by 10. If Phase B does not divide, the dose is 10x too high. If it does divide, the printed number no longer appears in the parsed value.

```text
'38.75 g/10 kg  seeds'
'600g/100  Kg seed'
'0.75-1.0/100  Kg seed'
```

**4. PER_N_LITRE likewise**

'25 ml/100 lit' is per_litre_water only after dividing by 100.

```text
'25 ml/100 lit'
'70-87.5/100 l of  water'
'0.90/10 Lit water'
```

**5. NUM_WITH_METHOD is numeric only if the qualifier is discardable**

'750 (Soil drench)' is a number plus an application method — safe to parse and keep the method in `raw`. But the same bucket holds '500 20 ltr/ha (via drone application)', which is two volumes for two equipment types. Splitting these needs a decision.

```text
'750  (Soil drench)'
'500-750  depending upon  crop canopy'
'500  20 ltr/ha (via  drone  application)'
```

**6. Ranges: which end is kept**

Dose has value_min and value_max, so a range can be carried whole. Stating the rule anyway because the Advisory layer will later have to pick one, and PHI already documents the opposite choice (larger = safer for PHI; for dose the LOWER end is the safer one).

```text
'500-750'
'1.5-2KG'
'0.0025-0.005%'
```
