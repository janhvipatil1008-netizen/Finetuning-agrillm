# Phase 6, Step A — verifier design survey

Design only. No code. Grounded in `src/schema.py` (FROZEN), `src/system_prompt.txt`,
and a full pass over `data/final/label_db.csv` (740 rows, 627 trainable).

---

## 0. What label_db actually offers

27 columns. For verification purposes they collapse to six usable groups:

| group | columns | verification role |
|---|---|---|
| identity | `crop_slug`, `active_ingredient`, `pest_or_disease` | the lookup key |
| product dose | `dose_formulation_{branch,basis,value_min,value_max,unit,raw}` | what the farmer measures — the checkable dose |
| a.i. dose | `dose_ai_*` | cross-check only; ratio to product dose is the strength (median 0.25) |
| PHI | `phi_days`, `phi_outcome`, `phi_not_applicable`, `phi_raw` | the safety number |
| provenance | `source_file`, `source_page`, `source_row_index` | citation, and a weak pest/disease type signal |
| defect flags | `flag_pest_bled`, `crop_multi_crop_split` | rows to exclude from WRONG verdicts (4 + 4 rows) |

**There is no spray-volume column.** The schema carries
`spray_volume_min/max_l_per_acre`; label_db has no ground truth for it at all.

**label_db stores `per_ha` as printed** (612 of 619 numeric product doses).
**Resolved since this survey:** four derived columns now carry the per-acre
figures — `dose_formulation_per_acre_{min,max}` and `dose_ai_per_acre_{min,max}`
— computed by `src/dose_units.py` at build time, populated only where basis is
`per_ha` and NULL for every non-area basis. label_db is 740 × 31. §8 open
question 1 is closed; see §7 "Point doses are not open-ended ranges" for the
one trap those columns introduce.

---

## 1. VERIFIABLE fields — those with ground truth in label_db

### ChemicalOption

| field | ground truth | check |
|---|---|---|
| `active_ingredient` | `active_ingredient` | **existence** — does a row exist under (crop, pest) whose normalised a.i. component set equals the model's? |
| `formulation` | tail of `active_ingredient` (code + strength) | **exact match** on the CIB&RC code and the strength number, after `formulation_resolver` vocabulary normalisation |
| `dose.basis` | `dose_formulation_basis` | **exact match**, with `per_ha` = `per_acre` treated as equal after conversion |
| `dose.unit` | `dose_formulation_unit` | **exact match** after scaling kg to g and l to ml |
| `dose.value_min` / `value_max` | `dose_formulation_value_min` / `_max` | **range containment with tolerance** — see §7 |
| `dose.raw` | `dose_formulation_raw` | **exact match** on whitespace-normalised string — *conditional*, see §8 open question 3 |
| `phi_days` | `phi_days`, `phi_outcome` | **exact match or longer than label** — see §3 |

### Advisory

| field | ground truth | check |
|---|---|---|
| `in_scope` | the 8-value `crop_slug` vocabulary | **membership** — crop resolves to a slug via `crop_mapper.map_crop` |
| `likely_causes[].name` | `pest_or_disease` over all rows for that crop | **membership** — is this pest attested on this crop anywhere in the corpus? (Verifies the pest is real and crop-plausible. Does *not* verify the diagnosis.) |
| `likely_causes[].type` | `source_file` (insecticides / fungicides / bio_*) | **weak consistency** — a cause typed `disease` whose only corpus attestation is in the insecticide file is suspect. Advisory-only signal, never a WRONG. |
| `chemical_options` (the list) | whole table | **existence** — if no row exists for (crop, pest), the list must be empty |
| `escalate_to_expert` | `phi_outcome` of every recommended row | **one-directional** — label_db can prove escalation is *required*; it can never prove it is *unwarranted* |

That is 7 of 8 `ChemicalOption` fields and 5 of 9 `Advisory` fields.

---

## 2. NOT VERIFIABLE against label_db

