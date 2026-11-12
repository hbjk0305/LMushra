"""Portable team bundles, strict training-contract validation and safe merging."""
from collections import Counter
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import numpy as np
import soundfile as sf
from deepmushra_data.config import file_checksum
from deepmushra_data.metadata import write_json, write_jsonl
from deepmushra_data.training_export import export_training_jsonl
from .preparation import prepare
from .pipeline import generate,validate_dataset
from .profile import default_config,release_profile

SPLITS=("train","valid","test")

def check_row(row):
    if not isinstance(row,dict) or set(row)!={"messages","audios"}:raise ValueError("Training row must have exactly messages and audios")
    messages=row["messages"];audio=row["audios"]
    if not isinstance(messages,list) or len(messages)!=2 or not all(isinstance(m,dict) and set(m)=={"role","content"} for m in messages):raise ValueError("Exactly two role/content messages required")
    if [m["role"] for m in messages]!=["user","assistant"]:raise ValueError("Message order must be user, assistant")
    if not all(isinstance(m["content"],str) and m["content"].strip() for m in messages):raise ValueError("Message contents must be nonempty strings")
    if messages[0]["content"].count("<audio>")!=2 or "<audio>" in messages[1]["content"]:raise ValueError("Exactly two user audio placeholders required")
    if not isinstance(audio,list) or len(audio)!=2 or not all(isinstance(p,str) and p for p in audio):raise ValueError("Two audio paths required")
    for path in audio:
        p=PurePosixPath(path)
        if p.is_absolute() or ".." in p.parts or "\\" in path:raise ValueError("Team training paths must be portable POSIX-relative paths")


