"""Render the active mapping decisions and scientific figures; no fitting."""
import argparse,csv,hashlib,html,json,re
from pathlib import Path
import numpy as np
from deepmushra_mapped.mapping import load_table,parameter_for_quality,estimate_quality,TABLE_PATH
from deepmushra_mapped.profile import release_profile,default_config

ARTS=("LP","SH","UN","QN")
COLORS={"LP":"#2765a0","SH":"#b9581e","UN":"#7455a3","QN":"#19866a"}
NAMES={"LP":"Bandwidth limitation","SH":"Spectral holes","UN":"Tonal-to-noise replacement","QN":"Additive noise"}
SCALE={"LP":1000.,"SH":.01,"UN":1000.,"QN":1.}
UNIT={"LP":"kHz","SH":"%","UN":"kHz","QN":"dB SNR"}
LABEL={"LP":"Passband-edge cutoff (kHz)","SH":"Hole probability (%)","UN":"Replacement crossover (kHz)","QN":"Measured mono waveform SNR (dB)"}
TARGETS=(50,65,75)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def render_html(md,root):
    """Render this report's limited Markdown, embedding all figure SVGs."""
    lines=md.splitlines();out=[];i=0
    inline=lambda text:re.sub(r"\*\*(.*?)\*\*",r"<strong>\1</strong>",html.escape(text))
    while i<len(lines):
        line=lines[i]
        if not line.strip():i+=1;continue
        if line.startswith("~~~"):
            code=[];i+=1
            while i<len(lines) and not lines[i].startswith("~~~"):code.append(lines[i]);i+=1
            out.append("<pre>"+html.escape("\n".join(code))+"</pre>");i+=1;continue
        image=re.fullmatch(r"!\[(.*?)\]\((.*?)\)",line)
        if image:
            svg=(root/Path(image[2]).with_suffix(".svg")).read_text()
            out.append('<figure aria-label="'+html.escape(image[1],quote=True)+'">'+svg[svg.index("<svg"):]+"<figcaption>"+inline(image[1])+"</figcaption></figure>")
            i+=1;continue
        if line.startswith("|"):
            rows=[]
            while i<len(lines) and lines[i].startswith("|"):
                cols=[v.strip() for v in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[: -]+",c) for c in cols):rows.append(cols)
                i+=1
            out.append("<table><thead><tr>"+"".join("<th>"+inline(c)+"</th>" for c in rows[0])+"</tr></thead><tbody>")
            for row in rows[1:]:out.append("<tr>"+"".join("<td>"+inline(c)+"</td>" for c in row)+"</tr>")
            out.append("</tbody></table>");continue
        heading=re.match(r"^(#{1,4}) (.*)",line)
        if heading:
            n=len(heading[1]);out.append(f"<h{n}>"+inline(heading[2])+f"</h{n}>");i+=1;continue
        if line.startswith("- "):
            out.append("<ul>")
            while i<len(lines) and lines[i].startswith("- "):
                out.append("<li>"+inline(lines[i][2:])+"</li>");i+=1
            out.append("</ul>");continue
        para=[line];i+=1
        while i<len(lines) and lines[i].strip() and not lines[i].startswith(("#","|","- ","!","~~~")):
            para.append(lines[i]);i+=1
        out.append("<p>"+inline(" ".join(para))+"</p>")
    css="""body{margin:0;background:#f2f5f7;color:#1c2b38;font:16px/1.58 system-ui,sans-serif;overflow-wrap:anywhere}main{max-width:1160px;margin:auto;background:white;padding:38px 42px 70px}h1{font-size:34px;line-height:1.2}h2{margin:42px 0 16px;border-top:1px solid #d8e1e8;padding-top:24px;font-size:25px}h3{margin-top:24px}p,li{max-width:1000px}table{border-collapse:collapse;width:100%;margin:18px 0;font-variant-numeric:tabular-nums}th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #dfe6eb}thead{background:#eaf1f7}figure{margin:22px 0}svg{display:block;width:100%;height:auto}figcaption{font-size:13px;color:#556574;margin:8px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#edf3f7;padding:18px;border-radius:8px;font:14px/1.6 ui-monospace,monospace}strong{color:#123c58}@media(max-width:700px){main{padding:20px 12px}h1{font-size:28px}th,td{padding:7px;font-size:13px}}@media print{body{background:white}main{padding:0;max-width:none}figure,table{break-inside:avoid}h2{break-after:avoid}}"""
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DeepMUSHRA final mapping decisions</title><style>'+css+"</style><main>"+"\n".join(out)+"</main></html>"

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report-dir",type=Path,default=Path("docs"))
    args=ap.parse_args();root=args.report_dir;figdir=root/"figures/final_mapping";figdir.mkdir(parents=True,exist_ok=True)
    table=load_table();profile=release_profile();config=default_config();before=sha(TABLE_PATH)
    for a in ARTS:
        assert tuple(config["artifacts"][a]["quality_targets"])==TARGETS
        c=table["artifacts"][a]
        for x,y in zip(c["x"],c["quality_mean"]):
            assert abs(estimate_quality(a,x)["estimated_quality_mean"]-y)<1e-10
            assert abs(parameter_for_quality(a,y)-x)<1e-8
        for q in TARGETS:assert abs(estimate_quality(a,parameter_for_quality(a,q))["estimated_quality_mean"]-q)<1e-9
    common=(max(min(c["quality_mean"]) for c in table["artifacts"].values()),min(max(c["quality_mean"]) for c in table["artifacts"].values()))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":11,"axes.spines.top":False,"axes.spines.right":False,
        "axes.titleweight":"bold","svg.fonttype":"none","svg.hashsalt":"DeepMUSHRA-final-mapping-v1"})
    figures=[]
    def save(fig,name):
        for ext in ("png","svg"):
            p=figdir/(name+"."+ext)
            fig.savefig(p,dpi=165,metadata={"Date":None} if ext=="svg" else {"Software":"DeepMUSHRA final mapping report"})
            if ext=="svg":p.write_text("\n".join(line.rstrip() for line in p.read_text().splitlines())+"\n")
            figures.append(p)
        plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(13.5,9.3),constrained_layout=True)
    for ax,a in zip(axes.flat,ARTS):
        c=table["artifacts"][a];x=np.array(c["x"])/SCALE[a];y=np.array(c["quality_mean"])
        ax.plot(x,y,color=COLORS[a],lw=2.5,label="Frozen mean; straight-line interpolation")
        ax.scatter(x,y,color=COLORS[a],s=45,zorder=4,label="Five calibration knots")
        ax.scatter([parameter_for_quality(a,q)/SCALE[a] for q in TARGETS],TARGETS,marker="*",s=180,color="#e1a100",edgecolor="#352b0c",lw=.7,zorder=6,label="Provisional pilot settings: 50, 65, 75")
        for q in TARGETS:ax.axhline(q,color="#bdc4cb",linestyle=":",lw=.8,zorder=0)
        for xx,yy in zip(x,y):ax.annotate(f"{yy:.1f}",(xx,yy),xytext=(0,-17),textcoords="offset points",ha="center",fontsize=8,color=COLORS[a])
        ax.set(title=f"{a}: {NAMES[a]}  |  calibration n={c['calibration_listeners']}",xlabel=LABEL[a],ylabel="Transferred estimated quality (0–100)",ylim=(0,104))
        ax.grid(axis="y",alpha=.15)
        ax.text(.02,.96,"More holes → lower quality" if a=="SH" else "Higher control value → higher quality",transform=ax.transAxes,va="top",fontsize=9,color="#4c5661")
        ax.legend(loc="lower left" if a=="SH" else "lower right",fontsize=8,framealpha=.95)
    fig.suptitle("The four implemented mapping rules",fontsize=18,fontweight="bold")
    fig.supxlabel("Stars are engineer-selected pilot settings, not a final sampling policy or human observations.",fontsize=10)
    save(fig,"01_parameter_quality_curves")
    fig,ax=plt.subplots(figsize=(13.5,5.8),constrained_layout=True)
    for i,name in enumerate(["Bad","Poor","Fair","Good","Excellent"]):
        ax.axvspan(i*20,(i+1)*20,color="#f2f4f6" if i%2==0 else "#e8edf2",zorder=0)
        ax.text(i*20+10,4.65,name,ha="center",fontsize=10,color="#4c5661")
    ax.axvspan(*common,color="#73b5a0",alpha=.25,zorder=1)
    for i,a in enumerate(ARTS):
        yy=3-i;c=table["artifacts"][a];lo=min(c["quality_mean"]);hi=max(c["quality_mean"])
        ax.plot([lo,hi],[yy,yy],color=COLORS[a],lw=8,solid_capstyle="round",zorder=2)
        ax.scatter(c["quality_mean"],[yy]*5,color="white",edgecolor=COLORS[a],s=38,zorder=3)
        ax.scatter(TARGETS,[yy]*3,marker="*",s=135,color="#d69700",edgecolor="#44350d",lw=.5,zorder=4)
        ax.text(lo-.8,yy+.22,f"{lo:.2f}",ha="right",fontsize=9,color=COLORS[a]);ax.text(hi+.8,yy+.22,f"{hi:.2f}",ha="left",fontsize=9,color=COLORS[a])
    for q in TARGETS:ax.axvline(q,color="#927327",linestyle=":",lw=1,zorder=1)
    ax.set(xlim=(0,100),ylim=(-.75,5.05),yticks=[3,2,1,0],yticklabels=ARTS,xlabel="Transferred estimated quality (higher is better)",title="Current pilot coverage — sampling policy is not final")
    ax.text(sum(common)/2,4.02,f"Common supported interval: {common[0]:.2f}–{common[1]:.2f}",ha="center",fontsize=11,fontweight="bold",color="#155d49")
    ax.text(0,-.58,"Pilot only: 50 = Fair; 65 = Good; 75 = Good. The adopted label policy is quality 0–100 plus categories.",fontsize=10)
    ax.grid(axis="x",alpha=.2);save(fig,"02_supported_quality_and_defaults")
    sensitivity_path=Path(__file__).resolve().parents[1]/"docs/report_data/final_mapping_qn_sensitivity.json"
    sensitivity=json.loads(sensitivity_path.read_text())
    assert sensitivity["mapping_table_sha256"]==before and not sensitivity["heldout_ratings_used"]
    c=table["artifacts"]["QN"];loo=[]
    for label in c["released_parameter_knots"]:
        row=next(r for r in sensitivity["points"] if r["released_condition_label"]==label)
        loo.append((row["leave_one_listener_min"],row["leave_one_listener_max"]))
    fig,axes=plt.subplots(1,2,figsize=(13.5,5.6),constrained_layout=True)
    ax=axes[0];x=np.array(c["released_parameter_knots"]);y=np.array(c["x"]);ranges=np.array(c["qn_mono_snr_source_ranges"])
    ax.errorbar(x,y,yerr=[y-ranges[:,0],ranges[:,1]-y],fmt="o-",color=COLORS["QN"],lw=2,capsize=5,label="Median; min/max across 4 recordings")
    ax.plot([0,24],[0,24],"--",color="#858e98",lw=1,label="Identity reference only; not the mapping")
    ax.set(title="QN control axis: measured, not renamed",xlabel="Released ODAQ NMR condition label (dB)",ylabel="Measured mono waveform SNR (dB)")
    ax.legend(fontsize=8);ax.grid(alpha=.2)
    for xx,yy in zip(x,y):ax.annotate(f"{yy:.2f}",(xx,yy),xytext=(0,9),textcoords="offset points",ha="center",fontsize=9)
    ax=axes[1];x=np.array(c["x"]);y=np.array(c["quality_mean"]);bands=np.array(c["conditional_listener_weight_95_bands"]);loo=np.array(loo)
    ax.fill_between(x,loo[:,0],loo[:,1],color="#afb7bf",alpha=.4,label="Leave-one-listener sensitivity range")
    ax.fill_between(x,bands[:,0],bands[:,1],color=COLORS["QN"],alpha=.3,label="Conditional 95% listener-weight band")
    ax.plot(x,y,"o-",lw=2,color=COLORS["QN"],label="Frozen QNMS mean (3 calibration listeners)")
    ax.set(title="QN uncertainty: the small panel matters",xlabel="Measured mono SNR coordinate (dB)",ylabel="Original stereo quality estimate",ylim=(0,100))
    ax.legend(fontsize=8,loc="lower right");ax.grid(alpha=.2)
    fig.supxlabel("Source ranges and conditional bands do not validate mono/synthetic perceived quality.",fontsize=10)
    save(fig,"03_qn_coordinate_and_sensitivity")
    defaults=[]
    for a in ARTS:
        for q in TARGETS:
            p=parameter_for_quality(a,q)
            defaults.append({"artifact":a,"requested_estimated_quality":q,"parameter_axis":table["artifacts"][a]["axis"],"parameter_internal_units":p,
                "display_value":p/SCALE[a],"display_unit":UNIT[a],"estimated_category":estimate_quality(a,p)["estimated_quality_category"]})
    csvpath=figdir/"default_parameters.csv"
    with csvpath.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(defaults[0]),lineterminator="\n");w.writeheader();w.writerows(defaults)
    inverse="\n".join("| "+a+" | "+" | ".join(f"{parameter_for_quality(a,q)/SCALE[a]:.3f}" for q in TARGETS)+" | "+UNIT[a]+" |" for a in ARTS)
    support="\n".join(f"| {a} | {min(table['artifacts'][a]['quality_mean']):.2f}–{max(table['artifacts'][a]['quality_mean']):.2f} |" for a in ARTS)
    knots=[]
    for a in ARTS:
        c=table["artifacts"][a]
        knots.append(f"### {a}: {LABEL[a]}\n\n| Parameter | Estimated mean quality |\n|---:|---:|\n"+"\n".join(f"| {x/SCALE[a]:.3f} | {q:.3f} |" for x,q in zip(c["x"],c["quality_mean"])))
    md=f"""# Quality-label mapping: 0–100 and five categories

**Agreed label policy:** retain transferred estimated quality on the 0–100 scale and derive Bad/Poor/Fair/Good/Excellent. A separate 1–5 severity label is not adopted.

**Software snapshot:** package 0.3.0, profile mapped-poc-1. Stereo-to-mono and approximate-operator transfer assumptions remain explicit. The 50/65/75 pilot targets were an engineering choice, not a user-specified final sampling rule.

## The final decision

Use **one pooled calibration-mean curve per artifact**, with bounded piecewise linear interpolation and inverse lookup for generation. The controls are LP cutoff, SH probability, UN crossover and QN mono waveform SNR. All teammates use the same frozen table. The output label is **continuous transferred estimated quality plus its five-category label**. These are estimates, not newly measured human MUSHRA scores. The existing pilot targets 50/65/75 remain provisional software settings; the final dataset sampling policy is not specified by this label decision.

## 1. Rule for each generator

| Artifact | Mapped control | Direction of better estimated quality | Fixed processing choices |
|---|---|---|---|
| LP | Passband-edge cutoff, Hz | Higher cutoff | Causal Butterworth; 1500 Hz transition; 0.5 dB ripple; 60 dB attenuation |
| SH | Per-band/block hole probability, 0–1 | Lower probability | Start 4 kHz; 500 Hz bands; four-frame blocks; zero gain |
| UN | Replacement crossover, Hz | Higher crossover | Strength 1; 500 Hz envelope sigma; 12 dB peak threshold |
| QN | Mono waveform SNR, dB | Higher SNR | Local spectral-shaped additive noise; exact final SNR; original content retained |

LP/SH/UN use the original ODAQ pooled curves. SH does not combine the 2025 LR/MS/mixed contexts. QN uses the **separated QNMS** curve, not QNLR or a mixed-context curve. New recordings share the family curve; instrument/category does not select an ODAQ source-specific curve.

![Four active parameter-to-quality curves](figures/final_mapping/01_parameter_quality_curves.png)

Circles are frozen calibration knots; straight lines are implemented interpolation; stars are provisional pilot requests, not an approved final sampling policy. Plot values retain the recorded transfer assumptions.

## 2. Mean versus median

At each parameter, average each calibration listener equally over the four reference recordings, average listeners within their cohort, then weight cohort means by original study size:

~~~text
Q(p) = Σ_c (N_c / N_total) × mean_i_in_cohort_c [mean_s_over_4_recordings rating(i,s,p)]
~~~

- LP/SH/UN: nine calibration listeners. Cohort weights 14/42, 12/42, 8/42 and 8/42; calibration counts 3/2/2/2.
- QNMS: three calibration listeners. Cohort weights 9/16 and 7/16; calibration counts 2/1.
- **Quality values are cohort-weighted means, not medians.**
- **Only QN's horizontal SNR coordinate is a median across four downmixed audio recordings.** Its vertical quality remains a mean rating.

Only the frozen approximately 20% calibration panel produced these means. The remaining 80% ratings did not select the generator settings. Averaged knots were already monotonic, so lookup and isotonic knots coincide. The active generator uses the pooled curve, not the earlier source-conditioned shrinkage models.

## 3. Interpolation and generation

Between adjacent knots:

~~~text
Forward: Q(p) = Q_i + (p−p_i)/(p_(i+1)−p_i) × (Q_(i+1)−Q_i)
Inverse: p(Q) = p_i + (Q−Q_i)/(Q_(i+1)−Q_i) × (p_(i+1)−p_i)
~~~

Generation normally uses the inverse. SH has decreasing quality with increasing probability; its quality-axis order is reversed for inversion. Full floating-point values are retained. Report rounding does not alter generation. No curve is extrapolated or refitted on a teammate's corpus.

**Worked example:** LP quality 65 falls between 9 kHz / 55.5119 and 10.5 kHz / 65.8968. Inversion produces a **10.370462 kHz passband edge**. This is not a −3 dB cutoff.

## 4. Existing pilot settings — not a final dataset sampling rule

The current pilot configuration generates three requests per artifact. This table documents the implementation; it does not establish the final sampling design:

| Artifact | Quality 50 parameter | Quality 65 parameter | Quality 75 parameter | Display unit |
|---|---:|---:|---:|---|
{inverse}

Internal units are Hz for LP/UN, probability 0–1 for SH and waveform dB SNR for QN. SH quality 65 therefore uses 0.210501, not 21.0501 as a raw probability. One excerpt yields 12 variants before no-op filtering.

### Support and category coverage

| Artifact | Supported estimated quality interval |
|---|---:|
{support}

The common interval is **{common[0]:.2f}–{common[1]:.2f}**, so the three provisional pilot requests fit every family without extrapolation. This overlap does not require retaining those requests in the final dataset.

![Supported ranges and why the defaults are shared](figures/final_mapping/02_supported_quality_and_defaults.png)

Estimated categories are assigned after the point estimate: Bad [0,20), Poor [20,40), Fair [40,60), Good [60,80), Excellent [80,100]. **50 is Fair; 65 and 75 are both Good.** These are three numerical quality levels, not three categories or validated severity tiers. The existing pilot does not cover all five categories. Changing dataset sampling is a separate decision and must be applied consistently across workers. Do not invent labels or extrapolate curves just to populate a category.

## 5. QN's special rule

The released NMR condition label is not copied into our SNR setting. The x coordinates were measured from downmixed ODAQ QNMS reference/degraded pairs exported at 44.1 kHz mono:

~~~text
Released ODAQ label:             0       6       12       18       24
Measured median mono SNR:      2.229   6.661   12.065   17.724   23.206 dB
Transferred quality mean:     20.055  34.922   55.898   74.711   92.656
~~~

Waveform SNR is 10log10(sum(reference²)/sum(residual²)). Our generator adds locally spectral-shaped noise at the requested SNR while retaining the original content. The implemented transfer is **measured mono SNR → frozen QNMS stereo-quality prior**. This is an empirical coordinate change, not a psychoacoustic NMR model or universal NMR/SNR identity.

![QN coordinate measurements and small-panel sensitivity](figures/final_mapping/03_qn_coordinate_and_sensitivity.png)

Left bars show min/max across four recordings, not confidence intervals. The right panel uses calibration-only results: conditional 95% listener-weight bands and actual leave-one-listener sensitivity. One of the three listeners retains 43.75% of panel weight. Those bands omit operator/mono transfer and unobserved population variation; a narrow band does not establish precise synthetic labels.

## 6. Runtime and metadata rules

- Record exact parameters, algorithm/profile IDs, seeds, actual masks/noise evidence, measured signal changes and source provenance.
- Write the prediction under calibration_estimate.estimated_quality_mean; derive estimated_quality_category separately. Preserve the table fingerprint and transfer assumptions.
- Keep human_mushra_score, audibility and human perceived_severity null. estimated_quality_loss_proxy = 100−quality is a quality-loss proxy, not percent distortion or human severity.
- Preserve conditional reference-listener bands separately; mono_transfer_validated and operator_transfer_validated remain false. Synthetic transfer intervals stay null.
- If processing selects nothing, the reference is silent, or relative residual energy is below the numerical tolerance 1e-20, write no_effect_quality_not_estimated and a null quality. Keep the audit record, omit it from training JSONL by default. This is not an audibility threshold.
- Reject unsupported generation requests. Queries outside support return null. QN 30/40 dB and SH quality 90 cannot be silently labeled.
- AudioLM rows contain exactly messages and audios, with reference before degraded. Residuals/evidence/rich metadata stay in aligned sidecars. Technical captions state processing facts; perceptual candidates remain unverified.

## 7. Shared-team rule

Every worker uses the same released code/profile, frozen mapping, numerical environment, master generation seed **20261111** and the same explicitly versioned sampling configuration. The present 50/65/75 configuration is a provisional pilot, not an agreed final dataset design. Per-example seeds are deterministic. Recording groups, portable path prefixes and fingerprint-checked merges preserve the common implementation.

The earlier listener split seed **20261110** and approximately 20/80 panel roles are distinct from the synthetic source split of 70/15/15. Neither listener selection nor mappings are rerun when processing another corpus. PE/TM remain excluded.

## 8. Implemented versus validated

The 0–100 score and category derivation are already implemented. The provisional pilot request set must not be mistaken for an agreed final sampling policy. Existing readiness evidence: **179 tests passed**; an installed wheel processed eight independent recordings in two workers, generating 96 triplets and exporting 92 examples after four no-op UN cases. Merged rows were train 60 / valid 12 / test 20. These establish engineering behavior and format compatibility, not human-perceptual validation.

The final Phase 1 decision is an **ODAQ-informed assumed-transfer POC**. Mono perceived quality, operator equivalence, new-content generalization and QN's small listener panel remain limitations. The report performs no new audio generation, fitting, held-out evaluation or model training.

## Appendix A. Frozen numerical knots

Values use each plot's displayed units. Full precision remains in mapping_table.json.

{chr(10).join(knots)}

## Appendix B. Reproducibility and source of truth

- Frozen table: src/deepmushra_mapped/mapping_table.json.
- Forward/inverse code: src/deepmushra_mapped/mapping.py.
- Recipe: configs/generator.yaml and packaged profile.json.
- Generators: src/deepmushra_mapped/generators.py and shared DSP helpers.
- Numeric figure data: figures/final_mapping/default_parameters.csv.
- Profile fingerprint: {profile['fingerprint']}.
- Mapping table SHA256: {before}.
- Frozen calibration model SHA256: {table['provenance']['models_sha256']}.
- Listener split SHA256: {table['provenance']['listener_split_sha256']}.
- QN coordinate SHA256: {table['provenance']['qn_coordinates_sha256']}.

Regenerate from the checkout root:

~~~bash
python scripts/report_final_mapping.py
~~~

Outputs: this Markdown report, self-contained final_mapping_report.html, PNG/SVG figures and a verification receipt. The QN sensitivity panel uses docs/report_data/final_mapping_qn_sensitivity.json, a small aggregate snapshot of calibration-only fit/frozen_predictions.csv. Regeneration needs no ODAQ recordings or private calibration outputs. This report does not modify generators or mappings.

Related reports: team_generator_workflow.md; team_generator_readiness.md; odaq_calibration_phase1_poc.md; odaq_qn_downmix_poc.md.
"""
    report=root/"final_mapping_report.md";report.write_text(md)
    (root/"final_mapping_report.html").write_text(render_html(md,root))
    assert sha(TABLE_PATH)==before
    receipt={"valid":True,"profile_fingerprint":profile["fingerprint"],"mapping_sha256":before,"common_quality_support":list(common),"default_targets":list(TARGETS),"sampling_status":"provisional_engineering_pilot_not_final_dataset_decision",
        "default_parameters":defaults,"generation_or_fitting_performed":False,"heldout_ratings_read":False,
        "files":{str(p.relative_to(root)):sha(p) for p in [report,root/"final_mapping_report.html",csvpath,*figures]}}
    (root/"final_mapping_report.verification.json").write_text(json.dumps(receipt,indent=2,sort_keys=True,allow_nan=False)+"\n")
    print(json.dumps({k:v for k,v in receipt.items() if k not in ("files","default_parameters")},indent=2))
    print("Reports:",report,root/"final_mapping_report.html",flush=True)

if __name__=="__main__":main()
