from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
import pytest
import soundfile as sf

from deepmushra_data.cli import main
from deepmushra_data.config import load_config, recipes, validate_config
from deepmushra_data.metadata import read_jsonl, validate_record, write_jsonl
from deepmushra_data.pipeline import generate_dataset
from deepmushra_data.sources import assign_splits, discover_sources, read_source
from deepmushra_data.validation import validate_dataset


REPO = Path(__file__).resolve().parents[1]


def test_example_configs_and_sampled_ranges():
    for name in ("pilot", "sampled"):
        config = load_config(REPO / f"docs/archive/configs/{name}.yaml")
        assert min(config["input"]["sample_rates"]) >= 44100
    config = load_config(REPO / "docs/archive/configs/sampled.yaml")
    for artifact in config["artifacts"]:
        a = list(recipes(config, artifact, "source"))
        assert a == list(recipes(config, artifact, "source"))
        assert a != list(recipes(config, artifact, "other-source"))
        for _, p, tier in a:
            assert tier == "unspecified"
            if artifact == "LP":
                assert 5000 <= p["cutoff_hz"] <= 16000
            elif artifact == "SH":
                assert 0.05 <= p["hole_probability"] <= 0.5
                assert type(p["run_frames"]) is int and 1 <= p["run_frames"] <= 8
                assert p["band_width_hz"] in (250, 500, 1000)
            else:
                assert 3000 <= p["crossover_hz"] <= 12000
                assert 0.1 <= p["strength"] <= 1
                assert 250 <= p["smoothing_hz"] <= 1000


@pytest.mark.parametrize("changes", [
    {"input": {"sample_rates": [16000, 48000]}},
    {"seed": -1}, {"include_identity": "yes"},
    {"splits": {"train": 1, "validation": 1, "test": 1}},
    {"artifacts": {"PE": {"settings": [{}]}}},
    {"artifacts": {"TM": {"settings": [{}]}}},
    {"artifacts": {"LP": {"sampling": {"count": 3, "parameters": {"cutoff_hz": {"uniform": [20000, 23000]}}}}}},
])
def test_invalid_configs(small_config, changes):
    with pytest.raises(ValueError):
        validate_config({**small_config, **changes})


def test_sampling_validates_joint_range_corners_and_middle_choices(small_config):
    for parameters in (
        {"cutoff_hz": {"choice": [5000, 23000, 10000]}},
        {"cutoff_hz": {"choice": [10000]}, "passband_ripple_db": {"uniform": [0.1, 3]},
         "attenuation_db": {"uniform": [2, 60]}},
    ):
        c = deepcopy(small_config)
        c["artifacts"] = {"LP": {"sampling": {"count": 1, "parameters": parameters}}}
        with pytest.raises(ValueError):
            validate_config(c)


def test_generated_triplets_metadata_and_splits(tiny_dataset):
    report = validate_dataset(tiny_dataset)
    assert report["valid"], report
    assert report["sample_count"] == 12
    assert report["source_group_count"] == 3
    assert report["sample_rates_hz"] == [44100, 48000]
    assert report["max_residual_reconstruction_error"] < 1e-12
    assert report["split_counts"] == {"train": 4, "validation": 4, "test": 4}
    source_splits = {}
    for record in read_jsonl(tiny_dataset / "metadata.jsonl"):
        validate_record(record)
        source = record["source"]
        source_splits.setdefault(source["source_id"], set()).add(source["split"])
        assert record["perceptual_annotation"]["quality_category"] is None
        assert record["perceptual_annotation"]["audibility"] is None
        assert record["descriptions"]["perceptual_candidate_status"] == "unverified"
        assert record["degradation"]["parameter_severity"]["status"] == "provisional_parameter_based"
        assert "NaN" not in json.dumps(record, allow_nan=False)
        arrays = [sf.read(tiny_dataset / record["audio"][role]["path"], always_2d=True)[0]
                  for role in ("reference", "degraded", "residual")]
        np.testing.assert_array_equal(arrays[2], arrays[1] - arrays[0])
        if record["degradation"]["artifact_type"] == "IDENTITY":
            assert np.all(arrays[2] == 0)
    assert all(len(splits) == 1 for splits in source_splits.values())


