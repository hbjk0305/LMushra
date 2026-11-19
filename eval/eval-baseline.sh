#!/usr/bin/env bash
set -euo pipefail

# Usage from the repository root:
#   bash eval/eval-baseline.sh ENCODER CHECKPOINT_DIR REQUESTS_JSONL
# Example:
#   bash eval/eval-baseline.sh dac \
#     output/phase1_real_speech_music_v1-dac/v2-20261115-153620/checkpoint-6400 \
#     eval/odaq/requests.jsonl
# Supported encoders: dac, encodec.
# Outputs go next to REQUESTS_JSONL in TRAINING_DIR--RUN_DIR--CHECKPOINT_DIR.
# Override the default GPU (0) or Python interpreter with CUDA_VISIBLE_DEVICES
# or SWIFT_PYTHON.

usage() {
  echo "Usage: bash $0 ENCODER CHECKPOINT_DIR REQUESTS_JSONL"
}

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
  usage
  exit 0
fi
if [[ $# -ne 3 ]]; then
  usage >&2
  exit 2
fi
encoder=$1
case "$encoder" in
  dac|encodec) ;;
  *)
    echo "Unsupported encoder: $encoder (expected dac or encodec)" >&2
    exit 2
    ;;
esac
if [[ ! -d "$2" || ! -f "$3" ]]; then
  echo "Expected an existing checkpoint directory and request file: $2 $3" >&2
  exit 2
fi

checkpoint=$(realpath -- "$2")
requests=$(realpath -- "$3")
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
run_dir=$(dirname -- "$checkpoint")
training_name=$(basename -- "$(dirname -- "$run_dir")")
out=$(dirname -- "$requests")/"$training_name--$(basename -- "$run_dir")--$(basename -- "$checkpoint")"

python_bin=${SWIFT_PYTHON:-/home/hwangbo5/miniconda3/envs/swift/bin/python}
export PATH="$(dirname -- "$python_bin"):$PATH"
export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}
export PYTHONPATH="$repo_dir/ms-swift:$repo_dir${PYTHONPATH:+:$PYTHONPATH}"
export NUMBA_CACHE_DIR=${NUMBA_CACHE_DIR:-/tmp/lmushra-numba}

mkdir -p -- "$out"
cd -- "$repo_dir"
echo "Writing evaluation results to $out"
"$python_bin" -m swift.cli.main infer \
  --model Qwen/Qwen2-Audio-7B-Instruct \
  --adapters "$checkpoint" \
  --use_hf true \
  --infer_backend transformers \
  --val_dataset "$requests" \
  --result_path "$out/predictions.jsonl" \
  --max_batch_size 1 \
  --max_new_tokens 160 \
  --temperature 0 \
  --stream false \
  --load_from_cache_file false \
  --external_plugins "$repo_dir/scripts/${encoder}_plugin.py" \
  --model_type "qwen2_audio_$encoder" \
  --template "qwen2_audio_$encoder" \
  > "$out/inference.log" 2>&1
