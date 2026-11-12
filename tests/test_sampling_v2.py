"""Sampling contracts, actual waveforms, legacy compatibility and portable training rows."""
from copy import deepcopy
import json
from pathlib import Path
import numpy as np
import pytest
import soundfile as sf
from deepmushra_data.metadata import read_jsonl, write_jsonl
from deepmushra_mapped.profile import default_config, resolve_config, check_shared_config
from deepmushra_mapped.sampling import sample_requests, knots, validate_sampling
from deepmushra_mapped.mapping import load_table, estimate_quality, parameter_for_quality, _plateau_inverse
from deepmushra_mapped.pipeline import generate, validate_recipe, validate_dataset
from deepmushra_mapped.collaboration import build, check_export
from deepmushra_mapped.cli import main

SOURCE = {"source_id":"recording-a", "checksum":"a" * 64}


def recipe(mode):
    return resolve_config(profile_id="mapped-poc-v2", sampling_mode=mode)


@pytest.mark.parametrize("artifact", ["LP", "SH", "UN", "QN"])
def test_all_knots_nominal_units_and_bridge(artifact):
    requests, report = sample_requests(recipe("odaq_knots"), artifact, SOURCE)
    assert report["attempted"] == report["retained"] == 5
    assert report["skipped_count"] == report["deduplicated_count"] == 0
    assert [r["sampling"]["nominal_condition_id"] for r in requests] == [f"Q{i}" for i in range(1,6)]
    c = load_table()["artifacts"][artifact]
    for r in requests:
        origin = r["sampling"]["origins"][0]
        assert estimate_quality(artifact, r["parameter"])["support_status"] == "inside"
        if artifact == "QN":
            assert origin["nominal_parameter"] != r["parameter"]
            assert r["parameter"] == c["x"][c["released_parameter_knots"].index(origin["nominal_parameter"])]
            assert "not_NMR_identity" in origin["bridge"]
        elif artifact == "SH":
            assert r["parameter"] == pytest.approx(origin["nominal_parameter"] / 100)
        else:
            assert r["parameter"] == origin["nominal_parameter"] * 1000


@pytest.mark.parametrize("strategy", ["continuous_uniform", "continuous_stratified"])
@pytest.mark.parametrize("artifact", ["LP", "SH", "UN", "QN"])
def test_continuous_deterministic_bounded_roundtrip(strategy, artifact):
    c = recipe("quality_target"); c["sampling"]["quality_target"]["strategy"] = strategy
    requests, report = sample_requests(c, artifact, SOURCE)
    assert (requests,report) == sample_requests(c,artifact,SOURCE)
    different,_ = sample_requests(c,artifact,{**SOURCE,"source_id":"other"})
    assert requests != different
    for r in requests:
        assert estimate_quality(artifact,r["parameter"])["estimated_quality_mean"] == pytest.approx(r["value"],abs=1e-8)
        lo,hi = r["sampling"]["supported_quality_range"]
        assert lo <= r["value"] <= hi
        if strategy == "continuous_stratified":
            a,b = r["sampling"]["origins"][0]["quality_interval"]
            assert a <= r["value"] <= b
    if strategy == "continuous_stratified":
        assert len({tuple(r["sampling"]["origins"][0]["quality_interval"]) for r in requests}) == 5


@pytest.mark.parametrize("artifact", ["LP", "SH", "UN", "QN"])
def test_explicit_skip_not_clip(artifact):
    c = recipe("quality_target")
    c["sampling"]["quality_target"] = {"strategy":"explicit","targets":[10,30,50,70,90],"allow_extrapolation":False,"unsupported_target_policy":"skip_with_report"}
    c = validate_recipe(c)
    requests,report = sample_requests(c,artifact,SOURCE)
    curve = load_table()["artifacts"][artifact];lo,hi = min(curve["quality_mean"]),max(curve["quality_mean"])
    expected=[v for v in [10,30,50,70,90] if lo <= v <= hi]
    assert [r["value"] for r in requests] == expected
    assert report["attempted"] == 5 and report["skipped_count"] == 5-len(expected)
    assert all(r["reason"] == "quality_outside_calibration_support" for r in report["skipped"])
    assert 10 not in expected


def test_stratified_intersections_do_not_force_bad():
    c=recipe("quality_target");c["sampling"]["quality_target"]["intervals"]=[[0,20],[20,40],[40,60],[60,80],[80,100]]
    requests,report=sample_requests(c,"UN",SOURCE)
    assert len(requests)==5
    assert all(45.8 < r["value"] < 90 for r in requests)
    assert len(report["interval_reports"])==2


