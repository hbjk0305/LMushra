"""Export synthetic triplets to the paired JSONL contract on hwangbo/train.

Only messages/audios are model inputs. Rich metadata and the residual stay in
parallel sidecars. Export never changes audio or invents perceptual ratings.
"""

from collections import Counter
from contextlib import ExitStack
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile

import numpy as np
import soundfile as sf

from .config import file_checksum
from .metadata import write_json
from .validation import local_path


CONTRACT_REVISION = "34f4f54b5d4e96d2846cb703e9267dbcf953f686"
SPLIT_FILES = {"train": "train", "validation": "valid", "test": "test"}
ALLOWED_ARTIFACTS = {"LP", "SH", "UN", "QN", "IDENTITY"}
DEFAULT_PROMPT = """Reference audio (original): <audio>
Degraded audio (processed counterpart): <audio>

Compare the processed audio with the reference. Describe the processing-related
changes concisely, making the direction of the comparison clear. Treat possible
perceptual effects as uncertain unless verified. Do not invent audibility,
perceived severity, MOS, MUSHRA ratings, or a codec identity. Do not transcribe
speech or summarize musical content.
"""


def _target(record, description):
    value = record["descriptions"].get(description)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{record.get('sample_id')}: missing/empty description {description}")
    if "<audio>" in value:
        raise ValueError("Assistant description must not contain audio placeholders")
    if description == "perceptual_candidate":
        if record["descriptions"].get("perceptual_candidate_status") != "unverified":
            raise ValueError("Candidate export requires explicit unverified status")
        status = "unverified"
    else:
        status = "processing_description_not_perceptual_ground_truth"
    return value.strip(), status


def _waveform(root, info, source, role):
    path = local_path(root, info["path"])
    expected_hash = info.get("sha256")
    if not isinstance(expected_hash, str) or file_checksum(path) != expected_hash:
        raise ValueError(f"{role} audio checksum mismatch: {path}")
    waveform, rate = sf.read(path, dtype="float64", always_2d=True)
    expected_shape = (source["sample_count"], 1)
    if rate != 44100 or waveform.shape != expected_shape:
        raise ValueError(f"{role} must match metadata at 44100 Hz mono: {path}")
    if not np.isfinite(waveform).all():
        raise ValueError(f"{role} contains NaN/Inf: {path}")
    if np.max(np.abs(waveform)) > 1:
        raise ValueError(f"{role} exceeds digital full scale: {path}")
    return path, waveform


