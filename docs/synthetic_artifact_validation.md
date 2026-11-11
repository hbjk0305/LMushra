# Synthetic artifact implementation and scientific validation audit

## 1. Executive summary

The current code supports aligned **44,100 Hz mono** reference/degraded/residual
generation. The four operators have distinguishable mathematical behavior and
useful objective controls within tested settings. Several limitations require
decisions before large-scale perceptual supervision.

| Artifact | Implementation valid? | Same broad family as ODAQ? | Known limitations | Recommended action |
|---|---|---|---|---|
| LP | Yes for specified causal filter design and waveform contract | Yes, with a different unverified filter implementation | Phase dominates many residuals; startup and post-ringing; residual energy is often nonmonotonic | Resolve phase/reference-context policy and caption semantics before scale-up |
| SH | Yes for Bernoulli block masks and matching overlap-add reconstruction | Yes, configurable attenuation generalizes ODAQ's reported zeroing | Pre-onset spreading, STFT inconsistency, frequency/time grid quantization, content-dependent energy removal | Resolve PE holdout criterion; retain actual masks and measured output changes |
| UN | Conditional validity as a tonal-band replacement surrogate | Partial model of ODAQ tonal-to-noise substitution | Stochastic peaks in noise trigger replacement; envelope error; band and threshold dependence; pre-onset spreading | Review tonal detector and negative controls before producing tonal-replacement labels at scale |
| QN | Yes as global-color additive noise with exact waveform SNR | Partial model of ODAQ signal-shaped additive QN | Whole-clip color lacks local spectral tracking; offset tails; no psychoacoustic masking threshold | Decide whether global-color surrogate meets the task; constrain unsupported parameter combinations |

These are engineering conclusions. Audibility, perceived severity, and perceptual
independence require listening evidence. All tests and measurements here use
analytical fixtures or independent recordings. ODAQ papers provide mechanism
descriptions only. No ODAQ audio, scores or comments enter these experiments.

Completed work comprises **1,134 main conditions**, **44 secondary parameter
conditions**, **10 LP design/impulse-response checks**, **6 window-ablation
conditions**, a matched-energy additive-noise comparison, and a **104-triplet
mono dataset through the normal generation entry point**. The current unit suite
passes **104 tests in 7.07 s**. Generators, existing tests and existing
configurations retain their pre-audit file hashes.

## 2. Code and processing contract reviewed

Directly reviewed source includes [degradations.py](../src/deepmushra_data/degradations.py),
[stft.py](../src/deepmushra_data/stft.py), [pipeline.py](../src/deepmushra_data/pipeline.py),
[metadata.py](../src/deepmushra_data/metadata.py), [sources.py](../src/deepmushra_data/sources.py),
[config.py](../src/deepmushra_data/config.py), [audioio.py](../src/deepmushra_data/audioio.py),
the three existing YAML configurations and all four existing test modules.
Reviewed file SHA256 values are retained in the output directory.

Production version is 0.2.0, algorithm 1.1. Operators accept float64 arrays with
shape [samples, channels], channels one or two. A mono training waveform must
enter this API as [N,1]. The generator validates source sample rates, channels,
duration, finite samples and source amplitude. It preserves channel count,
sample count and the source sample grid. Existing configs allow 44.1/48 kHz and
mono/stereo. The audit uses a new output-local config restricted to 44.1 kHz mono.

The pipeline applies one source gain g=min(1, source_peak_limit/source_peak).
It applies that same reference to every variant. Each degraded and residual
peak is checked against output_peak_limit; excessive peaks abort publication.
Operators themselves can return peaks above full scale, so callers must retain
the pipeline's headroom checks. No automatic per-variant peak/loudness
normalization occurs.

Saved signals are lossless DOUBLE WAV. Residuals are calculated after reloading
both saved inputs, e=d−r. The optional WAV PEAK timestamp is canonicalized for
deterministic bytes. LP has frequency-dependent signal delay despite identical
file origins. File alignment does not remove filter phase.

