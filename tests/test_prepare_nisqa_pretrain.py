import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/prepare_nisqa_pretrain.py'


def test_conversion_keeps_tasks_and_reference_groups_separate(tmp_path):
    corpus = tmp_path / 'NISQA_Corpus'
    annotations = tmp_path / 'captions'
    annotations.mkdir()
    rows = []
    for i in range(30):
        for variant in range(2):
            rel = f'NISQA_TRAIN_SIM/deg/c{variant:05d}_source{i}.wav'
            path = corpus / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(path, np.zeros(1600), 16000)
            rows.append({'audios': ['/old/NISQA_Corpus/' + rel],
                         'clean_path': [f'/old/NISQA_Corpus/NISQA_TRAIN_SIM/ref/source{i}.wav'],
                         'query': 'Evaluate <audio>', 'response': 'Quality is good.'})
    (annotations / 'train_nisqa_llama_10k.json').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    pairs = [{'audios': [rows[i]['audios'][0], rows[i+2]['audios'][0]],
              'query': 'Compare <audio> and <audio>', 'response': 'B is better.'}
             for i in range(0, 56, 2)]
    (annotations / 'train_nisqa_abtest_llama_10k.json').write_text(''.join(json.dumps(r)+'\n' for r in pairs))
    output = tmp_path / 'out'
    result = subprocess.run([sys.executable, str(SCRIPT), '--corpus', str(corpus),
                             '--captions', str(annotations), '--output', str(output),
                             '--val-ratio', '0.3'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    groups = {}
    for split in ['train', 'valid']:
        provenance = [json.loads(l) for l in (output / f'{split}.provenance.jsonl').read_text().splitlines()]
        samples = [json.loads(l) for l in (output / f'{split}.jsonl').read_text().splitlines()]
        groups[split] = {g for r in provenance for g in r['source_ids']}
        assert samples
        for sample in samples:
            assert len(sample['audios']) == sample['messages'][0]['content'].count('<audio>')
            assert all(Path(p).is_file() for p in sample['audios'])
        assert any(len(s['audios']) == 1 for s in samples)
    assert not groups['train'] & groups['valid']
    assert any(len(json.loads(l)['audios']) == 2 for l in (output/'train.jsonl').read_text().splitlines())
    # An annotation prompt losing its audio placeholder must fail before writing output.
    rows[0]['query'] = 'Evaluate this speech'
    (annotations / 'train_nisqa_llama_10k.json').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    bad_output = tmp_path / 'bad'
    invalid = subprocess.run([sys.executable, str(SCRIPT), '--corpus', str(corpus),
                              '--captions', str(annotations), '--output', str(bad_output),
                              '--val-ratio', '0.3'], capture_output=True, text=True)
    assert invalid.returncode != 0
    assert 'invalid prompt/response' in invalid.stderr
    assert not bad_output.exists()
