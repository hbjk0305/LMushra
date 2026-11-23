#!/usr/bin/env python3
"""Build ODAQ requests that ask the model for a single 1-5 severity digit.

Run: python eval/odaq/severity_requests.py REQUESTS.jsonl [--followup PREDICTIONS.jsonl] -o OUT.jsonl

Two variants:
  direct    (default)  one user turn: the two audios + the rating question
  followup  (--followup PREDICTIONS.jsonl) the original description request, the
            model's own description from PREDICTIONS.jsonl as the assistant turn, then
            the rating question. Tests whether the rating is consistent with what it said.

Run the output with eval/run-severity-probs.sh (1 new token, top log-probabilities),
then score it with eval/odaq/severity_probs.py.
"""

import argparse
import json
from pathlib import Path

QUESTION = (
    "Rate how strongly the processed audio is degraded relative to the reference, "
    "on this scale:\n"
    "1 = no audible difference\n"
    "2 = slight degradation\n"
    "3 = noticeable degradation\n"
    "4 = strong degradation\n"
    "5 = very strong degradation\n"
    "Answer with a single digit only."
)
DIRECT_PREFIX = "Reference audio (original): <audio>\nDegraded audio (processed counterpart): <audio>\n\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("requests", type=Path, help="e.g. eval/odaq/requests.local.jsonl")
    ap.add_argument("--followup", type=Path, help="predictions JSONL with the model's descriptions")
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()

    requests = [json.loads(line) for line in args.requests.open() if line.strip()]
    if args.followup:
        preds = [json.loads(line) for line in args.followup.open() if line.strip()]
        if len(preds) != len(requests):
            raise SystemExit(f"{len(preds)} predictions for {len(requests)} requests")
    with args.output.open("w") as f:
        for i, req in enumerate(requests):
            if args.followup:
                pred = preds[i]
                if [Path(a).relative_to(Path(a).parents[1]) for a in pred["audios"]] != \
                        [Path(a).relative_to(Path(a).parents[1]) for a in req["audios"]]:
                    raise SystemExit(f"line {i + 1}: predictions and requests are not in the same order")
                messages = [req["messages"][0], {"role": "assistant", "content": pred["response"]},
                            {"role": "user", "content": QUESTION}]
            else:
                messages = [{"role": "user", "content": DIRECT_PREFIX + QUESTION}]
            f.write(json.dumps({"messages": messages, "audios": req["audios"]}) + "\n")
    print(args.output, len(requests))


if __name__ == "__main__":
    main()
