# ODAQ QN downmix proof of concept

Date: 2026-11-11. Branch: pt/data. This is an ODAQ-informed audio diagnostic, not a synthetic training dataset or a new perceptual calibration study.

## Result

Downmixing is operationally straightforward and preserves pairing/residual correctness. The measured mono waveform-SNR coordinate is much more consistent across these four recordings for QNMS than QNLR. The original calibration quality curves remain unchanged: **no new mono ratings exist and no mono-quality mapping was fitted**.

The figures show how existing stereo quality priors look when paired with the actual downmixed waveform measurements. They do not establish that listeners would assign those scores in mono, or that our synthetic QN at the same SNR would sound equally impaired.

## Inputs and processing

- All 56 main-study QN-degraded conditions: QNLR 20, QNMS 20, QNmix LR 8 and MS 8. Four source identities: violin, RnB/dream_home, and the two hard-panned dialogue/music mixtures. These are repeated source/processing conditions, not 56 independent recordings. Mixed-context assets can closely repeat the separated-context audio.
- The source reference is the reference WAV within each exact trial folder; all selected originals are 48 kHz stereo. Trial-specific reference differences are retained.
- Main-study anchors, mono anchors, training examples, SH, PE and TM are excluded.
- Downmix: M=(L+R)/2 for both reference and degraded signals. No normalization, clipping, gain fitting or noise adjustment.
- Two exports: native 48 kHz mono to isolate channel averaging; 44.1 kHz mono using scipy.signal.resample_poly, up 147/down 160, Kaiser beta 5, constant-zero boundary padding. This is downsampling an original high-rate source.
- DOUBLE WAV output; reload saved reference/degraded and compute the saved residual from their exact difference. Record source hashes, resampler, pairing, measured differences and calibration-prior provenance in manifest.jsonl.
- Frozen calibration-only isotonic pooled curves are read from outputs/odaq_calibration_phase1_poc_v1/fit/models.json. No fit is changed. The curves use the three calibration listeners and cohort weights described in the existing POC; no held-out 80% scores are read.
- The script also records existing source-conditioned stereo priors as a separate diagnostic column. It does not assign them as mono labels.

## What the mapping looks like

The left plot shows the unchanged released-label-to-stereo-quality curves. The right plot replaces the horizontal coordinate with measured mono waveform SNR. The vertical values remain the same frozen stereo calibration means.

![Original curves and mono measurement coordinates](../outputs/odaq_qn_downmix_v1/figures/mapping_overview.png)

### Separated-context results at 44.1 kHz

SNR columns are the **median across four recording measurements**, not listener statistics. Quality columns are **cohort-weighted mean stereo MUSHRA estimates from three calibration listeners**, averaged equally across the source set. These are different summaries with different meanings.

| Released ODAQ NMR label | QNMS mono SNR median, dB | QNMS inherited stereo mean | QNLR mono SNR median, dB | QNLR inherited stereo mean |
|---|---:|---:|---:|---:|
| 0 | 2.23 | 20.05 | 3.48 | 21.96 |
| 6 | 6.66 | 34.92 | 8.03 | 43.55 |
| 12 | 12.07 | 55.90 | 13.43 | 61.88 |
| 18 | 17.72 | 74.71 | 18.87 | 81.84 |
| 24 | 23.21 | 92.66 | 23.52 | 93.41 |

The observed points form increasing traces. Across every source/group at both output rates, waveform SNR increased with the released NMR label: 32/32 series. Lines between plotted points are visual guides, not a new fitted mono-quality estimator. Between-knot behavior remains an assumption.

### Content and context matter

At released NMR label 12:

| Context/basis | Mono SNR range across four sources, dB | Mono SNR median, dB | Inherited stereo quality mean |
|---|---:|---:|---:|
| QNLR | 10.96–15.03 | 13.43 | 61.88 |
| QNMS | 11.99–12.24 | 12.07 | 55.90 |
| QNmix_LR | 10.96–15.03 | 13.43 | 70.55 |
| QNmix_MS | 11.99–12.14 | 12.07 | 59.42 |

QNMS has a tighter measured SNR range here than QNLR. This is evidence about these released waveforms, not proof that the psychoacoustic parameter is waveform SNR. Its endpoints and offsets are not numerically identical, and the underlying masking recipe is still unresolved.

At label 12 the LR conditions span approximately 4.06 dB across sources, versus 0.25 dB for MS. A universal label-to-SNR conversion loses content information. Prefer the actual per-example measurements over median coordinates if exploring any future transfer model.

The separated and mixed trials also retain different stereo quality priors, even when corresponding audio/SNR is very similar. At label 12, QNLR inherits 61.88 while QNmix_LR inherits 70.55. This is why presentation contexts must not be merged into one noise-quality curve or treated as independent content examples.

![Per-source coordinate traces](../outputs/odaq_qn_downmix_v1/figures/source_mapping_coordinates.png)

Each source trace pairs its measured SNR with the group-level pooled stereo prior. It is not a measured source-specific mono rating. Horizontal bars in the overview show source min/max, **not confidence intervals**. The figures do not convey population confidence; the three-rater calibration's uncertainty limitations remain in force.

## How downmix and resampling change the signal

Waveform SNR is computed as 10log10(sum(reference²)/sum(residual²)); the stereo version sums both channels. For native mono, define reference retention Rr=E(M(reference))/(E(stereo reference)/2) and noise retention Re=E(M(residual))/(E(stereo residual)/2). Then native mono SNR change=10log10(Rr/Re). The actual source correlation and error correlation determine the result.

