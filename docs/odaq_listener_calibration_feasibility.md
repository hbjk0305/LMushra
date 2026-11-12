# ODAQ listener calibration feasibility and proposed split protocol

**Status — feasibility analysis and proposed partitions only.** Analysis completed
on KNN using the downloaded ODAQ-Collection release, Zenodo record 23425817.
The analysis computed coverage, reference-based QC diagnostics and confidence
intervals. No severity mapping was fitted, no calibration was applied to synthetic
data, and the original benchmark files were preserved.

## 1. Assessment

A cohort-stratified approximately 20% calibration split is feasible as a data
partition. The proposed primary assignment has **12 calibration and 46 evaluation
study-scoped listener IDs** across the original and stereo main tests.
Original LP/SH/UN cells have **nine calibration listeners** after pooling the
original and follow-up cohorts. QN and stereo SH cells have **three**.
This provides complete coverage of the administered parameter settings, with
limited precision and very little independent source diversity.

For an initial mapping with a desired uncertainty of roughly ±5–10 MUSHRA points,
a single 20% split is particularly weak for QN and stereo SH. The observed
pointwise interval widths also warrant caution for original SH and UN. An
independent listening study of the actual synthetic operators and intended mono
playback is the preferred route to perceptual calibration. Repeated grouped
20%/80% evaluation on ODAQ can serve a separately declared benchmark-adaptation
experiment.

## 2. Exact listener counts and experimental coverage

Counts below use unique listener IDs within each released study/cohort.
LP refers to its dedicated Q1–Q5 trials in this table. Low-pass anchors are
accounted for separately.

| Cohort | Dedicated LP | SH | UN | QN |
|---|---:|---:|---:|---:|
| Original A, German laboratory | 14 | 14 | 14 | 0 |
| Original A, US laboratory | 12 | 12 | 12 | 0 |
| AES follow-up B1 | 8 | 8 | 8 | 0 |
| AES follow-up B2 | 8 | 8 | 8 | 0 |
| **Original material pooled** | **42** | **42** | **42** | **0** |
| 2025 stereo main test | 0 | 16 | 0 | 16 |
| **Main studies, summed study-scoped IDs** | **42** | **58** | **42** | **16** |
| Supplementary stereo SH test | 0 | 8 | 0 | 0 |
| **Including supplement** | **42** | **66** | **42** | **16** |

These columns overlap because the same listeners rated several artifacts.
There are **58 main study-scoped listener records** in this analysis and eight
supplementary records, rather than a sum of the artifact-column counts.
The other ODAQ subsets do not add isolated LP/SH/UN/QN experimental panels.

The 2025 main test covers SHLR, SHMS, SHmix, QNLR, QNMS and QNmix. SHMS contains
only two source items in the main test. The supplement contains SHLR and SHMS on
two hard-panned items. The absence of those SHMS hard-pan cells in the main test
is structural design coverage. Every main-test listener completed the same
administered cells.

Original A is the post-screened cohort of 26, the two AES cohorts each contain
eight, and the stereo main panel contains 16. B1 and B2 differ in how anchors
were explained during training. The stereo panel's XML dates reveal nine
D-coded sessions in April–May 2024 and seven E-coded sessions in July 2025,
including the literal code `EO13`. These are useful strata for the proposed
split. We preserve the released code rather than silently changing its spelling.

### Low-pass anchors

The 3.5 and 7 kHz anchors add LP-related observations in other artifact contexts.
Across all trial types in these input tables, they contribute **3,288 ratings**:
2,520 from the original 42 listeners, 704 from the 2025 main test, and 64 from the
supplement. Thus LP-related anchor ratings involve 58 main study-scoped IDs, or
66 including the supplement.

These counts must not inflate the dedicated LP calibration table. Anchors were
rated alongside different artifact families, including families outside this
analysis. Their role and listening context affect scale use. The primary proposal
excludes anchors, references and mono anchors from calibration-target counts,
while using references for QC diagnostics.

