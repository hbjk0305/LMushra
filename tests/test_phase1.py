"""Behavioral tests for added noise and phase-1 integration."""
from copy import deepcopy
import json
import numpy as np
import pytest
import soundfile as sf
from deepmushra_data.degradations import apply_effect, resolve_parameters
from deepmushra_data.metadata import measure, read_jsonl, write_jsonl
from deepmushra_data.pipeline import generate_dataset
from deepmushra_data.stft import STFTConfig

@pytest.mark.parametrize("sr", [44100,48000])
@pytest.mark.parametrize("channels", [1,2])
@pytest.mark.parametrize("snr", [20,30,40])
def test_qn_additive_snr_and_reproducibility(sr,channels,snr):
    t=np.arange(sr//3)/sr
    x=np.repeat((.12*np.sin(2*np.pi*1000*t)+.03*np.sin(2*np.pi*11000*t))[:,None],channels,axis=1)
    a=apply_effect("QN",x,sr,{"snr_db":snr},34)
    b=apply_effect("QN",x,sr,{"snr_db":snr},34)
    assert a.audio.shape==x.shape and np.isfinite(a.audio).all()
    np.testing.assert_array_equal(a.audio,b.audio)
    np.testing.assert_allclose(a.audio-x,a.arrays["added_noise"],atol=3e-17,rtol=0)
    for channel in range(channels):
        measured=10*np.log10(np.sum(x[:,channel]**2)/np.sum((a.audio[:,channel]-x[:,channel])**2))
        assert measured==pytest.approx(snr,abs=1e-11)
    assert not np.array_equal(a.audio,apply_effect("QN",x,sr,{"snr_db":snr},35).audio)
    assert np.max(np.abs(a.audio))<1
    m=measure(x,a.audio,sr,STFTConfig(),a.arrays,"QN",a.parameters)
    assert m["smoothed_noise_reference_psd_cosine"]>.9
    basis=np.exp(-2j*np.pi*1000*t)
    assert .93<abs(basis@a.audio[:,0])/abs(basis@x[:,0])<1.07

@pytest.mark.parametrize("artifact,params", [("LP",{"cutoff_hz":10000}),("SH",{"hole_probability":.7}),
    ("UN",{"crossover_hz":7000,"strength":1}),("QN",{"snr_db":20})])
def test_channel_order_no_crosstalk(artifact,params):
    sr=44100;t=np.arange(sr//5)/sr
    x=np.column_stack((.1*np.sin(2*np.pi*11200*t),np.zeros_like(t)))
    result=apply_effect(artifact,x,sr,params,3)
    assert np.all(result.audio[:,1]==0)
    assert np.any(result.audio[:,0]!=0)

@pytest.mark.parametrize("mode",["linked","independent"])
def test_qn_causal_onset_and_channel_noise_mode(mode):
    sr=44100;x=np.zeros((sr,2));t=np.arange(sr//4)/sr
    x[sr//4:sr//2]=(.1*np.sin(2*np.pi*11000*t))[:,None]
    out=apply_effect("QN",x,sr,{"snr_db":20,"channel_mode":mode},2)
    assert np.all(out.audio[:sr//4]==0)
    assert np.any(out.audio[sr//2:]!=0)
    if mode=="linked": np.testing.assert_array_equal(out.audio[:,0],out.audio[:,1])
    else: assert not np.array_equal(out.audio[:,0],out.audio[:,1])

def test_qn_silence_is_identity():
    x=np.zeros((1000,2));r=apply_effect("QN",x,44100,{},1)
    np.testing.assert_array_equal(r.audio,x)
    assert not r.evidence["transformation_applied"]
    stats=measure(x,r.audio,44100,STFTConfig(),r.arrays,"QN",r.parameters)
    assert stats["measured_snr_db"] is None
    json.dumps(stats,allow_nan=False)

@pytest.mark.parametrize("parameters",[{"snr_db":-1},{"snr_db":101},{"fir_taps":128},
 {"fir_taps":1},{"fir_taps":129.5},{"envelope_ms":0},{"smoothing_hz":0},{"channel_mode":"ms"}])
def test_qn_parameter_validation(parameters):
    with pytest.raises(ValueError): resolve_parameters("QN",parameters,44100)

def test_qn_saved_triplets_provenance_and_determinism(tmp_path,small_config,source_manifest):
    config=deepcopy(small_config)
    config["artifacts"]={"QN":{"settings":[{"snr_db":20},{"snr_db":40}]}}
    entries=read_jsonl(source_manifest)
    for entry in entries: entry["source_provenance"]={"license":"test fixture","artist_and_track":"functional signal"}
    write_jsonl(source_manifest,entries)
    runs=[tmp_path/"a",tmp_path/"b"]
    for root in runs:
        report=generate_dataset(config,root,manifest=source_manifest,diagnostics=False)
        assert report["valid"] and report["sample_count"]==9
    assert (runs[0]/"metadata.jsonl").read_bytes()==(runs[1]/"metadata.jsonl").read_bytes()
    for record in read_jsonl(runs[0]/"metadata.jsonl"):
        assert record["source"]["source_provenance"]["license"]=="test fixture"
        assert record["perceptual_annotation"]["audibility"] is None
        for info in record["audio"].values():
            assert (runs[0]/info["path"]).read_bytes()==(runs[1]/info["path"]).read_bytes()
        mask=record["degradation"]["mask"]["path"]
        assert (runs[0]/mask).read_bytes()==(runs[1]/mask).read_bytes()
        ref,sr=sf.read(runs[0]/record["audio"]["reference"]["path"],always_2d=True)
        deg,_=sf.read(runs[0]/record["audio"]["degraded"]["path"],always_2d=True)
        err,_=sf.read(runs[0]/record["audio"]["residual"]["path"],always_2d=True)
        np.testing.assert_array_equal(err,deg-ref)
