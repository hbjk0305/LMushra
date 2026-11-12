# Four-artifact mappings and generators: implemented POC

> This records the earlier mapped pilot. For the single supported release0.3.0 CLI and portable training bundles, use [the team workflow](team_generator_workflow.md). Old CLI/config examples are historical.

Date: 2026-11-11. Profile: mapped-poc-1. New module: deepmushra_mapped. Shared low-level DSP and historical outputs are preserved; public generation now uses one team workflow.

## 1. How each artifact is mapped

We use frozen cohort-weighted calibration mean curves, with piecewise linear interpolation. The inverse curve converts a requested estimated quality into a processing parameter. LP/SH/UN retain their original ODAQ axes. QN uses measured mono QNMS waveform SNR rather than substituting NMR numbers into an SNR control.

The mapping table is [mapping_table.json](../src/deepmushra_mapped/mapping_table.json), packaged with the module. It records frozen-fit, listener-split and QN-downmix-coordinate hashes. It does not require rating CSVs or ODAQ audio at generation time. No new fitting or held-out rating access occurs.

| Artifact | Control -> quality | Generator behavior |
|---|---|---|
| LP | Passband-edge cutoff -> original LP pooled mean | Causal Butterworth low-pass |
| SH | Hole probability -> original SH pooled mean | Random STFT-band zeroing |
| UN | Crossover frequency -> original UN pooled mean | Full envelope-shaped noise replacement in peak-selected bands |
| QN | Measured mono waveform SNR -> transferred QNMS pooled mean | Local spectral-shaped additive noise, with exact waveform SNR |

### Frozen knots

Values are paired in order. Frequency units are kHz, SH is percent and QN is waveform SNR in dB.

| Artifact | Parameter knots | Estimated quality means |
|---|---|---|
| LP | 5.00, 9.00, 10.50, 12.00, 15.00 | 22.78, 55.51, 65.90, 88.81, 97.95 |
| SH | 10.00, 20.00, 30.00, 50.00, 70.00 | 78.78, 66.57, 51.61, 32.93, 25.21 |
| UN | 3.00, 5.00, 7.00, 9.00, 10.50 | 45.81, 59.22, 67.93, 83.60, 89.95 |
| QN | 2.23, 6.66, 12.07, 17.72, 23.21 | 20.05, 34.92, 55.90, 74.71, 92.66 |

LP/SH/UN quality values are cohort-weighted means from nine calibration listeners, equally averaging four recordings. QN quality values are weighted means from three calibration listeners. Only QN's horizontal SNR coordinate is a median across the four downmixed recordings. Medians are not substituted for listener mean ratings.

More cutoff/crossover/SNR predicts higher quality; more SH probability predicts lower quality. All knots are already monotone. Interpolation is bounded; the module rejects unsupported generation requests and returns null from unsupported estimate queries. No curve is extrapolated.

The QN mapping's released ODAQ labels 0/6/12/18/24 remain provenance only. Its actual SNR coordinates 2.23/6.66/12.07/17.72/23.21 come from the downmix experiment; this is an empirical reparameterization of QNMS stereo priors, not an NMR identity.

![Frozen curves and pilot requests](../outputs/mapped-poc-final/analysis/mapping_curves.png)

## 2. Implemented generators

All inputs must already be 44.1 kHz mono. The new pipeline validates format and does not implicitly downmix/resample. Original recording IDs and exact duplicate checks reuse the existing source-disjoint splitting infrastructure.

- **LP:** unchanged legacy Butterworth SOS algorithm. Cutoff is its passband edge; transition 1500 Hz, ripple 0.5 dB and attenuation 60 dB. Causal phase/group delay is retained.
- **SH:** unchanged legacy STFT algorithm, with start 4 kHz, width 500 Hz, four-frame run scheduling and literal zero gain. Probability is per band/block, not percent audible frames. The profile uses 2048-point periodic Hann, hop 512.
- **UN:** unchanged legacy replacement algorithm configured with full strength 1, sigma 500 Hz and a conservative 12 dB peak threshold. The crossover is the mapped control. The threshold passes the independent white-noise negative control and tonal-replacement fixture; it is a POC design choice, not a recovered ODAQ parameter or universal tonal classifier.
- **QN:** a separate local spectral-noise algorithm. Reference power is Gaussian-smoothed in frequency separately per STFT frame (sigma 500 Hz). Seeded noise is shaped by this local envelope and inverse-transformed. A gate retains noise only where the reference sample is nonzero and past-only activity power is positive, then noise is normalized to the exact requested waveform SNR. The original signal is retained additively. Hard support gating can introduce boundary modulation; this tradeoff is recorded. It is not a psychoacoustic masking model.

