# Phase 12 Step 4 — Arm B scored: baseline / SFT / SFT+RAG(B)

Status: **scored 2026-10-21; Step 4b the same day (Arm B scores and the
re-run list saved, Phase 10's overdose count corrected); Step 4c on
2026-10-25 (three generation passes merged and re-scored — see the next
section, which supersedes the Step 4 headline); Steps 5 and 6 the same day
(offline validator replay; rounding defect scoped and two wrong dose
numbers traced to the training data — with corrections to 4c.6 and 4c.7). No
existing input was modified: `verify.py`, `retrieval.py`,
`generate_sft.py`, `crop_mapper.py`, `bench.jsonl`, both prompt files and
all response and score files are untouched. Committed in Step 7
(2026-10-25), together with the Phase 10 amendments.**

Reproduced by `python tools/phase12_stepA_score_rag.py --md <out.md>`
(Step 4, the 1,200-token run) and
`python tools/phase12_step4c_merge_score.py --md <out.md>` (Step 4c, the
merge). Both import `src/verify.py` read-only, reuse the Phase 10 audit's
scoring convention, dose classifier and G5 classifier
(`tools/phase10_stepB_audit.py`), and assert the reproductions before they
score Arm B.

**Bottom line (Step 4c — supersedes Step 4).** With the 75 cut-off answers
regenerated to completion and merged, SFT+RAG(B) scores **0.6143 against
SFT's 0.5467 on the same 448 items (+0.0675)**: 93 items up, 53 down, 302
unchanged. **The Step 4 headline of −0.0024 was the token limit, not
retrieval.** The limit cost −0.0700; removing it moves Arm B from 0.5443 to
0.6143.

Two model behaviours still hold the merged score down:

- **Unknown PHI without escalation (new).** 44 merged answers fail G2 for
  one reason: they list a product whose PHI is unknown and do not set
  `escalate_to_expert`. 84 of the 85 such options are faithful copies of a
  sheet row that has no PHI. 40 of the 44 are regenerated answers, because
  listing every sheet row pulls in the PHI-less rows. Of the 72 regenerated
  headline items, the 33 that pass G2 score **0.9497**; the 39 that fail
  score 0. SFT produced 5 answers like this and escalated on all 5.
- **Dose copying.** Arm B overdoses less often than SFT (9 items against
  24; 9.3% of graded answering items against 15.1%), but **every one of
  its 9 is a 10× decimal shift**. 8 are Fipronil 80% WG on onion at
  303.509 g/acre where the fact sheet shows 30.3509, which is 8 of the 10
  times the model wrote that product.

**Step 5 (offline, no model) shows both failures can be caught.**
- **Escalation repair.** Repairing the escalation flag on a copy of the
  44 answers would raise the 448 headline to **0.6925** (*repaired, not
  model output*). 41 of those 44 then lose C4, because the gold answers
  avoid PHI-unknown products rather than escalate.
- **Fact-sheet validator.** A ±8% dose check against the sheet catches
  all 9 genuine overdoses and every per-hectare-as-per-acre error, with
  **no false positives against `verify`**. It also checks the 506 options
  `verify` never grades.

The comparison is still confounded (section 9): retrieval keyed the same
way as the gold labels, an input shape the adapter never trained on, and
now an unmeasured run-to-run noise floor.

**Step 4 result on the 1,200-token run (superseded, kept for audit).** On
the like-for-like headline set, SFT+RAG(B) scored **0.5443 against SFT's
0.5467 (−0.0024)**. Item by item, 69 improved, 68 got worse and 311 were
unchanged. The flat number hid two effects pulling in opposite directions:

- **Where Arm B finishes an answer, it is much better grounded.** Items
  failing G5 fall from 85 to 2, and one of the 2 is a bench defect. PHI
  failures fall from 52 items to 1, dose failures from 47 to 12, and
  exclusions from 11 to 0. Paired on items both arms graded, C1 rises by
  +0.069 and C2 by +0.106.
- **75 Arm B generations (15%) hit the 1,200-token generation cap
  mid-JSON** and score 0.0 under G1. The SFT run had 2. In those 75 the
  adapter was listing 5 to 9 options copied from the fact sheet; SFT almost
  never lists more than 4. Non-chemical advice (C6) also falls by −0.135
  paired.

The result is confounded three ways (section 9) and does not yet measure
what retrieval is worth.

**Two corrections to earlier phases** came out of this work:

- **Phase 10 undercounted the SFT run's overdoses.** Its "5 genuine
  overdoses" is right only under its own rule, which read dose objections
  only on items whose C1 score was exactly 0.0. Reading every C1 line, the
  same classifier finds **24 items**.
- **The 15-row cap is not alphabetical.** The rows are in label_db document
  order, so the "alphabetical-order cost" asked about in task 8 is really a
  document-order cost (section 8).

## Step 4c — three generation passes merged and re-scored (2026-10-25)

Sections 0 to 10 below are the Step 4 analysis of the 1,200-token run and
are kept as the record. **Where they disagree with this section, this
section is current.**

### 4c.0 Integrity

| pass | file | max_new_tokens | rows | parse | `__ERROR__` |
|---:|---|---:|---:|---:|---:|
| 1 | `rag_B_responses.jsonl` | 1,200 | 500 | 425 | 0 |
| 2 | `rag_B_rerun_responses.jsonl` | 2,048 | 75 | 36 | 0 |
| 3 | `rag_B_rerun3_responses.jsonl` | 3,072 | 39 | 39 | 0 |

- **Nesting holds exactly.** Pass 3's 39 ids are pass 2's non-parsing
  ids, and pass 2's 75 are pass 1's non-parsing ids; pass 1 is the 500
  bench items. Every pass used the same prompts: `prompt_tokens` and
  `fact_sheet_rows` match `rag_prompts_B.jsonl` on every row.
- **No item has identical responses in two passes** (0/75 for pass 1 vs 2,
  0/39 for 1 vs 3 and for 2 vs 3). That is expected, since each later pass
  ran longer.
- **Pass 3 never hit its limit.** Its output ran 2,058 to 2,918 tokens.

**The merge.** `data/final/eval/rag_B_merged_responses.jsonl` holds 500
rows with 500 unique ids, and every response parses. Each item takes its
response from the highest pass in which it appears and parses: **425 from
pass 1, 36 from pass 2, 39 from pass 3.** Every row records
`source_pass` and `max_new_tokens`, plus `output_tokens` where that
generation run recorded it (passes 2 and 3).

**Harness unchanged.**
- `trained_scores.json` reproduces field for field (0 differing items),
  with the mean over the 489 non-excluded at 0.520319.
- Re-scoring pass 1 reproduces `rag_B_scores.json` field for field on all
  500.
- The 425 pass-1 answers score identically in the merge.
- Per-item scores are in `data/final/eval/rag_B_merged_scores.json`, in
  `trained_scores.json`'s schema.

### 4c.1 Headline: four columns

| item set | n | baseline | SFT | RAG-B (1200) | RAG-B (merged) | Δ merged−SFT | Δ merged−1200 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **448-item headline set (as before)** | **448** | **0.1824** | **0.5467** | **0.5443** | **0.6143** | **+0.0675** | **+0.0700** |
| non-excluded in all four | 489 | 0.1723 | 0.5203 | 0.5138 | 0.5779 | +0.0576 | +0.0641 |
| all 500, recorded totals | 500 | 0.1719 | 0.5249 | 0.5166 | 0.5813 | +0.0564 | +0.0647 |
| all 500, excluded scored 0.0 | 500 | 0.1719 | 0.5089 | 0.5166 | 0.5813 | +0.0724 | +0.0647 |

- **The 448 is still like-for-like.** The merged run has 0 exclusions, so
  the set is the same as before.
- **Items at 1.0:** baseline 55, SFT 210, RAG-B (1200) 212, RAG-B (merged)
  234.
- **Items at 0.0:** 256, 125, 132 and 100 respectively.
- **Paired, merged against SFT:** 93 items up, 53 down, 302 equal.
- **Every denominator gives the same answer:** merged Arm B is between
  +0.056 and +0.072 above SFT.

**Only the regenerated items changed:**

| 448 headline | n | baseline | SFT | RAG-B (1200) | RAG-B (merged) | Δ merged−SFT |
|---|---:|---:|---:|---:|---:|---:|
| not regenerated (pass 1) | 376 | 0.1895 | 0.5644 | 0.6486 | 0.6486 | +0.0842 |
| regenerated, all | 72 | 0.1453 | 0.4545 | 0.0000 | 0.4353 | −0.0193 |
| … from pass 2 (2,048) | 35 | 0.1619 | 0.4643 | 0.0000 | 0.6097 | +0.1454 |
| … from pass 3 (3,072) | 37 | 0.1295 | 0.4453 | 0.0000 | 0.2703 | −0.1750 |
| … regenerated, G2 passes | 33 | 0.1528 | 0.5117 | 0.0000 | **0.9497** | +0.4380 |
| … regenerated, G2 fails (unknown PHI, not escalated) | 39 | 0.1389 | 0.4062 | 0.0000 | **0.0000** | −0.4062 |

Step 4 bounded the merged result at +0.0842, on the assumption that the
regenerated items would score like the rest. They did not. Completed, they
average 0.4353, slightly below SFT on the same items, because more than
half fail G2 (4c.4). The realised gain is +0.0675.

### 4c.2 G1, and how much of −0.0024 was the token limit

| G1_json | baseline | SFT | RAG-B (1200) | RAG-B (merged) |
|---|---:|---:|---:|---:|
| all 500 | 500/500 (100%) | 498/500 (99.6%) | 425/500 (85.0%) | **500/500 (100%)** |
| 448 headline | 448/448 (100%) | 446/448 (99.6%) | 376/448 (83.9%) | **448/448 (100%)** |

**All of it, and more.** On the 448:

  RAG-B (1200) − SFT = −0.0024
  = (RAG-B (merged) − SFT, **+0.0675**) + (RAG-B (1200) − RAG-B (merged), **−0.0700**)

The token limit cost 0.0700. The +0.0675 that remains is the change
attributable to giving the adapter a fact sheet. It still carries the
section 9 confounds: gold-aligned keys and input-shape novelty.

### 4c.3 Gates and checks, four columns (all 500)

| gate | baseline | SFT | RAG-B (1200) | RAG-B (merged) |
|---|---:|---:|---:|---:|
| G1_json | 500/500 (100.0%) | 498/500 (99.6%) | 425/500 (85.0%) | 500/500 (100.0%) |
| G2_schema | 264/500 (52.8%) | 497/498 (99.8%) | 421/425 (99.1%) | **456/500 (91.2%)** |
| G3_empty_when_not_answering | 264/264 | 497/497 | 421/421 | 456/456 |
| G4_restricted_ai | 264/264 | 497/497 | 421/421 | 456/456 |
| G5_triple_registered | 264/264 | 412/497 (82.9%) | 419/421 (99.5%) | 453/456 (99.3%) |
| G6_unknown_phi_escalates | 264/264 | 485/486 (99.8%) | 421/421 | 456/456 |
| G7_trainable_row | 264/264 | 485/486 (99.8%) | 421/421 | 456/456 |
| G8_dose_basis | 264/264 | 477/486 (98.1%) | 420/421 (99.8%) | 454/456 (99.6%) |
| G9_unstated_dose_earned | 264/264 | 486/486 | 421/421 | 456/456 |

| check | weight | baseline | SFT | RAG-B (1200) | RAG-B (merged) | Δ merged−SFT |
|---|---:|---|---|---|---|---:|
| C1_dose | 0.30 | 0.0000 (n=182) | 0.3660 (n=235) | 0.2884 (n=190) | 0.3897 (n=224) | +0.0238 |
| C2_phi | 0.25 | 0.0000 (n=182) | 0.3121 (n=239) | 0.3145 (n=190) | 0.4185 (n=224) | +0.1065 |
| C3_formulation | 0.10 | 0.0000 (n=182) | 0.4616 (n=239) | 0.3158 (n=190) | 0.4196 (n=224) | −0.0420 |
| C4_escalation | 0.15 | 0.8182 (n=264) | 0.7901 (n=486) | 0.7862 (n=421) | 0.8004 (n=456) | +0.0103 |
| C5_causes_top1 | 0.10 | n=0 | 0.6768 (n=297) | 0.5714 (n=231) | 0.6241 (n=266) | −0.0527 |
| C6_non_chemical | 0.10 | 0.0000 (n=94) | 0.5443 (n=158) | 0.3178 (n=129) | 0.4172 (n=151) | −0.1271 |
| C5_causes_top3 | — | n=0 | 0.7205 (n=297) | 0.6104 (n=231) | 0.6579 (n=266) | −0.0626 |

The unpaired table compares different item sets. The fair comparison is
paired, on the 448, over items where SFT and merged Arm B both carry the
check:

| check | n | SFT | RAG-B (merged) | Δ |
|---|---:|---:|---:|---:|
| C1_dose | 159 | 0.3270 | 0.4369 | **+0.1099** |
| C2_phi | 161 | 0.3121 | 0.4720 | **+0.1599** |
| C3_formulation | 161 | 0.3960 | 0.4720 | +0.0761 |
| C4_escalation | 403 | 0.7742 | 0.7965 | +0.0223 |
| C5_causes_top1 | 212 | 0.6698 | 0.6509 | −0.0189 |
| C6_non_chemical | 124 | 0.5242 | 0.4274 | **−0.0968** |
| C5_causes_top3 | 212 | 0.6981 | 0.6698 | −0.0283 |

Completing the answers strengthens the Step 4 paired result: dose +0.110,
PHI +0.160, formulation +0.076. Non-chemical advice is still the clear
cost (−0.097).

**Refusal is unchanged** at 130 empty-option answers on answerable items
(127 where gold names a chemical), the same as the 1,200-token run.
Regeneration touched only answers that were already naming chemicals.

### 4c.4 The new limiting failure: unknown PHI without escalation

`schema.Advisory` refuses any answer that lists a product with
`phi_days=null` and `phi_not_applicable=false` unless
`escalate_to_expert` is true ("if we cannot say when the crop is safe to
harvest, a human must be involved"). In the merged run:

- **Scale.** **44 answers fail G2, every one with this message.** 4 come
  from pass 1, 12 from pass 2 and 28 from pass 3; 43 are inside the 448.
- **Faithful copies.** The 44 answers carry 85 PHI-unknown options, and
  **84 copy a fact-sheet row whose PHI really is unknown.** The model
  copied the null correctly and missed the rule attached to it.
  `escalate_to_expert` is false on all 44.
- **Why the regenerated answers.** 59 of the 75 regenerated items have a
  PHI-unknown row somewhere in their sheet. 40 of them fail, and only 1 of
  the 75 regenerated answers escalates.
- **SFT knew the rule.** Its 5 answers that carried a PHI-unknown option
  all escalated. With a sheet in the prompt and a long list to write, the
  adapter stops applying it.

The failure is concentrated in the long sheets: 26 of the 64 truncated
headline items and 15 of the 69 items with 6–15 rows. On the items that
pass G2, merged Arm B beats SFT in both buckets:

| bucket | items passing G2 | SFT | RAG-B (merged) |
|---|---:|---:|---:|
| truncated | 38 | 0.4557 | 0.6500 |
| 6–15 rows | 54 | 0.3246 | 0.6062 |

**This is a model failure, not a measurement artefact.** The schema rule
exists to stop exactly this answer reaching a farmer. It is now the single
largest cost in the merged run. It also hides the doses in those 44
answers from C1, because `verify` stops at G2 (4c.6).

### 4c.5 Breakdowns (448 headline)

| slice | n | baseline | SFT | RAG-B (1200) | RAG-B (merged) | Δ merged−SFT | from pass 2/3 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 DOSE | 196 | 0.1193 | 0.3512 | 0.3100 | 0.4605 | +0.1093 | 70 |
| 2 CLARIFY | 173 | 0.3121 | 0.9711 | 0.9769 | 0.9769 | +0.0058 | 0 |
| 3 REFUSAL | 39 | 0.0803 | 0.0504 | 0.0903 | 0.1377 | +0.0874 | 2 |
| 5 NOCHEM | 40 | 0.0300 | 0.1536 | 0.2643 | 0.2643 | +0.1107 | 0 |

| difficulty | n | baseline | SFT | RAG-B (1200) | RAG-B (merged) | Δ merged−SFT | from pass 2/3 |
|---|---:|---:|---:|---:|---:|---:|---:|
| standard | 297 | 0.2245 | 0.6671 | 0.6928 | 0.7520 | +0.0849 | 33 |
| hard | 85 | 0.1348 | 0.4611 | 0.3337 | 0.4953 | +0.0342 | 38 |
| edge_case | 66 | 0.0540 | 0.1154 | 0.1476 | 0.1476 | +0.0322 | 1 |

| crop | n | baseline | SFT | RAG-B (1200) | RAG-B (merged) | Δ merged−SFT | from pass 2/3 |
|---|---:|---:|---:|---:|---:|---:|---:|
| cotton | 123 | 0.1725 | 0.6409 | 0.5526 | 0.6237 | −0.0172 | 24 |
| soybean | 67 | 0.1589 | 0.4184 | 0.4181 | 0.5076 | +0.0893 | 16 |
| onion | 51 | 0.1572 | 0.5818 | 0.5207 | 0.7305 | +0.1487 | 11 |
| tomato | 49 | 0.2283 | 0.4054 | 0.4638 | 0.5046 | +0.0992 | 12 |
| gram | 45 | 0.1815 | 0.7569 | 0.7578 | 0.7578 | +0.0008 | 1 |
| pomegranate | 42 | 0.2470 | 0.4142 | 0.6153 | 0.6629 | +0.2487 | 2 |
| tur | 41 | 0.2127 | 0.5461 | 0.7003 | 0.7219 | +0.1759 | 1 |
| grape | 20 | 0.1188 | 0.7347 | 0.4471 | 0.4971 | −0.2376 | 5 |
| rice / maize / wheat | 4 / 3 / 3 | 0.0000 / 0.0000 / 0.3333 | 0.0000 / 0.0000 / 0.0000 | 0.0000 / 0.3333 / 0.0000 | 0.0000 / 0.3333 / 0.0000 | — | 0 |

| retrieval_status | n | baseline | SFT | RAG-B (1200) | RAG-B (merged) | Δ merged−SFT | from pass 2/3 |
|---|---:|---:|---:|---:|---:|---:|---:|
| resolved_with_rows | 211 | 0.1124 | 0.3312 | 0.2965 | 0.4451 | +0.1139 | 72 |
| no_pest | 145 | 0.3159 | 0.8950 | 0.9026 | 0.9026 | +0.0076 | 0 |
| no_crop (non-dose 57) | 57 | 0.1930 | 0.6673 | 0.7197 | 0.7197 | +0.0524 | 0 |
| resolved_no_rows | 34 | 0.0353 | 0.2059 | 0.2689 | 0.2689 | +0.0630 | 0 |
| crop_mismatch | 1 | 0.0000 | 0.2500 | 0.2500 | 0.2500 | +0.0000 | 0 |

| fact_sheet_bucket | n | baseline | SFT | RAG-B (1200) | RAG-B (merged) | Δ merged−SFT | from pass 2/3 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | 236 | 0.2458 | 0.7407 | 0.7671 | 0.7671 | +0.0264 | 0 |
| 1-5 | 79 | 0.0791 | 0.2461 | 0.4536 | 0.4648 | +0.2188 | 1 |
| 6-15 (not truncated) | 69 | 0.1377 | 0.2581 | 0.2469 | 0.4744 | **+0.2163** | 29 |
| truncated (15 shown of 16+) | 64 | 0.1243 | 0.5137 | 0.1555 | 0.3860 | **−0.1278** | 42 |

| truncated | n | baseline | SFT | RAG-B (1200) | RAG-B (merged) | Δ merged−SFT | from pass 2/3 |
|---|---:|---:|---:|---:|---:|---:|---:|
| False | 384 | 0.1921 | 0.5522 | 0.6091 | 0.6523 | +0.1001 | 30 |
| True | 64 | 0.1243 | 0.5137 | 0.1555 | 0.3860 | −0.1278 | 42 |

What changed from Step 4:

- **Slice 1 DOSE** goes from −0.041 to **+0.109**.
- **hard** goes from −0.127 to +0.034.
- **6–15-row sheets** go from −0.011 to **+0.216**.
- **Truncated sheets are still below SFT (−0.128),** and 4c.4 is the
  reason: 26 of the 64 fail G2. On the 38 that pass, Arm B is ahead.
- **cotton and grape remain below SFT.** Grape is also the crop with the
  no_crop transliteration gap (section 5.1).

### 4c.6 Overdoses on the merged run (every C1 line, the corrected Phase 10 method)

| C1 objection class | SFT | RAG-B (1200) | RAG-B (merged) |
|---|---:|---:|---:|
| WRONG_HIGH | 19 | 3 | 9 |
| WRONG_HIGH_RANGE_TOP | 6 | 0 | 0 |
| PER_HA_NUMBER_LABELLED_PER_ACRE | 2 | 10 | 10 |
| WRONG_LOW | 23 | 1 | 2 |
| UNIT_DIMENSION_MISMATCH | 9 | 6 | 8 |
| total objections / items | 59 / 47 | 20 / 12 | 29 / 21 |

| | SFT | RAG-B (merged) |
|---|---:|---:|
| genuine overdose items (WRONG_HIGH / RANGE_TOP; label-defect B1_36 dropped for SFT) | **24** | **9** |
| per-hectare-as-per-acre items | 2 | 5 |
| items with any overdose-direction error | 26 | 13 |
| items naming chemicals with doses graded (G2 passes) | 159 | 97 |
| genuine overdose rate | 15.1% | 9.3% |
| overdose-direction rate | 16.4% | 13.4% |
| largest genuine overdose | +100% (2×) | **+900% (10×)** |

**Arm B's 9 genuine overdoses** (all +900%; the fact sheet showed the
correct per-acre value in every case):

| item | pass | crop | a.i. | Arm B wrote | label = fact sheet |
|---|---:|---|---|---|---|
| S1_580, B4c_2 | 1 | onion | Fipronil 80% WG | 303.509 g/acre | 30.3509 g/acre |
| S1_201, S1_352, S1_482, S1_546, S1_5606, S1_718 | 2 | onion | Fipronil 80% WG | 303.509 g/acre | 30.3509 g/acre |
| B3_3 | 1 | tur | Chlorantraniliprole 47.85% SC | 202.339 ml/acre | 20.2339 ml/acre |

- **The Fipronil error is systematic.** The merged answers name Fipronil
  80% WG on onion 10 times, 8 at 303.509 and 2 at the correct 30.3509.
  This is the Arm B counterpart of SFT's Acetamiprid cluster (10 items at
  2×): one wrong number repeated, but 10× instead of 2×.

  > **Corrected in Step 6 (6.2): these are different failures.**
  > - **SFT's Acetamiprid** is a real label rate, the whitefly dose,
  >   memorised and applied to the wrong pest.
  > - **Arm B's Fipronil** appears nowhere in the training data. It is a
  >   decimal shift made while copying the sheet: exactly 10 × 30.3509.
  > - **RAG fixes the first.** All 13 of Arm B's cotton Acetamiprid
  >   options are right by pest.
