"""Read the dynamic library needs and glibc symbol versions of an ELF64 image without loading it."""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path

_SHT_DYNAMIC = 6
_SHT_GNU_VERNEED = 0x6FFFFFFE
_DT_NULL = 0
_DT_NEEDED = 1
_SECTION_HEADER = 64
_GLIBC_VERSION = re.compile(r"GLIBC_(\d+)\.(\d+)(?:\.(\d+))?")


@dataclass(frozen=True, slots=True)
class ElfRequirements:
    """What an ELF64 little-endian image asks of its host."""

    needed: tuple[str, ...]
    """The ``DT_NEEDED`` library names, in load order."""
    glibc: tuple[int, ...] | None
    """The highest ``GLIBC_x.y[.z]`` symbol version the image requires, or ``None`` when it requires none."""


def _unpack(data: bytes, format: str, offset: int, path: Path) -> tuple[int, ...]:
    try:
        return tuple(int(value) for value in struct.unpack_from(format, data, offset))
    except struct.error as error:
        raise ValueError(f"Truncated ELF image: {path}") from error


def _string(data: bytes, table: tuple[int, int], index: int, path: Path) -> str:
    start, size = table
    if index >= size or start + size > len(data):
        raise ValueError(f"Invalid ELF string reference: {path}")
    end = data.find(b"\0", start + index, start + size)
    if end < 0:
        raise ValueError(f"Unterminated ELF string: {path}")
    return data[start + index : end].decode("utf-8")


def _sections(data: bytes, path: Path) -> list[tuple[int, int, int, int, int]]:
    """Return ``(type, offset, size, link, info)`` of every section header."""
    if len(data) < 64 or data[:4] != b"\x7fELF" or data[4:6] != b"\x02\x01":
        raise ValueError(f"Expected an ELF64 little-endian image: {path}")
    (offset,) = _unpack(data, "<Q", 0x28, path)
    entry_size, count = _unpack(data, "<HH", 0x3A, path)
    if offset == 0 or count == 0 or entry_size < _SECTION_HEADER:
        raise ValueError(f"ELF image has no section headers: {path}")
    sections: list[tuple[int, int, int, int, int]] = []
    for index in range(count):
        _name, kind, _flags, _address, start, size, link, info, _align, _entries = _unpack(
            data, "<IIQQQQIIQQ", offset + index * entry_size, path
        )
        sections.append((kind, start, size, link, info))
    return sections


def _needed(data: bytes, sections: list[tuple[int, int, int, int, int]], path: Path) -> list[str]:
    names: list[str] = []
    for kind, start, size, link, _info in sections:
        if kind != _SHT_DYNAMIC:
            continue
        if link >= len(sections):
            raise ValueError(f"Invalid ELF dynamic string table: {path}")
        table = (sections[link][1], sections[link][2])
        for position in range(start, start + size, 16):
            tag, value = _unpack(data, "<qQ", position, path)
            if tag == _DT_NULL:
                break
            if tag == _DT_NEEDED:
                names.append(_string(data, table, value, path))
    return names


def _glibc_versions(data: bytes, table: tuple[int, int], entry: int, path: Path) -> tuple[list[tuple[int, ...]], int]:
    """Return the ``GLIBC_`` versions one version-need entry names and the offset of the following entry."""
    _version, count, _file, auxiliary, following = _unpack(data, "<HHIII", entry, path)
    record = entry + auxiliary
    found: list[tuple[int, ...]] = []
    for _ in range(count):
        _hash, _flags, _other, name, next_record = _unpack(data, "<IHHII", record, path)
        version = _GLIBC_VERSION.fullmatch(_string(data, table, name, path))
        if version is not None:
            found.append(tuple(int(part) for part in version.groups() if part is not None))
        record += next_record
    return found, following


def _glibc(data: bytes, sections: list[tuple[int, int, int, int, int]], path: Path) -> tuple[int, ...] | None:
    versions: list[tuple[int, ...]] = []
    for kind, start, size, link, info in sections:
        if kind != _SHT_GNU_VERNEED:
            continue
        if link >= len(sections):
            raise ValueError(f"Invalid ELF version string table: {path}")
        table = (sections[link][1], sections[link][2])
        entry = start
        for _ in range(info):
            found, following = _glibc_versions(data, table, entry, path)
            versions.extend(found)
            if following == 0 or entry + following >= start + size:
                break
            entry += following
    return max(versions, default=None)


def read_elf_requirements(path: Path) -> ElfRequirements:
    """Read the needed libraries and highest glibc symbol version of the ELF64 image at ``path``."""
    data = path.read_bytes()
    sections = _sections(data, path)
    return ElfRequirements(needed=tuple(_needed(data, sections, path)), glibc=_glibc(data, sections, path))
