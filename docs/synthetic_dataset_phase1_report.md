# DeepMUSHRA: Phase 1 synthetic dataset design and preliminary results

**Experiment date:** 2026-11-02. **Status:** completed small engineering pilot;
perceptual calibration and model evaluation are proposed work. Everything is on
KNN, branch `pt/data`; no new commit or push was made. This report supersedes
neither the external-benchmark audit nor its source-count definitions.

## 1. Research objective and completed work

Test whether controlled signal processing produces reproducible, aligned
reference/degraded/residual examples with truthful processing metadata and
metadata-only description candidates. This establishes implementation behavior,
not human audibility, perceived severity, description usefulness to listeners,
or performance of an audio-language model.

Completed: eight distinct recording excerpts, LP/SH/UN review, an additive
QN-like generator, three settings per effect, 96 degraded pairs, eight identity
controls, source-grouped manifests, two complete generation runs, effect-specific
measurements, temporal probes, 26 PNG figures, and 104 passing automated tests.
No ODAQ audio, excerpts, ratings, comments, or audio analyses entered generation,
parameter choice, captions, calibration, or these signal measurements. No new
ODAQ files were downloaded. PE/TM remain unavailable as generators. No LALM,
quality predictor, listening infrastructure, or stereo-width operator was built.

## 2. Reference material, legality and content coverage

The eight original recordings are from the **MedleyDB portion of MUSDB18-HQ**,
not ODAQ. The official [MUSDB18-HQ record][hq] distributes uncompressed 44.1 kHz
stereo audio. The [SigSep tracklist and license page][musdb] identifies these
tracks as MedleyDB/CC BY-NC-SA; [MedleyDB][medley] specifies CC BY-NC-SA 4.0.
Use is noncommercial research, with attribution and share-alike obligations.
MedleyDB also asks users not to redistribute its audio collection or portions
without contacting the curators. We retain recordings privately on KNN and
commit no audio; any public package needs a separate distribution decision.

Each excerpt is **8 s / 352,800 samples / two channels / native 44,100 Hz**.
Acquisition selects the highest mean-square-energy window among starts at
20, 40 and 60 s, preferring the earlier start on ties. This fixed clean-source
activity rule does not use artifact outputs, ratings, or human judgments.
The raw excerpts are losslessly converted to DOUBLE WAV; the generator applies
one common source gain only when peak headroom requires it.

| Original recording / attribution | Stem / declared content proxy | Excerpt (s) | Nominal split | Reference STFT energy above 7 kHz |
|---|---|---:|---|---:|
| Aimee Norwich - Child | other / tonal_instrument_stem | 60–68 | validation | 0.4017% |
| Alexander Ross - Goodbye Bolero | other / tonal_instrument_stem | 60–68 | train | 0.0131% |
| Auctioneer - Our Future Faces | drums / percussion_stem | 40–48 | train | 3.2134% |
| Celestial Shore - Die For Us | drums / percussion_stem | 60–68 | train | 1.7394% |
| Clara Berry And Wooldog - Air Traffic | vocals / vocal_stem | 20–28 | test | 0.5142% |
| Creepoid - OldTree | vocals / vocal_stem | 60–68 | train | 0.2830% |
| Helado Negro - Mitad Del Mundo | mixture / mixture | 60–68 | train | 0.3585% |
| Steven Clark - Bounty | mixture / mixture | 60–68 | train | 0.3764% |

The two `other` stems are **tonal-instrument content proxies**, not verified
isolated instruments; they may contain several instruments or bleed. Vocals
are singing, not a separate spoken-speech condition. Genre comes from the
upstream tracklist; there are no new human content or cleanliness annotations.
Distinct songs and artists establish recording-level separation, not statistical
independence from a common corpus or a guarantee of pristine mastering.

Source provenance was checked against the already-cached ODAQ attribution
registries solely for **source exclusion**. No selected artist/recording title
matched; ODAQ's neural-subset README traces its sources to the original ODAQ
speech material. See `data/phase1_sources/benchmark_exclusion_receipt.json`.
This provenance check is not acoustic fingerprinting of undocumented derivatives.
The generator never reads that receipt or any ODAQ directory.

The 22,656,664,047-byte upstream ZIP was not downloaded in full. Bounded HTTP
206 reads retrieved its directory and **only eight selected compressed WAV
members**, using 284,277,475 bytes of range traffic in the initial run. Selected
members passed ZIP CRC checks. The whole-archive MD5 was not verified by reading
all bytes: its advertised size/checksum and the tracklist SHA256 are pinned in
the acquisition script. Receipts retain individual excerpt SHA256, archive
member, crop, header, attribution, license, and integrity qualifications.

The pilot is deliberately music-focused. Speech, environmental sound, silence,
very sparse isolated instruments, and speech-over-background scenes require
independent future source pools. Music is a content domain within audio; it is
not covered merely by giving speech waveforms a high sample-rate header.

## 3. Implementations, actual ranges, and time-frequency behavior

Shared analysis: periodic Hann STFT, 2,048-point FFT, 512-sample hop, one-sided
spectrum, centered zero extension and final padding; matching overlap-add ISTFT
trims to the original sample count. At 44.1 kHz, bin spacing is 21.533 Hz,
window length 46.440 ms and hop 11.610 ms. Padding cells remain in declared
TF-coverage denominators. A valid round-trip reconstructs the actual reference
waveforms to **2.22e-16 maximum absolute error**.

