"""Summarize frozen ODAQ calibration outputs without refitting any model."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from deepmushra_calibration.experiment import read_csv, write_csv
from deepmushra_calibration.models import MODEL_NAMES


def derived_tables(root):
    cells=json.loads((root/"fit/cells.json").read_text())
    draws=np.load(root/"fit/calibration_bootstrap.npz")["predictions"]
    frozen=read_csv(root/"fit/frozen_predictions.csv")
    scored=read_csv(root/"evaluation/cell_predictions_vs_heldout.csv")
    point=np.array([[float(r["estimated_quality"]) for r in frozen if r["model"]==name] for name in MODEL_NAMES])
    target=np.array([float(r["heldout_mean"]) for r in scored if r["model"]=="isotonic"])
    output=[]
    for group in sorted({cell["group"] for cell in cells}):
        for m,name in enumerate(MODEL_NAMES):
            for value in sorted({c["parameter"] for c in cells if c["group"]==group}):
                indices=[i for i,c in enumerate(cells) if c["group"]==group and c["parameter"]==value]
                low,high=np.quantile(draws[:,m,indices].mean(axis=1),[.025,.975])
                prediction=float(point[m,indices].mean())
                heldout=float(target[indices].mean())
                output.append({
                    "group":group,"model":name,"parameter":value,"prediction":prediction,
                    "heldout_source_averaged_mean":heldout,"bayesian_lower":float(low),
                    "bayesian_upper":float(high),"covered":bool(low<=heldout<=high),
                    "source_mean_error":prediction-heldout,
                })
    write_csv(root/"evaluation/parameter_mean_diagnostics.csv",output)
    return output


def report(root, path):
    protocol=json.loads((root/"fit/protocol.json").read_text())
    models=json.loads((root/"fit/models.json").read_text())
    metrics=read_csv(root/"evaluation/metrics.csv")
    cv=read_csv(root/"fit/calibration_only_cv.csv")
    frozen=read_csv(root/"fit/frozen_predictions.csv")
    mean_uncertainty=read_csv(root/"fit/calibration_mean_uncertainty.csv")
    derived=derived_tables(root)
    relative=root.relative_to(Path.cwd()) if root.is_relative_to(Path.cwd()) else root
    links="../"+str(relative)

    knots=[]
    shrinkage=[]
    uncertainty=[]
    group_metrics=[]
    cv_rows=[]
    parameter_diagnostics=[]
    for group,entry in sorted(models.items()):
        curve=entry["models"]["isotonic"]["pooled"]
        knots.append(f"| {group} | {entry['parameter_units']} | "+", ".join(f"{x:g}" for x in curve["x"])+" | "+", ".join(f"{y:.2f}" for y in curve["quality"])+" |")
        penalty="fully pooled" if entry["selected_penalty"] is None else f"{entry['selected_penalty']:g}"
        shrinkage.append(f"| {group} | {entry['calibration_listeners']} | {len(entry['sources'])} | {penalty} |")
        rows=[r for r in frozen if r["group"]==group and r["model"]=="isotonic"]
        half=np.median([(float(r["bayesian_weight_95_upper"])-float(r["bayesian_weight_95_lower"]))/2 for r in rows])
        influence=max(float(r["leave_one_listener_max_abs_change"]) for r in rows)
        diagnostic=[r for r in mean_uncertainty if r["group"]==group]
        t_half=[(float(r["unweighted_t95_upper"])-float(r["unweighted_t95_lower"]))/2 for r in diagnostic]
        curve_checks=[r for r in derived if r["group"]==group and r["model"]=="isotonic"]
        coverage=sum(r["covered"] for r in curve_checks)/len(curve_checks)
        uncertainty.append(f"| {group} | {half:.2f} | {influence:.2f} | {min(t_half):.2f}–{max(t_half):.2f} | {100*coverage:.0f}% |")
        line=[next(r for r in metrics if r["scope"]=="group" and r["label"]==group and r["model"]==name) for name in MODEL_NAMES]
        group_metrics.append(f"| {group} | {line[0]['cells']} | {float(line[0]['rmse']):.2f} | {float(line[1]['rmse']):.2f} | {float(line[2]['rmse']):.2f} | {float(line[2]['mae']):.2f} | {float(line[2]['pearson']):.3f} | {float(line[2]['spearman']):.3f} |")
        for scheme in ("listener","interior_parameter","source"):
            rows=[r for r in cv if r["group"]==group and r["scheme"]==scheme]
            values=[next(r for r in rows if r["model"]==name) for name in MODEL_NAMES]
            numbers=[f"{float(r['weighted_rmse']):.2f}" if r["weighted_rmse"] else "unavailable (two knots)" for r in values]
            cv_rows.append(f"| {group} | {scheme} | {values[0]['validation_ratings']} | "+" | ".join(numbers)+" |")
        errors=[r["source_mean_error"] for r in curve_checks]
        parameter_diagnostics.append(f"| {group} | {float(np.sqrt(np.mean(np.array(errors)**2))):.2f} | {len(curve_checks)} |")

    artifact_rows=[]
    for artifact in ("LP","SH","UN","QN"):
        rows=[next(r for r in metrics if r["scope"]=="artifact" and r["label"]==artifact and r["model"]==name) for name in MODEL_NAMES]
        last=rows[-1]
        artifact_rows.append(f"| {artifact} | {last['cells']} | {float(rows[0]['rmse']):.2f} | {float(rows[1]['rmse']):.2f} | {float(last['rmse']):.2f} | {float(last['mae']):.2f} | {float(last['fixed_fit_rmse_resampling_lower']):.2f}–{float(last['fixed_fit_rmse_resampling_upper']):.2f} |")

    examples=[]
    for source,curve in models["UN_original"]["models"]["source_shrinkage"]["sources"].items():
        examples.append("| "+source+" | "+", ".join(f"{y:.2f}" for y in curve["quality"])+" |")

    example_rows=[r for r in frozen if r["group"]=="LP_original" and r["model"]=="isotonic" and float(r["parameter"])==12]
    value=float(example_rows[0]["estimated_quality"])
    proposal={
        "record_type":"proposed_calibration_companion_annotation","schema_version":"proposal-1",
        "synthetic_sample_id":None,"status":"proposal_only",
        "estimator":{
            "id":"odaq-calibration-poc-v1/LP_original/isotonic",
            "fit_models_sha256":hashlib.sha256((root/"fit/models.json").read_bytes()).hexdigest(),
            "split_sha256":protocol["split_sha256"],"training_role":"calibration",
            "parameter_name":"cutoff_khz","parameter_value":12.,
        },
        "reference_domain_estimate":{
            "dataset":"ODAQ-Collection/23425817","playback_channels":2,
            "context":"original LP trials","source_conditioning":"average of four released source items",
            "estimated_mushra_quality":value,"estimated_quality_loss_proxy_points":100-value,
            "observed_listener_weight_95_interval":[float(example_rows[0]["bayesian_weight_95_lower"]),float(example_rows[0]["bayesian_weight_95_upper"])],
            "interval_interpretation":"conditional resampling interval; population uncertainty and synthetic transfer are additional",
            "calibration_listener_count":9,
            "quality_category":None,"audibility":None,"human_severity_label":None,
        },
        "synthetic_transfer":{
            "status":"unverified","operator_version":None,"mono_transfer_validated":False,
            "synthetic_quality_estimate":None,"synthetic_perceptual_severity":None,
            "transfer_uncertainty":None,
            "required_evidence":"matching parameter semantics, operator response, source and playback validation",
        },
        "qn_application_rule":"A waveform snr_db value cannot be passed as an ODAQ nmr_label_db value",
    }
    lp_diagnostic=next(row for row in mean_uncertainty if row["group"]=="LP_original" and float(row["parameter"])==12)
    lp_half=float(lp_diagnostic["cohort_weighted_t95_half_width"])
    proposal["reference_domain_estimate"]["approximate_population_mean_t95"]={
        "lower":value-lp_half,"upper":value+lp_half,
        "method":"cohort-weighted Satterthwaite t on listener source averages",
    }
    proposal["reference_domain_estimate"]["leave_one_calibration_listener_max_abs_change"]=float(example_rows[0]["leave_one_listener_max_abs_change"])
    qn_rows=[row for row in frozen if row["group"]=="QNLR" and row["model"]=="isotonic" and float(row["parameter"])==12]
    qn=qn_rows[0]
    qn_diagnostic=next(row for row in mean_uncertainty if row["group"]=="QNLR" and float(row["parameter"])==12)
    proposal["additional_reference_examples"]=[{
        "mapping_id":"odaq-calibration-poc-v1/QNLR/isotonic",
        "reference_domain":"ODAQ stereo LR, separated presentation",
        "parameter_name":"odaq_nmr_label_db","parameter_value":12.,
        "estimated_quality":float(qn["estimated_quality"]),
        "conditional_observed_listener_weight_95_interval":[float(qn["bayesian_weight_95_lower"]),float(qn["bayesian_weight_95_upper"])],
        "approximate_population_mean_t95":None,
        "population_interval_status":"unidentifiable within-cohort variance: one E-cohort calibration listener",
        "unweighted_source_average_t95_diagnostic":[float(qn_diagnostic["unweighted_t95_lower"]),float(qn_diagnostic["unweighted_t95_upper"])],
        "leave_one_listener_max_abs_change":float(qn["leave_one_listener_max_abs_change"]),
        "calibration_listener_count":3,"singleton_cohort_weight":7/16,
        "synthetic_parameter_name":"snr_db","synthetic_transfer_status":"unverified",
        "synthetic_quality_estimate":None,"human_perceived_severity":None,
    }]
    proposal_path=path.with_name("odaq_calibration_metadata_proposal.json")
    proposal_path.write_text(json.dumps(proposal,indent=2,allow_nan=False)+"\n")
    verification_path=root/"verification.json"
    verification=json.loads(verification_path.read_text()) if verification_path.exists() else {}
    body="""# Phase 1 ODAQ-informed perceptual calibration POC

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

