# DeepMUSHRA dataset handoff guide

**Prepared:** 2026-11-23. **Audience:** dataset, caption-generation, model-training, and evaluation teammates.

**Start here:** use the published NNN caption exports for AudioLM training, the namespaced KNN listener split for calibration reproducibility, and the small matched sets for development. These are different resources with different purposes.

Two naming corrections are essential:

1. The million-audio checkpoint contains **1,000,000 accepted audio examples**. The primary LLM-caption export contains **999,773 examples**, after 227 caption rejections. It is a format-checked, warning-preserving pseudo-label release, **not a fully semantically corrected or human-verified million-caption dataset**.
2. The **ODAQ calibration subset** is selected human ratings of original ODAQ stimuli. It is **not** a curated synthetic-caption SFT dataset. The strongest existing small synthetic caption checks belong to a separate 44-example diagnostic pilot.

No audio was copied, moved, regenerated, or relabeled to prepare this guide. No inference or training was launched.

## 1. Quick resource map

All paths are **host-local**. NNN and KNN are not assumed to share a filesystem.

| Resource | Host | Size | Appropriate use |
|---|---|---|---|
| Original accepted synthetic audio checkpoint | NNN | 1,000,000 audio triplets; 964,965 train / 35,035 validation | Frozen audio, metadata, original technical targets |
| Primary calibrated caption export | NNN | **999,773**; 964,747 train / 35,026 validation | Large-scale Phase 1 pseudo-label SFT experiments |
| Original listener partition | KNN | 66 study-scoped records in the split file; **58 main-study records** used in the POC | Reproduce the listener-held-out protocol |
| ODAQ calibration score selection | KNN | **846 ratings from 12 main-study listener IDs**, covering 162 degraded stimulus/context conditions | Reproduce parameter-to-quality calibration; not caption SFT |
| Production-policy matched ablations | NNN | **1,025 IDs** per strategy; 982 train / 43 validation | First training/integration POC and comparable three-strategy experiments |
| Stricter reasoned-caption pilot | NNN | **44 retained IDs** per strategy; 36 train / 8 validation, from 64 attempted IDs | Small diagnostic comparison of grounding, quality impact, and failure handling |

The 1,025-example set inherits the million-run policy; it is not more semantically curated just because it is smaller. The 44-example set has stronger executed automated checks but still has no human perceptual ground truth.

## 2. Full synthetic audio and primary caption dataset

### 2.1 Frozen audio and original metadata

Host: **NNN**, `nnn.cs.illinois.edu`.

```text
/scratch/tingyup2/projects/AudioLM/production/phase1_real_speech_music_v1/
├── manifests/checkpoint_1000000/
│   ├── train.jsonl
│   ├── valid.jsonl
│   ├── train.metadata.jsonl
│   ├── valid.metadata.jsonl
│   └── validation.json
└── shards/                         # actual WAVs and original per-example metadata
```

The checkpoint manifests select the accepted population. **Do not concatenate raw shard exports**: those intermediates may include examples excluded by the production acceptance ledger. The original technical-template targets are not the final teacher-generated captions.

Audio: 10 seconds, 44,100 Hz, mono, 441,000 samples, with aligned reference/degraded/residual triplets. Saved residuals use the exact saved degraded minus reference signals. Shared references avoid unnecessary duplication. The original waveform checks and production receipt remain authoritative; this handoff inspection did not decode all million triplets again.

### 2.2 Primary caption training export

Host: **NNN**.

```text
/scratch/tingyup2/projects/AudioLM/annotations/caption-poc-fast-v3/run/snapshots/population_1000000/calibrated_llm/
├── train.jsonl                    # 964,747 rows
├── val.jsonl                      # 35,026 rows
├── train.metadata.jsonl
├── val.metadata.jsonl
├── valid.jsonl -> val.jsonl
└── valid.metadata.jsonl -> val.metadata.jsonl
```

| Artifact | Captioned examples | Rejected captions |
|---|---:|---:|
| LP | 249,844 | 156 |
| SH | 249,934 | 66 |
| UN | 249,995 | 5 |
| QN | 250,000 | 0 |
| Total | **999,773** | **227** |

The same snapshot root also contains `technical_template/`, `ablation_sample/`, and `matched_ablations/`. These are alternatives or overlapping subsets, not additional independent audio populations.

### 2.3 What the quality/status labels mean

The current read-only ledger inspection confirms:

