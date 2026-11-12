"""One public CLI for preparing, generating and sharing synthetic AudioLM data."""
import argparse,json
from pathlib import Path
import yaml
from deepmushra_data.training_export import export_training_jsonl
from .pipeline import generate,validate_dataset
from .profile import default_config,check_shared_config,release_profile,resolve_config
from .preparation import prepare
from .collaboration import build,merge,check_export


def _sources(p):
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest",type=Path);source.add_argument("--input-dir",type=Path)

def _prepare_options(p):
    p.add_argument("--dataset-id",required=True);p.add_argument("--clip-seconds",type=float,default=8.)
    p.add_argument("--shard-index",type=int,default=0);p.add_argument("--shard-count",type=int,default=1)

def _sampling_options(parser):
    parser.add_argument("--profile",choices=("mapped-poc-1","mapped-poc-v2"),help="Default remains mapped-poc-1")
    parser.add_argument("--config",type=Path,help="V1 fixed shared config or a fingerprinted v2 sampling recipe")
    parser.add_argument("--sampling-mode",choices=("odaq_knots","quality_target","hybrid"),help="Override sampling mode in a v2 recipe")


def main(argv=None):
    p=argparse.ArgumentParser(description="Shared LP/SH/UN/QN generators and exact hwangbo/train JSONL bundles")
    sub=p.add_subparsers(dest="command",required=True)
    for name in ("build","prepare","generate"):
        g=sub.add_parser(name);g.add_argument("--output",type=Path,required=True);_sources(g)
        if name in ("build","prepare"):_prepare_options(g)
        if name=="build":g.add_argument("--audio-prefix",required=True,help="Final bundle directory relative to the training checkout root")
        if name in ("build", "generate"):
            _sampling_options(g)
    v=sub.add_parser("validate");v.add_argument("--dataset",type=Path,required=True)
    e=sub.add_parser("export-training");e.add_argument("--dataset",type=Path,required=True);e.add_argument("--output",type=Path,required=True)
    e.add_argument("--audio-prefix");e.add_argument("--relative-to",type=Path,help="Reference-only compatibility export; requires original dataset")
    e.add_argument("--description",choices=("technical","perceptual_candidate"),default="technical");e.add_argument("--prompt-file",type=Path)
    e.add_argument("--include-no-effect",action="store_true",help="Include no-op records; default omits them")
    c=sub.add_parser("check-export");c.add_argument("--bundle",type=Path,required=True);c.add_argument("--relative-to",type=Path)
    m=sub.add_parser("merge");m.add_argument("--inputs",type=Path,nargs="+",required=True);m.add_argument("--output",type=Path,required=True);m.add_argument("--relative-to",type=Path,required=True)
    _sampling_options(sub.add_parser("profile"))
    a=p.parse_args(argv)
    try:
        if a.command in ("prepare","build"):
            kwargs={k:getattr(a,k) for k in ("output","dataset_id","manifest","input_dir","clip_seconds","shard_index","shard_count")}
            result=build(audio_prefix=a.audio_prefix,config=resolve_config(a.config,a.profile,a.sampling_mode),**kwargs) if a.command=="build" else prepare(**kwargs)
        elif a.command=="generate":
            config=resolve_config(a.config,a.profile,a.sampling_mode)
            result=generate(config,a.output,manifest=a.manifest,input_dir=a.input_dir)
        elif a.command=="validate":
            config=json.loads((a.dataset/"resolved_config.json").read_text())
            if config.get("schema_version") in ("mapped-poc-1", "mapped-poc-v2"):result=validate_dataset(a.dataset)
            else:
                # Read-only verification of historical files; old generation is not exposed.
                from deepmushra_data.validation import validate_dataset as old_validate
                result=old_validate(a.dataset)
        elif a.command=="export-training":
            portable=a.relative_to is None
            if portable and not a.audio_prefix:raise ValueError("Portable export requires --audio-prefix; use --relative-to only for reference-only exports")
            result=export_training_jsonl(a.dataset,a.output,description=a.description,relative_to=a.relative_to,
                prompt=a.prompt_file.read_text() if a.prompt_file else None,bundle_audio=portable,audio_prefix=a.audio_prefix,skip_no_effect=not a.include_no_effect)
        elif a.command=="check-export":result=check_export(a.bundle,a.relative_to)
        elif a.command=="merge":result=merge(a.inputs,a.output,a.relative_to)
        else:result={"valid":True,**release_profile(resolve_config(a.config,a.profile,a.sampling_mode))}
    except (ValueError,OSError,KeyError,TypeError,RuntimeError) as error:
        print("error: "+str(error),file=__import__("sys").stderr);return 1
    print(json.dumps(result,indent=2,sort_keys=True,allow_nan=False));return 0 if result.get("valid",True) else 1

if __name__=="__main__":raise SystemExit(main())
