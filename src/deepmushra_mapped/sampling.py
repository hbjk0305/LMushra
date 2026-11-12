"""Versioned request sampling; operators and frozen calibration coordinates are reused."""
from copy import deepcopy
import math
import numpy as np
from deepmushra_data.config import stable_seed
from .mapping import load_table, parameter_for_quality, estimate_quality

MODES = ("odaq_knots", "quality_target", "hybrid")
CONDITIONS = ("Q1", "Q2", "Q3", "Q4", "Q5")
UNITS = {"LP": "Hz", "SH": "probability", "UN": "Hz", "QN": "dB waveform SNR"}
DEFAULT_TOLERANCE = {"LP": 1e-6, "SH": 1e-12, "UN": 1e-6, "QN": 1e-9}


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(name + " must be finite numeric")
    return float(value)


def validate_sampling(value):
    if not isinstance(value, dict) or set(value) - {"mode", "odaq_knots", "quality_target", "hybrid"}:
        raise ValueError("Unknown sampling fields")
    s = deepcopy(value)
    if s.get("mode") not in MODES:
        raise ValueError("Expected sampling mode odaq_knots, quality_target or hybrid")
    k = s.setdefault("odaq_knots", {})
    if not isinstance(k, dict) or set(k) - {"conditions"}:
        raise ValueError("Unknown odaq_knots fields")
    k.setdefault("conditions", list(CONDITIONS))
    if not isinstance(k["conditions"], list) or not k["conditions"] or any(v not in CONDITIONS for v in k["conditions"]) or len(set(k["conditions"])) != len(k["conditions"]):
        raise ValueError("Conditions must be a nonempty unique subset of Q1..Q5")
    # Canonical order is independent of YAML key/list order.
    k["conditions"] = [q for q in CONDITIONS if q in k["conditions"]]
    q = s.setdefault("quality_target", {})
    if not isinstance(q, dict) or set(q) - {"strategy", "targets", "targets_per_artifact", "intervals", "allow_extrapolation", "unsupported_target_policy"}:
        raise ValueError("Unknown quality_target fields")
    q.setdefault("strategy", "continuous_stratified")
    if q["strategy"] not in ("explicit", "continuous_uniform", "continuous_stratified"):
        raise ValueError("Unsupported quality target strategy")
    q.setdefault("allow_extrapolation", False)
    q.setdefault("unsupported_target_policy", "skip_with_report")
    if q["allow_extrapolation"] is not False or q["unsupported_target_policy"] != "skip_with_report":
        raise ValueError("Only bounded skip_with_report sampling is permitted")
    if q["strategy"] == "explicit":
        if not isinstance(q.get("targets"), list) or not q["targets"]:
            raise ValueError("Explicit strategy requires targets")
        q["targets"] = [_number(v, "Quality target") for v in q["targets"]]
        if "intervals" in q or "targets_per_artifact" in q:
            raise ValueError("Explicit targets cannot include continuous settings")
    else:
        if "targets" in q:
            raise ValueError("Continuous strategies cannot include explicit targets")
        q.setdefault("targets_per_artifact", 5)
        n = q["targets_per_artifact"]
        if isinstance(n, bool) or not isinstance(n, int) or not 0 <= n <= 10000:
            raise ValueError("targets_per_artifact must be an integer in [0,10000]")
        if "intervals" in q:
            if q["strategy"] != "continuous_stratified" or not isinstance(q["intervals"], list) or not q["intervals"]:
                raise ValueError("intervals require continuous_stratified")
            previous = -math.inf
            for interval in q["intervals"]:
                if not isinstance(interval, list) or len(interval) != 2:
                    raise ValueError("Intervals must be [lower,upper] pairs")
                lo, hi = [_number(v, "Interval endpoint") for v in interval]
                if lo >= hi or lo < previous:
                    raise ValueError("Intervals must be ordered, nonoverlapping and increasing")
                previous = hi
    h = s.setdefault("hybrid", {})
    if not isinstance(h, dict) or set(h) - {"deduplicate_parameters", "parameter_atol", "parameter_rtol"}:
        raise ValueError("Unknown hybrid fields")
    h.setdefault("deduplicate_parameters", True)
    if not isinstance(h["deduplicate_parameters"], bool):
        raise ValueError("deduplicate_parameters must be boolean")
    atol = h.setdefault("parameter_atol", dict(DEFAULT_TOLERANCE))
    if not isinstance(atol, dict) or set(atol) != set(UNITS):
        raise ValueError("parameter_atol must specify LP/SH/UN/QN")
    for artifact, tolerance in atol.items():
        if _number(tolerance, "Parameter tolerance") < 0 or tolerance > DEFAULT_TOLERANCE[artifact] * 1000:
            raise ValueError("Parameter tolerance is negative or too large for near-duplicate removal")
    h.setdefault("parameter_rtol", 0.)
    if not 0 <= _number(h["parameter_rtol"], "Relative tolerance") <= 1e-9:
        raise ValueError("Relative tolerance must be in [0,1e-9]")
    return s


