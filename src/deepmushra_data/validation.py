"""Independent on-disk triplet, manifest, evidence, and split checks."""

from collections import Counter
import json
from pathlib import Path

import numpy as np
import soundfile as sf

from .config import digest, file_checksum, validate_config
from .metadata import read_jsonl, validate_record
from .stft import STFTConfig, analyze


def local_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Dataset path escapes run directory: {relative}")
    return path


def validate_dataset(dataset):
    root = Path(dataset).resolve()
    errors = []
    max_error = 0.0
    records = []
    rates = set()
    group_splits, checksum_splits = {}, {}
    ids = set()
    try:
        config = validate_config(json.loads((root / "resolved_config.json").read_text()))
        records = read_jsonl(root / "metadata.jsonl")
        if not records:
            raise ValueError("Dataset has no examples")
        manifest = read_jsonl(root / "manifest.jsonl")
        if len(manifest) != len(records):
            raise ValueError("Manifest and metadata counts disagree")
        rows = {row["sample_id"]: row for row in manifest}
        if len(rows) != len(manifest):
            raise ValueError("Duplicate manifest sample IDs")
        stft = STFTConfig(**config["stft"])
        for record in records:
            sample_id = record.get("sample_id", "unknown")
            try:
                validate_record(record)
                if sample_id in ids:
                    raise ValueError("Duplicate metadata sample ID")
                ids.add(sample_id)
                if record["provenance"]["configuration_sha256"] != digest(config):
                    raise ValueError("Configuration digest mismatch")
                row = rows[sample_id]
                source = record["source"]
                split = source["split"]
                rates.add(source["sample_rate"])
                for registry, key in ((group_splits, source["source_id"]), (checksum_splits, source["source_checksum_sha256"])):
                    if key in registry and registry[key] != split:
                        raise ValueError("Source-level or exact-duplicate split leakage")
                    registry[key] = split
                metadata_file = local_path(root, row["metadata_path"])
                if json.loads(metadata_file.read_text()) != record:
                    raise ValueError("Per-example metadata differs from metadata.jsonl")
                from .pipeline import _training_row
                if row != _training_row(record):
                    raise ValueError("Training manifest disagrees with metadata")
                audio = {}
                for role, info in record["audio"].items():
                    path = local_path(root, info["path"])
                    if file_checksum(path) != info["sha256"]:
                        raise ValueError(f"{role} audio checksum mismatch")
                    data, sr = sf.read(path, dtype="float64", always_2d=True)
                    if sr != source["sample_rate"] or data.shape != (source["sample_count"], source["channels"]):
                        raise ValueError(f"{role} rate/shape mismatch")
                    if sf.info(path).subtype != info["subtype"] or info["subtype"] != "DOUBLE":
                        raise ValueError(f"{role} storage subtype mismatch")
                    if not np.isfinite(data).all():
                        raise ValueError(f"{role} contains nonfinite samples")
                    if np.max(np.abs(data)) > config["input"]["output_peak_limit"]:
                        raise ValueError(f"{role} peak exceeds configured limit")
                    audio[role] = data
                difference = audio["degraded"] - audio["reference"]
                error = float(np.max(np.abs(difference - audio["residual"])))
                reconstruction_error = float(np.max(np.abs(audio["reference"] + audio["residual"] - audio["degraded"])))
                max_error = max(max_error, error, reconstruction_error)
                if error > 1e-12 or reconstruction_error > 1e-12:
                    raise ValueError("Residual inconsistency or waveform misalignment")
                for role, data in audio.items():
                    expected_rms = float(np.sqrt(np.mean(data ** 2)))
                    if not np.isclose(expected_rms, record["measurements"][f"{role}_rms"], atol=1e-12, rtol=1e-10):
                        raise ValueError(f"{role} stored RMS disagrees with waveform")
                mask = record["degradation"]["mask"]
                mask_path = local_path(root, mask["path"])
                if file_checksum(mask_path) != mask["sha256"]:
                    raise ValueError("Mask checksum mismatch")
                with np.load(mask_path, allow_pickle=False) as arrays:
                    frequencies, times, spectrum = analyze(audio["reference"], source["sample_rate"], stft)
                    selected = arrays["selected_mask"]
                    if selected.dtype != bool or selected.shape != spectrum.shape:
                        raise ValueError("Invalid processing selection mask")
                    if not np.array_equal(frequencies, arrays["frequencies_hz"]) or not np.array_equal(times, arrays["times_s"]):
                        raise ValueError("Mask coordinates disagree with STFT grid")
                    if not np.isclose(selected.mean(), record["measurements"]["affected_tf_ratio"], atol=1e-15, rtol=0):
                        raise ValueError("Mask coverage disagrees with metadata")
                    if any(not np.isfinite(arrays[key]).all() for key in arrays.files):
                        raise ValueError("Nonfinite evidence array")
            except (ValueError, KeyError, TypeError, OSError, RuntimeError) as error:
                errors.append(f"{sample_id}: {error}")
        if set(rows) != ids:
            errors.append("Manifest/metadata sample IDs disagree")
        for split in ("train", "validation", "test"):
            expected = [row for row in manifest if row["split"] == split]
            if read_jsonl(root / f"manifests/{split}.jsonl") != expected:
                errors.append(f"{split} manifest disagrees with combined manifest")
    except (ValueError, KeyError, TypeError, OSError, RuntimeError) as error:
        errors.append(str(error))
    return {"valid": not errors, "errors": errors, "sample_count": len(records),
            "source_group_count": len(group_splits), "sample_rates_hz": sorted(rates),
            "artifact_counts": dict(Counter(r.get("degradation", {}).get("artifact_type") for r in records)),
            "split_counts": dict(Counter(r.get("source", {}).get("split") for r in records)),
            "max_residual_reconstruction_error": max_error,
            "residual_tolerance": 1e-12, "minimum_sample_rate_hz": 44100}
