# ODAQ reference and processed audio evaluation

Run the commands from the LMushra repository root. The supplied `requests.jsonl`
compares each reference with a processed version or with itself as a control.
It covers LP, PE, SH, TM, and UN, including the LP35 and LP70 anchors.

## 1. Run inference
```bash
bash eval/eval-baseline.sh dac \
  output/phase1_real_speech_music_v1-dac/v2-20261115-153620/checkpoint-6400 \
  eval/odaq/requests.jsonl
```

## 2. Export predictions to CSV

```bash
python eval/odaq/analyze.py \
  eval/odaq/calibrated_llm-dac--v1-20261116-160324--checkpoint-14200/predictions.jsonl
```


- `processing method` comes from the audio paths. Both low-pass anchors are labeled `LP`, and identical reference pairs are labeled `reference`.
- `actual severity level` follows the order in `CONDITIONS`. The first
  condition, Q1, is `1` (strongest), and the last, Q5, is `5` (weakest). LP35 is `0.5`, LP70 is `1.5`, and the reference control is `999`.
- `LP`, `PE`, `SH`, `TM`, and `UN` indicate which text patterns matched the response. Multiple columns can be `True` for the same response.

## 3. Listen to the pairs next to the model's descriptions

`listen_page.py` builds a local web page with one card per pair: reference and
degraded players side by side, the model's description, and its scores.

```bash
P=eval/odaq/calibrated_llm-dac--v1-20261116-160324--checkpoint-30148/predictions.jsonl

# Optional, for extra details on each card (run before building the page):
python eval/odaq/clap_score.py "$P"                        # -> predictions_clap.csv (CLAP scores)
python eval/odaq/compare_mushra.py "${P%.jsonl}.csv"       # -> predictions_mushra.csv (listener scores)

python eval/odaq/listen_page.py "$P"                       # -> predictions_listen/
python eval/odaq/listen_page.py --serve "${P%.jsonl}_listen" --port 8765
```

Use `$SWIFT_PYTHON` instead of `python` on enn. The server listens on
localhost only. When working over SSH, forward the port from your own machine
and open http://localhost:8765:

```bash
ssh -L 8765:localhost:8765 USER@enn.cs.illinois.edu
```

The page writes 16-bit PCM copies of the audio into `predictions_listen/audio/`.
The original ODAQ files are 24-bit WAVE_FORMAT_EXTENSIBLE, which many browsers
play as silence. Only one clip plays at a time.

Each card shows:
- the item, the condition (or "identical pair"), and the actual processing type
- **matched**: the types the description's wording matches (the regex cues
  from `analyze.py`). Green means the correct type was matched; on an identical
  pair, green means no processing was named.
- the actual and predicted severity, the mean listener MUSHRA score (0–100,
  higher is better), and the CLAP scores when those files exist

Header controls:

| Control | Use |
|---|---|
| Method | Show one processing type (LP, PE, SH, TM, UN or reference) |
| Detected | Pairs where the correct type was or was not matched |
| Severity | **high**: level 1 plus the LP35/LP70 anchors (60 pairs); **medium**: levels 2–3; **low**: levels 4–5; identical pairs |
| Search | Text in the description |
| Sort | File order, CLAP Δ, CLAP reference↔degraded similarity, or listener MUSHRA (worst first) |

To compare the description with what you hear, a useful order is:
1. Severity **high** and Sort **listener MUSHRA, worst first**: degradations
   everyone hears. Is the type named, and is the wording strong enough?
2. Method **reference** (the identical pairs): does the model claim a difference that isn't there?
3. Method **SH**, **TM** or **UN** with Detected **not matched**: which
   wording does it use in place of the right type?

A page for another checkpoint or decoding setting works the same way. Point
`listen_page.py` at, for example, `predictions_sample_t07.jsonl` (the sweep
outputs from `decoding_sweep.sh`). Each page is written next to its JSONL.

## Note

Many responses say that the processed audio loses high-frequency detail. One possible reason is that the training captions often describe spectral holes (SH) as a loss of high-frequency detail, too. The model also sometimes says the audio is slightly degraded when both inputs are the same reference clip. This suggests that its answers may not be well grounded in the audio.

One idea is to add a metadata classifier that reads the audio tokens after they pass through the projector. I would use the classifier's loss as an auxiliary loss alongside the main training loss to help the model learn audio features that distinguish different types of processing.


# Linear probes on frozen pre-LLM audio tokens (DAC checkpoint-14600 and EnCodec checkpoint-9400)

Balanced sample: 4096 train / 1024 valid from separate published metadata splits.

# Predict type of the processing

target classes: LP, QN, SH, UN

Representation
* degraded: degraded feature -> dim=4096
* paired: (reference, degraded, reference-degraded) -> dim=4096*3
 
| Model | Representation | Probe input | Clip accuracy | Clip macro-F1 | Token accuracy |
|---|---|---|---:|---:|---:|
| dac | mean | degraded | 78.61% | 0.7827 | - |
| dac | mean | paired | 99.71% | 0.9971 | - |
| dac | tokens | degraded | 73.93% | 0.7375 | 61.74% |
| dac | tokens | paired | 96.88% | 0.9691 | 88.34% |
| encodec | mean | degraded | 54.98% | 0.5387 | 54.98% |
| encodec | mean | paired | 78.71% | 0.7886 | 78.71% |
| encodec | tokens | degraded | 42.09% | 0.4167 | 36.57% |
| encodec | tokens | paired | 66.31% | 0.6680 | 52.82% |

Regression summary (`mean/paired`, validation; MAE in original units):

| Parameter | Min | Max | Train-mean MAE | DAC MAE | EnCodec MAE |
|---|---:|---:|---:|---:|---:|
| LP.cutoff_hz | 5000 | 15000 | 2518.77 | 996.325 | 2112.73 |
| QN.snr_db | 2.22851 | 23.206 | 5.9752 | 3.72166 | 5.79936 |
| SH.hole_probability | 0.1 | 0.7 | 0.162343 | 0.0391046 | 0.0955689 |
| UN.crossover_hz | 3000 | 10500 | 1984.66 | 2407.31 | 1967.25 |

Min/Max are the observed probe-training ranges from schema.json, used for target normalization; validation values are not clipped.

`mean` probes read mean-pooled full token sequences. `tokens` probes read 8 fixed, evenly spaced individual tokens per clip; clip results average their logits/predictions.å