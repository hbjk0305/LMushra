# Supporting Data and Calibration Resources

For audio–text training and inference files, use the [dataset catalog](dataset_handoff_guide.md). NNN and KNN have host-local storage and require individual access permissions.

## Original synthetic audio checkpoint

On **NNN**, the original checkpoint contains **1,000,000 accepted audio triplets** (964,965 train and 35,035 validation). It supplies the audio underlying the three caption exports. Adding it to those exports would repeat audio.

```text
/scratch/tingyup2/projects/AudioLM/production/phase1_real_speech_music_v1/manifests/checkpoint_1000000/
```

Use `train.jsonl` and `valid.jsonl` for the original deterministic technical targets. Their matching `*.metadata.jsonl` files carry exact processing parameters, recording provenance, licenses and frozen split assignments. The published manifests select accepted examples from the production shards. Each triplet contains aligned 10-second, 44.1 kHz mono reference, degraded and residual WAVs. The saved residual equals degraded minus reference.

## ODAQ listener partition

The frozen partition on **KNN** (`knn.cs.illinois.edu`) is at

```text
/data/tingyup2/projects/AudioLM/LMushra/outputs/odaq_listener_calibration_feasibility_v1/proposed_listener_split.csv
```

Possible cross-study listener matches are recorded at

```text
/data/tingyup2/projects/AudioLM/LMushra/outputs/odaq_listener_calibration_feasibility_v1/candidate_cross_study_links.json
```

The CSV assigns 66 study-scoped records. The POC uses 58 main-study records, with **12 calibration and 46 evaluation**. The eight supplementary SH records belong to a separate panel. Filter by study and role to recover the main partition.

| Cohort | Namespaced calibration IDs |
|---|---|
| Original German | `2024-icassp::DEID10`, `2024-icassp::DEID2`, `2024-icassp::DEID256` |
| Original US | `2024-icassp::USLA12`, `2024-icassp::USLG03` |
| AES B1 | `2024-aes/B1::D004`, `2024-aes/B1::D009` |
| AES B2 | `2024-aes/B2::D005`, `2024-aes/B2::D015` |
| Stereo D sessions | `2025-aes::D004`, `2025-aes::D005` |
| Stereo E sessions | `2025-aes::E009` |

Study-scoped IDs preserve separate records for matching codes. The split keeps nine possible cross-study participant pairs on the same side. Their identities remain unconfirmed. The protocol is `odaq-listener-feasibility-v1`, seed `20261110`, with frozen CSV SHA-256 `60c1f20d7335d595d282e2c7341fb8ed6be90302b26002b1eaf0bc5aac15f654`.

## ODAQ calibration scores and frozen models

Find the original ODAQ audio and human scores on KNN at

```text
/data/tingyup2/projects/AudioLM/LMushra/data/external/odaq_collection_audit/release/odaq-collection/
```

Four score files supply the relevant trials, relative to that root.

```text
2024-icassp/ODAQ_listening_test/ODAQ_results.csv
2024-aes/Cohort_B1_results.csv
2024-aes/Cohort_B2_results.csv
2025-aes/ODAQ_v1.5_listening_test/ODAQ_1.5_results.csv
```

Filtering those tables by calibration listener and eligible LP/SH/UN/QN conditions yields the 846 human ratings used to fit the parameter-to-quality curves. References, anchors, PE and TM are excluded. The three NNN training exports supply synthetic caption targets.

| Artifact | Degraded stimulus/context conditions | Calibration human ratings | Listener-held-out evaluation ratings |
|---|---:|---:|---:|
| LP | 20 | 180 | 660 |
| SH | 66 | 318 | 1,258 |
| UN | 20 | 180 | 660 |
| QN | 56 | 168 | 728 |
| Total | **162** | **846** | **3,306** |

The two listener partitions rated the same conditions, spanning 11 named source excerpts. A repeated stimulus in another presentation context contributes another condition. QN has just three calibration listeners. Keep the stereo LR, MS and mixed contexts separate.

The KNN fit directory records the models, knots, protocol and seal created before held-out evaluation.

```text
/data/tingyup2/projects/AudioLM/LMushra/outputs/odaq_calibration_phase1_poc_v1/
├── fit/models.json
├── fit/quality_knots.csv
├── fit/protocol.json
├── fit/frozen_fit_seal.json
└── evaluation/                   # held-out results; not inputs to fitting/tuning
```

Use `deepmushra_calibration.data.load_ratings(release, split, "calibration")` to select the fitting rows from the original release. The [completed POC](odaq_calibration_phase1_poc.md) documents the exact protocol. Reserve the 3,306 evaluation ratings for listener-held-out evaluation. Both the transfer from stereo to synthetic mono and the empirical QN mono-SNR proxy remain unvalidated perceptually.

## Strict pilot diagnostics

On NNN, `selection.json` lists the 64 attempted sample IDs (one ID may appear under multiple strategies). Use `records.json` and `attempt_analysis.json` to inspect rejections and retries, and `output-verification.json` to check the final 44-example export. The per-request rendered inputs and raw model responses are in `runs/reasoned-caption-v10-2bd3cd87099f/rendered-requests/requests_and_raw_responses.jsonl` under the pilot root.

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

The sibling controlled runs include counterfactual LP quality inputs. Use those runs only for prompt diagnostics.

## Verification and access

NNN export paths and publication receipts were checked on 2026-11-23. The KNN paths and namespaced IDs above come from the completed [listener split](odaq_listener_calibration_feasibility.md) and [calibration POC](odaq_calibration_phase1_poc.md) reports. KNN SSH authentication was unavailable for this documentation pass. Before reproducing the analysis, check the split SHA-256 on KNN. Respect source licenses when transferring audio.
