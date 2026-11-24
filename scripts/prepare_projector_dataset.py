"""Prepare calibrated severity SFT manifests for either training stage."""

import argparse
import json
from pathlib import Path
from tempfile import NamedTemporaryFile


def convert(source, destination, audio_root, include_residual, include_description=False):
    count = 3 if include_residual else 2
    inputs = ['Reference: <audio>', 'Processed: <audio>', 'Residual: <audio>']
    fields = ('artifact', 'estimated_severity')
    requested = 'artifact and estimated_severity'
    if include_description:
        fields += ('description',)
        requested = 'artifact, estimated_severity, and a brief description'
    prompt = '\n'.join(inputs[:count]) + (
        f'\n\nCompare processed to reference. Return JSON with {requested}.'
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile('w', dir=destination.parent, encoding='utf-8', delete=False) as output:
        temporary = Path(output.name)
        try:
            with output, source.open(encoding='utf-8') as rows:
                for number, line in enumerate(rows, 1):
                    try:
                        row = json.loads(line)
                        audios = row['audios']
                        messages = row['messages']
                        if len(audios) != 3 or messages[-1]['role'] != 'assistant':
                            raise ValueError('expected reference, processed, residual and an assistant target')
                        target = json.loads(messages[-1]['content'])
                        labels = {key: target[key] for key in fields}
                        row = {
                            'audios': [str(audio_root / path) for path in audios[:count]],
                            'messages': [
                                {'role': 'user', 'content': prompt},
                                {'role': 'assistant', 'content': json.dumps(labels, separators=(',', ':'))},
                            ],
                        }
                        output.write(json.dumps(row, ensure_ascii=False) + '\n')
                    except (ValueError, KeyError, IndexError, TypeError) as exc:
                        raise ValueError(f'{source}:{number}: {exc}') from exc
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--audio-root', type=Path, required=True)
    parser.add_argument('--include-residual', action='store_true')
    parser.add_argument('--include-description', action='store_true')
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error('source and output directories must differ')
    audio_root = args.audio_root.resolve(strict=True)
    for split in ('train.jsonl', 'valid.jsonl'):
        convert(args.source / split, args.output / split, audio_root,
                args.include_residual, args.include_description)


if __name__ == '__main__':
    main()
