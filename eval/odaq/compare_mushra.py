#!/usr/bin/env python3
"""Compare model outputs on ODAQ pairs with the ODAQ listener (MUSHRA) ratings.

Run: python eval/odaq/compare_mushra.py PREDICTIONS.csv [--clap PRED_clap.csv]
         [--ratings /mnt/data2/hwangbo5/data/ODAQ/ODAQ_listening_test/ODAQ_results.csv] [-o OUT.csv]

PREDICTIONS.csv is the output of analyze.py. Pairs are joined to the ratings on
(item folder, degraded file stem); identical pairs join to the hidden reference.
Writes one row per pair with the mean/median listener score and the model-side
measures, then prints Spearman correlations (overall and within each method).

Model-side measures:
  word_severity   mean ordinal of the severity words in the response (see WORD_LEVEL;
                  negated words skipped), or the explicit "level N" if one is given
  correct_method  the regex cue for the actual method matched (analyze.py)
  clap_*          from clap_score.py, if --clap is given (delta = text->deg - text->ref)
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import mannwhitneyu, spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze import EXPLICIT_LEVEL, METHOD_PATTERNS, SEVERITY_PHRASE  # noqa: E402

RATINGS = "/mnt/data2/hwangbo5/data/ODAQ/ODAQ_listening_test/ODAQ_results.csv"
# Ordinal for every word SEVERITY_PHRASE can match: higher = more severe.
WORD_LEVEL = {
    "minimal": 1, "very subtle": 1, "very slight": 1, "very mild": 1, "barely perceptible": 1,
    "slight": 2, "slightly": 2, "subtle": 2, "mild": 2, "perceptible": 2,
    "fairly subtle": 2, "somewhat": 2,
    "noticeable": 3, "moderate": 3, "moderately": 3, "fairly noticeable": 3,
    "pronounced": 4, "significant": 4, "substantial": 4, "very noticeable": 4,
    "highly noticeable": 4,
    "severe": 5, "severely": 5, "extreme": 5, "very severe": 5, "extremely severe": 5,
}


def word_severity(text):
    numbers = {int(n) for n in EXPLICIT_LEVEL.findall(text)}
    if len(numbers) == 1:
        return float(numbers.pop())
    levels = []
    for m in SEVERITY_PHRASE.finditer(text):
        if re.search(r"\b(?:not|no|hardly)\s+$", text[:m.start()], re.I):
            continue
        phrase = " ".join(m.group().lower().split())
        level = WORD_LEVEL.get(phrase, WORD_LEVEL.get(phrase.split()[-1]))
        if level is not None:
            levels.append(level)
    return sum(levels) / len(levels) if levels else float("nan")


def load(pred_csv, clap_csv, ratings_csv):
    d = pd.read_csv(pred_csv)
    d["item"] = d["reference path"].map(lambda p: Path(p).parent.name)
    d["process"] = [("reference" if r == g else Path(g).stem)
                    for r, g in zip(d["reference path"], d["degraded path"])]
    r = pd.read_csv(ratings_csv)
    agg = r.groupby(["item", "process"]).score.agg(mushra="mean", mushra_median="median",
                                                   n_listeners="count").reset_index()
    d = d.merge(agg, on=["item", "process"], how="left", validate="many_to_one")
    d["word_severity"] = d.response.map(word_severity)
    d["correct_method"] = [bool(row[row["processing method"]]) if row["processing method"] in METHOD_PATTERNS
                           else not any(row[k] for k in METHOD_PATTERNS) for _, row in d.iterrows()]
    if clap_csv:
        c = pd.read_csv(clap_csv)
        assert len(c) == len(d) and (c.response.values == d.response.values).all(), "CLAP rows do not line up"
        d["clap_text_degraded"] = c.clap_text_degraded.values
        d["clap_text_reference"] = c.clap_text_reference.values
        d["clap_delta"] = d.clap_text_degraded - d.clap_text_reference
        d["clap_audio_ref_deg"] = c.clap_audio_ref_deg.values
    return d


def rho(x, y):
    m = x.notna() & y.notna()
    if m.sum() < 5:
        return f"   n/a (n={m.sum()})"
    s = spearmanr(x[m], y[m])
    return f"{s.statistic:+.2f} (p={s.pvalue:.3f}, n={m.sum()})"


def report(d):
    p = d[d["processing method"] != "reference"]
    print(f"pairs: {len(d)}, with ratings: {d.mushra.notna().sum()}, "
          f"listeners per pair: {int(d.n_listeners.min())}-{int(d.n_listeners.max())}")
    cols = ["word_severity"] + [c for c in ("clap_delta", "clap_audio_ref_deg") if c in d]
    print("\nSpearman with mean MUSHRA (processed pairs; higher MUSHRA = better quality,"
          " so a good severity measure is negative and audio similarity positive)")
    print(f"  {'':10s}" + "".join(f"{c:>30s}" for c in cols))
    for name, g in [("all", p), *p.groupby("processing method")]:
        print(f"  {name:10s}" + "".join(f"{rho(g[c], g.mushra):>30s}" for c in cols))
    print("\nMUSHRA when the correct method was / was not named (processed pairs):")
    for name, g in [("all", p), *p.groupby("processing method")]:
        a, b = g[g.correct_method].mushra, g[~g.correct_method].mushra
        test = (f"MWU p={mannwhitneyu(a, b).pvalue:.3f}" if len(a) and len(b) else "")
        print(f"  {name:10s} named {a.mean():5.1f} (n={len(a):3d})   missed {b.mean():5.1f} (n={len(b):3d})  {test}")
    ref = d[d["processing method"] == "reference"]
    print(f"\nIdentical pairs: mean MUSHRA {ref.mushra.mean():.1f}; "
          f"mean word severity {ref.word_severity.mean():.2f} "
          f"(processed pairs: {p.word_severity.mean():.2f})")
    print("\nMean word severity by MUSHRA band (processed pairs):")
    bands = pd.cut(p.mushra, [0, 20, 40, 60, 80, 100], include_lowest=True)
    print(p.groupby(bands, observed=True).agg(n=("mushra", "size"), word_severity=("word_severity", "mean"),
                                              resolved=("word_severity", "count")).round(2).to_string())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("predictions", type=Path, help="CSV from analyze.py")
    ap.add_argument("--clap", type=Path)
    ap.add_argument("--ratings", type=Path, default=Path(RATINGS))
    ap.add_argument("-o", "--output", type=Path, help="Defaults to PREDICTIONS_mushra.csv")
    args = ap.parse_args()
    d = load(args.predictions, args.clap, args.ratings)
    out = args.output or args.predictions.with_name(args.predictions.stem + "_mushra.csv")
    d.drop(columns=["reference path", "degraded path"]).to_csv(out, index=False)
    report(d)
    print(f"\n{out}")


if __name__ == "__main__":
    main()