Split SHA256: `@SPLIT_HASH@`.

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
@SHRINKAGE@

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
@KNOTS@

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
@UN_SOURCES@

The source-specific estimates show why a single processing-parameter value
cannot determine perceptual quality uniformly across recordings.

![LP mappings](@ASSETS@/figures/LP_mappings.png)
![SH mappings](@ASSETS@/figures/SH_mappings.png)
![UN mappings](@ASSETS@/figures/UN_mappings.png)
![QN mappings](@ASSETS@/figures/QN_mappings.png)

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
@ARTIFACT_METRICS@

All errors use MUSHRA points. The last column resamples evaluation participant
blocks with predictions fixed. It describes evaluation-panel variability,
conditional on the fitted mapping, and excludes fitting and operator-transfer
uncertainty.

| Mapping | Cells | Lookup RMSE | Monotonic RMSE | Source-aware RMSE | Source-aware MAE | Source-aware Pearson | Source-aware Spearman |
|---|---:|---:|---:|---:|---:|---:|---:|
@GROUP_METRICS@

The source-conditioned model has lower held-out RMSE for LP, UN and QN and for
most stereo SH contexts on these familiar source recordings. Original SH selected
complete pooling and has the same predictions under all approaches. The outcome
supports content dependence within the tested material. It provides no direct
validation for unseen synthetic recordings.

