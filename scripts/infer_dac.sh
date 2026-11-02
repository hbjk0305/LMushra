#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $# -lt 1 ]]; then
  echo "Usage: bash scripts/infer_dac.sh PATH_TO_CHECKPOINT [additional swift arguments]" >&2
  exit 2
fi
ADAPTER_PATH="$1"
shift
PYTHON_BIN="${SWIFT_PYTHON:-python}"
export PYTHONPATH="${PWD}/ms-swift:${PWD}${PYTHONPATH:+:${PYTHONPATH}}"
export NUMBA_CACHE_DIR="${NUMBA_CACHE_DIR:-/tmp/lmushra-numba}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

"${PYTHON_BIN}" -m swift.cli.main infer \
  --external_plugins ./scripts/dac_plugin.py \
  --model Qwen/Qwen2-Audio-7B-Instruct \
  --model_type qwen2_audio_dac \
  --template qwen2_audio_dac \
  --adapters "${ADAPTER_PATH}" \
  --use_hf true \
  --infer_backend transformers \
  --val_dataset ./data/dummy-100/valid.jsonl \
  --max_batch_size 1 \
  --max_new_tokens 256 \
  --stream false \
  "$@"
