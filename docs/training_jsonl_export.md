# Export metadata to the hwangbo/train JSONL contract

> This documents the original reference-only exporter. The current [team workflow](team_generator_workflow.md) reuses this exporter with complete portable bundles and the single supported generator profile.

Inspected and fetched origin/hwangbo/train at **34f4f54b5d4e96d2846cb703e9267dbcf953f686** without switching away from pt/data. The existing training example is [data/dummy-100/train.jsonl](https://github.com/hbjk0305/LMushra/blob/34f4f54b5d4e96d2846cb703e9267dbcf953f686/data/dummy-100/train.jsonl); the [branch README](https://github.com/hbjk0305/LMushra/blob/34f4f54b5d4e96d2846cb703e9267dbcf953f686/README.md) documents paths, placeholders and model inputs.

## Contract

Each line is one JSON object with exactly:

- **messages:** user prompt followed by assistant target; both contents are strings.
- **audios:** two file paths, ordered **reference, degraded**.

The user prompt contains exactly two literal audio placeholders in that order. The residual is not a third model input in this export. Our generator continues storing full reference/degraded/residual triplets and rich metadata; the export does not replace those records.

Names are **train.jsonl**, **valid.jsonl** and **test.jsonl**. Existing source split validation maps to the filename valid; there is no resplitting or truncation to match the dummy dataset’s count of100.

The example dummy targets include original single-stimulus NISQA MOS claims. The exporter copies none of those targets or ratings. Our default target is descriptions.technical. These are processing descriptions, not verified human-perceptual labels.

## Use on KNN

All execution/storage stays remote:

~~~bash
cd /data/tingyup2/projects/AudioLM/LMushra
. ../env.sh
python -m deepmushra_data export-training   --dataset outputs/artifact-validation/mono_pipeline   --output data/swift-run-001   --relative-to .
~~~

Choose a new output directory; existing outputs are never overwritten. The same command is available through the installed deepmushra-data CLI.

To export the explicitly unverified candidate description instead:

~~~bash
python -m deepmushra_data export-training   --dataset outputs/artifact-validation/mono_pipeline   --output data/swift-candidate-run-001   --relative-to .   --description perceptual_candidate
~~~

Optional prompt-file overrides must contain exactly two audio placeholders. The default prompt supports speech and music; it does not inject artifact names, parameter values or source metadata as answer hints.

## Generated files

~~~text
data/swift-mono-pilot/
  train.jsonl                 #78 records
  valid.jsonl                 #13 records
  test.jsonl                  #13 records
  train.metadata.jsonl
  valid.metadata.jsonl
  test.metadata.jsonl
  export_report.json
~~~

This actual example exports104 existing mono-pilot records from eight independent source-recording groups:24LP,24SH,24UN,24QN and8identity controls. All stored input audio is44.1kHz mono and4s long. These are small pilot examples, not a newly quality-approved corpus or a full training dataset.

No audio is copied, resampled, downmixed or modified. This directory contains text exports; the source dataset/audio must remain available.

## Actual model row

Below is the first generated training record, pretty-printed for readability. The file itself stores one complete object per line.

~~~json
{
  "messages": [
    {
      "role": "user",
      "content": "Reference audio (original): <audio>\nDegraded audio (processed counterpart): <audio>\n\nCompare the processed audio with the reference. Describe the processing-related\nchanges concisely, making the direction of the comparison clear. Treat possible\nperceptual effects as uncertain unless verified. Do not invent audibility,\nperceived severity, MOS, MUSHRA ratings, or a codec identity. Do not transcribe\nspeech or summarize musical content.\n"
    },
    {
      "role": "assistant",
      "content": "Signal-shaped noise is added at a 30 dB reference-to-noise energy ratio per channel, using 500 Hz spectral smoothing and a causal 5 ms RMS envelope. The original waveform is retained; this is not a psychoacoustic NMR simulation."
    }
  ],
  "audios": [
    "outputs/artifact-validation/mono_pipeline/audio/reference/510d028ee5e2ef51143de93960ea9bca5d7828603e3ca0f04c1d036358619639.wav",
    "outputs/artifact-validation/mono_pipeline/audio/055c4e26dbe9703b98c90e26/degraded.wav"
  ]
}
~~~

## Metadata sidecars and caption provenance

A sidecar line corresponds to the same zero-based row_index in its split JSONL. It includes sample_id, source_id, source/training split names, source_dataset, target field/status, emitted reference/degraded/residual paths and **the complete original metadata object** under metadata.

This preserves processing parameters, objective measurements, source/license provenance, residual and evidence references, unknown perceptual annotations and any additional generator fields. Sidecar metadata is not supplied as the model’s messages or additional audio. In particular, extra calibration estimates are not automatically converted to assistant ratings.

Target status is processing_description_not_perceptual_ground_truth by default or unverified for perceptual candidates. Original perceptual severity, quality category and audibility remain untouched. The caption workstream can join sidecars by sample_id and replace the description-generation stage later; this change does not run an LLM or add human annotations.

The original metadata.jsonl, manifest.jsonl and per-record metadata remain unchanged. Export reads the common full-metadata fields and accepts additional fields; it does not rewrite records into the narrower historical core schema.

## Paths and model use

With relative-to set to the training checkout root, audio paths are relative to that root. The actual pilot’s paths begin outputs/artifact-validation/mono_pipeline/audio/. Without relative-to, the exporter writes absolute paths on the current host.

Do not reuse /home/hwangbo5/... paths from the original dummy examples. For another host/check-out, transfer the source audio tree with its relative layout or re-export against the correct root. Sidecar source_dataset is the original host’s dataset location; relocate provenance/evidence references deliberately if moving the data.

On hwangbo/train, after the files and source audio are available in that checkout, the documented DAC launcher can consume them:

~~~bash
bash scripts/train_dac_dummy_100.sh   --dataset ./data/swift-mono-pilot/train.jsonl   --val_dataset ./data/swift-mono-pilot/valid.jsonl
~~~

This is a usage example only: **no training was run**. Use the DAC44.1k path when preserving high-frequency artifact information. The branch’s baseline16k and EnCodec24k inputs lose upper-band information even when source files are44.1k.

## Validation and scientific boundaries

Before publishing an export, the exporter checks:

- Supported LP/SH/UN/QN/identity labels; PE/TM remain excluded.
- Source IDs, source checksums and exact-reference hashes do not cross splits.
- Every input path stays inside the source dataset, exists and matches its recorded hash.
- All three stored waveforms have matching44.1kHz mono length, are finite and within digital full scale, and are at most30s long.
- Residual reconstruction agrees to1e-12. Actual104-record pilot maximum error:2.7755575615628914e-17.
- Known original_header rates below44.1k are rejected; passing stored headers is not a complete acquisition/provenance or cleanliness audit.
- Targets are nonempty and do not contain extra audio placeholders; candidate status must be explicitly unverified.
- Input metadata is unchanged during export; partial outputs are discarded and existing outputs preserved.

The existing pipeline may preserve native48k/stereo sources, but this model export deliberately requires **already generated44.1k mono triplets**. Convert the clean reference before degradation, then regenerate triplets/metadata. Do not silently downmix/resample completed triplets and keep old measurements.

Full mask semantics, source rights and perceptual validity are not re-certified by this format exporter. A structurally compatible training file does not establish that the captions are perceptually correct.

Tests:23 new exporter cases passed, covering schema/order, sidecars, split preservation/leakage, deterministic output, CLI/relative paths, unknown labels, additional metadata, invalid source formats, clipping/nonfinite/corrupt audio, residual mismatch, path escape, overwrite protection and unsupported/held-out labels. All 25 existing pipeline regression tests also passed. No model weights, training frameworks or new dependencies are required.

## Implementation

- src/deepmushra_data/training_export.py — streaming, atomically published paired export.
- src/deepmushra_data/cli.py — export-training command.
- tests/test_training_export.py — contract/integrity tests.
- data/swift-mono-pilot/export_report.json — generated-file hashes, source/split counts, branch contract revision, target limitations and audio checks.

Generated data/outputs remain ignored by Git. The branch and dummy examples were inspected through Git objects; no training-branch files were checked out or modified. No commit or push is included in this work.
