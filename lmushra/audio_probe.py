"""Fixed-slice audio-use probes and caption-split filtering.

Warmup is working only when teacher-forced CE satisfies normal < silence and
normal < shuffle. Shuffling swaps clips and must be re-encoded: placeholder
length follows waveform length.
"""
import copy
import json
import random
from pathlib import Path

import torch


def should_probe(step: int, interval: int) -> bool:
    return interval > 0 and step > 0 and step % interval == 0


def silence_waveforms(rows):
    """Same tokens and captions, with each waveform replaced by zeros."""
    silenced = []
    for row in rows:
        if 'input_features' not in row:
            raise KeyError('encoded row has no input_features')
        updated = dict(row)
        updated['input_features'] = [torch.zeros_like(torch.as_tensor(wave)) for wave in row['input_features']]
        silenced.append(updated)
    return silenced


def derange_audios(records, seed=0):
    """Move each clip to a different slot. Captions stay with their example."""
    records = copy.deepcopy(records)
    slots = [(i, j) for i, record in enumerate(records) for j in range(len(record['audios']))]
    if len(slots) < 2:
        return records
    order = list(range(len(slots)))
    rng = random.Random(seed)
    for _ in range(32):
        rng.shuffle(order)
        if all(source != dest for dest, source in enumerate(order)):
            break
    else:
        order = order[1:] + order[:1]
    clips = [records[i]['audios'][j] for i, j in slots]
    for dest, source in enumerate(order):
        i, j = slots[dest]
        records[i]['audios'][j] = clips[source]
    return records


def filter_by_audio_count(records, n_audios):
    return [record for record in records if len(record.get('audios') or []) == n_audios]


def write_filtered_split(source_dir, output_dir, n_audios):
    source_dir, output_dir = Path(source_dir), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for split in ('train', 'valid'):
        source = source_dir / f'{split}.jsonl'
        if not source.is_file():
            raise FileNotFoundError(f'Missing {source}')
        records = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
        kept = filter_by_audio_count(records, n_audios)
        if not kept:
            raise ValueError(f'No examples with {n_audios} audio clip(s) in {source}')
        (output_dir / f'{split}.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in kept))
        counts[split] = len(kept)
    return counts
