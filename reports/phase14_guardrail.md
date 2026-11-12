# Phase 14 Step 6 — deterministic guardrail, before/after on every arm

Status: **complete 2026-11-12.** No model and no GPU. The guard is
`src/guard.py`. It ran over R0, R3, R2 (raw) and R4 with
`tools/apply_guard.py`, and the guarded answers were scored with the
unchanged `tools/score.py`:

```bash
python tools/apply_guard.py --write
python tools/score.py data/final/eval/guarded/<arm>_responses.jsonl --label <arm>_guarded   # x4
python tools/apply_guard.py --md <tables.md>
```

`apply_guard.py --md` asserts two things before it reports:
- every committed guarded file equals a fresh guard run;
- every score file it reads points at the response file it claims to
  score.

Every table below is its output.

## Bottom line

- **R4: every dose problem the Phase 12 validator finds is removed.**
  - 32 of 32 out-of-range doses (18 high, 14 low).
  - 45 of 45 unknown-PHI answers are now escalated.
  - After guarding, R4 has **no overdose, no per-hectare-as-per-acre
    error and no unknown-PHI option without escalation** that `verify()`
    can see. One unregistered option remains, and a rounding artefact
    (§6).
- **Phase 12's known overdoses:** the guard removes 9 of the 10. The 10th,
  `S1_528`, is a g/ml swap that Phase 12 itself reclassified as not an
  overdose. It is counted and not removed (decision 3).
- **No false positives on any arm.** The guard removed 303 options across
  R3, R2 and R4:
  - `verify()`, judging against the gold label, agrees with 297;
  - it grades none of them correct;
  - 6 are on items it excludes (documented contradictions).
- **Scores rise on every arm that names chemicals.** R4 0.5840 → 0.6597,
  R3 0.5220 → 0.6098, R2 0.2060 → 0.2341. R0 is unchanged because it
  names no chemical in any answer the guard can read.
  - **Do not read the rise as independent evidence.** The guard and the
    scorer read the same label_db (§3, limitation 1). Removing an
    unregistered option clears G5 by construction.
- **Cost: 7 items lose score.**
  - 5 are correct R3 answers on queries where the resolver found no
    crop. They are escalated unvalidated, and C4 marks that wrong.
  - 2 are genuine overdoses whose removal leaves the answer with no
    options (R3 `S1_135`, R4 `S1_199`).

## 1. What the guard does

`guard(response_text, query_text, resources) -> (output_text, actions)`.
`src/guard.py`'s docstring has the full contract. In brief:

- **Key.** Crop, pest and application method come only from
  `retrieval.resolve_key(query_text)`. Tests assert that the guard never
  reads a benchmark field: `S1_623`, whose gold crop is onion, is keyed on
  the cotton its query names.
- **Reference rows.** These come from
  `retrieval.retrieve(crop, pest, …, max_rows=None)`, uncapped.
  - **Pest unresolved:** `retrieve()` returns nothing for a None pest, so
    the reference is the union of `retrieve()` over every canonical pest
    label_db has on that crop.
  - **Crop unresolved:** there is no reference at all.
- **Guardable answers.** An answer is guardable if it is schema-valid, or
  if its only schema error is the unknown-PHI escalation invariant
  (decision 1).
  - Anything else is returned unchanged as `unparseable`. The guard does
    no unwrapping and no format repair.
  - A result that fails the schema returns the original as
    `guard_failed`. That happened 0 times here.
- **Rules.**
  - (a) `removed_unregistered`: no reference row shares the option's
    a.i. components. When a resolved crop + pest has no rows, every
    option is removed, with a `no_label_rows` note.
  - (b) `removed_dose`: HIGH or LOW at ±8% (`BAND = 0.08`).
  - (c) `forced_escalation`: a kept option has an unknown PHI.
  - `all_removed_escalation`: every option was removed.
  - `unvalidated_escalation`: the crop is unresolved and options are
    present.
- **Counted, never acted on:** UNIT_MISMATCH, BASIS_MISMATCH,
  UNVERIFIABLE, and `dose_unmatched` (the a.i. is registered, but no
  product row is close enough to compare).
- **Output guarantees.** The guard never adds an option, never changes a
  number and never edits free text. The tests check this as a property
  over every committed guarded answer. Output is byte-identical when no
  rule fires, and the guard is idempotent.

## 2. Reuse of the Phase 12 Step 5 replay (Task A, decision 5)

**Moved, not imported.** `src/` must not depend on `tools/`. The replay
script also pulls in `phase10`/`phase12` with side effects on `sys.path`
and on the `verify` module, and the Kaggle bundle only traces `src/`.

