# Generator compatibility with ODAQ-based calibration

**Assessment:** 2026-11-11, branch pt/data, checkout 24dcac7c386bb90a4fd9005ffe2782e6aa4c875c. Generator package 0.2.0; algorithm 1.1.

## 1. Recommendation and scope

Retain all four generators as reproducible synthetic surrogates. A second configuration can match the published **LP, SH and UN parameter grids**, but matching those grids establishes neither operator equivalence nor perceptual-quality equivalence. QN cannot become NMR-controlled through a configuration rename or numeric conversion.

For the Phase 1 POC, keep ODAQ-domain predictions as **reference-domain estimates**, separate from synthetic perceptual labels. The smallest immediate step is a three-artifact parameter-matched profile plus explicit transfer-status annotations. Keep existing QN on its SNR axis until a masking definition or independent empirical transfer bridge is available. A complete four-artifact “ODAQ-aligned” generation mode is not yet justified.

This assessment changes documentation only. It does not refit mappings, change generators/configurations, generate a dataset, implement PE/TM, or select settings from held-out scores. Recommendations use published condition grids, code inspection and prior independent DSP probes. Frozen calibration fit/protocol artifacts were inspected; held-out score tables/evaluation outputs were not used for these recommendations.

Related work: [calibration POC](odaq_calibration_phase1_poc.md), [listener feasibility](odaq_listener_calibration_feasibility.md), [metadata proposal](odaq_calibration_metadata_proposal.json), [independent scientific validation](synthetic_artifact_validation.md), [Phase 1 pilot](synthetic_dataset_phase1_report.md), [collection audit](odaq_collection_audit.md).

## 2. ODAQ evidence: known conditions and missing details

