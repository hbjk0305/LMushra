"""Dataset workstream CLI, independent of model training frameworks."""

import argparse
import json
from pathlib import Path
import sys

from .config import load_config
from .pipeline import generate_dataset
from .validation import validate_dataset


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate and validate full-band DeepMUSHRA triplets (minimum 44.1 kHz).")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("demo", "generate"):
        p = commands.add_parser(command)
        p.add_argument("--config", required=True, type=Path)
        p.add_argument("--output", required=True, type=Path)
        p.add_argument("--no-diagnostics", action="store_true")
        if command == "generate":
            inputs = p.add_mutually_exclusive_group(required=True)
            inputs.add_argument("--input-dir", type=Path)
            inputs.add_argument("--manifest", type=Path)
    p = commands.add_parser("validate")
    p.add_argument("--dataset", required=True, type=Path)
    p = commands.add_parser("analyze")
    p.add_argument("--dataset", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command in ("demo", "generate"):
            config = load_config(args.config)
            result = generate_dataset(config, args.output, input_dir=getattr(args, "input_dir", None),
                                      manifest=getattr(args, "manifest", None), demo=args.command == "demo",
                                      diagnostics=not args.no_diagnostics)
        elif args.command == "validate":
            result = validate_dataset(args.dataset)
        else:
            result = validate_dataset(args.dataset)
            if result["valid"]:
                from .diagnostics import plot_dataset
                result["figures"] = plot_dataset(args.dataset)
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0 if result.get("valid", True) else 1
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
