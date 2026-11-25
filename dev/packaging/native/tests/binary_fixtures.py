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


def elf_with_requirements(
    path: Path, *, needed: tuple[str, ...] = (), glibc: tuple[str, ...] = (), machine: int = 62
) -> Path:
    """Write an ELF64 image whose dynamic section needs ``needed`` and whose version needs name ``glibc``.

    Each ``glibc`` entry is a version number such as ``2.34``, written as the symbol version ``GLIBC_2.34``.
    """
    strings = bytearray(b"\0")

    def string(text: str) -> int:
        offset = len(strings)
        strings.extend(text.encode() + b"\0")
        return offset

    dynamic = b"".join(struct.pack("<qQ", 1, string(name)) for name in needed) + struct.pack("<qQ", 0, 0)
    versions = b""
    if glibc:
        file = string("libc.so.6")
        versions = struct.pack("<HHIII", 1, len(glibc), file, 16, 0)
        for index, version in enumerate(glibc):
            following = 16 if index < len(glibc) - 1 else 0
            versions += struct.pack("<IHHII", 0, 0, 0, string(f"GLIBC_{version}"), following)
    parts = [(0, b"", 0, 0), (3, bytes(strings), 0, 0), (6, dynamic, 1, 0)]
    if glibc:
        parts.append((0x6FFFFFFE, versions, 1, 1))
    body = bytearray(64)
    headers = [struct.pack("<IIQQQQIIQQ", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)]
    for kind, content, link, info in parts[1:]:
        headers.append(struct.pack("<IIQQQQIIQQ", 0, kind, 0, 0, len(body), len(content), link, info, 1, 0))
        body.extend(content)
    table = len(body)
    body.extend(b"".join(headers))
    body[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<H", body, 18, machine)
    struct.pack_into("<Q", body, 0x28, table)
    struct.pack_into("<HH", body, 0x3A, 64, len(headers))
    path.write_bytes(body)
    return path


def pe_with_imports(path: Path, *imported: str) -> Path:
    """Write a PE32+ AMD64 image whose import table names ``imported``."""
    image = bytearray(0x400)
    image[:2] = b"MZ"
    struct.pack_into("<I", image, 0x3C, 0x80)
    image[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", image, 0x84, 0x8664)
    struct.pack_into("<H", image, 0x86, 1)
    struct.pack_into("<H", image, 0x94, 240)
    struct.pack_into("<H", image, 0x98, 0x20B)
    base, virtual = 0x400, 0x1000
    descriptors = base
    names = descriptors + 20 * (len(imported) + 1)
    section = bytearray(names - base)
    cursor = len(section)
    for index, name in enumerate(imported):
        struct.pack_into("<IIIII", section, 20 * index, 0, 0, 0, virtual + cursor, 0)
        encoded = name.encode("ascii") + b"\0"
        section.extend(encoded)
        cursor += len(encoded)
    struct.pack_into("<II", image, 0x98 + 112 + 8, virtual, 20 * (len(imported) + 1))
    table = 0x98 + 240
    struct.pack_into("<IIII", image, table + 8, len(section), virtual, len(section), base)
    path.write_bytes(bytes(image) + bytes(section))
    return path


def macho_image(path: Path, *, dependencies: tuple[str, ...] = (), identity: str | None = None) -> Path:
    """Write a thin ARM64 Mach-O image for macOS 13.3 that loads ``dependencies``."""

    def dylib(command: int, name: str) -> bytes:
        encoded = name.encode() + b"\0"
        size = (24 + len(encoded) + 7) & ~7
        return struct.pack("<IIIIII", command, size, 24, 0, 0, 0) + encoded.ljust(size - 24, b"\0")

    commands = [struct.pack("<IIIIII", 0x32, 24, 1, (13 << 16) | (3 << 8), 0, 0)]
    if identity is not None:
        commands.append(dylib(0xD, identity))
    commands.extend(dylib(0xC, name) for name in dependencies)
    payload = b"".join(commands)
    header = struct.pack("<IIIIIIII", 0xFEEDFACF, 0x0100000C, 0, 6, len(commands), len(payload), 0, 0)
    path.write_bytes(header + payload)
    return path
