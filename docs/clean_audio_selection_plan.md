# DeepMUSHRA initial clean-reference selection plan

Date: **2026-11-11**. Proposal based on the [38-entry inventory](clean_audio_corpus_inventory.md) and [machine-readable comparison](clean_audio_corpus_inventory.csv). Work and storage remain on KNN. No large download or synthetic generation is started by this plan.

## 1. Target and accounting

Target a manageable **200 hours of selected reference recording time**, within the requested 100–300 h range. This is a design allocation, **not a measured eligible-hours estimate**. Every source still has unknown eligible hours pending license/provenance, deduplication and per-artifact quality screening.

Use a noncommercial academic-research pool provisionally, with separate rights labels. Maintain a CC0/BY subset for easier reuse; NC/SA/custom-term material must remain distinguishable. Commercially reusable model/data requirements could change the allocation substantially. ND, unknown-rights and uncleared BBC/YouTube sources are excluded from the proposed initial release.

Count original recording intervals once. Multiple stems, mics, channel views, overlapping crops, effect settings or paraphrases do not increase independent reference hours. Preserve independent source groups across all splits.

## 2. Proposed allocation

| Source | Stratum | Target hours | Purpose / condition |
|---|---|---:|---|
| EARS | Directly recorded full-band speech |40| Expressive speech, read styles and monologues;48 k->44.1 k; BY-NC4. Use clean dataset, not noisy blind test. |
| VCTK | Directly recorded full-band speech |15| Accent/speaker coverage; select one microphone per performance;48 k->44.1 k; BY4. Exact corpus hours not established in survey. |
| DAPS clean | Directly recorded speech |4.5| Studio reference only;~4.5 h published upper target; BY-NC4. Sentence derivative is a subset, never extra duration. |
| LibriSpeech clean | Lower-bandwidth diversity |10|16 k/MP3-derived speech; upsample and retain low-band flag. SH/UN only with supported bands; LP10–16 k excluded. |
| MLS non-English FLAC | Lower-bandwidth multilingual |10| Prefer several of seven non-English languages;16 k->44.1 k; BY4. Avoid extra Opus encoding; audiobook ancestry remains. |
| MAESTRO | Real acoustic piano |25| Harmonic structure, transients/decays; mix of composers/years;44.1/48 k stereo->44.1 mono; BY-NC-SA4. |
| GuitarSet microphone | Real acoustic guitar |3|~3 h nominal corpus target, exact sum unmeasured; pick mic rather than processed/debleeded pickup; native 44.1 mono; BY4. |
| MedleyDB / MUSDB HQ | Real mixtures/stems |10| Diverse mixes, drums, vocals and instruments; unique recording intervals only; mostly NC/SA, track-level clearance.10 h is conditional on full Medley access/yield. |
| Slakh non-omitted | Synthesized music |12.5| Controlled multitimbral mixtures/stems; native 44.1 mono; BY4; exclude duplicate MIDI groups. Keep synthetic origin explicit. |
| VocalSet | Singing |10|20 singers, normal voiced passages preferred; native 44.1 mono; BY4. Near-corpus upper target, not promised post-QC yield. |
| FSD50K | Events/animals/mechanical/effects |40| Diverse discrete sources; first prefer CC0/BY and well-traced acquisition; native 44.1 mono. Per-file fidelity/rights screening essential. |
| Clotho unique sources | Events/short scenes |10| Longer contextual events; exclude all sources already selected from other Freesound corpora and ODAQ. Per-file audio license; captions not needed. |
| TAU2019 development | Field scenes |9| Urban/public/transport ambience;48 k 24 bit binaural->mono. Custom noncommercial terms; derivative rights reviewed before sharing. |
| DEMAND | Field ambience |1| One physical mic per scene,48 k->44.1 k; nominal release~1.5 h unique scene time. Optional until license conflict resolved. |
| **Total** | **Selected recording time** |**200**| **Proposed quotas; eligible yield unknown.** |

Strata totals: **59.5 h directly recorded speech +20 h lower-bandwidth speech +50.5 h music/instruments (including 12.5 h synthesis) +10 h singing +60 h environment/events**.

Thus 180 h is nominally full-band-rate content and 20 h is explicitly lower-bandwidth. The 180 h is not 180 h of proven clean/high-frequency-eligible audio. The strongest directly documented acquisition candidates total~107.5 h (speech 59.5 +real musical material 38 +singing 10), still subject to individual quality/rights checks. Environmental material remains selectively eligible; diffuse ambience generally supports different effects from pitched instruments.

**Fallbacks:** quotas are soft, diversity caps are firm. If VocalSet loses too much to technique/duration/duplicate screening, reduce its target and fill with independently licensed clean vocals from admitted Medley recordings, while counting those intervals only once. If Medley access/unique duration is insufficient, retain a smaller real-mixture allocation and expand other independently recorded instruments/speech rather than pretending stems add hours. If Clotho duplicates overlap FSD50K, fill from other unique FSD50K sources only after QC. If TAU/DEMAND rights remain unclear, replace their quotas with cleared event recordings; do not silently override restrictions. Report a smaller accepted pool if diversity/quality gates cannot be met;100 h of sound evidence is preferable to inventing 200 h eligibility.

