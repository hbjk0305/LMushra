# Final end-to-end verification: generators and ODAQ integration

**Result:** the unchanged mapped-poc-1 implementation passed fresh generation, saved-file inspection, mapping round trips and training export. All 179 tests passed in 77.25s. No source code, calibration fit, listener split or sampling configuration was changed. The 77 protected file hashes match before/after.

This verifies a provisional ODAQ-informed synthetic-quality POC. It does not establish human perceptual validation of our synthetic operators.

## 1. What was run

Existing profile: package 0.3.0, mapped-poc-1; unchanged 50/65/75 engineering pilot settings. These settings were not adopted as the final dataset design. Eight independent licensed MedleyDB/MUSDB excerpts from the earlier mono audit were used, four seconds each. No ODAQ audio was a synthetic source.

Actual command, from the KNN checkout:

~~~bash
cd /data/tingyup2/projects/AudioLM/LMushra
source /data/tingyup2/projects/AudioLM/env.sh
python -m deepmushra_data build \
  --manifest outputs/artifact-validation/mono_real_sources.jsonl \
  --dataset-id final-e2e-poc --clip-seconds 4 \
  --output data/final-e2e-poc-v1 \
  --audio-prefix data/final-e2e-poc-v1
~~~

The output now exists; use a fresh output directory if rerunning. Logs/results: outputs/final_e2e_verification_v1/.

## 2. Actual saved-output checks

| Check | Fresh observed result |
|---|---|
| Generated triplets |96: 24 per artifact |
| WAV format |44100 Hz, mono, DOUBLE, 176400 samples / 4 seconds |
| Reference/degraded/residual shape |Identical for every triplet |
| Saved residual |Bit-exact equality to saved degraded−reference for all 96 |
| Reference+residual reconstruction |Maximum error 2.7755575615628914e-17; tolerance 1e-12 |
| Finite / clipping checks |All finite; maximum waveform peak 0.269097829, below .999 |
| Source lineage/alignment |Saved reference equals prepared source × recorded shared gain exactly |
| Deterministic recomputation |Selected LP/SH/UN/QN degraded waveforms and evidence arrays rerender bit-exactly |
| Calibration provenance |Correct mapping ID, table checksum, source group, panel count and profile fingerprint |
| Transfer flags |mono_transfer_validated=false; operator_transfer_validated=false |
| Human annotations |Human score, audibility, perceived severity and human category all null |
| Export |92 paired records with complete aligned metadata sidecars |
| Training contract |All 92 match the structure of all 100 dummy records on hwangbo/train at 34f4f54b5d4e96d2846cb703e9267dbcf953f686 |
| Source leakage |No source group crosses splits |

Alignment here means the same sampling grid, start index and sample count, with correct processing lineage. LP intentionally retains causal frequency-dependent phase/group delay. These checks do not establish identical acoustic feature phase or absence of SH/UN window spreading.

### Exceptions and failed checks

**No output-integrity or mapping-consistency check failed.** Important coverage observations remain:

- Four UN cases selected no eligible components: target 65/75 for Auctioneer–Our Future Faces and Clara Berry And Wooldog–Air Traffic. Their estimates are null, their human labels remain unknown, and they are omitted from model exports as designed.
- Export split counts are train 70, valid 0, test 22. The validation JSONL exists but is empty because the eight recording groups received no validation assignment under the stable hash split. This is not a structural/integrity failure; it is insufficient coverage for a training run requiring a nonempty validation set. Use a larger independent source pool rather than silently resplitting these recordings or changing their identities to force coverage.
- The five-condition proposal is accepted by the internal recipe validator, but intentionally rejected by the current shared-profile guard because it differs from the unchanged packaged recipe. A YAML-only edit would therefore not work.

## 3. Four complete mapping examples

A matched reference source was used for these four examples: final-e2e-poc:musdb18hq:Aimee Norwich - Child. Every example has actual WAVs, exact parameters/seeds, a metadata file and an independently recomputed trace.

