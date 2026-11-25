#!/usr/bin/env python3
"""Is the ODAQ degradation information present in the frozen encoder latents?

Tests the representation the LLM receives (pre-quantization codec latents, pooled as
in training) directly on the 160 ODAQ pairs, without any decoder or LLM:

1. Distance d(reference, degraded) as a quality metric: Spearman with mean MUSHRA
   (pooled and within method) and within-item ranking accuracy against the
   listeners (same scoring as ranking_accuracy.py). A good encoder should do at
   least as well as CLAP audio<->audio (.868 significant-pair accuracy).
2. Detectability floor: does each condition move the latents more than an inaudible
   1-sample delay of the reference? (Key case: LP150, a 15 kHz low-pass.)
3. Method probe: leave-one-item-out logistic regression on paired features,
   classes LP/PE/SH/TM/UN/reference.

Representations: DAC 44.1 kHz encoder, EnCodec 24 kHz encoder (both pooled x4 as in
lmushra), and a 44.1 kHz log-mel (128 bands to 22.05 kHz, same frame rate as DAC)
as a no-learning, full-band reference point.

Run:  source /data/aisaro2/enn_env.sh
      $SWIFT_PYTHON eval/odaq/latent_probe.py [--requests eval/odaq/requests.local.enn.jsonl]
          [--compare RUN_mushra.csv] [--reps dac encodec mel] [--out eval/odaq/latent_probe]
--compare adds clap_audio_ref_deg and word_severity from a compare_mushra.py output.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf
import torch
import torch.nn.functional as F
from scipy import signal
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze import CONDITIONS  # noqa: E402
from ranking_accuracy import bootstrap_ci, pairs, rating_matrix, score, summarize  # noqa: E402

RATINGS = os.environ.get("ODAQ_RATINGS", "/data/aisaro2/ODAQ/ODAQ_listening_test/ODAQ_results.csv")
DEFAULT_COMPARE = HERE / "calibrated_llm-dac--v1-20261116-160324--checkpoint-30148/predictions_mushra.csv"
POOL = 4
CLASSES = ["LP", "PE", "SH", "TM", "UN", "reference"]


def load_mono(path, sr):
    x, fs = sf.read(path, dtype="float32", always_2d=True)
    x = x.mean(1)
    g = np.gcd(int(fs), int(sr))
    return signal.resample_poly(x, sr // g, fs // g).astype(np.float32)


def label(ref, deg):
    if ref == deg:
        return "reference", 999.0
    stem = Path(deg).stem
    if stem in ("LP35", "LP70"):
        return "LP", {"LP35": 0.5, "LP70": 1.5}[stem]
    for method, conds in CONDITIONS.items():
        if stem in conds:
            return method, float(conds.index(stem) + 1)
    raise ValueError(f"unknown ODAQ condition {deg}")


# ---------------------------------------------------------------- representations
class Dac:
    name, sr = "dac", 44100

    def __init__(self, dev):
        import dac
        path = os.environ.get("DAC_MODEL_PATH") or dac.utils.download(
            model_type="44khz", model_bitrate="8kbps", tag="0.0.1")
        self.m = dac.DAC.load(path).to(dev).float().eval()
        self.dev = dev

    @torch.no_grad()
    def __call__(self, x):
        t = torch.from_numpy(x)[None, None].to(self.dev)
        t = F.pad(t, (0, (-t.shape[-1]) % self.m.hop_length))  # as DacAudioTower (pad_to_hop)
        z = F.avg_pool1d(self.m.encoder(t), POOL, POOL, ceil_mode=True)
        return z[0].T.cpu().numpy()  # [frames, 1024]


class Encodec:
    name, sr = "encodec", 24000

    def __init__(self, dev):
        from encodec import EncodecModel
        ckpt = os.environ.get("ENCODEC_MODEL_PATH")
        self.m = EncodecModel.encodec_model_24khz(pretrained=not ckpt)
        if ckpt:
            self.m.load_state_dict(torch.load(ckpt, map_location="cpu", weights_only=True), strict=True)
        self.m = self.m.to(dev).eval()
        self.dev = dev

    @torch.no_grad()
    def __call__(self, x):
        t = torch.from_numpy(x)[None, None].to(self.dev)
        z = F.avg_pool1d(self.m.encoder(t), POOL, POOL, ceil_mode=True)
        return z[0].T.cpu().numpy()  # [frames, 128]


class Mel:
    """Log-mel at 44.1 kHz, hop 512, pooled x4 -> same frame rate as DAC tokens."""
    name, sr = "mel", 44100

    def __init__(self, dev):
        import librosa
        self.librosa = librosa

    def __call__(self, x):
        m = self.librosa.feature.melspectrogram(y=x, sr=self.sr, n_fft=2048, hop_length=512,
                                                n_mels=128, fmin=0, fmax=self.sr / 2, power=2.0)
        m = 10 * np.log10(m + 1e-10).T  # [frames, 128], dB
        n = int(np.ceil(len(m) / POOL)) * POOL
        m = np.pad(m, ((0, n - len(m)), (0, 0)), mode="edge")
        return m.reshape(-1, POOL, m.shape[1]).mean(1)


REPS = {"dac": Dac, "encodec": Encodec, "mel": Mel}


# ---------------------------------------------------------------- features
def frame_dist(zr, zd, scale):
    """Per-frame RMS of the difference, in units of reference per-dimension std."""
    n = min(len(zr), len(zd))
    return np.sqrt((((zd[:n] - zr[:n]) / scale) ** 2).mean(1))


def paired_features(zr, zd, scale):
    n = min(len(zr), len(zd))
    diff = (zd[:n] - zr[:n]) / scale
    return np.concatenate([diff.mean(0), np.abs(diff).mean(0)])


def delayed(x, k=1):
    return np.concatenate([np.zeros(k, x.dtype), x[:-k]])


def extract(rep, requests):
    """Latents for every clip (references cached), plus the 1-sample-delay floor."""
    refs, degs = {}, {}
    for r in requests:
        ref, deg = r["audios"]
        if ref not in refs:
            x = load_mono(ref, rep.sr)
            refs[ref] = (rep(x), rep(delayed(x)))
        if deg != ref and deg not in degs:
            degs[deg] = rep(load_mono(deg, rep.sr))
    # Per-dimension scale from all reference frames (avoids one dimension dominating).
    allref = np.concatenate([z for z, _ in refs.values()])
    scale = allref.std(0) + 1e-6
    return refs, degs, scale


def probe(X, y, groups, seed=0):
    """Leave-one-item-out multinomial logistic regression; returns predictions."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import LeaveOneGroupOut
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    pred = np.empty(len(y), dtype=object)
    for tr, te in LeaveOneGroupOut().split(X, y, groups):
        clf = make_pipeline(StandardScaler(), LogisticRegression(C=0.05, max_iter=5000, random_state=seed))
        clf.fit(X[tr], y[tr])
        pred[te] = clf.predict(X[te])
    return pred


