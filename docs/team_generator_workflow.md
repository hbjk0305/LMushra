# Team generator workflow and AudioLM data contract

## Supported release

Use the single deepmushra-data CLI from package 0.3.0 and profile mapped-poc-1.
Both python -m deepmushra_data and python -m deepmushra_mapped delegate to the same
CLI. They do not expose separate generator versions. Historical configurations
are retained only under docs/archive/configs for old experiments/regression tests;
shared low-level DSP functions are internal implementation helpers.

The only active recipe is configs/generator.yaml, also packaged as profile.json.
The current pilot requests are 50/65/75, chosen for engineering tests rather than
a user-approved final sampling design. The agreed label policy is transferred
estimated quality 0–100 plus Bad/Poor/Fair/Good/Excellent; a separate severity1–5
scale is not adopted. A --config argument must resolve to the
same recipe. Updating a generator/recipe/mapping requires a reviewed release used
by every worker, not per-worker edits.

Profile fingerprints cover the shared source modules, actual recipe, frozen
mapping/contract hashes, Python major/minor, NumPy/SciPy/SoundFile versions and
libsndfile version. The commit/environment are additionally recorded. Pin
requirements-generator.txt and use Python 3.10 to match the verified release.
Documented byte reproducibility applies to the same numerical platform; the
fingerprint is a compatibility gate, not proof that every possible platform has
identical floating-point behavior.

## Raw source manifests

Each JSONL row requires source_file and source_id. File paths resolve relative
to the manifest directory. content_category and source_provenance are retained.
Use real dataset/license/URL/artist/session identifiers. Example:

~~~json
{"source_id":"production-123","source_file":"audio/mix.wav","content_category":"music","source_provenance":{"dataset":"YOUR_CORPUS","license":"ACTUAL_LICENSE","source_url":"ACTUAL_URL"}}
{"source_id":"production-123","source_file":"audio/drums.wav","content_category":"music","source_provenance":{"dataset":"YOUR_CORPUS","license":"ACTUAL_LICENSE"}}
~~~

The default global recording identity is dataset-id:source_id. Use the same
dataset-id across shards of one corpus. Optional recording_group_id supplies a
curated global identity for related recordings across corpus namespaces. All
related stems/crops/microphones must share the same group; automatic hashing
cannot discover semantic overlap between independently named productions.
Directory mode (--input-dir) treats a file stem/relative path as a recording ID;
prefer manifests whenever files are related.

Preparation accepts native >=44100Hz WAV/FLAC, one/two channels, finite waveform
samples within digital full scale. Known original_header.sample_rate below 44100
is rejected even if the stored file was upsampled. Rate checks do not certify
cleanliness, effective bandwidth, prior codec history or source rights. Preserve
those provenance flags. Other source formats need an explicit audited decoding
stage with original-rate provenance; the tool does not silently transcode MP3.

The default 8-second nonoverlapping windows retain a final remainder if at least
one second long. clip-seconds must be 1–30. Clean audio is arithmetically downmixed,
rationally resampled with scipy.signal.resample_poly (Kaiser beta5, zero boundary)
when needed, and given a shared preparation gain only if needed for headroom.
The original header/hash, start sample, count and transformations are recorded.
The generator then applies its shared source gain before all variants.

Sharding is a stable hash of the recording group modulo shard-count. Splitting
uses a separate seeded hash with 70/15/15 thresholds. It never reapportions a local
shard to force nonempty partitions. Empty shards fail clearly; tiny valid/test
splits can be empty. Full train/valid/test source separation is checked on merge.

## One-command build

~~~bash
deepmushra-data build --manifest /corpus/sources.jsonl --dataset-id corpus-name \
  --output data/corpus-name --audio-prefix data/corpus-name --clip-seconds 8
~~~

No ODAQ assets or private KNN paths are required. The default frozen mapping is
inside the installed wheel. Output directories are never overwritten; failed
staging directories are removed. All audio processing runs on CPU.

For separate preparation/generation/export stages:

~~~bash
deepmushra-data prepare --manifest /corpus/sources.jsonl --dataset-id corpus-name --output data/prepared-corpus
deepmushra-data generate --manifest data/prepared-corpus/sources.jsonl --output outputs/corpus-generated
deepmushra-data validate --dataset outputs/corpus-generated
deepmushra-data export-training --dataset outputs/corpus-generated --output data/corpus-name --audio-prefix data/corpus-name
deepmushra-data check-export --bundle data/corpus-name --relative-to .
~~~

Portable export copies the generated dataset and evidence without changing WAVs.
Build additionally includes prepared source clips and their manifest/report. For
read-only historical interoperability, export-training --relative-to produces a
reference-only export; that mode is not a portable team handoff.

## Portable bundle layout