| Artifact | Requested quality | Inverse-mapped control | Forward estimate in final metadata | Category | Rerender check |
|---|---:|---|---:|---|---|
| LP | 65 | 10370.4623614826 Hz cutoff | 65 | Good | exact audio + evidence match |
| SH | 65 | 0.210501193317423 probability | 65 | Good | exact audio + evidence match |
| UN | 65 | 6327.25615314494 Hz crossover | 65 | Good | exact audio + evidence match |
| QN | 65 | 14.8031382419543 dB waveform SNR | 65 | Good | exact audio + evidence match |

Across all 92 non-null estimates, maximum target/forward absolute error was **1.4210854715202004e-14**, below the intended **1e-8** tolerance. Four intentional no-op nulls are excluded from this equality check.

QN's example requested 14.803138241954303 dB and measured 14.803138241954304 dB in the saved signals. The maximum requested-versus-saved SNR discrepancy across QN examples was 3.5527136788005009e-15 dB.

This inverse/forward agreement is a software consistency check: both directions use the same frozen curve. It is not independent evidence that a listener would assign 65 to the synthetic output.

### Parameters and versions actually recorded

| Artifact | Underlying algorithm version | Profile version | Complete effect parameters for the example |
|---|---|---|---|
| LP | 1.1 | mapped-poc-1 | {"attenuation_db": 60, "cutoff_hz": 10370.462361482614, "filter_design": "butterworth", "passband_ripple_db": 0.5, "transition_hz": 1500} |
| SH | 1.1 | mapped-poc-1 | {"attenuation_db": "zero", "band_width_hz": 500, "hole_probability": 0.2105011933174225, "run_frames": 4, "start_hz": 4000} |
| UN | 1.1 | mapped-poc-1 | {"channel_mode": "linked", "crossover_hz": 6327.256153144944, "smoothing_hz": 500, "strength": 1.0, "tonal_threshold_db": 12.0} |
| QN | mapped-poc-1 | mapped-poc-1 | {"activity_policy": "exact_sample_support", "smoothing_hz": 500, "snr_db": 14.803138241954303} |

The active QN operator is local_spectral_additive_noise_v1. LP/SH/UN use shared algorithm 1.1 with the mapped profile's fixed settings. No generator was rewritten in this verification.

## 4. Which artifacts emit provisional quality metadata?

| Artifact | Generated examples | Non-null quality/category | Intentional nulls |
|---|---:|---:|---:|
| LP |24 |24 |0 |
| SH |24 |24 |0 |
| UN |24 |20 |4 |
| QN |24 |24 |0 |

All four can already emit estimated_quality_mean, estimated_quality_category, mapping provenance, conditional reference-listener bands and transfer flags. They emit provisional quality estimates, not measured human perceived-severity ratings.

## 5. QN bridge: independently reconstructed

### Audio observations

Four original **QNMS main-study reference items**, each at five released conditions, give 20 stereo degraded/reference pairs. For each pair:

1. Read the original 48 kHz stereo reference and degraded files.
2. Downmix each independently with (L+R)/2.
3. Resample both to 44.1 kHz using scipy.signal.resample_poly, up 147/down 160, Kaiser beta 5, constant-zero boundary handling, without additional normalization.
4. Compute residual from the resulting mono pair and waveform SNR = 10log10(sum(reference²)/sum(residual²)).
5. Take the median SNR across the four reference items at each released condition.

### Human-rating observations

The y coordinate is the **original stereo** QNMS calibration mean. It uses only the three frozen calibration listeners: two in cohort D, one in cohort E. Cohorts retain 9/16 and 7/16 total weights, and the four reference items are equally weighted. Thus each condition has 12 calibration scores; the five conditions use 60 scores. This audit recomputed those means without fitting a new model.