### LP: bandwidth limitation

Existing implementation: `buttord`/`ellipord` determines order, then causal
zero-state SOS filtering independently processes each channel. `cutoff_hz`
is a **passband edge**, not a -3 dB frequency. The stopband starts at
`cutoff_hz + transition_hz`. Stored evidence includes SOS coefficients, order,
response arrays and measured response bounds. The boolean mask is a projected
frequency response below -1 dB; it is **not an applied STFT mask** and excludes
phase-only changes.

Accepted ranges: cutoff [1, Nyquist) Hz; transition [1, Nyquist) Hz with their sum
strictly below Nyquist; ripple 0.01–3 dB; attenuation ripple+1 through 120 dB;
Butterworth or elliptic. Orders above 256 are rejected before construction.
Phase 1 uses Butterworth, **5/10/16 kHz**, 1.5 kHz transition, 0.5 dB maximum
passband loss, and 60 dB minimum stopband attenuation. Orders are 28/38/26.

The reference is not shifted or delay-compensated, but LP introduces
frequency-dependent phase/group delay and post-transient ringing. Zero initial
state at the excerpt boundary also creates startup behavior. For the 5 kHz
probe, passband group delay over 100 Hz–5 kHz has median 0.589 ms and maximum
1.292 ms. Causality gives zero signal before an initially silent onset.
It does not make the residual a pure high-frequency removal signal.

### SH: spectral holes

Existing implementation: independently draw a Bernoulli decision for each
eligible frequency band and each nonoverlapping temporal block; apply linked
channel gains and reconstruct. This is a transparent random-bin-band surrogate,
**not lowest-SMR selection or a psychoacoustic bit allocator**. Exact selection
and amplitude-gain arrays are saved. Adjacent selected blocks can merge.

Accepted ranges: start [0, Nyquist) Hz, probability 0–1, nominal band width
1–Nyquist Hz, integer block length 1–100,000 frames, attenuation 0–200 dB or
literal `zero`. Phase 1 holds start **4 kHz**, width **500 Hz**, block length
**4 frames**, and attenuation **80 dB** fixed while sweeping probability
**0.1/0.3/0.7**. Four hops span 46.44 ms; this is a selection-grid block duration,
not a guaranteed audible-event duration. Band edges are quantized to FFT bins.

Retained coefficients keep their phases, but abrupt gain boundaries and centered
analysis/synthesis can ring or spread before/after transients. Reanalysis of
an ISTFT waveform need not recover the modified STFT exactly. Therefore 80 dB
is the applied coefficient gain, not a promise of 80 dB reanalyzed attenuation.

### UN: tonal-detail replacement / harmonic-smearing surrogate

Existing implementation: estimate an RMS envelope from Gaussian-smoothed STFT
power. A shared channel-RMS spectrum selects bands containing a peak above
that envelope. Seeded noise is spectrally shaped, normalized to original
frame/band/channel energy, linearly blended with the original complex spectrum,
then normalized again before ISTFT. Bands have nominal width twice the smoothing
sigma. The detector is an engineering contrast heuristic, not perceptual
masking or guaranteed harmonic identification.

Accepted ranges: crossover [0, Nyquist) Hz, strength 0–1, smoothing sigma
1–Nyquist/2 Hz, threshold 0–60 dB, linked or independent noise. Phase 1 fixes
**7 kHz**, **500 Hz sigma**, **6 dB peak/envelope threshold**, linked noise,
and sweeps strength **0.25/0.5/1.0**. Strength is a complex blend coefficient,
not an exact fraction of waveform energy replaced. Full replacement changes
phase/fine structure; centered windows can spread noise before onsets.
Pre-ISTFT band energy normalization does not ensure exact post-ISTFT energy or
local envelope conservation. Some weak/no-tonal-content inputs can be no-ops;
none of these 24 pilot examples was a no-op.

### QN-like: added signal-shaped noise (new)

The new path retains the original waveform: **degraded = reference + noise**.
It estimates whole-excerpt mean STFT power, smooths it in frequency, designs a
finite minimum-phase FIR approximating its square-root amplitude, filters seeded
white noise causally, and modulates it by a **past-only exponential reference
RMS envelope**. Per-channel scalar normalization produces the requested
waveform reference/noise SNR. The frequency-color estimate is offline, not
an online adaptive masker. Filtering and the zero-state temporal envelope are
causal, so there is no noise before the first nonzero input sample.

Accepted ranges: SNR 0–100 dB; smoothing sigma 1–Nyquist/2 Hz; envelope time
constant 0.1–1000 ms; odd FIR length 17–2049; independent or linked noise.
Phase 1 uses **40/30/20 dB**, **500 Hz**, **5 ms**, **129 taps**, independent
channels. SciPy >=1.14 supports the full-length minimum-phase factorization.
The approximate spectral floor is 1e-6 of normalized amplitude. The short FIR
and global color cannot preserve every instantaneous spectral envelope.
The RMS envelope has a measurable post-offset tail; see Section 5.

This is **neither ODAQ's psychoacoustic NMR implementation nor a literal
quantizer**. UN replaces tonal content; QN adds a noise component without
replacing/filtering the original signal. Additive noise can obscure spectral
peaks, so this algebraic distinction does not prove perceptual independence.
QN evidence retains actual noise samples, FIR coefficients and causal RMS;
its TF support is a thresholded *measurement* of added noise, not a gain mask.

