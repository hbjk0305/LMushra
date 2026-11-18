"""Opt-in DAC artifact model, JSON-target template and combined SFT loss."""
import json
import math
import os
import torch
from scripts.dac_plugin import DacQwenLoader, DacQwenTemplate
from lmushra.artifact_supervision import ArtifactProjector, encode_targets
from lmushra.dac_artifact import Qwen2AudioDacArtifact
from swift.model import ModelArch, ModelGroup, ModelMeta, register_model
from swift.template import register_template
from swift.template.templates.qwen import QwenTemplateMeta
from swift.loss.causal_lm import CustomCrossEntropyLoss
from swift.loss.mapping import loss_map


def load_schema(config):
    path = os.environ.get('ARTIFACT_SCHEMA')
    if path:
        with open(path) as source:
            schema = json.load(source)
    else:
        schema = getattr(config, 'lmushra_artifact_schema', None)
    if schema is None:
        raise ValueError('Set ARTIFACT_SCHEMA to the converted training schema.json')
    return schema


class ArtifactLoader(DacQwenLoader):
    def get_model(self, model_dir, config, processor, model_kwargs):
        model = super().get_model(model_dir, config, processor, model_kwargs)
        model.__class__ = Qwen2AudioDacArtifact
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
        if any(not math.isfinite(value) or value < 0 for value in config.lmushra_artifact_weights.values()):
            raise ValueError('Artifact loss weights must be finite and nonnegative')
        config.keys_to_ignore_at_inference = list(set(getattr(config, 'keys_to_ignore_at_inference', []) +
            ['artifact_cls_loss', 'artifact_reg_loss', 'artifact_aux_loss']))
        # Transformers.from_pretrained deep-copies its config argument. Forward
        # reads model.config; retain the supplied config for Swift's processor too.
        for name in ('lmushra_artifact_schema', 'lmushra_artifact_weights', 'keys_to_ignore_at_inference'):
            setattr(model.config, name, getattr(config, name))
        return model


class ArtifactTemplateMixin:
    def _encode(self, inputs):
        target = None
        if inputs.messages and inputs.messages[-1]['role'] == 'assistant' and inputs.messages[-1].get('content'):
            target = json.loads(inputs.messages[-1]['content'])['degradation']
            if len(inputs.audios) != 2:
                raise ValueError('Artifact supervision requires exactly two audios: reference, degraded')
        encoded = super()._encode(inputs)
        if target is not None:
            schema = getattr(self, '_artifact_schema', None)
            if schema is None:
                schema = self._artifact_schema = load_schema(self.config)
            for key, value in encode_targets(target, schema).items():
                encoded[f'artifact_{key}'] = value
        return encoded

    def _data_collator(self, batch, *, padding_to=None):
        keys = ('artifact_categorical', 'artifact_numeric', 'artifact_numeric_mask')
        presence = [keys[0] in item for item in batch]
        if any(presence) and not all(presence):
            raise ValueError('Cannot mix labeled and unlabeled artifact examples')
        clean = [{k: v for k, v in item.items() if k not in keys} for item in batch]
        result = super()._data_collator(clean, padding_to=padding_to)
        if all(presence):
            for key, dtype in zip(keys, (torch.long, torch.float32, torch.bool)):
                result[key] = torch.tensor([item[key] for item in batch], dtype=dtype)
        return result


class ArtifactTemplate(ArtifactTemplateMixin, DacQwenTemplate):
    pass


class ArtifactLoss(CustomCrossEntropyLoss):
    def __init__(self, args, trainer):
        super().__init__(args, trainer)
        if trainer.template.sequence_parallel_size != 1:
            raise ValueError('Artifact loss currently requires sequence_parallel_size=1')

    def __call__(self, outputs, labels, **kwargs):
        if 'artifact_aux_loss' not in outputs:
            raise ValueError('Artifact loss requires auxiliary labels and the artifact model')
        text = super().__call__(outputs, labels, **kwargs)
        if self.trainer is not None:
            mode = 'train' if self.trainer.model.training else 'eval'
            for name in ('artifact_cls_loss', 'artifact_reg_loss'):
                self.trainer.custom_metrics[mode][name].update(outputs[name].detach())
        auxiliary = outputs['artifact_aux_loss']
        num_items = kwargs.get('num_items_in_batch')
        if num_items is not None:
            # Swift/HF normalizes text by all accumulated supervised tokens.
            # Apply the same microbatch share so accumulation does not amplify aux.
            auxiliary = auxiliary * ((labels[:, 1:] != -100).sum().to(auxiliary.device) / num_items)
        return text + auxiliary


loss_map['dac_artifact'] = ArtifactLoss
register_template(QwenTemplateMeta('qwen2_audio_dac_artifact', template_cls=ArtifactTemplate), exist_ok=True)
register_model(ModelMeta(
    'qwen2_audio_dac_artifact', [ModelGroup([])], loader=ArtifactLoader,
    template='qwen2_audio_dac_artifact', model_arch=ModelArch.qwen2_audio, is_multimodal=True,
    requires=['transformers>=4.48,<4.49', 'descript-audio-codec==1.0.0', 'librosa'],
    tags=['audio']), exist_ok=True)