def read_bundle(bundle,training_root=None):
    bundle=Path(bundle).resolve();report=json.loads((bundle/"export_report.json").read_text())
    profile=report.get("generator_profile_fingerprint")
    if not isinstance(profile,str) or len(profile)!=64:raise ValueError("Bundle lacks a released generator fingerprint")
    prefix=report.get("portable_audio_prefix")
    root=Path(training_root).resolve() if training_root is not None else None
    if root is None and not prefix:raise ValueError("Merged/reference exports require --relative-to training root")
    def resolve(path):
        rel=PurePosixPath(path)
        if rel.is_absolute() or ".." in rel.parts:raise ValueError("Unsafe training path")
        if root is not None:
            p=(root/str(rel)).resolve()
            if not p.is_relative_to(root):raise ValueError("Training audio escapes root")
            return p
        try:local=rel.relative_to(PurePosixPath(prefix))
        except ValueError as e:raise ValueError("Audio prefix does not match portable bundle") from e
        p=(bundle/str(local)).resolve()
        if not p.is_relative_to(bundle):raise ValueError("Bundle path escape")
        return p
    items=[];ids=set();seen={};counts=Counter()
    for split in SPLITS:
        path=bundle/(split+".jsonl");side=bundle/(split+".metadata.jsonl")
        if file_checksum(path)!=report["files"][path.name] or file_checksum(side)!=report["files"][side.name]:raise ValueError("Export text checksum mismatch")
        data=[json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        sides=[json.loads(l) for l in side.read_text().splitlines() if l.strip()]
        if len(data)!=len(sides):raise ValueError("Model/metadata row count mismatch")
        for index,(row,meta) in enumerate(zip(data,sides)):
            check_row(row)
            if meta["row_index"]!=index or meta["training_split"]!=split:raise ValueError("Sidecar row ordering mismatch")
            rec=meta["metadata"];source=rec["source"]
            declared="valid" if source["split"]=="validation" else source["split"]
            if declared!=split or meta["source_split"]!=source["split"]:raise ValueError("Source split metadata mismatch")
            if meta["sample_id"]!=rec["sample_id"] or meta["source_id"]!=source["source_id"]:raise ValueError("Sidecar source identity mismatch")
            stored=resolve((PurePosixPath(meta["source_dataset"])/"metadata"/(rec["sample_id"]+".json")).as_posix())
            if json.loads(stored.read_text())!=rec:raise ValueError("Copied metadata disagrees with sidecar")
            if rec["sample_id"] in ids:raise ValueError("Duplicate sample ID")
            ids.add(rec["sample_id"])
            if rec["provenance"].get("generator_profile_fingerprint")!=profile:raise ValueError("Record generator fingerprint mismatch")
            if row["audios"]!=[meta["audio_paths"][k] for k in ("reference","degraded")]:raise ValueError("Reference/degraded audio order mismatch")
            keys=[source["source_id"],source["source_checksum_sha256"],rec["audio"]["reference"]["sha256"]]
            original=source.get("source_provenance",{}).get("original_source_checksum_sha256")
            if original:keys.append(original)
            for key in keys:
                if key in seen and seen[key]!=split:raise ValueError("Recording-level train/validation/test leakage")
                seen[key]=split
            audio={}
            for role in ("reference","degraded","residual"):
                p=resolve(meta["audio_paths"][role])
                if file_checksum(p)!=rec["audio"][role]["sha256"]:raise ValueError("Training audio checksum mismatch")
                x,sr=sf.read(p,always_2d=True)
                if sr!=44100 or x.shape!=(source["sample_count"],1) or len(x)>30*sr or not np.isfinite(x).all() or abs(x).max()>1:raise ValueError("Invalid model waveform")
                audio[role]=x
            if not np.array_equal(audio["residual"],audio["degraded"]-audio["reference"]):raise ValueError("Residual reconstruction mismatch")
            if report.get("prepared_sources_prefix"):
                prepared=resolve((PurePosixPath(report["prepared_sources_prefix"])/source["source_file"]).as_posix())
                if file_checksum(prepared)!=source["source_checksum_sha256"]:raise ValueError("Prepared source checksum mismatch")
            ep=resolve((PurePosixPath(meta["source_dataset"])/rec["degradation"]["mask"]["path"]).as_posix())
            if file_checksum(ep)!=rec["degradation"]["mask"]["sha256"]:raise ValueError("Missing/corrupt metadata evidence")
            items.append((split,row,meta));counts[split]+=1
    if not items:raise ValueError("No model records")
    if report["sample_count"]!=len(items) or any(report["split_counts"][s]!=counts[s] for s in SPLITS):raise ValueError("Export report count mismatch")
    return report,items


def check_export(bundle,training_root=None):
    report,items=read_bundle(bundle,training_root)
    return {"valid":True,"sample_count":len(items),"split_counts":report["split_counts"],"generator_profile_fingerprint":report["generator_profile_fingerprint"],
            "training_contract":report["contract"],"external_training_paths_checked":training_root is not None}


def build(output,audio_prefix,dataset_id,manifest=None,input_dir=None,clip_seconds=8.,shard_index=0,shard_count=1,config=None):
    config=default_config() if config is None else config
    output=Path(output).resolve()
    if not isinstance(audio_prefix,str) or not audio_prefix or "\\" in audio_prefix or PurePosixPath(audio_prefix).is_absolute() or ".." in PurePosixPath(audio_prefix).parts:
        raise ValueError("audio-prefix must be a nonempty portable relative POSIX path")
    if output.exists():raise ValueError("Output exists; choose a new bundle directory")
    output.parent.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix="."+output.name+".building-",dir=output.parent))
    try:
        preparation=prepare(work/"prepared",dataset_id,manifest,input_dir,clip_seconds,shard_index,shard_count)
        generated=generate(config,work/"generated",manifest=work/"prepared/sources.jsonl")
        if generated["sample_count"] == 0:
            # A fully rejected target list still leaves an auditable diagnostic bundle.
            # It is explicitly not an empty training dataset masquerading as usable data.
            (work/"bundle").mkdir()
            shutil.copytree(work/"generated",work/"bundle/dataset")
            shutil.copytree(work/"prepared",work/"bundle/source_clips")
            result={"valid":True,"training_ready":False,"reason":"no_supported_sampling_requests",
                "generated_samples":0,"training_samples":0,"skipped_no_effect":0,
                "sampling_summary":json.loads((work/"generated/sampling_summary.json").read_text())}
            write_json(work/"bundle/sampling_only_report.json",result)
            write_json(work/"bundle/generator_profile.json",release_profile(config))
            if output.exists():raise ValueError("Output appeared during build")
            (work/"bundle").rename(output)
            return {**result,"output":str(output)}
        report=export_training_jsonl(work/"generated",work/"bundle",bundle_audio=True,audio_prefix=audio_prefix,skip_no_effect=True)
        shutil.copytree(work/"prepared",work/"bundle/source_clips")
        report.pop("output",None)  # The returned runtime path must not enter portable provenance.
        report["prepared_sources_prefix"]=(PurePosixPath(audio_prefix)/"source_clips").as_posix()
        write_json(work/"bundle/export_report.json",report)
        write_json(work/"bundle/preparation_report.json",preparation)
        write_json(work/"bundle/generator_profile.json",release_profile(config))
        verified=check_export(work/"bundle")
        write_json(work/"bundle/bundle_verification.json",verified)
        if output.exists():raise ValueError("Output appeared during build")
        (work/"bundle").rename(output)
        return {"valid":True,"output":str(output),"generated_samples":generated["sample_count"],"training_samples":report["sample_count"],
                "skipped_no_effect":report["skipped_no_effect_count"],"split_counts":report["split_counts"],"fingerprint":report["generator_profile_fingerprint"]}
    finally:shutil.rmtree(work,ignore_errors=True)


