# Phase 10 Step A — baseline benchmark on untrained Qwen2.5-7B-Instruct

Status: **complete 2026-09-12. Generation run 2026-09-11; scorer changed
the same day (section 3a); re-scored 2026-09-12 under the new rule
(section 2a).**

> **The official baseline is 0.1719 (new rule, section 2a).** The
> score-mode rule in `src/verify.py` was changed on 2026-09-11, *after*
> the 500 responses were generated, in response to this report's own
> mechanism-3 finding. Section 2 keeps the OLD-rule numbers (mean 0.3776)
> for the record and because they are what the finding was made on.
> Section 2a re-scores the same 500 raw responses under the NEW rule and
> shows both columns. Every future comparison is against the new-rule
> column.

This is the pre-training reference point for `data/final/bench.jsonl`
(500 items, frozen per `reports/phase9_stepA_benchmark_design.md`). Every
later number in Phase 10 is read against this one. The old-rule mean is
0.3776 and the official new-rule mean is 0.1719; section 3 explains why
neither number should be read as partial competence.

## 1. Run configuration

| setting | value |
|---|---|
| model | `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` (no fine-tuning, no LoRA) |
| quantisation | 4-bit (bitsandbytes, as shipped) |
| hardware | Kaggle, 2 × T4 |
| benchmark | `bench.jsonl`, all 500 items |
| decoding | greedy (`temperature=0`) |
| `max_new_tokens` | 1200 |
| system prompt | `kaggle_upload/system_prompt.txt` (same prompt the SFT data was generated under) |
| scorer | `src/verify.py` in `score` mode, `label_db.parquet` |

Greedy decoding was chosen so the baseline is reproducible and so a
re-run after training compares like with like.

## 2. Headline numbers (OLD rule, as originally scored)

Everything in sections 2.1–2.5 is under the scorer as it stood when the
run was made, before the change in section 3a. Kept for the record; the
official numbers are in section 2a.

| metric | value |
|---|---:|
| mean total score | **0.3776** |
| items scoring 1.0 | **148 / 500** (29.6%) |

### 2.1 Gate pass rates

| gate | passed | of | rate |
|---|---:|---:|---:|
| G1_json | 500 | 500 | 100.0% |
| G2_schema | 264 | 500 | 52.8% |
| G3_empty_when_not_answering | 264 | 264 | 100.0% |
| G4_restricted_ai | 264 | 264 | 100.0% |
| G5_triple_registered | 264 | 264 | 100.0% |
| G6_unknown_phi_escalates | 264 | 264 | 100.0% |
| G7_trainable_row | 264 | 264 | 100.0% |
| G8_dose_basis | 264 | 264 | 100.0% |
| G9_unstated_dose_earned | 264 | 264 | 100.0% |

G3–G9 are evaluated only on the 264 items that cleared G2. Every one of
those 264 passes every later gate; section 3 explains why that is not
good news.

### 2.2 Check means

| check | weight | n applicable | mean |
|---|---:|---:|---:|
| C1_dose | 0.30 | 0 | never graded |
| C2_phi | 0.25 | 0 | never graded |
| C3_formulation | 0.10 | 0 | never graded |
| C4_escalation | 0.15 | 264 | 0.8182 |
| C5_causes_top1 | 0.10 | 0 | never graded |
| C6_non_chemical | 0.10 | 94 | 0.0000 |

**C1_dose, C2_phi, C3_formulation and C5_causes_top1 all have n = 0.**
Not one item in the benchmark produced a chemical recommendation the
verifier could grade. The only checks with a non-zero n are
C4_escalation, which is scored on every schema-valid item, and
C6_non_chemical, which the model failed on all 94 items where CIB&RC
ground truth required a non-chemical option.

### 2.3 Per-slice breakdown

| slice | n | mean total |
|---|---:|---:|
| S1 DOSE | 243 | 0.5333 |
| S2 CLARIFY | 173 | 0.3121 |
| S3 REFUSAL | 44 | 0.0909 |
| S5 NOCHEM | 40 | 0.0300 |

The scorer reports by slice id, so the Phase 9 buckets fold in: OFFTOPIC
items carry their source slice (S2, two in S1), the HARD constructed
items carry the slice of the row they were built from, and S1 combines
sourced and constructed DOSE items. The four rows sum to 500.