| Internal caption status | Count | Meaning |
|---|---:|---|
| `warning` | 832,556 | Passed hard gates; unresolved semantic/editorial/consistency concerns retained |
| `unchecked` | 167,164 | Passed hard gates; no clean sampled semantic-audit status |
| `accepted` | 53 | Clean status from a limited **same-model** audit, not human verification |
| `rejected` | 227 | Not exported in the primary calibrated training set |

All retained LLM captions remain unverified pseudo-labels. Do not report 99.9773% structural usability as caption accuracy. The 53 internally accepted captions are not an independently validated gold set. There is currently no verified, fully corrected one-million-caption replacement.

## 3. Training schema and usage

Each training JSONL row has exactly these top-level keys:

```json
{
  "messages": [
    {"role": "user", "content": "...two audio placeholders and the comparison instruction..."},
    {"role": "assistant", "content": "...description target..."}
  ],
  "audios": ["/absolute/path/to/reference.wav", "/absolute/path/to/degraded.wav"]
}
```

This is a schematic schema example, not a replacement training record. Keep the actual exported messages unchanged.

- Audio order is **reference first, degraded second**. The residual is linked in the sidecar, not a third student input in the current export.
- Training rows deliberately omit `sample_id`; recover it from the matching sidecar at the same row position. Check IDs when joining different versions; do not join independent datasets by row number.
- Sidecars retain `sample_id`, `source_id`, original metadata, three audio paths, exact processing parameters, measurements, source provenance/license, sampling provenance, quality estimates, annotation version, and strategy-specific diagnostics.
- Example pointers include `metadata.source.source_provenance.recording_group_id`, `metadata.calibration_estimate`, and, for the million caption policy, `annotation.status`, `annotation.warnings`, and `annotation.observability`. Annotation details differ between the fast and reasoned versions; do not assume identical internal schemas.
- Use the original **train versus validation partition**, not a new random split of derivatives. The primary caption row ratio is about 96.5%/3.5%, rather than exactly 95%/5%.
- `val.jsonl` and `valid.jsonl` alias the same validation data. Sidecar `training_split` commonly retains the original value `valid`. These names do not represent different partitions.
- Do not expose DSP parameters, quality scores, or teacher evidence to the student merely because they are available in sidecars.

Select the primary files on NNN:

```bash
DATASET=/scratch/tingyup2/projects/AudioLM/annotations/caption-poc-fast-v3/run/snapshots/population_1000000/calibrated_llm
TRAIN_JSONL="$DATASET/train.jsonl"
VAL_JSONL="$DATASET/val.jsonl"
```

Pass those two paths to the current training configuration's dataset inputs. This guide does not launch training or invent a new training CLI. The inspected loader contract was `hwangbo/train` revision `34f4f54b5d4e96d2846cb703e9267dbcf953f686`; recheck compatibility if the training branch changes. Earlier loader smoke tests exercised real decoding/collation, not model forward passes or full tokenizer prompt encoding.

To inspect the first row and its ID without altering anything:

```bash
python3 - "$TRAIN_JSONL" "$DATASET/train.metadata.jsonl" <<'PY_CHECK'
import json, sys
from pathlib import Path
with open(sys.argv[1]) as f:
    row = json.loads(next(f))
with open(sys.argv[2]) as f:
    sidecar = json.loads(next(f))
assert set(row) == {"messages", "audios"}
assert row["audios"] == [sidecar["audio_paths"]["reference"], sidecar["audio_paths"]["degraded"]]
assert all(Path(p).is_file() for p in row["audios"])
print("sample_id:", sidecar["sample_id"])
print("original split:", sidecar["training_split"])
print("audio paths:", row["audios"])
print("caption:", row["messages"][-1]["content"])
print("caption status:", sidecar["annotation"].get("status"))
PY_CHECK
```

## 4. Original listeners used for ODAQ calibration

Host: **KNN**, `knn.cs.illinois.edu`.

Authoritative partition file:

```text
/data/tingyup2/projects/AudioLM/LMushra/outputs/odaq_listener_calibration_feasibility_v1/proposed_listener_split.csv
```

Related conservative identity-link file:

```text
/data/tingyup2/projects/AudioLM/LMushra/outputs/odaq_listener_calibration_feasibility_v1/candidate_cross_study_links.json
```

The split CSV contains **66 study-scoped records**: 58 main-study records plus eight supplementary-SH records. The primary calibration POC uses only the 58 main-study records: **12 calibration / 46 evaluation**. The optional supplementary panel's proposed 2/6 partition was not included in the primary POC. Filter by study and role; do not blindly count all calibration rows in the CSV.