## 3. Completeness and quality-control evidence

The full released row grids are:

| CSV / cohort | Listeners | Rows per listener | Total rows | Missing cells | Duplicate keys | Invalid scores |
|---|---:|---:|---:|---:|---:|---:|
| Original A | 26 | 240 | 6,240 | 0 | 0 | 0 |
| AES B1 | 8 | 240 | 1,920 | 0 | 0 | 0 |
| AES B2 | 8 | 240 | 1,920 | 0 | 0 | 0 |
| Stereo main | 16 | 176 | 2,816 | 0 | 0 | 0 |
| Supplementary SH | 8 | 32 | 256 | 0 | 0 | 0 |

A rating key is `listener + method + item + condition + process`.
Every listener has the complete Cartesian product with their panel's observed
condition grid. All scores are finite and within 0–100. All Q1–Q5 cells required
by the respective dedicated trial designs are represented. The mixed trials
deliberately contain fewer levels.

**12,896 CSV scores were cross-checked against XML scores, with zero differences.**
The 58 main XML listener records are marked complete. The supplementary panel
has CSV data but no corresponding individual XML records in this release.
XML filenames prepend the source name in the stereo subset. The Dream Home
source uses `dream_home_14-24` in WAV filenames and `dream_home_14_24` in trial
names. The analysis normalizes these filename conventions for the cross-check
without editing either source.

The original paper reports 28 initial participants, with one from each laboratory
excluded for rating hidden references below 90 in more than 15% of trials.
The retained counts are 14 German and 12 US listeners. Excluded score records
are unavailable in the released post-screened table.

The expansion reports 42 listeners after screening. It does not establish
additional rejected-listener counts for B1/B2 in the released tables. The stereo
paper reports 16 completed main tests and an eight-listener follow-up, without
a separately recoverable pre-screened rejection roster. We therefore report the
retained sample and documented exclusions explicitly.

As a diagnostic, the original reference rule was evaluated on every retained
listener's whole released test. **All retained records pass**. The maximum
reference-below-90 counts are 4/30 for A, 3/30 for B1, 3/30 for B2, 3/22 for
the stereo main panel, and 0/4 for the supplement. Anchor-order reversals are
listed in `qc_diagnostics.csv` as diagnostics. No additional exclusions were
made. Changing QC after inspecting model or calibration outcomes would introduce
another selection step and would need a separately specified analysis.

## 4. Proposed reproducible 20% / 80% protocol

### Namespaces, cohorts and possible repeat participants

Each participant record has a study-scoped ID. Examples are
`2024-icassp::DEID10`, `2024-aes/B1::D004` and `2025-aes::D004`.
The original raw CSV subject string is retained in the split table.
A code match across studies is not used as proof of global identity.

There are **nine candidate links** between the AES D-codes and the later stereo
D-codes. The matching codes are D001, D002, D004, D005, D010, D011, D016,
D018 and D019. Both sets originate from the BSU studies, and their session dates
are compatible with repeat participation. The available release contains no
confirmed cross-study identity crosswalk.

As a conservative assignment constraint, each matching pair is placed on the
same side of the split. The nine links remain explicitly marked unconfirmed.
This gives 49 main assignment blocks, including ten calibration blocks, while
retaining all 58 study-scoped participant records. These are analysis blocks
whose purpose is preventing possible crossover. Confirmation from the authors
would be required to claim distinct-person separation across studies.
The supplementary L1–L8 codes cannot be linked to other panels from the release
and are retained as a separate exploratory panel.

### Counts and exact assignment

The seed is **20261110** and the protocol tag is
`odaq-listener-feasibility-v1`.

