# Historical README snapshot

Superseded by the repository README and docs/team_generator_workflow.md. Paths in this snapshot were relative to the repository root.

# DeepMUSHRA synthetic data

A standalone dataset workstream for **DeepMUSHRA: Perceptually Accurate Natural
Language Descriptions for Subtle Audio Differences**. It generates reference,
degraded, and residual audio with reproducible processing evidence and
metadata-derived text. It does not train models or predict MUSHRA ratings.

**All source and generated audio must be at least 44.1 kHz.** The supplied configs
accept 44.1 and 48 kHz and preserve the original rate. The pipeline never silently
resamples or downmixes. Upsampling low-bandwidth audio cannot restore missing
high-frequency information.

## Install

From this repository, using Python 3.10 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --cache-dir .cache/pip -e '.[dev]'
```

For the original functional-pilot dependency versions (Python 3.12.5 on macOS arm64):

```bash
python -m pip install --cache-dir .cache/pip -r requirements-tested.txt
python -m pip install --cache-dir .cache/pip -e '.[dev]'
```

The numerical packages are NumPy, SciPy, and SoundFile; configuration uses
PyYAML, diagnostic figures use Matplotlib, and tests use pytest. No GPU, model
weights, external audio corpus, or `ms-swift` initialization is required. The
existing `ms-swift` submodule is left untouched. Dependencies, caches, and all
generated data are ignored by Git.

## Generate the functional pilot

```bash
deepmushra-data demo --config configs/pilot.yaml --output outputs/pilot
deepmushra-data validate --dataset outputs/pilot
pytest -q
```

The demo creates six four-second analytical sources: tonal, transient, and
broadband signals at both 44.1 and 48 kHz, with mono and stereo layouts. Three
settings for each of LP, SH, and UN produce 54 degraded pairs; six identity
controls bring the total to 60 triplets. The fixed master seed is `20261101`.
These are **functional test signals, not representative perceptual evaluation
data**, and all metadata carries that flag.

Existing output directories are never overwritten. To reproduce the pilot,
choose a fresh directory such as `outputs/pilot-repeat`. Within the same recorded
software environment and implementation, waveform, mask, and manifest bytes
are deterministic. Figures are diagnostic artifacts and are not part of the
byte-for-byte reproducibility contract.

## Use clean recordings

```bash
deepmushra-data generate --config configs/pilot.yaml \
  --input-dir /path/to/clean-clips --output outputs/clean-pilot

deepmushra-data generate --config configs/sampled.yaml \
  --manifest /path/to/sources.jsonl --output outputs/sampled-pilot
```

Directory mode recursively discovers WAV/FLAC files, treating each file as an
original recording and using a checksum as its source identity. Content category
is `unknown` unless supplied by a manifest. For excerpts, stems, alternate
microphones, or related recordings, use a manifest and assign the same
`source_id` to every file derived from the same original recording:

```json
{"source_file":"clips/song_a.wav","source_id":"song_a","content_category":"music"}
{"source_file":"clips/song_b_drums.wav","source_id":"song_b","content_category":"music"}
{"source_file":"clips/song_b_mix.wav","source_id":"song_b","content_category":"music"}
```

Paths are relative to the manifest; absolute source paths also work. A template
is supplied in `configs/source_manifest.example.jsonl`. Input defaults require
1–30 seconds and one or two channels. Prepare clips explicitly; there is no
automatic cropping. The default three-way split needs at least three independent
source groups. For a one-source experiment, explicitly configure
`splits: {train: 1, validation: 0, test: 0}`.

`configs/sampled.yaml` demonstrates uniform, log-uniform, inclusive integer, and
choice sampling. `configs/pilot.yaml` lists every setting explicitly. All recipe
parameters are validated against each source's Nyquist frequency. Invalid input
or an output peak above the configured limit stops the run; a failed run is not
published as a dataset. If necessary, lower the shared `source_peak_limit` in a
new configuration. There is no per-degraded-file loudness normalization or clamp.

## Outputs and interfaces

```text
src/deepmushra_data/     algorithms, STFT, IO, sources, pipeline, schema, text, CLI
configs/                explicit pilot, bounded sampling, source-manifest example
tests/                  DSP, reproducibility, integrity, split, and CLI tests
docs/                   dataset specification, design decisions, verification
outputs/pilot/          ignored, regenerated artifacts
  audio/                shared reference WAVs and per-example degraded/residual WAVs
  evidence/             compressed NPZ masks, coordinates, and algorithm evidence
  metadata/             per-example JSON records
  metadata.jsonl        all complete metadata records
  manifest.jsonl        downstream audio paths and description candidates
  manifests/            train.jsonl, validation.jsonl, test.jsonl
  diagnostics/          LP.png, SH.png, UN.png
  resolved_config.json  normalized run configuration (resolved DSP parameters in metadata)
  run.json              versions, source-code hash, split map, environment
  validation_summary.json
