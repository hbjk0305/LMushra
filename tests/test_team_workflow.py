from copy import deepcopy
import json
from pathlib import Path
import shutil
import numpy as np
import pytest
import soundfile as sf
from deepmushra_data.config import file_checksum
from deepmushra_data.metadata import write_json,write_jsonl,read_jsonl
from deepmushra_mapped.preparation import prepare
from deepmushra_mapped.profile import default_config,stable_splits,release_profile,check_shared_config
from deepmushra_mapped.collaboration import build,check_export,check_row,merge
from deepmushra_mapped.cli import main

@pytest.fixture
def raw_sources(tmp_path):
    root=tmp_path/"raw";root.mkdir();entries=[]
    for i in range(6):
        sr=48000 if i%2 else 44100;t=np.arange(int(sr*1.1))/sr
        x=.07*np.sin(2*np.pi*(700+73*i)*t)+.04*np.sin(2*np.pi*(11000+37*i)*t)
        p=root/f"recording{i}.wav"
        sf.write(p,x if i%2==0 else np.column_stack((x,.8*x)),sr,subtype="DOUBLE")
        entries.append({"source_id":f"song{i}","source_file":p.name,"content_category":"functional_test_music", "is_functional_test_signal":True,
                        "source_provenance":{"license":"generated test signal"}})
    manifest=root/"raw.jsonl";write_jsonl(manifest,entries)
    return root,manifest

def test_prepare_native_rate_conversion_groups_and_shards(tmp_path,raw_sources):
    root,m=raw_sources;full=tmp_path/"full";repeat=tmp_path/"repeat"
    for out in (full,repeat):assert prepare(out,"corpus",manifest=m,clip_seconds=1)["clips"]==6
    for p in full.rglob("*"):
        if p.is_file():assert p.read_bytes()==(repeat/p.relative_to(full)).read_bytes()
    rows=read_jsonl(full/"sources.jsonl")
    all_ids={r["source_id"] for r in rows};shards=[]
    for index in range(2):
        out=tmp_path/f"shard{index}";prepare(out,"corpus",manifest=m,clip_seconds=1,shard_index=index,shard_count=2)
        subset=read_jsonl(out/"sources.jsonl");shards.append({r["source_id"] for r in subset})
        for row in subset:
            x,sr=sf.read(out/row["source_file"],always_2d=True)
            assert sr==44100 and x.shape==(44100,1) and np.isfinite(x).all()
            assert (out/row["source_file"]).read_bytes()==(full/row["source_file"]).read_bytes()
            assert row["source_provenance"]["original_header"]["sample_rate"] in (44100,48000)
    assert not shards[0]&shards[1] and shards[0]|shards[1]==all_ids
    sources=[{"source_id":s} for s in sorted(all_ids)]
    expected=stable_splits(sources,default_config()["splits"],default_config()["seed"])
    for ids in shards:
        assert stable_splits([{"source_id":s} for s in ids],default_config()["splits"],default_config()["seed"])=={s:expected[s] for s in ids}

@pytest.mark.parametrize("change",["lowrate","upsampled","stereo4","too_short","bad_shard","bad_namespace","nonfinite"])
def test_preparation_rejects_invalid_inputs(tmp_path,raw_sources,change):
    root,m=raw_sources;entries=read_jsonl(m)[:1];p=root/entries[0]["source_file"]
    kw={"clip_seconds":1}
    if change=="lowrate":sf.write(p,np.zeros(16000),16000)
    elif change=="upsampled":entries[0]["source_provenance"]["original_header"]={"sample_rate":16000}
    elif change=="stereo4":sf.write(p,np.zeros((44100,4)),44100)
    elif change=="too_short":sf.write(p,np.zeros(100),44100)
    elif change=="bad_shard":kw.update(shard_index=2,shard_count=2)
    elif change=="nonfinite":sf.write(p,np.full(44100,np.nan),44100,subtype="DOUBLE")
    write_jsonl(m,entries)
    out=tmp_path/"invalid"
    with pytest.raises(ValueError):prepare(out,"bad/name" if change=="bad_namespace" else "corpus",manifest=m,**kw)
    assert not out.exists()
    assert not list(tmp_path.glob('.invalid.preparing-*'))

def test_shared_profile_is_fixed():
    assert check_shared_config(default_config())["schema_version"]=="mapped-poc-1"
    changed=deepcopy(default_config());changed["artifacts"]["QN"]["quality_targets"]=[50]
    with pytest.raises(ValueError,match="shared release"):check_shared_config(changed)
    assert release_profile()==release_profile()

@pytest.fixture
def portable_bundle(tmp_path,raw_sources):
    root,m=raw_sources
    entries=read_jsonl(m)[:3];small=root/'small.jsonl';write_jsonl(small,entries)
    destination=tmp_path/'training/data/team'
    result=build(destination,'data/team','corpus',manifest=small,clip_seconds=1)
    assert result['generated_samples']==36
    return destination,tmp_path/'training',root,small

def test_exact_training_contract_portability_and_complete_metadata(tmp_path,portable_bundle):
    bundle,training_root,raw,manifest=portable_bundle
    report=check_export(bundle,training_root)
    assert report['sample_count']>0
    for split in ('train','valid','test'):
        rows=read_jsonl(bundle/(split+'.jsonl'));sides=read_jsonl(bundle/(split+'.metadata.jsonl'))
        for row,side in zip(rows,sides):
            assert set(row)=={'messages','audios'}
            assert [m['role'] for m in row['messages']]==['user','assistant']
            assert len(row['audios'])==row['messages'][0]['content'].count('<audio>')==2
            assert all(p.startswith('data/team/dataset/audio/') for p in row['audios'])
            assert 'calibration_estimate' in side['metadata']
            assert side['metadata']['perceptual_annotation']['human_mushra_score'] is None
            assert (training_root/side['audio_paths']['residual']).exists()
    moved=tmp_path/'new-machine/data/team';moved.parent.mkdir(parents=True);shutil.copytree(bundle,moved)
    shutil.rmtree(bundle);shutil.rmtree(raw)
    assert check_export(moved,tmp_path/'new-machine')['sample_count']==report['sample_count']
    assert check_export(moved)['valid']
    assert (moved/'source_clips/sources.jsonl').exists()

