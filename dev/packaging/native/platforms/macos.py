"""Mach-O relocation with explicit dependencies, deployment floor and final image sealing."""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...runtime_wheelhouse_contract import target_platform
from .posix import (
    acquire_sdk,
    assemble,
    command,
    dependencies_by_name,
    install_external_probe,
    relative_loader_path,
    verify_package,
)

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


def _select_arm64(path: Path) -> None:
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
    spans = []
    machines = set()
    selected = None
    for index in range(count):
        position = 8 + index * width
        values = struct.unpack_from(endian + ("IIQQII" if wide else "IIIII"), data, position)
        cpu, subtype, start, size, alignment = values[:5]
        if (
            cpu not in {0x01000007, 0x0100000C}
            or cpu in machines
            or alignment > 31
            or start < table_end
            or size < 32
            or start + size > len(data)
            or start % (1 << alignment)
            or (wide and values[5] != 0)
            or any(start < end and begin < start + size for begin, end in spans)
        ):
            raise ValueError(f"Invalid or overlapping universal Mach-O slice: {path}")
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
    path.write_bytes(selected)


def inspect(path: Path) -> MachO:
    """Read ARM64 Mach-O load commands without loading the image."""
    data = path.read_bytes()
    if len(data) < 32 or data[:4] != b"\xcf\xfa\xed\xfe" or struct.unpack_from("<I", data, 4)[0] != 0x0100000C:
        raise ValueError(f"Expected a thin ARM64 Mach-O image: {path}")
    if struct.unpack_from("<I", data, 8)[0] != _ARM64_ALL:
        raise ValueError(f"Mach-O image requires a different ARM64 CPU subtype: {path}")
    count, size = struct.unpack_from("<II", data, 16)
    end = 32 + size
    if end > len(data) or count > size // 8:
        raise ValueError(f"Truncated Mach-O load commands: {path}")
    dependencies: list[str] = []
    rpaths: list[str] = []
    identity = None
    minimum = None
    offset = 32
    for _ in range(count):
        if offset + 8 > end:
            raise ValueError(f"Truncated Mach-O command: {path}")
        command_id, length = struct.unpack_from("<II", data, offset)
        if length < 8 or length % 8 or offset + length > end:
            raise ValueError(f"Invalid Mach-O command length: {path}")
        if command_id == 0x27:
            raise ValueError(f"Mach-O image embeds loader environment controls: {path}")
        if command_id in {0xC, 0xD, 0x20, 0x80000018, 0x8000001F, 0x80000023, 0x8000001C}:
            if length < 16:
                raise ValueError(f"Truncated Mach-O path command: {path}")
            start = struct.unpack_from("<I", data, offset + 8)[0]
            if start < 12 or start >= length:
                raise ValueError(f"Invalid Mach-O path offset: {path}")
            raw = data[offset + start : offset + length]
            if b"\0" not in raw:
                raise ValueError(f"Unterminated Mach-O path: {path}")
            value = raw.split(b"\0", 1)[0].decode("utf-8")
            if command_id == 0xD:
                identity = value
            elif command_id == 0x8000001C:
                rpaths.append(value)
            else:
                dependencies.append(value)
        if command_id in {0x32, 0x24}:
            if length < (24 if command_id == 0x32 else 16):
                raise ValueError(f"Truncated Mach-O deployment command: {path}")
            if command_id == 0x32 and struct.unpack_from("<I", data, offset + 8)[0] != 1:
                raise ValueError(f"Mach-O image is not built for macOS: {path}")
            version = struct.unpack_from("<I", data, offset + (12 if command_id == 0x32 else 8))[0]
            declared = (version >> 16, (version >> 8) & 255, version & 255)
            minimum = max(minimum or declared, declared)
        offset += length
    if offset != end or minimum is None:
        raise ValueError(f"Mach-O image lacks a valid deployment floor: {path}")
    return MachO(tuple(dependencies), tuple(rpaths), identity, minimum)


def relocate(images: list[Path], root: Path, contract: dict[str, Any]) -> None:
    """Rewrite every non-system dependency to its package-relative image and reseal it."""
    target = target_platform(contract["platform"])
    floor = (*map(int, target.floor.removeprefix("macos-").split(".")), 0)
    tools = contract["native_tools"]
    signing_identity = contract["native_signing_identity"]
    if not isinstance(signing_identity, str) or not signing_identity:
        raise ValueError("Mach-O relocation requires an explicit sealing identity")
    for path in images:
        _select_arm64(path)
    names = dependencies_by_name(images)
    system = set(contract["native_system_libraries"])
    for path in images:
        image = inspect(path)
        if image.minimum > floor:
            raise ValueError(f"Mach-O exceeds canonical deployment floor: {path}")
        arguments = []
        for dependency in image.dependencies:
            if dependency in system:
                if Path(dependency).name in names:
                    raise ValueError(f"Bundled image shadows system dependency: {dependency}")
                continue
            target_path = names.get(Path(dependency).name)
            if target_path is None:
                raise ValueError(f"Unresolved Mach-O dependency: {path}: {dependency}")
            replacement = relative_loader_path(path.parent, target_path, "@loader_path")
            arguments.extend(["-change", dependency, replacement])
        for rpath in image.rpaths:
            arguments.extend(["-delete_rpath", rpath])
        if image.identity is not None:
            arguments.extend(["-id", f"@rpath/{path.name}"])
        if arguments:
            command(tools["install_name_tool"], *arguments, str(path))
        command(tools["codesign"], "--force", "--sign", signing_identity, str(path))
        command(tools["codesign"], "--verify", "--strict", str(path))
        rewritten = inspect(path)
        if rewritten.rpaths or any(
            dependency not in system and not dependency.startswith("@loader_path/")
            for dependency in rewritten.dependencies
        ):
            raise ValueError(f"Mach-O relocation left an ambient load path: {path}")


def assemble_native(python: Path, packages: Path, native: Path, root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    """Assemble the selected macOS SDK and wheel closure, then seal each image."""
    return assemble(python, packages, native, root, contract, relocate)


def provision_sdk(destination: Path, pin: str, tools: dict[str, Any], contract: dict[str, Any]) -> Path:
    """Require macOS provenance before acquiring an SDK; no system-framework fallback."""
    if target_platform(contract["platform"]).sys_platform != "darwin":
        raise ValueError("macOS SDK backend received another operating system")
    return acquire_sdk(destination, pin, tools, contract)


def external_probe(destination: Path) -> list[str]:
    """Install the executable used by macOS artifact PATH-override verification."""
    return install_external_probe(destination)


def resources(
    destination: Path, version: str, number: int, date: str, tools: Path, entrypoints: dict[str, str]
) -> None:
    """Validate embedded identity; application bundle metadata belongs to the bundle assembler."""
    metadata = json.loads((destination / "build.json").read_text(encoding="utf-8"))
    if target_platform(metadata["target"]).sys_platform != "darwin" or metadata["version"] != version:
        raise ValueError("Mach-O build metadata does not match the selected product/target")


def verify(
    package: Path, *, destination: Path | None, product: bool, build_root: Path | None, already_relocated: bool = False
) -> None:
    """Run artifact-bound macOS imports, child identity, hostile-loader and immutability checks."""
    if already_relocated:
        if destination is not None or build_root is None:
            raise ValueError("Already relocated verification requires its owning build root without a destination")
        verify_package(package, build_root, "darwin", already_relocated=True)
        return
    if destination is None:
        raise ValueError("Supply an isolated native verification destination")
    verify_package(package, destination, "darwin")
