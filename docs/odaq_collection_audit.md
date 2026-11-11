# ODAQ-Collection audit for DeepMUSHRA

Audit date: 2026-11-01. Repository baseline: `pt/data`, commit `11d1f0d`.
All downloads, code execution, measurements, and figures are on KNN. **This is
an external-benchmark audit: no ODAQ audio, ratings, or comments were used for
training, calibration, threshold fitting, or training-description generation.
No synthetic degradation algorithm or configuration was changed.**

## 1. Findings, acquisition, and licensing

The reported **17 processing classes are subset-specific method groups, not 17
independent audio artifacts**. Released metadata gives `6 + 6 + 3 + 2 = 17`.
There are 16 distinct literal group labels because DE appears twice. The two
neural groups are `speech` and `combined`, each containing the same six models.
Stereo `mix` labels denote presentation contexts rather than additional operators.

The main inventory reconciles to **688 non-reference pair observations including
anchors, or 488 excluding anchors**. It contains **18,984 individual rating rows
including references and anchors**. These are not independent source counts.

Key exceptions to simplified accounts of the dataset:

- Human language exists: **504 optional XML comments**. Coverage and quality
  differ sharply across subsets and listeners; they are not standardized captions.
- Neural speech has **13 listeners in the release versus 11 in the paper**,
  explicitly documented by the released README.
- Supplementary stereo SH trials are present but excluded by the main benchmark.
- All selected WAV headers measure 48 kHz stereo, even where source tables say
  44.1 kHz/16-bit. An original-release header confirms at least one discrepancy
  predates collection consolidation.
- References are experiment-specific comparators: notably BCC reconstructions
  for ICC/ILD and task-specific dialogue comparators for DE.

### Source pinning and selective downloads

Primary sources: [official GitHub][G], [collection dataset][D], [2026 paper][P26],
[original paper][P24], [stereo paper][PS], and [codec paper][PC]. The dataset API
reports publication date **2026-10-30**. The official repository snapshot is
`9c9c1c8f49153b40a1fe8796a811961bf221e787`.

The downloadable archive is one **3,303,086,821-byte ZIP (3.30 GB decimal)**,
with advertised MD5 `cd5ad8a4ae8a0a486fd2a1f6de155d75`. KNN had about 12 TiB
free. We did **not** download the full ZIP or verify its whole-file MD5.
Bounded HTTP 206 ranges retrieved the central directory and selected members;
complete extracted members were verified against ZIP CRCs and given SHA256 hashes.

- Inventory: 1,323 ZIP entries, including 1,044 WAVs and 93 XML files.
- First pass: 131 non-audio metadata/documentation files, about 8.85 MB of range
  traffic including block overfetch. Five PDFs and four available HTML papers
  were downloaded; the expansion paper's HTML returned 404, its PDF succeeded.
- Second pass: **29 representative pairs / 46 WAV paths / 125,301,426 WAV bytes**,
  plus two listening-instruction DOCX files. Range traffic was about 132.31 MB.
  Selection used fixed source/condition rules, never rating values.
- One additional original-release API record and a **2,048-byte original WAV
  header** were retrieved to check a format discrepancy, not its full audio ZIP.
- Figures, analysis JSON and receipts bring the inspection footprint to about
  150 MB. All external files are under the already-gitignored directory
  `data/external/odaq_collection_audit/`. No local Mac copies were created.

### Licensing and recording history

Read each subset's `_license_disclaimer.txt` and `_detailed_license.csv`.
The original and stereo packages contain CC BY, CC BY-NC, and CC0 audio;
processed files inherit the corresponding original source's license. The new
addition lists CC BY and CC BY-NC. Their disclaimers assign CC BY 4.0 to non-audio
materials. The neural README attributes the original authors and states CC BY
4.0, as on that subset's Zenodo record. Retain underlying source attribution and
resolve any conflicting restrictions before redistribution of a larger package;
`open` access is not a universal license grant.

The selected original instrumental items have CC BY or CC0 source entries;
selected Cosmos material is CC BY, while the selected new DE DLG02 mixture has
a CC BY-NC source entry. This audit is research inspection, not redistribution.
Glockenspiel's source is listed as **AAC LC 256 kbps**; clapping originated as
ALAC. A high-rate PCM container alone does not establish pristine source history.

## 2. All subsets and count reconciliation

Here N excludes references and anchors; N+A excludes references but includes
anchors. Rating-row counts include all rated conditions, including references.

| Subset | Contribution | N | N+A | Rating rows | Listeners |
|---|---|---:|---:|---:|---|
| 2024-icassp | Original artifacts and DE | 150 | 210 | 6,240 | 26 |
| 2024-aes | Additional scores of the same original material | 0 new | 0 new | 3,840 | 8 B1 + 8 B2; original pooled total 42 |
| 2025-aes | QN/SH in LR/MS and mixed presentation contexts | 102 | 154 | 2,816 | 16 main-test listeners |
| proposed-addition (2026) | ICC/ILD and new DE | 104 | 148 | 3,118 | 23 cue / 12 DE listeners |
| 2025-lanzendorfer | Six models on speech and combined content | 132 | 176 | 2,970 | 13 speech / 17 combined in release |
| **Main total** | Five subset identifiers, four audio additions | **488** | **688** | **18,984** | No single common listener pool |