def test_deterministic_runs_and_source_order(tmp_path, small_config, source_manifest):
    first, second = tmp_path / "first", tmp_path / "second"
    generate_dataset(small_config, first, manifest=source_manifest, diagnostics=False)
    entries = read_jsonl(source_manifest)
    write_jsonl(source_manifest, entries[::-1])
    generate_dataset(small_config, second, manifest=source_manifest, diagnostics=False)
    assert (first / "metadata.jsonl").read_bytes() == (second / "metadata.jsonl").read_bytes()
    assert (first / "manifest.jsonl").read_bytes() == (second / "manifest.jsonl").read_bytes()
    for record in read_jsonl(first / "metadata.jsonl"):
        for info in record["audio"].values():
            assert (first / info["path"]).read_bytes() == (second / info["path"]).read_bytes()
        evidence = record["degradation"]["mask"]["path"]
        assert (first / evidence).read_bytes() == (second / evidence).read_bytes()


def test_source_aliases_and_related_excerpts_stay_together(tmp_path, source_manifest, small_config):
    entries = read_jsonl(source_manifest)
    # Same file with a different recording ID connects two otherwise separate IDs.
    entries.extend([{**entries[0], "source_id": "alias"}, {**entries[1], "source_id": "alias"}])
    write_jsonl(source_manifest, entries)
    sources = discover_sources(manifest=source_manifest, policy=small_config["input"])
    assert len(sources) == 3
    assert sources[0]["source_id"] == "alias"
    assert len({s["source_id"] for s in sources}) == 2
    with pytest.raises(ValueError, match="Too few"):
        assign_splits(sources, small_config["splits"], 1)
    splits = assign_splits(sources, {"train": 1, "validation": 0, "test": 0}, 1)
    assert set(splits.values()) == {"train"}


def test_decode_rate_and_channel_validation(tmp_path, small_config):
    policy = small_config["input"]
    low = tmp_path / "low.wav"
    sf.write(low, np.zeros(1600), 16000)
    with pytest.raises(ValueError, match="44100"):
        read_source(low, policy)
    broken = tmp_path / "broken.wav"
    broken.write_text("not audio")
    with pytest.raises(ValueError, match="decode"):
        read_source(broken, policy)
    multichannel = tmp_path / "multi.wav"
    sf.write(multichannel, np.zeros((3000, 3)), 48000)
    with pytest.raises(ValueError, match="Channel"):
        read_source(multichannel, policy)
    over = tmp_path / "over.wav"
    sf.write(over, np.full(3000, 2.0), 48000, subtype="DOUBLE")
    with pytest.raises(ValueError, match="full-scale"):
        read_source(over, policy)


def test_headroom_and_atomic_failure(tmp_path, small_config, source_manifest):
    c = deepcopy(small_config)
    c["input"]["source_peak_limit"] = 0.01
    c["input"]["output_peak_limit"] = 0.01
    c["artifacts"] = {"LP": {"settings": [{"cutoff_hz": 10000}]}}
    # Fault injection proves failed effects do not publish a partial dataset.
    from unittest.mock import patch
    output = tmp_path / "failed"
    with patch("deepmushra_data.pipeline.apply_effect", side_effect=ValueError("simulated failure")):
        with pytest.raises(ValueError, match="simulated"):
            generate_dataset(c, output, manifest=source_manifest, diagnostics=False)
    assert not output.exists()
    assert not list(tmp_path.glob(".failed.building-*"))


@pytest.mark.parametrize("scale,role", [(10, "degraded"), (-3, "residual")])
def test_generated_peak_excess_is_rejected_not_clamped(tmp_path, small_config, source_manifest, scale, role):
    from unittest.mock import patch
    from deepmushra_data.degradations import apply_effect

    c = deepcopy(small_config)
    c["artifacts"] = {"LP": {"settings": [{"cutoff_hz": 10000}]}}
    def excessive(artifact, audio, sr, parameters, seed, stft):
        result = apply_effect(artifact, audio, sr, parameters, seed, stft)
        result.audio = scale * audio
        return result
    output = tmp_path / "over-peak"
    with patch("deepmushra_data.pipeline.apply_effect", side_effect=excessive):
        with pytest.raises(ValueError, match=f"{role} peak"):
            generate_dataset(c, output, manifest=source_manifest, diagnostics=False)
    assert not output.exists()


