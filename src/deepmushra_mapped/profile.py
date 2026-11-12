"""Single shared recipe, deterministic split assignment, and team compatibility ID."""
import importlib.metadata
import json
from pathlib import Path
import platform
import soundfile as sf
from deepmushra_data.config import digest, file_checksum, stable_seed

ROOT=Path(__file__).parent

def default_config(profile_id="mapped-poc-1"):
    if profile_id not in ("mapped-poc-1", "mapped-poc-v2"):
        raise ValueError("Unknown generator profile")
    filename = "profile.json" if profile_id == "mapped-poc-1" else "profile-v2.json"
    return json.loads((ROOT/filename).read_text())["config"]

def release_profile(config=None):
    modules={}
    for package in (ROOT,ROOT.parent/"deepmushra_data"):
        for p in sorted(package.glob("*.py")):modules[package.name+"/"+p.name]=file_checksum(p)
    if config is None:
        config = default_config()
    else:
        from .pipeline import validate_recipe
        config = validate_recipe(config)
    payload={"profile_id":config["schema_version"],"config":config,"modules":modules,
        "mapping_table_sha256":file_checksum(ROOT/"mapping_table.json"),"training_contract_sha256":file_checksum(ROOT/"training_contract.json"),
        "numerical_environment":{"python":".".join(platform.python_version_tuple()[:2]),
            **{name:importlib.metadata.version(name) for name in ("numpy","scipy","soundfile")},"libsndfile":sf.__libsndfile_version__}}
    return {"fingerprint":digest(payload),**payload}

def check_shared_config(config):
    from .pipeline import validate_recipe
    resolved=validate_recipe(config)
    if resolved["schema_version"] == "mapped-poc-v2":
        return resolved  # The complete selected recipe is fingerprinted and checked on merge.
    expected=validate_recipe(default_config())
    if resolved!=expected:raise ValueError("Configuration differs from the shared release profile; use configs/generator.yaml unchanged")
    return resolved

def stable_splits(sources,proportions,seed):
    result={}
    for source in sources:
        key=source["source_id"]
        value=stable_seed(seed,key,"global-source-split-v1")
        split="train" if value<int(proportions["train"]*2**64) else "validation" if value<int((proportions["train"]+proportions["validation"])*2**64) else "test"
        result[key]=split
    return result


def resolve_config(config_path=None, profile_id=None, sampling_mode=None):
    """V1 stays fixed; v2 accepts validated recipes and records the complete recipe hash."""
    if config_path is not None:
        import yaml
        path = Path(config_path)
        config = json.loads(path.read_text()) if path.suffix.lower() == ".json" else yaml.safe_load(path.read_text())
        if not isinstance(config, dict):
            raise ValueError("Configuration must be an object")
        if profile_id is not None and config.get("schema_version") != profile_id:
            raise ValueError("Config and --profile versions disagree")
    else:
        config = default_config(profile_id or "mapped-poc-1")
    if sampling_mode is not None:
        if config.get("schema_version") != "mapped-poc-v2":
            raise ValueError("Sampling modes require --profile mapped-poc-v2 or a v2 config")
        config["sampling"]["mode"] = sampling_mode
    return check_shared_config(config)
