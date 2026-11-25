#!/usr/bin/env bash
# Compare decoding methods on one checkpoint (greedy predictions.jsonl must already exist).
# Usage: source /data/aisaro2/enn_env.sh
#        bash eval/odaq/decoding_sweep.sh dac $DAC_RUN/checkpoint-30148 [eval/odaq/requests.local.enn.jsonl]
set -euo pipefail
cd "$(dirname "$0")/../.."
encoder=$1 checkpoint=$(realpath "$2") requests=${3:-eval/odaq/requests.local.enn.jsonl}
run_dir=$(dirname "$checkpoint")
out=$(dirname "$requests")/"$(basename "$(dirname "$run_dir")")--$(basename "$run_dir")--$(basename "$checkpoint")"
py=${SWIFT_PYTHON:-python}

declare -A CONFIGS=(
  [beam4]="--temperature 0 --num_beams 4"
  [sample_t07]="--temperature 0.7 --top_p 0.9 --seed 42"
  [rep12]="--temperature 0 --repetition_penalty 1.2"
)
for tag in beam4 sample_t07 rep12; do
  if [[ ! -s "$out/predictions_$tag.jsonl" ]]; then
    echo "== $tag: ${CONFIGS[$tag]}"
    # shellcheck disable=SC2086
    DECODE_TAG=$tag bash eval/eval-baseline.sh "$encoder" "$checkpoint" "$requests" ${CONFIGS[$tag]}
  fi
done

runs=()
for tag in "" _beam4 _sample_t07 _rep12; do
  if [[ ! -s "$out/predictions${tag}_mushra.csv" ]]; then  # keep existing (e.g. greedy with CLAP columns)
    "$py" eval/odaq/analyze.py "$out/predictions$tag.jsonl" > /dev/null
    "$py" eval/odaq/compare_mushra.py "$out/predictions$tag.csv" > "$out/compare_mushra$tag.txt"
  fi
  runs+=("${tag:-_greedy}=$out/predictions${tag}_mushra.csv")
done
"$py" eval/odaq/ranking_accuracy.py "${runs[@]/#_/}" --splits 50 -o "$out/ranking_accuracy_decoding.csv"
