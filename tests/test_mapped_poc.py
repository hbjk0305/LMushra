from copy import deepcopy
import json
from pathlib import Path
import numpy as np
import pytest
import soundfile as sf
import yaml
from deepmushra_data.degradations import apply_effect
from deepmushra_data.stft import STFTConfig, analyze
from deepmushra_mapped.mapping import estimate_quality, parameter_for_quality, load_table
from deepmushra_mapped.generators import generate_effect
from deepmushra_mapped.pipeline import generate, validate_dataset, validate_recipe

@pytest.mark.parametrize("artifact",["LP","SH","UN","QN"])
def test_frozen_knots_inverse_and_no_extrapolation(artifact):
    c=load_table()["artifacts"][artifact]
    for x,y in zip(c["x"],c["quality_mean"]):
        estimate=estimate_quality(artifact,x)
        assert estimate["estimated_quality_mean"]==pytest.approx(y)
        assert parameter_for_quality(artifact,y)==pytest.approx(x)
        assert estimate["human_mushra_score"] is None
        assert not estimate["mono_transfer_validated"]
    p=parameter_for_quality(artifact,65.)
    assert estimate_quality(artifact,p)["estimated_quality_mean"]==pytest.approx(65)
    assert estimate_quality(artifact,c["x"][0]-1)["estimated_quality_mean"] is None
    with pytest.raises(ValueError):parameter_for_quality(artifact,min(c["quality_mean"])-1)

def test_reference_values_and_nmr_not_snr():
    assert estimate_quality("LP",12000)["estimated_quality_mean"]==pytest.approx(88.81349206349206)
    c=load_table()["artifacts"]["QN"]
    assert c["axis"]=="waveform_snr_db"
    assert c["x"]!=c["released_parameter_knots"]
    assert c["x"][2]==pytest.approx(12.06516953880947)
    assert estimate_quality("QN",30)["support_status"]=="outside_no_extrapolation"

@pytest.mark.parametrize("artifact",["PE","TM","other"])
def test_no_heldout_generator(artifact):
    with pytest.raises(ValueError):generate_effect(artifact,np.zeros((1000,1)),1,quality=65)

