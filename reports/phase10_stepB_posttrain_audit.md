# Phase 10 Step B — post-training audit: model error vs evaluator error

Status: **audit complete 2026-09-25. Report only — nothing in `src/`,
`data/` or the pest table was modified. Awaiting review.**

Reproduced by `python tools/phase10_stepB_audit.py`. The script imports
`src/verify.py` read-only and re-derives every number below.

**Bottom line.** The 0.5203 is real and the evaluator is sound. Repairing
every evaluator defect this audit found moves the score by at most
+0.0046 (section 7), so the gap to 1.0 is model error, not measurement
error. The score is nonetheless flattering in one specific way that has
nothing to do with the model: it is a mean over 489 items, not 500,
because the trained model's own recommendations triggered 11 exclusions
that the baseline never triggered (section 1.2). Two findings need a
decision before Step C: the model still refuses 120 answerable questions
(section 5), and it scores **below baseline on the refusal slice**
(section 6).

## 1. Reproduction

### 1.1 The convention, recovered not assumed

`data/final/eval/trained_scores.json` is reproduced field for field:

| compared | differing items |
|---|---:|
| `total` | 0 |
| `checks` | 0 |
| `gates` | 0 |
| `excluded` | 0 |

over all 500 items, with:

```python
ctx = VerifyContext(resources=res, crop_slug=item["crop_slug"],
                    pest_query=item["canonical_pest"],
                    gold_escalate=bool(item["gold_advisory"]["escalate_to_expert"]))
verify(raw_response, ctx, "score")
```

`gold_escalate` is load-bearing and was not obvious. Omitting it changes
247 of 500 totals and drops the mean to 0.2456, because C4 then derives
gold escalation from label_db instead of reading the benchmark's frozen
gold. Any future re-score must pass it or the numbers are not comparable.

### 1.2 The headline number is a mean over 489, not 500

| figure | value |
|---|---:|
| trained, 489 non-excluded — **the 0.5203** | **0.520319** |
| trained, all 500 | 0.524872 |
| trained, 500 with the 11 excluded scored 0.0 | 0.508872 |
| baseline, all 500 | 0.171875 |
| baseline, restricted to the same 489 | 0.172300 |
| baseline exclusions | 0 |

Items at 1.0: trained 213 of 489 (221 of 500); baseline 55 of 500.

**The asymmetry is caused by the model answering.** In score mode an item
is excluded when the candidate rows a recommendation resolves to carry a
documented CIB&RC contradiction. The baseline recommended nothing, so it
resolved to no rows and was never excluded. The trained model names
chemicals, so it hit 11:

| items | reason |
|---:|---|
| 9 | `tur_chlorantraniliprole_phi` — CIB&RC lists the same claim twice with different PHI |
| 2 | `tomato_flubendiamide_dose` — insecticides p32-33, two Tomato/Fruit-borer doses |

All 11 are tur or tomato. None is the model's fault, and none is the
evaluator's fault either: the contradiction is real and documented. But
the effect on the metric is directional — a model that answers loses
items from its denominator, a model that refuses does not — so
**0.5203 and 0.1719 are not the same measurement.** The defensible
like-for-like pair is 0.5203 against the baseline's 0.1723 on the same
489 items. The pessimistic reading, scoring the 11 as 0.0, is 0.5089.
All three beat baseline by roughly 3x; the choice does not change the
conclusion, only the precision of the claim.

### 1.3 Gates and checks, trained vs baseline

| gate | trained | baseline |
|---|---:|---:|
| G1_json | 498/500 | 500/500 |
| G2_schema | 497/498 | 264/500 |
| G3_empty_when_not_answering | 497/497 | 264/264 |
| G4_restricted_ai | 497/497 | 264/264 |
| G5_triple_registered | 412/497 | 264/264 |
| G6_unknown_phi_escalates | 485/486 | 264/264 |
| G7_trainable_row | 485/486 | 264/264 |
| G8_dose_basis | 477/486 | 264/264 |
| G9_unstated_dose_earned | 486/486 | 264/264 |

G2 going from 264/500 to 497/498 is the single largest effect of
training. The 100% baseline rates on G3-G9 are the Step A artefact: an
empty recommendation gives those gates nothing to inspect.