| Released QN condition label | Recomputed median mono SNR, dB | Min/max across four items | Frozen stereo quality mean | Calibration scores |
|---:|---:|---:|---:|---:|
| 0 | 2.228506302816 | 2.13563–2.24496 | 20.05468750 | 12 |
| 6 | 6.661260379446 | 6.55800–6.68932 | 34.92187500 | 12 |
| 12 | 12.065169538809 | 11.98916–12.23572 | 55.89843750 | 12 |
| 18 | 17.724421587885 | 17.56263–18.04444 | 74.71093750 | 12 |
| 24 | 23.205954857699 | 22.49199–23.98005 | 92.65625000 | 12 |

All five recomputed medians and means match the packaged table within 1e-12. Source-level measurements are in outputs/final_e2e_verification_v1/qn_bridge_observations.csv.

### Exclusions and validity

- Only the evaluation method QNMS and its noiseMS conditions enter this bridge—not QNLR, mixed-context conditions, PE or TM.
- Combined rating CSVs contain multiple listener roles. The loader filters by the frozen calibration role before converting/using ratings. Only calibration records were returned and aggregated; no held-out 80% score was used for fitting, coordinate construction, selection or tuning.
- The audio stimuli are shared across calibration and held-out listeners by design. Using those waveforms is not using held-out listener scores, but this remains listener-held-out rather than stimulus-independent work.
- Original stereo conditions have human MUSHRA observations. **The mono-SNR bridge itself has no mono listening validation, and our synthetic QN has no independent human quality validation.**
- The implemented link is measured mono-SNR coordinate → inherited stereo quality mean. It is not NMR=SNR, a psychoacoustic masking model, or proof that equal SNR means equal quality across different noise operators/content.

No PE/TM condition, new ODAQ download, calibration-model change or new listener split was introduced.

## 6. Training JSONL: what is ready and what is not

The actual train/valid/test files have exactly messages and audios. Messages are user then assistant, both string contents. There are two user audio placeholders and two model paths ordered reference then degraded. Residuals and the complete metadata are in copied dataset files and matching sidecars, not a third model input. All exported paths, file/evidence hashes, source splits and metadata correspondence were checked.

**Current assistant targets are technical processing descriptions only.** Estimated quality and category are in sidecars; they are not currently written into assistant text. Therefore structural AudioLM compatibility is ready, but joint description-plus-quality supervision would still need an agreed target formatter/prompt update if the model team wants the score/category in its output. No new generator or calibration fit is needed for that later text-format change. No LLM paraphrasing or model training was run.

## 7. Three requests versus five supported conditions

| Aspect | Existing 50/65/75 pilot | Proposed five-condition Phase 1 POC |
|---|---|---|
| Chosen starting point |Three requested quality values |Five supported physical conditions per artifact |
| Mapping direction |Inverse curve selects parameter; forward query confirms label |Physical parameter → forward estimated quality/category |
| Variants per excerpt |12 |20 |
| Eight-source nominal triplets |96 |160 before no-op filtering |
| Category coverage |Fair and Good |Poor/Fair/Good/Excellent, depending on artifact; no supported Bad means |
| DSP changes |None for this audit |None required |
| Calibration/model changes |None |None required |
| Shared recipe changes |None performed |Two synchronized recipe copies plus recipe-dependent checks/reports |

Q1–Q5 below are ordered processing conditions within each family, most to least degraded. They must not be relabeled automatically as Bad through Excellent. Categories come from the actual forward mean estimate. In particular, UN's worst mean is Fair, and SH's best mean is Good.

| Artifact | Recommended parameters in Q1→Q5 order | Internal axis |
|---|---|---|
| LP | 5000, 9000, 10500, 12000, 15000 | cutoff_hz |
| SH | 0.7, 0.5, 0.3, 0.2, 0.1 | hole_probability |
| UN | 3000, 5000, 7000, 9000, 10500 | crossover_hz |
| QN | 2.22850630282, 6.66126037945, 12.0651695388, 17.7244215879, 23.2059548577 | waveform_snr_db |

