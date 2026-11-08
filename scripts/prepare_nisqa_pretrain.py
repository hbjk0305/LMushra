"""Convert published NISQA quality captions into Swift SFT JSONL (no ALLD).

Keep single-audio MOS descriptions and two-audio A/B tasks distinct. Validation
is a deterministic reference-utterance holdout, not a speaker-disjoint benchmark.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import soundfile as sf


def prepare(corpus, captions, output, val_ratio=0.05, seed=42):
    corpus = corpus.resolve()

    def relative(value):
        marker = '/NISQA_Corpus/'
        if marker not in value:
            raise ValueError(f'Expected NISQA_Corpus path: {value}')
        rel = value.split(marker, 1)[1]
        path = (corpus / rel).resolve()
        if not path.is_relative_to(corpus):
            raise ValueError(f'Path escapes corpus: {value}')
        return path.relative_to(corpus).as_posix()

    def read(name):
        return [json.loads(line) for line in (captions / name).read_text().splitlines() if line.strip()]

    single = read('train_nisqa_llama_10k.json')
    pairs = read('train_nisqa_abtest_llama_10k.json')
    sources = {}
    for row in single:
        key = relative(row['audios'][0])
        source = relative(row['clean_path'][0])
        if key in sources and sources[key] != source:
            raise ValueError(f'Conflicting reference for {key}')
        sources[key] = source
    # CSV covers A/B audios not present in the single-audio annotation subset.
    csv_path = corpus / 'NISQA_corpus_file.csv'
    if csv_path.exists():
        import csv
        with csv_path.open(newline='') as stream:
            for row in csv.DictReader(stream):
                key = row['filepath_deg'].replace('\\', '/')
                source = row['filepath_ref'].replace('\\', '/')
                if key in sources and sources[key] != source:
                    raise ValueError(f'CSV/reference mismatch: {key}')
                sources[key] = source

    def split(source):
        fraction = int(hashlib.sha256(f'{seed}:{source}'.encode()).hexdigest(), 16) / 2**256
        return 'valid' if fraction < val_ratio else 'train'

    samples = {'train': [], 'valid': []}
    provenance = {'train': [], 'valid': []}
    audio_info = {}
    counts = Counter()
    for task, rows, expected in [('mos', single, 1), ('ab', pairs, 2)]:
        for index, row in enumerate(rows, 1):
            paths = [relative(p) for p in row['audios']]
            if len(paths) != expected:
                raise ValueError(f'{task}:{index}: expected {expected} audios')
            if any(not p.startswith('NISQA_TRAIN_SIM/deg/') for p in paths):
                raise ValueError(f'{task}:{index}: non-training audio in training captions')
            source_ids = [sources[p] for p in paths]  # Fail if reference identity is unknown.
            splits = {split(s) for s in source_ids}
            if len(splits) > 1:
                counts['ab_cross_split_excluded'] += 1
                continue
            target_split = splits.pop()
            query, response = row['query'].strip(), row['response'].strip()
            if query.count('<audio>') != expected or not response:
                raise ValueError(f'{task}:{index}: invalid prompt/response')
            for rel in paths:
                if rel not in audio_info:
                    info = sf.info(corpus / rel)
                    if not 0 < info.duration <= 30 or info.channels != 1:
                        raise ValueError(f'Expected mono audio <=30 seconds: {rel}')
                    audio_info[rel] = {'duration': info.duration, 'sample_rate': info.samplerate}
            samples[target_split].append({'messages': [
                {'role': 'user', 'content': query},
                {'role': 'assistant', 'content': response}],
                'audios': [str(corpus / p) for p in paths]})
            provenance[target_split].append({'task': task, 'annotation_line': index,
                                              'source_ids': source_ids, 'audio_paths': paths})
            counts[f'{target_split}_{task}'] += 1
    if not all(samples.values()):
        raise ValueError('Empty train or validation split; adjust --val-ratio or data')
    groups = {s: {g for r in rows for g in r['source_ids']} for s, rows in provenance.items()}
    if groups['train'] & groups['valid']:
        raise ValueError('Reference leakage between splits')
    output.mkdir(parents=True, exist_ok=True)
    for name in samples:
        for suffix, rows in [('.jsonl', samples[name]), ('.provenance.jsonl', provenance[name])]:
            (output / (name + suffix)).write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows))
    report = {'corpus': str(corpus), 'captions': str(captions.resolve()), 'seed': seed,
              'val_ratio': val_ratio, 'counts': dict(counts), 'unique_audio': len(audio_info),
              'source_groups': {s: len(g) for s, g in groups.items()},
              'method': 'SFT on published generated captions, not ALLD',
              'limitations': ['Reference-utterance split, not speaker-disjoint.',
                              'Single-audio MOS and A/B preference are not reference-relative captions.',
                              'Speech MOS is not MUSHRA; captions are not manually verified.']}
    (output / 'report.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, default=Path('/home/hwangbo5/data/NISQA_Corpus'))
    parser.add_argument('--captions', type=Path, default=Path('/home/hwangbo5/data/speech-quality-descriptive-caption'))
    parser.add_argument('--output', type=Path, default=Path('data/nisqa-pretrain'))
    parser.add_argument('--val-ratio', type=float, default=0.05)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    if not 0 < args.val_ratio < 1:
        parser.error('--val-ratio must be between 0 and 1')
    print(json.dumps(prepare(args.corpus, args.captions, args.output, args.val_ratio, args.seed), indent=2))


if __name__ == '__main__':
    main()
