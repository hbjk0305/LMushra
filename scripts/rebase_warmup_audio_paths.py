"""Rewrite warmup JSONL audio paths to production-relative form.

Reads and writes only under the warmup output directory. Does not follow
valid.jsonl, which is a symlink to val.jsonl. Prints the wav list to stdout.
"""
import argparse
import json
import os
from pathlib import Path

from lmushra.data_paths import collect_production_wavs, relativize_export_value


def rebase_file(path: Path, wavs: set) -> None:
    temporary = Path(str(path) + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with path.open() as source, temporary.open("w") as dest:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            rewritten = relativize_export_value(json.loads(line))
            collect_production_wavs(rewritten, wavs)
            dest.write(json.dumps(rewritten, ensure_ascii=False) + "\n")
            if line_number % 5000 == 0:
                print(f"{path.name} {line_number}", flush=True)
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("/scratch/jackiel4/data/AudioLM/projector-warmup-24k"),
    )
    parser.add_argument(
        "--wav-list",
        type=Path,
        default=Path("/scratch/jackiel4/data/AudioLM/projector-warmup-24k/audio_relpaths.txt"),
    )
    args = parser.parse_args()
    wavs = set()
    for name in ("train.jsonl", "train.metadata.jsonl", "val.jsonl", "val.metadata.jsonl"):
        path = args.dataset / name
        if path.is_symlink():
            raise SystemExit(f"refusing to rewrite symlink {path}")
        print(f"rebasing {path}", flush=True)
        rebase_file(path, wavs)
    ordered = sorted(wavs)
    if any(not item.startswith("production/") or item.startswith("production/../") for item in ordered):
        raise SystemExit("wav list left the production/ tree")
    args.wav_list.write_text("".join(f"{item}\n" for item in ordered))
    print(json.dumps({"wavs": len(ordered), "list": str(args.wav_list)}))


if __name__ == "__main__":
    main()