| Stratum | Available IDs | Proposed calibration | Proposed evaluation | Calibration fraction |
|---|---:|---:|---:|---:|
| Original A, German laboratory | 14 | 3 | 11 | 21.4% |
| Original A, US laboratory | 12 | 2 | 10 | 16.7% |
| 2024 AES cohort B1 | 8 | 2 | 6 | 25.0% |
| 2024 AES cohort B2 | 8 | 2 | 6 | 25.0% |
| 2025 main, D-code / April–May 2024 sessions | 9 | 2 | 7 | 22.2% |
| 2025 main, E-code / July 2025 sessions | 7 | 1 | 6 | 14.3% |
| Supplementary SH panel | 8 | 2 | 6 | 25.0% |

The main allocation is **12/58 = 20.69%** calibration and **46/58 = 79.31%**
evaluation. For original material it is 9/42 versus 33/42; for the stereo main
test it is 3/16 versus 13/16. The optional supplement has a separate 2/8 versus
6/8 proposal, making 14/66 versus 52/66 across all study-scoped records.

Algorithm:

1. Form namespaced listener keys and cohort strata using metadata only.
2. Rank candidate IDs with SHA256 of
   `protocol_tag|seed|namespaced_listener_id`. Choose the first three A-DE,
   two A-US, one later stereo E-code, and two supplementary IDs.
3. Enumerate the 28 choices of two B1 listeners and the 28 choices of two B2
   listeners. Keep the combinations containing exactly two codes among the nine
   candidate-returning D listeners. There are **318** valid combinations.
4. Sort the four chosen namespaced IDs, join them with `|`, hash with the same
   tag/seed prefix, and select the combination with the smallest digest.
   Assign the two corresponding stereo D-code records to calibration as well.
5. Put every remaining record into evaluation. All conditions, artifacts,
   sources, repeated stimuli and listening contexts for a listener follow that
   role. No score, outcome or observed interval width enters selection.

| Stratum | Proposed calibration IDs |
|---|---|
| A_DE | `2024-icassp::DEID10`, `2024-icassp::DEID2`, `2024-icassp::DEID256` |
| A_US | `2024-icassp::USLA12`, `2024-icassp::USLG03` |
| B1 | `2024-aes/B1::D004`, `2024-aes/B1::D009` |
| B2 | `2024-aes/B2::D005`, `2024-aes/B2::D015` |
| 2025_D | `2025-aes::D004`, `2025-aes::D005` |
| 2025_E | `2025-aes::E009` |
| supplement | `2025-aes-supp::L3`, `2025-aes-supp::L7` |

The full calibration/evaluation membership is in
[`proposed_listener_split.csv`](../outputs/odaq_listener_calibration_feasibility_v1/proposed_listener_split.csv).

The 2025 E stratum has only one calibration listener. A prespecified alternative
with two D and two E listeners would use 4/16 = 25% and allow within-stratum
variance estimation. That would remain a small sample. Do not search seeds or
subsets for favorable quality differences or narrower intervals.

The supplement should stay separate from the primary analysis. Its limited
sources, selective follow-up design, and unresolved identities make simple
pooling with main-test votes inappropriate.

## 5. Calibration rating counts by artifact, level and recording

The primary counts include only non-anchor experimental conditions:

| Artifact | Main available ratings | Proposed calibration ratings | Evaluation ratings |
|---|---:|---:|---:|
| LP | 840 | 180 | 660 |
| SH, original plus stereo main | 1,576 | 318 | 1,258 |
| UN | 840 | 180 | 660 |
| QN | 896 | 168 | 728 |
| **Total** | **4,152** | **846** | **3,306** |
| Supplementary SH, separate | 160 | 40 | 120 |

QN has no original-2024 counterpart. The SH total contains multiple bases and
presentation contexts. The supplement adds two SHMS hard-pan sources and further
SHLR judgments on hard-pan sources already covered by the main test.

### Per source, quality level and channel basis