Shared STFT uses a periodic Hann window with N=2048, hop=512, one-sided spectrum
scaling, centered zero extension and final padding. Frequency spacing is
21.533 Hz, window length 46.440 ms and hop 11.610 ms at 44.1 kHz. The paired
ISTFT trims to original length. NOLA is checked. A modified spectrum need not
be STFT-consistent after overlap-add. STFT round-trip on the audit sources
has maximum absolute error **1.6653e-16**.

### LP mathematics and actual accepted ranges

For each channel, d[n]=sum_k h[k]r[n−k], implemented with zero-state
scipy.signal.sosfilt. Butterworth/elliptic design order is obtained from the
passband and stopband requirements. The passband edge is cutoff_hz, the stopband
edge is cutoff_hz+transition_hz. The configured cutoff is distinct from the
filter's −3 dB frequency. Filter order is limited to 256 before SOS construction.

Accepted cutoff is [1,22050) Hz and transition [1,22050) Hz, with their sum
strictly below Nyquist. Passband ripple/loss spans 0.01–3 dB; requested stopband
attenuation spans ripple+1 through 120 dB. Both Butterworth and elliptic designs
are accepted. The audit tests 5/7/10/13/16 kHz, 1500 Hz transition, 0.5 dB
passband loss and 60 dB attenuation. LP has no stochastic operations.

Evidence contains SOS coefficients, filter order, dense magnitude response and
measured design bounds. Its TF selection array projects frequencies with
attenuation exceeding 1 dB. This projection omits phase changes and is labeled
accordingly.

### SH mathematics and actual accepted ranges

Let R[t,f] be the reference STFT. For each eligible frequency band b and
nonoverlapping run block j, draw B[j,b]~Bernoulli(p). Expand the decision over
run_frames frames and that band's frequency bins. With selected mask M and
a=10^(−attenuation_db/20), set D=R·[1−(1−a)M], then apply ISTFT.
The literal zero attenuation option sets a=0. Channel selections are linked.

Accepted start_hz is [0,22050), probability [0,1], band width [1,22050] Hz,
integer run_frames 1–100000, and attenuation 0–200 dB or zero. Audited primary
probabilities are 0/.1/.3/.5/.7/1, with start 4 kHz, width 500 Hz, run four frames,
80 dB attenuation. Secondary probes vary attenuation through 0/6/20/40/80 dB
and zero, runs 1/2/4/8/16, and widths 1/125/500/2000 Hz.

The seed drives NumPy default_rng. Fixed seed, source and grid give nested masks
as probability increases. Changing run length or band width changes the number
and arrangement of random decisions. Adjacent selected blocks can merge.
Selection does not use signal-to-mask ratio. Sub-bin band widths collapse to
FFT-bin selections. Centered masking can
produce oscillatory leakage and new temporal variation around transients.

### UN mathematics and actual accepted ranges

For Z=STFT(r), estimate E=sqrt(G_sigma*|Z|²), smoothing along frequency.
The shared channel-RMS spectrum supplies a peak indicator where magnitude
exceeds its smoothed envelope by tonal_threshold_db and a relative floor.
Bands above crossover_hz containing any qualifying peak are selected.

A seeded white-noise STFT W is shaped as E·W/sqrt(G_sigma*|W|²). For every
selected frame/band/channel, scale its energy to the reference band energy.
Blend V=(1−strength)Z+strength·W_shaped, renormalize V to the original
band energy, replace the selected coefficients, and synthesize. At strength
one the original coefficients in selected cells have zero blend weight.
Overlap-add and unselected leakage can leave residual tonal projection.

Accepted crossover is [0,22050) Hz, strength [0,1], smoothing 1–11025 Hz,
threshold 0–60 dB, and linked/independent noise. The frequency sigma used by the
code is max(smoothing_hz/df,0.5) bins. Consequently, requested smoothing below
about 10.77 Hz cannot attain that nominal resolution at N=2048. Band width is
twice requested smoothing. This can give unexpectedly narrow selections when
the requested smoothing and effective sigma differ.

The primary audit fixes crossover 7 kHz, smoothing 500 Hz, threshold 6 dB and
sweeps strength 0/.25/.5/.75/1. Secondary probes vary crossover 3/7/10.5/16 kHz,
smoothing 1/125/250/500/1000 Hz and threshold 3/6/12/20 dB. Phase replacement and
centered windows can spread noise around transients. Spectral-band energy
normalization occurs before ISTFT, so waveform energy and envelope are approximate.