## 3. Which effects each stratum should serve

| Stratum | LP | SH | UN | QN |
|---|---|---|---|---|
| Anechoic/studio speech | Per-excerpt high-band/fricative check | Active speech spectra | Voiced target-band peaks only | Low-noise passages, independently checked |
| Piano/guitar/tonal singing | Depends on actual upper harmonics and cutoff | Sustained harmonics and active regions | Strongest candidates; exclude noisy techniques | Conditional noise/room/decay checks |
| Mixed music/percussion | Often broad-band; reject dark/silent cases | Broad structured spectra/transients | Tonal/mixed passages, not noise-only drums | Mastering/recording noise requires screening |
| Synthesized music | Controlled waveform provenance | Strong controlled spectra | Tonal instrument subset | Conditional sample-library floor/tails |
| Events/animals/machines | High-band subset, not whole corpus | Active structured regions | Harmonic bird/motor/alarms only | Only unusually clean references |
| Diffuse ambience | Conditional high-band content | Conditional meaningful removal | Usually low suitability | Usually poor clean-noise baseline |
|16 k speech | Lower-cutoff only;10–16 k ineligible | Validated lower bands | Lower-band configurations or sufficient 7–8 k structure | Conditional prior MP3/noise floor |

Do not force every source to generate all four artifacts. Keep artifact-specific eligible duration and failed/null-effect rates. The same 200 h candidate pool can yield very different eligible hours for LP16 k, UN and QN.

## 4. Download priorities and bounded acquisition gates

**Priority 1 — small verified starting set:** GuitarSet microphone samples, a few EARS and VCTK speakers, and ordinary-phonation VocalSet examples. These have public creator releases and useful source IDs. Already inspected one file from each, but this is not a corpus certification. Recheck licenses and native headers on the actual chosen material.

**Priority 2 — real content diversity:** selected cleared MedleyDB/MUSDB recordings (mix, percussion, vocals, tonal stems), a small composer/year-balanced MAESTRO selection, and FSD50K **metadata first**. Use source IDs/licenses and the ODAQ exclusion registry before fetching event examples. Existing eight pilot excerpts are functional precedents, not representative hour estimates.

**Priority 3 — limited diversity strata:** selected non-English MLS FLAC and LibriSpeech clean; modest non-omitted Slakh. Keep low-bandwidth, MP3 ancestry and synthetic origin visible. Do not let plentiful audiobook/piano/synthesis hours dominate.

**Priority 4 — contextual scenes:** source-deduplicated Clotho and selected TAU/DEMAND only after count/license questions are resolved. ESC-50/UrbanSound/FSDnoisy can be small controlled diversity checks, but overlapping sources and source preprocessing reduce their incremental value.

**Defer bulk acquisition:** Common Voice until pinned locale/API/terms and actual codec/bandwidth QC are established; Libri-Light/People’s Speech because scale and codec ancestry add little first-stage benefit; FMA/Jamendo because existing MP3 coding confounds subtle artifacts; WavCaps/BBC/AudioSet because component rights/overlap/download reliability are costly. GigaSpeech requires an explicit gate/application and is codec-exposed. Opencpop ND and NUS unresolved access/rights are not initial shared-pool sources.

This survey downloaded only small metadata/docs and bounded audio examples. Nothing in these priorities requests or runs complete large archives.

## 5. Expected storage and preprocessing

Published package sizes below are **whole-distribution planning bounds**, not permission to fetch them now and not costs proportional to selected hours.

| Source | Published complete package / access pattern | Initial acquisition approach |
|---|---|---|
| GuitarSet mic |0.657 GB mic ZIP +39.1 MB JAMS; other pickup archives unnecessary | Bounded samples, then mic-only if admitted |
| EARS |69.166 GB across 107 speaker ZIPs | Selected speaker packages;40/100 hours times total is~27.7 GB planning proxy, actual speaker sizes vary |
| VCTK |11.747 GB ZIP; mic views share performances | Small bounded members first; keep one mic for counting/selection |
| DAPS |16.056 GB all 15 conditions; segmented subset 0.229 GB | Request/use clean partition; segmented subset supplies fewer unique hours |
| VocalSet |2.077 GB alternate 1.1 organization;5.992 GB1.2 ZIP | Verify one pinned organization; do not count layouts/versions twice; investigate 1.2 member issue |
| MAESTROv 3 |101 GB ZIP,~120 GB unpacked | Selected performances if bounded retrieval practical; otherwise defer full archive to next approved acquisition phase |
| MUSDB18-HQ |22.657 GB full ZIP | Track-level rights and source grouping; selected members; full Medley size/access unknown |
| Slakh |104.323 GB compressed, nearly 500 GB all-stem WAV | Small non-omitted mixtures/stems; retain compressed masters; avoid decoding all stems |
| FSD50K |24.672 GB multipart audio;6.7 MB metadata | Metadata/license/source filters first, then a small audio batch |
| Clotho |7.052 GB three audio 7 z files | Metadata/dedup first; complete archives only after admission decision |
| TAU2019 |35.622 GB audio 21 ZIPs | Resolve license and select recording groups |
| DEMAND48 k |5.596 GB for 18 scene ZIPs,16 mic files each | Select one physical mic; do not add 16 k duplicate delivery |
| LibriSpeech / MLS |6.3 G clean 100; other splits 23 G/30 G; MLS non-English~6.2–115 G per language FLAC | Restrict languages/speakers and recording groups; no English multi-TB bulk |

