"""SoundFile WAV output with deterministic optional PEAK-chunk timestamps."""

from pathlib import Path
import struct

import soundfile as sf


def write_wav(path, audio, sample_rate):
    """Write float64 WAV and zero libsndfile's wall-clock PEAK timestamp.

    Only the timestamp is changed; peaks and every waveform byte are preserved.
    This avoids private libsndfile APIs and makes repeated runs byte-identical.
    """
    sf.write(path, audio, sample_rate, format="WAV", subtype="DOUBLE")
    with Path(path).open("r+b") as stream:
        header = stream.read(12)
        if header[:4] != b"RIFF" or header[8:] != b"WAVE":
            raise ValueError("Expected little-endian RIFF/WAVE output")
        while True:
            chunk = stream.read(8)
            if not chunk:
                break
            if len(chunk) != 8:
                raise ValueError("Truncated WAV chunk header")
            kind, size = struct.unpack("<4sI", chunk)
            start = stream.tell()
            if kind == b"PEAK":
                if size < 8:
                    raise ValueError("Invalid PEAK chunk")
                stream.seek(start + 4)  # version, then POSIX timestamp
                stream.write(struct.pack("<I", 0))
            stream.seek(start + size + size % 2)