### QN mathematics and actual accepted ranges

Let C[f] be Gaussian-smoothed mean reference STFT power over the whole excerpt.
A finite FIR approximates sqrt(C), after normalization and a 1e-6 amplitude
floor. A homomorphic full-length minimum-phase conversion produces h.
With seeded white noise w and alpha=exp(−1/(fs·tau)), the causal RMS envelope is

a[n]=sqrt((1−alpha)·sum_{k>=0} alpha^k r[n−k]²).

Form n0[n]=(h*w)[n]a[n], with zero initial filter/envelope state. Set
n=n0·sqrt(E_r·10^(−SNR/10)/E_n0), then d=r+n. Silence produces zero added noise.
The target ratio is normalized independently per channel.

Accepted SNR is 0–100 dB, smoothing 1–11025 Hz, envelope 0.1–1000 ms, odd FIR
length 17–2049 and linked/independent noise. Sigma has the same half-bin lower
bound as UN. The primary audit uses 50/40/30/20/10 dB, 500 Hz, 5 ms, 129 taps.
Secondary probes cover envelope .1/1/5/20/100 ms, taps 17/129/513 and smoothing
1/125/500/1000 Hz.

Only noise is filtered. The reference component is retained exactly in the
additive construction. There is zero initial noise before an initially silent
input starts, although spectral-color estimation uses the whole excerpt.
The exponential RMS leaves noise after offsets and during later gaps.
Evidence saves added noise, FIR coefficients and RMS envelope. Its thresholded
noise-STFT support is derived evidence; it is not an applied removal mask.

## 3. Comparison with ODAQ and scientific interpretation

| Artifact | Published ODAQ mechanism and controls | Current relationship |
|---|---|---|
| LP | Bandwidth limitation generated as MUSHRA low-pass anchors; original nominal frequencies 5/9/10.5/12/15 kHz | Same family, different filter specification. Exact anchor filter/phase equivalence has not been established |
| SH | Bands quantized to zero with controlled hole probability; original 70/50/30/20/10%, with MS processing; stereo extension compares LR/MS | Same family with explicit block/band surrogate and optional finite attenuation. Exact ODAQ transform, masks and temporal schedules are unverified |
| UN | Tonal components substituted by noise under their spectral envelope; crossover 3/5/7/9/10.5 kHz | Partial approximation through threshold-selected bands, Gaussian power envelopes and complex blending |
| QN | Stereo extension adds random noise controlled by frequency-dependent noise-to-mask ratio, with LR/MS variants | Partial approximation of signal-shaped additive noise through global color and waveform SNR |

The original paper's Section 3.2 defines LP/SH/UN and their controls. The stereo
paper's Section 2.2 specifies additive noise to avoid quantization-induced holes.
The collection paper locates these families within the larger release. Our
comparison uses those descriptions and the existing audit, without measuring
ODAQ waveforms or opening ratings for this task. [Original ODAQ][original]
[stereo extension][stereo] [collection][collection]

SNR=10 log10(E_reference/E_noise) controls noise relative to total signal energy.
NMR relates noise to a frequency-dependent psychoacoustic masking threshold.
No masking threshold is calculated by our QN path, so an SNR setting cannot be
assigned an ODAQ NMR value or quality level from these experiments. The stereo
paper lists NMR values 0/6/12/18/24 dB; conversion to our SNR, including the exact
generator's convention, is unverified. [Stereo extension][stereo]

No operator is claimed as a faithful reproduction of the exact ODAQ generator.
The same broad family does not imply matched perceptual severity or matched
waveforms. Stereo variants can also produce spatial effects that a mono model
cannot represent. Our audit concerns the mono signal mechanism.

## 4. Experimental setup and reproduction

KNN checkout is /data/tingyup2/projects/AudioLM/LMushra. Outputs are isolated in
`outputs/artifact-validation/`. Production source/test/config hashes were
captured before experimentation. Python is 3.10.12 with NumPy 2.2.4,
SciPy 1.15.2, SoundFile 0.14.0 and Matplotlib 3.10.1.

