"""Plot existing mapped-pilot measurements; no refitting or listener-score access."""
import argparse,csv,json
from pathlib import Path
import numpy as np
from deepmushra_mapped.mapping import load_table,parameter_for_quality

def main():
    p=argparse.ArgumentParser();p.add_argument("--dataset",type=Path,required=True);args=p.parse_args()
    out=args.dataset;rows=[json.loads(line) for line in (out/"metadata.jsonl").read_text().splitlines()]
    table=load_table();dest=out/"analysis";dest.mkdir(exist_ok=True)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    artifacts=["LP","SH","UN","QN"]
    fig,axes=plt.subplots(2,2,figsize=(12,8),constrained_layout=True)
    for ax,a in zip(axes.flat,artifacts):
        c=table["artifacts"][a];scale=1000 if a in ("LP","UN") else .01 if a=="SH" else 1
        ax.plot(np.array(c["x"])/scale,c["quality_mean"],"o-")
        for q in (50,65,75):ax.plot(parameter_for_quality(a,q)/scale,q,"*",ms=12)
        ax.set(title=a,xlabel={"LP":"Passband edge (kHz)","SH":"Hole probability (%)","UN":"Crossover (kHz)","QN":"Mono waveform SNR (dB)"}[a],ylabel="Estimated quality under transfer assumptions",ylim=(0,100));ax.grid(alpha=.2)
    fig.suptitle("Frozen four-artifact priors; stars = requests 50 / 65 / 75")
    fig.savefig(dest/"mapping_curves.png",dpi=150);plt.close(fig)
    definitions={"LP":("stopband_spectral_energy_change_db","Stopband energy change (dB)"),
                 "SH":("eligible_tf_selection_ratio","Selected eligible TF fraction"),
                 "UN":("reference_tonal_peak_mean_contrast_db_after","Peak contrast after replacement (dB)"),
                 "QN":("measured_snr_db","Measured waveform SNR (dB)")}
    summary=[]
    fig,axes=plt.subplots(2,2,figsize=(12,8),constrained_layout=True)
    for ax,a in zip(axes.flat,artifacts):
        field,label=definitions[a]
        for q in (50,65,75):
            selected=[r for r in rows if r["degradation"]["artifact_type"]==a and r["request"]["value"]==q]
            values=[r["measurements"][field] for r in selected if r["measurements"].get(field) is not None]
            if values:ax.scatter([q]*len(values),values,alpha=.55)
            summary.append({"artifact":a,"requested_estimated_quality":q,"parameter":parameter_for_quality(a,q),
                "examples":len(selected),"with_quality_estimate":sum(r["calibration_estimate"]["estimated_quality_mean"] is not None for r in selected),
                "metric":field,"metric_valid_count":len(values),"metric_median":float(np.median(values)) if values else None,
                "metric_min":min(values) if values else None,"metric_max":max(values) if values else None})
        ax.set(title=a,xlabel="Requested estimated quality",ylabel=label);ax.grid(alpha=.2)
    fig.suptitle("Objective checks on independent recordings; no audibility interpretation")
    fig.savefig(dest/"objective_checks.png",dpi=150);plt.close(fig)
    with (dest/"pilot_summary.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
    example=next(r for r in rows if r["degradation"]["artifact_type"]=="LP" and r["request"]["value"]==65)
    (dest/"metadata_example.json").write_text(json.dumps(example,indent=2,sort_keys=True,allow_nan=False)+"\n")
    print(json.dumps(summary,indent=2,allow_nan=False))

if __name__=="__main__":main()
