"""Dispatch filesystem-trace analysis to the selected platform."""

import argparse
from pathlib import Path

from .layout import backend, load_layout


def analyze(directory: Path) -> None:
    """Check a capture using its implemented native platform analyzer."""
    backend(load_layout()).analyze_trace(directory)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    analyze(parser.parse_args().directory)