@pytest.mark.parametrize("artifact", ["LP", "SH", "UN", "QN"])
def test_hybrid_dedup_keeps_both_origins_and_canonical_seed(artifact):
    c=recipe("hybrid");ys=load_table()["artifacts"][artifact]["quality_mean"]
    c["sampling"]["quality_target"]={"strategy":"explicit","targets":ys}
    c=validate_recipe(c)
    requests,report=sample_requests(c,artifact,SOURCE)
    assert report["supported_before_deduplication"] == 10
    assert report["retained"] == report["deduplicated_count"] == 5
    assert all(len(r["sampling"]["origins"])==2 for r in requests)
    knots_only,_=sample_requests(recipe("odaq_knots"),artifact,SOURCE)
    assert [r["seed"] for r in requests] == [r["seed"] for r in knots_only]
    c["sampling"]["hybrid"]["deduplicate_parameters"]=False
    assert len(sample_requests(c,artifact,SOURCE)[0])==10


def test_hybrid_same_continuous_requests_as_quality_mode():
    b,_=sample_requests(recipe("quality_target"),"LP",SOURCE)
    c,_=sample_requests(recipe("hybrid"),"LP",SOURCE)
    assert [(r["value"],r["seed"]) for r in b] == [(r["value"],r["seed"]) for r in c[5:]]


def test_plateau_inverse_deterministic_and_no_extrapolation():
    assert _plateau_inverse([1,2,3,4],[10,20,20,40],20)==2
    assert _plateau_inverse([1,2,3,4],[40,20,20,10],20)==2
    assert _plateau_inverse([1,2,3,4],[10,20,20,40],30)==3.5
    assert _plateau_inverse([1,2],[20,20],20)==1
    with pytest.raises(ValueError):_plateau_inverse([1,2],[20,20],10)


@pytest.mark.parametrize("mutation", ["extrapolate","clip","badmode","negative_n","badinterval","hugetolerance","unknownartifact"])
def test_invalid_sampling_rejected(mutation):
    c=recipe("hybrid");s=c["sampling"]
    if mutation=="extrapolate":s["quality_target"]["allow_extrapolation"]=True
    elif mutation=="clip":s["quality_target"]["unsupported_target_policy"]="clip"
    elif mutation=="badmode":s["mode"]="PE"
    elif mutation=="negative_n":s["quality_target"]["targets_per_artifact"]=-1
    elif mutation=="badinterval":s["quality_target"]["intervals"]=[[60,40]]
    elif mutation=="hugetolerance":s["hybrid"]["parameter_atol"]["LP"]=2000
    else:c["artifacts"]["PE"]={}
    with pytest.raises(ValueError):validate_recipe(c)


@pytest.fixture
def fixture_manifest(tmp_path):
    t=np.arange(44100)/44100
    # Tonal high band exercises UN above every crossover, not just length checks.
    x=.05*np.sin(2*np.pi*1100*t)+.03*np.sin(2*np.pi*11200*t)
    sf.write(tmp_path/"clean.wav",x,44100,subtype="DOUBLE")
    m=tmp_path/"sources.jsonl";write_jsonl(m,[{"source_id":"independent-fixture","source_file":"clean.wav","is_functional_test_signal":True}])
    return m


@pytest.mark.parametrize("mode", ["odaq_knots","quality_target","hybrid"])
def test_actual_triplets_metadata_determinism_export_and_cli(tmp_path,fixture_manifest,mode):
    c=recipe(mode);a=tmp_path/"a";b=tmp_path/"b"
    count=40 if mode=="hybrid" else 20
    assert generate(c,a,manifest=fixture_manifest)["sample_count"]==count
    assert generate(c,b,manifest=fixture_manifest)["sample_count"]==count
    for p in a.rglob("*"):
        if p.is_file():assert p.read_bytes()==(b/p.relative_to(a)).read_bytes(),str(p)
    records=read_jsonl(a/"metadata.jsonl")
    for r in records:
        assert r["schema_version"]=="mapped-poc-v2" and r["sampling_mode"]==mode
        assert r["perceptual_annotation"]["human_mushra_score"] is None
        assert r["calibration_estimate"]["has_actual_human_ratings"] is False
        assert not r["calibration_estimate"]["operator_transfer_validated"]
        wave={k:sf.read(a/v["path"],always_2d=True) for k,v in r["audio"].items()}
        assert all(sr==44100 and x.shape==(44100,1) and np.isfinite(x).all() for x,sr in wave.values())
        assert np.array_equal(wave["residual"][0],wave["degraded"][0]-wave["reference"][0])
        if r["degradation"]["artifact_type"]=="UN":assert r["degradation"]["parameters"]["strength"]==1
        for origin in r["sampling"]["origins"]:
            if origin["requested_quality_target"] is not None:assert abs(origin["target_forward_difference"])<1e-8
        assert r["calibration_estimate"]["estimated_quality_mean"] is not None
    assert validate_dataset(a)["valid"]
    config=tmp_path/"config.json";config.write_text(json.dumps(c))
    assert main(["build","--config",str(config),"--manifest",str(fixture_manifest),"--dataset-id","sampling-test","--clip-seconds","1","--output",str(tmp_path/"bundle"),"--audio-prefix","data/sampling-test"])==0
    assert check_export(tmp_path/"bundle")["sample_count"]==count
    assert (tmp_path/"bundle/dataset/sampling_summary.json").exists()
    for split in ("train","valid","test"):
        for row in read_jsonl(tmp_path/"bundle"/(split+".jsonl")):
            assert set(row)=={"messages","audios"} and len(row["audios"])==2


