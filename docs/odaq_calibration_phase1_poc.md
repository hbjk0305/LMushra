# Phase 1 ODAQ-informed perceptual calibration POC

**Status — completed calibration-stage experiment.** The user authorized use of
the previously proposed approximately 20% calibration panel on 2026-11-11.
This experiment is **ODAQ-informed and listener-held-out**. It reuses ODAQ
recordings, parameter settings and listening contexts across fitting/evaluation.
It does not constitute a fully independent external benchmark.

Only the calibration stage was implemented. Existing synthetic generators and
training datasets were preserved, PE/TM were filtered before reading target
scores, and no Audio-Language Model was trained. Synthetic severity labels
remain unassigned pending transfer validation.

## 1. Frozen data use and participant split

The POC reuses the exact
`outputs/odaq_listener_calibration_feasibility_v1/proposed_listener_split.csv`
and its candidate cross-study link file. There was no listener reselection.

| Panel | Calibration records | Evaluation records |
|---|---:|---:|
| Original German expert cohort | 3 | 11 |
| Original US expert cohort | 2 | 10 |
| AES B1 | 2 | 6 |
| AES B2 | 2 | 6 |
| Stereo main, D-code sessions | 2 | 7 |
| Stereo main, E-code sessions | 1 | 6 |
| **Main totals** | **12** | **46** |

There are nine calibration IDs per original LP/SH/UN condition and three per
stereo SH/QN condition. The existing eight-listener supplementary SH proposal
remains outside this primary POC.

Nine matching D-code pairs were conservatively assigned together across studies.
Their identities are unconfirmed. After those candidate links, there are ten
calibration assignment blocks and 39 evaluation blocks. These are grouping
assumptions, with no established collection-wide count of distinct people.

| Artifact | Calibration ratings | Evaluation ratings |
|---|---:|---:|
| LP | 180 | 660 |
| SH | 318 | 1,258 |
| UN | 180 | 660 |
| QN | 168 | 728 |
| **Total** | **846** | **3,306** |

References, low-pass anchors, mono anchors, PE, TM and other processing tasks
were excluded from all fit targets and evaluation targets. The fit loader
checks the listener role before parsing a score. Tests poison evaluation
scores and PE/TM scores with non-numeric sentinels and confirm calibration
loading remains unchanged.

Within original material, German/US/B1/B2 cohort weights match the full released
panel fractions 14/42, 12/42, 8/42 and 8/42. Within stereo tests, the D/E fractions
are 9/16 and 7/16. A cohort's mass is divided among its selected listeners.
Evaluation applies the same target-population fractions using only evaluation
ratings. This keeps a change in cohort mixture from silently changing the target.

Source items and parameter cells receive equal weight within a context.
There are eleven separate artifact/context/basis mappings and 162
source/parameter/context cells. LR, MS and mixed presentation contexts remain
distinct.

Split SHA256: `60c1f20d7335d595d282e2c7341fb8ed6be90302b26002b1eaf0bc5aac15f654`.

## 2. Model definitions and calibration-only selection

### Lookup and linear interpolation

For each parameter knot, compute a cohort-weighted mean of the calibration
ratings, averaging equally over the source recordings in that context. Return
the knot mean at a tested setting and use piecewise linear interpolation
between knots in the physical parameter units. Extrapolation is rejected.

### Monotonic regression

Apply PAVA isotonic regression to the calibration knot means, then linearly
interpolate the resulting knots. Quality increases with LP cutoff, UN crossover
and the released QN NMR label. Quality decreases with SH hole probability.
Directions were declared from the processing design before evaluation.

All eleven full-panel calibration curves were already ordered in their expected
directions. Consequently, the fitted pooled lookup and monotonic knots are
identical in this experiment. This equality is a data result. Interpolation
between knots has not been directly tested against new listener-rated parameter
settings by the 80% holdout, which contains the original tested settings.

