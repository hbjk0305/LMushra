#!/usr/bin/env python3
"""Convert ODAQ predictions to CSV. Run: python eval/odaq/analze.py PREDICTIONS.jsonl"""

import argparse
import csv
import json
import re
from pathlib import Path

# ODAQ listening-test conditions in Q1 to Q5 order, strongest to weakest.
CONDITIONS = {
    "LP": ("LP50", "LP90", "LP105", "LP120", "LP150"),
    "PE": (
        "PE_4096_MS_NMR10", "PE_2048_MS_NMR10", "PE_1024_MS_NMR10",
        "PE_2048_MS_NMR16", "PE_1024_MS_NMR16",
    ),
    "SH": ("SH70_MS", "SH50_MS", "SH30_MS", "SH20_MS", "SH10_MS"),
    "TM": ("TM3k", "TM5k", "TM7k", "TM9k", "TM10.5k"),
    "UN": ("UN3k", "UN5k", "UN7k", "UN9k", "UN10.5k"),
    # "DE": ("OpenUnmix_mid", "TFC_TDF_U_Net_mid", "Cocktail_mid",
    #        "DeepFilterNet2_mid", "PSM_quantize_mask"),
}

# Caption cues from calibrated_llm/valid.jsonl. Matches can overlap across methods.
# PE and TM retain mechanism-based cues because the validation set lacks those labels.
HIGH_FREQUENCY = r"\b(?:high(?:er)?[- ]frequenc\w*|upper (?:spectral|frequency) range)\b"
CLARITY_AND_FULLNESS = r"\bclarity and fullness\b"

METHOD_PATTERNS = {
    "LP": (
        r"\blow[- ]pass\b|\bbandwidth limit\w*\b|\bhigh[- ]frequency roll[- ]off\b"
        r"|\b(?:reduc\w*|remov\w*|loss|attenuat\w*|less)\b[^.!?]{0,48}\b(?:high(?:er)?[- ]frequenc\w*|upper (?:spectral|frequency) range)\b|\bmuffled\b"
    ),
    "PE": r"\bpre[- ]?echo(?:es)?\b|\b(?:smear\w*|noise)\b[^.!?]{0,40}\bbefore (?:a |the )?transients?\b",
    "SH": (
        r"\bspectral (?:holes?|gaps?)\b|\b(?:spectral|frequency) bands?\b[^.!?]{0,40}\bzeroed\b"
        r"|\b(?:spectral regions?|frequency (?:bands?|ranges?|regions?))\b[^.!?]{0,48}\b(?:more (?:affected|attenuated)|(?:affected|attenuated) more) than others\b|\b(?:remov\w*|loss|attenuat\w*)\b[^.!?]{0,36}\b(?:some|certain|selected|specific)\b[^.!?]{0,24}\b(?:bands?|components?|frequencies)\b"
        rf"|{CLARITY_AND_FULLNESS}[^.!?]{{0,100}}{HIGH_FREQUENCY}"
        rf"|{HIGH_FREQUENCY}[^.!?]{{0,100}}{CLARITY_AND_FULLNESS}"
    ),
    "TM": r"\btonality mismatch\b|\bnoise[- ]like\b[^.!?]{0,45}\b(?:replac\w*|substitut\w*)\b[^.!?]{0,25}\btonal\b",
    "UN": (
        r"\bunmasked noise\b|\b(?:peak[- ]selected|tonal)\b[^.!?]{0,60}\b(?:replac\w*|substitut\w*)\b[^.!?]{0,35}\bnoise\b"
        r"|\btonal (?:clarity|contrast)\b"
        r"|\b(?:reduc\w*|loss|less|decreas\w*)\b[^.!?]{0,32}\btonal definition\b"
    ),
}
FIELDS = [
    "reference path", "degraded path", "processing method", "actual severity level",
    "response", *METHOD_PATTERNS, "predicted severity level",
]

SEVERITY_WORDS = {
    "very mild": 1, "very slight": 1, "very subtle": 1, "minimal": 1,
    "mild": 2, "slight": 2, "slightly": 2, "subtle": 2,
    "moderate": 3, "moderately": 3,
    "severe": 4, "severely": 4,
    "very severe": 5, "extremely severe": 5,
}
SEVERITY_PHRASE = re.compile(
    r"\b(?:(?:very|extremely|highly|fairly|somewhat|rather)\s+)?"
    r"(?:mild|slight(?:ly)?|subtle|minimal|moderate(?:ly)?|severe(?:ly)?|"
    r"noticeable|perceptible|pronounced|significant|substantial|extreme)\b"
    r"(?!\s+(?:portion|fraction|number|amount)\b)",
    re.I,
)
EXPLICIT_LEVEL = re.compile(
    r"\b(?:severity(?: level| score)?\s*(?:is\s+|of\s+|[:=]\s*)?|level\s+)"
    r"([1-5])(?![\d.]|\s*(?:kHz|Hz|dB|%))"
    r"(?:\s*(?:/\s*5|out of 5))?\b",
    re.I,
)


def predicted_severity(response):
    """Use one unambiguous level, or retain the response's original wording."""
    numbers = set(EXPLICIT_LEVEL.findall(response))
    if numbers:
        return " / ".join(sorted(numbers))
    phrases = list(dict.fromkeys(
        match.group() for match in SEVERITY_PHRASE.finditer(response)
        if not re.search(r"\b(?:not|no|hardly)\s+$", response[:match.start()], re.I)
    ))
    levels = {SEVERITY_WORDS.get(" ".join(phrase.lower().split())) for phrase in phrases}
    if len(levels) == 1 and None not in levels:
        return levels.pop()
    return " / ".join(phrases)


def actual_condition(reference, degraded):
    if reference == degraded or degraded.stem == "reference":
        return "reference", 999
    if degraded.stem == "LP35":
        return "LP", 0.5
    if degraded.stem == "LP70":
        return "LP", 1.5
    method = degraded.parent.name.split("_", 1)[0]
    conditions = CONDITIONS.get(method, ())
    return method, conditions.index(degraded.stem) + 1 if degraded.stem in conditions else ""


def convert(input_path, output_path):
    """Write one CSV row for each reference/degraded prediction."""
    if input_path.resolve() == output_path.resolve():
        raise ValueError("input and output paths must differ")
    with input_path.open(encoding="utf-8") as source, output_path.open(
        "w", encoding="utf-8", newline=""
    ) as output:
        writer = csv.writer(output)
        writer.writerow(FIELDS)
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                reference, degraded = record["audios"]
                response = record["response"]
                method, severity = actual_condition(Path(reference), Path(degraded))
                flags = [bool(re.search(pattern, response, re.I)) for pattern in METHOD_PATTERNS.values()]
                writer.writerow([
                    reference, degraded, method, severity, response, *flags,
                    predicted_severity(response),
                ])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"{input_path}:{line_number}: {exc}") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("-o", "--output", type=Path, help="Defaults to the input path with .csv")
    args = parser.parse_args()
    output = args.output or args.predictions.with_suffix(".csv")
    convert(args.predictions, output)
    print(output)


if __name__ == "__main__":
    main()