For QN these are the five **empirical mono-SNR coordinates**, not the raw NMR labels 0/6/12/18/24. The proposed recipe passed validation in memory only. No five-condition audio dataset was generated.

## 8. Minimum change and exact next-pilot proposal

The existing code already supports parameters lists. After approval:

1. Replace the artifact settings in configs/generator.yaml with the proposed list below.
2. Put the identical artifact settings into src/deepmushra_mapped/profile.json under config.artifacts. Updating YAML alone is rejected by check_shared_config(). Keep the generator operators and frozen mapping_table.json unchanged.
3. Refresh recipe-dependent tests/fixtures and report expectations: tests/test_mapped_poc.py currently injects quality_targets into the default setting; tests/test_team_workflow.py expects 36 examples for three sources; scripts/report_final_mapping.py asserts 50/65/75; scripts/report_mapped_poc.py selects those requests explicitly. These assumptions need to follow the five-condition recipe; this is not algorithm development.
4. Rerun the small pilot/tests and distribute the updated shared recipe fingerprint to all workers. Do not merge old/new recipe fingerprints.

**Proposed configuration only—not applied:**

~~~yaml
schema_version: mapped-poc-1
seed: 20261111
input:
  sample_rates: [44100]
  channels: [1]
  min_duration_s: 1
  max_duration_s: 30
  source_peak_limit: 0.15
  output_peak_limit: 0.999
splits: {train: 0.7, validation: 0.15, test: 0.15}
artifacts:
  LP:
    parameters: [5000, 9000, 10500, 12000, 15000]
  SH:
    parameters: [0.7, 0.5, 0.3, 0.2, 0.1]
  UN:
    parameters: [3000, 5000, 7000, 9000, 10500]
  QN:
    parameters:
      - 2.228506302815756
      - 6.661260379445558
      - 12.06516953880947
      - 17.724421587884798
      - 23.205954857698543
~~~

**Recommended command after those shared recipe/check updates:**

~~~bash
cd /data/tingyup2/projects/AudioLM/LMushra
source /data/tingyup2/projects/AudioLM/env.sh
python -m deepmushra_data build \
  --manifest outputs/artifact-validation/mono_real_sources.jsonl \
  --dataset-id final-e2e-poc --clip-seconds 4 \
  --output data/final-e2e-five-condition-v1 \
  --audio-prefix data/final-e2e-five-condition-v1
python -m deepmushra_data check-export \
  --bundle data/final-e2e-five-condition-v1 --relative-to .
~~~

Keep dataset-id fixed when comparing recipes on the same corpus so source group identities/splits do not change. With the currently unchanged packaged profile, the command would still use the old pilot recipe; it does not become five-condition merely because its output directory says so. The validation-coverage limitation of this tiny source pool remains for that controlled comparison.

## 9. Remaining transfer assumptions

- LP: nominal frequency alignment does not establish identical ODAQ edge convention, response/transition or phase.
- SH: published probability does not establish identical time/frequency masks, eligible regions, block/window behavior or stereo MS processing.
- UN: crossover alignment does not validate our peak selector/envelope or the 12 dB threshold as ODAQ-equivalent.
- QN: the empirical SNR coordinate does not equate NMR with SNR or validate the new local noise operator perceptually.
- All families: stereo ratings are provisionally transferred to 44.1 kHz mono and new content. Perception and source dependence require independent validation. Conditional reference-listener bands do not include that transfer error, especially with QN's three listeners.

These are unverified scientific assumptions, not missing pipeline modules. Do not duplicate already implemented generators, fitting, lookup, metadata or export code to address them.

## Appendix A. Actual audio/metadata paths

All paths below are relative to /data/tingyup2/projects/AudioLM/LMushra/ and exist on KNN. Generated audio is Git-ignored.

