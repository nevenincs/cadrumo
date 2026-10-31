"""Bounded ARM64 Mach-O decoding for native package assembly."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

# LLVM maps the declared generic arm64/aarch64 target to CPU_SUBTYPE_ARM64_ALL.
# arm64e (including pointer-authentication ABI/version bits) is a different target.
_ARM64_ALL = 0


@dataclass(frozen=True)
class MachO:
    """Validated single-architecture load commands needed for bundle relocation."""

    dependencies: tuple[str, ...]
    rpaths: tuple[str, ...]
    identity: str | None
    minimum: tuple[int, int, int]
    info_plist: bytes | None = None
    """The property list embedded in the image's ``__TEXT,__info_plist`` section, when it has one."""


def select_arm64(path: Path) -> None:
    """Project an admitted universal image onto its one bounded ARM64 slice."""
    data = path.read_bytes()
    formats = {
        b"\xca\xfe\xba\xbe": (">", False),
        b"\xbe\xba\xfe\xca": ("<", False),
        b"\xca\xfe\xba\xbf": (">", True),
        b"\xbf\xba\xfe\xca": ("<", True),
    }
    if data[:4] not in formats:
        return
    if len(data) < 8:
        raise ValueError(f"Truncated universal Mach-O header: {path}")
    endian, wide = formats[data[:4]]
    count = struct.unpack_from(endian + "I", data, 4)[0]
    width = 32 if wide else 20
    table_end = 8 + count * width
    if count not in {1, 2} or table_end > len(data):
        raise ValueError(f"Invalid universal Mach-O architecture table: {path}")
    selected = _select_fat_slice(data, endian, wide, count, width, table_end, path)
    path.write_bytes(selected)


def _select_fat_slice(
    data: bytes, endian: str, wide: bool, count: int, width: int, table_end: int, path: Path
) -> bytes:
    spans: list[tuple[int, int]] = []
    machines: set[int] = set()
    selected = None
    for index in range(count):
        position = 8 + index * width
        values = struct.unpack_from(endian + ("IIQQII" if wide else "IIIII"), data, position)
        cpu, subtype, start, size, _alignment = values[:5]
        _validate_fat_slice(values, table_end, len(data), machines, spans, wide, path)
        machines.add(cpu)
        spans.append((start, start + size))
        image = data[start : start + size]
        if image[:4] != b"\xcf\xfa\xed\xfe" or struct.unpack_from("<II", image, 4) != (cpu, subtype):
            raise ValueError(f"Universal Mach-O slice disagrees with its architecture table: {path}")
        if cpu == 0x0100000C:
            if subtype != _ARM64_ALL:
                raise ValueError(f"Universal Mach-O slice requires a different ARM64 CPU subtype: {path}")
            selected = image
    if selected is None:
        raise ValueError(f"Universal Mach-O image lacks the declared ARM64 target: {path}")
    return selected


def _validate_fat_slice(
    values: tuple[int, ...],
    table_end: int,
    data_size: int,
    machines: set[int],
    spans: list[tuple[int, int]],
    wide: bool,
    path: Path,
) -> None:
    cpu, _subtype, start, size, alignment = values[:5]
    if (
        not _supported_fat_cpu(cpu, machines)
        or alignment > 31
        or start < table_end
        or size < 32
        or start + size > data_size
        or start % (1 << alignment)
        or (wide and values[5] != 0)
        or _fat_slice_overlaps(start, size, spans)
    ):
        raise ValueError(f"Invalid or overlapping universal Mach-O slice: {path}")


def _supported_fat_cpu(cpu: int, machines: set[int]) -> bool:
    return cpu in {0x01000007, 0x0100000C} and cpu not in machines


def _fat_slice_overlaps(start: int, size: int, spans: list[tuple[int, int]]) -> bool:
    return any(start < end and begin < start + size for begin, end in spans)


def inspect_macho(path: Path) -> MachO:
    """Read ARM64 Mach-O load commands without loading the image."""
    data = path.read_bytes()
    count, end = _macho_header(data, path)
    dependencies: list[str] = []
    rpaths: list[str] = []
    identity = None
    minimum = None
    info_plist = None
    offset = 32
    for _ in range(count):
        command_id, length = _macho_command_header(data, offset, end, path)
        if command_id == 0x19:
            info_plist = _macho_info_plist(data, offset, length, path) or info_plist
        if command_id in {0xC, 0xD, 0x20, 0x80000018, 0x8000001F, 0x80000023, 0x8000001C}:
            identity = _record_macho_path(data, offset, length, command_id, path, dependencies, rpaths, identity)
        if command_id in {0x32, 0x24}:
            declared = _macho_deployment(data, offset, length, command_id, path)
            minimum = max(minimum or declared, declared)
        offset += length
    if offset != end or minimum is None:
        raise ValueError(f"Mach-O image lacks a valid deployment floor: {path}")
    return MachO(tuple(dependencies), tuple(rpaths), identity, minimum, info_plist)


