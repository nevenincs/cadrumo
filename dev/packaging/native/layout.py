"""Resolve the canonical package contract and its explicitly implemented platform."""

from __future__ import annotations

import importlib
import json
import platform
import posixpath
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, cast

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
    scripts = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
    for entrypoint in shared["entrypoints"]:
        if not _ENTRYPOINT_NAME.fullmatch(entrypoint) or entrypoint not in scripts:
            raise ValueError(f"Native entrypoint is not a declared console script: {entrypoint}")
    bundled_images(shared)
    application_images(shared)
    application_bundle(shared)
    return shared


def _validate_bundled_image(name: str, entry: object, entrypoints: list[str]) -> dict[str, object]:
    if not _ENTRYPOINT_NAME.fullmatch(name) or name in entrypoints:
        raise ValueError(f"Bundled image is not a distinct lowercase hyphenated name: {name!r}")
    if not isinstance(entry, dict) or set(cast(dict[str, object], entry)) != {"distribution", "description"}:
        raise ValueError(f"Bundled image {name} must declare its distribution and description")
    entry = cast(dict[str, object], entry)
    if not all(isinstance(value, str) and value for value in entry.values()):
        raise ValueError(f"Bundled image {name} values must be non-empty strings")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", cast(str, entry["distribution"])):
        raise ValueError(f"Bundled image {name} must name a canonical distribution")
    return entry


