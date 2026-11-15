# agri-llm: label-grounded pesticide advice from a fine-tuned 7B model

I fine-tuned Qwen2.5-7B-Instruct with a LoRA adapter (QLoRA, 4-bit). It answers a
farmer's pest or disease question with a structured JSON advisory: likely
cause, non-chemical measures first, then chemical options with dose and
pre-harvest interval, and whether to call an expert. The chemical facts come
from the legally binding labels of India's Central Insecticides Board
(CIB&RC), for eight crops in Maharashtra.

The model is trained and evaluated against a deterministic verifier built
before any training, on a frozen 500-item benchmark. A deterministic
guardrail then filters its output. On the benchmark it scores **0.5840 alone**
and **0.6597 with the guardrail**.

> **⚠️ Research / portfolio project. NOT for real pesticide advice.** Wrong
> output here means a farmer applying the wrong chemical at the wrong rate.
> Always follow the product label and a local agriculture officer.

## The problem

A pesticide recommendation is only safe if three facts on the label are
right:
- **Registration.** The product must be registered for that crop *and*
  that pest. A chemical registered on one crop is not thereby registered
  on another.
- **Dose with its basis.** Per acre, per hectare, per litre of water: a
  correct number on the wrong basis is still an overdose.
- **Pre-harvest interval (PHI).** If it is unknown, the right answer is
  "ask an expert", not a guess.

General-purpose models answer fluently without checking any of these.

## Approach

1. **Ground truth:** CIB&RC "Major Uses of Pesticides" PDFs, parsed into
   `label_db`. Its 740 rows hold dose, PHI and the registered crop × pest
   pairs. Every parser refuses to guess.
2. **Verifier first:** `src/verify.py` was written before any training. Its
   gates zero an answer for unregistered chemicals, the wrong dose basis or
   an unknown PHI that isn't escalated. Graded checks then score dose, PHI,
   formulation, escalation, cause and non-chemical advice.
3. **Synthetic training data:** Claude wrote answers to Kisan Call Centre
   (KCC) farmer queries, given the matching label rows. Only answers the
   verifier scored perfect were kept: 4,493 training and 1,136 test
   examples.
4. **Frozen benchmark:** 500 items, 379 sampled from held-out data and 121
   constructed. Never trained on.
5. **QLoRA fine-tune:** Qwen2.5-7B-Instruct (4-bit), LoRA r 32, one epoch.
6. **Retrieval:** for each query, up to 15 label rows for its crop and pest
   go into the prompt as a fact sheet.
7. **Guardrail:** `src/guard.py` removes unregistered or out-of-range options
   and forces escalation when the PHI is unknown. It never adds or edits
   anything else.

## Results

All scores come from the project's verifier, on 498 benchmark items (500
minus 2 with known defects). Each score is between 0 and 1.

The arms:

| arm | what it is |
|---|---|
| R0 | the base model |
| R3 | the fine-tuned model alone |
| R2 | the base model, shown the output schema plus the fact sheet |
| R2 unwrapped | R2 re-scored with its `{"Advisory": …}` wrapper removed — a scoring check |
| R4 | the fine-tuned model plus the fact sheet |

"cap" is `max_new_tokens`.

| arm | cap | mean | scored / excl / missing | G1 % | G2 % | C1_dose | C2_phi | C3_formulation | C4_escalation | C5_causes_top1 | C6_non_chemical | hit_limit |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R0_baseline | 1,200 | **0.1726** | 498 / 0 / 0 | 100.0 | 53.0 | 0.0000 | 0.0000 | 0.0000 | 0.8182 | n/a | 0.0000 | 0 |
| R3_sft | 1,200 | **0.5220** | 487 / 11 / 0 | 99.6 | 99.4 | 0.3675 | 0.3134 | 0.4636 | 0.7913 | 0.6746 | 0.5385 | 2 |
| R2_base_rag | 3,072 | **0.2060** | 497 / 1 / 0 | 100.0 | 66.7 | 0.4575 | 0.4592 | 0.1219 | 0.4139 | 0.5556 | 0.7732 | 0 |
| R2_base_rag_unwrapped | 3,072 | **0.2912** | 487 / 11 / 0 | 100.0 | 80.1 | 0.6370 | 0.6459 | 0.1583 | 0.4665 | 0.5769 | 0.7686 | 0 |
| R4_sft_rag | 3,072 | **0.5840** | 498 / 0 / 0 | 100.0 | 91.0 | 0.3926 | 0.4204 | 0.4215 | 0.7991 | 0.6236 | 0.4122 | 0 |