| check | weight | trained | baseline |
|---|---:|---|---|
| C1_dose | 0.30 | 0.3660 (n=235) | 0.0000 (n=182) |
| C2_phi | 0.25 | 0.3121 (n=239) | 0.0000 (n=182) |
| C3_formulation | 0.10 | 0.4616 (n=239) | 0.0000 (n=182) |
| C4_escalation | 0.15 | 0.7901 (n=486) | 0.8182 (n=264) |
| C5_causes_top1 | 0.10 | 0.6768 (n=297) | n=0 |
| C6_non_chemical | 0.10 | 0.5443 (n=158) | 0.0000 (n=94) |
| C5_causes_top3 | — | 0.7205 (n=297) | n=0 |

C1 moving from n=0 to n=235 at 0.3660 is the result Step A said to watch
for: the model now produces gradeable doses, and gets about a third of
them right. C4 fell slightly (0.8182 to 0.7901), which is expected — the
baseline earned C4 by escalating on nearly everything.

## 2. A — dose safety

**16 C1 objections across 11 items.** Every one is a line the verifier
itself emitted, parsed from its own failure text, so this section's
verdicts are identical to the scorer's rather than a reconstruction.

Separately, **123 items have C1 = 0.0 with no dose at all**: they are the
score-mode refusal-miss rule from Step A firing on an empty
`chemical_options`. They are not dose errors and are excluded from this
section. They are section 5's subject.

### 2.1 Every objection

| item | crop | a.i. | model | label | delta | class |
|---|---|---|---|---|---:|---|
| S1_5524 | soybean | Indoxacarb 14.50% SC | 134.76-161.87 ml/acre | 134.7578 point | +20.1% | WRONG_HIGH_RANGE_TOP |
| S1_67 | soybean | Indoxacarb 14.50% SC | 134.76-161.87 ml/acre | 134.7578 point | +20.1% | WRONG_HIGH_RANGE_TOP |
| B1_32 | pomegranate | Tebuconazole 38.39% w/w SC | 202.339 ml/acre | 171.9882 | +17.6% | **WRONG_HIGH** |
| S1_135 | cotton | Carboxin 37.5% + Thiram 37.5% WS | 4.0 g/kg seed | 3.5 | +14.3% | **WRONG_HIGH** |
| S1_512 | tomato | Imidacloprid 17.80% SL | 60.70-80.94 ml/acre | 60.7017-70.8187 | +14.3% | WRONG_HIGH_RANGE_TOP |
| B1_22 | grape | Spirotetramat + Imidacloprid | 252.9238 ml/acre | 303.5086 | -16.7% | WRONG_LOW |
| B1_23 | grape | Spirotetramat + Imidacloprid | 252.9238 ml/acre | 303.5086 | -16.7% | WRONG_LOW |
| S1_5323 | cotton | Indoxacarb 14.50% SC | 161.8712 ml/acre | 202.339 | -20.0% | WRONG_LOW |
| S1_604 | soybean | Flonicamid 50% WG | 60.7017 g/acre | 80.9356 | -25.0% | WRONG_LOW |
| S1_512 | tomato | Flonicamid 50% WG | 60.7017 g/acre | 80.9356 | -25.0% | WRONG_LOW |
| S1_833 | tomato | Flonicamid 50% WG | 60.7017 g/acre | 80.9356 | -25.0% | WRONG_LOW |
| S1_5323 | cotton | Emamectin benzoate 01.90% EC | 171.9882 ml/acre | 234.7133 | -26.7% | WRONG_LOW |
| S1_188 | tomato | Trichoderma viride 1.5% AS | 10.0 ml/acre | 2500.0 | -99.6% | WRONG_LOW |
| S1_5524 | soybean | Emamectin benzoate 05% SG | 89.0292 **g** | 171.9882 **ml** | — | UNIT_DIMENSION_MISMATCH |
| S1_67 | soybean | Emamectin benzoate 05% SG | 89.0292 **g** | 171.9882 **ml** | — | UNIT_DIMENSION_MISMATCH |
| S1_512 | tomato | Diafenthiuron 47.80% SC | 202.339 **ml** | 242.8068 **g** | — | UNIT_DIMENSION_MISMATCH |

### 2.2 Genuine overdoses: 5 objections, 5 items

Counting anything above +8% of the authorised top:

- **B1_32** pomegranate Tebuconazole, +17.6%. The model used 500 g/ha
  where CIB&RC states 425. A flat overdose of a real registered product.
