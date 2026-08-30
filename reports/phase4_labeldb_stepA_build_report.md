# Phase 4 (label_db) Step A — build report

Wrote data/final/label_db.csv, label_db.parquet (740 rows) and exclusion_log.csv (2963 rows).

## Totals

- Rows in (every row of the 4 raw CSVs, all row kinds): **3703**
- Rows kept in label_db: **740**
- Rows excluded: **2963**

### Exclusion breakdown

| reason | rows |
|---|---|
| crop_out_of_scope | 1707 |
| crop_blank | 1229 |
| crop_not_a_crop_cell | 15 |
| no_registered_header | 6 |
| phi_defect | 5 |
| structural_filler | 1 |

## Per-slug row counts (label_db)

| slug | rows |
|---|---|
| cotton | 222 |
| soybean | 72 |
| tur | 44 |
| gram | 52 |
| onion | 31 |
| tomato | 175 |
| grape | 119 |
| pomegranate | 25 |
| **total** | **740** |

## Per-slug dose coverage

### dose_ai

| slug | numeric | free_text | empty | unparseable | n |
|---|---|---|---|---|---|
| cotton | 68.5% | 23.0% | 8.1% | 0.5% | 222 |
| soybean | 75.0% | 22.2% | 2.8% | 0.0% | 72 |
| tur | 61.4% | 9.1% | 29.5% | 0.0% | 44 |
| gram | 44.2% | 19.2% | 36.5% | 0.0% | 52 |
| onion | 67.7% | 29.0% | 3.2% | 0.0% | 31 |
| tomato | 52.0% | 26.3% | 19.4% | 2.3% | 175 |
| grape | 72.3% | 22.7% | 3.4% | 1.7% | 119 |
| pomegranate | 84.0% | 16.0% | 0.0% | 0.0% | 25 |

### dose_formulation

| slug | numeric | free_text | empty | unparseable | n |
|---|---|---|---|---|---|
| cotton | 5.9% | 0.0% | 1.4% | 92.8% | 222 |
| soybean | 16.7% | 1.4% | 4.2% | 77.8% | 72 |
| tur | 18.2% | 0.0% | 0.0% | 81.8% | 44 |
| gram | 17.3% | 0.0% | 9.6% | 73.1% | 52 |
| onion | 19.4% | 0.0% | 0.0% | 80.6% | 31 |
| tomato | 25.1% | 4.6% | 6.9% | 63.4% | 175 |
| grape | 42.9% | 0.0% | 1.7% | 55.5% | 119 |
| pomegranate | 52.0% | 4.0% | 0.0% | 44.0% | 25 |

## Per-slug PHI coverage

| slug | resolved | not_applicable | raised | n |
|---|---|---|---|---|
| cotton | 75.2% | 24.8% | 0.0% | 222 |
| soybean | 69.4% | 30.6% | 0.0% | 72 |
| tur | 68.2% | 31.8% | 0.0% | 44 |
| gram | 42.3% | 57.7% | 0.0% | 52 |
| onion | 80.6% | 19.4% | 0.0% | 31 |
| tomato | 68.6% | 31.4% | 0.0% | 175 |
| grape | 85.7% | 14.3% | 0.0% | 119 |
| pomegranate | 96.0% | 4.0% | 0.0% | 25 |

## Nemastin exclusion — full list

6 rows.

| source_file | page | row | crop_raw | pest_or_disease |
|---|---|---|---|---|
| bio_insecticides_20260331.pdf | 10 | 9 | `Gerbera` | `Meloidogyne incognita` |
| bio_insecticides_20260331.pdf | 10 | 10 | `Carnations` | `Meloidogyne incognita` |
| bio_insecticides_20260331.pdf | 10 | 11 | `Tuberose` | `Meloidogyne incognita` |
| bio_insecticides_20260331.pdf | 10 | 12 | `Banana` | `Meloidogyne incognita` |
| bio_insecticides_20260331.pdf | 10 | 13 | `Acid lime` | `Citrus nematodes (Tylenchulus  semipenetrans)` |
| bio_insecticides_20260331.pdf | 11 | 1 | `Papaya` | `Meloidogyne spp.  Reniform Nematodes  (Rotelenchulus  reniformis)` |

## phi_defect exclusion — full list

5 rows.

| source_file | page | row | crop_slug | phi_raw |
|---|---|---|---|---|
| insecticides_20260331.pdf | 60 | 1 | soybean | `1 7` |
| insecticides_20260331.pdf | 60 | 2 | cotton | `2 1` |
| fungicides_20260331.pdf | 17 | 0 | grape | `February  followed by  2 dusting in  summer` |
| bio_fungicides_20260331.pdf | 3 | 2 | tomato | `500 lit per ha` |
| bio_fungicides_20260331.pdf | 14 | 5 | tomato | `Dilution in  water- 500  liter/ha` |

## 20-row sample from label_db

