# Projector warmup dataset and training plan

This machine built the dataset. Projector warmup runs on mnn. The data is already at `/data/jackiel4/data/AudioLM/` on that host. It is not in git.

The subset is written. Train is 24,000 rows: 6,000 per family and 2,000 per family-by-tertile. Valid is 3,776: the 2,400 speech/piano sample plus the three held-out groups (guitarset-performer:01, 896; librivox-speaker:6097, 449; vocalset-singer:female6, 31). Origins are 44 strict, 154 clean matched, and the rest full synthetic. No `sample_id` or `source_id` is in both splits. One user prompt. Details are in `selection_report.json`.

## Start on mnn

Data root: `/data/jackiel4/data/AudioLM`. JSONL directory: `/data/jackiel4/data/AudioLM/projector-warmup-24k`. Wavs named by each row's `audios` field are beside that directory, under `production/phase1_real_speech_music_v1/`. 51,736 unique files, about 170 GB. References are shared across rows, so this is fewer than two files per row. `residual.wav` and the corpus files under `references/` were not copied. Training does not open them.

`scripts/audiolm_data_dir.sh` sets `AUDIOLM_DATA_DIR` to `/data/jackiel4/data/AudioLM` when that directory exists and the scratch path does not, and exports `ROOT_IMAGE_DIR` to the same directory. Swift already joins relative media paths to `ROOT_IMAGE_DIR`, so `production/...` resolves without a patch to `ms-swift`. `lmushra/data_paths.py` is the same root for our own code. Some non-wav annotation paths in the metadata sidecar are still absolute under `/scratch/tingyup2` and were not copied. Leave them. The assistant text is already in the JSONL.

`valid.jsonl` is a relative symlink to `val.jsonl`, and `valid.metadata.jsonl` to `val.metadata.jsonl`. The copy used `rsync -a`, which keeps those links. Training scripts open `valid.jsonl`.

The warmup launcher still defaults to single-clip NISQA. This set has two clips, so the first run has to override both:

```bash
export AUDIOLM_DATA_DIR=/data/jackiel4/data/AudioLM
export NISQA_DATASET_DIR=/data/jackiel4/data/AudioLM/projector-warmup-24k
CAPTION_TASK=ab bash scripts/train_projector_warmup.sh dac
```

`CAPTION_TASK=ab` is required. The default `mos` keeps one-audio rows only and will find none. The script then writes a filtered copy under `$NISQA_DATASET_DIR/ab/`. Paths in that copy stay `production/...`.

That launcher is caption cross-entropy only. Family and severity heads are not in the checkout yet. Implement them before the weight sweep. Do not point `--model` at a full warmup checkpoint. The codec loader rebuilds `multi_modal_projector`, and `scripts/audio_use_probe.py` saves `multi_modal_projector.pt`.

Do not launch `scripts/train_calibrated_llm_pretrain.sh` unchanged. Its default dataset is the full export on the build server, which is not on mnn, and `--modules_to_save multi_modal_projector` trains the projector. First SFT should use this same 24k directory, load the warmup wrapper, freeze it, and train LoRA on caption tokens only.

Regenerating the subset is a build-server job. The script refuses a nonempty output directory. Remove the directory before a rerun. `audio_relpaths.txt` in the JSONL directory lists the 51,736 copied wavs.

Regenerate it with:

```bash
python scripts/select_projector_warmup.py \
  --output /scratch/jackiel4/data/AudioLM/projector-warmup-24k
```

The published source stores validation rows in `val.jsonl`. `valid.jsonl` in that folder is a relative symlink to `val.jsonl`. The warmup subset repeats that pair, and the symlink is relative, so it still resolves after the directory is copied. Training scripts that open `valid.jsonl` follow the link.

The user prompt is the original dataset text, copied unchanged. Nothing in the dataloader should replace it. Family and severity are side fields in `chat_template_kwargs.degradation` and in the metadata sidecar.

Sections from "Family and severity heads" onward are the training plan for the other machine. They have not been run here.

A Cursor chat does not follow an SSH host. On the training machine, open this file in a new chat.

## Training scheme

Warmup stays the staged scheme in [projector_warmup_plan.md](projector_warmup_plan.md) and [scripts/train_projector_warmup.sh](../scripts/train_projector_warmup.sh): frozen DAC, frozen LLM, trainable projector, caption cross-entropy, probes where normal CE beats silence and a shuffled degraded clip. NISQA is not the warmup set. The later SFT launcher, [scripts/train_calibrated_llm_pretrain.sh](../scripts/train_calibrated_llm_pretrain.sh), should load the saved `multi_modal_projector.pt` and train LoRA with the projector frozen.