The original paper's **240** means 30 trial screens x eight rated conditions,
including 30 hidden references. Excluding those gives 210; excluding 60 anchors
gives 150. Across the main collection, 200 of 688 observations are anchors.
The paper's source-count table reports 43 unique source assets; neither 488 nor
688 should be interpreted as independent recordings or distinct waveform contents.

**Supplementary stereo exception:**
`2025-aes/ODAQ_v1.5_additional_SH_items/ODAQ_1.5_additional_results.csv` contains
256 further ratings from eight listeners: four screens x eight conditions x
eight listeners. It includes ten non-anchor SHLR and ten SHMS trial conditions.
The SHLR hard-pan items already appear in the main test; the SHMS hard-pan
conditions extend main SHMS coverage from two source items to four. The official
`AES2025Loader` excludes these supplementary trials. Do not silently add them to
the 688/488 tally, or confuse reratings with newly independent source content.

**Duplicate score representation:** neural `eval_mushra.csv` and
`lanzendorfer_2025_results.csv` contain the same 2,970 ratings with different
column names and reconstructed listener IDs. Count them once. Likewise,
2024-aes adds listener judgments, not new processed audio.

## 3. Complete inventory of the 17 method groups

Counts below are exact main-release CSV counts. All groups provide a reference
and human scalar MUSHRA scores. Mechanisms and likely perceptual consequences
summarize the cited papers, not new perceptual annotations. Format codes:
**O** = original papers/source tables say 44.1/48 kHz stereo, selected reference
and target both measured 48 kHz stereo; **S** = stereo/new/codec contribution
specified as 48 kHz stereo and selected pairs confirmed. This is not an audit of
every WAV header in the archive.

| # | Subset/year | Official name | Category | N / N+A | Levels / parameters | Mechanism / expected artifacts | Reference; human MUSHRA listeners | Format |
|---|---|---|---|---:|---|---|---|---|
| 1 | 2024-icassp/2024 | **LP**: Low-pass / bandwidth limitation | Distinct controlled spectral family | 20 / 28 | 5; 5/9/10.5/12/15 kHz | Bandwidth loss / coloration | Source comparator; 42 pooled | O |
| 2 | 2024-icassp/2024 | **SH**: Spectral holes | Distinct controlled spectral family | 20 / 28 | 5; 70/50/30/20/10% holes; MS | Spectral zeroing; missing/fluctuating detail | Source comparator; 42 pooled | O |
| 3 | 2024-icassp/2024 | **UN**: Unmasked noise | Distinct tonal-to-noise family | 20 / 28 | 5; crossover 3/5/7/9/10.5 kHz | Envelope-shaped noise substitution; reduced tonality | Source comparator; 42 pooled | O |
| 4 | 2024-icassp/2024 | **PE**: Pre-echoes | Distinct controlled temporal family | 20 / 28 | 5; (NMR,block)=(10,4096)/(10,2048)/(10,1024)/(16,2048)/(16,1024) | Noise smearing around transients | Source comparator; 42 pooled | O |
| 5 | 2024-icassp/2024 | **TM**: Tonality mismatch | Distinct noise-to-tonal family | 20 / 28 | 5; crossover 3/5/7/9/10.5 kHz | Noise-like structure replaced by tonal components | Source comparator; 42 pooled | O |
| 6 | 2024-icassp/2024 | **DE**: Dialogue enhancement | Compound application and implementations | 50 / 70 | 5 separator/oracle-system conditions | Separation/remix; leakage and suppression errors | Ground-truth enhanced comparator; 42 pooled | O |
| 7 | 2025-aes/2025 | **QNLR**: Quantization noise, left/right | QN family; LR stereo variation | 20 / 28 | 5; NMR 0/6/12/18/24 dB, block1024 | Added signal-shaped noise in LR | Trial comparator; 16 | S |
| 8 | 2025-aes/2025 | **QNMS**: Quantization noise, mid/side | QN family; MS stereo variation | 20 / 28 | 5; same NMR settings | Added signal-shaped noise in MS | Trial comparator; 16 | S |
| 9 | 2025-aes/2025 | **QNmix**: Quantization noise, mixed comparison | Presentation context | 16 / 28 | 2 strengths (6/12) x LR/MS = 4 conditions | Existing LR/MS processes compared together | Trial comparator; 16 | S |
| 10 | 2025-aes/2025 | **SHLR**: Spectral holes, left/right | Repeated SH family; LR variation | 20 / 28 | 5; 70/50/30/20/10% | Spectral omissions in LR; spatial side effects | Trial comparator; 16 (+8 supplementary) | S |
| 11 | 2025-aes/2025 | **SHMS**: Spectral holes, mid/side | Repeated SH family; MS variation | 10 / 14 (+10 supplementary) | 5; 70/50/30/20/10% | Spectral omissions in MS; spatial side effects | Trial comparator; 16; extra items 8 | S |
| 12 | 2025-aes/2025 | **SHmix**: Spectral holes, mixed comparison | Presentation context | 16 / 28 | 2 strengths (30/10%) x LR/MS = 4 conditions | Existing LR/MS processes compared together | Trial comparator; 16 | S |
| 13 | proposed-addition/2026 | **ICC**: Interaural cross-correlation distortions | Distinct controlled spatial family | 28 / 42 | 4; overflow/collapse/d0.99/d0 | BCC correlation-cue changes; width/coherence | BCC reconstruction; 23 | S |
| 14 | proposed-addition/2026 | **ILD**: Interaural level-difference distortions | Distinct controlled spatial family | 28 / 42 | 4; fixed0 dB / 5 / 7 / 100 levels | BCC level-cue quantization; localization changes | BCC reconstruction; 23 | S |
| 15 | proposed-addition/2026 | **DE**: Dialogue enhancement | Repeated application; new implementations | 48 / 64 | 6 system/mask settings | MS separation and perturbed masks; mixed spectral/spatial errors | Provided task comparator; 12 | S |
| 16 | 2025-lanzendorfer/2025 | **speech**: Speech-only codec condition | Content condition, not artifact/model | 66 / 88 | 6 models, not ordered quality levels | Six codec/decoder outputs; compound changes | Provided speech comparator; 13 released, 11 paper | S |
| 17 | 2025-lanzendorfer/2025 | **combined**: Speech-with-background codec condition | Content condition, not artifact/model | 66 / 88 | Same 6 models | Same model set on combined content | Provided mixture comparator; 17 | S |

