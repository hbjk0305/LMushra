"""Objective measurements, processing-region projections, and schema checks."""

import json
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter1d

from . import MIN_SAMPLE_RATE, SCHEMA_VERSION, TRAINING_ARTIFACTS
from .degradations import resolve_parameters
from .stft import analyze


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def write_jsonl(path, values):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w") as stream:
        for value in values:
            stream.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def read_jsonl(path):
    with Path(path).open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _runs(selected):
    edges = np.diff(np.r_[False, selected, False].astype(int))
    return list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)))


def processing_regions(arrays, sample_rate, sample_count, config):
    mask = arrays["selected_mask"]
    frequencies, times = arrays["frequencies_hz"], arrays["times_s"]
    duration = sample_count / sample_rate
    half_window = config.n_fft / (2 * sample_rate)
    df = sample_rate / config.n_fft
    time_regions = []
    for start, stop in _runs(mask.any(axis=(1, 2))):
        low = max(0.0, float(times[start]) - half_window)
        high = min(duration, float(times[stop - 1]) + half_window)
        if low < high:
            time_regions.append([low, high])
    frequency_regions = [[max(0.0, float(frequencies[start]) - df / 2),
                          min(sample_rate / 2, float(frequencies[stop - 1]) + df / 2)]
                         for start, stop in _runs(mask.any(axis=(0, 2)))]
    return {"frequency_regions_hz": frequency_regions, "time_regions_s": time_regions,
            "region_interpretation": "projections of processing selections with STFT window support; not audible-event annotations; see full mask for joint structure"}


def measure(reference, degraded, sample_rate, config, arrays, artifact, parameters):
    residual = degraded - reference
    ref_energy, deg_energy, err_energy = [float(np.sum(x ** 2)) for x in (reference, degraded, residual)]
    _, _, rz = analyze(reference, sample_rate, config)
    _, _, dz = analyze(degraded, sample_rate, config)
    rm, dm = np.abs(rz), np.abs(dz)
    selected = arrays["selected_mask"]
    if selected.shape != rz.shape:
        raise ValueError("Mask does not match the analysis grid")
    denominator = float(np.sum(rm ** 2))
    # Fixed declared threshold for observed magnitude changes, not an audibility test.
    floor = max(float(rm.max()) * 1e-4, 1e-15)
    valid = (rm > floor) | (dm > floor)
    delta_db = 20 * np.log10(np.maximum(dm, floor) / np.maximum(rm, floor))
    changed = (np.abs(delta_db) >= 1.0) & valid
    stats = {
        "reference_rms": float(np.sqrt(np.mean(reference ** 2))),
        "degraded_rms": float(np.sqrt(np.mean(degraded ** 2))),
        "residual_rms": float(np.sqrt(np.mean(residual ** 2))),
        "reference_energy": ref_energy, "degraded_energy": deg_energy,
        "residual_energy": err_energy, "net_energy_change": deg_energy - ref_energy,
        "relative_residual_energy": err_energy / ref_energy if ref_energy else None,
        "rms_change_db": 10 * float(np.log10(deg_energy / ref_energy)) if deg_energy and ref_energy else None,
        "reference_peak": float(np.max(np.abs(reference))),
        "degraded_peak": float(np.max(np.abs(degraded))),
        "residual_peak": float(np.max(np.abs(residual))),
        "normalized_spectral_magnitude_error": float(np.sqrt(np.sum((dm - rm) ** 2) / denominator)) if denominator else None,
        "affected_tf_ratio": float(selected.mean()),
        "affected_frame_ratio": float(selected.any(axis=(1, 2)).mean()),
        "measured_changed_tf_ratio": float(changed.mean()),
        "measurement_grid_cells": int(selected.size),
        "measured_change_definition": "magnitude change >=1 dB; floor=max(reference peak STFT magnitude *1e-4,1e-15); all analyzed cells",
        "audibility_interpretation": "none; objective measurements only",
    }
    frequencies = arrays["frequencies_hz"]
    def spectral_ratio(mask):
        before = float(np.sum(rm[:, mask] ** 2))
        after = float(np.sum(dm[:, mask] ** 2))
        return 10 * float(np.log10(after / before)) if before and after else None
    stats["spectral_energy_change_db_by_band"] = {
        f"{lo:g}-{hi:g}Hz": spectral_ratio((frequencies >= lo) & (frequencies < hi))
        for lo, hi in ((0, 4000), (4000, 10000), (10000, sample_rate/2+1))}
    if artifact == "LP":
        stats["stopband_spectral_energy_change_db"] = spectral_ratio(frequencies >= parameters["cutoff_hz"] + parameters["transition_hz"])
        low = frequencies < parameters["cutoff_hz"] * 0.8
        low_energy = float(np.sum(rm[:, low] ** 2))
        stats["passband_magnitude_relative_error"] = float(np.linalg.norm(dm[:, low]-rm[:, low])/np.sqrt(low_energy)) if low_energy else None
    if reference.shape[1] == 2:
        for label, audio in (("reference", reference), ("degraded", degraded)):
            stats[f"{label}_channel_correlation"] = float(np.corrcoef(audio.T)[0, 1]) if np.all(np.std(audio,axis=0)>0) else None
    if artifact == "QN":
        stats["measured_snr_db"] = 10 * float(np.log10(ref_energy / err_energy)) if ref_energy and err_energy else None
        stats["per_channel_snr_db"] = [10 * float(np.log10(np.sum(r**2)/np.sum(e**2))) if np.any(r) and np.any(e) else None for r,e in zip(reference.T,residual.T)]
        stats["stored_noise_residual_max_abs_error"] = float(np.max(np.abs(residual-arrays["added_noise"])))
        sigma = max(parameters["smoothing_hz"]/(sample_rate/config.n_fft),0.5)
        _, _, nz = analyze(residual,sample_rate,config)
        color_r = gaussian_filter1d(np.mean(rm**2,axis=(0,2)),sigma)
        color_n = gaussian_filter1d(np.mean(np.abs(nz)**2,axis=(0,2)),sigma)
        norm = np.linalg.norm(color_r)*np.linalg.norm(color_n)
        stats["smoothed_noise_reference_psd_cosine"] = float(np.dot(color_r,color_n)/norm) if norm else None
    if artifact == "SH":
        eligible = frequencies >= parameters["start_hz"]
        stats["eligible_tf_selection_ratio"] = float(selected[:,eligible].mean())
        before = float(np.sum(rm[selected]**2)); after = float(np.sum(dm[selected]**2))
        stats["selected_cell_energy_change_db_after_istft"] = 10*float(np.log10(after/before)) if before and after else None
        stats["selected_reference_spectral_energy_fraction"] = float(np.sum(rm[selected] ** 2) / denominator) if denominator else None
    if artifact == "UN":
        sigma = max(parameters["smoothing_hz"] / (sample_rate / config.n_fft), 0.5)
        re = np.sqrt(gaussian_filter1d(rm ** 2, sigma=sigma, axis=1, mode="nearest"))
        de = np.sqrt(gaussian_filter1d(dm ** 2, sigma=sigma, axis=1, mode="nearest"))
        norm = float(np.sum(re[selected] ** 2))
        stats["selected_envelope_relative_error"] = float(np.sqrt(np.sum((de[selected] - re[selected]) ** 2) / norm)) if norm else None
        active = selected & (re > floor)
        reference_peaks = active & (rm > re * 10 ** (parameters["tonal_threshold_db"] / 20))
        for label, magnitude, envelope in (("before", rm, re), ("after", dm, de)):
            contrast = 20 * np.log10(np.maximum(magnitude, floor) / np.maximum(envelope, floor))
            stats[f"selected_tonal_contrast_p95_db_{label}"] = float(np.percentile(contrast[active], 95)) if active.any() else None
            stats[f"reference_tonal_peak_mean_contrast_db_{label}"] = float(np.mean(contrast[reference_peaks])) if reference_peaks.any() else None
    return stats


