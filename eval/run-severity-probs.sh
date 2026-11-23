#!/usr/bin/env bash
set -euo pipefail

# Generate one token per request and keep the top log-probabilities, for the 1-5
# severity question built by eval/odaq/severity_requests.py.
# Usage from the repository root:
#   bash eval/run-severity-probs.sh ENCODER CHECKPOINT_DIR REQUESTS_JSONL OUT_JSONL
# Example:
#   CUDA_VISIBLE_DEVICES=0 bash eval/run-severity-probs.sh dac \
#     /mnt/data2/hwangbo5/checkpoints/calibrated_llm-dac/v1-20261116-160324/checkpoint-16400 \
#     eval/odaq/severity_direct.jsonl result/infer_dac/checkpoint-16400_severity_direct.jsonl
# Needs about 18 GB of GPU memory. SWIFT_PYTHON selects the interpreter (default: python on PATH).

if [[ $# -ne 4 ]]; then
  echo "Usage: bash $0 ENCODER CHECKPOINT_DIR REQUESTS_JSONL OUT_JSONL" >&2
  exit 2
fi
encoder=$1 checkpoint=$2 requests=$3 out=$4
case "$encoder" in dac|encodec) ;; *) echo "Unsupported encoder: $encoder" >&2; exit 2 ;; esac
[[ -d $checkpoint && -f $requests ]] || { echo "Missing checkpoint or requests: $checkpoint $requests" >&2; exit 2; }

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
export PYTHONPATH="$repo_dir/ms-swift:$repo_dir${PYTHONPATH:+:$PYTHONPATH}"
export NUMBA_CACHE_DIR=${NUMBA_CACHE_DIR:-/tmp/lmushra-numba}
export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}
mkdir -p -- "$(dirname -- "$out")"

"${SWIFT_PYTHON:-python}" -m swift.cli.main infer \
  --model Qwen/Qwen2-Audio-7B-Instruct \
  --adapters "$(realpath -- "$checkpoint")" \
  --use_hf true \
  --infer_backend transformers \
  --val_dataset "$(realpath -- "$requests")" \
  --result_path "$out" \
  --max_batch_size 1 \
  --max_new_tokens 1 \
  --temperature 0 \
  --logprobs true \
  --top_logprobs 50 \
  --stream false \
  --load_from_cache_file false \
  --external_plugins "$repo_dir/scripts/${encoder}_plugin.py" \
  --model_type "qwen2_audio_$encoder" \
  --template "qwen2_audio_$encoder" \
  2>&1 | tee "${out%.jsonl}.log"
