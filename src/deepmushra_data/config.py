"""Validated YAML recipes and stable, order-independent identifiers."""

from copy import deepcopy
import hashlib
from itertools import product
import json
from pathlib import Path

import numpy as np
import yaml

from . import MIN_SAMPLE_RATE, TRAINING_ARTIFACTS
from .degradations import DEFAULTS, resolve_parameters
from .stft import STFTConfig


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def stable_seed(*parts):
    return int(digest(parts)[:16], 16)


def file_checksum(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def _keys(mapping, allowed, name):
    if not isinstance(mapping, dict):
        raise ValueError(f"{name} must be a mapping")
    unknown = set(mapping) - set(allowed)
    if unknown:
        raise ValueError(f"Unknown {name} keys: {sorted(unknown)}")


def load_config(path):
    with Path(path).open() as stream:
        return validate_config(yaml.safe_load(stream))


def validate_config(raw):
    _keys(raw, {"schema_version", "seed", "input", "splits", "stft", "artifacts", "include_identity"}, "config")
    c = deepcopy(raw)
    if c.get("schema_version", 1) != 1:
        raise ValueError("Unsupported configuration schema_version")
    c["schema_version"] = 1
    c.setdefault("seed", 20261101)
    _integer(c["seed"], "seed")
    c.setdefault("include_identity", True)
    if not isinstance(c["include_identity"], bool):
        raise ValueError("include_identity must be boolean")
    supplied_input = c.get("input", {})
    _keys(supplied_input, {"sample_rates", "channels", "min_duration_s", "max_duration_s", "source_peak_limit", "output_peak_limit"}, "input")
    c["input"] = {"sample_rates": [44100, 48000], "channels": [1, 2],
                  "min_duration_s": 1.0, "max_duration_s": 30.0,
                  "source_peak_limit": 0.5, "output_peak_limit": 0.999,
                  **supplied_input}
    policy = c["input"]
    rates = policy["sample_rates"]
    if not isinstance(rates, list) or not rates:
        raise ValueError("input.sample_rates must be a nonempty list")
    for sr in rates:
        _integer(sr, "sample_rates", MIN_SAMPLE_RATE)
    if not isinstance(policy["channels"], list) or not policy["channels"] or any(type(x) is not int or x not in (1, 2) for x in policy["channels"]):
        raise ValueError("channels must be a nonempty subset of [1, 2]")
    for key in ("min_duration_s", "max_duration_s", "source_peak_limit", "output_peak_limit"):
        v = policy[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not np.isfinite(v) or v <= 0:
            raise ValueError(f"{key} must be positive and finite")
    if policy["max_duration_s"] < policy["min_duration_s"]:
        raise ValueError("max_duration_s is below min_duration_s")
    if not 0 < policy["source_peak_limit"] <= policy["output_peak_limit"] <= 1:
        raise ValueError("Require 0 < source_peak_limit <= output_peak_limit <= 1")
    c.setdefault("splits", {"train": 0.7, "validation": 0.15, "test": 0.15})
    _keys(c["splits"], {"train", "validation", "test"}, "splits")
    if set(c["splits"]) != {"train", "validation", "test"}:
        raise ValueError("splits must specify train, validation, test")
    weights = list(c["splits"].values())
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not np.isfinite(x) or x < 0 for x in weights) or not np.isclose(sum(weights), 1, atol=1e-9, rtol=0):
        raise ValueError("Split proportions must be finite, nonnegative, and sum to one")
    c.setdefault("stft", {})
    _keys(c["stft"], {"n_fft", "hop_length"}, "stft")
    stft = STFTConfig(**c["stft"])
    c["stft"] = {"n_fft": stft.n_fft, "hop_length": stft.hop_length}
    artifacts = c.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise ValueError("artifacts must be a nonempty mapping of LP, SH, UN, QN")
    for artifact, spec in artifacts.items():
        if artifact not in TRAINING_ARTIFACTS:
            raise ValueError(f"{artifact} is not a training augmentation; PE and TM are held out")
        _keys(spec, {"defaults", "settings", "sampling"}, artifact)
        defaults = spec.setdefault("defaults", {})
        _keys(defaults, set(DEFAULTS[artifact]) | ({"cutoff_hz"} if artifact == "LP" else set()), f"{artifact}.defaults")
        if ("settings" in spec) == ("sampling" in spec):
            raise ValueError(f"{artifact} must specify exactly one of settings or sampling")
        if "settings" in spec:
            if not isinstance(spec["settings"], list) or not spec["settings"]:
                raise ValueError("settings must be a nonempty list")
            for entry in spec["settings"]:
                if not isinstance(entry, dict):
                    raise ValueError("Each setting must be a parameter mapping")
                tier = entry.get("parameter_tier", "unspecified")
                if tier not in ("unspecified", "subtle", "moderate", "strong"):
                    raise ValueError("parameter_tier must be unspecified, subtle, moderate, or strong")
                supplied = {**defaults, **{k: v for k, v in entry.items() if k != "parameter_tier"}}
                for sr in rates:
                    resolve_parameters(artifact, supplied, sr)
        else:
            sampling = spec["sampling"]
            _keys(sampling, {"count", "parameters"}, "sampling")
            _integer(sampling.get("count"), "sampling.count", 1)
            if not isinstance(sampling.get("parameters"), dict) or not sampling["parameters"]:
                raise ValueError("sampling.parameters must be a nonempty mapping")
            allowed_parameters = set(DEFAULTS[artifact]) | ({"cutoff_hz"} if artifact == "LP" else set())
            for name, rule in sampling["parameters"].items():
                if name not in allowed_parameters:
                    raise ValueError(f"Unknown sampled parameter {name}")
                _validate_sampling_rule(rule)
            # Validate every choice and every combination of numeric range endpoints.
            # Independent ranges can violate joint constraints only at mixed corners
            # (e.g. maximum passband ripple paired with minimum attenuation).
            names = sorted(sampling["parameters"])
            candidates = [next(iter(sampling["parameters"][name].values())) for name in names]
            for values in product(*candidates):
                bound = {**defaults, **dict(zip(names, values))}
                for sr in rates:
                    resolve_parameters(artifact, bound, sr)
    canonical_json(c)
    return c


def _validate_sampling_rule(rule):
    if not isinstance(rule, dict) or len(rule) != 1:
        raise ValueError("Sampling rule must specify one of uniform, loguniform, randint, choice")
    kind, values = next(iter(rule.items()))
    if kind not in ("uniform", "loguniform", "randint", "choice") or not isinstance(values, list) or not values:
        raise ValueError("Invalid sampling rule")
    if kind == "choice":
        return
    if len(values) != 2 or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not np.isfinite(x) for x in values) or values[0] > values[1]:
        raise ValueError("Sampling bounds must be two finite, ordered numbers")
    if kind == "loguniform" and values[0] <= 0:
        raise ValueError("loguniform bounds must be positive")
    if kind == "randint":
        for v in values:
            _integer(v, "randint bound")


def recipes(config, artifact, source_key):
    spec = config["artifacts"][artifact]
    defaults = spec["defaults"]
    if "settings" in spec:
        for index, setting in enumerate(spec["settings"]):
            yield index, {**defaults, **{k: v for k, v in setting.items() if k != "parameter_tier"}}, setting.get("parameter_tier", "unspecified")
        return
    for index in range(spec["sampling"]["count"]):
        rng = np.random.default_rng(stable_seed(config["seed"], source_key, artifact, index, "parameters"))
        params = defaults.copy()
        for name, rule in sorted(spec["sampling"]["parameters"].items()):
            kind, values = next(iter(rule.items()))
            if kind == "choice":
                value = values[int(rng.integers(len(values)))]
            elif kind == "uniform":
                value = float(rng.uniform(*values))
            elif kind == "loguniform":
                value = float(np.exp(rng.uniform(*np.log(values))))
            else:
                value = int(rng.integers(values[0], values[1] + 1))
            params[name] = value
        yield index, params, "unspecified"
