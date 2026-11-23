# Audio–text dataset catalog

All three exports live on **NNN** (`nnn.cs.illinois.edu`). Choose one dataset, then one caption strategy within it. Keep its paired train/validation files and metadata sidecars together. Each LLM description is a metadata-grounded pseudo-label. Human perceptual caption accuracy has not been independently measured.

## Full Synthetic Dataset

```text
/scratch/tingyup2/projects/AudioLM/annotations/caption-poc-fast-v3/run/snapshots/population_1000000/calibrated_llm/
```

Use this directory directly for large-scale training with provisional quality-informed captions. The sibling `technical_template/` covers the full million original audio pairs (964,965 train and 35,035 validation). The sibling `matched_ablations/` and `ablation_sample/` are overlapping comparisons. The production run generated metadata-only captions on a sample of the population.

## Matched POC Dataset

```text
/scratch/tingyup2/projects/AudioLM/annotations/caption-poc-fast-v3/run/snapshots/population_1000000/matched_ablations/
```

Choose `technical_template/`, `metadata_llm/`, or `calibrated_llm/`. All three contain identical audio IDs, student prompts, audio paths and split assignments. Use the same training settings across strategies to study the effect of changing the target text.

## Strict Reasoned Pilot

```text
/scratch/tingyup2/projects/AudioLM/annotations/reasoned-caption-32b-v13-pilot/registry/runs/reasoned-caption-v10-2bd3cd87099f/exports/unique64_absolute/
```

Choose `technical_template/`, `metadata_llm/`, or `calibrated_llm/`. This separate experiment attempted 64 source-diverse examples, 16 per artifact. Stronger automated checks retained 44 common IDs. Only **five IDs overlap** the Matched POC. Both small sets reuse audio from the full population. Combining the three manifests as independent populations would double-count examples.

## Dataset comparison

| | Full Synthetic | Matched POC | Strict Reasoned Pilot |
|---|---|---|---|
| Exported IDs (train / validation) | 999,773 (964,747 / 35,026) | 1,025 (982 / 43) | 44 (36 / 8) |
| LP / SH / UN / QN | 249,844 / 249,934 / 249,995 / 250,000 | 271 / 243 / 259 / 252 | 11 / 15 / 13 / 5 |
| Source selection | Recorded speech, singing and instruments from seven corpora¹ | Same seven corpora, 417 recording groups sampled from production | 64 distinct recording groups attempted across EARS, GuitarSet, MAESTRO, VCTK and VocalSet. Each retained example has a different group |
| Teacher for LLM targets | Qwen3-32B, fast, thinking off, FP16, 384 output tokens maximum | Same production teacher and settings | Qwen3-32B, thinking on, BF16, up to 4,096 output tokens per request |
| Grounding and prior | One pass writes acoustic character and tentative impact from processing evidence and the supplied prior | Calibrated uses the same joint prompt. Metadata-only receives no prior | Character writer sees physical evidence only. Calibrated reuses the same character sentence and adds a separately written prior-informed impact |
| Checks and rejections | Hard format/leakage/contradiction checks, one correction allowed, sampled same-model review. 227 caption rejections (LP 156, SH 66, UN 5, QN 0) | Same policy. 1,025 usable metadata-only captions from 1,029 selected IDs. Four rejected IDs excluded from the matched comparison | Claim/evidence checks, quote and extent checks, and an impact-stance check. At most three attempts per component. Of 64 selected, 46 passed metadata-only and 44 passed calibrated. 20 excluded from the common export |
| Caption status | 832,556 with warnings, 167,164 unchecked, 53 with clean sampled same-model audit status | Calibrated has 871 warnings and 154 unchecked. Metadata-only has 56 warnings and 969 unchecked | All 44 LLM captions per strategy carry `unverified_metadata_inference` |
| Best use and limit | Large-scale SFT. Warning-bearing captions include unresolved claims and inconsistent extent or omission declarations | Matched training ablations. The sample inherits production caption issues and has only 43 validation IDs | Projector smoke tests and failure diagnosis. Retention favors easier cases, especially for QN (5/16). Eight validation examples give little evidence about generalization |

¹ AISHELL-3, EARS, GuitarSet, HiFiTTS-clean, MAESTRO-v3, VCTK-0.92 and VocalSet-ordinary. Source license and prior lossy-coding information are in the sidecar. Both LLM configurations used Qwen3-32B revision `9216db5781bf21249d130ec9da846c4624c16137`, temperature 0.6 and top-p 0.95. Automated acceptance measures compliance with the respective policy. It supplies no estimate of human perceptual agreement. [Production validation rules](caption_generation_overview.md)

Among the 227 primary rejections, 180 contained numerical leakage alone, 28 had inconsistent impact declarations alone, and one had both. Four failed attribute checks and 14 failed JSON/schema checks. The [production report](caption_generation_overview.md) describes the retry and warning policies.

