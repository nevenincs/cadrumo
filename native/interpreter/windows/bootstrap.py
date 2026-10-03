"""Retain explicit Windows DLL search directories for the interpreter lifetime."""

import os

_HANDLES = []


def prepare(root, manifest):
    """Register only existing native directories beneath the package root."""
    for relative in manifest["dll_directories"]:
        directory = (root / relative).resolve()
        if not directory.is_relative_to(root) or directory == root or not directory.is_dir():
            raise ImportError(f"Invalid bundled native directory: {directory}")
        _HANDLES.append(os.add_dll_directory(str(directory)))