### Exact condition and implementation notes

- LP Q1–Q5: `LP50`, `LP90`, `LP105`, `LP120`, `LP150`. The two anchors are
  `LP35` and `LP70`. Exact filter coefficients, phase implementation and seeds
  are not supplied in the released metadata.
- Original SH uses `SH70_MS` through `SH10_MS`: a nominal band probability and
  MS basis, not realized masks or percent audible frames.
- Original UN/TM crossover process labels are `UN3k`...`UN10.5k` and
  `TM3k`...`TM10.5k`. They move tonal structure in opposite directions and must
  not be conflated with generic additive noise.
- PE Q1–Q5: `PE_4096_MS_NMR10`, `PE_2048_MS_NMR10`, `PE_1024_MS_NMR10`,
  `PE_2048_MS_NMR16`, `PE_1024_MS_NMR16`. Block length is in samples.
- Original DE Q1–Q5: OpenUnmix, TFC-TDF U-Net, Cocktail Fork,
  DeepFilterNet2, quantized PSM. The paper uses estimated foreground/background
  separation and 20 dB background attenuation; the comparator is the intended
  ground-truth enhanced remix. Do not substitute the original full-background
  mixture. `DE_systems_info.xls` supplies model/version provenance, not error masks.
- QN is deliberately **added noise**, rather than actual coarse quantization,
  to avoid introducing spectral holes. Names expose 1024-sample processing and
  NMR 0/6/12/18/24 for Q1–Q5. Do not assume a larger positive number means
  stronger noise or invent a sign convention for the psychoacoustic parameter.
- QNmix uses NMR6/NMR12 x LR/MS; SHmix uses 30%/10% holes x LR/MS. These are
  four comparison conditions but only two strength settings. The mono anchor
  does not create a seventh stereo artifact class.
- ICC Q1–Q4 map to `ICCn4_ILD0` (overflow), `ICCMAX_ILD0` (collapse),
  `ICC0.99_ILD0`, `ICC0_ILD0`. The d parameter is a frequency-dependent
  perceptual-distance control, not global waveform correlation.
- ILD Q1–Q4 map to `ICC0_ILDMAX` (fixed zero level difference),
  `ICC0_ILD95` (5 levels), `ICC0_ILD93` (7 levels), `ICC0_ILD0` (100 levels).
  The documented span is +/-24 dB. Codes 93/95 do not mean 93/95 dB errors.
- New DE Q1–Q6: DeepFilterNet, Bandit-v2, qmsPSM(4,2), qmsPSM(3,3),
  qmsPSM(3,5), qPSM. Tuple order is **(side bits, mid bits)**. qPSM uses
  3-bit LR masks; qmsPSM perturbs quantized MS masks with uniform noise in
  [-delta,delta]. Background attenuation is 16 dB. The XLSX documents source
  SHAs and confirms pretrained DeepFilterNet2 weights. Cocktail/MossFormer2
  entries there concern training examples, not extra main-test methods.
- Neural models: DAC, EnCodec, SNAC, Mimi are codecs; MBD and Vocos are
  alternative decoders of EnCodec latents. Paper operating points include DAC
  44.1 kHz/7.74 kbps, SNAC 44.1 kHz/2.6 kbps, EnCodec 24 kHz/6 kbps, and Mimi
  24 kHz/4.4 kbps. These are not six ordered severity levels or per-row CSV
  parameter fields. Each channel is processed separately. Native codec
  bandwidth and the observed 48 kHz output container must be distinguished.

## 4. Consolidated taxonomy of genuine perceptual families

The following is an **analyst taxonomy**, not an official claim that eight
families are mutually orthogonal perceptual dimensions.

| Controlled family | ODAQ manifestations | Main axis |
|---|---|---|
| Bandwidth loss | LP; LP anchors throughout | Missing high-frequency information / coloration |
| Spectral omissions | SH, SHLR, SHMS, SHmix | Patchy detail, fluctuations, possible birdies |
| Tonal-to-noise substitution | UN | Reduced tonal definition / noisiness |
| Noise-to-tonal substitution | TM | Artificial tonal structure |
| Added quantization-like noise | QNLR, QNMS, QNmix | Signal-shaped noise, possible spatial interaction |
| Temporal noise smearing | PE | Pre-onset noise and altered transients |
| Level-cue error | ILD | Lateral localization errors / jumps |
| Correlation-cue error | ICC | Width, coherence and image stability |
| **Compound applications, not isolated families** | DE twice; neural models in speech/combined | Multiple spectral, temporal and spatial changes |

