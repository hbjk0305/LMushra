#!/usr/bin/env python3
"""Within-item pairwise ranking accuracy against ODAQ listeners, with a listener ceiling.

Run: python eval/odaq/ranking_accuracy.py NAME=RUN_mushra.csv [NAME=RUN_mushra.csv ...]
         [--ratings ODAQ_results.csv] [--alpha 0.05] [--splits 1000]

RUN_mushra.csv is the output of compare_mushra.py. Each ODAQ item has 8 conditions
(5 levels, LP35, LP70, hidden reference), all rated by the same 26 listeners, so every
item gives 28 condition pairs. For each pair the listeners' mean decides which
condition is better; a metric is right when it orders the pair the same way.

  acc_all   all 28 pairs per item (560)
  acc_sig   only pairs where listeners differ significantly (paired Wilcoxon,
            two-sided p < alpha across the 26 listeners)
  acc_noref acc_sig without pairs involving the hidden reference
A tie in the metric scores 0.5; `ties` is the fraction of tied pairs. A pair where
the metric is missing (no severity words) is scored 0.5 as well and counted in `missing`.
  acc_decided  acc_sig restricted to pairs the metric does order (no tie, nothing missing)
  ci_sig       95% bootstrap CI of acc_sig, resampling items

Listener ceiling (same pairs, same scoring):
  single listener vs mean of the other 25  -- how well one person agrees with the panel
  split half 13 vs 13 (random splits)      -- agreement between two half-panels
A model compared with the full 26-listener mean can in principle exceed both.
"""

import argparse
import os
import itertools
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

RATINGS = os.environ.get("ODAQ_RATINGS", "/mnt/data2/hwangbo5/data/ODAQ/ODAQ_listening_test/ODAQ_results.csv")
# (column in *_mushra.csv, sign that turns it into "higher = better quality")
METRICS = {
    "word_severity": ("word_severity", -1),
    "expected_severity": ("expected_severity", -1),  # from severity_probs.py
    "clap_delta": ("clap_delta", -1),        # larger delta = text fits the degraded clip = more change
    "clap_audio_ref_deg": ("clap_audio_ref_deg", +1),
}


def rating_matrix(path):
    """item -> (conditions, array [listeners x conditions])"""
    r = pd.read_csv(path)
    r = r[r.method != "DE"]
    out = {}
    for item, g in r.groupby("item"):
        m = g.pivot(index="subject", columns="process", values="score")
        assert not m.isna().any().any(), item
        out[item] = m
    return out


def pairs(ratings, alpha):
    """All within-item condition pairs with the panel decision and significance."""
    rows = []
    for item, m in ratings.items():
        for a, b in itertools.combinations(m.columns, 2):
            diff = m[a] - m[b]
            p = 1.0 if (diff == 0).all() else wilcoxon(m[a], m[b]).pvalue
            rows.append(dict(item=item, a=a, b=b, panel=np.sign(diff.mean()), p=p,
                             sig=p < alpha, has_ref="reference" in (a, b)))
    return pd.DataFrame(rows)


def score(pr, quality):
    """Pairwise agreement; `quality` maps (item, condition) -> higher-is-better value."""
    qa = np.array([quality.get((i, a), np.nan) for i, a in zip(pr.item, pr.a)])
    qb = np.array([quality.get((i, b), np.nan) for i, b in zip(pr.item, pr.b)])
    missing = np.isnan(qa) | np.isnan(qb)
    s = np.sign(np.nan_to_num(qa) - np.nan_to_num(qb))
    right = np.where(missing | (s == 0), 0.5, (s == pr.panel.values).astype(float))
    right[pr.panel.values == 0] = np.nan  # panel tie: no decision to agree with
    return right, (s == 0) & ~missing, missing


def summarize(pr, right, ties=None, missing=None):
    out = {}
    for name, mask in [("acc_all", np.ones(len(pr), bool)), ("acc_sig", pr.sig.values),
                       ("acc_noref", pr.sig.values & ~pr.has_ref.values)]:
        out[name] = np.nanmean(right[mask])
    if ties is not None:
        decided = pr.sig.values & ~ties & ~missing
        out["acc_decided"] = np.nanmean(right[decided])  # significant pairs the metric actually orders
        out["ties"], out["missing"] = ties.mean(), missing.mean()
    return out