def validate_record(record):
    required = {"schema_version", "sample_id", "source", "audio", "degradation", "measurements", "perceptual_annotation", "descriptions", "provenance"}
    if set(record) != required or record["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Invalid metadata top-level schema")
    source = record["source"]
    for key in ("source_id", "source_file", "source_checksum_sha256", "content_category", "sample_rate", "sample_count", "duration_s", "channels", "split"):
        if key not in source:
            raise ValueError(f"Missing source field {key}")
    if source["sample_rate"] < MIN_SAMPLE_RATE:
        raise ValueError("Metadata violates minimum sample rate of 44100 Hz")
    if source["channels"] not in (1, 2) or source["sample_count"] <= 0:
        raise ValueError("Invalid source shape")
    if not np.isclose(source["duration_s"], source["sample_count"] / source["sample_rate"], atol=1e-12, rtol=0):
        raise ValueError("Source duration does not match sample count/rate")
    if source["split"] not in ("train", "validation", "test"):
        raise ValueError("Invalid split")
    degradation = record["degradation"]
    artifact = degradation["artifact_type"]
    if artifact not in (*TRAINING_ARTIFACTS, "IDENTITY"):
        raise ValueError("Held-out or unsupported artifact in generated dataset")
    if artifact != "IDENTITY":
        resolved = resolve_parameters(artifact, degradation["parameters"], source["sample_rate"])
        if resolved != degradation["parameters"]:
            raise ValueError("Metadata parameters must include resolved defaults")
    if degradation["parameter_severity"]["status"] != "provisional_parameter_based":
        raise ValueError("Parameter severity must be marked provisional")
    if set(record["audio"]) != {"reference", "degraded", "residual"}:
        raise ValueError("Metadata must contain exactly one audio triplet")
    for info in record["audio"].values():
        if not isinstance(info.get("path"), str) or not isinstance(info.get("sha256"), str):
            raise ValueError("Invalid audio reference")
    annotation = record["perceptual_annotation"]
    if annotation["status"] == "unverified":
        if any(annotation[key] is not None for key in ("audibility", "perceived_severity", "quality_category", "natural_language_description")):
            raise ValueError("Unverified perceptual labels must be null")
    else:
        raise ValueError("This generator only emits unverified perceptual annotations")
    if record["descriptions"]["perceptual_candidate_status"] != "unverified":
        raise ValueError("Perceptual candidates must be unverified")
    json.dumps(record, allow_nan=False)
