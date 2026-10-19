"""Refuse a lane run on a staged package or test host older than what it is built from.

A run against stale bytes proves nothing about the sources it appears to test.
The staged package is built from the inputs CMake declares for it, which name
the bundled agent's own project files too, and lists in its binary directory;
the test host is built from the desktop crate, the crates it names by path,
the interpreter host sources it compiles, and the shell it embeds. Test-only
files are not built into either, so editing a spec or a unit test leaves both
current.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from ..source_tree import repository_files

#: What the test host build copies and compiles, relative to the checkout; it
#: mirrors the members the host's source snapshot takes from ``native``.
HOST_SOURCES = (
    "native/desktop/src-tauri/Cargo.toml",
    "native/desktop/src-tauri/Cargo.lock",
    "native/desktop/src-tauri/build.rs",
    "native/desktop/src-tauri/src",
    "native/desktop/src-tauri/tauri.conf.json.in",
    "native/application",
    "native/platform",
    "native/installer",
    "native/manager",
    "native/launch_guard",
    "native/interpreter_host",
    "native/interpreter/windows/host.manifest",
    "native/interpreter/windows/host.c",
    "native/interpreter/launch_guard.h",
    "native/interpreter/launch_profile.h",
    "native/desktop/frontend",
)

_TEST_DIRECTORIES = frozenset({"tests", "testing", "__tests__"})


def built_from(relative: str) -> bool:
    """Whether a source path is built into its product, rather than only testing it."""
    path = PurePosixPath(relative)
    name = path.name
    return not (
        _TEST_DIRECTORIES.intersection(path.parts[:-1])
        or name in {"tests.rs", "conftest.py"}
        or name.endswith(("_tests.rs", ".stories.tsx", ".stories.ts"))
        or ".test." in name
        or ".spec." in name
        or name.startswith("test_")
    )


@dataclass(frozen=True)
class Staleness:
    """The newest source an artifact is older than."""

    artifact: Path
    source: Path


def newer_source(artifact: Path, sources: Iterable[Path]) -> Staleness | None:
    """The newest of ``sources`` changed after ``artifact`` was written, if any."""
    built = artifact.stat().st_mtime_ns
    newest: tuple[int, Path] | None = None
    for source in sources:
        try:
            changed = source.stat().st_mtime_ns
        except FileNotFoundError:
            continue
        if changed > built and (newest is None or changed > newest[0]):
            newest = (changed, source)
    return None if newest is None else Staleness(artifact, newest[1])


def host_sources(repository: Path) -> list[Path]:
    """The checkout files the test host is built from."""
    return [
        repository / relative for relative in repository_files(repository, under=HOST_SOURCES) if built_from(relative)
    ]


def package_sources(build: Path) -> list[Path]:
    """The inputs CMake declares for the staged package, the bundled agent's included."""
    sources: list[Path] = []
    for listing in sorted(build.glob("inputs-*.txt")):
        for line in listing.read_text(encoding="utf-8").splitlines():
            if line.strip() and built_from(Path(line).as_posix()):
                sources.append(Path(line))
    return sources
