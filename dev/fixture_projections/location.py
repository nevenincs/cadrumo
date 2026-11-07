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

A window producer's scratch follows the same selection: under CMake it is the
selected build's own ``TEMPORARY`` directory, so a build writes nothing outside
its tree; outside CMake it is the checkout's ``.tmp``. A profile a producer
opens in its scratch may have configured the process's diagnostic log file
there, and that file's handler would recreate the directory with its next
record, so a scratch tree detaches it before the tree is removed.
"""

from __future__ import annotations

import functools
import json
import logging
import os
import platform
import re
import tempfile
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Final, cast

from ..packaging.runtime_wheelhouse_contract import target_platform
from ..paths import REPO_ROOT, TEMP_ROOT
from ..temporary_output import prepare_temp_root

#: The environment variable naming the selected CMake binary directory.
BINARY_DIRECTORY_VARIABLE: Final[str] = "CADRUMO_CMAKE_BINARY_DIR"
#: The build-path registry's key for the window projections, and its name in ``build-paths.json``.
WINDOW_FIXTURES_KEY: Final[str] = "WINDOW_FIXTURES"
#: The build-path registry's key for a build's own temporary directory, where its producers write scratch.
TEMPORARY_KEY: Final[str] = "TEMPORARY"
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
def _declared_member(key: str) -> PurePosixPath:
    """The directory below a binary directory that the build-path registry declares under ``key``.

    Raises:
        WindowProjectionsUnavailableError: When the registry declares no such directory.
    """
    declaration = _DIRECTORIES.search(_BUILD_PATHS.read_text(encoding="utf-8"))
    words = declaration.group(1).split() if declaration else []
    members = dict(zip(words[::2], words[1::2], strict=True)) if len(words) % 2 == 0 else {}
    member = members.get(key)
    if member is None or not _MEMBER.fullmatch(member):
        raise WindowProjectionsUnavailableError(f"{_BUILD_PATHS} declares no {key} build directory")
    return PurePosixPath(member)


def window_member() -> PurePosixPath:
    """The window projections' directory below a binary directory, as the build-path registry declares it.

    Raises:
        WindowProjectionsUnavailableError: When the registry declares no such directory.
    """
    return _declared_member(WINDOW_FIXTURES_KEY)


def temporary_member() -> PurePosixPath:
    """A build's own temporary directory below its binary directory, as the build-path registry declares it.

    Raises:
        WindowProjectionsUnavailableError: When the registry declares no such directory.
    """
    return _declared_member(TEMPORARY_KEY)


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


def scratch_directory(root: Path = REPO_ROOT, environment: Mapping[str, str] | None = None) -> Path:
    """Where a window producer writes scratch: the named build's temporary directory, else the checkout's ``.tmp``.

    Raises:
        WindowProjectionsUnavailableError: When the named directory is not ``build/<preset>`` of ``root``.
    """
    environment = os.environ if environment is None else environment
    if not environment.get(BINARY_DIRECTORY_VARIABLE, ""):
        return root / TEMP_ROOT.relative_to(REPO_ROOT)
    return selected_build(root, environment).joinpath(*temporary_member().parts)


def producer_scratch(root: Path = REPO_ROOT, environment: Mapping[str, str] | None = None) -> Path:
    """Prepare and return the window producer scratch root, admitted as ``prepare_temp_root`` admits it.

    Raises:
        WindowProjectionsUnavailableError: When the named directory is not ``build/<preset>`` of the checkout.
        ValueError: When the build's temporary directory is not a declared member of its build-path manifest.
    """
    return prepare_temp_root(override=scratch_directory(root, environment))


def _detach_diagnostic_files(directory: Path) -> None:
    """Deliver every pending diagnostic record, then detach and close each diagnostic log file inside ``directory``.

    Raises:
        OSError: When the pending records cannot be delivered, since the files may still be written.
    """
    from cadrumo.core.logging import AsyncDiagnosticHandler, flush_logging

    if not flush_logging(timeout=30.0):
        raise OSError(f"the diagnostic records were not delivered before {directory} was removed")
    inside = Path(os.path.normcase(directory))
    root = logging.getLogger()
    for handler in tuple(root.handlers):
        if not isinstance(handler, AsyncDiagnosticHandler):
            continue
        sink = handler.sink
        if isinstance(sink, logging.FileHandler) and Path(os.path.normcase(sink.baseFilename)).is_relative_to(inside):
            root.removeHandler(handler)
            handler.close()
            sink.close()


@contextmanager
def scratch_tree(root: Path = REPO_ROOT, environment: Mapping[str, str] | None = None) -> Generator[Path]:
    """A fresh directory in the producer scratch root, removed on exit, every failure to remove it raised.

    A diagnostic log file inside it is detached first: its handler would otherwise write, and so recreate the
    directory, with the next record. Records after that reach the remaining sinks only.
    """
    scratch = tempfile.TemporaryDirectory(dir=producer_scratch(root, environment))
    directory = Path(scratch.name)
    try:
        yield directory
    finally:
        _detach_diagnostic_files(directory)
        scratch.cleanup()


def output_directory(output_root: str, root: Path) -> Path:
    """A family's output root below ``root``; the window projections stand in for ``WINDOW_ROOT``."""
    return window_projections(root) if output_root == WINDOW_ROOT else root / output_root


def family_directory(family: str) -> Path:
    """The directory a window family's projections are written into: its own folder in the projection directory."""
    return window_projections() / family