## 4. Experimental results on real recordings

The table reports median [minimum, maximum] across **eight sources**, not
confidence intervals. Settings vary one parameter per effect; defaults above
stay fixed. No claim of equal perceived severity across rows or effects is made.

Primary metrics: LP = degraded/reference stopband STFT energy change (dB),
SH = fraction selected among eligible TF-channel cells, UN = reduction in mean
peak/envelope contrast at reference-detected tonal peak cells (dB),
QN = waveform reference/noise SNR (dB). The common magnitude metric is
`sqrt(sum((abs(D)-abs(R))^2)/sum(abs(R)^2))`. Global residual energy remains
available but is insufficient to characterize these different effects.

| Effect | Swept value (units above) | Primary metric: median [min,max] | Median spectral magnitude error |
|---|---:|---|---:|
| LP | 5000 | -41.3844 [-60.602, -34.3046] | 0.0930632 |
| LP | 10000 | -36.8912 [-58.6854, -24.9535] | 0.0346467 |
| LP | 16000 | -33.8007 [-41.9513, -14.2998] | 0.00853067 |
| SH | 0.1 | 0.0992818 [0.0960502, 0.101277] | 0.0313104 |
| SH | 0.3 | 0.300642 [0.295114, 0.309291] | 0.0596063 |
| SH | 0.7 | 0.698973 [0.691165, 0.712293] | 0.087968 |
| UN | 0.25 | 0.340453 [0.313881, 0.430198] | 0.00939153 |
| UN | 0.5 | 2.27046 [2.0189, 2.82857] | 0.0218885 |
| UN | 1 | 8.08583 [7.56103, 9.66989] | 0.0341486 |
| QN | 20 | 20 [20, 20] | 0.0722436 |
| QN | 30 | 30 [30, 30] | 0.0225251 |
| QN | 40 | 40 [40, 40] | 0.00716652 |

**LP:** direct SOS response measurements meet the requested stopband bounds:
minimum over the 5/10/16 kHz designs is 62.39/61.60/61.78 dB. Full-excerpt
STFT output ratios differ from those steady-state transfer-function bounds.
An explicit boundary check excludes frame centers within 4,096 samples of
either edge; median band changes become **-77.61/-75.55/-74.35 dB**, compared
with full-excerpt **-41.38/-36.89/-33.80 dB**. Thus boundary treatment materially
affects this diagnostic; finite-window STFT ratios are not filter specifications.
All values, including exceptions, are in `lp_boundary_check.json`.

The LP residual is a major caveat: at **16 kHz**, median relative residual
energy is **0.20365** while median magnitude error is **0.00853**; at **5 kHz**,
they are **1.06144** and **0.09306**. Across sources, relative residual energy
can reach **3.00147**. Phase changes can therefore dominate residual-based
features despite limited magnitude loss. This is not evidence of equivalent
perceived degradation. A future decision on causal prefix context, boundary
handling and phase-aware model inputs must precede scale-up. Zero-phase filtering
or centered delay compensation is not an automatic fix because it can pre-ring.

**SH:** realized coverage closely follows requested occupancy. However,
**97.11–100% of analyzed frames** contain at least one selected band across the
24 examples. A 10% eligible-TF probability must not be described as “10% of
frames affected.” Selected reference spectral energy is content-dependent;
at p=0.7 its median is only **0.00868 of total STFT energy**, range
**0.000849–0.04211**. Exact mask occupancy, energy selection and reanalyzed
spectral changes are distinct metadata fields. These checks establish controlled
processing behavior, not perceptual importance of the removed cells.

**UN:** mean contrast at reference tonal peaks falls by about **0.34/2.27/8.09 dB**
at the three strengths. Median selected RMS-envelope relative errors are
**0.0166/0.0538/0.1267**; full-replacement errors range **0.1000–0.1851**.
This supports reduced peak contrast with approximate, not exact, post-ISTFT
envelope preservation. A broad p95 contrast statistic alone is unsuitable for
rare narrow peaks, which is why the reference-peak metric is also retained.

**QN:** every source/channel meets its requested **40/30/20 dB** SNR to floating
precision. Median cosine similarity between Gaussian-smoothed mean noise and
reference PSDs is about **0.966**; across all settings/sources it ranges
**0.9573–0.9863**. This verifies approximate spectral coloring and controlled
noise energy; neither cosine nor SNR is a psychoacoustic masking/audibility score.

### Content dependence

Mean normalized spectral magnitude error for the numerically strongest setting
of each effect (LP 5 kHz, SH p=.7, UN strength=1, QN 20 dB):

| Content proxy (two sources each) | LP | SH | UN | QN |
|---|---:|---:|---:|---:|
| mixture | 0.09932 | 0.10244 | 0.03085 | 0.07077 |
| percussion_stem | 0.19278 | 0.18269 | 0.07620 | 0.07125 |
| tonal_instrument_stem | 0.06107 | 0.05977 | 0.01823 | 0.07394 |
| vocal_stem | 0.07793 | 0.07963 | 0.03611 | 0.07602 |

Percussion has larger LP/SH/UN magnitude changes in these particular excerpts;
their above-7-kHz reference energy is also greater. This is descriptive evidence
from n=2 per proxy, not a general music-versus-vocals finding or audibility ranking.
Above-16-kHz energy spans only **0.000174–0.04834%** of total STFT energy across
sources. A native 44.1-kHz header alone cannot guarantee a useful high-cutoff LP
example. Future source coverage must measure bandwidth and tonal/transient
structure independently of benchmark ratings; retain weak/no-op controls rather
than silently claiming strong changes everywhere.

