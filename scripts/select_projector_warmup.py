"""Select the projector-warmup subset from calibrated_llm exports.

The published validation file is val.jsonl. valid.jsonl in that folder is a
symlink to val.jsonl. This script reads val.jsonl and writes the same pair:
val.jsonl plus a relative valid.jsonl symlink, so a copied directory still
resolves on another machine.

User text is copied unchanged. Family and severity travel in
chat_template_kwargs.degradation, not in the prompt.

  python scripts/select_projector_warmup.py \
    --output /scratch/jackiel4/data/AudioLM/projector-warmup-24k
"""
import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lmushra.data_paths import relativize_export_value


SEED = 20261124
FAMILIES = ("LP", "SH", "UN", "QN")
BINS = ("subtle", "moderate", "strong")
CONTENTS = (
    "speech",
    "music_piano",
    "speech_codec_exposed",
    "music_guitar_instrument",
    "music_singing",
)
HOLDOUT_CONTENTS = (
    "speech_codec_exposed",
    "music_guitar_instrument",
    "music_singing",
)
VAL_CONTENTS = ("speech", "music_piano")
TRAIN_PER_CELL = 2000
VAL_PER_CELL = 200
# parameter name, True when a lower raw value is more severe
AXES = {
    "LP": ("cutoff_hz", True),
    "SH": ("hole_probability", False),
    "UN": ("crossover_hz", True),
    "QN": ("snr_db", True),
}
ORIGINS = {
    "strict_reasoned_pilot": 0,
    "matched_poc": 1,
    "full_synthetic": 2,
}


def largest_remainder(weights, total):
    """Split total into integer parts that sum to total and follow weights."""
    keys = list(weights)
    raw = {key: total * weights[key] for key in keys}
    floors = {key: int(raw[key]) for key in keys}
    leftover = total - sum(floors.values())
    order = sorted(keys, key=lambda key: (-(raw[key] - floors[key]), key))
    for key in order[:leftover]:
        floors[key] += 1
    return floors


def unit_severity(raw, low, high, lower_is_worse):
    if high == low:
        return 0.5
    fraction = min(1.0, max(0.0, (raw - low) / (high - low)))
    return (1.0 - fraction) if lower_is_worse else fraction


def assign_bin(raw, low_edge, high_edge, lower_is_worse):
    if lower_is_worse:
        if raw <= low_edge:
            return "strong"
        if raw <= high_edge:
            return "moderate"
        return "subtle"
    if raw <= low_edge:
        return "subtle"
    if raw <= high_edge:
        return "moderate"
    return "strong"


def percentile(sorted_values, fraction):
    """Nearest-rank index int(fraction * (n - 1)), recorded in the report."""
    if not sorted_values:
        raise ValueError("empty percentile input")
    index = int(fraction * (len(sorted_values) - 1))
    return sorted_values[index], index


def is_clean(annotation):
    return not (annotation or {}).get("warnings")


def load_small_export(folder, origin):
    """Load jsonl and metadata for strict or matched, keyed by sample_id."""
    records = {}
    for split_name in ("train", "val"):
        jsonl_path = folder / f"{split_name}.jsonl"
        meta_path = folder / f"{split_name}.metadata.jsonl"
        with jsonl_path.open() as examples, meta_path.open() as metadata:
            for index, (example_line, meta_line) in enumerate(zip(examples, metadata)):
                example = json.loads(example_line)
                side = json.loads(meta_line)
                sample_id = side["sample_id"]
                published = "train" if split_name == "train" else "valid"
                records[sample_id] = {
                    "example": example,
                    "metadata": side,
                    "origin": origin,
                    "published_split": published,
                    "row_index": index,
                    "clean": True if origin == "strict_reasoned_pilot" else is_clean(side.get("annotation")),
                }
        # A truncated pair would have been silent if one file were longer.
        with jsonl_path.open() as examples, meta_path.open() as metadata:
            example_count = sum(1 for _ in examples)
            meta_count = sum(1 for _ in metadata)
        if example_count != meta_count:
            raise ValueError(f"line count mismatch in {folder} {split_name}: {example_count} vs {meta_count}")
    return records


def source_id_of(metadata):
    source = metadata["metadata"]["source"]
    group = source.get("source_id")
    top = metadata.get("source_id")
    if group and top and group != top:
        raise ValueError(f"source_id mismatch for {metadata.get('sample_id')}: {group} vs {top}")
    if not group:
        raise ValueError(f"missing source_id for {metadata.get('sample_id')}")
    return group


def content_of(metadata):
    return metadata["metadata"]["source"]["content_category"]


