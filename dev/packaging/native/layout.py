"""Resolve the canonical package contract and its explicitly implemented platform."""

from __future__ import annotations

import importlib
import json
import platform
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from cadrumo.core.toml import parse_toml
from dev._paths import REPO_ROOT

# Entrypoint names reach C string literals, CMake target names and Python source.
_ENTRYPOINT_NAME = re.compile(r"[a-z][a-z0-9]*(-[a-z0-9]+)*")
# Application image targets and artifact variables are CMake identifiers read at configure time.
_CMAKE_TARGET = re.compile(r"[A-Za-z0-9_.+-]+")
_CMAKE_VARIABLE = re.compile(r"[A-Z][A-Z0-9_]*")
_IMAGE_REQUIRED = frozenset({"name", "placement", "target", "artifact", "desktop", "signed", "version_arguments"})
_IMAGE_OPTIONAL = frozenset({"startup"})
# The platform context maps only an image in the package root, or a declared entrypoint in the
# native directory, back to the package; any other placement could not find its package.
_PACKAGE_ROOT = "."


@dataclass(frozen=True)
class ApplicationImage:
    """A native executable that is not an interpreter host, staged from its CMake build target."""

    name: str
    file: str
    placement: str
    target: str
    artifact: str
    desktop: bool
    signed: bool
    startup: bool
    version_arguments: tuple[str, ...]

    @property
    def package_path(self) -> str:
        """Return the image's package-relative path."""
        return self.file if self.placement == _PACKAGE_ROOT else f"{self.placement}/{self.file}"


def load_layout(name: str | None = None, *, root: Path = REPO_ROOT) -> dict[str, Any]:
    """Combine shared locations with one implemented platform's physical mapping."""
    if name is None:
        machine = platform.machine().lower()
        architecture = {"amd64": "x86-64", "x86_64": "x86-64"}.get(machine, machine)
        name = f"{ {'win32': 'windows', 'darwin': 'macos'}.get(sys.platform, sys.platform) }-{architecture}"
    if name == "windows-x86-64":
        name = "windows-x64"
    shared = json.loads((root / "native/package-layout.json").read_text(encoding="utf-8"))
    mapping = shared.pop("platforms")
    if name not in mapping:
        raise NotImplementedError(f"Native packaging is not implemented for {name}")
    selected = json.loads((root / "native" / mapping[name]).read_text(encoding="utf-8"))
    for key in ("paths", "files"):
        shared[key].update(selected.pop(key))
    shared.update(selected)
    scripts = parse_toml((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
    for entrypoint in shared["entrypoints"]:
        if not _ENTRYPOINT_NAME.fullmatch(entrypoint) or entrypoint not in scripts:
            raise ValueError(f"Native entrypoint is not a declared console script: {entrypoint}")
    application_images(shared)
    return shared


def distribution_target(layout: dict[str, Any]) -> str:
    """Return the canonical distribution target for a native platform mapping."""
    platform = str(layout["platform"])
    return "windows-x86-64" if platform == "windows-x64" else platform


def entrypoint_files(layout: dict[str, Any]) -> dict[str, str]:
    """Map each declared console entrypoint to its package-relative executable in the native directory."""
    native = layout["paths"]["native"]
    return {name: f"{native}/{name}{layout['entrypoint_suffix']}" for name in layout["entrypoints"]}


def _image(entry: object, suffix: str) -> ApplicationImage:
    if not isinstance(entry, dict) or not _IMAGE_REQUIRED <= set(entry) <= _IMAGE_REQUIRED | _IMAGE_OPTIONAL:
        raise ValueError(
            f"Application image must declare {sorted(_IMAGE_REQUIRED)} and optionally {sorted(_IMAGE_OPTIONAL)}: "
            f"{entry!r}"
        )
    name, placement, target, artifact = entry["name"], entry["placement"], entry["target"], entry["artifact"]
    if not isinstance(name, str) or not _ENTRYPOINT_NAME.fullmatch(name):
        raise ValueError(f"Application image name is not a lowercase hyphenated identifier: {name!r}")
    if not isinstance(target, str) or not _CMAKE_TARGET.fullmatch(target):
        raise ValueError(f"Application image {name} must name a CMake target: {target!r}")
    if not isinstance(artifact, str) or not _CMAKE_VARIABLE.fullmatch(artifact):
        raise ValueError(f"Application image {name} must name the CMake variable holding its artifact: {artifact!r}")
    if placement != _PACKAGE_ROOT:
        raise NotImplementedError(f"Application image {name} placement {placement!r} is not implemented")
    flags = {key: entry.get(key, False) for key in ("desktop", "signed", "startup")}
    if not all(isinstance(value, bool) for value in flags.values()):
        raise ValueError(f"Application image {name} flags must be booleans: {flags}")
    arguments = entry["version_arguments"]
    if not isinstance(arguments, list) or not all(isinstance(item, str) and item for item in arguments):
        raise ValueError(f"Application image {name} version_arguments must be a list of non-empty strings")
    return ApplicationImage(
        name=name,
        file=f"{name}{suffix}",
        placement=placement,
        target=target,
        artifact=artifact,
        version_arguments=tuple(arguments),
        **flags,
    )


def application_images(layout: dict[str, Any]) -> tuple[ApplicationImage, ...]:
    """Validate the platform mapping's application images against every other package-root name."""
    declared = layout.get("application_images", [])
    if not isinstance(declared, list):
        raise ValueError("application_images must be a list")
    # Windows file names compare without case, so every collision check folds case.
    occupied = {
        str(path).split("/")[0].casefold(): str(path) for path in (*layout["paths"].values(), *layout["files"].values())
    }
    entrypoints = set(layout["entrypoints"])
    images: list[ApplicationImage] = []
    for entry in declared:
        image = _image(entry, layout["entrypoint_suffix"])
        if image.name in entrypoints:
            # A same-named copy at the package root is the displaced entrypoint the verifier refuses.
            raise ValueError(f"Application image collides with a console entrypoint: {image.name}")
        if image.package_path.casefold() in occupied:
            raise ValueError(
                f"Application image {image.file} collides with package file {occupied[image.package_path.casefold()]}"
            )
        if any(image.name == other.name for other in images):
            raise ValueError(f"Duplicate application image: {image.name}")
        if any(image.artifact == other.artifact for other in images):
            raise ValueError(f"Application images share the artifact variable {image.artifact}")
        images.append(image)
    if sum(image.desktop for image in images) > 1:
        raise ValueError("At most one application image is the desktop application")
    return tuple(images)


def staged_application_images(layout: dict[str, Any], *, user_docs: bool) -> tuple[ApplicationImage, ...]:
    """Return the images a package stages; the desktop image serves the bundled docs, so it needs them."""
    return tuple(image for image in application_images(layout) if user_docs or not image.desktop)


def desktop_image(layout: dict[str, Any]) -> ApplicationImage | None:
    """Return the one image that receives desktop registration, when the platform declares one."""
    return next((image for image in application_images(layout) if image.desktop), None)


def backend(contract: dict[str, Any]) -> ModuleType:
    """Select only an enrolled backend from the canonical contract."""
    name = contract["backend"]
    if name == "windows":
        return importlib.import_module("dev.packaging.native.platforms.windows")
    if name == "linux":
        return importlib.import_module("dev.packaging.native.platforms.linux")
    if name == "macos":
        return importlib.import_module("dev.packaging.native.platforms.macos")
    raise ValueError("Native backend has no implemented enrollment")
