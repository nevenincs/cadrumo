"""Read PE import names without loading or executing the inspected library."""

from __future__ import annotations

import struct
from pathlib import Path


def imports(path: Path) -> set[str]:
    """Return ordinary and delayed import basenames from a PE32+ image."""
    data = path.read_bytes()

    def unpack(format: str, offset: int) -> tuple[int, ...]:
        try:
            return tuple(int(value) for value in struct.unpack_from(format, data, offset))
        except struct.error as error:
            raise ValueError(f"Truncated PE image: {path}") from error

    header = unpack("<I", 0x3C)[0]
    if data[:2] != b"MZ" or data[header : header + 4] != b"PE\0\0":
        raise ValueError(f"Invalid PE image: {path}")
    if unpack("<H", header + 4)[0] != 0x8664:
        raise ValueError(f"Expected an AMD64 PE image: {path}")
    sections = unpack("<H", header + 6)[0]
    optional_size = unpack("<H", header + 20)[0]
    optional = header + 24
    if unpack("<H", optional)[0] != 0x20B:
        raise ValueError(f"Expected a PE32+ image: {path}")
    section_table = optional + optional_size

    def offset(rva: int) -> int:
        for index in range(sections):
            virtual_size, address, raw_size, raw = unpack("<IIII", section_table + index * 40 + 8)
            if address <= rva < address + max(virtual_size, raw_size):
                result = raw + rva - address
                if result < len(data):
                    return result
        raise ValueError(f"Invalid PE import address in {path}: {rva}")

    result = set()
    for directory, width, name_index in ((1, 20, 3), (13, 32, 1)):
        rva, size = unpack("<II", optional + 112 + directory * 8)
        if not rva:
            continue
        start = offset(rva)
        for position in range(start, start + size, width):
            descriptor = unpack("<" + "I" * (width // 4), position)
            if not any(descriptor):
                break
            if directory == 13 and descriptor[0] != 1:
                raise ValueError(f"Unsupported non-RVA delayed import in {path}")
            name_start = offset(descriptor[name_index])
            name_end = data.find(b"\0", name_start, name_start + 1024)
            if name_end < 0:
                raise ValueError(f"Unterminated PE import in {path}")
            name = data[name_start:name_end].decode("ascii").casefold()
            if "/" in name or "\\" in name:
                raise ValueError(f"Expected an import basename in {path}: {name}")
            result.add(name)
    return result