def raw_parameter(metadata):
    degradation = metadata["metadata"]["degradation"]
    artifact = degradation["artifact_type"]
    if artifact not in AXES:
        raise ValueError(f"unexpected artifact {artifact}")
    name, _lower_is_worse = AXES[artifact]
    value = degradation["parameters"][name]
    if not isinstance(value, (int, float)):
        raise ValueError(f"{metadata.get('sample_id')} {name} is not numeric: {value!r}")
    return artifact, name, float(value)


def compact_from_metadata(metadata, origin, published_split, row_index):
    artifact, parameter_name, raw = raw_parameter(metadata)
    return {
        "sample_id": metadata["sample_id"],
        "source_id": source_id_of(metadata),
        "artifact": artifact,
        "parameter_name": parameter_name,
        "raw": raw,
        "content": content_of(metadata),
        "origin": origin,
        "published_split": published_split,
        "row_index": row_index,
        "store": origin,
    }


def scan_full(folder):
    """Stream the full export. Keep compact clean rows and every val source id."""
    clean = []
    val_sources = set()
    counts = Counter()
    for split_name, published in (("train", "train"), ("val", "valid")):
        meta_path = folder / f"{split_name}.metadata.jsonl"
        jsonl_path = folder / f"{split_name}.jsonl"
        # valid.jsonl is a symlink to val.jsonl; open the real name.
        seen = 0
        with meta_path.open() as metadata, jsonl_path.open() as examples:
            for index, (meta_line, example_line) in enumerate(zip(metadata, examples)):
                side = json.loads(meta_line)
                if published == "valid":
                    val_sources.add(source_id_of(side))
                counts["rows"] += 1
                if not example_line.strip():
                    raise ValueError(f"empty jsonl line {split_name}:{index}")
                if is_clean(side.get("annotation")):
                    clean.append(compact_from_metadata(side, "full_synthetic", published, index))
                    counts["clean"] += 1
                if (index + 1) % 200000 == 0:
                    print(f"scanned {split_name} {index + 1}", flush=True)
            seen = index + 1
            extra_meta = sum(1 for _ in metadata)
            extra_examples = sum(1 for _ in examples)
        if extra_meta or extra_examples:
            raise ValueError(f"{split_name} has {extra_meta} extra metadata lines and {extra_examples} extra jsonl lines")
        counts[f"{published}_rows"] = seen
    return clean, val_sources, counts


def annotate_severity(records):
    grouped = defaultdict(list)
    for record in records:
        if record["published_split"] == "train":
            grouped[record["artifact"]].append(record["raw"])
    edges = {}
    for artifact in FAMILIES:
        values = sorted(grouped[artifact])
        if not values:
            raise ValueError(f"no clean train rows for {artifact}")
        low_edge, low_index = percentile(values, 1 / 3)
        high_edge, high_index = percentile(values, 2 / 3)
        edges[artifact] = {
            "parameter": AXES[artifact][0],
            "lower_is_worse": AXES[artifact][1],
            "min": values[0],
            "max": values[-1],
            "p33": low_edge,
            "p66": high_edge,
            "p33_index": low_index,
            "p66_index": high_index,
            "n": len(values),
            "percentile": "index int(p * (n - 1)) on the sorted clean-train values",
        }
    for record in records:
        edge = edges[record["artifact"]]
        record["bin"] = assign_bin(record["raw"], edge["p33"], edge["p66"], edge["lower_is_worse"])
        record["severity"] = unit_severity(record["raw"], edge["min"], edge["max"], edge["lower_is_worse"])
    return edges


def choose_holdouts(train_records):
    counts = defaultdict(Counter)
    for record in train_records:
        if record["content"] in HOLDOUT_CONTENTS:
            counts[record["content"]][record["source_id"]] += 1
    chosen = {}
    for content in HOLDOUT_CONTENTS:
        if not counts[content]:
            raise ValueError(f"no clean train source ids for {content}")
        # Smallest clean group. Ties break by source_id so the seed is not involved.
        source_id = sorted(counts[content], key=lambda key: (counts[content][key], key))[0]
        chosen[content] = {"source_id": source_id, "clean_rows": counts[content][source_id]}
    return chosen


def content_weights(train_records):
    counts = Counter(record["content"] for record in train_records)
    total = sum(counts.values())
    weights = {content: counts[content] / total for content in CONTENTS if counts[content]}
    for content, count in counts.items():
        weights.setdefault(content, count / total)
    return weights, dict(counts)