### Figures and inspectable examples

All paths are relative to the checkout. Generated assets are gitignored:

- `outputs/phase1-pilot/diagnostics/{LP,SH,UN,QN}.png`: standard triplet views.
- `outputs/phase1-pilot/phase1_analysis/{LP,SH,UN,QN}_parameter_metrics.png`:
  per-source parameter curves, family metric plus magnitude error.
- `.../phase1_analysis/content_comparison.png`: family-specific strongest-setting
  metrics, two source dots per category; no pooled perceptual scale.
- `.../phase1_analysis/{effect}_{content_category}_triplet.png`: 16 fixed-rule
  examples covering all four effects and all four content proxies. Each contains
  reference/degraded/residual waveforms and fixed-scale spectrograms for channel 1.
  Selection is by requested parameter then source ID, never the largest measured
  distortion. Stereo is preserved in files, not silently averaged for figures.
- `.../phase1_analysis/per_sample_metrics.csv`, `summary.json`,
  `lp_boundary_check.json`, and `temporal_probes.json`: numerical evidence.

![Parameter-versus-distortion example](../outputs/phase1-pilot/phase1_analysis/UN_parameter_metrics.png)

![Across-content measurements](../outputs/phase1-pilot/phase1_analysis/content_comparison.png)

Figures link to remote ignored artifacts and will not appear in a Git-only clone
until regeneration. They visualize processing, not human annotations.

## 5. Alignment, temporal artifacts, stereo, and the PE holdout

Files preserve sample count, rate, channel order and sample-index origin.
The causal LP phase response changes feature timing even though no file offset
is inserted. A common source gain applies to all variants. There is no clipping,
per-variant normalization, resampling, or channel mixing in LP/SH. Standalone
validation reloads DOUBLE WAV files and checks
`residual == degraded-reference` and reconstruction; the maximum reconstruction
error is **5.55e-17**. All peaks are below the 0.999 rejection threshold;
maximum degraded peaks by family are LP **0.52572**, SH **0.50178**,
UN **0.50122**, QN **0.50849**. Identity residuals are zero.

A separate analytical probe is **not a dataset source or a PE augmentation**:
a one-second 44.1 kHz stereo signal has an abruptly gated 1/11.2-kHz tone mixture
between samples 14,700 and 29,400. Right is 0.7 times left. Each effect uses a
fixed seed 20261102 and its documented strong setting. Pre/post energy is a
fraction of the *whole residual's* energy; extent is the earliest/latest residual
sample exceeding max(residual peak x 1e-4, 1e-15), i.e. a declared engineering
threshold, **not an audibility threshold**.

| Effect | Pre-onset residual energy fraction | Pre-onset extent (ms) | Post-offset fraction | Post-offset extent (ms) |
|---|---:|---:|---:|---:|
| LP | 0.00000% | 0.000 | 0.01923% | 4.104 |
| SH | 0.01247% | 37.279 | 0.03256% | 37.370 |
| UN | 0.38509% | 29.456 | 0.36678% | 28.073 |
| QN | 0.00000% | 0.000 | 1.66526% | 88.435 |

SH and UN have measurable pre-onset spreading from centered windows. Combined
analysis/synthesis support can approach one full 46.44-ms window, not only a
half-window. LP has causal post-ringing. QN has zero pre-onset energy but an
approximately **88-ms** low-level noise tail at this threshold, caused by the
5-ms power-envelope exponential and its square root. These examples do not show
that a listener hears pre-echo, nor quantify spreading for every transient.
The fixed burst is a stress probe, not representative source audio.

**PE/TM are held out as intentional operators; a strict perceptually pure PE
holdout is not established.** Before making that stronger claim, agree whether
incidental temporal smearing is acceptable, or evaluate a separately versioned
short-window/causal/source-gated alternative on independent development material.
No such alternative or PE/TM generator was implemented here. TM (noise-to-tone)
is also distinct from both tonal replacement and additive noise, but a model's
pretraining exposure cannot be ruled out by this synthetic-data policy.

Stereo shape preservation is verified by mono/stereo tests at 44.1/48 kHz,
channel-order/no-crosstalk tests, and silent-channel checks. Spatial invariance
is not claimed. Maximum absolute change in broadband L/R correlation across
24 examples is LP **0.02062**, SH **0.01974**, UN **0.00693**, QN **0.00990**.
Filtering/selection reweights frequency-dependent stereo statistics; linked UN
noise or independent QN noise can change coherence. Correlation is only a coarse
signal diagnostic, not a stereo-perception measure. Stereo width/coherence
augmentation remains an unimplemented proposal pending model input support.

## 6. Metadata and metadata-only language

The complete record below is an **actual QN 30-dB example**, copied byte-for-byte
from the generated JSON into
[`synthetic_dataset_phase1_metadata.example.json`](synthetic_dataset_phase1_metadata.example.json).
Its paths are relative to `outputs/phase1-pilot/`. The record is not abbreviated.

The information boundaries are deliberate:

1. **Exact processing facts:** resolved parameters/seed, source/license/crop,
   common gain, native shape, filter settings, exact applied selections or saved
   additive noise, mask semantics, hashes, algorithm and generator versions.
