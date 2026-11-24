#!/usr/bin/env bash
# Two-step smoke test for projector-only DAC warmup.
# Same device layout as train_projector_warmup.sh: GPUs 0,1, two processes,
# per-device batch 1, gradient accumulation 4 (effective batch 8).
#
#   bash scripts/smoke_projector_warmup.sh
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
PYTHON_BIN="${SWIFT_PYTHON:-$REPO_ROOT/.venv/bin/python}"
export SWIFT_PYTHON="$PYTHON_BIN"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0,1}"
export NPROC_PER_NODE="${NPROC_PER_NODE:-2}"
export AUDIO_PROBE_INTERVAL=2
export AUDIO_PROBE_EXAMPLES=2
export PROJECTOR_ZERO_INIT_LAST=1

SMOKE_ROOT="$REPO_ROOT/output/dac-projector-warmup-smoke"
DATA_DIR="$SMOKE_ROOT/data"
RUN_DIR="$SMOKE_ROOT/run"
LOG="$SMOKE_ROOT/smoke.log"
mkdir -p "$DATA_DIR" "$RUN_DIR"
rm -rf "$RUN_DIR"
mkdir -p "$RUN_DIR"

"$PYTHON_BIN" - <<PY
import json
from pathlib import Path
src = Path("$REPO_ROOT/data/nisqa-pretrain")
dst = Path("$DATA_DIR")
def take(name, n):
    rows = []
    for line in (src / name).read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if len(row.get("audios") or []) != 1:
            continue
        rows.append(row)
        if len(rows) == n:
            break
    if len(rows) < n:
        raise SystemExit(f"needed {n} single-audio rows in {name}, found {len(rows)}")
    (dst / name).write_text("".join(json.dumps(r) + "\n" for r in rows))
take("train.jsonl", 4)
take("valid.jsonl", 2)
print(f"smoke data: {dst}")
PY

set -o pipefail
NISQA_DATASET_DIR="$DATA_DIR" \
  bash "$REPO_ROOT/scripts/train_projector_warmup.sh" dac \
  --max_steps 2 \
  --eval_steps 2 \
  --save_steps 2 \
  --logging_steps 1 \
  --save_total_limit 1 \
  --add_version false \
  --output_dir "$RUN_DIR" \
  2>&1 | tee "$LOG"

"$PYTHON_BIN" - <<PY
import ast
import re
import torch
from pathlib import Path
log = Path("$LOG").read_text(errors="replace")
run = Path("$RUN_DIR")
if "freeze_parameters:" not in log or "language_model" not in log or "audio_tower" not in log:
    raise SystemExit("smoke failed: LLM/codec were not frozen")
match = re.search(r"Trainable parameters \((\d+)\): (\[.*?\])", log)
if not match:
    raise SystemExit("smoke failed: trainable-parameter report missing")
names = ast.literal_eval(match.group(2))
if not names or any("multi_modal_projector" not in name for name in names):
    raise SystemExit(f"smoke failed: unexpected trainable parameters: {names}")
if "'loss'" not in log and '"loss"' not in log and "loss" not in log:
    raise SystemExit("smoke failed: no loss logged")
weights = list(run.rglob("multi_modal_projector.pt"))
if not weights:
    raise SystemExit(f"smoke failed: no projector checkpoint under {run}")
state = torch.load(weights[0], map_location="cpu", weights_only=True)
last = state.get("3.weight")
if last is None or not last.abs().sum():
    raise SystemExit("smoke failed: projector final layer did not train")
print(f"smoke ok: trainable={len(names)} projector={weights[0]}")
PY