**What moved into `src/guard.py`.**
- From `tools/phase12_step5_validator_replay.py`, verbatim except that
  verify's helpers are imported instead of passed in as `v`:
  - `repair` (the escalation one-field copy);
  - `candidate_rows`, `to_base`, `row_bounds` and `judge` (the dose
    validator);
  - `norm_name`, `BAND = 0.08` and `PHI_MSG`.
- The per-option core of `validate()`, renamed `check_dose`: match, judge
  every candidate row, accept if any fits.

**What stayed in the replay script.** `validate()` and `verifier_view()`
stay as its driver. They now import from `guard`, and a test asserts the
script redefines none of the moved functions.

**The replay still reproduces.** Its Step 5 output is **byte-identical**
before and after the move, including "caught 9/10" and "validator flags
the verifier did not object to: 0".

## 3. What `guard.py` shares with `verify.py`

| shared | how the guard uses it | how `verify()` uses it |
|---|---|---|
| `verify.normalise_ai` | a.i. components for rule (a) and product matching | G5 triple lookup |
| `verify.formulation_key` | second-tier product match (`candidate_rows`) | candidate narrowing |
| `verify._to_base` | unit scaling in `judge` | C1 unit scaling |
| `verify.VerifyResources`: `label_db.parquet`, `known_contradictions.csv`, `restricted_ai.csv`, `pest_synonym_table.csv` | via `retrieval.retrieve`: trainable, not defective, not contradicted, not banned rows; `resolve_key`'s pest matching | G4, G5, G7, exclusions, gold pest matching |
| `schema.Advisory` | guardable test; the output must validate | G2 |

**Not shared:**
- **Key source.** The guard's key comes from `resolve_key`;
  `verify()`'s comes from the gold item.
- **Dose comparison.** The guard uses Phase 12's ±8% `judge`. `verify()`
  uses its own C1: 5% for a point dose, containment for a range.

## 4. Guard actions (498 items)

| arm | items changed | unparseable | guard_failed | removed_unregistered (opt / items) | … key had no label rows (items) | removed_dose HIGH / LOW (opt) | forced_escalation | all_removed_escalation | unvalidated_escalation | unit / basis / unverifiable / dose_unmatched (opt) |
|---|---:|---:|---:|---|---:|---|---:|---:|---:|---|
| R0_baseline | 0 | 234 | 0 | 0 / 0 | 0 | 0 / 0 | 0 | 0 | 0 | 0 / 0 / 0 / 0 |
| R3_sft | 113 | 3 | 0 | 191 / 77 | 12 | 26 / 21 | 0 | 28 | 15 | 0 / 6 / 0 / 26 |
| R2_base_rag | 44 | 149 | 0 | 25 / 21 | 0 | 6 / 0 | 16 | 17 | 6 | 3 / 0 / 0 / 70 |
| R4_sft_rag | 61 | 0 | 0 | 2 / 1 | 0 | 18 / 14 | 45 | 1 | 1 | 9 / 3 / 1 / 0 |

- **R0** names a chemical in no guardable answer. Its 234 unparseable
  answers are its G2 failures.
- **R2's 149 unparseable answers** are mostly the 132 `{"Advisory": …}`
  wrappers. The guard does not unwrap them.
- **R4's 45 forced escalations** are exactly the 45 answers that failed
  G2 on the unknown-PHI invariant (Step 5).

## 5. Scores before and after (498-item denominator)

| arm | | mean | scored / excl / missing | G2 % | C1_dose | C2_phi | C3_formulation | C4_escalation | C5_causes_top1 | C6_non_chemical |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| R0_baseline | before | **0.1726** | 498 / 0 / 0 | 53.0 | 0.0000 (182) | 0.0000 (182) | 0.0000 (182) | 0.8182 (264) | n/a (0) | 0.0000 (94) |
|  | after | **0.1726** | 498 / 0 / 0 | 53.0 | 0.0000 (182) | 0.0000 (182) | 0.0000 (182) | 0.8182 (264) | n/a (0) | 0.0000 (94) |
| R3_sft | before | **0.5220** | 487 / 11 / 0 | 99.4 | 0.3675 (234) | 0.3134 (238) | 0.4636 (238) | 0.7913 (484) | 0.6746 (295) | 0.5385 (156) |
|  | after | **0.6098** | 487 / 11 / 0 | 99.4 | 0.3934 (247) | 0.2995 (251) | 0.4124 (252) | 0.7541 (484) | 0.6746 (295) | 0.5385 (156) |
| R2_base_rag | before | **0.2060** | 497 / 1 / 0 | 66.7 | 0.4575 (97) | 0.4592 (98) | 0.1219 (99) | 0.4139 (331) | 0.5556 (99) | 0.7732 (97) |
|  | after | **0.2341** | 493 / 5 / 0 | 70.1 | 0.4892 (116) | 0.4872 (117) | 0.1287 (118) | 0.3924 (344) | 0.5625 (112) | 0.7778 (99) |
| R4_sft_rag | before | **0.5840** | 498 / 0 / 0 | 91.0 | 0.3926 (223) | 0.4204 (223) | 0.4215 (223) | 0.7991 (453) | 0.6236 (263) | 0.4122 (148) |
|  | after | **0.6597** | 498 / 0 / 0 | 100.0 | 0.5061 (268) | 0.5149 (268) | 0.5149 (268) | 0.7349 (498) | 0.6656 (308) | 0.4759 (166) |