The original paper describes LP as MUSHRA-anchor-style filtering, SH as probabilistic band zeroing, and UN as tonal-to-noise substitution under a spectral envelope. Original SH uses individually processed MS channels. Sources were normalized to −23 LUFS before processing. Its five-level axes are LP 5/9/10.5/12/15 kHz, SH 70/50/30/20/10%, and UN crossover 3/5/7/9/10.5 kHz. [Original ODAQ, Table 1 and §3.2](https://arxiv.org/html/2401.00197#S3.SS2).

The stereo extension deliberately adds noise instead of applying actual coarse quantization. Its QN labels are 0/6/12/18/24 dB; LR and MS are separate processing bases. Mixed trials change presentation context. Main stereo stimuli are 48 kHz, 24-bit, two-channel excerpts. These facts do not define the masking model or an SNR conversion. [Stereo extension, §2.2–2.4 and Tables 1–3](https://arxiv.org/html/2512.14259#S2.SS2).

All evidence below is already on KNN, relative to the checkout. External assets remain Git-ignored.

| Evidence | Exact location / interpretation |
|---|---|
| Frozen official repository | data/external/odaq_collection_audit/official_repository/; README and benchmark loader/evaluation files, not artifact-synthesis code |
| Original conditions | data/external/odaq_collection_audit/release/odaq-collection/2024-icassp/ODAQ_listening_test/; e.g. LP_11_guitar and UN_21_violin |
| Stereo conditions | data/external/odaq_collection_audit/release/odaq-collection/2025-aes/ODAQ_v1.5_listening_test/; e.g. QNmix_21_violin/21_violin_noiseLR_1024_NMR12.wav |
| Inventory and integrity | External sources/archive_inventory.json, pair_inventory.json and full_release_receipt.json; archive SHA256 4c2c33bdb1cdec2b91a79dace7515b8ef42d618cb8e870b3e3a0e47b91dacbe3 |
| Frozen calibration protocol | outputs/odaq_calibration_phase1_poc_v1/fit/protocol.json |
| Frozen mappings | Same fit directory, models.json SHA256 3ee63890861e144aeb237c48e760abfcf7a418d3cc8d79a83359e30f1d39e328 |
| Frozen participant split | outputs/odaq_listener_calibration_feasibility_v1/proposed_listener_split.csv; SHA256 60c1f20d7335d595d282e2c7341fb8ed6be90302b26002b1eaf0bc5aac15f654 |
| Independent probes | outputs/artifact-validation/{summary,supplementary,parameter_probes,tonality_detail}.json |
| This review's verification | outputs/odaq_generator_compatibility_review/{hashes_before.json,generator_tests.log,verification.json} |

Released names include LP50/LP90/LP105/LP120/LP150, SH70_MS through SH10_MS, UN3k through UN10.5k, and noiseLR_1024_NMR* / noiseMS_1024_NMR*. A filename is a condition identifier, not a full processing specification. **The 1024 token does not establish FFT size, window, hop, overlap or noise temporal support.** The previous collection audit calls it “1024-sample processing”; this assessment deliberately narrows that inference.

No LP coefficients, realized SH masks, seeds, full UN detector/envelope specification or executable QN masking recipe were found in the inspected release documentation/metadata and frozen official snapshot. The papers cite Dick, Schinkel-Bielefeld and Disch, AES 2017 paper 10001, as the originating framework. Its full generation recipe was not independently verified here. Unresolved details must not be replaced with assumptions about typical codecs.

## 3. Compatibility decision table

“Reuse” means family-level surrogate reuse. “Direct axis” means matching units and named physical role; implementation/perceptual equivalence remains unverified.

| Artifact | Reuse unchanged? | Configuration-only alignment? | Algorithmic modification necessary? | Direct axis | Unsupported correspondence and family assessment |
|---|---|---|---|---|---|
| LP | Yes, as causal bandwidth limitation | Yes: published cutoff grid, fixed declared response settings | Not for parameter-matched POC; conditional on a verified target response requiring another operator | Nominal frequency Hz↔kHz, subject to edge definition | Passband edge need not equal ODAQ cutoff. Design, transition, phase and quality unverified. Same bandwidth-loss family |
| SH | Yes, as random band attenuation/removal | Yes: probabilities and literal zero gain | Not for mono surrogate; explicit basis/mask policy needed for a stereo comparator | Probability p↔percent/100 | No verified correspondence for eligible region, runs, bands or masks. Same spectral-gap family, possible temporal/spatial side effects |
| UN | Yes, with selection limitations | Yes: crossover sweep, full replacement strength 1 | Needed before claiming robust tonal-only selection; exact ODAQ recipe still unknown | Nominal crossover Hz↔kHz | No ODAQ counterpart for our blend strength, sigma or threshold. Same family on tonal fixtures; current defaults also modify noise |
| QN | Yes, as additive SNR-controlled noise | **No** NMR alignment through existing configuration | A specified masking path is needed for genuine NMR control; empirical transfer is a different option | None between snr_db and released NMR labels | No justified numeric conversion. Same additive-noise family with different masking/locality behavior |

No row authorizes treating an ODAQ stereo MUSHRA prediction as verified mono synthetic quality.

## 4. Implementation review and configuration ranges

Sources: [degradations.py](../src/deepmushra_data/degradations.py), [stft.py](../src/deepmushra_data/stft.py), [config.py](../src/deepmushra_data/config.py), [pipeline.py](../src/deepmushra_data/pipeline.py). Tests: [test_degradations.py](../tests/test_degradations.py), [test_phase1.py](../tests/test_phase1.py), [test_pipeline.py](../tests/test_pipeline.py), [test_audioio.py](../tests/test_audioio.py).

### Shared waveform and stereo contract

The training target is 44.1 kHz mono. The library currently supports both 44.1/48 kHz and mono/stereo; all three checked YAML files permit both rates/channels. Input validation does not convert formats. The first real-content pilot used stereo; the later independent scientific audit includes 104 mono44.1 kHz triplets. A mono-only profile must explicitly restrict input.sample_rates=[44100] and input.channels=[1], with documented source preparation.

Default STFT: 2048-point periodic Hann, hop 512, zero boundary extension, padded end, spectrum scaling and matched ISTFT trimmed to original length. At 44.1 kHz: 46.44 ms window, 11.61 ms hop, 21.53 Hz/bin. The same integers at 48 kHz change physical resolution. Identity reconstruction passes, but modified coefficients may be inconsistent under synthesis/reanalysis.

All effects preserve length, sample rate and channel order. LP changes internal phase; equal array indices do not guarantee equal feature phase. Existing silent-channel tests find no crosstalk. SH shares masks across channels; UN shares selection with linked/independent noise; QN uses linked/independent noise with channel-dependent shaping. These policies do not reproduce independently processed LR or MS conditions automatically.

One source-dependent peak-reduction gain is applied before degradation. Output is DOUBLE WAV; saved reference/degraded signals are reloaded before residual=degraded−reference is saved. Peak violations raise errors; no clipping or separate degraded normalization occurs. The current peak policy is not −23 LUFS normalization. Future loudness preparation must precede both versions, retain headroom and be recorded. Separate post-processing gains would alter the intended energy/noise relationship.

### LP: causal IIR with passband-edge control

Implementation: _lowpass, lines 106–135; validation/defaults lines 14–89. Butterworth/elliptic order is derived from passband edge cutoff_hz, stopband edge cutoff+transition_hz, ripple and attenuation. SOS filtering is causal, zero-state, independently per channel, with no delay compensation.

Defaults: transition 1500 Hz, ripple 0.5 dB, attenuation 60 dB. Cutoff/transition must be positive, stopband below Nyquist; ripple 0.01–3 dB; attenuation ripple+1 through 120 dB; order capped at 256.

[phase1.yaml](../configs/phase1.yaml) and [pilot.yaml](../configs/pilot.yaml) use 5/10/16 kHz. [sampled.yaml](../configs/sampled.yaml) samples 5–16 kHz. Cutoff is not the −3 dB point: the existing 5 kHz Butterworth probe reaches −3 dB around 5174.7 Hz, with order 28 and maximum measured passband group delay 1.292 ms.

Causality avoids pre-onset output in tests, but startup response, frequency-dependent delay and post-ringing remain. Residual energy can be phase-dominated; it is unsuitable as the sole LP severity correspondence. Preserve phase policy until verified response evidence justifies a versioned alternative. Forward/backward filtering would change magnitude response and introduce noncausal ringing.

**Decision:** configuration alignment of nominal cutoffs is justified. Transition/ripple/attenuation remain declared synthetic choices. Verify the target cutoff convention and magnitude/phase response before changing filter design.

### SH: random bands and nonoverlapping run blocks

Implementation: _holes, lines 138–157. Eligible bins above start_hz are grouped by band_width_hz. Bernoulli choices are independent per band and nonoverlapping block of run_frames; selected blocks attenuate every band/frame coefficient. Adjacent blocks can join. The gain mask is linked across channels.

Ranges: p 0–1, start 0–Nyquist exclusive, width 1 Hz–Nyquist, run integer 1–100000, attenuation 0–200 dB or literal zero. Phase 1 uses start 4 kHz, width 500 Hz, run 4, attenuation 80 dB and p=.1/.3/.7. Sampled settings use p=.05–.5, widths 250/500/1000 Hz and runs 1–8.

This is not an SMR-ranked hole selector. Probability is per eligible band/block, not percent frames, percent waveform or audible-event coverage. At 44.1 kHz run 4 schedules four hops, approximately 46.44 ms; waveform support also depends on window overlap. Bin quantization/boundaries change realized regions. The saved gain mask is exact for processing, not a promise of zero reanalyzed coefficients.

A mono signal encoded as double mono has zero side signal, but that algebra does not transfer ratings from a real stereo scene. Shared LR masks do not reproduce an unspecified MS masking policy.

**Decision:** use p=.1/.2/.3/.5/.7 and attenuation_db: zero for a parameter-matched removal profile. Retain start/width/run as explicitly unmatched controls. Current 80 dB attenuation remains valid in diverse mode but is not literal zeroing.

### UN: peak-selected band replacement

Implementation: _unmasked_noise, lines 160–207. Gaussian-smoothed power defines an envelope; smoothing_hz is its Gaussian standard deviation. Channel-RMS peaks above the envelope by tonal_threshold_db trigger replacement of entire bands of width2×sigma above crossover_hz. Seeded noise is envelope-shaped and normalized to original band/frame/channel energy. Complex blending is followed by another energy normalization.

Ranges: crossover 0–Nyquist exclusive, strength 0–1, sigma 1 Hz–Nyquist/2, threshold 0–60 dB, linked/independent noise. Defaults: crossover 7 kHz, strength .5, sigma 500 Hz, threshold 6 dB, linked noise.

Phase 1 varies strength .25/.5/1 at fixed 7 kHz. Pilot settings vary crossover and strength together; sampled settings vary crossover 3–12 kHz, strength .1–1 and sigma 250–1000 Hz. **Strength is not percentage energy replaced**, because normalization follows blending. An ODAQ crossover curve cannot label a fixed-crossover strength sweep.

Existing independent negative controls reveal default selection of 31.97% of analyzed TF cells on white noise. A threshold crossing is not evidence of persistent tonality. Raising thresholds suppresses that fixture but may miss real tones; it is not a validated repair.

**Decision:** nominal crossover-grid alignment with strength 1 is possible. Detector/envelope equivalence is unknown. Validate a separately versioned detector before claiming robust tonal-only replacement. In present descriptions use “noise replacement in peak-selected bands”; perceived tonal loss remains unverified. Exact EnCodec/DAC behavior is not established either.

### QN: global spectral color, causal envelope, exact SNR

Implementation: _quantization_like_noise, lines 210–251. Whole-excerpt mean STFT power is Gaussian-smoothed in frequency. Its square-root profile designs a finite FIR converted to minimum phase. Causally filtered seeded white noise is multiplied by a past-only exponential RMS envelope, then scaled per channel to exact requested waveform SNR. Original content remains additively present.

Defaults: SNR 30 dB, sigma 500 Hz, envelope 5 ms, 129 taps, independent noise. Ranges: SNR 0–100 dB, sigma 1 Hz–Nyquist/2, envelope .1–1000 ms, odd taps 17–2049. Phase 1 uses 40/30/20 dB.

There is no masking threshold, critical-band spreading, absolute hearing threshold/level calibration, tonality correction or framewise local spectral target. Initial causality does not imply local spectral fidelity: the independent switching-tone probe puts 49.956% of high-frequency added-noise energy in the earlier 1 kHz-only passage, because the color uses the whole clip. This is not temporal pre-echo. Envelope decay also carries noise into later gaps.

**Decision:** retain as additive signal-shaped noise with measured SNR. Its stored “selected mask” is derived diagnostic noise support, not a psychoacoustic masking threshold or applied gain mask.

## 5. Incidental temporal cues and the PE holdout

PE/TM remain excluded from generation and calibration. Excluding names does not establish absence of their cues.

The prior independent window ablation measured pre-onset residual support for SH/UN. At 2048 points it found 29.02/28.87 ms respectively, at a relative −80 dB amplitude engineering criterion. Corresponding pre-onset residual-energy fractions were 0.000235/0.004218. These are fixture-specific objective measurements, not human audibility.

Centered windows detect an onset using samples on both sides. Modification disrupts cancellation responsible for identity-path silence. Analysis-plus-synthesis support can approach a full window, not merely half. Shorter windows reduce extent in some probes but change resolution, masks and detection. They cannot be selected as an ODAQ match from the1024 filename token.

QN is exactly zero before the first onset in its tested fixture but can trail offsets/gaps; LP is causal with post-ringing. Neither guarantees artifact isolation on all material.

Recommended policy: record incidental SH/UN pre-onset support/energy, define a preregistered engineering tolerance on independent transient material, and agree how this limits the PE holdout claim. If strict zero pre-onset modification is required, propose a separately versioned onset-aware restriction or causal analysis design, including checks for its boundary artifacts. No such change is made here. Do not generate PE captions from incidental ringing.

## 6. QN: NMR versus SNR and masking-model feasibility

The current control is

SNR_wave = 10 log10(sum x_r² / sum (x_d−x_r)²),

over the entire saved excerpt, independently per channel. It does not determine the noise's relationship to a local masking threshold.

For a **new explicitly declared** model with threshold power T(t,b), one possible convention is

NMR_local(t,b) = 10 log10(P_noise(t,b) / T(t,b)).

A desired offset r targets P_noise=T×10^(r/10). This is a proposed convention, not a verified definition of ODAQ's filename labels. Increasing r increases noise here. Published Q1→Q5 instead associates increasing released labels with improving quality. Sign, reference and aggregation therefore require clarification; do not silently negate labels or assume r=−label. The original paper cites Brandenburg's 1987 NMR work without supplying the executable threshold recipe.

Even with a declared model, conversion to global SNR requires the source, time/band weights, transform normalization and overlap-add realization. Ratio-of-sums differs from mean-of-ratios and mean-dB aggregation. Silence floors, playback-level assumptions and channel basis add dependencies. No source-independent constant converts current 20/30/40 SNR settings into released 0/6/12/18/24 labels.

### Necessity

- Mask-relative generation requires a specified threshold model or verified original model. Smoothed source power alone is not a masking threshold.
- Current SNR QN needs no masking model to remain useful.
- Independent empirical listening calibration could transfer quality to current QN without a masking model; that establishes an empirical SNR/content relationship, not NMR equivalence.
- A generic masking model alone cannot reproduce ODAQ without its conventions and processing details.

### Feasibility and candidate reference

A framewise CPU masking path is feasible in principle at pilot scale; units, auditory calibration, noise synthesis and validation dominate scientific complexity. No throughput benchmark or model integration was performed here.

GstPEAQ is a concrete inspectable reference. Its FFT ear model exposes excitation/masking quantities; peaq_mov_nmr documents bandwise noise/mask calculation. Source headers specify GNU Library GPL v2-or-later; the project says it does not meet BS.1387-1 conformance tolerances. It is an assessment implementation, not an ODAQ noise generator. [Official repository](https://github.com/HSU-ANT/gstpeaq), [NMR source](https://github.com/HSU-ANT/gstpeaq/blob/develop/src/movs.c#L793), [license](https://github.com/HSU-ANT/gstpeaq/blob/develop/COPYING).

Its noise pattern uses processed spectral-magnitude differences; substituting a waveform-residual PSD changes the definition. A CLI aggregate score is not an invertible synthesis mask. Inspect exact commit, auditory level mapping, sample-rate constraints, dependencies and license integration before adoption. No package was installed.

Smallest defensible route:

1. Request ODAQ's model/version, label sign/reference, transform/window/hop, level calibration, temporal shaping, LR/MS normalization and noise correlation. This author inquiry is proposed, not completed.
2. If unavailable, declare an independent versioned model: auditory bands, spreading, tonal/noise masker treatment, absolute-threshold and dBFS-to-SPL assumption, aggregation, silence policy, rate and temporal support.
3. Add a separate optional masking-shaped QN algorithm, preserving legacy SNR behavior. Distinguish mask_nmr_offset_db from snr_db and from odaq_nmr_label_db.
4. Derive local target noise from reference only, add seeded noise without tonal replacement, and measure achieved quantities after final synthesis/saving. Requested local ratios will not automatically survive overlap-add.
5. Avoid backward/pre-masking temporal spread initially to protect the PE holdout; this is a declared synthetic restriction, not an ODAQ claim. Verify finite-window onset and offset behavior.
6. Store achieved model-relative NMR distributions and waveform SNR together. Agreement under a model does not prove equal human quality.

A simpler framewise local-color QN could improve locality without a masking model. It would still be SNR-controlled and would not solve NMR calibration. Treat it as another optional version, not as ODAQ equivalence.

## 7. Proposed two-mode generation design

These are proposals, not newly written configs or accepted parser keys.

| Property | Diverse synthetic mode | ODAQ-parameter-matched POC mode |
|---|---|---|
| Operator | Existing algorithm 1.1 unchanged | Initially same LP/SH/UN, unmatched details explicit |
| Sampling | Broad current ranges; provisional parameter tiers | Published discrete axes, vary one aligned control at a time |
| Sources | Explicit format profile; historical runs preserved | Independent mono44.1 kHz sources; optional native stereo comparators separately labeled |
| QN | Existing waveform-SNR control | NMR transfer unsupported pending a declared model/bridge |
| Labels | Unknown unless independently assessed | ODAQ-domain prior plus transfer status; synthetic quality unknown |
| Reproducibility | Old config hashes/seeds unchanged | New profile/hash; new algorithm IDs only for changed operators |

### Configuration-only proposals through existing keys

| Effect | POC axis | Remaining declared synthetic controls |
|---|---|---|
| LP | cutoff_hz=[5000,9000,10500,12000,15000] | Butterworth, transition 1500 Hz, ripple .5 dB, attenuation 60 dB; edge/phase correspondence unverified |
| SH | hole_probability=[.1,.2,.3,.5,.7], attenuation_db=zero | start 4000 Hz, width 500 Hz, run 4, FFT 2048/hop 512 are legacy controls, not inferred ODAQ settings |
| UN | crossover_hz=[3000,5000,7000,9000,10500], strength=1 | Sigma 500 Hz, threshold 6 dB and selection remain provisional; disclose noise false positives |
| QN | No NMR-aligned value via snr_db |40/30/20 dB may remain independent SNR examples, without transferred labels |

All grids come from published conditions, not held-out scores. There is no scientifically determined ODAQ match for our remaining controls. For one channel, linked/independent noise cannot represent a spatial condition.

Existing recipes accept these LP/SH/UN settings; no DSP rewrite is needed merely to enumerate them. The parser rejects a new top-level mode key. Initially use separate YAML filenames and run documentation rather than silently extending semantics. Keep parameter_tier unspecified. Proposed mono profile restricts rates/channels; no conversion is implicit.

Do not extrapolate curves to LP 16 kHz, UN 12 kHz, SH p<.1 or arbitrary QN SNR settings. These remain legitimate diverse-mode parameters with unsupported calibration transfer. Mixed-context curves have narrower support as documented below.

## 8. Stereo-to-mono and sample-rate limitations

Synthetic training prepares independent mono sources, then degrades at 44.1 kHz. ODAQ mappings predict quality of original stereo conditions. This is a domain shift even when an artifact is primarily timbral.

For D(L,R)=(L+R)/2 and identical linear LP H, D(Hx)=H(Dx), before nonlinear gain decisions. This algebra does not equate subjective stereo/mono ratings. For SH it may hold under identical LR masks, but not generally under independently selected MS/LR masks. UN detection/envelope normalization and QN shaping/scaling depend on channel content; downmixing and processing generally do not commute.

Averaging independent equal-power LR noise halves its power; linked noise may retain it. Reference power changes with its own correlation. There is no universal 3 dB SNR correction. Side errors may disappear, and spatial/binaural/context cues change.

Resampling 48→44.1 kHz changes Nyquist 24→22.05 kHz and removes the top band. Fixed FFT integers change time/frequency resolution; digital filter responses change too. Record downmix convention, resampler/anti-alias filter, operation order, loudness and gain. Recompute metrics and residuals from the exported saved pair, rather than separately resampling a prior residual. Preserve native ODAQ assets.

Any interim assumption must be explicit: “stereo-derived quality is provisionally used as a prior for timbral quality of prepared mono signals.” Its error bound is unknown. A stereo-test mono anchor does not validate mono artifact curves. Keep LR, MS and mixed-context mappings separate; do not choose a curve according to the desired label.

## 9. Transfer protocol, uncertainty and metadata

The frozen fit contains 11 context/basis mappings. Original LP/SH/UN use 9 calibration raters per source/level; stereo SH/QN use 3 (two D-cohort, one E-cohort). Preserve split seed 20261110, namespaced participant/cohort IDs and candidate cross-study grouping. Source-aware curves condition on actual known recordings, not semantic categories transferable by renaming a new source.

### Application gates

1. Verify artifact, algorithm/version, parameter semantics/units, rate, channels/basis, source domain, context and range. An in-range scalar is insufficient.
2. Use a predeclared frozen pooled/monotonic model only within its reference-domain support: original LP 5–15 kHz, UN 3–10.5 kHz, SH 10–70%; retain distinct stereo models. SH mixed contexts cover 10/30% only; QN mixed contexts 6/12 labels only. Do not add excluded anchors as fit knots.
3. Treat interpolation as model-dependent. Existing listener-weight intervals do not capture between-knot shape uncertainty. Outside support or on a different axis, return null with a reason.
4. Establish a cross-operator/content/mono bridge on independent recordings with independent judgments. Fit correction on a bridge calibration partition; validate on source/production-disjoint material. Keep stems/crops/repeated recordings grouped.
5. Until bridge validation, store a reference-domain prior separately; leave synthetic_quality_estimate, perceived_severity, quality_category and audibility null. Do not insert a predicted human judgment into a factual description.

QN's three-rater panel is particularly weak for population inference. The singleton E-cohort retains 7/16 target-panel weight and supplies no within-cohort variance estimate. Conditional listener-weight bootstrap bands reflect observed panel weights and fixed selected hyperparameters, not unobserved listeners, new sources, operator mismatch or mono transfer. Narrow bands do not establish confident synthetic labels.

Keep uncertainty components separate: conditional mapping interval, cohort/listener limitations and leave-one-listener sensitivity, source variation, interpolation uncertainty, operator transfer and stereo→mono transfer. Unidentified components should be null/status text, not arbitrary widening factors. Do not combine dependent variance components without a joint model. Quality loss 100−quality is only a proxy, not an artifact-specific perceived-severity measurement.

### Proposed companion example

This is an unexecuted lookup request, not an annotated audio sample. It extends the existing companion proposal conceptually and does not change the generator schema.

~~~json
{
  "schema_version": "compatibility-proposal-1",
  "sample_id": "future-synthetic-id",
  "generation": {
    "artifact": "LP",
    "algorithm_version": "1.1",
    "profile": "proposed-odaq-parameter-matched",
    "sample_rate_hz": 44100,
    "channels": 1,
    "parameters": {
      "cutoff_hz": 12000,
      "filter_design": "butterworth",
      "transition_hz": 1500,
      "passband_ripple_db": 0.5,
      "attenuation_db": 60
    }
  },
  "calibration_request": {
    "mapping_id": "odaq-calibration-poc-v1/LP_original/isotonic",
    "split_seed": 20261110,
    "parameter_name": "cutoff_khz",
    "parameter_value": 12.0,
    "scalar_range_status": "inside",
    "reference_domain": "ODAQ original stereo LP trials",
    "reference_domain_prediction": null,
    "prediction_status": "request_example_not_executed"
  },
  "transfer": {
    "operator_match": "unverified",
    "cutoff_definition_match": "unverified",
    "mono_transfer_validated": false,
    "content_transfer_validated": false,
    "synthetic_quality_estimate": null,
    "transfer_interval_95": null,
    "status": "prior_only_transfer_unverified"
  },
  "perceptual_annotation": {
    "audibility": null,
    "perceived_severity": null,
    "quality_category": null,
    "human_mushra_score": null
  },
  "description_policy": {
    "technical_facts": "allowed_from_generation_and_measurements",
    "perceptual_candidate_status": "unverified",
    "calibrated_quality_claim": "blocked_until_transfer_validated"
  }
}
~~~

For QN distinguish waveform_snr_db, odaq_nmr_label_db, requested_mask_offset_db and measured_model_nmr. Missing correspondence is null, not a copied number. Future masking metadata needs model/version, sign/aggregation, units, signal-level assumption and requested/achieved values.

ODAQ ratings used for calibration are training-relevant benchmark information even when ODAQ audio does not enter SFT. Report **ODAQ-informed, listener-held-out evaluation**, not an independent external ODAQ benchmark. Original data/split remain intact. The 80% have already been evaluated once in the frozen POC; do not use them for iterative generator selection. Choosing future methods from those results requires a newly declared protocol or independent test set.

## 10. Proposed verification experiments

Completed here: code/config/test inspection, method/documentation review, frozen fit/protocol inspection and existing generator test rerun. No new audio search/optimization, masking implementation, listening study or parameter sweep was performed.

Use independent licensed sources/analytical fixtures for the following work:

| Experiment | Measurements and predeclared evidence | Decision |
|---|---|---|
| LP response/phase | Magnitude, pass/−3 dB/stop edges, impulse, group delay and ringing; compare verified target response if obtained | Config representability versus new operator |
| SH masks/locality | Eligible-band/block coverage, runs, exact zero gain, removed energy, reanalysis leakage, onset support | Probability semantics and temporal cues |
| SH stereo algebra | Explicit invertible LR/MS transforms, silent side, shared/independent masks, downmix-before/after difference | Scope of waveform equivalence without inheriting scores |
| UN selectivity | Tones/harmonics/noise/mixtures/transients; selection false positives/negatives, tone retention, local flatness and envelope error | Need for a versioned detector; valid crossover sweep |
| QN locality | Switching bands, gaps and attacks; saved SNR, frame/band noise PSD, tone retention, onset/offset support | Separation from UN and adequacy of shaping |
| Mask-model units | Power scaling, ±6 dB target-offset response, silence/level floors, supported rates, target/achieved NMR and deterministic seeds | Genuine control of a declared masking quantity |
| Rate/channel export | Lost-band energy, changed SNR/NMR, fresh residual consistency | Quantify domain shift, not recover mono human labels |
| Independent listening bridge | Native/mono/operator pairs, new listeners and source-disjoint evaluation | Transfer-error calibration and perceptual-label validation |

Retain finite waveforms, unchanged lengths/rates/channels, deterministic output, no peak violations and exact saved residual consistency. Preregister detector/locality/perceptual tolerances on independent development data before final bridge evaluation; do not derive them from held-out ODAQ listeners.

Any later authorization to analyze calibration-domain ODAQ waveforms should log LP/SH/UN/QN assets and resulting choices as calibration usage. Avoid held-out ratings and PE/TM conditions. This review used prior independent probes, not a new ODAQ audio parameter search.

### Current test result and preservation

Run on KNN:

~~~bash
cd /data/tingyup2/projects/AudioLM/LMushra
. /data/tingyup2/projects/AudioLM/env.sh
python -m pytest -q tests/test_audioio.py tests/test_degradations.py tests/test_phase1.py tests/test_pipeline.py
~~~

**104 passed in 6.66 s.** Tests cover STFT identity, filter response/causality, applied SH masks, UN tonal-fixture behavior, QN SNR/additivity, silence/channel handling, bounds, deterministic saved triplets, serialization and source-disjoint splits. They do not prove ODAQ equivalence, detector specificity on arbitrary content, audibility or mono-quality transfer.

All 22 files in the prior scientific-audit hash list matched before this assessment. Final verification compares the source/config/test snapshot and frozen fit/split hashes. The sole new project deliverable is this Markdown report; receipts/logs are ignored outputs. Existing calibration work and corpus documentation are preserved.

## 11. Prioritized implementation plan

| Priority | Work | Smallest justified change |
|---|---|---|
| P0 | Freeze legacy/calibration contracts | Preserve algorithm 1.1, old configs/seeds/hashes and frozen split. Separate companion annotations from strict current schema |
| P0 | Add mono and parameter-matched profiles | New YAML files using existing keys and listed LP/SH/UN grids; no default changes, no QN NMR alias, unspecified parameter tiers |
| P0 | Add transfer-support gate | Separate annotation stage rejects wrong axes/contexts, unsupported ranges and unvalidated mono claims |
| P1 | Resolve QN definition | Author clarification or declared absence; choose verified model, independent mask approximation or direct empirical SNR bridge |
| P1 | Review UN selection | Independent negative controls and separately versioned validated detector; no silent threshold retuning |
| P1 | Define PE cue tolerance | Onset-spreading checks; versioned restriction only if needed, with boundary-artifact validation |
| P2 | Optional mask-shaped QN | Distinct algorithm/schema, mask provenance and achieved-NMR metrics after conventions are specified |
| P2 | Independent mono transfer study | New listeners and diverse held-out sources; three-rater QN curve remains a weak prior |
| P3 | Apply labels/scale | Only after transfer validation, with uncertainty/support flags; training/full generation remain later work |

Future code changes should be confined to annotation/support checks, explicit version dispatch, an optional validated UN detector and a separately specified masking-QN path. LP/SH have no justified immediate DSP rewrite. New paths must preserve the old API/byte-reproducible outputs; never infer version silently from parameter names.

### Decisions for the team

1. Are ODAQ-domain priors with unknown synthetic transfer sufficient for this POC, or are validated synthetic labels required?
2. Which listening context/basis is the target, and can we run an independent mono bridge?
3. Can ODAQ authors supply QN sign/model details and LP/SH/UN operator specifications?
4. Is masking-model QN needed now, or should current SNR QN await independent direct calibration?
5. What incidental onset-spreading tolerance is compatible with the PE holdout claim?
6. What evidence is needed before descriptions call UN-selected regions tonal?
7. Which uncertainty/null fields can the model team consume without treating estimates as human annotations?
8. How will reports distinguish this ODAQ-informed POC from an independent benchmark?

## 12. Primary sources

- [Official ODAQ repository](https://github.com/Fraunhofer-IIS/ODAQ) and [complete release](https://doi.org/10.5281/zenodo.23425817).
- [Original ODAQ, Table 1/§3.2](https://arxiv.org/html/2401.00197#S3.SS2).
- [Stereo extension, Table 1/§2.2–2.4](https://arxiv.org/html/2512.14259#S2.SS2).
- [Author explanation of tonal/noise bandwidth-extension artifacts](https://www.audiolabs-erlangen.de/content/resources/aesCodingTutorial/bwe.html): family context, not executable ODAQ equivalence.
- [GstPEAQ repository](https://github.com/HSU-ANT/gstpeaq), [NMR source](https://github.com/HSU-ANT/gstpeaq/blob/develop/src/movs.c#L793), [license](https://github.com/HSU-ANT/gstpeaq/blob/develop/COPYING). Web develop links inspected 2026-11-11; pin an exact commit before implementation.
- Source paths, condition examples and frozen hashes above support reproducibility. Implementation and perceptual-transfer studies remain proposed.