@pytest.mark.parametrize("artifact",["LP","SH","UN","QN"])
def test_mapped_generator_determinism_shapes_silence_and_format(artifact):
    sr=44100;t=np.arange(sr//3)/sr
    x=(.08*np.sin(2*np.pi*1000*t)+.04*np.sin(2*np.pi*11200*t))[:,None]
    a,q=generate_effect(artifact,x,12,quality=65)
    b,qb=generate_effect(artifact,x,12,quality=65)
    np.testing.assert_array_equal(a.audio,b.audio)
    assert a.audio.shape==x.shape and np.isfinite(a.audio).all()
    assert q==qb and q["estimated_quality_mean"]==pytest.approx(65)
    for name in a.arrays:np.testing.assert_array_equal(a.arrays[name],b.arrays[name])
    silent,q=generate_effect(artifact,np.zeros((1500,1)),12,quality=65)
    assert not np.any(silent.audio) and q["estimated_quality_mean"] is None
    with pytest.raises(ValueError):generate_effect(artifact,np.repeat(x,2,axis=1),12,quality=65)
    with pytest.raises(ValueError):generate_effect(artifact,x,12,quality=65,sample_rate=48000)

@pytest.mark.parametrize("artifact",["LP","SH","UN"])
def test_legacy_algorithm_is_preserved(artifact):
    t=np.arange(12000)/44100;x=(.1*np.sin(2*np.pi*11200*t))[:,None]
    mapped,_=generate_effect(artifact,x,4,quality=65)
    old=apply_effect(artifact,x,44100,mapped.parameters,4,STFTConfig())
    np.testing.assert_array_equal(mapped.audio,old.audio)

@pytest.mark.parametrize("snr",[3,12,20])
def test_local_qn_exact_additive_snr_and_causality(snr):
    sr=44100;t=np.arange(sr//2)/sr;x=(.07*np.sin(2*np.pi*11200*t))[:,None];x[:2000]=0;x[-2000:]=0
    a,_=generate_effect("QN",x,3,parameter=snr)
    residual=a.audio-x
    measured=10*np.log10(np.sum(x**2)/np.sum(residual**2))
    assert measured==pytest.approx(snr,abs=1e-10)
    np.testing.assert_allclose(residual,a.arrays["added_noise"],atol=3e-17,rtol=0)
    assert np.all(residual[:2000]==0) and np.all(residual[-2000:]==0)
    basis=np.exp(-2j*np.pi*11200*t)
    assert .8<abs(basis@a.audio[:,0])/abs(basis@x[:,0])<1.2
    other,_=generate_effect("QN",x,4,parameter=snr)
    assert not np.array_equal(a.audio,other.audio)

def test_qn_frame_local_spectral_color():
    sr=44100;t=np.arange(sr)/sr
    x=np.where(t<.5,.1*np.sin(2*np.pi*1000*t),.1*np.sin(2*np.pi*11200*t))[:,None]
    result,_=generate_effect("QN",x,4,parameter=12)
    f,frames,z=analyze(result.arrays["added_noise"],sr,STFTConfig())
    power=abs(z[:,f>7000])**2
    early=float(power[frames<.4].sum());late=float(power[(frames>.6)&(frames<.9)].sum())
    assert early/late<.01

def test_un_noise_negative_control_and_tonal_replacement():
    noise=np.random.default_rng(4).normal(scale=.03,size=(44100,1))
    r,q=generate_effect("UN",noise,4,parameter=7000)
    assert r.arrays["selected_mask"].mean()<.01
    t=np.arange(44100)/44100;x=(.1*np.sin(2*np.pi*11200*t))[:,None]
    r,_=generate_effect("UN",x,4,parameter=7000)
    b=np.exp(-2j*np.pi*11200*t)
    assert abs(b@r.audio[:,0])/abs(b@x[:,0])<.3

@pytest.fixture
def batch_inputs(tmp_path):
    entries=[]
    for i in range(3):
        t=np.arange(12000)/44100;x=(.05*np.sin(2*np.pi*(1000+70*i)*t)+.03*np.sin(2*np.pi*11200*t))[:,None]
        p=tmp_path/f"source{i}.wav";sf.write(p,x,44100,subtype="DOUBLE")
        entries.append({"source_id":f"original{i}","source_file":p.name,"source_provenance":{"dataset":"independent test fixture"}})
    manifest=tmp_path/"sources.jsonl";manifest.write_text("".join(json.dumps(e)+"\n" for e in entries))
    c=yaml.safe_load(Path("configs/generator.yaml").read_text());c["input"]["min_duration_s"]=.1
    for a in c["artifacts"]:c["artifacts"][a]["quality_targets"]=[50,75]
    return c,manifest

def test_pipeline_reproducibility_metadata_and_splits(tmp_path,batch_inputs):
    c,m=batch_inputs;outs=[tmp_path/"run1",tmp_path/"run2"]
    for out in outs:
        result=generate(c,out,manifest=m)
        assert result["valid"] and result["sample_count"]==24
    files=[p.relative_to(outs[0]) for p in outs[0].rglob("*") if p.is_file()]
    for f in files:assert (outs[0]/f).read_bytes()==(outs[1]/f).read_bytes(),str(f)
    rows=[json.loads(line) for line in (outs[0]/"metadata.jsonl").read_text().splitlines()]
    groups={}
    for row in rows:
        assert row["source"]["sample_rate"]==44100 and row["source"]["channels"]==1
        assert row["calibration_estimate"]["estimated_quality_mean"]==pytest.approx(row["request"]["value"],abs=1e-8)
        assert row["perceptual_annotation"]["human_mushra_score"] is None
        groups.setdefault(row["source"]["source_id"],set()).add(row["source"]["split"])
    assert all(len(v)==1 for v in groups.values())  # Hash splits need not fill all partitions in a tiny shard.
    row=rows[0];p=outs[0]/row["audio"]["residual"]["path"]
    x,sr=sf.read(p);x[0]+=.01;sf.write(p,x,sr,subtype="DOUBLE")
    assert not validate_dataset(outs[0])["valid"]

def test_reject_benchmark_sources_and_unsupported_config(tmp_path,batch_inputs):
    c,m=batch_inputs;rows=[json.loads(line) for line in m.read_text().splitlines()]
    rows[0]["source_provenance"]["dataset"]="ODAQ"
    m.write_text("".join(json.dumps(e)+"\n" for e in rows))
    with pytest.raises(ValueError,match="ODAQ"):generate(c,tmp_path/"blocked",manifest=m)
    c["artifacts"]["SH"]["quality_targets"]=[90]
    with pytest.raises(ValueError):validate_recipe(c)


def test_individual_metadata_and_evidence_validation(tmp_path,batch_inputs):
    c,m=batch_inputs;c["artifacts"]={"QN":{"quality_targets":[65]}}
    out=tmp_path/"metadata_validation";generate(c,out,manifest=m)
    rows=[json.loads(line) for line in (out/"metadata.jsonl").read_text().splitlines()]
    p=out/"metadata"/(rows[0]["sample_id"]+".json")
    original=p.read_text();modified=json.loads(original);modified["source"]["channels"]=2;p.write_text(json.dumps(modified))
    assert not validate_dataset(out)["valid"]
    p.write_text(original)
    assert validate_dataset(out)["valid"]
    evidence=out/rows[0]["degradation"]["mask"]["path"];evidence.write_bytes(b"changed")
    assert not validate_dataset(out)["valid"]
