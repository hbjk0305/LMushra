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

## Note

Many responses say that the processed audio loses high-frequency detail. One possible reason is that the training captions often describe spectral holes (SH) as a loss of high-frequency detail, too. The model also sometimes says the audio is slightly degraded when both inputs are the same reference clip. This suggests that its answers may not be well grounded in the audio.

One idea is to add a metadata classifier that reads the audio tokens after they pass through the projector. I would use the classifier's loss as an auxiliary loss alongside the main training loss to help the model learn audio features that distinguish different types of processing.