def cell_quotas(weights, per_cell, contents):
    quotas = {}
    for artifact in FAMILIES:
        for bin_name in BINS:
            parts = largest_remainder({content: weights[content] for content in contents}, per_cell)
            for content, count in parts.items():
                quotas[(artifact, bin_name, content)] = count
    return quotas


def seeded_shuffle(records, label):
    ordered = sorted(records, key=lambda record: record["sample_id"])
    random.Random(f"{SEED}:{label}").shuffle(ordered)
    return ordered


def fill_cells(pool, quotas, force, seed_tag):
    buckets = defaultdict(list)
    for record in pool:
        buckets[(record["artifact"], record["bin"], record["content"])].append(record)
    chosen = []
    achieved = Counter()
    for key, items in buckets.items():
        forced = [record for record in items if record["sample_id"] in force or record.get("force")]
        forced_ids = {record["sample_id"] for record in forced}
        quota = quotas.get(key, 0)
        need = max(0, quota - len(forced))
        rest = [record for record in items if record["sample_id"] not in forced_ids]
        picked = seeded_shuffle(rest, f"{seed_tag}:{key}")[:need]
        keep = forced + picked
        chosen.extend(keep)
        achieved[key] = len(keep)
    return chosen, achieved


def top_up_family_bins(chosen, pool, per_cell, seed_tag):
    chosen_ids = {record["sample_id"] for record in chosen}
    remaining = defaultdict(list)
    for record in pool:
        if record["sample_id"] not in chosen_ids:
            remaining[(record["artifact"], record["bin"])].append(record)
    have = Counter((record["artifact"], record["bin"]) for record in chosen)
    extra = []
    for artifact in FAMILIES:
        for bin_name in BINS:
            need = per_cell - have[(artifact, bin_name)]
            if need <= 0:
                continue
            options = seeded_shuffle(remaining[(artifact, bin_name)], f"{seed_tag}:topup:{artifact}:{bin_name}")
            extra.extend(options[:need])
    return chosen + extra


def tally(records):
    return {
        "n": len(records),
        "origin": dict(Counter(record["origin"] for record in records)),
        "artifact": dict(Counter(record["artifact"] for record in records)),
        "bin": dict(Counter(record["bin"] for record in records)),
        "content": dict(Counter(record["content"] for record in records)),
        "artifact_bin": {
            f"{artifact}|{bin_name}": sum(
                1 for record in records if record["artifact"] == artifact and record["bin"] == bin_name)
            for artifact in FAMILIES for bin_name in BINS
        },
    }


