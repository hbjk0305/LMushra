"""Scientific audit of the existing artifact operators at 44.1 kHz mono.

This program imports production operators unchanged. Its inputs are analytical
signals and the independent licensed source manifest. ODAQ inputs are unused.
"""
import argparse
from collections import defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
from scipy import signal
from scipy.ndimage import gaussian_filter1d
import soundfile as sf

from deepmushra_data.audioio import write_wav
from deepmushra_data.config import file_checksum, load_config
from deepmushra_data.degradations import apply_effect
from deepmushra_data.metadata import measure, read_jsonl, write_json, write_jsonl
from deepmushra_data.pipeline import generate_dataset
from deepmushra_data.stft import STFTConfig, analyze, synthesize

SR = 44100
STFT = STFTConfig()
SEEDS = [901, 902, 903]
RECIPES = {
    "LP": [{"cutoff_hz": cutoff} for cutoff in [16000, 13000, 10000, 7000, 5000]],
    "SH": [{"hole_probability": probability, "run_frames": 4} for probability in [0, .1, .3, .5, .7, 1]],
    "UN": [{"crossover_hz": 7000, "strength": strength} for strength in [0, .25, .5, .75, 1]],
    "QN": [{"snr_db": snr} for snr in [50, 40, 30, 20, 10]],
}


def energy(audio):
    return float(np.sum(np.abs(audio) ** 2))


def relative(a, b):
    denominator = energy(b)
    return float(np.sqrt(energy(a) / denominator)) if denominator else None


def flatness(power):
    if not np.any(power):
        return None
    floor = float(np.max(power)) * 1e-12
    return float(np.exp(np.mean(np.log(np.maximum(power, floor)))) / np.mean(power))


def cosine(a, b):
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denominator) if denominator else None


def sources(output):
    directory = output / "inputs"
    directory.mkdir()
    t = np.arange(SR) / SR
    rng = np.random.default_rng(732)
    white = rng.standard_normal(SR)
    frequencies = np.fft.rfftfreq(SR, 1 / SR)
    pink_spectrum = np.fft.rfft(white) / np.sqrt(np.maximum(frequencies, 20))
    pink = np.fft.irfft(pink_spectrum, n=SR)
    harmonic = sum(np.cos(2 * np.pi * 400 * k * t + .1 * k) / k for k in range(1, 46))
    impulse = np.zeros(SR)
    onset, offset = SR // 3, 2 * SR // 3
    impulse[onset] = 1
    burst = np.zeros(SR)
    burst[onset:offset] = .1 * np.cos(2 * np.pi * 11200 * t[:offset-onset]) + .05 * np.cos(2 * np.pi * 1000 * t[:offset-onset])
    transient = np.zeros(SR)
    for start in [4410, 15435, 28665]:
        count = min(SR - start, 8000)
        transient[start:start+count] += rng.standard_normal(count) * np.exp(-np.arange(count) / 220)
    switching = np.zeros(SR)
    first = (t >= .1) & (t < .3)
    second = (t >= .6) & (t < .8)
    switching[first] = np.cos(2 * np.pi * 1000 * t[first])
    switching[second] = np.cos(2 * np.pi * 11200 * t[second])
    fixtures = {
        "sine_1k": np.sin(2 * np.pi * 1000 * t),
        "sine_11200": np.sin(2 * np.pi * 11200 * t),
        "harmonic": harmonic, "white_noise": white, "pink_noise": pink,
        "impulse": impulse, "tonal_burst": burst, "transient_train": transient,
        "switching_tones": switching, "silence": np.zeros(SR),
    }
    result = []
    for name, mono in fixtures.items():
        peak = float(np.max(np.abs(mono)))
        audio = mono[:, None] * (.2 / peak if peak else 1)
        entry = {"source_id": name, "source_file": f"inputs/{name}.wav", "content_category": "analytical",
                 "is_functional_test_signal": True, "source_provenance": {"license": "Project-generated analytical fixture", "seed": 732}}
        if name == "tonal_burst":
            entry.update(onset_sample=onset, offset_sample=offset)
        if name == "impulse":
            entry.update(onset_sample=onset, offset_sample=onset+1)
        write_wav(directory / f"{name}.wav", audio, SR)
        result.append((entry, audio))
    for index, row in enumerate(read_jsonl("data/phase1_sources/sources.jsonl")):
        original, sr = sf.read(Path("data/phase1_sources") / row["source_file"], always_2d=True)
        if sr != SR:
            raise ValueError("Unexpected source rate")
        audio = np.mean(original[:4*SR], axis=1, keepdims=True)
        peak = float(np.max(np.abs(audio)))
        gain = min(1., .25 / peak) if peak else 1.
        audio *= gain
        name = f"recording_{index+1:02d}"
        write_wav(directory / f"{name}.wav", audio, SR)
        entry = deepcopy(row)
        entry["source_file"] = f"inputs/{name}.wav"
        entry["source_provenance"].update(audit_crop_offset_s=0, audit_duration_s=4,
            mono_conversion="Arithmetic channel mean before artifact generation",
            audit_shared_gain=gain, stereo_excerpt_sha256=file_checksum(Path("data/phase1_sources") / row["source_file"]))
        result.append((entry, audio))
    write_jsonl(output / "sources.jsonl", [entry for entry, audio in result])
    return result


