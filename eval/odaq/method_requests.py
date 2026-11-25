#!/usr/bin/env python3
"""Build ODAQ requests that ask the model which processing was applied, answered with one token.

Run: python eval/odaq/method_requests.py REQUESTS.jsonl --format mc|yesno -o OUT.jsonl

  mc     one multiple-choice question per pair (A-F), asked in len(ORDERS) option
         orders so that a preference for a letter position averages out
  yesno  one yes/no question per pair and method

Next to OUT.jsonl it writes OUT.meta.jsonl with, per request, the pair index and the
letter -> method mapping (mc) or the method asked about (yesno). Run OUT.jsonl with
eval/run-severity-probs.sh (1 new token, top log-probabilities), then score it with
eval/odaq/method_probs.py.

TM and UN follow the definitions in analyze.py (METHOD_PATTERNS).
"""

import argparse
import json
from pathlib import Path

from severity_requests import DIRECT_PREFIX

# (label, how it is described to the model); NONE = identical-reference control
METHODS = [
    ("LP", "low-pass filtering (high frequencies removed above a cutoff)"),
    ("SH", "spectral holes (narrow frequency bands missing)"),
    ("PE", "pre-echo (noise smeared before sharp attacks)"),
    ("TM", "tonality mismatch (above some frequency, noise-like content replaced by tonal components)"),
    ("UN", "unmasked noise (above some frequency, tonal content replaced by audible noise)"),
    ("NONE", "no processing (identical to the reference)"),
]
LETTERS = "ABCDEF"
# Option orders as indices into METHODS; each method sits at a different position in each.
ORDERS = [[0, 1, 2, 3, 4, 5], [2, 3, 4, 5, 0, 1], [5, 4, 3, 2, 1, 0]]
YESNO = {
    label: (f"Was this processing applied to the processed audio: {desc}?\nAnswer with yes or no only."
            if label != "NONE" else
            "Is the processed audio identical to the reference, with no processing applied?\n"
            "Answer with yes or no only.")
    for label, desc in METHODS
}


def mc_question(order):
    lines = [f"{LETTERS[pos]} = {METHODS[m][1]}" for pos, m in enumerate(order)]
    return ("Which processing was applied to the processed audio?\n" + "\n".join(lines)
            + "\nAnswer with a single letter only.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("requests", type=Path, help="e.g. eval/odaq/requests.local.enn.jsonl")
    ap.add_argument("--format", choices=["mc", "yesno"], required=True)
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()

    requests = [json.loads(line) for line in args.requests.open() if line.strip()]
    meta_path = args.output.with_suffix(".meta.jsonl")
    with args.output.open("w") as f, meta_path.open("w") as fm:
        variants = ORDERS if args.format == "mc" else [label for label, _ in METHODS]
        for k, variant in enumerate(variants):
            for i, req in enumerate(requests):
                if args.format == "mc":
                    question = mc_question(variant)
                    meta = {"pair": i, "order": k,
                            "letters": {LETTERS[pos]: METHODS[m][0] for pos, m in enumerate(variant)}}
                else:
                    question, meta = YESNO[variant], {"pair": i, "method": variant}
                f.write(json.dumps({"messages": [{"role": "user", "content": DIRECT_PREFIX + question}],
                                    "audios": req["audios"]}) + "\n")
                fm.write(json.dumps(meta) + "\n")
    print(args.output, len(requests) * len(variants), meta_path)


if __name__ == "__main__":
    main()
