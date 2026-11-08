# LMushra

Train Qwen2-Audio with its original Whisper-based encoder (baseline), or replace
it with DAC or EnCodec. All variants train LLM LoRA adapters. The baseline keeps
the original encoder and projector frozen; DAC and EnCodec use frozen encoders,
four-frame pooling of continuous pre-quantization features, and a new trainable
projector.

| Encoder | Audio input | Model type |
| --- | --- | --- |
| Baseline (Whisper-based) | 16 kHz mono | `qwen2_audio` |
| DAC | 44.1 kHz mono | `qwen2_audio_dac` |
| EnCodec | 24 kHz mono | `qwen2_audio_encodec` |

## Setup

Run commands from the repository root. Use Python 3.12 and a CUDA-capable GPU
for training the 7B model.

```bash
git submodule update --init --recursive
python -m venv .venv
source .venv/bin/activate

# Example for CUDA 12.4; adjust for your CUDA environment.
python -m pip install torch==2.6.0 torchaudio==2.6.0 torchvision==0.21.0 \
  --index-url https://download.pytorch.org/whl/cu124
python -m pip install -r requirements_hwangbo.txt
```

## Prepare data

Create `data/dummy-100/train.jsonl` and `valid.jsonl`, with one record per line:

```json
{"messages":[{"role":"user","content":"Reference: <audio>\nDegraded: <audio>\nDescribe the quality differences."},{"role":"assistant","content":"The degraded audio sounds muffled."}],"audios":["data/audio/reference.wav","data/audio/degraded.wav"]}
```

Audio paths are relative to the repository root or absolute paths on your own
machine. Match the order of `<audio>` placeholders to the `audios` array.
Audio is automatically resampled and converted to mono; split files longer
than 30 seconds before use. Regenerate existing manifests if they contain
another machine's paths.

Alternatively, generate a smoke dataset from locally available NISQA audio and
caption annotations. Arrange them under your chosen data root:

```text
data/
  NISQA_Corpus/...
  speech-quality-descriptive-caption/train_nisqa_llama_10k.json
```

```bash
python scripts/make_dummy_dataset.py --data-root ./data \
  --output ./data/dummy-100 --train-size 100 --val-size 16
```

Use `--data-root /path/to/your/data` for an external directory. This dummy
dataset checks the pipeline; its captions are not verified relative-quality
descriptions.

## Train

Choose one encoder. Defaults use two GPUs and 100 steps:

```bash
bash scripts/train_dummy_100.sh          # Original Qwen2-Audio baseline
bash scripts/train_dac_dummy_100.sh
bash scripts/train_encodec_dummy_100.sh
```

For a short single-GPU run:

```bash
CUDA_VISIBLE_DEVICES=0 NPROC_PER_NODE=1 bash scripts/train_dac_dummy_100.sh \
  --max_steps 2 --eval_strategy no --save_steps 2
```

Use `train_dummy_100.sh` for the baseline or `train_encodec_dummy_100.sh` for
EnCodec. Extra arguments override defaults:

```bash
bash scripts/train_dac_dummy_100.sh \
  --dataset ./data/my-train.jsonl --val_dataset ./data/my-valid.jsonl \
  --output_dir ./output/my-dac-run
```


## Inference and resume

Replace `RUN_DIRECTORY/checkpoint-100` with an existing checkpoint:

Baseline inference and resume (no external plugin required):

```bash
CUDA_VISIBLE_DEVICES=0 PYTHONPATH=ms-swift:. "${SWIFT_PYTHON:-python}" -m swift.cli.main infer \
  --model Qwen/Qwen2-Audio-7B-Instruct --use_hf true \
  --adapters ./output/dummy-100/RUN_DIRECTORY/checkpoint-100 \
  --infer_backend transformers --val_dataset ./data/dummy-100/valid.jsonl \
  --max_batch_size 1 --max_new_tokens 256 --stream false

bash scripts/train_dummy_100.sh \
  --resume_from_checkpoint ./output/dummy-100/RUN_DIRECTORY/checkpoint-100
```

