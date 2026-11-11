# Design decisions and research questions

## Initial engineering decisions

1. **Require at least 44.1 kHz.** Music artifacts can lie above the bandwidth of
   speech-oriented frontends. Accept 44.1/48 kHz by default and preserve native
   rate. Neither upsampling nor a high sample-rate header proves that high-band
   information exists. Audit actual bandwidth when selecting research sources.
2. **Keep this workstream independent.** The repository originally contained only
   an uninitialized `ms-swift` submodule. A standalone package makes DSP and
   metadata testable without model weights, GPU software, or assumptions about
   another team member's training interface. The submodule is unchanged.
3. **Use one declared STFT convention.** Explicit padding and channel handling
   avoid silent short-input window changes and transpose errors. Identity-path
   tests include very short signals, boundaries, odd lengths, and both rates.
4. **Use causal LP filtering by default.** Zero-phase or group-delay-compensated
   sharp filtering can introduce pre-ringing. Causal SOS filters avoid deliberate
   look-ahead, but have frequency-dependent delay, start-up behavior, and possible
   ringing. Residuals therefore include phase distortion. We record that policy
   rather than claiming a perfectly isolated magnitude-only artifact.
5. **Record realized SH selections.** A requested probability is not realized
   coverage. Nonoverlapping Bernoulli run blocks are transparent and reproducible.
   They do not implement a psychoacoustic bit allocator or lowest-SMR selection.
6. **Shape UN with a power envelope.** Smoothed amplitude and smoothed power
   behave differently when a narrow line becomes distributed noise. An early
   amplitude-envelope implementation failed the envelope test. The RMS power
   envelope gives an explicit energy interpretation and a measured post-ISTFT
   envelope error. Normalization is per selected band/frame/channel, not a claim
   of exact waveform energy conservation.
7. **Treat channel linking as a policy, not spatial invariance.** SH shares
   selections across channels. UN shares selections and defaults to shared noise;
   this can change stereo coherence or width. Independent noise can also change
   spatial perception. No exact preservation of spatial cues is claimed.
8. **Save float64 audio and recompute the residual from disk.** This avoids PCM
   quantization or clipping as accidental artifacts and allows tight consistency
   checks. The WAV PEAK timestamp is canonicalized for deterministic checksums.
   Any future encoding/export stage must regenerate and revalidate residuals.
9. **Separate facts from perception.** Parameter tiers, mask coverage, and signal
   energy are objective processing quantities. Audibility, perceived severity,
   and quality category need independent evidence. Candidate language stays
   conditional and unverified; no MUSHRA labels or LLM paraphrases are generated.
10. **Use source groups before examples.** Hash ordering and whole-group allocation
    keep all variants together. File aliases connect transitively. Related
    excerpts and stems need a common manifest source ID; automatic filename
    guessing would create misleading leakage guarantees.
11. **Keep PE and TM held out.** They are neither selectable operators nor training
    example classes in this pipeline. Avoid adding pre-echo or noise-to-tone
    transformations through other augmentation libraries. The claim is absence
    of intentional project augmentation, not proof of absence from a pretrained
    model or of every incidental temporal side effect.
12. **Publish only validated small runs.** Fail fast on invalid sources, recipes,
    or peaks; do not silently skip examples and change the intended distribution.
    Staging avoids a successful-looking partial manifest. Large-scale execution,
    retry/resume, distributed generation, and cloud storage are not implemented.

## ODAQ relationship