Thus the controlled mechanisms consolidate to five original artifact families,
one added-noise family, and two spatial-cue families. DE and real codec outputs
remain compound observations. UN substitutes signal structure; QN retains the
underlying structure while adding noise. LR/MS changes stereo application of an
operator. A listening presentation context can affect judgments without
establishing a new physical transform. Repeated DE contributes different systems
and scenes without becoming a pure sixth original artifact.

## 5. Metadata, MUSHRA scores, language, and localization

### Released score schemas

Original/stereo/new CSVs use:

```text
score,method,condition,process,item,subject
```

`condition` contains Q1...Q5/Q6 or control labels; `process` gives the named
processing implementation. Mixed stereo conditions use process-like names.
Join by subset + trial item + process/condition, not Q3 alone. Preserve listener
cohort and content condition namespaces. Repeated source content occurs across
trials; split neither by processed filename nor rating row for model development.

Neural normalized CSV:

```text
score,condition,item,subject,dataset_type
```

Original neural CSV:

```text
session_id,rating_stimulus,rating_score,dataset_type,stimulus
```

The normalized README says listener IDs are reconstructed from consecutive
11-stimulus session blocks, with an explicitly documented interleaving exception.
It retains all **13 speech** listeners because the two exclusions underlying the
paper's N=11 could not be established from the released data. Combined has 17.
Do not guess exclusions to reproduce the paper; choose and disclose a protocol.

Raw XML stores experiment timing, trial names, playback counts, scores,
optional comments, and some listener survey fields. One actual entry is:

```xml
<testFile fileName="LP35.wav" plays="0" score="7.0" comment="worst" />
```

This is an example of the released representation, not a DeepMUSHRA target.
The standard label is overall scalar quality, not mandatory artifact, audibility,
frequency, timing, instrument, or perceptual-severity dimensions.

### Listener comments: available but not a caption benchmark

The 93 XML files contain **504 non-empty comments**. Of these, 503 come from six
2024-icassp listener files; one is a Mono-anchor comment in the new addition.
Original non-anchor comments number **272**, covering **148 of 150** unique
non-anchor trial/stimulus pairs. This is broad original-stimulus coverage from
few listeners. Neither “no descriptions exist” nor “complete expert captions
exist” accurately describes it.

Comments include perceptual remarks, terse judgments, comparisons to other
conditions, and reference identifications. They are optional, not standardized
or independently adjudicated, and omitted from the normalized score CSVs.
They could support a separately designed external qualitative evaluation after
adjudication and uncertainty handling. They must not be mined into training
text or used to calibrate synthetic descriptions while ODAQ remains external.
Exact source XML, trial, filename and text associations are preserved in the
ignored `sources/comment_audit.json`.

### What is missing, and what must remain uncertain

- No released per-cell corruption masks, randomized generator seeds, structured
  time/frequency localization labels or exhaustive artifact annotations were
  found in the archive or pinned benchmark code. Nominal processing settings
  exist; actual random masks do not.
- `odaq-collection-content-analysis.csv` has 68 item rows with
  `subset,item,content_type,spatial`. Its mono/stereo flag denotes the benchmark's
  distortion focus, **not the physical WAV channel count**.
- Transcripts describe speech content. License/content tables are recording
  provenance. Neither is a per-item perceptual degradation caption.
- A comment can contain qualitative timing hints without constituting a
  standardized localization annotation. Derived residual heatmaps are not
  official affected-region or audible-region ground truth.
- Official benchmark defaults exclude hidden references and support explicit
  anchor selection. Macro aggregation averages subset/method correlations in
  Fisher-z space; pooled micro correlation is a different analysis. Keep method,
  subset, content and presentation context visible in future reporting.

## 6. Representative audio and measured changes

Selection: lexicographic source + Q3 where graded; SH30/NMR12 for mixed stereo
contexts, with both LR/MS; all six codec conditions for one speech and one
combined source. No rating-based search, fitting or quality prediction was used.
Every exact reference/target association is in `sources/representative_selection.json`.

All 29 selected pairs match sample rate, channels and sample count. Raw residuals
were computed without gain fitting, resampling, or latency correction. Equal
file grids do not establish absence of processing phase/delay errors. Every
measured pair is 48 kHz stereo; most targets are PCM_24, while selected PE is
PCM_16, original DE target FLOAT, and neural/new-DE targets PCM_16.

The selected original guitar listening reference measures **48 kHz / PCM_24**,
where the detailed source table says current format 44.1 kHz / 16 bit. Checking
only the header of its counterpart in the original 10405774 release also yields
48 kHz / PCM_24. This is **not evidence of collection-introduced resampling**;
it is a documentation/header discrepancy. Use actual headers for loading.
Do not generalize this sample to a census of all original WAVs.

ICC/ILD must use the supplied BCC no-distortion `reference.wav`, not an
unprocessed master. For DE, use supplied listening comparators, not a guessed
full mixture; original and new papers describe different remix procedures.

Analysis uses channel-1 Hann STFT, FFT2048/hop512, with common -100 to -10 dB
magnitude color limits. RMS/energy use both channels. Global LR correlation,
channel balance, and side/mid ratios are **derived spatial proxies**, not the
original per-band ICC/ILD control values. Numerical changes do not establish
human quality or audibility.

Illustrative findings:

