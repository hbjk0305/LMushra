# ODAQ results: DAC v1-20261116-160324, checkpoint-16400 (compared with checkpoint-14200)

Run: `result/infer_dac/v1-20261116-160324-checkpoint-16400-20261120-062537.{jsonl,csv,_clap.csv,_listen/}`
on `requests.local.jsonl` (the same 160 pairs as `requests.jsonl`, with `/mnt/data2/hwangbo5/...` audio paths).
Method mentions come from the regex cues in `analyze.py`, not from human labels.

## Processing type and severity

| | 14200 | 16400 |
|---|---:|---:|
| Mentions the correct processing method | 45.7% | 45.7% |
| Mentions **only** the correct method | 33.6% | 43.6% |
| Mentions no method at all | 22.5% | 13.8% |
| Distinct responses (out of 160) | 71 | 119 |
| Numeric severity found in the response | 40 | 52 |
| Spearman correlation, actual vs. predicted severity (processed pairs) | −0.11 | −0.01 |
| Identical-reference controls that claim a degradation | 20/20 | 16/20 |

Fraction of responses for each actual processing type (rows) that match each method's cues (columns), checkpoint 16400:

| actual \ mentioned | LP | PE | SH | TM | UN |
|---|---:|---:|---:|---:|---:|
| LP (n=60) | **1.00** | 0 | .05 | 0 | 0 |
| PE (n=20) | .20 | **0** | .15 | 0 | .10 |
| SH (n=20) | .85 | 0 | **0** | 0 | .05 |
| TM (n=20) | .50 | 0 | .60 | **0** | .35 |
| UN (n=20) | .50 | 0 | .05 | 0 | **.20** |
| reference (n=20) | .25 | 0 | .20 | 0 | .45 |

- Responses are more varied and less hedged than at checkpoint 14200, but they are still biased toward "high-frequency loss". The model never names PE or TM.
- The predicted severity tells us nothing about the actual severity. Numeric answers are almost always "2"; otherwise responses use vague words ("subtle", "noticeable").
- None of the identical-reference responses says the clips are identical. Example: "subtle reduction in tonal clarity and a slight increase in background noise…"
- The 60% SH match on TM pairs may be a false positive from the regex. Check it by hand.

## CLAP scores (`clap_score.py`, `laion/larger_clap_general`)

Columns: `clap_text_degraded` = cos(text, degraded audio), the usual CLAPScore;
`clap_text_reference` = cos(text, reference audio), the baseline;
`clap_audio_ref_deg` = cos(reference audio, degraded audio). Audio longer than 10 s is split into 10 s windows, and their embeddings are averaged.

| method | text→degraded | text→reference | Δ (deg − ref) | Δ > 0 | audio ref↔deg |
|---|---:|---:|---:|---:|---:|
| LP | 0.046 | 0.009 | +0.036 | 73% | 0.777 |
| PE | 0.022 | 0.016 | +0.007 | 60% | 0.896 |
| SH | 0.070 | 0.034 | +0.037 | 70% | 0.791 |
| TM | 0.028 | 0.020 | +0.008 | 55% | 0.972 |
| UN | 0.001 | 0.017 | −0.016 | 35% | 0.977 |
| reference | 0.001 | 0.001 | 0 | — | 1.000 |

Findings:
- **Text–audio scores are near zero and mostly track the clip.** The text→degraded score ranges from −0.17 to 0.21 (mean 0.03). Its rank correlation with text→reference is 0.83. The clip explains 32% of its variance and the processing method only 6%. The scores range from 11_guitar (−0.08) to 39_clapping (+0.12). CLAP general was trained on content captions ("a guitar playing"), not on descriptions of processing differences, so it barely responds to the wording we care about.
- **Δ is the more useful number.** Subtracting the reference score removes most of the clip effect: the method explains 18% of Δ's variance, against 6% for the raw score. Δ is positive for LP and SH, where the text mentions high-frequency loss and the degraded audio really is band-limited. It is about 0 for PE and TM and negative for UN. Overall only 55% of pairs have Δ > 0, so CLAP gives weak evidence that the text refers to the degraded clip specifically.
- **Audio↔audio similarity tracks severity within each method** (Spearman 0.34 for LP, 0.42 PE, 0.62 SH, 0.55 TM, 0.09 UN). It is low for LP and SH (about 0.78) and close to 1 for TM and UN (about 0.97), so CLAP itself hardly hears TM and UN. That fits the model rarely describing them correctly.
- **CLAP doesn't see LP150.** Its similarity is exactly 1.000, most likely because CLAP's mel front end stops around 14 kHz, below the 15 kHz cutoff. Don't read CLAP scores for content above about 14 kHz.
- **Identical controls score Δ = 0 by construction**, so CLAP can't penalize the false "degraded" claims on them. Use the text classification above for those.