### Source-conditioned shrinkage curves

Fit a monotonic curve to each known source recording. Blend it with the pooled
monotonic curve using `alpha = n/(n+lambda)`, where n is the number of calibration
listeners per source/parameter cell. Candidate lambda values are 0, 1, 3, 9,
and fully pooled. Select lambda by cohort-weighted leave-one-calibration-listener-
out MSE. Ties favor stronger shrinkage.

This is a content-aware model through the recording identity. It learns how
the tested recordings respond to processing, without an acoustic feature model
that predicts a new recording's susceptibility. An unknown source falls back
to the pooled curve. Source-aware improvements on the 80% listener test therefore
concern familiar recordings.

The selected penalties are:

| Mapping | Calibration listeners | Source recordings | Selected pseudo-listeners lambda |
|---|---:|---:|---|
| LP_original | 9 | 4 | 3 |
| QNLR | 3 | 4 | 1 |
| QNMS | 3 | 4 | 1 |
| QNmix_LR | 3 | 4 | 1 |
| QNmix_MS | 3 | 4 | 0 |
| SHLR | 3 | 4 | 3 |
| SHMS | 3 | 2 | 9 |
| SH_original | 9 | 4 | fully pooled |
| SHmix_LR | 3 | 4 | 1 |
| SHmix_MS | 3 | 4 | 0 |
| UN_original | 9 | 4 | 1 |

For three-listener contexts, inner folds are extremely small. A fold excluding
the sole E-code listener has no E-cohort observations; its cohort weights are
renormalized over the represented cohorts. Every such case is recorded in
`fit/penalty_selection.json`. These folds provide a mechanical selection rule
with weak evidence for hyperparameter stability.

### Additional calibration-only diagnostics

Outer leave-one-listener, interior-parameter and source folds were computed
using calibration scores only. Each outer training set selects the source
penalty through a new inner listener CV, keeping outer validation scores out
of that selection. Mixed contexts have only two parameter knots, so an
interior-parameter test is unavailable.

Source-held-out prediction uses the pooled fallback. Source-conditioned curves
therefore do not establish an improvement for unseen recordings. Full CV results
are in `fit/calibration_only_cv.csv` and Appendix A below.

### Fit/evaluation boundary

Fit protocol, models, chosen penalties, predictions, CV diagnostics and resampling
outputs were hashed in `fit/frozen_fit_seal.json` before evaluation.
The evaluation command verifies these hashes and the frozen participant split.
It reads evaluation target scores only after loading the frozen predictions.
All three prespecified approaches are reported. Evaluation results did not
select penalties, change curve directions or alter predictions.

## 3. Fitted mappings

The following are the actual cohort-weighted pooled monotonic knots. Lookup
knots are identical. Values are estimated quality on ODAQ's stereo MUSHRA scale.

| Mapping | Parameter units | Tested parameter knots, ascending | Estimated quality at those knots |
|---|---|---|---|
| LP_original | cutoff_khz | 5, 9, 10.5, 12, 15 | 22.78, 55.51, 65.90, 88.81, 97.95 |
| QNLR | odaq_nmr_label_db | 0, 6, 12, 18, 24 | 21.96, 43.55, 61.88, 81.84, 93.41 |
| QNMS | odaq_nmr_label_db | 0, 6, 12, 18, 24 | 20.05, 34.92, 55.90, 74.71, 92.66 |
| QNmix_LR | odaq_nmr_label_db | 6, 12 | 41.91, 70.55 |
| QNmix_MS | odaq_nmr_label_db | 6, 12 | 41.04, 59.42 |
| SHLR | hole_probability_percent | 10, 20, 30, 50, 70 | 83.03, 73.80, 57.68, 42.81, 29.64 |
| SHMS | hole_probability_percent | 10, 20, 30, 50, 70 | 84.23, 71.89, 58.98, 41.61, 18.28 |
| SH_original | hole_probability_percent | 10, 20, 30, 50, 70 | 78.78, 66.57, 51.61, 32.93, 25.21 |
| SHmix_LR | hole_probability_percent | 10, 30 | 79.55, 53.99 |
| SHmix_MS | hole_probability_percent | 10, 30 | 54.34, 47.66 |
| UN_original | crossover_khz | 3, 5, 7, 9, 10.5 | 45.81, 59.22, 67.93, 83.60, 89.95 |

