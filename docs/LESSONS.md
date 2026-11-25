# Lessons

## Why the model fails on ODAQ: the encoder keeps the information, but the LLM doesn't verbalize it (2026-11-25)

**Finding.** The frozen DAC encoder output (pre-quantization, pooled x4 as in training) already contains the degradation and severity information. The failure happens between the latents and the text: the projector, the training data and the training objective.

**Evidence** (`eval/odaq/latent_probe.py`, results in `eval/odaq/latent_probe/`). This measures the distance between reference and degraded latents directly, with no decoder and no LLM:

| | Ranking accuracy (significant pairs) | ρ within item |
|---|---:|---:|
| One listener vs. the other 25 | .933 | |
| DAC latent distance (95th percentile) | .950 | −0.88 |
| EnCodec latent distance (95th percentile) | .969 | −0.93 |
| 44.1 kHz log-mel distance | .926 | −0.82 |
| CLAP audio↔audio | .868 | −0.68 |
| Model's severity wording (DAC 30148) | .606 | −0.53 |

- **DAC registers high frequencies.** A 15 kHz low-pass (LP150) moves its latents 4.5× more than an inaudible 1-sample delay. The full-band information survives the strided 1D convolutions well enough to tell the conditions apart.
- **EnCodec (24 kHz) is blind above 12 kHz.** LP120 and LP150 sit at 0.12× and 0.00× of that floor. Prefer DAC.
- **A leave-one-item-out method classifier on DAC latents gets 75%** (chance .375). LP, SH and the identical pairs are near perfect and PE is 70%. TM and UN get confused with each other, but the log-mel confuses them too, so this is not specific to DAC.
- **These results match the earlier probe**, where a paired linear probe on DAC tokens reached 99.7% on the training degradations (LP/QN/SH/UN; `eval/odaq/README.md`).

**Probable causes** (on the text side, not the encoder):
1. **The training data never covers part of ODAQ.** Training uses only LP/QN/SH/UN. The model never names PE or TM, and it can't name a label it has never seen.
2. **There are no identical pairs in training.** The model claims a degradation on 16–20 of the 20 identical controls.
3. **The captions describe spectral holes (SH) as "high-frequency loss".** This teaches the "reduced clarity in higher frequencies" template the model overuses.
4. **The training objective (next-token prediction on free-text captions) doesn't force the projected tokens to carry the method and severity.** Longer training doesn't help: 16400 and 30148 barely differ, and the projector moved only 0.3–2%.

**What this does not show.** The DAC/EnCodec decoders do lose high-frequency detail when reconstructing, with or without RVQ (Hwangbo's spectrograms, `eval/codec_hf/`). That matters for reconstruction, not for discrimination. Latent distance is also an upper bound: it shows the information is available to the LLM, not that the LLM can explain it.

**How to apply.** Prioritize data fixes (PE/TM coverage, identical pairs, severity-explicit captions), a projector warm-up and an auxiliary method/severity loss over switching encoders. Treat a full-band AST-style encoder and the codec retrained without RVQ or the adversarial loss as research directions after Dec 1. Screen any new encoder with `latent_probe.py` before integrating it.
