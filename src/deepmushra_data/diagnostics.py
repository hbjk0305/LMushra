"""Headless diagnostic figures; visual differences are not listening labels."""

import os
from pathlib import Path

import numpy as np
import soundfile as sf

from .metadata import read_jsonl
from .stft import STFTConfig, analyze


def plot_dataset(dataset):
    root = Path(dataset).resolve()
    os.environ.setdefault("MPLCONFIGDIR", str(root / ".plot-cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    records = read_jsonl(root / "metadata.jsonl")
    destination = root / "diagnostics"
    destination.mkdir(exist_ok=True)
    generated = []
    for artifact in ("LP", "SH", "UN", "QN"):
        candidates = [r for r in records if r["degradation"]["artifact_type"] == artifact]
        if not candidates:
            continue
        record = max(candidates, key=lambda r: r["measurements"]["residual_rms"])
        cfg = record["degradation"]["evidence"]["stft"]
        stft = STFTConfig(cfg["n_fft"], cfg["hop_length"])
        fig, axes = plt.subplots(3, 2, figsize=(12, 8), constrained_layout=True)
        for row, role in enumerate(("reference", "degraded", "residual")):
            audio, sr = sf.read(root / record["audio"][role]["path"], always_2d=True)
            # Plot channel 1 explicitly; never silently downmix stereo evidence.
            stride = max(1, len(audio) // 4000)
            axes[row, 0].plot(np.arange(0, len(audio), stride) / sr, audio[::stride, 0], linewidth=0.5)
            axes[row, 0].set(xlabel="Time (s)", ylabel="Amplitude", title=f"{role}: channel 1")
            frequencies, times, spectrum = analyze(audio, sr, stft)
            db = 20 * np.log10(np.maximum(np.abs(spectrum[:, :, 0]), 1e-8))
            axes[row, 1].pcolormesh(times, frequencies / 1000, db.T, shading="auto", vmin=-100, vmax=-10, cmap="magma")
            axes[row, 1].set(xlabel="Time (s)", ylabel="Frequency (kHz)", title="STFT magnitude (dBFS, fixed color scale)")
        fig.suptitle(f"{artifact}: {record['sample_id']} — objective diagnostics, perceptual claims unverified")
        path = destination / f"{artifact}.png"
        fig.savefig(path, dpi=120)
        plt.close(fig)
        generated.append(path.relative_to(root).as_posix())
    return generated