For example, LP's tested cutoff at 12 kHz maps to **88.81** estimated quality
in the original stereo context. Its quality-loss proxy is **11.19 points**,
defined as `100 - estimated quality`. This arithmetic proxy does not establish
a separate human-rated severity scale.

Complete source-conditioned knots, interpolation bounds, cohort counts,
parameter units and model identity are in `fit/models.json` and
`fit/quality_knots.csv`. As one example, UN source-specific curves at crossover
3/5/7/9/10.5 kHz are:

| Released source | Estimated quality across the five UN settings |
|---|---|
| 20c_accordion | 32.31, 46.11, 56.61, 80.65, 94.62 |
| 21_violin | 28.74, 41.72, 48.95, 76.92, 85.74 |
| AmateurOnPurpose | 57.38, 67.67, 80.32, 85.62, 87.22 |
| CreatureFromTheBlackjackTable | 64.79, 81.39, 85.84, 91.20, 92.22 |

The source-specific estimates show why a single processing-parameter value
cannot determine perceptual quality uniformly across recordings.

![LP mappings](../outputs/odaq_calibration_phase1_poc_v1/figures/LP_mappings.png)
![SH mappings](../outputs/odaq_calibration_phase1_poc_v1/figures/SH_mappings.png)
![UN mappings](../outputs/odaq_calibration_phase1_poc_v1/figures/UN_mappings.png)
![QN mappings](../outputs/odaq_calibration_phase1_poc_v1/figures/QN_mappings.png)

Thin green lines show known-source curves. Black crosses show held-out,
source-averaged targets. Shaded blue intervals have the conditional
observed-listener interpretation explained below.

## 4. Listener-held-out evaluation

The primary metric is RMSE between a frozen prediction and the held-out
cohort-weighted mean for each source/parameter/context cell. MAE, bias, Pearson
correlation, Spearman correlation and individual-listener RMSE are also retained.
Family summaries average equally over available cells, including the distinct
contexts. They do not merge those contexts into a shared fitted curve.

| Artifact | Cells | Lookup RMSE | Monotonic RMSE | Source-aware RMSE | Source-aware MAE | Fixed-fit RMSE resampling 95% interval |
|---|---:|---:|---:|---:|---:|---|
| LP | 20 | 9.72 | 9.72 | 8.47 | 6.68 | 5.90–11.55 |
| SH | 66 | 11.49 | 11.49 | 9.10 | 7.38 | 8.00–11.37 |
| UN | 20 | 16.90 | 16.90 | 7.79 | 7.03 | 5.82–10.78 |
| QN | 56 | 14.81 | 14.81 | 10.28 | 7.95 | 8.63–13.24 |

All errors use MUSHRA points. The last column resamples evaluation participant
blocks with predictions fixed. It describes evaluation-panel variability,
conditional on the fitted mapping, and excludes fitting and operator-transfer
uncertainty.