- **S1_135** cotton Carboxin + Thiram seed dressing, 4.0 vs 3.5 g/kg
  seed, +14.3%.
- **S1_5524** and **S1_67** soybean Indoxacarb, +20.1% at the top. The
  label states a POINT dose of 333 g/ha; the model invented a range
  topping out at 400 g/ha. This is the failure mode `verify.py`'s
  docstring names first: a point dose is not an open-ended range.
- **S1_512** tomato Imidacloprid, +14.3% at the top. Label authorises
  150-175 per ha; the model claimed 150-200. Its lower bound is legal,
  its upper bound is not.

Three of the five are the same error: the model appends an upper bound
the label does not authorise. None is an order-of-magnitude overdose.
There is no repeat of the baseline's "Decis / permethrin at 20 ml per
litre" — no banned molecule was recommended anywhere (G4 497/497), and
no dose was wrong by more than 21% on the high side.

The largest error in the table is an **underdose**: S1_188, Trichoderma
viride at 10 ml against a label 2500 ml, off by 250x. Underdosing is an
efficacy and resistance problem rather than an acute hazard, but on a
biological control agent 10 ml/acre is functionally no treatment.

### 2.3 The per_acre question: answered, and it is not a basis error

The brief asked whether the top C1 pattern is the model writing
per-hectare numbers under a `per_acre` label. **It is not.** Zero
objections classify that way, and the arithmetic is exact in the other
direction:

```
60.7017  x 2.4711 = 150.0000      252.9238 x 2.4711 = 625.0000
134.7578 x 2.4711 = 333.0000      202.3390 x 2.4711 = 499.9999
171.9882 x 2.4711 = 425.0000      161.8712 x 2.4711 = 399.9999
```

Every value the model emits is an exact per-acre conversion of a round
per-hectare figure. It has learned the conversion perfectly and declares
the basis correctly (the 9 G8 failures are a separate matter). What it
gets wrong is **which per-hectare figure applies**:

| item | model implies /ha | label /ha |
|---|---:|---:|
| S1_5323 | 425.0 | 580.0 |
| S1_5323 | 400.0 | 500.0 |
| S1_604 | 150.0 | 200.0 |
| S1_512 | 150.0 | 200.0 |
| S1_833 | 150.0 | 200.0 |
| B1_22 / B1_23 | 625.0 | 750.0 |
| B1_32 | 500.0 | 425.0 |

These are recall errors over a small set of round label values, not unit
or basis confusion. That matters for Step C: the fix is grounding, not an
arithmetic or prompt-format correction.

### 2.4 A verifier bug I looked for and did not find

An earlier pass of this audit reported an "inside range" case where the
model's value sat inside the label range yet C1 failed, which would have
been a verifier bug. It was not. The audit had picked the candidate row
kindest to the model; the verifier was objecting to the model's *upper*
bound (S1_512 Imidacloprid, section 2.2). Rewriting this section to parse
the verifier's own messages removed the false finding. **No C1 conversion
bug exists.** The three unit-dimension mismatches are real model errors:
a g/ml swap, which `_to_base` correctly refuses to compare.

## 3. B — G5 audit, all 82 failures classified

85 items fail G5; 3 of them are also excluded, leaving the **82** the
brief names. Classification is per recommended option, so those 85 items
carry 220 failing options.

| class | options | items |
|---|---:|---:|
| (i) synonym false negative | 4 | 4 |
| (ii) mis-association — a.i. on the crop, different pest | 71 | 51 |
| (iii) invention — a.i. not on the crop at all | 134 | 68 |
| (iv) pest unresolved — no canonical to form a triple | 11 | 3 |

Class (iv) is not in the brief's three-way split and is reported
separately rather than forced into one of them: these are S2 CLARIFY
items where the query identifies no pest, so no `(crop, pest, a.i.)`
triple exists to check. Naming a chemical there is a real error, but it
is an error of answering an unresolved question, not of picking the wrong
molecule.

### 3.1 Class (i) — all four, with evidence

Every one is a multi-pest CIB&RC cell whose canonical extraction dropped
the organism, not a missing synonym-table entry:

