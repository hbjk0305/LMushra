"""Objective pilot diagnostics; no listening annotations or ODAQ inputs."""
import argparse, csv, hashlib, json, os
from collections import defaultdict
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy import signal
from scipy.ndimage import gaussian_filter1d
from deepmushra_data.audioio import write_wav
from deepmushra_data.degradations import apply_effect
from deepmushra_data.metadata import read_jsonl, write_json
from deepmushra_data.stft import STFTConfig, analyze, synthesize
from deepmushra_data.validation import validate_dataset

EFFECTS=("LP","SH","UN","QN")
PARAM={"LP":"cutoff_hz","SH":"hole_probability","UN":"strength","QN":"snr_db"}
METRIC={"LP":"stopband_spectral_energy_change_db","SH":"eligible_tf_selection_ratio", "UN":"tonal_contrast_reduction_db","QN":"measured_snr_db"}
LABEL={"LP":"Stopband spectral energy change (dB)","SH":"Selected eligible TF fraction", "UN":"Reference-peak contrast reduction (dB)","QN":"Measured reference/noise SNR (dB)"}
UNIT={"LP":"Passband edge (Hz)","SH":"Hole selection probability","UN":"Replacement blend strength","QN":"Requested SNR (dB)"}

def value(record):
    a=record["degradation"]["artifact_type"];m=record["measurements"]
    if a=="UN":
        before=m["reference_tonal_peak_mean_contrast_db_before"];after=m["reference_tonal_peak_mean_contrast_db_after"]
        return None if before is None or after is None else before-after
    return m[METRIC[a]]

def summary(numbers):
    vals=[x for x in numbers if x is not None]
    return {"n":len(vals),"median":float(np.median(vals)) if vals else None,"min":float(min(vals)) if vals else None,"max":float(max(vals)) if vals else None}