Individual listeners vary more than their panel means. Corresponding
individual-listener RMSE values are in `evaluation/metrics.csv`; these should
not be confused with cell-mean RMSE. Correlation across widely separated quality
levels can be high alongside substantial absolute score errors.

![Held-out RMSE](@ASSETS@/figures/heldout_rmse.png)

### Parameter-mean evaluation

A pooled curve estimates the mean across its tested source set. As a
matched-estimand secondary diagnostic, average held-out source means at each
parameter before computing its error:

| Mapping | Monotonic RMSE against source-averaged held-out means | Tested knots |
|---|---:|---:|
@PARAMETER_METRICS@

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
@UNCERTAINTY@

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

![QN sensitivity](@ASSETS@/figures/QN_small_panel_sensitivity.png)

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
python -m deepmushra_calibration fit @ARGS@
python -m deepmushra_calibration evaluate @ARGS@
python -m deepmushra_calibration figures --output @RUN@
python scripts/report_odaq_calibration_poc.py --run @RUN@ --report docs/odaq_calibration_phase1_poc.md
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
**@REPEAT_COUNT@ fit/evaluation/figure files byte for byte**.

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

Frozen split SHA256: `@SPLIT_HASH@`.
Calibration source SHA256 at fitting: `@SOURCE_HASH@`.
Full model artifact SHA256: `@MODEL_HASH@`.