Ten independent analytical fixtures comprise 1 kHz and 11.2 kHz sine waves,
400 Hz harmonic series through 18 kHz, white noise, pink noise, impulse,
an abruptly gated two-tone burst, decaying broadband transient train,
sequential 1/11.2 kHz tone bursts with an intervening gap, and silence.
Random fixture seed is 732. Analytical sources last one second and have peak
0.2 where nonzero. They are functional diagnostic signals.

Eight legally usable MedleyDB recordings from the previously acquired MUSDB18-HQ
sources supply two instrument stems, two drum stems, two sung-vocal stems and
two mixtures. They carry CC BY-NC-SA 4.0 provenance. We use the first four seconds
of each independent eight-second excerpt, average channels before processing,
and apply one common gain capped at peak .25. No resampling occurs.
Original source hashes, crop, mono conversion and gain are retained.
The source corpus labels the instrument recordings with guitar/piano and
other tonal instruments. These are multi-instrument other stems; frame-level
instrument activity and recording cleanliness were not human-annotated.
Spoken speech remains outside this audit's recorded-source coverage.
[Source record][musdb] [source licensing][license]

Every source receives all primary settings with matched seeds 901/902/903.
LP is deterministic, so its three seeds repeat the same result. Stochastic
operators share random draws across settings within a source/seed for controlled
comparisons. The production pipeline hashes parameters into its seed, so its
usual variants also vary the random realization. Our matched-seed monotonicity
results apply to this controlled design.

Reproduce on KNN in a fresh audit output directory:

~~~bash
cd /data/tingyup2/projects/AudioLM/LMushra
source /data/tingyup2/projects/AudioLM/env.sh
python -m pytest -q
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/validate_synthetic_artifacts.py \
  --output outputs/artifact-validation-repeat
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/audit_parameter_probes.py \
  --output outputs/artifact-validation-repeat
~~~

The scripts import the existing production functions and use the independent
source manifest at `data/phase1_sources/sources.jsonl`. The main audit writes its
configuration, source manifest, 1,134 measurements, saved examples and evidence,
monotonicity classifications, response checks and mono pipeline outputs.
The secondary script writes 44 parameter probes and additional figures.
Inputs and settings are fixed independently of ODAQ ratings.

## 5. Signal-level results

### LP frequency response, phase and ringing

| Design | Passband edge (Hz) | Order | Loss at edge (dB) | First −3 dB bin (Hz) | Minimum stopband attenuation (dB) | Median passband delay (ms) |
|---|---:|---:|---:|---:|---:|---:|
| butterworth | 5000 | 28 | 0.500 | 5174.70 | 62.394 | 0.589 |
| butterworth | 7000 | 34 | 0.500 | 7184.01 | 61.747 | 0.504 |
| butterworth | 10000 | 38 | 0.500 | 10192.61 | 61.596 | 0.376 |
| butterworth | 13000 | 35 | 0.500 | 13201.87 | 61.300 | 0.243 |
| butterworth | 16000 | 26 | 0.500 | 16212.48 | 61.784 | 0.121 |
| elliptic | 5000 | 7 | 0.500 | 5074.43 | 60.000 | 0.178 |
| elliptic | 7000 | 7 | 0.500 | 7095.19 | 60.000 | 0.122 |
| elliptic | 10000 | 7 | 0.500 | 10111.86 | 60.000 | 0.077 |
| elliptic | 13000 | 7 | 0.500 | 13107.66 | 60.000 | 0.050 |
| elliptic | 16000 | 7 | 0.500 | 16085.30 | 60.000 | 0.032 |

Every tested design meets its requested 0.5 dB passband and 60 dB stopband
specification. Impulse FFT versus SOS response differs by at most 6.56e-14.
The −3 dB frequencies are above the declared passband edges, as expected from
the definition. Butterworth passband delay is frequency-dependent; the 5 kHz
case has median .589 ms and maximum 1.292 ms over 100 Hz–cutoff.

At 5 kHz, the impulse's post-offset residual extends **4.671 ms** and the gated
tone's post-offset residual **4.104 ms**, using the declared relative −80 dB
amplitude threshold. Both have exactly zero pre-onset residual. These durations
establish causal post-ringing; they do not establish whether listeners hear it.