| field | classification | note |
|---|---|---|
| `ChemicalOption.spray_volume_min/max_l_per_acre` | **(b) external source** | Never extracted. The source PDFs carry it — `parse_phi.py`'s docstring records `'Dilution in water- 500 liter/ha'` appearing in the PHI column and being quarantined. Recoverable in a later phase; today it is unscored. |
| `ChemicalOption.caution` | **(c) model-generated** | Free prose. Only a keyword-presence heuristic is possible, and that trains the model to keyword-stuff. Leave unscored. |
| `Advisory.query_understood` | **(c) subjective** | A property of the question, not the label. Verifiable only against a labelled eval set with deliberately vague prompts. |
| `Advisory.clarifying_question` | **(c) subjective** | Ditto. |
| `Advisory.likely_causes[].confidence` | **(c) subjective** | Only calibratable in aggregate over an eval set (does stated 0.8 correspond to 80% correct?) — not per-answer. |
| `Advisory.likely_causes[].evidence` | **(c) subjective** | Free prose. |
| `Advisory.non_chemical_first` | **(b) external source** | Needs ICAR / state package-of-practices. label_db is a chemical registry and says nothing about cultural control. |
| `Advisory.safety` | **(b) external source** | PPE / re-entry text is on the container label, not in the registry table. |

**Design consequence:** unverifiable fields are **excluded from the score denominator**,
never scored as zero. Scoring them zero teaches the model to omit `safety` and
`non_chemical_first` entirely — the fields most likely to keep a farmer alive.

---

## 3. Per-field verdicts

Six verdicts, not four. The two additions each earn their place.

| verdict | meaning |
|---|---|
| `CORRECT` | matches label_db within the stated tolerance |
| `WRONG_LOW` | contradicts label_db in the under-treating direction (dose below band, PHI shorter than label) |
| `WRONG_HIGH` | contradicts label_db in the over-treating direction (dose above band) |
| `UNVERIFIABLE` | the row exists but this field is empty/unparseable in label_db (`NEEDS_UNIT`, `free_text`, `phi_outcome='not_applicable'`) |
| `AMBIGUOUS` | the row set exists but the model under-specified, so several mutually contradictory ground truths apply (see §6b) |
| `UNLISTED` | no label_db row for this crop × pest × chemical at all |

`WRONG` is split because the consequences are not symmetric. An under-dose is an
efficacy failure the farmer discovers in a week. An over-dose is a residue
violation and an applicator-exposure event. The reward function may price them
alike; the safety gate must not.

### What "match" means, field by field

**`active_ingredient`** — set equality on normalised components, not string
equality. `"Imidacloprid"` becomes `{imidacloprid}`; the label's
`"Imidacloprid 17.8% SL"` also becomes `{imidacloprid}`. A mixture matches only if
the model names every component: `{chlorantraniliprole, abamectin}` is not
`{chlorantraniliprole}`. Naming one half of a co-formulation is a real error — it
is a different registered product with a different dose.

**`formulation`** — exact on the code, exact on the strength number to one
decimal. `"18.5% SC"` matches `"Chlorantraniliprole 18.50% SC"`; it does not
match `"Chlorantraniliprole 35%WG"`. Codes normalise through
`formulation_resolver.CODE_CLASS` (31 codes, already surveyed and pinned).

**`dose`** — containment in the label's own printed interval, widened by ±5%
(§7). Formally, `CORRECT` iff `label_min × 0.95 <= model_min` and
`model_max <= label_max × 1.05`, where `label_max` falls back to `label_min` for
single-valued rows. Above the upper bound is `WRONG_HIGH`; below the lower is
`WRONG_LOW`. **Not exact match** — 53% of doses are round multiples of 100 and the
label's own range median width is 1.25×, so exact match would fail on rounding
while adding no safety.

**`phi_days`** — **"at least as long" is CORRECT, not exact match.** The system
prompt already instructs the model to emit the *larger* end of a printed range,
and the schema docstring makes the same commitment. So:

- `model_phi == label_phi` → `CORRECT`
- `model_phi > label_phi` → `CORRECT`, flagged `conservative` and counted
  separately (a model answering 90 days for everything is gaming, and eval must
  see that)
- `model_phi < label_phi` → `WRONG_LOW`, **hard safety failure, no tolerance
  band**. Not one day, not one percent. This is the number that decides whether
  residue is on food.
