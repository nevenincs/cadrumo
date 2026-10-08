"""ELF assembly with explicit dependency closure and per-object relative RUNPATH."""

from __future__ import annotations

import json
import re
import struct
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


def relocate(images: list[Path], root: Path, contract: dict[str, Any]) -> None:
    """Refuse wrong architectures/floors and resolve every non-system DT_NEEDED in the bundle."""
    target = target_platform(contract["platform"])
    tools = contract["native_tools"]
    system = set(contract["native_system_libraries"])
    names = dependencies_by_name(images)
    machine = {"x86_64": 62, "aarch64": 183}[target.platform_machine]
    floor = (*map(int, target.floor.removeprefix("glibc-").split(".")), 0)
    for path in images:
        with path.open("rb") as source:
            header = source.read(20)
        if len(header) != 20 or header[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", header, 18)[0] != machine:
            raise ValueError(f"Wrong ELF architecture or ABI: {path}")
        versions = command(tools["readelf"], "--version-info", str(path))
        for version in re.findall(r"\bGLIBC_([A-Za-z0-9_.]+)", versions):
            if not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", version):
                raise ValueError(f"ELF uses an unadmitted glibc ABI requirement: {path}: {version}")
            required = tuple(map(int, version.split(".")))
            if required > floor:
                raise ValueError(f"ELF exceeds canonical glibc floor: {path}: {version}")
        needed = command(tools["patchelf"], "--print-needed", str(path)).splitlines()
        directories = set()
        for dependency in needed:
            if dependency in system:
                if dependency in names:
                    raise ValueError(f"Bundled image shadows a system dependency: {dependency}")
                continue
            if "/" in dependency or dependency not in names:
                raise ValueError(f"Unresolved ELF dependency: {path}: {dependency}")
            directories.add(relative_loader_path(path.parent, names[dependency].parent, "$ORIGIN"))
        if directories:
            command(tools["patchelf"], "--set-rpath", ":".join(sorted(directories)), str(path))
        else:
            command(tools["patchelf"], "--remove-rpath", str(path))
        actual = command(tools["patchelf"], "--print-rpath", str(path))
        if actual != ":".join(sorted(directories)):
            raise ValueError(f"ELF RUNPATH rewrite failed: {path}")


def assemble_native(python: Path, packages: Path, native: Path, root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    """Assemble the selected Linux SDK and wheel closure."""
    return assemble(python, packages, native, root, contract, relocate)


def provision_sdk(destination: Path, pin: str, tools: dict[str, Any], contract: dict[str, Any]) -> Path:
    """Require Linux provenance before acquiring an SDK; no host or source-build fallback."""
    if target_platform(contract["platform"]).sys_platform != "linux":
        raise ValueError("Linux SDK backend received another operating system")
    return acquire_sdk(destination, pin, tools, contract)


def external_probe(destination: Path) -> list[str]:
    """Install the executable used by Linux artifact PATH-override verification."""
    return install_external_probe(destination)


def resources(
    destination: Path, version: str, number: int, date: str, tools: Path, entrypoints: dict[str, str]
) -> None:
    """Validate embedded build identity; ELF hosts need no additional resource compiler."""
    metadata = json.loads((destination / "build.json").read_text(encoding="utf-8"))
    if target_platform(metadata["target"]).sys_platform != "linux" or metadata["version"] != version:
        raise ValueError("ELF build metadata does not match the selected product/target")


def verify(
    package: Path, *, destination: Path | None, product: bool, build_root: Path | None, already_relocated: bool = False
) -> None:
    """Run artifact-bound Linux imports, child identity, hostile-loader and immutability checks."""
    if already_relocated:
        if destination is not None or build_root is None:
            raise ValueError("Already relocated verification requires its owning build root without a destination")
        verify_package(package, build_root, "linux", already_relocated=True)
        return
    if destination is None:
        raise ValueError("Supply an isolated native verification destination")
    verify_package(package, destination, "linux")
