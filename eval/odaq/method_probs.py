#!/usr/bin/env python3
"""Score the 1-token method readout built by method_requests.py.

Run: python eval/odaq/method_probs.py PREDICTIONS.jsonl --meta REQUESTS.meta.jsonl
         --mushra RUN_mushra.csv [-o OUT.csv]

The format (mc or yesno) is read from the meta file.

  mc     p(A..F) of the first generated token, renormalized and mapped back to methods,
         then averaged over the option orders. `letter_mass` is the probability on
         A-F before renormalizing. Prints the confusion matrix, per-method recall,
         macro-F1, the mean probability per letter position (position bias), and
         p(correct) by condition level.
  yesno  p(yes) / (p(yes) + p(no)) per pair and method, and per method the AUC
         separating pairs that have it from pairs that don't.

The true method comes from the condition name (LP35/LP70 anchors count as LP,
identical pairs as NONE). The output is RUN_mushra.csv with one column per method added.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

sys.path.insert(0, str(Path(__file__).resolve().parent))
from method_requests import LETTERS, METHODS  # noqa: E402

LABELS = [label for label, _ in METHODS]


def top_probs(record, keep):
    """Sum the probabilities of the first token's top-k candidates, keyed by keep(token)."""
    content = (record.get("logprobs") or {}).get("content") or []
    if not content:
        raise ValueError("no logprobs in record; run with --logprobs true --top_logprobs N")
    first = content[0]
    out = {}
    for cand in first.get("top_logprobs") or [first]:
        key = keep(cand["token"])
        if key is not None:
            out[key] = out.get(key, 0.0) + math.exp(cand["logprob"])
    return out


def true_method(process):
    return "NONE" if process == "reference" else process[:2]


def check_order(recs, meta, d):
    for rec, m in zip(recs, meta):
        item, process = d.loc[m["pair"], ["item", "process"]]
        ref, deg = (Path(a) for a in rec["audios"])
        stem = "reference" if ref == deg else deg.stem
        if (deg.parent.name, stem) != (item, process):
            raise SystemExit(f"order mismatch: {deg} vs {item}/{process}")


def score_mc(recs, meta, d):
    probs = np.zeros((len(d), len(LABELS)))
    mass = np.zeros(len(d))
    pos_mean = np.zeros(len(LETTERS))
    n_orders = len({m["order"] for m in meta})
    for rec, m in zip(recs, meta):
        p = top_probs(rec, lambda t: t.strip() if t.strip() in LETTERS else None)
        total = sum(p.values())
        mass[m["pair"]] += total / n_orders
        if total == 0:
            continue
        for pos, letter in enumerate(LETTERS):
            share = p.get(letter, 0.0) / total
            probs[m["pair"], LABELS.index(m["letters"][letter])] += share / n_orders
            pos_mean[pos] += share / len(recs)

    out = d.copy()
    for j, label in enumerate(LABELS):
        out[f"p_{label}"] = probs[:, j]
    out["letter_mass"] = mass
    out["true_method"] = out.process.map(true_method)
    out["pred"] = [LABELS[j] for j in probs.argmax(1)]
    out["p_correct"] = [probs[i, LABELS.index(t)] for i, t in enumerate(out.true_method)]

    print(f"letter mass: median {np.median(mass):.3f}, min {mass.min():.3f}")
    print("mean probability by letter position:", {k: round(float(v), 3) for k, v in zip(LETTERS, pos_mean)})
    print("mean probability by method (all pairs):", {k: round(float(v), 3) for k, v in zip(LABELS, probs.mean(0))})
    cm = pd.crosstab(out.true_method, out.pred).reindex(index=LABELS, columns=LABELS, fill_value=0)
    recall = np.diag(cm) / cm.sum(axis=1)
    precision = np.diag(cm) / cm.sum(axis=0).replace(0, np.nan)
    f1 = (2 * precision * recall / (precision + recall)).fillna(0)
    print(f"\naccuracy {np.trace(cm) / cm.values.sum():.3f} (chance {1 / len(LABELS):.3f}), macro-F1 {f1.mean():.3f}")
    print("confusion (rows = true, columns = predicted):")
    print(cm.assign(recall=recall.round(2)).to_string())
    print("\nmean p(correct) by condition, ordered by designed level (most severe first):")
    for method, g in out[out.true_method != "NONE"].groupby("true_method"):
        lv = g.groupby("process").agg(level=("actual severity level", "first"), p=("p_correct", "mean"))
        lv = lv.sort_values("level")
        print(f"  {method}: " + "  ".join(f"{proc} {p:.2f}" for proc, p in lv.p.items()))
    return out


def score_yesno(recs, meta, d):
    out = d.copy()
    out["true_method"] = out.process.map(true_method)
    pyes = {label: np.full(len(d), np.nan) for label in LABELS}
    mass = []
    for rec, m in zip(recs, meta):
        p = top_probs(rec, lambda t: t.strip().lower() if t.strip().lower() in ("yes", "no") else None)
        total = p.get("yes", 0.0) + p.get("no", 0.0)
        mass.append(total)
        if total > 0:
            pyes[m["method"]][m["pair"]] = p.get("yes", 0.0) / total
    for label in LABELS:
        out[f"pyes_{label}"] = pyes[label]

    print(f"yes/no mass: median {np.median(mass):.3f}, min {min(mass):.3f}")
    print(f"{'method':6} {'AUC':>6} {'p(yes) | has it':>16} {'p(yes) | not':>13}")
    for label in LABELS:
        has = out.true_method == label
        s = out[f"pyes_{label}"]
        pos, neg = s[has].dropna(), s[~has].dropna()
        auc = mannwhitneyu(pos, neg).statistic / (len(pos) * len(neg)) if len(pos) and len(neg) else float("nan")
        print(f"{label:6} {auc:6.3f} {pos.mean():16.3f} {neg.mean():13.3f}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("predictions", type=Path)
    ap.add_argument("--meta", type=Path, required=True, help="*.meta.jsonl from method_requests.py")
    ap.add_argument("--mushra", type=Path, required=True, help="*_mushra.csv from compare_mushra.py")
    ap.add_argument("-o", "--output", type=Path, help="Defaults to PREDICTIONS_mushra.csv")
    args = ap.parse_args()

    recs = [json.loads(line) for line in args.predictions.open() if line.strip()]
    meta = [json.loads(line) for line in args.meta.open() if line.strip()]
    d = pd.read_csv(args.mushra)
    if len(recs) != len(meta):
        raise SystemExit(f"{len(recs)} predictions vs {len(meta)} meta rows")
    if {m["pair"] for m in meta} != set(range(len(d))):
        raise SystemExit(f"meta pairs don't cover the {len(d)} rows of {args.mushra}")
    check_order(recs, meta, d)

    out = score_mc(recs, meta, d) if "letters" in meta[0] else score_yesno(recs, meta, d)
    path = args.output or args.predictions.with_name(args.predictions.stem + "_mushra.csv")
    out.to_csv(path, index=False)
    print(path)


if __name__ == "__main__":
    main()
