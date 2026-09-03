# Phase 8 Step A — SFT generation pipeline design (survey, no code)

Status: DESIGN FOR REVIEW. Nothing here is built. Every number below was
re-measured from the shipped files on 2026-09-01, not quoted from memory.

Sources read: `src/schema.py`, `src/system_prompt.txt`, `src/verify.py`,
`src/scope.py`, `data/final/label_db.csv`, `data/final/restricted_ai.csv`,
`data/interim/kcc_tagged.parquet`.

---

## 0. Slice mapping, reconciled against the shipped parquet

`kcc_tagged.parquet` has no `flag_F/flag_C/flag_E` columns. The flags map to:

| Roadmap flag | Actual column condition | Count |
|---|---|---|
| flag_F (dose-stating) | `answerability == "ANSWERABLE"` | 1,410 |
| flag_C (clarifying) | `answerability == "PEST_UNKNOWN"` | 4,130 |
| flag_E (refusal) | `banned_chemical_query == True` | 99 |
| — (unclaimed) | `answerability == "NO_REGISTERED_CHEMISTRY"` | 152 |

Two things the roadmap slicing does not capture:

1. **The flags overlap.** The 99 banned-chemical queries split 61 PEST_UNKNOWN
   / 36 ANSWERABLE / 2 NO_REGISTERED_CHEMISTRY. Slice assignment must be
   priority-ordered: **E first, then F, then C** — a query asking for a banned
   chemical is a refusal item even when the pest is answerable. Slice 1 is
   therefore 1,410 − 36 = 1,374 rows; Slice 2 is 4,130 − 61 = 4,069.
