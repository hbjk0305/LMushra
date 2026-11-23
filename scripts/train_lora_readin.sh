#!/usr/bin/env bash
# Stage 2: LoRA on the frozen LLM, projector loaded from Stage 1 and kept frozen.
#
#   bash scripts/train_lora_readin.sh dac ./output/dac-projector-warmup/v0-*/checkpoint-3000/multi_modal_projector.pt
#
# Pass the base Qwen model through Swift as usual. Do not point --model at the full
# warmup checkpoint: the codec loader discards and rebuilds multi_modal_projector.
# Fresh optimizer (no --resume_from_checkpoint). Default 2000 steps, LoRA LR 2e-5.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
ENCODER="${1:-}"
PROJECTOR="${2:-}"
case "$ENCODER" in
  dac|encodec) ;;
  *) echo 'Usage: bash scripts/train_lora_readin.sh dac|encodec PATH_TO_multi_modal_projector.pt [Swift arguments]' >&2
     exit 2 ;;
esac
if [[ -z "$PROJECTOR" || ! -f "$PROJECTOR" ]]; then
  echo "Projector checkpoint not found: ${PROJECTOR:-<missing>}" >&2
  exit 2
fi
shift 2

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
export PROJECTOR_CHECKPOINT="$(cd "$(dirname "$PROJECTOR")" && pwd)/$(basename "$PROJECTOR")"
export PROJECTOR_ZERO_INIT_LAST=0
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
  --tuner_type lora \
  --torch_dtype bfloat16 \
  --dataset "$FILTERED/train.jsonl" \
  --val_dataset "$FILTERED/valid.jsonl" \
  --split_dataset_ratio 0 \
  --load_from_cache_file false \
  --target_modules all-linear \
  --freeze_llm false \
  --freeze_vit true \
  --freeze_aligner true \
  --lora_rank 32 \
  --lora_alpha 64 \
  --lora_dropout 0.05 \
  --learning_rate 2e-5 \
  --lr_scheduler_type cosine \
  --warmup_ratio 0.03 \
  --max_steps 2000 \
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
  --callbacks audio_use_probe \
  --output_dir "$REPO_ROOT/output/${ENCODER}-lora-readin" \
  --report_to tensorboard \
  "$@"
