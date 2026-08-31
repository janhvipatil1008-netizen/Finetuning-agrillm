# Phase 5, Step B — formulation unit resolution report

NEEDS_UNIT rows going in: **545**
Resolved via resolve_formulation_unit: **532**
Still NEEDS_UNIT (no confident code found): **13**

## Per-slug dose_formulation coverage (after resolution)

| slug | numeric | free_text | empty | unparseable | n |
|---|---|---|---|---|---|
| cotton | 95.5% | 0.0% | 1.4% | 3.2% | 222 |
| soybean | 93.1% | 1.4% | 4.2% | 1.4% | 72 |
| tur | 97.7% | 0.0% | 0.0% | 2.3% | 44 |
| gram | 88.5% | 0.0% | 9.6% | 1.9% | 52 |
| onion | 96.8% | 0.0% | 0.0% | 3.2% | 31 |
| tomato | 86.3% | 4.6% | 6.9% | 2.3% | 175 |
| grape | 96.6% | 0.0% | 1.7% | 1.7% | 119 |
| pomegranate | 96.0% | 4.0% | 0.0% | 0.0% | 25 |

## Trainable rows

Rows where BOTH dose_ai and dose_formulation parsed to numeric or free_text (not empty, not unparseable) -- the real size of the answer space.

- Trainable rows: **627** / 740 (84.7%)

| slug | trainable | n |
|---|---|---|
| cotton | 200 (90.1%) | 222 |
| soybean | 67 (93.1%) | 72 |
| tur | 30 (68.2%) | 44 |
| gram | 30 (57.7%) | 52 |
| onion | 29 (93.5%) | 31 |
| tomato | 135 (77.1%) | 175 |
| grape | 111 (93.3%) | 119 |
| pomegranate | 25 (100.0%) | 25 |

## Remaining NEEDS_UNIT rows

13 rows.

| crop_slug | active_ingredient | dose_formulation_raw |
|---|---|---|
| tomato | `Dazomet` | `30 –40` |
| cotton | `Fenvalerate 02%Conc.` | `4000 – 5000` |
| cotton | `Azadirachtin 05.00% w/w Min. Neem Extract Concentrates` | `375.0` |
| tomato | `Azadirachtin 05.00% w/w Min. Neem Extract Concentrates` | `200.0` |
| tomato | `Bacillus thuringiensis var. galleriae 1593 M serotype H 59 5b, 1.3% flowable concentrate Potency 1500  IU/mg` | `1.0-1.5` |
| cotton | `(Okra)` | `2.0-2.5` |
| cotton | `Bacillus thuringiensis var. kurstaki` | `750-1000` |
| cotton | `Bacillus thuringiensis var. kurstaki, serotype H-39, 3B, Strain Z-52` | `500-750` |
| gram | `Bacillus thuringiensis var. kurstaki, serotype H-39, 3B, Strain Z-52` | `500-750` |
| tur | `Bacillus thuringiensis var. kurstaki, serotype H-39, 3B, Strain Z-52` | `500-750` |
| soybean | `Bacillus thuringiensis var. kurstaki, serotype H-39, 3B, Strain Z-52` | `500-750` |
| cotton | `Bacillus thuringiensis var. kurstaki Strain HD-1, serotype 3a, 3b, 3.5% ES for Import &repack.  Potency17600 IU/mg` | `750-1000` |
| cotton | `PB Rope L` | `9875` |

## Sample of newly-resolved rows

| crop_slug | active_ingredient | dose_formulation_raw | resolved_unit | value_min | value_max |
|---|---|---|---|---|---|
| tomato | `Abamectin 01.90 % EC` | `450 - 600` | ml | 450.0 | 600.0 |
| cotton | `Chlorpyrifos 20% EC` | `3750` | ml | 3750.0 | None |
| cotton | `Fenpropathrin 10% EC` | `750 –1000` | ml | 750.0 | 1000.0 |
| tur | `Isocycloseram 9.2% W/W Dc (10% W/V) DC` | `500-600` | ml | 500.0 | 600.0 |
| soybean | `Spinetoram 11.70 %SC` | `450` | ml | 450.0 | None |
| tomato | `Chlorantraniliprole 4.3% +Abamectin 1.7% SC` | `500` | ml | 500.0 | None |
| soybean | `Lufenuron 4% + Emamectin Benzoate 1.5% EC` | `625` | ml | 625.0 | None |
| tomato | `Picarbutrazox 9.53% w/w SC` | `1000-1250` | ml | 1000.0 | 1250.0 |
| grape | `Copper Sulphate 47.15% + Mancozeb 30% WDG` | `5000` | g | 5000.0 | None |
| cotton | `Sedaxane 2.5% w/v + Fludioxonil 2.5% w/v + Thiamethoxam 26.25% w/v FS` | `4.0` | ml | 4.0 | None |
