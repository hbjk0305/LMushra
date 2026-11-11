# DeepMUSHRA clean audio corpus inventory

Survey date: **2026-11-11**. KNN repository: /data/tingyup2/projects/AudioLM/LMushra, branch **pt/data**, baseline commit 684220e998477fac751b8db7b3ad4c24505a920d. This is source-selection research, not training or perceptual calibration.

## 1. Findings and recommendation

Use a diverse reference pool with a **full-band core and separately identified lower-bandwidth/previously encoded diversity strata**. A 44.1 kHz container is an input contract, not a fidelity certificate. EARS/VCTK have directly documented speech acquisition; GuitarSet/MAESTRO/VocalSet add controlled musical material; selected FSD50K events add environmental/animal/mechanical diversity. MedleyDB/MUSDB and synthesized Slakh add mixtures, vocals, percussion and instrumentation with different provenance and licensing.

The survey covers **38 dataset/split entries**, including every requested candidate. It does not exhaust all public audio. There is no defensible deduplicated “total clean hours” yet. Published durations, conditional obtainable bounds and **unknown eligible hours** are separate fields in [the 47-column CSV](clean_audio_corpus_inventory.csv). All full-corpus eligible-hour values remain unknown.

The [selection plan](clean_audio_selection_plan.md) targets **200 h after selection**, including 20 h of lower-bandwidth speech and 12.5 h of synthesized music, explicitly separated from directly recorded full-band material. Allocations are design targets, not measured yields or authorization to download large archives.

The existing [artifact validation](synthetic_artifact_validation.md) matters: LP needs actual high-band activity; UN needs tonal peaks; QN needs a sufficiently low baseline noise floor. Source choice cannot fix the documented UN detector specificity, QN temporal/spectral locality or STFT pre-onset spreading. No generators changed. PE/TM remain held out; ICC/ILD remain deferred.

## 2. Scope and evidence

First reviewed README, dataset_spec, synthetic_artifact_validation, odaq_collection_audit, odaq_listener_calibration_feasibility, source-preparation code and existing source receipts. All work stayed on KNN. /data had approximately 12 TiB free; home/root is unsuitable for project downloads. Ignored evidence: data/external/clean_corpus_survey/.

Verification labels:

- **D:** creator/publisher documentation, official repository, release paper, API listing or license. A listed download does not verify every byte is reachable.
- **M:** downloaded metadata parsed directly; not an audio-file census.
- **I:** bounded ZIP directory inspection; member counts are not unique-performance counts.
- **F:** actual decoded header/waveform, SHA256, finite/peak checks and limited spectral measurements.
- **Judgement/proposal:** our suitability and sampling decisions; not official labels, measured audibility or human MUSHRA scores.

The CSV includes citation/version/source, counts/hours/size, downloadable format/encoding, native rate/channels, depth/bitrate, acquisition and prior-codec provenance, license/access/redistribution, content metadata, conversion, overlap and individual LP/SH/UN/QN rationales. Unknown is deliberate. Some literature-nominal properties, notably MusicNet/NUS-48 E, could not be confirmed from the inspected release description or actual files and are marked accordingly. Opus 48 k clocks or decoded PCM depth do not establish original fidelity.

No credentials were supplied to publishers, gated terms accepted, applications submitted, entire large audio archives downloaded, or ODAQ signals/ratings/comments analyzed.

## 3. Comparison tables

H/C/L = High/Conditional/Low corpus-level potential for **LP/SH/UN/QN**, respectively. High means promising after file screening, not that every excerpt supports 16 kHz removal or is pristine. Lower-rate speech remains eligible for effects inside its actual bandwidth. The CSV provides reasons and exact verification status.

### Speech

