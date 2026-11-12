from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from deepmushra_data.cli import main
from deepmushra_data.config import file_checksum
from deepmushra_data.metadata import read_jsonl, write_jsonl
from deepmushra_data.pipeline import generate_dataset
from deepmushra_data.training_export import export_training_jsonl


@pytest.fixture
def paired_dataset(tmp_path, small_config):
    sources = tmp_path / "sources"
    sources.mkdir()
    entries = []
    rate = 44100
    time = np.arange(5292) / rate
    for i in range(4):
        waveform = .1 * np.sin(2 * np.pi * (500 + 100 * i) * time)
        waveform += .06 * np.sin(2 * np.pi * (10000 + 100 * i) * time)
        path = sources / f"source_{i}.wav"
        sf.write(path, waveform, rate, subtype="DOUBLE")
        entries.append({"source_file": path.name, "source_id": f"recording_{i}",
                        "content_category": "functional_test_tonal",
                        "is_functional_test_signal": True})
    manifest = sources / "sources.jsonl"
    write_jsonl(manifest, entries)
    config = deepcopy(small_config)
    config["include_identity"] = True
    config["artifacts"]["QN"] = {"settings": [{"snr_db": 30}]}
    output = tmp_path / "dataset"
    result = generate_dataset(config, output, manifest=manifest, diagnostics=False)
    assert result["valid"]
    return output


def test_contract_audio_order_splits_and_lossless_metadata(paired_dataset, tmp_path):
    original = (paired_dataset / "metadata.jsonl").read_bytes()
    records = read_jsonl(paired_dataset / "metadata.jsonl")
    destination = tmp_path / "export"
    report = export_training_jsonl(paired_dataset, destination)
    assert report["valid"] and report["sample_count"] == len(records)
    assert report["residual_in_model_input"] is False
    assert report["human_perceptual_ratings_added"] is False
    assert set(report["artifact_counts"]) == {"LP", "SH", "UN", "QN", "IDENTITY"}
    assert original == (paired_dataset / "metadata.jsonl").read_bytes()
    source_sets = {}
    for source_split, output_split in [("train", "train"), ("validation", "valid"), ("test", "test")]:
        expected = [r for r in records if r["source"]["split"] == source_split]
        rows = read_jsonl(destination / f"{output_split}.jsonl")
        sidecars = read_jsonl(destination / f"{output_split}.metadata.jsonl")
        assert report["split_counts"][output_split] == len(expected)
        assert len(rows) == len(sidecars) == len(expected)
        source_sets[output_split] = {r["source"]["source_id"] for r in expected}
        for i, (row, sidecar, record) in enumerate(zip(rows, sidecars, expected)):
            assert set(row) == {"messages", "audios"}
            assert [m["role"] for m in row["messages"]] == ["user", "assistant"]
            assert row["messages"][0]["content"].count("<audio>") == len(row["audios"]) == 2
            assert row["messages"][1]["content"] == record["descriptions"]["technical"]
            assert row["audios"] == [
                str((paired_dataset / record["audio"][role]["path"]).resolve())
                for role in ("reference", "degraded")
            ]
            assert all(Path(p).is_file() for p in row["audios"])
            assert sidecar["row_index"] == i and sidecar["metadata"] == record
            assert sidecar["target"]["status"] == "processing_description_not_perceptual_ground_truth"
            assert sidecar["audio_paths"]["residual"].endswith("/residual.wav")
    assert not source_sets["train"] & source_sets["valid"]
    assert not source_sets["train"] & source_sets["test"]


def test_deterministic_relative_paths_and_cli(paired_dataset, tmp_path):
    a, b = tmp_path / "export_a", tmp_path / "export_b"
    export_training_jsonl(paired_dataset, a, relative_to=tmp_path)
    assert main(["export-training", "--dataset", str(paired_dataset), "--output", str(b),
                 "--relative-to", str(tmp_path)]) == 0
    assert {p.name: p.read_bytes() for p in a.iterdir()} == {p.name: p.read_bytes() for p in b.iterdir()}
    rows = read_jsonl(a / "train.jsonl")
    assert rows
    assert all(not Path(p).is_absolute() and (tmp_path / p).is_file()
               for r in rows for p in r["audios"])


def test_candidates_and_extra_metadata_do_not_become_ratings(paired_dataset, tmp_path):
    records = read_jsonl(paired_dataset / "metadata.jsonl")
    for record in records:
        record["calibration_estimate"] = {"estimated_quality": 12.3456789, "transfer": "unverified"}
    write_jsonl(paired_dataset / "metadata.jsonl", records)
    out = tmp_path / "candidates"
    report = export_training_jsonl(paired_dataset, out, description="perceptual_candidate")
    assert report["target_status"] == "unverified"
    for name in ("train", "valid", "test"):
        rows = read_jsonl(out / f"{name}.jsonl")
        sides = read_jsonl(out / f"{name}.metadata.jsonl")
        for row, side in zip(rows, sides):
            assert row["messages"][1]["content"] == side["metadata"]["descriptions"]["perceptual_candidate"]
            assert "12.3456789" not in row["messages"][1]["content"]
            assert side["target"]["status"] == "unverified"
            assert side["metadata"]["calibration_estimate"]["estimated_quality"] == 12.3456789
            assert side["metadata"]["perceptual_annotation"]["quality_category"] is None


