"""Minimal native image headers shared by packaging policy tests."""

from __future__ import annotations

import struct
from pathlib import Path


def elf_image(path: Path, machine: int = 62) -> Path:
    """Write a 64-bit little-endian ELF header for the requested machine."""
    data = bytearray(64)
    data[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<H", data, 18, machine)
    path.write_bytes(data)
    return path
