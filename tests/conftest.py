from copy import deepcopy

import numpy as np
import pytest
import soundfile as sf

from deepmushra_data.config import validate_config
from deepmushra_data.metadata import write_jsonl


@pytest.fixture
def small_config():
    return validate_config({
        "seed": 1234, "input": {"min_duration_s": 0.02, "max_duration_s": 2},
        "stft": {"n_fft": 512, "hop_length": 128},
        "artifacts": {
            "LP": {"settings": [{"cutoff_hz": 10000}]},
            "SH": {"settings": [{"hole_probability": 0.4, "run_frames": 2}]},
            "UN": {"settings": [{"crossover_hz": 7000, "strength": 1.0}]},
        },
    })


@pytest.fixture
def source_manifest(tmp_path):
    entries = []
    for index in range(3):
        sr = 44100 if index == 0 else 48000
        t = np.arange(round(sr * 0.12)) / sr
        mono = 0.15 * np.sin(2 * np.pi * (700 + index * 100) * t) + 0.12 * np.sin(2 * np.pi * 11500 * t)
        audio = mono[:, None] if index == 0 else np.column_stack((mono, 0.7 * mono))
        name = f"source_{index}.wav"
        sf.write(tmp_path / name, audio, sr, subtype="DOUBLE")
        entries.append({"source_file": name, "source_id": f"recording_{index}", "content_category": "functional_test_tonal"})
    path = tmp_path / "sources.jsonl"
    write_jsonl(path, entries)
    return path


@pytest.fixture
def tiny_dataset(tmp_path, small_config, source_manifest):
    from deepmushra_data.pipeline import generate_dataset
    output = tmp_path / "dataset"
    report = generate_dataset(deepcopy(small_config), output, manifest=source_manifest, diagnostics=False)
    assert report["valid"], report
    return output