**S1 DOSE has the highest slice mean, and that is the single most
misleading number in this report.** No S1 item received a gradeable
dose; see section 3, mechanism 3.

### 2.4 Per-difficulty breakdown

| difficulty | n | mean total |
|---|---:|---:|
| standard | 320 | 0.4188 |
| hard | 107 | 0.4748 |
| edge_case | 73 | 0.0548 |

Hard outscoring standard is another artefact of the empty-answer
policy, not evidence the model handles range doses or multi-cause
queries: with `chemical_options = []` the hard content of an item is
never examined. The edge_case collapse is real, though: edge items are
dominated by S3 REFUSAL and S5 NOCHEM, where the gold answer requires a
specific refusal or a non-chemical recommendation, and the model
supplies neither.

### 2.5 Per-crop breakdown

| crop | n | mean total |
|---|---:|---:|
| cotton | 135 | 0.3837 |
| soybean | 68 | 0.3765 |
| onion | 53 | 0.3057 |
| tomato | 53 | 0.3962 |
| tur | 52 | 0.3115 |
| gram | 50 | 0.2240 |
| pomegranate | 44 | 0.5909 |
| grape | 35 | 0.5657 |
| rice | 4 | 0.0000 |
| maize | 3 | 0.0000 |
| wheat | 3 | 0.3333 |

Rice, maize and wheat are the out-of-scope crops used by the S3
"banned chemical on out-of-scope crop" bucket and the two mandatory S1
OFFTOPIC rows; they are not in-scope crops. Grape and pomegranate score
highest because their S1 items are almost entirely constructed DOSE
items (25 and 16 of their S1 totals), which again are graded on C4 only.
Gram is lowest among the in-scope crops; the per-item output should be
checked for whether its schema failure rate is higher than the others
before reading anything into it.

## 2a. Re-scored under the new rule — the official baseline

Same 500 raw responses, same `bench.jsonl`, same greedy decode. Only
`src/verify.py` moved (section 3a): in score mode, a schema-valid answer
with an empty `chemical_options` on an ANSWERABLE item now enters
C1_dose, C2_phi and C3_formulation as 0.0 misses. Re-scored 2026-09-12
from the regenerated Kaggle bundle, whose verify.py is byte-identical to
`src/verify.py`.

**The new-rule number, 0.1719, is the official baseline for all future
comparisons.** The old-rule 0.3776 is retained only as the record of what
the refusal artefact was worth.

### 2a.1 Headline

| metric | old rule | new rule |
|---|---:|---:|
| mean total score | 0.3776 | **0.1719** |
| items scoring 1.0 | 148 / 500 | **55 / 500** |

### 2a.2 Gates

Unchanged, as designed: gates are identical in every mode and the rule
touches only graded checks. G1_json 500/500; G2_schema 264/500 (52.8%);
G3–G9 264/264 (100%) on the items that reach them. See 2.1 for the full
table.

### 2a.3 Check means

| check | weight | old rule | new rule |
|---|---:|---:|---:|
| C1_dose | 0.30 | n = 0 | **0.0000 (n = 182)** |
| C2_phi | 0.25 | n = 0 | **0.0000 (n = 182)** |
| C3_formulation | 0.10 | n = 0 | **0.0000 (n = 182)** |
| C4_escalation | 0.15 | 0.8182 (n = 264) | 0.8182 (n = 264), unchanged |
| C5_causes_top1 | 0.10 | n = 0 | n = 0, unchanged |
| C6_non_chemical | 0.10 | 0.0000 (n = 94) | 0.0000 (n = 94), unchanged |

The 182 is the count of schema-valid responses on ANSWERABLE items, all
of which offered no chemical option. Every one of the 182 is a miss on
all three checks: the model never produced a gradeable dose, PHI or
formulation, and now the score says so. C5 stays at n = 0 because the
rule does not touch it: it is entered only when `likely_causes` is
non-empty, and the model never named a cause on a matched item.

### 2a.4 By slice

| slice | n | old rule | new rule |
|---|---:|---:|---:|
| S1 DOSE | 243 | 0.5333 | **0.1136** |
| S2 CLARIFY | 173 | 0.3121 | 0.3121 |
| S3 REFUSAL | 44 | 0.0909 | 0.0712 |
| S5 NOCHEM | 40 | 0.0300 | 0.0300 |

