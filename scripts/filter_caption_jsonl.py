"""Keep single-audio MOS rows or two-audio A/B rows from a Swift JSONL dataset."""
import argparse
import json
from pathlib import Path

from lmushra.audio_probe import write_filtered_split


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--audios', type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    print(json.dumps(write_filtered_split(args.input, args.output, args.audios)))


if __name__ == '__main__':
    main()
