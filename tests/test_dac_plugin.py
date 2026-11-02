import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf
import torch


def plugin(codec='dac'):
    path = Path(__file__).resolve().parents[1] / f'scripts/{codec}_plugin.py'
    assert path.exists(), f'ms-swift {codec} plugin is not implemented'
    spec = importlib.util.spec_from_file_location(f'{codec}_test_plugin', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def template(codec='dac'):
    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace
    from transformers import PreTrainedTokenizerFast
    from swift.model import MODEL_MAPPING
    from swift.template import get_template
    module = plugin(codec)
    backend = Tokenizer(WordLevel({'[UNK]': 0, '[PAD]': 1, '<|AUDIO|>': 2,
                                 '<|im_end|>': 3, '<|endoftext|>': 4}, unk_token='[UNK]'))
    backend.pre_tokenizer = Whitespace()
    tokenizer = PreTrainedTokenizerFast(tokenizer_object=backend, unk_token='[UNK]', pad_token='[PAD]',
                                       eos_token='<|im_end|>', additional_special_tokens=['<|AUDIO|>'])
    processor = SimpleNamespace(
        tokenizer=tokenizer, audio_token='<|AUDIO|>',
        model_info=SimpleNamespace(config=SimpleNamespace(audio_token_index=2),
                                   task_type='causal_lm', max_model_len=4096),
        model_meta=MODEL_MAPPING[f'qwen2_audio_{codec}'])
    result = get_template(processor, template_type=f'qwen2_audio_{codec}')
    result.set_mode('train')
    return module, result


@pytest.mark.parametrize('codec,rate,lengths', [('dac', 44100, [4096, 1025, 10]),
                                              ('encodec', 24000, [2560, 321, 10])])
def test_template_expands_tokens_and_collates_different_lengths(tmp_path, codec, rate, lengths):
    _, tpl = template(codec)
    paths = []
    for i, n in enumerate(lengths):
        path = tmp_path / f'{i}.wav'
        sf.write(path, np.zeros(n, dtype=np.float32), rate)
        paths.append(str(path))
    def encode(audios):
        return tpl.encode({'messages': [{'role': 'user', 'content': '<audio> ' * len(audios)},
                                       {'role': 'assistant', 'content': 'description'}], 'audios': audios})
    first, second = encode(paths[:2]), encode(paths[2:])
    assert first['input_ids'].count(2) == 3
    assert second['input_ids'].count(2) == 1
    for item in [first, second]:
        assert all(label == -100 for token, label in zip(item['input_ids'], item['labels']) if token == 2)
    batch = tpl.data_collator([first, second])
    assert batch['input_features'].shape == (3, 1, lengths[0])
    assert batch['feature_attention_mask'].sum(-1).tolist() == lengths


@pytest.mark.parametrize('codec', ['dac', 'encodec'])
def test_template_rejects_empty_audio(tmp_path, codec):
    module, tpl = template(codec)
    path = tmp_path / 'empty.wav'
    sf.write(path, np.zeros(0, dtype=np.float32), module.SAMPLE_RATE)
    with pytest.raises(ValueError, match='audio'):
        tpl.encode({'messages': [{'role': 'user', 'content': '<audio>'}], 'audios': [str(path)]})


@pytest.mark.skipif(not os.environ.get('DAC_MODEL_PATH'), reason='Set DAC_MODEL_PATH for pretrained DAC integration')
def test_loader_with_pretrained_dac(tmp_path):
    from swift.model import MODEL_MAPPING, ModelInfo
    from transformers import Qwen2AudioForConditionalGeneration
    from test_dac_audio import tiny_model

    module = plugin()
    config = tiny_model().config
    directory = tmp_path / 'base'
    Qwen2AudioForConditionalGeneration(config).save_pretrained(directory)
    info = ModelInfo('qwen2_audio_dac', str(directory), torch.float32, 4096, None, None,
                     config=config, task_type='causal_lm', is_multimodal=True)
    loader = module.DacQwenLoader(info, MODEL_MAPPING['qwen2_audio_dac'], load_model=True, model_kwargs={})
    model = loader.get_model(str(directory), config, None, dict(torch_dtype=torch.float32)).train()
    audio = torch.randn(2, 1, 4410) * 0.01
    mask = torch.tensor([[1] * 4410, [1] * 1000 + [0] * 3410])
    features, lengths = model.audio_tower(audio, mask)
    assert features.shape == (2, 3, 1024)
    assert lengths.tolist() == [3, 1]
    audio[1, :, 1000:] = 1000
    other, _ = model.audio_tower(audio, mask)
    torch.testing.assert_close(features, other)
    ids = torch.tensor([[1, 30, 30, 30, 2, 3], [1, 30, 2, 3, 0, 0]])
    labels = ids.masked_fill(ids.eq(30) | ids.eq(0), -100)
    result = model(input_ids=ids, attention_mask=ids.ne(0), input_features=audio,
                   feature_attention_mask=mask, labels=labels)
    result.loss.backward()
    assert torch.isfinite(result.loss)
    assert any(p.grad is not None and p.grad.abs().sum() > 0 for p in model.multi_modal_projector.parameters())
    assert all(p.grad is None for p in model.audio_tower.parameters())
