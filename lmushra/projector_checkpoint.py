"""Restore a stage-one projector after a codec plugin replaces the base projector."""

import json
import os
from pathlib import Path


def load_stage_one_projector(model, codec):
    checkpoint = os.environ.get('LMUSHRA_PROJECTOR_CHECKPOINT')
    if not checkpoint:
        return

    from safetensors import safe_open

    checkpoint = Path(checkpoint)
    config_key = f'lmushra_{codec}'
    config = json.loads((checkpoint / 'config.json').read_text(encoding='utf-8'))
    if config_key not in config or config[config_key] != getattr(model.config, config_key):
        raise ValueError(f'{checkpoint} does not match the current {codec} audio configuration')

    projector = model.multi_modal_projector
    index = checkpoint / 'model.safetensors.index.json'
    weight_map = json.loads(index.read_text(encoding='utf-8'))['weight_map'] if index.is_file() else None
    shards = {}
    for name in projector.state_dict():
        key = f'multi_modal_projector.{name}'
        if weight_map is not None and key not in weight_map:
            raise ValueError(f'{checkpoint} is missing {key}')
        shard = weight_map[key] if weight_map is not None else 'model.safetensors'
        shards.setdefault(shard, []).append((name, key))

    state = {}
    for shard, names in shards.items():
        with safe_open(checkpoint / shard, framework='pt', device='cpu') as tensors:
            for name, key in names:
                state[name] = tensors.get_tensor(key)
    projector.load_state_dict(state, strict=True)