S2 and S5 are unchanged because their items are not ANSWERABLE (unknown
pest, or nothing registered), so the rule never fires. S3 moves only
slightly even though 27 of its 44 items (the REFUSAL_DOSE kind: a banned
chemical asked about on a pair that has registered legal chemistry) are
ANSWERABLE by the verifier's definition, so the rule fires on them; the
small drop shows nearly all 27 were already at 0.0 under the old rule
through schema failure or a mismatched escalation flag. S1 collapses from the top
slice to near the bottom, which is where a slice with zero gradeable
doses belongs.

### 2a.5 By difficulty

| difficulty | n | old rule | new rule |
|---|---:|---:|---:|
| standard | 320 | 0.4188 | **0.2136** |
| hard | 107 | 0.4748 | **0.1310** |
| edge_case | 73 | 0.0548 | 0.0489 |

### 2a.6 By crop

| crop | n | old rule | new rule |
|---|---:|---:|---:|
| cotton | 135 | 0.3837 | 0.1598 |
| soybean | 68 | 0.3765 | 0.1590 |
| onion | 53 | 0.3057 | 0.1544 |
| tomato | 53 | 0.3962 | 0.2174 |
| tur | 52 | 0.3115 | 0.1970 |
| gram | 50 | 0.2240 | 0.1633 |
| pomegranate | 44 | 0.5909 | **0.2401** |
| grape | 35 | 0.5657 | **0.1107** |
| rice | 4 | 0.0000 | 0.0000 |
| maize | 3 | 0.0000 | 0.0000 |
| wheat | 3 | 0.3333 | 0.3333 |

### 2a.7 Findings from the re-score

1. **The difficulty inversion is resolved.** Under the old rule hard
   (0.4748) outscored standard (0.4188). Under the new rule the ordering
   is standard > hard > edge_case (0.2136 > 0.1310 > 0.0489), which is
   the ordering a benchmark should show. The old inversion was entirely
   the refusal artefact: hard items are disproportionately S1 DOSE items
   (range doses, multi-cause), which is exactly where an empty answer
   used to be graded on C4 alone.

2. **The grape/pomegranate anomaly is resolved.** Grape fell from 0.5657
   to 0.1107 and pomegranate from 0.5909 to 0.2401. Both crops' S1 items
   are almost entirely constructed DOSE items, and every one of them was
   an empty answer scored on escalation only. There was no grape or
   pomegranate domain knowledge in the baseline; there was a crop mix
   that happened to maximise the artefact. The gram anomaly flagged in
   2.5 has also dissolved: gram is now mid-table at 0.1633.

3. **C4_escalation at 0.8182 is the only non-zero check, and it is
   trivially earned.** The score is genuine: the model's
   `escalate_to_expert` flag matched gold on 216 of 264 schema-valid
   items. But it is earned by a policy that escalates on nearly
   everything, on a benchmark where most items warrant escalation (every
   S2 CLARIFY, every S3 REFUSAL, every S5 NOCHEM and every S1 item with
   an unknown PHI). A model that always sets the flag would score about
   the same on C4. It is the whole of the 0.1719: with C1/C2/C3/C6 all
   at 0.0, the mean is C4's 0.15 weight spread over each item's
   denominator. Post-training, C4 must be read next to C1's mean, never
   alone; a model that learns dose and PHI but over-escalates should
   lose on C4 (the check is two-directional) and gain far more on C1/C2.

**Reading the official baseline.** 0.1719 is what a model scores for
producing valid schema roughly half the time, recommending nothing, and
guessing the escalation flag well. It contains no verified agronomy. The
trained model's first real test remains whether C1_dose acquires a
non-zero mean, not merely a non-zero n, and whether G2 approaches 100%.

## 3. Interpretation — the 0.3776 is not partial competence

**The number is the score of consistent unhelpfulness, not of domain
knowledge.** Three mechanisms, all visible in the tables above, account
for essentially all of it.

**Mechanism 1 — the model does not know the schema (236/500).** G2_schema
fails on 236 items because the untrained model invents its own JSON
layout instead of the frozen `Advisory` schema in `src/schema.py`. The
observed keys are `recommendation`, `pests`, `pre_harvest_interval` and
similar, where the schema requires `likely_causes`, `chemical_options`
and `phi_days` (nested under each `ChemicalOption`). A gate failure sets
total to 0.0 regardless of content, so these 236 contribute nothing.
Whatever agronomy is in those responses is invisible to the scorer and
was never verified.