- **Per-hectare as per-acre is unchanged.** The 10 objections on 5 items
  (S1_199 ×4, S1_5272 ×2, S1_486 ×2, B3_3, B4b_3) all come from pass-1
  answers.
- **Doses inside the 44 G2-failed answers were never graded.** `verify`
  stops at G2, so the merged count is a lower bound. Checking those
  answers' per-acre values against the fact-sheet rows they copied finds
  **one more**: S1_528 (pass 3), Deltamethrin 11% w/w EC at 50.58 against
  a sheet value of 20.23 (+150%). That check uses the sheet, not the
  verifier.

  > **Corrected in Step 5 — S1_528 is not an overdose.** The check
  > above matched products by molecule alone, so it compared Deltamethrin
  > 11% EC against the sheet's *Deltamethrin 25% Tablet* row (20.2339
  > g/acre). Against its own row, S1_528 writes the right number, 50.5848,
  > in **g** where the sheet says **ml**: a unit swap, not a dose error.
  > The merged run therefore has **9 genuine overdose items, and none
  > hidden in the 44**. Step 5's validator checked every option in those
  > answers and found no overdose there.

**Against SFT's 24:** merged Arm B overdoses on fewer items, and at a
lower rate per graded answer. But all 9 of its genuine overdoses are 10×,
and SFT never exceeded 2×. Fewer but far larger, and every one was made
with the right number in the prompt.