def plots(root,records,destination,plt):
    colors={c:plt.get_cmap("tab10")(i) for i,c in enumerate(sorted({r["source"]["content_category"] for r in records}))}
    for artifact in EFFECTS:
        rows=[r for r in records if r["degradation"]["artifact_type"]==artifact]
        fig,axes=plt.subplots(1,2,figsize=(12,4),constrained_layout=True)
        for source in sorted({r["source"]["source_id"] for r in rows}):
            series=sorted([r for r in rows if r["source"]["source_id"]==source],key=lambda r:r["degradation"]["parameters"][PARAM[artifact]])
            category=series[0]["source"]["content_category"]
            xs=[r["degradation"]["parameters"][PARAM[artifact]] for r in series]
            axes[0].plot(xs,[value(r) if value(r) is not None else np.nan for r in series],"o-",color=colors[category],alpha=.8)
            axes[1].plot(xs,[r["measurements"]["normalized_spectral_magnitude_error"] for r in series],"o-",color=colors[category],alpha=.8)
        axes[0].set(xlabel=UNIT[artifact],ylabel=LABEL[artifact]);axes[1].set(xlabel=UNIT[artifact],ylabel="Normalized spectral magnitude error")
        for category,color in colors.items(): axes[0].plot([],[],color=color,label=category)
        axes[0].legend(fontsize=8)
        fig.suptitle(f"{artifact}: eight source recordings; objective changes, no perceptual calibration")
        fig.savefig(destination/f"{artifact}_parameter_metrics.png",dpi=150);plt.close(fig)
        # Select by processing parameter and source ID, never by largest measured effect.
        target=min if artifact in ("LP","QN") else max
        level=target(r["degradation"]["parameters"][PARAM[artifact]] for r in rows)
        strong=[r for r in rows if r["degradation"]["parameters"][PARAM[artifact]]==level]
        for category in sorted(colors):
            r=min([r for r in strong if r["source"]["content_category"]==category],key=lambda r:r["source"]["source_id"])
            cfg=r["degradation"]["evidence"]["stft"]; stft=STFTConfig(cfg["n_fft"],cfg["hop_length"])
            fig,axes=plt.subplots(3,2,figsize=(11,8),constrained_layout=True)
            for i,role in enumerate(("reference","degraded","residual")):
                x,sr=sf.read(root/r["audio"][role]["path"],always_2d=True)
                step=max(1,len(x)//5000)
                axes[i,0].plot(np.arange(0,len(x),step)/sr,x[::step,0],lw=.4)
                axes[i,0].set(xlabel="Time (s)",ylabel="Amplitude",title=f"{role}, channel 1")
                f,t,z=analyze(x,sr,stft)
                image=axes[i,1].pcolormesh(t,f/1000,20*np.log10(np.maximum(np.abs(z[:,:,0]),1e-8)).T,shading="auto",vmin=-100,vmax=-10,cmap="magma")
                axes[i,1].set(xlabel="Time (s)",ylabel="Frequency (kHz)",title=f"{role}: STFT dBFS")
            fig.colorbar(image,ax=axes[:,1],label="STFT magnitude dBFS")
            fig.suptitle(f"{artifact} / {category}: {r['source']['source_id']}\n{r['sample_id']}; fixed scale; channel 1 only")
            fig.savefig(destination/f"{artifact}_{category}_triplet.png",dpi=120);plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(12,8),constrained_layout=True)
    for ax,artifact in zip(axes.flat,EFFECTS):
        rows=[r for r in records if r["degradation"]["artifact_type"]==artifact]
        level=(min if artifact in ("LP","QN") else max)(r["degradation"]["parameters"][PARAM[artifact]] for r in rows)
        for i,category in enumerate(sorted(colors)):
            points=[value(r) for r in rows if r["source"]["content_category"]==category and r["degradation"]["parameters"][PARAM[artifact]]==level]
            points=[v for v in points if v is not None]
            ax.scatter(np.full(len(points),i),points,color=colors[category])
            if points: ax.plot([i-.2,i+.2],[np.mean(points)]*2,color="black")
        ax.set_xticks(range(len(colors)),[c.replace("_","\n") for c in sorted(colors)],fontsize=8)
        ax.set(title=f"{artifact}: setting {level:g}",ylabel=LABEL[artifact])
    fig.suptitle("Content comparison: two independent recordings per category; dots=sources, bars=mean")
    fig.savefig(destination/"content_comparison.png",dpi=150);plt.close(fig)