```

All generated audio is lossless IEEE float64 WAV (`DOUBLE`). The residual is
computed **after reloading the exact saved reference and degraded signals**:
`residual = degraded - reference`. Every role preserves sample rate, channel
order, time grid, and sample count. References are shared by file checksum to
avoid unnecessary duplication. Each manifest row includes audio paths relative
to the run root, a metadata path, sample rate, split, and text candidates. It is
model-independent; adapters to training-framework formats belong downstream.

Perceptual annotation fields are `null` and `unverified`. The parameter tier is
explicitly provisional, and candidate perceptual text is never treated as human
annotation or a MUSHRA target. Technical descriptions state known processing
facts. **PE and TM are excluded from project augmentation** for later zero-shot
ODAQ evaluation. Do not insert their synthetic examples into train/validation
manifests or instruction demonstrations.

Recreate figures without regeneration:

```bash
deepmushra-data analyze --dataset outputs/pilot
```

This first validates the dataset, then writes channel-1 waveform and spectrogram
figures with fixed spectrogram color limits. `--no-diagnostics` skips figures
during generation.

See [the dataset specification](docs/dataset_spec.md),
[design decisions and open research questions](docs/design_decisions.md), and
[verification results](docs/validation_results.md). A complete, real pilot
record is in [the metadata example](docs/metadata.example.json), with paths
relative to the generated dataset root. No generated audio should be
committed. A future metadata-to-LLM paraphrasing stage can use the pure
`describe(artifact, parameters, evidence)` interface; no LLM is used here.

## Phase 1: real-recording research pilot (KNN)

All project execution and artifacts belong on KNN for this workspace. Do not
create environments, checkouts, or downloads on the coordinating Mac.
The existing Linux environment is Python 3.10.12; use it as follows:

```bash
ssh tingyup2@knn.cs.illinois.edu
cd /data/tingyup2/projects/AudioLM/LMushra
source /data/tingyup2/projects/AudioLM/env.sh
python -m pip install --no-deps --no-build-isolation -e .  # existing tested env
python -m pytest -q
```

For a fresh compatible remote environment, install the pinned dependencies in
`requirements-phase1-knn.txt`, then `python -m pip install --no-deps -e .`.
SciPy >=1.14 is required for the QN minimum-phase FIR factorization.

Read the upstream noncommercial/share-alike source conditions before acquisition:
[MUSDB18-HQ](https://zenodo.org/records/3338373),
[MUSDB licenses](https://sigsep.github.io/datasets/musdb.html), and
[MedleyDB distribution](https://medleydb.weebly.com/downloads.html).
Only eight MedleyDB tracks are selected, from distinct original recordings and
artists. WAVs and downloaded documentation stay under gitignored `data/`.
Do not redistribute dataset audio through Git. Source attribution, the license,
original member, crop, integrity checks, and content-category basis are retained.

```bash
# Acquisition refuses to overwrite a completed source manifest.
python scripts/prepare_phase1_sources.py --output data/phase1_sources
python -m deepmushra_data generate --config configs/phase1.yaml \
  --manifest data/phase1_sources/sources.jsonl --output outputs/phase1-pilot
python -m deepmushra_data generate --config configs/phase1.yaml \
  --manifest data/phase1_sources/sources.jsonl --output outputs/phase1-repeat --no-diagnostics