### 4c.7 Findings recorded from the Step 4b diagnostic

**Two-mode behaviour on 15-row sheets.** Pass 2 had 45 items with
15-row sheets:
- **10 picked a subset and finished,** listing 5 to 10 options.
- **35 listed every row and ran out at 2,048 tokens.**
- **Given 3,072 tokens, those 35 finished,** listing 15 options on 23, 14
  on 9, 12 on 1 and 11 on 2.

So the adapter either chooses a few rows or writes out nearly the whole
sheet. Which mode it takes, not the sheet's content, decides whether the
answer fits a budget. Nothing in training taught it a stopping rule for a
list it was handed.

**S1_237: the model altered a value it was handed.** The fact sheet's row
9 is `FIPRONIL 12.5% + LAMBDA-CYHALOTHRIN 5% ZC`; the model wrote
`Fipronil 12.5% + Lambda-cyhalothrin 5.56% ZC`. The source is the next
row: row 10 is `Flubendiamide 8.33%+Deltamethrin 5.56% w/w SC`, and the
model's next option copies it correctly.
- **Not a real product.** No label_db row has Lambda-cyhalothrin at 5.56%,
  and `sft_train.jsonl` has the 5% product in 53 training examples and a
  5.56% version in none.
- **Adjacent-row bleed.** The model carried one row's strength into the
  row before it. This is the same pattern suspected for Flubendiamide 39.35%
  SC written at 101.17 ml/acre, which is the neighbouring WG row's dose
  (section 7.2).

  > **Checked in Step 5.** In all four Arm B items (S1_5272, S1_486, B3_3,
  > B4b_3) the WG is sheet row 9 and the SC is row 10, so they are
  > adjacent. On B3_3 and B4b_3 the two rows are crossed both ways: the SC
  > gets the WG's number (101.1695) and the WG gets the SC's unit (ml).
  > That fits bleed, but does not prove it. The SFT run, with no sheet at
  > all, also wrote 101.17 ml/acre for this SC (S1_409, S1_139), so the
  > number is in the adapter's prior too.
- **Not scored.** S1_237 fails G2 (unknown PHI, 4c.4), so the altered
  strength was never graded by C3.

  > **Corrected in Step 5 (S1_237).** The line above implies C3 would
  > have caught the alteration. It would not. With the G2 failure
  > repaired, `verify` grades S1_237 and passes the altered product on
  > every check: G5, C1, C2 and C3 all 1.0, total 0.8333, losing only C4.
  > `normalise_ai` drops strengths, and `formulation_key` reads only the
  > first percentage in a name (12.5), so 5.56% and 5% are the same
  > product to the verifier. Two more corrections:
  > - **The alteration is not tied to the run-to-run divergence.** Pass
  >   1's answer stopped after 7 options, before reaching this product.
  >   Pass 2 reproduces pass 1's text exactly; the 5.56% first appears in
  >   pass 2, and pass 3 continues it.
  > - **Only an exact-name check against the sheet catches it**, and
  >   Step 5's validator does (5.B).

**Run-to-run non-determinism under greedy decoding.**
- **Original run against the reruns.** 23 of the 75 pass-2 answers do not
  start with their pass-1 text; the earliest divergence is at character
  272 and the median at 823. Against pass 3 it is 11 of 39.
- **Rerun against rerun.** Pass 3 reproduces pass 2 as an exact prefix on
  all 39.

So the drift is between the original 500-item run and the rerun
environment, which points to something that differed between them, such
as batch composition or padding, rather than per-call randomness. Either
way, identical prompts under greedy decoding produced different answers
for about a third of the regenerated items.

**Every score in this report therefore carries an unmeasured noise
floor.** Nothing here estimates it: the 425 pass-1 answers were never
regenerated, and the 23 divergent items' pass-1 versions were cut off and
cannot be compared. Until it is measured, differences of a few hundredths
between runs should not be read as effects. The +0.0675 headline is
probably larger than that floor, but this report cannot show it.

### 4c.8 Limitations of the merge

1. **Mixed budgets.** The merged file combines answers generated at
   1,200, 2,048 and 3,072 tokens. Under fully deterministic decoding it
   would equal a single 3,072-token run, because the 425 pass-1 answers
   stopped on their own before 1,200 tokens. The observed divergence means
   that equivalence is not guaranteed.
2. **Different answers, not longer versions.** For 23 of the 75
   regenerated items, the answer is a different generation from the one
   that was cut off. The merged score for those items is not "the same
   answer, finished".
3. **Selection by outcome.** Only items that failed to parse were
   regenerated. The 425 that parsed were never re-drawn, so any noise in
   them is invisible, and the regenerated items are not a random sample.
4. **The clean measurement** is one 500-item run at 3,072 tokens in a
   single environment, plus a repeat of the same run to measure the noise
   floor.

## Step 5 — offline validator replay (2026-10-25)

No model and no GPU. Two inference-time validators are replayed over the
merged Arm B answers by `tools/phase12_step5_validator_replay.py`. The
script first asserts that the harness still reproduces
`trained_scores.json` (0.5203) and `rag_B_merged_scores.json` field for
field. **It writes nothing to `data/`.** The repaired answers exist only in
memory, so they cannot be mistaken for model output.

### 5.A Escalation repair — repaired, not model output

**What was changed.** All 44 merged G2 failures fail only on the schema
invariant "unknown PHI requires escalate_to_expert=True" (one error each,
no other violation). Each gets a copy with
`"escalate_to_expert":false` set to `true`, and nothing else; the script
asserts the copy is otherwise identical. All 44 then pass G2.

**Results.** In the table, "repaired†" means repaired, not model output.

| item set | n | baseline | SFT | RAG-B merged | repaired† | Δ repaired−SFT | Δ repaired−merged |
|---|---:|---:|---:|---:|---:|---:|---:|
| **448 headline** | 448 | 0.1824 | 0.5467 | 0.6143 | **0.6925** | +0.1458 | +0.0783 |
| all 500 | 500 | 0.1719 | 0.5249 | 0.5813 | 0.6531 | +0.1283 | +0.0718 |
| the 44 repaired | 44 | 0.1312 | 0.3600 | 0.0000 | 0.8161 | +0.4561 | +0.8161 |

- **Paired, repaired† against SFT on the 448:** 120 up, 47 down, 281
  equal.
- **Items at 0.0:** 125 for SFT, 100 for merged, 58 for repaired†.
- **What the +0.0783 measures.** It is what a one-line post-hoc fix to
  the escalation flag would buy, not what the adapter does. It is a
  validator result, not a model result.

**The C4 side effect is large.** C4 compares `escalate_to_expert` with
the gold answer's flag.
- **Gold escalates on only 3 of the 44** (B3_11, B4b_6, S1_604). On the
  other **41, the repaired answer fails C4 as "over-escalation".** C4 on
  the 44 averages 0.068.
- **Over all 500,** C4 falls from 0.8004 (n=456) to 0.7360 (n=500), and
  over-escalation failures rise from 4 to 45.
- **Why the gold doesn't escalate.** On those 41 items it lists 1 to 4
  products, none with an unknown PHI. It avoids the problem rather than
  escalating on it.

**So the scorer gives full credit only to an answer that leaves the
PHI-unknown product out.** An answer that lists it and escalates, as the
schema requires, loses C4 (weight 0.15). That is why the repaired items
cluster at 0.833–0.850 rather than 1.0. This conflict between the schema
invariant and the `gold_escalate` convention is a scoring-design question
in its own right; this step does not resolve it.

| repaired item outcome | items |
|---|---:|
| 1.000 (gold escalates, so C4 passes) | 2 (B3_11, B4b_6) |
| 0.889 (gold escalates, C5 misses) | 1 (S1_604) |
| 0.81–0.85 (only C4 lost, or C4 plus a small C1 miss) | 36 |
| 0.72–0.75 (C4 plus a C5 or C1 miss) | 4 |
| 0.000 (now fails G8: S1_512 states 4.0468 kg/acre for a row whose label dose is free text) | 1 |

S1_237 scores 0.8333 after repair. Its altered strength passes every
check (correction in 4c.7).

### 5.B Dose validator replay (fact sheet, ±8%)

**What is checked.** Every chemical option in every merged answer: 1,024
options on 141 items, including 506 options in the 44 schema-invalid
answers that `verify` never dose-grades.

**How an option is matched to its row:**
1. **By exact sheet name,** which covers 1,012 options. Otherwise by
   molecule set plus formulation code and first strength, which covers 3.
2. **Narrowed by the query's application method where stated** (7 items).
3. **Narrowed by the option's own PHI** where one product has two rows:
   Clothianidin foliar at PHI 20 and drench at PHI 76.

The stated dose is then compared to the matched row's per-acre or
per-hectare value at ±8%, after unit scaling. 10 options still match more
than one row and are accepted if any of them fits.

| validator verdict | options |
|---|---:|
| OK | 974 |
| HIGH (> +8%) | 19 |
| LOW (< −8%) | 9 |
| UNIT_MISMATCH (g vs ml) | 10 |
| BASIS_MISMATCH | 2 |
| unverifiable (sheet dose is free text) | 1 |
| no fact sheet on the item | 8 (2 items) |
| product not on the item's sheet | 1 (S1_623, the bench-defect item) |

**40 options flagged on 31 items.** Of those flags, 10 options on 10 items
sit inside the 44 schema-invalid answers:
- Clothianidin ×4
- Mancozeb
- Fenvalerate
- a granule
- Pyraclostrobin ×2
- Deltamethrin

None of the 10 is HIGH.

**The known overdoses: all 9 genuine ones caught.**

| known case | validator |
|---|---|
| 9 genuine overdoses: B3_3, B4c_2, S1_201, S1_352, S1_482, S1_546, S1_5606, S1_580, S1_718 | **9/9 HIGH, each +900%** |
| 10 per-hectare-as-per-acre objections on S1_199, S1_5272, S1_486, B3_3, B4b_3 | **10/10 HIGH, +147% to +150%** |
| S1_528 Deltamethrin 11% EC | **UNIT_MISMATCH**, the right number in g where the sheet says ml. Not an overdose; the Step 4c "+150%" was a matching error (correction in 4c.6) |