### LP: 111224f0f0615dd30bebca7e

- degraded: data/final-e2e-poc-v1/dataset/audio/111224f0f0615dd30bebca7e/degraded.wav
- reference: data/final-e2e-poc-v1/dataset/audio/reference/8db4a3a6a9c0819d755cd3d5123098bdb16a65d6432743856caadc61462a8f6d.wav
- residual: data/final-e2e-poc-v1/dataset/audio/111224f0f0615dd30bebca7e/residual.wav
- Full metadata: data/final-e2e-poc-v1/dataset/metadata/111224f0f0615dd30bebca7e.json
- Independent trace: outputs/final_e2e_verification_v1/examples/LP.trace.json

### SH: a15cbb5df074c997ce124232

- degraded: data/final-e2e-poc-v1/dataset/audio/a15cbb5df074c997ce124232/degraded.wav
- reference: data/final-e2e-poc-v1/dataset/audio/reference/8db4a3a6a9c0819d755cd3d5123098bdb16a65d6432743856caadc61462a8f6d.wav
- residual: data/final-e2e-poc-v1/dataset/audio/a15cbb5df074c997ce124232/residual.wav
- Full metadata: data/final-e2e-poc-v1/dataset/metadata/a15cbb5df074c997ce124232.json
- Independent trace: outputs/final_e2e_verification_v1/examples/SH.trace.json

### UN: 8b6124d58b18cb5517c5e9d8

- degraded: data/final-e2e-poc-v1/dataset/audio/8b6124d58b18cb5517c5e9d8/degraded.wav
- reference: data/final-e2e-poc-v1/dataset/audio/reference/8db4a3a6a9c0819d755cd3d5123098bdb16a65d6432743856caadc61462a8f6d.wav
- residual: data/final-e2e-poc-v1/dataset/audio/8b6124d58b18cb5517c5e9d8/residual.wav
- Full metadata: data/final-e2e-poc-v1/dataset/metadata/8b6124d58b18cb5517c5e9d8.json
- Independent trace: outputs/final_e2e_verification_v1/examples/UN.trace.json

### QN: 35b2888d0d80607b5ad955d8

- degraded: data/final-e2e-poc-v1/dataset/audio/35b2888d0d80607b5ad955d8/degraded.wav
- reference: data/final-e2e-poc-v1/dataset/audio/reference/8db4a3a6a9c0819d755cd3d5123098bdb16a65d6432743856caadc61462a8f6d.wav
- residual: data/final-e2e-poc-v1/dataset/audio/35b2888d0d80607b5ad955d8/residual.wav
- Full metadata: data/final-e2e-poc-v1/dataset/metadata/35b2888d0d80607b5ad955d8.json
- Independent trace: outputs/final_e2e_verification_v1/examples/QN.trace.json


## Appendix B. Complete example metadata extracts

Full original records are preserved in each sample's metadata JSON and the audit examples directory. These extracts show the complete calibration and human-annotation blocks, not fabricated ratings.

### LP — actual metadata extract

