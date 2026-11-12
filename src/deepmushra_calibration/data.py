"""Read only the authorized artifact rows for one side of the frozen split."""
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re

FILES = (
    ("2024-icassp", "A", "2024-icassp/ODAQ_listening_test/ODAQ_results.csv"),
    ("2024-aes", "B1", "2024-aes/Cohort_B1_results.csv"),
    ("2024-aes", "B2", "2024-aes/Cohort_B2_results.csv"),
    ("2025-aes", "main", "2025-aes/ODAQ_v1.5_listening_test/ODAQ_1.5_results.csv"),
)
ALLOWED = {"LP", "SH", "UN", "SHLR", "SHMS", "SHmix", "QNLR", "QNMS", "QNmix"}
CONTROLS = {"Ref", "LP3.5", "LP7", "Mono"}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_split(path):
    with Path(path).open(newline="") as stream:
        people = list(csv.DictReader(stream))
    if len({row["listener_id"] for row in people}) != len(people):
        raise ValueError("Split contains duplicate participant records")
    return people


def load_ratings(release, split_path, role):
    if role not in {"calibration", "evaluation"}:
        raise ValueError("Unknown split role")
    people = {row["listener_id"]: row for row in read_split(split_path)}
    rows = []
    for study, cohort, relative in FILES:
        namespace = study + ("/"+cohort if study == "2024-aes" else "")
        with (Path(release)/relative).open(newline="", encoding="utf-8-sig") as stream:
            for raw in csv.DictReader(stream):
                # PE/TM and all controls are filtered before reading any score.
                if raw["method"] not in ALLOWED or raw["condition"] in CONTROLS:
                    continue
                code = raw["subject"].split(":")[-1].strip()
                uid = namespace+"::"+code
                person = people[uid]
                if person["proposed_role"] != role:
                    continue
                method, process = raw["method"], raw["process"]
                if method == "LP":
                    artifact, parameter, units = "LP", float(process[2:])/10, "cutoff_khz"
                    group = "LP_original"
                elif method == "UN":
                    artifact, parameter, units = "UN", float(process[2:-1]), "crossover_khz"
                    group = "UN_original"
                elif method.startswith("SH"):
                    artifact, parameter, units = "SH", float(re.search(r"SH(\d+)", process).group(1)), "hole_probability_percent"
                    basis = "MS" if "_MS" in process else "LR"
                    group = "SH_original" if method == "SH" else method if not method.endswith("mix") else method+"_"+basis
                else:
                    artifact, parameter, units = "QN", float(re.search(r"NMR(\d+)", process).group(1)), "odaq_nmr_label_db"
                    basis = "MS" if process.startswith("noiseMS") else "LR"
                    group = method if not method.endswith("mix") else method+"_"+basis
                value = float(raw["score"])
                if not 0 <= value <= 100:
                    raise ValueError("Invalid score")
                rows.append({
                    "listener_id": uid, "stratum": person["stratum"], "role": role,
                    "artifact": artifact, "group": group, "parameter": parameter, "parameter_units": units,
                    "source": raw["item"].split("_",1)[1], "process": process,
                    "score": value, "study": study, "cohort": cohort,
                    "method": method, "source_csv": relative,
                })
    return rows


def population_counts(people, group):
    return Counter(row["stratum"] for row in people if (
        row["study"] in {"2024-icassp", "2024-aes"} if group.endswith("_original")
        else row["study"] == "2025-aes"
    ))


def check_split(split_path, alias_path):
    people = read_split(split_path)
    main = [row for row in people if row["study"] != "2025-aes-supp"]
    counts = Counter(row["proposed_role"] for row in main)
    if counts != {"calibration": 12, "evaluation": 46}:
        raise ValueError(f"Unexpected frozen split {counts}")
    roles = {row["listener_id"]: row["proposed_role"] for row in people}
    aliases = json.loads(Path(alias_path).read_text())
    for pair in aliases:
        if roles[pair["earlier_listener_id"]] != roles[pair["later_listener_id"]]:
            raise ValueError("Candidate participant alias crosses split roles")
    return people, aliases


def check_design(rows, expected_ratings):
    if len(rows) != expected_ratings:
        raise ValueError(f"Expected {expected_ratings} artifact ratings; found {len(rows)}")
    keys = [(r["listener_id"], r["group"], r["source"], r["parameter"]) for r in rows]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate model input condition")
    by_group = defaultdict(list)
    for row in rows:
        if row["artifact"] not in {"LP", "SH", "UN", "QN"}:
            raise ValueError("Held-out artifact entered calibration")
        by_group[row["group"]].append(row)
    if len(by_group) != 11:
        raise ValueError(f"Expected eleven artifact/context/basis groups; found {len(by_group)}")
    for group, selected in by_group.items():
        n = len({r["listener_id"] for r in selected})
        cells = len({(r["source"], r["parameter"]) for r in selected})
        if len(selected) != n*cells:
            raise ValueError(f"Incomplete within-group design {group}")
    return by_group