```mermaid
flowchart LR
  warmup["Warmup caption CE plus heads"] --> sft["SFT LoRA captions only"]
  sft --> quality["Optional ODAQ scalar head"]
```

## Warmup subset

Seed `20261124`. Published snapshots stay untouched.

A full scan of `calibrated_llm` shows a 24k training subset is possible. A validation set with the same content mix is possible only by holding out whole recording groups.

- Full train has 964,747 rows and 161,356 with an empty `annotation.warnings` list (`unchecked` or `accepted`). Clean counts by family are LP 42,561, SH 35,725, UN 44,398, QN 38,672. Each family still has a wide severity range, so 6,000 per family and 2,000 per family-by-tertile cell fit without using warned rows.
- The dominant warning, on 748,419 train rows, is `quality_impact_not_independently_confirmed_from_wording`. Matched POC train is 982 rows and only 148 are clean. Strict reasoned pilot is 44 rows, all with status `unverified_metadata_inference` and no warning list; count those as clean. Five sample ids sit in both small sets. Matched and strict ids are subsets of the full export (982/43 and 36/8 on the published train/val sides).
- UN `strength` is 1.0 throughout. Its severity axis is `crossover_hz`. LP uses `cutoff_hz` (lower is more severe). SH uses `hole_probability` (higher is more severe). QN uses `snr_db` (lower is more severe). Tertile edges are the clean-train 33rd and 66th percentiles, nearest-rank index `int(p * (n - 1))`, written into `selection_report.json`.
- Clean train content is speech 68,656, piano 67,615, codec-exposed speech 17,665, guitar 5,791, singing 1,629. Representative means these proportions. Equal counts per content type are impossible: singing does not have 4,800 clean rows.
- Published val clean is 5,861 and only speech and piano. Guitar has 6 source ids, singing 20, and codec-exposed speech 3, all inside the published train split. The smallest clean `source_id` of each is held out of train and included whole in validation. Splitting a group would leak the recording.

Selection rule, implemented in [scripts/select_projector_warmup.py](../scripts/select_projector_warmup.py):

- Train target 24,000. Equal family counts, equal severity tertiles inside each family, content proportional to the clean-train mix. If a tertile cell cannot fill, leftover slots are filled from other contents in that same family and tertile.
- Validation samples the speech and piano grid at one tenth (200 rows per family-by-tertile), then adds the three held-out groups whole. Achieved validation size will not be 2,400. `selection_report.json` records target versus achieved.
- Clean rows only. Warned matched rows are not included.
- Order inside each split: strict reasoned pilot, then matched POC, then full synthetic. Dedup by `sample_id`; on the five overlaps keep the strict row. Priority rows that fall in a stratum are kept even if that cell then needs fewer fill rows.
- Assign validation before train. Validation source ids are the published val groups, the strict-val and matched-val ids, and the three held-out train groups. No `source_id` appears in both splits.
- Sidecar fields: `selection_origin` (`strict_reasoned_pilot`, `matched_poc`, or `full_synthetic`), `selection_seed`, `severity_value` in [0, 1] (higher is more degraded), `severity_bin`, plus `severity_parameter` and `severity_parameter_name`.

Output files: `train.jsonl`, `train.metadata.jsonl`, `val.jsonl`, `val.metadata.jsonl`, `valid.jsonl` -> `val.jsonl`, `valid.metadata.jsonl` -> `val.metadata.jsonl`, `selection_report.json`. The user message and assistant caption are copied from the source row.

## Data and prompt

The warmup filter in [lmushra/audio_probe.py](../lmushra/audio_probe.py) reads an entire JSONL into memory. The 24k file is the one it should see.

Warmup and first SFT both use the original user prompt already stored in the dataset. Do not hardcode a replacement in the dataloader.

```text
Reference audio (original): <audio>
Degraded audio (processed counterpart): <audio>

Compare the processed audio with the reference. Describe the processing-related
changes concisely, making the direction of the comparison clear. Treat possible
perceptual effects as uncertain unless verified. Do not invent audibility,
perceived severity, MOS, MUSHRA ratings, or a codec identity. Do not transcribe
speech or summarize musical content.
```

