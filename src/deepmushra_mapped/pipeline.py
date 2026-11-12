"""Small source-disjoint mapped batches; frozen priors remain estimated labels."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import numpy as np
import soundfile as sf
import yaml
from deepmushra_data.audioio import write_wav
from deepmushra_data.config import digest, file_checksum, stable_seed, validate_config
from deepmushra_data.sources import discover_sources, assign_splits, read_source
from deepmushra_data.metadata import write_json, write_jsonl, measure, processing_regions
from deepmushra_data.stft import STFTConfig
from deepmushra_data.pipeline import _environment, _revision
from .generators import generate_effect, VERSION
from .profile import stable_splits, release_profile
from .mapping import load_table, estimate_quality, parameter_for_quality, TABLE_PATH
from .sampling import validate_sampling, sample_requests, attach_sampling_metadata, validate_sampling_record


def validate_recipe(config):
    if not isinstance(config,dict) or set(config)-{"schema_version","seed","input","splits","artifacts","sampling"}:
        raise ValueError("Unknown mapped config fields")
    if config.get("schema_version") not in ("mapped-poc-1", "mapped-poc-v2"):raise ValueError("Expected mapped-poc-1 or mapped-poc-v2 schema")
    is_v2 = config["schema_version"] == "mapped-poc-v2"
    if not is_v2 and "sampling" in config:raise ValueError("Sampling modes require mapped-poc-v2")
    c=deepcopy(config)
    base=validate_config({"seed":c.get("seed",20261111),"input":c.get("input",{}),
        "splits":c.get("splits",{"train":.7,"validation":.15,"test":.15}),
        "artifacts":{"LP":{"settings":[{"cutoff_hz":10000}]}}})
    c.update({k:base[k] for k in ("seed","input","splits")})
    if c["input"]["sample_rates"]!=[44100] or c["input"]["channels"]!=[1]:
        raise ValueError("Mapped profile requires sample_rates:[44100], channels:[1]")
    if not isinstance(c.get("artifacts"),dict) or not c["artifacts"]:raise ValueError("No artifacts configured")
    if is_v2:
        c["sampling"] = validate_sampling(c.get("sampling"))
    for a,spec in c["artifacts"].items():
        if a not in load_table()["artifacts"]:raise ValueError("Only LP/SH/UN/QN; PE/TM held out")
        if is_v2:
            if spec != {}:raise ValueError("V2 artifacts use empty setting objects; configure the sampling section")
            continue
        if not isinstance(spec,dict) or len(spec)!=1 or next(iter(spec)) not in ("quality_targets","parameters"):
            raise ValueError("Each artifact needs quality_targets or parameters")
        kind,values=next(iter(spec.items()))
        if not isinstance(values,list) or not values:raise ValueError("Empty settings")
        for v in values:
            p=parameter_for_quality(a,v) if kind=="quality_targets" else v
            if estimate_quality(a,p)["support_status"]!="inside":raise ValueError("Unsupported parameter request")
    return c


def description(artifact,p):
    if artifact=="LP":text=f"Low-pass filtering has a passband edge of {p['cutoff_hz']/1000:.2f} kHz."
    elif artifact=="SH":text=f"Random spectral bands above 4 kHz are zeroed with per-band/block probability {p['hole_probability']:.1%}."
    elif artifact=="UN":text=f"Peak-selected bands above {p['crossover_hz']/1000:.2f} kHz are replaced with envelope-shaped noise."
    else:text=f"Local spectral-shaped noise is added at a target waveform SNR of {p['snr_db']:.2f} dB."
    candidate={"LP":"High-frequency detail may be reduced.","SH":"The sound may have intermittent spectral gaps.",
        "UN":"Selected high-frequency content may sound less tonal.","QN":"Added noise may make the sound rougher or noisier."}[artifact]
    return {"technical":text,"perceptual_candidate":candidate,"perceptual_candidate_status":"unverified"}


def generate(config,output,manifest=None,input_dir=None):
    c=validate_recipe(config);output=Path(output).resolve()
    if output.exists():raise ValueError("Output exists; choose a fresh directory")
    sources=discover_sources(input_dir=input_dir,manifest=manifest,policy=c["input"])
    for s in sources:
        provenance = deepcopy(s["source_provenance"])
        source_path = str(s["path"])
        if isinstance(provenance.get("preparation"), dict) and provenance["preparation"].get("version") == "prepare-v1":
            # Prepared paths and dataset_id are output labels, not recording origin.
            # Preserve inspection of original_source_file, original dataset and all other origin facts.
            source_path = provenance.get("original_source_file", source_path)
            provenance.pop("dataset_id", None)
        if "odaq" in source_path.lower() or "odaq" in json.dumps(provenance).lower():
            raise ValueError("ODAQ sources must not enter synthetic generation")
    splits=stable_splits(sources,c["splits"],c["seed"])
    output.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix="."+output.name+".building-",dir=output.parent))
    records=[];sampling_reports=[];config_hash=digest(c);stft=STFTConfig()
    profile=release_profile()
    profile={k:v for k,v in profile.items() if k!="fingerprint"}
    profile["config"]=c
    profile["profile_id"]=c["schema_version"]
    profile={"fingerprint":digest(profile),**profile}
    source_hash=digest({p.name:file_checksum(p) for p in sorted(Path(__file__).parent.glob("*.py"))})
    try:
        write_json(stage/"resolved_config.json",c)
        for source in sources:
            x,sr=read_source(source["path"],c["input"])
            peak=float(abs(x).max());gain=min(1.,c["input"]["source_peak_limit"]/peak) if peak else 1.
            x=x*gain
            ref=Path("audio/reference")/(source["checksum"]+".wav")
            (stage/ref).parent.mkdir(parents=True,exist_ok=True);write_wav(stage/ref,x,sr)
            x,_=sf.read(stage/ref,always_2d=True)
            for artifact,spec in sorted(c["artifacts"].items()):
                if c["schema_version"] == "mapped-poc-v2":
                    requests, sampling_report = sample_requests(c, artifact, source)
                    sampling_reports.append(sampling_report)
                else:
                    kind, values = next(iter(spec.items()))
                    requests = [{"kind":kind,"value":v} for v in values]
                for index,request in enumerate(requests):
                    kind, v = request["kind"], request["value"]
                    seed=request["seed"] if "seed" in request else stable_seed(c["seed"],source["source_id"],source["checksum"],artifact,index,v,VERSION)
                    kwargs={"quality":v} if kind=="quality_targets" else {"parameter":v}
                    result,prior=generate_effect(artifact,x,seed,**kwargs)
                    sample_id=digest([VERSION,source_hash,config_hash,file_checksum(TABLE_PATH),source["checksum"],source["source_id"],artifact,index])[:24]
                    folder=Path("audio")/sample_id;(stage/folder).mkdir(parents=True)
                    deg=folder/"degraded.wav";err=folder/"residual.wav"
                    # Safety gain is never fitted separately on degraded audio.
                    if float(abs(result.audio).max())>c["input"]["output_peak_limit"]:
                        raise ValueError("Output peak exceeded; lower shared source_peak_limit and rerun")
                    write_wav(stage/deg,result.audio,sr);y,_=sf.read(stage/deg,always_2d=True)
                    residual=y-x
                    if float(abs(residual).max())>c["input"]["output_peak_limit"]:raise ValueError("Residual peak exceeded; lower shared source_peak_limit")
                    write_wav(stage/err,residual,sr)
                    ep=Path("evidence")/(sample_id+".npz");(stage/ep).parent.mkdir(exist_ok=True)
                    np.savez_compressed(stage/ep,**result.arrays)
                    stats=measure(x,y,sr,stft,result.arrays,artifact,result.parameters)
                    if not np.any(x) or not result.evidence["transformation_applied"] or stats["relative_residual_energy"] is None or stats["relative_residual_energy"]<1e-20:
                        prior={**prior,"status":"no_effect_quality_not_estimated","estimated_quality_mean":None,"estimated_quality_category":None,
                            "estimated_quality_loss_proxy":None,"conditional_reference_listener_weight_95_band":None}
                    if artifact=="QN" and stats["measured_snr_db"] is not None:
                        prior=estimate_quality(artifact,stats["measured_snr_db"])
                        if prior["support_status"]!="inside" and abs(stats["measured_snr_db"]-result.parameters["snr_db"])<1e-9:
                            prior=estimate_quality(artifact,result.parameters["snr_db"])
                        prior["actual_saved_waveform_snr_db"]=stats["measured_snr_db"]
                    record={"schema_version":c["schema_version"],"sample_id":sample_id,
                        "source":{"source_id":source["source_id"],"source_file":source["source_file"],"source_checksum_sha256":source["checksum"],
                          "source_provenance":source["source_provenance"],"content_category":source["content_category"],"sample_rate":sr,
                          "sample_count":len(x),"channels":1,"duration_s":len(x)/sr,"split":splits[source["source_id"]],"shared_source_gain":gain, "is_functional_test_signal":source["is_functional_test_signal"]},
                        "audio":{role:{"path":str(p),"sha256":file_checksum(stage/p),"subtype":"DOUBLE"} for role,p in [("reference",ref),("degraded",deg),("residual",err)]},
                        "degradation":{"artifact_type":artifact,"profile_version":VERSION,"parameters":result.parameters,"random_seed":seed,
                          "algorithm_evidence":result.evidence,"mask":{"path":str(ep),"sha256":file_checksum(stage/ep)},
                          "regions":processing_regions(result.arrays,sr,len(x),stft)},
                        "measurements":stats,"calibration_estimate":prior,
                        "request":{"kind":kind,"value":v},
                        "perceptual_annotation":{"audibility":None,"perceived_severity":None,"quality_category":None,"human_mushra_score":None,"status":"unverified"},
                        "descriptions":description(artifact,result.parameters),
                        "provenance":{"generator_profile_fingerprint":profile["fingerprint"],"configuration_sha256":config_hash,"mapped_source_sha256":source_hash,"mapping_table_sha256":file_checksum(TABLE_PATH)}}
                    if "sampling" in request:
                        attach_sampling_metadata(record, request)
                    write_json(stage/"metadata"/(sample_id+".json"),record);records.append(record)
        if sampling_reports:
            write_jsonl(stage/"sampling_report.jsonl",sampling_reports)
            write_json(stage/"sampling_summary.json",{
                "sampling_mode":c["sampling"]["mode"],
                **{key:sum(r[key] for r in sampling_reports) for key in ("attempted","supported_before_deduplication","retained","skipped_count","deduplicated_count")},
                "artifacts":{a:{key:sum(r[key] for r in sampling_reports if r["artifact"]==a) for key in ("attempted","supported_before_deduplication","retained","skipped_count","deduplicated_count")} for a in sorted(c["artifacts"])}})
        write_jsonl(stage/"metadata.jsonl",records)
        manifest_rows=[{"sample_id":r["sample_id"],"source_id":r["source"]["source_id"],"split":r["source"]["split"],
            "artifact":r["degradation"]["artifact_type"],"audio":{k:v["path"] for k,v in r["audio"].items()},
            "metadata":f"metadata/{r['sample_id']}.json","technical_description":r["descriptions"]["technical"],
            "estimated_quality_mean":r["calibration_estimate"]["estimated_quality_mean"],"label_status":r["calibration_estimate"]["status"]} for r in records]
        write_jsonl(stage/"manifest.jsonl",manifest_rows)
        for split in ("train","validation","test"):
            write_jsonl(stage/"manifests"/(split+".jsonl"),[r for r in manifest_rows if r["split"]==split])
        write_json(stage/"run.json",{"profile_version":c["schema_version"],"source_groups":len(splits),"source_split_map":splits,"samples":len(records),
            "artifact_counts":dict(Counter(r["artifact"] for r in manifest_rows)),"held_out_artifacts":["PE","TM"],"environment":_environment(),
            "configuration_sha256":config_hash,"mapping_table_sha256":file_checksum(TABLE_PATH),"mapped_source_sha256":source_hash,"generator_profile":profile,"split_policy":"global-source-hash-v1",**_revision()})
        report=validate_dataset(stage);write_json(stage/"validation_summary.json",report)
        if not report["valid"]:raise ValueError(str(report["errors"]))
        if output.exists():raise ValueError("Output appeared during generation")
        stage.rename(output);return report
    except BaseException:
        shutil.rmtree(stage);raise


def validate_dataset(root):
    root=Path(root);rows=[json.loads(line) for line in (root/"metadata.jsonl").read_text().splitlines()]
    errors=[];groups={};checksums={};max_error=0.
    config=json.loads((root/"resolved_config.json").read_text())
    policy=config["input"]
    if not rows and config["schema_version"] != "mapped-poc-v2":errors.append("Empty dataset")
    seen=set()
    manifest=[json.loads(line) for line in (root/"manifest.jsonl").read_text().splitlines()]
    if len(manifest)!=len(rows):errors.append("Manifest count mismatch")
    if len({r["sample_id"] for r in manifest})!=len(manifest):errors.append("Duplicate manifest sample")
    for r in rows:
        source=r["source"];sid=r["sample_id"]
        if sid in seen:errors.append("Duplicate sample")
        seen.add(sid)
        if source["sample_rate"]!=44100 or source["channels"]!=1:errors.append("Invalid source format metadata")
        if json.loads((root/"metadata"/(sid+".json")).read_text())!=r:errors.append("Individual metadata mismatch")
        matching=[v for v in manifest if v["sample_id"]==sid]
        if len(matching)!=1 or matching[0]["split"]!=source["split"] or matching[0]["audio"]!={k:v["path"] for k,v in r["audio"].items()}:
            errors.append("Manifest reference mismatch")
        if config["schema_version"] == "mapped-poc-v2":
            errors.extend(validate_sampling_record(r))
        cal=r["calibration_estimate"]
        if cal["human_mushra_score"] is not None or cal["mono_transfer_validated"] or cal["operator_transfer_validated"]:
            errors.append("Estimated labels must retain transfer status")
        if r["descriptions"]["perceptual_candidate_status"]!="unverified":errors.append("Unverified description status required")
        for grouping,key in [(groups,source["source_id"]),(checksums,source["source_checksum_sha256"])]:
            if key in grouping and grouping[key]!=source["split"]:errors.append("Source leakage")
            grouping[key]=source["split"]
        if r["degradation"]["artifact_type"] not in ("LP","SH","UN","QN"):errors.append("Held-out artifact")
        if any(r["perceptual_annotation"][k] is not None for k in ("audibility","perceived_severity","quality_category","human_mushra_score")):errors.append("Human annotations must remain unknown")
        audio={}
        for role,info in r["audio"].items():
            p=root/info["path"];x,sr=sf.read(p,always_2d=True)
            if file_checksum(p)!=info["sha256"]:errors.append("Checksum mismatch "+sid)
            if sr!=44100 or x.shape!=(source["sample_count"],1) or not np.isfinite(x).all():errors.append("Invalid waveform "+sid)
            if abs(x).max()>policy["output_peak_limit"]:errors.append("Peak limit violation "+sid)
            audio[role]=x
        if not np.array_equal(audio["residual"],audio["degraded"]-audio["reference"]):errors.append("Residual mismatch "+sid)
        max_error=max(max_error,float(abs(audio["reference"]+audio["residual"]-audio["degraded"]).max()))
        ep=root/r["degradation"]["mask"]["path"]
        if not ep.exists() or file_checksum(ep)!=r["degradation"]["mask"]["sha256"]:errors.append("Evidence checksum mismatch")
    if config["schema_version"] == "mapped-poc-v2":
        reports = [json.loads(line) for line in (root/"sampling_report.jsonl").read_text().splitlines()]
        summary = json.loads((root/"sampling_summary.json").read_text())
        if sum(r["retained"] for r in reports) != len(rows) or summary["retained"] != len(rows):
            errors.append("Sampling retained count mismatch")
        for report in reports:
            if report["attempted"] != report["retained"] + report["skipped_count"] + report["deduplicated_count"]:
                errors.append("Sampling accounting mismatch")
    return {"valid":not errors,"errors":errors,"sample_count":len(rows),"source_groups":len(groups),"max_residual_reconstruction_error":max_error}
