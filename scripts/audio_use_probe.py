"""Swift callback: normal / silence / shuffle CE, and projector checkpoints.

Register with `--external_plugins ./scripts/audio_use_probe.py --callbacks audio_use_probe`.
The codec loader replaces `multi_modal_projector` after `from_pretrained`, so a full
checkpoint cannot be reloaded as `--model`. This callback writes `multi_modal_projector.pt`.
"""
import json
import os

import torch

from lmushra.audio_probe import derange_audios, should_probe, silence_waveforms
from lmushra.dac_audio import save_projector_state
from swift.callbacks import TrainerCallback
from swift.callbacks.mapping import callbacks_map
from swift.utils import get_logger

logger = get_logger()


def _distributed() -> bool:
    return torch.distributed.is_available() and torch.distributed.is_initialized()


def _rank() -> int:
    return torch.distributed.get_rank() if _distributed() else 0


def _barrier() -> None:
    if _distributed():
        torch.distributed.barrier()


def _unwrap(trainer):
    accelerator = getattr(trainer, 'accelerator', None)
    if accelerator is not None:
        return accelerator.unwrap_model(trainer.model)
    return getattr(trainer.model, 'module', trainer.model)


class AudioUseProbeCallback(TrainerCallback):
    def __init__(self, args, trainer):
        super().__init__(args, trainer)
        self.interval = int(os.environ.get('AUDIO_PROBE_INTERVAL', '500'))
        self.n_examples = int(os.environ.get('AUDIO_PROBE_EXAMPLES', '100'))
        self.seed = int(os.environ.get('AUDIO_PROBE_SEED', '0'))
        self._normal = None
        self._silence = None
        self._shuffled = None

    def on_train_begin(self, args, state, control, **kwargs):
        if _rank() != 0:
            return
        names = [name for name, param in _unwrap(self.trainer).named_parameters() if param.requires_grad]
        logger.info('Trainable parameters (%d): %s', len(names), names)

    def on_save(self, args, state, control, **kwargs):
        self._save_projector(os.path.join(args.output_dir, f'checkpoint-{state.global_step}'))

    def on_train_end(self, args, state, control, **kwargs):
        self._save_projector(args.output_dir)

    def on_step_end(self, args, state, control, **kwargs):
        if not should_probe(state.global_step, self.interval):
            return
        dataset = getattr(self.trainer, 'eval_dataset', None)
        if dataset is None or len(dataset) == 0:
            if _rank() == 0:
                logger.warning('Skipping audio-use probe: no eval dataset')
            return
        self._ensure_rows()
        # Every rank must run the same forwards, then meet again before the next
        # training collective. Returning early on rank 0 deadlocks DDP.
        _barrier()
        model = self.trainer.model
        was_training = model.training
        model.eval()
        try:
            losses = {name: self._mean_loss(rows) for name, rows in (
                ('normal', self._normal), ('silence', self._silence), ('shuffle', self._shuffled))}
        finally:
            model.train(was_training)
        _barrier()
        if _rank() == 0:
            used = losses['normal'] < losses['silence'] and losses['normal'] < losses['shuffle']
            record = {'step': state.global_step, **losses, 'audio_used': used}
            logger.info(
                'audio_probe step=%s normal=%.4f silence=%.4f shuffle=%.4f audio_used=%s',
                state.global_step, losses['normal'], losses['silence'], losses['shuffle'], used)
            path = os.path.join(args.output_dir, 'audio_use_probes.jsonl')
            with open(path, 'a') as stream:
                stream.write(json.dumps(record) + '\n')
        # Rank 0 logging must finish before either rank enters the next collective.
        _barrier()

    def _save_projector(self, directory):
        if _rank() != 0:
            return
        path = save_projector_state(_unwrap(self.trainer).multi_modal_projector, directory)
        logger.info('Saved projector to %s', path)

    def _ensure_rows(self):
        if self._normal is not None:
            return
        source = getattr(self.trainer.eval_dataset, 'dataset', self.trainer.eval_dataset)
        n = min(self.n_examples, len(source))
        raw = [source[i] for i in range(n)]
        template = self.trainer.template
        self._normal = [_encode(template, row) for row in raw]
        self._silence = silence_waveforms(self._normal)
        self._shuffled = [_encode(template, row) for row in derange_audios(raw, self.seed)]

    def _mean_loss(self, rows):
        total = 0.0
        for row in rows:
            batch = self.trainer.template.data_collator([row])
            batch = self.trainer._prepare_inputs(batch)
            with torch.no_grad():
                loss = self.trainer.compute_loss(self.trainer.model, batch)
            total += float(loss.detach().float().cpu())
        return total / len(rows)


def _encode(template, row):
    encoded = template.encode(row, return_length=True)
    return encoded[0] if isinstance(encoded, list) else encoded


callbacks_map['audio_use_probe'] = AudioUseProbeCallback