Paired comparisons:
- **CI** is a percentile bootstrap: 10,000 resamples, seed 0.
- **p** is a two-sided exact sign test.

| A vs B | n | mean A | mean B | Δ (A−B) | 95% CI | wins / losses / ties | sign test p |
|---|---:|---:|---:|---:|---|---|---:|
| R4_sft_rag vs R2_base_rag | 497 | 0.5852 | 0.2060 | **+0.3792** | [+0.3236, +0.4337] | 332 / 76 / 89 | 3.07e-39 |
| R4_sft_rag vs R2_base_rag_unwrapped | 487 | 0.5791 | 0.2912 | **+0.2879** | [+0.2306, +0.3446] | 307 / 104 / 76 | 2.38e-24 |
| R4_sft_rag vs R3_sft | 487 | 0.5807 | 0.5220 | **+0.0586** | [+0.0229, +0.0939] | 105 / 59 / 323 | 4.08e-04 |
| R2_base_rag_unwrapped vs R0_baseline | 487 | 0.2912 | 0.1730 | **+0.1183** | [+0.0710, +0.1667] | 172 / 134 / 181 | 0.034 |

**With the guardrail (R4).** Counts are options / items.

| R4 | model alone | model + guard |
|---|---:|---:|
| mean (498 items) | **0.5840** | **0.6597** |
| G2 (schema-valid) % | 91.0 | 100.0 |
| overdoses (WRONG_HIGH, RANGE_TOP) | 12 / 10 | 1 / 1 |
| per-hectare dose labelled per acre | 10 / 5 | 0 / 0 |
| unregistered chemicals (G5) | 3 / 1 | 1 / 1 |
| unknown-PHI options not escalated | 87 / 45 | 0 / 0 |
| false positives (removed options the verifier grades correct) | — | 0 (of 2 unregistered + 32 dose removals) |

The one overdose left is a verifier rounding defect; the dose matches the
label. **The guard reads the same label data as the scorer**, so the
0.5840 → 0.6597 gain shows consistency between the two, not independent
proof.

## Key findings

- **Fine-tuning was necessary.** Given the same fact sheet, the fine-tuned
  model beats the base model by **+0.379** (95% CI +0.324 to +0.434).
  Forgiving the base model's formatting slip, the gap is still **+0.288**
  (+0.231 to +0.345).
- **Retrieval adds a smaller, real gain.** Fine-tuned model plus fact sheet
  against the fine-tuned model alone: **+0.059** (+0.023 to +0.094), 105
  items up and 59 down.
- **Fine-tuning lost pest conditioning, and retrieval restored it**
  (Phase 12).
  - Without a fact sheet, the model wrote Acetamiprid 20% SP at the
    whitefly rate for aphid and jassid: **10 options, 2× the label rate**.
  - With the fact sheet, **all 13** of its Acetamiprid options were right.
- **The noise floor is small.** Re-running the same prompts in a new
  environment changed the text of 105 of 425 finished answers, but the
  score of only **4 of 424** (mean |Δ| **0.0028**). That is an order of
  magnitude below the smallest effect above.
- **What the guard catches and costs.**
  - It removes **all 32** out-of-range doses the Phase 12 validator finds in
    R4.
  - It escalates **all 45** answers with an unknown PHI.
  - It has **0** false positives against the verifier.
  - It costs score on **7** items and lowers the escalation check (C4) from
    0.7991 to 0.7349.

## Limitations

**Evaluation:**
- **One judge.** Every score comes from this project's own verifier, with
  no agronomist review. The guard reads the same label data as the scorer.
- **The retrieval key overlaps with the gold labels.** The resolver
  (`resolve_key`) shares steps with the tagger that produced the gold
  labels. Its key matches gold on 80.7% of KCC-sourced items, against
  65.3% of constructed ones.
