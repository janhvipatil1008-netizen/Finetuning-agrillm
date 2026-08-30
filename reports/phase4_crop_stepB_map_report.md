# Phase 4 (crop) Step B — crop_map_report

Wrote C:\Users\J\OneDrive\Desktop\Fine-Tuning project\agri-llm\data\interim\crop_map_report.csv (3703 output rows from every crop cell across the 4 in-scope files, all row kinds including headers; a multi-crop split produces more than one output row per input row)

## Coverage (all row kinds, i.e. includes 921+89 header rows whose crop cell is blank by construction)

- in-scope (maps to a slug): **746**
- out of scope (real crop, not one of the 8): **1713**
- not_a_crop_cell (prose that merely mentions a crop): **15**
- blank raw_crop: **1229**
- check: 3703 == 3703

Of the blanks, **219** are on data rows (`assignment_kind` in ordinal_6/fallback_subset) -- this is the number comparable to Phase A's 219. The remaining 1010 are header rows, which Phase A excluded by scope and this run does not.

## Per-slug row counts (in-scope only)

| slug | rows |
|---|---|
| cotton | 223 |
| soybean | 73 |
| tur | 44 |
| gram | 52 |
| onion | 31 |
| tomato | 178 |
| grape | 120 |
| pomegranate | 25 |
| **total** | **746** |

## Multi-crop splits

4 distinct source strings produced a multi-crop-flagged result; 4 total output rows from them.

| raw_crop | slugs produced | rows |
|---|---|---|
| `Cabbage/  Cauliflower,  Tomato,  Brinjal,  Chillies,  Beans,  Ornamental` | ['tomato'] | 1 |
| `Rice (Paddy)  &cotton` | ['cotton'] | 1 |
| `Tomato/Chilli es` | ['tomato'] | 1 |
| `Wheat, Gram` | ['gram'] | 1 |

## Pest-bled rows

9 rows total: 4 in-scope (crop of interest per your decision 3), 5 on out-of-scope crops (`slug` blank below -- the flag still fires because pest text bled into the cell regardless of which crop it names, but these rows never reach label_db since slug is None; listed for completeness).

| source_file | page | row | raw_crop | slug |
|---|---|---|---|---|
| insecticides_20260331.pdf | 86 | 7 | `Green gram  Whitefly` | (out of scope) |
| fungicides_20260331.pdf | 16 | 3 | `Paddy (Rice)  Blast,` | (out of scope) |
| fungicides_20260331.pdf | 52 | 8 | `Paddy (Rice)  Blast, sheath blight` | (out of scope) |
| fungicides_20260331.pdf | 57 | 13 | `Paddy Sheath  Blight` | (out of scope) |
| fungicides_20260331.pdf | 61 | 5 | `Pomegranate  Alternaria fruit` | pomegranate |
| bio_insecticides_20260331.pdf | 3 | 10 | `Cauliflower  Spodoptera, Diamond` | (out of scope) |
| bio_insecticides_20260331.pdf | 4 | 10 | `Pigeon Pea  Heliothis sp.` | tur |
| bio_insecticides_20260331.pdf | 5 | 5 | `Pigeon pea  Bollworm (Helicoverpa` | tur |
| bio_insecticides_20260331.pdf | 5 | 16 | `Pigeon Pea  Helicoverpa armiger` | tur |

## not_a_crop_cell rows

15 rows.