## Caption strategies

| Strategy | What supplies the assistant target | Use |
|---|---|---|
| `technical_template` | Deterministic sentence from DSP metadata, which can include numerical processing parameters | Technical baseline |
| `metadata_llm` | Teacher compares reference and degraded audio using processing facts and measured changes. Input is text metadata only, with no ODAQ quality prior | Acoustic-character supervision, including an initial audio-to-language projector check |
| `calibrated_llm` | Teacher also receives a provisional ODAQ-derived quality estimate to express tentative overall impact | Quality-informed supervision. Transfer to these synthetic mono examples remains unvalidated |

<details>
<summary>Read actual training captions for LP, SH, UN and QN</summary>

These are the first retained training examples of each artifact, in strict-pilot export order. The three captions within each example share the same audio. Parameter values and priors here summarize the sidecar for the reader.

**LP · `ba5d645096342c1052e58b55`** · GuitarSet, music_guitar_instrument. Passband edge 10.59 kHz. Provisional quality 67.31/100.

- `technical_template` — Low-pass filtering has a passband edge of 10.59 kHz.
- `metadata_llm` — The processed sound exhibits a muffled, less bright timbre with reduced high-frequency presence compared to the original.
- `calibrated_llm` — The processed sound exhibits a muffled, less bright timbre with reduced high-frequency presence compared to the original. The provisional estimate suggests moderate overall quality with noticeable degradation relative to the reference.

**SH · `494df2134902ef080a0066ff`** · VocalSet-ordinary, music_singing. Hole probability 10%. Provisional quality 78.78/100.

- `technical_template` — Random spectral bands above 4 kHz are zeroed with per-band/block probability 10.0%.
- `metadata_llm` — The timbre exhibits a smoother, less vibrant character with diminished high-frequency texture.
- `calibrated_llm` — The timbre exhibits a smoother, less vibrant character with diminished high-frequency texture. The provisional estimate indicates an overall quality that is reasonably close to the reference, with a moderate extent of quality loss.

**UN · `978c06d8939db37d91f48468`** · VCTK-0.92, speech. Crossover 7 kHz. Provisional quality 67.93/100.

- `technical_template` — Peak-selected bands above 7.00 kHz are replaced with envelope-shaped noise.
- `metadata_llm` — The processed speech exhibits a subtly muffled texture with reduced brightness compared to the reference, as tonal contrasts are softened and high-frequency clarity is diminished.
- `calibrated_llm` — The processed speech exhibits a subtly muffled texture with reduced brightness compared to the reference, as tonal contrasts are softened and high-frequency clarity is diminished. The provisional estimate suggests the processed audio has moderate quality loss compared to the reference.

**QN · `8beb28e6dc3a53deb3a50f83`** · VocalSet-ordinary, music_singing. Waveform SNR 17.5 dB. Provisional quality 74.06/100.

- `technical_template` — Local spectral-shaped noise is added at a target waveform SNR of 17.53 dB.
- `metadata_llm` — The processed audio exhibits a textured, slightly roughened timbre compared to the original, with added spectral complexity during active vocal passages.
- `calibrated_llm` — The processed audio exhibits a textured, slightly roughened timbre compared to the original, with added spectral complexity during active vocal passages. The provisional estimate suggests the processed quality is reasonably close to reference quality, with moderate overall degradation.

</details>

## Quick start

An optional first check uses the strict pilot with `metadata_llm` captions. Its 36 train and eight validation examples can exercise audio loading and projector alignment. Use the matched POC for larger controlled comparisons.

On NNN, in your own configured **`hwangbo/train` checkout**, select the strategy directory. For another dataset, substitute one of the directories above.

```bash
export DATASET=/scratch/tingyup2/projects/AudioLM/annotations/reasoned-caption-32b-v13-pilot/registry/runs/reasoned-caption-v10-2bd3cd87099f/exports/unique64_absolute/metadata_llm
export TRAIN_JSONL="$DATASET/train.jsonl"
export VAL_JSONL="$DATASET/val.jsonl"
```

Each strategy directory supplies `train.jsonl`, `val.jsonl`, `train.metadata.jsonl` and `val.metadata.jsonl`. The `valid.jsonl` alias refers to `val.jsonl`. Load validation once. Preserve the published source-disjoint splits.

**Inspect an actual row and recover its metadata.** The two audio placeholders correspond to reference first and degraded second. The assistant message is the selected target. Residual audio, source ID, processing metadata and quality priors stay in the sidecar. Pair rows within the same export and split by position. Across exports, join by the sidecar's stable `sample_id`.

