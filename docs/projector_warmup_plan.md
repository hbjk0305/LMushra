# Projector / LLM Adaptation Plan (DAC first, then EnCodec)

This note captures the training scheme for fixing early SFT where the model
looks **unstable** or **ignores audio** after swapping Whisper for DAC/EnCodec.
Run these experiments before (or as a gate before) full SFT on the final
reference/degraded quality-description dataset.

Related code:

- Projector definition: [`lmushra/dac_audio.py`](../lmushra/dac_audio.py) (`DacProjector`)
- DAC plugin: [`scripts/dac_plugin.py`](../scripts/dac_plugin.py)
- EnCodec plugin: [`scripts/encodec_plugin.py`](../scripts/encodec_plugin.py)
- NISQA caption prep: [`scripts/prepare_nisqa_pretrain.py`](../scripts/prepare_nisqa_pretrain.py)
- Current joint SFT (projector + LoRA): [`scripts/train_dac_dummy_100.sh`](../scripts/train_dac_dummy_100.sh), [`scripts/train_nisqa_pretrain.sh`](../scripts/train_nisqa_pretrain.sh) / [`scripts/train_calibrated_llm_pretrain.sh`](../scripts/train_calibrated_llm_pretrain.sh)

## Problem diagnosis

Current DAC/EnCodec training typically does **all of the following at once**:

1. Replace Whisper `audio_tower` + pretrained `multi_modal_projector` with a
   frozen codec encoder + **randomly initialized** `DacProjector`
2. Train `multi_modal_projector` and LLM LoRA **together**
3. Use a relatively high LR (e.g. `1e-4` in the dummy script)

That lets the LLM adapt faster than the projector becomes meaningful, so LoRA
learns to answer from the **text prompt** and ignore audio slots.

Token-rate mismatch vs Whisper (~25 Hz) is real but **secondary**:

| Front-end | Approx tokens/s after pool |
| --- | --- |
| Whisper (Qwen2-Audio) | ~25 |
| DAC, `pool_size=4` | ~21.5 (`44100/512/4`) |
| EnCodec, `pool_size=4` | ~18.75 (`24000/320/4`) |

Pooling is `F.avg_pool1d(..., kernel=4, stride=4)` on codec latents in
`DacAudioTower.forward` **before** the projector. The template expands one
`<audio>` placeholder per pooled frame via `hop_length * pool_size`.

Do **not** “fix” rate by interpolating LLM positional embeddings. Prefer
matching feature timeline density (pool choice or latent resample to
`T ≈ duration * 25`). For EnCodec, `pool_size=3` gives exactly 25 Hz. Address
rate after projector warmup works.

## Goal of warmup

**Projector-only CE warmup** = standard next-token cross-entropy on assistant
captions, but with:

- DAC/EnCodec encoder **frozen**
- LLM **fully frozen** (no LoRA)
- Only `multi_modal_projector` trainable

This is LLaVA-style Stage-1 alignment: make codec latents land in a usable LLM
embedding space **before** the LLM can learn to ignore them.

Whisper-space distillation (MSE/cosine to frozen Whisper+projector outputs) is
**optional and secondary**. It can help initialization for generic speech
understanding but may erase codec cues useful for quality/artifacts if used as
the main loss. Prefer caption CE; use weak annealed distillation only if Stage 1
fails.

## Dataset

### Use for warmup (Stage 1)

**NISQA published quality captions**, prepared into Swift JSONL:

```bash
python scripts/prepare_nisqa_pretrain.py \
  --corpus /path/to/NISQA_Corpus \
  --captions /path/to/speech-quality-descriptive-caption \
  --output ./data/nisqa-pretrain
```

Primary: **single-audio MOS-style captions** (answers require hearing the clip).  
Optional Stage 1b: **A/B two-audio captions** (teaches two-audio layouts).

### Do not use for warmup

- Final reference/degraded relative quality-description set (save for Stage 3)
- `data/dummy-100` (plumbing smoke only; captions are not verified relative descriptions)

## Audio-use probes (run every ~500 steps)

On a fixed ~100-example val slice, compare teacher-forced CE (or generation quality):

1. **Normal** audio
2. **Silence** (or noise) substituted for audio
3. **Shuffled** audio–caption pairs