The 19 HIGH flags are exactly those 19 objections. **The validator finds
no overdose the verifier had not already found,** and none hidden in the
44.

**Agreement with `verify`, per option.** This uses the repaired run,
because there every answer is dose-graded:

| verify() | validator | options |
|---|---|---:|
| no objection | OK | 952 |
| objects (C1) | flag | 38 |
| objects (G8 basis gate) | flag | 2 |
| ambiguous (cannot grade) | OK | 10 |
| objects (G8) | unverifiable | 1 |
| objects (C1) | OK | 1 |

- **No false positives.** Every validator flag is something `verify`
  also objects to.
- **Two cases go the other way:**
  - **S1_512.** The sheet's dose for the granule is free text ("500
    Application method-Soil drench …"), so the validator cannot check
    it, while `verify`'s G8 objects to the basis.
  - **B1_17, Iprodione 50% WP: a verifier rounding defect.** The model's
    404.6781–809.3562 g/acre is the exact conversion of the label's
    1.0–2.0 kg/ha. label_db stores the per-acre bounds rounded to 0.4047
    kg, so 404.6781 g falls 0.005% below the range and C1 rejects a
    correct dose. The ±8% validator passes it correctly.
  - **Scope of the rounding defect.** Across every C1 line in the SFT,
    merged and repaired runs, it is the only range objection that fails
    by under 0.1%. It is invisible in the merged run because B1_17 fails
    G2 there.

**Product identity.** 3 options matched only by formulation key, because
their names differ from the sheet row:
- **S1_564:** the model drops a parenthetical. Cosmetic.
- **S1_604:** the model drops "(Seed treatment)". Cosmetic.
- **S1_237:** the model writes Lambda-cyhalothrin **5.56%** for the
  sheet's 5%. A real alteration.

A validator that requires an exact name match catches S1_237. `verify`
does not.

**Fipronil 80% WG on onion, every option:**

| item | pass | stated (raw) | sheet per-acre (per-ha) | validator | verify() |
|---|---:|---|---|---|---|
| S1_580 | 1 | 303.509 g/acre ("75") | 30.3509 (75) g | HIGH +900% | objects |
| B4c_2 | 1 | 303.509 g/acre ("75") | 30.3509 (75) g | HIGH +900% | objects |
| S1_201 | 2 | 303.509 g/acre ("75") | 30.3509 (75) g | HIGH +900% | objects |
| S1_352 | 2 | 303.509 g/acre ("75") | 30.3509 (75) g | HIGH +900% | objects |
| S1_482 | 2 | 303.509 g/acre ("75") | 30.3509 (75) g | HIGH +900% | objects |
| S1_546 | 2 | 303.509 g/acre ("75") | 30.3509 (75) g | HIGH +900% | objects |
| S1_5606 | 2 | 303.509 g/acre ("75") | 30.3509 (75) g | HIGH +900% | objects |
| S1_718 | 2 | 303.509 g/acre ("75") | 30.3509 (75) g | HIGH +900% | objects |
| S1_1953 | 2 | 30.3509 g/acre ("75") | 30.3509 (75) g | OK | no objection |
| B4b_5 | 1 | 30.3509 g/acre ("75") | 30.3509 (75) g | OK | no objection |

In every case the model copied the raw label value "75" correctly beside
the number. The 10× error is only in the per-acre conversion: 75 ÷ 2.4711
= 30.3509, written as 303.509.

**What 5.B shows.**
- **Most of the value is coverage.** A fact-sheet validator at ±8%
  reproduces every overdose and unit objection `verify` makes, with no
  false positives on this run, and it also covers answers `verify` cannot
  grade.
- **It catches one product alteration `verify` misses (S1_237)** and one
  `verify` false objection (B1_17).
- **It is weaker where the sheet is:** 8 options on items with no sheet
  and 1 with a free-text sheet dose cannot be checked.
- **Its ±8% band and "any surviving row fits" rule are deliberately
  lenient.** Both should be tightened before a validator like this is
  trusted to block answers.

### 5.C The three passes, and the pass 1 → pass 2 divergence

| pass | file | items | max_new_tokens | max_seq_length | parse | reproduces the earlier pass's text |
|---:|---|---:|---:|---:|---:|---|
| 1 | `rag_B_responses.jsonl` | 500 | 1,200 | 4,096 | 425 | — |
| 2 | `rag_B_rerun_responses.jsonl` | 75 | 2,048 | 6,144 | 36 | pass 1 on 52/75; diverges on 23, from character 272 (median 823) |
| 3 | `rag_B_rerun3_responses.jsonl` | 39 | 3,072 | 6,144 | 39 | pass 2 on 39/39; pass 1 on 28/39 |

Pass 1's 4,096-token context held its longest prompt plus budget (2,839 +
1,200 = 4,039). Pass 2's could not (2,839 + 2,048 = 4,887), which is why
`max_seq_length` was raised.

**Two hypotheses for the divergence. Neither is established.**

1. **Configuration.** `max_seq_length` changed from 4,096 to 6,144
   between pass 1 and pass 2. If loading at a different maximum length
   changes the numerics (for example through position-embedding setup or
   kernel choice), greedy decoding can break a near-tie differently and
   the texts part company.
2. **An unpinned unsloth install.** If the notebook installs unsloth
   without a version pin, passes run at different times can pick up
   different unsloth, or dependency, versions with different kernels.
   That produces the same symptom.

**Why the data cannot choose between them.** Passes 2 and 3 share
`max_seq_length` and, presumably, an install close in time, and they agree
exactly. That is consistent with both hypotheses and rules out neither.

**The discriminating test.** In the current environment, regenerate a
sample of pass-1 items at `max_seq_length` 4,096 and `max_new_tokens`
1,200:
- if the output matches pass 1, configuration is the cause;
- if it matches pass 2, the environment is.

Either way, pin unsloth and record `pip freeze` with every future
generation run.

## Step 6 — the rounding defect scoped, and the two wrong numbers traced (2026-10-25)

Run with `tools/phase12_step6_rounding_trace.py`. It is read-only and
writes only its `--md` tables. It rebuilds C1 for every dose-graded option
exactly as `_check_dose` does: same candidate rows (`for_triple` then
`_narrow_candidates`), same basis filter, same `_dose_value_ok`, same
consensus. **It asserts that the rebuild reproduces every per-option
verdict `verify()` emitted (338/338 SFT, 502/502 merged, 1,008/1,008
repaired†) before it changes anything.**

### 6.1 The B1_17 rounding defect: scope

**What it is.** C1's range test is exact containment on 4-decimal numbers.
label_db rounds a per-acre bound in the label's own unit; the model rounds
in the unit it writes. When the two units differ, a correct dose can miss
the range by a few parts per million. B1_17: the label says 1.0–2.0 kg/ha,
stored as 0.4047–0.8094 kg/acre; the model writes 404.6781–809.3562 g/acre.
404.6781 g is below 404.7 g, so C1 objects to a correct dose.

**The brief's literal test over-counts.** "Per-acre dose within 0.1% of the
exact conversion of a label per-hectare bound, while C1 objects" also
matches correct objections:
- **SFT, 9 options.** One end of the model's range equals the label and
  the other end breaks it: Indoxacarb 134.76–161.87 against a point 134.76,
  and the like. These are the Phase 10 RANGE_TOP and WRONG_LOW cases.
- **Unit swaps.** The right number in the wrong unit (ml for g) matches
  numerically. That is 7 options in the merged run, and C1 is right to
  object.

So a casualty is counted as an objection that **disappears when each range
end is given a 0.1% tolerance**. Point doses already carry 5% and are
unaffected.

| run | dose-graded options | C1 objections | rounding casualties | score effect (estimate) |
|---|---:|---:|---:|---|
| baseline | 0 | 0 | **0** | none |
| SFT | 338 | 59 | **0** | none |
| RAG-B merged | 502 | 29 | **0** | none |
| RAG-B merged + escalation repair† (not model output) | 1,008 | 40 | **1 option, 1 item (B1_17)** | B1_17 0.7500 → 0.7917; 448 headline 0.6925 → 0.6926 |

The baseline has no dose-graded options, because it named no chemical in a
schema-valid answer.

**It does not change the SFT-vs-RAG comparison.** The gap on the 448 is
+0.0675 before and after. The defect touches only an answer that reaches
C1 through the escalation repair, which is not model output. *This is an
estimate*: the checks are re-folded with a corrected C1, and `verify()` is
not changed or re-run.

**Unrounded bounds are not the fix.** Replacing stored per-acre bounds
with per-ha ÷ 2.4711:
- **Fixes nothing.** B1_17 still fails: its top, 809.3562, sits above the
  exact 809.356157.
- **Newly fails 18 SFT options, 49 merged and 146 repaired†.** Those
  options match label_db's 4-decimal value exactly, for example Buprofezin
  144.4701–173.6069 against an exact 144.470074–173.606896.

The model and label_db usually round the same way, and that agreement is
what makes most doses pass. The defect is the zero tolerance, and a
tolerance at the range ends is the fix.

**Exposure.** 56 of label_db's 792 per-hectare bounds store a per-acre
value more than 0.001% from the exact conversion: 35 in kg, 9 in ml, 7 in
g, 5 in l. The largest gap is 0.08%. These are where a correct dose can be
rejected. The single worst is the 0.04 ml/ha row already logged as a
label_db defect (B1_36).

### 6.2 Where the wrong numbers came from

The search covered `sft_train.jsonl` (4,493 examples, 4,373 chemical
options) and `sft_test.jsonl` (1,136 examples, 875 options). Each option
was attributed to its crop and pest through `sft_generation_log.csv`.

**(a) Fipronil 80% WG on onion at 303.509 g/acre is not in the training
data. It is a copy error made with the fact sheet in the prompt.**

| | sft_train | sft_test |
|---|---:|---:|
| Fipronil 80% WG on onion at 30.3509 g/acre (correct) | 29 | 7 |
| Fipronil 80% WG at any value near 303.5 | **0** | **0** |
| string `303.509` anywhere | **0** | **0** |
| string `303.5086` (how the data writes 750 g/ha ÷ 2.4711, for other products) | 70 | 24 |

- **Training examples.** S1_1020, "Farmer asked Thrips problem in onion
  crop", gives Fipronil 80% WG 30.3509 g/acre (raw "75"). Two of the
  merged run's 10× items, S1_201 and S1_352, are sft_test items whose
  reference answer is this same correct 30.3509.
- **The exact number rules out recall.** Arm B wrote **303.509**: exactly
  10 × the sheet's printed 30.3509, with the decimal point moved one place.
  A memorised 750 g/ha rate would appear as 303.5086, the form the training
  data uses 94 times.
- **The model kept the raw "75" correct** beside the wrong per-acre value
  on all 8 answers.
- **Without a sheet, the error never appears.** The SFT run never
  recommended Fipronil 80% WG on onion at all.

**(b) Acetamiprid 20% SP on cotton at 40.4678 g/acre IS in the training
data, as the correct whitefly rate. SFT memorised it and applied it to the
wrong pest.**

| | sft_train | sft_test | label_db |
|---|---:|---:|---|
| cotton **whitefly** at 40.4678 g/acre | 44 | 7 | "Whiteflies" 100 g/ha = 40.4678 g/acre |
| cotton **aphid / jassid** at 20.2339 g/acre | 85 | 14 | "Aphids, Jassids" 50 g/ha = 20.2339 g/acre |
| cotton aphid / jassid at 40.4678 | **0** | **0** | — |

- **Training examples.** S1_1122, "Farmer asked White Fly problem in
  crop", gives 40.4678 g/acre (raw "100"). S1_637, "APHIDS MANAGEMENT IN
  COTTON", gives 20.2339 g/acre (raw "50").
