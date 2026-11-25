# TODO

- [ ] Follow [`projector_warmup_dataset_plan.md`](projector_warmup_dataset_plan.md). The 24k subset is on mnn at `/data/jackiel4/data/AudioLM/projector-warmup-24k` (not NISQA). Next: family and severity heads off the decoding path, then caption-only LoRA SFT. Launch warmup with `CAPTION_TASK=ab`.
- [x] Add a train script for projector-only warmup (no LoRA) that matches the plan flags. (`scripts/train_projector_warmup.sh`, probes in `scripts/audio_use_probe.py`, LoRA read-in in `scripts/train_lora_readin.sh`.)
- [ ] Compare DAC/EnCodec pooling sizes 1, 2, and 4 (and EnCodec pool 3 for ~25 Hz) after warmup probes pass, to check whether pool size 4 saves compute without losing brief artifacts important for audio quality assessment.
