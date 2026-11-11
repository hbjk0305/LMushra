"""Pure metadata-to-text interface; candidates never become human annotations."""

TEMPLATE_VERSION = "1.1"


def describe(artifact, parameters, evidence):
    attributes = {"artifact": artifact, "content_attribution": "unknown",
                  "audibility": "unknown", "perceived_severity": "unknown"}
    if not evidence["transformation_applied"]:
        technical = "No transformation was applied; the processed waveform is identical to the reference."
        candidate = "No difference is expected from this processing operation; this has not been verified by listening."
    elif artifact == "LP":
        cutoff = parameters["cutoff_hz"] / 1000
        technical = (f"Low-pass filtering uses a {cutoff:g} kHz passband edge and a "
                     f"{parameters['transition_hz'] / 1000:g} kHz transition to the stopband. "
                     "High-frequency content is attenuated; causal filtering also changes phase.")
        candidate = "The processed audio may sound less bright or detailed in the high frequencies."
    elif artifact == "SH":
        attenuation = parameters["attenuation_db"]
        action = "removed" if attenuation == "zero" else f"attenuated by {attenuation:g} dB"
        technical = (f"Selected STFT regions above {parameters['start_hz'] / 1000:g} kHz are {action}, "
                     f"using {parameters['band_width_hz']:g} Hz bands and {parameters['run_frames']}-frame selection blocks. "
                     "These are processing-grid selections, not verified audible events.")
        candidate = "The processed audio may have intermittent gaps or fluctuations in high-frequency detail."
    elif artifact == "UN":
        technical = (f"Selected tonal bands above {parameters['crossover_hz'] / 1000:g} kHz are blended "
                     f"with envelope-shaped noise at replacement strength {parameters['strength']:g}. "
                     "Selected-band STFT energy is normalized before waveform reconstruction.")
        candidate = "High-frequency tonal detail may sound noisier or less clearly defined."
    elif artifact == "QN":
        technical = (f"Signal-shaped noise is added at a {parameters['snr_db']:g} dB reference-to-noise "
                     f"energy ratio per channel, using {parameters['smoothing_hz']:g} Hz spectral smoothing "
                     f"and a causal {parameters['envelope_ms']:g} ms RMS envelope. "
                     "The original waveform is retained; this is not a psychoacoustic NMR simulation.")
        candidate = "Additional background noise or hiss may be present, following the signal's spectral color."
    else:
        raise ValueError(f"No description template for {artifact}")
    return {"template_version": TEMPLATE_VERSION, "technical": technical,
            "technical_status": "processing_facts", "perceptual_candidate": candidate,
            "perceptual_candidate_status": "unverified", "attributes": attributes}