def temporal_probes(destination,plt):
    sr=44100; n=sr; onset=sr//3;offset=2*sr//3
    x=np.zeros((n,2));t=np.arange(offset-onset)/sr
    x[onset:offset,0]=.1*np.cos(2*np.pi*11200*t)+.05*np.cos(2*np.pi*1000*t)
    x[onset:offset,1]=.7*x[onset:offset,0]
    settings={"LP":{"cutoff_hz":5000},"SH":{"start_hz":4000,"hole_probability":.7,"run_frames":4},"UN":{"crossover_hz":7000,"strength":1},"QN":{"snr_db":20}}
    write_wav(destination/"probe_reference.wav",x,sr)
    rows=[];fig,axes=plt.subplots(4,1,figsize=(11,9),constrained_layout=True)
    for ax,(artifact,p) in zip(axes,settings.items()):
        result=apply_effect(artifact,x,sr,p,20261102)
        residual=result.audio-x
        pre=float(np.sum(residual[:onset]**2)); total=float(np.sum(residual**2))
        limit=max(float(np.max(np.abs(residual)))*1e-4,1e-15)
        selected=np.flatnonzero(np.max(np.abs(residual[:onset]),axis=1)>limit)
        extent=(onset-int(selected[0]))/sr*1000 if len(selected) else 0.
        post_selected=np.flatnonzero(np.max(np.abs(residual[offset:]),axis=1)>limit)
        post_extent=(int(post_selected[-1])+1)/sr*1000 if len(post_selected) else 0.
        row={"post_offset_energy_fraction":float(np.sum(residual[offset:]**2))/total if total else None,
            "post_offset_extent_ms_relative_minus80dB":post_extent,"artifact":artifact,"parameters":result.parameters,"pre_onset_residual_energy":pre,"total_residual_energy":total,
            "pre_onset_energy_fraction":pre/total if total else None,"pre_onset_extent_ms_relative_minus80dB":extent,
            "threshold_absolute":limit,"threshold_definition":"max(residual peak*1e-4,1e-15), engineering threshold not audibility",
            "onset_sample":onset,"offset_sample":offset,"sample_rate":sr,"seed":20261102}
        if artifact=="LP":
            sos=np.array(result.evidence["sos_coefficients"])
            freqs,response=signal.sosfreqz(sos,worN=16384,fs=sr)
            delay=-np.gradient(np.unwrap(np.angle(response)),2*np.pi*freqs)*1000
            selected_band=(freqs>100)&(freqs<result.parameters["cutoff_hz"])
            row.update(filter_order=result.evidence["filter_order"],passband_group_delay_median_ms=float(np.median(delay[selected_band])),passband_group_delay_max_ms=float(np.max(delay[selected_band])))
        rows.append(row)
        write_wav(destination/f"probe_{artifact}_degraded.wav",result.audio,sr)
        write_wav(destination/f"probe_{artifact}_residual.wav",residual,sr)
        idx=np.arange(max(0,onset-round(.06*sr)),onset+round(.03*sr))
        ax.plot((idx-onset)/sr*1000,x[idx,0],label="reference",alpha=.5,lw=.5)
        ax.plot((idx-onset)/sr*1000,residual[idx,0],label="residual",lw=.5)
        ax.axvline(0,color="black",ls="--");ax.set(title=f"{artifact}: pre-onset energy fraction {row['pre_onset_energy_fraction']:.3g}, extent {extent:.2f} ms",xlabel="Time relative to onset (ms)",ylabel="Amplitude")
        ax.legend(fontsize=8)
    fig.suptitle("Analytical burst probe only; not training data or perceptual pre-echo labels")
    fig.savefig(destination/"temporal_onset_probes.png",dpi=150);plt.close(fig)
    write_json(destination/"temporal_probes.json",rows)
    return rows