For real mono excerpts at 16 kHz cutoff, median magnitude error is **.00806**
but relative residual energy is **.15989**. Median fraction of residual STFT
energy below that cutoff is **.99937**. At 5 kHz the magnitude error is **.08616**
and residual energy **.93181**, with source maxima reaching **3.04749**.
Consequently, a caption or model treating the LP residual solely as removed
high-frequency energy would be inaccurate.

![LP response and delay](../outputs/artifact-validation/figures/LP_response_phase.png)

### SH coverage, removal, consistency and transients

For real excerpts, median eligible coverage is .10457/.30490/.50773/.70194/1.0
at probabilities .1/.3/.5/.7/1. Median net waveform energy removed is
.00177/.00479/.00726/.01007/.01359. At probability one, source removal ranges
from **.000899 to .05592**. Selecting an energetic or a weak high band makes a
large difference even at equal mask occupancy.

Applied gain masks reconstruct the returned waveform with zero maximum
difference in all tested SH conditions. Reanalyzed spectra differ from the
modified coefficients; at p=.5 real-source relative complex STFT consistency
error ranges **.00583–.04992**. Low-energy surviving spectra can give larger
relative errors, including **.712** on an almost removed high-frequency sine.
This is the expected distinction between applying an STFT mask and obtaining a
consistent STFT after synthesis.

On white noise at p=.3, increasing attenuation 0→6→20→40→80 dB→zero increases
removed energy from 0 through .20612/.28651/.29410/.29470/.29470.
Increasing temporal run length changes temporal structure and realization, and
does not supply a universal scalar-strength ordering. Sub-bin width requests
become single-bin selections. Fast mask changes and sharp frequency masks can
introduce ringing and transient variation; waveform sample-step measurements
are recorded as engineering diagnostics, with no listening interpretation.

The impulse at p=1 has **22.971 ms** pre-onset and post-offset support and
9.04% of its residual energy before the onset. Even a constant high-band
suppression mask can pre-ring through the centered transform.

### UN replacement, envelope behavior and noise controls

On the 11.2 kHz sine at strength one, retained sinusoid amplitude is **.05420**
of reference. QN at 20 dB retains **.99778**. A generic high-band additive-noise
control with the **same residual energy as UN** retains **1.00820**. The
mathematical replacement mechanism and measured tonal retention support a
distinction from generic additive noise.

Within a fixed 11–12 kHz band, mean-power spectral flatness changes from
**3.86e-7** for the reference to **.92088** for UN. QN at 20 dB gives **.00912**,
and the matched-error additive control **.16752**. A broad 7–20 kHz flatness
statistic on the pure tone can stay tiny or even decrease because UN replaces
only a selected narrow band while the remainder stays near the numerical
floor. The report retains both measurements to expose metric sensitivity.

For real excerpts, median reference-peak contrast reductions at strengths
.25/.5/.75/1 are **.356/2.407/6.366/8.337 dB**. Median selected-envelope relative
errors are **.01685/.05110/.09052/.11865**. Full-strength source/seed errors span
**.0912–.1933**. This supports approximate envelope preservation.

A significant limitation appears on white noise at default 6 dB threshold:
**31.97% of all analyzed TF cells** are selected. The output changes by relative
residual energy **.52031**, and loses **15.56%** of waveform energy, although
broad high-band flatness stays approximately .99. A stochastic spectral peak
does not establish a persistent tonal component. At 12/20 dB threshold, this
white-noise fixture becomes an identity; at 20 dB the pure-tone fixture also
becomes an identity. Threshold adjustment therefore needs independent negative
and positive controls, not a blanket change based on this one fixture.
At smoothing 1 Hz the harmonic fixture receives no replacement.

![Tone retention](../outputs/artifact-validation/figures/UN_vs_addition.png)

![Local spectral structure](../outputs/artifact-validation/figures/UN_local_spectral_structure.png)

### QN addition, SNR, spectral shaping and localization

