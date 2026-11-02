"""ms-swift external plugin: --model_type qwen2_audio_dac.

Run with the repository's ms-swift on PYTHONPATH; see README.md.
"""

import os
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lmushra.dac_audio import DacAudioTower, DacProjector, Qwen2AudioDac
from swift.model import ModelArch, ModelGroup, ModelLoader, ModelMeta, register_model
from swift.template import Template, register_template
from swift.template.templates.qwen import Qwen2AudioTemplate, QwenTemplateMeta
from swift.template.vision_utils import load_audio


# Pin the codec and temporal compression so adapter reload uses the same features.
SAMPLE_RATE = 44100
HOP_LENGTH = 512
LATENT_DIM = 1024
POOL_SIZE = 4
MAX_AUDIO_SECONDS = 30


class DacQwenLoader(ModelLoader):
    def get_model(self, model_dir, config, processor, model_kwargs):
        import dac

        self.auto_model_cls = Qwen2AudioDac
        model = super().get_model(model_dir, config, processor, model_kwargs)
        audio_device = next(model.audio_tower.parameters()).device
        text_parameter = model.get_input_embeddings().weight
        del model.audio_tower
        del model.multi_modal_projector
        checkpoint = os.environ.get('DAC_MODEL_PATH')
        if not checkpoint:
            checkpoint = dac.utils.download(model_type='44khz', model_bitrate='8kbps', tag='0.0.1')
        codec = dac.DAC.load(checkpoint).cpu().float().eval()
        if (codec.sample_rate, int(codec.hop_length), codec.latent_dim) != (SAMPLE_RATE, HOP_LENGTH, LATENT_DIM):
            raise ValueError('DAC_MODEL_PATH must contain the DAC 44kHz/8kbps encoder (44100 Hz, hop 512, dim 1024)')
        model.audio_tower = DacAudioTower(codec.encoder, SAMPLE_RATE, HOP_LENGTH, POOL_SIZE).to(audio_device)
        model.multi_modal_projector = DacProjector(LATENT_DIM, config.text_config.hidden_size).to(
            device=text_parameter.device, dtype=text_parameter.dtype)
        model.config.lmushra_dac = dict(
            sample_rate=SAMPLE_RATE, hop_length=HOP_LENGTH, latent_dim=LATENT_DIM,
            pool_size=POOL_SIZE, model_type='44khz', model_bitrate='8kbps', tag='0.0.1',
            representation='encoder_pre_quantization')
        return model


class DacQwenTemplate(Qwen2AudioTemplate):
    codec_name = 'DAC'
    sample_rate = SAMPLE_RATE
    hop_length = HOP_LENGTH
    pool_size = POOL_SIZE
    max_audio_seconds = MAX_AUDIO_SECONDS

    def init_env_args(self):
        Template.init_env_args(self)
        self.sampling_rate = self.sample_rate

    def _encode(self, inputs):
        # Skip Qwen2AudioTemplate's mel feature extraction.
        encoded = Template._encode(self, inputs)
        if not inputs.audios:
            return encoded
        if inputs.chat_template_kwargs.get('sampling_rate', self.sample_rate) != self.sample_rate:
            raise ValueError(f'{self.codec_name} audio must be loaded at {self.sample_rate} Hz')
        audios = []
        for source in inputs.audios:
            waveform = np.asarray(load_audio(source, sampling_rate=self.sample_rate), dtype=np.float32)
            if waveform.ndim != 1 or waveform.size == 0 or not np.isfinite(waveform).all():
                raise ValueError(f'{self.codec_name} audio must be a nonempty finite mono waveform')
            if waveform.size > self.sample_rate * self.max_audio_seconds:
                raise ValueError(f'{self.codec_name} audio exceeds {self.max_audio_seconds} seconds; '
                                 'split the audio before training')
            audios.append(torch.from_numpy(waveform.copy()))
        token = self.config.audio_token_index
        indices = [i for i, value in enumerate(encoded['input_ids']) if value == token]
        if len(indices) != len(audios):
            raise ValueError(f'Each {self.codec_name} audio needs exactly one <audio> placeholder')
        samples_per_token = self.hop_length * self.pool_size
        counts = [(len(audio) + samples_per_token - 1) // samples_per_token for audio in audios]
        encoded['input_ids'], encoded['labels'], encoded['loss_scale'] = self._extend_tokens(
            encoded['input_ids'], encoded.get('labels'), encoded.get('loss_scale'),
            indices, lambda i: [token] * counts[i])
        encoded['input_features'] = audios
        return encoded

    def _data_collator(self, batch, *, padding_to=None):
        # Padding spans the entire batch, including examples with different numbers
        # of audio clips. Retain example order, then clip order, for token insertion.
        text_batch = [{k: v for k, v in item.items() if k != 'input_features'} for item in batch]
        result = Template._data_collator(self, text_batch, padding_to=padding_to)
        audios = [torch.as_tensor(audio, dtype=torch.float32)
                  for item in batch for audio in item.get('input_features', [])]
        if audios:
            lengths = torch.tensor([audio.numel() for audio in audios])
            result['input_features'] = torch.nn.utils.rnn.pad_sequence(audios, batch_first=True).unsqueeze(1)
            result['feature_attention_mask'] = (
                torch.arange(result['input_features'].shape[-1])[None] < lengths[:, None]).long()
        return result


register_template(QwenTemplateMeta('qwen2_audio_dac', template_cls=DacQwenTemplate), exist_ok=True)
register_model(ModelMeta(
    'qwen2_audio_dac', [ModelGroup([])], loader=DacQwenLoader, template='qwen2_audio_dac',
    model_arch=ModelArch.qwen2_audio, is_multimodal=True,
    requires=['transformers>=4.48,<4.49', 'descript-audio-codec==1.0.0', 'librosa'],
    tags=['audio']), exist_ok=True)