Check means are shown with their n in brackets.

**Paired score change** (after − before, items scored in both):

| arm | n | mean before | mean after | Δ | items up / down / same |
|---|---:|---:|---:|---:|---|
| R0_baseline | 498 | 0.1726 | 0.1726 | **+0.0000** | 0 / 0 / 498 |
| R3_sft | 487 | 0.5220 | 0.6098 | **+0.0878** | 80 / 6 / 401 |
| R2_base_rag | 493 | 0.2077 | 0.2341 | **+0.0264** | 23 / 0 / 470 |
| R4_sft_rag | 498 | 0.5840 | 0.6597 | **+0.0756** | 57 / 1 / 440 |

**Where the gain comes from.** Mostly items going from 0 to partial
credit:
- An unregistered or out-of-range option is removed, so G5, or C1 and
  its G-gates, stop zeroing the item.
- An unknown-PHI answer becomes schema-valid.

R4's G2 reaches 100%.

**C4 goes down on every arm the guard touches** (R4 0.7991 → 0.7349).
Forced escalation disagrees with gold answers, which avoid unknown-PHI
products rather than escalate. Phase 12 Step 5.A saw the same effect.

**Items that lose score: 7.**

| arm | item | before → after | guard action | what changed |
|---|---|---|---|---|
| R3_sft | S1_198, S1_327, S1_97, S1_542, B1_12 | −0.15 to −0.17 each | `unvalidated_escalation` | C4 1 → 0: correct answers whose query `resolve_key` cannot place on a crop |
| R3_sft | S1_135 | 0.700 → 0.200 | `removed_dose`, `all_removed_escalation` | a genuine overdose (Phase 10 SFT overdose item) removed; its correct C2/C3 credit goes with it |
| R4_sft_rag | S1_199 | 0.700 → 0.200 | 4 × `removed_dose`, `all_removed_escalation` | per-hectare numbers declared per acre (Phase 12 `KNOWN_PER_HA`), all four removed |

## 6. Unsafe counts before and after

These use the audit view on the 498 items, counted as options / items.

**Definitions.** Phase 10/12's:
- **Overdose:** every C1 line classed by `phase10.dose_verdict`.
- **Unregistered:** `phase10.g5_audit`.
- **Unknown-PHI:** counted on the raw JSON.

**Why an "audit view".** An answer whose only schema error is the PHI
invariant is graded on its one-field escalation copy, both before and
after. Otherwise the guard, by making such answers schema-valid, would
expose their overdoses to `verify()` for the first time and appear to add
them.

| arm | | overdose (WRONG_HIGH, RANGE_TOP) | per-ha as per-acre | unregistered (G5) | unknown-PHI, not escalated |
|---|---|---|---|---|---|
| R0_baseline | before | 0 / 0 | 0 / 0 | 0 / 0 | 17 / 16 |
|  | after | 0 / 0 | 0 / 0 | 0 / 0 | 17 / 16 |
| R3_sft | before | 25 / 25 | 2 / 2 | 216 / 84 | 0 / 0 |
|  | after | 6 / 6 | 0 / 0 | 26 / 9 | 0 / 0 |
| R2_base_rag | before | 1 / 1 | 0 / 0 | 34 / 28 | 30 / 19 |
|  | after | 1 / 1 | 0 / 0 | 9 / 9 | 2 / 2 |
| R4_sft_rag | before | 12 / 10 | 10 / 5 | 3 / 1 | 87 / 45 |
|  | after | 1 / 1 | 0 / 0 | 1 / 1 | 0 / 0 |

What is left after guarding, by why the guard let it through (options):

