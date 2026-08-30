# Phase 4 Step D — dose_parse_report

Wrote C:\Users\J\OneDrive\Desktop\Fine-Tuning project\agri-llm\data\interim\dose_parse_report.csv (7406 rows: every dose_ai and dose_formulation cell across the 4 in-scope files)

## 4a. Coverage by branch

| column | branch | count | % of column |
|---|---|---|---|
| `dose_ai` | numeric | 1640 | 44.3% |
| `dose_ai` | free_text | 571 | 15.4% |
| `dose_ai` | empty | 1470 | 39.7% |
| `dose_ai` | unparseable | 22 | 0.6% |
| `dose_formulation` | numeric | 581 | 15.7% |
| `dose_formulation` | free_text | 55 | 1.5% |
| `dose_formulation` | empty | 1336 | 36.1% |
| `dose_formulation` | unparseable | 1731 | 46.7% |

| branch | count (both columns) | % of all cells |
|---|---|---|
| numeric | 2221 | 30.0% |
| free_text | 626 | 8.5% |
| empty | 2806 | 37.9% |
| unparseable | 1753 | 23.7% |

## 4b. Unparseable — full distinct (raw_string, code) list

1753 unparseable cells total, 468 distinct (raw_string, code) pairs. Split below because NEEDS_UNIT is the expected, correct outcome for a bare dose_formulation number (rule 8 — see section 5) and would otherwise bury the small number of genuinely actionable rows.

### 4b.1 NEEDS_UNIT — 1719 cells, 438 distinct raw strings — expected, not shown here (see section 5)

### 4b.2 Everything else — 34 cells, 30 distinct pairs — the actionable list

| raw_string | code | occurrences | columns | files |
|---|---|---|---|---|
| `48 hrs.` | TIME_VALUE | 2 | dose_formulation | insecticides |
| `Flubendamide-  52.5 &  Hexaconazole-  75` | AI_NAME | 2 | dose_ai | fungicides |
| `37:3` | RATIO_OR_INEQUALITY | 2 | dose_ai | fungicides |
| `Kresoxim-methyl-  150 &  Chlorothalonil- 560` | AI_NAME | 2 | dose_ai | fungicides |
| `05 days` | TIME_VALUE | 1 | dose_formulation | insecticides |
| `72 hrs.` | TIME_VALUE | 1 | dose_formulation | insecticides |
| `48 hrs.      24 hrs.` | TIME_VALUE | 1 | dose_formulation | insecticides |
| `07days` | TIME_VALUE | 1 | dose_formulation | insecticides |
| `25    50` | COLUMN_COLLAPSE | 1 | dose_ai | insecticides |
| `100    200` | COLUMN_COLLAPSE | 1 | dose_formulation | insecticides |
| `Flubendiamide –  43.75 &  Hexaconazole –  62.5` | AI_NAME | 1 | dose_ai | insecticides |
| `594 +59.4 –` | TRUNCATED | 1 | dose_ai | insecticides |
| `0.005%  0.05%` | AMBIGUOUS_PAIR | 1 | dose_formulation | fungicides |
| `0.005%  0.2%` | AMBIGUOUS_PAIR | 1 | dose_formulation | fungicides |
| `30-50 gm  0.030%  0.050%` | COLUMN_COLLAPSE | 1 | dose_ai | fungicides |
| `30-37.5    0.03-  0.0375%` | COLUMN_COLLAPSE | 1 | dose_ai | fungicides |
| `500  500  500` | COLUMN_COLLAPSE | 1 | dose_ai | fungicides |
| `715  715  715` | COLUMN_COLLAPSE | 1 | dose_formulation | fungicides |
| `Ametoctradin  25% (w/w) +  Metalaxyl 20%  (w/w) WDG` | AI_NAME | 1 | dose_ai | fungicides |
| `(7.5+15.0) to  (8.75+17.5) (for` | TRUNCATED | 1 | dose_ai | fungicides |
| `10 kg seed)` | TRUNCATED | 1 | dose_ai | fungicides |
| `Flubendamide-  35 &  Hexaconazole-  50` | AI_NAME | 1 | dose_ai | fungicides |
| `1000 to 1250 ml 375 – 500 L` | COLUMN_COLLAPSE | 1 | dose_formulation | fungicides |
| `Fluopyram112.5  +Tebconazole112.5` | AI_NAME | 1 | dose_ai | fungicides |
| `Fluopyram100  +Tebconazole100` | AI_NAME | 1 | dose_ai | fungicides |
| `Fluopyram110  +Tebconazole110` | AI_NAME | 1 | dose_ai | fungicides |
| `Kresoxim-methyl-  200  &Hexaconazole -  40` | AI_NAME | 1 | dose_ai | fungicides |
| `1500   1140` | COLUMN_COLLAPSE | 1 | dose_ai | fungicides |
| `1500  750` | COLUMN_COLLAPSE | 1 | dose_formulation | fungicides |
| `>140` | RATIO_OR_INEQUALITY | 1 | dose_ai | bio_insecticides |