def knots(artifact):
    """Use the packaged bridge/coordinates, preserving nominal released values and units."""
    curve = load_table()["artifacts"][artifact]
    released = curve["released_parameter_knots"]
    expected = {"LP": [5, 9, 10.5, 12, 15], "SH": [70, 50, 30, 20, 10],
                "UN": [3, 5, 7, 9, 10.5], "QN": [0, 6, 12, 18, 24]}[artifact]
    result = []
    for condition, nominal in zip(CONDITIONS, expected):
        matches = [i for i, v in enumerate(released) if v == nominal]
        if len(matches) != 1:
            result.append({"condition_id": condition, "nominal_parameter": nominal,
                           "reason": "nominal_condition_not_in_frozen_bridge"})
            continue
        i = matches[0]
        parameter = float(curve["x"][i])
        # LP/UN are nominal kHz converted to passband-edge/crossover Hz; SH is percent.
        converted = nominal * 1000 if artifact in ("LP", "UN") else nominal / 100 if artifact == "SH" else parameter
        if not np.isclose(parameter, converted, rtol=0, atol=1e-10):
            raise ValueError("Released condition does not match the frozen coordinate")
        result.append({"condition_id": condition, "nominal_parameter": nominal,
                       "nominal_unit": "kHz" if artifact in ("LP", "UN") else "%" if artifact == "SH" else "dB ODAQ NMR label",
                       "parameter": parameter, "parameter_unit": UNITS[artifact],
                       "bridge": "empirical_QNMS_mono_median_SNR_not_NMR_identity" if artifact == "QN" else None})
    return result


def _targets(spec, curve, rng):
    lo, hi = min(curve["quality_mean"]), max(curve["quality_mean"])
    if spec["strategy"] == "explicit":
        return [(v, None) for v in spec["targets"]], []
    n = spec["targets_per_artifact"]
    if spec["strategy"] == "continuous_uniform":
        return [(float(v), [lo, hi]) for v in rng.uniform(lo, hi, n)], []
    if "intervals" in spec:
        intervals = [[max(lo, a), min(hi, b)] for a, b in spec["intervals"] if max(lo, a) < min(hi, b)]
        excluded = [[a, b] for a, b in spec["intervals"] if max(lo, a) >= min(hi, b)]
    else:
        edges = np.linspace(lo, hi, max(n, 1) + 1)
        intervals = [[float(a), float(b)] for a, b in zip(edges[:-1], edges[1:])]
        excluded = []
    if n and not intervals:
        return [], [{"reason": "no_positive_width_supported_interval", "intervals": spec.get("intervals")}]
    targets = []
    for i in range(n):
        a, b = intervals[i % len(intervals)]
        targets.append((float(rng.uniform(a, b)), [a, b]))
    return targets, [{"reason": "interval_has_no_supported_overlap", "interval": v} for v in excluded]