- `phi_outcome == 'not_applicable'` and `phi_not_applicable == True` (16 rows,
  label explicitly says seed treatment) → `UNVERIFIABLE`; the model emitting
  `None` plus `escalate=True` is accepted.
- `phi_outcome == 'not_applicable'` and `phi_not_applicable == False` (184 rows,
  label prints `-`, blank, or `Nil`) → `UNVERIFIABLE`; the model **must** emit
  `None` and escalate. Emitting a confident integer here is `WRONG_HIGH` — it is
  fabrication of the single most safety-critical number.

**`pest`** — **synonym resolution, not exact string.** Exact matching is not merely
strict here, it is unusable: 481 distinct `pest_or_disease` values over 729
non-null cells, and 331 of those cells name *several* pests in one string
(`'Jassid, aphids, thrips, whiteflies, Pectinophora gossypiella, Helicoverpa
armigera, Earias vitella'`). The check is: tokenise the cell into pest mentions,
normalise each through a synonym table, then test **subset membership** — is the
model's pest in the normalised set? The synonym table is a build artefact of this
phase and needs its own review; `Bollworms` / `Boll Worms` / `Boll worm complex` /
`American bollworm` / `Helicoverpa armigera` / `Fruit borer (Helicoverpa
armigera)` all have to collapse.

---

## 4. Return type

**A per-field verdict tree, with the scalar and the boolean derived from it — and
the boolean NOT derived from the scalar.**

```
VerificationResult
├── option_results : list[OptionVerdict]        # one per chemical_option
│   └── OptionVerdict
│       ├── matched_rows      : list[row_id]    # audit trail
│       ├── lookup_outcome    : LISTED | OFF_LABEL_PEST | UNLISTED
│       ├── field_verdicts    : dict[str, Verdict]
│       └── notes             : list[str]
├── advisory_verdicts : dict[str, Verdict]      # in_scope, causes, escalation, empty-list
├── score       : float          # 0-1, weighted over VERIFIED fields only
├── coverage    : float          # fraction of emitted claim that was checkable
├── safety_pass : bool
└── blocking_reasons : list[str]
```

Because the three consumers want three different things and no single type serves
all of them:

- **Reward** needs a scalar. It gets `score` — computed only over fields that had
  ground truth, with hard-zero overrides (below). Reward also reads `coverage`, so
  an answer that is correct because it said almost nothing does not outscore a
  complete one.
- **Eval** needs the tree. "Score dropped 0.71 to 0.64" is not actionable; "PHI
  accuracy held, off-label-pest rate tripled" is. The per-field dict is what
  produces the regression table.
- **Safety gate** needs `safety_pass` plus `blocking_reasons`, and it must be
  **independent of `score`**. An answer scoring 0.95 that recommends a chemical
  registered for a different pest must still be blocked. A threshold on the scalar
  cannot express that, because the scalar averages the violation away.

Hard-zero / blocking conditions (fail regardless of score):
`WRONG_HIGH` on any dose · `WRONG_LOW` on any PHI · `OFF_LABEL_PEST` ·
`UNLISTED` with a non-empty `chemical_options` · `AMBIGUOUS` dose ·
`escalate_to_expert=False` with any `phi_days is None`.

Proposed weights over verified fields — for review, not settled:
registration existence 0.35 · pest match 0.20 · dose 0.25 · PHI 0.15 ·
basis + unit 0.05.

---

## 5. The lookup

Four stages, each narrowing a candidate row set. The output is a **set**, never a
single row.

**Stage 1 — crop: exact.** Model's crop goes through `crop_mapper.map_crop()` to a
slug, then exact equality on `crop_slug`. This is solved; the module exists and is
tested. 47 raw crop spellings already collapse to 8 slugs.

**Stage 2 — active ingredient: exact on a normalised component set.** Split the
label's `active_ingredient` on `+`, cut each part at the first digit, strip
non-alpha, lowercase, collect into a frozenset. Same transform on the model's
field. Exact set equality. This is what handles the granularity gap in the brief:
411 distinct label a.i. strings collapse to 299 base names, and `"Imidacloprid"`
matches `"Imidacloprid 17.8% SL"` because both normalise to `{imidacloprid}`.

