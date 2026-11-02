import copy
import importlib.util

import pytest
import torch
from torch import nn
from transformers import Qwen2AudioConfig, Qwen2AudioEncoderConfig, Qwen2Config


def components(codec='dac'):
    if codec == 'encodec':
        assert importlib.util.find_spec('lmushra.encodec_audio') is not None, 'EnCodec integration is not implemented'
        from lmushra.encodec_audio import EncodecAudioTower, Qwen2AudioEncodec
        from lmushra.dac_audio import DacProjector
        return EncodecAudioTower, DacProjector, Qwen2AudioEncodec
    from lmushra.dac_audio import DacAudioTower, DacProjector, Qwen2AudioDac
    return DacAudioTower, DacProjector, Qwen2AudioDac


def tiny_model(codec='dac'):
    tower_cls, projector_cls, model_cls = components(codec)
    config = Qwen2AudioConfig(
        audio_config=Qwen2AudioEncoderConfig(
            num_mel_bins=4, encoder_layers=1, encoder_attention_heads=2,
            encoder_ffn_dim=16, d_model=8, max_source_positions=16),
        text_config=Qwen2Config(vocab_size=32, hidden_size=16, intermediate_size=32,
                               num_hidden_layers=1, num_attention_heads=2,
                               num_key_value_heads=2, pad_token_id=0),
        audio_token_index=30, pad_token_id=0)
    model = model_cls(config)
    # A real convolutional encoder exercises crop-before-encode boundary behavior;
    # the downloaded DAC weights are deliberately excluded from unit tests.
    model.audio_tower = tower_cls(nn.Conv1d(1, 8, 3, stride=2, padding=1),
                                 sample_rate=16000, hop_length=2, pool_size=2)
    model.multi_modal_projector = projector_cls(8, 16)
    return model


@pytest.fixture(params=['dac', 'encodec'])
def model_factory(request):
    return lambda: tiny_model(request.param)


def test_padding_isolation_and_frozen_encoder(model_factory):
    model = model_factory().train()
    audio = torch.randn(2, 1, 12)
    mask = torch.tensor([[1] * 12, [1] * 5 + [0] * 7])
    features, lengths = model.audio_tower(audio, mask)
    changed = audio.clone()
    changed[1, :, 5:] = 1000
    other, _ = model.audio_tower(changed, mask)
    assert lengths.tolist() == [3, 2]
    torch.testing.assert_close(features, other)
    assert not model.audio_tower.encoder.training
    assert not features.requires_grad
    with pytest.raises(ValueError):
        model.audio_tower(audio, torch.zeros_like(mask))


def test_forward_backward_and_token_mismatch(model_factory):
    model = model_factory().train()
    ids = torch.tensor([[1, 30, 30, 30, 2, 3], [1, 30, 30, 2, 3, 0]])
    args = dict(input_ids=ids, attention_mask=ids.ne(0),
                input_features=torch.randn(2, 1, 12),
                feature_attention_mask=torch.tensor([[1] * 12, [1] * 5 + [0] * 7]))
    labels = ids.masked_fill(ids.eq(30) | ids.eq(0), -100)
    result = model(**args, labels=labels)
    assert torch.isfinite(result.loss)
    result.loss.backward()
    assert any(p.grad is not None and p.grad.abs().sum() > 0
               for p in model.multi_modal_projector.parameters())
    assert all(p.grad is None for p in model.audio_tower.parameters())
    with pytest.raises(ValueError, match='audio'):
        model(**{**args, 'input_ids': ids.masked_fill(ids.eq(30), 4)})


@pytest.mark.parametrize('num_beams', [1, 2])
def test_cached_generation(num_beams, model_factory):
    model = model_factory().eval()
    generated = model.generate(
        input_ids=torch.tensor([[1, 30, 30, 2]]), attention_mask=torch.ones(1, 4, dtype=torch.long),
        input_features=torch.randn(1, 1, 8), feature_attention_mask=torch.ones(1, 8, dtype=torch.long),
        max_new_tokens=3, num_beams=num_beams, do_sample=False, eos_token_id=None, pad_token_id=0)
    assert generated.shape == (1, 7)


def test_generation_expansion_keeps_audio_groups_together(model_factory):
    model = model_factory().eval()
    ids = torch.tensor([[1, 30, 30, 2, 30, 3], [1, 30, 2, 3, 0, 0]])
    audio = torch.tensor([1., 2., 3.])[:, None, None].expand(3, 1, 8).clone()
    mask = torch.tensor([[1] * 8, [1] * 4 + [0] * 4, [1] * 4 + [0] * 4])
    expanded_ids, expanded = model._expand_inputs_for_generation(
        expand_size=2, input_ids=ids, attention_mask=ids.ne(0),
        input_features=audio, feature_attention_mask=mask)
    assert expanded_ids.shape == (4, 6)
    assert expanded['input_features'][:, 0, 0].tolist() == [1, 2, 1, 2, 3, 3]
    assert expanded['feature_attention_mask'].sum(-1).tolist() == [8, 4, 8, 4, 4, 4]


def test_peft_projector_roundtrip(tmp_path, model_factory):
    from peft import LoraConfig, PeftModel, get_peft_model
    base = model_factory()
    restored = copy.deepcopy(base)
    model = get_peft_model(base, LoraConfig(
        task_type='CAUSAL_LM', target_modules=['q_proj', 'v_proj'],
        modules_to_save=['multi_modal_projector'], r=2, lora_alpha=4))
    with torch.no_grad():
        for p in model.base_model.model.multi_modal_projector.parameters():
            if p.requires_grad:
                p.add_(0.2)
    args = dict(input_ids=torch.tensor([[1, 30, 30, 2]]), attention_mask=torch.ones(1, 4, dtype=torch.long),
                input_features=torch.randn(1, 1, 8), feature_attention_mask=torch.ones(1, 8, dtype=torch.long))
    model.eval()
    before = model(**args).logits
    model.save_pretrained(tmp_path)
    loaded = PeftModel.from_pretrained(restored, tmp_path).eval()
    torch.testing.assert_close(before, loaded(**args).logits)