| Corpus / version | Published files; hours | Downloaded/released format and native rate | Archive size | Audio license caveat | LP/SH/UN/QN |
|---|---|---|---|---|---|
| [Mozilla Common Voice Scripted Speech](https://discourse.mozilla.org/t/common-voice-scripted-speech-v27-0-and-spontaneous-speech-v5-0-released/149490) — 27.0 (announced 2026-09-18) | 32,349,999 clips; **42593 (approximately; includes non-validated audio) h** | MP3 plus TSV metadata; Variable across recordings/releases; v 27 headers unverified Hz; ch Historical releases mono; v 27 per-file configuration unverified | Per locale; aggregate unknown. Official indexed v 27 Finnish listing 477.16 MB, not a global estimate | CC0-1.0 | C/C/C/C |
| [Mozilla Common Voice Spontaneous Speech](https://discourse.mozilla.org/t/common-voice-scripted-speech-v27-0-and-spontaneous-speech-v5-0-released/149490) — 5.0 (announced 2026-09-18) | 89,754 clips; 80 languages; **302 transcribed/validated; total audio hours unknown h** | unknown for pinned v 5 locale; verify download record; unknown Hz; ch unknown | unknown | unknown for specific v 5 locale; verify MDC record | C/C/C/C |
| [LibriSpeech train-clean-100](https://www.openslr.org/12/) — SLR12 original release | unknown in inspected landing documentation; enumerate manifest before acquisition; **100 nominal split hours h** | FLAC in tar.gz; 16000 Hz; ch 1 | 6.3 G tar.gz (official display units) | CC BY 4.0 | L/C/C/C |
| [LibriSpeech train-clean-360](https://www.openslr.org/12/) — SLR12 original release | unknown in inspected landing documentation; enumerate manifest before acquisition; **360 nominal split hours h** | FLAC in tar.gz; 16000 Hz; ch 1 | 23 G tar.gz (official display units) | CC BY 4.0 | L/C/C/C |
| [LibriSpeech train-other-500](https://www.openslr.org/12/) — SLR12 original release | unknown in inspected landing documentation; enumerate manifest before acquisition; **500 nominal split hours h** | FLAC in tar.gz; 16000 Hz; ch 1 | 30 G tar.gz (official display units) | CC BY 4.0 | L/C/C/C |
| [CSTR VCTK Corpus](https://datashare.ed.ac.uk/handle/10283/3443) — 0.92 | 88,328 audio ZIP entries inspected (two microphone views, not unique performances);110 speakers stated; **unknown in inspected primary record/README h** | FLAC in ZIP (48 k silence-trimmed variant); 48000 delivered; recorded 96000 Hz; ch 1 per microphone; two alternate mic recordings | 11,747,302,977 bytes ZIP (repository API) | CC BY 4.0 | H/C/C/H |
| [DAPS - Device and Produced Speech](https://zenodo.org/records/4660670) — 1.0 | 20 speakers; audio file count not verified; **~4.5 unique speech hours; 15 aligned versions each ~4.5 h h** | WAV in tar.gz; 44.1 kHz clean family documented by segmented derivative; 44100 clean family; full variant headers unverified Hz; ch unknown until clean partition headers inspected | 16,055,782,487 bytes tar.gz (all versions) | CC BY-NC 4.0 | H/C/C/H |
| [Segmented DAPS](https://zenodo.org/records/4783456) — 1.0 | unknown sentence count; 20 speakers first script; **unknown h** | WAV + TXT + JSON; 44100 Hz; ch unknown until headers inspected | 228,702,819 bytes tar.gz | CC BY-NC 4.0 | H/C/C/H |
| [Multilingual LibriSpeech](https://www.openslr.org/94/) — SLR94 single improved release (2020) | unknown total segments; eight languages; **~44500 English + ~6000 seven other languages h** | Original FLAC or smaller Opus in tar.gz; 16000 processing rate (paper) Hz; ch mono expected; native headers not inspected | English FLAC 2.4 T / Opus 651 G; German 115 G, Dutch 86 G, French 61 G, Spanish 50 G, Italian 15 G, Portuguese 9.3 G, Polish 6.2 G FLAC | CC BY 4.0 | L/C/C/C |
| [Libri-Light](https://github.com/facebookresearch/libri-light) — 2019/2020 release; repository main snapshot | unknown audiobook segment count; **~60000 headline; listed small 577 / medium 5193 / large 51934 h h** | FLAC + JSON in TAR; 16000 processing Hz; ch mono processing expected; headers not inspected | small 35 GB; medium 321 GB; large 3.05 TB; duplicate 274 GB | Data audio permission requires upstream LibriVox/public-domain provenance; repository MIT is code license | L/C/C/C |
| [The People’s Speech](https://huggingface.co/datasets/MLCommons/peoples_speech) — HF MLCommons official card snapshot; card references v 1.0 | 8,051,212 Hub rows displayed; includes repeated dev/test across configs, not unique recordings; **30000+ headline h** | FLAC audio embedded in Parquet; source IDs retain original path; 16000 Hz; ch unknown native files; ASR decode generally mono, verify | HF full repository 2.12 TB displayed; clean config 398,550,700,437 bytes download_size | CC BY 4.0 and CC BY-SA 4.0 subsets; Apache 2 code is separate | L/C/C/C |
| [GigaSpeech](https://github.com/SpeechColab/GigaSpeech) — 1.0.0 original family (not GigaSpeech 2/3) | unknown raw-file count; segmented utterances are a different count; **10000 labeled; paper 40000 total vs current README33000+ unsupervised h** | Original Opus + JSON; HF repackaged Parquet; 16000 source resampling; Opus decoders may report 48000 clock/output Hz; ch unknown native headers; verify decode | unknown original archive bytes; subset-specific gated distribution | Audio noncommercial research/education access agreement; Apache 2 badge/code does not grant audio copyright | L/C/C/C |
| [EARS - Expressive Anechoic Recordings of Speech](https://github.com/facebookresearch/ears_dataset) — 2024 dataset release | 107 speakers; ZIP member counts not enumerated for entire corpus; **100 h** | WAV in per-speaker ZIP; 48000 Hz; ch 1 in inspected sample; entire corpus not inspected | 69,165,795,600 bytes across 107 speaker ZIP assets (GitHub release API) | CC BY-NC 4.0 | H/C/C/H |
| [LibriTTS](https://www.openslr.org/60/) — SLR60 original | unknown enumerated count; **~585 h** | WAV in tar.gz; 24000 Hz; ch mono expected; headers not inspected | Per split; inspect official links before acquisition; aggregate unknown | CC BY 4.0 | C/C/C/C |
| [Hi-Fi Multi-Speaker English TTS (Hi-Fi TTS)](https://www.openslr.org/109/) — v 0 / SLR109 | 10 speakers; utterance count unknown; **291.6 h** | FLAC expected release; headers unverified; 44100 Hz; ch unknown until sample inspection | 41 G tar.gz official display | CC BY 4.0 | C/C/C/C |

### Music, instruments and singing

| Corpus / version | Published files; hours | Downloaded/released format and native rate | Archive size | Audio license caveat | LP/SH/UN/QN |
|---|---|---|---|---|---|
| [MAESTRO](https://magenta.tensorflow.org/datasets/maestro) — 3.0.0 | 1276 performances (WAVs; MIDI separate); **198.7 h** | WAV + MIDI + CSV/JSON in ZIP; 44100 or 48000 Hz; ch 2 | 101 GB ZIP;120 GB uncompressed (official display) | CC BY-NC-SA 4.0 | H/H/H/H |
| [Slakh2100-redux](https://zenodo.org/records/4599666) — redux Zenodo 4599666 | 2100 track directories incl omitted duplicates; many stems per mixture; **145 mixture hours incl original track population h** | FLAC + MIDI + YAML; 44100 Hz; ch 1 | 104,322,767,708 bytes tar.gz; almost 500 GB decoded WAV incl stems | CC BY 4.0 | H/H/H/H |
| [MUSDB18-HQ](https://zenodo.org/records/3338373) — 1.0.0 | 150 songs x 5 WAVs =750 audio files; **~10 mixture hours h** | WAV: mixture,bass,drums,vocals,other; 44100 Hz; ch 2 | 22,656,664,047 bytes ZIP | Mixed: educational/noncommercial terms; MedleyDB CC BY-NC-SA4, Easton Ellises BY-NC-SA3, other permissions | H/H/H/C |
| [GuitarSet](https://zenodo.org/records/3371780) — 1.1.0 | 360 performances;360 mic WAVs; alternate pickup variants separate; **~3 derived nominal (360 x~30 s) h** | WAV + JAMS in ZIP; 44100 observed Hz; ch mic 1 / hex 6; mixed pickup version also supplied | mic 656,927,981 bytes; mono-pickup 683,145,360; hex 3,210,735,945; debleed 3,607,349,578 | CC BY 4.0 | H/H/H/H |
| [MusicNet](https://zenodo.org/records/5120004) — 1.0 / Zenodo 5120004 | 330 recordings; **34 h** | PCM WAV + CSV; MIDI separate; 44100 nominal in corpus literature; not established by inspected Zenodo description/header Hz; ch mono nominal in corpus literature; not established by inspected Zenodo description/header | 11.1 GB tar.gz; metadata 43.8 kB and MIDI2.6 MB separate | Per-recording CC/public-domain performances; verify metadata; no blanket license assumed from labels | H/H/H/C |
| [MedleyDB](https://medleydb.weebly.com/description.html) — 1.0 +2.0 | 122 +74 =196 multitracks; mix/stem/raw file count unknown; **unknown across both releases in inspected documentation h** | WAV + YAML/CSV annotations; 44100 Hz; ch mix/stems stereo; raw mono | unknown; per-song/access delivery | CC BY-NC-SA 4.0 | H/H/H/C |
| [FMA - Free Music Archive dataset](https://github.com/mdeff/fma) — 2017 release; official repo snapshot | 106574 tracks full/large;25000 medium;8000 small (overlapping subsets); **343 days full =8232 h; small 66.67 h, medium 208.33 h, large 888.12 h nominal 30 s-derived h** | MP3 + CSV metadata; variable/unverified; do not assume uniform 44.1 k Hz; ch variable/unverified | small 7.2 GiB; medium 22 GiB; large 93 GiB; full 879 GiB ZIP (README also 917 GiB headline) | Per-track artist-selected license; metadataCC BY4; codeMIT | C/C/C/L |
| [MTG-Jamendo](https://github.com/MTG/mtg-jamendo-dataset) — 2019 corpus; current official distribution snapshot | 55701 raw_30 s tracks; splits 55525 autotagging tracks; nested subsets; **unknown exact sum in inspected README; do not confuse 30 s minimum with 30 s excerpts h** | 320 kbps MP3; optional mono LAME VBR2 transcode; unknown exact native distribution until headers checked Hz; ch full-quality unverified; audio-low explicitly mono | 508 GB full-quality raw_30 s/audio;156 GB audio-low per current README | Current distribution academic/noncommercial only; track CC licenses; metadata BY-NC-SA4 | C/C/C/L |
| [NSynth](https://magenta.tensorflow.org/datasets/nsynth) — 2017 official release | 305979 notes; train 289205,valid 12678,test 4096; **339.977 derived nominal h** | 16-bit PCM WAV +JSON or TFRecord; 16000 Hz; ch 1 | unknown verified archive bytes; train/valid/test jsonwav and TFRecord separate | CC BY 4.0 | L/C/C/C |
| [VocalSet](https://zenodo.org/records/1442513) — 1.2 (alternate 1.1 archive in same record) | 20 singers; unique take count unverified;1.2 contains three reorganizations of same audio; **10.1 h** | PCM WAV in ZIP; 44100 verified on 1.1 sample Hz; ch 1 verified on 1.1 sample | 1.2 ZIP5,991,573,193 bytes;1.1 ZIP2,077,243,579 bytes; do not count twice | CC BY 4.0 | H/C/C/H |
| [Opencpop](https://wenet-e2e.github.io/opencpop/) — 2022 release | 3756 utterances from 100 songs;1 singer; **5.2 h** | WAV documented; delivery workflow on official Download page not completed; 44100 Hz; ch unknown header channel count | unknown verified archive size | CC BY-NC-ND 4.0 | H/C/C/H |
| [NUS Sung and Spoken Lyrics Corpus (NUS-48 E)](https://smcnus.comp.nus.edu.sg/archive/pdf/2012-2013/2013_05-Pub-NUS-48E.pdf) — 2013 | 48 sung performances by 12 subjects plus spoken counterparts; exact downloadable WAV count unknown; **unknown verified duration; do not substitute community-mirror totals h** | WAV nominal (paper); current official download unavailable; unknown verified release; commonly described 44.1 k requires original documentation/header confirmation Hz; ch unknown | unknown | Original current audio license not verified; community research-only mirror is not a new permission grant | H/C/C/H |

### Environmental, animal, effects and industrial audio

| Corpus / version | Published files; hours | Downloaded/released format and native rate | Archive size | Audio license caveat | LP/SH/UN/QN |
|---|---|---|---|---|---|
| [FSD50K](https://zenodo.org/records/4060432) — 1.0 | 51197 (40966 dev,10231 eval); **108.3 (80.4 dev +27.9 eval) h** | WAV in split ZIP plus JSON/CSV; 44100 Hz; ch 1 | 24,671,691,926 bytes audio multipart ZIP (official API sum); metadata 6,700,838 bytes | Per clip CC0/BY/BY-NC/Sampling+; corpus curation BY; no universal commercial license | C/C/C/C |
| [Clotho](https://zenodo.org/records/4783391) — 2.1 (pinned Zenodo 4783391) | 6974 headline; pinned released metadata 3839 dev+1045 val+1045 eval=5929 rows; **unknown exact pinned-release sum h** | WAV in 7 z; captions/metadata CSV; 44100 nominal; not measured Hz; ch unknown native channel count in this survey | 7,052,010,191 bytes across three 7 z audio archives | Per-file Freesound licenses; captions have separate Tampere noncommercial attribution license | C/C/C/C |
| [ESC-50](https://github.com/karolpiczak/ESC-50) — official GitHub snapshot (2015 corpus) | 2000 (5 s each); ESC10 is 400-clip subset; **2.778 derived (2000 x 5 s) h** | WAV +CSV metadata; 44100 Hz; ch 1 | ~600 MB ZIP official README | CC BY-NC 3.0 | C/C/C/C |
| [UrbanSound8K](https://urbansounddataset.weebly.com/urbansound8k.html) — 2014 release | 8732 clips <=4 s; **unknown in inspected official landing page h** | WAV +CSV; variable, same as Freesound upload Hz; ch variable, original | unknown current archive bytes; download form/soundata route | CC BY-NC 3.0 stated corpus terms; verify current form and source attribution | C/C/C/C |
| [FSDnoisy18k](https://zenodo.org/records/2529934) — 1.0 | 18532 (17585 train,947 test); **42.5 h** | WAV +CSV in ZIP; 44100 Hz; ch 1 | 9,542,773,434 bytes audio ZIP train+test; docs/meta additional~170 kB | Per clip CC0/BY; dataset curation BY | C/C/C/C |
| [WavCaps](https://huggingface.co/datasets/cvssp/WavCaps) — official 2024 card/current snapshot | 403050 (Freesound 262300,BBC31201,SoundBible 1232,AudioSetSL108317); **~7567.26 derived from displayed rounded mean 67.59 s x 403050; exact total unknown h** | FLAC ZIPs +JSON metadata; unknown exact release distribution; do not assume a single sample rate Hz; ch unknown actual distribution | unknown current aggregate FLAC ZIP bytes | Academic-only conditions plus underlying source rights; HF BY badge does not override them | C/C/C/C |
| [BBC Sound Effects](https://sound-effects.bbcrewind.co.uk/about) — live archive as accessed 2026-11-11 | over 30000 per current official About; exact count unverified; **unknown h** | WAV/MP3 options described by archive; actual downloads not inspected; variable/unverified Hz; ch variable/unverified | No verified complete public bulk archive; individual file sizes vary | RemArc terms; personal/educational/research; commercial licensing via Pro Sound Effects | C/C/C/C |
| [DEMAND - Diverse Environments Multichannel Acoustic Noise Database](https://zenodo.org/records/1227121) — Zenodo 1227121 release | Description says 15 recordings; API lists 18 environments x 16 mono channels per rate; **unknown exact; nominal 18 x 5 min =1.5 h at one channel, subject to WAV verification h** | 16 separate mono WAVs/environment in ZIP;48 k and 16 k variants; 48000 original;16000 downsampled Hz; ch 16 synchronized microphones as separate mono files | 5,596,071,543 bytes across 18 original 48 k ZIPs;16 k alternatives not added | Conflict: record badgeCC BY4.0; description explicitlyCC BY-SA3.0 | C/C/L/L |
| [AudioSet](https://research.google.com/audioset/download.html) — 2017 segment release;2021 strong-label extension | 2085544 segment rows from published split counts; raw audio not supplied; **~5793.18 nominal 10 s-derived; current live audio availability unknown h** | CSV IDs/timestamps/labels and TFRecord embeddings; source YouTube media external; Source-dependent; VGGish 16 k feature processing does not define original recording bandwidth Hz; ch Source-dependent | Official metadata/features only; no raw audio archive | CC BY4 dataset metadata/features; does not grant copyright to YouTube waveforms | C/C/C/C |
| [TAU Urban Acoustic Scenes 2019 development](https://zenodo.org/records/2589280) — 2019 / Zenodo 2589280 | 14400 10-second stereo segments; **40 h** | WAV in 21 ZIPs +metadata; 48000 Hz; ch 2 binaural | 35,622,369,320 bytes across 21 audio ZIPs; metadata/docs additional | Noncommercial release terms; API other-nc; read bundled license before redistribution | C/C/L/L |
| [MIMII - Malfunctioning Industrial Machine Investigation and Inspection](https://zenodo.org/records/3384388) — public 1.0 /2019 | Exact unique recording count unknown; public 1.0 four models/type, not all seven described in introduction; **unknown unique; repeatedSNR mixes must not multiply independent hours h** | WAV in ZIP by machine type and noise SNR; 16000 Hz; ch 8 | 100,243,834,344 bytes across 12 machine/SNR ZIPs | CC BY-SA 4.0 | L/C/C/L |


## 4. Release details that change selection

**Common Voice:** latest official announcement located is scripted 27.0/spontaneous 5.0, September 18,2026. Stale locale pages must not decide the version. Scripted reports 42,593 total hours, not a verified clean/validated subset. Spontaneous reports 302 transcribed/validated hours rather than total duration. Pin locale export, terms and headers before downloading. [Mozilla announcement](https://discourse.mozilla.org/t/common-voice-scripted-speech-v27-0-and-spontaneous-speech-v5-0-released/149490), [MDC](https://mozilladatacollective.com/).

**Lossless audiobook containers:** LibriSpeech explicitly supplies its original MP3 files; LibriTTS documents reusing these. Libri-Light explicitly converts MP3 to FLAC. Its MIT code license does not grant audio copyright. MLS uses that acquisition route and offers FLAC or additional Opus encoding. Hi-Fi TTS selects bandwidth>=13 kHz and SNR>=32 dB in its paper; that does not promise usable 16 kHz content or independently establish pristine recordings. [LibriSpeech](https://www.openslr.org/12/), [LibriTTS](https://www.openslr.org/60/), [Libri-Light preparation](https://github.com/facebookresearch/libri-light/tree/main/data_preparation), [MLS](https://arxiv.org/html/2012.03411v2), [Hi-Fi TTS](https://arxiv.org/abs/2104.01497).

**Repeated views:** VCTK mics, DAPS device versions, GuitarSet pickups/mic, musical stems, VocalSet reorganizations, Slakh MIDI re-renderings and DEMAND channels are not independent hours. VCTK has 88,328 inspected audio ZIP entries, not that many distinct performances. Exclude Slakh omitted duplicates. FMA small/medium/large have 30-second excerpts; Jamendo raw_30 s contains **full tracks with a minimum 30 s duration**. FMA’s 343 full days equal 8232 h, not a sum of its subsets. [VCTK](https://datashare.ed.ac.uk/handle/10283/3443), [DAPS](https://zenodo.org/records/4660670), [GuitarSet](https://guitarset.weebly.com/), [VocalSet](https://zenodo.org/records/1442513), [Slakh](https://zenodo.org/records/4599666), [FMA](https://github.com/mdeff/fma), [Jamendo](https://github.com/MTG/mtg-jamendo-dataset).

**Clotho count scope:** pinned record headline 6974; prose 3840 development/1046 validation. The released CSVs parse to 3839 development +1045 validation +1045 evaluation = **5929 rows,5905 distinct sound IDs**. No claim is made that the three archives contain precisely 5929 valid WAVs. The headline may have broader split scope; the one-row-per-split prose discrepancy also needs reconciliation. **1774 rows lack excerpt bounds**. Development/validation failed strict UTF-8; Latin-1 fallback was recorded; evaluation decoded as UTF-8. Do not invent missing intervals or exact hours. [Pinned release and CSVs](https://zenodo.org/records/4783391).

**Environmental “clean”:** FSDnoisy18k’s clean/noisy distinction describes **labels**, not acoustic fidelity. FSD50K event/predominance annotations are not quality ratings. ESC-50 explicitly warns of class-dependent source bandlimiting. [FSDnoisy18k](https://zenodo.org/records/2529934), [FSD50K](https://zenodo.org/records/4060432), [ESC-50](https://github.com/karolpiczak/ESC-50#caveats).

**DEMAND conflicts:** prose says 15 recordings, API lists 18 environments per rate; license badgeBY4.0 differs from descriptionBY-SA3.0. Resolve before sharing derivatives. Count scenes once across channels/rates. This is ambience/noise content, not clean-QN calibration. [DEMAND](https://zenodo.org/records/1227121).

**Access badges do not clear waveform rights:** GigaSpeech’s Apache 2 badge does not override its gated noncommercial audio agreement. WavCaps’ BY badge does not override academic-only/component terms. AudioSet supplies IDs, labels and embeddings, not waveforms or copyright to YouTube recordings. TAU’s downloaded bundled license allows experimental/noncommercial use/copy, with commercial use prohibited; public derivative sharing still needs the exact terms reviewed. Opencpop is ND and excluded from a shared transformed pool absent permission. [GigaSpeech](https://huggingface.co/datasets/speechcolab/gigaspeech), [WavCaps](https://huggingface.co/datasets/cvssp/WavCaps), [AudioSet](https://research.google.com/audioset/download.html), [TAU](https://zenodo.org/records/2589280), [Opencpop license](https://wenet-e2e.github.io/opencpop/liscense/).

## 5. Actual file inspection

Convenience/functional examples, **not random samples, a listening study or eligibility-yield estimates**. ESC-50: first dog/rain/engine metadata match after known-ODAQ Freesound-ID exclusion. GuitarSet/EARS/VCTK: bounded small archive members. VocalSet 1.1 sample is vocal fry, not a proposed tonal-UN baseline. LibriSpeech: first bounded-stream FLAC. Eight existing MedleyDB-derived MUSDB pilot excerpts were reused.

**16 decoded files;122.236099 s (~0.03395 h); seven corpus families; all finite; maximum absolute sample 0.99884033; no decoded sample>=0.999.** This does not exclude historical analog/normalized clipping, noise or codec artifacts.

Successful/recorded acquisition requests account for **18,545,325 bytes** including ZIP indexes/range overhead. A failed VocalSet 1.2 range attempt was not fully metered separately; this is not an exact total-traffic claim. Evidence occupied approximately 17 MiB. No complete large audio archive was fetched.

Spectrum method: whole-example Welch PSD, mean mono, Hann 4096 samples,50% overlap, no detrending/silence gate. Fraction above 10 k = summed PSD bins>10 k / all bins. This is **not** a bandwidth-cutoff estimator, SNR, audibility threshold or fidelity score. First-window-only spectra were replaced because initial windows can be silent; final results use whole examples.

| Example relative to remote checkout | Hz / channels / subtype | Seconds | Peak | Energy fraction >10 kHz |
|---|---|---:|---:|---:|
| data/external/clean_corpus_survey/samples/1-100032-A-0.wav | 44100 / 1 / PCM_16 | 5.000000 | 0.998840 | 0.000423078 |
| data/external/clean_corpus_survey/samples/1-17367-A-10.wav | 44100 / 1 / PCM_16 | 5.000000 | 0.663574 | 8.34028 e-09 |
| data/external/clean_corpus_survey/samples/1-18527-A-44.wav | 44100 / 1 / PCM_16 | 5.000000 | 0.301453 | 6.90602 e-06 |
| data/external/clean_corpus_survey/samples/guitarset_04_Jazz1-200-B_solo_mic.wav | 44100 / 1 / PCM_16 | 14.400000 | 0.947815 | 0.00216342 |
| data/external/clean_corpus_survey/samples/ears_emo_confusion_sentences.wav | 48000 / 1 / FLOAT | 6.765458 | 0.154570 | 0.00110867 |
| data/external/clean_corpus_survey/samples/374-180298-0021.flac | 16000 / 1 / PCM_16 | 12.965000 | 0.531708 | 0 |
| data/phase1_sources/reference_01.wav | 44100 / 2 / DOUBLE | 8.000000 | 0.427979 | 0.00151544 |
| data/phase1_sources/reference_02.wav | 44100 / 2 / DOUBLE | 8.000000 | 0.370483 | 2.41749 e-05 |
| data/phase1_sources/reference_03.wav | 44100 / 2 / DOUBLE | 8.000000 | 0.327759 | 0.0119096 |
| data/phase1_sources/reference_04.wav | 44100 / 2 / DOUBLE | 8.000000 | 0.140472 | 0.0033239 |
| data/phase1_sources/reference_05.wav | 44100 / 2 / DOUBLE | 8.000000 | 0.178192 | 0.00236672 |
| data/phase1_sources/reference_06.wav | 44100 / 2 / DOUBLE | 8.000000 | 0.476410 | 0.000790393 |
| data/phase1_sources/reference_07.wav | 44100 / 2 / DOUBLE | 8.000000 | 0.765686 | 0.00090836 |
| data/phase1_sources/reference_08.wav | 44100 / 2 / DOUBLE | 8.000000 | 0.745056 | 0.00072837 |
| data/external/clean_corpus_survey/samples/vctk_p250_100_mic1.flac | 48000 / 1 / PCM_16 | 1.242375 | 0.554504 | 0.000738257 |
| data/external/clean_corpus_survey/samples/vocalset11_f9_scales_vocal_fry_o.wav | 44100 / 1 / PCM_16 | 7.863265 | 0.055359 | 0.000144012 |


Rain’s >10 k energy fraction is~8.34 e-9 versus GuitarSet~2.16 e-3. These **individual files** show why 44.1 k alone is insufficient. High-band energy can be noise; low energy can reflect legitimate content rather than codec damage. LibriSpeech 16 k has no >10 k content by construction. Sampled EARS isFLOAT32; sampled VCTK/GuitarSet/ESC/VocalSet arePCM16. Existing MUSDB excerpts areDOUBLE exports with upstreamPCM16 header receipts: DOUBLE export did not add recording precision.

Failures and limits retained:

- VocalSet 1.2 bounded ZIP-member read: **Truncated file header**. Alternate 1.1 member/CRC succeeded. This does not establish whole 1.2 archive corruption.
- NUS-48 E original download routes unreachable; paper accessible. Community mirrors were not substituted as permission grants.
- GigaSpeech raw endpoint 401; public terms/gate visible; no bypass.
- BBC licensing endpoint returned app/About shell remotely; detailed current permission text not successfully archived. Conditional status remains.
- NSynth: official HTTP archive HEADs returned 200 and file sizes; an HTTPS rewrite failed certificate hostname validation. No TLS check was disabled and no archive transferred.
- No ffprobe on KNN. SoundFile/libsndfile verified sampled WAV/FLAC headers/waveforms; no new dependencies installed.
- Bounded reads do not verify whole-archive checksums. Successfully extracted ZIP members passed CRC; saved SHA256 values are retained.

## 6.44.1 kHz mono compatibility

All decodable audio can technically be converted; this does not establish permission or artifact suitability. Select and convert the **clean master before degradation**, retaining native and delivery provenance.

| Native source | Export | Consequence |
|---|---|---|
| 48 k or higher | Bandlimited resample to 44.1 k | Removes>22.05 k; current 5-16 k LP remains representable; existing ultra-high-band artifacts may disappear. |
| 44.1 k stereo | Explicit mono mix | Channel cancellation can alter high-band activity; remeasure after downmix. |
| 24 k | Upsample to 44.1 k | Native Nyquist remains 12 k; LP5-10 k possible,12-16 k cannot remove absent content. |
| 16 k | Upsample to 44.1 k | Native Nyquist remains 8 k; high LP unsuitable; SH/UN need supported lower bands or sufficient 7-8 k activity. |
| MP3/Opus/web-derived PCM/FLAC | Decode once; record source codec | Existing coding artifacts remain confounds, even in lossless exports. |
| Array/pickup/stem variants | Select physical mic/source or document mix | Views share recordings; do not count channels/stems as independent duration. |

Use a documented resampler and verify delay/length. Do not independently resample formed reference/degraded/residual triplets. Generate effects after final clean conversion; derive residual from exact saved mono signals and remeasure. Do not denoise, dereverberate or bandwidth-extend and call the result an untouched reference; that creates another processing stratum.

Proposed acquisition fields: dataset/version/publisher URL; original recording/source URL/ID; speaker/artist/uploader/session; original interval; acquisition and release rate/channels/subtype; delivery codec/bitrate; prior_lossy_status (documented/unknown); license/attribution; archive/member checksums; decoder/resampler/downmix versions; export hash; noise/bandwidth/clip flags; artifact eligibility; dedup cluster; split; exclusion reason.

“No lossy stage documented” differs from “verified never lossy.” Automatic spectra cannot upgrade unknown provenance to pristine.

## 7. Artifact-specific inclusion

**LP:** measure energy/occupancy in 5-8,8-10,10-12,12-16,16-20 k and in each actual cutoff/transition band. Track source-codec history. Dark instruments and silence must not receive false severe-LP captions. Low-bandwidth sources remain usable for lower-cutoff operations.

**SH:** require active energy in the target bands; distinguish nominal mask coverage from active-energy-weighted coverage. Speech frication, harmonics and percussion support different masks. Baseline codec holes must not be attributed to the synthetic mask. Retain null-effect controls.

**UN:** require tonal peaks in the **processed band**, not merely harmonics at 1 k. Normal phonation and sustained instruments are promising; breathy vocals, percussion and diffuse hiss conditional. The current detector’s selection on white noise prevents claiming every selected peak was tonal. Verify retained tonal energy/envelope change; listening remains necessary.

**QN:** require low enough existing noise for the intended noise addition; container depth does not measure it. Codec-exposed/noisy references need a separate condition. Reverberation and instrument decay are not automatically noise. Audit tails because existing QN temporal spreading can overlap a strict PE holdout.

Any quantitative admission thresholds must be developed later on independent sources, stratified by content. No threshold/severity mapping was fitted here. No ODAQ audio/scores/comments/original recordings supplied calibration targets. Objective differences must not become audible/mild/bad/MUSHRA labels without perceptual evidence.

## 8. License and leakage strategy

Keep separate rights flags for internal research, transformation, processed-audio redistribution, commercial use and text. Retain attribution/change notices through cropping/resampling/degradation. NC/SA/custom terms differ. Code/metadata permissions do not relicense audio. ND prohibits sharing transformed recordings under that license; defer Opencpop from a shareable pool absent permission. [CC BY-NC-ND4 deed](https://creativecommons.org/licenses/by-nc-nd/4.0/).

Maintain a **CC0/BY reusable subset** and separate **NC/SA research subset**. Unknown/ND/BBC/YouTube/custom-disputed sources are not automatically admitted to a public processed corpus. Model-weight licensing implications require a team/institutional decision.

| Recording lineage | Connect before splitting |
|---|---|
| LibriVox chapter/performance | LibriSpeech/LibriTTS/Libri-Light/MLS/Hi-Fi TTS; possible People’s Speech/Internet Archive reuse |
| Freesound ID/uploader/session | FSD50K/FSDnoisy/Clotho/ESC50/UrbanSound/WavCaps; some ODAQ originals |
| BBC asset | BBC archive and WavCaps component; reposts |
| YouTube/original production | AudioSet/WavCaps/GigaSpeech; reposts |
| Music recording | MedleyDB/MUSDB/DSD100; possible FMA/Jamendo shared catalogs; mixes/stems |
| Reorganizations/re-encodes | FMA subsets, Jamendo audio-low/tag subsets, VocalSet folders/versions, VCTK mics |
| Synthetic score/scene | Slakh repeated MIDI, GuitarSet related takes, DEMAND/machine channels/SNR views |

Proposed deduplication:

1. Canonicalize original service URLs/IDs, filenames, recording/session/book/chapter and intervals before cropping. Release versions are views.
2. Compare original and canonical decoded-audio hashes among candidate corpora; re-encoding/gain changes defeat simple file hashes.
3. Use robust fingerprints/windowed similarity for trims/re-encodes/reposts; manually review uncertain matches. Same words or composition alone do not prove same recording.
4. Form connected recording components across mics/stems/crops/channels/variants, then assign deterministic source-level splits. Prefer speaker/artist/uploader/session separation; preserve official splits when claiming benchmark scores.
5. Store method/confidence, provenance and exclusion/registry versions. Unknown origin -> quarantine. Do not sum hours before grouping.

**ODAQ exclusion:** this task read only the three released detailed-license attribution CSVs: original filenames, source links, authors/licenses. It built a blacklist with **14 distinct Freesound IDs** and non-Freesound original productions (Netflix/BSU, Blender, SoundCloud, others). No ODAQ WAVs/ratings/comments/signal-analysis outputs were used. Exclude entire original recordings/productions, alternate excerpts and stems, not only named benchmark crops. Fourteen IDs alone cannot guarantee separation.

Clotho metadata has **zero exact matches to those 14 IDs**; this narrow check does not certify absence of reposted/hidden overlap. ESC convenience examples passed that known-ID filter. Ask evaluation owners for a complete authoritative exclusion ledger. Any later ODAQ-reference fingerprint comparison should be isolated leakage screening returning only exclusion decisions, never training features or calibration/parameter-selection evidence. No corpus-wide similarity screening was performed here.

## 9. Published, downloadable and eligible hours

Published = publisher duration for the specified population; arithmetic-derived values are labeled. Downloadable = actually advertised/obtainable under access and use constraints; a published upper bound is not a full verified transfer. Eligible = deduplicated licensed non-ODAQ audio passing content/artifact QC after conversion. **Full-corpus eligible hours are unknown.**

| Stratum, deliberately non-additive | Published examples | Downloadability / restriction | Eligible |
|---|---|---|---|
| Promising controlled full-band | EARS100 h; MAESTRO198.7; VocalSet 10.1; DAPS~4.5 clean; GuitarSet~3 nominal; VCTK exact hours unverified | Public releases; EARS/VCTK/GuitarSet/VocalSet bounded samples verified; NC/SA differ | Unknown |
| Lower-bandwidth usable speech/notes | LibriSpeech 100.6/363.6/496.7 paper-reported; MLS~50.5 kh; Libri-Light~60 kh headline; LibriTTS~585; NSynth~340 derived note h | Public originals/repackages; native limits and audiobook ancestry; LibriSpeech sample verified | Unknown |
| Lossy/provenance-QC | CVscripted 42593 h; People’s Speech 30000+; FMA8232 full h; Jamendo exact h unknown; WavCaps~7567 rounded-mean-derived | Mixed MDC/public/academic access; also includes audiobook FLAC above | Unknown |
| Access/use restricted | GigaSpeech 10000 labeled; Medley duration unknown; Opencpop 5.2; EARS/MAESTRO NC; BBC custom | Gate observed; full Medley access unconfirmed; ND/custom terms may block shared derivatives | Unknown |
| Metadata-only/unreliable waveform route | AudioSet~5793 nominal 10 s-derived h; NUS total unverified | Official AudioSet has no waveform archive; NUS original download unavailable; source survival unknown | Unknown |

Rows overlap. Do not sum them or dataset versions. FSD/Clotho/WavCaps/BBC also share source material. The only actual decoded duration here is 122.236 s of convenience examples, not an accepted reference pool.

## 10. Decisions and limitations

Completed:38-entry survey, remote evidence cache,16 file checks, count/license discrepancy flags, artifact suitability judgments and a 200 h candidate plan. No full dataset, generator change, listening observations or training.

Resolve before scaling:

- Commercial/redistributable audio and released-weight requirements: whether NC/SA/custom sources can be included.
- A cap and explicit loader metadata for lower-bandwidth/previously coded diversity.
- Independent per-artifact energy/tonality/noise/clipping/duration gates and null-effect caption policy.
- Speaker/language/genre/recording quotas and singing coverage beyond vowels/exercises.
- Clotho count scope, DEMAND license conflict, TAU derivative rights, Medley access and VocalSet 1.2 bounded-read issue.
- Evaluation-team source ledger for all ODAQ original productions and variants.
- UN specificity/QN locality/STFT overlap acceptance under strict PE/TM holdouts.

Begin with small GuitarSet mic, selected EARS/VCTK and ordinary-phonation VocalSet acquisitions, then independently licensed mixed/percussive material and filtered FSD50K. Validate gates before bulk downloads.

## 11. Dataset citations and source notes

Primary release/paper links and citations follow. The CSV retains separate verification/access/redistribution fields. A linked paper is not proof that uninspected download bytes match it.

### Mozilla Common Voice Scripted Speech

Ardila et al., Common Voice, LREC 2020; v 27 release announcement 2026. [evidence 1](https://discourse.mozilla.org/t/common-voice-scripted-speech-v27-0-and-spontaneous-speech-v5-0-released/149490) [evidence 2](https://commonvoice.mozilla.org/es/datasets) [evidence 3](https://arxiv.org/abs/1912.06670)

Provenance: Crowdsourced browser/device recordings in uncontrolled rooms. Content metadata: client_id, locale, sentence/transcript, votes, demographic fields when supplied; pin locale schema. Limitation: Noise, clipping, device DSP, differing effective bandwidth; text validation is not a fidelity rating. Obtainable scope: unknown accessible/validated total; up to ~42593 advertised across locales. Actual files inspected: none.

### Mozilla Common Voice Spontaneous Speech

Mozilla, Common Voice Spontaneous Speech v 5 release, 2026. [evidence 1](https://discourse.mozilla.org/t/common-voice-scripted-speech-v27-0-and-spontaneous-speech-v5-0-released/149490)

Provenance: Volunteer free-form answers recorded on consumer devices. Content metadata: Questions, transcripts and contributor/language metadata; exact export schema unverified. Limitation: Unmeasured corpus-level fidelity; sample rate alone is insufficient. Obtainable scope: unknown; published total is not a verified obtainable total. Actual files inspected: none.

### LibriSpeech train-clean-100

Panayotov et al., LibriSpeech, ICASSP 2015. [evidence 1](https://www.openslr.org/12/)

Provenance: LibriVox audiobooks; OpenSLR also distributes original-mp 3 archive. Content metadata: Speaker/chapter/book IDs, transcripts, speaker metadata. Limitation: "clean" is an ASR partition, not guaranteed absence of noise/codec artifacts; other-500 especially variable. Obtainable scope: Up to 100 nominal hours advertised publicly; complete archive not verified. Actual files inspected: One native mono 16 k PCM_16 FLAC, 12.965 s.

### LibriSpeech train-clean-360

Panayotov et al., LibriSpeech, ICASSP 2015. [evidence 1](https://www.openslr.org/12/)

Provenance: LibriVox audiobooks; OpenSLR also distributes original-mp 3 archive. Content metadata: Speaker/chapter/book IDs, transcripts, speaker metadata. Limitation: "clean" is an ASR partition, not guaranteed absence of noise/codec artifacts; other-500 especially variable. Obtainable scope: Up to 360 nominal hours advertised publicly; complete archive not verified. Actual files inspected: none.

### LibriSpeech train-other-500

Panayotov et al., LibriSpeech, ICASSP 2015. [evidence 1](https://www.openslr.org/12/)

Provenance: LibriVox audiobooks; OpenSLR also distributes original-mp 3 archive. Content metadata: Speaker/chapter/book IDs, transcripts, speaker metadata. Limitation: "clean" is an ASR partition, not guaranteed absence of noise/codec artifacts; other-500 especially variable. Obtainable scope: Up to 500 nominal hours advertised publicly; complete archive not verified. Actual files inspected: none.

### CSTR VCTK Corpus

Yamagishi, Veaux & MacDonald, CSTR VCTK Corpus 0.92, 2019, doi:10.7488/ds/2645. [evidence 1](https://datashare.ed.ac.uk/handle/10283/3443)

Provenance: Identical dual-mic setup, hemi-anechoic chamber; DPA4035 / MKH800. Content metadata: Speaker IDs, accent/demographics, sentence transcripts; p 315 text missing. Limitation: Two mic variants are duplicate performances; mic 2 technical issues for p 280/p 315; utterance trimming. Obtainable scope: unknown exact hours; public 11.75 GB archive and bounded member acquisition verified. Actual files inspected: One 48 k mono PCM_16 FLAC via bounded ZIP plus complete ZIP directory listing;88,328 audio entries.

### DAPS - Device and Produced Speech

Mysore, IEEE Signal Processing Letters 22(8), 2015, doi:10.1109/LSP.2014.2379648. [evidence 1](https://zenodo.org/records/4660670)

Provenance: Studio speech plus produced versions and consumer-device re-recordings. Content metadata: Speaker and script IDs, aligned condition recordings. Limitation: Use clean only; produced/equalized/device versions change baseline quality. Obtainable scope: Up to ~4.5 unique clean hours advertised; public archive listed, not acquired. Actual files inspected: none.

### Segmented DAPS

Morrison et al., Segmented DAPS 2021; cite Mysore 2015. [evidence 1](https://zenodo.org/records/4783456)

Provenance: First script of original DAPS clean partition, sentence segmentation. Content metadata: Sentence text; phone and word alignments; speaker/script IDs. Limitation: Sentence crops and boundary artifacts; same recordings as DAPS. Obtainable scope: unknown, bounded above by DAPS ~4.5 clean hours. Actual files inspected: none.

### Multilingual LibriSpeech

Pratap et al., MLS, arXiv:2012.03411 v 2, 2020. [evidence 1](https://www.openslr.org/94/) [evidence 2](https://arxiv.org/html/2012.03411v2)

Provenance: LibriVox downloads using Libri-Light acquisition tools; 10-20 s segmentation. Content metadata: Speaker/book IDs, transcripts, limited-supervision subsets. Limitation: Unmeasured corpus-level fidelity; sample rate alone is insufficient. Obtainable scope: Up to ~50500 advertised publicly; practical selected-language subset only; full transfer not tested. Actual files inspected: none.

### Libri-Light

Kahn et al., Libri-Light, ICASSP 2020, arXiv:1912.07875. [evidence 1](https://github.com/facebookresearch/libri-light/tree/main/data_preparation) [evidence 2](https://github.com/facebookresearch/libri-light/blob/main/LICENSE)

Provenance: LibriVox audiobook harvesting; explicit MP3-to-FLAC conversion scripts. Content metadata: LibriVox speaker/book IDs; VAD/SNR metadata; unlabeled speech. Limitation: Unmeasured corpus-level fidelity; sample rate alone is insufficient. Obtainable scope: Listed partitions advertised; exact reachable source-clean hours unknown; multi-TB deferred. Actual files inspected: none.

### The People’s Speech

Galvez et al., The People’s Speech, NeurIPS Datasets and Benchmarks 2021, arXiv:2111.09344. [evidence 1](https://huggingface.co/datasets/MLCommons/peoples_speech)

Provenance: Internet Archive recordings incl proceedings, histories, speeches; source example explicitly .mp 3 origin. Content metadata: Source id, duration_ms, transcript; clean/dirty and SA configs. Limitation: Background noise and transcript alignment problems documented; clean label not a pristine-audio guarantee. Obtainable scope: Up to 30000+ advertised; selected config accessible via HF, complete audio untested. Actual files inspected: none.

### GigaSpeech

Chen et al., GigaSpeech, Interspeech 2021, arXiv:2106.06909. [evidence 1](https://github.com/SpeechColab/GigaSpeech) [evidence 2](https://huggingface.co/datasets/speechcolab/gigaspeech)

Provenance: Audiobooks, podcasts, YouTube. Content metadata: aid/sid, source URL, category, timestamps, transcript, subset IDs. Limitation: Background music/noise and existing codec artifacts; ASR transcription quality is not fidelity. Obtainable scope: unknown until access granted; nominal labeled subset sizes 10/250/1000/2500/10000 h. Actual files inspected: none.

### EARS - Expressive Anechoic Recordings of Speech

Richter et al., EARS, Interspeech 2024, arXiv:2406.06185. [evidence 1](https://github.com/facebookresearch/ears_dataset)

Provenance: Anechoic recording; reading styles,22 emotions, freeform monologues. Content metadata: Speaker demographics, native language, reading transcripts, style/emotion filenames. Limitation: Whisper/yell/tails and actual HF activity vary; exclude noisy blind-test release. Obtainable scope: Up to 100 h advertised; one speaker archive member fetched successfully. Actual files inspected: One clean speaker p 001 WAV via bounded ZIP;48 k mono FLOAT.

### LibriTTS

Zen et al., LibriTTS, Interspeech 2019, arXiv:1904.02882. [evidence 1](https://www.openslr.org/60/)

Provenance: Explicitly reprocessed original LibriSpeech LibriVox MP3 and Gutenberg material. Content metadata: Speaker/chapter/utterance IDs, normalized and original text. Limitation: Unmeasured corpus-level fidelity; sample rate alone is insufficient. Obtainable scope: Up to~585 h advertised publicly; not fetched. Actual files inspected: none.

### Hi-Fi Multi-Speaker English TTS (Hi-Fi TTS)

Bakhturina et al., Hi-Fi TTS, Interspeech 2021, arXiv:2104.01497. [evidence 1](https://www.openslr.org/109/) [evidence 2](https://arxiv.org/abs/2104.01497)

Provenance: LibriVox audiobooks; paper selects bandwidth >=13 kHz and SNR>=32 dB. Content metadata: Speaker IDs, transcripts, quality subsets/manifests. Limitation: 13 k minimum selection bandwidth does not establish 16 k support; author SNR is not our independent noise measurement. Obtainable scope: Up to 291.6 advertised publicly; archive untested. Actual files inspected: none.

### MAESTRO

Hawthorne et al., Enabling Factorized Piano Music Modeling and Generation, ICLR2019. [evidence 1](https://magenta.tensorflow.org/datasets/maestro)

Provenance: International Piano-e-Competition Yamaha Disklavier acoustic grand recordings. Content metadata: Composer, piece, year, performance path, MIDI, composition-disjoint splits. Limitation: Piano-only content; hall/mic noise and natural ringing; MIDI duration not necessarily exact WAV duration. Obtainable scope: Up to 198.7 publicly advertised; only metadata surveyed. Actual files inspected: none.

### Slakh2100-redux

Manilow et al., Cutting Music Source Separation Some Slakh, WASPAA2019. [evidence 1](https://zenodo.org/records/4599666)

Provenance: Lakh MIDI rendered using 187 sample-based instrument patches;34 classes. Content metadata: Track ID, instrument, program, synth patch, aligned MIDI, split/omitted group. Limitation: Synthetic timbre/mixing, repeated MIDI; does not replace real-room recordings. Obtainable scope: Up to 145 mixture hours advertised; unique non-omitted duration unknown. Actual files inspected: none.

### MUSDB18-HQ

Rafii et al., MUSDB18 corpus, 2017/2019 HQ release. [evidence 1](https://zenodo.org/records/3338373) [evidence 2](https://sigsep.github.io/datasets/musdb.html)

Provenance: 100 DSD100/Mixing Secrets,46 MedleyDB,2 Native Instruments,2 Easton Ellises recordings. Content metadata: Song/artist, genre, source/license track list, stem identity. Limitation: Unmeasured corpus-level fidelity; sample rate alone is insufficient. Obtainable scope: Up to~10 mixture hours advertised;8 existing excerpts already local to KNN. Actual files inspected: 8 existing 8 s DOUBLE stereo WAV excerpts; recorded upstream PCM_16 headers.

### GuitarSet

Xi et al., GuitarSet, ISMIR2018. [evidence 1](https://guitarset.weebly.com/) [evidence 2](https://zenodo.org/records/3371780)

Provenance: 6 players; NeumannU87 mic and hexaphonic pickup; backing tracks used in sessions. Content metadata: Player/style/progression/tempo, strings/notes/pitch/chords/beats. Limitation: Solo file inspected 14.4 s, illustrating ~30 s is not exact; possible backing bleed; pickup debleeding changes signal. Obtainable scope: ~3 nominal mic hours public; exact decoded duration unknown. Actual files inspected: One 14.4 s 44.1 k mono PCM_16 mic WAV via ZIP.

### MusicNet

Thickstun,Harchaoui & Kakade, Learning Features of Music from Scratch, ICLR2017, arXiv:1611.09827. [evidence 1](https://zenodo.org/records/5120004) [evidence 2](https://arxiv.org/abs/1611.09827)

Provenance: Isabella Stewart Gardner Museum, European Archive, Musopen performances; per-recording source metadata. Content metadata: Recording source/composer/ensemble; time-aligned note/instrument CSV, MIDI. Limitation: Historical/mixed recording chains; score alignment labels estimated 4% errors, not artifact labels. Obtainable scope: Up to 34 advertised public; per-license usable duration unknown. Actual files inspected: none.

### MedleyDB

Bittner et al., MedleyDB, ISMIR2014; MedleyDB2 release documentation. [evidence 1](https://medleydb.weebly.com/description.html) [evidence 2](https://medleydb.weebly.com/downloads.html)

Provenance: Independent artists, NYU studio, Weathervane, Music Delta; majority professional studios. Content metadata: Artist/title, instruments, source/stem mapping, melody/activation annotations. Limitation: Studio mastering/reverb, varied content; stem quality differs from mixture. Obtainable scope: unknown accessible full duration; existing 8 MedleyDB-derived pilot excerpts verified. Actual files inspected: none.

### FMA - Free Music Archive dataset

Defferrard et al., FMA: A Dataset for Music Analysis, ISMIR2017. [evidence 1](https://github.com/mdeff/fma)

Provenance: User/artist uploads to Free Music Archive. Content metadata: Track/artist/album IDs, genres,tags,license URLs,technical fields. Limitation: Existing coding artifacts, source mastering and broken/clipped files require QC. Obtainable scope: Up to 8232 reported full hours advertised; license-filtered reachable duration unknown. Actual files inspected: none.

### MTG-Jamendo

Bogdanov et al., MTG-Jamendo Dataset for Automatic Music Tagging, ICML ML4 MD2019. [evidence 1](https://github.com/MTG/mtg-jamendo-dataset)

Provenance: Jamendo artist uploads; full tracks longer than 30 s. Content metadata: Track/artist/album IDs,195 genre/instrument/mood tags, audio_licenses.txt. Limitation: Compression and mastering artifacts; weak content tags; smaller low version unsuitable for clean-baseline claims. Obtainable scope: unknown exact duration; public scripted multipart audio download advertised. Actual files inspected: none.

### NSynth

Engel et al., Neural Audio Synthesis of Musical Notes with WaveNet Autoencoders, ICML2017. [evidence 1](https://magenta.tensorflow.org/datasets/nsynth)

Provenance: 1006 acoustic/electronic/synthetic sampled instruments;4-second rendered notes. Content metadata: Instrument/family/source, pitch, velocity,qualities; instrument-disjoint official splits. Limitation: Many qualities include distortion; velocity duplicates, silence/decay; upperband absent. Obtainable scope: Up to~339.977 nominal note hours public; active/unique eligible hours unknown. Actual files inspected: none.

### VocalSet

Wilkins,Seetharaman,Wahl & Pardo, VocalSet, ISMIR2018. [evidence 1](https://zenodo.org/records/1442513)

Provenance: Professional singers; vowels,scales,arpeggios,extended techniques and short songs. Content metadata: Singer,technique,vowel,voice type; organized folder variants. Limitation: Extended vocal techniques can already be noisy;1.2 bounded ZIP-member read failed with Truncated file header,1.1 retry succeeded; no whole-archive validation. Obtainable scope: Up to 10.1 unique hours public; duplicate organization and quality-filtered duration unknown. Actual files inspected: One 7.863 s 44.1 k mono PCM_16 vocal-fry WAV from alternate 1.1 ZIP;3613 physical WAV entries indexed, uniqueness not established.

### Opencpop

Wang et al., Opencpop, Interspeech 2022, arXiv:2201.07429. [evidence 1](https://wenet-e2e.github.io/opencpop/) [evidence 2](https://wenet-e2e.github.io/opencpop/liscense/)

Provenance: Professional female singer in studio; Mandarin popular songs. Content metadata: Lyrics,notes/phonemes, boundaries,pitch; song IDs. Limitation: Single singer and copyrighted composition chain; ND conflict with public degraded examples. Obtainable scope: 5.2 advertised; zero approved for redistributed transformed pool without separate permission. Actual files inspected: none.

### NUS Sung and Spoken Lyrics Corpus (NUS-48 E)

Duan,Fang,Li,Sim & Wang, NUS Sung and Spoken Lyrics Corpus, APSIPA ASC2013. [evidence 1](https://smcnus.comp.nus.edu.sg/archive/pdf/2012-2013/2013_05-Pub-NUS-48E.pdf)

Provenance: Controlled singing/spoken performances of English songs;12 subjects. Content metadata: Song/singer IDs and phone alignments described in paper. Limitation: Small pool; rights and accessible original release unresolved. Obtainable scope: unknown; not admitted to initial pool. Actual files inspected: none.

### FSD50K

Fonseca et al., FSD50K, IEEE/ACM TASLP30:829-852,2022. [evidence 1](https://zenodo.org/records/4060432)

Provenance: Freesound uploads, diverse devices/sound-production processes. Content metadata: Freesound ID/uploader/title/tags/license;200 event classes; predominance labels. Limitation: Community noise,bandlimiting,clipping,synthetic effects; human event labels not fidelity certification. Obtainable scope: Up to 108.3 public; license-filtered non-ODAQ obtainable hours unknown. Actual files inspected: none.

### Clotho

Drossos,Lipping & Virtanen, Clotho, ICASSP2020, doi:10.1109/ICASSP40776.2020.9052990. [evidence 1](https://zenodo.org/records/4783391)

Provenance: Freesound clips,15-30 s excerpts. Content metadata: sound_id/link,uploader,keywords,license,excerpt sample bounds (sometimes empty);five captions. Limitation: Prior codec/noise varies; metadata CSV mixed encoding; caption accuracy unrelated to quality. Obtainable scope: unknown exact, public archives listed;5929 metadata-linked clips, not 6974 verified waveforms. Actual files inspected: none.

### ESC-50

Piczak, ESC: Dataset for Environmental Sound Classification, ACM MM2015. [evidence 1](https://github.com/karolpiczak/ESC-50)

Provenance: Freesound excerpts, source-dependent preprocessing. Content metadata: Freesound sourceID,take,category,fold,ESC10 membership; per-clip attributions. Limitation: Author warns source-dependent bandlimiting and classification leakage; sample rain effectively lacks>10 kHz. Obtainable scope: Up to 2.778 nominal hours public;3 samples verified, usable hours unknown. Actual files inspected: 3 mono 44.1 k PCM_16 WAVs (dog,rain,engine); source IDs not in known ODAQ blacklist.

### UrbanSound8K

Salamon,Jacoby & Bello, A Dataset and Taxonomy for Urban Sound Research, ACM MM2014. [evidence 1](https://urbansounddataset.weebly.com/urbansound8k.html)

Provenance: Freesound field-recording excerpts. Content metadata: fsID,start,end,salience,class,fold; source-linked filename. Limitation: Noise/mixed scenes, variable recording rates and short duration; original-fold/source leakage. Obtainable scope: unknown until current archive/metadata acquisition; clip counts do not establish duration. Actual files inspected: none.

### FSDnoisy18k

Fonseca et al., Learning Sound Event Classifiers from Web Audio with Noisy Labels, ICASSP2019. [evidence 1](https://zenodo.org/records/2529934)

Provenance: Freesound; manually validated label subset and unvalidated tags. Content metadata: Freesound fname,label,manually_verified,noisy_small; license mapping. Limitation: "clean" means correct/complete labels, not acoustically clean; source codec/noise varies. Obtainable scope: Up to 42.5 public; noise/fidelity-screened hours unknown. Actual files inspected: none.

### WavCaps

Mei et al., WavCaps, IEEE/ACM TASLP2024, arXiv:2303.17395. [evidence 1](https://github.com/XinhaoMei/WavCaps) [evidence 2](https://huggingface.co/datasets/cvssp/WavCaps)

Provenance: Freesound/BBC/SoundBible/AudioSet; caption text LLM processed. Content metadata: Source IDs/URLs, raw and generated descriptions; AudioSet timestamps recovered from source metadata. Limitation: Duplicate sources, existing codecs, auto-caption hallucination; no fidelity labels. Obtainable scope: unknown source-cleared hours; FLAC ZIPs advertised, not acquired. Actual files inspected: none.

### BBC Sound Effects

BBC Sound Effects Archive; cite individual effect ID and license. [evidence 1](https://sound-effects.bbcrewind.co.uk/about) [evidence 2](https://sound-effects.bbcrewind.co.uk/licensing)

Provenance: BBC production archive, variable era/equipment/mastering. Content metadata: Effect title/description/category, stable effect IDs; exact API/export not verified. Limitation: Historical hiss,edit/compression/recording defects; nominal WAV not fidelity proof. Obtainable scope: unknown; item access does not establish lawful bulk-training availability. Actual files inspected: none.

### DEMAND - Diverse Environments Multichannel Acoustic Noise Database

Thiemann,Ito & Vincent, DEMAND, 2013; doi:10.5281/zenodo.1227121. [evidence 1](https://zenodo.org/records/1227121) [evidence 2](https://zenodo.org/records/1227121/files/DEMAND.pdf?download=1)

Provenance: Real field environments recorded with microphone array. Content metadata: Environment names, categories, array positions/recording setup. Limitation: Designed as background noise, not clean isolated source; avoid QN severity calibration. Obtainable scope: unknown exact unique duration; publicly listed 18 environment archives. Actual files inspected: none.

### AudioSet

Gemmeke et al., Audio Set, ICASSP2017. [evidence 1](https://research.google.com/audioset/download.html)

Provenance: YouTube user uploads and re-uploads. Content metadata: YouTube ID,start/end,ontology labels; strong timestamps separate. Limitation: Unknown codec history,noise,mixing; download attrition and rights risks. Obtainable scope: unknown source-cleared live audio;0 waveform hours supplied by official metadata download. Actual files inspected: none.

### TAU Urban Acoustic Scenes 2019 development

Mesaros et al., A multi-device dataset for urban acoustic scene classification, DCASE2018;2019 release. [evidence 1](https://zenodo.org/records/2589280) [evidence 2](https://github.com/toni-heittola/dcase2019_task1_baseline)

Provenance: Binaural urban field recordings,10 scenes/10 cities. Content metadata: Scene label,city/location/recording identifiers, official splits. Limitation: Diffuse ambience and noise, not isolated clean sounds; mono downmix changes binaural recording. Obtainable scope: Up to 40 h public; exact license-cleared duration after grouping unknown. Actual files inspected: none.

### MIMII - Malfunctioning Industrial Machine Investigation and Inspection

Purohit et al., MIMII Dataset, DCASE2019, arXiv:1909.09347. [evidence 1](https://zenodo.org/records/3384388)

Provenance: Machines recorded via array; factory background noises mixed at-6/0/+6 dB. Content metadata: Machine type/ID,normal/anomaly,noise-SNR variant; no general captions. Limitation: Factory-noise mixtures are not clean machine masters;8 kNyquist excludes high LP. Obtainable scope: unknown unique duration; public archives available but noisy-source eligibility unresolved. Actual files inspected: none.


## 12. Evidence paths and reproducibility

Remote root: **/data/tingyup2/projects/AudioLM/LMushra/data/external/clean_corpus_survey/**.

- fetch_receipt*.json and cached official pages/API records: sources, byte counts, successes/failures; earlier receipts includeSHA256.
- inventory_rows.json: curated 47-column CSV input.
- sample_receipt.json: URLs,members,licenses,CRC scope,recorded transfer bytes and failures.
- sample_measurements.json:16 header/measurement/SHA256 records.
- vctk_archive_audio_index.json and vocalset11_archive_index.json: physical entry inventories, not unique-performance totals.
- odaq_provenance_exclusion.json: attribution only, no audio/scores/comments.
- inspect_cached_samples.py: offline deterministic remeasurement.
- author_inventory.py, finalize_inventory.py, write_reports.py: remote survey authoring helpers. Acquisition helpers preserve one-off procedures; do not run them as bulk downloaders.

Recheck without new downloads:

~~~bash
ssh -S /private/tmp/codex-audiolm-knn-push.sock tingyup 2@knn.cs.illinois.edu
cd /data/tingyup2/projects/AudioLM/LMushra
. ../env.sh
python data/external/clean_corpus_survey/inspect_cached_samples.py
python data/external/clean_corpus_survey/finalize_inventory.py
python data/external/clean_corpus_survey/write_reports.py
python data/external/clean_corpus_survey/verify_survey.py
~~~

Socket is session-specific; use ordinary authorized SSH if expired. For a fresh CSV reconstruction, author_inventory.py creates initial curated rows, followed by finalize_inventory.py for reviewed corrections. Offline measurements use cached files only; report generation does not fetch or synthesize audio.

Checks: CSV UTF-8/38-row/47-column round trip, unique IDs, required-corpus coverage, valid suitability values, explicit unknown eligibility, nonempty fields, local Markdown-link targets, saved-file SHA256/finite values and deterministic repeat measurement/report output. Existing tracked generator/config/test files remain unchanged; unrelated calibration work is preserved. No reason to repeat unrelated generator tests for this documentation-only change.

Requested deliverable isCSV. Artifact-tool/runtime/authoring marker are absent on KNN; standard-library csv was used without creating an unrequestedXLSX or local Mac artifacts. Raw evidence/audio is Git-ignored. Requested documents remain uncommitted; no commit/push is implied.
