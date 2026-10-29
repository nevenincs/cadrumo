"""Assemble a package from shared inputs and an explicit platform contract."""

from __future__ import annotations

import shutil
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from .hashing import digest
from .layout import (
    ApplicationImage,
    application_images,
)


def image_artifact(argument: str) -> tuple[str, Path]:
    """Split one FILE=ARTIFACT argument, refusing an empty side."""
    name, separator, artifact = argument.partition("=")
    if not separator or not name or not artifact:
        raise ValueError(f"Application image arguments take FILE=ARTIFACT: {argument!r}")
    return name, Path(artifact)


def named_application_images(layout: Mapping[str, Any], artifacts: Mapping[str, Path]) -> tuple[ApplicationImage, ...]:
    """Return the declared images CMake named with an artifact, in declaration order.

    CMake alone decides which images a package stages; an artifact for an undeclared
    image is refused when staging.
    """
    return tuple(image for image in application_images(dict(layout)) if image.file in artifacts)


def stage_application_images(
    root: Path,
    images: tuple[ApplicationImage, ...],
    artifacts: Mapping[str, Path],
    binary_dir: Path,
    *,
    copy_function: Callable[[Path, Path], object] = shutil.copy2,
) -> list[str]:
    """Copy each staged application image from the artifact its CMake target built, refusing any gap."""
    unexpected = sorted(set(artifacts) - {image.file for image in images})
    if unexpected:
        raise ValueError(f"Artifacts were supplied for images this package does not stage: {unexpected}")
    owner = binary_dir.resolve()
    staged: list[str] = []
    for image in images:
        if image.file not in artifacts:
            raise ValueError(f"No artifact was supplied for application image {image.file}; build {image.target}")
        source = artifacts[image.file].resolve()
        if not source.is_relative_to(owner):
            raise ValueError(f"Application image artifact lies outside the CMake binary directory: {source}")
        if not source.is_file():
            raise FileNotFoundError(f"Application image artifact is missing: {source}; build {image.target}")
        target = root / image.package_path
        if target.exists():
            raise FileExistsError(f"Application image collides with an assembled file: {image.package_path}")
        copy_function(source, target)
        staged.append(image.package_path)
    return staged


def _license_member(value: object) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ValueError("SDK license paths must be nonempty relative strings")
    member = PurePosixPath(value)
    if member.is_absolute() or ".." in member.parts or "\\" in value or ":" in value or not member.parts:
        raise ValueError(f"SDK license path is not package-relative: {value!r}")
    return member


def stage_sdk_licenses(root: Path, sdk: Path, contract: Mapping[str, Any]) -> None:
    """Retain CPython's canonical notice and all declared embedded SDK notices."""
    declarations = dict(contract["sdk"].get("licenses", {}))
    declarations[contract["sdk"]["license"]] = contract["files"]["python_license"]
    for source_name, destination_name in declarations.items():
        source_member = _license_member(source_name)
        source = sdk
        for part in source_member.parts:
            source /= part
            if source.is_symlink() or source.is_junction():
                raise ValueError(f"SDK license source is linked: {source}")
        destination = root / _license_member(destination_name)
        if not source.resolve(strict=True).is_relative_to(sdk.resolve(strict=True)):
            raise ValueError(f"SDK license source escapes the SDK: {source}")
        _validate_license_members(source)
        if destination.exists():
            raise FileExistsError(f"SDK license collides with a staged file: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)


def native_assembly_layout(contract: dict[str, Any], provenance: Mapping[str, Any]) -> dict[str, Any]:
    """Bind binary rewriting to the exact tools selected and hashed by CMake."""
    required = {
        "windows": (),
        "linux": ("readelf", "patchelf"),
        "macos": ("install_name_tool", "codesign"),
    }[contract["backend"]]
    if not required:
        return contract
    toolchain = provenance.get("build_toolchain", {})
    tools = toolchain.get("native_tools", {})
    hashes = toolchain.get("native_tool_sha256", {})
    selected: dict[str, str] = {}
    for name in required:
        value = tools.get(name)
        if not isinstance(value, str) or not Path(value).is_absolute() or not Path(value).is_file():
            raise ValueError(f"Native assembly requires an explicit absolute {name} tool")
        if digest(Path(value)) != hashes.get(name):
            raise ValueError(f"Native assembly tool differs from CMake provenance: {name}")
        selected[name] = value
    projected: dict[str, Any] = dict(contract, native_tools=selected)
    if contract["backend"] == "macos":
        identity = toolchain.get("native_signing_identity")
        if not isinstance(identity, str) or not identity:
            raise ValueError("Native macOS assembly requires an explicit signing identity")
        projected["native_signing_identity"] = identity
    return projected


def _validate_license_members(source: Path) -> None:
    members = [source, *sorted(source.rglob("*"))] if source.is_dir() else [source]
    for member in members:
        if member.is_symlink() or member.is_junction() or not (member.is_dir() or member.is_file()):
            raise ValueError(f"SDK license source is linked or special: {member}")
