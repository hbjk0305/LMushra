"""Small reproducible batches with atomic publication of a validated output directory."""

from collections import Counter
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile

import numpy as np
import soundfile as sf

from . import SCHEMA_VERSION, __version__
from .audioio import write_wav
from .config import digest, file_checksum, recipes, stable_seed, validate_config
from .degradations import ALGORITHM_VERSION, EffectResult, apply_effect, resolve_parameters
from .descriptions import describe
from .metadata import measure, processing_regions, validate_record, write_json, write_jsonl
from .sources import assign_splits, discover_sources, read_source
from .stft import STFTConfig, analyze


def _revision():
    package = Path(__file__).resolve().parent
    source_hash = digest({p.name: file_checksum(p) for p in sorted(package.glob("*.py"))})
    try:
        repo = Path(__file__).resolve().parents[2]
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=repo, text=True))
        return {"git_revision": revision, "git_dirty": dirty, "generator_source_sha256": source_hash}
    except (OSError, subprocess.CalledProcessError):
        return {"git_revision": None, "git_dirty": None, "generator_source_sha256": source_hash}


def _environment():
    return {"python": platform.python_version(),
            "packages": {name: importlib.metadata.version(name) for name in
                         ("numpy", "scipy", "soundfile", "PyYAML", "matplotlib")},
            "libsndfile": sf.__libsndfile_version__}


