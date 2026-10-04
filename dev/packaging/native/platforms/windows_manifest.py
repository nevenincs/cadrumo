"""Check the manifest actually embedded in a Windows host after linking."""

from __future__ import annotations

import argparse
import ctypes
from pathlib import Path


def embedded_manifest(executable: Path) -> bytes:
    """Read process manifest resource 1 without executing the image."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    pointer = ctypes.c_void_p
    signatures = {
        "LoadLibraryExW": ([ctypes.c_wchar_p, pointer, ctypes.c_uint32], pointer),
        "FindResourceW": ([pointer, pointer, pointer], pointer),
        "LoadResource": ([pointer, pointer], pointer),
        "LockResource": ([pointer], pointer),
        "SizeofResource": ([pointer, pointer], ctypes.c_uint32),
        "FreeLibrary": ([pointer], ctypes.c_int),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(kernel, name)
        function.argtypes = arguments
        function.restype = result
    # LOAD_LIBRARY_AS_DATAFILE: inspect resources without resolving imports or running DllMain.
    image = kernel.LoadLibraryExW(str(executable.resolve(strict=True)), None, 2)
    if not image:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        resource = kernel.FindResourceW(image, 1, 24)
        if not resource:
            raise ValueError(f"Missing process manifest in {executable}")
        size = kernel.SizeofResource(image, resource)
        loaded = kernel.LoadResource(image, resource)
        address = kernel.LockResource(loaded) if loaded else None
        if not size or not address:
            raise ctypes.WinError(ctypes.get_last_error())
        return ctypes.string_at(address, size)
    finally:
        kernel.FreeLibrary(image)


def check(executable: Path, manifest: Path) -> None:
    """Reject source/image divergence before staging an interpreter."""
    if embedded_manifest(executable) != manifest.read_bytes():
        raise ValueError(f"Embedded process manifest differs from {manifest}: {executable}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    check(args.executable, args.manifest)
