import importlib.util
import os

import numpy as np
import pytest
import soundfile as sf
import torch
from torch.nn import functional as F


def test_encodec_native_padding_and_frame_lengths():
    from encodec import EncodecModel
    assert importlib.util.find_spec('lmushra.encodec_audio') is not None, 'EnCodec tower missing'
    from lmushra.encodec_audio import EncodecAudioTower

    codec = EncodecModel.encodec_model_24khz(pretrained=False)
    tower = EncodecAudioTower(codec.encoder, 24000, 320, 4).train()
    lengths = [1, 319, 320, 321, 1280, 1281]
    audio = torch.randn(6, 1, 1281) * 0.01
    mask = torch.arange(1281)[None] < torch.tensor(lengths)[:, None]
    features, counts = tower(audio, mask)
    assert features.shape == (6, 2, 128)
    assert counts.tolist() == [1, 1, 1, 1, 1, 2]
    # EnCodec owns its reflection/causal padding. Additional external zeros
    # change boundary features, even when token counts still look correct.
    with torch.no_grad():
        for i, length in enumerate(lengths):
            expected = F.avg_pool1d(codec.encoder(audio[i:i + 1, :, :length]), 4, 4, ceil_mode=True)
            torch.testing.assert_close(features[i, :counts[i]], expected[0].transpose(0, 1))
    assert not features.requires_grad
    assert not codec.encoder.training


def test_encodec_template_resamples_stereo(tmp_path):
    from test_dac_plugin import template
    _, tpl = template('encodec')
    path = tmp_path / 'stereo48.wav'
    sf.write(path, np.zeros((4800, 2), dtype=np.float32), 48000)
    encoded = tpl.encode({'messages': [{'role': 'user', 'content': '<audio>'},
                                       {'role': 'assistant', 'content': 'description'}], 'audios': [str(path)]})
    batch = tpl.data_collator([encoded])
    assert batch['input_features'].shape == (1, 1, 2400)
    assert batch['feature_attention_mask'].sum().item() == 2400
    assert encoded['input_ids'].count(2) == 2


@pytest.mark.skipif(not os.environ.get('ENCODEC_MODEL_PATH'), reason='Set ENCODEC_MODEL_PATH for pretrained test')
def test_pretrained_encodec_loader_backward_and_generation(tmp_path):
    from swift.model import MODEL_MAPPING, ModelInfo
    from transformers import Qwen2AudioForConditionalGeneration
    from test_dac_audio import tiny_model
    from test_dac_plugin import plugin

    module = plugin('encodec')
    config = tiny_model().config
    directory = tmp_path / 'base'
    Qwen2AudioForConditionalGeneration(config).save_pretrained(directory)
    info = ModelInfo('qwen2_audio_encodec', str(directory), torch.float32, 4096, None, None,
                     config=config, task_type='causal_lm', is_multimodal=True)
    loader = module.EncodecQwenLoader(info, MODEL_MAPPING['qwen2_audio_encodec'], load_model=True, model_kwargs={})
    model = loader.get_model(str(directory), config, None, dict(torch_dtype=torch.float32)).train()
    audio = torch.randn(2, 1, 2400) * 0.01
    mask = torch.tensor([[1] * 2400, [1] * 321 + [0] * 2079])
    features, lengths = model.audio_tower(audio, mask)
    assert features.shape == (2, 2, 128)
    assert lengths.tolist() == [2, 1]
    changed = audio.clone()
    changed[1, :, 321:] = 1000
    torch.testing.assert_close(features, model.audio_tower(changed, mask)[0])
    ids = torch.tensor([[1, 30, 30, 2, 30, 3]])
    args = dict(input_ids=ids, attention_mask=torch.ones_like(ids),
                input_features=audio, feature_attention_mask=mask)
    result = model(**args, labels=ids.masked_fill(ids.eq(30), -100))
    result.loss.backward()
    assert torch.isfinite(result.loss)
    assert any(p.grad is not None and p.grad.abs().sum() > 0 for p in model.multi_modal_projector.parameters())
    assert all(p.grad is None for p in model.audio_tower.parameters())
    model.eval()
    assert model.generate(**args, num_beams=2, max_new_tokens=2,
                          eos_token_id=None, pad_token_id=0).shape == (1, 8)