200 h at 44.1 k mono is **63.504 GB PCM16**, **127.008 GB float32**, or 254.016 GB float64 before container overhead. These are arithmetic storage calculations, not source archive estimates. Original multitracks, downloads, expanded copies, duplicate views and scratch increase cost substantially.

A provisional **0.5–1 TB acquisition/QC working budget** is reasonable for this mixed proposal if whole packages are necessary; exact requirements remain unknown, especially Medley delivery and selected archive extraction. Refresh KNN capacity and backup/retention arrangements before relying on one copy. The earlier 12 TiB free is a point-in-time check, not reserved capacity.

For perspective only,12 degraded variants per reference (four effects xthree settings), with one shared reference and both degraded/residual float32 files, would use 25 x 127.008 GB = **3.1752 TB**, excluding masks/plots/masters. This is not a generation request or a final storage design; streaming/batching and reference deduplication can matter.

All roots are remote:

- Originals/evidence: /data/tingyup2/projects/AudioLM/LMushra/data/external/.
- Proposed future registry/admitted manifests: remote project data directory, versioned small text only in Git.
- Processed references/diagnostics: remote ignored data/outputs.
- Environment/caches/temp: source /data/tingyup2/projects/AudioLM/env.sh.
- Mac workspace: small coordination notes only.

## 6. Admission and split protocol before scaling

1. Pin publisher release, license text/hash, source ID/URL, original interval and checksums. Gate transformations and redistribution separately; do not submit access applications automatically.
2. Exclude all known ODAQ original productions/recordings and alternate views using evaluation-owned provenance. Quarantine ambiguous IDs. No ODAQ audio/ratings/comments may tune quality thresholds, captions or effect parameters.
3. Deduplicate recording lineages across corpora, releases, microphones, stems, channels and overlapping crops. Proposed hashes/fingerprints operate on independent candidate sources; manual review resolves ambiguous matches.
4. Validate decoder integrity, finite values, native rate/channels, duration, clipping evidence and source-history flags. Never infer pristine acquisition from WAV/FLAC.
5. Resample/downmix only the clean master to 44.1 k mono. Preserve native provenance; measure bandwidth/high-band activity after downmix. No restoration/enhancement disguised as clean acquisition.
6. Label artifact-specific eligibility from independent processing checks: active-band energy for LP/SH; target-band tonal peaks for UN; noise-floor uncertainty/locality for QN. Include ineligible/no-effect reasons. All gates remain proposed until measured on a small independent selection pilot.
7. Split recording connected components deterministically, e.g.80/10/10 with seed 20261111, before cropping/effect generation. This proportion/seed is a proposal; preserve the existing generator’s configurable infrastructure. Keep speaker/artist/uploader/session disjointness where feasible, and all related views in one split.
8. Report accepted unique hours by corpus/content/license/native bandwidth/codec provenance and **per artifact**. Keep rejected, quarantined and duplicate hours separate. Do not report an expected 200 h as achieved.
9. Only after the artifact-audit issues and source gates are reviewed, approve a small multi-source synthesis pilot and independent listening calibration. Objective gates and parameter tiers are not perceived-severity labels.

## 7. Questions for the team

- Is the intended release academic-only or commercially reusable, and will processed WAVs and model weights both be published?
- Is a 200 h target with 20 h lower-bandwidth diversity and 12.5 h synthesized music acceptable, or should all learning focus on directly recorded full-band audio?
- Does the mono 44.1 k training path preserve the artifact bands end-to-end, including any alternative 16/24 k encoder path?
- Who owns ODAQ original-recording exclusion, cross-corpus deduplication and source-level split assignments?
- What independent band-activity/tonality/noise/clipping gates and null-effect caption policy will be validated?
- Which UN specificity/QN locality/STFT temporal-overlap fixes are essential before generating the training set?
- Do we resolve disputed/custom licenses or replace those allocations with cleared recordings?
- How will we obtain broader clean multilingual speech, conventional lyrical singing and ensemble music without simply adding lossy web audio?

Next concrete step: review these choices, then acquire a **small rights-cleared sample batch**, measure per-artifact eligibility yield, and revise the quotas from actual evidence. Full training dataset generation remains out of scope.
