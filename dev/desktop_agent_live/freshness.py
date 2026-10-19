"""Refuse a lane run on any staged binary or the test host when it is older than its sources.

A run against stale bytes proves nothing about the sources it appears to test.
Each part of the staged package is checked on its own, so the refusal names the
one that is stale and the smallest target that rebuilds it and updates the
package in place:

- the desktop image, from the desktop crate, the crates it names by path, the
  interpreter host sources it compiles and the shell it embeds;
- the background-services manager, from its crate and the crates it names;
- the interpreter hosts and entry points, from their C sources;
- the Python product and the bundled agent, from the inputs CMake declares for
  each in its binary directory, which name the agent's own project files;
- and the remote-debugging test host, from the same sources as the desktop image.

Test-only files are built into none of them, so editing a spec or a unit test
leaves every part current. The documentation is never a source of anything the
lane runs.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from ..packaging.native.layout import entrypoint_files
from ..source_tree import repository_files

#: What the desktop image and the test host are compiled from; it mirrors the
#: members the host's source snapshot takes from ``native``, plus the shell.
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
MANAGER_SOURCES = ("native/manager", "native/application", "native/platform", "native/installer")
INTERPRETER_SOURCES = ("native/interpreter", "native/platform", "native/launch_guard")

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
    """A built part, the newest source it is older than, and the target that rebuilds it."""

    part: str
    artifact: Path
    source: Path
    target: str


def newer_source(artifact: Path, sources: Iterable[Path]) -> Path | None:
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
    return None if newest is None else newest[1]


def checkout_sources(repository: Path, under: Iterable[str]) -> list[Path]:
    """The checkout files below ``under`` that are built into a product."""
    return [repository / relative for relative in repository_files(repository, under=under) if built_from(relative)]


def declared_inputs(build: Path, listing: str, repository: Path) -> list[Path]:
    """The inputs a CMake action declares in ``inputs-<listing>.txt``, test-only files aside."""
    path = build / f"inputs-{listing}.txt"
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    # Another action's output in the binary directory is not a source; its own sources are checked.
    # The repository's build tooling shapes how a part is made, not the bytes it stages.
    outputs = build.resolve()
    tooling = (repository / "dev").resolve()
    return [
        Path(line)
        for line in lines
        if line.strip()
        and built_from(Path(line).as_posix())
        and not Path(line).resolve().is_relative_to(outputs)
        and not Path(line).resolve().is_relative_to(tooling)
    ]


@dataclass(frozen=True)
class Part:
    """One separately built part: where its bytes are, what they come from, what rebuilds them."""

    name: str
    artifacts: Callable[[], list[Path]]
    sources: Callable[[], list[Path]]
    target: str


def stale_parts(parts: Iterable[Part]) -> tuple[list[Staleness], list[str]]:
    """Each part older than one of its sources, and each part with nothing built to check."""
    stale: list[Staleness] = []
    missing: list[str] = []
    for part in parts:
        artifacts = [artifact for artifact in part.artifacts() if artifact.is_file()]
        if not artifacts:
            missing.append(part.name)
            continue
        oldest = min(artifacts, key=lambda artifact: artifact.stat().st_mtime_ns)
        source = newer_source(oldest, part.sources())
        if source is not None:
            stale.append(Staleness(part.name, oldest, source, part.target))
    return stale, missing


def package_parts(package: Path, layout: dict[str, Any], build: Path, repository: Path) -> list[Part]:
    """The separately built parts of a staged package and the in-place targets that refresh them."""
    packages = package / layout["paths"]["packages"]
    images = [
        package / layout["paths"]["executable"],
        *(package / image for image in entrypoint_files(layout).values()),
    ]
    return [
        Part(
            "desktop image",
            lambda: [package / "cadrumo.exe"],
            lambda: checkout_sources(repository, HOST_SOURCES),
            "app-native",
        ),
        Part(
            "background-services manager",
            lambda: [package / "cadrumo-manager.exe"],
            lambda: checkout_sources(repository, MANAGER_SOURCES),
            "app-native",
        ),
        Part(
            "interpreter hosts and entry points",
            lambda: images,
            lambda: checkout_sources(repository, INTERPRETER_SOURCES),
            "app-native",
        ),
        Part(
            "Python product",
            lambda: sorted(packages.glob("cadrumo-*.dist-info/RECORD")),
            lambda: declared_inputs(build, "product", repository),
            "app-payload",
        ),
        Part(
            "bundled agent",
            lambda: sorted(packages.glob("cadrumo_agent-*.dist-info/RECORD")),
            lambda: declared_inputs(build, "agent", repository),
            "app-agent",
        ),
    ]


def host_part(record: Path, repository: Path) -> Part:
    """The remote-debugging test host, by the record its build writes last."""
    return Part(
        "test host",
        lambda: [record],
        lambda: checkout_sources(repository, HOST_SOURCES),
        "desktop-packaged-host",
    )