| item | crop | queried | CIB&RC prints on the registered row |
|---|---|---|---|
| S1_233 | soybean | Girdle beetle | `Stem fly Girdle beetle Whitefly` |
| S1_5524 | soybean | Helicoverpa armigera | `Defoliators (Helicoverpa armigera, Spodoptera litura and Semilooper)` |
| S1_67 | soybean | Helicoverpa armigera | `Defoliators (Helicoverpa armigera, Spodoptera litura and Semilooper)` |
| B4c_1 | cotton | Helicoverpa armigera | `Bollworms (Helicoverpa armigera)` |

In each case the cell **literally prints the queried organism's name**,
the synonym table already maps that name to the right canonical, and the
row still did not get the canonical attached — so `for_triple` missed a
registration that CIB&RC does grant. These four are genuine evaluator
defects.

**The brief's example pairs are already handled.** I tested them against
the live table before counting:

| pair | resolves to |
|---|---|
| Mealybug / mealy bug (grape) | both `Mealybug` — SAME |
| Wilt / Fungal wilt (cotton) | both `Wilt` — SAME |
| Red spider mite / Mites (grape, cotton) | both `Red spider mite` — SAME |

So the synonym table is not the weak point the brief suspected. Class (i)
is small because the table is good; what fails is canonical extraction
from compound cells.

### 3.2 Two false positives I removed

An earlier heuristic counted shared words as synonymy and produced two
wrong class (i) calls, both worth recording so they are not
re-introduced:

- **Pink bollworm vs American bollworm** (S1_564, S1_1974). Different
  insects — *Pectinophora gossypiella* and *Helicoverpa armigera*.
  Sharing the word "bollworm" is not synonymy. Correctly class (ii).
- **Fruit rot vs Fruit borer** (B1_40) and **Fruit spot vs Fruit rot**
  (B1_29). Different problems sharing the word "fruit". Correctly class
  (ii).

The final test requires the printed cell to contain a name the synonym
table already maps to the queried canonical. It is deliberately strict,
because a loose test here would manufacture evaluator defects and excuse
real model errors.

### 3.3 Inventions are the bulk

134 of 220 failing options name a molecule with **no CIB&RC row on that
crop for any pest**. Recurring examples: Tebufenpyrad on cotton (05% EW
and 20% WP), Tebuconazole 5.4% FS on cotton, Acetamiprid 20% SP on
soybean, Buprofezin + Diafenthiuron on cotton. These are real products
registered elsewhere, applied to the wrong crop — precisely the
"registered on one crop is not registered on another" rule the system
prompt states explicitly. G5 is doing its job.

## 4. C — the C5 surface-form defect

**Confirmed, traced, and it changes no score.**

### 4.1 Why cotton / Helicoverpa armigera prints as Jassid, Aphids, thrips

`surface_forms_for("cotton", "Helicoverpa armigera")` returns 22 forms,
beginning `['Jassid', 'Aphids', 'thrips', 'Whiteflies', 'Pectinophora
gossypiella', 'Helicoverpa armigera', ...]`.

The mechanism is a single CIB&RC cell naming seven pests. label_db row 8
prints:

```
Jassid, aphids, thrips,  whiteflies,  Pectinophora  gossypiella,  Helicoverpa  armigera, Earias
```

That row carries **7 canonicals**, Helicoverpa armigera among them, and
it is correct that it does: the row genuinely is registered for
Helicoverpa. `for_pair` therefore returns it. But `surface_forms_for`
then collects the printed forms of *every* matched row, so the other six
pests sharing that cell come back as "what CIB&RC prints for Helicoverpa
armigera". They are not; they are its cell-mates. 26 rows match the pair,
and **325 of 740 label_db rows are multi-canonical**, so the effect is
widespread.

### 4.2 It is a message defect, not a scoring defect

`surface_forms_for` is read at exactly two places in `src/verify.py`,
line 811 in the G5 failure string and line 1172 in the C5 failure string.
Both are failure-text construction. It never touches a verdict.

Confirmed empirically from the other direction: of the **96 C5 top-1
failures**, **zero** are cases where the model's cause and the gold
canonical are the same organism under different names. Every one is a
genuine diagnostic miss. The most common:

| n | gold | model said |
|---:|---|---|
| 7 | Red spider mite | Thrips |
| 6 | Leaf spot (unspecified) | Bacterial blight (cotton) |
| 4 | Tobacco caterpillar | Semilooper |
| 4 | Root rot | Wilt |
| 4 | Termite | Helicoverpa armigera |

