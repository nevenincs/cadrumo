"""Argument contract shared by the controlled installed-TUI child fixtures."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_receipt_path() -> Path:
    """Accept the supervisor's full child flag set and return where the receipt goes."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--workspace-root")
    parser.add_argument("--profile-label")
    parser.add_argument("--journey")
    parser.add_argument("--profile-bootstrap")
    return parser.parse_args().receipt