def test_v1_default_and_guard_unchanged():
    old=default_config()
    assert old["schema_version"]=="mapped-poc-1" and "sampling" not in old
    assert all(v=={"quality_targets":[50,65,75]} for v in old["artifacts"].values())
    assert resolve_config()==validate_recipe(old)
    changed=deepcopy(old);changed["artifacts"]["LP"]["quality_targets"]=[50]
    with pytest.raises(ValueError):check_shared_config(changed)
    with pytest.raises(ValueError):resolve_config(sampling_mode="hybrid")


def test_all_unsupported_generate_leaves_report(tmp_path,fixture_manifest):
    c=recipe("quality_target");c["sampling"]["quality_target"]={"strategy":"explicit","targets":[10]}
    out=tmp_path/"unsupported"
    result=generate(c,out,manifest=fixture_manifest)
    assert result["sample_count"]==0 and result["valid"]
    report=json.loads((out/"sampling_summary.json").read_text())
    assert report["skipped_count"]==4 and report["retained"]==0


def test_all_unsupported_build_retains_diagnostics(tmp_path,fixture_manifest):
    c=recipe("quality_target");c["sampling"]["quality_target"]={"strategy":"explicit","targets":[10]}
    out=tmp_path/"diagnostic-bundle"
    result=build(out,"data/diagnostic","unsupported",manifest=fixture_manifest,clip_seconds=1,config=c)
    assert result["valid"] and not result["training_ready"]
    assert result["sampling_summary"]["skipped_count"]==4
    assert (out/"dataset/sampling_report.jsonl").exists()
    assert not (out/"train.jsonl").exists()


def test_v2_metadata_tampering_detected(tmp_path,fixture_manifest):
    c=recipe("odaq_knots");c["artifacts"]={"QN":{}}
    out=tmp_path/"tamper";generate(c,out,manifest=fixture_manifest)
    rows=read_jsonl(out/"metadata.jsonl")
    rows[0]["sampling"]["origins"][0]["nominal_parameter"]=99
    write_jsonl(out/"metadata.jsonl",rows)
    for r in rows:(out/"metadata"/(r["sample_id"]+".json")).write_text(json.dumps(r))
    assert "Nominal condition/bridge mismatch" in validate_dataset(out)["errors"]


def test_prepared_output_labels_do_not_count_as_benchmark_sources(tmp_path,fixture_manifest):
    from deepmushra_mapped.preparation import prepare
    prepared=tmp_path/"odaq_knots-prepared"
    prepare(prepared,"sampling-odaq_knots",manifest=fixture_manifest,clip_seconds=1)
    c=recipe("odaq_knots");c["artifacts"]={"LP":{}}
    assert generate(c,tmp_path/"allowed",manifest=prepared/"sources.jsonl")["sample_count"]==5
    rows=read_jsonl(prepared/"sources.jsonl")
    rows[0]["source_provenance"]["original_source_file"]="ODAQ/reference.wav"
    write_jsonl(prepared/"sources.jsonl",rows)
    with pytest.raises(ValueError,match="ODAQ"):generate(c,tmp_path/"blocked",manifest=prepared/"sources.jsonl")


def test_plateau_lookup_api(monkeypatch):
    import deepmushra_mapped.mapping as mapping
    table=deepcopy(mapping.load_table())
    table["artifacts"]["LP"]["quality_mean"]=[10,20,20,40,50]
    monkeypatch.setattr(mapping,"load_table",lambda:table)
    assert mapping.parameter_for_quality("LP",20)==9000
    assert mapping.parameter_for_quality("LP",30)==11250