def bundled_images(layout: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Validate the interpreter-host images the package declares for a bundled distribution.

    Such an image is not one of Cadrumo's console scripts: it runs only the invocations its
    launch profiles declare, with itself as the interpreter. It lives in the native directory.
    """
    declared = layout.get("bundled_images", {})
    if not isinstance(declared, dict):
        raise ValueError("bundled_images must be a mapping")
    images: dict[str, dict[str, str]] = {}
    for name, entry in cast(dict[str, object], declared).items():
        entry = _validate_bundled_image(name, entry, layout["entrypoints"])
        images[str(name)] = {"distribution": str(entry["distribution"]), "description": str(entry["description"])}
    return images


def bundled_image_files(layout: dict[str, Any]) -> dict[str, str]:
    """Map each bundled-distribution image to its package-relative executable in the native directory."""
    native = layout["paths"]["native"]
    return {name: f"{native}/{name}{layout['entrypoint_suffix']}" for name in bundled_images(layout)}


def distribution_target(layout: dict[str, Any]) -> str:
    """Return the canonical distribution target for a native platform mapping."""
    platform = str(layout["platform"])
    return "windows-x86-64" if platform == "windows-x64" else platform


def entrypoint_files(layout: dict[str, Any]) -> dict[str, str]:
    """Map each declared console entrypoint to its package-relative executable in the native directory."""
    native = layout["paths"]["native"]
    return {name: f"{native}/{name}{layout['entrypoint_suffix']}" for name in layout["entrypoints"]}


def _image_identifiers(entry: dict[str, object]) -> tuple[str, str, str, str]:
    name, placement, target, artifact = entry["name"], entry["placement"], entry["target"], entry["artifact"]
    if not isinstance(name, str) or not _ENTRYPOINT_NAME.fullmatch(name):
        raise ValueError(f"Application image name is not a lowercase hyphenated identifier: {name!r}")
    if not isinstance(target, str) or not _CMAKE_TARGET.fullmatch(target):
        raise ValueError(f"Application image {name} must name a CMake target: {target!r}")
    if not isinstance(artifact, str) or not _CMAKE_VARIABLE.fullmatch(artifact):
        raise ValueError(f"Application image {name} must name the CMake variable holding its artifact: {artifact!r}")
    if placement != _PACKAGE_ROOT:
        raise NotImplementedError(f"Application image {name} placement {placement!r} is not implemented")
    return name, cast(str, placement), target, artifact


def _image_options(name: str, entry: dict[str, object]) -> tuple[dict[str, bool], tuple[str, ...]]:
    flags = {key: entry.get(key, False) for key in ("desktop", "signed", "startup")}
    if not all(isinstance(value, bool) for value in flags.values()):
        raise ValueError(f"Application image {name} flags must be booleans: {flags}")
    arguments = entry["version_arguments"]
    if not isinstance(arguments, list) or not all(
        isinstance(item, str) and item for item in cast(list[object], arguments)
    ):
        raise ValueError(f"Application image {name} version_arguments must be a list of non-empty strings")
    return cast(dict[str, bool], cast(object, flags)), tuple(cast(list[str], arguments))


def _image(entry: object, suffix: str) -> ApplicationImage:
    if (
        not isinstance(entry, dict)
        or not _IMAGE_REQUIRED <= set(cast(dict[str, object], entry)) <= _IMAGE_REQUIRED | _IMAGE_OPTIONAL
    ):
        raise ValueError(
            f"Application image must declare {sorted(_IMAGE_REQUIRED)} and optionally {sorted(_IMAGE_OPTIONAL)}: "
            f"{entry!r}"
        )
    entry = cast(dict[str, object], entry)
    name, placement, target, artifact = _image_identifiers(entry)
    flags, arguments = _image_options(name, entry)
    return ApplicationImage(
        name=name,
        file=f"{name}{suffix}",
        placement=placement,
        target=target,
        artifact=artifact,
        version_arguments=arguments,
        **flags,
    )


def _check_image_collision(
    image: ApplicationImage, entrypoints: set[str], occupied: dict[str, str], images: list[ApplicationImage]
) -> None:
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


def application_images(layout: dict[str, Any]) -> tuple[ApplicationImage, ...]:
    """Validate the platform mapping's application images against every other package-root name."""
    declared = layout.get("application_images", [])
    if not isinstance(declared, list):
        raise ValueError("application_images must be a list")
    # Windows file names compare without case, so every collision check folds case.
    occupied = {
        str(path).split("/")[0].casefold(): str(path) for path in (*layout["paths"].values(), *layout["files"].values())
    }
    entrypoints = set(layout["entrypoints"]) | set(layout.get("bundled_images", {}))
    images: list[ApplicationImage] = []
    for entry in cast(list[object], declared):
        image = _image(entry, layout["entrypoint_suffix"])
        _check_image_collision(image, entrypoints, occupied, images)
        images.append(image)
    if sum(image.desktop for image in images) > 1:
        raise ValueError("At most one application image is the desktop application")
    return tuple(images)


_BUNDLE_FIELDS = frozenset({"executable_directory", "resources", "payload"})
_BUNDLE_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


@dataclass(frozen=True)
class ApplicationBundle:
    """Bundle-relative placements of an application wrapper around the flat package.

    The wrapper's main executable lives in the executable directory; the package lives
    unchanged beneath the resources directory, where non-code files can be sealed.
    """

    executable_directory: str
    resources: str
    payload: str

    @property
    def payload_from_executable(self) -> str:
        """Return the package directory relative to the main executable's directory."""
        return posixpath.relpath(self.payload, self.executable_directory)


def _bundle_path(name: str, value: object) -> str:
    if not isinstance(value, str) or not all(_BUNDLE_SEGMENT.fullmatch(part) for part in value.split("/")):
        raise ValueError(f"application_bundle.{name} must be a relative path of plain segments: {value!r}")
    return value


def application_bundle(layout: dict[str, Any]) -> ApplicationBundle | None:
    """Validate the platform's application wrapper placements, when it declares a wrapper."""
    declared = layout.get("application_bundle")
    if declared is None:
        return None
    if not isinstance(declared, dict) or set(cast(dict[str, object], declared)) != _BUNDLE_FIELDS:
        raise ValueError(f"application_bundle must declare exactly {sorted(_BUNDLE_FIELDS)}")
    entry = cast(dict[str, object], declared)
    bundle = ApplicationBundle(**{name: _bundle_path(name, entry[name]) for name in sorted(_BUNDLE_FIELDS)})
    if not bundle.payload.startswith(bundle.resources + "/"):
        raise ValueError("application_bundle.payload must lie beneath its resources directory")
    if bundle.executable_directory.startswith(bundle.resources + "/") or bundle.resources.startswith(
        bundle.executable_directory + "/"
    ):
        raise ValueError("application_bundle executable and resources directories must be distinct")
    if desktop_image(layout) is None:
        raise ValueError("An application bundle requires the platform's desktop image")
    return bundle


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
