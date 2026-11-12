"""Fit, freeze, and evaluate ODAQ mappings in separate stages."""
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import stats

from deepmushra_data.metadata import write_json, write_jsonl
from .data import FILES, check_design, check_split, load_ratings, population_counts, sha256
from .models import MODEL_NAMES, cohort_weights, fit_models, predict, select_shrinkage

VERSION = "odaq-calibration-poc-v1"
BOOTSTRAP_SEED = 20261111


def read_csv(path):
    with Path(path).open(newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    rows = list(rows)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        Path(path).write_text("")
        return
    with Path(path).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def digest(value):
    data = json.dumps(value, sort_keys=True, allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


def source_hash():
    return digest({p.name: sha256(p) for p in sorted(Path(__file__).parent.glob("*.py"))})


def new_directory(path):
    path = Path(path)
    if path.exists():
        raise ValueError(f"Output already exists: {path}")
    path.mkdir(parents=True)
    return path


def coupled_weights(people, aliases, role, repetitions, seed):
    selected = [person for person in people
                if person["study"] != "2025-aes-supp" and person["proposed_role"] == role]
    link = {pair["later_listener_id"]: pair["earlier_listener_id"] for pair in aliases}
    blocks = sorted({link.get(person["listener_id"], person["listener_id"]) for person in selected})
    index = {key: position for position, key in enumerate(blocks)}
    rng = np.random.default_rng(seed)
    draws = rng.exponential(size=(repetitions, len(blocks)))
    draws = np.maximum(draws, 1e-12)
    return [
        {person["listener_id"]: float(draw[index[link.get(person["listener_id"], person["listener_id"])]])
         for person in selected}
        for draw in draws
    ], blocks


def basic_mean(rows, counts, multipliers=None):
    weights = cohort_weights(rows, counts, multipliers)
    # One source/level cell has one score for every listener.
    return sum(weights[row["listener_id"]] * row["score"] for row in rows)


def cv_diagnostics(rows, counts, increasing):
    """Outer folds plus calibration-only inner penalty selection for source curves."""
    ids = sorted({row["listener_id"] for row in rows})
    parameters = sorted({row["parameter"] for row in rows})
    sources = sorted({row["source"] for row in rows})
    schemes = {
        "listener": [(uid, lambda row, uid=uid: row["listener_id"] == uid) for uid in ids],
        "interior_parameter": [(str(value), lambda row, value=value: row["parameter"] == value)
                               for value in parameters[1:-1]],
        "source": [(value, lambda row, value=value: row["source"] == value) for value in sources],
    }
    output = []
    for scheme, folds in schemes.items():
        errors = defaultdict(list)
        for label, held in folds:
            training = [row for row in rows if not held(row)]
            validation = [row for row in rows if held(row)]
            penalty, _ = select_shrinkage(training, counts, increasing)
            fitted = fit_models(training, counts, increasing, penalty)
            for name in MODEL_NAMES:
                errors[name].extend([
                    (row, (predict(fitted[name], row["parameter"], row["source"])-row["score"])**2)
                    for row in validation
                ])
        for name in MODEL_NAMES:
            pairs = errors[name]
            if pairs:
                weights = cohort_weights([row for row, _ in pairs], counts)
                denominator = sum(weights[row["listener_id"]] for row, _ in pairs)
                mse = sum(weights[row["listener_id"]]*error for row,error in pairs)/denominator
            else:
                mse = None
            output.append({"scheme": scheme, "model": name, "folds": len(folds),
                           "validation_ratings": len(pairs), "weighted_mse": mse,
                           "weighted_rmse": float(np.sqrt(mse)) if mse is not None else None})
    return output


def mean_diagnostics(rows, counts):
    parameters = sorted({row["parameter"] for row in rows})
    output = []
    for value in parameters:
        selected = [row for row in rows if row["parameter"] == value]
        per_listener = defaultdict(list)
        stratum = {}
        for row in selected:
            per_listener[row["listener_id"]].append(row["score"])
            stratum[row["listener_id"]] = row["stratum"]
        vector = np.array([np.mean(values) for values in per_listener.values()])
        by_stratum = defaultdict(list)
        for uid, scores in per_listener.items():
            by_stratum[stratum[uid]].append(float(np.mean(scores)))
        mean = float(np.mean(vector))
        half = float(stats.t.ppf(.975, len(vector)-1)*np.std(vector, ddof=1)/np.sqrt(len(vector)))
        population = sum(counts.values())
        weighted_mean = sum(counts[h]/population*np.mean(values) for h,values in by_stratum.items())
        estimable = all(len(values)>1 for values in by_stratum.values())
        weighted_half = None
        if estimable:
            components = [(float((counts[h]/population)**2*np.var(values,ddof=1)/len(values)),len(values)-1)
                          for h,values in by_stratum.items()]
            variance = sum(v for v,_ in components)
            denominator = sum(v*v/df for v,df in components)
            df = variance*variance/denominator if denominator else None
            weighted_half = float(stats.t.ppf(.975,df)*np.sqrt(variance)) if df else 0.
        output.append({
            "parameter": value, "listeners": len(vector), "unweighted_source_averaged_mean": mean,
            "unweighted_t95_lower": mean-half, "unweighted_t95_upper": mean+half,
            "cohort_weighted_mean": float(weighted_mean),
            "cohort_weighted_t95_half_width": weighted_half,
            "singleton_strata": "|".join(h for h,values in by_stratum.items() if len(values)==1),
        })
    return output


def fit(release, split_path, alias_path, output, repetitions=2000):
    people, aliases = check_split(split_path, alias_path)
    before = {relative: sha256(Path(release)/relative) for _,_,relative in FILES}
    rows = load_ratings(release, split_path, "calibration")
    groups = check_design(rows, 846)
    destination = new_directory(Path(output)/"fit")
    protocol = {
        "version": VERSION, "stage": "fit", "split_seed": 20261110,
        "bootstrap_seed": BOOTSTRAP_SEED, "bootstrap_repetitions": repetitions,
        "split_sha256": sha256(split_path), "aliases_sha256": sha256(alias_path),
        "source_code_sha256": source_hash(), "csv_checksums": before,
        "population_weighting": "released full-panel stratum fractions; equal sources and parameter cells",
        "methods": list(MODEL_NAMES), "shrinkage_grid": [0,1,3,9,"fully_pooled"],
        "selection": "source-shrinkage penalty only; leave-one-calibration-listener-out weighted MSE",
        "extrapolation": "disabled", "supplement": "excluded from primary POC",
        "excluded_artifacts": ["PE","TM"], "excluded_conditions": ["Ref","LP3.5","LP7","Mono"],
        "interpretation": "ODAQ-informed stereo quality mapping; listener-held-out evaluation",
        "synthetic_transfer_validated": False, "mono_transfer_validated": False,
        "bootstrap_interpretation": "cohort-normalized whole-listener Bayesian bootstrap; shared candidate-alias weights; singleton strata remain fixed",
        "bootstrap_selection_uncertainty": "conditional on the chosen shrinkage penalty",
        "primary_evaluation": "equal-cell RMSE against held-out cohort-weighted means; all three models reported",
    }
    write_json(destination/"protocol.json", protocol)
    draws, blocks = coupled_weights(people, aliases, "calibration", repetitions, BOOTSTRAP_SEED)
    models, cvs, penalty_audit, diagnostics, knot_rows = {},[],{},[],[]
    cells = []
    for group, selected in sorted(groups.items()):
        print(f"Calibration-only fitting: {group}", flush=True)
        counts = population_counts(people, group)
        increasing = selected[0]["artifact"] != "SH"
        penalty, details = select_shrinkage(selected, counts, increasing)
        penalty_audit[group] = {"selected_penalty": penalty, "candidates": details}
        fitted = fit_models(selected, counts, increasing, penalty)
        models[group] = {
            "artifact": selected[0]["artifact"], "parameter_units": selected[0]["parameter_units"],
            "increasing_quality_with_parameter": increasing,
            "calibration_listeners": len({r["listener_id"] for r in selected}),
            "sources": sorted({r["source"] for r in selected}),
            "population_counts": dict(counts), "selected_penalty": penalty, "models": fitted,
        }
        for record in cv_diagnostics(selected, counts, increasing):
            cvs.append({"artifact": selected[0]["artifact"], "group": group, **record})
        for record in mean_diagnostics(selected, counts):
            diagnostics.append({"artifact": selected[0]["artifact"],"group":group,**record})
        for name, model in fitted.items():
            for source, curve in [("__pooled__",model["pooled"]),*model["sources"].items()]:
                for x,y in zip(curve["x"],curve["quality"]):
                    knot_rows.append({"artifact":selected[0]["artifact"],"group":group,"model":name,
                                      "source":source,"parameter":x,"parameter_units":selected[0]["parameter_units"],
                                      "estimated_quality":y,"estimated_quality_loss_points":100-y})
        for source, value in sorted({(r["source"],r["parameter"]) for r in selected}):
            cells.append({"artifact":selected[0]["artifact"],"group":group,"source":source,
                          "parameter":value,"parameter_units":selected[0]["parameter_units"]})
    predictions = np.array([
        [predict(models[cell["group"]]["models"][name],cell["parameter"],cell["source"]) for cell in cells]
        for name in MODEL_NAMES
    ])
    bootstrap = np.empty((repetitions,len(MODEL_NAMES),len(cells)))
    loo = defaultdict(list)
    for group, selected in sorted(groups.items()):
        print(f"Calibration uncertainty: {group}, {repetitions} draws", flush=True)
        counts = models[group]["population_counts"]
        increasing = models[group]["increasing_quality_with_parameter"]
        penalty = models[group]["selected_penalty"]
        indices = [i for i,cell in enumerate(cells) if cell["group"]==group]
        for b, multipliers in enumerate(draws):
            fitted = fit_models(selected,counts,increasing,penalty,multipliers)
            for m,name in enumerate(MODEL_NAMES):
                bootstrap[b,m,indices] = [
                    predict(fitted[name],cells[i]["parameter"],cells[i]["source"]) for i in indices
                ]
        for uid in sorted({r["listener_id"] for r in selected}):
            remaining = [r for r in selected if r["listener_id"]!=uid]
            fitted = fit_models(remaining,counts,increasing,penalty)
            for m,name in enumerate(MODEL_NAMES):
                for i in indices:
                    loo[(m,i)].append(predict(fitted[name],cells[i]["parameter"],cells[i]["source"]))
    low,high = np.quantile(bootstrap,[.025,.975],axis=0)
    prediction_rows=[]
    for m,name in enumerate(MODEL_NAMES):
        for i,cell in enumerate(cells):
            prediction_rows.append({
                **cell,"model":name,"estimated_quality":float(predictions[m,i]),
                "bayesian_weight_95_lower":float(low[m,i]),"bayesian_weight_95_upper":float(high[m,i]),
                "leave_one_listener_min":float(min(loo[(m,i)])),
                "leave_one_listener_max":float(max(loo[(m,i)])),
                "leave_one_listener_max_abs_change":float(max(abs(value-predictions[m,i]) for value in loo[(m,i)])),
            })
    write_json(destination/"models.json",models)
    write_json(destination/"penalty_selection.json",penalty_audit)
    write_json(destination/"cells.json",cells)
    write_json(destination/"calibration_participants.json",{
        "listener_ids":sorted({r["listener_id"] for r in rows}),"candidate_assignment_blocks":blocks,
        "ratings":len(rows),"artifact_counts":dict(Counter(r["artifact"] for r in rows)),
    })
    write_csv(destination/"calibration_only_cv.csv",cvs)
    write_csv(destination/"quality_knots.csv",knot_rows)
    write_csv(destination/"calibration_mean_uncertainty.csv",diagnostics)
    write_csv(destination/"frozen_predictions.csv",prediction_rows)
    np.savez_compressed(destination/"calibration_bootstrap.npz",predictions=bootstrap)
    assert before == {relative:sha256(Path(release)/relative) for _,_,relative in FILES}
    seal={p.name:sha256(p) for p in sorted(destination.iterdir()) if p.is_file()}
    write_json(destination/"frozen_fit_seal.json",seal)
    return {"stage":"fit","groups":len(groups),"source_parameter_cells":len(cells),
            "calibration_ratings":len(rows),"independent_candidate_blocks":len(blocks),
            "frozen_files":len(seal)}


def metric_values(prediction, target):
    error = np.asarray(prediction)-np.asarray(target)
    p=np.asarray(prediction);t=np.asarray(target)
    variable = len(p)>2 and np.std(p)>0 and np.std(t)>0
    return {"rmse":float(np.sqrt(np.mean(error**2))),"mae":float(np.mean(np.abs(error))),
            "bias":float(np.mean(error)),
            "pearson":float(stats.pearsonr(p,t).statistic) if variable else None,
            "spearman":float(stats.spearmanr(p,t).statistic) if variable else None}


def evaluate(release, split_path, alias_path, output, repetitions=2000):
    root=Path(output)
    fit_dir=root/"fit"
    seal=json.loads((fit_dir/"frozen_fit_seal.json").read_text())
    for name,expected in seal.items():
        if sha256(fit_dir/name)!=expected:
            raise ValueError(f"Frozen fit changed: {name}")
    people,aliases=check_split(split_path,alias_path)
    protocol=json.loads((fit_dir/"protocol.json").read_text())
    if sha256(split_path)!=protocol["split_sha256"] or sha256(alias_path)!=protocol["aliases_sha256"]:
        raise ValueError("Participant split changed")
    if source_hash()!=protocol["source_code_sha256"]:
        raise ValueError("Calibration source code changed after fitting")
    for relative,expected in protocol["csv_checksums"].items():
        if sha256(Path(release)/relative)!=expected:
            raise ValueError(f"Input benchmark changed: {relative}")
    rows=load_ratings(release,split_path,"evaluation")
    groups=check_design(rows,3306)
    models=json.loads((fit_dir/"models.json").read_text())
    cells=json.loads((fit_dir/"cells.json").read_text())
    frozen=read_csv(fit_dir/"frozen_predictions.csv")
    prediction=np.array([[float(r["estimated_quality"]) for r in frozen if r["model"]==name] for name in MODEL_NAMES])
    lower=np.array([[float(r["bayesian_weight_95_lower"]) for r in frozen if r["model"]==name] for name in MODEL_NAMES])
    upper=np.array([[float(r["bayesian_weight_95_upper"]) for r in frozen if r["model"]==name] for name in MODEL_NAMES])
    targets=np.empty(len(cells))
    repeated,blocks=coupled_weights(people,aliases,"evaluation",repetitions,BOOTSTRAP_SEED+1)
    target_draws=np.empty((repetitions,len(cells)))
    comparisons=[]
    individual_errors=defaultdict(list)
    for i,cell in enumerate(cells):
        selected=[row for row in groups[cell["group"]] if row["source"]==cell["source"] and row["parameter"]==cell["parameter"]]
        n_expected=33 if cell["group"].endswith("_original") else 13
        if len(selected)!=n_expected:
            raise ValueError("Held-out support differs from frozen source/parameter grid")
        counts=models[cell["group"]]["population_counts"]
        targets[i]=basic_mean(selected,counts)
        for b,multipliers in enumerate(repeated):
            target_draws[b,i]=basic_mean(selected,counts,multipliers)
        weights=cohort_weights(selected,counts)
        for m,name in enumerate(MODEL_NAMES):
            comparisons.append({**cell,"model":name,"prediction":float(prediction[m,i]),
                "heldout_mean":float(targets[i]),"evaluation_listeners":len(selected),
                "prediction_minus_target":float(prediction[m,i]-targets[i]),
                "calibration_band_contains_heldout_mean":bool(lower[m,i]<=targets[i]<=upper[m,i])})
            individual_errors[(cell["group"],name)].append(
                sum(weights[row["listener_id"]]*(prediction[m,i]-row["score"])**2 for row in selected))
    destination=new_directory(root/"evaluation")
    write_csv(destination/"cell_predictions_vs_heldout.csv",comparisons)
    np.savez_compressed(destination/"heldout_target_bootstrap.npz",means=target_draws)
    target_low,target_high=np.quantile(target_draws,[.025,.975],axis=0)
    write_csv(destination/"heldout_target_uncertainty.csv",[
        {**cell,"heldout_mean":float(targets[i]),"heldout_resampling_lower":float(target_low[i]),
         "heldout_resampling_upper":float(target_high[i])} for i,cell in enumerate(cells)])
    metrics=[]
    labels=[("group",key) for key in sorted(groups)]
    labels += [("artifact",key) for key in ("LP","SH","UN","QN")]
    for scope,label in labels:
        indices=[i for i,cell in enumerate(cells) if cell[scope]==label]
        for m,name in enumerate(MODEL_NAMES):
            values=metric_values(prediction[m,indices],targets[indices])
            boot_errors=np.sqrt(np.mean((target_draws[:,indices]-prediction[m,indices][None,:])**2,axis=1))
            lo,hi=np.quantile(boot_errors,[.025,.975])
            if scope=="group":
                observation_rmse=float(np.sqrt(np.mean(individual_errors[(label,name)])))
            else:
                group_names=[g for g,entry in models.items() if entry["artifact"]==label]
                observation_rmse=float(np.sqrt(np.mean([v for g in group_names for v in individual_errors[(g,name)]])))
            metrics.append({
                "scope":scope,"label":label,"model":name,"cells":len(indices),**values,
                "fixed_fit_rmse_resampling_lower":float(lo),"fixed_fit_rmse_resampling_upper":float(hi),
                "individual_listener_rmse":observation_rmse,
                "calibration_band_coverage_of_test_means":float(np.mean(
                    (lower[m,indices]<=targets[indices])&(targets[indices]<=upper[m,indices]))),
            })
    write_csv(destination/"metrics.csv",metrics)
    write_json(destination/"evaluation_participants.json",{
        "listener_ids":sorted({r["listener_id"] for r in rows}),"candidate_assignment_blocks":blocks,
        "ratings":len(rows),"artifact_counts":dict(Counter(r["artifact"] for r in rows)),
        "target_weighting":protocol["population_weighting"],
        "interpretation":"fixed-fit evaluation; resampling intervals include evaluation-panel variability only",
    })
    for name,expected in seal.items():
        assert sha256(fit_dir/name)==expected
    write_json(destination/"verification.json",{
        "frozen_fit_unchanged":True,"split_unchanged":True,"source_csvs_unchanged":True,
        "calibration_listener_overlap":len(set(json.loads((fit_dir/"calibration_participants.json").read_text())["listener_ids"]) & {r["listener_id"] for r in rows}),
        "no_evaluation_model_selection":True,"no_generator_or_dataset_modification":True,
        "provenance":"ODAQ-informed listener-held-out POC; existing public source material reused",
    })
    return {"stage":"evaluate","evaluation_ratings":len(rows),"cells":len(cells),"candidate_blocks":len(blocks)}