| Mapping | Cells | Lookup RMSE | Monotonic RMSE | Source-aware RMSE | Source-aware MAE | Source-aware Pearson | Source-aware Spearman |
|---|---:|---:|---:|---:|---:|---:|---:|
| LP_original | 20 | 9.72 | 9.72 | 8.47 | 6.68 | 0.975 | 0.983 |
| QNLR | 20 | 13.25 | 13.25 | 9.15 | 7.10 | 0.970 | 0.932 |
| QNMS | 20 | 12.72 | 12.72 | 9.23 | 7.37 | 0.971 | 0.964 |
| QNmix_LR | 8 | 18.12 | 18.12 | 12.19 | 8.97 | 0.926 | 0.857 |
| QNmix_MS | 8 | 19.09 | 19.09 | 13.00 | 10.53 | 0.935 | 0.952 |
| SHLR | 20 | 10.75 | 10.75 | 9.18 | 7.46 | 0.965 | 0.959 |
| SHMS | 10 | 10.57 | 10.57 | 10.20 | 8.44 | 0.942 | 0.976 |
| SH_original | 20 | 9.59 | 9.59 | 9.59 | 8.23 | 0.965 | 0.975 |
| SHmix_LR | 8 | 14.19 | 14.19 | 8.29 | 6.08 | 0.939 | 0.905 |
| SHmix_MS | 8 | 15.16 | 15.16 | 6.65 | 5.07 | 0.966 | 0.964 |
| UN_original | 20 | 16.90 | 16.90 | 7.79 | 7.03 | 0.989 | 0.977 |

The source-conditioned model has lower held-out RMSE for LP, UN and QN and for
most stereo SH contexts on these familiar source recordings. Original SH selected
complete pooling and has the same predictions under all approaches. The outcome
supports content dependence within the tested material. It provides no direct
validation for unseen synthetic recordings.

Individual listeners vary more than their panel means. Corresponding
individual-listener RMSE values are in `evaluation/metrics.csv`; these should
not be confused with cell-mean RMSE. Correlation across widely separated quality
levels can be high alongside substantial absolute score errors.

![Held-out RMSE](../outputs/odaq_calibration_phase1_poc_v1/figures/heldout_rmse.png)

### Parameter-mean evaluation

A pooled curve estimates the mean across its tested source set. As a
matched-estimand secondary diagnostic, average held-out source means at each
parameter before computing its error:

| Mapping | Monotonic RMSE against source-averaged held-out means | Tested knots |
|---|---:|---:|
| LP_original | 8.13 | 5 |
| QNLR | 5.59 | 5 |
| QNMS | 6.29 | 5 |
| QNmix_LR | 7.34 | 2 |
| QNmix_MS | 10.59 | 2 |
| SHLR | 6.95 | 5 |
| SHMS | 8.01 | 5 |
| SH_original | 8.40 | 5 |
| SHmix_LR | 3.89 | 2 |
| SHmix_MS | 5.57 | 2 |
| UN_original | 6.83 | 5 |

These secondary summaries and their interval checks were computed from the
already frozen predictions. They did not feed fitting, model selection or tuning.
Raw comparisons are in `evaluation/parameter_mean_diagnostics.csv`.

## 5. Uncertainty, especially the three-listener QN panel

### Resampling bands

The fit uses 2,000 whole-listener exponential-weight/Bayesian bootstrap draws,
normalized inside the declared cohorts. A single draw weight is shared across
candidate D-code aliases and across that listener's sources, levels and contexts.
All repeated judgments stay grouped. Shrinkage penalties remain fixed at their
calibration-CV selections, so the resampling is conditional on those choices.

These pointwise 2.5/97.5-percentile bands represent uncertainty supported by the
observed panel under this weighting procedure. They do not estimate unseen
between-listener variability in a cohort with a single observed calibration
listener. In QN and stereo SH, the sole E-cohort listener always retains
7/16 of the cohort-weighted estimate after normalization. Resampling cannot
learn the missing E-cohort variance.

### Small-panel diagnostics and interval adequacy

We also report leave-one-calibration-listener sensitivity and approximate
unweighted t intervals on per-listener source averages. For original cohorts,
cohort-weighted Satterthwaite t intervals are available. For stereo groups,
cohort-weighted t variance is unidentifiable because E has n=1.

