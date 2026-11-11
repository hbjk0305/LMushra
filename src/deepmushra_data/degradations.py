"""Four controlled approximations; no PE or TM training generators."""

from dataclasses import dataclass
import numbers

import numpy as np
from scipy import signal
from scipy.ndimage import gaussian_filter1d

from . import MIN_SAMPLE_RATE, TRAINING_ARTIFACTS
from .stft import STFTConfig, analyze, synthesize, validate_audio

ALGORITHM_VERSION = "1.1"
DEFAULTS = {
    "QN": {"snr_db": 30.0, "smoothing_hz": 500.0, "envelope_ms": 5.0,
           "fir_taps": 129, "channel_mode": "independent"},
    "LP": {"filter_design": "butterworth", "transition_hz": 1500.0,
           "passband_ripple_db": 0.5, "attenuation_db": 60.0},
    "SH": {"start_hz": 4000.0, "hole_probability": 0.1, "band_width_hz": 500.0,
           "run_frames": 4, "attenuation_db": 80.0},
    "UN": {"crossover_hz": 7000.0, "strength": 0.5, "smoothing_hz": 500.0,
           "tonal_threshold_db": 6.0, "channel_mode": "linked"},
}


@dataclass
class EffectResult:
    audio: np.ndarray
    parameters: dict
    evidence: dict
    arrays: dict


def _number(params, key, low, high, inclusive_high=True, integer=False):
    value = params[key]
    if isinstance(value, bool) or not isinstance(value, numbers.Real) or not np.isfinite(value):
        raise ValueError(f"{key} must be a finite number")
    if integer and not isinstance(value, numbers.Integral):
        raise ValueError(f"{key} must be an integer")
    if value < low or (value > high if inclusive_high else value >= high):
        raise ValueError(f"{key} outside allowed range: {value}")


def resolve_parameters(artifact, supplied, sample_rate):
    if artifact not in TRAINING_ARTIFACTS:
        raise ValueError(f"Unsupported training artifact {artifact!r}; PE and TM are held out")
    if not isinstance(sample_rate, numbers.Integral) or sample_rate < MIN_SAMPLE_RATE:
        raise ValueError("Source sample rate must be at least 44100 Hz; upsampling is not a remedy")
    allowed = set(DEFAULTS[artifact]) | ({"cutoff_hz"} if artifact == "LP" else set())
    unknown = set(supplied) - allowed
    if unknown:
        raise ValueError(f"Unknown {artifact} parameters: {sorted(unknown)}")
    p = {**DEFAULTS[artifact], **supplied}
    nyquist = sample_rate / 2
    if artifact == "LP":
        if "cutoff_hz" not in p:
            raise ValueError("LP requires cutoff_hz")
        _number(p, "cutoff_hz", 1, nyquist, False)
        _number(p, "transition_hz", 1, nyquist, False)
        if p["cutoff_hz"] + p["transition_hz"] >= nyquist:
            raise ValueError("LP stopband edge must be below Nyquist")
        _number(p, "passband_ripple_db", 0.01, 3)
        _number(p, "attenuation_db", p["passband_ripple_db"] + 1, 120)
        if p["filter_design"] not in ("butterworth", "elliptic"):
            raise ValueError("filter_design must be butterworth or elliptic")
    elif artifact == "SH":
        _number(p, "start_hz", 0, nyquist, False)
        _number(p, "hole_probability", 0, 1)
        _number(p, "band_width_hz", 1, nyquist)
        _number(p, "run_frames", 1, 100000, integer=True)
        if p["attenuation_db"] != "zero":
            _number(p, "attenuation_db", 0, 200)
    elif artifact == "UN":
        _number(p, "crossover_hz", 0, nyquist, False)
        _number(p, "strength", 0, 1)
        _number(p, "smoothing_hz", 1, nyquist / 2)
        _number(p, "tonal_threshold_db", 0, 60)
        if p["channel_mode"] not in ("linked", "independent"):
            raise ValueError("channel_mode must be linked or independent")
    else:
        _number(p, "snr_db", 0, 100)
        _number(p, "smoothing_hz", 1, nyquist / 2)
        _number(p, "envelope_ms", 0.1, 1000)
        _number(p, "fir_taps", 17, 2049, integer=True)
        if p["fir_taps"] % 2 != 1:
            raise ValueError("fir_taps must be odd")
        if p["channel_mode"] not in ("linked", "independent"):
            raise ValueError("channel_mode must be linked or independent")
    return p