2. **Measured changes:** waveform energy/RMS/peaks, per-band spectral change,
   TF occupancy, spectral magnitude error, family metrics, channel correlation.
   Selected energy, net energy change, and residual energy are not interchangeable.
3. **Perception:** audibility, severity, quality category, human description and
   provenance stay `null`; status is `unverified`. No MUSHRA targets exist.
   All Phase 1 parameter tiers are `unspecified`, with the schema's explicit
   provisional-parameter status. No level is labeled perceptually subtle/strong.
4. **Text:** technical descriptions state operations; perceptual candidates use
   conditional language and remain `unverified`. No listening observations or
   LLM paraphrases were generated. The pure `describe(artifact,parameters,evidence)`
   interface remains available for a later constrained paraphrasing stage.

Examples of current templates: LP explicitly mentions causal phase changes;
SH labels processing-grid selections; UN labels pre-reconstruction energy
normalization; QN says added noise with a per-channel SNR and disclaims NMR.
These are faithful operation descriptions, not proof that their conditional
“less bright,” “gaps,” “noisier,” or “hiss” candidates match listening experience.
In particular, a broad processing-region projection cannot justify a precise
“most noticeable at 7.6 s” statement. Such timing/attribution needs independent
perceptual evidence or must be labeled an objective measurement only.

<details>
<summary>Complete actual JSON record (click to expand)</summary>

