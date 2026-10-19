"""Admit a lane run on a staged package by the build records of what was staged, and the test host by its sources.

Each staged component (the interpreter hosts and entry points, the
background-services manager, the desktop image, the Python product and the
bundled agent) has a build record its build writes when it completes: the
fingerprint of the inputs it was built from, whether those inputs stayed
unchanged throughout (``settled``), and the digest of every artifact it staged.
A run is refused when a record is missing or unsettled, or when the staged
bytes are not the ones it records. Inputs edited after the build do not make
the stage stale for the run; they are reported as newer edits since the
snapshot the results are for. Modification times never decide it, so a rebuild
that leaves an output unchanged leaves it current.

The remote-debugging test host has no build record; it is still refused when it
is older than a source it is built from. Test-only files are built into nothing.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

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


def host_part(record: Path, repository: Path) -> Part:
    """The remote-debugging test host, by the record its build writes last."""
    return Part(
        "test host",
        lambda: [record],
        lambda: checkout_sources(repository, HOST_SOURCES),
        "desktop-packaged-host",
    )


STAGED_COMPONENTS: Mapping[str, str] = {
    "interpreter": "app-native",
    "manager": "app-native",
    "desktop": "app-native",
    "app-payload": "app-payload",
    "app-agent": "app-agent",
}
"""Each component whose staged bytes the lane runs, and the target that rebuilds and records it."""


@dataclass(frozen=True)
class StageVerdict:
    """Why a stage cannot be run, the build each component's bytes come from, and what was edited since."""

    refusals: list[str]
    snapshot: dict[str, str]
    changed: dict[str, list[str]]


def stage_verdict(
    build: Path,
    configuration: str,
    *,
    read_record: Callable[[Path, str], dict[str, Any] | None] | None = None,
    changed_inputs: Callable[[Path, str], list[str]] | None = None,
) -> StageVerdict:
    """Judge the ``configuration`` stage of ``build`` by its components' build records."""
    from ..packaging.native import build_stamp
    from ..packaging.native.hashing import digest, digest_cache

    read = build_stamp.read_record if read_record is None else read_record
    edited = build_stamp.changed_inputs if changed_inputs is None else changed_inputs
    refusals: list[str] = []
    snapshot: dict[str, str] = {}
    changed: dict[str, list[str]] = {}
    with digest_cache(build):
        for component, target in STAGED_COMPONENTS.items():
            rebuild = f"rebuild with: just build-native {configuration} {target}"
            record = read(build, component)
            if record is None:
                refusals.append(f"{component} has no build record; {rebuild}")
                continue
            if record.get("state") != "settled":
                refusals.append(f"{component}'s build is {record.get('state')}, not settled; {rebuild}")
                continue
            staged = (record.get("staged") or {}).get(configuration)
            if not isinstance(staged, Mapping) or not staged.get("artifacts"):
                refusals.append(f"{component} records nothing staged for {configuration}; {rebuild}")
                continue
            package = build / str(staged["package"])
            differing = sorted(
                str(member)
                for member, expected in staged["artifacts"].items()
                if not (package / member).is_file() or digest(package / member) != expected
            )
            if differing:
                refusals.append(
                    f"{component}'s staged bytes are not the ones build {record.get('build_id')} recorded "
                    f"({len(differing)}, first {differing[0]}); {rebuild}"
                )
                continue
            snapshot[component] = str(record.get("build_id"))
            try:
                newer = edited(build, component)
            except FileNotFoundError:
                refusals.append(f"{component}'s build records no inputs; {rebuild}")
                continue
            if newer:
                changed[component] = newer
    return StageVerdict(refusals, snapshot, changed)