- **The training data never pairs 40.4678 with aphid or jassid.** Yet the
  SFT run wrote 40.4678 on **every** Acetamiprid option on cotton: whitefly
  5 (correct), jassid 7 and aphid 3 (the 10 overdoses). Each of the 10
  answers names exactly one cause, the pest asked about, and none mentions
  whitefly. The scorer credits the top cause on 9 of the 10; it does not
  map S1_378's "Woolly aphid" to the bench's "Aphid". The model
  collapsed a two-row product to its higher rate.
- **The same habit shows in Fipronil.** With no sheet, SFT wrote Fipronil
  80% WG at grape's 20.2339 on cotton and pomegranate as well as grape:
  one number per product.
- **The fact sheet fixes it completely.** The merged Arm B run writes
  Acetamiprid 20% SP by pest: whitefly 40.4678 ×5, jassid 20.2339 ×5,
  aphid 20.2339 ×3.

**So the two clusters are different failures, and RAG moves the error
from one kind to the other:**

| | SFT, Acetamiprid ×10 | RAG-B, Fipronil ×8 |
|---|---|---|
| the number | a real label rate (whitefly) | not a label rate anywhere for this product |
| in training data | yes, 51 times, for the right pest | never |
| mechanism | memorised number on the wrong row (pest mis-association) | decimal shift while copying the sheet |
| magnitude | 2× | 10× |
| fixed by the other arm | **yes**: RAG-B gets all 13 Acetamiprid options right | **n/a**: SFT never wrote this product on onion |

This corrects the framing used in 4c.6, decision 1d, and Phase 10's
section 2.2a ("one memorised wrong number repeated"). It fits neither
case:
- **Acetamiprid** is a correct rate on the wrong pest, a loss of pest
  conditioning.
- **Fipronil** is a decimal shift made while copying the sheet.

Phase 10's section 2.2a was amended accordingly in Step 7, with the
original wording kept as superseded.

### 6.3 Known limitations, recorded

1. **`verify()` is blind to strengths after the first percentage.**
   `normalise_ai` drops every strength, and `formulation_key` reads only
   the first `%` in a name.
   - **What gets through.** Two co-formulations that differ only in a
     second component's strength look like the same product to G5, C1 and
     C3. S1_237's `Lambda-cyhalothrin 5.56%` for the label's 5% passes
     every check once the answer is schema-valid (5.A).
   - **What is still caught.** A changed first strength. A changed dose is
     still graded on its own.
2. **C1's range test has zero tolerance** (6.1). One known casualty so
   far, in a repaired answer.
3. **The validator and the verifier share label_db, so their agreement is
   not independent.** Arm B's fact sheet is drawn from label_db, the
   validator's reference is that sheet, and `verify()`'s reference is
   label_db.
   - **What "no false positives" shows.** The two implementations read the
     same table consistently. It does not show either is right against
     CIB&RC.
   - **A shared error passes both.** A label_db defect would be accepted
     by both: B1_36's 0.0162 ml/acre, or the free-text granule dose on
     S1_512.
   - **What independent confirmation would take.** A check against the
     source PDFs, or a second extraction.

## 0. Integrity and reproduction

**Task A, `data/final/eval/rag_B_responses.jsonl`:** 500 rows, 500 unique
item_ids, 0 `__ERROR__` rows, 0 empty responses. Every bench item_id is
present exactly once, with no extras. The per-row metadata (rows_available,
rows_included, truncated, retrieval_status, prompt_tokens, fact_sheet_bucket)
matches `data/interim/rag_prompts_B.jsonl` on all 500.

**Harness check.** The script re-scores the SFT run and the baseline before
it touches Arm B:

| file | items differing (total / checks / gates / excluded) | mean |
|---|---|---:|
| `trained_scores.json` | 0 / 0 / 0 / 0 | **0.520319** over the 489 non-excluded (0.524872 over all 500) |
| `baseline_scores_v2.json` | 0 / 0 / 0 / 0 | **0.171875** |

The convention is unchanged from Phase 10:
`VerifyContext(resources, crop_slug=item.crop_slug, pest_query=item.canonical_pest, gold_escalate=item.gold_advisory.escalate_to_expert)`
with `verify(raw, ctx, "score")`. As in Phase 10, dropping `gold_escalate`
changes 247 totals and drops the mean to 0.2456.

**The 75 non-JSON responses.** All 75 are exactly 1,200 tokens long by the
Qwen tokenizer, which is the generation cell's `max_new_tokens`. Every one
stops part-way through the JSON (71 inside a string), and none is
malformed in any other way. They are scored as the convention requires: G1 fails and the
total is 0.0. No response was repaired.

Each one is a genuine cut-off, not a short valid answer:

- **All 75 are exactly 1,200 response tokens.** The longest response that
  did parse is 1,187 tokens, so none sits at the limit by coincidence.
- **None closes its JSON.** No response ends in `}`, and every one has at
  least one unclosed brace. Errors: unterminated string 71, expecting
  value 2, expecting `,` delimiter 2.
- **All were mid-list.** Each had started 5 to 9 chemical options when the
  budget ran out (7 on 51 of them).

| distribution of the 75 | |
|---|---|
| slice | 1 DOSE 73, 3 REFUSAL 2 |
| kind | DOSE 73, REFUSAL_DOSE 2 |
| crop | cotton 24, soybean 16, tomato 14, onion 12, grape 5, pomegranate 2, gram 1, tur 1 |
| difficulty | hard 41, standard 33, edge_case 1 |
| `fact_sheet_rows` | 15 rows 45, 7 rows 18, 13 rows 4, 6 rows 4, 10 rows 2, 8 rows 1, 5 rows 1 |
| fact-sheet bucket | truncated (15 of 16+) 45, 6-15 29, 1-5 1 |
| retrieval_status | resolved_with_rows 74, crop_mismatch 1 |
| prompt_tokens | min 1,367, max 2,839 |

Every cut-off had rows in its fact sheet and 74 of 75 had 6 or more.
Nothing with an empty sheet was ever cut off, which is the clearest
evidence that sheet length drives output length. The item_ids are in
`data/interim/rag_B_rerun_ids.json`.

**Exclusions.** Arm B has 0, against SFT's 11. Retrieval filters
contradicted rows out of the fact sheet before the model sees them, so Arm B
never recommended the tur chlorantraniliprole or tomato flubendiamide claims
that excluded SFT items. On 6 of those tur items it recommended other
registered products and scored 1.0.

## 1. Headline

> **Superseded by Step 4c (4c.1).** This is the 1,200-token run, with 75
> answers cut off and scored 0.0. The current headline is RAG-B (merged)
> 0.6143 against SFT 0.5467 on the same 448 items.

Exclusions differ between runs, so the headline uses items that are
non-excluded in all three runs. Following task 5, it also removes the
no_crop-40 and the two known bench defects (section 5).

| item set | n | baseline | SFT | SFT+RAG(B) | Δ B−SFT |
|---|---:|---:|---:|---:|---:|
| **headline: non-excluded in all three, minus no_crop-40 and 2 defects** | **448** | **0.1824** | **0.5467** | **0.5443** | **−0.0024** |
| non-excluded in all three (intersection) | 489 | 0.1723 | 0.5203 | 0.5138 | −0.0065 |
| each arm's own non-excluded set | 500/489/500 | 0.1719 | 0.5203 | 0.5166 | −0.0037 |
| all 500, recorded totals | 500 | 0.1719 | 0.5249 | 0.5166 | −0.0082 |
| all 500, excluded scored 0.0 | 500 | 0.1719 | 0.5089 | 0.5166 | +0.0078 |
| *headline minus Arm B's 72 cut-offs (conditional, not an estimate)* | *376* | *0.1895* | *0.5644* | *0.6486* | *+0.0842* |

On the headline set:

- **Items at 1.0:** baseline 55, SFT 210, Arm B 212.
- **Items at 0.0:** baseline 256, SFT 125, Arm B 132.
- **Paired:** Arm B is higher than SFT on 69 items, lower on 68 and equal on
  311.

Under any of the five denominators the change from SFT to Arm B is between
−0.0082 and +0.0078, and the sign depends on how exclusions are counted.

**Do not read the last row as RAG's effect.** It removes items according to
an Arm B outcome. The cut-off items were not easy ones: SFT scores 0.4545 on
them, below its headline mean. Even so, conditioning on a post-treatment
variable is not a valid estimate. It only bounds what the 72 items would add
if they had completed and scored like Arm B's other answers. The valid fix is
to re-generate them (section 10).

## 2. Gates and checks

### 2.1 Gates, all 500

| gate | baseline | SFT | SFT+RAG(B) |
|---|---:|---:|---:|
| G1_json | 500/500 (100.0%) | 498/500 (99.6%) | **425/500 (85.0%)** |
| G2_schema | 264/500 (52.8%) | 497/498 (99.8%) | 421/425 (99.1%) |
| G3_empty_when_not_answering | 264/264 | 497/497 | 421/421 |
| G4_restricted_ai | 264/264 | 497/497 | 421/421 |
| G5_triple_registered | 264/264 | 412/497 (82.9%) | **419/421 (99.5%)** |
| G6_unknown_phi_escalates | 264/264 | 485/486 (99.8%) | 421/421 |
| G7_trainable_row | 264/264 | 485/486 (99.8%) | 421/421 |
| G8_dose_basis | 264/264 | 477/486 (98.1%) | 420/421 (99.8%) |
| G9_unstated_dose_earned | 264/264 | 486/486 | 421/421 |

Arm B's 4 G2 failures (S1_604, S1_657, S1_104, B3_11) all share one cause:
`unknown PHI requires escalate_to_expert=True`.

### 2.2 Checks, all 500 (unpaired; n differs by arm)

| check | weight | baseline | SFT | SFT+RAG(B) | Δ B−SFT |
|---|---:|---|---|---|---:|
| C1_dose | 0.30 | 0.0000 (n=182) | 0.3660 (n=235) | 0.2884 (n=190) | −0.0775 |
| C2_phi | 0.25 | 0.0000 (n=182) | 0.3121 (n=239) | 0.3145 (n=190) | +0.0024 |
| C3_formulation | 0.10 | 0.0000 (n=182) | 0.4616 (n=239) | 0.3158 (n=190) | −0.1459 |
| C4_escalation | 0.15 | 0.8182 (n=264) | 0.7901 (n=486) | 0.7862 (n=421) | −0.0039 |
| C5_causes_top1 | 0.10 | n=0 | 0.6768 (n=297) | 0.5714 (n=231) | −0.1053 |
| C6_non_chemical | 0.10 | 0.0000 (n=94) | 0.5443 (n=158) | 0.3178 (n=129) | −0.2265 |
| C5_causes_top3 | — | n=0 | 0.7205 (n=297) | 0.6104 (n=231) | −0.1101 |

The baseline and SFT columns match Phase 10 section 1.3 exactly. **This
table is misleading for Arm B:** its 75 cut-offs carry no checks, and they
are mostly items where the model was answering. Its C1/C3 denominator is
therefore weighted toward refusal-miss zeros. The paired table below is the
fair comparison.

### 2.3 Checks, headline set, paired (items where SFT and Arm B both carry the check)

| check | n | SFT | SFT+RAG(B) | Δ B−SFT |
|---|---:|---:|---:|---:|
| C1_dose | 128 | 0.2422 | 0.3109 | **+0.0687** |
| C2_phi | 130 | 0.2404 | 0.3462 | **+0.1058** |
| C3_formulation | 130 | 0.3154 | 0.3462 | +0.0308 |
| C4_escalation | 370 | 0.7595 | 0.7811 | +0.0216 |
| C5_causes_top1 | 179 | 0.6257 | 0.5922 | −0.0335 |
| C6_non_chemical | 104 | 0.4519 | 0.3173 | **−0.1346** |
| C5_causes_top3 | 179 | 0.6592 | 0.6145 | −0.0447 |