The main sweep meets requested 50/40/30/20/10 dB SNR within 1e-10 dB for every
nonzero source/seed condition. Recorded noise agrees with d−r within 1e-15.
Real-source smoothed noise/reference mean-PSD cosine spans **.95493–.98502**
at 500 Hz smoothing/129 taps. On the harmonic source, FIR lengths
17/129/513 give cosine **.86197/.98293/.98381**. On a sine, requested smoothing
1/125/500/1000 Hz gives **.39064/.87877/.96353/.96785** at 129 taps. The accepted
parameter space is wider than the combinations with good spectral approximation.

There is exactly zero noise before the initial onset on all tested silent-prefix
fixtures. Noise after the gated burst extends **1.542/16.009/84.989/332.721/333.333 ms**
at envelope time constants .1/1/5/20/100 ms. The 100-ms result reaches the file
boundary and is right-censored; the actual exponential tail is longer.

The switching-tone probe demonstrates the temporal-spectral limitation.
During a passage containing only a 1 kHz tone, **49.96%** of added-noise FFT
energy lies above 7 kHz because the whole-excerpt profile also includes a later
11.2 kHz tone. **1.347%** of total noise energy occurs in the exactly silent
inter-burst gap. Thus the global profile can anticipate the frequency content
of later events even though the waveform envelope prevents noise before the
first signal onset. This is a potential time-frequency confound.

QN applies no zeroing mask. Nevertheless, additive interference can reduce
individual observed coefficients. At SNR 20 dB, real-source median **1.565%**
of active reference cells are attenuated by more than 6 dB; at 10 dB it is
**3.384%**. The reference activity floor is −60 dB relative to peak STFT magnitude.
This is observed cancellation, with a different mechanism from deliberately
selected SH removal. Perceptual hole-like impressions remain untested.

### Monotonicity and source sensitivity

The following counts refer to 54 source/seed series per metric, with settings
ordered toward increasing nominal processing strength. Silence accounts for
three undefined series for energy-normalized measures. LP's three seeds duplicate
its deterministic output, so the counts are not independent statistical samples.
Tolerance is max(1e-12, 1e-6 times the largest absolute series value).

| Artifact | Objective metric | Increasing | Flat | Nonmonotonic | Undefined |
|---|---|---:|---:|---:|---:|
| LP | normalized_spectral_magnitude_error | 48 | 0 | 3 | 3 |
| SH | net_removed_waveform_energy_fraction | 51 | 0 | 0 | 3 |
| UN | fixed_reference_peak_contrast_drop_db | 45 | 0 | 0 | 9 |
| QN | relative_residual_energy | 51 | 0 | 0 | 3 |

SH eligible-mask occupancy increases in all 54 series. Its removal energy and
residual energy increase in all 51 nonzero-source series. UN peak-contrast
reduction increases in all 45 defined series; impulse and low-frequency sine
have no eligible detected peak. QN residual energy has exact SNR-driven
monotonicity for all 51 nonzero series.

LP magnitude error increases for 48 series and is nonmonotonic on the low-band
1 kHz sine, where small full-excerpt differences can include finite-window and startup
effects. LP residual energy is nonmonotonic in 18 series across six sources.
On white noise it decreases from **1.72783 to 1.23683** as cutoff drops from
16 to 5 kHz. It is unsuitable as a universal LP-strength proxy.

The real-source LP magnitude changes are monotonic in all eight recording
series. Equal controls still yield different source distortions. For example,
p=1 SH removes about .09–5.59% of waveform energy across the real excerpts.
Nominally weak high-band settings may produce little useful evidence when
the source has little high-band energy. The controls include aggressive
stress conditions such as 5 kHz LP, full-band-eligible SH selection, full
UN replacement, and 10 dB QN. Their audibility and acceptable severity remain
unmeasured. None of these numerical tiers is a human severity label.

![Parameter control example](../outputs/artifact-validation/figures/UN_control.png)

![Real source comparisons](../outputs/artifact-validation/figures/real_content_spectral_changes.png)

## 6. Overlap, temporal support and PE/TM holdouts