QN's new local color avoids legacy whole-excerpt spectral coloring: an independent switching-tone test verifies high-frequency added-noise energy in an early low-frequency-only passage is below 1% of the later high-frequency passage. Additive SNR, silence, first-onset/gap support, seed dependence and tonal retention are tested.

LP/SH reuse the legacy implementation directly. UN changes only its POC settings. New QN is implemented in [generators.py](../src/deepmushra_mapped/generators.py). No legacy DSP/default or old configuration was edited. PE/TM remain excluded. Centered SH/UN windows still permit incidental temporal spreading; this profile makes no claim that those cues are perceptually absent.

## 3. Ready-to-run parameter requests

[configs/generator.yaml](../configs/generator.yaml) requests estimated qualities 50/65/75. Their inverse mappings are:

| Artifact | Quality 50 parameter | Quality 65 parameter | Quality 75 parameter |
|---|---:|---:|---:|
| LP | 8.326 | 10.370 | 11.096 |
| SH | 31.721 | 21.050 | 13.097 |
| UN | 3.625 | 6.327 | 7.903 |
| QN | 10.546 | 14.803 | 17.813 |

Units match the knot table: kHz, percent, kHz and dB. These targets are inside all four supported ranges. They are estimated quality requests, not measured human severity labels.

Each artifact can instead use parameters, e.g. LP: {parameters: [9000,12000]} or QN: {parameters: [12,20]}. Internal frequency units are Hz; SH probability is 0–1. Specify either quality_targets or parameters for each artifact. SH quality 90 and QN 30/40 dB are outside support and are rejected rather than silently extrapolated.

~~~bash
cd /data/tingyup2/projects/AudioLM/LMushra
. /data/tingyup2/projects/AudioLM/env.sh
# For a fresh remote environment/checkout:
python -m pip install -e '.[dev]'
python -m deepmushra_mapped generate --config configs/generator.yaml --manifest outputs/artifact-validation/mono_real_sources.jsonl --output outputs/mapped-poc-new
python -m deepmushra_mapped validate --dataset outputs/mapped-poc-new
python scripts/report_mapped_poc.py --dataset outputs/mapped-poc-new
~~~

Use a fresh output directory; existing outputs are never overwritten. For another corpus replace the manifest with grouped source/provenance JSONL or use --input-dir. Excerpts/stems of one original recording must share source_id. The module rejects known ODAQ paths/provenance as synthetic sources. No full corpus download or training is performed.

API example:

~~~python
from deepmushra_mapped.generators import generate_effect
# mono_audio has shape [samples,1], already sampled at 44100 Hz.
effect, estimate = generate_effect("QN", mono_audio, seed=123, quality=65, sample_rate=44100)
~~~

The generator API also supports parameter= instead of quality=. Sampling-rate/channel violations are rejected.

## 4. Actual pilot and objective checks

The final pilot uses the eight independent licensed MedleyDB/MUSDB excerpts prepared in the scientific audit: four-second 44.1 kHz mono sources across tonal-instrument stem proxies, drums, vocals and mixtures. Provenance/license is retained. These are not ODAQ recordings, and they are not newly certified perceptually clean references.

- Primary: outputs/mapped-poc-final/.
- Repeat: outputs/mapped-poc-final-repeat/.
- **96 triplets**, 24 per artifact; three parameter requests per source.
- Split rows: {'train': 72, 'validation': 12, 'test': 12}; all variants of one recording stay together.
- **92 provisional estimates.** Four UN cases have no eligible processing/no meaningful numerical change and retain null quality estimates. They remain visible in the manifest with status no_effect_quality_not_estimated.

