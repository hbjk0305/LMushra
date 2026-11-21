# TODO

- [ ] Follow [`projector_warmup_plan.md`](projector_warmup_plan.md): DAC projector-only CE warmup on NISQA, probes (normal / silence / shuffle), then LoRA read-in, then real quality-description SFT.
- [ ] Add a train script for projector-only warmup (no LoRA) that matches the plan flags.
- [ ] Compare DAC/EnCodec pooling sizes 1, 2, and 4 (and EnCodec pool 3 for ~25 Hz) after warmup probes pass, to check whether pool size 4 saves compute without losing brief artifacts important for audio quality assessment.