| Mapping | Median conditional weight-band half-width | Maximum change after dropping one listener | Unweighted source-average t95 half-width range | Conditional band includes held-out parameter mean |
|---|---:|---:|---:|---:|
| LP_original | 4.23 | 3.79 | 1.04–11.44 | 20% |
| QNLR | 1.81 | 16.95 | 8.70–55.58 | 40% |
| QNMS | 0.87 | 16.08 | 3.29–52.71 | 0% |
| QNmix_LR | 2.17 | 15.09 | 31.15–49.54 | 0% |
| QNmix_MS | 3.44 | 13.84 | 33.68–46.13 | 0% |
| SHLR | 3.21 | 14.11 | 9.86–48.41 | 0% |
| SHMS | 3.08 | 10.72 | 14.64–35.34 | 0% |
| SH_original | 5.59 | 3.54 | 9.88–15.22 | 20% |
| SHmix_LR | 3.61 | 5.63 | 19.60–24.33 | 50% |
| SHmix_MS | 2.87 | 8.09 | 28.79–29.51 | 50% |
| UN_original | 4.28 | 3.89 | 3.37–12.30 | 0% |

The last column compares each pooled parameter band's intended source-mean
target with the corresponding held-out source-averaged mean. It is an empirical
check on these few public-data settings, without a claim of nominal 95% coverage.
The observed fractions demonstrate that the narrow conditional bands are
insufficient as population-confidence statements.

For QNLR, the median conditional band half-width is about **1.81 points**, yet
dropping one calibration listener can shift a fitted value by **16.95 points**.
The approximate unweighted t diagnostic reaches about **55.58 points** of
half-width. QNMS shows a similar sensitivity, with a maximum leave-one shift of
**16.08 points**. Three listeners provide weak absolute calibration evidence,
even where ordering and correlation look plausible.

Source-specific band coverage against source-specific evaluation means is also
listed in `evaluation/metrics.csv`. For pooled curves, those comparisons include
between-source heterogeneity and cannot be read as a nominal coverage test for
the source-average estimand. Source-conditioned bands have a matching
source-specific target but still inherit the small-panel limitations.

No interval was enlarged or redefined to improve observed evaluation coverage.
The t diagnostics and leave-one sensitivity were part of the fit-stage outputs.
Future calibration labels should retain all these limitations rather than
present the narrowest band as total uncertainty.

![QN sensitivity](../outputs/odaq_calibration_phase1_poc_v1/figures/QN_small_panel_sensitivity.png)

## 6. Applicability to the synthetic generators

| Artifact | ODAQ parameter axis | Current synthetic axis/details | Application recommendation |
|---|---|---|---|
| LP | 5/9/10.5/12/15-kHz cutoff | Causal Butterworth/elliptic filter; pilot 5/10/16-kHz passband edges | A provisional parameter-ordering reference within 5–15 kHz; confirm cutoff semantics, filter response, phase and playback before transferring quality values |
| SH | 10–70% nominal holes with MS/LR and listening-context differences | 4-kHz start, 500-Hz bands, four-frame runs, 80-dB gains and linked masks in the pilot | Hole probability is a related control axis, but realized coverage, removed energy, timing and basis need validation; keep context-specific estimates |
| UN | Crossover 3–10.5 kHz | Pilot fixes crossover at 7 kHz and varies replacement strength 0.25/0.5/1 | The fitted crossover curve cannot label the strength sweep directly; obtain a crossover/strength bridge using the actual implementation |
| QN | Psychoacoustic NMR label 0/6/12/18/24 dB, LR/MS | Waveform SNR 40/30/20 dB; spectral coloring and causal RMS envelope | No direct numeric conversion; a dedicated operator/content/playback validation is needed |

### QN NMR versus waveform SNR

The fitted QN curve accepts ODAQ's released NMR labels. Our generator's SNR is
`10 log10(reference waveform energy / added-noise waveform energy)`.
ODAQ's NMR involves a frequency-dependent masking reference. Its relationship
to a waveform SNR depends on signal content, masking assumptions, spectral
allocation, temporal processing and channel basis.

