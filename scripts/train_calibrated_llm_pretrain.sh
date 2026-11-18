#!/usr/bin/env bash
# Usage: bash scripts/train_nisqa_pretrain.sh baseline|dac|encodec [Swift arguments]
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
ENCODER="${1:-}"
case "$ENCODER" in
  baseline) EXTRA=() ;;
  dac|encodec)
    EXTRA=(--external_plugins "$REPO_ROOT/scripts/${ENCODER}_plugin.py"
           --model_type "qwen2_audio_${ENCODER}" --template "qwen2_audio_${ENCODER}"
           --modules_to_save multi_modal_projector) ;;
  *) echo 'Usage: bash scripts/train_nisqa_pretrain.sh baseline|dac|encodec [Swift arguments]' >&2; exit 2 ;;
esac
shift
PYTHON_BIN="${SWIFT_PYTHON:-python}"
# DATASET_DIR="${NISQA_DATASET_DIR:-/scratch/tingyup2/projects/AudioLM/production/phase1_real_speech_music_v1/manifests/checkpoint_1000000}"
DATASET_DIR="${NISQA_DATASET_DIR:-/scratch/tingyup2/projects/AudioLM/annotations/caption-poc-fast-v3/run/snapshots/population_1000000/calibrated_llm}"

DATASET_DIR="$(cd "$DATASET_DIR" && pwd)"
# Resolve manifest audio paths (e.g. shards/...) from this directory.
# AUDIO_ROOT="${NISQA_AUDIO_ROOT:-/scratch/tingyup2/projects/AudioLM/production/phase1_real_speech_music_v1}"
for split in train valid; do
  if [[ ! -s "$DATASET_DIR/$split.jsonl" ]]; then
    echo "Missing $DATASET_DIR/$split.jsonl; run python scripts/prepare_nisqa_pretrain.py first." >&2
    exit 2
  fi
done
export PYTHONPATH="${REPO_ROOT}/ms-swift:${REPO_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export NUMBA_CACHE_DIR="${NUMBA_CACHE_DIR:-/tmp/lmushra-numba}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0,1}"
export NPROC_PER_NODE="${NPROC_PER_NODE:-2}"
# cd "$AUDIO_ROOT"
"$PYTHON_BIN" -m swift.cli.main sft \
  --model Qwen/Qwen2-Audio-7B-Instruct --use_hf true \
  "${EXTRA[@]}" \
  --tuner_type lora --torch_dtype bfloat16 \
  --dataset "$DATASET_DIR/train.jsonl" --val_dataset "$DATASET_DIR/valid.jsonl" \
  --split_dataset_ratio 0 --load_from_cache_file false \
  --target_modules all-linear --freeze_llm false --freeze_vit true --freeze_aligner true \
  --lora_rank 32 --lora_alpha 64 --lora_dropout 0.05 \
  --learning_rate 2e-5 --warmup_ratio 0.03 --num_train_epochs 1 \
  --per_device_train_batch_size 16 --per_device_eval_batch_size 1 \
  --gradient_accumulation_steps 2 --gradient_checkpointing true \
  --gradient_checkpointing_kwargs '{"use_reentrant":false}' \
  --padding_free false --packing false --max_length 4096 \
  --truncation_strategy delete --strict true \
  --eval_strategy steps --eval_steps 200 --logging_steps 10 \
  --save_steps 200 --save_total_limit 2 \
  --output_dir "$REPO_ROOT/output/calibrated_llm-${ENCODER}" --report_to tensorboard \
  "$@"