| Trial group | Levels represented | Calibration ratings per source / level / basis | Calibration ratings across sources at each level | Total calibration ratings |
|---|---|---:|---:|---:|
| Original LP | Q1–Q5 | 9 | 36 | 180 |
| Original SH | Q1–Q5 | 9 | 36 | 180 |
| Original UN | Q1–Q5 | 9 | 36 | 180 |
| SHLR main | Q1–Q5 | 3 | 12 | 60 |
| SHMS main | Q1–Q5 | 3 | 6 | 30 |
| SHmix main | Q3, Q5; LR and MS | 3 | 24 | 48 |
| QNLR main | Q1–Q5 | 3 | 12 | 60 |
| QNMS main | Q1–Q5 | 3 | 12 | 60 |
| QNmix main | Q2, Q3; LR and MS | 3 | 24 | 48 |
| SHLR supplement | Q1–Q5 | 2 | 4 | 20 |
| SHMS supplement | Q1–Q5 | 2 | 4 | 20 |

For mixed trials, the across-source column combines both LR and MS at that level;
there are six calibration ratings per source/level across both bases. These
multiple observations come from the same three listeners.

The parameter labels in the release are:

| Artifact | Q1 | Q2 | Q3 | Q4 | Q5 |
|---|---:|---:|---:|---:|---:|
| LP cutoff, kHz | 5 | 9 | 10.5 | 12 | 15 |
| SH hole probability, % | 70 | 50 | 30 | 20 | 10 |
| UN crossover, kHz | 3 | 5 | 7 | 9 | 10.5 |
| QN released NMR label, dB | 0 | 6 | 12 | 18 | 24 |

These are the exact ODAQ parameter labels. In particular, its QN NMR setting is
a different control variable from the synthetic generator's waveform SNR.

The source-level inventory below makes the small content pool explicit.
Counts combine the administered experimental levels and bases within each row.

| Artifact | Trial group | Released source key | Calibration ratings | All available ratings |
|---|---|---|---:|---:|
| LP | LP | 11_guitar | 45 | 210 |
| LP | LP | 23_jazz | 45 | 210 |
| LP | LP | AmateurOnPurpose | 45 | 210 |
| LP | LP | CreatureFromTheBlackjackTable | 45 | 210 |
| QN | QNLR | 21_violin | 15 | 80 |
| QN | QNLR | CosmosLandromat_remix3_hardpan_LD3 | 15 | 80 |
| QN | QNLR | dream_home_14_24 | 15 | 80 |
| QN | QNLR | female_speech_music_1_hardpan_LD0 | 15 | 80 |
| QN | QNMS | 21_violin | 15 | 80 |
| QN | QNMS | CosmosLandromat_remix3_hardpan_LD3 | 15 | 80 |
| QN | QNMS | dream_home_14_24 | 15 | 80 |
| QN | QNMS | female_speech_music_1_hardpan_LD0 | 15 | 80 |
| QN | QNmix | 21_violin | 12 | 64 |
| QN | QNmix | CosmosLandromat_remix3_hardpan_LD3 | 12 | 64 |
| QN | QNmix | dream_home_14_24 | 12 | 64 |
| QN | QNmix | female_speech_music_1_hardpan_LD0 | 12 | 64 |
| SH | SH | 04_choral | 45 | 210 |
| SH | SH | 13_glockenspiel | 45 | 210 |
| SH | SH | AmateurOnPurpose | 45 | 210 |
| SH | SH | CreatureFromTheBlackjackTable | 45 | 210 |
| SH | SHLR | 13_glockenspiel | 15 | 80 |
| SH | SHLR | AmateurOnPurpose | 15 | 80 |
| SH | SHLR | CosmosLandromat_remix3_hardpan_LD3 | 15 | 80 |
| SH | SHLR | female_speech_music_1_hardpan_LD0 | 15 | 80 |
| SH | SHMS | 13_glockenspiel | 15 | 80 |
| SH | SHMS | AmateurOnPurpose | 15 | 80 |
| SH | SHmix | 13_glockenspiel | 12 | 64 |
| SH | SHmix | AmateurOnPurpose | 12 | 64 |
| SH | SHmix | CosmosLandromat_remix3_hardpan_LD3 | 12 | 64 |
| SH | SHmix | female_speech_music_1_hardpan_LD0 | 12 | 64 |
| UN | UN | 20c_accordion | 45 | 210 |
| UN | UN | 21_violin | 45 | 210 |
| UN | UN | AmateurOnPurpose | 45 | 210 |
| UN | UN | CreatureFromTheBlackjackTable | 45 | 210 |