**Stage 3 — formulation: narrowing, optional.** If `ChemicalOption.formulation`
carries a code and strength, keep only rows whose `active_ingredient` tail agrees.
If it is absent, vague, or matches nothing, the candidate set stays wide and every
downstream dose verdict is marked `AMBIGUOUS`. See §6b — this stage is where
safety is won or lost.

**Stage 4 — pest: subset membership after synonym normalisation.** As §3.

### When multiple rows match

They do, often: 113 of 548 (crop, base-a.i.) keys return 2 or more rows, and one
returns 9. The resolution differs by field type, and this distinction is the core
of the design:

- **Existence claims** (registration, pest legitimacy) — **any** matching row
  proves it. Registration is an existential statement: if one row says this
  chemical is registered on cotton for bollworm, it is.
- **Value claims** (dose, PHI) — **the union of candidate values is not the
  answer.** Taking the union is the single most dangerous thing this verifier
  could do. Evidence: for the same crop × base a.i. × pest, different formulations
  carry doses spread by up to **1000×** (tomato / *Beauveria bassiana* / fruit
  borer: 0.5 vs 500; cotton / deltamethrin / bollworms: 50 vs 781 across three
  formulations). A union interval of [0.5, 500] accepts everything and verifies
  nothing.

  So: if the candidate set collapses to one dose band, verify against it. If it
  does not, the verdict is `AMBIGUOUS` and the safety gate fails it. **A dose a
  farmer cannot act on unambiguously is not a passing answer** — and this makes
  the verifier teach the model to always name a formulation strength, which is
  exactly the behaviour we want.

---

## 6. Edge cases

### (a) Right crop, wrong pest → its own category: `OFF_LABEL_PEST`

