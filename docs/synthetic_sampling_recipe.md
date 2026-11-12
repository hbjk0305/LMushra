# Unified synthetic sampling recipe: mapped-poc-v2

DeepMUSHRA uses the existing LP, SH, UN and QN operators and frozen ODAQ-informed curves. V2 adds request sampling, skip/deduplication accounting and provenance; it does not refit a curve or change an audio algorithm. PE and TM remain excluded. No ODAQ recording is a synthetic source.

## Profiles and compatibility

- `mapped-poc-1` remains the CLI default: its unchanged packaged recipe uses quality targets 50/65/75. These are historical engineering defaults, not the final dataset decision. Its parameter, seed and waveform behavior is preserved. V1 custom configurations remain rejected by the public shared-profile guard.
- `mapped-poc-v2` accepts a validated sampling recipe. Every resolved recipe, source-code release, frozen table, training contract and numerical environment enters the generator fingerprint. Workers must use identical fingerprints; mixed profiles/recipes cannot be merged.
- The package release is 0.4.0. The reused operator profile remains `mapped-poc-1` in degradation metadata; the sampling profile/schema is `mapped-poc-v2`. LP/SH/UN algorithm 1.1 and QN `local_spectral_additive_noise_v1` are unchanged.
- Adding sampler code changes release fingerprints and sample IDs even when a v1 waveform remains identical. Previous outputs are immutable and are not rewritten or relabeled.

## Three modes

| Mode | Selection | Intended use |
|---|---|---|
| `odaq_knots` | Five nominal Q1–Q5 conditions, then forward quality lookup | Operator checks, clear five-condition Phase 1 baseline |
| `quality_target` | Explicit targets or continuous supported targets, bounded inverse, generation, forward lookup | Controlled exploration of the supported quality-prior axis |
| `hybrid` | Knot requests followed by additional quality requests, optional parameter deduplication | Diverse follow-up POC and future scaling after transfer validation |

Q1–Q5 order denotes five nominal processing conditions, most to least degraded within each family. They are not labels Bad/Poor/Fair/Good/Excellent and do not certify relative human severity on new content.

| Artifact | Nominal Q1→Q5 | Generator control / semantics |
|---|---|---|
| LP | 5, 9, 10.5, 12, 15 kHz | 5000, 9000, 10500, 12000, 15000 Hz Butterworth passband edge; fixed 1500 Hz transition, .5 dB passband ripple, 60 dB stop specification; causal SOS phase |
| SH | 70, 50, 30, 20, 10% | Frozen probabilities .7000000000000001, .5, .3, .2, .1; above 4 kHz, 500 Hz bands, four-frame runs, zero attenuation. This is per-band/block selection probability, not actual modified TF ratio. |
| UN | 3, 5, 7, 9, 10.5 kHz | Crossover 3000, 5000, 7000, 9000, 10500 Hz; replacement strength 1; existing 12 dB peak selector and 500 Hz smoothing |
| QN | NMR labels 0, 6, 12, 18, 24 dB | Empirical mono-SNR proxies 2.228506302815756, 6.661260379445558, 12.06516953880947, 17.724421587884798, 23.205954857698543 dB |

All five QN conditions exist in the frozen bridge. The sampler matches the nominal labels to the packaged `released_parameter_knots` and takes the corresponding `x` coordinate. A missing bridge condition is reported as unsupported, never converted by numeric NMR=SNR substitution. LP Hz conversion and SH percentage conversion are cross-checked against the frozen coordinates. The tiny floating difference .7000000000000001 versus .7 preserves the table coordinate exactly.

The QN bridge uses 20 released QNMS stereo audio pairs (four sources × five conditions), separate arithmetic downmix, 48→44.1 kHz resampling and the median waveform SNR across four sources per condition. Its quality coordinates are the original stereo means from 60 calibration ratings by three listeners. It uses no held-out 80% ratings or PE/TM data. There is no mono or synthetic-QN human listening validation. NMR is not SNR; equal SNR across operators/content need not mean equal quality.

## Configuration

Use the existing seed/input/splits/artifacts structure. V2 uses empty artifact objects and a shared sampling section. The schema and CLI reject unknown effects, extrapolation and clipping policies.

