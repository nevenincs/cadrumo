"""Where the generated window projections live: the selected CMake build tree.

A projection is build output and is never committed. It sits in the directory
the build-path registry, ``native/cmake/BuildPaths.cmake``, declares as
``WINDOW_FIXTURES`` below a CMake binary directory. The binary directory is the
one ``CADRUMO_CMAKE_BINARY_DIR`` names, which every CMake action sets, so each
configured preset seeds and reads only its own projections. A command run
outside CMake, such as ``just fixtures-seed``, names none; it then uses the
host's own configure preset, the one visible preset in ``CMakePresets.json``
that inherits from no other and targets this machine. The frontend's readers
always run inside a CMake build and read the same directory through the
build-path manifest.
"""

from __future__ import annotations

import functools
import json
import os
import platform
import re
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Final, cast

from ..packaging.runtime_wheelhouse_contract import target_platform
from ..paths import REPO_ROOT

#: The environment variable naming the selected CMake binary directory.
BINARY_DIRECTORY_VARIABLE: Final[str] = "CADRUMO_CMAKE_BINARY_DIR"
#: The build-path registry's key for the window projections, and its name in ``build-paths.json``.
WINDOW_FIXTURES_KEY: Final[str] = "WINDOW_FIXTURES"
#: Stands for the window projections' directory: as a family's output root and as a command argument.
WINDOW_ROOT: Final[str] = "{window}"
#: Written by a seed that leaves every window family fresh: each family's outputs and their sha256.
#: The frontend's type check reads it to refuse a partial or edited set.
WINDOW_INDEX: Final[str] = ".window-projections.json"
WINDOW_INDEX_FORMAT: Final[str] = "cadrumo-window-projections-v1"

_BUILD_PATHS: Final[Path] = REPO_ROOT / "native" / "cmake" / "BuildPaths.cmake"
_PRESETS: Final[Path] = REPO_ROOT / "CMakePresets.json"
_DIRECTORIES: Final = re.compile(r"set\(CADRUMO_BUILD_DIRECTORIES\s+([^)]*)\)")
_MEMBER: Final = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*(/[a-z0-9]+(-[a-z0-9]+)*)*")


class WindowProjectionsUnavailableError(RuntimeError):
    """No CMake build directory can hold the window projections."""


@functools.cache
def window_member() -> PurePosixPath:
    """The window projections' directory below a binary directory, as the build-path registry declares it.

    Raises:
        WindowProjectionsUnavailableError: When the registry declares no such directory.
    """
    declaration = _DIRECTORIES.search(_BUILD_PATHS.read_text(encoding="utf-8"))
    words = declaration.group(1).split() if declaration else []
    members = dict(zip(words[::2], words[1::2], strict=True)) if len(words) % 2 == 0 else {}
    member = members.get(WINDOW_FIXTURES_KEY)
    if member is None or not _MEMBER.fullmatch(member):
        raise WindowProjectionsUnavailableError(f"{_BUILD_PATHS} declares no {WINDOW_FIXTURES_KEY} build directory")
    return PurePosixPath(member)


def host_preset() -> str:
    """The host's own configure preset: visible, inheriting nothing, and targeting this machine.

    Raises:
        WindowProjectionsUnavailableError: When no preset, or more than one, is the host's own.
    """
    document = json.loads(_PRESETS.read_text(encoding="utf-8"))
    host = (platform.system(), platform.machine())
    matching: list[str] = []
    for preset in cast(list[dict[str, object]], document["configurePresets"]):
        if preset.get("hidden") or "inherits" in preset:
            continue
        variables = cast(Mapping[str, str], preset.get("cacheVariables", {}))
        target = target_platform(variables["CADRUMO_TARGET"])
        if (target.platform_system, target.platform_machine) == host:
            matching.append(cast(str, preset["name"]))
    if len(matching) != 1:
        raise WindowProjectionsUnavailableError(f"No single configure preset is enrolled for host {host}: {matching}")
    return matching[0]


def _same(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.normpath(left)) == os.path.normcase(os.path.normpath(right))


def selected_build(root: Path = REPO_ROOT, environment: Mapping[str, str] | None = None) -> Path:
    """The binary directory the window projections belong to: the named one, else the host preset's.

    Raises:
        WindowProjectionsUnavailableError: When the named directory is not ``build/<preset>`` of ``root``.
    """
    environment = os.environ if environment is None else environment
    named = environment.get(BINARY_DIRECTORY_VARIABLE, "")
    if not named:
        return root / "build" / host_preset()
    build = Path(named)
    if not build.is_absolute() or ".." in build.parts or not _same(build.parent, root / "build"):
        raise WindowProjectionsUnavailableError(
            f"{BINARY_DIRECTORY_VARIABLE} must name an absolute build/<preset> directory of {root}: {named}"
        )
    if build.is_symlink() or build.is_junction():
        raise WindowProjectionsUnavailableError(f"The CMake build directory is linked: {build}")
    return build


def window_projections(root: Path = REPO_ROOT, environment: Mapping[str, str] | None = None) -> Path:
    """The window projections' directory in the selected build tree, spelled from the selected directory."""
    build = selected_build(root, environment)
    target = build
    for part in window_member().parts:
        target /= part
        if target.is_symlink() or target.is_junction():
            raise WindowProjectionsUnavailableError(f"The window projections' directory is linked: {target}")
    return target


def output_directory(output_root: str, root: Path) -> Path:
    """A family's output root below ``root``; the window projections stand in for ``WINDOW_ROOT``."""
    return window_projections(root) if output_root == WINDOW_ROOT else root / output_root


def family_directory(family: str) -> Path:
    """The directory a window family's projections are written into: its own folder in the projection directory."""
    return window_projections() / family