## 4c. Numeric — parsed_basis frequency

2221 numeric cells.

| basis | count | % of numeric |
|---|---|---|
| per_ha | 1739 | 78.3% |
| concentration_pct | 240 | 10.8% |
| per_kg_seed | 143 | 6.4% |
| per_litre_water | 74 | 3.3% |
| per_tree | 13 | 0.6% |
| per_plant | 12 | 0.5% |

## 4d. Random sample (5 per branch, seed=20260404)

### numeric (5 of 2221)

```text
fungicides_20260331.pdf p55 row3 [dose_formulation]
  raw:     '3.5gm/Kg  seed'
  pattern: PER_KG_SEED   code: -
  parsed:  basis=per_kg_seed min=3.5 max= unit=g

insecticides_20260331.pdf p36 row11 [dose_ai]
  raw:     '300 - 540'
  pattern: BARE_RANGE   code: -
  parsed:  basis=per_ha min=300.0 max=540.0 unit=g

insecticides_20260331.pdf p53 row3 [dose_formulation]
  raw:     '5 ml/kg seed'
  pattern: PER_KG_SEED   code: -
  parsed:  basis=per_kg_seed min=5.0 max= unit=ml

fungicides_20260331.pdf p35 row8 [dose_ai]
  raw:     '1.50-2.00  kg'
  pattern: RANGE_UNIT   code: -
  parsed:  basis=per_ha min=1.5 max=2.0 unit=kg

insecticides_20260331.pdf p39 row8 [dose_ai]
  raw:     '60'
  pattern: BARE_NUMBER   code: -
  parsed:  basis=per_ha min=60.0 max= unit=g

```

### free_text (5 of 626)

```text
fungicides_20260331.pdf p59 row4 [dose_ai]
  raw:     '50 + 250'
  pattern: COMPOUND   code: -
  parsed:  basis=free_text min= max= unit=

fungicides_20260331.pdf p66 row10 [dose_ai]
  raw:     '0.1052+0.0048'
  pattern: COMPOUND   code: -
  parsed:  basis=free_text min= max= unit=

insecticides_20260331.pdf p67 row7 [dose_ai]
  raw:     '312 +32'
  pattern: COMPOUND   code: -
  parsed:  basis=free_text min= max= unit=

insecticides_20260331.pdf p82 row10 [dose_ai]
  raw:     '43.31 +37.13-  45.94 +39.38'
  pattern: COMPOUND   code: -
  parsed:  basis=free_text min= max= unit=

fungicides_20260331.pdf p33 row2 [dose_formulation]
  raw:     'Disease  and  can  be  controlled  by spraying  40gmswith  350 to 420  gms copper  oxychloride  (50% Wettable  powder) in  67 liters of  water per  hectare with  air blast  sprayer,  covering two rows on either  side.'
  pattern: PROSE_METHOD   code: -
  parsed:  basis=free_text min= max= unit=

```

### empty (5 of 2806)

```text
insecticides_20260331.pdf p62 row12 [dose_ai]
  raw:     ''
  pattern: EMPTY   code: -

fungicides_20260331.pdf p47 row4 [dose_ai]
  raw:     ''
  pattern: EMPTY   code: -

fungicides_20260331.pdf p24 row16 [dose_formulation]
  raw:     ''
  pattern: EMPTY   code: -

insecticides_20260331.pdf p91 row17 [dose_formulation]
  raw:     ''
  pattern: EMPTY   code: -

insecticides_20260331.pdf p97 row7 [dose_ai]
  raw:     ''
  pattern: EMPTY   code: -

```

### unparseable (5 of 1753)

```text
fungicides_20260331.pdf p72 row5 [dose_formulation]
  raw:     '1000'
  pattern: BARE_NUMBER   code: NEEDS_UNIT

insecticides_20260331.pdf p43 row0 [dose_formulation]
  raw:     '1000'
  pattern: BARE_NUMBER   code: NEEDS_UNIT

insecticides_20260331.pdf p69 row13 [dose_formulation]
  raw:     '350 –400'
  pattern: BARE_RANGE   code: NEEDS_UNIT

insecticides_20260331.pdf p66 row5 [dose_formulation]
  raw:     '625'
  pattern: BARE_NUMBER   code: NEEDS_UNIT

fungicides_20260331.pdf p22 row4 [dose_formulation]
  raw:     '400'
  pattern: BARE_NUMBER   code: NEEDS_UNIT

```

## 5. dose_formulation NEEDS_UNIT count

**1719** of 3703 dose_formulation cells (46.4%) returned NEEDS_UNIT — a bare number with no unit in the cell and default_unit=None, exactly as expected per dose_parser.py rule 8. These need the formulation-type lookup (EC/SC -> ml, WP/WG -> g) as a later step; this run does not attempt to resolve them.