# ---------------------------------------------------------------- reports
def rho(x, y):
    m = x.notna() & y.notna()
    if m.sum() < 5:
        return np.nan, np.nan
    s = spearmanr(x[m], y[m])
    return s.statistic, s.pvalue


def within_rho(d, col, by="processing method"):
    """Percentile ranks taken inside each group, then pooled (groups differ in size:
    LP has 60 processed pairs, the others 20, so raw ranks are not comparable)."""
    p = d[d["processing method"] != "reference"].copy()
    p["_m"] = p.groupby(by)[col].rank(pct=True)
    p["_q"] = p.groupby(by)["mushra"].rank(pct=True)
    return rho(p["_m"], p["_q"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--requests", type=Path, default=HERE / "requests.local.enn.jsonl")
    ap.add_argument("--ratings", type=Path, default=Path(RATINGS))
    ap.add_argument("--compare", type=Path, default=DEFAULT_COMPARE if DEFAULT_COMPARE.exists() else None)
    ap.add_argument("--reps", nargs="+", default=list(REPS), choices=list(REPS))
    ap.add_argument("--out", type=Path, default=HERE / "latent_probe")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    dev = "cuda" if torch.cuda.is_available() else "cpu"

    requests = [json.loads(line) for line in open(args.requests)]
    d = pd.DataFrame([dict(zip(("processing method", "actual severity level"), label(*r["audios"])),
                           ref=r["audios"][0], deg=r["audios"][1]) for r in requests])
    d["item"] = d.ref.map(lambda p: Path(p).parent.name)
    d["process"] = [("reference" if r == g else Path(g).stem) for r, g in zip(d.ref, d.deg)]
    agg = pd.read_csv(args.ratings).groupby(["item", "process"]).score.mean().rename("mushra")
    d = d.join(agg, on=["item", "process"])
    assert d.mushra.notna().all(), "some pairs have no ratings"
    print(f"{len(d)} pairs, {d.item.nunique()} items; device {dev}")

    probe_rows, floor_rows, metric_cols = [], [], []
    for name in args.reps:
        rep = REPS[name](dev)
        refs, degs, scale = extract(rep, requests)
        dist_mean, dist_p95, feats, above_floor = [], [], [], []
        for ref, deg in zip(d.ref, d.deg):
            zr, zr_shift = refs[ref]
            zd = zr if deg == ref else degs[deg]
            fd = frame_dist(zr, zd, scale)
            floor = frame_dist(zr, zr_shift, scale)
            dist_mean.append(fd.mean())
            dist_p95.append(np.percentile(fd, 95))
            above_floor.append(fd.mean() / floor.mean())
            feats.append(paired_features(zr, zd, scale))
        d[f"{name}_dist"] = dist_mean
        d[f"{name}_dist_p95"] = dist_p95
        d[f"{name}_vs_floor"] = above_floor  # >1: moves latents more than a 1-sample delay
        metric_cols += [f"{name}_dist", f"{name}_dist_p95"]

        X, y = np.array(feats), d["processing method"].values
        pred = probe(X, y, d.item.values)
        d[f"{name}_probe"] = pred
        row = dict(rep=name, acc=(pred == y).mean(),
                   acc_processed=(pred[y != "reference"] == y[y != "reference"]).mean())
        for c in CLASSES:
            row[f"recall_{c}"] = (pred[y == c] == c).mean()
        probe_rows.append(row)
        pd.crosstab(pd.Series(y, name="actual"), pd.Series(pred, name="predicted")).reindex(
            index=CLASSES, columns=CLASSES, fill_value=0).to_csv(args.out / f"confusion_{name}.csv")

        for (m, cond), g in d[d["processing method"] != "reference"].groupby(["processing method", "process"]):
            floor_rows.append(dict(rep=name, method=m, condition=cond,
                                   level=g["actual severity level"].iloc[0],
                                   median_vs_floor=g[f"{name}_vs_floor"].median(),
                                   frac_above_floor=(g[f"{name}_vs_floor"] > 1).mean(),
                                   mushra=g.mushra.mean()))
        print(f"done: {name} ({rep.sr} Hz, dim {X.shape[1] // 2})")
        del rep
        if dev == "cuda":
            torch.cuda.empty_cache()

    if args.compare:
        c = pd.read_csv(args.compare)[["item", "process", "clap_audio_ref_deg", "word_severity"]]
        d = d.merge(c, on=["item", "process"], how="left", validate="one_to_one")
        d["clap_audio_dist"] = -d.clap_audio_ref_deg  # similarity -> distance
        metric_cols += ["clap_audio_dist", "word_severity"]

    # 1. Distance as a quality metric (higher distance / severity = worse).
    ratings = rating_matrix(args.ratings)
    pr = pairs(ratings, 0.05)
    rows = [dict(metric="designed level", **summarize(pr, *score(
        pr, dict(zip(zip(d.item, d.process), d["actual severity level"])))))]
    for col in metric_cols:
        right, ties, missing = score(pr, dict(zip(zip(d.item, d.process), -d[col])))
        ci = bootstrap_ci(pr, right, pr.sig.values)
        processed = d[d["processing method"] != "reference"]
        r_all, _ = rho(processed[col], processed.mushra)
        r_wm, p_wm = within_rho(d, col)
        r_wi, _ = within_rho(d, col, by="item")
        row = dict(metric=col, **summarize(pr, right, ties, missing), ci_sig=f"{ci[0]:.3f}-{ci[1]:.3f}",
                   rho_pooled=r_all, rho_within=r_wm, p_within=p_wm, rho_item=r_wi)
        for m, g in processed.groupby("processing method"):
            row[f"rho_{m}"] = rho(g[col], g.mushra)[0]
        rows.append(row)
    metrics = pd.DataFrame(rows)
    probes, floors = pd.DataFrame(probe_rows), pd.DataFrame(floor_rows)

    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 30)
    print("\n== Distance vs. listeners (ranking accuracy; Spearman with MUSHRA should be NEGATIVE) ==")
    print(metrics.drop(columns=["p_within"], errors="ignore").round(3).to_string(index=False))
    print("\n== Leave-one-item-out method probe (chance: majority class LP = .375) ==")
    print(probes.round(3).to_string(index=False))
    print("\n== Distance relative to an inaudible 1-sample delay (median ratio; >1 = detectable) ==")
    print(floors.pivot_table(index=["method", "condition", "level"], columns="rep",
                             values="median_vs_floor").sort_index(level=[0, 2]).round(2).to_string())

    d.drop(columns=["ref", "deg"]).to_csv(args.out / "pairs.csv", index=False)
    metrics.to_csv(args.out / "metrics.csv", index=False)
    probes.to_csv(args.out / "probe.csv", index=False)
    floors.to_csv(args.out / "floor.csv", index=False)
    print(f"\nwrote {args.out}/{{pairs,metrics,probe,floor,confusion_*}}.csv")


if __name__ == "__main__":
    main()