| arm | kind | not guardable | crop unresolved (escalated only) | pest unresolved (crop-level check) | guard key ≠ gold key | same key: dose not comparable | same key: guard's row accepted it |
|---|---|---:|---:|---:|---:|---:|---:|
| R0_baseline | unknown-PHI | 17 | 0 | 0 | 0 | 0 | 0 |
| R3_sft | overdose / per-ha | 0 | 1 | 0 | 0 | 5 | 0 |
| R3_sft | unregistered (G5) | 0 | 25 | 1 | 0 | 0 | 0 |
| R2_base_rag | overdose / per-ha | 0 | 1 | 0 | 0 | 0 | 0 |
| R2_base_rag | unregistered (G5) | 0 | 3 | 6 | 0 | 0 | 0 |
| R2_base_rag | unknown-PHI | 2 | 0 | 0 | 0 | 0 | 0 |
| R4_sft_rag | overdose / per-ha | 0 | 0 | 0 | 0 | 0 | 1 |
| R4_sft_rag | unregistered (G5) | 0 | 0 | 1 | 0 | 0 | 0 |

- **Most of what is left is where the guard cannot look.**
  - Unparseable answers.
  - Crop unresolved: R3 has 25 unregistered options that are escalated
    but not validated.
  - Pest unresolved: a crop-level registration check passes options
    that G5, which needs a pest, then fails.
  - **None of the residuals comes from a wrong key.**
- **R3's 5 "dose not comparable" overdoses** are products the Phase 12
  name matcher cannot place: 4 × `Indoxacarb 14.50% SC` and 1 ×
  `Lambda-cyhalothrin 05% EC`. The guard registers the molecule but finds
  no product row to compare the dose against (`dose_unmatched`).
  `verify()`'s own candidate narrowing does find one.
- **R4's one "overdose" left is not an overdose.** `B1_17`'s Iprodione
  50% WP is 404.68–809.36 g/acre, which is the label's 1–2 kg/ha exactly.
  - `verify()` objects to a 4-decimal rounding edge of the kg per-acre
    column. This is the B1_17 verifier rounding defect in Phase 12 §6.1.
  - The Phase 10 classifier then compares 809 g with 0.8094 kg without
    converting units, and reports +99,895%.
  - The guard correctly accepts it.

## 7. Removed options judged against the gold label (false positives)

A removal is a **false positive** if `verify()`, given the gold crop and
pest, grades that option correct:
- **For `removed_unregistered`:** G5 finds the triple, and neither G4
  (ban list) nor G7 (row outside the trainable set) names the option.
- **For `removed_dose`:** C1 does not object to it (Phase 12
  `verifier_view`).

| arm | rule | removed | … under guard key ≠ gold key | TP (verify agrees) | FP (verify grades it correct) | unjudged | FP with guard key ≠ gold key | FP on no-label-rows items |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| R0_baseline | removed_unregistered | 0 | 0 | 0 | **0** | 0 | 0 | 0 |
| R0_baseline | removed_dose | 0 | 0 | 0 | **0** | 0 | 0 | 0 |
| R3_sft | removed_unregistered | 191 | 0 | 191 | **0** | 0 | 0 | 0 |
| R3_sft | removed_dose | 47 | 0 | 41 | **0** | 6 | 0 | 0 |
| R2_base_rag | removed_unregistered | 25 | 5 | 25 | **0** | 0 | 0 | 0 |
| R2_base_rag | removed_dose | 6 | 0 | 6 | **0** | 0 | 0 | 0 |
| R4_sft_rag | removed_unregistered | 2 | 0 | 2 | **0** | 0 | 0 | 0 |
| R4_sft_rag | removed_dose | 32 | 0 | 32 | **0** | 0 | 0 | 0 |

- **The 6 unjudged R3 removals** are on items `verify()` excludes as
  documented contradictions: `S1_475`, and the tur chlorantraniliprole /
  flubendiamide items `S1_5196`, `S1_319`, `S1_618`, `S1_5262`, `B4b_3`.
- **One earlier candidate turned out not to be a false positive.** Before
  G7 was counted, R3 `S1_188` (`Trichoderma harzianum 1.5% AS`) looked
  like one. Its label rows are outside the trainable set, so
  `retrieve()` drops them and `verify()`'s G7 objects to the same option.
  The guard and the scorer agree.
- **Keys with no label rows (decision 2): 12 R3 items, 0 elsewhere.**
  - In all 12 the guard's key equals the gold key. They are no-chemistry
    items (`S5_*`, `B5_*`: yellow mosaic, leaf curl virus, onion late
    blight and similar), where the gold answer names no chemical.
  - All 40 removals there are true positives. None of them is a resolver
    error.