```json
{
  "audio": {
    "degraded": {
      "path": "audio/c84a6c950c4e0a8e812b62e3/degraded.wav",
      "sha256": "eccedb0c34ab7944b26336eb4c467b9e48132951a8af3d1e99a0062967bf01af",
      "subtype": "DOUBLE"
    },
    "reference": {
      "path": "audio/reference/11fd27bdc757c684868d990b3baab6263644d4f5aed4cafa5935934b0acbe8ea.wav",
      "sha256": "11fd27bdc757c684868d990b3baab6263644d4f5aed4cafa5935934b0acbe8ea",
      "subtype": "DOUBLE"
    },
    "residual": {
      "path": "audio/c84a6c950c4e0a8e812b62e3/residual.wav",
      "sha256": "93ee84fe47157cd7b71fe44d54ad4d8d276b84f3e832ad070517a4a97e7b2fb1",
      "subtype": "DOUBLE"
    }
  },
  "degradation": {
    "algorithm": "deepmushra_data.qn",
    "algorithm_version": "1.1",
    "artifact_type": "QN",
    "evidence": {
      "algorithm_version": "1.1",
      "coverage_denominator": "all analyzed time-frequency-channel cells, including boundary padding",
      "envelope_alpha": 0.9954751208601006,
      "mask_kind": "derived_added_noise_stft_support_not_an_applied_gain_mask",
      "no_tonal_replacement": true,
      "noise_waveform_array": "added_noise",
      "perceptual_equivalence_to_odaq": "unverified",
      "phase_policy": "reference unchanged; added noise uses causal minimum-phase FIR and past-only exponential RMS",
      "psychoacoustic_masking_model": null,
      "reference_phase_modified": false,
      "smoothing_definition": "Gaussian standard deviation in Hz",
      "snr_definition": "reference-to-added-noise waveform energy, calibrated independently per channel",
      "spectral_color": "whole-excerpt mean STFT power, Gaussian frequency smoothing, finite FIR approximation",
      "stft": {
        "axis_order": "time,frequency,channel",
        "boundary": "zeros",
        "hop_length": 512,
        "n_fft": 2048,
        "padded": true,
        "scaling": "spectrum",
        "window": "periodic_hann"
      },
      "support_definition": "noise STFT magnitude > max(noise peak STFT magnitude*1e-4,1e-15); centered analysis can project before actual waveform support",
      "temporal_envelope": "sqrt of causal exponential mean reference power; zero state; may trail offsets",
      "transformation_applied": true
    },
    "frequency_regions_hz": [
      [
        0.0,
        22050.0
      ]
    ],
    "mask": {
      "axis_order": "time,frequency,channel",
      "format": "npz",
      "path": "evidence/c84a6c950c4e0a8e812b62e3.npz",
      "selection_array": "selected_mask",
      "sha256": "ee37383b180ff1ea6be4d658c28d8044f00779bfe0585c183d6f9c17142e483a"
    },
    "parameter_severity": {
      "status": "provisional_parameter_based",
      "tier": "unspecified"
    },
    "parameters": {
      "channel_mode": "independent",
      "envelope_ms": 5,
      "fir_taps": 129,
      "smoothing_hz": 500,
      "snr_db": 30
    },
    "random_seed": 7063811228729895671,
    "region_interpretation": "projections of processing selections with STFT window support; not audible-event annotations; see full mask for joint structure",
    "time_regions_s": [
      [
        0.0,
        8.0
      ]
    ]
  },
  "descriptions": {
    "attributes": {
      "artifact": "QN",
      "audibility": "unknown",
      "content_attribution": "unknown",
      "perceived_severity": "unknown"
    },
    "perceptual_candidate": "Additional background noise or hiss may be present, following the signal's spectral color.",
    "perceptual_candidate_status": "unverified",
    "technical": "Signal-shaped noise is added at a 30 dB reference-to-noise energy ratio per channel, using 500 Hz spectral smoothing and a causal 5 ms RMS envelope. The original waveform is retained; this is not a psychoacoustic NMR simulation.",
    "technical_status": "processing_facts",
    "template_version": "1.1"
  },
  "measurements": {
    "affected_frame_ratio": 1.0,
    "affected_tf_ratio": 0.9971317637923123,
    "audibility_interpretation": "none; objective measurements only",
    "degraded_channel_correlation": 0.8901583204557161,
    "degraded_energy": 1767.2829409055855,
    "degraded_peak": 0.42785294812766844,
    "degraded_rms": 0.05004650531283069,
    "measured_change_definition": "magnitude change >=1 dB; floor=max(reference peak STFT magnitude *1e-4,1e-15); all analyzed cells",
    "measured_changed_tf_ratio": 0.24155659877872296,
    "measured_snr_db": 30.0,
    "measurement_grid_cells": 1416550,
    "net_energy_change": 1.105139193169407,
    "normalized_spectral_magnitude_error": 0.022835485539279433,
    "per_channel_snr_db": [
      30.0,
      30.0
    ],
    "reference_channel_correlation": 0.8910112710748099,
    "reference_energy": 1766.177801712416,
    "reference_peak": 0.427978515625,
    "reference_rms": 0.05003085501642021,
    "relative_residual_energy": 0.0009999999999999996,
    "residual_energy": 1.7661778017124155,
    "residual_peak": 0.012716031776478905,
    "residual_rms": 0.0015821145513754869,
    "rms_change_db": 0.0027166333741282644,
    "smoothed_noise_reference_psd_cosine": 0.9661114303589025,
    "spectral_energy_change_db_by_band": {
      "0-4000Hz": 0.002719430545808307,
      "10000-22051Hz": 0.005375319516986962,
      "4000-10000Hz": 0.005126446720578997
    },
    "stored_noise_residual_max_abs_error": 2.7159264420761886e-17
  },
  "perceptual_annotation": {
    "audibility": null,
    "description_attributes": null,
    "natural_language_description": null,
    "perceived_severity": null,
    "provenance": null,
    "quality_category": null,
    "status": "unverified"
  },
  "provenance": {
    "configuration_sha256": "758f3609248042ba89718c84d7175df1c6a0ac4292a655da8f9030d23340847d",
    "generator_source_sha256": "8b42e04fd0721bb599460e3eed37e5b682da2b6746defaf604178da939afc5b3",
    "generator_version": "0.2.0",
    "git_dirty": true,
    "git_revision": "11d1f0d4cbed3a2e1bab0f46db9d6c2aef36c68a",
    "master_seed": 20261102
  },
  "sample_id": "c84a6c950c4e0a8e812b62e3",
  "schema_version": "1.0",
  "source": {
    "channels": 2,
    "content_category": "tonal_instrument_stem",
    "content_category_provenance": "source_manifest",
    "declared_source_id": "musdb18hq:Aimee Norwich - Child",
    "duration_s": 8.0,
    "is_functional_test_signal": false,
    "original_peak": 0.427978515625,
    "sample_count": 352800,
    "sample_rate": 44100,
    "shared_source_gain": 1.0,
    "source_checksum_sha256": "11fd27bdc757c684868d990b3baab6263644d4f5aed4cafa5935934b0acbe8ea",
    "source_file": "reference_01.wav",
    "source_id": "musdb18hq:Aimee Norwich - Child",
    "source_provenance": {
      "archive_member": "train/Aimee Norwich - Child/other.wav",
      "archive_member_crc32": "68de40cf",
      "artist_and_track": "Aimee Norwich - Child",
      "category_basis": "MUSDB stem designation; other is a multi-instrument tonal-content proxy, not a verified solo instrument",
      "dataset": "MUSDB18-HQ / MedleyDB",
      "excerpt_duration_s": 8,
      "excerpt_start_s": 60,
      "full_member_crc_verified": true,
      "genre": "Singer/Songwriter",
      "integrity_note": "Selected compressed member fully read and CRC verified; whole-archive MD5 not verified",
      "license": "CC BY-NC-SA 4.0",
      "license_evidence": "https://sigsep.github.io/datasets/musdb.html",
      "license_url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
      "modifications": "Excerpting and lossless DOUBLE WAV conversion; generator records any subsequent shared gain",
      "original_header": {
        "channels": 2,
        "sample_count": 8346782,
        "sample_rate": 44100,
        "subtype": "PCM_16"
      },
      "perceptual_cleanliness": "unverified; uncompressed release, not a human-quality certification",
      "permitted_use": "Noncommercial research; retain attribution and share-alike obligations; no audio in Git",
      "record_url": "https://zenodo.org/records/3338373",
      "selection_rule": "Highest mean-square energy of fixed 8-second windows starting at 20,40,60 s; ties prefer earlier",
      "stem": "other"
    },
    "split": "validation"
  }
}
```

</details>

## 7. Sampling, splitting, and scaling plan

**Completed:** `configs/phase1.yaml`, seed **20261102**, explicit levels above;
12 variants plus one identity per recording. Stochastic seeds hash master seed,
source ID/checksum, artifact, variant and parameter mapping. The same setting
on the same source is reproducible; different setting variants use different
noise/mask realizations. Curves therefore include stochastic variation as well
as parameter effects. This is not a multi-seed variance study or severity fit.

