"""Frozen, pre-quantization DAC features for Qwen2-Audio (Transformers 4.48)."""

import torch
from torch import nn
from torch.nn import functional as F
from transformers import Qwen2AudioForConditionalGeneration


class DacAudioTower(nn.Module):
    """Keep only DAC's encoder; crop each waveform before encoding/pooling.

    Neither the vector quantizer nor decoder is retained. Pooling reduces the
    number of language-model tokens, and never averages batch padding.
    """

    codec_name = 'DAC'
    pad_to_hop = True

    def __init__(self, encoder, sample_rate, hop_length, pool_size=4):
        super().__init__()
        if min(sample_rate, hop_length, pool_size) < 1:
            raise ValueError(f'{self.codec_name} sample rate, hop length and pool size must be positive')
        self.encoder = encoder.float().requires_grad_(False).eval()
        self.sample_rate = int(sample_rate)
        self.hop_length = int(hop_length)
        self.pool_size = int(pool_size)

    @property
    def device(self):
        return next(self.encoder.parameters()).device

    def train(self, mode=True):
        super().train(False)
        return self

    @torch.no_grad()
    def forward(self, input_features, feature_attention_mask):
        if input_features.ndim != 3 or input_features.shape[1] != 1:
            raise ValueError(f'{self.codec_name} audio must have shape [num_audios, 1, samples]')
        if feature_attention_mask.shape != (input_features.shape[0], input_features.shape[2]):
            raise ValueError(f'{self.codec_name} audio mask must have shape [num_audios, samples]')
        lengths = feature_attention_mask.long().sum(-1)
        expected_mask = torch.arange(input_features.shape[-1], device=lengths.device)[None] < lengths[:, None]
        if (lengths <= 0).any() or not torch.equal(feature_attention_mask.bool(), expected_mask):
            raise ValueError(f'{self.codec_name} audio masks must describe nonempty, right-padded waveforms')
        self.encoder.eval()
        features = []
        for waveform, length in zip(input_features, lengths.tolist()):
            waveform = waveform[None, :, :length].to(self.device, torch.float32)
            if self.pad_to_hop:
                waveform = F.pad(waveform, (0, (-length) % self.hop_length))
            # Disable training autocast: the pretrained codec stays fp32.
            with torch.autocast(device_type=self.device.type, enabled=False):
                latent = self.encoder(waveform)
                latent = F.avg_pool1d(latent, self.pool_size, self.pool_size, ceil_mode=True)
            features.append(latent.squeeze(0).transpose(0, 1))
        output_lengths = torch.tensor([x.shape[0] for x in features], device=self.device)
        return nn.utils.rnn.pad_sequence(features, batch_first=True), output_lengths


class DacProjector(nn.Sequential):
    def __init__(self, latent_dim, hidden_size):
        super().__init__(nn.LayerNorm(latent_dim), nn.Linear(latent_dim, hidden_size),
                         nn.GELU(), nn.Linear(hidden_size, hidden_size))


class Qwen2AudioDac(Qwen2AudioForConditionalGeneration):
    """Use expanded audio placeholders, preserving Qwen's loss and generation.

    The loader installs DAC after loading the original Qwen checkpoint, so HF's
    missing-weight initialization cannot overwrite the pretrained DAC weights.
    """

    codec_name = 'DAC'
    codec_template = 'qwen2_audio_dac'

    def _expand_inputs_for_generation(self, expand_size=1, is_encoder_decoder=False,
                                      input_ids=None, **model_kwargs):
        # HF expands text rows independently. Audio rows, however, are flattened
        # clips, so expand complete per-example groups rather than individual clips.
        audio = model_kwargs.pop('input_features', None)
        mask = model_kwargs.pop('feature_attention_mask', None)
        expanded_ids, expanded = super()._expand_inputs_for_generation(
            expand_size=expand_size, is_encoder_decoder=is_encoder_decoder,
            input_ids=input_ids, **model_kwargs)
        if audio is None:
            return expanded_ids, expanded
        if mask is None or input_ids is None:
            raise ValueError(f'{self.codec_name} audio generation requires input_ids and feature_attention_mask')
        if expand_size == 1:
            expanded.update(input_features=audio, feature_attention_mask=mask)
            return expanded_ids, expanded
        samples_per_token = self.audio_tower.hop_length * self.audio_tower.pool_size
        clip_tokens = ((mask.long().sum(-1) + samples_per_token - 1) // samples_per_token).tolist()
        audio_groups, mask_groups = [], []
        offset = 0
        for count in input_ids.eq(self.config.audio_token_index).sum(-1).tolist():
            start, consumed = offset, 0
            while consumed < count and offset < len(clip_tokens):
                consumed += clip_tokens[offset]
                offset += 1
            if consumed != count:
                raise ValueError(f'{self.codec_name} audio tokens do not match per-example clips during generation')
            audio_groups.extend([audio[start:offset]] * expand_size)
            mask_groups.extend([mask[start:offset]] * expand_size)
        if offset != len(clip_tokens):
            raise ValueError(f'Unused {self.codec_name} audio clips during generation')
        expanded.update(input_features=torch.cat(audio_groups), feature_attention_mask=torch.cat(mask_groups))
        return expanded_ids, expanded

    def forward(self, input_ids=None, input_features=None, attention_mask=None,
                feature_attention_mask=None, position_ids=None, past_key_values=None,
                inputs_embeds=None, labels=None, use_cache=None,
                output_attentions=None, output_hidden_states=None, return_dict=None):
        cache_length = 0
        if past_key_values is not None:
            cache_length = (past_key_values.get_seq_length() if hasattr(past_key_values, 'get_seq_length')
                            else past_key_values[0][0].shape[-2])
        if inputs_embeds is None and input_features is not None and cache_length == 0:
            if input_ids is None or feature_attention_mask is None:
                raise ValueError(f'{self.codec_name} audio requires input_ids and feature_attention_mask')
            inputs_embeds = self.get_input_embeddings()(input_ids)
            features, lengths = self.audio_tower(input_features, feature_attention_mask)
            projector_parameter = next(self.multi_modal_projector.parameters())
            features = self.multi_modal_projector(features.to(projector_parameter.device, projector_parameter.dtype))
            valid = torch.arange(features.shape[1], device=lengths.device)[None] < lengths[:, None]
            features = features[valid.to(features.device)]
            audio_mask = input_ids.eq(self.config.audio_token_index)
            if audio_mask.sum().item() != features.shape[0]:
                raise ValueError(f'{self.codec_name} audio tokens/features mismatch: {audio_mask.sum().item()} vs '
                                 f'{features.shape[0]}; use the {self.codec_template} template')
            inputs_embeds = inputs_embeds.masked_scatter(
                audio_mask.to(inputs_embeds.device).unsqueeze(-1).expand_as(inputs_embeds),
                features.to(inputs_embeds.device, inputs_embeds.dtype))
        # Passing embeds bypasses Qwen's original mel/Whisper path. Cached decoding
        # omits audio; the inherited generation hooks carry the attention mask.
        return super().forward(
            input_ids=input_ids, inputs_embeds=inputs_embeds, attention_mask=attention_mask,
            position_ids=position_ids, past_key_values=past_key_values, labels=labels,
            use_cache=use_cache, output_attentions=output_attentions,
            output_hidden_states=output_hidden_states, return_dict=return_dict)
