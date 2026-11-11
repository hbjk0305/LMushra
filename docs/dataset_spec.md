# Dataset specification, schema 1.0

## Purpose and limits

Each example consists of an aligned triplet `(reference, degraded, residual)`,
processing evidence, objective measurements, and text candidates. The convention
is **residual = degraded − reference**, so degraded = reference + residual.

Synthesis operators are known; their human perceptual consequences are not.
This dataset must not be described as containing human MUSHRA ground truth.
It supports LP, SH, UN, and additive signal-shaped QN-like noise. PE (pre-echo) and TM (tonality mismatch) remain
held out from training and development augmentation for subsequent ODAQ tests.
The residual, metadata, and text must remain in the same source-level partition.

## Audio contract

- The hard minimum sample rate is **44,100 Hz**, including when users override
  the configuration. Default accepted rates are 44,100 and 48,000 Hz; a higher
  rate can be explicitly allowlisted. No resampling is performed.
- Inputs are readable mono/stereo WAV or FLAC, nonempty, finite, within the
  configured duration, and within normalized full scale. A WAV container is not
  evidence that its recording history is lossless or full bandwidth.
- Default duration is 1–30 s. No automatic cropping, channel conversion, silence
  deletion, time stretching, or content transcription is performed.
- Internal arrays and saved triplets use float64. Output subtype is WAV DOUBLE.
  Validate downstream readers explicitly; a conversion to PCM/float32 is a new
  dataset export and requires recomputing its residual from its saved signals.
- One scalar source gain is applied only if needed to fit `source_peak_limit`.
  All variants use that same reference. The original peak and gain are recorded.
- Reference, degraded, and residual peaks must each stay below
  `output_peak_limit` (default 0.999). An excess is an error. Nothing is clipped,
  independently peak-normalized, or independently loudness-normalized.
- Saved reference and degraded samples are reloaded before residual subtraction.
  Standalone validation checks the subtraction and reconstruction within
  absolute tolerance 1e-12.
- Sample alignment means the same origin, sample indices, rate, and channel
  layout. The causal LP's phase response can delay signal features; this is a
  documented property of that operator, not an inserted file offset. No
  cross-correlation alignment or group-delay compensation is performed.

Floating-point WAV files written by libsndfile can include a PEAK chunk with a
wall-clock timestamp. The writer zeros that optional timestamp without changing
the peak values or waveform bytes. This chunk name refers to peak amplitude,
**not** a PE/pre-echo augmentation.

## Configuration

Top-level keys are `schema_version`, `seed`, `input`, `splits`, `stft`,
`artifacts`, and `include_identity`. Unknown keys are rejected. Artifact names
are uppercase `LP`, `SH`, `UN`, and `QN`; optional identity controls are produced by
the pipeline rather than declared as a degradation.

Each artifact has `defaults` and exactly one of:

- `settings`: a nonempty list of explicit parameter mappings, optionally carrying
  `parameter_tier: unspecified|subtle|moderate|strong`;
- `sampling`: `count` and `parameters`, whose rules are `uniform: [low, high]`,
  `loguniform: [low, high]`, `randint: [low, high]` (both inclusive), or
  `choice: [value, ...]`.

Sampling recipes have tier `unspecified`. All choices and range corners are
validated against the allowlisted rates, including joint LP constraints. A
chosen source is validated again before generation. Source discovery order
does not affect parameter sampling or waveform randomness.

| Artifact | Parameter | Meaning |
|---|---|---|
| LP | `cutoff_hz` | Passband edge, strictly below Nyquist |
| LP | `filter_design` | `butterworth` (default) or `elliptic` |
| LP | `transition_hz` | Stopband edge minus passband edge; default 1500 Hz |
| LP | `passband_ripple_db` | Maximum design passband loss; default 0.5 dB |
| LP | `attenuation_db` | Minimum design stopband attenuation; default 60 dB |
| SH | `start_hz` | Lowest eligible STFT-bin center; default 4000 Hz |
| SH | `hole_probability` | Bernoulli probability per band/run block; default 0.1 |
| SH | `band_width_hz` | Nominal band width; default 500 Hz, quantized to bins |
| SH | `run_frames` | Nonoverlapping block length; default 4 |
| SH | `attenuation_db` | Amplitude attenuation; default 80 dB, or literal `zero` |
| UN | `crossover_hz` | Lowest eligible bin center; default 7000 Hz |
| UN | `strength` | Complex interpolation coefficient in [0,1]; default 0.5 |
| UN | `smoothing_hz` | Gaussian power-envelope standard deviation; default 500 Hz |
| UN | `tonal_threshold_db` | Peak/envelope amplitude contrast; default 6 dB |
| UN | `channel_mode` | `linked` default or `independent` noise realizations |

LP filter order is derived from passband/stopband requirements and capped at
256. Stopband edge must be strictly below Nyquist. A very narrow transition may
therefore fail rather than silently generate an impractical filter.

## Processing evidence