The complete machine-readable cross-tabulation is
[`coverage_by_condition_and_cohort.csv`](../outputs/odaq_listener_calibration_feasibility_v1/coverage_by_condition_and_cohort.csv).
It gives source, artifact, method, parameter/process, Q level, basis, presentation
context, cohort, available ratings, and proposed calibration/evaluation counts.
Thus all source/level counts can be recovered without pooling distinct contexts.

## 6. Precision and coverage assessment

### Estimands and assumptions

A per-condition estimate uses one rating per selected listener for a fixed
source, processing setting, channel basis and presentation context. The primary
precision diagnostic is the two-sided, pointwise Student-t interval

`mean ± t(0.975, n-1) × sample_standard_deviation / sqrt(n)`.

Intervals are reported in their unbounded statistical form; clipping them to
0–100 would hide uncertainty. They are approximate at these sample sizes,
especially n=2 or 3, and are not simultaneous intervals across all conditions.
The calculations use only the fixed candidate calibration subset after its
score-independent assignment.

For the original pooled material, a second estimator uses the full released
cohort weights `N_h/N` for A-DE, A-US, B1 and B2. Its variance is estimated as
`sum_h (N_h/N)^2 × s_h^2/n_h`, with a Welch–Satterthwaite t approximation.
A different target listener population would require an explicitly different
weighting choice. No finite-population correction is applied because the intended
claim concerns future listeners.

The three-listener stereo split has n=1 in its later E cohort. An unbiased
within-stratum variance estimate is unavailable there. Its pooled t intervals
are descriptive diagnostics with cohort-homogeneity assumptions. The report does
not substitute a zero variance for that missing estimate.

### Actual interval widths in the proposed split

The table gives median [minimum, maximum] half-width across source/parameter
cells, in MUSHRA points. The ±5 and ±10 targets are illustrative planning
thresholds chosen for this feasibility assessment.

| Panel / method | Calibration n per cell | Diagnostic 95% half-width, median [min,max] | Cells with half-width ≤10 | Cohort-weighted median half-width |
|---|---:|---|---:|---|
| Original pooled / LP | 9 | 8.46 [1.27, 13.85] | 14/20 | 12.73 |
| Original pooled / SH | 9 | 15.44 [10.02, 22.15] | 0/20 | 17.52 |
| Original pooled / UN | 9 | 12.56 [4.06, 19.12] | 5/20 | 15.97 |
| 2025 main / QNLR | 3 | 47.37 [3.79, 81.27] | 2/20 | Undefined for E stratum n=1 |
| 2025 main / QNMS | 3 | 32.68 [1.43, 84.03] | 5/20 | Undefined for E stratum n=1 |
| 2025 main / QNmix | 3 | 43.58 [6.25, 78.92] | 1/16 | Undefined for E stratum n=1 |
| 2025 main / SHLR | 3 | 30.99 [10.34, 93.29] | 0/20 | Undefined for E stratum n=1 |
| 2025 main / SHMS | 3 | 20.83 [10.83, 60.87] | 0/10 | Undefined for E stratum n=1 |
| 2025 main / SHmix | 3 | 30.55 [14.97, 63.74] | 0/16 | Undefined for E stratum n=1 |
| Supplement / SHLR | 2 | 54.00 [12.71, 158.83] | 0/10 | Same single-panel estimate |
| Supplement / SHMS | 2 | 28.59 [0.00, 76.24] | 2/10 | Same single-panel estimate |