~~~json
{
  "calibration_estimate": {
    "assumptions": [
      "Original stereo quality means are transferred provisionally to mono.",
      "Synthetic operators approximate the ODAQ artifact family.",
      "QN uses measured mono QNMS median SNR, not an NMR-to-SNR identity."
    ],
    "band_interpretation": "conditional stereo-reference band; linearly interpolated between knots; not a mono/synthetic population CI",
    "calibration_listeners": 9,
    "conditional_reference_listener_weight_95_band": [
      60.587173517443226,
      69.70943045936527
    ],
    "estimated_quality_category": "Good",
    "estimated_quality_loss_proxy": 35.0,
    "estimated_quality_mean": 65.0,
    "human_mushra_score": null,
    "mapping_id": "odaq-transferred-poc-1/LP",
    "mono_transfer_validated": false,
    "operator_transfer_validated": false,
    "parameter_axis": "cutoff_hz",
    "parameter_value": 10370.462361482614,
    "reference_group": "LP_original",
    "reference_sources": 4,
    "status": "odaq_informed_provisional_transfer",
    "support_status": "inside",
    "synthetic_transfer_interval_95": null,
    "table_sha256": "a3c8a64d935b8ef9a70ee8e4783b2ca4468f0f400b2ddcbe129ee2bd5b2a7dd5"
  },
  "parameters": {
    "attenuation_db": 60,
    "cutoff_hz": 10370.462361482614,
    "filter_design": "butterworth",
    "passband_ripple_db": 0.5,
    "transition_hz": 1500
  },
  "perceptual_annotation": {
    "audibility": null,
    "human_mushra_score": null,
    "perceived_severity": null,
    "quality_category": null,
    "status": "unverified"
  },
  "request": {
    "kind": "quality_targets",
    "value": 65
  },
  "sample_id": "111224f0f0615dd30bebca7e",
  "source_id": "final-e2e-poc:musdb18hq:Aimee Norwich - Child"
}
~~~

### SH — actual metadata extract

~~~json
{
  "calibration_estimate": {
    "assumptions": [
      "Original stereo quality means are transferred provisionally to mono.",
      "Synthetic operators approximate the ODAQ artifact family.",
      "QN uses measured mono QNMS median SNR, not an NMR-to-SNR identity."
    ],
    "band_interpretation": "conditional stereo-reference band; linearly interpolated between knots; not a mono/synthetic population CI",
    "calibration_listeners": 9,
    "conditional_reference_listener_weight_95_band": [
      59.366249004724416,
      70.73125680401844
    ],
    "estimated_quality_category": "Good",
    "estimated_quality_loss_proxy": 35.0,
    "estimated_quality_mean": 65.0,
    "human_mushra_score": null,
    "mapping_id": "odaq-transferred-poc-1/SH",
    "mono_transfer_validated": false,
    "operator_transfer_validated": false,
    "parameter_axis": "hole_probability",
    "parameter_value": 0.2105011933174225,
    "reference_group": "SH_original",
    "reference_sources": 4,
    "status": "odaq_informed_provisional_transfer",
    "support_status": "inside",
    "synthetic_transfer_interval_95": null,
    "table_sha256": "a3c8a64d935b8ef9a70ee8e4783b2ca4468f0f400b2ddcbe129ee2bd5b2a7dd5"
  },
  "parameters": {
    "attenuation_db": "zero",
    "band_width_hz": 500,
    "hole_probability": 0.2105011933174225,
    "run_frames": 4,
    "start_hz": 4000
  },
  "perceptual_annotation": {
    "audibility": null,
    "human_mushra_score": null,
    "perceived_severity": null,
    "quality_category": null,
    "status": "unverified"
  },
  "request": {
    "kind": "quality_targets",
    "value": 65
  },
  "sample_id": "a15cbb5df074c997ce124232",
  "source_id": "final-e2e-poc:musdb18hq:Aimee Norwich - Child"
}
~~~

### UN — actual metadata extract