Equal numeric dB values do not establish equivalent noise or quality.
For example, passing synthetic `snr_db=20` into the fitted ODAQ curve at an NMR
label of 20 would substitute a different physical quantity. The current POC
does not perform that conversion. Fitted artifacts explicitly store their
parameter units and ODAQ context.

A future bridge could measure signal/noise statistics and masking-relative
quantities on independent recordings processed by the actual generator, then
validate perceived quality under the intended playback. Any use of ODAQ
ratings for that bridge would remain ODAQ-informed calibration. The current
stage has generated no such synthetic comparison set.

### Stereo-to-mono assumption

The fitted targets are the original stereo listening judgments. The current DAC
training path downmixes to mono. Neither this split nor these regressions measure
what listeners would score after downmixing. Stereo coupling, side cancellation,
spatial artifacts and noise statistics can change audibility and quality.

**All numerical mappings in this report carry an ODAQ-stereo scope.** Applying
them to mono synthetic files would be an additional unverified transfer
assumption. No mono perceptual-quality claim or synthetic label was produced.

## 7. Proposed synthetic metadata representation

Use a versioned calibration companion annotation, or a future explicitly
versioned metadata extension. The existing generator's strict metadata schema
was not altered. An illustrative companion is provided in
[`odaq_calibration_metadata_proposal.json`](odaq_calibration_metadata_proposal.json).

The proposed fields retain:

- Estimator/model ID, fit artifact digest, participant-split digest and data-use role.
- Parameter name, value and units, context, channel basis and source conditioning.
- Estimated reference-domain quality and the `100-quality` loss proxy.
- Uncertainty method, interval, effective sample support, singleton-cohort flags,
  leave-one sensitivity and the distinction between conditional and population uncertainty.
- Transfer status, synthetic operator/version, playback channels and separate
  transfer uncertainty.
- Unknown/unverified audibility, human severity and quality-category annotations.

The example uses the actual fitted LP value at 12 kHz within a clearly identified
ODAQ stereo reference domain. Its synthetic-quality and perceptual-severity
fields are null because transfer has not been validated. It is a schema proposal,
not a label attached to an existing synthetic sample.

If a transfer becomes validated, a synthetic estimate may be stored as a
model estimate with its provenance and uncertainty. Candidate descriptions
should reflect that estimated status. Quality classes or severity tiers need
declared thresholds and independent validation; processing parameters or an
estimated MUSHRA mean alone do not supply human severity annotations.

For QN, the metadata should require `odaq_nmr_label_db` for the reference
mapping and retain synthetic `snr_db` separately. No constant conversion is
established by this experiment.

## 8. Benchmark interpretation and recommendations

This POC intentionally changes the experiment's benchmark role from the earlier
external-only plan. The user authorized the frozen calibration subset's ratings
for this stage. Original ODAQ audio, CSVs and aggregate benchmark files remain
intact, while the new mappings and reports reside in separate derived outputs.

The resulting evaluation is **ODAQ-informed, listener-held-out evaluation on
shared source material and processing conditions**. It is not a fully
independent external benchmark. The split also has unresolved possible
cross-study participant identities beyond the conservative D-code blocks.
No empirical result here supports a global distinct-person count.

The recommended next use is an experimental reference for quality ordering and
content dependence. A general synthetic severity-labeling stage needs:

1. An explicit operator and parameter-compatibility bridge, especially for UN
   strength and QN SNR, with recording and playback coverage.
2. A mono listening validation if the model consumes mono.
3. More calibration listeners, particularly in the later stereo cohort.
4. New recordings and content descriptors if a content-aware model is expected
   to generalize beyond the known source IDs.
5. Population-uncertainty methods that can estimate cohort variability, plus
   validation of any quality/severity categories.
6. A separate independent evaluation when reporting broader generalization.