- LP105 guitar: relative residual energy about `9.96e-5`; fraction above 10 kHz
  changes from `9.38e-5` to `2.11e-5`. Small energy removal is not inaudibility.
- Selected SHLR/SHMS glockenspiel: global LR correlation moves from about
  `0.391` to `0.273` / `0.359`. This supports treating LR/MS as different
  spatial consequences of SH, not two new spectral families.
- QNLR/QNMS violin: relative residual energies both near `0.064`; similarity
  of error energy does not establish similar perception.
- ICC Q3 example: global LR correlation moves from `-0.166` to `0.744`, with
  RMS change only `-0.038 dB`. Level-only or mono-only measures can miss cues.
- Matching process names in mixed/separate contexts were **not assumed
  bit-identical**: inspected SH counterparts differ by at most `2.38e-7`, and
  QN counterparts by `6.10e-5`, in waveform amplitude. They remain the same
  named LR/MS mechanism presented in different test contexts.
- Neural MBD on selected speech changes global LR correlation from near 1 to
  about `0.905`, illustrating that independent channel synthesis can add spatial
  differences. This is not an inferred subjective quality ranking.

No human-expert audition was performed in this audit. Expected perceptual
interpretations come from the mechanisms and available listener text; the
assistant does not claim to have heard these changes.

| # | Subset / group | Item; process | Rate/channels; duration | Relative residual energy | RMS change (dB) | Figure |
|---|---|---|---|---|---|---|
| 1 | 2024-icassp / DE | `DE_CosmosLandromat_remix1_LD6`; `Cocktail_mid` | 48000/2; 10.000s | 0.05388 | -0.3283 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/01_2024-icassp_DE_Cocktail_mid.png) |
| 2 | 2024-icassp / LP | `LP_11_guitar`; `LP105` | 48000/2; 10.000s | 9.962e-05 | -0.0004328 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/02_2024-icassp_LP_LP105.png) |
| 3 | 2024-icassp / PE | `PE_27_castanets`; `PE_1024_MS_NMR10` | 48000/2; 10.008s | 0.1157 | 0.4454 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/03_2024-icassp_PE_PE_1024_MS_NMR10.png) |
| 4 | 2024-icassp / SH | `SH_04_choral`; `SH30_MS` | 48000/2; 10.000s | 0.03949 | -0.1939 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/04_2024-icassp_SH_SH30_MS.png) |
| 5 | 2024-icassp / TM | `TM_01b_trumpet`; `TM7k` | 48000/2; 11.500s | 0.008028 | -0.01402 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/05_2024-icassp_TM_TM7k.png) |
| 6 | 2024-icassp / UN | `UN_20c_accordion`; `UN7k` | 48000/2; 12.000s | 0.003755 | -0.01649 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/06_2024-icassp_UN_UN7k.png) |
| 7 | 2025-aes / QNLR | `QNLR_21_violin`; `noiseLR_1024_NMR12` | 48000/2; 10.000s | 0.06362 | 0.0003575 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/07_2025-aes_QNLR_noiseLR_1024_NMR12.png) |
| 8 | 2025-aes / QNMS | `QNMS_21_violin`; `noiseMS_1024_NMR12` | 48000/2; 10.000s | 0.06391 | -0.01007 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/08_2025-aes_QNMS_noiseMS_1024_NMR12.png) |
| 9 | 2025-aes / QNmix | `QNmix_21_violin`; `noiseLR_1024_NMR12` | 48000/2; 10.000s | 0.06362 | 0.0003578 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/09_2025-aes_QNmix_noiseLR_1024_NMR12.png) |
| 10 | 2025-aes / SHLR | `SHLR_13_glockenspiel`; `SH30_LR` | 48000/2; 10.000s | 0.223 | 0.01304 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/10_2025-aes_SHLR_SH30_LR.png) |
| 11 | 2025-aes / SHMS | `SHMS_13_glockenspiel`; `SH30_MS` | 48000/2; 10.000s | 0.2096 | 0.004262 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/11_2025-aes_SHMS_SH30_MS.png) |
| 12 | 2025-aes / SHmix | `SHmix_13_glockenspiel`; `SH30_LR` | 48000/2; 10.000s | 0.223 | 0.01304 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/12_2025-aes_SHmix_SH30_LR.png) |
| 13 | 2025-lanzendorfer / combined | `CosmosLandromat_remix1_LD6`; `dac` | 48000/2; 10.000s | 0.09601 | 0.06755 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/13_2025-lanzendorfer_combined_dac.png) |
| 14 | 2025-lanzendorfer / combined | `CosmosLandromat_remix1_LD6`; `encodec` | 48000/2; 10.000s | 0.2234 | 0.1027 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/14_2025-lanzendorfer_combined_encodec.png) |
| 15 | 2025-lanzendorfer / combined | `CosmosLandromat_remix1_LD6`; `mbd` | 48000/2; 10.000s | 0.4776 | 0.3821 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/15_2025-lanzendorfer_combined_mbd.png) |
| 16 | 2025-lanzendorfer / combined | `CosmosLandromat_remix1_LD6`; `mimi` | 48000/2; 10.000s | 0.2307 | 0.2189 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/16_2025-lanzendorfer_combined_mimi.png) |
| 17 | 2025-lanzendorfer / combined | `CosmosLandromat_remix1_LD6`; `snac` | 48000/2; 10.000s | 0.3368 | 0.103 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/17_2025-lanzendorfer_combined_snac.png) |
| 18 | 2025-lanzendorfer / combined | `CosmosLandromat_remix1_LD6`; `vocos` | 48000/2; 10.000s | 0.3157 | 0.023 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/18_2025-lanzendorfer_combined_vocos.png) |
| 19 | 2025-lanzendorfer / speech | `CosmosLandromat_remix1_FG`; `dac` | 48000/2; 10.000s | 0.06659 | 0.01148 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/19_2025-lanzendorfer_speech_dac.png) |
| 20 | 2025-lanzendorfer / speech | `CosmosLandromat_remix1_FG`; `encodec` | 48000/2; 10.000s | 0.1601 | -0.03667 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/20_2025-lanzendorfer_speech_encodec.png) |
| 21 | 2025-lanzendorfer / speech | `CosmosLandromat_remix1_FG`; `mbd` | 48000/2; 10.000s | 0.2489 | -0.1802 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/21_2025-lanzendorfer_speech_mbd.png) |
| 22 | 2025-lanzendorfer / speech | `CosmosLandromat_remix1_FG`; `mimi` | 48000/2; 10.000s | 0.1223 | -0.01922 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/22_2025-lanzendorfer_speech_mimi.png) |
| 23 | 2025-lanzendorfer / speech | `CosmosLandromat_remix1_FG`; `snac` | 48000/2; 10.000s | 0.2023 | 0.002371 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/23_2025-lanzendorfer_speech_snac.png) |
| 24 | 2025-lanzendorfer / speech | `CosmosLandromat_remix1_FG`; `vocos` | 48000/2; 10.000s | 0.2205 | -0.05093 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/24_2025-lanzendorfer_speech_vocos.png) |
| 25 | proposed-addition / DE | `DE_DLG02_p1`; `qmsPSM_4_2` | 48000/2; 9.000s | 0.08666 | 0.244 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/25_proposed-addition_DE_qmsPSM_4_2.png) |
| 26 | proposed-addition / ICC | `ICC_DLG09_amb_only`; `ICC0.99_ILD0` | 48000/2; 13.000s | 0.6207 | -0.03821 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/26_proposed-addition_ICC_ICC0.99_ILD0.png) |
| 27 | proposed-addition / ILD | `ILD_DLG02_moving_dry`; `ICC0_ILD93` | 48000/2; 16.689s | 0.007451 | -0.0002987 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/27_proposed-addition_ILD_ICC0_ILD93.png) |
| 28 | 2025-aes / SHmix | `SHmix_13_glockenspiel`; `SH30_MS` | 48000/2; 10.000s | 0.2096 | 0.004262 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/28_2025-aes_SHmix_SH30_MS.png) |
| 29 | 2025-aes / QNmix | `QNmix_21_violin`; `noiseMS_1024_NMR12` | 48000/2; 10.000s | 0.06391 | -0.01007 | [PNG](../data/external/odaq_collection_audit/analysis/spectrograms/29_2025-aes_QNmix_noiseMS_1024_NMR12.png) |