| source_file | page | row | raw_crop |
|---|---|---|---|
| insecticides_20260331.pdf | 4 | 7 | `Empty Go downs &  Sheds` |
| insecticides_20260331.pdf | 4 | 8 | `Rodents Burrows` |
| insecticides_20260331.pdf | 5 | 2 | `Millets, pulses, dry  fruits, nuts, spices  & oilseeds (Air  tight cover or go  downs)` |
| insecticides_20260331.pdf | 5 | 5 | `Other processed  Food and Empty  Godowns & Sheds  (under air tight  condition)` |
| insecticides_20260331.pdf | 5 | 11 | `Go downs,  Residential Premises,  Public halls` |
| insecticides_20260331.pdf | 8 | 14 | `Residential  premises` |
| insecticides_20260331.pdf | 8 | 15 | `Poultry Farm` |
| insecticides_20260331.pdf | 9 | 1 | `Residential premises` |
| insecticides_20260331.pdf | 9 | 2 | `Poultry Farm` |
| insecticides_20260331.pdf | 23 | 10 | `Walls, ceilings  floors of Go  downs` |
| insecticides_20260331.pdf | 23 | 11 | `Public health` |
| insecticides_20260331.pdf | 31 | 2 | `Pre- construction  (Building)` |
| insecticides_20260331.pdf | 31 | 3 | `Post- construction  (Building)` |
| insecticides_20260331.pdf | 31 | 22 | `For rodent  control in  field, storage  and crops like  rice, soybean and coconut)` |
| insecticides_20260331.pdf | 55 | 18 | `For rodent  control in  field and  residential  premises(to  be used under  the  supervision  of trained  personal)` |

## Phase A reconciliation

Phase A (data rows only, pre-split, one string = one bucket): **47 distinct strings / 746 cells**.

This run, data rows only, POST-split (multi-crop cells now contribute one output row per slug):
- distinct source strings that produced an in-scope result: **47**
- output rows: **745**

Difference from 746: **-1**.

Full explanation, not a guess: Phase A's `slugs_for` had no concept of `not_a_crop_cell` -- it token-matched every string, including prose, and its 5 flagged 'MULTI-CROP?' cells each named exactly ONE in-scope slug, so each contributed its 1 cell to that slug's total same as any other member. Phase A's 746 therefore already includes those 5 cells: `Wheat, Gram`->gram, `Rice (Paddy) &cotton`->cotton, `Tomato/Chilli es`->tomato, the Cabbage list->tomato, and the rodenticide row->soybean.

Step B changes exactly one of those five: `map_crop` recognises the rodenticide cell as prose ('For rodent control in field, storage and crops like rice, soybean and coconut)') via `_NOT_A_CROP_CELL` and returns slug=None, not_a_crop_cell=True -- per decision 1, drop entirely. The other four still resolve to exactly one slug each, unchanged. So the only expected movement is -1 (soybean loses the rodenticide cell), and 746 - 1 = 745 matches what this run produced exactly.

## Sample: 10 in-scope (>=1 per slug where possible) + 5 out-of-scope

### In-scope

```text
insecticides_20260331.pdf p18 row3
  raw_crop: 'Cotton'   slug: cotton

fungicides_20260331.pdf p79 row3
  raw_crop: 'Soybean'   slug: soybean

insecticides_20260331.pdf p35 row17
  raw_crop: 'Red gram'   slug: tur

bio_insecticides_20260331.pdf p14 row4
  raw_crop: 'Chick pea'   slug: gram

fungicides_20260331.pdf p21 row5
  raw_crop: 'Onion'   slug: onion

insecticides_20260331.pdf p43 row12
  raw_crop: 'Tomato'   slug: tomato

fungicides_20260331.pdf p59 row8
  raw_crop: 'Grape'   slug: grape

fungicides_20260331.pdf p25 row1
  raw_crop: 'Pomegranate'   slug: pomegranate

insecticides_20260331.pdf p50 row2
  raw_crop: 'Grapes'   slug: grape

fungicides_20260331.pdf p41 row18
  raw_crop: 'Tomato'   slug: tomato

```

### Out-of-scope

```text
insecticides_20260331.pdf p8 row2
  raw_crop: 'Chilli'

insecticides_20260331.pdf p20 row0
  raw_crop: 'Okra'

insecticides_20260331.pdf p14 row8
  raw_crop: 'Groundnut'

fungicides_20260331.pdf p7 row12
  raw_crop: 'Cauliflower'

insecticides_20260331.pdf p50 row16
  raw_crop: 'Tea'

```