```yaml
schema_version: mapped-poc-v2
seed: 20261111
input:
  sample_rates: [44100]
  channels: [1]
  min_duration_s: 1
  max_duration_s: 30
  source_peak_limit: 0.15
  output_peak_limit: 0.999
splits: {train: 0.7, validation: 0.15, test: 0.15}
artifacts: {LP: {}, SH: {}, UN: {}, QN: {}}
sampling:
  mode: hybrid
  odaq_knots:
    conditions: [Q1, Q2, Q3, Q4, Q5]
  quality_target:
    strategy: continuous_stratified
    targets_per_artifact: 5
    allow_extrapolation: false
    unsupported_target_policy: skip_with_report
  hybrid:
    deduplicate_parameters: true
    parameter_atol: {LP: 0.000001, SH: 0.000000000001, UN: 0.000001, QN: 0.000000001}
    parameter_rtol: 0
```

The configuration key is `odaq_knots`, as shown above. Mode determines which request groups are enabled; separate enabled flags are unnecessary. Choose a subset of conditions and `targets_per_artifact` to control the knot/quality count ratio. Setting zero continuous targets permits a knot-only hybrid; no new DSP configuration is introduced.

Ready-to-run configurations:

- `configs/sampling_odaq_knots.yaml`
- `configs/sampling_quality_target.yaml` (five continuous stratified targets)
- `configs/sampling_hybrid.yaml` (five knots + five continuous targets)
- `configs/sampling_quality_explicit.yaml` (10/30/50/70/90, unsupported requests skipped)

For explicit sampling, replace the complete `quality_target` block with:

```yaml
quality_target:
  strategy: explicit
  targets: [10, 30, 50, 70, 90]
  allow_extrapolation: false
  unsupported_target_policy: skip_with_report
```

For uniform continuous sampling, choose `strategy: continuous_uniform` and a count. `continuous_stratified` defaults to equal-width strata across that artifact's supported quality range, one draw per stratum when count is five. Optional `intervals: [[0,20],[20,40],[40,60],[60,80],[80,100]]` instead intersects each requested interval with support, reports zero-width/unsupported intersections and distributes draws round-robin among remaining intervals. These are sampling intervals, not newly validated perceptual classes.

Targets outside support are never extrapolated or clipped. Current supported mean ranges are LP 22.7778–97.9484, SH 25.2063–78.7817, UN 45.8056–89.9524 and QN 20.0547–92.6563. No supported mean lies in Bad [0,20). Categories use the existing 20-point boundaries and are derived from the forward estimate, with no forced category coverage.

## Determinism, inverse policy and deduplication

Sampling RNG is keyed by the configured seed, stable source recording group, exact prepared-clip checksum and artifact. Worker order and shard boundaries do not alter a clip's requests. Knot order is canonical Q1→Q5, followed by quality-target order. B and C use the same continuous requests on the same source/seed, and A/C use the same knot seeds.

The existing bounded piecewise-linear inverse is used. Current frozen curves are strictly monotone and have unique inverses. The lookup API additionally handles an exact monotone plateau deterministically by choosing the lowest parameter on that plateau; non-flat segments interpolate normally. No frozen curve was changed. Out-of-support values raise or become reported skips.

Hybrid deduplication retains the first parameter realization and appends all original request provenance. It never averages scores or contexts. Defaults: absolute parameter tolerance LP/UN 1e-6 Hz, SH 1e-12 probability, QN 1e-9 dB; relative tolerance zero. Near-duplicate target requests retain their original inverse parameter and requested target, alongside the actual retained parameter and actual forward difference. Exact duplicate-knot tests exercise 10 candidates → 5 retained examples per artifact. Independent stochastic realizations at the same parameter can be requested by disabling deduplication.

The three runs are alternative recipes: hybrid intentionally reuses the knot and continuous realizations from A/B on the same recording. Do not concatenate all three into one training set or count them as independent stimuli; cross-recipe fingerprints prevent normal team merging.

## Metadata and export

Common source/audio/degradation/measurements/calibration/descriptions fields remain. V2 adds `sampling_mode` and a `sampling` block with:

- Sampling profile and component; original nominal condition/parameter/unit/bridge, if applicable.
- Exact chosen generator parameter, axis and unit; requested quality and inverse parameter/policy.
- Complete `origins` including requests merged by deduplication.
- Supported parameter/quality ranges; whether the parameter falls between calibration knots.
- Forward estimate, signed forward-minus-target difference, 1e-8 numerical tolerance and no-effect status.

