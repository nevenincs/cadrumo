"""Mach-O relocation with explicit dependencies, deployment floor and final image sealing."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dev.paths import REPO_ROOT

from ...runtime_wheelhouse_contract import target_platform
from ..agent_runtime import STAGED_RECEIPT_NAME, STAGED_RUNTIME_TREES
from ..build_stamp import BuildStamp
from ..identity import DistributionIdentity
from ..layout import application_images
from .macos_macho import MachO, inspect_macho, select_arm64
from .posix import (
    acquire_sdk,
    command,
    dependencies_by_name,
    install_external_probe,
    relative_loader_path,
    verify_package,
)
from .posix_assembly import PosixAssemblyResult, assemble


def relocate(images: list[Path], root: Path, contract: dict[str, Any]) -> None:
    """Rewrite every non-system dependency to its package-relative image and reseal it."""
    target = target_platform(contract["platform"])
    floor = (*map(int, target.floor.removeprefix("macos-").split(".")), 0)
    tools = contract["native_tools"]
    signing_identity = contract["native_signing_identity"]
    if not isinstance(signing_identity, str) or not signing_identity:
        raise ValueError("Mach-O relocation requires an explicit sealing identity")
    vendor, owned = split_vendor_images(images, root)
    for path in owned:
        select_arm64(path)
    names = load_targets(owned)
    system = set(contract["native_system_libraries"])
    desktop = _desktop_sealing_targets(contract, root, owned)
    for path in vendor:
        require_relocatable_as_shipped(path, floor, system)
    for path in owned:
        _relocate_image(
            path,
            floor,
            names,
            system,
            tools,
            signing_identity,
            hardened=path in desktop,
            entitlements=desktop.get(path),
        )


def _desktop_sealing_targets(contract: dict[str, Any], root: Path, owned: list[Path]) -> dict[Path, Path | None]:
    """Validate embedded desktop identity and return its declared entitlements."""
    declared = application_images(contract) if contract.get("application_images") else ()
    desktop = {
        root / image.package_path: None if image.entitlements is None else REPO_ROOT / image.entitlements
        for image in declared
        if image.desktop
    }
    shipped = sorted(desktop.keys() & set(owned))
    if shipped:
        expected = Path(contract["desktop_info_plist"]).read_bytes()
        for path in shipped:
            _require_embedded_identity(path, expected)
    return desktop


def _require_embedded_identity(path: Path, expected: bytes) -> None:
    """Refuse a desktop image whose embedded identity is not the one this build generated."""
    if inspect_macho(path).info_plist != expected:
        raise ValueError(f"Desktop image does not embed the generated identity property list: {path}")


def split_vendor_images(images: list[Path], root: Path) -> tuple[list[Path], list[Path]]:
    """Separate images inside the trees a runtime receipt pins from the images this build owns.

    The agent runtime ships the vendor's executable under a receipt that names its exact
    digest, and the package inventory is compared with that receipt. Resealing it would
    replace the vendor signature and break the digest, so it is kept as shipped.
    """
    pinned = [
        receipt.parent / name
        for receipt in root.rglob(STAGED_RECEIPT_NAME)
        if receipt.is_file()
        for name in STAGED_RUNTIME_TREES
    ]
    vendor = [path for path in images if any(path.is_relative_to(directory) for directory in pinned)]
    return vendor, [path for path in images if path not in vendor]


def require_relocatable_as_shipped(path: Path, floor: tuple[int, ...], system: set[str]) -> None:
    image = inspect_macho(path)
    if image.minimum > floor:
        raise ValueError(f"Mach-O exceeds canonical deployment floor: {path}")
    if image.rpaths or image.identity is not None or any(dependency not in system for dependency in image.dependencies):
        raise ValueError(f"Vendor Mach-O needs relocation and cannot ship as pinned: {path}")


def load_targets(images: list[Path]) -> dict[str, Path]:
    """Index the images a load command can name: dynamic libraries with an install name.

    Executables and loadable bundles carry no install name and no load command can
    reference them, so equally named but different programs do not conflict.
    """
    return dependencies_by_name([path for path in images if inspect_macho(path).identity is not None])


def _relocate_image(
    path: Path,
    floor: tuple[int, ...],
    names: Mapping[str, Path],
    system: set[str],
    tools: Mapping[str, str],
    signing_identity: str,
    *,
    hardened: bool = False,
    entitlements: Path | None = None,
) -> None:
    image = inspect_macho(path)
    if image.minimum > floor:
        raise ValueError(f"Mach-O exceeds canonical deployment floor: {path}")
    arguments = _macho_dependency_changes(path, image, names, system)
    for rpath in image.rpaths:
        arguments.extend(["-delete_rpath", rpath])
    if image.identity is not None:
        arguments.extend(["-id", f"@rpath/{path.name}"])
    if arguments:
        command(tools["install_name_tool"], *arguments, str(path))
    _seal_macho_image(path, tools, signing_identity, hardened=hardened, entitlements=entitlements)
    _require_relocated_paths(path, system)


def _seal_macho_image(
    path: Path,
    tools: Mapping[str, str],
    signing_identity: str,
    *,
    hardened: bool,
    entitlements: Path | None,
) -> None:
    """Seal the rewritten image and verify its final signature."""
    # The desktop image is the application's own program: it takes the hardened runtime, and
    # its identifier comes from the identity property list it embeds. Its entitlements are the
    # declared ones only: ad-hoc code carries no team identity for library validation to accept.
    options = ["--options", "runtime"] if hardened else []
    if entitlements is not None:
        options.extend(["--entitlements", str(entitlements)])
    command(tools["codesign"], "--force", "--sign", signing_identity, *options, str(path))
    command(tools["codesign"], "--verify", "--strict", str(path))


def _require_relocated_paths(path: Path, system: set[str]) -> None:
    """Refuse loader paths that still escape the assembled package."""
    rewritten = inspect_macho(path)
    if rewritten.rpaths or any(
        dependency not in system and not dependency.startswith("@loader_path/") for dependency in rewritten.dependencies
    ):
        raise ValueError(f"Mach-O relocation left an ambient load path: {path}")


def _macho_dependency_changes(path: Path, image: MachO, names: Mapping[str, Path], system: set[str]) -> list[str]:
    arguments: list[str] = []
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
    return arguments


def assemble_native(
    python: Path, packages: Path, native: Path, root: Path, contract: dict[str, Any]
) -> PosixAssemblyResult:
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
    destination: Path,
    version: str,
    stamp: BuildStamp,
    tools: Path,
    entrypoints: dict[str, str],
    product: DistributionIdentity,
    *,
    shared: Path | None = None,
) -> None:
    """Validate embedded identity; application bundle metadata belongs to the bundle assembler."""
    metadata = json.loads((destination / "build.json").read_text(encoding="utf-8"))
    if (
        target_platform(metadata["target"]).sys_platform != "darwin"
        or metadata["version"] != version
        or metadata["application_id"] != product.application_id
    ):
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
