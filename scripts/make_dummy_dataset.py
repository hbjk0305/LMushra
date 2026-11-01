"""Build a paired-input smoke dataset; captions are NOT relative descriptions.

Run after extraction: python scripts/make_dummy_dataset.py
Requires: numpy, soundfile. Original audio and annotations are never modified.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import soundfile as sf


# Adapted from docs/proposal.pdf, Sections 3 and 4.3. This two-audio dummy
# baseline has neither residual audio nor structured relative-description labels.
# Keep free-form supervision compatible with the original NISQA captions;
# do not require timestamps, frequency bounds, or MUSHRA categories absent there.
PROMPT = """Reference audio (original): <audio>
Degraded audio (processed counterpart): <audio>

Assess the perceptual quality of the degraded speech, using the reference to
identify audible changes introduced in the processed counterpart. The first
audio is the reference and the second is the signal to evaluate.

Listen for the following aspects when they are audible:
- Noise: added hiss, hum, background noise, or noise-like artifacts.
- Coloration and distortion: changes in timbre, clarity, brightness, bandwidth,
  or naturalness, including muffling, harshness, and metallic or smeared sound.
- Continuity: interruptions, dropouts, stuttering, or other temporal artifacts.
- Loudness: changes in level or fluctuations that affect listening comfort.

Write a concise natural-language paragraph describing the most salient quality
issues, their perceived strength, and how they affect overall listening quality.
Make the direction of any comparison clear: describe the degraded audio relative
to the reference. Mention timing or affected frequency regions only when they
can be identified confidently; do not invent exact timestamps or frequency values.
If no difference is perceptible, say so. If a difference is uncertain, qualify it.
Do not assume that every listed issue is present or infer a particular codec or
processing algorithm from an artifact alone. Focus on perceptual quality rather
than transcribing speech, summarizing its meaning, or choosing an A/B winner.
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, default=Path('/home/hwangbo5/data'))
    parser.add_argument('--output', type=Path, default=Path('data/dummy'))
    parser.add_argument('--train-size', type=int, default=128)
    parser.add_argument('--val-size', type=int, default=16)
    parser.add_argument('--skip-missing', action='store_true',
                        help='Explicitly allow excluding records with missing audio')
    args = parser.parse_args()
    if min(args.train_size, args.val_size) < 1:
        parser.error('split sizes must be positive')
    corpus = (args.data_root / 'NISQA_Corpus').resolve()
    source = args.data_root / 'speech-quality-descriptive-caption/train_nisqa_llama_10k.json'

    def local_path(value):
        relative = value.split('/NISQA_Corpus/', 1)[1]
        path = (corpus / relative).resolve()
        if not path.is_relative_to(corpus):
            raise ValueError(f'Invalid audio path: {path}')
        return str(path)

    candidates = []
    missing = []
    for index, line in enumerate(source.read_text().splitlines()):
        row = json.loads(line)
        ref = local_path(row['clean_path'][0])
        deg = local_path(row['audios'][0])
        if not Path(ref).is_file() or not Path(deg).is_file():
            missing.append({'annotation_line': index + 1, 'reference': ref, 'degraded': deg})
            continue
        caption = row['response'].strip()
        if not caption:
            raise ValueError(f'Empty caption at row {index}')
        candidates.append((ref, deg, caption, index))
    if missing and not args.skip_missing:
        raise ValueError(
            f'{len(missing)} records have missing audio. Finish extraction first '
            'or explicitly pass --skip-missing. No dataset files were written.')
    # Stable selection independent of annotation row order; isolate reference groups.
    groups = sorted({r[0] for r in candidates}, key=lambda p: hashlib.sha256(
        ('42:' + str(Path(p).relative_to(corpus))).encode()).hexdigest())
    by_ref = {ref: [] for ref in groups}
    for row in candidates:
        by_ref[row[0]].append(row)
    val, train = [], []
    for ref in groups:
        if len(val) < args.val_size:
            val.extend(by_ref[ref])
        else:
            train.extend(by_ref[ref])
    train, val = train[:args.train_size], val[:args.val_size]
    if len(train) != args.train_size or len(val) != args.val_size:
        raise ValueError('Not enough records for requested split sizes')
    assert not {r[0] for r in train} & {r[0] for r in val}
    args.output.mkdir(parents=True, exist_ok=True)
    report = {
        'purpose': 'Dummy pipeline validation, not a relative-description benchmark',
        'source': str(source.resolve()),
        'supervision': 'Original single-audio quality caption; reference added as input',
        'prompt': PROMPT,
        'limitations': [
            'Targets are absolute-quality captions, not verified relative descriptions.',
            'No residual audio, track embeddings, or reconstruction objective.',
            'No MUSHRA category labels; source MOS is not a MUSHRA score.',
        ],
        'selection_seed': 42,
        'candidate_count': len(candidates),
        'skipped_missing_audio': len(missing),
        'splits': {},
        'audio': {},
    }
    for name, rows in [('train', train), ('valid', val), ('overfit', train[:16])]:
        samples = []
        provenance = []
        for ref, deg, caption, index in rows:
            for audio in [ref, deg]:
                if audio not in report['audio']:
                    waveform, rate = sf.read(audio, dtype='float32', always_2d=True)
                    duration = len(waveform) / rate
                    if not 0 < duration <= 30:
                        raise ValueError(f'Unsupported duration {duration}: {audio}')
                    if waveform.shape[1] != 1:
                        raise ValueError(f'Expected mono audio: {audio}')
                    if not np.isfinite(waveform).all():
                        raise ValueError(f'Nonfinite samples: {audio}')
                    report['audio'][audio] = {'sample_rate': rate, 'duration': duration}
            samples.append({'messages': [
                {'role': 'user', 'content': PROMPT},
                {'role': 'assistant', 'content': caption},
            ], 'audios': [ref, deg]})
            provenance.append({'annotation_line': index + 1, 'reference': ref, 'degraded': deg})
        (args.output / f'{name}.jsonl').write_text(''.join(
            json.dumps(s, ensure_ascii=False) + '\n' for s in samples))
        (args.output / f'{name}.provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
        report['splits'][name] = len(samples)
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    (args.output / 'missing_audio.json').write_text(json.dumps(missing, indent=2) + '\n')
    print(json.dumps({'output': str(args.output.resolve()), 'splits': report['splits'],
                      'unique_audio_files_decoded': len(report['audio'])}, indent=2))


if __name__ == '__main__':
    main()