def lp_boundary_check(root, records):
    rows=[]
    for record in records:
        if record["degradation"]["artifact_type"]!="LP":continue
        x,sr=sf.read(root/record["audio"]["reference"]["path"],always_2d=True)
        y,_=sf.read(root/record["audio"]["degraded"]["path"],always_2d=True)
        f,t,z=analyze(x,sr,STFTConfig());_,_,dz=analyze(y,sr,STFTConfig())
        interior=(t>4096/sr)&(t<len(x)/sr-4096/sr)
        band=f>=record["degradation"]["parameters"]["cutoff_hz"]+record["degradation"]["parameters"]["transition_hz"]
        ratio=np.sum(np.abs(dz[interior][:,band])**2)/np.sum(np.abs(z[interior][:,band])**2)
        rows.append({"sample_id":record["sample_id"],"cutoff_hz":record["degradation"]["parameters"]["cutoff_hz"],
            "full_stft_band_change_db":record["measurements"]["stopband_spectral_energy_change_db"],
            "interior_stft_band_change_db":float(10*np.log10(ratio)),
            "response_stopband_min_db":record["degradation"]["evidence"]["response_stopband_attenuation_min_db"]})
    return {"method":"Exclude STFT frame centers within 4096 samples of either file boundary; same stopband bins and 2048-point Hann analysis", "samples":rows}


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--dataset",required=True);ap.add_argument("--repeat");args=ap.parse_args()
    root=Path(args.dataset).resolve();out=root/"phase1_analysis";out.mkdir(exist_ok=True)
    import matplotlib;matplotlib.use("Agg");import matplotlib.pyplot as plt
    records=read_jsonl(root/"metadata.jsonl");valid=validate_dataset(root)
    if not valid["valid"]:raise ValueError(valid)
    flat=[];grouped={}
    for artifact in EFFECTS:
        rows=[r for r in records if r["degradation"]["artifact_type"]==artifact]
        for level in sorted({r["degradation"]["parameters"][PARAM[artifact]] for r in rows}):
            selected=[r for r in rows if r["degradation"]["parameters"][PARAM[artifact]]==level]
            grouped[f"{artifact}:{level:g}"]={"artifact":artifact,"parameter":PARAM[artifact],"level":level,
                "primary_metric":METRIC[artifact],"primary":summary(value(r) for r in selected),
                "spectral_magnitude_error":summary(r["measurements"]["normalized_spectral_magnitude_error"] for r in selected),
                "relative_residual_energy":summary(r["measurements"]["relative_residual_energy"] for r in selected),
                "un_envelope_error":summary(r["measurements"].get("selected_envelope_relative_error") for r in selected),
                "qn_color_cosine":summary(r["measurements"].get("smoothed_noise_reference_psd_cosine") for r in selected),
                "selected_energy_fraction":summary(r["measurements"].get("selected_reference_spectral_energy_fraction") for r in selected)}
        for r in rows:
            flat.append({"sample_id":r["sample_id"],"source_id":r["source"]["source_id"],"category":r["source"]["content_category"],"artifact":artifact,"parameter":PARAM[artifact],"level":r["degradation"]["parameters"][PARAM[artifact]],"primary_metric":METRIC[artifact],"primary_value":value(r),"spectral_magnitude_error":r["measurements"]["normalized_spectral_magnitude_error"],"residual_relative_energy":r["measurements"]["relative_residual_energy"],"channel_correlation_change":r["measurements"].get("degraded_channel_correlation",0)-r["measurements"].get("reference_channel_correlation",0)})
    with (out/"per_sample_metrics.csv").open("w") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
    source_stats=[];seen=set();roundtrip=0.
    for r in records:
        if r["source"]["source_id"] in seen:continue
        seen.add(r["source"]["source_id"]);x,sr=sf.read(root/r["audio"]["reference"]["path"],always_2d=True)
        f,t,z=analyze(x,sr,STFTConfig());roundtrip=max(roundtrip,float(np.max(np.abs(synthesize(z,sr,len(x),STFTConfig())-x))))
        power=np.abs(z)**2;den=power.sum()
        source_stats.append({"source_id":r["source"]["source_id"],"category":r["source"]["content_category"],"high_band_energy_fraction_above_7k":float(power[:,f>=7000].sum()/den),"high_band_energy_fraction_above_16k":float(power[:,f>=16000].sum()/den),"rms":float(np.sqrt(np.mean(x*x))),"peak":float(np.max(np.abs(x))),"split":r["source"]["split"]})
    determinism=None
    if args.repeat:
        repeat=Path(args.repeat).resolve();differences=[];count=0
        files={"metadata.jsonl","manifest.jsonl","resolved_config.json","run.json"}
        for r in records:
            files.update(info["path"] for info in r["audio"].values());files.add(r["degradation"]["mask"]["path"]);files.add(f"metadata/{r['sample_id']}.json")
        for rel in sorted(files):
            if (root/rel).read_bytes()!=(repeat/rel).read_bytes(): differences.append(rel)
            count+=1
        determinism={"byte_compared_files":count,"differences":differences,"identical":not differences}
        if differences:raise ValueError(determinism)
    write_json(out/"lp_boundary_check.json",lp_boundary_check(root,records))
    plots(root,records,out,plt);probes=temporal_probes(out,plt)
    write_json(out/"summary.json",{"validation":valid,"stft_roundtrip_max_abs_error":roundtrip,"determinism":determinism,"by_setting":grouped,"sources":source_stats,"temporal_probes":probes,"perceptual_claims":"unverified; no listening performed"})
    print(json.dumps({"analysis":str(out),"settings":len(grouped),"figures":len(list(out.glob("*.png"))),"determinism":determinism},indent=2))
if __name__=="__main__":main()
