"""Mapped POC algorithms; legacy algorithm1.1 is never changed."""
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy import signal
from deepmushra_data.degradations import apply_effect, EffectResult
from deepmushra_data.stft import STFTConfig, analyze, synthesize, validate_audio
from .mapping import estimate_quality, parameter_for_quality

VERSION="mapped-poc-1"

def local_qn(audio,snr_db,seed,config):
    """Frame-local spectral coloring, followed by causal activity gating and exact SNR."""
    sr=44100
    f,t,z=analyze(audio,sr,config)
    sigma=500/(sr/config.n_fft)
    envelope=np.sqrt(gaussian_filter1d(np.abs(z)**2,sigma,axis=1,mode="nearest"))
    rng=np.random.default_rng(seed)
    _,_,nz=analyze(rng.standard_normal(audio.shape),sr,config)
    noise_envelope=np.sqrt(gaussian_filter1d(np.abs(nz)**2,sigma,axis=1,mode="nearest"))
    shaped=envelope*nz/np.maximum(noise_envelope,1e-15)
    shaped[:,0]=shaped[:,0].real;shaped[:,-1]=shaped[:,-1].real
    noise=synthesize(shaped,sr,len(audio),config)
    # Past-only activity gate enforces zero before the first onset and in exact silent gaps.
    past_power=signal.lfilter([1-np.exp(-1/(sr*.005))],[1,-np.exp(-1/(sr*.005))],audio**2,axis=0)
    active=(past_power>0)&(audio!=0)
    noise*=active
    target=float(np.sum(audio**2))*10**(-snr_db/10)
    actual=float(np.sum(noise**2))
    if target and actual:noise*=np.sqrt(target/actual)
    else:noise[:]=0
    _,_,noise_z=analyze(noise,sr,config)
    floor=max(float(np.abs(noise_z).max())*1e-4,1e-15)
    arrays={"selected_mask":np.abs(noise_z)>floor,"frequencies_hz":f,"times_s":t,
            "added_noise":noise,"reference_local_envelope":envelope,"causal_activity_gate":active}
    evidence={"algorithm_version":VERSION,"operator":"local_spectral_additive_noise_v1","stft":config.metadata(),
        "smoothing_hz":500,"mask_kind":"derived_added_noise_support_not_psychoacoustic_mask",
        "phase_policy":"reference phase unchanged; centered local noise synthesis with sample activity gating",
        "activity_gate":"past RMS positive and reference sample nonzero; no backward temporal masking",
        "psychoacoustic_masking_model":None,"no_tonal_replacement":True,
        "perceptual_equivalence_to_odaq":"approximate_family_only","transformation_applied":bool(np.any(noise))}
    return EffectResult(audio+noise,{"snr_db":float(snr_db),"smoothing_hz":500,"activity_policy":"exact_sample_support"},evidence,arrays)

def generate_effect(artifact,audio,seed,quality=None,parameter=None,sample_rate=44100):
    audio=validate_audio(audio)
    if sample_rate!=44100:raise ValueError("Mapped POC requires 44100 Hz")
    if audio.shape[1]!=1:raise ValueError("Mapped POC requires 44.1 kHz mono source preparation")
    if (quality is None)==(parameter is None):raise ValueError("Supply quality or parameter, not both")
    p=parameter_for_quality(artifact,quality) if quality is not None else parameter
    annotation=estimate_quality(artifact,p)
    if annotation["support_status"]!="inside":raise ValueError("Parameter outside mapping support")
    config=STFTConfig(2048,512)
    if artifact=="LP":
        params={"cutoff_hz":p,"filter_design":"butterworth","transition_hz":1500,"passband_ripple_db":.5,"attenuation_db":60}
    elif artifact=="SH":
        params={"hole_probability":p,"start_hz":4000,"band_width_hz":500,"run_frames":4,"attenuation_db":"zero"}
    elif artifact=="UN":
        params={"crossover_hz":p,"strength":1.,"smoothing_hz":500,"tonal_threshold_db":12.,"channel_mode":"linked"}
    else:
        result=local_qn(audio,p,seed,config)
        return result, _finalize_annotation(audio,result,annotation)
    result=apply_effect(artifact,audio,44100,params,seed,config)
    result.evidence={**result.evidence,"mapped_profile_version":VERSION,"operator_transfer":"approximate_family"}
    return result, _finalize_annotation(audio,result,annotation)


def _finalize_annotation(audio,result,annotation):
    delta=float(np.sum((result.audio-audio)**2))
    reference=float(np.sum(audio**2))
    if not result.evidence["transformation_applied"] or not reference or delta<reference*1e-20:
        return {**annotation,"status":"no_effect_quality_not_estimated","estimated_quality_mean":None,
                "estimated_quality_category":None,"estimated_quality_loss_proxy":None,
                "conditional_reference_listener_weight_95_band":None}
    return annotation
