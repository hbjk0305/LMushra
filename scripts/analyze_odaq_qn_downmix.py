"""Downmix ODAQ QN pairs; associate frozen stereo priors without fitting mono quality."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np
import scipy
from scipy.signal import resample_poly
import soundfile as sf

from deepmushra_data.audioio import write_wav


def checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False, sort_keys=True)+"\n")


def energy(x):
    return float(np.sum(np.asarray(x, dtype=np.float64)**2))


def ratio_db(numerator, denominator):
    return float(10*np.log10(numerator/denominator)) if numerator > 0 and denominator > 0 else None


def downmix(x):
    if x.ndim != 2 or x.shape[1] != 2:
        raise ValueError("Expected stereo [samples,2]")
    return np.mean(x, axis=1, keepdims=True)


def csv_write(path, rows):
    with path.open("w", newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader();w.writerows(rows)


def basic_checks():
    rng=np.random.default_rng(20261111)
    x=rng.normal(size=(2048,1));n=rng.normal(size=x.shape)
    stereo=np.repeat(x,2,axis=1)
    assert np.array_equal(downmix(stereo),x)
    same=np.repeat(n,2,axis=1)
    anti=np.column_stack((n[:,0],-n[:,0]))
    assert np.array_equal(downmix(same),n)
    assert np.all(downmix(anti)==0)
    assert np.max(np.abs(downmix(stereo+same)-downmix(stereo)-downmix(same)))<1e-14
    y=resample_poly(x,147,160,axis=0,window=("kaiser",5.0),padtype="constant")
    assert y.shape==(int(np.ceil(len(x)*147/160)),1)
    return {"linked_noise_retained":True,"antiphase_noise_cancelled":True,
            "downmix_linearity":True,"resampling_length":True}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output",type=Path,default=Path("outputs/odaq_qn_downmix_v1"))
    args=ap.parse_args();out=args.output
    if out.exists():raise ValueError("Output exists; use a fresh --output path")
    out.mkdir(parents=True);(out/"figures").mkdir()
    base=Path("data/external/odaq_collection_audit/release/odaq-collection/2025-aes/ODAQ_v1.5_listening_test")
    fit=Path("outputs/odaq_calibration_phase1_poc_v1/fit")
    split=Path("outputs/odaq_listener_calibration_feasibility_v1/proposed_listener_split.csv")
    protected=[fit/"models.json",fit/"calibration_bootstrap.npz",fit/"frozen_fit_seal.json",split]
    protected += sorted(Path("src/deepmushra_data").glob("*.py"))+sorted(Path("configs").glob("*"))+sorted(Path("tests").glob("*.py"))
    before={str(p):checksum(p) for p in protected if p.is_file()}
    models=json.loads((fit/"models.json").read_text())
    measured=[];records=[];input_hashes={};written_hashes={};max_linear_error=0.;max_residual_error=0.
    checks=basic_checks()
    for trial in sorted(base.glob("QN*")):
        refs=list(trial.glob("*_reference.wav"))
        assert len(refs)==1
        ref_path=refs[0];input_hashes[str(ref_path)]=checksum(ref_path)
        x,sr=sf.read(ref_path,always_2d=True,dtype="float64")
        assert sr==48000 and x.shape[1]==2 and np.isfinite(x).all()
        source=trial.name.split("_",1)[1]
        for degraded_path in sorted(trial.glob("*_NMR*.wav")):
            input_hashes[str(degraded_path)]=checksum(degraded_path)
            y,ysr=sf.read(degraded_path,always_2d=True,dtype="float64")
            assert ysr==sr and y.shape==x.shape and np.isfinite(y).all()
            noise=y-x;mx=downmix(x);my=downmix(y);mn=my-mx
            linear_error=float(np.max(np.abs(mn-downmix(noise))))
            max_linear_error=max(max_linear_error,linear_error)
            assert linear_error<1e-14
            basis="MS" if "noiseMS" in degraded_path.name else "LR"
            group="QNmix_"+basis if trial.name.startswith("QNmix_") else "QN"+basis
            label=float(re.search(r"NMR(\d+)",degraded_path.name).group(1))
            curve=models[group]["models"]["isotonic"]["pooled"]
            assert label in curve["x"] and source in models[group]["sources"]
            quality=float(curve["quality"][curve["x"].index(label)])
            local=models[group]["models"]["source_shrinkage"]["sources"][source]
            source_quality=float(local["quality"][local["x"].index(label)])
            er=energy(x);en=energy(noise);reference_retention=energy(mx)/(er/2)
            noise_retention=energy(mn)/(en/2)
            noise_cosine=float(np.sum(noise[:,0]*noise[:,1])/np.sqrt(energy(noise[:,0])*energy(noise[:,1])))
            stereo_snr=ratio_db(er,en)
            case=degraded_path.stem
            for target_rate in [48000,44100]:
                if target_rate==48000:rx,dy=mx,my
                else:
                    rx=resample_poly(mx,147,160,axis=0,window=("kaiser",5.0),padtype="constant")
                    dy=resample_poly(my,147,160,axis=0,window=("kaiser",5.0),padtype="constant")
                assert rx.shape==dy.shape==(int(np.ceil(len(x)*target_rate/sr)),1)
                folder=out/"audio"/str(target_rate)/trial.name
                folder.mkdir(parents=True,exist_ok=True)
                paths={"reference":folder/"reference.wav","degraded":folder/(case+".wav"),
                       "residual":folder/(case+"_residual.wav")}
                if not paths["reference"].exists():write_wav(paths["reference"],rx,target_rate)
                saved_ref,rsr=sf.read(paths["reference"],always_2d=True,dtype="float64")
                assert np.array_equal(saved_ref,rx) and rsr==target_rate
                write_wav(paths["degraded"],dy,target_rate)
                saved_deg,dsr=sf.read(paths["degraded"],always_2d=True,dtype="float64")
                residual=saved_deg-saved_ref
                write_wav(paths["residual"],residual,target_rate)
                saved_error,esr=sf.read(paths["residual"],always_2d=True,dtype="float64")
                assert dsr==esr==target_rate and np.array_equal(saved_error,saved_deg-saved_ref)
                assert np.isfinite(saved_ref).all() and np.isfinite(saved_deg).all() and np.isfinite(saved_error).all()
                assert max(abs(saved_ref).max(),abs(saved_deg).max())<1
                reconstruction_error=float(np.max(np.abs(saved_ref+saved_error-saved_deg)))
                max_residual_error=max(max_residual_error,reconstruction_error)
                snr=ratio_db(energy(saved_ref),energy(saved_error))
                rr={"group":group,"source":source,"nmr_label_db":label,"sample_rate_hz":target_rate,
                    "inherited_stereo_quality_mean":quality,"inherited_source_conditioned_quality":source_quality,
                    "stereo_waveform_snr_db":stereo_snr,"mono_waveform_snr_db":snr,
                    "snr_change_vs_native_stereo_db":snr-stereo_snr,
                    "native_downmix_reference_energy_retention":reference_retention,
                    "native_downmix_noise_energy_retention":noise_retention,
                    "native_noise_lr_cosine":noise_cosine,
                    "reference_peak":float(np.max(abs(saved_ref))),"degraded_peak":float(np.max(abs(saved_deg))),
                    "residual_peak":float(np.max(abs(saved_error))),"samples":len(saved_ref),
                    "trial":trial.name,"original_degraded":str(degraded_path)}
                measured.append(rr)
                rec={"analysis_id":trial.name+"/"+case+"/"+str(target_rate),"artifact":"QN",
                    "source":source,"processing":{"downmix":"(L+R)/2","source_sample_rate_hz":sr,
                    "target_sample_rate_hz":target_rate,"resampler":None if target_rate==sr else
                    {"function":"scipy.signal.resample_poly","up":147,"down":160,"window":["kaiser",5.0],"padtype":"constant"},
                    "normalization":"none","saved_audio_subtype":"DOUBLE","residual_definition":"saved_degraded - saved_reference"},
                    "measurements":rr,"original_assets":{"reference":str(ref_path),"degraded":str(degraded_path)},
                    "audio":{k:str(p.relative_to(out)) for k,p in paths.items()},
                    "calibration_prior":{"model_id":"odaq-calibration-poc-v1/"+group+"/isotonic",
                    "parameter":"odaq_nmr_label_db","parameter_value":label,"quality":quality,
                    "domain":"original ODAQ stereo condition","calibration_listeners":3,
                    "mono_quality_estimate":None,"mono_transfer_validated":False},
                    "usage":"ODAQ-informed downmix diagnostic; not training data or independent evaluation"}
                records.append(rec)
                for p in paths.values():written_hashes[str(p.relative_to(out))]=checksum(p)
    assert len(measured)==112 and len(records)==112
    csv_write(out/"measurements.csv",measured)
    with (out/"manifest.jsonl").open("w") as f:
        for r in records:f.write(json.dumps(r,sort_keys=True,allow_nan=False)+"\n")
    aggregate=[]
    for group in sorted({r["group"] for r in measured}):
        for rate in (48000,44100):
            for label in sorted({r["nmr_label_db"] for r in measured if r["group"]==group}):
                subset=[r for r in measured if r["group"]==group and r["sample_rate_hz"]==rate and r["nmr_label_db"]==label]
                assert len(subset)==4
                snrs=[r["mono_waveform_snr_db"] for r in subset];shifts=[r["snr_change_vs_native_stereo_db"] for r in subset]
                aggregate.append({"group":group,"sample_rate_hz":rate,"nmr_label_db":label,"sources":4,
                    "inherited_stereo_quality_mean":subset[0]["inherited_stereo_quality_mean"],
                    "mono_snr_median_db":float(np.median(snrs)),"mono_snr_min_db":min(snrs),"mono_snr_max_db":max(snrs),
                    "snr_shift_median_db":float(np.median(shifts)),"snr_shift_min_db":min(shifts),"snr_shift_max_db":max(shifts),
                    "native_noise_retention_median":float(np.median([r["native_downmix_noise_energy_retention"] for r in subset]))})
    csv_write(out/"mapping_coordinates.csv",aggregate)
    monotonicity=[]
    for group in sorted({r["group"] for r in measured}):
        for source in models[group]["sources"]:
            for rate in (48000,44100):
                subset=sorted([r for r in measured if r["group"]==group and r["source"]==source and r["sample_rate_hz"]==rate],key=lambda r:r["nmr_label_db"])
                monotonicity.append({"group":group,"source":source,"rate":rate,
                    "snr_increasing_with_label":bool(np.all(np.diff([r["mono_waveform_snr_db"] for r in subset])>=0))})
    write_json(out/"monotonicity.json",monotonicity)
    plot(out,models,measured,aggregate)
    assert all(checksum(p)==h for p,h in before.items())
    assert all(checksum(p)==h for p,h in input_hashes.items())
    checks.update({"input_files_unchanged":True,"protected_files_unchanged":True,
        "all_saved_residuals_exact":True,"finite_waveforms":True,"reference_degraded_below_full_scale":True})
    summary={"conditions":56,"mono_triplets":112,"rates":[48000,44100],"source_recordings":4,
        "group_condition_counts":{g:sum(r["group"]==g and r["sample_rate_hz"]==44100 for r in measured) for g in models if g.startswith("QN")},
        "calibration_listeners":3,"new_mono_ratings":0,"new_mapping_fit":False,"heldout_ratings_read":False,
        "max_downmix_linearity_error":max_linear_error,"max_residual_reconstruction_error":max_residual_error,
        "monotonic_snr_series":sum(r["snr_increasing_with_label"] for r in monotonicity),"snr_series":len(monotonicity),
        "checks":checks,"input_sha256":input_hashes,"protected_sha256":before,
        "output_audio_sha256":written_hashes,"script_sha256":checksum(__file__),
        "versions":{"numpy":np.__version__,"scipy":scipy.__version__,"soundfile":sf.__version__,"python":sys.version.split()[0]}}
    write_json(out/"summary.json",summary)
    print(json.dumps({k:v for k,v in summary.items() if not k.endswith("sha256")},indent=2),flush=True)
    print("44.1 kHz coordinates:",flush=True)
    for a in aggregate:
        if a["sample_rate_hz"]==44100:print(json.dumps(a),flush=True)


def plot(out,models,rows,aggregate):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    groups=["QNLR","QNMS","QNmix_LR","QNmix_MS"]
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),constrained_layout=True)
    for group in groups:
        c=models[group]["models"]["isotonic"]["pooled"]
        axes[0].plot(c["x"],c["quality"],"o-",label=group)
        rr=[r for r in aggregate if r["group"]==group and r["sample_rate_hz"]==44100]
        xs=np.array([r["mono_snr_median_db"] for r in rr]);ys=[r["inherited_stereo_quality_mean"] for r in rr]
        err=np.array([[r["mono_snr_median_db"]-r["mono_snr_min_db"] for r in rr],[r["mono_snr_max_db"]-r["mono_snr_median_db"] for r in rr]])
        axes[1].errorbar(xs,ys,xerr=err,fmt="o-",capsize=3,label=group)
    axes[0].set(xlabel="Released ODAQ NMR label (dB)",ylabel="Frozen calibration stereo quality mean",ylim=(0,100),title="Original calibration curves (unchanged)")
    axes[1].set(xlabel="Measured mono waveform SNR (dB), 44.1 kHz",ylabel="Inherited STEREO quality prior",ylim=(0,100),title="Mono measurements + unchanged stereo priors")
    axes[1].text(.02,.02,"Horizontal bars: min/max across 4 sources\nNot confidence intervals; no mono listening ratings",transform=axes[1].transAxes,fontsize=8)
    for ax in axes:ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.savefig(out/"figures/mapping_overview.png",dpi=150);plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(12,8),constrained_layout=True)
    for ax,group in zip(axes.flat,groups):
        for source in models[group]["sources"]:
            rr=sorted([r for r in rows if r["group"]==group and r["source"]==source and r["sample_rate_hz"]==44100],key=lambda r:r["nmr_label_db"])
            ax.plot([r["mono_waveform_snr_db"] for r in rr],[r["inherited_stereo_quality_mean"] for r in rr],"o-",label=source)
        ax.set(title=group,xlabel="Measured mono waveform SNR (dB)",ylabel="Inherited STEREO quality prior",ylim=(0,100));ax.grid(alpha=.2);ax.legend(fontsize=6)
    fig.suptitle("Source-dependent coordinates; lines are visual guides, not fitted mono-quality models")
    fig.savefig(out/"figures/source_mapping_coordinates.png",dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),constrained_layout=True)
    for ax,group in zip(axes,["QNLR","QNMS"]):
        for source in models[group]["sources"]:
            rr=sorted([r for r in rows if r["group"]==group and r["source"]==source and r["sample_rate_hz"]==44100],key=lambda r:r["nmr_label_db"])
            ax.plot([r["nmr_label_db"] for r in rr],[r["snr_change_vs_native_stereo_db"] for r in rr],"o-",label=source)
        ax.axhline(0,color="black",lw=.7);ax.set(title=group,xlabel="Released NMR label (dB)",ylabel="Mono 44.1k SNR minus native stereo SNR (dB)");ax.grid(alpha=.2);ax.legend(fontsize=6)
    fig.savefig(out/"figures/downmix_snr_change.png",dpi=150);plt.close(fig)


if __name__=="__main__":main()