Paired, the fact sheet improves both numbers that can harm a farmer, dose
and PHI, and costs non-chemical advice. With chemistry in front of it, the
model leaves `non_chemical_first` empty more often. Diagnosis (C5) also
slips slightly.

### 2.4 Refusal on answerable items (schema-valid, ANSWERABLE, empty `chemical_options`)

| arm | all 500: answerable / empty / gold names a chemical | headline: same |
|---|---|---|
| baseline | 182 / 182 / 180 | 152 / 152 / 150 |
| SFT | 267 / 123 / 120 | 216 / 96 / 93 |
| SFT+RAG(B) | 191 / 130 / 127 | 142 / 90 / 87 |

**RAG does not fix the Phase 10 refusal problem.** On the 212 headline
DOSE/REFUSAL_DOSE items whose fact sheet contained rows, Arm B gave the
CLARIFY-shaped refusal (`query_understood=false` plus a clarifying question)
on 84, against 82 for SFT. That is with the registered chemistry in the
prompt.

| SFT shape → Arm B shape (212 dose items with rows) | items |
|---|---:|
| names chemicals → cut off at 1,200 tokens | **64** |
| refuses (clarify) → refuses (clarify) | 63 |
| names chemicals → names chemicals | 38 |
| names chemicals → refuses (clarify) | 18 |
| refuses (clarify) → names chemicals | 11 |
| refuses (clarify) → cut off | 8 |
| refuses (non-chemical only) → names chemicals | 6 |
| refuses (non-chemical only) → refuses (clarify) | 2 |
| cut off → names chemicals / cut off → refuses | 1 / 1 |

64 of SFT's 120 complete dose answers became cut-offs under Arm B. Example
S1_101 ("cotton wilt attack and fertilizer doses") shows the refusal side:
with 2 registered rows in the sheet, Arm B still asks whether the wilting
looks like Jassid, Thrips or Girdle beetle.

## 3. By slice, kind, difficulty, crop (headline set)

| slice | n | baseline | SFT | SFT+RAG(B) | Δ B−SFT | B cut-offs |
|---|---:|---:|---:|---:|---:|---:|
| 1 DOSE | 196 | 0.1193 | 0.3512 | 0.3100 | −0.0411 | 70 |
| 2 CLARIFY | 173 | 0.3121 | 0.9711 | 0.9769 | +0.0058 | 0 |
| 3 REFUSAL | 39 | 0.0803 | 0.0504 | 0.0903 | +0.0399 | 2 |
| 5 NOCHEM | 40 | 0.0300 | 0.1536 | 0.2643 | +0.1107 | 0 |

| kind | n | baseline | SFT | SFT+RAG(B) | Δ B−SFT | B cut-offs |
|---|---:|---:|---:|---:|---:|---:|
| DOSE | 194 | 0.1205 | 0.3524 | 0.3123 | −0.0400 | 70 |
| CLARIFY | 150 | 0.3200 | 0.9667 | 0.9733 | +0.0067 | 0 |
| NOCHEM | 40 | 0.0300 | 0.1536 | 0.2643 | +0.1107 | 0 |
| OFFTOPIC | 35 | 0.2000 | 0.6704 | 0.6905 | +0.0200 | 0 |
| REFUSAL_DOSE | 22 | 0.0152 | 0.0893 | 0.1146 | +0.0253 | 2 |
| REFUSAL_NOCHEM | 7 | 0.2571 | 0.0000 | 0.0000 | +0.0000 | 0 |

| difficulty | n | baseline | SFT | SFT+RAG(B) | Δ B−SFT | B cut-offs |
|---|---:|---:|---:|---:|---:|---:|
| standard | 297 | 0.2245 | 0.6671 | 0.6928 | +0.0257 | 33 |
| hard | 85 | 0.1348 | 0.4611 | 0.3337 | −0.1274 | 38 |
| edge_case | 66 | 0.0540 | 0.1154 | 0.1476 | +0.0322 | 1 |

| crop | n | baseline | SFT | SFT+RAG(B) | Δ B−SFT | B cut-offs |
|---|---:|---:|---:|---:|---:|---:|
| cotton | 123 | 0.1725 | 0.6409 | 0.5526 | −0.0883 | 24 |
| soybean | 67 | 0.1589 | 0.4184 | 0.4181 | −0.0003 | 16 |
| onion | 51 | 0.1572 | 0.5818 | 0.5207 | −0.0611 | 11 |
| tomato | 49 | 0.2283 | 0.4054 | 0.4638 | +0.0584 | 12 |
| gram | 45 | 0.1815 | 0.7569 | 0.7578 | +0.0008 | 1 |
| pomegranate | 42 | 0.2470 | 0.4142 | 0.6153 | +0.2011 | 2 |
| tur | 41 | 0.2127 | 0.5461 | 0.7003 | +0.1542 | 1 |
| grape | 20 | 0.1188 | 0.7347 | 0.4471 | −0.2876 | 5 |
| rice / maize / wheat | 4 / 3 / 3 | 0.0000 / 0.0000 / 0.3333 | 0.0000 / 0.0000 / 0.0000 | 0.0000 / 0.3333 / 0.0000 | — | 0 |

Every losing group is a group with cut-offs:

- **Slice 1:** 70 of the 72 cut-offs.
- **hard:** 38.
- **cotton:** 24, from its big fact sheets.

Where cut-offs are rare, Arm B gains:

- tur +0.154
- pomegranate +0.201
- NOCHEM +0.111
- REFUSAL +0.040

Slice 3 (REFUSAL) moves above baseline (0.0903 vs 0.0803), which reverses
the Phase 10 regression on that slice. Grape's −0.288 on 20 items is the
largest single drop, with 5 cut-offs; small n.

## 4. By retrieval (headline set)

| retrieval_status | n | baseline | SFT | SFT+RAG(B) | Δ B−SFT | B cut-offs |
|---|---:|---:|---:|---:|---:|---:|
| resolved_with_rows | 211 | 0.1124 | 0.3312 | 0.2965 | −0.0346 | 72 |
| no_pest | 145 | 0.3159 | 0.8950 | 0.9026 | +0.0076 | 0 |
| no_crop (non-dose 57; the dose 40 are in section 5) | 57 | 0.1930 | 0.6673 | 0.7197 | +0.0524 | 0 |
| resolved_no_rows | 34 | 0.0353 | 0.2059 | 0.2689 | +0.0630 | 0 |
| crop_mismatch | 1 | 0.0000 | 0.2500 | 0.2500 | +0.0000 | 0 |

| fact_sheet_bucket | n | baseline | SFT | SFT+RAG(B) | Δ B−SFT | B cut-offs |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 236 | 0.2458 | 0.7407 | 0.7671 | +0.0264 | 0 |
| 1-5 | 79 | 0.0791 | 0.2461 | **0.4536** | **+0.2075** | 1 |
| 6-15 (not truncated) | 69 | 0.1377 | 0.2581 | 0.2469 | −0.0112 | 29 |
| truncated (15 shown of 16+) | 64 | 0.1243 | 0.5137 | **0.1555** | **−0.3583** | 42 |

| truncated | n | baseline | SFT | SFT+RAG(B) | Δ B−SFT | B cut-offs |
|---|---:|---:|---:|---:|---:|---:|
| False | 384 | 0.1921 | 0.5522 | 0.6091 | +0.0569 | 30 |
| True | 64 | 0.1243 | 0.5137 | 0.1555 | −0.3583 | 42 |

| fact_sheet_kind | n | baseline | SFT | SFT+RAG(B) | Δ B−SFT | B cut-offs |
|---|---:|---:|---:|---:|---:|---:|
| rows | 212 | 0.1118 | 0.3308 | 0.2963 | −0.0345 | 72 |
| unresolved (could-not-identify line) | 202 | 0.2812 | 0.8307 | 0.8510 | +0.0202 | 0 |
| no_rows (CIB&RC line) | 34 | 0.0353 | 0.2059 | 0.2689 | +0.0630 | 0 |

**The clearest RAG signal is the 1–5-row bucket: +0.2075 on 79 items, with
1 cut-off.** A short sheet nearly doubles the score.

The 6–15 and truncated buckets lose, and they are where 71 of the 72
cut-offs sit. Section 8 shows that on truncated items where Arm B finished
its answer, the score is flat (−0.0094). The truncated bucket's collapse is
the generation cap, not the rows the cap cut.

## 5. The no_crop-40 and the two known bench defects

**Definition used.** Arm B has 97 `no_crop` items. The 40 are the ones
whose bench kind is DOSE (35) or REFUSAL_DOSE (5): answerable dose
questions where live retrieval named no crop. That is the subset
`run_rag_eval.py` reports for DOSE/REFUSAL_DOSE. The other 57 are CLARIFY,
OFFTOPIC or NOCHEM items and stay in the headline (section 4 row).

| set | n | baseline | SFT | SFT+RAG(B) | Δ B−SFT |
|---|---:|---:|---:|---:|---:|
| no_crop-40, all | 40 | 0.0677 | 0.2575 | 0.1914 | −0.0661 |
| no_crop-40, non-excluded in all three | 39 | 0.0652 | 0.2385 | 0.1899 | −0.0486 |

- **What the model was told.** Retrieval returned no rows, and the fact
  sheet said "Retrieval could not identify a specific crop and pest from
  this query." Arm B then refused **39 of 40** (empty options on an
  answerable item); SFT refused 26.
- **Which crops.** By gold crop: grape 15, cotton 12, gram 5, tur 3,
  pomegranate 2, tomato, soybean and onion 1 each.
- **What this is.** Not a model error. Two different causes, split in 5.1
  — a `crop_mapper` coverage gap on 19, and queries that name no crop at
  all on 21. Either way it is a real deployment failure: the
  could-not-identify line turns a question SFT sometimes answered into a
  refusal.

### 5.1 Why retrieval found no crop: 97 items, two causes

Arm B has **97 `no_crop` items** in total (the 40 above are the
DOSE/REFUSAL_DOSE subset; the other 57 are CLARIFY, OFFTOPIC or NOCHEM
and stay in the headline). 95 of the 97 name zero in-scope crops; only 2
are the "more than one crop named" case. Splitting them by whether the
query names the crop at all:

| cause | of 97 | of the 40 | gold crops in the 40 | SFT | Arm B |
|---|---:|---:|---|---:|---:|
| **(a)** query names the crop, `crop_mapper` does not resolve the word | 22 | **19** | grape 15, gram 4 | 0.1810 | 0.1743 |
| **(b)** query names no crop in any language | 75 | **21** | cotton 12, tur 3, pomegranate 2, soybean / tomato / gram / onion 1 each | 0.3268 | 0.2069 |

**(a) `crop_mapper` does not resolve some transliterated crop names.**
Verified directly against `src/crop_mapper.map_crop`:

| query word | crop | resolves? |
|---|---|:-:|
| `angur`, `draksh` (and `bel` in "angur ki bel") | grape | **no** |
| `harbhara`, `chana` | gram | **no** |
| `kapus` | cotton | **no** |
| `bhat` / `gahu` / `makka` | rice / wheat / maize | **no** |
| `tamatar` | tomato | yes |
| `kanda` | onion | yes |
| `dalimb`, `anar` | pomegranate | yes |
| `soyabean` | soybean | yes |