For original LP, only 4/20 cells meet a ±5-point diagnostic target; original SH
has 0/20 and UN 1/20. The cohort-weighted intervals are generally wider. The
largest original UN weighted half-width is **78.01 points**, reflecting unstable
variance estimation in tiny cohort samples.

The QNLR, QNMS and QNmix median diagnostic half-widths are approximately
**47.37, 32.68 and 43.58 points**. Few cells meet even a ±10-point planning target.
With three listeners, a smooth parameter curve would be strongly dependent on
modeling assumptions. Fitting such a curve would not create additional independent
human observations.

Averaging sources and, within mixed trials, bases *within each listener* retains
n=9 or n=3 independent listener observations. This can estimate an average for
the finite tested source set. It does not justify treating 36 LP votes at one
level as 36 independent listeners. The source-averaged original LP half-widths
range about 1.04–11.44 points across levels; QNLR still ranges about 8.70–55.58.
Detailed results are in
`precision_after_averaging_sources.csv`. Four tested source excerpts cannot
establish generalization to arbitrary speech/music content.

Bootstrap resampling would need to resample whole listener response vectors,
within strata and respecting candidate alias blocks. With n=1–3 per stratum,
its apparent stability can be misleading. Repeated sources, levels and channel
bases must remain clustered. At n=2, even a zero estimated half-width can result
from two equal ratings and should not be interpreted as certainty.

![Per-condition calibration precision](../outputs/odaq_listener_calibration_feasibility_v1/calibration_precision.png)

**Coverage conclusion.** Original LP/SH/UN cover five discrete settings on four
sources each. QN covers five settings in separated LR/MS trials, but only two
levels in mixed trials. The proposed subset is adequate for an exploratory
coverage check and coarse tendencies. It is too sparse for a well-supported,
content-conditional five-level QN quality mapping or a uniformly precise
per-source mapping. Original SH/UN also need greater precision for a tight
severity calibration.

## 7. Dependencies and risks

### Repeat participants

Namespacing prevents accidental merging of unrelated IDs. It does not establish
different-person independence across studies. The nine candidate D links are
blocked together in this proposal, but renamed participants and overlap with
the L-coded follow-up cannot be resolved. A confirmed crosswalk or a narrowly
within-study claim is necessary for a strict participant-held-out interpretation.

### Repeated sources and stimuli

The original 42 listeners evaluated the same audio conditions. A listener split
therefore evaluates agreement with new raters on familiar signals and parameters.
It does not measure generalization to new recordings.

Waveform comparisons found 28 matched source/process pairs across mixed and
separated stereo contexts, plus ten original-SH versus stereo-SHMS pairs.
None is bit-identical as decoded PCM. However, median relative waveform errors
are small for mixed/separated pairs; after allowing a single amplitude scalar,
the median is approximately **0.000311**. Original/stereo SH pairs differ in
gain, with median residual error after a scalar adjustment approximately
**1.43e-6**. These comparisons support close stimulus reuse despite file/level
differences. They must not be counted as independent source recordings.
All pair measurements are retained in `repeated_stimuli.json`.

### Listening context and cohort scale use

B1 and B2 received different anchor explanations. The expansion paper documents
a shift in anchor grading and scale use. The stereo study also contrasts LR/MS
presented separately against both presented in the same trial. Context can alter
judgments of the same or closely related processing. Keep cohort, method, basis
and presentation context in any future mapping. The mixed condition is not
an independent degradation operator.

### Stereo-to-mono transfer

The human scores describe the released stereo playback. The current DAC training
path consumes 44.1 kHz mono, while the baseline and EnCodec paths use still lower
sample rates. Downmixing can change noise correlation, cancel side components,
alter spatial errors and change audibility. A mean stereo score cannot be assumed
to be a validated quality label for its mono export. A mono evaluation against
these scores measures an additional cross-format transfer and needs to be
reported explicitly. The spatially manipulated stereo conditions are especially
sensitive to this mismatch.

### Operator/parameter mismatch