Sources are grouped before recipes. Related stems/excerpts/versions must share
one recording identity. Exact-file aliases are joined transitively. Hash-ordered
whole-group allocation gives **6/1/1 recordings** and **78/13/13 rows** for nominal
train/validation/test. Splits have no source overlap. These small partitions are
engineering demonstrations, not balanced content evaluations; the report examines
them all. Treat these pilot sources as explored development material, and create
fresh untouched final synthetic test groups before making generalization claims.

**Proposed only:** broaden independently licensed source coverage, including
native high-band instruments, clean spoken speech, environmental sounds, sparse
transients, and mixed scenes. Group by recording/production and, where feasible,
performer/session before extracting clips. Separate source/license manifests from
variant manifests; freeze source hashes, exact package environment and DSP config.
Stratify content and active high-band/tonal/transient coverage without deriving
thresholds from ODAQ. Retain identities and low-content/no-op cases explicitly.

For a scaling study, first repeat multiple seeds per source/setting and quantify
variance; sweep one factor at a time before jointly sampling parameters. Use
bounded uniform/choice/log-uniform recipes already supported by the pipeline,
with natural units and explicit seed receipts. Do not combine effects until
single-effect descriptions/localization are validated. Select counts and
storage format with the model team; do not expand this 104-item pilot into full
training by simply multiplying parameter combinations.

## 8. Proposed independent perceptual severity calibration

No calibration or listening study has been performed. Proposed sequence:

1. Resolve LP phase/startup, SH/UN pre-onset confounds, and QN offset tails first.
   Freeze a candidate algorithm version and engineering constraints using
   recordings outside ODAQ. Do not silently relabel the current pilot as perceptually
   verified after changing its operator.
2. Recruit a small initial panel, e.g. 5–8 listeners, with an independent licensed
   development pool spanning roughly 12–20 new recording groups and content types.
   The sample size and expertise are discussion items, not a power calculation.
   Use playback supporting the intended native bandwidth and headphones suitable
   for the task; record hearing/playback context where appropriate.
3. Use randomized, blinded reference-based comparisons with identities/repeats.
   Collect audibility separately from perceived difference/severity and quality;
   allow “no audible difference/uncertain.” Do not show artifact names or template
   candidates before free artifact/timing descriptions. Include discrimination
   tasks for uncertain near-threshold changes if needed.
4. Check rating/repeat reliability and content interactions. Fit any monotonic
   severity mapping only on this development pool, retain uncertainty, and do not
   equate equal SNR/cutoff/coverage with equal subjective severity. Use a standardized
   quality protocol if actual MUSHRA labels are desired; do not manufacture them
   from these parameter settings or assume five equal-width quality bins.
5. Separately assess candidate-description correctness and omissions, especially
   timing, frequencies, source attribution and unjustified certainty. Store raters,
   protocol, approval/consent requirements, provenance and confidence when genuine
   annotations become available. Freeze mappings and evaluate on new source groups.
   ODAQ remains an external benchmark, never a calibration resource.

This is a study proposal, not implemented human-test infrastructure or an assertion
that human ratings will validate the current templates.

## 9. Reproducibility, tests and exact locations

Host: `tingyup2@knn.cs.illinois.edu`.
Checkout: `/data/tingyup2/projects/AudioLM/LMushra/`.
Environment: `/data/tingyup2/projects/AudioLM/envs/deepmushra-py310/`.
Source `/data/tingyup2/projects/AudioLM/env.sh` before execution; temporary files
and caches remain under `/data`. The Mac contains only small context notes.

Generator **0.2.0**, algorithm/template **1.1**, metadata schema **1.0** (same
top-level layout; QN extends the allowed artifact enumeration). The numerical
LP/SH/UN paths were preserved. Git base is `11d1f0d`, with uncommitted changes;
the exact generator source SHA256 is:
`8b42e04fd0721bb599460e3eed37e5b682da2b6746defaf604178da939afc5b3`.
Config SHA256: `758f3609248042ba89718c84d7175df1c6a0ac4292a655da8f9030d23340847d`.
Python 3.10.12, NumPy 2.2.4, SciPy 1.15.2, SoundFile 0.14.0/libsndfile 1.2.2,
PyYAML 6.0.3, Matplotlib 3.10.1, pytest 9.2.0. Pinned remote dependencies are in
`requirements-phase1-knn.txt`; no GPU is required.

```bash
ssh tingyup2@knn.cs.illinois.edu
cd /data/tingyup2/projects/AudioLM/LMushra
source /data/tingyup2/projects/AudioLM/env.sh
# Existing compatible remote environment:
python -m pip install --no-deps --no-build-isolation -e .
python -m pytest -q
# Fresh destinations required; completed outputs are never overwritten.
python scripts/prepare_phase1_sources.py --output data/phase1_sources
python -m deepmushra_data generate --config configs/phase1.yaml \
  --manifest data/phase1_sources/sources.jsonl --output outputs/phase1-pilot
python -m deepmushra_data generate --config configs/phase1.yaml \
  --manifest data/phase1_sources/sources.jsonl --output outputs/phase1-repeat --no-diagnostics
python scripts/analyze_phase1.py --dataset outputs/phase1-pilot --repeat outputs/phase1-repeat
python -m deepmushra_data validate --dataset outputs/phase1-pilot
```

Acquisition refuses an already completed source manifest. Reuse the existing
manifest to regenerate audio or choose a new acquisition destination. For a new
remote environment install `requirements-phase1-knn.txt`, then the checkout with
`python -m pip install --no-deps -e .`. Do not execute the historical macOS env
archived on KNN.

