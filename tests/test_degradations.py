import numpy as np
import pytest

from deepmushra_data.degradations import apply_effect, resolve_parameters
from deepmushra_data.metadata import measure
from deepmushra_data.stft import STFTConfig, analyze, synthesize


@pytest.mark.parametrize("sr", [44100, 48000])
@pytest.mark.parametrize("channels", [1, 2])
@pytest.mark.parametrize("count", [1, 97, 512, 1739])
def test_stft_roundtrip(sr, channels, count):
    audio = np.random.default_rng(1).normal(scale=0.1, size=(count, channels))
    config = STFTConfig(512, 128)
    _, _, spectrum = analyze(audio, sr, config)
    restored = synthesize(spectrum, sr, count, config)
    assert restored.shape == audio.shape
    np.testing.assert_allclose(restored, audio, atol=1e-12, rtol=0)


@pytest.mark.parametrize("artifact,parameters", [
    ("LP", {"cutoff_hz": 10000}),
    ("SH", {"hole_probability": 0.4}),
    ("UN", {"crossover_hz": 7000, "strength": 0.8}),
])
@pytest.mark.parametrize("sr", [44100, 48000])
@pytest.mark.parametrize("channels", [1, 2])
def test_shape_finite_deterministic(artifact, parameters, sr, channels):
    t = np.arange(sr // 8) / sr
    mono = 0.1 * np.sin(2 * np.pi * 1000 * t) + 0.1 * np.sin(2 * np.pi * 11500 * t)
    audio = np.repeat(mono[:, None], channels, axis=1)
    a = apply_effect(artifact, audio, sr, parameters, 7)
    b = apply_effect(artifact, audio, sr, parameters, 7)
    np.testing.assert_array_equal(a.audio, b.audio)
    assert a.audio.shape == audio.shape
    assert np.isfinite(a.audio).all()
    assert np.max(np.abs(a.audio)) < 1
    for name in a.arrays:
        np.testing.assert_array_equal(a.arrays[name], b.arrays[name])


@pytest.mark.parametrize("design", ["butterworth", "elliptic"])
def test_lowpass_frequency_response_and_causality(design):
    sr = 48000
    impulse = np.zeros((sr // 3, 1))
    impulse[1024, 0] = 0.1
    result = apply_effect("LP", impulse, sr, {"cutoff_hz": 10000, "filter_design": design}, 1)
    assert np.all(result.audio[:1024] == 0), "Causal LP must not introduce pre-onset energy"
    assert result.evidence["response_passband_loss_max_db"] <= 0.51
    assert result.evidence["response_stopband_attenuation_min_db"] >= 59.9
    t = np.arange(sr) / sr
    for frequency, expected_low in ((1000, False), (14000, True)):
        audio = (0.1 * np.sin(2 * np.pi * frequency * t))[:, None]
        output = apply_effect("LP", audio, sr, {"cutoff_hz": 10000, "filter_design": design}, 2).audio
        ratio = np.linalg.norm(output[sr // 4:]) / np.linalg.norm(audio[sr // 4:])
        assert ratio < 0.002 if expected_low else 0.93 < ratio < 1.01


def test_subtle_16khz_lowpass_is_observable_full_band():
    sr = 44100
    t = np.arange(sr // 2) / sr
    audio = (0.1 * np.sin(2 * np.pi * 1000 * t) + 0.02 * np.sin(2 * np.pi * 19000 * t))[:, None]
    result = apply_effect("LP", audio, sr, {"cutoff_hz": 16000}, 1)
    frequencies = np.fft.rfftfreq(len(audio) - 4096, 1 / sr)
    before = np.abs(np.fft.rfft(audio[4096:, 0]))
    after = np.abs(np.fft.rfft(result.audio[4096:, 0]))
    high = (frequencies > 18500) & (frequencies < 19500)
    assert np.linalg.norm(after[high]) < 0.02 * np.linalg.norm(before[high])


@pytest.mark.parametrize("parameters", [{"hole_probability": 0}, {"attenuation_db": 0}])
def test_holes_identity(parameters):
    audio = np.random.default_rng(1).normal(scale=0.1, size=(4097, 2))
    result = apply_effect("SH", audio, 48000, parameters, 1)
    np.testing.assert_array_equal(result.audio, audio)
    assert not result.arrays["selected_mask"].any()


def test_holes_actual_gain_mask_and_full_removal():
    audio = np.random.default_rng(1).normal(scale=0.1, size=(10000, 2))
    result = apply_effect("SH", audio, 48000, {
        "start_hz": 0, "hole_probability": 1, "attenuation_db": "zero", "run_frames": 4,
    }, 10)
    assert result.arrays["selected_mask"].all()
    assert np.all(result.arrays["gain_mask"] == 0)
    assert np.all(result.audio == 0)


def test_holes_bands_runs_and_reconstruction():
    config = STFTConfig(512, 128)
    audio = np.random.default_rng(1).normal(scale=0.1, size=(17000, 2))
    p = {"start_hz": 4000, "hole_probability": 0.3, "run_frames": 5, "band_width_hz": 1000, "attenuation_db": 20}
    result = apply_effect("SH", audio, 48000, p, 8, config)
    mask = result.arrays["selected_mask"]
    frequencies = result.arrays["frequencies_hz"]
    assert not mask[:, frequencies < 4000].any()
    np.testing.assert_array_equal(mask[:, :, 0], mask[:, :, 1])
    for start in range(0, len(mask), 5):
        assert np.all(mask[start:start + 5] == mask[start])
    _, _, spectrum = analyze(audio, 48000, config)
    expected = synthesize(spectrum * result.arrays["gain_mask"], 48000, len(audio), config)
    np.testing.assert_array_equal(result.audio, expected)
    other = apply_effect("SH", audio, 48000, p, 9, config)
    assert not np.array_equal(mask, other.arrays["selected_mask"])
    assert abs(float(mask[:, frequencies >= 4000].mean()) - 0.3) < 0.1


def test_un_reduces_tonality_with_bounded_envelope_error():
    sr = 48000
    t = np.arange(sr // 2) / sr
    audio = (0.1 * np.sin(2 * np.pi * 1000 * t) + 0.08 * np.sin(2 * np.pi * 11200 * t)
             + 0.06 * np.sin(2 * np.pi * 14500 * t))[:, None]
    config = STFTConfig()
    result = apply_effect("UN", audio, sr, {"crossover_hz": 7000, "strength": 1}, 7, config)
    stats = measure(audio, result.audio, sr, config, result.arrays, "UN", result.parameters)
    assert result.evidence["transformation_applied"]
    assert stats["reference_tonal_peak_mean_contrast_db_after"] < stats["reference_tonal_peak_mean_contrast_db_before"] - 5
    assert stats["selected_envelope_relative_error"] < 0.8
    frequencies, _, before = analyze(audio, sr, config)
    _, _, after = analyze(result.audio, sr, config)
    low = frequencies < 3000
    assert np.linalg.norm(after[:, low] - before[:, low]) / np.linalg.norm(before[:, low]) < 0.01
    # Independently check that narrow high-frequency lines lose energy concentration.
    high = (frequencies > 7000) & (frequencies < 18000)
    def peak_fraction(z):
        power = np.mean(np.abs(z[4:-4, high]) ** 2, axis=(0, 2))
        return np.sort(power)[-6:].sum() / power.sum()
    assert peak_fraction(after) < 0.4 * peak_fraction(before)
    other = apply_effect("UN", audio, sr, result.parameters, 8, config)
    assert not np.array_equal(result.audio, other.audio)


def test_un_identity_and_no_eligible_tones():
    rng = np.random.default_rng(3)
    audio = rng.normal(scale=0.03, size=(9000, 2))
    result = apply_effect("UN", audio, 48000, {"strength": 0}, 1)
    np.testing.assert_array_equal(result.audio, audio)
    silent = np.zeros((3000, 1))
    result = apply_effect("UN", silent, 44100, {}, 1)
    np.testing.assert_array_equal(result.audio, silent)
    assert not result.evidence["transformation_applied"]


@pytest.mark.parametrize("artifact,parameters,sr", [
    ("PE", {}, 48000), ("TM", {}, 48000),
    ("LP", {"cutoff_hz": 10000}, 16000),
    ("LP", {"cutoff_hz": 21000, "transition_hz": 2000}, 44100),
    ("LP", {"cutoff_hz": float("nan")}, 48000),
    ("SH", {"hole_probability": 1.1}, 48000),
    ("SH", {"run_frames": 1.5}, 48000),
    ("SH", {"band_width_hz": -1}, 48000),
    ("UN", {"strength": -1}, 48000),
    ("UN", {"smoothing_hz": 0}, 48000),
    ("UN", {"unknown": 1}, 48000),
])
def test_parameter_validation(artifact, parameters, sr):
    with pytest.raises(ValueError):
        resolve_parameters(artifact, parameters, sr)


def test_invalid_signal_and_stft():
    with pytest.raises(ValueError, match="NaN"):
        apply_effect("SH", np.array([[np.nan]]), 48000, {}, 1)
    with pytest.raises(ValueError):
        STFTConfig(512, 512)


def test_impractical_filter_is_rejected_before_construction():
    from unittest.mock import patch
    with patch("deepmushra_data.degradations.signal.butter", side_effect=AssertionError("Must not construct a huge filter")):
        with pytest.raises(ValueError, match="exceeds 256"):
            apply_effect("LP", np.zeros((1000, 1)), 48000,
                         {"cutoff_hz": 10000, "transition_hz": 1, "attenuation_db": 120}, 1)
