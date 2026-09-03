#!/bin/bash
# Slice 2 generation via Groq's free tier (GroqBackend, tools/generate_sft.py).
#
# Estimated time: ~4 hours at the free tier's 30 req/min cap (~4,055
# buildable Slice 2 items + retries; measured item count via a real
# --slices 2 dry-run on 2026-09-03, not the 4,069 raw partition count --
# a few rows drop out at the date-split cross-boundary dedup step).
#
# Prerequisites:
#   - GROQ_API_KEY env var set (or pass --groq-api-key on the line below)
#   - `openai` package installed (already present in this repo's venv;
#     elsewhere: pip install openai)
#
# --resume is load-bearing here, not decorative: a 4-hour rate-limited run
# WILL be interrupted at some point (Kaggle session timeout, network blip).
# Re-running this exact command after an interruption skips every row
# already 'accepted' or 'rejected_after_retries' in
# data/final/sft_generation_log.csv and merges new results into the
# existing sft_train.jsonl / sft_test.jsonl / sft_generation_log.csv rather
# than overwriting them. Without --resume, a re-run regenerates everything
# from scratch and re-spends the whole rate-limit budget.
set -euo pipefail

python tools/generate_sft.py \
  --backend groq \
  --slices 2 \
  --model qwen/qwen3.6-27b \
  --out-dir data/final \
  --resume
