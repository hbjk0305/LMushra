# Initial pipeline verification

Verified on 2026-11-01, on `pt/data`, without committing or pushing changes.
This report concerns software behavior on analytical signals, not human
perceptual validity.

## Environment

- Python 3.12.5, macOS arm64
- NumPy 2.2.4; SciPy 1.15.2
- SoundFile 0.14.0; libsndfile 1.2.2
- PyYAML 6.0.3; Matplotlib 3.10.1
- pytest 9.2.0

The project environment at `.venv/` reused the preinstalled numerical packages
through system-site-packages; missing configuration/test packages were installed
locally. `requirements-tested.txt` records the dependency closure for a fresh
environment. No external recording corpus, neural model, or `ms-swift` dependency
was used.

## Automated tests

Command:

```bash
.venv/bin/python -m pytest -q
```

Result: **76 passed in 9.39 s**.

Coverage includes both sample rates and channel counts, STFT identity recovery
(including one-sample and non-window-aligned inputs), LP response and causality,
subtle 16 kHz filtering, SH masks/probabilities/runs and complete removal, UN
tonal-peak reduction and envelope error, deterministic seeds and file bytes,
source aliases/excerpts/duplicate grouping, input integrity and minimum sample
rate, shared headroom, degraded/residual peak rejection, atomic failure cleanup,
unknown perceptual labels, strict serialization, corruption detection, and the
CLI with saved diagnostic figures. The LP order limit is checked before large
filter construction.

Repeated small end-to-end runs produced identical audio, NPZ, metadata, and
manifest bytes after reversing the input manifest order. A separate test checks
deterministic analytical source generation. WAV timestamp canonicalization is
verified without changing waveform samples.

## Full pilot

Commands:

```bash
.venv/bin/deepmushra-data demo --config configs/pilot.yaml --output outputs/pilot
.venv/bin/deepmushra-data demo --config configs/pilot.yaml --output outputs/pilot-verified
.venv/bin/deepmushra-data validate --dataset outputs/pilot-verified
```

The second run uses the final implementation, including the filter-order guard.
Both directories remain ignored by Git. Existing runs are not overwritten.

| Check | Result |
|---|---|
| Source recordings | 6 analytical fixtures, each 4 s |
| Sample rates | 44,100 and 48,000 Hz |
| Channel layouts | Mono and stereo |
| Examples | 60 triplets |
| Artifacts | 18 LP, 18 SH, 18 UN, 6 identity |
| Source groups per split | 4 train, 1 validation, 1 test |
| Examples per split | 40 train, 10 validation, 10 test |
| Validation errors | 0 |
| Maximum residual/reconstruction error | 5.551115123125783e-17 |
| Required numerical tolerance | 1e-12 |
| WAVs per pilot | 132: 6 original fixtures, 6 shared references, 120 outputs |
| Storage per run | Approximately 372 MB, including masks and figures |
| Figures | `diagnostics/LP.png`, `SH.png`, `UN.png` |

The pilot's maximum degraded peaks were approximately 0.347 (LP), 0.369 (SH),
and 0.509 (UN), below the configured 0.999 limit. Identity samples have exactly
zero residual. The independent validator checks every saved role, file hash,
rate, shape, peak, residual, manifest, split, and evidence grid.

The strongest displayed UN example on the tonal fixture has selected-envelope
relative error approximately 0.128. Its mean contrast at reference tonal peak
locations changes from about 13.03 dB to 0.44 dB. These are objective DSP checks;
they do not establish perceptual equivalence to ODAQ or subjective strength.
The UN diagnostic figure was visually inspected.

## Metadata and interpretation

[metadata.example.json](metadata.example.json) is copied from a real pilot SH
example at 44.1 kHz. It uses hole probability 0.3, start frequency 4 kHz, 500 Hz
bands, four-frame blocks, and 80 dB attenuation. Its realized selected-grid ratio
is approximately 0.2473; it differs from 0.3 because coverage includes unselected
low-frequency bins and realized random occupancy. This ratio is not audibility.

All perceptual labels remain `null`, all perceptual candidates remain
`unverified`, and every source is marked as functional test material. PE and TM
are absent from the generator and every training manifest.

The next research step is source-corpus selection and independent listening
validation of candidate text and subtle settings. The pilot is ready for code
review, not for claims about listener agreement or model performance.
