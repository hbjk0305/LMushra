# Team generator readiness

Verified on KNN, 2026-11-11. Package 0.3.0, profile mapped-poc-1. The implementation
is ready for review/commit and teammate handoff; no commit or push was performed.
Current baseline HEAD is 24dcac7c386bb90a4fd9005ffe2782e6aa4c875c and the feature
changes remain in the pt/data working tree. GitHub will receive them only after
an authorized commit/push.

## Verified

- **179 automated tests passed in 52.86s.** Log: outputs/team-generator-final-tests.log.
- A fresh isolated Python 3.10 environment installed pinned dependencies and the
  built wheel, outside the repository working directory. Both imported generator
  packages resolved to site-packages, not source-tree imports.
- Wheel: deepmushra_data-0.3.0-py3-none-any.whl; SHA256 7d33a30bb31669403db4a5131ebbc9e87d399a77b3ef5641328ede105237a60f.
- Frozen profile, mapping and training-contract JSON assets are included in the
  wheel. No KNN-private source data, ODAQ downloads or runtime Git access is needed.
- Two independent workers processed all 8 licensed mono pilot recordings using
  deterministic recording shards. They generated 96 triplets and exported 92 model
  rows after omitting 4 no-op UN cases. Merged splits: train 60, valid 12, test 20.
- **All 100 records** in hwangbo/train's data/dummy-100/train.jsonl were inspected
  at commit 34f4f54b5d4e96d2846cb703e9267dbcf953f686. All 92 generated merged records match the
  exact top-level keys/types, role/content messages, two-placeholder convention
  and reference/degraded audio order. Captions/paths are our own.
- Repeating worker0 in a different output root matched **70 files byte-for-byte**.
- Copying its complete bundle to a new training root passed every model-path,
  WAV/residual/evidence and metadata consistency check.
- Tests reject mixed generator fingerprints, duplicate/overlapping worker data,
  source leakage, malformed rows, wrong audio order, path escapes, corrupted WAVs,
  mismatched metadata, invalid source rates and partial-output retries.
- The installed-wheel compatibility fingerprint matches the source environment:
  3af2e4150a832daf855ab151ce1cdbbef5927ca5b49be016fb1af6163471a798.

## Deliverables

- README.md and docs/team_generator_workflow.md: one supported CLI, installation,
  raw manifests, one-command builds, source sharding and central merge.
- configs/generator.yaml and requirements-generator.txt: shared recipe/environment.
- src/deepmushra_mapped: generator profile, preparation, stable splits, CLI, portable
  build and merge checks. Shared DSP utilities remain internal.
- src/deepmushra_data/training_export.py: reused paired exporter, extended with
  portable copies, sidecars and no-op omission.
- schemas/audiolm_row.schema.json and schemas/generator_metadata.schema.json:
  machine-readable structural contracts. CLI checks add file integrity, path,
  placeholder, ordering and signal checks beyond JSON Schema.
- docs/examples/audiolm_record.json: an actual merged model record.
- docs/mapped_generators_example.json: complete current pilot metadata.
- docs/archive/: older public instructions/configs, retained as historical evidence.

## Reproducible evidence

All evidence remains remote and Git-ignored:

~~~text
outputs/team_release_check_final/
  verification.json
  release_check.log
  run_release_check.py
  wheels/deepmushra_data-0.3.0-py3-none-any.whl
  training-root/data/worker0/
  training-root/data/worker1/
  training-root/data/combined/
  repeat-root/data/worker0/
  relocated-root/data/worker0/
~~~

The clean environment is /data/tingyup2/projects/AudioLM/envs/generator-release-check-py310/.
These are pilot handoff artifacts, not a full training corpus. The initial
outputs/team_release_check/ run is retained as pre-fix evidence: it caught a
build-temporary path in export_report.json. That path was removed and regression
coverage added; the final run above passed.

## Practical limits

No AudioLM/ms-swift training was run. Structural compatibility and portable file
loading are verified, not model quality or human-perceptual caption validity.
Default assistant targets are technical templates; future LLM descriptions can
be joined through sample_id and metadata sidecars. Quality fields retain their
ODAQ-informed assumed-transfer status. PE/TM and held-out listener tuning remain
excluded. Source rights and semantic recording overlaps require the shared
corpus ledger; hashes cannot discover independently renamed related productions.

Use the same reviewed commit, profile and numerical environment across workers.
This is a CPU data tool; CUDA/model dependencies belong in the separate training
environment. The new release changes source splitting to stable hashes; do not
mix historical quota-split outputs with new worker bundles.
