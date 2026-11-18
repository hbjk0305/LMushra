"""Artifact-supervised baseline, DAC and EnCodec; original plugins stay unchanged."""
import os
import math
from scripts.dac_artifact_plugin import ArtifactTemplateMixin, ArtifactTemplate, ArtifactLoss, load_schema
from scripts.dac_plugin import DacQwenLoader
from scripts.encodec_plugin import EncodecQwenLoader, EncodecQwenTemplate
from lmushra.artifact_supervision import ArtifactProjector
from lmushra.dac_artifact import Qwen2AudioDacArtifact, Qwen2AudioEncodecArtifact, Qwen2AudioBaselineArtifact
from swift.model.models.qwen import Qwen2AudioLoader
from swift.model import ModelArch, ModelGroup, ModelMeta, register_model
from swift.template import register_template
from swift.template.templates.qwen import Qwen2AudioTemplate, QwenTemplateMeta
from swift.loss.mapping import loss_map


class ArtifactLoaderMixin:
    artifact_model_cls = None

    def get_model(self, model_dir, config, processor, model_kwargs):
        model = super().get_model(model_dir, config, processor, model_kwargs)
        model.__class__ = self.artifact_model_cls
        model.audio_tower.requires_grad_(False).eval()
        schema = load_schema(config)
        parameter = next(model.multi_modal_projector.parameters())
        model.multi_modal_projector = ArtifactProjector(
            model.multi_modal_projector, config.text_config.hidden_size, schema).to(
                device=parameter.device, dtype=parameter.dtype)
        config.lmushra_artifact_schema = schema
        previous = getattr(config, 'lmushra_artifact_weights', {})
        config.lmushra_artifact_weights = {
            'classification': float(os.environ.get('ARTIFACT_CLS_WEIGHT', previous.get('classification', 1.))),
            'regression': float(os.environ.get('ARTIFACT_REG_WEIGHT', previous.get('regression', 1.)))}
        if any(not math.isfinite(v) or v < 0 for v in config.lmushra_artifact_weights.values()):
            raise ValueError('Artifact loss weights must be finite and nonnegative')
        config.keys_to_ignore_at_inference = list(set(getattr(config, 'keys_to_ignore_at_inference', []) +
            ['artifact_cls_loss', 'artifact_reg_loss', 'artifact_aux_loss']))
        # Transformers.from_pretrained deep-copies its config argument. Forward
        # reads model.config; retain the supplied config for Swift's processor too.
        for name in ('lmushra_artifact_schema', 'lmushra_artifact_weights', 'keys_to_ignore_at_inference'):
            setattr(model.config, name, getattr(config, name))
        return model


class DacArtifactLoader(ArtifactLoaderMixin, DacQwenLoader):
    artifact_model_cls = Qwen2AudioDacArtifact


class EncodecArtifactLoader(ArtifactLoaderMixin, EncodecQwenLoader):
    artifact_model_cls = Qwen2AudioEncodecArtifact


class BaselineArtifactLoader(ArtifactLoaderMixin, Qwen2AudioLoader):
    artifact_model_cls = Qwen2AudioBaselineArtifact


class EncodecArtifactTemplate(ArtifactTemplateMixin, EncodecQwenTemplate):
    pass


class BaselineExpandedTemplate(Qwen2AudioTemplate):
    def _encode(self, inputs):
        encoded = super()._encode(inputs)
        if not inputs.audios:
            return encoded
        token = self.config.audio_token_index
        indices = [i for i, value in enumerate(encoded['input_ids']) if value == token]
        mel_lengths = encoded['feature_attention_mask'].long().sum(-1)
        counts = (((mel_lengths - 1) // 2 + 1 - 2) // 2 + 1).tolist()
        if len(indices) != len(counts) or any(count < 2 for count in counts):
            raise ValueError('Baseline audio needs one placeholder per clip and at least two output tokens')
        encoded['input_ids'], encoded['labels'], encoded['loss_scale'] = self._extend_tokens(
            encoded['input_ids'], encoded.get('labels'), encoded.get('loss_scale'),
            indices, lambda i: [token] * counts[i])
        return encoded


class BaselineArtifactTemplate(ArtifactTemplateMixin, BaselineExpandedTemplate):
    pass


loss_map['audio_artifact'] = ArtifactLoss
for name, loader, template, dependencies in [
    ('baseline', BaselineArtifactLoader, BaselineArtifactTemplate, []),
    ('dac', DacArtifactLoader, ArtifactTemplate, ['descript-audio-codec==1.0.0']),
    ('encodec', EncodecArtifactLoader, EncodecArtifactTemplate, ['encodec==0.1.1']),
]:
    model_type = f'qwen2_audio_{name}_artifact'
    register_template(QwenTemplateMeta(model_type, template_cls=template), exist_ok=True)
    register_model(ModelMeta(
        model_type, [ModelGroup([])], loader=loader, template=model_type,
        model_arch=ModelArch.qwen2_audio, is_multimodal=True,
        requires=['transformers>=4.48,<4.49', 'librosa'] + dependencies,
        tags=['audio']), exist_ok=True)