def bootstrap_ci(pr, right, mask, n=2000, seed=0):
    """95% CI resampling items (pairs within an item are not independent)."""
    rng = np.random.default_rng(seed)
    items = pr.item.unique()
    by_item = {i: right[(pr.item.values == i) & mask] for i in items}
    stats = []
    for _ in range(n):
        v = np.concatenate([by_item[i] for i in rng.choice(items, len(items))])
        stats.append(np.nanmean(v))
    return np.percentile(stats, [2.5, 97.5])


def listener_ceiling(ratings, pr, splits, seed=0):
    subjects = next(iter(ratings.values())).index.tolist()
    loo = []
    for s in subjects:
        one = {(i, c): m.loc[s, c] for i, m in ratings.items() for c in m.columns}
        rest = {(i, c): m.drop(index=s)[c].mean() for i, m in ratings.items() for c in m.columns}
        pr_rest = pr.copy()
        pr_rest["panel"] = [np.sign(rest[(i, a)] - rest[(i, b)]) for i, a, b in zip(pr.item, pr.a, pr.b)]
        loo.append(summarize(pr_rest, score(pr_rest, one)[0]))
    rng = np.random.default_rng(seed)
    half = []
    for _ in range(splits):
        perm = rng.permutation(subjects)
        h1, h2 = perm[: len(perm) // 2], perm[len(perm) // 2:]
        q1 = {(i, c): m.loc[h1, c].mean() for i, m in ratings.items() for c in m.columns}
        q2 = {(i, c): m.loc[h2, c].mean() for i, m in ratings.items() for c in m.columns}
        pr_h = pr.copy()
        pr_h["panel"] = [np.sign(q2[(i, a)] - q2[(i, b)]) for i, a, b in zip(pr.item, pr.a, pr.b)]
        half.append(summarize(pr_h, score(pr_h, q1)[0]))
    return pd.DataFrame(loo), pd.DataFrame(half)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+", help="NAME=path/to/RUN_mushra.csv")
    ap.add_argument("--ratings", type=Path, default=Path(RATINGS))
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--splits", type=int, default=1000)
    ap.add_argument("-o", "--output", type=Path, help="Optional CSV of the summary table")
    args = ap.parse_args()

    ratings = rating_matrix(args.ratings)
    pr = pairs(ratings, args.alpha)
    print(f"{len(ratings)} items, {len(pr)} pairs; significant: {pr.sig.sum()} "
          f"({pr.sig.mean():.0%}); significant without reference: {(pr.sig & ~pr.has_ref).sum()}")

    rows = []
    first = pd.read_csv(args.runs[0].split("=", 1)[1])
    designed = first["actual severity level"].astype(float)  # Q1=1 (worst) ... reference=999
    rows.append(dict(run="designed level", metric="actual severity level",
                     **summarize(pr, *score(pr, dict(zip(zip(first.item, first.process), designed))))))
    for spec in args.runs:
        name, path = spec.split("=", 1)
        d = pd.read_csv(path)
        for metric, (col, sign) in METRICS.items():
            audio_only = metric == "clap_audio_ref_deg"  # same for every run: report once
            if col not in d or (audio_only and any(r["metric"] == metric for r in rows)):
                continue
            right, ties, missing = score(pr, dict(zip(zip(d.item, d.process), sign * d[col])))
            ci = bootstrap_ci(pr, right, pr.sig.values)
            rows.append(dict(run="(audio only)" if audio_only else name, metric=metric,
                             **summarize(pr, right, ties, missing), ci_sig=f"{ci[0]:.3f}-{ci[1]:.3f}"))

    loo, half = listener_ceiling(ratings, pr, args.splits)
    for label, df in [("single listener vs other 25", loo), ("split half 13 vs 13", half)]:
        row = dict(run="listeners", metric=label)
        for c in ("acc_all", "acc_sig", "acc_noref"):
            row[c] = df[c].mean()
        row["ci_sig"] = f"{df.acc_sig.quantile(.025):.3f}-{df.acc_sig.quantile(.975):.3f} (spread)"
        rows.append(row)
    table = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(table.round(3).to_string(index=False))
    if args.output:
        table.to_csv(args.output, index=False)
        print(args.output)


if __name__ == "__main__":
    main()