## Appendix A. Calibration-only nested validation results

The entries below are individual-rating RMSE from outer calibration-only folds,
not the final evaluation-panel-mean RMSE. Their estimands differ.
Parameter validation contains only interior knots; a two-knot mixed curve has
no such validation. Source-aware unseen-source predictions use the pooled fallback.

| Mapping | Outer fold grouping | Validation ratings | Lookup RMSE | Monotonic RMSE | Source-aware RMSE |
|---|---|---:|---:|---:|---:|
@CV@

## References

- [ODAQ original processing and listening-test design](https://arxiv.org/abs/2401.00197).
- [ODAQ stereo extension, QN NMR and presentation contexts](https://arxiv.org/abs/2512.14259).
- [ODAQ-Collection release](https://doi.org/10.5281/zenodo.23425817).
- [SciPy 1.15.2 isotonic regression/PAVA](https://docs.scipy.org/doc/scipy-1.15.2/reference/generated/scipy.optimize.isotonic_regression.html).
"""
    arguments=(
        "--release data/external/odaq_collection_audit/release/odaq-collection "
        "--split outputs/odaq_listener_calibration_feasibility_v1/proposed_listener_split.csv "
        "--aliases outputs/odaq_listener_calibration_feasibility_v1/candidate_cross_study_links.json "
        f"--output {relative} --bootstrap-repetitions 2000"
    )
    substitutions={
        "@SHRINKAGE@":"\n".join(shrinkage),"@KNOTS@":"\n".join(knots),
        "@UN_SOURCES@":"\n".join(examples),"@ARTIFACT_METRICS@":"\n".join(artifact_rows),
        "@GROUP_METRICS@":"\n".join(group_metrics),"@PARAMETER_METRICS@":"\n".join(parameter_diagnostics),
        "@UNCERTAINTY@":"\n".join(uncertainty),"@CV@":"\n".join(cv_rows),
        "@ASSETS@":links,"@ARGS@":arguments,"@RUN@":str(relative),
        "@SPLIT_HASH@":protocol["split_sha256"],"@SOURCE_HASH@":protocol["source_code_sha256"],
        "@MODEL_HASH@":hashlib.sha256((root/"fit/models.json").read_bytes()).hexdigest(),
        "@REPEAT_COUNT@":str(verification.get("repeated_files_byte_identical","pending verification")),
    }
    for key,value in substitutions.items():body=body.replace(key,value)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(body)
    print(json.dumps({"report":str(path),"metadata_proposal":str(proposal_path),"characters":len(body)},indent=2))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--run",type=Path,required=True)
    parser.add_argument("--report",type=Path)
    args=parser.parse_args()
    root=args.run.resolve()
    if args.report:
        report(root,args.report)
    else:
        derived_tables(root)
        print("Wrote post-fit parameter-mean diagnostics")


if __name__=="__main__":
    main()