The original ODAQ paper defines LP, SH, UN, TM, PE, and dialogue-enhancement
conditions. It describes UN as replacing tonal components with spectrally
enveloped noise and SH as controlled zero quantization of spectral regions.
Those definitions motivate our operators, but do not establish algorithmic
equivalence. See the [original ODAQ paper](https://arxiv.org/abs/2401.00197) and
[expanded analysis](https://arxiv.org/abs/2504.00742).

ODAQ is now a broader collection, including spatial and real codec conditions;
the [official repository](https://github.com/Fraunhofer-IIS/ODAQ) and
[collection paper](https://arxiv.org/abs/2610.37959) describe those releases.
This initial generator does not reproduce or evaluate the whole collection.
ODAQ's scalar listening scores do not supply word-level description ground
truth or exact audible event boundaries for our synthetic masks.

## Questions for the research team

- **Source material and coverage:** choose licensed clean music, solo instruments,
  percussion, speech, and mixed scenes. Audit native bandwidth, existing codec
  damage, dynamic range, and recording provenance. Exclude ODAQ sources and
  related productions from synthetic train/development data. The functional
  pilot is not a substitute for this corpus selection.
- **Music versus broader audio:** keep explicit content categories and stratify
  future results by content. Natural noise or percussion can be legitimate source
  content; it is not automatically a degradation. A numerical parameter can have
  different consequences on tonal music, dense mixtures, and speech. Do not
  enforce a perceptual label solely to balance a parameter grid.
- **Audibility and quality supervision:** commission an independent synthetic
  listening pilot before treating text candidates as perceptual ground truth.
  Validate subtle and no-op cases as well as obvious examples. Keep human labels
  and provenance separate from synthetic facts. Select category calibration on
  development material without fitting the final ODAQ test scores.
- **Temporal side effects:** decide whether causal LP phase changes and STFT
  boundary effects are acceptable or need a future isolation study. Holding PE
  out does not make every LP/SH/UN waveform free of transient smearing. Do not
  weaken this distinction in paper claims.
- **Envelope and stereo acceptance:** set research-level tolerances for UN
  envelope deviation and spatial side effects after listening. Current tests
  establish behavior on analytical fixtures, not perceptual equivalence to ODAQ
  UN or generative codec artifacts.
- **Model observability:** the model team must retain full-band/stereo evidence
  if the target differences depend on it. Standard Qwen2-Audio preprocessing uses
  [16 kHz input](https://huggingface.co/Qwen/Qwen2-Audio-7B-Instruct/blob/main/preprocessor_config.json),
  so a direct 16 kHz conversion discards the 10–16 kHz differences in this plan.
  Preserve masters here and explicitly specify a downstream encoder/export
  policy rather than changing this dataset to match an unsuitable frontend.
- **Description evaluation:** evaluate artifact facts, numeric grounding, and
  hallucinated claims separately from paraphrase wording. BLEU against a
  metadata-derived template does not establish human perceptual correctness.
- **Reconstruction objective:** compact text describing a random-noise artifact
  cannot generally identify its exact random waveform. A residual decoder needs
  an explicitly chosen stochastic/distributional objective or additional
  conditioning; metadata seeds are reproduction tools, not presumed perceptual
  information available in natural language.

Future LLM paraphrasing, human-test tooling, score prediction, full ODAQ
evaluation, training adapters, real codec runs, and large-scale generation remain
separate workstreams. No external corpora or model weights are downloaded by
the demo command.


## Phase 1 decisions (2026-11-02)

- Add QN-like noise in the time domain with an unchanged reference component,
  causal coloring FIR and causal RMS envelope. Offline long-term color avoids
  a claim of online masking or exact ODAQ NMR replication. A short FIR limits
  spectral resolution; exact SNR is distinct from exact spectral matching.
- Pilot uses eight native 44.1 kHz stereo MedleyDB recordings from MUSDB18-HQ,
  two content proxies each (other/drums/vocals/mixture), not ODAQ assets. Retain
  NC/share-alike provenance. Other stems are not verified isolated instruments.
- Hold crossover, band width, run length and smoothing fixed while sweeping one
  parameter per effect. Different variants have independent deterministic seeds;
  this pilot is not an estimate of stochastic variability or perceptual severity.
- Keep the existing causal LP and centered SH/UN implementations visible. Measure
  phase delay, pre-onset spreading, envelope error and stereo correlation rather
  than hiding incidental artifacts. No stereo-width operator is approved.
- Repeat whole pilot generation for byte-level audio/evidence/metadata checks.
  Objective probes and source-content plots are not human quality annotations.
- No full-scale generation, ODAQ calibration, model training or listening-test
  infrastructure was implemented. Human severity calibration remains proposed.
