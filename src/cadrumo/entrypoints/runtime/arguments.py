"""Validate runtime invocation syntax before importing application dependencies."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_runtime_arguments(arguments: list[str] | None = None) -> argparse.Namespace:
    """Parse the explicit runtime owner binding without accessing runtime state."""
    parser = argparse.ArgumentParser(prog="cadrumo-runtime", allow_abbrev=False)
    parser.add_argument("--storage-root", required=True, type=Path)
    parser.add_argument("--storage-identity", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument(
        "--supervised",
        action="store_true",
        help="Answer the launching supervisor over standard input and output.",
    )
    return parser.parse_args(arguments)