def export_training_jsonl(dataset, output, *, description="technical",
                          relative_to=None, prompt=None, bundle_audio=False, audio_prefix=None, skip_no_effect=False):
    """Export all existing splits, with no resplitting, audio copying or resampling.

    Input is the generator's full metadata.jsonl, including mapped variants that
    preserve its common source/audio/descriptions fields. Extra fields are kept
    verbatim in sidecars, never implicitly promoted to model supervision.
    """
    root, output = Path(dataset).resolve(), Path(output).resolve()
    metadata_file = root / "metadata.jsonl"
    if description not in ("technical", "perceptual_candidate"):
        raise ValueError("description must be technical or perceptual_candidate")
    prompt = DEFAULT_PROMPT if prompt is None else prompt
    if not isinstance(prompt, str) or prompt.count("<audio>") != 2:
        raise ValueError("User prompt must contain exactly two <audio> placeholders")
    if output.exists():
        raise ValueError(f"Output already exists; refusing overwrite: {output}")
    if output.is_relative_to(root):
        raise ValueError("Export output must be outside the source dataset directory")
    base = Path(relative_to).resolve() if relative_to is not None else None
    if bundle_audio:
        if base is not None:raise ValueError("Use audio-prefix for portable bundles, not relative-to")
        if not isinstance(audio_prefix,str) or not audio_prefix or "\\" in audio_prefix:raise ValueError("Portable bundle requires a POSIX audio-prefix")
        prefix=PurePosixPath(audio_prefix)
        if prefix.is_absolute() or ".." in prefix.parts:raise ValueError("audio-prefix must be relative without ..")
    elif audio_prefix is not None:raise ValueError("audio-prefix requires bundle_audio")
    metadata_hash = file_checksum(metadata_file)
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.building-", dir=output.parent))
    split_counts, artifact_counts = Counter(), Counter()
    source_groups, source_hash_groups, reference_groups = {}, {}, {}
    sample_ids = set()
    skipped_no_effect = 0
    fingerprints = set()
    functional_flags = Counter()
    max_residual_error = 0.0

    def emit_path(path):
        if bundle_audio:
            return (prefix/"dataset"/path.relative_to(root).as_posix()).as_posix()
        if base is None:
            return str(path)
        try:
            return path.relative_to(base).as_posix()
        except ValueError as error:
            raise ValueError(f"Audio {path} is outside relative path base {base}") from error

    try:
        with ExitStack() as stack:
            streams = {name: stack.enter_context((stage / f"{name}.jsonl").open(
                "w", encoding="utf-8", newline="\n")) for name in SPLIT_FILES.values()}
            sidecars = {name: stack.enter_context((stage / f"{name}.metadata.jsonl").open(
                "w", encoding="utf-8", newline="\n")) for name in SPLIT_FILES.values()}
            metadata_stream = stack.enter_context(metadata_file.open(encoding="utf-8"))
            for line_number, line in enumerate(metadata_stream, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if skip_no_effect and record.get("calibration_estimate",{}).get("status")=="no_effect_quality_not_estimated":
                        skipped_no_effect += 1
                        continue
                    fingerprint=record.get("provenance",{}).get("generator_profile_fingerprint")
                    fingerprints.add(fingerprint)
                    if len(fingerprints)>1:raise ValueError("Mixed generator profile fingerprints")
                    sample_id = record["sample_id"]
                    if not isinstance(sample_id, str) or not sample_id or sample_id in sample_ids:
                        raise ValueError("Empty/duplicate/invalid sample_id")
                    sample_ids.add(sample_id)
                    source = record["source"]
                    split = source["split"]
                    if split not in SPLIT_FILES:
                        raise ValueError(f"Unsupported source split: {split}")
                    if source["sample_rate"] != 44100 or source["channels"] != 1:
                        raise ValueError("Training export requires saved 44100 Hz mono audio; no automatic conversion")
                    count = source["sample_count"]
                    if isinstance(count, bool) or not isinstance(count, int) or not 0 < count <= 30 * 44100:
                        raise ValueError("Each training clip must be nonempty and at most 30 seconds")
                    if not np.isclose(source["duration_s"], count / 44100, atol=1e-12, rtol=0):
                        raise ValueError("Source duration disagrees with sample count")
                    original_rate = source.get("source_provenance", {}).get("original_header", {}).get("sample_rate")
                    if original_rate is not None and original_rate < 44100:
                        raise ValueError("Known lower-rate original does not qualify through upsampling")
                    artifact = record["degradation"]["artifact_type"]
                    if artifact not in ALLOWED_ARTIFACTS:
                        raise ValueError(f"Held-out or unsupported training artifact: {artifact}")
                    audio = record["audio"]
                    if set(audio) != {"reference", "degraded", "residual"}:
                        raise ValueError("Exactly reference/degraded/residual metadata is required")
                    for registry, key in (
                        (source_groups, source["source_id"]),
                        (source_hash_groups, source["source_checksum_sha256"]),
                        (reference_groups, audio["reference"]["sha256"]),
                    ):
                        if not isinstance(key, str) or not key:
                            raise ValueError("Missing source grouping identity")
                        if key in registry and registry[key] != split:
                            raise ValueError("Source-level or exact-reference split leakage")
                        registry[key] = split
                    paths, waveforms = {}, {}
                    for role in ("reference", "degraded", "residual"):
                        paths[role], waveforms[role] = _waveform(root, audio[role], source, role)
                    error = max(
                        float(np.max(np.abs(waveforms["degraded"] - waveforms["reference"] - waveforms["residual"]))),
                        float(np.max(np.abs(waveforms["reference"] + waveforms["residual"] - waveforms["degraded"]))),
                    )
                    if error > 1e-12:
                        raise ValueError("Saved residual does not reconstruct degraded/reference triplet")
                    max_residual_error = max(max_residual_error, error)
                    target, target_status = _target(record, description)
                    row = {
                        "messages": [
                            {"role": "user", "content": prompt},
                            {"role": "assistant", "content": target},
                        ],
                        "audios": [emit_path(paths["reference"]), emit_path(paths["degraded"])],
                    }
                    name = SPLIT_FILES[split]
                    sidecar = {
                        "row_index": split_counts[name],
                        "sample_id": sample_id,
                        "source_id": source["source_id"],
                        "source_split": split,
                        "training_split": name,
                        "source_dataset": (prefix/"dataset").as_posix() if bundle_audio else str(root),
                        "audio_roles": ["reference", "degraded"],
                        "audio_paths": {role: emit_path(path) for role, path in paths.items()},
                        "target": {"field": f"descriptions.{description}", "status": target_status},
                        "metadata": record,
                    }
                    streams[name].write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                    sidecars[name].write(json.dumps(sidecar, ensure_ascii=False, allow_nan=False) + "\n")
                    split_counts[name] += 1
                    artifact_counts[artifact] += 1
                    functional_flags[str(source.get("is_functional_test_signal", "unknown")).lower()] += 1
                except (KeyError, ValueError, TypeError, OSError, RuntimeError) as error:
                    raise ValueError(f"metadata.jsonl line {line_number}: {error}") from error
        if not sample_ids:
            raise ValueError("Cannot export empty metadata")
        if bundle_audio:
            if any(p.is_symlink() for p in root.rglob("*")):raise ValueError("Portable dataset must not contain symlinks")
            shutil.copytree(root,stage/"dataset")
            for line in (stage/"dataset/metadata.jsonl").read_text().splitlines():
                rec=json.loads(line)
                for info in rec["audio"].values():
                    if file_checksum(local_path(stage/"dataset",info["path"]))!=info["sha256"]:
                        raise ValueError("Copied audio checksum mismatch")
        if file_checksum(metadata_file) != metadata_hash:
            raise ValueError("Input metadata changed during export")
        report = {
            "valid": True,
            "format": "messages+audios paired JSONL",
            "format_version": "1.0",
            "contract": {"branch": "hwangbo/train", "revision": CONTRACT_REVISION,
                         "example": "data/dummy-100/train.jsonl"},
            "input_metadata": (prefix/"dataset/metadata.jsonl").as_posix() if bundle_audio else str(metadata_file),
            "input_metadata_sha256": metadata_hash,
            "audio_roles": ["reference", "degraded"],
            "residual_in_model_input": False,
            "audio_copied_or_modified": bundle_audio,
            "audio_copied": bundle_audio,
            "audio_modified": False,
            "portable_audio_prefix": str(prefix) if bundle_audio else None,
            "skipped_no_effect_count": skipped_no_effect,
            "generator_profile_fingerprint": next(iter(fingerprints)),
            "sample_rate_hz": 44100,
            "channels": 1,
            "maximum_clip_seconds": 30,
            "path_style": "portable_bundle" if bundle_audio else "absolute" if base is None else "relative",
            "relative_path_base": str(base) if base is not None else None,
            "sample_count": len(sample_ids),
            "split_counts": {name: split_counts[name] for name in SPLIT_FILES.values()},
            "source_group_count": len(source_groups),
            "artifact_counts": dict(sorted(artifact_counts.items())),
            "description_field": f"descriptions.{description}",
            "target_status": "unverified" if description == "perceptual_candidate" else
                             "processing_description_not_perceptual_ground_truth",
            "human_perceptual_ratings_added": False,
            "functional_test_record_flags": dict(sorted(functional_flags.items())),
            "max_residual_reconstruction_error": max_residual_error,
            "limitations": [
                "Template text is metadata-derived, not human-verified perceptual supervision.",
                "No MOS, MUSHRA or perceived severity is inferred from processing parameters.",
                "This verifies stored audio and declared original rates, not full recording provenance/cleanliness.",
                "Relative paths resolve from the chosen training working directory; absolute paths are host-specific.",
                "Portable mode includes dataset audio/evidence/metadata; reference-only exports require the original dataset.",
                "Structural compatibility is checked; no model training or ms-swift execution is performed.",
            ],
            "files": {p.name: file_checksum(p) for p in sorted(stage.glob("*.jsonl"))},
        }
        write_json(stage / "export_report.json", report)
        if output.exists():
            raise ValueError(f"Output appeared during export; refusing overwrite: {output}")
        stage.rename(output)
        return {"output": str(output), **report}
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