## Family and severity heads

Finish the path sketched in [scripts/dac_artifact_plugin.py](../scripts/dac_artifact_plugin.py). It imports `lmushra/artifact_supervision.py` and `lmushra/dac_artifact.py`, which are not in this checkout. The current template parses the assistant message as degradation JSON. That would make the model say the DSP label. The assistant message stays the perceptual caption.

- Label channel: `chat_template_kwargs.degradation`, which Swift keeps. Other extra columns are dropped by `RowPreprocessor.remove_useless_columns`. Fields: `artifact` in {LP, SH, UN, QN} and `severity` in [0, 1], higher meaning more degraded, using the same axes and tertile edges as the subset (LP cutoff, SH hole probability, UN crossover, QN inverted SNR). UN strength is unused because it is constant.
- `ArtifactProjector` wraps `DacProjector` in [lmushra/dac_audio.py](../lmushra/dac_audio.py). `forward` returns language embeddings for the audio tokens. A separate readout mean-pools each clip using its true length, subtracts reference from degraded, and applies a 4-way linear layer and a scalar linear layer. Both heads live under `multi_modal_projector` so [scripts/audio_use_probe.py](../scripts/audio_use_probe.py) saves them in `multi_modal_projector.pt`. The last language linear may be zero-initialized. The heads may not.
- Clips are flattened reference-then-degraded, so pair `0,1`, `2,3`, and so on. Assert an even clip count.
- Warmup loss is caption cross-entropy plus classification weight times family cross-entropy plus severity weight times severity regression. Frozen DAC, frozen LLM, trainable wrapper, no LoRA. Model type `qwen2_audio_dac_artifact`, loss type `dac_artifact`. Reuse the token-count rescaling already in `ArtifactLoss` so gradient accumulation does not inflate the auxiliary term.
- First SFT builds the same wrapper, loads the checkpoint, freezes it (`--freeze_aligner true`), and trains LoRA on caption tokens only. Artifact loss is off. Same prompt and same captions. Loading this file into a plain `DacProjector` fails on the head keys.

Real clips will usually be none of the four training families. The family head is a training constraint and a seen-class probe. It is not decoded, and inference does not argmax it. An argmax would force an unseen process into LP, SH, UN, or QN.

Stop warmup when three curves agree: caption loss on real audio below silence and below a degraded-clip swap, seen-family accuracy above chance and flat, and severity correlation flat. Caption loss alone does not show that the head worked.

## Weight experiments

Caption-only control: classification weight 0, severity weight 0. Then severity weight fixed at 0.5 and classification weight in {0.3, 1, 3}. Then classification weight fixed at 1 and severity weight in {0.25, 0.5, 1}.

Select a run only if the audio probes pass and generated captions contain no operator names or numbers. Among those, prefer severity correlation on a family held out of the head loss over in-family accuracy. A large classification weight can separate the four names and still hurt a new degradation. Starting point before the sweep is classification weight 1 and severity weight 0.5. If family accuracy stays near 25%, check the clip pairing before raising the weight. If caption loss stalls while family accuracy saturates, lower the classification weight.

## ODAQ prior

The provisional 0–100 ODAQ estimate is in the `calibrated_llm` teacher only.

- Dataset 1, full synthetic `calibrated_llm`: the teacher saw the prior. `technical_template` did not. `metadata_llm` exists only on the matched sample and did not.
- Dataset 2, matched POC: `calibrated_llm` saw the prior. `metadata_llm` and `technical_template` on the same 1,025 ids did not. This is the control set for whether the prior changed the words.
- Dataset 3, strict reasoned pilot: `calibrated_llm` adds an explicit prior sentence. `metadata_llm` is character only. 44 ids.

Use the prior as a scalar cross-artifact distance label, because the four generator parameters do not share a unit and a fifth, unseen process has no class. That follow-up regresses the sidecar mean on dataset 1, or ranks pairs by it, and checks dataset 2 against `metadata_llm`. Keep it only if it still orders a held-out artifact. PE and TM were left out of the generators; if those clips exist they are a stronger unseen test than holding out one of the four. If that check fails, the fallback scalar is a measurement defined for any new clip, such as residual energy or spectral magnitude error, reported as a DSP distance.

Leave the prior out of the 4-way family loss. A head that matches it agrees with an unvalidated transfer function. `quality_prior_limitations` on these records says operator equivalence and mono transfer were not validated.