The synthetic LP, SH, UN and QN implementations approximate related artifact
mechanisms with different details. Original LP is sampled at cutoffs that differ
from our 5/10/16-kHz pilot. ODAQ UN varies crossover while the pilot holds
crossover at 7 kHz and sweeps replacement strength. ODAQ QN uses psychoacoustic
NMR, whereas the current generator sets waveform SNR. ODAQ SH includes MS
processing and its realized masks differ from our generator's linked selections.
An ODAQ parameter-to-quality relationship would require a transfer hypothesis
before being used to label synthetic settings. Direct numerical substitution
would have no established validity.

### Benchmark contamination and held-out effects

The README currently reserves ODAQ for external evaluation and excludes its
ratings from severity calibration. This feasibility task examines a possible
future change to that policy. The observed CI diagnostics are exploratory
analyses of the published benchmark. They are not a fitted severity mapping.

If ODAQ ratings later select generator strengths, quality categories, thresholds,
captions, model objectives, hyperparameters or decision rules, ODAQ has become
a calibration/development resource for that experiment. Holding out listeners
does not undo exposure to the same signals or artifact parameters.

The correct future claim would explicitly state **ODAQ-calibrated,
listener-held-out evaluation**, with the exact cohorts and any unresolved
identity links. A separate claim of source generalization requires recording-
and production-level separation, including repeated excerpts, stems and remixes.
PE/TM target ratings must remain outside a proposed LP/SH/UN/QN mapping.
Shared reference material can still limit content novelty of PE/TM tests.

## 8. Recommendation and proposed validation strategy

| Approach | What it can establish | Main limitation | Recommendation |
|---|---|---|---|
| One cohort-stratified 20%/80% split | Rater transfer on the same released recordings and conditions | QN n=3; tiny cohort cells; sensitivity to selected listeners | Exploratory diagnostic |
| Repeated constrained 20%/80% splits | Sensitivity to calibration-panel selection | Reuses the benchmark and yields correlated repeated evaluations | Secondary ODAQ adaptation study |
| Independent listening study | Calibration of actual synthetic operators under intended playback | Requires new recordings, listeners and study work | Preferred primary calibration route |

For an ODAQ adaptation study, predeclare a fixed list of seeds before fitting.
Apply the same cohort quotas and candidate-link constraints on every repetition.
Use whole listeners as groups and report the distribution across splits.
Preserve presentation contexts and evaluate all held-out conditions for each
listener. A reversed five-fold scheme with about 20% calibration per round can
be considered, but small strata make folds unequal, and test sets overlap.
Repeated split results cannot be treated as independent replications.

Any hyperparameter or mapping-model choice must use only the development side,
with an inner grouped validation process or a separately fixed development
design. Pooling the held-out ratings into a complete-panel mean before evaluation
would leak calibration votes into the target. Compute evaluation targets from
the evaluation raters only. Keep participant-level uncertainty clustered and
account for repeated source/process cells.

For an independent study:

1. Use independently licensed recordings outside ODAQ, with recording/production
   groups reserved for development and future source-held-out evaluation.
2. Render the actual versioned synthetic operators and intended mono export,
   including common gain and saved residual conventions.
3. Obtain audibility, difference/severity and quality judgments separately,
   with randomized blinded reference comparisons and genuine control/repeat trials.
4. Use an initial panel to estimate variance and content interactions, then plan
   the required listeners per condition against a declared precision goal.
   A rough planning relation is `n ≈ (1.96 × SD / desired_half_width)^2`,
   with allowance for small-sample t effects, grouping and attrition. For illustration,
   SD 15–20 and a five-point half-width suggest roughly 35–62 independent listeners
   before such adjustments. These are planning examples, not a power guarantee
   derived from this three-listener QN subset.
5. Freeze the resulting calibration and description rules before the final
   ODAQ benchmark evaluation.

## 9. Future calibration-use record

The current status is **proposed feasibility protocol; mapping fitting pending**.
The source release and its original aggregate benchmark remain available intact.