| Artifact | Requested estimate | Available estimates/examples | Objective metric | Median across sources |
|---|---:|---:|---|---:|
| LP | 50 | 8/8 | stopband_spectral_energy_change_db | -36.966 |
| LP | 65 | 8/8 | stopband_spectral_energy_change_db | -32.856 |
| LP | 75 | 8/8 | stopband_spectral_energy_change_db | -34.641 |
| SH | 50 | 8/8 | eligible_tf_selection_ratio | 0.31628 |
| SH | 65 | 8/8 | eligible_tf_selection_ratio | 0.21039 |
| SH | 75 | 8/8 | eligible_tf_selection_ratio | 0.13164 |
| UN | 50 | 8/8 | reference_tonal_peak_mean_contrast_db_after | 3.6524 |
| UN | 65 | 6/8 | reference_tonal_peak_mean_contrast_db_after | 2.8181 |
| UN | 75 | 6/8 | reference_tonal_peak_mean_contrast_db_after | 3.652 |
| QN | 50 | 8/8 | measured_snr_db | 10.546 |
| QN | 65 | 8/8 | measured_snr_db | 14.803 |
| QN | 75 | 8/8 | measured_snr_db | 17.813 |

These measurements verify processing behavior, not audibility. LP's STFT stopband difference includes finite-window/boundary effects; it is not the analytic filter stopband guarantee. UN's metric is selected-peak contrast after replacement, not an overall human tonality rating. SH's realized fraction and QN's exact SNR verify their intended controls.

![Objective pilot checks](../outputs/mapped-poc-final/analysis/objective_checks.png)

No-effect detection uses the processing flag, silence and a relative residual-energy numerical tolerance 1e-20. This is not an audibility threshold. A nonzero processing difference does not establish a human-perceptible impairment.

## 5. Metadata and description contract

A [complete actual metadata record](mapped_generators_example.json) is copied from the pilot. Each sample contains source/provenance, audio references, degradation parameters/seed/evidence, measured signal changes, the original request, calibration_estimate, unverified perceptual fields, descriptions and hashes.

- calibration_estimate holds the transferred estimated mean, estimated quality category (five 20-point intervals), quality-loss proxy 100−quality, frozen-table provenance, conditional reference-listener band and explicit unvalidated mono/operator-transfer flags.
- perceptual_annotation keeps human MUSHRA, audibility, perceived severity and human quality category null.
- Technical descriptions state processing facts. Candidate perceptual descriptions are flagged unverified; estimated quality is not inserted into captions as a measured human judgment.
- The uncertainty bands are the frozen observed-listener conditional bands, linearly interpolated between knots. They are not mono/synthetic population confidence intervals. Transfer uncertainty remains null.
- New mapped-poc-1 metadata is an opt-in schema. The legacy strict 1.0 records are unchanged; downstream model loaders should use manifest.jsonl/metadata pointers for this profile explicitly.

Source, degraded and residual WAVs have matching length/rate/channels. A shared source gain provides headroom; no separate degraded normalization occurs. Residuals are computed from exact saved DOUBLE WAV signals. Masks/noise arrays are saved as compressed evidence; per-sample JSON, JSONL and per-split manifests are produced.

## 6. Validation and reproducibility

- **136 tests passed in 9.11 seconds**, including 23 new tests. Full log: outputs/mapped-poc-final.tests.log.
- Final repeated runs match **400 core files byte-for-byte**, including WAVs, evidence, metadata, manifests and run/validation records.
- Maximum residual reconstruction error: 2.78e-17; saved residual arrays equal saved degraded−reference exactly.
- Original 22 audit-listed source/config/test files and frozen calibration models/split/downmix coordinates remain unchanged.
- New package wheel builds successfully and includes mapping_table.json.
- Manifest/individual JSON consistency, evidence hashes, provisional-label status, source leakage, format, finite values and configured peak limits are checked.
- Receipt: outputs/mapped-poc-final/verification.json. Plot/metric helper: [report_mapped_poc.py](../scripts/report_mapped_poc.py). Tests: [test_mapped_poc.py](../tests/test_mapped_poc.py).

Pre-final pilots under outputs/mapped-poc-v1* are historical validation runs; use final paths above. Generated audio, outputs, environments and caches stay on KNN and out of Git. No commit/push has been performed.

## 7. Interpretation

This is an operational **ODAQ-informed mapping under explicit stereo-to-mono and approximate-operator transfer assumptions**. It is suitable for the agreed Phase 1 POC, with estimates labeled as estimates. No new mono listening evidence was created; independent mono calibration remains needed for validated severity labels. QN's reference panel has only three calibration listeners. No held-out 80% tuning, PE/TM generation, full synthetic dataset or model training was performed.

Provenance: [calibration POC](odaq_calibration_phase1_poc.md),
[QN downmix experiment](odaq_qn_downmix_poc.md), and
[operator compatibility assessment](odaq_generator_calibration_compatibility.md).