The exact **12 main-study calibration IDs**, as recorded in the completed protocol, are:

| Cohort | Namespaced calibration IDs |
|---|---|
| Original German | `2024-icassp::DEID10`, `2024-icassp::DEID2`, `2024-icassp::DEID256` |
| Original US | `2024-icassp::USLA12`, `2024-icassp::USLG03` |
| AES B1 | `2024-aes/B1::D004`, `2024-aes/B1::D009` |
| AES B2 | `2024-aes/B2::D005`, `2024-aes/B2::D015` |
| Stereo D sessions | `2025-aes::D004`, `2025-aes::D005` |
| Stereo E sessions | `2025-aes::E009` |

Use namespaced IDs, not bare codes. Repeated codes across studies do not prove distinct or identical people. Nine possible cross-study links were conservatively assigned to the same side; a globally confirmed participant crosswalk is unavailable. Selection seed: `20261110`; protocol: `odaq-listener-feasibility-v1`. Frozen split SHA-256: `60c1f20d7335d595d282e2c7341fb8ed6be90302b26002b1eaf0bc5aac15f654`.

**Verification scope:** the NNN exports were checked live for this guide. KNN rejected the stored SSH credential during this session, so these KNN paths and assignments are taken from the completed calibration reports and have not been live-reverified today. Confirm the files and split hash on KNN before a new calibration reproduction; do not silently reconstruct the original CSV from this table.

## 5. What the calibration subset actually is

Original ODAQ audio and human-score release:

```text
/data/tingyup2/projects/AudioLM/LMushra/data/external/odaq_collection_audit/release/odaq-collection/
```

Relevant score files, relative to that release root:

```text
2024-icassp/ODAQ_listening_test/ODAQ_results.csv
2024-aes/Cohort_B1_results.csv
2024-aes/Cohort_B2_results.csv
2025-aes/ODAQ_v1.5_listening_test/ODAQ_1.5_results.csv
```

The calibration subset is **these original stimuli/scores + the frozen listener-role selection + the allowed LP/SH/UN/QN non-control conditions**. There is no separate copied calibration-audio folder and no published, curated ODAQ calibration-caption SFT set identified by this handoff.

| Artifact | Degraded stimulus/context conditions | Calibration human ratings | Listener-held-out evaluation ratings |
|---|---:|---:|---:|
| LP | 20 | 180 | 660 |
| SH | 66 | 318 | 1,258 |
| UN | 20 | 180 | 660 |
| QN | 56 | 168 | 728 |
| Total | **162** | **846** | **3,306** |

This covers 11 named reference-excerpt keys. The 162 source/processing/context conditions include repeated settings across listening contexts; they are **not 162 independent source recordings or a claim of 162 unique waveform contents**. Original LP/SH/UN each use four excerpts and five processing settings, with nine calibration ratings per source/setting. Stereo QN/SH contexts have three calibration listeners; MS/mixed presentation contexts remain separate.

The 20%/80% division is by **listeners**, not audio: both groups rate the same administered conditions. It is ODAQ-informed, listener-held-out evaluation, not an independently held-out audio benchmark. Original ODAQ playback and ratings are stereo; our synthetic audio is mono. Neither the stereo human ratings nor their intervals establish human quality for the mono synthetic signals.

Fitted mapping/provenance root:

```text
/data/tingyup2/projects/AudioLM/LMushra/outputs/odaq_calibration_phase1_poc_v1/
├── fit/models.json
├── fit/quality_knots.csv
├── fit/protocol.json
├── fit/frozen_fit_seal.json
└── evaluation/                   # held-out results; not inputs to fitting/tuning
```

Read-only selection example, to run on KNN after confirming access and the frozen split:

```bash
source /data/tingyup2/projects/AudioLM/env.sh
cd /data/tingyup2/projects/AudioLM/LMushra
PYTHONPATH=src python - <<'PY_CALIBRATION'
from pathlib import Path
import hashlib
from deepmushra_calibration.data import load_ratings
split = Path("outputs/odaq_listener_calibration_feasibility_v1/proposed_listener_split.csv")
assert hashlib.sha256(split.read_bytes()).hexdigest() == "60c1f20d7335d595d282e2c7341fb8ed6be90302b26002b1eaf0bc5aac15f654"
rows = load_ratings(Path("data/external/odaq_collection_audit/release/odaq-collection"), split, "calibration")
assert len(rows) == 846
assert len({r["listener_id"] for r in rows}) == 12
print("Selected calibration ratings:", len(rows))
print("Study-scoped listener IDs:", len({r["listener_id"] for r in rows}))
PY_CALIBRATION
```