def metrics(x, result, entry, config=STFT):
    y = result.audio
    residual = y - x
    stats = measure(x, y, SR, config, result.arrays, entry["artifact"], result.parameters)
    f, times, rz = analyze(x, SR, config)
    _, _, dz = analyze(y, SR, config)
    _, _, ez = analyze(residual, SR, config)
    rm, dm = np.abs(rz), np.abs(dz)
    valid_times = (times >= .08) & (times <= len(x)/SR-.08)
    high = (f >= 7000) & (f <= 20000)
    reference_power = np.mean(rm[valid_times][:, high, 0] ** 2, axis=0)
    degraded_power = np.mean(dm[valid_times][:, high, 0] ** 2, axis=0)
    stats["highband_psd_flatness_reference"] = flatness(reference_power)
    stats["highband_psd_flatness_degraded"] = flatness(degraded_power)
    sigma = 500 / (SR/config.n_fft)
    re = np.sqrt(gaussian_filter1d(rm**2, sigma, axis=1, mode="nearest"))
    de = np.sqrt(gaussian_filter1d(dm**2, sigma, axis=1, mode="nearest"))
    floor = max(float(rm.max()) * 1e-6, 1e-15)
    peaks = (rm > re * 10**(6/20)) & (rm > floor)
    peaks[:, f < 7000] = False
    peaks[~valid_times] = False
    contrast_ref = 20*np.log10(np.maximum(rm, floor)/np.maximum(re, floor))
    contrast_deg = 20*np.log10(np.maximum(dm, floor)/np.maximum(de, floor))
    stats["fixed_reference_peak_contrast_drop_db"] = float(np.mean((contrast_ref-contrast_deg)[peaks])) if peaks.any() else None
    stats["reference_peak_cells"] = int(peaks.sum())
    active = (rm > max(float(rm.max()) * 1e-3, 1e-15))
    observed_holes = active & (dm < rm * 10**(-6/20))
    stats["active_cells_attenuated_over6db_fraction"] = float(observed_holes.sum()/active.sum()) if active.any() else None
    stats["max_residual_sample_step"] = float(np.max(np.abs(np.diff(residual[:, 0]))))
    stats["net_removed_waveform_energy_fraction"] = (energy(x)-energy(y))/energy(x) if energy(x) else None
    stats["output_shape"] = list(y.shape)
    stats["output_finite"] = bool(np.isfinite(y).all())
    stats["output_over_peak_limit"] = bool(np.max(np.abs(y)) > .999)
    if "onset_sample" in entry:
        onset, offset = entry["onset_sample"], entry["offset_sample"]
        threshold = max(float(np.max(np.abs(residual)))*1e-4, 1e-15)
        before = np.flatnonzero(np.abs(residual[:onset, 0]) > threshold)
        after = np.flatnonzero(np.abs(residual[offset:, 0]) > threshold)
        stats.update(pre_energy_fraction=energy(residual[:onset])/energy(residual) if energy(residual) else 0.,
                     pre_extent_ms=(onset-int(before[0]))/SR*1000 if len(before) else 0.,
                     post_energy_fraction=energy(residual[offset:])/energy(residual) if energy(residual) else 0.,
                     post_extent_ms=(int(after[-1])+1)/SR*1000 if len(after) else 0.,
                     support_threshold=threshold)
    if entry["artifact"] == "LP":
        cutoff = result.parameters["cutoff_hz"]
        stats["residual_spectral_energy_below_cutoff_fraction"] = float(np.sum(np.abs(ez[:, f < cutoff])**2)/np.sum(np.abs(ez)**2)) if np.any(residual) else None
    if entry["artifact"] == "SH":
        modified = rz * result.arrays["gain_mask"]
        stats["modified_stft_consistency_error"] = relative(dz-modified, modified)
        stats["gain_mask_reconstruction_max_error"] = float(np.max(np.abs(synthesize(modified, SR, len(x), config)-y)))
    if entry["source_id"] == "sine_11200":
        t = np.arange(len(x))/SR
        part = (t >= .1) & (t < .9)
        basis = np.exp(-2j*np.pi*11200*t[part])
        stats["original_tone_complex_gain_abs"] = float(abs(basis@y[part, 0])/abs(basis@x[part, 0]))
    return stats