~~~json
{
  "calibration_estimate": {
    "assumptions": [
      "Original stereo quality means are transferred provisionally to mono.",
      "Synthetic operators approximate the ODAQ artifact family.",
      "QN uses measured mono QNMS median SNR, not an NMR-to-SNR identity."
    ],
    "band_interpretation": "conditional stereo-reference band; linearly interpolated between knots; not a mono/synthetic population CI",
    "calibration_listeners": 9,
    "conditional_reference_listener_weight_95_band": [
      60.3823819737879,
      69.61355595431282
    ],
    "estimated_quality_category": "Good",
    "estimated_quality_loss_proxy": 35.0,
    "estimated_quality_mean": 65.0,
    "human_mushra_score": null,
    "mapping_id": "odaq-transferred-poc-1/UN",
    "mono_transfer_validated": false,
    "operator_transfer_validated": false,
    "parameter_axis": "crossover_hz",
    "parameter_value": 6327.256153144944,
    "reference_group": "UN_original",
    "reference_sources": 4,
    "status": "odaq_informed_provisional_transfer",
    "support_status": "inside",
    "synthetic_transfer_interval_95": null,
    "table_sha256": "a3c8a64d935b8ef9a70ee8e4783b2ca4468f0f400b2ddcbe129ee2bd5b2a7dd5"
  },
  "parameters": {
    "channel_mode": "linked",
    "crossover_hz": 6327.256153144944,
    "smoothing_hz": 500,
    "strength": 1.0,
    "tonal_threshold_db": 12.0
  },
  "perceptual_annotation": {
    "audibility": null,
    "human_mushra_score": null,
    "perceived_severity": null,
    "quality_category": null,
    "status": "unverified"
  },
  "request": {
    "kind": "quality_targets",
    "value": 65
  },
  "sample_id": "8b6124d58b18cb5517c5e9d8",
  "source_id": "final-e2e-poc:musdb18hq:Aimee Norwich - Child"
}
~~~

### QN — actual metadata extract

~~~json
{
  "calibration_estimate": {
    "actual_saved_waveform_snr_db": 14.803138241954304,
    "assumptions": [
      "Original stereo quality means are transferred provisionally to mono.",
      "Synthetic operators approximate the ODAQ artifact family.",
      "QN uses measured mono QNMS median SNR, not an NMR-to-SNR identity."
    ],
    "band_interpretation": "conditional stereo-reference band; linearly interpolated between knots; not a mono/synthetic population CI",
    "calibration_listeners": 3,
    "conditional_reference_listener_weight_95_band": [
      62.001105226606434,
      68.0267826605333
    ],
    "estimated_quality_category": "Good",
    "estimated_quality_loss_proxy": 35.0,
    "estimated_quality_mean": 65.0,
    "human_mushra_score": null,
    "mapping_id": "odaq-transferred-poc-1/QN",
    "mono_transfer_validated": false,
    "operator_transfer_validated": false,
    "parameter_axis": "waveform_snr_db",
    "parameter_value": 14.803138241954304,
    "reference_group": "QNMS",
    "reference_sources": 4,
    "status": "odaq_informed_provisional_transfer",
    "support_status": "inside",
    "synthetic_transfer_interval_95": null,
    "table_sha256": "a3c8a64d935b8ef9a70ee8e4783b2ca4468f0f400b2ddcbe129ee2bd5b2a7dd5"
  },
  "parameters": {
    "activity_policy": "exact_sample_support",
    "smoothing_hz": 500,
    "snr_db": 14.803138241954303
  },
  "perceptual_annotation": {
    "audibility": null,
    "human_mushra_score": null,
    "perceived_severity": null,
    "quality_category": null,
    "status": "unverified"
  },
  "request": {
    "kind": "quality_targets",
    "value": 65
  },
  "sample_id": "35b2888d0d80607b5ad955d8",
  "source_id": "final-e2e-poc:musdb18hq:Aimee Norwich - Child"
}
~~~


## Evidence and unchanged-state record

- outputs/final_e2e_verification_v1/pilot.log and tests.log.
- actual_output_verification.json and per_sample_checks.csv: all 96 saved-triplet checks and mapping errors.
- qn_bridge_verification.json and qn_bridge_observations.csv: 20 original QNMS waveform observations and calibration-only mean verification.
- protected_before.json / protected_after.json:77 source/config/model/split/input hashes unchanged.
- Example files under outputs/final_e2e_verification_v1/examples/.
- Profile fingerprint: 3af2e4150a832daf855ab151ce1cdbbef5927ca5b49be016fb1af6163471a798.

No production source, calibration model, frozen split or sampling configuration was modified. Only the requested small pilot, verification artifacts and this report were created. No commit or push was performed.