```bash
python3 - <<'PY_ROW'
import json, os
from pathlib import Path
folder = Path(os.environ["DATASET"])
with (folder / "train.jsonl").open() as rows, (folder / "train.metadata.jsonl").open() as metadata:
    row, side = json.loads(next(rows)), json.loads(next(metadata))
assert row["audios"] == [side["audio_paths"][role] for role in ("reference", "degraded")]
print(json.dumps(row, indent=2))
print(side["sample_id"], side["training_split"], side["audio_paths"]["residual"])
PY_ROW
```

<details>
<summary>Actual first strict metadata_llm training record</summary>

Sidecar ID `ba5d645096342c1052e58b55`. Whitespace below is formatted for readability.

```json
{
  "audios": [
    "/scratch/tingyup2/projects/AudioLM/production/phase1_real_speech_music_v1/shards/LP/2c/2c28c21acbc844746efd9f6f47c01c3e/dataset/audio/reference/d0778afb3086fcb555f33c133b09f88caf6f66fee2aea37bddaadf9e9c97f25f.wav",
    "/scratch/tingyup2/projects/AudioLM/production/phase1_real_speech_music_v1/shards/LP/2c/2c28c21acbc844746efd9f6f47c01c3e/dataset/audio/ba5d645096342c1052e58b55/degraded.wav"
  ],
  "messages": [
    {
      "content": "Reference audio (original): <audio>\nDegraded audio (processed counterpart): <audio>\n\nCompare the processed audio with the reference. Describe the processing-related\nchanges concisely, making the direction of the comparison clear. Treat possible\nperceptual effects as uncertain unless verified. Do not invent audibility,\nperceived severity, MOS, MUSHRA ratings, or a codec identity. Do not transcribe\nspeech or summarize musical content.\n",
      "role": "user"
    },
    {
      "content": "The processed sound exhibits a muffled, less bright timbre with reduced high-frequency presence compared to the original.",
      "role": "assistant"
    }
  ]
}
```

</details>

**Use the existing training configuration.** The DAC launcher reads `NISQA_DATASET_DIR/train.jsonl` and `NISQA_DATASET_DIR/valid.jsonl`, changes to the training checkout root, and accepts additional Swift arguments. Its default trains the DAC projector **and** LLM LoRA adapters with the audio encoder frozen. An example for a scheduled single-GPU, two-step run follows.

```bash
CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}" NPROC_PER_NODE=1 NISQA_DATASET_DIR="$DATASET" \
  bash scripts/train_calibrated_llm_pretrain.sh dac \
  --max_steps 2 --per_device_train_batch_size 1 --gradient_accumulation_steps 1 \
  --save_steps 2 --logging_steps 1 --output_dir ./output/strict-metadata-dac-smoke
```

For a **projector-only** configuration, the pinned Swift implementation supports `--tuner_type full --freeze_llm true --freeze_vit true --freeze_aligner false`. The DAC plugin registers `language_model`, `audio_tower` and `multi_modal_projector` under the Qwen2-Audio architecture. Append these flags to the training command above with a separate output directory for a projector-only smoke test. Check its trainable parameter names before interpreting results. The full tuner and LoRA produce different checkpoint formats.

**Validation inference with a DAC LoRA adapter.** Set `DAC_ADAPTER` to an existing compatible adapter checkpoint. The extra argument overrides the inference script's dummy validation file. The eight validation rows supply the reference targets for comparing predictions.

```bash
bash scripts/infer_dac.sh "${DAC_ADAPTER:?Set DAC_ADAPTER to a DAC LoRA checkpoint}" \
  --val_dataset "$VAL_JSONL"
```

Scripts and freeze settings were inspected at `hwangbo/train` revision `28718f3d06280b46f09ae1f455d8028044cfd812`. These commands are documented for teammates and were not executed as training or inference during the documentation pass. [Training setup](https://github.com/hbjk0305/LMushra/blob/28718f3d06280b46f09ae1f455d8028044cfd812/README.md) · [SFT launcher](https://github.com/hbjk0305/LMushra/blob/28718f3d06280b46f09ae1f455d8028044cfd812/scripts/train_calibrated_llm_pretrain.sh) · [DAC inference](https://github.com/hbjk0305/LMushra/blob/28718f3d06280b46f09ae1f455d8028044cfd812/scripts/infer_dac.sh)

## Access and receipts

Use your own NNN account with read permissions for both the JSONLs and the referenced WAVs. Absolute audio paths resolve on NNN. For another host, coordinate authorized audio access and write a rebased manifest in your own experiment directory. Keep the published snapshots intact.

Counts were checked against `population_1000000/summary.json` and the strict run's `delivery-readiness.json`. The small exports and their hashes were checked against `population_1000000/publication.json` and `verified-training-view-hashes.json`. The recorded split/overlap audit is in [handoff verification](dataset_handoff_verification.json). Paths to the frozen audio checkpoint, ODAQ studies and pilot failure records are in [Supporting Data and Calibration Resources](supporting_data_and_calibration.md).