def _record_macho_path(
    data: bytes,
    offset: int,
    length: int,
    command_id: int,
    path: Path,
    dependencies: list[str],
    rpaths: list[str],
    identity: str | None,
) -> str | None:
    """Classify a validated path command without changing load-command order."""
    value = _macho_command_path(data, offset, length, path)
    if command_id == 0xD:
        return value
    if command_id == 0x8000001C:
        rpaths.append(value)
    else:
        dependencies.append(value)
    return identity


def _macho_info_plist(data: bytes, offset: int, length: int, path: Path) -> bytes | None:
    """Return the bytes of a segment's ``__TEXT,__info_plist`` section, or nothing."""
    segment_header, section_size = 72, 80
    if length < segment_header:
        raise ValueError(f"Truncated Mach-O segment command: {path}")
    sections = struct.unpack_from("<I", data, offset + 64)[0]
    if length < segment_header + sections * section_size:
        raise ValueError(f"Truncated Mach-O segment sections: {path}")
    for index in range(sections):
        start = offset + segment_header + index * section_size
        section, segment = (data[start + shift : start + shift + 16].rstrip(b"\0") for shift in (0, 16))
        if (segment, section) != (b"__TEXT", b"__info_plist"):
            continue
        size = struct.unpack_from("<Q", data, start + 40)[0]
        position = struct.unpack_from("<I", data, start + 48)[0]
        if position + size > len(data):
            raise ValueError(f"Mach-O info_plist section lies outside the image: {path}")
        return bytes(data[position : position + size])
    return None


def _macho_command_header(data: bytes, offset: int, end: int, path: Path) -> tuple[int, int]:
    if offset + 8 > end:
        raise ValueError(f"Truncated Mach-O command: {path}")
    command_id, length = struct.unpack_from("<II", data, offset)
    if length < 8 or length % 8 or offset + length > end:
        raise ValueError(f"Invalid Mach-O command length: {path}")
    if command_id == 0x27:
        raise ValueError(f"Mach-O image embeds loader environment controls: {path}")
    return int(command_id), int(length)


def _macho_header(data: bytes, path: Path) -> tuple[int, int]:
    if len(data) < 32 or data[:4] != b"\xcf\xfa\xed\xfe" or struct.unpack_from("<I", data, 4)[0] != 0x0100000C:
        raise ValueError(f"Expected a thin ARM64 Mach-O image: {path}")
    if struct.unpack_from("<I", data, 8)[0] != _ARM64_ALL:
        raise ValueError(f"Mach-O image requires a different ARM64 CPU subtype: {path}")
    count, size = struct.unpack_from("<II", data, 16)
    end = 32 + size
    if end > len(data) or count > size // 8:
        raise ValueError(f"Truncated Mach-O load commands: {path}")
    return int(count), int(end)


def _macho_deployment(data: bytes, offset: int, length: int, command_id: int, path: Path) -> tuple[int, int, int]:
    if length < (24 if command_id == 0x32 else 16):
        raise ValueError(f"Truncated Mach-O deployment command: {path}")
    if command_id == 0x32 and struct.unpack_from("<I", data, offset + 8)[0] != 1:
        raise ValueError(f"Mach-O image is not built for macOS: {path}")
    version = int(struct.unpack_from("<I", data, offset + (12 if command_id == 0x32 else 8))[0])
    return (version >> 16, (version >> 8) & 255, version & 255)


def _macho_command_path(data: bytes, offset: int, length: int, path: Path) -> str:
    if length < 16:
        raise ValueError(f"Truncated Mach-O path command: {path}")
    start = struct.unpack_from("<I", data, offset + 8)[0]
    if start < 12 or start >= length:
        raise ValueError(f"Invalid Mach-O path offset: {path}")
    raw = data[offset + start : offset + length]
    if b"\0" not in raw:
        raise ValueError(f"Unterminated Mach-O path: {path}")
    return raw.split(b"\0", 1)[0].decode("utf-8")
