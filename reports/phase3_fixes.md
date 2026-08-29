# Phase 3 — Header Fragments, Method Column, Type Guard

Targeted Step 2 re-run. All CSVs in `data/interim/` regenerated from the source PDFs; `tools/phase3_step2_extract.py` is the committed record of how.

## 1. Header-fragment sweep

### 1.1 What the sweep found (before any change)

Sweeping the previous run's 3762 rows for a crop or pest cell exactly matching a header label (case- and whitespace-insensitive) returned **19 hits, not the 2 Metarhizium rows** the defect was reported from. Every one is a two-tier column header extracted as data — including the MAIN table header on page 2 of all four files:

```text
insecticides p2  r1  crop='Crop'         :: Crop || Common Name of the pest || Dosage/ha || Waiting Period (days)
insecticides p2  r2  crop='a.i (gm)'     :: a.i (gm) || Formulation (gm/ml) || Dilution in Water (Liter)
insecticides p7  r1  pest='Method of application'
insecticides p50 r7,r8   crop='Crop'
insecticides p52 r18     crop='Name of crop'
insecticides p55 r17     crop='Crop'
fungicides   p2  r1,r2   crop='Crop' / 'a.    i. (g)'
fungicides   p43 r1      crop='Crop'      (assignment_kind was ordinal_6 — a full 6-segment header)
bio_insect   p2  r1,r2   crop='Name of crop'
bio_insect   p9  r10,r11 crop='Crop', pest='Common name of the target organism'   <- the reported case
bio_insect   p11 r3,r4   crop='Crop'
bio_fungi    p2  r1,r2   crop='Name of Crop'
```

### 1.2 Detector: boldness, not vocabulary

A label-vocabulary detector was built first and **rejected on measurement**. It both missed real headers (insecticides p92 r2, p91 r12/r13, p102 r14) and false-positived on real data — insecticides p99 r8/r9, `"Mosquitoes larvae | Clean surface water | 25-50 g a.i./ha"`, is a genuine public-health dose row that a vocabulary rule reads as a header because every word in it is header-ish.

The reliable signal is typographic: CIB&RC sets column labels in bold and data rows in regular. The whole-corpus bold-fraction histogram is sharply bimodal, which is what makes it safe to threshold:

| bold fraction | rows |
|---|---|
| 0.0 | 2671 |
| 0.1–0.8 | 137 |
| 0.9–1.0 | 957 |

Rows in the middle band were inspected: all are data rows whose y-band overlaps a bold chemical name above them, none is a header. The rule is **bold ≥ 0.9 AND ≥2 content segments** — the segment-count clause is what separates a column header from a chemical-name header (also bold, but always a single segment).

**89 rows** now classify as `column_header`. All 89 were reviewed individually; there are no false positives. They are kept in the raw CSV with every semantic column blank and `is_column_header=True` — the same treatment `chemical_header` rows already get, so nothing is silently deleted and the hard assertion still balances, but Phase 4 can exclude them with one predicate.

They also no longer advance the crop/chemical forward-fill. A row reading `crop='Crop'` was previously eligible to be inherited by every following blank-crop row.

Residual check after re-extraction: **0 rows** still carry a header label in crop or pest.

## 2. `method` column

`method` added to the raw CSV schema. **104 rows** now carry method text there instead of in `dilution_water`.

Per file:

| file | rows with method |
|---|---|
| `insecticides_20260331.pdf` | 13 |
| `fungicides_20260331.pdf` | 6 |
| `bio_insecticides_20260331.pdf` | 31 |
| `bio_fungicides_20260331.pdf` | 54 |

The reported case, now correct:

```text
bio_insecticides p10, Gerbera / Meloidogyne incognita
  crop            : Gerbera
  pest_or_disease : Meloidogyne incognita
  dilution_water  : ''   <- was the method sentence
  method          : Apply the Nemastin @ 50 gm/sq.m at the time of planting
```

## 3. Type guard on `fallback_subset`

Applied **after** geometric assignment, to the result only: a segment longer than 40 chars with no leading quantity is not an acceptable value for `dose_ai`, `dose_formulation` or `dilution_water`. Geometry still chooses the column; the guard only refuses an impossible outcome.

Two calibration details, both found by checking what the guard did rather than assuming:

- **Leading-quantity reprieve.** insecticides p87's `"108 (Spiropidion 60 + Acetamiprid 48) – 135 (Spiropidion 75 + Acetamiprid 60)"` is 77 chars but starts with a digit — a real compound dose, correctly exempt.
- **Ordinals are not quantities.** insecticides p55's `"(1st spray when insect pest reaches ETL. Repeat one spray at 10-15 days interval…)"` is 110 chars of prose that a bare leading-digit test waved through, because `"(1"` satisfied it. Leading ordinals (`1st`, `2nd`…) are excluded from the reprieve.

**Guard fired on 115 rows: 104 rerouted to `method`, 11 quarantined** as `cols_unresolved`.