def sample_requests(config, artifact, source):
    """One deterministic request plan per source clip/artifact, independent of worker order."""
    s = config["sampling"]; curve = load_table()["artifacts"][artifact]
    quality_range = [float(min(curve["quality_mean"])), float(max(curve["quality_mean"]))]
    requests = []; skipped = []; interval_reports = []; attempted = 0
    if s["mode"] in ("odaq_knots", "hybrid"):
        for knot in knots(artifact):
            if knot["condition_id"] not in s["odaq_knots"]["conditions"]:
                continue
            attempted += 1
            if "parameter" not in knot:
                skipped.append({"component": "odaq_knots", **knot})
                continue
            origin = {"component": "odaq_knots", **knot, "requested_quality_target": None,
                      "inverse_policy": None, "quality_interval": None}
            requests.append({"kind": "parameters", "value": knot["parameter"], "parameter": knot["parameter"], "origins": [origin]})
    if s["mode"] in ("quality_target", "hybrid"):
        rng_seed = stable_seed(config["seed"], source["source_id"], source["checksum"], artifact, "quality-sampling-v2")
        targets, interval_reports = _targets(s["quality_target"], curve, np.random.default_rng(rng_seed))
        for i, (target, interval) in enumerate(targets):
            attempted += 1
            origin = {"component": "quality_target", "strategy": s["quality_target"]["strategy"], "target_index": i,
                      "requested_quality_target": target, "quality_interval": interval, "sampling_seed": rng_seed,
                      "condition_id": None, "inverse_policy": "bounded_piecewise_linear; exact plateau -> lowest parameter"}
            if not quality_range[0] <= target <= quality_range[1]:
                skipped.append({**origin, "reason": "quality_outside_calibration_support", "supported_quality_range": quality_range})
                continue
            parameter = parameter_for_quality(artifact, target)
            origin.update(parameter=parameter, parameter_unit=UNITS[artifact], inverse_mapped_parameter=parameter)
            requests.append({"kind": "quality_targets", "value": target, "parameter": parameter, "origins": [origin]})
    before = len(requests); kept = []; duplicates = []
    for request in requests:
        existing = next((r for r in kept if np.isclose(r["parameter"], request["parameter"], atol=s["hybrid"]["parameter_atol"][artifact], rtol=s["hybrid"]["parameter_rtol"])), None) if s["mode"] == "hybrid" and s["hybrid"]["deduplicate_parameters"] else None
        if existing is None:
            kept.append(request)
        else:
            duplicates.append({"parameter": request["parameter"], "kept_parameter": existing["parameter"], "origin": request["origins"][0]})
            existing["origins"].extend(request["origins"])
    for request in kept:
        first = request["origins"][0]
        identity = [first["component"], first.get("condition_id"), first.get("target_index"), request["value"]]
        request["seed"] = stable_seed(config["seed"], source["source_id"], source["checksum"], artifact, identity, "mapped-poc-v2")
        request["sampling"] = {"profile_id": "mapped-poc-v2", "sampling_mode": s["mode"], "component": first["component"],
            "nominal_condition_id": first.get("condition_id"), "parameter_axis": curve["axis"], "parameter_unit": UNITS[artifact],
            "chosen_parameter": request["parameter"], "supported_quality_range": quality_range,
            "supported_parameter_range": [curve["x"][0], curve["x"][-1]], "origins": request.pop("origins"),
            "parameter_interpolation_used": not any(np.isclose(request["parameter"], p, rtol=0, atol=1e-10) for p in curve["x"]),
            "deduplication_policy": {"enabled": s["mode"] == "hybrid" and s["hybrid"]["deduplicate_parameters"],
                "atol": s["hybrid"]["parameter_atol"][artifact], "rtol": s["hybrid"]["parameter_rtol"], "unit": UNITS[artifact]}}
    return kept, {"source_id": source["source_id"], "source_checksum": source["checksum"], "artifact": artifact,
        "sampling_mode": s["mode"], "attempted": attempted, "supported_before_deduplication": before,
        "retained": len(kept), "skipped_count": len(skipped), "deduplicated_count": len(duplicates),
        "skipped": skipped, "deduplicated": duplicates, "interval_reports": interval_reports}