**Mechanism 2 — the 264 that pass schema pass G3–G9 by refusing.** Every
one of the 264 schema-valid responses has `chemical_options = []` and
either declines or asks a clarifying question. With no chemical named,
there is no active ingredient for G4_restricted_ai to ban, no triple for
G5_triple_registered to look up, no PHI for G6 to check, no dose for G8
or G9 to examine. G3–G9 pass at 100% on this subset because they have
nothing to inspect, not because the model chose registered chemistry at
a label dose. This is the verifier working as designed (an empty
recommendation is trivially safe) and the model contributing nothing.

**Mechanism 3 — an empty answer on a DOSE item is graded on
C4_escalation alone.** `verify()` in score mode computes the total as
the weighted mean over the checks that were *entered* and falls back to
1.0 when none were (`total = num / den if den else 1.0`). C1, C2 and C3
are only entered per chemical option, and C5 only when `likely_causes`
is non-empty. An S1 DOSE response with an empty option list and no
causes therefore has exactly one weighted check in the denominator,
C4_escalation, and scores 1.0 or 0.0 on whether its
`escalate_to_expert` flag happens to match gold. That is the whole
explanation for S1 DOSE being the top slice at 0.5333, for hard
outscoring standard, and for grape and pomegranate leading the crop
table. The 148 items at 1.0 are, to a first approximation, the
schema-valid items whose escalation flag matched, on the slices where
C6 did not also apply.

This is a property of the "inapplicable checks leave the denominator"
rule (Phase 6 verifier design, section 2). That rule exists so a model is
never punished for a gap in label_db; here it also means a model is not
punished for declining to answer an answerable question. For the
baseline the effect is an inflated mean. For the trained model it is
something to watch: a model that learns to refuse S1 items would score
about as well on this metric as the baseline does, and better than a
model that answers with occasional dose errors. The S1 slice mean should
be read together with the C1 n, never alone. Whether score mode should
treat an empty option list on an ANSWERABLE item as a C1 miss was the
open question when this section was first written. It was decided the
same day, in favour of the change; section 3a records what changed and
what did not.

**The n = 0 checks are the decisive evidence.** C1_dose, C2_phi,
C3_formulation and C5_causes_top1 carry 0.75 of the graded weight
between them (`CHECK_WEIGHTS` in `src/verify.py`). They were applicable
on zero items. A model with any usable knowledge of CIB&RC label doses
would have produced at least one gradeable recommendation on the 243 S1
DOSE items. The baseline produced none. C6_non_chemical, the one check
that requires the model to *say* something specific, scored 0.0000 on
all 94 items where it applied.

Consequences for reading later results:

- The mean can rise substantially from schema compliance alone, with no
  change in agronomic quality. **Track G2 pass rate and the n on
  C1/C2/C3/C5 alongside the mean**, not the mean by itself.
- The trained model's first real test is whether C1_dose acquires a
  non-zero n *and* a high mean simultaneously. A high n with a low mean
  is the dangerous direction (confidently wrong doses); a persistent
  n = 0 means the model learned to refuse, not to advise.
- Per-slice, the honest comparison for S1 DOSE is against zero
  competence, whatever the slice mean reads in section 2.3.

### 3a. Scorer change made after this run (2026-09-11)

**Decision.** In `score` mode only, when all four of these hold, C1_dose,
C2_phi and C3_formulation are entered into the checks dict as 0.0 misses
instead of being left out of the denominator:

1. `mode == "score"`
2. the item is `expected_answerable` (answerability == ANSWERABLE)
3. the response passed G2_schema
4. `chemical_options` is empty

Implemented as `SCORE_REFUSAL_MISS_CHECKS` in `src/verify.py`, applied
after the graded checks and before `_result()`, with a failure line
"refusing an answerable question (score mode)". C4 and C6 are untouched:
they already run on every item. Non-answerable items (out-of-scope crop,
unknown pest, nothing registered) are untouched: there an empty option
list is the correct answer.

**What the change does to the shape in mechanism 3.** A schema-valid
refusal on an answerable item with a matching escalate flag went from
1.0 (C4 alone in the denominator) to about 0.19 (C4 = 1.0 over
C1+C2+C3+C4, or 0.17 where C6 also applies and is met). A refusal with a
mismatched flag stays at 0.0. Learning to refuse S1 items is now visibly
worse than the baseline, not equal to it.

