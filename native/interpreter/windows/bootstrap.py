"""Retain explicit Windows DLL search directories for the interpreter lifetime."""

import os
import sys

_HANDLES = []


def prepare(root, manifest):
    """Register only existing native directories beneath the package root."""
    if sys.platform != "win32":
        raise ImportError("Windows DLL search directories require Windows")
    for relative in manifest["dll_directories"]:
        directory = (root / relative).resolve()
        if not directory.is_relative_to(root) or directory == root or not directory.is_dir():
            raise ImportError(f"Invalid bundled native directory: {directory}")
        _HANDLES.append(os.add_dll_directory(str(directory)))