If the team adopts future use of ODAQ ratings for calibration, record:

- Release DOI, archive digest, exact CSV hashes, and analysis/code commit.
- Namespaced participant IDs, cohort quotas, candidate-link blocks, seed and
  deterministic selection algorithm.
- Source/production groups, contexts, channel basis, and excluded anchors/controls.
- QC rules and exclusions, frozen independently of model performance.
- Which parameters, labels or decisions the ratings informed and the resulting
  mapping version, including operator compatibility assumptions.
- Evaluation-rater-only targets, source overlap, stereo/mono handling,
  nested/repeated-validation rules and all tuning decisions.
- The revised benchmark claim and an additional independent evaluation where
  appropriate.

This record should accompany any fitted mapping and paper results. The proposed
split CSV and this feasibility report alone do not activate calibration use.

## 10. Reproduction and verification

Run on KNN from `/data/tingyup2/projects/AudioLM/LMushra/`:

```bash
source /data/tingyup2/projects/AudioLM/env.sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python scripts/analyze_odaq_listener_feasibility.py \
  --release data/external/odaq_collection_audit/release/odaq-collection \
  --output outputs/odaq_listener_calibration_feasibility_v1
```

Use a fresh output directory when reproducing a completed run.
The analysis uses NumPy, SciPy, SoundFile and Matplotlib from the existing
remote environment. No training dependency or model weights are required.
Generator code and synthetic dataset files were not edited.

Generated artifacts are under `outputs/odaq_listener_calibration_feasibility_v1/`:

- `proposed_listener_split.csv` — all 66 study-scoped roles, seed, cohort,
  raw subject label and canonical namespace.
- `candidate_cross_study_links.json` — nine explicit unconfirmed links.
- `listener_counts_by_artifact_and_cohort.csv` — exact per-artifact/cohort counts.
- `coverage_by_condition_and_cohort.csv` — complete source/level/context counts.
- `completeness.json`, `xml_crosscheck.json`, `qc_diagnostics.csv` — integrity/QC.
- `calibration_precision_by_condition.csv` — individual-study per-cell estimates.
- `calibration_precision_original_pooled.csv` — explicitly pooled original
  cohorts with both diagnostic and cohort-weighted intervals.
- `precision_after_averaging_sources.csv` — clustered per-listener level summaries.
- `summary_by_method.csv`, `feasibility_summary.json` — summary evidence and
  immutable input hashes.
- `lowpass_anchor_counts.csv`, `repeated_stimuli.json`,
  `calibration_precision.png`, `verification.json` — controls, dependencies
  and reproducibility checks.

Two independent executions produced byte-identical analysis outputs, including
the proposed split, numeric tables and figure: **15 files compared**.
Input CSV SHA256 values were checked before/after, all administered rating cells
were complete, and the 12,896 available main scores matched XML exactly.
The code asserts fixed counts, disjoint roles, full-cohort membership, candidate
link consistency, and finite valid scores. No new listener exclusions or mapping
fit was performed.

Analysis source SHA256:
`cbc01685eab03f570c1e6895d31e5ce184a07a7115d22483c866cae45347331e`.

## 11. Primary evidence

- Downloaded rating CSVs listed in `completeness.json`, with per-file hashes in
  `feasibility_summary.json`.
- Original ODAQ listening-test protocol and screening rule, Sections 4–5 of
  [Torcoli et al.](https://arxiv.org/abs/2401.00197).
- Cohort A/B1/B2 training and anchor effects, Sections 3–4 of
  [Dick et al., Expanding and Analyzing ODAQ](https://arxiv.org/abs/2504.00742).
- Stereo designs, mixed contexts and supplementary-panel description,
  Sections 2–3 of [the stereo extension](https://arxiv.org/abs/2512.14259).
- [ODAQ-Collection release](https://doi.org/10.5281/zenodo.23425817) and
  [official repository](https://github.com/Fraunhofer-IIS/ODAQ).