def create_demo_sources(root, seed, duration_s=4.0):
    """Analytical test signals only; no perceptual representativeness claim."""
    root = Path(root)
    source_dir = root / "demo_sources"
    source_dir.mkdir(parents=True)
    entries = []
    for sr in (44100, 48000):
        n = round(sr * duration_s)
        t = np.arange(n) / sr
        for kind in ("tonal", "transient", "broadband"):
            rng = np.random.default_rng(stable_seed(seed, sr, kind, "demo_source"))
            if kind == "tonal":
                frequencies = [440, 880, 1760, 3520, 7040, 11200, 14520, 17300]
                mono = sum(np.sin(2 * np.pi * f * t + 0.1 * i) / (1 + 0.15 * i) for i, f in enumerate(frequencies))
                mono *= 0.8 + 0.2 * np.sin(2 * np.pi * 1.7 * t)
            elif kind == "transient":
                mono = np.zeros(n)
                for onset in (0.4, 1.1, 1.8, 2.5, 3.2):
                    start = round(onset * sr)
                    length = min(round(0.13 * sr), n - start)
                    if length > 0:
                        mono[start:start + length] += rng.standard_normal(length) * np.exp(-np.arange(length) / (0.015 * sr))
                mono += 0.03 * np.sin(2 * np.pi * 7300 * t)
            else:
                mono = rng.standard_normal(n) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.8 * t) ** 2)
            # Half-cosine ramps avoid start/end discontinuities in the tonal/noise fixtures.
            ramp = min(round(0.02 * sr), n // 2)
            fade = np.sin(np.linspace(0, np.pi / 2, ramp)) ** 2
            mono[:ramp] *= fade
            mono[-ramp:] *= fade[::-1]
            mono *= 0.35 / max(float(np.max(np.abs(mono))), 1e-15)
            channels = 1 if (sr == 44100 and kind != "transient") or (sr == 48000 and kind == "transient") else 2
            audio = mono[:, None] if channels == 1 else np.column_stack((mono, 0.8 * mono + 0.05 * np.roll(mono, 7)))
            name = f"{kind}_{sr}_{channels}ch"
            path = source_dir / f"{name}.wav"
            write_wav(path, audio, sr)
            entries.append({"source_file": f"demo_sources/{name}.wav", "source_id": name,
                            "content_category": f"functional_test_{kind}", "is_functional_test_signal": True})
    manifest = root / "demo_sources.jsonl"
    write_jsonl(manifest, entries)
    return manifest


def _identity(audio, sr, stft):
    frequencies, times, z = analyze(audio, sr, stft)
    return EffectResult(audio.copy(), {}, {
        "algorithm_version": ALGORITHM_VERSION, "stft": stft.metadata(),
        "mask_kind": "identity_no_selection", "transformation_applied": False,
        "coverage_denominator": "all analyzed time-frequency-channel cells, including boundary padding",
        "perceptual_equivalence_to_odaq": "not_applicable",
    }, {"selected_mask": np.zeros(z.shape, dtype=bool), "frequencies_hz": frequencies, "times_s": times})


def generate_dataset(config, output, input_dir=None, manifest=None, demo=False, diagnostics=True):
    config = validate_config(config)
    output = Path(output).resolve()
    if output.exists():
        raise ValueError(f"Output already exists; choose a new run directory: {output}")
    if demo and (input_dir is not None or manifest is not None):
        raise ValueError("demo cannot be combined with external inputs")
    if not demo and (input_dir is None) == (manifest is None):
        raise ValueError("Provide exactly one of input_dir or manifest")
    if not demo:
        sources = discover_sources(input_dir, manifest, config["input"])
        split_map = assign_splits(sources, config["splits"], config["seed"])
        _preflight_recipes(config, sources)
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.building-", dir=output.parent))
    try:
        if demo:
            manifest = create_demo_sources(stage, config["seed"])
            sources = discover_sources(manifest=manifest, policy=config["input"])
            split_map = assign_splits(sources, config["splits"], config["seed"])
            _preflight_recipes(config, sources)
        write_json(stage / "resolved_config.json", config)
        records = _generate(stage, config, sources, split_map)
        write_jsonl(stage / "metadata.jsonl", records)
        manifests = [_training_row(record) for record in records]
        write_jsonl(stage / "manifest.jsonl", manifests)
        for split in ("train", "validation", "test"):
            write_jsonl(stage / f"manifests/{split}.jsonl", [r for r in manifests if r["split"] == split])
        write_json(stage / "run.json", {
            "schema_version": SCHEMA_VERSION, "generator_version": __version__,
            "configuration_sha256": digest(config), "environment": _environment(), **_revision(),
            "functional_test_material_only": demo,
            "source_groups": len(split_map), "samples": len(records),
            "artifact_counts": dict(Counter(r["degradation"]["artifact_type"] for r in records)),
            "held_out_training_artifacts": ["PE", "TM"],
            "source_split_map": split_map,
        })
        from .validation import validate_dataset
        report = validate_dataset(stage)
        write_json(stage / "validation_summary.json", report)
        if not report["valid"]:
            raise ValueError(f"Generated dataset failed validation: {report['errors'][:3]}")
        if diagnostics:
            from .diagnostics import plot_dataset
            plot_dataset(stage)
        # rename publishes only a fully validated run; the staging directory is ours.
        if output.exists():
            raise ValueError(f"Output appeared during generation; refusing overwrite: {output}")
        stage.rename(output)
        return report
    except BaseException:
        shutil.rmtree(stage)
        raise


def _preflight_recipes(config, sources):
    for source in sources:
        for artifact in sorted(config["artifacts"]):
            key = [source["source_id"], source["checksum"]]
            for _, parameters, _ in recipes(config, artifact, key):
                resolve_parameters(artifact, parameters, source["sample_rate"])


def _generate(root, config, sources, split_map):
    stft = STFTConfig(**config["stft"])
    config_hash = digest(config)
    revision = _revision()
    records = []
    for source in sources:
        audio, sr = read_source(source["path"], config["input"])
        peak = float(np.max(np.abs(audio)))
        gain = min(1.0, config["input"]["source_peak_limit"] / peak) if peak else 1.0
        reference = audio * gain
        ref_rel = f"audio/reference/{source['checksum']}.wav"
        ref_path = root / ref_rel
        ref_path.parent.mkdir(parents=True, exist_ok=True)
        write_wav(ref_path, reference, sr)
        reference, _ = sf.read(ref_path, dtype="float64", always_2d=True)
        variants = [(a, i, p, tier) for a in sorted(config["artifacts"])
                    for i, p, tier in recipes(config, a, [source["source_id"], source["checksum"]])]
        if config["include_identity"]:
            variants.append(("IDENTITY", 0, {}, "unspecified"))
        for artifact, index, parameters, tier in variants:
            effect_seed = stable_seed(config["seed"], source["source_id"], source["checksum"], artifact, index, parameters)
            sample_id = digest([__version__, source["source_id"], source["checksum"], config_hash, artifact, index])[:24]
            effect = _identity(reference, sr, stft) if artifact == "IDENTITY" else apply_effect(artifact, reference, sr, parameters, effect_seed, stft)
            audio_rel = {"reference": ref_rel, "degraded": f"audio/{sample_id}/degraded.wav",
                         "residual": f"audio/{sample_id}/residual.wav"}
            (root / audio_rel["degraded"]).parent.mkdir(parents=True)
            if np.max(np.abs(effect.audio)) > config["input"]["output_peak_limit"]:
                raise ValueError(f"{sample_id} degraded peak exceeds output_peak_limit; lower source_peak_limit")
            write_wav(root / audio_rel["degraded"], effect.audio, sr)
            degraded, _ = sf.read(root / audio_rel["degraded"], dtype="float64", always_2d=True)
            # Compute from the exact on-disk waveforms, never from an unsaved intermediate.
            saved_reference, _ = sf.read(ref_path, dtype="float64", always_2d=True)
            residual = degraded - saved_reference
            if np.max(np.abs(residual)) > config["input"]["output_peak_limit"]:
                raise ValueError(f"{sample_id} residual peak exceeds output_peak_limit; lower source_peak_limit")
            write_wav(root / audio_rel["residual"], residual, sr)
            mask_rel = f"evidence/{sample_id}.npz"
            (root / mask_rel).parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(root / mask_rel, **effect.arrays)
            record = {
                "schema_version": SCHEMA_VERSION, "sample_id": sample_id,
                "source": {"source_id": source["source_id"], "declared_source_id": source["declared_source_id"],
                           "source_file": source["source_file"], "source_checksum_sha256": source["checksum"],
                           "content_category": source["content_category"], "content_category_provenance": "source_manifest" if source["content_category"] != "unknown" else "unknown",
                           "sample_rate": sr, "sample_count": len(reference), "duration_s": len(reference) / sr,
                           "channels": reference.shape[1], "split": split_map[source["source_id"]],
                           "shared_source_gain": gain, "original_peak": peak,
                           "is_functional_test_signal": source["is_functional_test_signal"]},
                "audio": {role: {"path": rel, "sha256": file_checksum(root / rel), "subtype": "DOUBLE"}
                          for role, rel in audio_rel.items()},
                "degradation": {"artifact_type": artifact, "algorithm": f"deepmushra_data.{artifact.lower()}",
                                "algorithm_version": ALGORITHM_VERSION, "parameters": effect.parameters,
                                "random_seed": effect_seed, "parameter_severity": {"tier": tier, "status": "provisional_parameter_based"},
                                **processing_regions(effect.arrays, sr, len(reference), stft),
                                "evidence": effect.evidence,
                                "mask": {"path": mask_rel, "sha256": file_checksum(root / mask_rel), "format": "npz", "selection_array": "selected_mask", "axis_order": "time,frequency,channel"}},
                "measurements": measure(saved_reference, degraded, sr, stft, effect.arrays, artifact, effect.parameters),
                "perceptual_annotation": {"status": "unverified", "audibility": None, "perceived_severity": None,
                                          "quality_category": None, "description_attributes": None,
                                          "natural_language_description": None, "provenance": None},
                "descriptions": describe(artifact, effect.parameters, effect.evidence),
                "provenance": {"generator_version": __version__, "configuration_sha256": config_hash,
                               "master_seed": config["seed"], **revision},
            }
            validate_record(record)
            write_json(root / f"metadata/{sample_id}.json", record)
            records.append(record)
    return sorted(records, key=lambda record: record["sample_id"])


def _training_row(record):
    return {"sample_id": record["sample_id"], "source_id": record["source"]["source_id"],
            "split": record["source"]["split"], "sample_rate": record["source"]["sample_rate"],
            "artifact_type": record["degradation"]["artifact_type"],
            **{f"{role}_audio": info["path"] for role, info in record["audio"].items()},
            "metadata_path": f"metadata/{record['sample_id']}.json",
            "technical_description": record["descriptions"]["technical"],
            "perceptual_description_candidate": record["descriptions"]["perceptual_candidate"],
            "perceptual_description_status": "unverified", "quality_category": None}