Which of the two outcomes a row gets is decided by whether its chemical block is free-text-method-shaped — i.e. whether a "Method of application" column exists there to receive the text. That test is **≥50% of the block's data rows have prose landing in a dose/dilution column**. Two narrower definitions were tried and measured first:

| block-shape test | consequence | verdict |
|---|---|---|
| every data row has `dose_ai` AND `dose_formulation` blank | quarantined 39 of bio_fungicides' 147 rows whose method column plainly exists — e.g. `"- \|\| 2.5 kg per ha (05 g/litre water) \|\| Spray Pseudomonas fluorescens 1.75% WP uniformly on the crop. \|\| 500 lit per ha"` carries a real dose AND real method text | rejected |
| ≥50% of rows have prose in ANY segment | counted long pest names (`"Mealy bugs (Phenococcus solenopsis, Thrips…"`) as evidence of a method column; inflated 48 blocks → 277 | rejected |
| ≥50% of rows have prose in a **guarded** column | 48 blocks | **used** |

### 3.1 Disposition of the 122–133 sentence-valued rows

Measured with the diagnosis report's own prose heuristic (≥4 words plus an instructional verb), which is a different test from the guard's (length plus leading quantity) — so these are overlapping populations, not the same set counted twice:

| outcome | rows |
|---|---|
| prose rerouted into `method` | 97 |
| prose still in a dose/dilution column | 17 |
| quarantined by the guard | 11 |

The 17 that remain are **below the 40-char threshold the instruction specified** — `"This is used as seed dresser"` (28), `"are dried in shade before sowing"` (32), `"after 40-45 days of transplantation."` (36). They are short enough that the type guard as specified does not reach them. Raising the threshold would catch them and would also start catching real dose expressions; that is a judgement call I have left to you rather than tightening unilaterally.

## 4. Row counts, new vs old

| file | raw (old) | raw (new) | quarantine (old) | quarantine (new) |
|---|---|---|---|---|
| `insecticides_20260331.pdf` | 2048 | 2042 | 3 | 9 |
| `fungicides_20260331.pdf` | 1273 | 1269 | 1 | 5 |
| `bio_insecticides_20260331.pdf` | 294 | 294 | 0 | 0 |
| `bio_fungicides_20260331.pdf` | 147 | 147 | 0 | 0 |
| **total** | **3762** | **3752** | **4** | **14** |

**HARD ASSERTION: 3752 raw + 14 quarantine = 3766 = total source rows. PASSED** (the script exits non-zero on mismatch).

The 10-row net drop in raw is the guard's 11 quarantines minus one row that moved the other way: insecticides p27 r15 was previously quarantined `cols_unresolved` as a 7-segment fumigation row, and is now correctly identified as that table's bold column header.

### Quarantine by reason code

| reason_code | old | new |
|---|---|---|
| `cols_unresolved` | 3 | 13 |
| `footnote_unresolved` | 0 | 0 |
| `truncated_cell` | 1 | 1 |
| `section_ambiguous` | 0 | 0 |

All 14 were reviewed: the fumigation tables (p4/p5/p27, 7-field schema), five full-width spray-timing notes on insecticides p54, fungicides p16/p17 (`"The liquid is used at 1% in conventional sprayers"` in a dose column, block not method-shaped), fungicides p71/p72 seed-treatment prose, and the known p38 truncated cell.

### assignment_kind distribution

| kind | rows |
|---|---|
| `ordinal_6` | 2134 |
| `chemical_header` | 921 |
| `fallback_subset` | 607 |
| `column_header` | 89 |
| `blank` | 1 |

## 5. `phi_cell_present`

Unchanged in meaning: True=3297, False=24 (insecticides p7 and bio_insecticides p10 only — the two genuinely ABSENT tables), blank=431 (non-crop-advisory).

One correctness follow-on: column-header rows are now excluded when deciding whether a table has PHI content. A bold `"Waiting period (days)"` LABEL in the PHI band is not evidence that any row carries a PHI VALUE, and counting it would have masked exactly the ABSENT vs PRESENT-AND-EMPTY distinction this field exists to preserve.

## 6. verify_sample

25 fresh rows, weighted as requested: **16 `fallback_subset`** (the class the guard acts on) and **8 carrying method text** (the bio free-text blocks), spanning all four files, and still including the page-boundary and section-boundary rows. The Gerbera row is in it.

> **`data/interim/verify_sample.csv` was locked during the run** (open in another program). The fresh sample was written to **`data/interim/verify_sample.locked.csv`** instead — the file ending `.csv` at the top level is the STALE one from the previous run. Close it and re-run `python tools/phase3_step2_extract.py` to regenerate in place, or just read the `.locked.csv`.

## 7. Not done

No normalisation, no dose parsing, no label_db. `waiting_period_phi` still holds raw cell text; `parse_phi` is not called. `schema.py` untouched.