```text
fungicides_20260331.pdf p13 | soybean | ai='Hexaconazole 5% EC'
    pest: 'Rust'
    dose_ai: '0.005%  (5g/100  lit)' -> numeric (0.005 %)
    phi: '30' -> resolved (30)

fungicides_20260331.pdf p62 | soybean | ai='Fluxapyroxad 167 g/l + Pyraclostrobin 33'
    pest: 'Frog eye leaf spot'
    dose_ai: '150' -> numeric (150.0 g)
    phi: '45' -> resolved (45)

insecticides_20260331.pdf p78 | tomato | ai='Flonicamid 11.7% + Diafenthiuron 36% WG'
    pest: 'White fly, Aphids,  Jassids'
    dose_ai: '73.13+225' -> free_text (nan )
    phi: '5' -> resolved (5)

insecticides_20260331.pdf p27 | gram | ai='Emamectin benzoate 01.90%EC'
    pest: 'Pod borer'
    dose_ai: '07.13' -> numeric (7.13 g)
    phi: '14' -> resolved (14)

insecticides_20260331.pdf p42 | tomato | ai='Novaluron 10 % EC'
    pest: 'Fruit borer'
    dose_ai: '75' -> numeric (75.0 g)
    phi: '1-3' -> resolved (3)

fungicides_20260331.pdf p8 | grape | ai='Copper oxychloride 50% WP'
    pest: 'Downy mildew'
    dose_ai: '1.25' -> numeric (1.25 g)
    phi: '-' -> not_applicable (<NA>)

fungicides_20260331.pdf p69 | cotton | ai='Metiram 55% + Pyraclostrobin 5% WG'
    pest: 'Alternaria leaf spot'
    dose_ai: '900-1050' -> numeric (900.0 g)
    phi: '45' -> resolved (45)

fungicides_20260331.pdf p19 | grape | ai='Meptyl Dinocap 35.7% EC'
    pest: 'Powdery  mildew'
    dose_ai: '108-120' -> numeric (108.0 g)
    phi: '30' -> resolved (30)

fungicides_20260331.pdf p44 | grape | ai='Ametoctradin 27%+ Dimethomorph 20.27% w/'
    pest: 'Downey mildew'
    dose_ai: '420-525' -> numeric (420.0 g)
    phi: '34' -> resolved (34)

insecticides_20260331.pdf p16 | tomato | ai='Chlorfluazuron 05.40%EC'
    pest: 'Fruit Borer  (Helicoverpa   amigera), Tobacco  Cat'
    dose_ai: '100' -> numeric (100.0 g)
    phi: '3' -> resolved (3)

insecticides_20260331.pdf p50 | tomato | ai='Tebufenpyrad 20% WP'
    pest: 'Red Spider Mites'
    dose_ai: '75-100' -> numeric (75.0 g)
    phi: '20' -> resolved (20)

insecticides_20260331.pdf p53 | soybean | ai='Thiamethoxam 30%WS (Seed treatment)'
    pest: 'Stem fly Girdle beetle,  Whitefly'
    dose_ai: '1.8 g ai/kg seed' -> numeric (1.8 g)
    phi: '' -> not_applicable (<NA>)

insecticides_20260331.pdf p43 | cotton | ai='Permethrin 25%EC'
    pest: 'Bollworms'
    dose_ai: '100 –125' -> numeric (100.0 g)
    phi: '-' -> not_applicable (<NA>)

insecticides_20260331.pdf p62 | cotton | ai='Buprofezin 22.0%+ Fipronil 3%SC'
    pest: 'Mealy bugs &  Thrips'
    dose_ai: '220+30' -> free_text (nan )
    phi: '17' -> resolved (17)

fungicides_20260331.pdf p59 | grape | ai='CF-1020 (Fluopicolide 10% + Dimethomorph'
    pest: 'Downy mildew  (Plasmopara viticola),  Anthracnose '
    dose_ai: '(99.9+200)' -> free_text (nan )
    phi: '34' -> resolved (34)

insecticides_20260331.pdf p69 | gram | ai='Indoxacarb 16% (12% S-Isomer + 4% R-Isom'
    pest: 'Pod borer  (Helicoverpa  armigera)'
    dose_ai: '48 + 48' -> free_text (nan )
    phi: '26 days' -> resolved (26)

insecticides_20260331.pdf p47 | tur | ai='Quinalphos 25 %EC'
    pest: 'Podborer, Podfly'
    dose_ai: '350' -> numeric (350.0 g)
    phi: '30' -> resolved (30)

insecticides_20260331.pdf p45 | cotton | ai='Pyridaben 20%w/w WP'
    pest: 'Whitefly'
    dose_ai: '100' -> numeric (100.0 g)
    phi: '28' -> resolved (28)

insecticides_20260331.pdf p30 | cotton | ai='Fenvalerate 02%Conc.'
    pest: 'Spotted & Spiny, Pink  American, Egyptian bollworm'
    dose_ai: '80 –100' -> numeric (80.0 g)
    phi: '-' -> not_applicable (<NA>)

insecticides_20260331.pdf p26 | tomato | ai='DIMPROPYRIDAZ 120 g/l SL'
    pest: 'White fly, Jassids, Aphids'
    dose_ai: '108 - 120' -> numeric (108.0 g)
    phi: '3' -> resolved (3)

```