**71 items carry a C5 or G5 failure message quoting surface forms that do
not belong to the item's pest.** The verdicts are right and the
explanations are misleading, which is a real problem for anyone reading
failures to decide what to fix — it nearly produced a wrong conclusion in
this very audit — but it contributes **0.0** to the score gap.

### 4.3 One genuine synonym gap found nearby

Unqualified `bollworm` resolves to `Bollworm complex`, not to
`Helicoverpa armigera`. A model answering "bollworm" on a Helicoverpa
query is scored wrong on C5. That is defensible, since the unqualified
term is ambiguous, but it is worth a decision. It is not counted in any
figure above.

## 5. D — refusal on answerable items

### 5.1 The model still refuses 120 answerable questions

Of 267 schema-valid items the verifier calls ANSWERABLE, **123 have an
empty `chemical_options`**. On **120** of them the gold advisory names a
chemical, so the refusal is wrong:

| slice / kind | items | gold names a chemical |
|---|---:|---:|
| 1 DOSE | 98 | 97 |
| 3 REFUSAL_DOSE | 23 | 23 |
| 1 OFFTOPIC | 2 | 0 |

The 23 S3 items are the banned-chemical-with-legal-alternative bucket:
the gold answer refuses the banned product *and* offers the registered
one. The model refuses entirely and so earns nothing. That is the
mechanism behind section 6's refusal-slice regression.

Under the Step A score-mode rule each of these 120 items takes
C1 = C2 = C3 = 0.0, which is 0.65 of the graded weight. **This is the
single largest contributor to the gap between 0.5203 and 1.0.**

### 5.2 It did not learn refusal from refusal examples — it learned CLARIFY

| shape of the 123 refusals | n |
|---|---:|
| `query_understood=false` + clarifying question, no chemicals | 112 |
| understood, non-chemical measures only | 9 |
| understood, nothing offered | 2 |

**112 of 123 (91%) are the slice-2 CLARIFY shape.** Example S1_101, a
cotton wilt dose question: the model sets `query_understood=false`, asks
which symptoms are present, and lists Jassid and Thrips as low-confidence
causes, while gold names a Sedaxane + Fludioxonil + Thiamethoxam seed
treatment at 1.6187 ml/acre.

The training data explains it, and not in the way the brief's hypothesis
suggested:

| slice | examples | share | empty options | clarifying question |
|---|---:|---:|---:|---:|
| 1 DOSE | 1,056 | 23.5% | 9 (0.9%) | 0 |
| 2 CLARIFY | 3,033 | 67.5% | 3,033 (100%) | 2,486 |
| 3 REFUSAL | 89 | 2.0% | 55 (61.8%) | 54 |
| 4 (train-only) | 200 | 4.5% | 2 (1.0%) | 2 |
| 5 NOCHEM | 115 | 2.6% | 115 (100%) | 0 |
| **total** | **4,493** | | **3,214 (71.5%)** | **2,542 (56.6%)** |

**The test result: no.** Only 9 of 1,056 slice-1 dose examples (0.9%)
refuse, so the model did not learn "refuse a dose question" from dose
examples. What it learned is that **71.5% of all training answers name no
chemical and 56.6% ask a clarifying question**, because slice 2 is 67.5%
of the corpus. It acquired the plurality policy and over-applies it to
questions that deserve an answer.

This is a data-composition problem, not a refusal-example problem, and it
will not be fixed by removing refusal examples.

## 6. E — slice balance vs slice score

| slice | SFT examples | SFT share | bench n | bench mean | baseline mean |
|---|---:|---:|---:|---:|---:|
| 1 DOSE | 1,056 | 23.5% | 232 | 0.3372 | 0.1117 |
| 2 CLARIFY | 3,033 | 67.5% | 173 | **0.9711** | 0.3121 |
| 3 REFUSAL | 89 | 2.0% | 44 | **0.0469** | 0.0712 |
| 4 | 200 | 4.5% | — | train-only | — |
| 5 NOCHEM | 115 | 2.6% | 40 | 0.1536 | 0.0300 |

The ordering of bench scores matches the ordering of training share
exactly. Slice 2 is two-thirds of the corpus and is nearly solved at
0.9711. Slice 3 is 2.0% of the corpus and is the **only slice where the
trained model is worse than the untrained baseline** (0.0469 vs 0.0712).

