#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash scripts/train_mushra_two_stage.sh serial dac|encodec [--max_steps N]
  bash scripts/train_mushra_two_stage.sh projector dac|encodec [Swift arguments]
  bash scripts/train_mushra_two_stage.sh lora dac|encodec PROJECTOR_CHECKPOINT [TRAIN_JSONL VALID_JSONL] [Swift arguments]

Generated manifests use Reference and Processed. Set INCLUDE_RESIDUAL=1 to add Residual.
LoRA targets include artifact, estimated_severity, and description by default.
Override the manifest source and audio root with NISQA_DATASET_DIR and NISQA_AUDIO_ROOT.
Serial uses the full dataset for projector training and the matched subset for LoRA.
Use STAGE1_DATASET_DIR to override the serial projector dataset. --max_steps caps stage one only.
Use SWIFT_PYTHON to select the Python environment.
EOF
}

if [[ ${1:-} == --help ]]; then
  usage
  exit 0
fi
if [[ $# -lt 2 ]]; then
  usage >&2
  exit 2
fi

stage=$1
encoder=$2
shift 2
case "$encoder" in
  dac|encodec) ;;
  *) usage >&2; exit 2 ;;
esac

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
python_bin="${SWIFT_PYTHON:-python}"
export PYTHONPATH="$repo_root/ms-swift:$repo_root${PYTHONPATH:+:$PYTHONPATH}"
export NUMBA_CACHE_DIR="${NUMBA_CACHE_DIR:-/tmp/lmushra-numba}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0,1}"
export NPROC_PER_NODE="${NPROC_PER_NODE:-2}"

prepare_manifests() {
    local run_name=$1 dataset_dir audio_root prepared_dir input_variant
    local -a residual_args
    shift
    dataset_dir="${NISQA_DATASET_DIR:-/data/hwangbo5/matched_ablations/calibrated_llm_sev}"
    audio_root="${NISQA_AUDIO_ROOT:-/data/hwangbo5/phase1_real_speech_music_v1}"
    residual_args=()
    input_variant=pair
    case "${INCLUDE_RESIDUAL:-0}" in
      0) ;;
      1) residual_args=(--include-residual); input_variant=residual ;;
      *) echo 'INCLUDE_RESIDUAL must be 0 or 1' >&2; exit 2 ;;
    esac
    output_dir="$repo_root/output/${run_name}-${encoder}-${input_variant}/runs"
    prepared_dir="${LMUSHRA_MANIFEST_DIR:-$repo_root/output/${run_name}-${encoder}-${input_variant}/manifests}"
    "$python_bin" "$repo_root/scripts/prepare_projector_dataset.py" \
      "$dataset_dir" "$prepared_dir" --audio-root "$audio_root" "${residual_args[@]}" "$@"
    train="$prepared_dir/train.jsonl"
    valid="$prepared_dir/valid.jsonl"
}

case "$stage" in
  serial)
    if [[ $# -ne 0 ]] && [[ $# -ne 2 || "$1" != --max_steps || ! "$2" =~ ^[1-9][0-9]*$ ]]; then
      usage >&2
      exit 2
    fi
    launcher="$repo_root/scripts/train_mushra_two_stage.sh"
    mkdir -p "$repo_root/output"
    stage1_dir="$(mktemp -d "$repo_root/output/serial-$encoder-stage1.XXXXXX")"
    NISQA_DATASET_DIR="${STAGE1_DATASET_DIR:-/data/hwangbo5/calibrated_llm_sev}" \
      LMUSHRA_MANIFEST_DIR="$stage1_dir/manifests" \
      bash "$launcher" projector "$encoder" --output_dir "$stage1_dir" --add_version false "$@"

    checkpoint="$(find "$stage1_dir" -maxdepth 1 -type d -name 'checkpoint-*' | sort -V | tail -n 1)"
    if [[ -z "$checkpoint" || ! -f "$checkpoint/config.json" ]] ||
       [[ ! -f "$checkpoint/model.safetensors" && ! -f "$checkpoint/model.safetensors.index.json" ]]; then
      echo "No usable projector checkpoint found in $stage1_dir" >&2
      exit 1
    fi
    echo "Stage two will use projector checkpoint $checkpoint"
    stage2_dir="$(mktemp -d "$repo_root/output/serial-$encoder-stage2.XXXXXX")"
    echo "Stage two output directory: $stage2_dir"
    exec bash "$launcher" lora "$encoder" "$checkpoint" --output_dir "$stage2_dir" --add_version false
    ;;
  projector)
    unset LMUSHRA_PROJECTOR_CHECKPOINT
    prepare_manifests mushra-projector
    stage_args=(--tuner_type full --freeze_llm true --freeze_vit true --freeze_aligner false
                --freeze_parameters_regex '^(?!multi_modal_projector\.)'
                --safe_serialization true --learning_rate 1e-4
                --eval_strategy epoch --save_steps 2000)
    ;;
  lora)
    if [[ $# -lt 1 || ! -f "$1/config.json" ]]; then
      usage >&2
      exit 2
    fi
    export LMUSHRA_PROJECTOR_CHECKPOINT="$(realpath "$1")"
    shift
    stage_args=(--tuner_type lora --freeze_llm false --freeze_vit true --freeze_aligner true
                --target_modules all-linear --lora_rank 32 --lora_alpha 64 --lora_dropout 0.05
                --learning_rate 2e-5)
    if [[ $# -eq 0 || "$1" == --* ]]; then
      prepare_manifests mushra-lora-caption --include-description
      stage_args+=(--eval_strategy epoch --save_steps 2000)
    else
      if [[ $# -lt 2 || ! -s "$1" || ! -s "$2" ]]; then
        usage >&2
        exit 2
      fi
      train="$(realpath "$1")"
      valid="$(realpath "$2")"
      shift 2
      output_dir="$repo_root/output/mushra-lora-$encoder"
      stage_args+=(--eval_strategy steps --eval_steps 200 --save_steps 200)
    fi
    ;;
  *) usage >&2; exit 2 ;;
esac

mkdir -p "$NUMBA_CACHE_DIR"
exec "$python_bin" -m swift.cli.main sft \
  --external_plugins "$repo_root/scripts/${encoder}_plugin.py" \
  --model Qwen/Qwen2-Audio-7B-Instruct --use_hf true \
  --model_type "qwen2_audio_${encoder}" --template "qwen2_audio_${encoder}" \
  --dataset "$train" --val_dataset "$valid" --split_dataset_ratio 0 \
  --load_from_cache_file false --torch_dtype bfloat16 "${stage_args[@]}" \
  --warmup_ratio 0.03 --num_train_epochs 1 \
  --per_device_train_batch_size 1 --per_device_eval_batch_size 1 \
  --gradient_accumulation_steps 8 --gradient_checkpointing true \
  --gradient_checkpointing_kwargs '{"use_reentrant":false}' \
  --padding_free false --packing false --max_length 4096 --truncation_strategy delete --strict true \
  --save_total_limit 2 --logging_steps 10 \
  --output_dir "$output_dir" --report_to tensorboard "$@"
