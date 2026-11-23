#!/usr/bin/env python3
"""Turn 1-token severity predictions (with top log-probabilities) into a continuous score.

Run: python eval/odaq/severity_probs.py SEVERITY_PREDICTIONS.jsonl --mushra RUN_mushra.csv [-o OUT.csv]

For each pair, the probabilities of the first generated token being "1".."5" are
renormalized and averaged: expected_severity = sum_k k * p(k) / sum_k p(k).
`digit_mass` = sum_k p(k) before renormalizing; a low value means the model mostly
wanted to answer with something other than a digit, and the score is less meaningful.
Digits outside the returned top-k count as probability 0.

The output is RUN_mushra.csv (from compare_mushra.py, same pair order) with the
columns p1..p5, digit_mass, argmax_digit and expected_severity added, so it can go
straight into ranking_accuracy.py.
"""

import argparse
import json
import math
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr

DIGITS = "12345"


def digit_probs(record):
    content = (record.get("logprobs") or {}).get("content") or []
    if not content:
        raise ValueError("no logprobs in record; run with --logprobs true --top_logprobs N")
    first = content[0]
    probs = dict.fromkeys(DIGITS, 0.0)
    for cand in first.get("top_logprobs") or [first]:
        tok = cand["token"].strip()
        if tok in probs:
            probs[tok] += math.exp(cand["logprob"])
    return probs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("predictions", type=Path)
    ap.add_argument("--mushra", type=Path, required=True, help="*_mushra.csv from compare_mushra.py")
    ap.add_argument("-o", "--output", type=Path, help="Defaults to PREDICTIONS_mushra.csv")
    args = ap.parse_args()

    recs = [json.loads(line) for line in args.predictions.open() if line.strip()]
    d = pd.read_csv(args.mushra)
    if len(recs) != len(d):
        raise SystemExit(f"{len(recs)} predictions vs {len(d)} rows in {args.mushra}")
    for rec, item, process in zip(recs, d["item"], d["process"]):
        ref, deg = (Path(a) for a in rec["audios"])
        stem = "reference" if ref == deg else deg.stem
        if (deg.parent.name, stem) != (item, process):
            raise SystemExit(f"order mismatch: {deg} vs {item}/{process}")

    rows = []
    for rec in recs:
        p = digit_probs(rec)
        mass = sum(p.values())
        exp = sum(int(k) * v for k, v in p.items()) / mass if mass > 0 else float("nan")
        rows.append({**{f"p{k}": v for k, v in p.items()}, "digit_mass": mass,
                     "argmax_digit": max(p, key=p.get) if mass > 0 else "",
                     "generated": rec.get("response", ""), "expected_severity": exp})
    out_df = pd.concat([d.drop(columns=[c for c in rows[0] if c in d]), pd.DataFrame(rows)], axis=1)
    out = args.output or args.predictions.with_name(args.predictions.stem + "_mushra.csv")
    out_df.to_csv(out, index=False)

    proc = out_df[out_df["processing method"] != "reference"]
    print(f"digit mass: median {out_df.digit_mass.median():.3f}, min {out_df.digit_mass.min():.3f}")
    print("argmax digit counts:", out_df.argmax_digit.value_counts().sort_index().to_dict())
    print(f"identical pairs: mean expected severity {out_df[out_df['processing method'] == 'reference'].expected_severity.mean():.2f}"
          f" vs processed {proc.expected_severity.mean():.2f}")
    s = spearmanr(proc.expected_severity, proc.mushra, nan_policy="omit")
    print(f"Spearman(expected severity, MUSHRA), processed pairs: {s.statistic:+.2f} (p={s.pvalue:.3g})")
    print(out)


if __name__ == "__main__":
    main()
