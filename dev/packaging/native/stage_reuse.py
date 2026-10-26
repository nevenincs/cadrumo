"""Decide from a build record whether a payload stage may skip its work.

A stage skips only when all of these hold:

- its current input fingerprint, computed through the shared digest cache, equals the
  fingerprint its build record names;
- the record is ``settled``: its inputs held still from the start to the end of that build;
- every artifact the record says it staged still has the recorded SHA-256 on disk.

Each check reads only file metadata for files whose digest the cache already holds, so
an unchanged stage is decided without reading its outputs back. Any failed check names
its reason, and the caller falls back to its full verification or rebuild.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from .build_stamp import SETTLED, read_record, record_path
from .hashing import digest


def staged_mismatch(build: Path, record: Mapping[str, Any]) -> str | None:
    """Name the first staged artifact of a record that is missing or changed, or ``None``."""
    root = build.resolve()
    for configuration, entry in sorted(record["staged"].items()):
        package = entry.get("package")
        if not isinstance(package, str):
            return f"the {configuration} staging names no package"
        directory = (root / package).resolve()
        if not directory.is_relative_to(root):
            return f"the {configuration} package {package} lies outside the build directory"
        for member, expected in sorted(entry["artifacts"].items()):
            relative = PurePosixPath(member)
            if relative.is_absolute() or ".." in relative.parts:
                return f"staged artifact {member} escapes its package"
            path = directory / relative
            if not path.is_file():
                return f"staged artifact {package}/{member} is missing"
            if digest(path) != expected:
                return f"staged artifact {package}/{member} changed"
    return None


def record_reuse(build: Path, component: str, fingerprint: str) -> str | None:
    """Say why ``component``'s recorded build cannot stand for ``fingerprint``, or ``None`` when it can."""
    record = read_record(build, component)
    if record is None:
        return f"no {component} build record"
    if record["fingerprint"] != fingerprint:
        return f"the inputs differ from the recorded {component} build"
    if record["state"] != SETTLED:
        return f"the recorded {component} build is {record['state']}"
    return staged_mismatch(build, record)


def package_records(build: Path, package: Path) -> Iterator[tuple[str, Mapping[str, Any], str]]:
    """Yield ``(component, record, configuration)`` for every record that staged into ``package``."""
    directory = record_path(build, "component").parent
    if not directory.is_dir():
        return
    root = build.resolve()
    target = package.resolve()
    for path in sorted(directory.glob("*.json")):
        if path.name.endswith(".inputs.json"):
            continue
        record = read_record(build, path.stem)
        if record is None:
            continue
        for configuration, entry in sorted(record["staged"].items()):
            named = entry.get("package")
            if isinstance(named, str) and (root / named).resolve() == target:
                yield path.stem, record, configuration


def package_mismatch(build: Path, package: Path) -> str | None:
    """Name a record staged into ``package`` that is unsettled or no longer matches it, or ``None``.

    Returns a reason as well when no record names the package: nothing then vouches for it.
    """
    found = False
    for component, record, configuration in package_records(build, package):
        found = True
        if record["state"] != SETTLED:
            return f"the recorded {component} build is {record['state']}"
        reason = staged_mismatch(build, {"staged": {configuration: record["staged"][configuration]}})
        if reason is not None:
            return reason
    return None if found else f"no build record names {package}"


def walk_files(directory: Path) -> Iterator[Path]:
    """Yield every file below ``directory``, following links as path resolution does."""
    for current, directories, files in os.walk(directory, followlinks=True):
        directories.sort()
        for name in sorted(files):
            yield Path(current) / name