The current estimates can inform this next study's design. They should not be
promoted directly to verified per-sample human labels or treated as ground-truth
natural-language descriptions.

PE and TM remain excluded from calibration. Shared reference content still
limits content novelty in a later family-held-out test. Future reporting should
distinguish artifact-family novelty, listener novelty and recording novelty.

## 9. Reproduction and verification

All work is on KNN, checkout
`/data/tingyup2/projects/AudioLM/LMushra/`, branch `pt/data`.

```bash
source /data/tingyup2/projects/AudioLM/env.sh
python -m pytest -q
python -m deepmushra_calibration fit --release data/external/odaq_collection_audit/release/odaq-collection --split outputs/odaq_listener_calibration_feasibility_v1/proposed_listener_split.csv --aliases outputs/odaq_listener_calibration_feasibility_v1/candidate_cross_study_links.json --output outputs/odaq_calibration_phase1_poc_v1 --bootstrap-repetitions 2000
python -m deepmushra_calibration evaluate --release data/external/odaq_collection_audit/release/odaq-collection --split outputs/odaq_listener_calibration_feasibility_v1/proposed_listener_split.csv --aliases outputs/odaq_listener_calibration_feasibility_v1/candidate_cross_study_links.json --output outputs/odaq_calibration_phase1_poc_v1 --bootstrap-repetitions 2000
python -m deepmushra_calibration figures --output outputs/odaq_calibration_phase1_poc_v1
python scripts/report_odaq_calibration_poc.py --run outputs/odaq_calibration_phase1_poc_v1 --report docs/odaq_calibration_phase1_poc.md
```

Use a fresh output root for a repeated run. The fit and evaluation each use
2,000 resampling draws. Models use NumPy/SciPy from the existing remote
environment. No additional model weights or training environment is required.

The pipeline modules are `src/deepmushra_calibration/data.py` (role-filtered
input), `models.py` (curves/selection), `experiment.py` (fit/freeze/evaluate),
and `figures.py`; `__main__.py` supplies the commands.
`scripts/report_odaq_calibration_poc.py` generates this report and a
matched-estimand secondary diagnostics table without refitting.
`tests/test_odaq_calibration.py` covers monotonic behavior, interpolation
bounds, cohort weighting, source fallback, calibration-only fitting/selection,
candidate-alias weights and poisoned held-out/excluded score isolation.

**113 tests passed**, including nine calibration tests.
Input CSV checksums, the frozen participant split and fit artifact seals were
verified by the evaluation stage, with zero calibration/evaluation ID overlap.
The final verification receipt records generator/training-output integrity and
the independent repeat comparison. The independent run reproduced all
**24 fit/evaluation/figure files byte for byte**.

Output files:

- `fit/protocol.json`, `models.json`, `quality_knots.csv` and
  `frozen_fit_seal.json` — fitted mappings and their frozen provenance.
- `fit/penalty_selection.json`, `calibration_only_cv.csv` — calibration-only
  selection and nested diagnostic folds.
- `fit/frozen_predictions.csv`, `calibration_bootstrap.npz` and
  `calibration_mean_uncertainty.csv` — fit predictions and uncertainty.
- `evaluation/metrics.csv`, `cell_predictions_vs_heldout.csv`,
  `heldout_target_uncertainty.csv`, `parameter_mean_diagnostics.csv` —
  scoring and post-fit diagnostics.
- `figures/` — six standalone PNG figures.

Frozen split SHA256: `60c1f20d7335d595d282e2c7341fb8ed6be90302b26002b1eaf0bc5aac15f654`.
Calibration source SHA256 at fitting: `bd28e5f5bd64d9ed0c6c41ed56b429b11470692081dd9cceb843a6f2674dc77c`.
Full model artifact SHA256: `3ee63890861e144aeb237c48e760abfcf7a418d3cc8d79a83359e30f1d39e328`.

## Appendix A. Calibration-only nested validation results

