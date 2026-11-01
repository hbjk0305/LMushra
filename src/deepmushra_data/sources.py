"""Source integrity, duplicate-aware grouping, and deterministic partitions."""

from pathlib import Path

import numpy as np
import soundfile as sf

from . import MIN_SAMPLE_RATE
from .config import file_checksum, stable_seed
from .metadata import read_jsonl


def read_source(path, policy):
    try:
        info = sf.info(path)
        if info.format not in ("WAV", "WAVEX", "FLAC"):
            raise ValueError("Only WAV/FLAC sources are accepted")
        if info.samplerate < MIN_SAMPLE_RATE or info.samplerate not in policy["sample_rates"]:
            raise ValueError(f"Sample rate {info.samplerate} is not allowed (minimum 44100 Hz)")
        if info.channels not in policy["channels"]:
            raise ValueError(f"Channel count {info.channels} is not allowed")
        duration = info.frames / info.samplerate
        if not policy["min_duration_s"] <= duration <= policy["max_duration_s"]:
            raise ValueError(f"Duration {duration:g}s is outside configured bounds")
        audio, sr = sf.read(path, dtype="float64", always_2d=True)
    except (RuntimeError, OSError, sf.LibsndfileError) as error:
        raise ValueError(f"Cannot decode source {path}: {error}") from error
    if audio.shape != (info.frames, info.channels) or not audio.size or not np.isfinite(audio).all():
        raise ValueError(f"Invalid or truncated waveform in {path}")
    if float(np.max(np.abs(audio))) > 1.0:
        raise ValueError(f"Source exceeds full-scale amplitude: {path}")
    return audio, sr


def discover_sources(input_dir=None, manifest=None, policy=None):
    if (input_dir is None) == (manifest is None):
        raise ValueError("Provide exactly one of input_dir or manifest")
    if input_dir is not None:
        root = Path(input_dir).resolve()
        if not root.is_dir():
            raise ValueError(f"Input directory does not exist: {root}")
        entries = [{"source_file": p.relative_to(root).as_posix(), "content_category": "unknown"}
                   for p in sorted(root.rglob("*")) if p.is_file() and p.suffix.lower() in (".wav", ".flac")]
    else:
        manifest = Path(manifest).resolve()
        root = manifest.parent
        entries = read_jsonl(manifest)
        if any(not isinstance(e, dict) or not e.get("source_id") for e in entries):
            raise ValueError("Each manifest row requires a nonempty source_id")
    if not entries:
        raise ValueError("No source audio files found")
    sources = []
    for entry in entries:
        if not isinstance(entry.get("source_file"), str) or not entry["source_file"]:
            raise ValueError("Each source requires source_file")
        path = (root / entry["source_file"]).resolve()
        audio, sr = read_source(path, policy)
        checksum = file_checksum(path)
        source_id = entry.get("source_id", checksum)
        category = entry.get("content_category", "unknown")
        if not isinstance(source_id, str) or not source_id or not isinstance(category, str):
            raise ValueError("source_id and content_category must be strings")
        sources.append({"path": path, "source_file": entry["source_file"],
                        "declared_source_id": source_id, "checksum": checksum,
                        "content_category": category, "sample_rate": sr,
                        "sample_count": len(audio), "channels": audio.shape[1],
                        "is_functional_test_signal": bool(entry.get("is_functional_test_signal", False))})
    # Union matching recording IDs AND exact-file duplicates. This handles aliases
    # transitively: two excerpts of one recording cannot be split through an alias.
    parent = list(range(len(sources)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    seen_ids, seen_checksums = {}, {}
    for i, source in enumerate(sources):
        for seen, key in ((seen_ids, source["declared_source_id"]), (seen_checksums, source["checksum"])):
            if key in seen:
                parent[find(i)] = find(seen[key])
            else:
                seen[key] = i
    groups = {}
    for i, source in enumerate(sources):
        groups.setdefault(find(i), []).append(source["declared_source_id"])
    for i, source in enumerate(sources):
        source["source_id"] = min(groups[find(i)])
    # Deduplicate identical bytes within a recording; do not create duplicate samples.
    result = {}
    for source in sorted(sources, key=lambda s: (s["source_id"], s["checksum"], s["source_file"])):
        result.setdefault((source["source_id"], source["checksum"]), source)
    return list(result.values())


def assign_splits(sources, proportions, seed):
    groups = sorted({s["source_id"] for s in sources}, key=lambda key: (stable_seed(seed, key, "split"), key))
    names = [name for name in ("train", "validation", "test") if proportions[name] > 0]
    if len(groups) < len(names):
        raise ValueError("Too few source groups for nonempty requested splits; add sources or set some split proportions to zero")
    exact = np.array([proportions[name] * len(groups) for name in names])
    counts = np.floor(exact).astype(int)
    for i in np.argsort(-(exact - counts), kind="stable")[:len(groups) - int(counts.sum())]:
        counts[i] += 1
    for i in range(len(counts)):
        if counts[i] == 0:
            donor = int(np.argmax(counts))
            counts[donor] -= 1
            counts[i] = 1
    result = {}
    offset = 0
    for name, count in zip(names, counts):
        result.update({key: name for key in groups[offset:offset + count]})
        offset += count
    return result
