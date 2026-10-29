"""Admit a lane run by the build records of everything it runs.

Each component the lane runs (the interpreter hosts and entry points, the
background-services manager, the desktop image, the Python product, the
bundled agent and the remote-debugging test host) has a build record its build
writes when it completes: the fingerprint of the inputs it was built from,
whether those inputs stayed unchanged throughout (``settled``), and the digest
of every artifact it staged. A run is refused when a record is missing or
unsettled, or when the bytes are not the ones it records. Inputs edited after
the build do not make it stale for the run; they are reported as newer edits
since the snapshot the results are for. Modification times never decide it, so
a rebuild that leaves an output unchanged leaves it current.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STAGED_COMPONENTS: Mapping[str, str] = {
    "interpreter": "app-native",
    "manager": "app-native",
    "desktop": "app-native",
    "app-payload": "app-payload",
    "app-agent": "app-agent",
    "desktop-test-host": "desktop-packaged-host",
}
"""Each component whose bytes the lane runs, and the target that rebuilds and records it.

The test host is the desktop image the lane runs in place of the staged one;
its record stages it under the testing directory rather than the package.
"""


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
            differing = _differing_artifacts(package, staged["artifacts"], digest)
            if differing:
                refusals.append(
                    f"{component}'s staged bytes are not the ones build {record.get('build_id')} recorded "
                    f"({len(differing)}, first {differing[0]}); {rebuild}"
                )
                continue
            snapshot[component] = str(record.get("build_id"))
            _record_changed_inputs(build, component, rebuild, edited, changed, refusals)
    return StageVerdict(refusals, snapshot, changed)


def _differing_artifacts(package: Path, artifacts: Mapping[str, str], digest: Callable[[Path], str]) -> list[str]:
    """Compare every recorded staged member while the caller owns its digest-cache scope."""
    return sorted(
        str(member)
        for member, expected in artifacts.items()
        if not (package / member).is_file() or digest(package / member) != expected
    )


def _record_changed_inputs(
    build: Path,
    component: str,
    rebuild: str,
    edited: Callable[[Path, str], list[str]],
    changed: dict[str, list[str]],
    refusals: list[str],
) -> None:
    """Retain post-snapshot edits and refuse missing input records without discarding the snapshot."""
    try:
        newer = edited(build, component)
    except FileNotFoundError:
        refusals.append(f"{component}'s build records no inputs; {rebuild}")
        return
    if newer:
        changed[component] = newer
