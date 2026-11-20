#!/usr/bin/env python3
"""Compute CLAP scores for ODAQ predictions.

Run: python eval/odaq/clap_score.py PREDICTIONS.jsonl [-o OUT.csv]

For each record (audios = [reference, degraded], response = model text) writes:
  clap_text_degraded   cosine(text(response), audio(degraded))   -- usual CLAPScore
  clap_text_reference  cosine(text(response), audio(reference))  -- baseline
  clap_audio_ref_deg   cosine(audio(reference), audio(degraded))
Audio longer than CLAP's 10 s window is split into consecutive 10 s windows whose
embeddings are averaged, so scores are deterministic (no random crop).
"""

import argparse
import csv
import json
from pathlib import Path

import librosa
import torch
from transformers import ClapModel, ClapProcessor

SR = 48_000
WINDOW = 10 * SR


@torch.no_grad()
def audio_embedding(path, model, processor, device):
    wav, _ = librosa.load(path, sr=SR, mono=True)
    chunks = [wav[i:i + WINDOW] for i in range(0, max(len(wav), 1), WINDOW)]
    # Drop a tiny trailing chunk (<1 s) unless it is the only one.
    if len(chunks) > 1 and len(chunks[-1]) < SR:
        chunks = chunks[:-1]
    inputs = processor(audios=chunks, sampling_rate=SR, return_tensors="pt",
                       truncation="rand_trunc", padding="repeatpad").to(device)
    emb = torch.nn.functional.normalize(model.get_audio_features(**inputs), dim=-1)
    return torch.nn.functional.normalize(emb.mean(0), dim=-1).cpu()


@torch.no_grad()
def text_embedding(text, model, processor, device):
    inputs = processor(text=[text], return_tensors="pt", padding=True,
                       truncation=True).to(device)
    return torch.nn.functional.normalize(model.get_text_features(**inputs), dim=-1)[0].cpu()


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("-o", "--output", type=Path,
                        help="Defaults to the input path with suffix _clap.csv")
    parser.add_argument("--model", default="laion/larger_clap_general")
    args = parser.parse_args()
    output = args.output or args.predictions.with_name(args.predictions.stem + "_clap.csv")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = ClapModel.from_pretrained(args.model).to(device).eval()
    processor = ClapProcessor.from_pretrained(args.model)

    records = [json.loads(l) for l in args.predictions.open(encoding="utf-8") if l.strip()]
    cache = {}

    def audio(path):
        if path not in cache:
            cache[path] = audio_embedding(path, model, processor, device)
        return cache[path]

    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["reference path", "degraded path", "response",
                         "clap_text_degraded", "clap_text_reference", "clap_audio_ref_deg"])
        for i, rec in enumerate(records, 1):
            ref, deg = rec["audios"]
            t = text_embedding(rec["response"], model, processor, device)
            a_ref, a_deg = audio(ref), audio(deg)
            writer.writerow([ref, deg, rec["response"],
                             f"{float(t @ a_deg):.4f}", f"{float(t @ a_ref):.4f}",
                             f"{float(a_ref @ a_deg):.4f}"])
            if i % 20 == 0:
                print(f"{i}/{len(records)}", flush=True)
    print(output)


if __name__ == "__main__":
    main()
