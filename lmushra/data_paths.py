"""AudioLM data root and production-relative wav paths.

JSONL stores wavs as ``production/...``. That path is joined to the data
directory, which is ``AUDIOLM_DATA_DIR`` when set, otherwise the first of
``/scratch/jackiel4/data/AudioLM`` and ``/data/jackiel4/data/AudioLM`` that
exists.
"""
import os
from pathlib import Path


DEFAULT_DATA_DIRS = (
    Path("/scratch/jackiel4/data/AudioLM"),
    Path("/data/jackiel4/data/AudioLM"),
)
# Published exports on this server store absolute paths under this prefix.
SOURCE_DATA_PREFIX = "/scratch/tingyup2/projects/AudioLM/"


def data_dir() -> Path:
    override = os.environ.get("AUDIOLM_DATA_DIR")
    if override:
        return Path(override)
    for candidate in DEFAULT_DATA_DIRS:
        if candidate.is_dir():
            return candidate
    return DEFAULT_DATA_DIRS[0]


def resolve_audio(path: str) -> str:
    """Join a production-relative path to the data directory. Other paths stay put."""
    if path.startswith("production/") or path == "production":
        return str(data_dir() / path)
    return path


def to_production_relative(path: str) -> str:
    """Turn an absolute AudioLM wav path into ``production/...``."""
    if path.startswith("production/"):
        return path
    if path.startswith(SOURCE_DATA_PREFIX):
        relative = path[len(SOURCE_DATA_PREFIX):]
    else:
        marker = "/production/"
        index = path.find(marker)
        if index == -1:
            raise ValueError(f"path is not under production/: {path}")
        relative = "production/" + path[index + len(marker):]
    if not relative.startswith("production/"):
        raise ValueError(f"path is not under production/: {path}")
    return relative


def relativize_export_value(value):
    """Rewrite absolute production wav paths. Annotation paths outside production/ stay put."""
    if isinstance(value, str):
        if value.startswith("production/"):
            return value
        if "/production/" in value:
            return to_production_relative(value)
        if value.startswith("/") and value.endswith(".wav"):
            raise ValueError(f"wav is not under production/: {value}")
        return value
    if isinstance(value, list):
        return [relativize_export_value(item) for item in value]
    if isinstance(value, dict):
        return {key: relativize_export_value(item) for key, item in value.items()}
    return value


def collect_production_wavs(value, found):
    if isinstance(value, str) and value.startswith("production/") and value.endswith(".wav"):
        found.add(value)
    elif isinstance(value, list):
        for item in value:
            collect_production_wavs(item, found)
    elif isinstance(value, dict):
        for item in value.values():
            collect_production_wavs(item, found)
