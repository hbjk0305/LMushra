#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON_BIN="${SWIFT_PYTHON:-python}"
export PYTHONPATH="${PWD}/ms-swift:${PWD}${PYTHONPATH:+:${PYTHONPATH}}"
export NUMBA_CACHE_DIR="${NUMBA_CACHE_DIR:-/tmp/lmushra-numba}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0,1}"
export NPROC_PER_NODE="${NPROC_PER_NODE:-2}"

"${PYTHON_BIN}" -m swift.cli.main sft \
  --model Qwen/Qwen2-Audio-7B-Instruct \
  --use_hf true \
  --tuner_type lora \
  --torch_dtype bfloat16 \
  --dataset ./data/dummy-100/train.jsonl \
  --val_dataset ./data/dummy-100/valid.jsonl \
  --split_dataset_ratio 0 \
  --target_modules all-linear \
  --freeze_llm false \
  --freeze_vit true \
  --freeze_aligner true \
  --lora_rank 32 \
  --lora_alpha 64 \
  --lora_dropout 0.05 \
  --learning_rate 1e-4 \
  --per_device_train_batch_size 1 \
  --per_device_eval_batch_size 1 \
  --gradient_accumulation_steps 4 \
  --gradient_checkpointing true \
  --max_length 4096 \
  --max_steps 100 \
  --eval_strategy steps \
  --eval_steps 20 \
  --logging_steps 1 \
  --save_steps 50 \
  --save_total_limit 2 \
  --output_dir ./output/dummy-100 \
  --report_to tensorboard \
  "$@"
