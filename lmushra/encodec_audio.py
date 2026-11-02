"""Pre-quantization EnCodec features using the shared codec-to-Qwen path."""

from .dac_audio import DacAudioTower, Qwen2AudioDac


class EncodecAudioTower(DacAudioTower):
    """EnCodec SEANet applies native causal/reflection padding itself."""

    codec_name = 'EnCodec'
    pad_to_hop = False


class Qwen2AudioEncodec(Qwen2AudioDac):
    codec_name = 'EnCodec'
    codec_template = 'qwen2_audio_encodec'
