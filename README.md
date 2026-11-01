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

For the tested dependency versions (Python 3.12.5 on macOS arm64):

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