The shared STFT uses a periodic Hann window, default FFT size 2048, default hop
512, spectrum scaling, one-sided spectra, zero boundary extension, and final
padding. Arrays use `[time, frequency, channel]` order. The ISTFT uses matching
settings and trims explicit padding to the original length. Short signals are
explicitly padded before analysis to avoid SciPy silently changing the window.
Window/hop choices must satisfy the nonzero overlap-add condition.

**LP** uses causal SOS filtering, with zero initial state. It stores SOS
coefficients, design order, a dense magnitude response, and measured design
passband/stopband bounds. Its selection array projects frequencies attenuated
by more than 1 dB onto the analysis grid. This is explicitly labeled a response
projection, **not an applied STFT mask**, and does not represent phase changes.

**SH** divides eligible bins into contiguous frequency bands, draws independent
Bernoulli decisions for nonoverlapping `run_frames` blocks, and applies the
specified amplitude gain. Adjacent selected blocks can merge into longer runs;
the probability is an occupancy parameter, not an event-onset rate. The last
block may be shorter. Selections are linked across channels. Evidence contains
the exact applied gain array and selection array. Nominal band edges and actual
bin centers may differ because of frequency-grid quantization. No psychoacoustic
masking model or lowest-SMR prioritization is implemented.

**UN** estimates an RMS spectral envelope as
`sqrt(gaussian_filter(abs(STFT)**2))`. A shared channel-RMS spectrum identifies
peaks above that envelope. Above the crossover, bands of nominal width
`2*smoothing_hz` containing a qualifying peak are selected. Seeded time-domain
white noise is analyzed on the same grid, spectrally shaped, and normalized to
each selected band/frame/channel's reference STFT energy. The complex blend
`(1-strength)*original + strength*replacement` is normalized to the original band
energy before inverse STFT. Zero strength or no eligible peaks returns the
original samples exactly. Selections remain linked across channels; the noise
realization can be shared or independent.

Per-band/frame STFT energy matching does not establish exact waveform energy or
perfect envelope preservation. Both are measured from the reconstructed output.
The UN operator is a controlled spectral substitution, not an EnCodec or DAC
simulation, and equivalence to ODAQ UN is unverified.

NPZ evidence includes `selected_mask`, `frequencies_hz`, and `times_s`, plus
artifact-specific arrays: SH `gain_mask`; LP `response_frequencies_hz` and
`response_gain`; UN `reference_envelope`. Metadata carries the evidence file's
relative path, checksum, format, selection key, and axis order.

## Metadata record

| Group | Fields and policy |
|---|---|
| Top-level | `schema_version`, `sample_id` |
| `source` | Group and declared source IDs, source file, SHA256, content category/provenance, sample rate/count, duration, channels, split, original peak, shared gain, functional-test flag |
| `audio` | `reference`, `degraded`, `residual`, each with relative path, SHA256, and subtype |
| `degradation` | Artifact, algorithm/version, resolved parameters, random seed, provisional parameter severity, frequency/time projections, algorithm evidence, mask reference |
| `measurements` | Signal/residual levels and energies, spectral differences, processing coverage, measured change coverage, artifact-specific statistics |
| `perceptual_annotation` | Status, audibility, perceived severity, quality category, description attributes, natural-language description, provenance |
| `descriptions` | Template version, technical text/status, perceptual candidate/status, structured attributes |
| `provenance` | Generator version/source-code SHA256, Git revision/dirty flag, resolved-config SHA256, master seed |

All unmeasured perceptual annotation values are JSON `null` and status
`unverified`. Description attributes use the explicit string `unknown` where
appropriate. Parameter tiers never populate perceptual severity or quality.
Identity controls also have unknown perceptual labels; they do not receive a
fabricated rating of 100 or an `Excellent` target.

The technical description may name an operator and known parameters. It must
not claim that listeners hear it, identify affected instruments from processing
parameters alone, or infer a quality score. The perceptual candidate says
“may” and is clearly marked unverified. The generator never produces a human
natural-language annotation. `describe(artifact, parameters, evidence)` is a pure
replaceable interface for later text processing; paraphrasers must preserve this
evidence boundary.

Frequency/time intervals are **separate projections** of processing selections.
Time projection includes STFT window support and is clipped to clip duration;
the NPZ mask preserves joint TF structure. Overlap-add and phase response can
spread actual changes beyond selected cells, so these intervals are not
guaranteed audible locations. No “most noticeable time” is inferred.

### Measurement definitions

- Waveform energy is the sum of squared samples over all channels; RMS is the
  square root of the mean square over all samples and channels.
- `net_energy_change = degraded_energy - reference_energy` is signed.
  `residual_energy = sum((degraded-reference)**2)` is nonnegative and is not
  “removed energy.” Noise replacement can preserve net energy while producing
  a large residual. Ratios or dB changes with a zero denominator are `null`.
- Normalized spectral magnitude error is
  `sqrt(sum((abs(D)-abs(R))**2) / sum(abs(R)**2))`, or `null` for a zero reference.
