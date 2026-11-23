# DeepMUSHRA datasets and generators

## Available Training and Inference Datasets

Choose a published audio–text export on **NNN**. Each example pairs a 10-second, 44.1 kHz mono reference with its degraded version. Counts below refer to distinct audio pairs within each dataset.

| Dataset | Examples | Train / Validation | Caption strategies | Recommended use |
|---|---:|---:|---|---|
| [Full Synthetic Dataset](docs/dataset_handoff_guide.md#full-synthetic-dataset) | 999,773 | 964,747 / 35,026 | Calibrated LLM | Large-scale pseudo-label training |
| [Matched POC Dataset](docs/dataset_handoff_guide.md#matched-poc-dataset) | 1,025 | 982 / 43 | Technical template, metadata LLM, calibrated LLM | Small-scale training and controlled ablations |
| [Strict Reasoned Pilot](docs/dataset_handoff_guide.md#strict-reasoned-pilot) | 44 retained from 64 attempted | 36 / 8 | Technical template, metadata LLM, calibrated LLM | Projector smoke test and caption diagnostics |

The two small sets overlap the full population. Choose one dataset and one caption strategy per experiment. The LLM descriptions are metadata-grounded pseudo-labels with no independent human perceptual verification.

- **[Caption strategies and real examples](docs/dataset_handoff_guide.md#caption-strategies)** — compare three targets for the same audio.
- **[Quick start](docs/dataset_handoff_guide.md#quick-start)** — select a split, inspect its audio and metadata, and use the existing training and inference scripts.
- **[Supporting Data and Calibration Resources](docs/supporting_data_and_calibration.md)** — original audio checkpoint, ODAQ listener partition, human scores, frozen mappings and caption diagnostics.

## Generating audio for a new corpus

The CPU generator supports LP, SH, UN and QN. Use a common release and environment across workers. The published datasets above can be consumed directly.

<details>
<summary>Generator installation and sampling example</summary>

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

</details>

For source manifests, recording-group splits, sharded builds and portable audio paths, see the [team generator workflow](docs/team_generator_workflow.md). Use the [versioned sampling recipe](docs/synthetic_sampling_recipe.md) for current profile selection. Retain source provenance and licenses, group all derivatives of a recording in one split, and run `deepmushra-data check-export` on generated bundles.

## Detailed documentation

- [Production caption prompt, validation rules and results](docs/caption_generation_overview.md)
- [Quality mapping rules and figures](docs/final_mapping_report.md)
- [Generator and mapping design](docs/mapped_generators_poc.md)
