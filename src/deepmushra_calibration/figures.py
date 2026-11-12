"""Figures from frozen predictions and final evaluation tables."""
from pathlib import Path
import json
import math
import numpy as np

from .experiment import read_csv
from .models import MODEL_NAMES

DISPLAY={"lookup_linear":"Lookup / linear interpolation",
         "isotonic":"Monotonic",
         "source_shrinkage":"Source-conditioned shrinkage"}


def figures(output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    root=Path(output)
    destination=root/"figures"
    destination.mkdir(exist_ok=True)
    predictions=read_csv(root/"fit/frozen_predictions.csv")
    comparisons=read_csv(root/"evaluation/cell_predictions_vs_heldout.csv")
    means=read_csv(root/"fit/calibration_mean_uncertainty.csv")
    metadata=json.loads((root/"fit/models.json").read_text())
    generated=[]
    colors={"lookup_linear":"tab:orange","isotonic":"tab:blue","source_shrinkage":"tab:green"}
    for artifact in ("LP","SH","UN","QN"):
        groups=sorted(key for key,value in metadata.items() if value["artifact"]==artifact)
        columns=min(2,len(groups))
        fig,axes=plt.subplots(math.ceil(len(groups)/columns),columns,
                              figsize=(7*columns,4.5*math.ceil(len(groups)/columns)),squeeze=False,constrained_layout=True)
        for axis,group in zip(axes.flat,groups):
            for model in MODEL_NAMES:
                rows=[r for r in predictions if r["group"]==group and r["model"]==model]
                xs=sorted({float(r["parameter"]) for r in rows})
                curve=[np.mean([float(r["estimated_quality"]) for r in rows if float(r["parameter"])==x]) for x in xs]
                axis.plot(xs,curve,"o-",label=DISPLAY[model],color=colors[model],lw=1.6)
                if model=="isotonic":
                    lower=[np.mean([float(r["bayesian_weight_95_lower"]) for r in rows if float(r["parameter"])==x]) for x in xs]
                    upper=[np.mean([float(r["bayesian_weight_95_upper"]) for r in rows if float(r["parameter"])==x]) for x in xs]
                    axis.fill_between(xs,lower,upper,color=colors[model],alpha=.15,label="95% observed-listener weight band")
                if model=="source_shrinkage":
                    for source in sorted({r["source"] for r in rows}):
                        local=sorted([r for r in rows if r["source"]==source],key=lambda r:float(r["parameter"]))
                        axis.plot([float(r["parameter"]) for r in local],[float(r["estimated_quality"]) for r in local],color=colors[model],alpha=.25,lw=.8)
            scored=[r for r in comparisons if r["group"]==group and r["model"]=="isotonic"]
            xs=sorted({float(r["parameter"]) for r in scored})
            axis.plot(xs,[np.mean([float(r["heldout_mean"]) for r in scored if float(r["parameter"])==x]) for x in xs],
                      "kx",ms=8,label="Held-out cohort-weighted mean")
            axis.set(title=f"{group}; calibration n={metadata[group]['calibration_listeners']}",
                     xlabel=metadata[group]["parameter_units"],ylabel="ODAQ stereo MUSHRA quality",ylim=(-3,103))
            axis.legend(fontsize=7)
        for axis in axes.flat[len(groups):]: axis.set_visible(False)
        fig.suptitle(f"{artifact}: frozen calibration mappings and listener-held-out targets")
        path=destination/f"{artifact}_mappings.png"
        fig.savefig(path,dpi=150);plt.close(fig);generated.append(path.name)
    metrics=read_csv(root/"evaluation/metrics.csv")
    groups=sorted({r["label"] for r in metrics if r["scope"]=="group"})
    matrix=np.array([[float(next(r["rmse"] for r in metrics if r["scope"]=="group" and r["label"]==g and r["model"]==name)) for name in MODEL_NAMES] for g in groups])
    fig,axis=plt.subplots(figsize=(9,7),constrained_layout=True)
    image=axis.imshow(matrix,cmap="magma")
    axis.set_yticks(range(len(groups)),groups)
    axis.set_xticks(range(3),[DISPLAY[name].replace(" / ","\n") for name in MODEL_NAMES],fontsize=9)
    for i in range(len(groups)):
        for j in range(3):axis.text(j,i,f"{matrix[i,j]:.2f}",ha="center",va="center",color="white")
    axis.set_title("Held-out cell-mean RMSE, MUSHRA points")
    fig.colorbar(image,ax=axis)
    fig.savefig(destination/"heldout_rmse.png",dpi=150);plt.close(fig);generated.append("heldout_rmse.png")
    groups=sorted(key for key,value in metadata.items() if value["artifact"]=="QN")
    fig,axes=plt.subplots(2,2,figsize=(13,9),constrained_layout=True)
    for axis,group in zip(axes.flat,groups):
        rows=[r for r in predictions if r["group"]==group and r["model"]=="isotonic"]
        xs=sorted({float(r["parameter"]) for r in rows})
        curve=[np.mean([float(r["estimated_quality"]) for r in rows if float(r["parameter"])==x]) for x in xs]
        low=[np.mean([float(r["leave_one_listener_min"]) for r in rows if float(r["parameter"])==x]) for x in xs]
        high=[np.mean([float(r["leave_one_listener_max"]) for r in rows if float(r["parameter"])==x]) for x in xs]
        axis.plot(xs,curve,"o-",label="Full 3-listener monotonic fit")
        axis.fill_between(xs,low,high,alpha=.25,label="Leave-one-listener sensitivity range")
        diagnostic=[r for r in means if r["group"]==group]
        axis.plot([float(r["parameter"]) for r in diagnostic],[float(r["unweighted_t95_lower"]) for r in diagnostic],"--",color="gray",label="Unweighted t95 diagnostic")
        axis.plot([float(r["parameter"]) for r in diagnostic],[float(r["unweighted_t95_upper"]) for r in diagnostic],"--",color="gray")
        axis.set(title=group,xlabel="ODAQ NMR label (dB)",ylabel="Quality points")
        axis.legend(fontsize=7)
    fig.suptitle("QN uncertainty with three calibration listeners; one later-cohort listener")
    fig.savefig(destination/"QN_small_panel_sensitivity.png",dpi=150)
    plt.close(fig);generated.append("QN_small_panel_sensitivity.png")
    return {"figures":generated,"directory":str(destination)}
