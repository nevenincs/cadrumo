"""Validate the native inventory; relative loader paths are established at assembly."""

import sys


def prepare(root, manifest):
    """Reject escaped or missing extensions without adding ambient loader directories."""
    if sys.platform not in {"linux", "darwin"}:
        raise ImportError("POSIX native loading requires Linux or macOS")
    for relative in manifest["modules"].values():
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or path == root or not path.is_file():
            raise ImportError(f"Invalid bundled native module: {relative}")