Two representative figures, retained only in ignored remote storage:

![LP105 guitar](../data/external/odaq_collection_audit/analysis/spectrograms/02_2024-icassp_LP_LP105.png)

![ICC Q3](../data/external/odaq_collection_audit/analysis/spectrograms/26_proposed-addition_ICC_ICC0.99_ILD0.png)

All 29 figures and the full feature definitions/values are in
`analysis/representative_analysis.json` and `analysis/spectrograms/`.

## 7. Comparison with DeepMUSHRA's current design

| Component | Current generator | Consequence of this audit |
|---|---|---|
| LP | Causal Butterworth/elliptic SOS; pilot 5/10/16 kHz | Same broad family, not verified identical ODAQ phase/filter design; phase/ringing can add cues |
| SH | Seeded band/run masks linked across LR; attenuation or zeroing | Related family, not verified ODAQ MS processing or lowest-SMR/bit-allocation simulation |
| UN | Tonal-band detection, smoothed power envelope, seeded noise replacement | Related substitution family, not exact ODAQ UN or a generative neural codec |
| Evidence | Actual masks, coefficients, seeds, regions, measured differences | Richer operator evidence than released ODAQ; do not invent corresponding ODAQ masks |
| Language | Technical facts plus unverified perceptual candidates | Keep audibility separate; ODAQ comments remain external evidence |
| Formats | Minimum 44.1 kHz, native rate/channels preserved | Retain this contract, check actual source history and frontend bandwidth |
| Holdouts | PE/TM excluded | Maintain across train/development operators and worked instruction examples |

## 8. Recommended small training set and artifact-selection matrix

**Current QN status: Implemented in the `pt/data` working tree.**
The Phase 1 generator is [`_quantization_like_noise()`](../src/deepmushra_data/degradations.py),
with behavior and integration tests in [`tests/test_phase1.py`](../tests/test_phase1.py).
The audit recommendation to add QN was completed during Phase 1.
This implementation uses signal-shaped additive noise controlled by waveform SNR.
Equivalence to ODAQ's psychoacoustic NMR processing remains unverified.


**Target five families: LP + SH + UN + added signal-shaped noise + one controlled
stereo width/coherence-error family.** This adds two dimensions instead of
imitating every reported method group. No new algorithm is implemented by this
audit; confirm the decisions with the team first.