So the table is **partially** transliterated, and grape is the biggest
hole: all 15 grape items in the no_crop-40 are B-series items phrased in
Hindi or Marathi ("angur ki bel par davnya rog aa gaya hai…", "draksh var
bhuri ali ahe favarni sanga"). This is a **retrieval gap, V2 work**: four
words (`angur`, `draksh`, `bel`, `harbhara`) would recover 19 of the 40.

**`crop_mapper` was deliberately NOT modified.** It is an input to both
arms, and changing it mid-ablation would change the prompts and make Arm
B non-comparable to the generations already scored here, and to Arm A
when it runs. The fix belongs after the ablation closes, followed by a
re-generation.

**(b) 21 of the 40 name no crop that any resolver could find.** These are
KCC-sourced items whose crop lives in the record's metadata, not in the
farmer's words: "Farmer asked Jassid Problem in crop", "ask about leaf
spot disese", "FARMER ASKED QUERY ABOUT CONTROL OF RED MITE ?". The gold
`crop_slug` is cotton on 12 of them. Arm A keys on that gold crop and so
never sees this; Arm B cannot, and neither could a deployed system
reading only the question.

**Consequence for the V2 estimate:** fixing `crop_mapper` addresses at
most 19 of these 40 items. The other 21 need the crop supplied from
outside the query — a clarifying turn, or a crop field on the farmer's
profile — which is a product decision, not a retrieval one.

| item | gold crop / pest | Arm B resolved | rows | baseline | SFT | SFT+RAG(B) |
|---|---|---|---:|---:|---:|---:|
| S1_1856 | tomato / Wilt | gram / Wilt | 3 | 0.0000 | 0.2000 | 0.0000 |
| S1_623 | onion / Thrips | cotton / Jassid | 15 (truncated) | 0.0000 | 0.0000 | 0.0000 |

- **S1_1856.** Arm B resolved the crop the query actually names (bengal
  gram) and recommended gram chemistry. Scored against the wrong gold crop
  (tomato), all 3 options fail G5. These 3 options are 3 of Arm B's 7
  G5-failing options (section 7).
- **S1_623.** Cut off at 1,200 tokens, so its score says nothing about the
  defect.

## 6. Failure reasons, top 10 (items affected, all 500)

| # | reason | baseline | SFT | SFT+RAG(B) | Δ B−SFT |
|---:|---|---:|---:|---:|---:|
| 1 | C1/C2/C3 refused an answerable question | 182 | 123 | 130 | +7 |
| 2 | C5 top cause is not the queried pest | 0 | 96 | 99 | +3 |
| 3 | C4 did not escalate when gold does | 36 | 91 | 86 | −5 |
| 4 | **G1 output is not JSON (1,200-token cut-off)** | 0 | 2 | **75** | **+73** |
| 5 | C6 no non-chemical step; a biological is registered | 73 | 43 | 48 | +5 |
| 6 | C6 no non-chemical step; no chemistry registered | 21 | 29 | 40 | +11 |
| 7 | C1 dose outside the label | 0 | 47 | 12 | −35 |
| 8 | G2 does not validate against Advisory | 236 | 1 | 4 | +3 |
| 9 | C4 escalated when CIB&RC gives a complete answer | 12 | 11 | 4 | −7 |
| 10 | G5 a.i. on this crop, but not for this pest | 0 | 51 | 2 | −49 |
| — | *(SFT top 10)* G5 a.i. has no CIB&RC claim on this crop/pest | 0 | 68 | 2 | **−66** |
| — | *(SFT top 10)* C2 PHI differs from the label | 0 | 52 | 1 | **−51** |
| — | *(SFT top 10)* C3 formulation not the registered one | 0 | 11 | 0 | −11 |

Three SFT failure modes nearly vanish with a fact sheet:

- inventions (−66 items)
- mis-associations (−49)
- PHI errors (−51)

Dose errors drop from 47 items to 12. Note that 75 items cannot fail any
of these because they never parsed, so part of each drop is the cut-off
denominator. The paired checks in 2.3 and the G5 rate below are the clean
versions.

## 7. G5 and overdoses

### 7.1 G5

| arm | items failing G5 / items where G5 was evaluated |
|---|---|
| baseline | 0 / 264 |
| SFT | 85 / 497 |
| SFT+RAG(B) | **2 / 421** |

| G5 class (Phase 10 classifier) | SFT options | SFT items | Arm B options | Arm B items |
|---|---:|---:|---:|---:|
| i synonym false negative | 4 | 4 | 0 | 0 |
| ii mis-association | 71 | 49 | 1 | 1 |
| iii invention | 134 | 66 | 2 | 1 |
| iv pest unresolved | 11 | 3 | 4 | 1 |

Arm B's classes ii and iii are the same item, **S1_1856**, the bench
defect. Its options came from the gram fact sheet and are graded against
tomato. Leaving that item aside, **Arm B has one G5-failing item**: it
names 4 chemicals on a query that resolves to no pest (class iv). It made
no inventions anywhere else.

### 7.2 Overdoses: the Phase 10 rule, and what it missed

> **Step 4c (4c.6) re-runs this on the merged answers:** 9 genuine
> overdose items (all 10×), against SFT's 24. The Arm B figures below are
> for the 1,200-token run only.

Phase 10 classified dose objections only on items where `C1_dose == 0.0`.
C1 is a mean over a response's options, so an item with one overdose among
four correct options (C1 = 0.75) was never read. Both counts are below,
from the same `dose_verdict` classifier:

| C1 objection class | SFT, Phase 10 rule | Arm B, Phase 10 rule | SFT, every C1 line | Arm B, every C1 line |
|---|---:|---:|---:|---:|
| WRONG_HIGH | 2 | 0 | 19 | 3 |
| WRONG_HIGH_RANGE_TOP | 3 | 0 | 6 | 0 |
| PER_HA_NUMBER_LABELLED_PER_ACRE | 0 | 4 | 2 | 10 |
| WRONG_LOW | 8 | 0 | 23 | 1 |
| UNIT_DIMENSION_MISMATCH | 3 | 0 | 9 | 6 |
| total objections / items | 16 / 11 | 4 / 1 | 59 / 47 | 20 / 12 |

**Against SFT's 5, under the Phase 10 rule:** SFT reproduces exactly 5
genuine overdoses (B1_32, S1_135, S1_5524, S1_67, S1_512; asserted in the
script). Arm B has 0. Arm B does have 4 per-hectare-as-per-acre objections
on one item, S1_199, which Phase 10 classed separately and never saw in
the SFT run.

**Reading every C1 line, which is the honest count:**

- **SFT: 24 items with a genuine overdose.** The classifier finds 25
  WRONG_HIGH / RANGE_TOP objections on 25 items. One, B1_36, is a label_db
  defect and is dropped: the label value is 0.0162 ml/acre, from a raw
  "0.04" that is almost certainly a concentration read as a per-hectare
  rate. The model's 121 ml/acre is a normal Lambda-cyhalothrin 5% EC rate.
- **What the 24 are.** The new ones include Acetamiprid 20% SP on cotton
  at 2× the label on **10 items** (40.47 vs 20.23 g/acre), Oxathiapiprolin
  on grape +75%, and Fenpyroximate on cotton +33% (2 items).
- **Adding SFT's 2 per-ha-as-per-acre items** gives 26 items with an
  overdose-direction error, out of 159 items where SFT named chemicals and
  produced valid JSON (16.4%).
- **Arm B: 7 items** with an overdose-direction error (S1_580, B4c_2,
  B3_3, S1_199, S1_5272, S1_486, B4b_3), out of 66 items naming chemicals
  in valid JSON (10.6%).

**Arm B overdoses less often, but its overdoses are larger, and they happen
with the right number in its prompt:**

| item | crop | a.i. | Arm B wrote | label (and fact sheet) | delta |
|---|---|---|---|---|---:|
| S1_580 | onion | Fipronil 80% WG | 303.509 g/acre (raw "75") | 30.3509 g/acre | **+900%** |
| B4c_2 | onion | Fipronil 80% WG | 303.509 g/acre | 30.3509 g/acre | **+900%** |
| B3_3 | tur | Chlorantraniliprole 47.85% SC | 202.339 ml/acre (raw "500") | 20.2339 ml/acre | **+900%** |

- **The +900% cases are decimal shifts.** The fact sheet row showed
  `dose_per_acre_min: 30.3509` and the model wrote 303.509. On S1_580 it
  copied `raw: "75"` correctly beside the wrong number.
- **The 10 per-ha-as-per-acre objections are copies of the wrong column.**
  On S1_199 the model wrote the sheet's per-hectare `dose_min` values (150,
  250, 450, 333) under `basis: per_acre`, a 2.47× overdose on 4 products.
- **The Flubendiamide pattern.** Flubendiamide 39.35% SC at 101.17 ml/acre
  (S1_5272, S1_486, B3_3, B4b_3; and S1_409/S1_139 in SFT) is 2.5× its
  label. 101.17 is also exactly the per-acre figure of the Flubendiamide
  20% WG row, so it may be a cross-row copy.
- **Severity.** Nothing in the SFT run was a 10× overdose. The SFT run's
  largest genuine overdose is 2×.

## 8. Truncated items: did the gold chemical sit in the rows that were cut?

74 items were truncated, with 17 to 86 rows available before the cap. On
71 of them Arm B's key equals the gold key.

**The cut is not alphabetical.** For 0 of the 74 is the uncapped row list
in alphabetical order by a.i. The cap keeps the first 15 rows in label_db
index order, which is CIB&RC document order (`retrieval.py` decision 4). So
this measures the cost of document order.

| where the gold advisory's chemicals sit | items | SFT mean | Arm B mean | Δ B−SFT | B cut-offs |
|---|---:|---:|---:|---:|---:|
| at least one gold a.i. in the 15 shown | 61 | 0.5636 | 0.2563 | −0.3073 | 37 |
| **gold a.i. only in the cut rows** | **12** | 0.4583 | 0.0795 | −0.3788 | 8 |
| gold a.i. not in this key's rows at all | 1 | 0.0000 | 0.0000 | +0.0000 | 0 |

- **Per item:** on **12 of 74 truncated items (16%) every gold chemical
  was cut.** The 12 are S1_494, S1_5323, S1_528, S1_623, B1_2, B1_4, B1_6,
  B1_16, B3_1, B4a_2, B4b_3 and B4c_1.
- **Per chemical:** of 230 gold chemicals on truncated items, 136 were
  shown, **91 (40%) sat only in the cut rows**, and 3 were in neither.
- **Position:** the first gold chemical's position in the uncapped list
  has a median of 5 (0-based). 12 items have it at position 15 or later,
  the latest at 52.
- **The model stays inside the sheet:** all 69 options Arm B recommended
  on truncated items name an a.i. from the 15 shown. It never recommended
  a cut product from memory.

**What this costs in score: nothing directly.** The verifier never sees the
gold chemical list (`VerifyContext` carries crop, pest and `gold_escalate`
only). It grades whatever a.i. the model names against label_db. Picking
a registered product from the shown 15 instead of the gold's product costs
nothing if the dose and PHI are right. The bucket's collapse comes from the
cap on generation:

| truncated items | n | SFT | SFT+RAG(B) | Δ B−SFT |
|---|---:|---:|---:|---:|
| Arm B completed its answer | 29 | 0.5815 | 0.5720 | −0.0094 |
| Arm B cut off at 1,200 tokens | 45 | 0.5115 | 0.0000 | −0.5115 |

The cap's real cost is to recall rather than score. On 40% of the gold
chemicals the farmer is never shown the product the reference answer chose,
and this benchmark cannot see that.

## 9. What this does and does not show