def lp_responses(output):
    impulse = np.zeros((SR, 1))
    impulse[SR//3] = .2
    rows = []
    fig_data = []
    for design in ["butterworth", "elliptic"]:
        for cutoff in [5000, 7000, 10000, 13000, 16000]:
            result = apply_effect("LP", impulse, SR, {"cutoff_hz": cutoff, "filter_design": design}, SEEDS[0])
            sos = np.asarray(result.evidence["sos_coefficients"])
            f, response = signal.sosfreqz(sos, worN=32768, fs=SR)
            db = 20*np.log10(np.maximum(abs(response), 1e-15))
            _, edge = signal.sosfreqz(sos, worN=np.array([cutoff, cutoff+1500]), fs=SR)
            delay = -np.gradient(np.unwrap(np.angle(response)), 2*np.pi*f)*1000
            passband = (f > 100) & (f < cutoff)
            impulse_fft = np.fft.rfft(result.audio[SR//3:, 0]/.2, n=65536)
            _, expected = signal.sosfreqz(sos, worN=np.fft.rfftfreq(65536, 1/SR), fs=SR)
            rows.append({"design": design, "cutoff_hz": cutoff, "order": result.evidence["filter_order"],
                "passband_loss_db": result.evidence["response_passband_loss_max_db"],
                "stopband_min_attenuation_db": result.evidence["response_stopband_attenuation_min_db"],
                "edge_loss_db": float(-20*np.log10(abs(edge[0]))),
                "first_minus3db_frequency_hz": float(f[np.flatnonzero(db <= -3)[0]]),
                "group_delay_median_ms": float(np.median(delay[passband])),
                "group_delay_max_ms": float(np.max(delay[passband])),
                "impulse_frequency_response_max_abs_error": float(np.max(np.abs(impulse_fft-expected)))})
            fig_data.append((design, cutoff, f, db, delay))
    write_json(output/"lp_response.json", rows)
    return rows, fig_data


def extra_experiments(output, data):
    lookup = {entry["source_id"]: audio for entry, audio in data}
    x = lookup["sine_11200"]
    un = apply_effect("UN", x, SR, {"strength": 1}, SEEDS[0])
    qn = apply_effect("QN", x, SR, {"snr_db": 20}, SEEDS[0])
    rng = np.random.default_rng(991)
    noise = rng.standard_normal(x.shape)
    spectrum = np.fft.rfft(noise[:, 0])
    frequencies = np.fft.rfftfreq(len(x), 1/SR)
    spectrum[frequencies < 7000] = 0
    noise[:, 0] = np.fft.irfft(spectrum, n=len(x))
    noise *= np.sqrt(energy(un.audio-x)/energy(noise))
    t = np.arange(len(x))/SR
    part = (t >= .1) & (t < .9)
    basis = np.exp(-2j*np.pi*11200*t[part])
    comparisons = []
    conditions = [("reference", x), ("UN_strength1", un.audio), ("QN_snr20", qn.audio),
                  ("additive_matched_UN_residual_energy", x+noise)]
    render_peak = max(float(np.max(np.abs(y))) for label, y in conditions)
    playback_gain = min(1., .95/render_peak)
    for label, y in conditions:
        _, _, z = analyze(y, SR, STFT)
        high = (un.arrays["frequencies_hz"] >= 7000) & (un.arrays["frequencies_hz"] <= 20000)
        power = np.mean(np.abs(z[4:-4, high, 0])**2, axis=0)
        comparisons.append({"condition": label, "shared_playback_gain": playback_gain, "tone_gain_abs": float(abs(basis@y[part,0])/abs(basis@x[part,0])),
            "highband_psd_flatness": flatness(power), "relative_residual_energy": energy(y-x)/energy(x)})
        write_wav(output/"examples"/f"UN_additive_comparison_{label}.wav", y*playback_gain, SR)
    switching = lookup["switching_tones"]
    q = apply_effect("QN", switching, SR, {"snr_db": 20}, SEEDS[0])
    first = q.arrays["added_noise"][round(.12*SR):round(.28*SR), 0]
    frequencies = np.fft.rfftfreq(len(first), 1/SR)
    power = np.abs(np.fft.rfft(first))**2
    high_noise_fraction = float(power[frequencies > 7000].sum()/power.sum())
    gap = q.arrays["added_noise"][round(.3*SR):round(.6*SR)]
    localization = {"high_frequency_noise_fraction_during_1k_tone": high_noise_fraction,
        "noise_energy_fraction_in_exact_silent_gap": energy(gap)/energy(q.arrays["added_noise"]),
        "initial_noise_max_abs_before_first_onset": float(np.max(np.abs(q.arrays["added_noise"][:4410])))}
    window_rows = []
    burst_entry = next(entry for entry, x in data if entry["source_id"] == "tonal_burst")
    for size in [1024, 2048, 4096]:
        config = STFTConfig(size, size//4)
        for artifact, params in [("SH", {"hole_probability": .7}), ("UN", {"strength": 1})]:
            result = apply_effect(artifact, lookup["tonal_burst"], SR, params, SEEDS[0], config)
            stats = metrics(lookup["tonal_burst"], result, {**burst_entry, "artifact": artifact}, config)
            window_rows.append({"artifact": artifact, "n_fft": size, "window_ms": size/SR*1000,
                "pre_extent_ms": stats["pre_extent_ms"], "pre_energy_fraction": stats["pre_energy_fraction"]})
    write_json(output/"supplementary.json", {"UN_additive_comparison": comparisons,
        "QN_localization": localization, "window_ablation": window_rows})
    return comparisons, localization, window_rows


def monotonicity(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["source_id"], row["artifact"], row["seed"])].append(row)
    results = []
    keys = {"LP": "normalized_spectral_magnitude_error", "SH": "net_removed_waveform_energy_fraction",
            "UN": "fixed_reference_peak_contrast_drop_db", "QN": "relative_residual_energy"}
    for (source, artifact, seed), group in groups.items():
        group.sort(key=lambda row: row["level_index"])
        metrics_to_test = [keys[artifact], "relative_residual_energy"]
        if artifact == "SH":
            metrics_to_test.append("eligible_tf_selection_ratio")
        for metric in dict.fromkeys(metrics_to_test):
            values = [row["measurements"].get(metric) for row in group]
            if any(value is None for value in values):
                status = "undefined"
                violations = []
            else:
                scale = max(max(abs(value) for value in values), 1e-12)
                tolerance = max(1e-12, 1e-6*scale)
                violations = [index for index in range(len(values)-1) if values[index+1] < values[index]-tolerance]
                status = "nonmonotonic" if violations else "flat" if max(values)-min(values) <= tolerance else "monotonic"
            results.append({"source_id": source, "artifact": artifact, "seed": seed,
                "metric": metric, "values": values, "status": status, "decreasing_steps": violations})
    return results


def figures(output, rows, responses, comparisons, window_rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    destination = output/"figures"
    destination.mkdir()
    for artifact in RECIPES:
        candidates = [row for row in rows if row["artifact"] == artifact]
        primary = {"LP": "normalized_spectral_magnitude_error", "SH": "eligible_tf_selection_ratio",
                   "UN": "fixed_reference_peak_contrast_drop_db", "QN": "measured_snr_db"}[artifact]
        fig, axes = plt.subplots(1, 2, figsize=(12, 4), constrained_layout=True)
        for source in sorted({row["source_id"] for row in candidates}):
            selected = sorted([row for row in candidates if row["source_id"] == source and row["seed"] == SEEDS[0]], key=lambda row: row["level_index"])
            if source == "silence":
                continue
            values = [row["measurements"].get(primary) for row in selected]
            axes[0].plot([row["level_index"] for row in selected], [np.nan if value is None else value for value in values], "o-", lw=.7, label=source.split(":")[-1][:24])
            axes[1].plot([row["level_index"] for row in selected], [row["measurements"]["relative_residual_energy"] for row in selected], "o-", lw=.7)
        axes[0].set(xlabel="Increasing nominal processing strength (setting index)", ylabel=primary)
        axes[1].set(xlabel="Increasing nominal processing strength (setting index)", ylabel="Residual / reference energy")
        axes[0].legend(fontsize=5, ncol=2)
        fig.suptitle(f"{artifact}: 44.1 kHz mono, paired random seed {SEEDS[0]}")
        fig.savefig(destination/f"{artifact}_control.png", dpi=160)
        plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), constrained_layout=True)
    for design, cutoff, f, db, delay in responses:
        if design == "butterworth":
            axes[0].plot(f/1000, db, label=f"{cutoff/1000:g} kHz")
            keep = f < cutoff
            axes[1].plot(f[keep]/1000, delay[keep])
    axes[0].set(xlabel="Frequency (kHz)", ylabel="Gain (dB)", ylim=(-120, 2))
    axes[1].set(xlabel="Passband frequency (kHz)", ylabel="Group delay (ms)")
    axes[0].legend()
    fig.savefig(destination/"LP_response_phase.png", dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4), constrained_layout=True)
    ax.bar([row["condition"].replace("_", "\n") for row in comparisons], [row["tone_gain_abs"] for row in comparisons])
    ax.set(ylabel="Retained 11.2-kHz sinusoid amplitude / reference", title="Tonal replacement and additive-noise controls")
    fig.savefig(destination/"UN_vs_addition.png", dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4), constrained_layout=True)
    for artifact in ["SH", "UN"]:
        group = [row for row in window_rows if row["artifact"] == artifact]
        ax.plot([row["window_ms"] for row in group], [row["pre_extent_ms"] for row in group], "o-", label=artifact)
    ax.set(xlabel="STFT window length (ms)", ylabel="Pre-onset residual extent (ms)", title="Relative -80 dB amplitude threshold; analytical burst")
    ax.legend()
    fig.savefig(destination/"window_temporal_support.png", dpi=160)
    plt.close(fig)
    for artifact in RECIPES:
        source = "tonal_burst"
        record = next(row for row in rows if row["source_id"] == source and row["artifact"] == artifact and row["level_index"] == len(RECIPES[artifact])-1 and row["seed"] == SEEDS[0])
        fig, axes = plt.subplots(3, 2, figsize=(11, 8), constrained_layout=True)
        for index, role in enumerate(["reference", "degraded", "residual"]):
            path = output/"inputs"/f"{source}.wav" if role == "reference" else output/record["audio"][role]
            audio, sr = sf.read(path, always_2d=True)
            t = np.arange(len(audio))/sr
            axes[index,0].plot(t, audio[:,0], lw=.4)
            axes[index,0].set(xlabel="Time (s)", ylabel="Amplitude", title=role)
            f, times, z = analyze(audio, sr, STFT)
            image = axes[index,1].pcolormesh(times, f/1000, 20*np.log10(np.maximum(np.abs(z[:,:,0]), 1e-8)).T,
                shading="auto", cmap="magma", vmin=-100, vmax=-10)
            axes[index,1].set(xlabel="Time (s)", ylabel="Frequency (kHz)", title=role)
        fig.colorbar(image, ax=axes[:,1], label="STFT magnitude (dBFS)")
        fig.suptitle(f"{artifact}: analytical burst, strongest tested setting")
        fig.savefig(destination/f"{artifact}_burst_triplet.png", dpi=130)
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if (output/"measurements.jsonl").exists():
        raise ValueError("Audit measurements already exist; choose a fresh output")
    output.mkdir(parents=True, exist_ok=True)
    (output/"examples").mkdir()
    write_json(output/"experiment_config.json", {"sample_rate": SR, "channels": 1,
        "stft": STFT.metadata(), "seeds": SEEDS, "recipes": RECIPES,
        "mono_preprocessing": "mean of native channels before processing; real clips first 4s of independent 8s excerpt",
        "extent_threshold": "max(residual waveform peak *1e-4,1e-15); objective support only",
        "audit_script_sha256": file_checksum(__file__)})
    data = sources(output)
    rows = []
    assertions = []
    errors = []
    roundtrip_max = 0.
    with (output/"measurements.jsonl").open("w") as stream:
        for entry, x in data:
            _, _, z = analyze(x, SR, STFT)
            restored = synthesize(z, SR, len(x), STFT)
            roundtrip_max = max(roundtrip_max, float(np.max(np.abs(restored-x))))
            for artifact, settings in RECIPES.items():
                for level, parameters in enumerate(settings):
                    for seed in SEEDS:
                        try:
                            result = apply_effect(artifact, x, SR, parameters, seed)
                            stats = metrics(x, result, {**entry, "artifact": artifact})
                            assert result.audio.shape == x.shape and np.isfinite(result.audio).all()
                            if artifact == "QN" and energy(x):
                                assert abs(stats["measured_snr_db"]-parameters["snr_db"]) < 1e-10
                                assert stats["stored_noise_residual_max_abs_error"] < 1e-15
                            if artifact == "SH":
                                assert stats["gain_mask_reconstruction_max_error"] < 1e-12
                            if "onset_sample" in entry and artifact in ["LP", "QN"]:
                                assert stats["pre_energy_fraction"] == 0
                            row = {"source_id": entry["source_id"], "category": entry["content_category"],
                                   "artifact": artifact, "level_index": level, "seed": seed,
                                   "parameters": result.parameters, "measurements": stats}
                            if seed == SEEDS[0] and level == len(settings)-1:
                                name = hashlib.sha256(entry["source_id"].encode()).hexdigest()[:12]
                                base = f"examples/{name}_{artifact}"
                                write_wav(output/f"{base}_degraded.wav", result.audio, SR)
                                saved, rate = sf.read(output/f"{base}_degraded.wav", always_2d=True)
                                reference, ref_rate = sf.read(output/entry["source_file"], always_2d=True)
                                write_wav(output/f"{base}_residual.wav", saved-reference, SR)
                                residual, residual_rate = sf.read(output/f"{base}_residual.wav", always_2d=True)
                                assert rate == ref_rate == residual_rate == SR
                                np.testing.assert_array_equal(residual, saved-reference)
                                repeat = apply_effect(artifact, x, SR, parameters, seed)
                                np.testing.assert_array_equal(result.audio, repeat.audio)
                                np.savez_compressed(output/f"{base}_evidence.npz", **result.arrays)
                                row["audio"] = {"reference": entry["source_file"], "degraded": f"{base}_degraded.wav", "residual": f"{base}_residual.wav"}
                            stream.write(json.dumps(row, allow_nan=False)+"\n")
                            rows.append(row)
                            assertions.append(True)
                        except Exception as error:
                            failure = {"source": entry["source_id"], "artifact": artifact, "level": level,
                                       "seed": seed, "exception": type(error).__name__, "message": str(error)}
                            errors.append(failure)
                            print("FAILED", json.dumps(failure), flush=True)
            stream.flush()
            print("Finished", entry["source_id"], len(rows), "conditions", flush=True)
    response_rows, responses = lp_responses(output)
    comparisons, localization, windows = extra_experiments(output, data)
    monotone = monotonicity(rows)
    write_json(output/"monotonicity.json", monotone)
    figures(output, rows, responses, comparisons, windows)
    # Exercise the normal saved-dataset entry point using real mono references.
    real_entries = [entry for entry, x in data if not entry.get("is_functional_test_signal")]
    write_jsonl(output/"mono_real_sources.jsonl", real_entries)
    config = load_config("configs/phase1.yaml")
    config["input"].update(sample_rates=[SR], channels=[1], min_duration_s=4, max_duration_s=4, source_peak_limit=.25)
    write_json(output/"mono_pipeline_config.json", config)
    pipeline = generate_dataset(config, output/"mono_pipeline", manifest=output/"mono_real_sources.jsonl", diagnostics=False)
    statuses = defaultdict(lambda: defaultdict(int))
    for row in monotone:
        statuses[f"{row['artifact']}:{row['metric']}"][row["status"]] += 1
    write_json(output/"summary.json", {"conditions": len(rows), "source_count": len(data),
        "analytical_sources": len(data)-len(real_entries), "real_sources": len(real_entries),
        "runtime_assertions_passed": len(assertions), "failed_conditions": errors,
        "max_stft_roundtrip_error": roundtrip_max, "monotonicity": dict(statuses),
        "output_peak_exceedances": sum(row["measurements"]["output_over_peak_limit"] for row in rows),
        "pipeline_validation": pipeline, "lp_responses": response_rows,
        "UN_additive_comparison": comparisons, "QN_localization": localization, "window_ablation": windows,
        "figure_count": len(list((output/"figures").glob("*.png"))),
        "source_file_hashes": {entry["source_file"]: file_checksum(output/entry["source_file"]) for entry, x in data}})
    print("AUDIT COMPLETE", len(rows), "conditions", len(errors), "failed", flush=True)


if __name__ == "__main__":
    main()