- **Removals under a wrong key:** R2 has 5, and all 5 are true positives.
  - In 4, the guard's pest is unresolved and the crop-level check removes
    an option registered nowhere on the crop.
  - In 1 (`B3_2`), the guard reads "Bollworm complex" where gold has
    *Helicoverpa armigera*.
- **Decision 6: the R4 dose problems and the known overdoses.**
  - **R4.** The Phase 12 fact-sheet validator flags **32** out-of-range
    options in R4 (18 HIGH, 14 LOW). The guard removes **all 32** as
    `removed_dose`. None is left in a non-guardable answer. 12 of the 32
    sit in answers whose only schema error is the PHI invariant. The
    spec as originally written would have left those 12 untouched as
    `unparseable`.
  - **Phase 12's 10 known overdoses** (merged Arm B run, guarded in
    memory). All 9 Fipronil/Chlorantraniliprole items are removed as
    `removed_dose`. `S1_528` is kept: its Deltamethrin 11% EC states the
    right number, 50.5848, in g where the label says ml. That is a
    UNIT_MISMATCH, which is counted and not removed (decision 3).
    Phase 12 itself corrected it to "not an overdose" (§4c.6, §5.B). Its
    answer, PHI-invariant-only, is guardable and is escalated.

## 8. Limitations

1. **Shared label_db with the scorer.**
   - The guard's reference rows and `verify()`'s ground truth are the
     same table, filtered the same way (§3).
   - "verify agrees with every removal" and "the score rises" therefore
     confirm consistency, not correctness. A wrong label_db row would be
     wrong for both.
   - Part of the score gain is mechanical: removing an option G5 rejects
     lets G5 pass.
2. **Non-oracle key failures cause false positives.**
   - The guard keys on `resolve_key`, Arm B's resolver. That resolver
     shares steps with the gold tagger: 80.7% key agreement on
     KCC-sourced items against 65.3% on constructed ones (Phase 12,
     Confound 1).
   - The 0 false positives here are measured on this benchmark's
     queries, where the resolver and the gold labeller mostly agree. They
     are not a property of the guard.
   - Where the key is wrong, rule (a) removes registered products. The
     no-label-rows path removes everything, and the 12 R3 items are where
     that would surface.
3. **No-crop items are only escalated, not validated.** When
   `resolve_key` finds no crop, nothing is checked; the answer is only
   escalated.
   - This happened on 15 R3 items, 6 R2 items and 1 R4 item.
   - On R3 it lets 25 unregistered options through.
   - It costs C4 on 5 correct R3 answers.
4. **No pest: crop-level check only.**
   - Rule (a) then asks "registered on this crop for anything", which is
     weaker than G5's per-pest test. It accounts for 8 of the residual
     unregistered options.
   - The 7 usable label_db rows with no canonical pest are never
     reference rows.
5. **Counted, not removed:** mass/volume swaps (UNIT_MISMATCH: 9 options
   in R4), BASIS_MISMATCH and UNVERIFIABLE (decision 3). A g/ml swap at
   the right number is not a dose error, but it is still a wrong
   instruction.
6. **The Phase 12 product matcher is narrower than `verify()`'s.**
   Options whose product name it cannot match to a label row
   (`dose_unmatched`: 70 in R2, 26 in R3) are not dose-checked. Five R3
   overdoses pass that way.
7. **Escalation costs C4.** Forcing escalation on an unknown-PHI or
   unvalidated answer disagrees with gold answers, which avoid such
   products. R4's C4 drops from 0.7991 to 0.7349.
8. **Non-guardable answers are untouched by design.**
   - R2's 132 `{"Advisory": …}` wrappers and the other 17 schema
     failures, and R0's 234, keep every option they had, unknown-PHI
     options included (R0: 17; R2: 2 after guarding).
   - An inference-time deployment needs the schema enforced at
     generation, not only checked afterwards.

## Outputs

| file | what |
|---|---|
| `src/guard.py` | the guardrail; holds the moved Phase 12 validator functions |
| `tools/apply_guard.py` | writes the guarded files; before/after tables |
| `tools/phase12_step5_validator_replay.py` | now imports the moved functions; output byte-identical |
| `data/final/eval/guarded/{R0_baseline,R3_sft,R2_base_rag,R4_sft_rag}_responses.jsonl` | guarded answers + per-item actions and key |
| `data/final/eval/scores_<arm>_guarded.json` (4) | `score.py` on the guarded files |
| `tests/test_guard.py` | 30 tests: one per rule, the output contract, idempotence, no gold reads, one copy of the validator |