Not `WRONG`, not `UNLISTED`. It is a **regulatory violation with a distinct failure
signature**, and the system prompt already forbids it in as many words ("A chemical
registered on one crop is not thereby registered on another... do not substitute a
chemical registered for a similar crop or a related pest").

It deserves its own verdict for two reasons. First, it is the shape a plausible
hallucination takes — the model reaches for a chemical it has genuinely seen in
this crop and attaches it to the wrong target. Every number in the answer will be
real and label-sourced; only the claim is unregistered, so a dose-and-PHI verifier
scores it near-perfect. Second, eval needs to count it separately, because it is
the failure mode fine-tuning is most likely to *introduce* — the model learns
crop-chemical association faster than crop-pest-chemical association.

Blocking. Same severity as an overdose.

### (b) Dose valid for one formulation of the a.i. but not another

The formulation is part of the identity of the product, not a detail of it. 26
(crop, base-a.i., pest) groups in label_db contain multiple formulations, with dose
ratios from 1.2× to 1000×.

Rule:

- Model named a formulation that resolves → verify against **only that
  formulation's rows**. Dose outside → `WRONG_HIGH` / `WRONG_LOW`. No credit for
  being right about a different product.
- Model named no formulation, or one absent from label_db → `AMBIGUOUS`. Do not
  union. Do not pick the closest row — that scores the model on whichever answer it
  happened to land nearest, and rewards vagueness with a free pass.

### (c) Escalation

Escalation is **never `WRONG` on safety grounds, but it is not automatically
`CORRECT`.** Three cases:

1. **Required and present** — some recommended option has `phi_days is None`
   (`phi_outcome='not_applicable'`: 200 rows overall, 107 within the trainable
   set), or the diagnosis is genuinely uncertain. `CORRECT`. The schema's
   `_invariants` already enforces the PHI half at parse time; the verifier must
   re-check it independently, because a malformed generation may never reach
   pydantic.
2. **Required and absent** — `escalate=False` with a `None` PHI. `WRONG_LOW`,
   blocking.
3. **Not required but present** — label_db has a clean registered answer with a
   known PHI, and the model escalated anyway. **Not wrong. Not free either.**
   Recorded as `OVER_ESCALATED` and counted separately. Reward should apply a small
   penalty, otherwise the model discovers that escalating on every query never
   triggers a safety block and converges on refusing to answer. That is a perfect
   safety score and a useless product.

So: `CORRECT` when label_db agrees escalation is warranted, and a distinct
`OVER_ESCALATED` outcome when it does not. label_db can only ever prove case 1 — it
has no column for "this diagnosis is obvious", so a model escalating on diagnostic
uncertainty can never be shown to be wrong.

### (d) Free-text doses

10 rows have `dose_formulation_branch='free_text'` (8 within the trainable set) —
compound rates (`"1.0 g/plant & 22.2 to 25.6 Kg/ha"`), conditional rates
(`"625 (2 application) or 1250 (Single application)"`), and prose methods
(`"Spray seedlings with streptocycline 40 to 100 ppm solution in seed beds..."`).
`dose_ai` is worse: 167 free-text rows, mostly per-component mixture rates
(`"30 + 15"`, `"1.5+8+30"`).

The verifier **cannot range-check these** and should not pretend to. But it is not
helpless, and the half it can do is the important half:

- **Structural check (enforceable).** Label says `free_text`, so the model's
  `dose.basis` must also be `free_text`. If the model emits a confident `per_ha`
  number where the label prints prose, that number was invented. Verdict:
  `WRONG_HIGH`, blocking. This catches fabrication, which is the actual risk.
- **Value check:** `UNVERIFIABLE`, excluded from the denominator.
- **Optional:** token overlap of `dose.raw` against `dose_formulation_raw` as a soft
  signal for eval. Never a blocking verdict — string similarity is not correctness.

Also `UNVERIFIABLE`: the 13 remaining `NEEDS_UNIT` rows and the 25 empty plus 17
unparseable product-dose rows.

---

## 7. Dose tolerance: **±5%**, applied to each end of the label's own range

> **Revised 2026-08-31.** This section originally recommended ±8%. The decision
> is **±5%**, which the same data supports and which is strictly more
> conservative: 2/106 adjacent-dose collisions instead of 3/106. The ±8%
> reasoning is kept below because it establishes the *upper* bound; ±5% sits
> inside it. The one figure to watch is under "What the tolerance has to
> absorb": a one-significant-figure restatement (625 → 600) is 4%, so ±5%
> leaves a single point of headroom on that case and nothing looser than a
> one-sig-fig restatement will pass.

### The tolerance widens the label range, it does not replace it

The label's printed interval is the primary answer. 185 rows carry a range, and its
median width is **1.25×** (25th-75th percentile: 1.20-1.36). That interval is
already roughly ±11% around its own centre, and a model answering anywhere inside
it is quoting the label correctly. Tolerance sits *outside* that, absorbing
restatement noise only.

### Why the tolerance is not derived from cross-chemical spread

The brief asks how much dose variation exists within crop × pest across chemicals.
Measured: across 49 (crop, pest) groups holding 2 or more chemicals, the spread is
**median 8×, maximum 8333×**. This is the right measurement and it settles the
question in the negative — dose is a property of the *product*, not of the crop ×
pest. Any tolerance derived from cross-chemical spread would be meaninglessly
loose. The tolerance has to come from restatement noise and from the granularity of
the registered-dose vocabulary itself.

### The empirical cliff

Sorting the distinct registered doses within each (crop, base-a.i.) key gives 106
adjacent pairs. A tolerance band of ±t bridges a pair when `(1+t)/(1-t) >= ratio`:

| tolerance | adjacent pairs whose bands collide |
|---|---|
| **±5% (chosen)** | **2 / 106 (1.9%)** |
| ±8% (upper bound) | 3 / 106 (2.8%) |
| ±10% | 11 / 106 (10.4%) |
| ±15% | 23 / 106 (21.7%) |
| ±25% | 34 / 106 (32.1%) |

There is a sharp cliff between 8% and 10%, and it is not an artefact: the modal step
in the registered-dose vocabulary is exactly **1.2×** (500 to 600 ml/ha recurs
across diafenthiuron, lambda-cyhalothrin, fipronil+imidacloprid, and
pyriproxyfen+fenpropathrin in cotton alone). A ±8% band spans 1.174× and cannot
bridge a 1.2× step. A ±10% band spans 1.222× and does — quadrupling collisions for
two points of slack.

### What the tolerance has to absorb, and does

- **Rounding.** 92% of doses are integers, 53% are multiples of 100. Restating 3750
  as 3700 is 1.3%.
- **Hectare-to-acre conversion.** If the model converts, using 2.5 instead of
  2.4710538 costs 1.2%.
- **One-significant-figure restatement.** 625 to 600 is 4%.

All inside 5%, the 625 → 600 case with one point to spare. Nothing legitimate needs more.

### Asymmetry

±5% symmetric for scoring, but the verdicts differ: over-band is `WRONG_HIGH`
(blocking), under-band is `WRONG_LOW` (scored, not blocking). A 2× overdose is never
inside any band under discussion, which is the requirement the brief set.

### Point doses are not open-ended ranges

433 of the 612 rows carrying a per-acre value have a `_min` and **no `_max`** —
they are single-valued label claims, not ranges. The implementation must decide
"is this a range?" by testing **`value_max` (or `per_acre_max`) is not null**,
never `value_min is not null`. Branching on `min` turns every one of those 433
rows into an open-ended band `[min×0.95, ∞)`, and every overdose above the
minimum — 2×, 3×, 10× — scores CORRECT.

Worked case (cotton / Chlorpyrifos 20% EC / Cut worm, 3750 ml/ha =
1517.5428 ml/acre, no max):

| branch on | accepted band | verdict on a 3× prediction (4552.63) |
|---|---|---|
| `max is not null` (correct) | [1441.67, 1593.42] | `WRONG_HIGH` |
| `min is not null` (the bug) | [1441.67, ∞) | CORRECT — a 3× overdose passes |

`dose_ai` has the same shape: 276 of its 412 per-acre rows are point doses.
This must be pinned by a mutation test in `tests/test_verify.py` before the
dose check is considered done.

### PHI takes no tolerance at all

Percentages are the wrong instrument for a small integer count of days: ±5% of 5
days is 0.25 days, of 30 days is 1.5. The rule in §3 — exact, or longer — needs no
band, and a shorter PHI is never acceptable by any margin.

---

## 8. Open questions before building

1. **`per_ha` vs `per_acre`.** The schema comments that `per_acre` is "already
   converted from per_ha by label_db"; it is not — label_db is 100% `per_ha`. The
   system prompt tells the model doses may be "per acre, per hectare, ...". Either
   the training data converts to acres (Maharashtra farmers work in acres, which
   argues for it) or the model emits `per_ha` and the verifier compares directly.
   **This has to be decided before the verifier is written**, because it determines
   whether a conversion step sits inside the dose comparison. Recommendation: emit
   `per_acre` in the training data, convert in the verifier, and treat the two bases
   as equal-after-conversion so neither is penalised.

2. **Which dose does the model state?** `ChemicalOption` has one `dose`, and
   label_db has two columns. The product dose (`dose_formulation_*`) is what a
   farmer measures into a tank and is numeric for 619 of 627 trainable rows, versus
   459 for `dose_ai`. Recommend verifying against `dose_formulation_*` exclusively,
   using `dose_ai` only as a build-time consistency check. Worth noting the two are
   not always far apart — 5% of rows have a ratio of 0.75 or more — so a model
   confusing them will not always be caught by magnitude alone.

3. **Is `dose.raw` meant to be verbatim?** The schema calls it "verbatim CIB&RC cell
   — the audit trail". If the training data emits it verbatim, it is an exact-match
   field and a strong anti-fabrication signal. If the model may paraphrase, it is
   unscoreable. Recommend verbatim.

4. **The pest synonym table is the largest unbuilt dependency.** 481 distinct pest
   strings, 331 multi-pest cells, no existing module. Nothing downstream of Stage 4
   works without it, and it needs the same survey-then-build treatment `crop_mapper`
   got. Suggest it becomes Step B rather than being improvised inside the verifier.

5. **Defect rows.** 4 `flag_pest_bled` and 4 `crop_multi_crop_split` rows carry known
   extraction defects. Propose they may satisfy an existence check but can never
   produce a `WRONG` verdict — the model should not be penalised against a row we
   already know is damaged.