This selects existing calibration data; it does not fit new curves, read held-out scores for tuning, generate captions, or train a model. It is a documented command, not executed on KNN during this handoff because authentication was unavailable.

If by “calibration subset” you mean “the most carefully checked caption-development set,” use the separate synthetic pilot below instead. Do not relabel ODAQ data as that resource or mix ODAQ stimuli into synthetic SFT. Generating LLM descriptions for ODAQ would not itself make them correct or human-verified.

## 6. Small datasets for POC and caption diagnosis

### 6.1 Recommended first training/integration POC: matched 1,025

Host: **NNN**.

```text
/scratch/tingyup2/projects/AudioLM/annotations/caption-poc-fast-v3/run/snapshots/population_1000000/matched_ablations/
├── technical_template/{train,val}.jsonl
├── metadata_llm/{train,val}.jsonl
└── calibrated_llm/{train,val}.jsonl
```

Each strategy also has matching `*.metadata.jsonl` sidecars. All three strategies use the same **982 train / 43 validation IDs**, same audio pairs, and same student input messages. Only the targets and annotation provenance differ.

| LP | SH | UN | QN | Original source groups |
|---:|---:|---:|---:|---:|
| 271 | 243 | 259 | 252 | 417 |

**Use for:** quick dataloader checks and three-way SFT ablations before large training. Start with identical IDs/settings and compare the technical, no-prior, and calibrated targets. Do not claim observed downstream differences prove a causal quality-prior benefit without controlling the experimental setup.

**Limit:** this is a sampled production-policy set, not a semantic gold set. Its calibrated captions contain **871 warning and 154 unchecked records**. Small validation size limits conclusions. All 1,025 IDs are already in the primary million-run export; do not add this set to it as new data or treat it as an independent benchmark.

### 6.2 Strongest existing small automated-grounding POC: 44 retained from 64

Host: **NNN**. Use the **absolute-path view**:

```text
/scratch/tingyup2/projects/AudioLM/annotations/reasoned-caption-32b-v13-pilot/registry/runs/reasoned-caption-v10-2bd3cd87099f/exports/unique64_absolute/
├── technical_template/{train,val}.jsonl
├── metadata_llm/{train,val}.jsonl
└── calibrated_llm/{train,val}.jsonl
```

Again, keep matching sidecars. Each strategy has **36 train / 8 validation IDs**, with 44 source groups:

| LP | SH | UN | QN |
|---:|---:|---:|---:|
| 11 | 15 | 13 | 5 |

The underlying diagnostic selection attempted 64 unique samples/references/recording groups, 16 per artifact, across GuitarSet, ordinary VocalSet, MAESTRO, EARS, and VCTK. Only 44 survived the common three-strategy export. QN retention was **5/16**, an important selection-bias limitation, not something to conceal by balancing accepted rows after the fact.

This separate reasoning-enabled pipeline separates acoustic character generation from quality-impact generation, binds claims/declarations to evidence and quoted text, and runs stronger same-model semantic checks. The character sentence is shared by metadata-only and calibrated versions, so quality information cannot change that sentence through the impact writer. It is **not** a corrected million-caption release or proof that these 44 labels are perceptually accurate.

**Use for:** inspecting known grounding issues, comparing character-only versus quality-informed targets, testing the output format, and a very small training smoke test. It is too small and imbalanced for reliable model ranking or full training conclusions. Keep the 20 excluded sample IDs/diagnostics when investigating why the stricter pipeline rejects cases.

Diagnostic evidence root:

```text
/scratch/tingyup2/projects/AudioLM/annotations/reasoned-caption-32b-v13-pilot/
├── delivery-readiness.json
├── actual-loader-all-rows.json
├── verified-training-view-hashes.json
└── runs/reasoned-caption-v10-2bd3cd87099f/unique64/
    ├── selection.json
    ├── records.json
    ├── attempt_analysis.json
    ├── output-verification.json
    └── delivery-summary.json
```

Use `records.json` and raw-request evidence for failed attempts; do not count each strategy/seed/request as a distinct audio recording. Controlled LP score overrides and counterfactual cases in sibling control runs are **diagnostics, not training examples**. Do not concatenate them into these exports.

All 44 retained IDs also exist in the million export (33 warning / 11 unchecked under the fast policy). Only five of them overlap the matched 1,025 set. Compare versions by stable sample ID and preserve original split membership. Repeated appearances do not create independent test data. These are development sets used during prompt/validator development, not untouched semantic benchmarks.