- **The runs differ in more than one way.** The no-fact-sheet runs used a
  1,200-token cap; the fact-sheet runs used 3,072. Library versions
  differed between runs, and the earliest runs recorded none.
- **One arm is missing.** The base model with the schema but no fact sheet
  was not run, so its schema and fact-sheet effects can't be separated.
- **Free text is not graded.** `verify()` grades chemicals, doses, PHI and
  escalation (plus the top cause's name, and whether any non-chemical advice
  is given), not free text.
  - Example: `B4b_7` is a grape query, but its answer names "pomegranate"
    in its evidence. It still scores 1.000 once the guard escalates it.
- **A ground-truth basis error the scorer inherits.** label_db records some
  seed-treatment (FS) doses as per hectare, where the label's bare number
  means per kg of seed. The scorer then accepts a per-acre dose for them.
  - Example: `S1_140` scores 1.000 while recommending 1.6187 ml per acre of
    two Sedaxane + Fludioxonil + Thiamethoxam FS products. Their cotton
    label dose is 4.0 ml per kg of seed.

**Guard:**
- **Some answers are only escalated, not validated.** If no crop resolves,
  nothing is checked; if no pest resolves, registration is checked at crop
  level only.
- **Some problems are counted but not removed:** mass/volume unit swaps.
- **Some answers pass through untouched:** those that fail the schema for
  any other reason.

**Training:**
- **Loss covered the whole sequence.** It was computed over system prompt +
  query + answer, not the answer only. The prompt is a median 72.5% of each
  training sequence.
- **Unverified settings.** They come from a session record, not a saved
  trainer state.
- **One run only:** no hyperparameter sweep, no repeat seeds.

**Scope:**
- Eight crops in Maharashtra only.
- Latin-script queries only (English and romanized Hindi); no Devanagari.

## Reproduce

```bash
python -m pytest tests/ -q                                       # 766 tests
python tools/score.py data/final/eval/R4_responses.jsonl --label my_R4
python tools/build_prompts.py                                    # prompts_R2/R4.jsonl
python tools/bundle_for_kaggle.py && python tools/smoke_test_kaggle_bundle.py

# on Kaggle (T4), from the uploaded bundle:
python generate.py --prompts prompts_R4.jsonl --adapter <agri_lora_final dir> \
    --out /kaggle/working/R4_responses.jsonl --max-seq-length 5911 --repetition-penalty 1.05
python generate.py --prompts prompts_R2.jsonl \
    --out /kaggle/working/R2_responses.jsonl --max-seq-length 6294 --repetition-penalty 1.05

python tools/phase14_step5_eval.py --md tables.md                # canonical table, comparisons, noise floor
python tools/apply_guard.py --write --force                      # guarded answers
python tools/score.py data/final/eval/guarded/R4_sft_rag_responses.jsonl --label my_R4_guarded
python tools/apply_guard.py --md guard_tables.md                 # before/after, false positives
```

**Files you have to rebuild.** `label_db.parquet` and `data/interim/` are
gitignored.
- **`label_db.parquet`:** rebuild it with `tools/build_label_db.py` from the
  source PDFs listed in `SOURCES.md`, or from the committed CSV as in
  `notebooks/try_it.ipynb`.
- **The fact-sheet prompts:** `tools/run_rag_eval.py --arm B` regenerates
  them.

To try the model itself, see `notebooks/try_it.ipynb` (Kaggle or Colab,
T4).

## Repository layout

| folder | contents |
|---|---|
| `src/` | label parsers, the verifier, retrieval and the guard: pure, separately tested modules |
| `tools/` | pipeline and evaluation scripts (`phaseN_*.py`, `score.py`, `generate.py`, `apply_guard.py`) |
| `tests/` | the pytest suite |
| `data/final/` | label_db, benchmark, SFT data, prompts, model responses and scores |
| `reports/` | what each phase found; start with `phase14_clean_eval.md` and `phase14_guardrail.md` |
| `hf/` | the Hugging Face model card |
| `notebooks/` | `try_it.ipynb` |
| `archive/` | a superseded schema draft |

## Links

- **Model:** <https://huggingface.co/Janhvi1008/agri-llm-qwen2.5-7b-lora>
- **Reports:** [`reports/`](reports/). The training record is
  [`reports/training_config.md`](reports/training_config.md).