**Completed checks:** 104 automated tests passed (6.59 s in the recorded run).
Tests cover 44.1/48 kHz mono/stereo lengths, STFT round-trip, actual LP response
and causality, exact SH masks/runs, UN tonality/envelope behavior, QN target SNR,
noise-vs-replacement distinction, silent-channel isolation, finite values,
clipping rejection rather than clamping, source grouping, metadata serialization,
provenance retention, corruption detection, deterministic bytes and CLI paths.
Both real-audio runs validate: 104 rows each, eight groups, no errors, maximum
residual reconstruction error 5.55e-17. All **428 compared files** match byte for
byte: unique WAVs, NPZ evidence, per-sample JSON, combined metadata/manifest,
resolved config and run receipt. Figures are excluded from the byte contract.
This guarantees the tested environment/inputs, not bit identity across arbitrary
SciPy/libsndfile versions or hardware.

Inspectable files:

| Artifact | Remote checkout-relative path |
|---|---|
| Clean excerpts, source manifest, licenses, acquisition/exclusion receipts | `data/phase1_sources/` |
| Raw selected source members, not all MUSDB | `data/phase1_sources/upstream_stems/` |
| Main WAV triplets, NPZ, JSON/JSONL and training interface | `outputs/phase1-pilot/` |
| Independent repeat | `outputs/phase1-repeat/` |
| Family curves, content comparisons, 16 triplet figures and probe evidence | `outputs/phase1-pilot/phase1_analysis/` |
| Technical/candidate text and source-grouped paths | `outputs/phase1-pilot/manifest.jsonl`, `manifests/` |
| Generation, repeat, analysis, installation and test logs | `outputs/phase1_logs/` |
| Complete example record | `docs/synthetic_dataset_phase1_metadata.example.json` |

Module map: `degradations.py` operators; `stft.py` shared transforms;
`pipeline.py` saved triplets and manifests; `sources.py` source policy/grouping;
`metadata.py` metrics/schema; `descriptions.py` text; `validation.py` independent
integrity checks; `diagnostics.py` standard plots; `scripts/prepare_phase1_sources.py`
selective acquisition; `scripts/analyze_phase1.py` research measurements/figures;
`tests/test_phase1.py` new behavior checks. Existing audit documentation and
unrelated model/submodule code were not modified.

## 10. Limitations and exact team decisions before scale-up

Completed engineering control is stronger than demonstrated perceptual validity.
The pilot has only eight music recordings, one realization per setting, no
manual listening, no spoken/environmental source pool and uneven small splits.
High-band energy can be tiny. Automatic tonality detection, phase/startup,
STFT inconsistency, temporal spreading, QN tails and stereo side effects are
exposed limitations. Candidate language is generic and unverified. The NC/share-
alike source choice limits downstream distribution/use decisions.

**Model-training team:**

1. What exact waveform sample rate, frontend bandwidth, clipping/normalization,
   duration and stereo-channel representation will reach the encoder? Can it
   retain the >12–16 kHz distinctions, or would frontend resampling erase them?
2. Will all three tracks be accepted with explicit reference/degraded/residual
   roles? Should the phase-heavy LP residual be used as is, given separate level
   normalization, or accompanied by a phase-aware representation? Agree on a
   policy before creating new exports or altering the residual definition.
3. Is WAV DOUBLE supported, or is a versioned float32 export required with
   residuals recomputed from its saved waveforms? Confirm manifest fields and
   whether metadata is supervision only, never an input answer leak.
4. Should candidate perceptual text remain separate from technical operation
   targets? What uncertainty/“no audible difference” outputs and unseen-artifact
   vocabulary must the model support? Do not train a fabricated quality category.
5. Does the architecture preserve stereo sufficiently to justify a later spatial
   family? Until confirmed, stereo width/coherence augmentation remains unapproved.

**Evaluation team:**

6. Does PE holdout mean no intentional PE operator, or no incidental pre-onset
   smearing? The latter requires revising/versioning SH/UN, then new independent
   probes and perceptual checks. What tests/criteria will define that boundary?
7. How will description correctness, omissions, localization and uncertainty be
   scored without treating synthetic masks, scalar MUSHRA or optional ODAQ comments
   as exact audible-caption ground truth? Which source-disjoint external subsets
   and repeat/anchor policies are frozen before any model comparison?
8. How are LP/QN implementation differences versus ODAQ reported? Keep ODAQ audio,
   ratings, comments and prior audio analyses out of all synthesis/calibration;
   do not tune these pilot strengths to external scores.

**Joint data/study decisions:**

9. Are noncommercial/share-alike music sources acceptable for planned training and
   publication, and should a less restrictive corpus replace them before release?
   Which independent speech/environment/solo-instrument sources fill the gaps?
10. Which phase/boundary policy and QN offset-envelope duration should be studied,
    and what independent listening-study protocol/budget supports genuine severity
    calibration? Keep the present exploratory sources out of future untouched tests.
11. Approve the source/artist grouping, output contract, multi-seed study and
    evidence-based description review before choosing full training volume.

The next research gate is resolving these input/holdout/annotation decisions
and validating candidate descriptions with independent listening, not scaling
this parameter sweep or fitting it to ODAQ.

[hq]: https://zenodo.org/records/3338373
[musdb]: https://sigsep.github.io/datasets/musdb.html
[medley]: https://medleydb.weebly.com/downloads.html