2. **152 NO_REGISTERED_CHEMISTRY rows belong to no slice.** scope.py calls
   these out explicitly ("These are your refusal-training cases. Do not let
   them disappear"). Proposed: **Slice 5** — correct answer is
   `chemical_options: []` + `non_chemical_first` populated (C6 enforces
   exactly this) + vector/cultural management. Cheap to generate (no fact
   sheet), high value. **DECISION NEEDED: include Slice 5?** This design
   assumes yes.

---

## 1. Shared generator architecture (all slices)

Every generation call has the same skeleton. What varies per slice is the
FACT SHEET and the TASK block.

```
[generator system prompt]                          — stable, cacheable
  You are generating training data for a plant-protection advisory
  model. Below is the system prompt that model will be deployed with,
  verbatim, delimited. Produce the JSON that model SHOULD emit.

  <deployment_system_prompt> ...src/system_prompt.txt verbatim... </>

  <output_contract>
    JSON schema derived from schema.py (Advisory / ChemicalOption /
    Dose / Cause), with the invariants spelled out in prose:
    - unknown PHI or basis "unstated" forces escalate_to_expert=true
    - phi_not_applicable never sits beside a phi_days number
    - no chemical_options when in_scope=false or query_understood=false
    Output: the JSON object only. First byte "{", last byte "}".
    No markdown fences, no prose, no trailing commentary.
  </output_contract>

  [one worked example per slice — input query + accepted JSON]

[per-item user message]                            — varies
  <query crop="..." district="..." season="...">
    ...verbatim KCC QueryText...
  </query>
  <fact_sheet> ...slice-specific, see below... </fact_sheet>
  <task> ...slice-specific instructions... </task>
```

Two mechanical rules enforced by the harness, not the prompt:

- **Structured outputs.** Call with `output_config.format` set to the Advisory
  JSON schema (or `client.messages.parse`). G1/G2 then fail only on semantic
  invariant violations, not on fences or prose — the "no markdown" instruction
  becomes belt-and-braces rather than the only defence.
- **The SFT record's prompt side is NOT the generator prompt.** `sft.jsonl`
  pairs `system_prompt.txt + farmer query` → `accepted JSON`. The fact sheet
  exists only at generation time. The trained model must answer without it;
  the fact sheet is how we make the training target correct, verify() is how
  we prove it.

---

## 2. Slice 1 — dose-stating (1,374 rows after E-overlap removal)

### 2a. Fact sheet: the only source of chemical facts

For the query's `(crop_slug, pest_canonical)`, select label_db rows where:

- both dose branches ∈ {numeric, free_text} (G7's trainable predicate);
- NOT `flag_pest_bled` and NOT `crop_multi_crop_split` (verify() excludes
  items whose candidates are defective — don't generate against them);
- NOT in `known_contradictions.csv` (verify() excludes these too);
- the a.i. is not on `restricted_ai.csv` for this crop (don't offer the
  generator a chemical G4 will kill — Monocrotophos and Carbofuran rows
  exist in label_db and are refused by the ban list's conservative
  encoding).

That filter is what takes 628 trainable rows down to the ~616 gradeable ones.

Serialize each surviving row as one compact JSON object carrying exactly the
fields the model may transcribe:

```
{"ai": "<active_ingredient verbatim>",
 "dose_basis": "...", "dose_min": .., "dose_max": .., "dose_unit": "..",
 "dose_per_acre_min": .., "dose_per_acre_max": ..,     # null off per_ha basis
 "dose_raw": "<verbatim CIB&RC cell>",
 "phi_days": .., "phi_not_applicable": bool, "phi_raw": "...",
 "application_method": "...",                           # usually null
 "biological": bool,                                    # source_file bio_*
 "pest_as_printed": "..."}
```

Hard instruction: **every number in `chemical_options` is a verbatim copy
from one fact-sheet row.** The model chooses which rows and writes the prose
(`caution`, `non_chemical_first`, `safety`, `evidence`); it never computes,
converts, or recalls a number. `dose.raw` = the row's `dose_raw`, byte for
byte.

### 2b. Option-selection policy (stated in the task block)

- Recommend 2–4 options. **Prefer rows with `phi_days` known or
  `phi_not_applicable=true`.** Picking an unknown-PHI row forces
  `escalate_to_expert=true` (G6) and flips C4's gold — legal but it turns a
  clean dose example into an escalation example. Only pick unknown-PHI rows
  when nothing else survives for the pair.
- Where `phi_not_applicable=true` (16 seed-dresser rows): emit
  `phi_days: null, phi_not_applicable: true`, no escalation. G6 verifies
  this claim in both directions.
- Dose basis: state whatever basis the chosen row carries. For `per_ha` rows,
  stating `per_acre` using the pre-derived `dose_per_acre_*` columns is
  equally valid (G8 treats the pair as compatible, C1 grades per_acre against
  the derived columns) and is the farmer-facing choice for Maharashtra.
  **Recommended: per_acre where derived values exist, per_ha otherwise;**
  either way copy the endpoints exactly, `raw` stays the printed cell.
  Never state `concentration_pct` or `per_litre_water` rows on an area basis
  (schema + G8 both forbid it).
- `spray_volume_*`: always null — no ground truth was extracted (known gap);
  an invented number is unverifiable forever.
- `likely_causes[0]` = the matched pest, high confidence — C5 grades top-1
  against the gold canonical through pest_matcher, so use the canonical name
  or a surface form the synonym table resolves.
- `non_chemical_first`: always ≥2 concrete measures. C6 only *requires* it
  when a bio row exists for the pair (the fact sheet's `biological` flag
  says so), but populating it always makes C6 moot and matches the
  deployment prompt's "non-chemical first" rule.
- `escalate_to_expert: false` when every chosen option has a known/NA PHI —
  which is exactly what C4's derived gold demands.

### 2c. Multiple matched pests

Queries like "RED MITES AND WHITE FLY ATTACK ON COTTON" name >1 organism.
`kcc_tagged.pest_canonical` carries one canonical per row (the tagger's
pick), but generation should re-run the matcher on the pest string and
branch:

- **One canonical** → normal path.
- **≥2 canonicals, non-empty chemistry intersection** (a.i. registered for
  *every* matched pest on this crop): fact sheet = the union of rows grouped
  by pest; instruct the model to list each pest in `likely_causes` and draw
  `chemical_options` only from the intersection. Verification: run
  verify(gate) once **per canonical** with the same output; accept only if
  every run passes (G5 fails any option not registered for that run's pest,
  which is precisely the intersection constraint).
- **≥2 canonicals, empty intersection** → do not force one answer to serve
  two masters. Generate a single-pest advisory for the tagged
  `pest_canonical`, mention the second organism only in `safety`/prose, and
  verify against the tagged pest. (Alternative: split into two SFT examples
  with rewritten single-pest queries — more data but synthetic query text;
  not recommended for v1.)

### 2d. Application method

Regex the query for method signals before building the fact sheet
(measured in-corpus: "drench(ing)" 34 hits, "seed treat/dress" 34, "soil
applic" 1):

- Signal found → set `VerifyContext.application_method` and narrow
  fact-sheet rows to that method **only if survivors exist** — the same
  or-else-keep rule `_narrow_candidates` uses, because a method matching no
  row is not evidence every row is wrong. Only 8 of 740 label_db rows carry
  a non-null method, so this rarely bites, but when it does it's a 6× dose
  gap (the Clothianidin cotton/Jassid example in verify.py).
- No signal → no narrowing, `application_method=None`, and verify() keeps
  both claims in the candidate set; a method-divergent pair then resolves
  AMBIGUOUS → excluded in gate mode, which is correct.

---

## 3. Slice 2 — clarifying question (4,069 rows after E-overlap removal)

No label_db rows in the prompt. Instead the fact sheet is the **scope
context** that grounds the question in the actual ambiguity:

```
<scope_context>
  crop: onion
  in-scope targets for this crop (from scope.TARGETS):
    Thrips (pest) | Purple blotch (disease) | Stemphylium blight (disease)
    | Basal rot (disease) | Anthracnose (disease)
  confusable pairs on this crop (from scope.CONFUSABLE_PAIRS):
    Purple blotch vs Stemphylium blight
  synonym hints (scope.SYNONYMS entries relevant to these targets)
</scope_context>
```

Task block:

- Decide which of the listed targets the vague description could plausibly
  be ("sucking pest on onion" → Thrips; "yellowing in soybean" → Yellow
  mosaic vs nutrient vs Rust).
- `query_understood: false`; `chemical_options: []`; `in_scope: true`.
- `likely_causes`: 0–3 candidates, every confidence ≤ 0.4, drawn from the
  listed targets (plus `nutrient`/`abiotic` where honest).
- `clarifying_question`: ONE question whose answer **discriminates between
  the listed candidates** — plant part, symptom morphology, or crop stage.
  Reject-listed phrasings ("can you provide more details", "what symptoms do
  you see") are banned in the prompt and lexically filtered after
  generation: the question must reference at least one candidate-specific
  symptom or plant part.

**The escalation decision — DECISION NEEDED, this gates the whole slice.**
With no chemical options, C4 is the *only* applicable graded check, and
`_check_escalation` derives gold=True whenever answerability is
PEST_UNKNOWN. So under the verifier's defaults, every Slice 2 example must
set `escalate_to_expert: true` to gate-pass. Training 4,069 examples (≈65%
of the dataset) to escalate-and-ask teaches blanket escalation — the exact
behavior C4 exists to price. Two coherent options:

- **(a) Recommended:** pass `ctx.gold_escalate=False` for Slice 2 and
  generate `escalate_to_expert: false`. Rationale: a clarifying question is
  a continuation of the conversation, not a terminal answer; escalation is
  the right *terminal* response to an unresolvable pest, and
  `VerifyContext.gold_escalate` is the documented override for exactly this
  ("override; else derived from label_db"). The deployment prompt already
  separates the two ("ask one specific clarifying question. Do not guess"
  vs the escalate rule).
- (b) Follow the verifier default: `escalate_to_expert: true` everywhere in
  Slice 2. Zero code-path deviation, but bakes in over-escalation.

---

## 4. Slice 3 — refusal of banned chemicals (99 rows)

Fact sheet = two parts:

1. The matching `restricted_ai.csv` row(s): a.i., tier
   (banned / refused_registration / restricted_use), restricted_crops,
   instrument, date, notes — so the explanation cites the real instrument
   ("Monocrotophos: S.O. 1482(E), banned on vegetables…") instead of
   inventing law.
2. The Slice-1-style fact sheet for this (crop, pest) **with the banned
   a.i. excluded** — the legal alternatives. "Closest" = registered for the
   same crop AND same canonical pest; that is the only closeness label_db
   can certify, and G5 enforces it anyway.

Task block: name the chemical the farmer asked about, state its status and
instrument in `safety` (the schema has no dedicated field; `safety` is where
"do not use X, it is banned" belongs), recommend alternatives as normal
verbatim-copied `chemical_options`, and set `escalate_to_expert: true`.

Branch on the overlap (§0):

| Sub-case | n | Shape |
|---|---|---|
| pest ANSWERABLE | 36 | refusal + full alternative advisory (options populated) |
| pest UNKNOWN | 61 | refusal + Slice-2-style clarifying question, `chemical_options: []` |
| NO_REGISTERED_CHEMISTRY | 2 | refusal + non-chemical measures only |

Verification: `escalate_to_expert: true` conflicts with C4's derived gold on
the 36 answerable rows (alternatives with known PHI ⇒ derived gold=False).
Pass **`ctx.gold_escalate=True` for all of Slice 3** — a farmer holding or
intending to use a banned pesticide (stock disposal, prior application,
residue on produce) is a legitimate expert-contact case, and the user spec
requires the flag. G4 automatically re-checks that no *alternative* is
itself restricted.

---

## 5. Slice 4 — augmentation (grape + multilingual)

### 5a. Grape synthetic queries

Measured: grape is 79/5,692 KCC queries (1.4%), only **26** ANSWERABLE —
against **112 trainable label_db rows** and five all-"rich" targets (Downy
mildew, Powdery mildew, Anthracnose, Thrips, Mealybug). Grape is the
economically heaviest crop in the scope for Maharashtra (Nashik belt) and
the second-largest label_db crop; 26 real dose examples would leave it
essentially untrained.

**Proposed target: 300 synthetic grape queries** (≈60 per target ± chem
richness). Rationale: brings grape's dose-slice share (~300/1,700 ≈ 18%)
to rough parity with its label_db share (112/616 ≈ 18%), and ~11×
augmentation over 26 real queries is defensible when the *answers* are
verbatim label_db facts — the synthetic part is only the question surface.
Generation: template-free paraphrase batches (query-writer call produces 20
at a time) varying symptom description, growth stage (pre-bloom / berry /
veraison), month, register (English/transliterated Marathi), and misspelling
noise matched to real KCC style (ALL CAPS, "attak", missing articles).
Hold out 40 of the 300 (template-disjoint) for the Phase 9 benchmark since
the real test side has only 1–2 grape answerables (§7).

### 5b. Multilingual — what the corpus actually says

Measured against `QueryText` (5,692 rows, 99.98% Latin script):

| scope.SYNONYMS term | hits | | term | hits |
|---|---|---|---|---|
| thrips | 249 | | mava (Aphid) | 9 |
| pink bollworm | 16 | | helicoverpa | 3 |
| oily spot (telya EN) | 11 | | bhuri / davnya / karpa / telya / tudtude / phulkide / pandhri mashi / gulabi bondhali | **0** |

Plus crop-name transliterations from the tagger: arhar 30, chana 4,
dalimb 3, kapas 1. Conclusion: **KCC operators wrote English; Marathi
robustness cannot come from the real corpus and must be synthetic.**

Proposal: **~500 transliteration variants** produced by rewriting the
*query side only* of already-accepted Slice 1/5 examples — the accepted JSON
answer is reused unchanged and re-verified under the same VerifyContext, so
the answer-side cost and risk are both ~zero. Basis terms, in priority
order: the disease terms farmers actually use on the high-value crops —
**bhuri, davnya, karpa, telya** (grape/pomegranate), then **mava, phulkide,
tudtude, pandhri mashi, gulabi bondhali**, and crop names **kapas, arhar,
chana, dalimb, kanda**. Constraint carried over from scope.py verbatim:
these transliterations "MUST be checked by a native speaker before they
enter the training set" — the 500 rows ship in a separately-flagged file
pending that review.

### Resulting dataset shape (train side, cutoff §7)

| Slice | Source rows | Target accepted |
|---|---|---|
| 1 dose | 1,374 × train frac ≈ 1,120 | ~1,050 |
| 2 clarify | 4,069 × train frac ≈ 3,230 | ~3,100 |
| 3 refusal | 93 (train side) | ~90 |
| 5 no-chemistry | ~150 | ~140 |
| 4a grape | 300 synthetic − 40 benchmark | 260 |
| 4b multilingual | 500 rewrites | ~480 |
| **total sft.jsonl** | | **~5,100** |

(The roadmap's "~8,000" assumed no train/test split of the KCC rows and no
E-overlap dedup; ~5,100 verified examples is what the same slices actually
yield. If more volume is wanted, the honest lever is more Slice 4a/4b
augmentation, not double-counting.)

---

## 6. verify() acceptance policy

Per generated example, in a loop:

```
ctx = VerifyContext(resources, crop_slug, pest_query=<KCC pest surface form>,
                    application_method=<from query regex, §2d>,
                    gold_escalate=<None | False (S2) | True (S3)>)
res = verify(output, ctx, mode="gate")
```

- **Accept iff `res.passed`** — gate mode's definition: all gates true AND
  `total == 1.0`. **Threshold is exactly 1.0, no partial credit.** A 0.9
  example is an example with a wrong dose, PHI, formulation or escalation in
  it; the whole point of generating from the fact sheet is that 1.0 is
  cheaply reachable, so anything below it is a generation bug, not noise to
  tolerate.
- **`res.excluded` → drop silently, never retry.** Exclusion means *our*
  ground truth is defective or ambiguous (contradicted rows, damaged
  fragments, AMBIGUOUS consensus); regenerating cannot fix it. Log to an
  exclusion sidecar mirroring `exclusion_log.csv` practice.
- **Failed → retry ≤2 with `res.failures` appended** to the generator
  message ("your previous attempt failed these checks: …"), then drop and
  log. Failures text is written for exactly this use.
- Multi-pest items: all per-canonical verify() runs must pass (§2c).

**The free_text question (Slice 1):** if the matched row's product dose is
genuine prose (`dose_formulation_branch == "free_text"`, 10 rows), the model
must emit `basis: "free_text"` with no numbers and `raw` = the prose
verbatim. verify() handles this correctly but cannot grade the string: C1
returns no verdict (no numeric bounds) and leaves the denominator, G8
*would* catch a fabricated numeric basis (`free_text` is incompatible with
every numeric basis), G9 doesn't fire (`free_text` ≠ `unstated`). So:
**ACCEPT, with one supplementary lexical check in the generator harness** —
`dose.raw` must byte-equal one fact-sheet `dose_raw` for that a.i. — because
that string is the one trainable fact the verifier cannot certify. A model
output that instead states a *number* for such a row is rejected by G8
automatically. (This is "free_text basis in label_db" — distinct from
`unstated`, which per G9 must only appear on rows with *no* parseable dose
and forces escalation.)

**`phi_not_applicable=True` rows:** fully supported, not a special case to
avoid. Fact sheet carries the flag and `phi_raw`; the model emits
`phi_days: null, phi_not_applicable: true`; G6 fails the claim in either
wrong direction; no escalation is forced (that is the point of the
2026-09-01 re-freeze). The 16 rows include the only seed-treatment answers
in scope (cotton Imidacloprid 48% FS etc.) — they are the ground truth for
the seed-treatment queries §2d routes.

---

## 7. Train/test split

**Date-based on `CreatedOn`, cutoff `2022-01-01`.** Measured outcomes:

| Cutoff | Train | Test | Test ANSW | Test banned | Test grape-ANSW |
|---|---|---|---|---|---|
| 2021-01-01 | 4,053 | 1,639 | 344 | 6 | 2 |
| **2022-01-01** | **4,491** | **1,201 (21%)** | **272** | **6** | **2** |
| 2022-07-01 | 4,549 | 1,143 | 256 | 6 | 1 |
| 2023-01-01 | 5,184 | 508 (9%) | 100 | 3 | 1 |

2022-01-01 gives ~79/21 with a calendar-clean boundary and a test side big
enough to power the benchmark (272 answerable, 895 pest-unknown);
2023-01-01 starves it. **Target ratio: ~80/20.**

Leakage controls, each pinned by an assertion in the eventual build script:

1. **sft.jsonl draws only from `CreatedOn < 2022-01-01`.** The Phase 9
   benchmark draws only from `>= 2022-01-01` plus constructed items
   (CONFUSABLE_PAIRS, CROSS_CROP_PESTS, the 40 held-out grape synthetics,
   synthetic banned-chemical items to supplement the thin 6 real ones).
2. **Cross-cutoff near-dupes are removed from the *test* side.** Measured:
   16 exact-normalized query repeats cross the boundary despite the Phase C
   semantic dedup ("thrips on cotton" phrasings recur across years). Drop
   test rows whose normalized text (lowercase, whitespace-collapsed) — or
   MinHash near-dupe — appears on the train side; dropping from test keeps
   train volume and costs the benchmark ~1% of items.
3. **All augmentation is train-parented.** Grape query-writer prompts may
   only be seeded with pre-cutoff real grape queries; multilingual rewrites
   only of accepted train examples. The 40 benchmark grape items come from
   a disjoint paraphrase batch never emitted to sft.jsonl.
4. **Disjointness test:** a pytest asserts no benchmark item shares a KCC
   row id or a normalized query string with any sft.jsonl record.

---

## 8. Cost estimate — claude-sonnet-4-6, $3/M input, $15/M output

Per-call token budget (measured/estimated):

| Component | Tokens |
|---|---|
| Generator preamble + output contract + worked example | ~1,400 (stable → cacheable) |
| system_prompt.txt verbatim | ~620 (stable → cacheable) |
| Slice 1/3 fact sheet: mean 24.7 rows/pair (median 8, p90 74) × ~85 tok | ~2,100 mean |
| Slice 2 scope context | ~300 |
| KCC query + metadata | ~50 |
| Output: Slice 1/3/4a advisory (2–4 options) | ~700 |
| Output: Slice 2/5 advisory (no options) | ~250 |
| Output: Slice 4b rewrite | ~80 |

Per-slice, generating the full corpus (~both sides, matching the roadmap's
~8,000-call framing) with a 1.3×/1.1× retry factor:

| Slice | Calls | Input Mtok | Output Mtok |
|---|---|---|---|
| 1 dose (1,374) | ~1,800 | 7.6 | 1.26 |
| 2 clarify (4,069) | ~4,500 | 10.7 | 1.13 |
| 3 refusal (99) | ~130 | 0.6 | 0.08 |
| 5 no-chem (152) | ~170 | 0.4 | 0.04 |
| 4a grape (300 + writer) | ~410 | 1.7 | 0.28 |
| 4b multilingual (500) | ~550 | 0.4 | 0.05 |
| **Total** | **~7,560** | **~21.4** | **~2.8** |

- **Straight Messages API: ~$64 input + ~$42 output ≈ $106.**
- **Batch API (50%, generation is not latency-sensitive): ≈ $53.**
- Prompt caching on the ~2,000-token stable prefix (write 1.25×/read 0.1×)
  saves a further ~$30 of the non-batch figure; batch + caching interaction
  is best-effort, so quote **$50–110 total** depending on path and realized
  retry rate. Train-side-only generation (§5 table) is ~35% less.

If Slice 1 items are grouped by (crop, pest) and sorted, the fact sheet
itself becomes a repeating prefix within each group — a second cache
breakpoint after the fact sheet makes the marginal call nearly free for the
big pairs (Thrips-cotton has 186 queries over one 74-row sheet).

---

## 9. Decisions needed before building

1. **Slice 5** (152 NO_REGISTERED_CHEMISTRY rows) — include? (§0, assumed yes)
2. **Slice 2 escalation** — `gold_escalate=False` override (recommended) or
   verifier-default `escalate=true` on 65% of the dataset? (§3)
3. **Slice 3** `gold_escalate=True` override — confirm. (§4)
4. Grape target **300** (40 held out for benchmark) — confirm or resize. (§5a)
5. Multilingual **500 rewrites**, shipped behind a native-speaker review
   flag — confirm. (§5b)
6. Cutoff **2022-01-01**, test-side dedup of cross-boundary repeats — confirm. (§7)
7. Dose basis preference: per_acre-where-derivable (farmer-facing) vs
   per_ha-as-printed. (§2b, recommended per_acre)
8. Batch API vs live calls. (§8)
