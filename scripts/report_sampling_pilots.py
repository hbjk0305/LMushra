"""Inspect saved v2 pilot bundles, export measured results and draw scientific figures.

No calibration fitting or ODAQ rating access. Run after the three CLI builds.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import signal
from deepmushra_data.config import file_checksum
from deepmushra_data.metadata import read_jsonl
from deepmushra_mapped.pipeline import validate_dataset
from deepmushra_mapped.collaboration import check_export
from deepmushra_mapped.mapping import load_table, estimate_quality
from deepmushra_mapped.profile import resolve_config
from deepmushra_mapped.sampling import sample_requests, knots

MODES=("odaq_knots","quality_target","hybrid")
ARTIFACTS=("LP","SH","UN","QN")
CATEGORIES=("Bad","Poor","Fair","Good","Excellent")
COLORS=("#2866a6","#d67c23","#25816e")


def table(headers,rows):
    return "| " + " | ".join(headers) + " |\n|" + "|".join(["---"]*len(headers)) + "|\n" + "".join("| " + " | ".join(map(str,row)) + " |\n" for row in rows)


def write_csv(path,rows):
    with path.open("w",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def render_html_reports(repo):
    """Reuse the existing offline SVG renderer with this report's fences/links."""
    spec=importlib.util.spec_from_file_location("sampling_report_renderer",repo/"scripts/report_final_mapping.py")
    renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
    for stem,title in (("synthetic_sampling_recipe","DeepMUSHRA sampling recipe"),("synthetic_sampling_pilot_report","DeepMUSHRA sampling pilot results")):
        md=repo/"docs"/(stem+".md")
        rendered=renderer.render_html(md.read_text().replace("```","~~~"),repo/"docs").replace("DeepMUSHRA final mapping decisions",title)
        rendered=re.sub(r"(?<!!)\[([^]\n]+)\]\(([^)\n]+)\)",r'<a href="\2">\1</a>',rendered)
        rendered=re.sub(r"`([^`\n]+)`",r"<code>\1</code>",rendered)
        md.with_suffix(".html").write_text(rendered)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo",type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument("--analysis-dir",type=Path,default=Path("outputs/multi_mode_sampling_v2/analysis-v3"))
    args=parser.parse_args();repo=args.repo.resolve();out=repo/args.analysis_dir
    out.mkdir(parents=True,exist_ok=False)
    figures=repo/"docs/figures/sampling_v2";figures.mkdir(parents=True,exist_ok=True)
    if any(figures.iterdir()):raise ValueError("Figure outputs exist; preserve the previous report before regenerating")
    examples=repo/"docs/examples/sampling_v2";examples.mkdir(parents=True,exist_ok=True)
    if any(examples.iterdir()):raise ValueError("Example outputs exist; preserve the previous report before regenerating")
    curve=load_table();all_rows=[];counts=[];bundles={};results={};source_splits={};max_errors=[];total_wavs=0
    for mode in MODES:
        bundle=repo/("data/sampling-v2-"+mode);dataset=bundle/"dataset"
        integrity=validate_dataset(dataset);assert integrity["valid"],integrity
        exported=check_export(bundle,repo);records=read_jsonl(dataset/"metadata.jsonl")
        summary=json.loads((dataset/"sampling_summary.json").read_text())
        profile=json.loads((bundle/"generator_profile.json").read_text())
        record_fingerprints={r["provenance"]["generator_profile_fingerprint"] for r in records}
        assert record_fingerprints=={profile["fingerprint"]},(mode,"profile mismatch")
        groups={r["source"]["source_id"] for r in records};assert len(groups)==8
        bundles[mode]=(bundle,dataset,records)
        error=[];max_peak=0.;max_reconstruction=0.;parameter_set=defaultdict(list);quality_count=Counter();noop=0
        for r in records:
            source=r["source"];group=source["source_id"]
            if group in source_splits:assert source_splits[group]==source["split"]
            source_splits[group]=source["split"]
            assert not source["is_functional_test_signal"]
            assert r["sampling_mode"]==mode and r["schema_version"]=="mapped-poc-v2"
            assert all(r["perceptual_annotation"][key] is None for key in ("human_mushra_score","perceived_severity","quality_category","audibility"))
            cal=r["calibration_estimate"]
            assert cal["human_mushra_score"] is None and cal["has_actual_human_ratings"] is False
            assert cal["mono_transfer_validated"] is False and cal["operator_transfer_validated"] is False
            audio={}
            for role,info in r["audio"].items():
                path=dataset/info["path"];x,sr=sf.read(path,always_2d=True);header=sf.info(path)
                assert file_checksum(path)==info["sha256"]
                assert sr==44100 and x.shape==(source["sample_count"],1) and header.subtype=="DOUBLE"
                assert np.isfinite(x).all() and abs(x).max()<.999
                max_peak=max(max_peak,float(abs(x).max()));audio[role]=x;total_wavs+=1
            assert np.array_equal(audio["residual"],audio["degraded"]-audio["reference"])
            prepared,rate=sf.read(bundle/"source_clips"/source["source_file"],always_2d=True)
            assert np.array_equal(audio["reference"],prepared*source["shared_source_gain"])
            max_reconstruction=max(max_reconstruction,float(abs(audio["reference"]+audio["residual"]-audio["degraded"]).max()))
            artifact=r["degradation"]["artifact_type"];assert artifact in ARTIFACTS
            sampling=r["sampling"];p=sampling["chosen_parameter"]
            if mode=="hybrid":
                for previous in parameter_set[(group,artifact)]:
                    tolerance=sampling["deduplication_policy"]
                    assert not np.isclose(previous,p,rtol=tolerance["rtol"],atol=tolerance["atol"])
            parameter_set[(group,artifact)].append(p)
            for origin in sampling["origins"]:
                if origin["component"]=="odaq_knots":
                    k=next(k for k in knots(artifact) if k["condition_id"]==origin["condition_id"])
                    assert origin["parameter"]==k["parameter"]
                    if artifact=="QN":assert origin["nominal_parameter"]!=p
                if origin["requested_quality_target"] is not None and cal["estimated_quality_mean"] is not None:
                    difference=cal["estimated_quality_mean"]-origin["requested_quality_target"]
                    assert difference==origin["target_forward_difference"] and abs(difference)<=1e-8
                    error.append(abs(difference));max_errors.append(abs(difference))
            value=cal["estimated_quality_mean"]
            if value is None:noop+=1
            else:
                quality_count[cal["estimated_quality_category"]]+=1
                expected=estimate_quality(artifact,p)["estimated_quality_mean"]
                assert abs(expected-value)<=1e-8
            all_rows.append({"mode":mode,"artifact":artifact,"component":sampling["component"],"sample_id":r["sample_id"],
                "source_id":group,"content_category":source["content_category"],"split":source["split"],
                "nominal_condition":sampling["nominal_condition_id"],"parameter":p,"parameter_unit":sampling["parameter_unit"],
                "requested_quality":sampling["requested_quality_target"],"estimated_quality_mean":value,
                "estimated_quality_category":cal["estimated_quality_category"],"target_forward_difference":sampling["target_forward_difference"],
                "measured_snr_db":r["measurements"].get("measured_snr_db"),"relative_residual_energy":r["measurements"]["relative_residual_energy"],
                "no_effect_quality_null":value is None,
                "normalized_spectral_magnitude_error":r["measurements"]["normalized_spectral_magnitude_error"],
                "affected_tf_ratio":r["measurements"]["affected_tf_ratio"],
                "lp_stopband_energy_change_db":r["measurements"].get("stopband_spectral_energy_change_db"),
                "sh_eligible_tf_selection_ratio":r["measurements"].get("eligible_tf_selection_ratio"),
                "un_peak_contrast_before_db":r["measurements"].get("reference_tonal_peak_mean_contrast_db_before"),
                "un_peak_contrast_after_db":r["measurements"].get("reference_tonal_peak_mean_contrast_db_after"),
                "qn_noise_reference_psd_cosine":r["measurements"].get("smoothed_noise_reference_psd_cosine")})
        for a in ARTIFACTS:
            subset=[r for r in records if r["degradation"]["artifact_type"]==a]
            nonnull=sum(r["calibration_estimate"]["estimated_quality_mean"] is not None for r in subset)
            counts.append({"mode":mode,"artifact":a,**summary["artifacts"][a],"quality_estimates":nonnull,"no_op_nulls":len(subset)-nonnull})
        assert exported["sample_count"]==len(records)-noop
        results[mode]={"valid":True,"generated":len(records),"exported":exported["sample_count"],"no_op_nulls":noop,
            "split_counts":exported["split_counts"],"source_groups":8,"sampling":summary,"category_counts":dict(quality_count),
            "max_target_forward_error":max(error,default=0.),"max_waveform_peak":max_peak,"max_residual_reconstruction_error":max_reconstruction,
            "generator_fingerprint":profile["fingerprint"]}
    assert len(source_splits)==8
    write_csv(out/"sample_measurements.csv",all_rows);write_csv(out/"counts.csv",counts)
    # Rejected explicit targets are analyzed with the sampler only, not generated or calibrated anew.
    explicit=resolve_config(repo/"configs/sampling_quality_explicit.yaml")
    unsupported=[]
    source={"source_id":"support-inspection","checksum":"0"*64}
    for a in ARTIFACTS:
        requests,report=sample_requests(explicit,a,source)
        accepted={r["value"]:r["parameter"] for r in requests}
        for target in explicit["sampling"]["quality_target"]["targets"]:
            unsupported.append({"artifact":a,"requested_quality":target,"supported":target in accepted,
                "parameter":accepted.get(target),"reason":"supported" if target in accepted else "quality_outside_calibration_support"})
    write_csv(out/"explicit_support.csv",unsupported)
    def save(fig,name):
        fig.tight_layout();fig.savefig(figures/(name+".png"),dpi=160);fig.savefig(figures/(name+".svg"));plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(11,7))
    for ax,a in zip(axes.flat,ARTIFACTS):
        for i,mode in enumerate(MODES):
            rows=[r for r in all_rows if r["mode"]==mode and r["artifact"]==a]
            vals=np.array([r["parameter"] for r in rows]);scale=.001 if a in ("LP","UN") else 100 if a=="SH" else 1
            jitter=np.linspace(-.18,.18,len(vals))
            ax.scatter(i+jitter,vals*scale,s=11,alpha=.65,color=COLORS[i])
        ax.set(xticks=range(3),xticklabels=["knots","quality","hybrid"],title=a,ylabel="kHz" if a in ("LP","UN") else "% selection probability" if a=="SH" else "waveform SNR (dB)")
        ax.grid(alpha=.2)
    fig.suptitle("Generator parameter distributions — processing facts")
    save(fig,"parameters")
    fig,axes=plt.subplots(2,2,figsize=(11,7))
    for ax,a in zip(axes.flat,ARTIFACTS):
        for i,mode in enumerate(MODES):
            values=[r["estimated_quality_mean"] for r in all_rows if r["mode"]==mode and r["artifact"]==a and r["estimated_quality_mean"] is not None]
            ax.hist(values,bins=np.arange(0,101,10),histtype="step",linewidth=1.8,label=mode,color=COLORS[i])
        ax.set(title=a,xlabel="Transferred reference-domain estimate (0–100)",ylabel="Generated examples",xlim=(0,100))
        ax.legend(fontsize=7);ax.grid(alpha=.2)
    fig.suptitle("Estimated quality priors — not human scores of synthetic audio")
    save(fig,"estimated_quality")
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for i,a in enumerate(ARTIFACTS):
        rows=[r for r in all_rows if r["artifact"]==a and r["requested_quality"] is not None and r["estimated_quality_mean"] is not None]
        axes[0].scatter([r["requested_quality"] for r in rows],[r["estimated_quality_mean"] for r in rows],s=12,alpha=.65,label=a)
        axes[1].scatter([r["requested_quality"] for r in rows],[abs(r["target_forward_difference"]) for r in rows],s=12,alpha=.65,label=a)
    axes[0].plot([0,100],[0,100],"k--",linewidth=1);axes[0].set(xlabel="Requested quality",ylabel="Forward estimate",xlim=(0,100),ylim=(0,100))
    axes[1].set(xlabel="Requested quality",ylabel="Absolute numerical error")
    axes[1].set_yscale("symlog",linthresh=1e-15)
    for ax in axes:ax.legend();ax.grid(alpha=.2)
    fig.suptitle("Inverse/forward consistency — same frozen curve in both directions")
    save(fig,"target_forward")
    fig,axes=plt.subplots(2,2,figsize=(12,8))
    categories=sorted({r["content_category"] for r in all_rows})
    for ax,a in zip(axes.flat,ARTIFACTS):
        for i,mode in enumerate(MODES):
            groups=[[r["relative_residual_energy"] for r in all_rows if r["artifact"]==a and r["mode"]==mode and r["content_category"]==category and r["relative_residual_energy"] is not None] for category in categories]
            values=[float(np.median(g)) if g else np.nan for g in groups]
            ax.plot(range(len(categories)),values,"o-",label=mode,alpha=.8,color=COLORS[i])
        ax.set(title=a,xticks=range(len(categories)),xticklabels=categories,ylabel="Median residual/reference energy")
        if a == "UN":ax.set_yscale("symlog",linthresh=1e-7)
        else:ax.ticklabel_format(axis="y",style="sci",scilimits=(-2,2))
        ax.set_ylim(bottom=0)
        ax.tick_params(axis="x",labelrotation=40,labelsize=7);ax.grid(alpha=.2);ax.legend(fontsize=7)
    fig.suptitle("Content dependence — objective differences, no audibility claim")
    save(fig,"content_distortion")
    bundle,dataset,records=bundles["odaq_knots"]
    chosen={}
    for a in ARTIFACTS:
        candidates=[r for r in records if r["degradation"]["artifact_type"]==a and r["sampling"]["nominal_condition_id"]=="Q3"]
        preferred={"LP":"mixture","SH":"percussion_stem","UN":"tonal_instrument","QN":"speech"}[a]
        r=next((r for r in candidates if r["source"]["content_category"]==preferred and r["calibration_estimate"]["estimated_quality_mean"] is not None),next((r for r in candidates if r["calibration_estimate"]["estimated_quality_mean"] is not None),candidates[0]));chosen[a]=r
        (examples/(a+".json")).write_text(json.dumps(r,indent=2,sort_keys=True,allow_nan=False)+"\n")
        fig,axes=plt.subplots(1,3,figsize=(13,3.5),sharey=True)
        image=None
        for ax,role in zip(axes,("reference","degraded","residual")):
            x,sr=sf.read(dataset/r["audio"][role]["path"])
            f,t,z=signal.stft(x,fs=sr,nperseg=1024,noverlap=768,boundary="zeros")
            db=20*np.log10(np.maximum(abs(z),1e-12));image=ax.pcolormesh(t,f/1000,db,shading="auto",vmin=-100,vmax=0,cmap="magma",rasterized=True)
            ax.set(title=role,xlabel="Time (s)",ylim=(0,22.05))
        axes[0].set_ylabel("Frequency (kHz)")
        fig.suptitle(a+" Q3: "+r["source"]["source_id"].split(":",1)[-1],fontsize=10)
        fig.subplots_adjust(right=.9,wspace=.12,top=.8,bottom=.18)
        cax=fig.add_axes([.92,.2,.014,.55]);fig.colorbar(image,cax=cax,label="STFT magnitude dB re 1 (shared scale)")
        fig.savefig(figures/("spectrogram_"+a+".png"),dpi=160);fig.savefig(figures/("spectrogram_"+a+".svg"));plt.close(fig)
    for mode in MODES:
        if mode=="odaq_knots":continue
        r=next(r for r in bundles[mode][2] if r["sampling"]["component"]=="quality_target" and r["calibration_estimate"]["estimated_quality_mean"] is not None)
        (examples/(mode+".json")).write_text(json.dumps(r,indent=2,sort_keys=True,allow_nan=False)+"\n")
    for split in ("train","valid","test"):
        rows=read_jsonl(bundles["hybrid"][0]/(split+".jsonl"))
        if rows:
            (examples/"training_row.json").write_text(json.dumps(rows[0],indent=2)+"\n");break
    category_rows=[]
    for mode in MODES:
        for a in ARTIFACTS:
            subset=[r for r in all_rows if r["mode"]==mode and r["artifact"]==a]
            c=Counter(r["estimated_quality_category"] for r in subset if r["estimated_quality_mean"] is not None)
            category_rows.append([mode,a,*[c[k] for k in CATEGORIES],sum(r["estimated_quality_mean"] is None for r in subset)])
    source_rows=[]
    entries=read_jsonl(repo/"data/multi_mode_sources_v2/sources.jsonl")
    for e in entries:
        info=sf.info(repo/"data/multi_mode_sources_v2"/e["source_file"])
        source_rows.append([e["source_id"],e["content_category"],info.samplerate,round(info.duration,6),e["source_provenance"].get("license","see source provenance")])
    testlog=(repo/"outputs/multi_mode_sampling_v2/tests-release.log").read_text()
    test_summary=re.findall(r"\d+ passed in [^\n]+",testlog)[-1]
    rowtable=table(["Mode","Generated","Exported","No-op nulls","Skipped","Deduplicated","Train/valid/test"],[[m,results[m]["generated"],results[m]["exported"],results[m]["no_op_nulls"],results[m]["sampling"]["skipped_count"],results[m]["sampling"]["deduplicated_count"],"/".join(str(results[m]["split_counts"][s]) for s in ("train","valid","test"))] for m in MODES])
    report="# Multi-mode sampling pilot: actual results\n\n"
    report+="Release 0.4.0 uses sampling profile `mapped-poc-v2` and unchanged operator profile `mapped-poc-1`. Completed experiments use the unchanged four DSP operators and frozen ODAQ-informed mappings. Only independent source recordings enter synthetic generation. No calibration refit, held-out listener-score access, PE/TM generation, LLM description stage, full dataset generation or model training was performed.\n\n"
    report+="## Observed counts\n\n"+rowtable+"\n"
    report+=table(["Mode","Artifact","Attempted","Supported before dedup","Retained audio","Quality estimates","No-op nulls"],[[r[k] for k in ("mode","artifact","attempted","supported_before_deduplication","retained","quality_estimates","no_op_nulls")] for r in counts])+"\n"
    report+="The three runs are alternative recipes: hybrid intentionally reuses the knot and continuous realizations from A/B on the same recording. Do not concatenate all three into one training set or count them as independent stimuli; cross-recipe fingerprints prevent normal team merging.\n\nSampling skips/deduplication and no-op export exclusions are separate. All five released conditions are supported for all four families, including QN through the empirical bridge. Continuous draws happened not to collide with knots within tolerance; dedicated exact-knot tests verify actual 10→5 deduplication while preserving both request origins.\n\n"
    report+="## Category coverage\n\n"+table(["Mode","Artifact",*CATEGORIES,"Null"],category_rows)+"\n"
    report+="These are categories of transferred reference-domain mean estimates, not observed synthetic-domain human judgments. No supported mean is Bad; missing classes are not filled by extrapolation.\n\n"
    report+="## Parameter and quality distributions\n\n![Processing parameters](figures/sampling_v2/parameters.png)\n\n![Transferred quality](figures/sampling_v2/estimated_quality.png)\n\n![Target-forward errors](figures/sampling_v2/target_forward.png)\n\n![Content dependence](figures/sampling_v2/content_distortion.png)\n\n"
    report+=f"Maximum absolute target/forward difference: **{max(max_errors,default=0.):.17g}**, below 1e-8. This is a same-curve numerical consistency check, not human validation. Null/no-effect samples do not participate in that equality test.\n\n"
    report+="The CSV also retains artifact-specific stopband attenuation (LP), eligible TF selection ratio (SH), selected-reference tonal contrast before/after (UN), and noise/reference PSD cosine plus saved SNR (QN). UN uses a nonnegative symlog axis to retain zero/no-op medians; the other energy axes are linear. Residual energy is a signal difference, not perceptual severity; causal LP phase can yield a large residual even when little high-frequency energy is removed.\n\n"
    report+="## Actual saved-file verification\n\n"
    report+=f"{sum(v['generated'] for v in results.values())} triplets inspected across all three pilots; every file is 44,100 Hz mono DOUBLE with matched sample count/grid and finite values. The saved residual equals saved degraded minus reference bit-exactly. Maximum reconstruction error is {max(v['max_residual_reconstruction_error'] for v in results.values()):.17g}; maximum peak is {max(v['max_waveform_peak'] for v in results.values()):.9g}, below .999. Prepared-reference lineage, audio/mask hashes, nominal condition units, inverse/forward fields, null human labels, both false transfer flags and all portable model paths were checked.\n\n"
    report+="Current source-group split assignments are shared across the three distinct versioned dataset IDs because their explicit recording_group_id is stable. No recording crosses splits. The stable eight-group assignment produced zero validation rows in every mode; this is a generator/export pilot, not a training-ready train/validation experiment. Enlarge the independent source pool rather than changing recording identities to force a split. An eight-source pilot is not evidence of population/content coverage.\n\n"
    report+="## Source recordings and restrictions\n\n"+table(["Source","Content proxy","Native input Hz","Excerpt seconds","License"],source_rows)+"\n"
    report+="Seven excerpts are four seconds; VCTK is 1.242375 seconds. Native rates are at least 44.1 kHz; no lower-rate source was upsampled. Header rate does not establish bandwidth or human-perceived cleanliness. Prior lossy ancestry is unknown for some references. These are real baseline recordings, not listening-certified transparent references. The two environmental clips were explicitly requested for this pilot, not a broader acquisition change. Existing source-ID exclusions were retained; no exhaustive identity screen is claimed. No new downloads occurred. Licenses and research-only/share-alike obligations must accompany any permitted redistribution; audio is ignored by Git.\n\n"
    report+="## Unsupported explicit requests\n\n"
    report+=table(["Artifact","Requested quality","Supported","Parameter","Decision"],[[r['artifact'],r['requested_quality'],r['supported'],r['parameter'],r['reason']] for r in unsupported])+"\n"
    report+="The support table itself did not generate audio or refit models. An additional one-source public-CLI explicit-target smoke check attempted 20 requests, generated 13, reported seven unsupported requests and exported 11 after two UN no-op exclusions. No target was clipped. Receipt: outputs/multi_mode_sampling_v2/explicit_smoke_verification.json. This diagnostic is separate from the three 640-triplet pilot totals. The explicit example config skips unsupported 10/30/50/70/90 requests and reports them. A run with no supported requests leaves a diagnostic bundle marked training_ready=false. No clipping to boundaries is performed.\n\n"
    report+="## Actual metadata and spectrogram examples\n\nQ3 examples use fixed content proxies: LP mixture, SH percussion, UN tonal instrument and QN speech, requiring a non-null transformation where available. This is illustration selection, not parameter tuning or human audibility selection.\n\n"
    for a,r in chosen.items():
        report+=f"### {a} Q3\n\nComplete JSON: [example](examples/sampling_v2/{a}.json). Sample `{r['sample_id']}`, source `{r['source']['source_id']}`. Actual audio paths relative to `data/sampling-v2-odaq_knots/dataset/`:\n\n"
        report+="\n".join("- "+role+": `"+r["audio"][role]["path"]+"`" for role in ("reference","degraded","residual"))+"\n\n"
        report+="Technical description: "+r["descriptions"]["technical"]+" Candidate perceptual description (unverified): "+r["descriptions"]["perceptual_candidate"]+"\n\n"
        report+=f"![{a} spectrogram](figures/sampling_v2/spectrogram_{a}.png)\n\n"
    report+="Complete [quality-target metadata](examples/sampling_v2/quality_target.json), [hybrid quality-component metadata](examples/sampling_v2/hybrid.json), and [actual training row](examples/sampling_v2/training_row.json) are also provided. Spectrogram panels use the same absolute magnitude scale, not independent normalization. They demonstrate signal modifications only.\n\n"
    report+="## Tests, reproducibility and release evidence\n\n"+test_summary+". Tests cover real waveforms, all modes, bounded inverse, explicit skips, QN label/proxy distinction, UN strength, plateau tie handling, hybrid deduplication, deterministic output, sidecar serialization, source leakage, true benchmark rejection and harmless output-label acceptance. V1 baseline waveforms/parameters/seeds/calibration agree bit-exactly before/after. New release fingerprints/sample IDs intentionally differ because the code release changed.\n\n"
    report+="Evidence remains on KNN in outputs/multi_mode_sampling_v2/: tests-release.log, legacy_release_compatibility.json, packaging_release_verification.json, the full per-example analysis CSVs and verification.json. A portable wheel loads v2 outside the checkout. The frozen mapping table, fitted models, bridge observations, listener split and DSP sources were not refit/modified. The actual-source subset repeat verifies 20/20/40 examples across A/B/C and 81/81/161 byte-identical audio, evidence and metadata files. See repeat-one-source/verification.json. Report SVGs use compact rasterized heatmaps with vector axes.\n\n"
    report+="## Mode recommendation and transfer limits\n\nUse **odaq_knots** for generator validation and the first controlled five-condition Phase 1 POC. Use **hybrid** for a follow-up POC and future scaling after independent perceptual calibration: it retains interpretable knots and adds supported-range coverage. Use **quality_target** for quality-axis ablations/exploration; drawing five targets does not mean drawing five validated categories.\n\n"
    report+="Exact processing strength, ODAQ stereo reference-domain estimate, unverified synthetic mono quality and actual human ratings are distinct. All actual synthetic human ratings remain null. LP edge/phase differences, SH mask semantics, UN detector/noise replacement and QN masking-versus-SNR mismatch remain unvalidated transfers. Three-listener QN conditional bands do not quantify population or mono/operator transfer uncertainty. Causal LP phase and centered STFT windows can introduce incidental temporal differences; the family holdout does not establish absence of every temporal cue. No-op prevalence and weak source bandwidth should be reviewed before scaling. Preserve the remaining listener panel for declared listener-held-out evaluation; this is ODAQ-informed, not a fully independent benchmark.\n\n"
    report+="Implementation, exact configuration options and all three CLI reproduction commands: [sampling recipe](synthetic_sampling_recipe.md). Completed data are data/sampling-v2-odaq_knots/, data/sampling-v2-quality_target/ and data/sampling-v2-hybrid/. Never overwrite prior output directories.\n"
    (repo/"docs/synthetic_sampling_pilot_report.md").write_text(report)
    verification={"valid":True,"modes":results,"triplets":sum(v['generated'] for v in results.values()),"waveform_role_checks":total_wavs,"source_split_map":source_splits,"max_target_forward_error":max(max_errors,default=0.),"test_summary":test_summary,"actual_synthetic_human_ratings":False,"held_out_ratings_used":False,"frozen_mapping_table_sha256":file_checksum(repo/"src/deepmushra_mapped/mapping_table.json")}
    (out/"verification.json").write_text(json.dumps(verification,indent=2,sort_keys=True,allow_nan=False)+"\n")
    render_html_reports(repo)
    print(json.dumps(verification,indent=2,sort_keys=True))


if __name__=="__main__":main()
