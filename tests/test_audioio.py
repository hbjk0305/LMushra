import struct

import numpy as np
import soundfile as sf

from deepmushra_data.audioio import write_wav


def test_wav_timestamp_normalization_preserves_exact_samples(tmp_path):
    audio = np.random.default_rng(99).normal(scale=0.1, size=(257, 2))
    path = tmp_path / "deterministic.wav"
    write_wav(path, audio, 44100)
    raw = path.read_bytes()
    peak = raw.find(b"PEAK")
    assert peak > 0
    assert struct.unpack("<I", raw[peak + 12:peak + 16])[0] == 0
    restored, sr = sf.read(path, dtype="float64", always_2d=True)
    assert sr == 44100
    np.testing.assert_array_equal(restored, audio)
    other = tmp_path / "other.wav"
    write_wav(other, audio, 44100)
    assert raw == other.read_bytes()