Slice 1 carries 47% of the benchmark but 23.5% of the training data, and
the benchmark's whole purpose is dose correctness.

### 6.1 Two regressions worth flagging

- **Slice 3 REFUSAL: 0.0469 trained vs 0.0712 baseline.** The baseline
  scored better by refusing, which is half the gold answer. The trained
  model refuses too (23 items, section 5.1) but now also loses C4 on
  some. The 44-item slice is small enough that this is a handful of
  items — still, on the safety-critical slice the model got worse.
- **Wheat: 0.0000 trained vs 0.3333 baseline** (n=3, out-of-scope
  items). Small n, but a clean regression on out-of-scope handling.

For completeness, by difficulty (non-excluded): standard 0.6373 vs
baseline 0.2137, hard 0.4346 vs 0.1278, edge_case 0.1187 vs 0.0495. The
Step A difficulty ordering holds.

## 7. Evaluator-corrected estimate

**This is an ESTIMATE, not a re-score.** It re-folds each item's
already-recorded checks with G5 forced True. It does not re-run the dose
and PHI comparisons that a real synonym repair would newly make
reachable, so it is a bound on the effect, not a prediction of it.

| scenario | value | vs observed |
|---|---:|---:|
| observed (489 non-excluded) | 0.5203 | — |
| class (i) repaired, strict | **0.5203** | +0.0000 |
| class (i) repaired, generous ceiling | **0.5249** | +0.0046 |
| C5 defect repaired | 0.5203 | +0.0000 |

**Strict is unchanged because zero items are rescued.** All four class (i)
items also carry a class (ii) mis-association on a *different*
recommended option, so G5 still fails on every one of them. G5 is
correctly all-or-nothing: one unregistered recommendation among good ones
is still an unregistered recommendation.

The generous arm excuses those other failures too, purely to bound the
effect. Even then the four items contribute +0.46pp:

| item | now | if fully rescued |
|---|---:|---:|
| S1_233 | 0.0 | 1.0 |
| S1_5524 | 0.0 | 0.475 |
| S1_67 | 0.0 | 0.350 |
| B4c_1 | 0.0 | 0.400 |

S1_233 is the one that stings: all six of its graded checks score 1.0 —
correct dose, PHI, formulation, escalation and diagnosis — and it totals
0.0 because a compound pest cell cost it G5.

**The C5 defect is credited zero** because it is message-only (section
4.2). Crediting it anything would be fabrication.

**Conclusion: the evaluator-corrected score is 0.5203, with a ceiling of
0.5249.** The 0.5203 is not inflated by evaluator leniency and is
depressed by at most half a point of evaluator strictness. The remaining
0.48 is model error, dominated by wrongful refusal (120 items), invention
(134 options) and mis-association (71 options).

## 8. What I did not do, and what needs a decision

Nothing was modified. `src/verify.py`, `src/schema.py`, the pest synonym
table and every file in `data/` are untouched. The one file added is
`tools/phase10_stepB_audit.py`, which is read-only.

Decisions I need from review before Step C:

1. **The denominator.** Fix a single convention for the headline metric
   and restate both runs under it. My recommendation: scoring the 11
   exclusions as 0.0 is wrong, because it punishes the model for our
   contradictions; the 489-item mean is defensible **only if the baseline
   is also restated on the same 489** (0.1723). Pick one and put it in
   the report body, not a footnote.
2. **The four class (i) items.** The defect is canonical extraction from
   compound pest cells, not the synonym table. Fixing it touches pest
   parsing, which is upstream of label_db — a bigger change than it looks
   for +0.46pp at most. My recommendation: log it, do not fix it during
   Phase 10, re-score once if it is ever fixed.
3. **The C5 message defect.** Worth fixing on its own merits, since it
   made this audit briefly reach a wrong conclusion, but it is cosmetic
   to the score. `surface_forms_for` should filter to the forms that
   actually resolve to the requested canonical.
4. **Slice rebalancing for the next run.** Slice 2 is 67.5% of training
   and slice 1 is 23.5%, and the model has learned to clarify when it
   should answer. This is the highest-value change available, and it is a
   data decision rather than a training-hyperparameter one.
5. **The unqualified-bollworm resolution** (section 4.3), which currently
   scores a defensible answer as wrong.
