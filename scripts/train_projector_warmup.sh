#!/usr/bin/env bash
# Stage 1 projector-only CE warmup (frozen codec, frozen LLM, no LoRA).
#
#   bash scripts/train_projector_warmup.sh dac
#   bash scripts/train_projector_warmup.sh encodec
#   CAPTION_TASK=ab bash scripts/train_projector_warmup.sh dac \
#     --max_steps 1500 --learning_rate 2e-4 --output_dir ./output/dac-projector-warmup-ab
#
# Stage 1a defaults: single-audio NISQA captions, 3000 steps, LR 5e-4, cosine, 3% warmup.
# Effective batch is EFFECTIVE_BATCH (default 8) = per-device 1 x grad-accum x GPUs.
# Probes (normal / silence / shuffle CE) run every AUDIO_PROBE_INTERVAL steps (default 500).
# Exit when probe/normal_ce is below both controls. Projector weights are written to
# <output>/checkpoint-*/multi_modal_projector.pt because the codec loader rebuilds that module.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
ENCODER="${1:-}"
case "$ENCODER" in
  dac|encodec) ;;
  *) echo 'Usage: bash scripts/train_projector_warmup.sh dac|encodec [Swift arguments]' >&2; exit 2 ;;
esac
shift

DATASET_DIR="${NISQA_DATASET_DIR:-$REPO_ROOT/data/nisqa-pretrain}"
TASK="${CAPTION_TASK:-mos}"
case "$TASK" in
  mos) N_AUDIOS=1 ;;
  ab) N_AUDIOS=2 ;;
  *) echo 'CAPTION_TASK must be mos or ab' >&2; exit 2 ;;
esac
FILTERED="$DATASET_DIR/$TASK"
PYTHON_BIN="${SWIFT_PYTHON:-python}"
export PYTHONPATH="${REPO_ROOT}/ms-swift:${REPO_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export NUMBA_CACHE_DIR="${NUMBA_CACHE_DIR:-/tmp/lmushra-numba}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0,1}"
export NPROC_PER_NODE="${NPROC_PER_NODE:-2}"
export PROJECTOR_ZERO_INIT_LAST="${PROJECTOR_ZERO_INIT_LAST:-1}"
export AUDIO_PROBE_INTERVAL="${AUDIO_PROBE_INTERVAL:-500}"
export AUDIO_PROBE_EXAMPLES="${AUDIO_PROBE_EXAMPLES:-100}"

"$PYTHON_BIN" "$REPO_ROOT/scripts/filter_caption_jsonl.py" \
  --input "$DATASET_DIR" --output "$FILTERED" --audios "$N_AUDIOS"

EFFECTIVE_BATCH="${EFFECTIVE_BATCH:-8}"
ACCUM=$(( EFFECTIVE_BATCH / NPROC_PER_NODE ))
if (( ACCUM < 1 )); then ACCUM=1; fi

"$PYTHON_BIN" -m swift.cli.main sft \
  --external_plugins "$REPO_ROOT/scripts/${ENCODER}_plugin.py" "$REPO_ROOT/scripts/audio_use_probe.py" \
  --model Qwen/Qwen2-Audio-7B-Instruct \
  --model_type "qwen2_audio_${ENCODER}" \
  --template "qwen2_audio_${ENCODER}" \
  --use_hf true \
  --tuner_type full \
  --torch_dtype bfloat16 \
  --dataset "$FILTERED/train.jsonl" \
  --val_dataset "$FILTERED/valid.jsonl" \
  --split_dataset_ratio 0 \
  --load_from_cache_file false \
  --freeze_llm true \
  --freeze_vit true \
  --freeze_aligner false \
  --learning_rate 5e-4 \
  --lr_scheduler_type cosine \
  --warmup_ratio 0.03 \
  --max_steps 3000 \
  --per_device_train_batch_size 1 \
  --per_device_eval_batch_size 1 \
  --gradient_accumulation_steps "$ACCUM" \
  --gradient_checkpointing true \
  --gradient_checkpointing_kwargs '{"use_reentrant":false}' \
  --padding_free false \
  --packing false \
  --max_length 4096 \
  --truncation_strategy delete \
  --strict true \
  --eval_strategy steps \
  --eval_steps 500 \
  --logging_steps 10 \
  --save_steps 500 \
  --save_total_limit 2 \
  --save_only_model true \
  --callbacks audio_use_probe \
  --output_dir "$REPO_ROOT/output/${ENCODER}-projector-warmup" \
  --report_to tensorboard \
  "$@"