@pytest.mark.parametrize('damage',['audio','metadata','wrong_order','extra_keys','prefix'])
def test_export_detects_corruption(tmp_path,portable_bundle,damage):
    bundle,training_root,_,_=portable_bundle
    export=json.loads((bundle/'export_report.json').read_text())
    split=next(s for s in ('train','valid','test') if export['split_counts'][s])
    rows=read_jsonl(bundle/(split+'.jsonl'));sides=read_jsonl(bundle/(split+'.metadata.jsonl'))
    if damage=='audio':(training_root/rows[0]['audios'][0]).write_bytes(b'bad')
    elif damage=='metadata':
        path=training_root/sides[0]['source_dataset']/'metadata'/(sides[0]['sample_id']+'.json')
        path.write_text('{}')
    else:
        if damage=='wrong_order':rows[0]['audios'].reverse()
        elif damage=='extra_keys':rows[0]['score']=42
        else:rows[0]['audios'][0]='../escape.wav'
        write_jsonl(bundle/(split+'.jsonl'),rows)
        export['files'][split+'.jsonl']=file_checksum(bundle/(split+'.jsonl'));write_json(bundle/'export_report.json',export)
    with pytest.raises((ValueError,OSError)):check_export(bundle,training_root)

def test_merge_disjoint_workers_and_reject_duplicates(tmp_path,raw_sources):
    raw,m=raw_sources;root=tmp_path/'training';bundles=[]
    for i in range(2):
        bundle=root/f'data/worker{i}';build(bundle,f'data/worker{i}','corpus',manifest=m,clip_seconds=1,shard_index=i,shard_count=2);bundles.append(bundle)
    reports=[check_export(b,root) for b in bundles]
    result=merge(bundles,root/'data/combined',root)
    assert result['sample_count']==sum(r['sample_count'] for r in reports)
    assert check_export(root/'data/combined',root)['valid']
    with pytest.raises(ValueError,match='Duplicate'):merge([bundles[0],bundles[0]],root/'data/duplicate',root)
    assert not (root/'data/duplicate').exists()

def test_merge_rejects_generator_drift(tmp_path,raw_sources,monkeypatch):
    raw,m=raw_sources;entries=read_jsonl(m);root=tmp_path/'training'
    first=raw/'first.jsonl';second=raw/'second.jsonl';write_jsonl(first,entries[:2]);write_jsonl(second,entries[2:4])
    build(root/'data/first','data/first','first',manifest=first,clip_seconds=1)
    import deepmushra_mapped.pipeline as pipeline
    original=pipeline.release_profile
    def drift():
        result=deepcopy(original());result['modules']['test-version']='changed';return result
    monkeypatch.setattr(pipeline,'release_profile',drift)
    build(root/'data/second','data/second','second',manifest=second,clip_seconds=1)
    with pytest.raises(ValueError,match='fingerprints differ'):merge([root/'data/first',root/'data/second'],root/'data/bad',root)

def test_canonical_cli_and_atomic_failure(tmp_path,raw_sources):
    _,m=raw_sources
    assert main(['profile'])==0
    assert main(['prepare','--manifest',str(m),'--dataset-id','corpus','--output',str(tmp_path/'clean'),'--clip-seconds','1'])==0
    assert main(['generate','--manifest',str(tmp_path/'clean/sources.jsonl'),'--output',str(tmp_path/'generated')])==0
    assert main(['validate','--dataset',str(tmp_path/'generated')])==0
    assert main(['export-training','--dataset',str(tmp_path/'generated'),'--output',str(tmp_path/'export'),'--audio-prefix','data/export'])==0
    assert main(['check-export','--bundle',str(tmp_path/'export')])==0
    assert main(['build','--manifest',str(m),'--dataset-id','corpus','--output',str(tmp_path/'broken'),'--audio-prefix','../escape','--clip-seconds','1'])==1
    assert not (tmp_path/'broken').exists() and not list(tmp_path.glob('.broken.building-*'))


def test_split_boundaries_and_expected_coverage(monkeypatch):
    import deepmushra_mapped.profile as profile
    values={"train":int(.699*2**64),"valid":int(.75*2**64),"test":int(.9*2**64)}
    monkeypatch.setattr(profile,"stable_seed",lambda seed,key,tag:values[key])
    result=profile.stable_splits([{"source_id":key} for key in values],{"train":.7,"validation":.15,"test":.15},123)
    assert result=={"train":"train","valid":"validation","test":"test"}


def test_portable_build_repeat_has_no_staging_paths(tmp_path,raw_sources):
    raw,m=raw_sources;small=raw/"repeat-small.jsonl";write_jsonl(small,read_jsonl(m)[:1])
    a=tmp_path/"machine-a/data/corpus";b=tmp_path/"machine-b/data/corpus"
    for out in (a,b):build(out,"data/corpus","repro-corpus",manifest=small,clip_seconds=1)
    for p in a.rglob("*"):
        if p.is_file():assert p.read_bytes()==(b/p.relative_to(a)).read_bytes(),str(p.relative_to(a))
    report=json.loads((a/"export_report.json").read_text())
    assert "output" not in report
    assert ".building-" not in json.dumps(report)