@pytest.mark.parametrize("fault,expected", [
    ("missing", "No such file"),
    ("hash", "checksum mismatch"),
    ("residual", "does not reconstruct"),
    ("shape", "must match metadata"),
    ("nonfinite", "NaN/Inf"),
    ("clipping", "full scale"),
    ("escape", "escapes run directory"),
])
def test_bad_audio_fails_atomically(paired_dataset, tmp_path, fault, expected):
    records = read_jsonl(paired_dataset / "metadata.jsonl")
    record = records[0]
    info = record["audio"]["residual"]
    path = paired_dataset / info["path"]
    if fault == "missing":
        path.unlink()
    elif fault == "escape":
        info["path"] = "../outside.wav"
    else:
        x, sr = sf.read(path)
        if fault == "hash":
            x[0] += .001
        elif fault == "residual":
            x[0] += .001
        elif fault == "shape":
            x = x[:-1]
        elif fault == "nonfinite":
            x[0] = np.nan
        else:
            x[0] = 1.1
        sf.write(path, x, sr, subtype="DOUBLE")
        if fault != "hash":
            info["sha256"] = file_checksum(path)
    write_jsonl(paired_dataset / "metadata.jsonl", records)
    output = tmp_path / "bad-export"
    with pytest.raises((ValueError, OSError), match=expected):
        export_training_jsonl(paired_dataset, output)
    assert not output.exists()
    assert not list(tmp_path.glob(".bad-export.building-*"))


@pytest.mark.parametrize("group", ["source_id", "source_checksum_sha256", "reference"])
def test_source_leakage_rejected(paired_dataset, tmp_path, group):
    records = read_jsonl(paired_dataset / "metadata.jsonl")
    first = records[0]
    other = next(r for r in records if r["source"]["split"] != first["source"]["split"])
    if group == "reference":
        other["audio"]["reference"]["sha256"] = first["audio"]["reference"]["sha256"]
    else:
        other["source"][group] = first["source"][group]
    write_jsonl(paired_dataset / "metadata.jsonl", [first, other])
    with pytest.raises(ValueError, match="split leakage"):
        export_training_jsonl(paired_dataset, tmp_path / "leaked")


@pytest.mark.parametrize("field,value,error", [
    ("sample_rate", 48000, "44100 Hz mono"),
    ("channels", 2, "44100 Hz mono"),
    ("sample_count", 30 * 44100 + 1, "at most 30 seconds"),
])
def test_model_input_contract_rejected_without_conversion(paired_dataset, tmp_path, field, value, error):
    records = read_jsonl(paired_dataset / "metadata.jsonl")
    records[0]["source"][field] = value
    write_jsonl(paired_dataset / "metadata.jsonl", records)
    with pytest.raises(ValueError, match=error):
        export_training_jsonl(paired_dataset, tmp_path / "wrong-format")


@pytest.mark.parametrize("fault,error", [
    ("duplicate", "duplicate"),
    ("blank_target", "empty description"),
    ("audio_target", "must not contain audio"),
    ("heldout", "Held-out"),
    ("upsampled", "lower-rate original"),
])
def test_invalid_supervision_or_provenance_rejected(paired_dataset, tmp_path, fault, error):
    records = read_jsonl(paired_dataset / "metadata.jsonl")
    if fault == "duplicate":
        records.append(records[0])
    elif fault == "blank_target":
        records[0]["descriptions"]["technical"] = ""
    elif fault == "audio_target":
        records[0]["descriptions"]["technical"] = "Something <audio> unexpected"
    elif fault == "heldout":
        records[0]["degradation"]["artifact_type"] = "PE"
    else:
        records[0]["source"]["source_provenance"] = {"original_header": {"sample_rate": 16000}}
    write_jsonl(paired_dataset / "metadata.jsonl", records)
    with pytest.raises(ValueError, match=error):
        export_training_jsonl(paired_dataset, tmp_path / "invalid")


def test_existing_output_and_invalid_prompt_are_safe(paired_dataset, tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("user-owned")
    with pytest.raises(ValueError, match="already exists"):
        export_training_jsonl(paired_dataset, output)
    assert sentinel.read_text() == "user-owned"
    with pytest.raises(ValueError, match="exactly two"):
        export_training_jsonl(paired_dataset, tmp_path / "bad-prompt", prompt="Only <audio>")


def test_empty_metadata_and_output_inside_dataset_rejected(paired_dataset, tmp_path):
    with pytest.raises(ValueError, match="outside"):
        export_training_jsonl(paired_dataset, paired_dataset / "export")
    (paired_dataset / "metadata.jsonl").write_text("")
    with pytest.raises(ValueError, match="empty metadata"):
        export_training_jsonl(paired_dataset, tmp_path / "empty")
