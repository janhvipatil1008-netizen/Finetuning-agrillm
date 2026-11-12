# Training record — the SFT run that produced `agri_lora_final`

> **Source: session record, not a committed file.** The training cell was
> run on Kaggle and never committed to this repository. The settings below
> are as recorded in the working session. They have **not** been verified
> against a saved `trainer_state.json`, which is not in the repo. The
> cross-checks in §2 are the only independent evidence available.

The session record calls this the **Phase 9 SFT run**. In this repo's
numbering, Phase 9 is the benchmark freeze (commit `7a0b6f0`, 2026-09-03),
and the post-training evaluation is Phase 10 Step B. The adapter files in
`models/agri_lora_final/` are dated 2026-09-21. That is after the Phase 10
untrained baseline (generated 2026-09-11) and before the post-training
responses (`trained_responses.jsonl`, 2026-09-22). So the run sits between
Phase 10 Steps A and B, whatever it is called.

## 1. Settings (from session record)

| setting | value |
|---|---|
| trainer | TRL `SFTTrainer` via Unsloth |
| base model | `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` (4-bit, QLoRA) |
| epochs | 1 |
| steps | 281 |
| learning rate | 2e-4, cosine schedule |
| warmup steps | 20 |
| per-device train batch size | 2 |
| gradient accumulation steps | 8 (effective batch 16) |
| optimizer | `adamw_8bit` |
| weight decay | 0.01 |
| precision | fp16 (T4 has no bf16) |
| max length | 2048 |
| seed | 42 |
| GPU | Kaggle T4 |
| dataset field | `dataset_text_field="text"`, no completion-only option |

**Run history.**
- The run was interrupted and resumed from `checkpoint-100`.
- The final logged loss was about **0.18**.
- The trainer's reported `training_loss` of 0.1267 is an artefact of the
  resume. **Do not quote it.**

**Loss masking.** With `dataset_text_field="text"` and no completion-only
option, the loss was computed over the **full sequence**: system prompt,
query and answer, not the answer alone. **Fix for a future run:**
`assistant_only_loss=True`, or a completion-only collator, so that only
the assistant turn is trained.

## 2. Cross-checks against the repo

| check | repo evidence | session record | result |
|---|---|---|---|
| LoRA r / alpha / dropout | `adapter_config.json`: 32 / 64 / 0 | — | consistent |
| target modules | `adapter_config.json`: `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj` (7) | — | consistent |
| base model | `adapter_config.json`: `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` | same | consistent |
| train / test examples | `sft_train.jsonl` 4,493 rows; `sft_test.jsonl` 1,136 rows | — | consistent with the Phase 8 record (4,493 / 1,136) |
| steps | ceil(4,493 / 16) = **281** | 1 epoch, effective batch 16, 281 steps | **consistent** |
| max length 2048 | chat-templated training examples: min 701, median 910, p99 1,944, max 2,540 tokens; **11 of 4,493 exceed 2,048** | 2048 | see below |

**No conflicts.** Two consequences follow.

**1. Eleven examples were probably truncated.** The SFT rows carry only
`messages`, so the training cell built the `text` field itself; how is not
recorded. If it applied the Qwen chat template to the messages, as measured
here, 11 examples (0.2%) are longer than `max_length` and lost the end of
their answer in training.

**2. Most of the loss was on the prompt.** Every training example carries
the same 642-token system prompt, and the prompt (system + query + template
header) is a median **72.5%** of each sequence. The answer is a median 250
tokens. With full-sequence loss, most of each step's loss was spent
reproducing that repeated prompt rather than the answer.
- The cleaner fix is answer-only loss, not a shorter prompt.
- The system prompt is frozen and is part of the deployment contract.

Lengths are measured with the Qwen2.5-7B-Instruct tokenizer
(`transformers` 5.0.0), chat template applied with
`apply_chat_template(..., tokenize=False)` and then encoded.

## 3. What is not known

- **No `trainer_state.json`, loss curve or evaluation loss is
  committed.** "About 0.18" is the last logged value as recorded.
- **One training run.** There was no hyperparameter sweep and no repeat
  with other seeds, so there is no estimate of run-to-run variance in the
  adapter itself. Phase 14's noise floor measures generation noise only,
  not training noise.