python scripts/analyze_phase1.py --dataset outputs/phase1-pilot --repeat outputs/phase1-repeat
python -m deepmushra_data validate --dataset outputs/phase1-pilot
```

Use fresh source/run paths when reproducing completed work; outputs are never
overwritten. The ZIP is 22.7 GB, but acquisition reads its directory and only
the eight selected compressed WAV members (initial run: 284 MB of HTTP ranges).
No ODAQ download or input is involved. Manifest `source_provenance` mappings
are carried into each complete generated record.

**QN status: Implemented.** The generator is
[`_quantization_like_noise()`](src/deepmushra_data/degradations.py), exposed through
`apply_effect("QN", ...)` and configured in [`configs/phase1.yaml`](configs/phase1.yaml).
[`tests/test_phase1.py`](tests/test_phase1.py) covers target SNR, additive-noise
consistency, reproducibility, mono/stereo behavior, causal onset, silence,
parameter validation, and saved triplet/metadata integrity.

`configs/phase1.yaml` has three settings each for LP/SH/UN and additive
signal-shaped QN-like noise, with eight identities: **104 triplets** total.
QN adds noise to the retained waveform at a specified per-channel waveform SNR;
it is neither ODAQ's psychoacoustic NMR method nor tonal replacement.
All perception fields and description candidates remain unverified. Stereo
width processing, PE, and TM are not implemented.

The completed experiment and limitations are documented in
[the Phase 1 team report](docs/synthetic_dataset_phase1_report.md).
Its `phase1_analysis/` directory contains per-source metrics, parameter curves,
content comparisons, spectrogram triplets, and analytical temporal probes.
These objective diagnostics do not establish human audibility or quality.

## Synthetic Dataset Design

### Overview

DeepMUSHRA aims to train a reference-aware Large Audio-Language Model (LALM) to identify and describe perceptually meaningful differences between reference and degraded audio.

We construct a synthetic dataset of controlled audio degradations, where the processing parameters and affected signal regions are known. The dataset supports supervised fine-tuning (SFT) with metadata-derived natural-language descriptions.

Our current training design targets **44.1 kHz mono audio**, with four training artifact families and two held-out artifact families for zero-shot evaluation. The existing generator preserves native mono or stereo inputs; the completed real-recording pilot uses 44.1 kHz stereo excerpts. A dedicated mono training export remains to be prepared.

### 1. Artifact Selection

The artifact selection is informed by the [ODAQ-Collection](https://arxiv.org/abs/2610.37959), which reports 17 processing-method groups across several listening-test subsets. These groups consolidate into fewer distinct degradation mechanisms.

#### Training Artifacts

| Artifact | Description | Perceptual dimension | Implementation status |
|---|---|---|---|
| **LP — Bandwidth Limitation** | Low-pass filtering that attenuates high-frequency content | Brightness, spectral detail | Implemented; perceptual validation pending |
| **SH — Spectral Holes** | Removal or attenuation of selected time-frequency components | Spectral completeness, temporal consistency | Implemented; perceptual validation pending |
| **UN — Unmasked Noise** | Replacement of tonal components with noise-like components | Tonality, spectral texture | Implemented; perceptual validation pending |
| **QN — Quantization-like Noise** | Addition of signal-shaped noise while preserving underlying content | Noisiness, roughness | Implemented; perceptual validation pending |

**Rationale for including QN:** Unlike UN, which replaces existing tonal information with noise, QN introduces additive noise while largely retaining the original signal structure. This provides an additional controlled degradation mechanism relevant to audio coding.

QN is also represented in the ODAQ 2025 stereo extension through QNLR, QNMS, and QNmix. These are stereo-processing and listening-test variations of the same underlying artifact family, not three separate artifact families.

Our QN implementation provides controllable signal-shaped additive noise. It should not be claimed as an exact reproduction of ODAQ's psychoacoustic Noise-to-Mask Ratio (NMR) processing without further verification.

The implementation is `_quantization_like_noise()` in [`src/deepmushra_data/degradations.py`](src/deepmushra_data/degradations.py), exposed through `apply_effect("QN", ...)`. Existing behavior and integration tests are in [`tests/test_phase1.py`](tests/test_phase1.py); all 28 tests in that file passed during the status check.

#### Held-Out Artifacts for Zero-Shot Evaluation

| Artifact | Description | Evaluation objective |
|---|---|---|
| **PE — Pre-Echo** | Noise-like energy spreading before transient attacks | Generalization to unseen temporal distortions |
| **TM — Tonality Mismatch** | Replacement of noise-like components with artificial tonal components | Generalization to unseen spectral-texture transformations |

PE and TM are excluded from our synthetic training and calibration datasets, including augmentation, description templates, and model-specific fine-tuning examples.

Here, **zero-shot refers to artifact families unseen during DeepMUSHRA-specific training**, not necessarily unseen during the base model's original pretraining.

The current SH/UN implementations exhibit incidental pre-onset spreading in analytical probes. The team must resolve how this affects the PE holdout definition before claiming a perceptually isolated holdout.

#### Deferred Artifacts

| Artifact | Reason for exclusion |
|---|---|
| ICC — Interaural Cross-Correlation Distortion | Requires stereo/spatial information |
| ILD — Interaural Level Difference Distortion | Requires stereo/spatial information |
| Other stereo-specific processing | Not compatible with the current mono input setting |

The selected DAC training path uses **44.1 kHz mono audio**. Spatial effects may be reconsidered if future model architectures support stereo or spatial audio representations.

### 2. Audio and Dataset Format

**Target training audio specification:**

- Sample rate: 44,100 Hz
- Channels: Mono
- Input: Reference and degraded audio, with residual audio available
- Residual definition: `residual = degraded - reference`
- Reference and degraded signals must have identical sample counts and alignment.
- Audio generation must be reproducible through fixed random seeds and recorded processing configurations.

Each synthetic sample should provide:

```text
sample_id/
├── reference.wav
├── degraded.wav
├── residual.wav
└── metadata.json
```

This illustrates the logical contents of a sample. The current implementation shares reference WAVs across variants and links them through a manifest. The final storage layout and training manifest may be optimized for large-scale generation.

**Important:** The `hwangbo/train` branch currently uses 44.1 kHz mono for DAC, 16 kHz mono for the Qwen2-Audio baseline, and 24 kHz mono for EnCodec. We must verify the selected model's complete preprocessing path. This is critical for bandwidth-related artifacts, especially high-frequency LP distortions.

A mono export must apply consistent channel conversion to the reference and degraded signals, recompute the residual from the saved exported pair, and update the distortion measurements.

### 3. Metadata and Description Design

Metadata should distinguish three categories:

**A. Objective generation metadata**

- Artifact type and implementation version
- Processing parameters and random seed
- Affected time-frequency regions or masks
- Source recording identifier
- Sample rate, duration, and audio format

**B. Measured signal properties**

- RMS and energy changes
- Spectral differences
- Artifact-specific distortion measurements
- Actual signal modifications and their locations

**C. Perceptual annotations and descriptions**

- Perceptual attributes
- Audibility, when assessed
- Perceived severity, when assessed
- Technical descriptions generated from metadata
- Candidate natural-language descriptions

Processing strength must not be treated as equivalent to perceptual severity.

Metadata-derived descriptions should distinguish verifiable signal-processing facts from unverified claims about what listeners hear. Human MUSHRA scores and perceptual judgments must never be fabricated from processing parameters.

### 4. Severity and Parameter Sampling

We plan to generate multiple parameter settings per artifact, ranging from subtle to clearly measurable degradation.

Initial parameter ranges are provisional and must be validated using independently sourced audio.

Severity calibration will consider:

1. The relationship between processing parameters and objective signal differences.
2. Content dependence across speech, music, and different instruments.
3. A small listening study to estimate audibility and perceived quality.
4. Uncertainty in predicted or estimated perceptual severity.

The completed engineering pilot covers generator validation and parameter exploration. Formal perceptual calibration will follow before full-scale dataset generation.

### 5. Dataset Splitting and Evaluation Policy

The synthetic dataset uses source-disjoint training, validation, and test splits. All versions derived from the same original recording must remain within the same split.

**ODAQ-Collection supports the Phase 1 calibration POC and listener-held-out evaluation.**

The user authorized this calibration-stage POC on 2026-11-11. It reuses the
frozen cohort-stratified split, with approximately 20% of listener records for
calibration and 80% for evaluation. The evaluation is **ODAQ-informed and
listener-held-out**, with shared source material and processing conditions.
The fitted mappings retain the original stereo-rating scope. Applying them to
mono synthetic audio requires a separate transfer validation.

- Only the frozen calibration listeners' LP, SH, UN, and QN ratings are used for fitting and calibration-only model selection.
- Evaluation listeners' ratings are used only to score the frozen mappings.
- ODAQ audio and listener comments are excluded from SFT and training-description generation.
- LP, SH, UN, and QN support seen-family, listener-held-out evaluation in this POC.
- PE and TM are reserved for zero-shot artifact-family evaluation.
- Dialogue enhancement (DE) and neural codec outputs can support evaluation on compound, real-world processing degradations.
- Stereo ODAQ conditions require careful interpretation when converted to mono, because the original subjective scores were obtained under stereo listening conditions.

ODAQ processing methods should not be assumed identical to our synthetic approximations.

The fitted mappings, uncertainty diagnostics, evaluation results, and limitations
are documented in [the calibration POC report](docs/odaq_calibration_phase1_poc.md).
This stage leaves synthetic generators and existing training data intact.
QN NMR-to-SNR and stereo-to-mono transfer remain unverified.

### 6. Current Implementation Status and Next Steps

**Current status (verified in the `pt/data` working tree):**

- LP, SH, UN, and QN generators have been implemented; perceptual validation remains pending.
- The real-recording pilot contains 104 triplets from eight 44.1 kHz stereo excerpts, including 24 examples per artifact and eight identity controls.
- Existing tests cover waveform alignment, residual correctness, metadata, reproducibility, and artifact-specific behavior.
- A dedicated 44.1 kHz mono training export remains pending.
- PE and TM remain held out.
- Stereo/spatial artifacts remain deferred.

**Next steps:**

1. Resolve the documented LP phase/boundary behavior and SH/UN pre-onset spreading.
2. Review the QN noise-envelope tail and calibrate candidate settings on independent recordings.
3. Prepare a 44.1 kHz mono training export and broaden source coverage across speech, music, and instruments.
4. Analyze parameter-dependent distortion through objective measurements and spectrograms.
5. Verify waveform alignment, residual correctness, and metadata reproducibility after export.
6. Review candidate natural-language descriptions for factual accuracy and conduct independent perceptual validation.
7. Coordinate with the model and evaluation teams on output structure, severity labels, and benchmark protocols.

### 7. Open Questions for Team Discussion

- Does the audio encoder preserve the full 44.1 kHz bandwidth?
- Will the LALM consume reference and degraded audio only, or also the residual?
- What structured description format should be used for SFT?
- How should perceptual severity be annotated or calibrated?
- Should additional non-spatial temporal or nonlinear artifact families be added in a later ablation?
- How should ODAQ stereo-to-mono evaluation and human MUSHRA score comparisons be reported?

### References

- [Original ODAQ (2024)](https://arxiv.org/abs/2401.00197)
- [ODAQ Stereo Extension (2025)](https://arxiv.org/abs/2512.14259)
- [ODAQ-Collection (2026)](https://arxiv.org/abs/2610.37959)
- [Official ODAQ Repository](https://github.com/Fraunhofer-IIS/ODAQ)

---

*This section records the current Phase 1 synthetic dataset design. Artifact selection and target training audio format are the current working decisions; implementation details, parameter ranges, and perceptual calibration remain subject to experimental validation and team review.*

## ODAQ-informed mapped POC

The versioned mapped-poc-1 profile supports LP cutoff, SH probability, UN crossover,
and QN mono waveform SNR with frozen, bounded quality priors. These are provisional
transferred estimates; human perceptual annotations remain separate.

See [the mapping and generator guide](docs/mapped_generators_poc.md) for tables,
installation/commands, the 96-triplet pilot, metadata and validation results.
The legacy generator interface remains available.