~~~text
data/corpus-name/
  train.jsonl
  valid.jsonl
  test.jsonl
  train.metadata.jsonl
  valid.metadata.jsonl
  test.metadata.jsonl
  export_report.json
  generator_profile.json
  bundle_verification.json
  preparation_report.json
  source_clips/                 # prepared clean inputs and provenance
    clips/*.wav
    sources.jsonl
    preparation_report.json
  dataset/
    audio/reference/*.wav
    audio/SAMPLE_ID/degraded.wav
    audio/SAMPLE_ID/residual.wav
    evidence/SAMPLE_ID.npz
    metadata/SAMPLE_ID.json
    metadata.jsonl
    manifest.jsonl
    manifests/*.jsonl
    resolved_config.json
    run.json
    validation_summary.json
~~~

Copy the complete directory to its --audio-prefix location relative to the model
training checkout. Model audio paths are POSIX-relative, not paths to a worker's
home directory. check-export without --relative-to validates internally anywhere;
with --relative-to /training/root it also verifies actual trainer-resolved paths.
source_clips and residual/evidence are retained for provenance and future caption
generation; only reference and degraded enter the current model example.

## Exact training JSONL contract

Verified against all 100 records at hwangbo/train commit
34f4f54b5d4e96d2846cb703e9267dbcf953f686, data/dummy-100/train.jsonl.
The pinned shape and example hash are in the packaged training_contract.json.

~~~json
{"messages":[{"role":"user","content":"Reference: <audio>\nDegraded: <audio>\nDescribe the difference."},{"role":"assistant","content":"High-frequency content is attenuated."}],"audios":["data/corpus-name/dataset/audio/reference/REFERENCE_ID.wav","data/corpus-name/dataset/audio/SAMPLE_ID/degraded.wav"]}
~~~

Exactly two top-level keys: messages and audios. Exactly two role/content objects:
user then assistant. Both contents are strings. Exactly two user audio placeholders
and two paths: reference then degraded. There is no residual audio or metadata
object in the model row. valid.jsonl is the required filename, although the rich
source metadata calls that partition validation.

Prompt wording is generalized for speech/music; format is identical, not a copy
of the original speech-only prompt or its NISQA MOS targets. Default assistant
text is descriptions.technical. export-training --description perceptual_candidate
can choose the explicitly unverified candidate. Later LLM descriptions should be
joined by sample_id using sidecars and keep the same model-row shape. This tool
neither calls an LLM nor fabricates a perceptual annotation.

## Rich sidecar metadata

Every *.metadata.jsonl row aligns to the same zero-based row_index in its model
split. It stores sample_id/source_id, original and training split names, portable
source_dataset, all three audio_paths, target field/status and the complete
metadata object. Source metadata includes native/prepared headers, raw/prepared
hashes, recording IDs, category, dataset/license provenance and clipping offsets.

The complete record keeps exact effect parameters/versions/seeds and TF evidence,
measured RMS/energy/spectral features, affected-region projections, estimated
quality/category and uncertainty provenance, unverified human fields and candidate
text. Conditional calibration bands are not mono/synthetic confidence intervals;
transfer flags remain explicit. Extra metadata never becomes an extra model input.

No-op records remain in dataset/metadata.jsonl but default exports omit them;
export-training --include-no-effect is available for diagnosis. This avoids
training on a replacement caption when no components were selected. Empty exports
fail; they are not published as usable training data.

## Merging completed work

Place all input bundles under their declared prefixes in one training root:

~~~bash
deepmushra-data merge --inputs data/worker-a data/worker-b --output data/combined --relative-to .
deepmushra-data check-export --bundle data/combined --relative-to .
~~~

The merged directory contains the six model/metadata JSONL files and a report;
it references original worker audio rather than copying it again. Keep those
worker bundles. Rows are sorted by sample_id for deterministic output regardless
of input order; split assignments are preserved.

Merge rejects inconsistent code/recipe/numerical fingerprints, training contracts,
duplicate samples, overlapping recording groups/original-source hashes/reference
hashes across workers, source split leakage, malformed rows, wrong audio order,
missing/modified WAVs, metadata disagreement and corrupt masks. It never silently
resplits or refits. Curate overlapping corpora before merging. It cannot identify
semantically related material whose IDs/provenance/hashes were all independently
changed; maintain the shared original-recording ledger.

## Generator and benchmark policy

LP/SH/UN use frozen original ODAQ calibration means; QN uses empirical mono QNMS
SNR coordinates with frozen stereo-quality means. These are assumed-transfer POC
estimates, not measured human labels. PE/TM remain held out. ODAQ audio/comments
are not synthetic sources or training captions, and held-out listener ratings
are not used for tuning. The benchmark must be described as ODAQ-informed and
listener-held-out. See mapped_generators_poc.md for mechanisms and limitations.

Readiness evidence is recorded in docs/team_generator_readiness.md. No model
training, Git push or dataset redistribution is part of this workflow change.