Warmup is working only if **normal ≪ silence ≈ shuffle**. If all three are
similar, audio is still ignored.

## Training scheme

### Stage 0 — Environment + data (other server)

```bash
git fetch origin && git checkout jackiel4/train   # or your branch
git submodule update --init --recursive
# follow README Setup (uv + torch cu124 + requirements_hwangbo.txt)
python scripts/prepare_nisqa_pretrain.py \
  --corpus /path/to/NISQA_Corpus \
  --captions /path/to/speech-quality-descriptive-caption \
  --output ./data/nisqa-pretrain
```

Optional: small last-layer init on `DacProjector` (near-zero final `Linear`) so
audio embeds start closer to neutral than high-norm noise.

### Stage 1a — Projector-only CE (required)

Conceptual flags (adapt into a new script or override Swift CLI):

- Plugin: `scripts/dac_plugin.py`, `--model_type qwen2_audio_dac`, `--template qwen2_audio_dac`
- `--modules_to_save multi_modal_projector`
- **No LoRA** (do not enable `--tuner_type lora` / leave LLM frozen)
- `--freeze_vit true` (codec tower frozen)
- Dataset: `./data/nisqa-pretrain/train.jsonl` (+ matching `valid.jsonl`)
- `--max_steps 3000` (or 0.5–1 epoch on single-audio; sanity: 200–500 steps)
- `--learning_rate 5e-4` (try `2e-4`–`1e-3`)
- Effective batch ~8–16 (`per_device_train_batch_size` × `gradient_accumulation_steps` × GPUs)
- Cosine schedule, ~3% warmup
- `--output_dir ./output/dac-projector-warmup`
- Probe normal / silence / shuffle every ~500 steps

**Exit:** probes show audio is used; val CE on normal audio clearly better than controls.

### Stage 1b — Optional A/B projector-only

- Same frozen LLM, continue or reload Stage 1a projector
- A/B subset only
- `500–1500` steps, LR `1e-4`–`2e-4`

### Stage 2 — Light LoRA read-in (still NISQA, not final task)

- Load Stage 1 projector (via checkpoint / `--adapters` as appropriate for Swift)
- Enable LoRA on LLM; **freeze projector** first (or projector LR ×0.1)
- NISQA captions, `1000–2000` steps
- LoRA LR `2e-5`–`5e-5` (do **not** jump to joint `1e-4` from a cold projector)
- Re-run probes

**Exit:** LoRA uses audio tokens (shuffle/silence hurt again).

### Stage 3 — Real SFT (reference / degraded quality descriptions)

- Your actual audio + quality-description JSONL
- Initialize from Stage 1/2 weights
- Prefer **fresh optimizer** (`--adapters CHECKPOINT` pattern in README), not blind resume of warmup optimizer state
- Train LoRA (+ optional slow projector unfreeze)
- Only then ablate rate: DAC pool 3 vs 4; EnCodec prefer `pool_size=3` (25 Hz); optional latent interpolate to `T = round(D * 25)`

## Minimal “this week” path

1. Prepare NISQA single-audio JSONL  
2. DAC **projector-only**, **~3k steps**, LR **5e-4**  
3. Confirm normal ≪ silence/shuffle  
4. SFT on real quality-description data with LoRA + frozen/slow projector  

## What not to do first

- Joint random projector + LoRA at high LR
- Judging adaptation only on `dummy-100`
- Pure Whisper distillation as the only Stage 1 objective
- Interpolating positional embeddings to “fix” rate
- Unfreezing the codec encoder early
- Spending GPU on pool ablations before probes pass

## EnCodec follow-up

Reuse the same staged recipe after DAC works:

- `scripts/encodec_plugin.py`, `qwen2_audio_encodec`
- Strongly consider `POOL_SIZE = 3` (75 Hz → 25 Hz) for rate match
- Same NISQA warmup → LoRA read-in → task SFT

## Success criteria checklist

- [ ] Stage 1a: projector-only loss decreases
- [ ] Stage 1a: normal CE < silence CE and normal CE < shuffle CE
- [ ] Stage 2: LoRA improves captions without collapsing probe gaps
- [ ] Stage 3: gains on real relative quality-description eval vs cold joint SFT baseline
- [ ] (Later) pool / rate ablation on artifact-sensitive examples
