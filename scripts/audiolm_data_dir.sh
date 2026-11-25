# Resolve production/... audio paths against the AudioLM data directory.
# This server: /scratch/jackiel4/data/AudioLM
# Training server: /data/jackiel4/data/AudioLM
# Override with AUDIOLM_DATA_DIR.
if [[ -z "${AUDIOLM_DATA_DIR:-}" ]]; then
  if [[ -d /scratch/jackiel4/data/AudioLM ]]; then
    AUDIOLM_DATA_DIR=/scratch/jackiel4/data/AudioLM
  elif [[ -d /data/jackiel4/data/AudioLM ]]; then
    AUDIOLM_DATA_DIR=/data/jackiel4/data/AudioLM
  else
    AUDIOLM_DATA_DIR=/scratch/jackiel4/data/AudioLM
  fi
fi
export AUDIOLM_DATA_DIR
# Swift joins relative media paths to ROOT_IMAGE_DIR. production/... wavs live here.
export ROOT_IMAGE_DIR="${ROOT_IMAGE_DIR:-$AUDIOLM_DATA_DIR}"