For the 20 QNLR conditions, the combined native-stereo-to-mono44.1 kHz SNR change ranges from **−1.04 to +2.92 dB**, median **+1.25 dB**. For QNMS it ranges from **−0.26 to +0.08 dB**, median approximately **0.00 dB**. Downmix therefore does not provide a universal +3 dB improvement. A negative change is possible when reference cancellation exceeds noise cancellation.

The additional 48-to-44.1 kHz resampling step changes measured SNR by less than **0.00052 dB** across all 56 conditions in this export. That small global-SNR effect does not establish identical high-frequency content or perceptual quality.

![SNR changes](../outputs/odaq_qn_downmix_v1/figures/downmix_snr_change.png)

## Interpretation for our synthetic QN

A preliminary coordinate system is now available: released NMR label -> actual mono SNR for each ODAQ source/basis -> inherited stereo-quality prior. This is a re-expression of existing observations under an explicit unchanged-quality assumption, not new evidence for mono perceived quality.

QNMS is the more consistent measured-SNR axis in this four-source diagnostic and is a reasonable candidate for a separately declared transfer experiment. That observation does not authorize choosing it because of held-out score performance; none was examined here.

Our current QN uses whole-clip spectral coloring, a causal RMS envelope and exact per-channel waveform SNR. Matching SNR does not match local masking, noise spectrum, temporal envelope or content. Accordingly:

1. Keep measured_mono_snr_db, released_odaq_nmr_label_db and inherited_stereo_quality_prior distinct.
2. Leave mono_quality_estimate and synthetic_quality_estimate null until an independent bridge or explicitly declared provisional assumption is approved.
3. Do not assign the inherited score to our generator simply because a scalar SNR matches. Current 30/40 dB synthetic settings are also beyond the observed mono-SNR range here; 20 dB lies within the measured range but remains an operator-transfer question.
4. If an assumption-based POC proceeds, report it as ODAQ-informed and stereo-to-mono transferred, preserve the prior's three-listener uncertainty and validate with new mono listeners before treating labels as ground truth.

For example, NMR label 12 in QNMS gives median mono SNR12.07 dB and a stereo prior 55.90. It does **not** prove that synthetic mono QN at SNR 12.07 has MUSHRA 55.90. That inference would require both operator and mono-quality transfer assumptions.

## Artifacts and reproducibility

All files remain on KNN under /data/tingyup2/projects/AudioLM/LMushra/.

- Script: [scripts/analyze_odaq_qn_downmix.py](../scripts/analyze_odaq_qn_downmix.py).
- Primary run: outputs/odaq_qn_downmix_v1/; repeat: outputs/odaq_qn_downmix_v1_repeat/.
- Each run has 112 mono triplets: 56 at each sample rate. Reference WAVs are shared within each trial; there are 248 WAV files per run.
- measurements.csv: 112 per-condition/rate records, with SNR, reference/noise retention, channel-error cosine and inherited stereo prior.
- mapping_coordinates.csv: 28 group/label/rate summaries, with four-source medians and ranges. A range is not a confidence interval.
- manifest.jsonl: exact pairings, processing, metrics and explicit null mono-quality labels.
- summary.json: provenance, input/protected/output hashes and processing checks.
- verification.json: independent saved-output and repeat checks.
- Three figures above; primary/repeat run logs are outputs/odaq_qn_downmix_v1.run.log and outputs/odaq_qn_downmix_v1_repeat.run.log.

Representative 44.1 kHz mono triplet, violin QNMS/NMR12:

~~~text
outputs/odaq_qn_downmix_v1/audio/44100/QNMS_21_violin/reference.wav
outputs/odaq_qn_downmix_v1/audio/44100/QNMS_21_violin/21_violin_noiseMS_1024_NMR12.wav
outputs/odaq_qn_downmix_v1/audio/44100/QNMS_21_violin/21_violin_noiseMS_1024_NMR12_residual.wav
~~~

To regenerate on KNN, use a fresh output directory; existing outputs are never overwritten:

~~~bash
cd /data/tingyup2/projects/AudioLM/LMushra
. /data/tingyup2/projects/AudioLM/env.sh
python scripts/analyze_odaq_qn_downmix.py --output outputs/odaq_qn_downmix_new
~~~

For a long-lived session, run the command in a new remote tmux session with a remote log. The script does not access listener-rating CSVs, evaluation outputs or fit new models. It requires the already downloaded release and frozen calibration fit.

## Validation and limits

- Analytical checks: double-mono preservation, linked-noise preservation, antiphase-noise cancellation, linearity and resampling length.
- All saved residual arrays equal saved degraded−reference exactly; maximum reference+residual reconstruction error 2.78e-17.
- All waveforms finite; reference/degraded outputs remain below full scale without clipping or independent normalization.
- All source/protected hashes are preserved, including original ODAQ WAVs, generator/config/test files, calibration models/bootstrap/seal and listener split.
- Two complete runs matched **256 files byte-for-byte**, including 248 WAVs and the figures/manifests/measurements.
- Independent verification checks all saved triplets, native-energy identities, resampling linearity, figures and frozen artifacts; its receipt is verification.json.
- No listening observations, mono ratings or human severity labels were fabricated. No PE/TM, generator changes, synthetic training generation, mapping refit or model training were performed.
- The output is not an independent benchmark: ODAQ waveforms and frozen calibration ratings inform this diagnostic. The original benchmark files remain intact; derivative outputs are evaluation/calibration research assets, not training exports.

The practical result is a reproducible downmix and an informative provisional plotting coordinate. Validation of mono human quality and transfer to our different synthetic noise algorithm remain open.
