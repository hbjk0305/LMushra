"""Audit ODAQ listener support and propose an unfitted, study-scoped split."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
from itertools import combinations
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import numpy as np
from scipy import stats
import soundfile as sf

SEED = 20261110
TAG = "odaq-listener-feasibility-v1"
SPECS = [
    ("2024-icassp", "A", "2024-icassp/ODAQ_listening_test/ODAQ_results.csv"),
    ("2024-aes", "B1", "2024-aes/Cohort_B1_results.csv"),
    ("2024-aes", "B2", "2024-aes/Cohort_B2_results.csv"),
    ("2025-aes", "main", "2025-aes/ODAQ_v1.5_listening_test/ODAQ_1.5_results.csv"),
    ("2025-aes-supp", "supplement", "2025-aes/ODAQ_v1.5_additional_SH_items/ODAQ_1.5_additional_results.csv"),
]
TARGETS = {"LP", "SH", "UN", "SHLR", "SHMS", "SHmix", "QNLR", "QNMS", "QNmix"}
CONTROLS = {"Ref", "LP3.5", "LP7", "Mono"}
NUMBERS = {"A_DE": 3, "A_US": 2, "B1": 2, "B2": 2, "2025_D": 2, "2025_E": 1, "supplement": 2}


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def write_csv(path, rows):
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def rank(label):
    return hashlib.sha256(f"{TAG}|{SEED}|{label}".encode()).hexdigest()


def partition(row):
    code = row["code"]
    if row["cohort"] == "A":
        return "A_DE" if code.startswith("DEID") else "A_US"
    if row["study"] == "2025-aes":
        return "2025_D" if code.startswith("D") else "2025_E"
    return row["cohort"]


def family(method):
    if method.startswith("SH"):
        return "SH"
    if method.startswith("QN"):
        return "QN"
    return method


def level(method, process, condition):
    if condition.startswith("Q"):
        return condition
    if method.startswith("SH"):
        percentage = int(re.search(r"SH(\d+)", process).group(1))
        return {70: "Q1", 50: "Q2", 30: "Q3", 20: "Q4", 10: "Q5"}[percentage]
    if method.startswith("QN"):
        value = int(re.search(r"NMR(\d+)", process).group(1))
        return {0: "Q1", 6: "Q2", 12: "Q3", 18: "Q4", 24: "Q5"}[value]
    raise ValueError((method, process, condition))


def context(method):
    if method in {"LP", "SH", "UN"}:
        return "original_separated"
    return "mixed" if method.endswith("mix") else "separated"


def basis(method, process):
    if method.startswith(("SH", "QN")):
        if "_MS" in process or process.startswith("noiseMS"):
            return "MS"
        if "_LR" in process or process.startswith("noiseLR"):
            return "LR"
    return "not_labelled"


def interval(values):
    values = np.asarray(values, dtype=float)
    n = len(values)
    if n < 2:
        return None, None, None, None
    sd = float(np.std(values, ddof=1))
    half = float(stats.t.ppf(.975, n - 1) * sd / np.sqrt(n))
    mean = float(values.mean())
    return sd, mean - half, mean + half, half


def weighted_interval(rows, listeners):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["stratum"]].append(row["score"])
    eligible = {person["stratum"] for person in listeners}
    population = Counter(person["stratum"] for person in listeners)
    if set(grouped) != eligible or any(len(values) < 2 for values in grouped.values()):
        return None, None, None
    total = sum(population.values())
    mean = 0.
    components = []
    for name, values in grouped.items():
        weight = population[name] / total
        mean += weight * float(np.mean(values))
        variance = weight ** 2 * float(np.var(values, ddof=1)) / len(values)
        components.append((variance, len(values)-1))
    variance = sum(value for value, _ in components)
    denominator = sum(value ** 2 / df for value, df in components)
    degrees = variance ** 2 / denominator if denominator else None
    half = float(stats.t.ppf(.975, degrees) * np.sqrt(variance)) if degrees else 0.
    return mean, half, degrees


def repeated_stimuli(root):
    inventory = root.parent.parent / "sources/pair_inventory.json"
    if not inventory.exists():
        return {"status": "Pair inventory unavailable"}
    pairs = json.loads(inventory.read_text())
    pairs = [pair for pair in pairs if not pair["is_reference"] and not pair["is_anchor"]
             and pair["method"] in {"SH", "SHLR", "SHMS", "SHmix", "QNLR", "QNMS", "QNmix"}]
    def compare(first, second):
        x, sr = sf.read(root.parent / first["target"], dtype="float64", always_2d=True)
        y, other_sr = sf.read(root.parent / second["target"], dtype="float64", always_2d=True)
        output = {"source": first["item"].split("_", 1)[1], "process": first["process"],
                  "first_target": first["target"], "second_target": second["target"],
                  "same_shape_and_rate": x.shape == y.shape and sr == other_sr}
        if output["same_shape_and_rate"]:
            energy = float(np.sum(x * x))
            gain = float(np.sum(x * y) / energy) if energy else 0.
            output.update(pcm_identical=bool(np.array_equal(x, y)),
                          max_abs_difference=float(np.max(np.abs(x - y))),
                          relative_waveform_error=float(np.linalg.norm(x-y) / np.sqrt(energy)) if energy else None,
                          relative_error_after_scalar_gain=float(np.linalg.norm(y-gain*x) / np.sqrt(energy)) if energy else None,
                          scalar_gain=gain)
        return output
    contexts = []
    cross_study = []
    for first in pairs:
        for second in pairs:
            same_source = first["item"].split("_", 1)[1] == second["item"].split("_", 1)[1]
            same_process = first["process"] == second["process"]
            if not same_source or not same_process:
                continue
            if first["method"] in {"SHmix", "QNmix"} and second["subset"] == "2025-aes" and second["method"] in {"SHLR", "SHMS", "QNLR", "QNMS"}:
                contexts.append(compare(first, second))
            if first["subset"] == "2024-icassp" and first["method"] == "SH" and second["subset"] == "2025-aes" and second["method"] == "SHMS":
                cross_study.append(compare(first, second))
    return {"mixed_separated_comparisons": contexts, "original_stereo_SH_comparisons": cross_study}


def plot_precision(result, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    labels, medians, lows, highs = [], [], [], []
    for artifact in ["LP", "SH", "UN"]:
        row = result["original_pooled_precision"][artifact]
        labels.append(f"{artifact}, original cohorts (9 listeners)")
        medians.append(row["diagnostic_median_half_width"])
        lows.append(row["diagnostic_min_half_width"])
        highs.append(row["diagnostic_max_half_width"])
    for row in result["summaries"]:
        if row["study"] == "2025-aes":
            labels.append(f"{row['method']}, 2025 main (3 listeners)")
            medians.append(row["ci_half_width_median"])
            lows.append(row["ci_half_width_min"])
            highs.append(row["ci_half_width_max"])
    y = np.arange(len(labels))
    medians = np.array(medians)
    fig, axis = plt.subplots(figsize=(11, 7), constrained_layout=True)
    axis.errorbar(medians, y, xerr=np.array([medians-np.array(lows), np.array(highs)-medians]),
                  fmt="o", capsize=3)
    axis.set_yticks(y, labels)
    axis.invert_yaxis()
    axis.axvline(5, color="green", linestyle="--", label="5-point planning target")
    axis.axvline(10, color="orange", linestyle="--", label="10-point planning target")
    axis.set(xlabel="95% t-CI half-width (MUSHRA points)",
             title="Proposed 20% calibration set: per-condition precision\nDots show median; whiskers show min/max across source/parameter cells")
    axis.legend(loc="lower right")
    fig.savefig(out / "calibration_precision.png", dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root, out = args.release.resolve(), args.output.resolve()
    if out.exists():
        raise ValueError("Use a fresh feasibility output directory")
    out.mkdir(parents=True)
    raw = []
    people = {}
    inputs = {}
    completeness = []
    for study, cohort, relative in SPECS:
        path = root / relative
        inputs[relative] = checksum(path)
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        keys = Counter((r["subject"], r["method"], r["item"], r["condition"], r["process"]) for r in rows)
        invalid = [r for r in rows if not np.isfinite(float(r["score"])) or not 0 <= float(r["score"]) <= 100]
        duplicates = sum(n-1 for n in keys.values() if n > 1)
        cells = {(r["method"], r["item"], r["condition"], r["process"]) for r in rows}
        subjects = sorted({r["subject"] for r in rows})
        missing = []
        for subject in subjects:
            present = {(r["method"], r["item"], r["condition"], r["process"]) for r in rows if r["subject"] == subject}
            missing.extend([{"subject": subject, "cell": cell} for cell in sorted(cells - present)])
        completeness.append({
            "study": study, "cohort": cohort, "source_csv": relative, "listeners": len(subjects),
            "rows": len(rows), "conditions_per_listener": len(cells),
            "missing_in_observed_design": len(missing), "duplicate_rating_keys": duplicates,
            "invalid_scores": len(invalid), "missing_cells": missing,
        })
        if missing or duplicates or invalid:
            raise ValueError(f"Incomplete/invalid input {relative}")
        for row in rows:
            code = row["subject"].split(":")[-1].strip()
            namespace = study + ("/" + cohort if study == "2024-aes" else "")
            uid = f"{namespace}::{code}"
            person = {"listener_id": uid, "study": study, "cohort": cohort, "code": code, "raw_subject": row["subject"]}
            person["stratum"] = partition(person)
            people[uid] = person
            raw.append({
                **row, "score": float(row["score"]), **person,
                "source_csv": relative, "supplement": study == "2025-aes-supp",
            })
    persons = sorted(people.values(), key=lambda p: p["listener_id"])
    strata = defaultdict(list)
    for person in persons:
        strata[person["stratum"]].append(person)
    selected = set()
    for name in ("A_DE", "A_US", "2025_E", "supplement"):
        selected.update(p["listener_id"] for p in sorted(strata[name], key=lambda p: rank(p["listener_id"]))[:NUMBERS[name]])

    # These links are conservative split constraints, not verified identities.
    old = {p["code"]: p for p in persons if p["stratum"] in {"B1", "B2"}}
    repeated = {p["code"]: p for p in strata["2025_D"] if p["code"] in old}
    assert len(repeated) == len(strata["2025_D"]) == 9
    options = []
    for first in combinations(strata["B1"], 2):
        for second in combinations(strata["B2"], 2):
            chosen = first + second
            if sum(person["code"] in repeated for person in chosen) == NUMBERS["2025_D"]:
                ids = sorted(person["listener_id"] for person in chosen)
                options.append((rank("|".join(ids)), chosen))
    assert options
    chosen = min(options, key=lambda value: value[0])[1]
    selected.update(person["listener_id"] for person in chosen)
    selected.update(repeated[p["code"]]["listener_id"] for p in chosen if p["code"] in repeated)
    aliases = []
    for code, current in sorted(repeated.items()):
        assert (old[code]["listener_id"] in selected) == (current["listener_id"] in selected)
        aliases.append({
            "participant_code": code, "earlier_listener_id": old[code]["listener_id"],
            "later_listener_id": current["listener_id"],
            "evidence": "Matching D-code in the same institution's released test files; identity unconfirmed",
            "split_constraint": "same partition",
        })
    for person in persons:
        person["proposed_role"] = "calibration" if person["listener_id"] in selected else "evaluation"
        person["seed"] = SEED
    for row in raw:
        row["proposed_role"] = people[row["listener_id"]]["proposed_role"]
    assert all(sum(p["proposed_role"] == "calibration" for p in group) == NUMBERS[name] for name, group in strata.items())
    write_csv(out / "proposed_listener_split.csv", persons)
    write_json(out / "candidate_cross_study_links.json", aliases)
    write_json(out / "completeness.json", completeness)

    # QC is evaluated over each listener's entire released test, without new exclusions.
    qc = []
    for person in persons:
        rows = [r for r in raw if r["listener_id"] == person["listener_id"]]
        refs = [r["score"] for r in rows if r["condition"] == "Ref"]
        low = sum(score < 90 for score in refs)
        trials = defaultdict(dict)
        for row in rows:
            trials[row["item"]][row["condition"]] = row["score"]
        reversals = sum(values.get("LP3.5", -1) > values.get("LP7", 101) for values in trials.values())
        qc.append({
            "listener_id": person["listener_id"], "study": person["study"], "cohort": person["cohort"],
            "reference_trials": len(refs), "reference_below_90": low,
            "reference_failure_fraction": low / len(refs),
            "would_exceed_original_15pct_reference_rule": low / len(refs) > .15,
            "anchor35_above_anchor70_trials": reversals,
            "action": "retain released post-screened data",
        })
    write_csv(out / "qc_diagnostics.csv", qc)

    # Each listener must have one matching complete XML where the original release supplies XML.
    xml_by_panel = {}
    for study, cohort, relative in SPECS:
        folder = (root / relative).parent
        if cohort in {"B1", "B2"}:
            folder = root / "2024-aes" / f"Cohort_{cohort}"
        entries = {}
        for path in folder.glob("*.xml"):
            tree = ET.parse(path).getroot()
            info = tree.find("info").attrib
            uid = info["subjectName"]
            trials = {}
            for trial in tree.findall("./trials/trial"):
                trial_name = trial.attrib["trialName"]
                source_prefix = trial_name.split("_", 1)[1] + "_"
                if source_prefix == "dream_home_14_24_":
                    source_prefix = "dream_home_14-24_"
                for item in trial.findall("testFile"):
                    process = Path(item.attrib["fileName"]).stem
                    if process.startswith(source_prefix):
                        process = process[len(source_prefix):]
                    trials[(trial_name, process)] = float(item.attrib["score"])
            entries[uid] = (info, trials)
        differences = []
        comparisons = 0
        for row in raw:
            if row["study"] != study or row["cohort"] != cohort:
                continue
            if row["code"] in entries:
                trials = entries[row["code"]][1]
                key = (row["item"], row["process"])
                if key not in trials or not np.isclose(row["score"], trials[key], rtol=0, atol=1e-10):
                    differences.append({"listener": row["listener_id"], "item": row["item"], "process": row["process"]})
                comparisons += 1
        xml_by_panel[f"{study}/{cohort}"] = {
            "xml_listeners": len(entries), "score_comparisons": comparisons,
            "differences": differences, "status": dict(Counter(value[0].get("testStatus") for value in entries.values())),
            "months": dict(Counter(value[0].get("startTime", "")[:7] for value in entries.values())),
        }
    write_json(out / "xml_crosscheck.json", xml_by_panel)
    assert all(not panel["differences"] for panel in xml_by_panel.values()), "CSV and XML disagree"


    active = []
    for row in raw:
        if row["method"] in TARGETS and row["condition"] not in CONTROLS:
            active.append({
                **row, "artifact": family(row["method"]),
                "source_recording_key": row["item"].split("_", 1)[1],
                "quality_level": level(row["method"], row["process"], row["condition"]),
                "presentation_context": context(row["method"]),
                "channel_basis": basis(row["method"], row["process"]),
            })
    groups = defaultdict(list)
    for row in active:
        key = (row["study"], row["artifact"], row["method"], row["source_recording_key"], row["quality_level"], row["process"])
        groups[key].append(row)
    coverage = []
    ci = []
    for key, rows in sorted(groups.items()):
        study, artifact, method, source, quality, process = key
        chosen = [r for r in rows if r["proposed_role"] == "calibration"]
        held = [r for r in rows if r["proposed_role"] == "evaluation"]
        assert not ({r["listener_id"] for r in chosen} & {r["listener_id"] for r in held})
        for cohort in sorted({r["stratum"] for r in rows}):
            part = [r for r in rows if r["stratum"] == cohort]
            coverage.append({
                "study": study, "stratum": cohort, "artifact": artifact, "method": method,
                "source_recording_key": source, "quality_level": quality, "process": process,
                "presentation_context": rows[0]["presentation_context"], "channel_basis": rows[0]["channel_basis"],
                "available_ratings": len(part),
                "proposed_calibration_ratings": sum(r["proposed_role"] == "calibration" for r in part),
                "proposed_evaluation_ratings": sum(r["proposed_role"] == "evaluation" for r in part),
            })
        sd, lower, upper, half = interval([r["score"] for r in chosen])
        eligible = [person for person in persons if person["study"] == study]
        weighted_mean, weighted_half, degrees = weighted_interval(chosen, eligible)
        ci.append({
            "study": study, "artifact": artifact, "method": method, "source_recording_key": source,
            "quality_level": quality, "process": process, "calibration_n": len(chosen),
            "calibration_mean": float(np.mean([r["score"] for r in chosen])),
            "calibration_sd": sd, "diagnostic_t_ci_lower": lower, "diagnostic_t_ci_upper": upper,
            "diagnostic_t_ci_half_width": half, "stratum_weighted_mean": weighted_mean,
            "stratum_weighted_half_width": weighted_half, "satterthwaite_df": degrees,
        })
    pooled_ci = []
    pooled_groups = defaultdict(list)
    for row in active:
        if row["study"] in {"2024-icassp", "2024-aes"}:
            key = (row["artifact"], row["source_recording_key"], row["quality_level"], row["process"])
            pooled_groups[key].append(row)
    original_people = [person for person in persons if person["study"] in {"2024-icassp", "2024-aes"}]
    for key, rows in sorted(pooled_groups.items()):
        chosen = [row for row in rows if row["proposed_role"] == "calibration"]
        sd, lower, upper, half = interval([row["score"] for row in chosen])
        weighted_mean, weighted_half, degrees = weighted_interval(chosen, original_people)
        pooled_ci.append({
            "artifact": key[0], "source_recording_key": key[1], "quality_level": key[2], "process": key[3],
            "calibration_listener_n": len(chosen), "available_listener_n": len(rows),
            "diagnostic_mean": float(np.mean([row["score"] for row in chosen])),
            "diagnostic_sd": sd, "diagnostic_t_ci_lower": lower, "diagnostic_t_ci_upper": upper,
            "diagnostic_t_ci_half_width": half, "stratum_weighted_mean": weighted_mean,
            "stratum_weighted_half_width": weighted_half, "satterthwaite_df": degrees,
        })
    write_csv(out / "calibration_precision_original_pooled.csv", pooled_ci)
    write_csv(out / "coverage_by_condition_and_cohort.csv", coverage)
    write_csv(out / "calibration_precision_by_condition.csv", ci)

    # Source-averaged levels retain one observation per listener within a presentation context.
    aggregated = defaultdict(lambda: defaultdict(list))
    for row in active:
        if row["proposed_role"] == "calibration":
            aggregated[(row["study"], row["method"], row["quality_level"])][row["listener_id"]].append(row["score"])
    for row in active:
        if row["study"] in {"2024-icassp", "2024-aes"} and row["proposed_role"] == "calibration":
            aggregated[("original_2024_pooled", row["method"], row["quality_level"])][row["listener_id"]].append(row["score"])
    level_precision = []
    for key, listener_scores in sorted(aggregated.items()):
        scores = [float(np.mean(values)) for values in listener_scores.values()]
        sd, lower, upper, half = interval(scores)
        level_precision.append({
            "study": key[0], "method": key[1], "quality_level": key[2],
            "independent_listener_observations": len(scores), "raw_ratings": sum(len(values) for values in listener_scores.values()),
            "mean_of_listener_source_averages": float(np.mean(scores)),
            "diagnostic_t_ci_lower": lower, "diagnostic_t_ci_upper": upper,
            "diagnostic_t_ci_half_width": half,
        })
    write_csv(out / "precision_after_averaging_sources.csv", level_precision)
    summaries = []
    for study, method in sorted({(r["study"], r["method"]) for r in active}):
        rows = [r for r in active if r["study"] == study and r["method"] == method]
        cells = [c for c in ci if c["study"] == study and c["method"] == method]
        widths = [c["diagnostic_t_ci_half_width"] for c in cells]
        summaries.append({
            "study": study, "artifact": family(method), "method": method,
            "available_listener_ids": len({r["listener_id"] for r in rows}),
            "calibration_listener_ids": len({r["listener_id"] for r in rows if r["proposed_role"] == "calibration"}),
            "evaluation_listener_ids": len({r["listener_id"] for r in rows if r["proposed_role"] == "evaluation"}),
            "sources": len({r["source_recording_key"] for r in rows}), "condition_cells": len(cells),
            "available_ratings": len(rows), "calibration_ratings": sum(r["proposed_role"] == "calibration" for r in rows),
            "evaluation_ratings": sum(r["proposed_role"] == "evaluation" for r in rows),
            "ci_half_width_median": float(np.median(widths)), "ci_half_width_min": float(min(widths)),
            "ci_half_width_max": float(max(widths)), "cells_with_half_width_at_most_5": sum(w <= 5 for w in widths),
            "cells_with_half_width_at_most_10": sum(w <= 10 for w in widths),
        })
    write_csv(out / "summary_by_method.csv", summaries)
    method_keys = {(r["study"], r["cohort"], r["method"]) for r in active}
    cohort_counts = []
    for study, cohort, method in sorted(method_keys):
        rows = [r for r in active if r["study"] == study and r["cohort"] == cohort and r["method"] == method]
        cohort_counts.append({
            "study": study, "cohort": cohort, "artifact": family(method), "method": method,
            "unique_listener_ids": len({r["listener_id"] for r in rows}),
            "available_ratings": len(rows), "proposed_calibration_ratings": sum(r["proposed_role"] == "calibration" for r in rows),
        })
    write_csv(out / "listener_counts_by_artifact_and_cohort.csv", cohort_counts)
    anchor_summary = Counter((r["study"], r["proposed_role"]) for r in raw if r["condition"] in {"LP3.5", "LP7"})
    write_csv(out / "lowpass_anchor_counts.csv", [
        {"study": key[0], "proposed_role": key[1], "anchor_ratings": value}
        for key, value in sorted(anchor_summary.items())
    ])
    for relative, original in inputs.items():
        assert checksum(root / relative) == original, relative
    result = {
        "seed": SEED, "protocol": TAG, "fitting_performed": False,
        "analysis_source_sha256": checksum(Path(__file__)) ,
        "proposal_only": True, "source_checksums_unchanged": inputs,
        "main_listener_entries": sum(p["study"] != "2025-aes-supp" for p in persons),
        "main_calibration_entries": sum(p["study"] != "2025-aes-supp" and p["proposed_role"] == "calibration" for p in persons),
        "main_evaluation_entries": sum(p["study"] != "2025-aes-supp" and p["proposed_role"] == "evaluation" for p in persons),
        "supplement_listener_entries": len(strata["supplement"]),
        "candidate_cross_study_links": len(aliases), "valid_B1_B2_combination_count": len(options),
        "strata": {name: {"n": len(group), "calibration": NUMBERS[name], "evaluation": len(group)-NUMBERS[name]} for name, group in strata.items()},
        "summaries": summaries,
        "all_retained_pass_original_reference_diagnostic": not any(q["would_exceed_original_15pct_reference_rule"] for q in qc),
        "n_source_condition_cells": len(ci),
        "original_pooled_precision": {
            artifact: {
                "calibration_listeners_per_cell": 9,
                "condition_cells": sum(row["artifact"] == artifact for row in pooled_ci),
                "diagnostic_median_half_width": float(np.median([row["diagnostic_t_ci_half_width"] for row in pooled_ci if row["artifact"] == artifact])),
                "diagnostic_min_half_width": min(row["diagnostic_t_ci_half_width"] for row in pooled_ci if row["artifact"] == artifact),
                "diagnostic_max_half_width": max(row["diagnostic_t_ci_half_width"] for row in pooled_ci if row["artifact"] == artifact),
                "weighted_median_half_width": float(np.median([row["stratum_weighted_half_width"] for row in pooled_ci if row["artifact"] == artifact])),
                "weighted_max_half_width": max(row["stratum_weighted_half_width"] for row in pooled_ci if row["artifact"] == artifact),
                "diagnostic_cells_with_half_width_at_most_5": sum(row["diagnostic_t_ci_half_width"] <= 5 for row in pooled_ci if row["artifact"] == artifact),
                "diagnostic_cells_with_half_width_at_most_10": sum(row["diagnostic_t_ci_half_width"] <= 10 for row in pooled_ci if row["artifact"] == artifact),
            } for artifact in ["LP", "SH", "UN"]
        },
    }
    write_json(out / "repeated_stimuli.json", repeated_stimuli(root))
    write_json(out / "feasibility_summary.json", result)
    plot_precision(result, out)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
