"""One explicit, channel-preserving STFT convention for synthesis and analysis."""

from dataclasses import asdict, dataclass

import numpy as np
from scipy import signal


@dataclass(frozen=True)
class STFTConfig:
    n_fft: int = 2048
    hop_length: int = 512

    def __post_init__(self):
        if isinstance(self.n_fft, bool) or not isinstance(self.n_fft, int):
            raise ValueError("n_fft must be an integer")
        if isinstance(self.hop_length, bool) or not isinstance(self.hop_length, int):
            raise ValueError("hop_length must be an integer")
        if self.n_fft < 64 or self.n_fft % 2:
            raise ValueError("n_fft must be even and at least 64")
        if not 0 < self.hop_length <= self.n_fft:
            raise ValueError("hop_length must be in [1, n_fft]")
        if not signal.check_NOLA(self.window, self.n_fft, self.n_fft - self.hop_length):
            raise ValueError("STFT window/hop fails the nonzero overlap-add condition")

    @property
    def window(self):
        return signal.windows.hann(self.n_fft, sym=False)

    def metadata(self):
        return {**asdict(self), "window": "periodic_hann", "boundary": "zeros",
                "padded": True, "scaling": "spectrum", "axis_order": "time,frequency,channel"}


def validate_audio(audio):
    audio = np.asarray(audio, dtype=np.float64)
    if audio.ndim != 2 or not audio.shape[0] or audio.shape[1] not in (1, 2):
        raise ValueError("Audio must have shape [nonzero samples, 1 or 2 channels]")
    if not np.isfinite(audio).all():
        raise ValueError("Audio contains NaN or infinity")
    return audio


def analyze(audio, sample_rate, config):
    audio = validate_audio(audio)
    # Pad explicitly: scipy otherwise silently reduces nperseg for short inputs.
    padded = np.pad(audio, ((0, max(0, config.n_fft - len(audio))), (0, 0)))
    spectra = []
    for channel in padded.T:
        frequencies, times, z = signal.stft(
            channel, fs=sample_rate, window=config.window, nperseg=config.n_fft,
            noverlap=config.n_fft - config.hop_length, nfft=config.n_fft,
            boundary="zeros", padded=True, scaling="spectrum",
        )
        spectra.append(z.T)
    return frequencies, times, np.stack(spectra, axis=-1)


def synthesize(spectrum, sample_rate, sample_count, config):
    channels = []
    for channel in range(spectrum.shape[-1]):
        _, audio = signal.istft(
            spectrum[:, :, channel].T, fs=sample_rate, window=config.window,
            nperseg=config.n_fft, noverlap=config.n_fft - config.hop_length,
            nfft=config.n_fft, input_onesided=True, boundary=True, scaling="spectrum",
        )
        if len(audio) < sample_count:
            raise ValueError("ISTFT unexpectedly returned too few samples")
        channels.append(audio[:sample_count])
    return validate_audio(np.stack(channels, axis=-1))
