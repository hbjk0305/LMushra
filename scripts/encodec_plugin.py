"""ms-swift EnCodec 24kHz mono plugin; see README.md."""

import os
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lmushra.dac_audio import DacProjector
from lmushra.encodec_audio import EncodecAudioTower, Qwen2AudioEncodec
from scripts.dac_plugin import DacQwenTemplate
from swift.model import ModelArch, ModelGroup, ModelLoader, ModelMeta, register_model
from swift.template import register_template
from swift.template.templates.qwen import QwenTemplateMeta


SAMPLE_RATE = 24000
HOP_LENGTH = 320
LATENT_DIM = 128
POOL_SIZE = 4
MAX_AUDIO_SECONDS = 30


class EncodecQwenLoader(ModelLoader):
    def get_model(self, model_dir, config, processor, model_kwargs):
        from encodec import EncodecModel

        self.auto_model_cls = Qwen2AudioEncodec
        model = super().get_model(model_dir, config, processor, model_kwargs)
        audio_device = next(model.audio_tower.parameters()).device
        text_parameter = model.get_input_embeddings().weight
        del model.audio_tower
        del model.multi_modal_projector
        checkpoint = os.environ.get('ENCODEC_MODEL_PATH')
        codec = EncodecModel.encodec_model_24khz(pretrained=not bool(checkpoint))
        if checkpoint:
            codec.load_state_dict(torch.load(checkpoint, map_location='cpu', weights_only=True), strict=True)
        codec = codec.cpu().float().eval()
        if (codec.sample_rate, codec.channels, codec.encoder.hop_length, codec.encoder.dimension) != (
                SAMPLE_RATE, 1, HOP_LENGTH, LATENT_DIM) or codec.normalize or codec.segment is not None:
            raise ValueError('Expected EnCodec 24kHz mono without normalization or segmentation')
        model.audio_tower = EncodecAudioTower(codec.encoder, SAMPLE_RATE, HOP_LENGTH, POOL_SIZE).to(audio_device)
        model.multi_modal_projector = DacProjector(LATENT_DIM, config.text_config.hidden_size).to(
            device=text_parameter.device, dtype=text_parameter.dtype)
        model.config.lmushra_encodec = dict(
            sample_rate=SAMPLE_RATE, hop_length=HOP_LENGTH, latent_dim=LATENT_DIM, pool_size=POOL_SIZE,
            checkpoint='encodec_24khz-d7cc33bc.th', representation='encoder_pre_quantization')
        return model


class EncodecQwenTemplate(DacQwenTemplate):
    codec_name = 'EnCodec'
    sample_rate = SAMPLE_RATE
    hop_length = HOP_LENGTH
    pool_size = POOL_SIZE
    max_audio_seconds = MAX_AUDIO_SECONDS


register_template(QwenTemplateMeta('qwen2_audio_encodec', template_cls=EncodecQwenTemplate), exist_ok=True)
register_model(ModelMeta(
    'qwen2_audio_encodec', [ModelGroup([])], loader=EncodecQwenLoader, template='qwen2_audio_encodec',
    model_arch=ModelArch.qwen2_audio, is_multimodal=True,
    requires=['transformers>=4.48,<4.49', 'encodec==0.1.1', 'librosa'], tags=['audio']), exist_ok=True)
