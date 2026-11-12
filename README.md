# DeepMUSHRA synthetic dataset generators

One shared CPU workflow for **LP, SH, UN and QN**. Version 0.4.0 preserves the fixed
`mapped-poc-1` default and adds configurable `mapped-poc-v2` sampling. Every teammate runs the same generators and calibration
tables on their assigned recordings. Old generation configurations are archived;
the public CLI does not accept them.

## Versioned sampling modes

The existing `mapped-poc-1` default is preserved. Opt into **`mapped-poc-v2`** for
`odaq_knots`, bounded `quality_target` (explicit/uniform/stratified), or `hybrid`
sampling with request provenance, skip reports and deterministic deduplication.
The four audio algorithms and frozen ODAQ-informed calibration curves are reused.

```bash
python -m deepmushra_data build --profile mapped-poc-v2 --sampling-mode hybrid \
  --manifest /path/to/sources.jsonl --dataset-id my-corpus-v1 --clip-seconds 8 \
  --output data/my-corpus-v1 --audio-prefix data/my-corpus-v1
```

See the [sampling recipe and three pilot commands](docs/synthetic_sampling_recipe.md)
and [actual pilot results](docs/synthetic_sampling_pilot_report.md). Quality estimates
are provisional transfers; synthetic human ratings remain unknown. Rich labels stay
in sidecars, and the paired AudioLM `messages`/`audios` format is unchanged.

## Install on your server

Use Python 3.10 and the pinned numerical dependencies so team fingerprints match.
No GPU, model weights, ODAQ download or ms-swift installation is needed.

```bash
git clone --branch pt/data https://github.com/hbjk0305/LMushra.git
cd LMushra
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-generator.txt
python -m pip install --no-deps -e .
python -m pytest -q
deepmushra-data profile
```

Use the same reviewed Git commit across workers. The profile command prints the
code/recipe/mapping/numerical-environment fingerprint; merge refuses mismatches.
This branch must include the current implementation before cloning these commands.

## Generate a portable AudioLM bundle

Create a source manifest. Paths are relative to this manifest (absolute paths
also work). Reuse source_id for all stems/excerpts of one original recording.
Provide real source/license information; a template is in
[configs/source_manifest.example.jsonl](configs/source_manifest.example.jsonl).

```json
{"source_id":"song-001","source_file":"raw/song-001.wav","content_category":"music","source_provenance":{"license":"YOUR_ACTUAL_LICENSE","source_url":"YOUR_ACTUAL_SOURCE"}}
{"source_id":"speaker-session-002","source_file":"raw/session-002.flac","content_category":"speech","source_provenance":{"license":"YOUR_ACTUAL_LICENSE"}}
```

One command prepares clips, generates triplets, validates them and exports the
training files:

```bash
deepmushra-data build --manifest /path/to/sources.jsonl   --dataset-id my-corpus --output data/my-corpus   --audio-prefix data/my-corpus --clip-seconds 8

deepmushra-data check-export --bundle data/my-corpus --relative-to .
```

Inputs must be original-rate >=44.1kHz WAV/FLAC with one or two channels. Preparation
makes nonoverlapping clips (up to 30s), downmixes the clean reference and downsamples
to 44.1kHz **before** degradation. It rejects known lower-rate originals, upsampling
claims and ODAQ inputs. Generated model audio is always 44.1kHz mono.

--audio-prefix is where the complete bundle will live relative to the **training
checkout root**. Copy the entire data/my-corpus directory there; do not copy only
the JSONL files. The bundle is portable and needs neither the original corpus nor
this machine's absolute paths for training.

## Exact hwangbo/train format

Each train.jsonl, valid.jsonl and test.jsonl line contains exactly:

```json
{"messages":[{"role":"user","content":"Reference: <audio>\nDegraded: <audio>\nDescribe the differences."},{"role":"assistant","content":"High-frequency content is attenuated above the configured cutoff."}],"audios":["data/my-corpus/dataset/audio/reference/REFERENCE_ID.wav","data/my-corpus/dataset/audio/SAMPLE_ID/degraded.wav"]}
```

The order is reference then degraded. The residual is stored but is **not** a third
model input. All additional metadata stays in corresponding *.metadata.jsonl
sidecars, preserving row indices and full per-sample records.

The contract is pinned to
[hwangbo/train, data/dummy-100/train.jsonl](https://github.com/hbjk0305/LMushra/blob/34f4f54b5d4e96d2846cb703e9267dbcf953f686/data/dummy-100/train.jsonl).
We match keys, types, roles, audio ordering and placeholders; source paths and
caption text are our own. Default captions are technical templates that can be
replaced later using the rich metadata. No NISQA/MOS text is copied.

## Split work across teammates

Different corpora use different dataset-id values. Workers processing shards of
the **same** corpus use the same dataset-id, clip duration, commit and environment:

```bash
# Worker0
deepmushra-data build --manifest sources.jsonl --dataset-id corpus-a   --shard-index 0 --shard-count 2 --clip-seconds 8   --output data/corpus-a-0 --audio-prefix data/corpus-a-0
# Worker1, on their own server
deepmushra-data build --manifest sources.jsonl --dataset-id corpus-a   --shard-index 1 --shard-count 2 --clip-seconds 8   --output data/corpus-a-1 --audio-prefix data/corpus-a-1
```

All excerpts/stems of a recording go to one shard and one stable hash-based split.
Splits do not depend on which other recordings a worker sees. A tiny shard may
have empty valid/test files; across large corpora the shared split probabilities
are 70/15/15. Do not manually resplit or rename recording groups per worker.

After copying both complete bundles under the training checkout's data/ directory:

```bash
deepmushra-data merge --inputs data/corpus-a-0 data/corpus-a-1   --output data/combined --relative-to .
deepmushra-data check-export --bundle data/combined --relative-to .
```

Merge keeps each example's original split and checks fingerprints, format,
checksums, duplicate samples and recording overlap. It does not refit mappings,
resplit recordings or copy audio a second time. Keep the worker bundles beside
the merged files.

## Generators and metadata

| Artifact | Shared operation | Mapped control |
|---|---|---|
| LP | Causal Butterworth low-pass | Cutoff frequency |
| SH | Random STFT-band zeroing | Hole probability |
| UN | Envelope-shaped noise replacement in peak-selected bands | Crossover frequency |
| QN | Local spectral-shaped additive noise | Exact mono waveform SNR |

The current pilot recipe requests estimated qualities 50/65/75 per artifact. I selected
those values for engineering checks; they are not an agreed final dataset sampling
policy. The agreed labels are transferred estimated quality 0–100 and derived
Bad/Poor/Fair/Good/Excellent, without a separate severity1–5 scale. These are
ODAQ-informed transferred estimates, not human ratings. QN uses the measured mono
QNMS SNR coordinate; NMR is not equated with SNR. Audibility and human perceptual
labels remain unknown. **PE and TM are excluded.**

Every bundle retains reference/degraded/residual WAVs, processing parameters and
seeds, actual TF masks/noise evidence, signal measurements, provisional calibration
estimates, technical descriptions, candidate-description status, source rights and
preparation provenance. No-op examples remain in the full dataset metadata and
are omitted from training JSONL by default.

See [the final mapping rules and visualizations](docs/final_mapping_report.md),
[the teammate workflow and schema](docs/team_generator_workflow.md),
[the mapping/algorithm report](docs/mapped_generators_poc.md), and
[the historical calibration POC](docs/odaq_calibration_phase1_poc.md).
All generated data, environments and outputs are Git-ignored. No model training
is run by these commands.