def _bands(frequencies, start, width):
    eligible = np.flatnonzero(frequencies >= start)
    if not len(eligible):
        return []
    ids = np.floor((frequencies[eligible] - start) / width).astype(int)
    return [eligible[ids == value] for value in np.unique(ids)]


def _base_evidence(config, mask_kind):
    return {"algorithm_version": ALGORITHM_VERSION, "stft": config.metadata(),
            "mask_kind": mask_kind, "coverage_denominator": "all analyzed time-frequency-channel cells, including boundary padding",
            "perceptual_equivalence_to_odaq": "unverified"}


def _lowpass(audio, sr, p, config):
    args = (p["cutoff_hz"], p["cutoff_hz"] + p["transition_hz"],
            p["passband_ripple_db"], p["attenuation_db"])
    if p["filter_design"] == "butterworth":
        order, wn = signal.buttord(*args, fs=sr)
    else:
        order, wn = signal.ellipord(*args, fs=sr)
    if order > 256:
        raise ValueError("LP filter order exceeds 256; widen transition or relax attenuation")
    if p["filter_design"] == "butterworth":
        sos = signal.butter(order, wn, fs=sr, output="sos")
    else:
        sos = signal.ellip(order, p["passband_ripple_db"], p["attenuation_db"],
                           wn, fs=sr, output="sos")
    degraded = signal.sosfilt(sos, audio, axis=0)
    frequencies, times, z = analyze(audio, sr, config)
    _, response = signal.sosfreqz(sos, worN=frequencies, fs=sr)
    selected = np.broadcast_to((np.abs(response) < 10 ** (-1 / 20))[None, :, None], z.shape).copy()
    response_f, dense_response = signal.sosfreqz(sos, worN=16384, fs=sr)
    response_db = 20 * np.log10(np.maximum(np.abs(dense_response), 1e-15))
    evidence = _base_evidence(config, "filter_response_projection_not_applied_stft_mask")
    evidence.update({"filter_order": int(order), "sos_coefficients": sos.tolist(),
                     "phase_policy": "causal IIR; frequency-dependent group delay; no delay compensation or look-ahead",
                     "cutoff_definition": "passband edge",
                     "response_passband_loss_max_db": float(-np.min(response_db[response_f <= p["cutoff_hz"]])),
                     "response_stopband_attenuation_min_db": float(-np.max(response_db[response_f >= p["cutoff_hz"] + p["transition_hz"]])),
                     "transformation_applied": True})
    return EffectResult(degraded, p, evidence,
                        {"selected_mask": selected, "frequencies_hz": frequencies, "times_s": times,
                         "response_frequencies_hz": response_f, "response_gain": np.abs(dense_response)})


