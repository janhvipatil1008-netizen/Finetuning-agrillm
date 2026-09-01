# Phase 6, Step C — the 27 ambiguous candidate sets, classified

Investigation only. **label_db is unedited.**

The 27 ambiguous sets counted by the verifier are **27 (crop, pest, a.i.,
formulation) triple-keys reaching 17 distinct row groups** — several groups are
reached through more than one pest canonical (a cell naming "Jassids, Aphids,
Thrips, Whitefly" resolves to four).

Evidence order: label_db → `data/interim/*_raw.csv` (`raw_row_text`, the
extracted PDF line) → the source PDF page itself. The raw text settled most;
five PDF pages were opened for the rest.

---

## Verdict

| class | groups | rows | response |
|---|---|---|---|
| **(a)** genuine duplicate extraction / parse defect | **1** | 2 | parser fix |
| **(b)** distinct registrations the key fails to separate | **11** | 26 | key fix |
| **(c)** real CIB&RC inconsistency | **5** | 11 | permanent exclusion |

**No group is the Phase 3 phantom-continuation pattern.** Three span a page
break and were checked against the PDF individually; in every case the rows on
the second page are genuine separate table rows under a continuing header, not
a wrapped cell. Phase 3's merge did not miss these.

---

## (b) — distinct registrations, 11 groups, 26 rows

Two sub-causes, both fixable by widening the lookup key.

### b1 · Application method is a registration-distinguishing attribute (3 groups)

`crop_mapper` recognises the method qualifier and deliberately strips it
(`test_method_qualifier_is_not_multi_crop`). But CIB&RC registers foliar and
soil-drench use of the same product as **separate claims with different doses
and different waiting periods**.

| # | crop | pest | a.i. / form. | rows | disagreement | source |
|---|---|---|---|---|---|---|
| 3, 4 | cotton | Jassid, Whitefly | Clothianidin 50% WDG | 61, 62, 63 | 30–40 g PHI 20 · 40–50 g PHI 20 · **200–250 g PHI 76** | insecticides p18 r14/r15/r16 |
| 14 | tomato | Whitefly | Thiamethoxam 25% WG | 261, 262 | 200 g · 400 g | insecticides p54 r7/r16 |
| 11 | grape | Thrips | Thiamethoxam 25% WG | 263, 264 | 400 g PHI 10 · 100 g PHI 15 | insecticides p54 r19/r21 |

Evidence — the qualifier survives into the extracted crop cell and is then
discarded:

```
p18 r14  'Cotton                    || Jassids || 15–20 || 30–40   || 500  || 20'
p18 r16  'Cotton (Soil  drench)     || Jassids, Aphids, Thrips, Whitefly
                                    || 100–125 || 200–250 || 1000 || 76'
p54 r7   'Tomato  Foliar  application || Whitefly || 50 || 200 || 500 || 05'
p54 r16  'Tomato   Soil drench       || White flies || 100 || 400 || 500 || 05'
```

A 200–250 g soil drench with a **76-day** interval and a 30–40 g foliar spray
with a **20-day** interval are different treatments. Collapsing them is the
most consequential defect found: it is the one case where an ambiguity could
have handed a farmer a 6× dose.

**Fix:** carry the application method as its own column and add it to the
lookup key. `crop_mapper` already parses it.

### b2 · Strain designation distinguishes bio-pesticide registrations (8 groups)

`normalise_ai` cuts at the first digit and `formulation_key` reads only code +
strength, so every strain of a bio-pesticide collapses to one key.
`formulation_resolver` already *cuts* strain tails deliberately (its Hazard 2)
— correct there, but it means the strain never enters any key.

| # | crop | pest | product | rows | distinguishing feature |
|---|---|---|---|---|---|
| 17 | tur | Helicoverpa | NPV 2.0% AS | 696, 698, 699, 701, 704 | strains **GBS/HNPV-01, NBRI-8821, IBH-17268, BIL/HV-9, IBL-17268** |
| 6 | gram | Helicoverpa | NPV 2.0% AS | 697, 700, 702, 705 | same five strains; 705 is 500–1000, the rest 250–500 |
| 2 | cotton | Bollworm complex | Beauveria bassiana 1.15% WP | 675, 676, 683 | 400 · 2000 · CFU-qualified variant |
| 7 | gram | Wilt | Trichoderma viride 1.0% WP | 733, 737 | Strain T-14 (Indore Biotech) 5 g/kg · unqualified 9 g/kg |
| 15 | tomato | Wilt | Pseudomonas fluorescens 1.0% WP | 720, 723 | IPL/PS-01 MTCC5727 · IIHR-PF-2 ITCCB0034 |
| 9 | grape | Anthracnose | Azoxystrobin 8.3% + Mancozeb 66.7% WG | 516, 517 | **alternate rate expression**, see below |
| 12 | pomegranate | Anthracnose | Metiram 70% WG | 441, 445 | **alternate rate expression**, see below |

The last two are a distinct sub-case worth separating: CIB&RC states **one
claim on two bases**, and the parser reads them correctly as two rows.

```
p46 r9   Grape | Powdery/Downy/Anthracnose | 124.5+1000 | 1500   | 500-750 | 21
p46 r10  Grape | Powdery/Downy/Anthracnose | 0.23%      | 0.30%  | 750-1000| 21
```

Same PHI, same pest, same product — an area rate and a concentration for the
same registration. Verified against the PDF (fungicides p46). Metiram p21 is
the same shape: 200 g/ha versus 150–200 per 100 L, parsed as `per_ha` and
`per_litre_water` respectively. Both are correct; they are not competing
values and should never have been compared.

**Fix:** add strain/accession to the a.i. key; treat rows that differ only in
`dose_*_basis` with equal PHI as alternate expressions of one claim, not as
disagreeing candidates.

---

## (c) — real CIB&RC inconsistency, 5 groups, 11 rows

The document itself states two values. Extraction is faithful; no fix is
possible at our end.

| # | crop | pest | product | rows | the contradiction | PDF |
|---|---|---|---|---|---|---|
| 1 | cotton | Aphid/Whitefly/Thrips/Jassid | Diafenthiuron 50% WP | 87, 88 | **300 g a.i./600 g, PHI 21** vs **239 g a.i./500 g, PHI 30** | insecticides p24 — two Cotton rows under one header, no sub-heading |
| 16 | tur | Helicoverpa | Chlorantraniliprole 18.50% SC | 35, 38 | **PHI 29** vs **PHI 22**, identical 30/150 dose | insecticides p12 "Pigeon pea" and p13 "Red Gram" — the same crop under two synonyms |
| 10 | grape | Powdery mildew | Pyriofenone 18% w/v SC | 464, 468 | identical 108/600/750, **PHI 7** vs **PHI 5** | fungicides p26 and p34 |
| 5 | cotton | Whitefly | Pyriproxyfen 10% EC | 202, 203 | 1000 ml PHI 31 vs 500–700 ml PHI 50 | insecticides p45 r14/r15 — both arithmetically consistent with 10% |
| 13 | tomato | Helicoverpa | Flubendiamide 20% WG | 131, 132 | 48 a.i./100 form vs 50 a.i./250 form, both PHI 05 | insecticides p32–33 |

### The Chlorantraniliprole case is the clearest

PDF p12 and p13, under a single header `Chlorantraniliprole 18.50% SC`:

```
p12   Pigeon pea | Gram Pod borer and Pod Fly                    | 30 | 150 | 500–750 | 29
p13   Red Gram   | Gram Pod borer (Helicoverpa armigera), Pod fly| 30 | 150 | 500     | 22
```

Pigeon pea and Red Gram are the **same crop**. `crop_mapper` resolves both to
`tur`, correctly — and in doing so surfaces a contradiction the document
carries. Same product, same pest, same dose, **two different waiting
periods**. This is not a page-break artifact: p13 continues the table normally
(Green gram precedes Red Gram) and both are ordinary rows.

### Flubendiamide 20% WG carries an arithmetically impossible row

A strength-consistency check — does `dose_ai == dose_formulation × stated %`?
— isolates which of the two is wrong:

| row | a.i. | formulation | strength | expected a.i. | |
|---|---|---|---|---|---|
| 131 | 48 | 100 | 20% | **20** | **mismatch** |
| 132 | 50 | 250 | 20% | 50 | ok |

Row 131's pairing is impossible for a 20% product, and `48 | 100 | 375–500 |
05` appears **verbatim** under `Flubendiamide 39.35% w/w SC` further down the
same PDF page. A row from the 39.35% SC table is duplicated into the 20% WG
table in the source document. We reproduce the error faithfully.

Applying that check to all disagreeing rows flagged only this one (the
Chlorantraniliprole 30-vs-27.8 flag is CIB&RC's own rounding, not a defect).
**Worth adding as a general label_db quality check** — it is cheap, it needs
no external source, and it catches header mis-attribution across the corpus.

---

## (a) — parse defect, 1 group, 2 rows

| # | crop | pest | product | rows | defect |
|---|---|---|---|---|---|
| 8 | grape | Anthracnose | Thiophanate Methyl 70% WP | 487, 488 | `COLUMN_COLLAPSE` |

```
p39 r0  'Grapes || Powdery mildew, Anthracnose, Rust
         || 500  500  500 || 715  715  715 || 750-1000  750-1000  750-1000 || 7'
p39 r3  'Grapes || Powdery mildew, Downy mildew and Anthracnose
         || 500 || 715 || 750- 1000 L/ha || 7'
```

Row 487 covers three pests and the PDF repeats each value once per pest; the
extractor merged the three sub-cells into one string, which `dose_parser`
correctly refused as `COLUMN_COLLAPSE`. The value is unambiguously 715 g/ha,
PHI 7 — identical to row 488. **Both rows are the same claim**; the
disagreement is entirely an artifact.

**Fix:** teach the extractor to split a repeated-value cell (`N N N` where all
three are equal) into one value, or drop 487 as a duplicate of 488.

---

## Recommended order

1. **b1, application method** — 3 groups, and the only one with a 6× dose gap
   (Clothianidin 30–40 g foliar vs 200–250 g soil drench). `crop_mapper`
   already parses the qualifier; it needs a column and a place in the key.
2. **b2, strain designation** — 8 groups, 26 rows, all bio-pesticides. Recovers
   the most rows.
3. **(a) Thiophanate** — 1 group, contained.
4. **(c), 5 groups / 11 rows** — permanent exclusions. Nothing to fix; record
   them so they are not re-investigated.

Fixing (a) and (b) would return **12 of the 17 groups** to gradeable and
recover most of the 22 trainable rows currently ungradeable. The remaining 5
(c) groups are a genuine ceiling.

---

## Regression guard

`tests/test_verify.py` now pins the populations:

- `test_multi_row_sets_that_agree_today_still_agree` — 8 triple-keys over 5 row
  groups currently agree on PHI and dose and grade normally. If a rebuild makes
  one disagree it silently becomes ambiguous, and this fails first. It also
  pins the 27-over-17 ambiguous count, so a change in either direction has to
  be explained.
- `test_agreeing_sets_are_not_reported_ambiguous` — the agreeing sets grade
  without exclusion, so an over-eager ambiguity check cannot shrink the
  training set unnoticed. It refuses to pass vacuously (all five carry no PHI,
  which broke the first version of this test).
- `test_the_investigated_ambiguous_groups_are_still_present` — the four row
  groups classified above still exist, so a classification cannot lapse
  silently.

---

## Addendum — 2 strength-consistency contradictions added

`tools/phase6_stepD_strength_check.py` (does `dose_ai == dose_formulation x
stated_strength_percent`?) found 3 SOLID-formulation rows where the pair is
arithmetically impossible — for a solid, `g_a.i. = g_product x %` is exact, so
a failure means the row's own two dose columns disagree about what product
they describe. One of the three was the Flubendiamide 20% WG defect already
in this report's (c) table. The other two are genuinely new findings, not
present in the 27-set ambiguity sweep above because each is a **single row**
with no sibling to disagree with — the internal a.i./formulation
inconsistency is the defect, not a clash between two rows.

Added to `data/final/known_contradictions.csv` with `reason=strength_mismatch`:

| crop | product | source | a.i. stated | implies | header says | ratio |
|---|---|---|---|---|---|---|
| grape | Copper Hydroxide 53.8% DF | fungicides p8 r25 | 525 g / 1500 g | ~35% | 53.8% | 0.65 |
| cotton | Pyrifluinazon 20% WG | insecticides p45 r11 | 100 g / 375 g | ~27% | 20% | 1.33 |

Same standard as class (c): the document (or the row's own internal pairing)
is inconsistent, extraction is faithful, and there is nothing to parse-fix.
Excluded by the verifier the same way — scoped to the candidates a
recommendation resolves to, never the whole (crop, pest) pair.

`known_contradictions.csv` is now **12 rows in 7 groups** (5 two-row
disagreement groups + 2 single-row strength-mismatch rows). Gradeable
trainable rows (dose-parseable, minus documented contradictions): **616**
(628 trainable − 12 contradicted).

The 3 liquid-formulation outliers the same tool found are **not** added here:
a liquid needs a density term the check cannot supply, and "outside the
0.80–1.35 band" is a coarse filter, not proof of a data error. See the tool's
docstring for the per-row reasoning.