DAC and EnCodec inference and resume:

```bash
bash scripts/infer_dac.sh ./output/dac-dummy-100/RUN_DIRECTORY/checkpoint-100
bash scripts/infer_encodec.sh ./output/encodec-dummy-100/RUN_DIRECTORY/checkpoint-100

bash scripts/train_dac_dummy_100.sh \
  --resume_from_checkpoint ./output/dac-dummy-100/RUN_DIRECTORY/checkpoint-100
bash scripts/train_encodec_dummy_100.sh \
  --resume_from_checkpoint ./output/encodec-dummy-100/RUN_DIRECTORY/checkpoint-100
```

Inference uses `data/dummy-100/valid.jsonl` by default. Append
`--val_dataset ./data/my-valid.jsonl` to use another dataset. A local Qwen
checkpoint can be selected with `--model ./models/Qwen2-Audio-7B-Instruct`.

To supply codec weights locally, set the corresponding variable before
training, inference, or resuming:

```bash
export DAC_MODEL_PATH=./models/dac-44khz-8kbps.pth
export ENCODEC_MODEL_PATH=./models/encodec_24khz-d7cc33bc.th
```

DAC requires the official 44 kHz/8 kbps checkpoint, tag `0.0.1`; EnCodec
requires the official 24 kHz mono state dict. Use the same codec weights for
training and inference. Local codec weights alone do not provide an offline
copy of the Qwen model.
## NISQA quality-description pretraining

Use the published single-audio MOS captions and two-audio A/B captions for SFT
before training on reference/degraded descriptions. This does not implement
ALLD preference optimization or reproduce the paper's training configuration.
Keep the original task prompts: A/B inputs are two evaluated samples, not a
reference/degraded pair. MOS targets are not MUSHRA ratings.

Prepare the full local caption dataset (defaults point to `/home/hwangbo5/data`):

```bash
python scripts/prepare_nisqa_pretrain.py \
  --corpus /home/hwangbo5/data/NISQA_Corpus \
  --captions /home/hwangbo5/data/speech-quality-descriptive-caption \
  --output ./data/nisqa-pretrain
```

This requires `train_nisqa_llama_10k.json` and
`train_nisqa_abtest_llama_10k.json`, plus their NISQA audio. It relocates original
annotation paths, checks audio headers (mono, up to 30 seconds), and holds out
approximately 5% of reference utterances using a stable hash. A/B pairs spanning
train and validation are excluded. `report.json` records retained counts and
limitations; provenance files retain task and source identities. This split is
not speaker-disjoint. Official NISQA test partitions are not used for training.
Original audio and annotations are never changed.

Choose an encoder (one epoch by default; this starts a full training run):

```bash
bash scripts/train_nisqa_pretrain.sh baseline
bash scripts/train_nisqa_pretrain.sh dac
bash scripts/train_nisqa_pretrain.sh encodec
```

Codec encoders stay frozen; DAC/EnCodec train the new projector and LLM LoRA.
The baseline freezes its original encoder/projector and trains LLM LoRA.
The learning rate is an initial experiment setting, not a reproduced paper value.
Use the active environment's Python, or explicitly set `SWIFT_PYTHON` if needed.
For a short execution check:

```bash
CUDA_VISIBLE_DEVICES=0 NPROC_PER_NODE=1 bash scripts/train_nisqa_pretrain.sh dac \
  --max_steps 2 --eval_strategy no --save_steps 2 --logging_steps 1 \
  --output_dir ./output/nisqa-pretrain-dac-smoke
```

`NISQA_DATASET_DIR` selects a different prepared dataset directory. Extra Swift
arguments override defaults. Resume an interrupted pretraining run with
`--resume_from_checkpoint PATH_TO_CHECKPOINT`. To start the later reference-pair
stage with a fresh optimizer/schedule, pass the pretrained checkpoint through
`--adapters PATH_TO_CHECKPOINT` to the corresponding training script rather than
resuming the old training state.
