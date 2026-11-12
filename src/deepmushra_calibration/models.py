"""Small parameter-to-quality models with bounded interpolation domains."""
import numpy as np
from scipy.optimize import isotonic_regression

MODEL_NAMES = ("lookup_linear", "isotonic", "source_shrinkage")
SHRINKAGE_GRID = (0., 1., 3., 9., None)


def fit_curve(parameters, responses, *, increasing, monotonic):
    x = np.asarray(parameters, dtype=float)
    y = np.asarray(responses, dtype=float)
    if x.ndim != 1 or y.shape != x.shape or len(x) < 2:
        raise ValueError("A curve requires at least two paired parameter knots")
    if not np.isfinite(x).all() or not np.isfinite(y).all() or np.any(np.diff(x) <= 0):
        raise ValueError("Parameters must be finite, distinct and sorted")
    fitted = isotonic_regression(y, increasing=increasing).x if monotonic else y.copy()
    return {"x": x.tolist(), "quality": fitted.tolist(), "increasing": bool(increasing)}


def interpolate(curve, parameter):
    x = np.asarray(curve["x"])
    if not np.isfinite(parameter) or not x[0] <= parameter <= x[-1]:
        raise ValueError("Parameter is outside the calibrated domain; extrapolation is disabled")
    return float(np.interp(parameter, x, curve["quality"]))


def cohort_weights(rows, target_counts, multipliers=None):
    """Normalize observed participant weights within each prespecified cohort."""
    members = {}
    for row in rows:
        members[row["listener_id"]] = row["stratum"]
    active = set(members.values())
    population = sum(target_counts[name] for name in active)
    if not population:
        raise ValueError("No represented cohorts")
    denominator = {name: 0. for name in active}
    for uid, stratum in members.items():
        value = 1. if multipliers is None else float(multipliers[uid])
        if value <= 0 or not np.isfinite(value):
            raise ValueError("Bootstrap weights must be finite and positive")
        denominator[stratum] += value
    return {
        uid: target_counts[stratum] / population
        * (1. if multipliers is None else multipliers[uid]) / denominator[stratum]
        for uid, stratum in members.items()
    }


def average_curve(rows, x, target_counts, multipliers=None):
    weights = cohort_weights(rows, target_counts, multipliers)
    means = []
    for value in x:
        selected = [row for row in rows if row["parameter"] == value]
        # The design is complete: each participant contributes the same source set.
        source_count = len({row["source"] for row in selected})
        total = sum(weights[row["listener_id"]] * row["score"] / source_count for row in selected)
        means.append(total)
    return means


def fit_models(rows, target_counts, increasing, shrinkage, multipliers=None):
    if any(row["role"] != "calibration" for row in rows):
        raise ValueError("Only calibration records may enter model fitting")
    x = sorted({row["parameter"] for row in rows})
    pooled = average_curve(rows, x, target_counts, multipliers)
    lookup = fit_curve(x, pooled, increasing=increasing, monotonic=False)
    monotone = fit_curve(x, pooled, increasing=increasing, monotonic=True)
    source_curves = {}
    for source in sorted({row["source"] for row in rows}):
        selected = [row for row in rows if row["source"] == source]
        local = fit_curve(x, average_curve(selected, x, target_counts, multipliers),
                          increasing=increasing, monotonic=True)
        n = len({row["listener_id"] for row in selected})
        fraction = n / (n + shrinkage) if shrinkage is not None else 0.
        local["quality"] = (
            fraction * np.array(local["quality"]) + (1-fraction) * np.array(monotone["quality"])
        ).tolist()
        source_curves[source] = local
    return {
        "lookup_linear": {"pooled": lookup, "sources": {}},
        "isotonic": {"pooled": monotone, "sources": {}},
        "source_shrinkage": {"pooled": monotone, "sources": source_curves,
                             "shrinkage_pseudo_listeners": shrinkage},
    }


def predict(model, parameter, source=None):
    curve = model["sources"].get(source, model["pooled"])
    return interpolate(curve, parameter)


def select_shrinkage(rows, target_counts, increasing):
    """Leave one calibration listener out; held-out benchmark votes never enter."""
    if any(row["role"] != "calibration" for row in rows):
        raise ValueError("Cross-validation accepts calibration listeners only")
    ids = sorted({row["listener_id"] for row in rows})
    weights = cohort_weights(rows, target_counts)
    candidates = []
    for penalty in SHRINKAGE_GRID:
        error = 0.
        fold_rows = []
        for uid in ids:
            training = [row for row in rows if row["listener_id"] != uid]
            validation = [row for row in rows if row["listener_id"] == uid]
            model = fit_models(training, target_counts, increasing, penalty)["source_shrinkage"]
            mse = float(np.mean([(predict(model, row["parameter"], row["source"])-row["score"])**2 for row in validation]))
            absent = sorted(set(target_counts)-{row["stratum"] for row in training})
            error += weights[uid] * mse
            fold_rows.append({"listener_id": uid, "mse": mse, "unrepresented_training_strata": absent})
        candidates.append({"penalty": penalty, "weighted_mse": error, "folds": fold_rows})
    # Ties favor stronger shrinkage. None denotes the completely pooled curve.
    selected = min(candidates, key=lambda item: (
        item["weighted_mse"], -(float("inf") if item["penalty"] is None else item["penalty"])
    ))
    return selected["penalty"], candidates