def attach_example(record, stores, full_examples):
    if record["store"] == "full_synthetic":
        example, metadata = full_examples[(record["published_split"], record["row_index"])]
    else:
        stored = stores[record["store"]][record["sample_id"]]
        example, metadata = stored["example"], stored["metadata"]
    if metadata["sample_id"] != record["sample_id"]:
        raise ValueError(f"sample_id drift at {record['sample_id']}")
    audios = [relativize_export_value(audio) for audio in (example.get("audios") or [])]
    if len(audios) != 2 or any(not audio.startswith("production/") for audio in audios):
        raise ValueError(f"{record['sample_id']} audios are not two production-relative wavs")
    user = example["messages"][0]["content"]
    assistant = example["messages"][1]["content"]
    if example["messages"][0]["role"] != "user" or example["messages"][1]["role"] != "assistant":
        raise ValueError(f"{record['sample_id']} roles are not user then assistant")
    written_example = {
        "messages": [
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
        "audios": audios,
        "chat_template_kwargs": {
            "degradation": {
                "artifact": record["artifact"],
                "severity": record["severity"],
            },
        },
    }
    side = relativize_export_value(dict(metadata))
    side["selection_origin"] = record["origin"]
    side["selection_seed"] = SEED
    side["severity_value"] = record["severity"]
    side["severity_parameter"] = record["raw"]
    side["severity_parameter_name"] = record["parameter_name"]
    side["severity_bin"] = record["bin"]
    side["selection_split"] = record["output_split"]
    return written_example, side, user


def load_selected_full_rows(folder, wanted):
    """wanted: published split -> set of row indexes."""
    loaded = {}
    for split_name, published in (("train", "train"), ("val", "valid")):
        indexes = wanted.get(published) or set()
        if not indexes:
            continue
        with (folder / f"{split_name}.jsonl").open() as examples, (folder / f"{split_name}.metadata.jsonl").open() as metadata:
            for index, (example_line, meta_line) in enumerate(zip(examples, metadata)):
                if index not in indexes:
                    continue
                loaded[(published, index)] = (json.loads(example_line), json.loads(meta_line))
        missing = indexes - {index for split, index in loaded if split == published}
        if missing:
            raise ValueError(f"missing {len(missing)} {published} rows from the full export")
    return loaded


def write_split(path_stem, records, stores, full_examples):
    records = sorted(records, key=lambda record: record["sample_id"])
    prompts = Counter()
    jsonl_path = path_stem.with_suffix(".jsonl")
    meta_path = Path(str(path_stem) + ".metadata.jsonl")
    with jsonl_path.open("w") as examples, meta_path.open("w") as metadata:
        for record in records:
            example, side, prompt = attach_example(record, stores, full_examples)
            prompts[prompt] += 1
            examples.write(json.dumps(example, ensure_ascii=False) + "\n")
            metadata.write(json.dumps(side, ensure_ascii=False) + "\n")
    return prompts


def link_valid_alias(output):
    """Match the source layout: valid.jsonl -> val.jsonl, relative so copies work."""
    for name in ("val.jsonl", "val.metadata.jsonl"):
        link = output / name.replace("val.", "valid.", 1)
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(name)


def self_test():
    weights = largest_remainder({"a": 0.5, "b": 0.5}, 3)
    assert sum(weights.values()) == 3
    assert assign_bin(1, 2, 4, True) == "strong"
    assert assign_bin(3, 2, 4, True) == "moderate"
    assert assign_bin(5, 2, 4, True) == "subtle"
    assert assign_bin(1, 2, 4, False) == "subtle"
    assert assign_bin(5, 2, 4, False) == "strong"
    assert unit_severity(5000, 5000, 15000, True) == 1
    assert unit_severity(15000, 5000, 15000, True) == 0
    assert percentile([10, 20, 30, 40], 1 / 3)[0] == 20
    from lmushra.data_paths import to_production_relative
    absolute = "/scratch/tingyup2/projects/AudioLM/production/phase1_real_speech_music_v1/a.wav"
    assert to_production_relative(absolute) == "production/phase1_real_speech_music_v1/a.wav"


def main():
    self_test()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", type=Path, default=Path(
        "/scratch/tingyup2/projects/AudioLM/annotations/caption-poc-fast-v3/run/snapshots/population_1000000/calibrated_llm"))
    parser.add_argument("--matched", type=Path, default=Path(
        "/scratch/tingyup2/projects/AudioLM/annotations/caption-poc-fast-v3/run/snapshots/population_1000000/matched_ablations/calibrated_llm"))
    parser.add_argument("--strict", type=Path, default=Path(
        "/scratch/tingyup2/projects/AudioLM/annotations/reasoned-caption-32b-v13-pilot/registry/runs/reasoned-caption-v10-2bd3cd87099f/exports/unique64_absolute/calibrated_llm"))
    parser.add_argument("--output", type=Path, default=Path("/scratch/jackiel4/data/AudioLM/projector-warmup-24k"))
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"refusing to overwrite nonempty {args.output}")

    print("loading strict and matched", flush=True)
    strict = load_small_export(args.strict, "strict_reasoned_pilot")
    matched = load_small_export(args.matched, "matched_poc")
    overlap = set(strict) & set(matched)
    print(f"strict {len(strict)} matched {len(matched)} overlap {len(overlap)}", flush=True)

    print("scanning full calibrated_llm", flush=True)
    full_clean, val_sources, scan_counts = scan_full(args.full)
    print(f"full clean {len(full_clean)} val source groups {len(val_sources)}", flush=True)

    by_id = {}
    for record in full_clean:
        by_id[record["sample_id"]] = record

    # Strict captions replace the full row. Matched ids keep the matched store.
    # A strict id missing from the clean full scan is still eligible.
    for sample_id, stored in strict.items():
        base = by_id.get(sample_id)
        record = compact_from_metadata(stored["metadata"], "strict_reasoned_pilot", stored["published_split"], stored["row_index"])
        record["store"] = "strict_reasoned_pilot"
        if base and base["published_split"] != record["published_split"]:
            raise ValueError(f"{sample_id} strict split {record['published_split']} != full {base['published_split']}")
        by_id[sample_id] = record
    for sample_id, stored in matched.items():
        if sample_id in strict:
            continue
        if not stored["clean"]:
            by_id.pop(sample_id, None)
            continue
        base = by_id.get(sample_id)
        record = compact_from_metadata(stored["metadata"], "matched_poc", stored["published_split"], stored["row_index"])
        record["store"] = "matched_poc"
        if base and base["published_split"] != record["published_split"]:
            raise ValueError(f"{sample_id} matched split {record['published_split']} != full {base['published_split']}")
        by_id[sample_id] = record

    records = list(by_id.values())
    train_candidates = [record for record in records if record["published_split"] == "train"]
    edges = annotate_severity(records)
    weights, clean_content_counts = content_weights(train_candidates)
    holdouts = choose_holdouts(train_candidates)
    held_ids = {item["source_id"] for item in holdouts.values()}
    val_sources |= held_ids
    for sample_id, stored in list(strict.items()) + list(matched.items()):
        if stored["published_split"] == "valid":
            val_sources.add(source_id_of(stored["metadata"]))

    train_pool = [record for record in records if record["published_split"] == "train" and record["source_id"] not in val_sources]
    val_pool = [record for record in records if record["source_id"] in val_sources]
    leaked = {record["source_id"] for record in train_pool} & {record["source_id"] for record in val_pool}
    if leaked:
        raise ValueError(f"source ids in both pools: {sorted(leaked)[:5]}")

    for record in val_pool:
        if record["source_id"] in held_ids or record["origin"] != "full_synthetic":
            record["force"] = True
    for record in train_pool:
        if record["origin"] != "full_synthetic":
            record["force"] = True

    train_quotas = cell_quotas(weights, TRAIN_PER_CELL, [content for content in weights])
    val_weights = {content: weights[content] for content in VAL_CONTENTS}
    val_scale = sum(val_weights.values())
    val_weights = {content: weight / val_scale for content, weight in val_weights.items()}
    val_quotas = cell_quotas(val_weights, VAL_PER_CELL, list(val_weights))

    train_force = {record["sample_id"] for record in train_pool if record.get("force")}
    val_force = {record["sample_id"] for record in val_pool if record.get("force")}
    train_chosen, train_achieved = fill_cells(train_pool, train_quotas, train_force, "train")
    train_chosen = top_up_family_bins(train_chosen, train_pool, TRAIN_PER_CELL, "train")
    val_chosen, val_achieved = fill_cells(val_pool, val_quotas, val_force, "valid")
    for record in train_chosen:
        record["output_split"] = "train"
    for record in val_chosen:
        record["output_split"] = "valid"

    train_ids = {record["sample_id"] for record in train_chosen}
    val_ids = {record["sample_id"] for record in val_chosen}
    if train_ids & val_ids:
        raise ValueError("sample id selected for both splits")
    if {record["source_id"] for record in train_chosen} & {record["source_id"] for record in val_chosen}:
        raise ValueError("source id selected for both splits")

    wanted = defaultdict(set)
    for record in train_chosen + val_chosen:
        if record["store"] == "full_synthetic":
            wanted[record["published_split"]].add(record["row_index"])
    print("reading selected full rows", flush=True)
    full_examples = load_selected_full_rows(args.full, wanted)
    stores = {"strict_reasoned_pilot": strict, "matched_poc": matched}

    args.output.mkdir(parents=True, exist_ok=True)
    prompt_counts = Counter()
    prompt_counts.update(write_split(args.output / "train", train_chosen, stores, full_examples))
    prompt_counts.update(write_split(args.output / "val", val_chosen, stores, full_examples))
    link_valid_alias(args.output)

    def quota_dump(quotas):
        return {f"{artifact}|{bin_name}|{content}": count for (artifact, bin_name, content), count in sorted(quotas.items())}

    report = {
        "seed": SEED,
        "output": str(args.output),
        "symlink": "valid.jsonl -> val.jsonl and valid.metadata.jsonl -> val.metadata.jsonl, relative",
        "prompt_policy": "copied from the source row; not rewritten",
        "distinct_user_prompts": len(prompt_counts),
        "scan": dict(scan_counts),
        "clean_train_content_before_holdout": clean_content_counts,
        "content_weights": weights,
        "severity_edges": edges,
        "holdouts": holdouts,
        "train_target_per_family_bin": TRAIN_PER_CELL,
        "val_sampled_target_per_family_bin": VAL_PER_CELL,
        "train_quotas": quota_dump(train_quotas),
        "val_sampled_quotas": quota_dump(val_quotas),
        "train": tally(train_chosen),
        "valid": tally(val_chosen),
        "notes": [
            "UN severity uses crossover_hz because strength is constant.",
            "Published val has no guitar, singing, or codec-exposed speech, so the smallest clean source_id of each is held out of train and included whole in valid.",
            "Warned rows are omitted. Strict rows are included even when the full-export annotation differs.",
            "On the strict/matched overlap the strict row is kept.",
        ],
    }
    (args.output / "selection_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"train": report["train"]["n"], "valid": report["valid"]["n"], "prompts": len(prompt_counts), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
