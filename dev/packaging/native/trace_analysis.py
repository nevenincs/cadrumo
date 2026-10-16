"""Dispatch filesystem-trace analysis to the selected platform."""

import argparse
from pathlib import Path

from .build_directory import require_enrolled_build
from .layout import backend, load_layout


def analyze(directory: Path, build_root: Path) -> None:
    """Check a capture using its implemented native platform analyzer."""
    backend(load_layout()).analyze_trace(directory, build_root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build", type=require_enrolled_build, required=True, help="The owning CMake binary directory."
    )
    parser.add_argument("directory", type=Path)
    arguments = parser.parse_args()
    analyze(arguments.directory, arguments.build)