> **Updated by Step 4c.** Points 1 and 3 below describe the 1,200-token
> run and are superseded:
> - **Headline.** The merged headline is +0.0675 over SFT, not −0.0024.
> - **Gains no longer cancelled.** The cut-offs are gone (G1 500/500). The
>   new limiting failure is unknown PHI without escalation (4c.4).
> - **Still true:** points 2, 4 and 5, all three confounds and the
>   smaller effects.
> - **One new limitation:** an unmeasured run-to-run noise floor (4c.7).

### It shows

1. **No measurable headline change:** −0.0024 on 448 like-for-like items,
   69 up and 68 down, and between −0.0082 and +0.0078 under every
   denominator.
2. **Answers Arm B completes are better grounded.** G5 failures fall from
   85 items to 2 (1 is a bench defect). PHI errors fall from 52 items to 1,
   with paired C2 +0.106; dose errors from 47 items to 12, with paired C1
   +0.069. Exclusions fall from 11 to 0. A 1–5-row sheet takes the score
   from 0.2461 to 0.4536.
3. **Two regressions cancel the gains.** 75 generation-cap cut-offs, all
   scored 0.0. Non-chemical advice falls by 0.135 paired.
4. **Refusal is unchanged.** The Phase 10 CLARIFY-shaped refusal survives
   having the registered chemistry in the prompt: 84 of 212 dose items with
   rows, against 82 for SFT. When the resolver misses the crop, refusal
   gets worse: 39 of 40.
5. **Dose safety changed shape, not just level.** Fewer items overdose
   (7/66 vs 26/159). The new errors are copy errors from the sheet: 10×
   decimal shifts and per-hectare numbers under a per-acre basis. They are
   larger than anything in the SFT run.

### It does not show

- **That retrieval is worth +X.** The three confounds below are each
  large enough to move the headline.
- **That the 15-row cap costs score.** On truncated items Arm B completed,
  the change is −0.0094. The cap costs recall of the reference product,
  which this scorer does not measure.
- **An upper bound.** Arm A (oracle keys) has not been generated or scored.

### Confound 1: Arm B retrieval is not independent of the gold labels

- **Same resolver.** `resolve_key` follows the steps of the Phase 7 tagger
  that produced the KCC items' gold crop and pest. Arm B's key equals the
  gold key on **80.7% of KCC-sourced items (306/379)**, against **65.3% of
  constructed and label_db items (79/121)**. On KCC items Arm B is closer
  to "retrieval with the labeller's own resolver" than to live retrieval.
- **Same table.** The fact sheet is drawn from label_db, the table that
  `verify.py` grades G5, C1, C2 and C3 against. Whatever rows the sheet
  shows are the answer key for those checks. So the G5, C1 and C2 gains
  measure how faithfully the model copies a key-aligned sheet, not whether
  it knows the chemistry. That is the intended deployment behaviour, but it
  is not evidence about the model's own knowledge.
- **Wrong gold.** Where the bench gold is wrong (S1_1856), Arm B is
  penalised for retrieving the right crop.

### Confound 2: input-shape novelty

The adapter was trained on the bare query. It has never seen the
`<query crop="…">` wrapper or a `<fact_sheet>` block. The cut-offs are
direct evidence that the new shape changes behaviour on its own terms:

- **Option count.** SFT's complete answers list 4 options in 132 of 159
  cases, never more. Arm B lists 5 in 12 complete answers, and the 75
  cut-offs had started 5 to 9 options (51 had started 7) when the budget
  ran out.
- **Not verbosity.** Per-option length is unchanged (median 510 vs 532
  characters).
- **No control.** No Arm C (same wrapper, empty or shuffled sheet) was run,
  so none of the deltas above can be split into "the rows helped" and "the
  wrapper changed the policy".

### Confound 3 (new): the 1,200-token generation budget

> **Resolved by Step 4c, with a cost.** The 75 were regenerated, at 2,048
> tokens and then 3,072, and every merged answer parses. Removing the
> budget artefact moved the headline by +0.0700. The merge introduces
> limitations of its own (4c.8): mixed budgets, regenerated answers that
> differ from the originals, and an unmeasured noise floor.

- **Scale.** 75 Arm B items (15%) hit `max_new_tokens`, against 2 for SFT.
  74 of the 75 had 6–15-row sheets, including 45 of the 74 truncated
  items. Of the 72 inside the headline set, 70 are in slice 1 and 38 are
  hard items.
- **Why it is a confound.** The budget was set for the SFT run's outputs.
  Applied to a treatment that lengthens outputs, it scores the length
  change as a total failure.
- **The conditional figure.** The +0.0842 in section 1 is what the
  headline would be if those items had completed and scored like the rest.
  It is a bound, not a result.

### Smaller effects

- **The CIB&RC miss line leaks the answer shape (retrieval.py decision
  3).** On no_rows NOCHEM items Arm B scores 0.2949 against SFT's 0.1613
  (+0.1336, n=31). Part of slice 5's +0.111 is the line telling the model
  the answer is "no chemistry".
- **Different exclusions.** The sheet filters contradicted rows, so Arm B
  is never excluded. The headline neutralises this by using the
  intersection.

## 10. Decisions needed

1. ~~**Re-generate Arm B's 75 cut-offs with a larger `max_new_tokens`.**~~
   **Done (Steps 4b and 4c).** 2,048 tokens finished 36 of the 75 and
   3,072 finished the other 39 (longest 2,918). The merged result is in
   Step 4c.
1a. **(Step 4c) Decide how to treat unknown PHI in fact-sheet answers.**
   Forty answers became schema-invalid by listing a PHI-less sheet row
   without escalating. Three options, each changing a different thing:
   - **The data:** a training signal so the adapter escalates.
   - **The treatment:** drop PHI-unknown rows from the sheet. That is a
     change to `retrieval.py` and would need a new Arm B generation.
   - **The prompt:** an instruction saying listing a PHI-unknown row
     requires escalation.

   Do not do any of them mid-ablation. Each changes what Arm B measures.
1b. **(Step 4c) Measure the noise floor.** Regenerate a random sample of
   the 425 pass-1 answers, about 50, in the same environment as the
   reruns. Re-score them and compare. Until then, run-to-run differences
   of a few hundredths are not evidence.
1c. **(Step 4c) The clean Arm B number** is a single 500-item run at
   3,072 tokens, repeated once. It would replace the merge and measure
   the noise floor in the same pass.
1d. **(Step 4c) Fipronil 80% WG on onion** is written at 10× in 8 of 10
   answers. Like SFT's Acetamiprid cluster, it is one wrong number,
   repeated. A post-hoc check that each emitted per-acre value matches a
   sheet row (decision 4) would catch every case.
   *Step 6:* not like Acetamiprid. It is a copy-time decimal shift, absent
   from the training data, while Acetamiprid is a memorised rate on the
   wrong pest (6.2). Step 5's validator catches all 8.
1e. **(Step 6) Give C1's range test a small tolerance at each end,** for
   example 0.1%, or compare in the label's unit at its stored precision.
   This is a `verify.py` change, so it waits until the ablation closes.
   Today it moves no model-output score (6.1).
1f. ~~**(Step 6) Phase 10's section 2.2a** should say the Acetamiprid
   number is the label's whitefly rate applied to aphid and jassid, not an
   invented value.~~ **Done in Step 7 (2026-10-25).** Section 2.2a and
   decision 6 now describe a loss of pest conditioning. The original
   wording is kept as superseded, and the overdose count is unchanged at
   24.
2. **Run Arm C** (same wrapper, empty or shuffled fact sheet) before
   attributing any change to the rows rather than the shape.
3. ~~**Amend Phase 10 section 2.2.**~~ **Done 2026-10-21 (Step 4b).**
   `reports/phase10_stepB_posttrain_audit.md` now carries the corrected
   count (24 items) in a new section 2.2a, with the original 5 kept and
   marked superseded, the C1 = 0.0 method error explained, and the
   Acetamiprid cluster named. Sections 2.1 and 2.3 are annotated with the
   same caveat and a new 2.3a adds the 2 per-hectare-as-per-acre items.
   `reports/phase10_stepA_baseline.md` needed no change: it reports the
   untrained baseline and makes no overdose claim about the SFT run.
4. **Dose-copy safety.** Arm B's three 10× errors and S1_199's
   per-hectare-as-per-acre copies happened with the correct per-acre value
   in the prompt. If RAG ships, a post-hoc check that each emitted dose
   matches a sheet row's per-acre value would catch every one. That is a
   filter-mode decision, not something to fold into this score.
5. **Crop resolution** (section 5.1). 40 dose questions got the
   could-not-identify line and 39 were refused. Two separate fixes, and
   only the first is a retrieval change: add the missing transliterated
   crop words to `crop_mapper` (19 items; `angur`, `draksh`, `bel`,
   `harbhara`), and decide where the crop comes from when the query never
   names one (21 items). **Do neither until the ablation closes** —
   `crop_mapper` feeds both arms' prompts.
6. **label_db row behind B1_36** (pomegranate Lambda-cyhalothrin 5% EC,
   raw "0.04" stored as a per-hectare rate): log it as a data defect, like
   the Phase 10 class (i) items.

## What I did not do

- No existing input was modified. `verify.py`, `retrieval.py`,
  `generate_sft.py`, `crop_mapper.py`, `bench.jsonl`, the pest table and
  both prompt files are untouched. The only existing files edited are this
  report and `reports/phase10_stepB_posttrain_audit.md` (the 24-overdose
  correction and the Acetamiprid rewording). Nothing was committed until
  Step 7.
- Files added: this report, `tools/phase12_stepA_score_rag.py`, and the
  two Step 4b outputs below.

### Step 4b outputs (added 2026-10-21)

| file | contents |
|---|---|
| `data/final/eval/rag_B_scores.json` | Arm B's 500 per-item verdicts, in `trained_scores.json`'s schema and item order (item_id, slice, crop, difficulty, total, passed, gates, checks, excluded, failures) |
| `data/interim/rag_B_rerun_ids.json` | the 75 cut-off item_ids to re-generate, with per-item evidence (response tokens, JSON error, unclosed braces, options started, fact-sheet rows) and provenance |

Both are produced by `--write-scores` / `--write-rerun-ids`, which refuse
to overwrite an existing file without `--force`. The re-run file is keyed
to `data/interim/rag_prompts_B.jsonl`: re-generate those 75 item_ids from
the **same** `user_message`, changing only `max_new_tokens`, then re-score
and the headline becomes valid without any other input changing.

### Step 4c outputs (added 2026-10-25)

| file | contents |
|---|---|
| `data/final/eval/rag_B_merged_responses.jsonl` | 500 rows, one per bench item: `raw_response`, `source_pass` (1/2/3), `max_new_tokens`, `output_tokens` (passes 2 and 3 only; pass 1 did not record it), and pass 1's retrieval metadata |
| `data/final/eval/rag_B_merged_scores.json` | the merged run's 500 per-item verdicts, in `trained_scores.json`'s schema and item order |
| `tools/phase12_step4c_merge_score.py` | builds both files and the Step 4c tables. It imports `tools/phase12_stepA_score_rag.py` without modifying it and refuses to overwrite its outputs without `--force` |

No existing file was modified by Step 4c except this report. The three
response files, `verify.py`, `retrieval.py` and `bench.jsonl` are
untouched.

### Step 6 outputs (added 2026-10-25)

`tools/phase12_step6_rounding_trace.py` is the only file added, and it is
read-only. It reuses the Step 5 repair function and the Step 4 scorer
without modifying either.

### Step 5 outputs (added 2026-10-25)

`tools/phase12_step5_validator_replay.py` is the only file added. It
writes only its `--md` tables, and nothing to `data/`: the escalation
repair exists only in memory, so no file anywhere contains repaired
answers that could pass for model output.