def _holes(audio, sr, p, seed, config):
    frequencies, times, z = analyze(audio, sr, config)
    mask = np.zeros(z.shape[:2], dtype=bool)
    bands = _bands(frequencies, p["start_hz"], p["band_width_hz"])
    rng = np.random.default_rng(seed)
    run = p["run_frames"]
    for bins in bands:
        blocks = rng.random((len(times) + run - 1) // run) < p["hole_probability"]
        mask[:, bins] = np.repeat(blocks, run)[:len(times), None]
    gain = 0.0 if p["attenuation_db"] == "zero" else 10 ** (-p["attenuation_db"] / 20)
    selected = np.broadcast_to(mask[:, :, None], z.shape).copy() & (gain < 1)
    gains = np.where(selected, gain, 1.0)
    degraded = synthesize(z * gains, sr, len(audio), config) if selected.any() else audio.copy()
    evidence = _base_evidence(config, "exact_applied_stft_gain")
    evidence.update({"band_edges_hz": [[float(frequencies[b[0]]), float(frequencies[b[-1]])] for b in bands],
                     "selection_policy": "independent Bernoulli decisions per band and nonoverlapping run block; linked across channels",
                     "transformation_applied": bool(selected.any())})
    return EffectResult(degraded, p, evidence,
                        {"selected_mask": selected, "gain_mask": gains,
                         "frequencies_hz": frequencies, "times_s": times})


def _unmasked_noise(audio, sr, p, seed, config):
    frequencies, times, z = analyze(audio, sr, config)
    sigma = max(p["smoothing_hz"] / (sr / config.n_fft), 0.5)
    magnitude = np.abs(z)
    envelope = np.sqrt(gaussian_filter1d(magnitude ** 2, sigma=sigma, axis=1, mode="nearest"))
    shared_magnitude = np.sqrt(np.mean(magnitude ** 2, axis=2))
    shared_envelope = np.sqrt(gaussian_filter1d(shared_magnitude ** 2, sigma=sigma, axis=1, mode="nearest"))
    peaks = shared_magnitude > shared_envelope * 10 ** (p["tonal_threshold_db"] / 20)
    peaks &= shared_magnitude > max(float(shared_magnitude.max()) * 1e-6, 1e-15)
    bands = _bands(frequencies, p["crossover_hz"], 2 * p["smoothing_hz"])
    mask = np.zeros(z.shape[:2], dtype=bool)
    rng = np.random.default_rng(seed)
    noise_channels = 1 if p["channel_mode"] == "linked" else audio.shape[1]
    noise = rng.standard_normal((len(audio), noise_channels))
    if noise_channels == 1:
        noise = np.repeat(noise, audio.shape[1], axis=1)
    _, _, nz = analyze(noise, sr, config)
    # Smoothly normalize stochastic magnitudes before applying the reference envelope.
    noise_scale = np.sqrt(gaussian_filter1d(np.abs(nz) ** 2, sigma=sigma, axis=1, mode="nearest"))
    shaped = envelope * nz / np.maximum(noise_scale, 1e-15)
    out = z.copy()
    strength = p["strength"]
    for bins in bands:
        active = peaks[:, bins].any(axis=1) & (strength > 0)
        mask[:, bins] = active[:, None]
        original = z[:, bins, :]
        replacement = shaped[:, bins, :]
        target_energy = np.sum(np.abs(original) ** 2, axis=1, keepdims=True)
        noise_energy = np.sum(np.abs(replacement) ** 2, axis=1, keepdims=True)
        replacement = replacement * np.sqrt(target_energy / np.maximum(noise_energy, 1e-30))
        blended = (1 - strength) * original + strength * replacement
        blended_energy = np.sum(np.abs(blended) ** 2, axis=1, keepdims=True)
        blended *= np.sqrt(target_energy / np.maximum(blended_energy, 1e-30))
        out[:, bins, :] = np.where(active[:, None, None], blended, original)
    # DC/Nyquist must be real for a real-valued inverse transform.
    out[:, 0, :] = out[:, 0, :].real
    out[:, -1, :] = out[:, -1, :].real
    selected = np.broadcast_to(mask[:, :, None], z.shape).copy()
    degraded = synthesize(out, sr, len(audio), config) if selected.any() else audio.copy()
    evidence = _base_evidence(config, "exact_applied_stft_replacement_selection")
    evidence.update({"selection_policy": "bands containing a peak above the smoothed envelope; linked across channels",
                     "replacement_band_width_hz": 2 * p["smoothing_hz"],
                     "smoothing_definition": "square root of Gaussian-smoothed power; Gaussian standard deviation in Hz",
                     "blend_definition": "linear complex blend, then per-frame/band/channel energy normalization",
                     "transformation_applied": bool(selected.any())})
    return EffectResult(degraded, p, evidence,
                        {"selected_mask": selected, "frequencies_hz": frequencies,
                         "times_s": times, "reference_envelope": envelope})


def _quantization_like_noise(audio, sr, p, seed, config):
    """Add spectral-colored, causal-envelope noise; not quantization or NMR masking."""
    frequencies, times, z = analyze(audio, sr, config)
    sigma = max(p["smoothing_hz"] / (sr / config.n_fft), 0.5)
    # Offline whole-excerpt spectral color, not a framewise masking threshold.
    power = gaussian_filter1d(np.mean(np.abs(z) ** 2, axis=0), sigma, axis=0, mode="nearest")
    rng = np.random.default_rng(seed)
    white = rng.standard_normal((len(audio), 1 if p["channel_mode"] == "linked" else audio.shape[1]))
    if white.shape[1] == 1:
        white = np.repeat(white, audio.shape[1], axis=1)
    alpha = float(np.exp(-1 / (sr * p["envelope_ms"] / 1000)))
    envelope = np.sqrt(np.maximum(signal.lfilter([1-alpha], [1, -alpha], audio ** 2, axis=0), 0))
    noise = np.zeros_like(audio)
    filters = []
    for channel in range(audio.shape[1]):
        amplitude = np.sqrt(power[:, channel])
        amplitude /= max(float(amplitude.max()), 1e-30)
        # A small spectral floor keeps the minimum-phase factorization well conditioned.
        linear = signal.firwin2(p["fir_taps"], frequencies, np.maximum(amplitude, 1e-6), fs=sr)
        causal = signal.minimum_phase(linear, method="homomorphic", half=False)
        filters.append(causal)
        shaped = signal.lfilter(causal, [1.0], white[:, channel]) * envelope[:, channel]
        target = float(np.sum(audio[:, channel] ** 2)) * 10 ** (-p["snr_db"] / 10)
        energy = float(np.sum(shaped ** 2))
        if target and energy:
            noise[:, channel] = shaped * np.sqrt(target / energy)
    _, _, nz = analyze(noise, sr, config)
    floor = max(float(np.max(np.abs(nz))) * 1e-4, 1e-15)
    selected = np.abs(nz) > floor
    evidence = _base_evidence(config, "derived_added_noise_stft_support_not_an_applied_gain_mask")
    evidence.update({"phase_policy": "reference unchanged; added noise uses causal minimum-phase FIR and past-only exponential RMS",
        "spectral_color": "whole-excerpt mean STFT power, Gaussian frequency smoothing, finite FIR approximation",
        "smoothing_definition": "Gaussian standard deviation in Hz",
        "temporal_envelope": "sqrt of causal exponential mean reference power; zero state; may trail offsets",
        "envelope_alpha": alpha, "snr_definition": "reference-to-added-noise waveform energy, calibrated independently per channel",
        "support_definition": "noise STFT magnitude > max(noise peak STFT magnitude*1e-4,1e-15); centered analysis can project before actual waveform support",
        "noise_waveform_array": "added_noise", "no_tonal_replacement": True,
        "psychoacoustic_masking_model": None, "reference_phase_modified": False,
        "transformation_applied": bool(np.any(noise))})
    return EffectResult(audio + noise, p, evidence,
        {"selected_mask": selected, "frequencies_hz": frequencies, "times_s": times,
         "added_noise": noise, "noise_fir_coefficients": np.stack(filters), "causal_rms_envelope": envelope})


def apply_effect(artifact, audio, sample_rate, parameters, seed, stft_config=None):
    audio = validate_audio(audio)
    p = resolve_parameters(artifact, parameters, sample_rate)
    config = stft_config or STFTConfig()
    if artifact == "LP":
        result = _lowpass(audio, sample_rate, p, config)
    elif artifact == "SH":
        result = _holes(audio, sample_rate, p, seed, config)
    elif artifact == "UN":
        result = _unmasked_noise(audio, sample_rate, p, seed, config)
    else:
        result = _quantization_like_noise(audio, sample_rate, p, seed, config)
    result.audio = validate_audio(result.audio)
    if result.audio.shape != audio.shape:
        raise ValueError("Effect changed waveform shape")
    return result