def merge(inputs,output,training_root):
    output=Path(output).resolve()
    if output.exists():raise ValueError("Merge output exists")
    bundles=[(Path(p).resolve(),*read_bundle(p,training_root)) for p in inputs]
    if len(bundles)<2:raise ValueError("Merge needs at least two worker bundles")
    fingerprints={report["generator_profile_fingerprint"] for _,report,_ in bundles}
    if len(fingerprints)!=1:raise ValueError("Generator fingerprints differ; use the same release, recipe and numerical environment")
    contracts={json.dumps(report["contract"],sort_keys=True) for _,report,_ in bundles}
    if len(contracts)!=1:raise ValueError("Training contracts differ")
    gathered={s:[] for s in SPLITS};seen_ids=set();owners={}
    for owner,report,items in bundles:
        for split,row,meta in items:
            if meta["sample_id"] in seen_ids:raise ValueError("Duplicate samples across worker bundles")
            seen_ids.add(meta["sample_id"]);rec=meta["metadata"];src=rec["source"]
            keys=[src["source_id"],src["source_checksum_sha256"],rec["audio"]["reference"]["sha256"]]
            original=src.get("source_provenance",{}).get("original_source_checksum_sha256")
            if original:keys.append(original)
            for key in keys:
                if key in owners and owners[key]!=(owner,split):raise ValueError("Recording overlap or split leakage between worker bundles")
                owners[key]=(owner,split)
            gathered[split].append((row,meta))
    output.parent.mkdir(parents=True,exist_ok=True);stage=Path(tempfile.mkdtemp(prefix="."+output.name+".merging-",dir=output.parent))
    try:
        counts={}
        for split,pairs in gathered.items():
            pairs.sort(key=lambda pair:pair[1]["sample_id"])
            write_jsonl(stage/(split+".jsonl"),[r for r,_ in pairs])
            write_jsonl(stage/(split+".metadata.jsonl"),[{**m,"row_index":i} for i,(_,m) in enumerate(pairs)])
            counts[split]=len(pairs)
        report={"valid":True,"sample_count":len(seen_ids),"split_counts":counts,"generator_profile_fingerprint":next(iter(fingerprints)),
                "contract":bundles[0][1]["contract"],"portable_audio_prefix":None,"path_style":"merged_references",
                "input_bundles":[str(p) for p,_,_ in bundles],"audio_copied":False,"audio_modified":False,
                "files":{p.name:file_checksum(p) for p in sorted(stage.glob("*.jsonl"))}}
        write_json(stage/"export_report.json",report)
        check_export(stage,training_root)
        if output.exists():raise ValueError("Output appeared during merge")
        stage.rename(output);return report
    except BaseException:
        shutil.rmtree(stage,ignore_errors=True);raise
