"""Secondary parameter probes using the unchanged production operators."""
import argparse
from pathlib import Path
import soundfile as sf
import json
import numpy as np
from deepmushra_data.stft import analyze, STFTConfig
from deepmushra_data.degradations import apply_effect
from deepmushra_data.metadata import write_json
from validate_synthetic_artifacts import metrics, SR


def detailed_figures(output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    comparison = json.loads((output/"supplementary.json").read_text())["UN_additive_comparison"]
    rows = []
    fig, ax = plt.subplots(figsize=(10, 4), constrained_layout=True)
    for row in comparison:
        audio, sr = sf.read(output/"examples"/f"UN_additive_comparison_{row['condition']}.wav", always_2d=True)
        f, t, z = analyze(audio, sr, STFTConfig())
        power = np.mean(np.abs(z[4:-4,:,0])**2, axis=0)
        selected = (f >= 11000) & (f < 12000)
        floor = max(float(power.max())*1e-12, 1e-30)
        local = power[selected]
        flat = float(np.exp(np.mean(np.log(np.maximum(local, floor))))/np.mean(local))
        rows.append({"condition": row["condition"], "flatness_11to12khz": flat})
        ax.plot(f[selected]/1000, 10*np.log10(np.maximum(local,1e-20)), label=row["condition"])
    ax.set(xlabel="Frequency (kHz)", ylabel="Mean STFT power (dBFS)", title="11.2-kHz tone and added/replacement noise, fixed 11–12 kHz band")
    ax.legend(fontsize=7)
    fig.savefig(output/"figures/UN_local_spectral_structure.png", dpi=150)
    plt.close(fig)
    write_json(output/"tonality_detail.json",rows)
    measurements = [json.loads(line) for line in (output/"measurements.jsonl").read_text().splitlines()]
    categories = ["tonal_instrument_stem","percussion_stem","vocal_stem"]
    fig, axes = plt.subplots(4,3,figsize=(16,12),constrained_layout=True)
    mappings = []
    for index, artifact in enumerate(["LP","SH","UN","QN"]):
        for column, category in enumerate(categories):
            candidates = [row for row in measurements if row["artifact"]==artifact and row["category"]==category and "audio" in row]
            row = min(candidates, key=lambda item:item["source_id"])
            x, sr = sf.read(output/row["audio"]["reference"], always_2d=True)
            y, _ = sf.read(output/row["audio"]["degraded"], always_2d=True)
            f, times, rz = analyze(x,sr,STFTConfig())
            _, _, dz = analyze(y,sr,STFTConfig())
            floor = max(float(np.abs(rz).max())*1e-4,1e-15)
            ratio = 20*np.log10(np.maximum(np.abs(dz[:,:,0]),floor)/np.maximum(np.abs(rz[:,:,0]),floor))
            image = axes[index,column].pcolormesh(times,f/1000,ratio.T,shading="auto",vmin=-15,vmax=15,cmap="RdBu_r")
            axes[index,column].set(xlabel="Time (s)",ylabel="Frequency (kHz)",title=f"{artifact} / {category}")
            mappings.append({"artifact":artifact,"category":category,"source_id":row["source_id"],"parameters":row["parameters"]})
        fig.colorbar(image,ax=axes[index,:],label="Degraded/reference magnitude (dB)")
    fig.suptitle("Real mono excerpts: strongest tested settings, magnitude changes; floor at reference peak -80 dB")
    fig.savefig(output/"figures/real_content_spectral_changes.png",dpi=130)
    plt.close(fig)
    write_json(output/"real_figure_sources.json",mappings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output.resolve()
    specifications = [
        ("SH", "white_noise", "attenuation_db", [0, 6, 20, 40, 80, "zero"], {"hole_probability": .3}),
        ("SH", "white_noise", "run_frames", [1, 2, 4, 8, 16], {"hole_probability": .3}),
        ("SH", "white_noise", "band_width_hz", [1, 125, 500, 2000], {"hole_probability": .3}),
        ("UN", "harmonic", "crossover_hz", [3000, 7000, 10500, 16000], {"strength": 1}),
        ("UN", "harmonic", "smoothing_hz", [1, 125, 250, 500, 1000], {"strength": 1}),
        ("UN", "white_noise", "tonal_threshold_db", [3, 6, 12, 20], {"strength": 1}),
        ("UN", "sine_11200", "tonal_threshold_db", [3, 6, 12, 20], {"strength": 1}),
        ("QN", "tonal_burst", "envelope_ms", [.1, 1, 5, 20, 100], {"snr_db": 20}),
        ("QN", "harmonic", "fir_taps", [17, 129, 513], {"snr_db": 20}),
        ("QN", "sine_11200", "smoothing_hz", [1, 125, 500, 1000], {"snr_db": 20}),
    ]
    rows = []
    for artifact, source, parameter, values, defaults in specifications:
        x, sr = sf.read(output/"inputs"/f"{source}.wav", always_2d=True)
        assert sr == SR
        entry = {"source_id": source, "artifact": artifact}
        if source == "tonal_burst":
            entry.update(onset_sample=SR//3, offset_sample=2*SR//3)
        for value in values:
            result = apply_effect(artifact, x, SR, {**defaults, parameter: value}, 901)
            row = {"artifact": artifact, "source": source, "varied_parameter": parameter,
                   "value": value, "resolved_parameters": result.parameters,
                   "measurements": metrics(x, result, entry)}
            rows.append(row)
    write_json(output/"parameter_probes.json", rows)
    detailed_figures(output)
    print(f"Secondary probes complete: {len(rows)} conditions, with local-tonality and real-content figures", flush=True)

if __name__ == "__main__":
    main()