- `affected_tf_ratio` counts selected cells divided by every analyzed TF/channel
  cell, including boundary padding. `affected_frame_ratio` counts frames with
  any selected cell divided by all analyzed frames. Neither is audible coverage.
- `measured_changed_tf_ratio` counts cells with at least 1 dB magnitude change,
  using floor `max(reference_peak_STFT_magnitude*1e-4, 1e-15)`, divided by all
  analyzed cells. This is an engineering threshold, not a masking threshold.
- SH additionally reports the fraction of reference spectral energy in selected
  cells. This is a grid statistic, not exact removed waveform energy.
- UN reports normalized RMS-envelope error over selected cells, 95th-percentile
  peak/envelope contrast over selected active cells, and mean contrast at the
  **reference-detected tonal peak locations** before and after processing. These
  complementary measures have different meanings; broadband percentiles alone
  can obscure removal of narrow harmonic peaks.

## Source splits, determinism, and manifest

Files with a common declared `source_id` or identical file SHA256 are connected
transitively into one source group. Exact duplicate files are generated once.
Groups are sorted by a seed-dependent SHA256 ordering. Largest-remainder
allocation approximates configured proportions; when enough groups exist, a
group is moved from the largest partition to any requested empty partition.
Too few groups raises an error. Six pilot groups produce 4/1/1 source groups,
or 40/10/10 examples with the default recipes.

Changing the source population can change allocation; persist and version each
run's split map rather than recomputing splits independently downstream. File
hashes do not detect re-encoded or cropped duplicates, and directory mode cannot
infer common recordings from unrelated filenames. Supply source identities and
perform corpus overlap review before research training. All ODAQ recordings,
stems, and related source productions must remain external to synthetic training
if ODAQ is the final content-held-out benchmark; this pipeline does not ship an
ODAQ fingerprint database or automatically certify that exclusion.

Seeds derive from stable source keys, master seed, artifact, variant index, and
parameters; RNG is NumPy's default PCG64. Sample IDs also bind generator version
and resolved configuration. Pin the recorded package and libsndfile versions for
exact reproducibility; cross-platform numerical identity is not promised.

`metadata.jsonl` contains complete records, also stored as individual JSON files.
`manifest.jsonl` and its split-specific copies contain relative triplet paths,
metadata path, IDs, split, sample rate, artifact, technical text, and the
unverified perceptual candidate. `quality_category` remains `null`. Do not feed
artifact names, parameters, or candidate text to a model at evaluation time as
if they were input observations. Model-format adapters are outside this module.

Generation uses a private staging directory, independently validates saved
outputs, and then renames that directory into the requested new output path.
On failure the staging directory is removed and no final dataset is published.
Diagnostics and all generated data remain outside version control.

## Phase 1 extension (generator 0.2.0, algorithm/template 1.1)

Schema 1.0 keeps the same top-level groups; the permitted artifact enumeration
now also includes QN. Consumers must accept this value. Optional manifest
`source_provenance` is a finite JSON mapping and is copied into source metadata;
use it for licenses, attribution, original recordings, crops, and integrity
qualifications. Missing provenance is `{}`, not a claim of a license grant.
Existing LP/SH/UN recipes keep their numerical behavior.

QN is additive signal-shaped noise, not a quantizer or a masking/NMR model.
It uses whole-excerpt mean STFT power (offline spectral analysis), Gaussian
frequency smoothing, a finite minimum-phase FIR, seeded white noise and a
past-only exponential RMS envelope. FIR filtering and RMS initialization are
causal and zero-state. It can trail signal offsets; it adds exactly no noise
before the first nonzero sample. Per-channel normalization targets waveform
reference/noise SNR. The original waveform is not filtered or replaced.

| QN parameter | Accepted range/default | Phase 1 |
|---|---|---|
| `snr_db` | 0–100 dB / 30 | 40, 30, 20 dB |
| `smoothing_hz` | 1–Nyquist/2 / 500 Hz (Gaussian sigma) | 500 Hz |
| `envelope_ms` | 0.1–1000 / 5 ms (exponential time constant) | 5 ms |
| `fir_taps` | odd integer 17–2049 / 129 | 129 |
| `channel_mode` | independent (default) or linked | independent |

QN evidence stores actual `added_noise`, FIR coefficients, and the causal RMS
envelope. Its boolean TF support is **derived from noise magnitude**, thresholded
at max(noise peak STFT magnitude x 1e-4, 1e-15); it is not an applied gain mask.
Centered diagnostic STFT support can project earlier than the causal waveform.
Measured SNR and noise/reference PSD cosine are objective implementation checks.
QN noise is not a removed-energy measurement; net and residual energy remain
distinct quantities. Finite colored noise can have nonzero correlation with the
reference, so output energy change need not equal added-noise energy exactly.

For SH/UN, centered analysis and overlap-add can create pre-onset residual energy
within roughly one full analysis-window length. Excluding a PE generator does
not establish the absence of incidental PE-like smearing. See the measured
onset probes and the required holdout-definition decision in the Phase 1 report.
Do not turn processing-region projections into verified audible-event labels.