The entries below are individual-rating RMSE from outer calibration-only folds,
not the final evaluation-panel-mean RMSE. Their estimands differ.
Parameter validation contains only interior knots; a two-knot mixed curve has
no such validation. Source-aware unseen-source predictions use the pooled fallback.

| Mapping | Outer fold grouping | Validation ratings | Lookup RMSE | Monotonic RMSE | Source-aware RMSE |
|---|---|---:|---:|---:|---:|
| LP_original | listener | 180 | 13.16 | 13.16 | 12.63 |
| LP_original | interior_parameter | 108 | 16.10 | 16.10 | 15.33 |
| LP_original | source | 180 | 12.83 | 12.83 | 12.83 |
| QNLR | listener | 60 | 23.76 | 23.76 | 23.00 |
| QNLR | interior_parameter | 36 | 19.44 | 19.44 | 17.50 |
| QNLR | source | 60 | 19.10 | 19.10 | 19.10 |
| QNMS | listener | 60 | 21.11 | 21.11 | 20.72 |
| QNMS | interior_parameter | 36 | 16.76 | 16.76 | 15.83 |
| QNMS | source | 60 | 16.75 | 16.75 | 16.75 |
| QNmix_LR | listener | 24 | 24.63 | 24.63 | 23.48 |
| QNmix_LR | interior_parameter | 0 | unavailable (two knots) | unavailable (two knots) | unavailable (two knots) |
| QNmix_LR | source | 24 | 21.15 | 21.15 | 21.15 |
| QNmix_MS | listener | 24 | 29.51 | 29.51 | 24.12 |
| QNmix_MS | interior_parameter | 0 | unavailable (two knots) | unavailable (two knots) | unavailable (two knots) |
| QNmix_MS | source | 24 | 30.41 | 30.41 | 30.41 |
| SHLR | listener | 60 | 18.62 | 18.62 | 18.60 |
| SHLR | interior_parameter | 36 | 14.10 | 14.10 | 13.18 |
| SHLR | source | 60 | 16.96 | 16.96 | 16.96 |
| SHMS | listener | 30 | 14.54 | 14.54 | 14.93 |
| SHMS | interior_parameter | 18 | 12.08 | 12.08 | 12.02 |
| SHMS | source | 30 | 13.83 | 13.83 | 13.83 |
| SH_original | listener | 180 | 20.27 | 20.27 | 20.27 |
| SH_original | interior_parameter | 108 | 20.69 | 20.69 | 20.69 |
| SH_original | source | 180 | 19.36 | 19.36 | 19.36 |
| SHmix_LR | listener | 24 | 17.44 | 17.44 | 15.82 |
| SHmix_LR | interior_parameter | 0 | unavailable (two knots) | unavailable (two knots) | unavailable (two knots) |
| SHmix_LR | source | 24 | 18.42 | 18.42 | 18.42 |
| SHmix_MS | listener | 24 | 27.12 | 27.12 | 23.51 |
| SHmix_MS | interior_parameter | 0 | unavailable (two knots) | unavailable (two knots) | unavailable (two knots) |
| SHmix_MS | source | 24 | 30.00 | 29.90 | 29.90 |
| UN_original | listener | 180 | 22.01 | 22.01 | 18.24 |
| UN_original | interior_parameter | 108 | 22.63 | 22.63 | 17.78 |
| UN_original | source | 180 | 24.63 | 24.63 | 24.63 |

## References

- [ODAQ original processing and listening-test design](https://arxiv.org/abs/2401.00197).
- [ODAQ stereo extension, QN NMR and presentation contexts](https://arxiv.org/abs/2512.14259).
- [ODAQ-Collection release](https://doi.org/10.5281/zenodo.23425817).
- [SciPy 1.15.2 isotonic regression/PAVA](https://docs.scipy.org/doc/scipy-1.15.2/reference/generated/scipy.optimize.isotonic_regression.html).