| Operator | Verified overlap or confound | Holdout implication |
|---|---|---|
| LP | Frequency-dependent delay, phase-heavy residuals and causal post-ringing | No initial pre-onset noise in tested fixtures; captions still need to acknowledge phase behavior |
| SH | Pre-ringing from centered frequency suppression and time-varying masks | Temporal behavior overlaps PE-like characteristics |
| UN | Centered noise replacement spreads around transients; noise spectra can trigger the tonal detector | Intentional UN processing can coexist with PE-like spreading and atonal changes |
| QN | Offset tails, noise in later gaps, global spectral color during earlier events, random cancellation | Initial causality alone does not prove local time-frequency isolation |
| UN versus QN | Strong difference in retained tone amplitude, addition/replacement algebra and local flatness | Perceptual distinguishability requires listening comparisons at matched perceptual strength |

For the gated-tone probe at p=.7/full UN and seed 901, pre-onset extent increases
with STFT length. SH reaches **18.44/29.02/64.31 ms** at FFT lengths
1024/2048/4096; UN reaches **13.45/28.87/71.02 ms**. Combined analysis/synthesis
support can approach one full window, not just the half-window. Pre-onset energy
fractions are retained separately from support duration.

![Window support](../outputs/artifact-validation/figures/window_temporal_support.png)

All support extents use max(residual peak x 1e-4,1e-15), corresponding to a
relative −80 dB amplitude criterion where the floor is inactive. It is an
engineering threshold, not an audibility threshold. No PE/TM operator was added.
No operation intentionally substitutes noise with harmonic components as TM
does. Fine-band modulation and finite random realizations can still produce
structured or tonal-looking output, so perceptual independence is unverified.

The team must define PE holdout as absence of an intentional augmentation
operator, or impose a stricter constraint on incidental pre-onset behavior.
The current SH/UN paths satisfy the former interpretation and exhibit
counterexamples to perfect temporal isolation.

## 7. Automated checks, failures and missing coverage

The existing suite passes 104 tests in 7.07 s. It covers mono/stereo and
44.1/48 kHz shapes, deterministic transformations, short STFT round-trip,
LP response/causality, exact SH masks and runs, UN narrow-line reduction,
QN SNR/additivity/causality, identity handling, clipping rejection, saved
triplets, hashes, serialization, source-group splits and CLI paths.

The corrected audit completed **1,134 runtime condition checks with zero
failures**, no NaN/Inf outputs and no output peak exceeding .999 under the
declared input gains. These checks enforce shape/finite values, exact
SH gain reconstruction, QN SNR/noise agreement and LP/QN initial causality.
Seventy-two strongest-setting examples were re-generated with the same seed and
matched exactly. Saved degraded/reference/residual files were reloaded and
checked for exact residual subtraction.

The normal pipeline generated **104 mono triplets**, eight source groups,
44.1 kHz only, split counts 78/13/13, and maximum reconstruction error
**2.7756e-17**. Its validator reported no errors. Linked and independent channel policies coincide for one channel when the seed
and all other processing parameters are fixed.

**Failed initial audit calculation.** The first audit helper computed
sum(z²) for complex STFT arrays instead of sum(|z|²) in the new consistency
metric. It logged **88 JSON-serialization failures** after non-finite helper
results. That run was stopped and retained at
`outputs/artifact-validation-initial/`, including its script and run log.
The complex-energy calculation was corrected in the audit helper and the
full sweep rerun. Those failed initial measurements are excluded from conclusions.
The production generators and test suite were unchanged.


**Auxiliary playback correction.** Final file QA found that the matched-error
additive-noise control reached peak 1.11709. Its DOUBLE WAV retained the values
without sample clipping, but ordinary full-scale playback could clip.
All four comparison files were re-rendered with the same gain 0.85042213,
giving peak .95 and preserving all relative-energy and tone-gain results.
Unscaled controls are retained under
`outputs/artifact-validation-initial/unscaled_comparison/`.
The original executed main-script snapshot is
`outputs/artifact-validation/executed_main_script.py`; the current regeneration
script incorporates the shared playback gain.

Coverage still missing as permanent regression tests includes atonal UN detector
negative controls, quantitative pre-onset budgets across transform settings,
QN local time-frequency color/localization, supported smoothing/FIR-resolution
combinations, LP phase-sensitive residual behavior, perceptual caption correctness,
and listening-based audibility/severity. The existing test named
test_un_identity_and_no_eligible_tones checks strength zero and silence; it does
not require nonzero broadband noise to be an identity. This audit exposes that gap.