def attach_sampling_metadata(record, request):
    sampling = deepcopy(request["sampling"])
    estimate = record["calibration_estimate"]["estimated_quality_mean"]
    for origin in sampling["origins"]:
        target = origin.get("requested_quality_target")
        origin["forward_estimated_quality"] = estimate
        origin["target_forward_difference"] = float(estimate - target) if estimate is not None and target is not None else None
        origin["target_forward_status"] = "no_effect_quality_not_estimated" if estimate is None else "not_quality_target" if target is None else "verified" if abs(estimate - target) <= 1e-8 else "outside_numerical_tolerance"
    first = sampling["origins"][0]
    sampling["requested_quality_target"] = first.get("requested_quality_target")
    sampling["inverse_mapped_parameter"] = first.get("inverse_mapped_parameter")
    sampling["inverse_policy"] = first.get("inverse_policy")
    sampling["target_forward_difference"] = first["target_forward_difference"]
    sampling["target_forward_tolerance"] = 1e-8
    record["sampling"] = sampling
    record["sampling_mode"] = sampling["sampling_mode"]
    record["calibration_estimate"].update(supported_quality_range=sampling["supported_quality_range"],
        supported_parameter_range=sampling["supported_parameter_range"], parameter_interpolation_used=sampling["parameter_interpolation_used"],
        has_actual_human_ratings=False, calibration_curve_provenance=load_table()["provenance"],
        quality_domain="ODAQ stereo reference-domain prior; synthetic mono transfer unverified")


def validate_sampling_record(record):
    """Cross-check recorded request facts against exact parameters and the frozen curve."""
    errors = []
    sampling = record.get("sampling", {})
    artifact = record["degradation"]["artifact_type"]
    axis = load_table()["artifacts"][artifact]["axis"]
    field = "snr_db" if artifact == "QN" else axis
    p = record["degradation"]["parameters"][field]
    if sampling.get("sampling_mode") != record.get("sampling_mode") or record.get("sampling_mode") not in MODES:
        errors.append("Sampling mode mismatch")
    if sampling.get("chosen_parameter") != p or sampling.get("parameter_unit") != UNITS[artifact]:
        errors.append("Sampling parameter/unit mismatch")
    if artifact == "UN" and record["degradation"]["parameters"]["strength"] != 1.:
        errors.append("UN aligned profile requires strength=1")
    if not sampling.get("origins"):
        errors.append("Sampling origins missing")
    cal = record["calibration_estimate"]
    if cal.get("has_actual_human_ratings") is not False or cal.get("calibration_curve_provenance") != load_table()["provenance"]:
        errors.append("Calibration provenance/human-rating status mismatch")
    for origin in sampling.get("origins", []):
        target = origin.get("requested_quality_target")
        if origin.get("component") == "odaq_knots":
            match = next((k for k in knots(artifact) if k["condition_id"] == origin.get("condition_id")), {})
            if origin.get("nominal_parameter") != match.get("nominal_parameter") or origin.get("parameter") != match.get("parameter"):
                errors.append("Nominal condition/bridge mismatch")
        if target is not None:
            inverse = parameter_for_quality(artifact, target)
            if origin.get("inverse_mapped_parameter") != inverse:
                errors.append("Inverse-mapped parameter mismatch")
        value = cal["estimated_quality_mean"]
        expected = value - target if value is not None and target is not None else None
        if origin.get("target_forward_difference") != expected or origin.get("forward_estimated_quality") != value:
            errors.append("Target/forward difference mismatch")
    return errors