def test_directory_input_and_shared_headroom(tmp_path, small_config, source_manifest):
    clean = tmp_path / "clean"
    clean.mkdir()
    for entry in read_jsonl(source_manifest):
        data, sr = sf.read(source_manifest.parent / entry["source_file"], always_2d=True)
        data *= 0.9 / np.max(np.abs(data))
        sf.write(clean / entry["source_file"], data, sr, subtype="DOUBLE")
    shutil.copyfile(clean / "source_0.wav", clean / "duplicate.wav")
    c = deepcopy(small_config)
    c["input"]["source_peak_limit"] = 0.1
    output = tmp_path / "directory-output"
    result = generate_dataset(c, output, input_dir=clean, diagnostics=False)
    assert result["sample_count"] == 12, "Identical duplicate must not create extra examples"
    for record in read_jsonl(output / "metadata.jsonl"):
        assert record["source"]["content_category"] == "unknown"
        assert record["source"]["shared_source_gain"] == pytest.approx(1 / 9)
        assert record["measurements"]["reference_peak"] == pytest.approx(0.1)


def test_noop_text_and_zero_energy_measurements():
    from deepmushra_data.degradations import apply_effect
    from deepmushra_data.descriptions import describe
    from deepmushra_data.metadata import measure
    from deepmushra_data.stft import STFTConfig

    audio = np.zeros((2049, 1))
    config = STFTConfig()
    result = apply_effect("UN", audio, 44100, {}, 1, config)
    stats = measure(audio, result.audio, 44100, config, result.arrays, "UN", result.parameters)
    assert stats["relative_residual_energy"] is None
    assert stats["rms_change_db"] is None
    assert stats["selected_envelope_relative_error"] is None
    json.dumps(stats, allow_nan=False)
    text = describe("UN", result.parameters, result.evidence)
    assert "No transformation" in text["technical"]
    assert text["perceptual_candidate_status"] == "unverified"


def test_demo_sources_are_reproducible(tmp_path):
    from deepmushra_data.pipeline import create_demo_sources
    first, second = tmp_path / "demo-a", tmp_path / "demo-b"
    a = create_demo_sources(first, seed=123, duration_s=0.1)
    b = create_demo_sources(second, seed=123, duration_s=0.1)
    assert a.read_bytes() == b.read_bytes()
    entries = read_jsonl(a)
    assert len(entries) == 6
    for entry in entries:
        assert entry["is_functional_test_signal"]
        rel = entry["source_file"]
        assert (first / rel).read_bytes() == (second / rel).read_bytes()


def test_existing_output_never_overwritten(tiny_dataset, small_config, source_manifest):
    before = (tiny_dataset / "metadata.jsonl").read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        generate_dataset(small_config, tiny_dataset, manifest=source_manifest, diagnostics=False)
    assert (tiny_dataset / "metadata.jsonl").read_bytes() == before


@pytest.mark.parametrize("target", ["audio", "mask", "metadata", "manifest"])
def test_validator_detects_corruption(tiny_dataset, target):
    record = read_jsonl(tiny_dataset / "metadata.jsonl")[0]
    if target == "audio":
        info = record["audio"]["residual"]
        path = tiny_dataset / info["path"]
        data, sr = sf.read(path, always_2d=True)
        data[0, 0] += 0.001
        sf.write(path, data, sr, subtype="DOUBLE")
    elif target == "mask":
        path = tiny_dataset / record["degradation"]["mask"]["path"]
        path.write_bytes(b"corrupt")
    elif target == "metadata":
        path = tiny_dataset / f"metadata/{record['sample_id']}.json"
        changed = json.loads(path.read_text())
        changed["perceptual_annotation"]["quality_category"] = "Excellent"
        path.write_text(json.dumps(changed))
    else:
        path = tiny_dataset / "manifests/train.jsonl"
        path.write_text("")
    report = validate_dataset(tiny_dataset)
    assert not report["valid"]
    assert report["errors"]


def test_cli_generate_validate_and_figures(tmp_path, small_config, source_manifest):
    config_file = tmp_path / "config.json"
    # JSON is a subset of YAML, exercising the same configuration parser.
    config_file.write_text(json.dumps(small_config))
    output = tmp_path / "cli"
    # Historical schemas are no longer accepted by the public generator.
    assert main(["generate", "--config", str(config_file), "--manifest", str(source_manifest), "--output", str(output)]) == 1
    generate_dataset(small_config, output, manifest=source_manifest, diagnostics=True)
    assert main(["validate", "--dataset", str(output)]) == 0
    assert main(["generate", "--config", str(config_file), "--manifest", str(source_manifest), "--output", str(output)]) == 1
    for artifact in ("LP", "SH", "UN"):
        figure = output / f"diagnostics/{artifact}.png"
        assert figure.read_bytes().startswith(b"\x89PNG")
    result = subprocess.run([sys.executable, "-m", "deepmushra_data", "validate", "--dataset", str(output)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["valid"]
