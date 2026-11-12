"""Prepare independently supplied high-rate recordings, with recording-level shards."""
import json
from pathlib import Path
import re
import shutil
import tempfile
import numpy as np
from scipy.signal import resample_poly
from math import gcd
import soundfile as sf
from deepmushra_data.audioio import write_wav
from deepmushra_data.config import digest, file_checksum, stable_seed
from deepmushra_data.metadata import write_json, write_jsonl


def prepare(output,dataset_id,manifest=None,input_dir=None,clip_seconds=8.,shard_index=0,shard_count=1):
    if not isinstance(dataset_id,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*",dataset_id):raise ValueError("dataset-id must contain letters/numbers/._- only")
    if not isinstance(clip_seconds,(int,float)) or isinstance(clip_seconds,bool) or not np.isfinite(clip_seconds) or not 1<=clip_seconds<=30:
        raise ValueError("clip-seconds must be between1 and30")
    if isinstance(shard_count,bool) or not isinstance(shard_count,int) or not isinstance(shard_index,int) or not 0<=shard_index<shard_count:
        raise ValueError("Require 0 <= shard-index < shard-count")
    if (manifest is None)==(input_dir is None):raise ValueError("Provide manifest or input-dir")
    output=Path(output).resolve()
    if output.exists():raise ValueError("Preparation output exists; choose a new directory")
    if manifest:
        manifest=Path(manifest).resolve();base=manifest.parent
        entries=[json.loads(line) for line in manifest.read_text().splitlines() if line.strip()]
    else:
        base=Path(input_dir).resolve()
        if not base.is_dir():raise ValueError("Input directory not found")
        entries=[{"source_file":str(p.relative_to(base)),"source_id":str(p.relative_to(base).with_suffix("")),"content_category":"unknown"}
            for p in sorted(base.rglob("*")) if p.suffix.lower() in (".wav",".flac") and p.is_file()]
    if not entries:raise ValueError("No input recordings")
    output.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix="."+output.name+".preparing-",dir=output.parent))
    result=[];selected=0;seen={};groups={}
    try:
        for e in entries:
            if not isinstance(e,dict) or not isinstance(e.get("source_id"),str) or not e["source_id"].strip():raise ValueError("Every source requires a nonempty source_id")
            if not isinstance(e.get("source_file"),str):raise ValueError("Every source requires source_file")
            group=e.get("recording_group_id",dataset_id+":"+e["source_id"])
            if not isinstance(group,str) or not group.strip():raise ValueError("recording_group_id must be nonempty")
            if stable_seed(group,"recording-shard-v1")%shard_count!=shard_index:continue
            path=(base/e["source_file"]).resolve();provenance=e.get("source_provenance",{})
            if not isinstance(provenance,dict):raise ValueError("source_provenance must be an object")
            json.dumps(provenance,allow_nan=False)
            if "odaq" in str(path).lower() or "odaq" in json.dumps(provenance).lower():raise ValueError("ODAQ inputs excluded")
            info=sf.info(path)
            if info.format not in ("WAV","WAVEX","FLAC") or info.samplerate<44100 or info.channels not in (1,2):
                raise ValueError("Inputs must be native >=44100Hz mono/stereo WAV/FLAC")
            original=provenance.get("original_header",{}).get("sample_rate",info.samplerate)
            if original<44100:raise ValueError("Known original rate below44100Hz; upsampling does not qualify")
            raw_hash=file_checksum(path)
            if raw_hash in groups and groups[raw_hash]!=group:raise ValueError("Identical recordings have different source_id; use a common recording group")
            groups[raw_hash]=group
            if raw_hash in seen:continue
            seen[raw_hash]=True;selected+=1
            chunk=int(round(clip_seconds*info.samplerate))
            with sf.SoundFile(path) as handle:
                for start in range(0,info.frames,chunk):
                    handle.seek(start);audio=handle.read(min(chunk,info.frames-start),dtype="float64",always_2d=True)
                    if len(audio)/info.samplerate<1:continue
                    if not np.isfinite(audio).all() or abs(audio).max()>1:raise ValueError("Invalid/full-scale source waveform")
                    mono=np.mean(audio,axis=1,keepdims=True)
                    if info.samplerate!=44100:
                        divisor=gcd(info.samplerate,44100)
                        mono=resample_poly(mono,44100//divisor,info.samplerate//divisor,axis=0,window=("kaiser",5.0),padtype="constant")
                    peak=float(abs(mono).max());gain=min(1.,.95/peak) if peak else 1.
                    mono*=gain
                    clip_id=digest([group,raw_hash,start,len(audio),44100,"prepare-v1"])[:24]
                    relative=Path("clips")/(clip_id+".wav");(stage/relative).parent.mkdir(exist_ok=True)
                    write_wav(stage/relative,mono,44100)
                    result.append({"source_id":group,"source_file":str(relative),"content_category":e.get("content_category","unknown"),
                      "is_functional_test_signal":bool(e.get("is_functional_test_signal",False)),
                      "source_provenance":{**provenance,"dataset_id":dataset_id,"recording_id":e["source_id"],
                        "original_source_file":e["source_file"],"original_source_checksum_sha256":raw_hash,
                        "original_header":provenance.get("original_header",{"sample_rate":info.samplerate,"channels":info.channels,"sample_count":info.frames,"subtype":info.subtype}),
                        "preparation":{"version":"prepare-v1","input_rate":info.samplerate,"input_channels":info.channels,"start_sample":start,"input_samples":len(audio),
                          "downmix":"arithmetic channel mean","output_rate":44100,"resampling":"identity" if info.samplerate==44100 else "resample_poly Kaiser5 constant; rational exact ratio",
                          "shared_preparation_gain":gain,"output_samples":len(mono)},"prepared_sha256":file_checksum(stage/relative)}})
        if not result:raise ValueError("No eligible clips in this shard; check shard assignment and durations")
        write_jsonl(stage/"sources.jsonl",result)
        report={"valid":True,"version":"prepare-v1","dataset_id":dataset_id,"recordings":selected,"clips":len(result),"clip_seconds":clip_seconds,
                "shard_index":shard_index,"shard_count":shard_count,"source_groups":len({r["source_id"] for r in result}),"sample_rate":44100,"channels":1}
        write_json(stage/"preparation_report.json",report)
        if output.exists():raise ValueError("Output appeared during preparation")
        stage.rename(output);return report
    except BaseException:
        shutil.rmtree(stage,ignore_errors=True);raise