Calibration metadata retains mapping ID/version, frozen table hash, fitted-model/listener-split/coordinate provenance hashes, reference context, conditional reference-listener bands, both transfer-validation flags false, actual human rating null and `has_actual_human_ratings: false`. Bands are conditional stereo-reference bands, not synthetic-domain confidence intervals. A no-effect sample retains exact processing facts but has null quality/category and no fabricated rating.

`dataset/sampling_report.jsonl` gives per-source/artifact skipped requests, reasons, deduplication pairs and interval exclusions. `sampling_summary.json` records attempted, supported-before-deduplication, skipped, deduplicated and retained counts. Retained is generated audio count, not training export count. Existing no-op export filtering can reduce training rows further.

Fully rejected requests still write a diagnostic bundle with `training_ready: false`, source clips and skip reports; no empty model JSONL is presented as usable training data.

AudioLM rows remain exactly `messages` + `audios`: user then assistant and reference then degraded. Residual audio, rich metadata and quality estimates stay in aligned sidecars. Assistant text is currently the existing technical template; LLM paraphrasing and a future joint description/quality target format are separate work, not implemented here.

## Commands

On KNN:

```bash
cd /data/tingyup2/projects/AudioLM/LMushra
source /data/tingyup2/projects/AudioLM/env.sh
python -m pip install --no-deps --no-build-isolation -e .
python -m pytest -q
```

For another installation: create a Python 3.10 environment, install `requirements-generator.txt`, then `pip install --no-deps -e .`. Preserve the numerical environment when byte reproduction or team merging is required.

Inspect a selected recipe:

```bash
python -m deepmushra_data profile --profile mapped-poc-v2 --sampling-mode hybrid
```

Reproduce each completed pilot in a **fresh** output directory; existing paths are refused:

```bash
for mode in odaq_knots quality_target hybrid; do
  python -m deepmushra_data build \
    --config "configs/sampling_${mode}.yaml" \
    --manifest data/multi_mode_sources_v2/sources.jsonl \
    --dataset-id "sampling-v2-${mode}" --clip-seconds 4 \
    --output "data/sampling-v2-${mode}" \
    --audio-prefix "data/sampling-v2-${mode}"
  python -m deepmushra_data check-export \
    --bundle "data/sampling-v2-${mode}" --relative-to .
done
```

Alternatively, use `--profile mapped-poc-v2 --sampling-mode MODE` instead of `--config`. `generate` supports the same options for already prepared mono input. `prepare`, `build`, source sharding and merge retain their existing interfaces. Use a fresh destination suffix for a repeat; keep the same dataset ID, recording group IDs and final audio-prefix if comparing bytes.

Teammates can supply their own manifest or `--input-dir` using native ≥44.1 kHz mono/stereo WAV/FLAC. Preparation preserves lineage, downmixes/resamples before degradation, and exports 44.1 kHz mono. Keep a shared `recording_group_id` for excerpts/stems of one original production even across dataset IDs. Grouping omissions cannot be inferred automatically. Check licensing/attribution and benchmark exclusions before generation; no audio is committed to Git.

The eight pilot references are existing EARS/VCTK speech, GuitarSet guitar, three independent MUSDB/MedleyDB productions and two ESC-50 environmental recordings. The VCTK excerpt is 1.242375 seconds; the other seven are four seconds. Environmental inclusion is explicitly authorized for this pilot and does not initiate a broader acquisition program. Native headers, licenses, source URLs, crop lineage and checksums remain in the ignored source manifest and output sidecars. High native rate is not a cleanliness/bandwidth guarantee; prior lossy encoding may be unknown. No new data was downloaded.

## Recommendations and remaining scientific limits

Use knots for generator validation and the first interpretable Phase 1 baseline. Use hybrid for a subsequent POC/large-scale candidate recipe once independent listening establishes useful severity/content coverage; continuous targeting gives finer parameter coverage but does not add human evidence. Quality-only sampling is useful for ablations and supported-range exploration.

All current labels are ODAQ-informed reference-domain priors transferred provisionally to different synthetic operators, mono listening and unseen content. Stereo-to-mono changes, algorithmic differences, three-listener QN uncertainty and content-specific no-ops remain unresolved. Do not tune this recipe using the held-out 80% scores or call the resulting study a fully independent ODAQ benchmark. PE/TM are absent from generation, descriptions and calibration. No model training or full dataset generation was performed.

Actual experimental counts/plots and complete example metadata: [pilot report](synthetic_sampling_pilot_report.md).