## 8. Essential improvements and decisions before scaling

1. **Enforce the 44.1 kHz mono contract in the production run configuration.**
   Downmix/reference preparation must precede processing; retain source identity
   and conversion provenance. Recompute residuals from saved exported signals.
   The audited mono pipeline configuration demonstrates this path.

2. **Resolve LP's phase and boundary policy.** Agree whether bandwidth-loss
   captions may include the existing phase effects. If temporal context is
   available, evaluate causal prefix processing followed by aligned cropping to
   reduce zero-state startup. Do not equate residual energy with removed energy.
   Any alternative filter requires versioned evidence and renewed checks.

3. **Review UN detection and labels using positive/negative controls.**
   The white-noise and smoothing probes show that current selections alone
   cannot establish tonal structure. Add detector/persistence criteria or
   explicitly qualify the supervision to describe the actual heuristic
   transformation. Validate tone retention and envelope changes after ISTFT.

4. **Decide the required QN locality and parameter support.**
   If the intended captions assert noise following local spectral content,
   whole-clip coloring needs improvement. Review temporal-envelope tails and
   restrict or validate smoothing/FIR combinations before sampling broadly.
   Retain the distinction between waveform SNR control and psychoacoustic NMR.

5. **Resolve the PE holdout criterion before collecting final training pairs.**
   Shorter windows reduce measured spreading but do not establish its perceptual
   absence. A stricter temporal-isolation requirement could call for a causal
   filterbank or other separately reviewed processing design.

6. **Validate perceptual supervision independently.**
   Source/seed objective monotonicity supplies engineering control. Audibility
   and severity need human evidence on independent recordings, with content
   coverage and uncertainty recorded. ODAQ remains external to parameter fitting
   and optimization in this audit.

Deferred work can include wider source/genre coverage, spoken-speech recordings,
more seeds and longer excerpts, richer caption language, more extensive stereo
support, and exact reproduction of unavailable ODAQ internals. Native mono
operation makes a new spatial family unnecessary for this training contract.

## 9. Evidence files and reproducibility limits

All paths below are relative to the KNN checkout.

- `scripts/validate_synthetic_artifacts.py` — controlled sweep, response checks,
  comparisons, figures and normal-entry-point mono dataset.
- `scripts/audit_parameter_probes.py` — secondary parameter sweeps, local flatness
  and real-source difference spectrograms.
- `outputs/artifact-validation/experiment_config.json` and `sources.jsonl` —
  settings, seeds, hashes, source provenance and input conversion.
- `measurements.jsonl`, `monotonicity.json`, `lp_response.json`,
  `supplementary.json`, `parameter_probes.json` and `tonality_detail.json` —
  detailed numerical results under the same output directory.
- `examples/` — reference paths, degraded/residual WAVs and actual NPZ evidence
  for strongest settings. `inputs/` holds the mono references.
- `mono_pipeline/` — complete triplets and model-facing manifest from the
  production generator, with `mono_pipeline_config.json` beside it.
- `figures/` — 13 PNGs including control curves, response/phase,
  replacement/addition comparison, local spectral structure, real-content
  spectrogram changes, window support and four burst triplets.
- `reviewed_file_hashes.json`, `baseline_tests.txt` and `run.log` — code/test/config
  identity, baseline tests and experiment progress.
- `source_documentation/` — two upstream MedleyDB instrument annotations.
  These are recording-level annotations, with no verified frame-level attribution.

All plots are objective diagnostics. Source code and packages are versioned in
the run evidence; bitwise reproducibility across arbitrary numerical-library
versions or hardware is unverified. The output summary's figure_count=11 refers
to the main script; the secondary script adds two figures, giving 13 total.
No full training dataset, model training or generator rewrite was performed.

[original]: https://arxiv.org/abs/2401.00197
[stereo]: https://arxiv.org/abs/2512.14259
[collection]: https://arxiv.org/abs/2610.37959
[musdb]: https://zenodo.org/records/3338373
[license]: https://medleydb.weebly.com/downloads.html
