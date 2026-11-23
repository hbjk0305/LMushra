import json
import os
from pathlib import Path

import torch

from lmushra.audio_probe import derange_audios, filter_by_audio_count, should_probe, silence_waveforms, write_filtered_split
from lmushra.dac_audio import DacProjector, load_projector_checkpoint, maybe_zero_init_last_linear, save_projector_state


def test_probe_interval():
    assert not should_probe(0, 500)
    assert should_probe(500, 500)
    assert not should_probe(400, 500)
    assert not should_probe(500, 0)


def test_silence_keeps_shape_and_zeros_audio():
    wave = torch.ones(8)
    rows = silence_waveforms([{'input_ids': [1, 2], 'input_features': [wave]}])
    assert rows[0]['input_ids'] == [1, 2]
    assert rows[0]['input_features'][0].shape == wave.shape
    assert torch.count_nonzero(rows[0]['input_features'][0]) == 0
    assert torch.count_nonzero(wave) == 8


def test_derange_moves_every_clip():
    records = [{'audios': [f'a{i}.wav']} for i in range(5)]
    moved = derange_audios(records, seed=1)
    assert [row['audios'][0] for row in moved] != [row['audios'][0] for row in records]
    assert sorted(row['audios'][0] for row in moved) == sorted(row['audios'][0] for row in records)
    assert [row['audios'] for row in records] == [[f'a{i}.wav'] for i in range(5)]


def test_filter_split_keeps_requested_audio_count(tmp_path):
    source = tmp_path / 'src'
    source.mkdir()
    rows = [
        {'messages': [], 'audios': ['one.wav']},
        {'messages': [], 'audios': ['a.wav', 'b.wav']},
    ]
    for split in ('train', 'valid'):
        (source / f'{split}.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    counts = write_filtered_split(source, tmp_path / 'mos', 1)
    assert counts == {'train': 1, 'valid': 1}
    kept = [json.loads(line) for line in (tmp_path / 'mos' / 'train.jsonl').read_text().splitlines()]
    assert filter_by_audio_count(kept, 1) == kept


def test_projector_zero_init_and_reload(tmp_path, monkeypatch):
    projector = DacProjector(4, 6)
    monkeypatch.setenv('PROJECTOR_ZERO_INIT_LAST', '1')
    maybe_zero_init_last_linear(projector)
    assert torch.count_nonzero(projector[-1].weight) == 0
    with torch.no_grad():
        projector[-1].weight.fill_(0.25)
    path = Path(save_projector_state(projector, tmp_path))
    assert path.name == 'multi_modal_projector.pt'
    restored = DacProjector(4, 6)
    monkeypatch.setenv('PROJECTOR_CHECKPOINT', str(path))
    assert load_projector_checkpoint(restored, str(tmp_path / 'missing'))
    torch.testing.assert_close(restored[-1].weight, projector[-1].weight)
    monkeypatch.delenv('PROJECTOR_CHECKPOINT', raising=False)
    os.environ.pop('PROJECTOR_CHECKPOINT', None)