1. **QN-like signal-shaped noise — Implemented.** It adds noise without replacing
   tonal content. Record the exact added waveform, seed, envelope, level/SNR,
   support and channel coupling. A basic generator is simple; faithful NMR
   requires a defined masking model and should not be claimed without one.
   Build/tune it only on independent clean sources. Avoid look-ahead noise
   spreading before transients, which would compromise the PE holdout.
2. **Add one spatial family when the model retains stereo evidence.** Bounded
   M/S side gain is an economical width-error operator. Record channel basis,
   side gain, region, exact transform and measured cue proxies. It is not BCC
   ICC manipulation; width scaling may change both level and correlation cues.
   If stereo is lost in the frontend, defer this fifth family and identify
   spatial tests as out-of-domain, rather than train on invisible labels.
3. Treat LR/MS SH/QN as **variants** with a `channel_basis` field, not new
   artifact families. Preserve independent perceptual validation of subtle
   settings: parameter tiers still do not become perceptual severity labels.

Ranks below are engineering judgments, **not derived from ODAQ ratings**.
Novel diversity is relative to LP/SH/UN; H difficulty means more implementation
work. All candidates need content-sensitive audibility validation.

| Candidate | Novel diversity | Difficulty | Relevance | Objective metadata / description suitability | PE/TM overlap risk | Recommendation |
|---|---|---|---|---|---|---|
| LP/SH/UN refinement | Existing core | M | H | Excellent operator evidence; perceptual text still unverified | Incidental temporal side effects | Retain |
| Added signal-shaped noise (QN) | M-H | L-M; H for faithful psychoacoustics | H | Exact added signal, envelope, support and strength; clear noisiness candidate | Moderate PE confound if smeared around attacks | **Implemented** |
| Stereo width/coherence error | H | L-M | H for stereo codecs | Exact M/S transform, timing and cue proxies; width/stability candidate | Low direct overlap; overlaps ICC/ILD axes | **Add second if stereo observable** |
| ILD quantization / cue error | H | M | H for stereo codecs | Known per-band quantizer and cue errors; localization candidate | Low PE/TM overlap; overlap with selected spatial family | Alternative spatial operator, not sixth default |
| LR/MS SH/QN variants | L as a new family | L-M | H | Basis/coupling metadata; same underlying descriptions | Same families; noise timing matters | Variation only |
| Clipping / saturation | H | L | M for this codec focus | Transfer curve, clipped support and error; harshness candidate | Harmonics differ from TM mechanism but semantic overlap exists | Optional later breadth; no isolated ODAQ class |
| Gain / dynamics errors | M | L-M | M | Exact gain/envelope; possible quality shortcut | Low direct overlap | Later controls/robustness |
| Echo / reverberation / temporal blur | H | M | M | Known impulse response; audible extent less direct | Moderate/high temporal overlap with PE | Defer |
| DE / separation errors | H, compound | H | H for broader audio | Requires trusted stems and masks; model identity is not exact artifact truth | Can include held-out-like effects | Future compound-effects study |
| Real neural codecs | H, compound | M-H | H | Model/bitrate known, exact impairment labels generally unknown | Uncontrolled PE/TM-like artifacts | External transfer first |
| Explicit PE or TM synthesis | H | M-H | H | Could support synthetic evidence, but violates current holdout | Direct contamination | **Exclude from train/development** |

The compact set spans bandwidth, omissions, substitution, added noise and
spatial image changes. It does not claim all coding artifacts are covered.
All severity settings and candidate descriptions must be calibrated/validated
on non-ODAQ material; no ranges or thresholds should be fit to this audit's
measured ODAQ examples.

## 9. Recommended zero-shot evaluation protocol

- **Primary held-out families: PE and TM.** Exclude explicit operators, synthetic
  instances and descriptions-as-training-examples across project adaptation.
  Permit open descriptions of unknown effects instead of forcing only trained
  class names. Absence from model/encoder pretraining cannot be established.
- **Seen-family external transfer:** LP/SH/UN and later QN remain external in
  source content and implementation even when family names are seen.
- **Spatial transfer:** ICC/ILD are implementation-transfer tests if related
  width/cue errors are trained. Claim unseen-family novelty only under a
  documented exclusion of the relevant spatial mechanisms.
- **Compound transfer:** DE and neural outputs are mixed-effects external tests,
  not clean single-artifact zero-shot labels. Report by subset, content, model
  and presentation context; six codecs are not a severity ladder.
- Freeze generation/evaluation decisions using independent development data.
  Keep ODAQ audio, comments and ratings out of SFT, preference targets,
  worked test prompts, paraphrase supervision and quality-bin calibration.
- Exclude source productions, stems, crops and alternate encodings related to
  ODAQ from clean training corpora using source URLs/provenance, not hashes alone.
  **Never use the recursive generator on `data/` or this external audit folder.**
  This audit does not add an automatic source-overlap checker.

## 10. Limitations and team decisions

1. Approve QN-like noise plus one spatial family, or temporarily retain four
   timbral families until full-band/stereo model observability is confirmed.
2. Define holdouts at the mechanism/perceptual level. QN and PE share noise
   ingredients; accidental smearing and unknown real-codec errors weaken strong
   novelty claims. Explicitly state permitted overlap.
3. Resolve model frontend bandwidth: 16 kHz input discards evidence above 8 kHz,
   and mono cannot preserve all inter-channel cues. Preserve high-rate masters.