### 6.3 Larger historical pilots

Older 200/2,000/20,000-example exports exist under:

```text
/scratch/tingyup2/projects/AudioLM/annotations/description-poc-v1/runs/metadata-teacher-poc-v4-bdcddf800d2d/exports/
```

They used **Qwen3-8B and an older prompt/validator policy**. They are historical experimental outputs, not a stronger curated replacement for either the million-run version or the strict 44-example pilot. Do not mix caption versions silently or describe historical acceptance counts as success under the current policy.

### 6.4 Recommendation

1. **Diagnose caption issues:** inspect the strict pilot's 64 attempted cases, including failures, and its 44 retained three-strategy targets. Compare original million-run captions for the same IDs.
2. **Run the first training POC:** use the matched 1,025 set and fixed train/validation assignments. Treat its warnings explicitly; it is useful for controlled experiments, not guaranteed clean supervision.
3. **Scale only the chosen experiment:** use the primary 999,773-caption export, keeping a record of annotation policy and warning treatment.
4. **Proposed, not completed:** if a larger semantically screened POC is needed, extend the stronger automated checks to a new source-diverse, artifact/strength-stratified 1K–2K diagnostic selection with explicit rejection accounting. This guide does not create that set or authorize a new inference campaign. Preserve fixed sources/splits; do not optimize the set by keeping only easy families.

There is no independently verified caption gold set identified here. Manual listening is not a Phase 1 gate, but automated acceptance must not be presented as perceptual truth.

## 7. Access, transfer, and scientific reminders

- Teammates should use their **own server accounts** and request dataset-path access when necessary. This report does not grant permissions. Existing named-user access for `hwangbo5` does not imply access for all members.
- Treat published checkpoints/snapshots as read-only inputs even where approved ACLs permit edits. Write experiments and filtered/rebased views into separate versioned directories.
- NNN JSONL paths are absolute NNN audio paths. A GitHub clone, copied JSONL, or KNN session alone cannot resolve them. Transfer the necessary audio and produce a separate rebased path view if training elsewhere; do not edit the originals.
- Keep training and metadata JSONLs paired and ordered. Use sample IDs for joins, preserve recording/production groups, and never independently shuffle sidecars.
- Use `val` **or** its `valid` alias once; do not load both and double-count validation.
- A native high sample rate does not certify recording cleanliness or lossless history. Source provenance and prior-lossy-coding flags remain relevant, including the flagged MP3-derived HiFiTTS-clean expansion.
- Review `metadata.source.source_provenance.license` and source conditions before redistribution. A shareable GitHub guide does not authorize publishing source audio.
- Do not interpret provisional quality means or reference-domain intervals as human ratings/confidence intervals for these mono synthetic examples. QN's empirical SNR bridge is not psychoacoustic NMR equivalence.
- Keep ODAQ stimuli out of synthetic SFT and preserve the held-out 80% rating boundary. ODAQ-informed calibration means the resulting evaluation is not fully independent. Keep PE/TM out of training and calibration.
- Do not restart production, teacher jobs, or full-checkpoint annotation just to consume the existing exports. None are needed to read the datasets.

## 8. What was checked for this handoff

The accompanying [machine-readable verification](dataset_handoff_verification.json) records the live NNN inspection:

- The million-run SQLite ledger still has 999,773 usable and 227 rejected primary records, with no pending primary jobs found in the earlier status query.
- The final snapshot publication SHA matches the completed full-audit receipt. The earlier full cumulative audit remains the proof for all million IDs; this handoff does not claim a new full decode or hash of every large export/audio file.
- All 12 regular JSONL/sidecar files for each small three-strategy set match their recorded publication/view hashes.
- Every small-set training row aligns with its sidecar; IDs, splits, audio ordering, and student input messages match across strategies.
- Small sets contain no duplicate IDs or cross-split recording-group leakage, and their audio paths are absolute and exist on NNN. Metadata specifies 44.1-kHz mono/441,000 samples; this handoff did not re-decode those WAVs.
- All retained small-set IDs occur in the million ledger with the same original split; overlap between the two small sets is five IDs.
- KNN paths remain documented but **not live-reverified** because SSH authentication failed. No credentials were copied into this guide, repository, or verification output.

For the million-caption prompt, exact hard thresholds, warning policy, and limitations, see [Caption generation overview](caption_generation_overview.md).