### CLAP: checkpoint 14200 vs. 16400

The 14200 scores (`result/infer_dac/v1-20261116-160324-checkpoint-14200_clap.csv`) come from a JSONL rebuilt from
`calibrated_llm-dac--...-checkpoint-14200/predictions.csv`, with the audio paths rewritten to `/mnt/data2/hwangbo5/...`.
The pairs are the same as for 16400, so the audio↔audio column is identical; only the text scores differ.

Processed pairs only (n=140; the "55% Δ > 0" above also counts the 20 controls, which are always 0):

| method | Δ 14200 | Δ > 0 14200 | Δ 16400 | Δ > 0 16400 |
|---|---:|---:|---:|---:|
| LP | +0.054 | 83% | +0.036 | 73% |
| PE | +0.010 | 55% | +0.007 | 60% |
| SH | +0.044 | 60% | +0.037 | 70% |
| TM | +0.001 | 45% | +0.008 | 55% |
| UN | −0.011 | 25% | −0.016 | 35% |
| all processed | +0.030 | 62% | +0.021 | 63% |

- Mean Δ is slightly *lower* at checkpoint 16400. Compared pair by pair, it drops by 0.009, and only 35% of pairs improve (Wilcoxon p = 0.003). The drop is mostly on LP: 14200's repeated "high-frequency loss" template matched band-limited audio well.
- For PE, SH, TM and UN, Δ is above 0 a little more often at 16400 (by 10 points each). This fits the more varied responses, but the effects are small.
- So CLAP doesn't support calling 16400 an improvement. The gain in the text classification (34% → 44% naming only the correct method) is not reflected in CLAP.

In short, CLAP is useful here as an audio-only sanity check of how far each degraded clip is from its reference. It is a weak signal for whether a description is correct, and Δ is better than the raw CLAPScore for that.

## Comparison with ODAQ listener ratings (MUSHRA)

`compare_mushra.py` joins each pair to `ODAQ_results.csv` (26 listeners per pair, scores 0–100, higher means better quality) on (item, condition), then correlates the ratings with three things: a severity score from the response text, the CLAP Δ, and the CLAP audio↔audio similarity.
`word_severity` is the explicit "level N" in the response if one is given. Otherwise it is the average of severity words mapped to a 1–5 scale (minimal = 1 … severe = 5; see `WORD_LEVEL`).
Per-pair output: `result/infer_dac/*_mushra.csv`.

For reference, the designed severity level alone gives Spearman 0.84 with MUSHRA.

Spearman with mean MUSHRA, processed pairs (n=140). A useful severity score should be **negative** and audio similarity **positive**:

| | 14200 | 16400 |
|---|---:|---:|
| word_severity, pooled | −0.35 (p<.001) | −0.27 (p=.001) |
| word_severity, **within method** (ranks taken inside each method, then pooled) | **−0.29 (p=.001)** | −0.06 (p=.50) |
| CLAP Δ, pooled | −0.32 | −0.24 |
| CLAP Δ, within method | −0.11 (p=.18) | −0.06 (p=.45) |
| CLAP audio ref↔deg, pooled / within method | +0.68 / +0.60 | same (it uses audio only) |

Within each method, the word_severity correlation at 14200 is PE −0.58, SH −0.44, LP −0.24, TM −0.04, UN +0.17. At 16400 it is LP −0.25 and PE −0.21, with SH, TM and UN *positive* (+0.22 to +0.32).

- **Checkpoint 14200's wording tracked how bad listeners found a pair; 16400's mostly doesn't.** Within a method, 14200 used stronger words for pairs rated worse (−0.29). At 16400 this is gone (−0.06): its responses got more varied, but the variation doesn't follow perceived quality. This is the clearest regression found so far.
- **Both checkpoints use strong words for identical pairs.** Those pairs get MUSHRA 98.7, but the word severity is about the same as for processed pairs (14200: 2.24 vs 2.44; 16400: 2.54 vs 2.49).
- **The pooled correlations mostly reflect differences between methods.** LP and SH get the lowest ratings (about 39) and the most "loss"-type wording. Use the within-method rows.
- **"Correct method named" vs. MUSHRA** (38.7 named vs 54.4 missed) is also mostly a between-method effect: LP is always named and rated low. The only real within-method contrast is UN: the 4 UN pairs where it named UN were rated 30–33, against about 70 for the 16 misses (p≈.01). So it names UN only when the noise is easy to hear.
- **CLAP audio↔audio similarity follows the listeners closely** (+0.60 within method, +0.97 on PE). The model's descriptions carry much less of this information than a generic audio embedding does. This fits the linear-probe result that the information is present before the LLM.
- **CLAP Δ doesn't follow the ratings within a method**, so it isn't a useful measure of perceived quality either.