4. Choose the neural listener protocol before evaluation. Released 13/17 is
   reproducible; the paper's 11-speech exclusion cannot be guessed. Namespace
   subjects and do not double-count the two neural CSV representations.
5. Decide whether/how to use optional comments in external qualitative evaluation.
   Their broad original-stimulus coverage is useful, but relative wording,
   few commenting listeners and missing other subsets require adjudication.
   They are not automatic BLEU references or training templates.
6. Distinguish exact operator support, derived signal changes and human labels.
   A nominal probability or residual peak cannot justify audible coverage or
   “most noticeable at 7.6 s.” No official TF masks were found.
7. This audit sampled headers and generated plots; it did not listen, inspect
   every audio file, or certify licenses for redistribution. Format-documentation
   discrepancies, source codec history and repeated recordings remain limitations.
8. Source-system XLS/XLSX provenance is not the artifact generator or random mask.
   Many exact generation details are unavailable; do not claim algorithm equivalence.
9. Keep references/anchors, supplemental trials, source reuse and test context
   explicit when counting samples or aggregating evaluation scores.
10. After agreement, design additions against independent recordings and explicit
    evidence schemas, then run a separate listening pilot before scaling. No new
    augmentation algorithms or training settings were implemented here.

## 11. Exact evidence and reproduction

Evidence paths below are under the ignored remote directory
`data/external/odaq_collection_audit/`:

| Evidence | Relative path |
|---|---|
| Dataset API, release size, advertised checksum | `sources/zenodo_23425817.json` |
| Full ZIP member inventory | `sources/archive_inventory.json` |
| Download URLs and paper hashes | `sources/download_receipt.json` |
| Metadata files, CRCs, SHA256, range traffic | `sources/metadata_extraction_receipt.json` |
| Audio paths, hashes and range receipt | `sources/audio_extraction_receipt.json` |
| All 17 groups and exact pair associations | `sources/method_inventory.json`, `sources/pair_inventory.json` |
| Systematic representative selection | `sources/representative_selection.json` |
| CSV/XML fields and comment coverage | `sources/score_schemas.json`, `sources/xml_schema_summary.json`, `sources/comment_audit.json` |
| Original-release header comparison | `sources/original_header_comparison.json` |
| Pinned official loaders and aggregation code | `official_repository/benchmark/` |
| Original extracted metadata and audio | `release/odaq-collection/` |
| All 29 measurements and plots | `analysis/representative_analysis.json`, `analysis/spectrograms/` |
| Reproduction helpers | `tools/range_zip.py`, `inventory_metadata.py`, `fetch_representatives.py`, `analyze_representatives.py` |

Direct released evidence, relative to extracted `odaq-collection/`:

- `2024-icassp/ODAQ_listening_test/ODAQ_results.csv`: six original labels,
  6,240 rows. Its XML siblings supply optional comments omitted from CSV.
- `2024-aes/Cohort_B1_results.csv`, `Cohort_B2_results.csv`: 1,920 rows each.
- `2025-aes/ODAQ_v1.5_listening_test/ODAQ_1.5_results.csv`: six stereo/context
  groups, 2,816 rows, main SHMS restricted to two items.
- `2025-aes/ODAQ_v1.5_additional_SH_items/ODAQ_1.5_additional_results.csv`:
  256 supplementary rows excluded from the main benchmark.
- `proposed-addition/odaq_binauralcue_listening_test/odaq_binauralcue_results.csv`:
  ICC/ILD, 2,254 rows, 28 non-anchor pairs each.
- `proposed-addition/odaq_binauralcue_de_listening_test/odaq_binauralcue_de_results.csv`:
  new DE, 864 rows, 48 non-anchor pairs.
- `2025-lanzendorfer/lanzendorfer_2025_results.csv` and `README.md`: two content
  conditions and the explicit 13-versus-11 speech-listener discrepancy.
- Per-subset license disclaimers/CSVs, `DE_systems_info.xls` and
  `DE_systems_info.xlsx`, `odaq-collection-content-analysis.csv` and
  `subset_references.csv`: license, provenance, systems and content evidence.

Recompute on KNN from the checkout after sourcing `../env.sh`:

```bash
python data/external/odaq_collection_audit/tools/inventory_metadata.py
python data/external/odaq_collection_audit/tools/analyze_representatives.py
```

The inventory asserts 17 groups, 488 non-anchor pairs and 688 including anchors.
Analysis uses no rating values. External data/figures are not committed; the only
intended tracked change is this report. No commit or push was performed.

[G]: https://github.com/Fraunhofer-IIS/ODAQ/tree/9c9c1c8f49153b40a1fe8796a811961bf221e787
[D]: https://doi.org/10.5281/zenodo.23425817
[P26]: https://arxiv.org/abs/2610.37959
[P24]: https://arxiv.org/abs/2401.00197
[PS]: https://arxiv.org/abs/2512.14259
[PC]: https://arxiv.org/abs/2511.19734

Additional primary sources: [expanded original analysis](https://arxiv.org/abs/2504.00742),
[original release](https://doi.org/10.5281/zenodo.10405774),
[additional original ratings](https://doi.org/10.5281/zenodo.13377284),
[stereo release](https://doi.org/10.5281/zenodo.17162670),
[codec release](https://doi.org/10.5281/zenodo.18184035),
[pinned loaders](https://github.com/Fraunhofer-IIS/ODAQ/blob/9c9c1c8f49153b40a1fe8796a811961bf221e787/benchmark/dataloaders.py).