**What did NOT change, and why.**

- **Gate mode is byte-identical.** Gate mode filtered the 5,629 Phase 8
  SFT examples; any movement would invalidate that dataset.
  `tools/phase10_gate_snapshot.py` was run once, against the pre-change
  verifier, to record gate-mode and filter-mode verdicts on every 5th
  benchmark item (100 items), each scored as its gold advisory and as
  that advisory with chemical_options and likely_causes emptied. That is
  400 verdicts, 54 items ANSWERABLE, saved to
  `tests/fixtures/phase10_gate_filter_snapshot.json`. A new test replays
  the same inputs and asserts every field of every verdict is equal.
  The fixture must not be regenerated to make the test pass.
- **Filter mode is unchanged.** At inference an empty answer is the safe
  outcome and must not be blocked.
- `schema.py`, `system_prompt.txt`, `bench.jsonl` and the SFT files are
  untouched.
- **The gate-mode counterpart of the finding exists and is left alone by
  decision.** The pre-change snapshot shows an emptied answer on an
  ANSWERABLE item passing gate mode with total 1.0 on 46 of 54 such
  items. That means a refusal on an answerable question was admissible
  as a Phase 8 training example. That is recorded here as a fact about
  the SFT filter, not changed, because changing it now would invalidate
  the dataset already built.

**Tests added** (`tests/test_verify.py`, suite 624 → 630, all passing):

| test | pins |
|---|---|
| `test_score_mode_empty_options_on_answerable_is_a_c1_c2_c3_miss` | the three misses are entered; every other check still scores 1.0, so the drop is entirely the rule; total is the weighted mean; score mode still passes on gates alone |
| `test_score_mode_empty_options_on_non_answerable_is_unaffected` (×3) | NO_REGISTERED_CHEMISTRY, PEST_UNKNOWN and OUT_OF_SCOPE_CROP enter no miss |
| `test_gate_and_filter_modes_ignore_the_score_mode_refusal_rule` | same refusal, same item: gate 1.0, filter 1.0, score lower |
| `test_gate_and_filter_modes_are_byte_identical_to_the_pre_phase10_snapshot` | 400 pre-change verdicts reproduced field for field |

**Bundle.** `kaggle_upload/verify.py` is the traced copy that
`tools/bundle_for_kaggle.py` produces. It was regenerated after the
change (20 files, 30,458,363 bytes) and `tools/smoke_test_kaggle_bundle.py`
passed standalone (three gold advisories at 1.0). The bundled verify.py
is byte-identical to `src/verify.py` and carries
`SCORE_REFUSAL_MISS_CHECKS`; the re-score in section 2a ran from it.

**Re-score.** Done 2026-09-12; both columns are in section 2a. The
post-training run is scored under the new rule only and compared to the
new-rule baseline column.

## 4. The failure mode the project exists to prevent

One sampled baseline response (an S1 DOSE item, schema-invalid, so it
scored 0.0 and would have been blocked in filter mode) recommended
**"Decis / permethrin" at "20 ml per litre"**. Both halves are wrong:

- Decis is a deltamethrin product, not permethrin. The model paired a
  trade name with the wrong active ingredient.
- "20 ml per litre" does not correspond to any CIB&RC label dose for
  either molecule on any of the eight in-scope crops; it is a
  hallucinated figure. Deltamethrin 2.8% EC label doses are in the order
  of tens of ml per acre in hundreds of litres of water, roughly two
  orders of magnitude below what was recommended.

This is exactly the behaviour the label_db, the verifier and the filter
mode were built to stop: a fluent, specific, confidently phrased
recommendation with a wrong molecule and a wrong number. It was caught
here only because the response also failed G2. A schema-valid version of
the same answer is what G4/G5/C1 exist for, and it is the case the
trained model must be measured against.

## 5. Next

- Committed as `phase 10: baseline 0.1719 (re-scored), score-mode
  refusal-miss rule, gate/filter pinned by snapshot`.
- Keep the raw scorer output alongside this report so the per-item
  scores can be diffed against the post-training run.
- Phase 10 Step B: train, re-run the identical configuration (greedy,
  1200 tokens, same bench file), and report G2 pass rate and C1 n before
  the mean.
- The scorer decision, bundle regeneration and re-score are all done
  (sections 2a and 3a). Compare every Step B number against section 2a,
  never section 2.
