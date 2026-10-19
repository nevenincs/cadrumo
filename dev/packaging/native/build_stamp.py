"""Give each native component and each staged package a build identity that moves only on real change.

A build identity is a ``YYYYMMDD`` UTC day with a per-day iteration (``build_id``), a
sequence that orders every identity of the build directory (``build_sequence``, the
16-bit Windows FILEVERSION fourth field) and the ISO UTC time it was allocated.

Identities are keyed by content. The interpreter hosts, the manager, the installer and
the desktop each have a fingerprint of the inputs compiled into them
(:mod:`.build_fingerprint`); a staged package has a fingerprint of its staged files and
of its components' fingerprints. The registry beside the generated contract maps each
recent fingerprint to the identity first allocated for it, so an unchanged component
keeps its identity, its generated identity file keeps its bytes and timestamp, and
nothing that embeds it rebuilds. Two builds that resolve the same fingerprint at once
(parallel ``cmake --build`` processes, MSBuild nodes, Debug and Release together)
serialize on the registry lock and receive one identity.

Explicit cache values freeze the id, the sequence or the date of every component and
package of the build directory for release callers.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import threading
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dev._paths import REPO_ROOT

from .action_cache import action_lock
from .build_directory import require_enrolled_build
from .build_fingerprint import COMPONENTS, current_fingerprints, inventory, inventory_fingerprint, resolution_order
from .build_log import BuildLog
from .build_paths import build_paths
from .hashing import digest
from .stable_output import write_text

STAMP_NAME = "build-stamp.json"
"""The registry of allocated identities and the directory's counters."""
FREEZE_NAME = "build-freeze.json"
"""The explicit cache values CMake configured, written by Contract.cmake."""
IDENTITY_DIRECTORY = "component-identity"
"""One ``<component>.json`` per resolved component, rewritten only when its identity changes.

The compile steps read these; they never change while a component's inputs stay the same."""
RECORD_DIRECTORY = "build-identity"
"""One ``<component>.json`` build record per component for readers outside the build, with
its ``<component>.inputs.json`` inventory; see :func:`read_record` and :func:`changed_inputs`."""
RECORD_SCHEMA = 1
BUILDING, SETTLED, UNSETTLED = "building", "settled", "unsettled"
"""Record states: a build of the fingerprint is under way; it completed from inputs that held
still from start to end; or its inputs moved while it ran, so its outputs prove nothing."""
ACTION_COMPONENTS = {"product": "app-payload", "agent": "app-agent"}
"""The Python payload producers, recorded beside the native components."""
PACKAGE = "package"
IMAGE_VARIABLE = "CADRUMO_IMAGE_COMPONENT"
"""Names the component whose images a compiler or Cargo command is building."""
SEQUENCE_LIMIT = 65535
"""The Windows FILEVERSION fourth field is 16 bits wide."""
HISTORY = 64
"""Fingerprints remembered per component; switching back to an older one reuses its identity."""
BUILD_TYPES = {"Debug": "debug", "Release": "release"}
_SCHEMA = 2
_BUILD_ID = re.compile(r"[0-9]{8}[0-9]{2,}")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
_FINGERPRINT = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class BuildStamp:
    """One allocated identity."""

    build_id: str
    build_sequence: int
    build_date: str

    def environment(self, component: str) -> dict[str, str]:
        """Project the identity into the variables only that component's compilers and build scripts read."""
        prefix = f"CADRUMO_{component.upper()}"
        return {
            f"{prefix}_BUILD_ID": self.build_id,
            f"{prefix}_BUILD_SEQUENCE": str(self.build_sequence),
            f"{prefix}_BUILD_DATE": self.build_date,
        }


@dataclass(frozen=True)
class Freeze:
    """Explicit release values; ``None`` lets the registry allocate that part."""

    number: int | None = None
    build_id: str | None = None
    date: str | None = None

    def __post_init__(self) -> None:
        """Refuse values CMake would also refuse at configure time."""
        if self.number is not None and not 1 <= self.number <= SEQUENCE_LIMIT:
            raise ValueError(f"CADRUMO_BUILD_NUMBER must be between 1 and {SEQUENCE_LIMIT}: {self.number}")
        if self.build_id is not None and not _BUILD_ID.fullmatch(self.build_id):
            raise ValueError(f"CADRUMO_BUILD_ID must be YYYYMMDD and a two-or-more-digit iteration: {self.build_id!r}")
        if self.date is not None and not _DATE.fullmatch(self.date):
            raise ValueError(f"CADRUMO_BUILD_DATE must be an ISO UTC timestamp: {self.date!r}")

    def apply(self, stamp: BuildStamp) -> BuildStamp:
        """Replace the allocated parts this freeze fixes."""
        return BuildStamp(
            self.build_id if self.build_id is not None else stamp.build_id,
            self.number if self.number is not None else stamp.build_sequence,
            self.date if self.date is not None else stamp.build_date,
        )


@dataclass(frozen=True)
class ComponentIdentity:
    """The identity one component's images embed, with the fingerprint it was resolved from."""

    component: str
    fingerprint: str
    version: str
    stamp: BuildStamp

    def document(self) -> dict[str, object]:
        """Return the published ``component-identity/<component>.json`` document."""
        return {
            "component": self.component,
            "fingerprint": self.fingerprint,
            "version": self.version,
            "build_id": self.stamp.build_id,
            "build_sequence": self.stamp.build_sequence,
            "build_date": self.stamp.build_date,
        }


def build_type(configuration: str) -> str:
    """Map a CMake configuration to the build type every image reports."""
    try:
        return BUILD_TYPES[configuration]
    except KeyError:
        raise ValueError(f"No build type for CMake configuration {configuration!r}; use Debug or Release") from None


def display_version(version: str, build_id: str, kind: str) -> str:
    """Return ``{version}+{build_id}``, with a ``.debug`` suffix for debug builds."""
    if kind not in BUILD_TYPES.values():
        raise ValueError(f"Unknown build type: {kind!r}")
    return f"{version}+{build_id}" + (".debug" if kind == "debug" else "")


def _validate(stamp: BuildStamp) -> BuildStamp:
    if not isinstance(stamp.build_id, str) or not _BUILD_ID.fullmatch(stamp.build_id):
        raise ValueError(f"Build id must be YYYYMMDD and a two-or-more-digit iteration: {stamp.build_id!r}")
    if type(stamp.build_sequence) is not int or not 1 <= stamp.build_sequence <= SEQUENCE_LIMIT:
        raise ValueError(f"Build sequence must be between 1 and {SEQUENCE_LIMIT}: {stamp.build_sequence!r}")
    if not isinstance(stamp.build_date, str) or not _DATE.fullmatch(stamp.build_date):
        raise ValueError(f"Build date must be an ISO UTC timestamp: {stamp.build_date!r}")
    return stamp


def _build_date(explicit: str | None, now: datetime | None) -> str:
    if explicit is not None:
        return explicit
    epoch = os.environ.get("SOURCE_DATE_EPOCH", "").strip()
    if epoch != "":
        return datetime.fromtimestamp(int(epoch), UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    moment = now if now is not None else datetime.now(UTC)
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class _Registry:
    day: str
    iteration: int
    sequence: int
    identities: dict[str, list[dict[str, str | int]]]

    def document(self) -> str:
        return (
            json.dumps(
                {
                    "schema": _SCHEMA,
                    "day": self.day,
                    "iteration": self.iteration,
                    "sequence": self.sequence,
                    "identities": self.identities,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )


def _read_registry(path: Path) -> _Registry:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _Registry("", 0, 0, {})
    schema = state.get("schema") if isinstance(state, dict) else None
    if schema == 1:
        # A per-invocation counter: keep its day, iteration and sequence so numbers never repeat.
        return _Registry(str(state.get("day", "")), int(state.get("iteration", 0)), int(state.get("sequence", 0)), {})
    identities = state.get("identities") if isinstance(state, dict) else None
    if schema != _SCHEMA or not isinstance(identities, dict):
        raise ValueError(f"Unreadable build identity registry {path}; remove it to restart this directory's sequence")
    return _Registry(str(state["day"]), int(state["iteration"]), int(state["sequence"]), identities)


def _stamp(entry: dict[str, str | int]) -> BuildStamp:
    return _validate(BuildStamp(str(entry["build_id"]), int(entry["build_sequence"]), str(entry["build_date"])))


def allocate(
    directory: Path, key: str, content: str, *, freeze: Freeze | None = None, now: datetime | None = None
) -> BuildStamp:
    """Return the identity of ``content`` for ``key``, allocating the next one only for unseen content.

    The lookup and the allocation happen under one lock, so concurrent callers with the same
    fingerprint share one identity. A new identity takes the next iteration of its UTC day
    (restarting at 1 each day and growing past 99 without truncation) and the next sequence,
    which never restarts and refuses to pass the Windows FILEVERSION limit instead of wrapping.
    """
    if not _FINGERPRINT.fullmatch(content):
        raise ValueError(f"A build identity is keyed by a SHA-256 fingerprint: {content!r}")
    freeze = freeze if freeze is not None else Freeze()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / STAMP_NAME
    with action_lock(directory, "build-stamp"):
        registry = _read_registry(path)
        history = registry.identities.setdefault(key, [])
        recorded = next((entry for entry in history if entry["fingerprint"] == content), None)
        if recorded is None:
            built = _build_date(freeze.date, now)
            day = built[:10].replace("-", "")
            iteration = registry.iteration + 1 if registry.day == day else 1
            sequence = registry.sequence + 1
            if sequence > SEQUENCE_LIMIT:
                if freeze.number is None:
                    raise ValueError(
                        f"The build sequence of {directory} reached {SEQUENCE_LIMIT}, the Windows FILEVERSION limit; "
                        "configure with -DCADRUMO_BUILD_NUMBER=<n> or build in a new binary directory"
                    )
                sequence = SEQUENCE_LIMIT
            registry.day, registry.iteration, registry.sequence = day, iteration, sequence
            recorded = {
                "fingerprint": content,
                "build_id": f"{day}{iteration:02d}",
                "build_sequence": sequence,
                "build_date": built,
            }
        else:
            history.remove(recorded)
        # Most recently used last; the oldest fingerprints fall out of the history.
        history.append(recorded)
        del history[:-HISTORY]
        stamp = _stamp(recorded)
        document = registry.document()
        if not path.is_file() or path.read_text(encoding="utf-8") != document:
            # Readers outside the lock see either the previous registry or this one, never a partial file.
            staging = directory / f".{STAMP_NAME}.{os.getpid()}.{threading.get_ident()}.tmp"
            staging.write_text(document, encoding="utf-8")
            os.replace(staging, path)
    return _validate(freeze.apply(stamp))


def package_identity(build: Path, content: str) -> BuildStamp:
    """Return the identity of a staged package whose staged content has this fingerprint."""
    return allocate(build_paths(build)["generated"], PACKAGE, content, freeze=read_freeze(build))


def read_freeze(build: Path) -> Freeze:
    """Read the explicit values CMake configured for this build directory."""
    path = build_paths(build)["generated"] / FREEZE_NAME
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(f"No {FREEZE_NAME} in {path.parent}; reconfigure the CMake build directory") from None
    return Freeze(
        int(document["number"]) if document.get("number") else None,
        document.get("id") or None,
        document.get("date") or None,
    )


def identity_path(build: Path, component: str) -> Path:
    """Locate the generated identity file of one component."""
    return build_paths(build)["generated"] / IDENTITY_DIRECTORY / f"{component}.json"


def _version(build: Path) -> str:
    version = json.loads((build_paths(build)["generated"] / "identity.json").read_text(encoding="utf-8"))["version"]
    if not isinstance(version, str) or not version:
        raise ValueError("The configured product identity has no version; reconfigure CMake")
    return version


def resolve(
    build: Path, components: Iterable[str], *, now: datetime | None = None, root: Path = REPO_ROOT
) -> dict[str, ComponentIdentity]:
    """Fingerprint the requested components and those they embed, and publish their identities.

    Each ``component-identity/<component>.json`` changes bytes only when the identity does,
    so an unchanged component never invalidates what reads or embeds it. A changed
    fingerprint also opens the component's build record.
    """
    generated = build_paths(build)["generated"]
    freeze = read_freeze(build)
    version = _version(build)
    fingerprints: dict[str, str] = {}
    resolved: dict[str, ComponentIdentity] = {}
    for name in resolution_order(tuple(components)):
        entries = inventory(name, build, fingerprints, root=root)
        fingerprints[name] = inventory_fingerprint(entries)
        stamp = allocate(generated, name, fingerprints[name], freeze=freeze, now=now)
        identity = ComponentIdentity(name, fingerprints[name], version, stamp)
        path = identity_path(build, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text(path, json.dumps(identity.document(), indent=2) + "\n")
        begin_record(build, identity, entries)
        resolved[name] = identity
    return resolved


def action_identity(build: Path, action: str, content: str, *, now: datetime | None = None) -> ComponentIdentity:
    """Allocate the identity of a Python payload producer's admitted inputs."""
    name = ACTION_COMPONENTS[action]
    stamp = allocate(build_paths(build)["generated"], name, content, freeze=read_freeze(build), now=now)
    return ComponentIdentity(name, content, _version(build), stamp)


def record_path(build: Path, component: str) -> Path:
    """Locate the build record of one component."""
    return build_paths(build)["generated"] / RECORD_DIRECTORY / f"{component}.json"


def inputs_path(build: Path, component: str) -> Path:
    """Locate the input inventory the build record of one component names."""
    return build_paths(build)["generated"] / RECORD_DIRECTORY / f"{component}.inputs.json"


def _publish(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return
    # Readers see the previous record or this one, never a partial file.
    staging = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    staging.write_text(content, encoding="utf-8")
    os.replace(staging, path)


def read_record(build: Path, component: str) -> dict[str, Any] | None:
    """Return the build record of one component, or ``None`` when none was written.

    A record has ``schema`` 1, the ``component`` name, its ``state`` (``building``,
    ``settled`` or ``unsettled``), the ``fingerprint`` of the inputs it was built from, the
    ``version``, ``build_id``, ``build_sequence`` and ``build_date`` of that identity, the
    ``inputs`` inventory file name beside it, and under ``staged`` each configuration's
    ``package`` directory (relative to the binary directory) with the SHA-256 of every
    artifact it staged, keyed by package-relative path.

    Anything else at that path (an identity file from before the records existed, an
    unfinished or partial write, another schema) reads as no record: the next resolution of
    the component regenerates it from the fingerprint, so a reader never fails on it.
    """
    try:
        document = json.loads(record_path(build, component).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return None
    return document if _is_record(document, component) else None


def _is_record(document: object, component: str) -> bool:
    if not isinstance(document, dict) or document.get("schema") != RECORD_SCHEMA:
        return False
    staged = document.get("staged")
    return bool(
        document.get("component") == component
        and document.get("state") in (BUILDING, SETTLED, UNSETTLED)
        and isinstance(document.get("fingerprint"), str)
        and _FINGERPRINT.fullmatch(document["fingerprint"]) is not None
        and isinstance(document.get("inputs"), str)
        and isinstance(staged, dict)
        and all(isinstance(entry, dict) and isinstance(entry.get("artifacts"), dict) for entry in staged.values())
    )


def begin_record(build: Path, identity: ComponentIdentity, files: Mapping[str, str]) -> None:
    """Open the record of a build of this identity, keeping a record that already names it."""
    current = read_record(build, identity.component)
    if current is not None and current["fingerprint"] == identity.fingerprint and current["state"] != UNSETTLED:
        return
    _publish(
        inputs_path(build, identity.component),
        {
            "schema": RECORD_SCHEMA,
            "component": identity.component,
            "fingerprint": identity.fingerprint,
            "files": dict(sorted(files.items())),
        },
    )
    _publish(
        record_path(build, identity.component),
        {
            "schema": RECORD_SCHEMA,
            **identity.document(),
            "state": BUILDING,
            "inputs": inputs_path(build, identity.component).name,
            "staged": {},
        },
    )


def settle_record(
    build: Path,
    component: str,
    *,
    settled: bool,
    configuration: str | None = None,
    package: str | None = None,
    artifacts: Mapping[str, str] | None = None,
) -> bool:
    """Close a component's record: settled only if its inputs held still, plus what one configuration staged.

    Without a record (its component was never resolved here) there is nothing to close; the
    next resolution opens one. Returns whether a record was closed.
    """
    record = read_record(build, component)
    if record is None:
        return False
    record["state"] = SETTLED if settled and record["state"] != UNSETTLED else UNSETTLED
    if configuration is not None:
        record["staged"][configuration] = {"package": package, "artifacts": dict(sorted((artifacts or {}).items()))}
    _publish(record_path(build, component), record)
    return True


def native_settled(build: Path, components: Iterable[str], *, root: Path = REPO_ROOT) -> dict[str, bool]:
    """Say, per native component, whether its inputs still give the fingerprint it was compiled from."""
    names = list(components)
    current = current_fingerprints(build, names, root=root)
    result: dict[str, bool] = {}
    for name in names:
        record = read_record(build, name)
        path = identity_path(build, name)
        compiled = load_identity(path, name).fingerprint if path.is_file() else None
        result[name] = record is not None and record["fingerprint"] == compiled == current[name]
    return result


def read_inputs(build: Path, component: str) -> dict[str, str] | None:
    """Return the ``{key: sha256}`` input inventory of a component's recorded build, or ``None``.

    The inventory belongs to the record's ``fingerprint``; ``None`` means there is no
    record, no inventory, or one of another fingerprint (a build of new inputs has begun).
    Keys are repository-relative paths for native components, absolute POSIX paths for
    ``app-payload`` and ``app-agent``, and ``@``-prefixed names for inputs that are not files.
    """
    record = read_record(build, component)
    try:
        document = json.loads(inputs_path(build, component).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return None
    if (
        record is None
        or not isinstance(document, dict)
        or document.get("schema") != RECORD_SCHEMA
        or document.get("fingerprint") != record["fingerprint"]
        or not isinstance(document.get("files"), dict)
    ):
        return None
    return {str(key): str(value) for key, value in document["files"].items()}


def changed_inputs(build: Path, component: str, *, root: Path = REPO_ROOT) -> list[str]:
    """Name every input of the recorded build of ``component`` whose content differs now.

    Native components recompute their whole inventory; the Python payload producers
    re-hash the files their inventory lists. An empty list means the recorded build
    still describes the inputs.
    """
    recorded = read_inputs(build, component)
    if recorded is None:
        raise FileNotFoundError(f"No recorded build of {component} in {build}; build it first")
    if component in COMPONENTS:
        order = resolution_order([component])
        embedded = current_fingerprints(build, order[:-1], root=root)
        current = inventory(component, build, embedded, root=root)
    else:
        current = {
            key: value if key.startswith("@") else digest(Path(key)) if Path(key).is_file() else "missing"
            for key, value in recorded.items()
        }
    return sorted(key for key in {*recorded, *current} if recorded.get(key) != current.get(key))


def load_identity(path: Path, component: str | None = None) -> ComponentIdentity:
    """Read a published component identity file, refusing a missing or malformed one with the remedy."""
    name = component if component is not None else path.stem
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(
            f"No build identity for the {name} component at {path}; build the targets that compile it "
            "(each resolves its component's identity first)"
        ) from None
    if document.get("component") != name or not _FINGERPRINT.fullmatch(str(document.get("fingerprint"))):
        raise ValueError(f"Malformed build identity {path}; rebuild the {name} component")
    stamp = _validate(BuildStamp(document["build_id"], document["build_sequence"], document["build_date"]))
    return ComponentIdentity(name, document["fingerprint"], document["version"], stamp)


def read_identity(build: Path, component: str) -> ComponentIdentity:
    """Read the published identity of one component of a build directory."""
    return load_identity(identity_path(build, component), component)


def image_environment(identity: ComponentIdentity) -> dict[str, str]:
    """Project one component's identity for the build of that component's own images.

    ``CADRUMO_IMAGE_COMPONENT`` names the image being built; a crate linked into it as a
    library sees another name and consumes no identity of its own.
    """
    return {IMAGE_VARIABLE: identity.component, **identity.stamp.environment(identity.component)}


def settle_test_host(build: Path, host_record: Path) -> None:
    """Close the remote-debugging test host's record from the host record its build wrote."""
    host = json.loads(host_record.read_text(encoding="utf-8"))
    executable = Path(host["executable"]).resolve()
    root = build.resolve()
    if not executable.is_relative_to(root) or digest(executable) != host["sha256"]:
        raise ValueError(f"The test host record {host_record} names an image this build did not produce")
    settled = native_settled(build, ["desktop-test-host"])["desktop-test-host"]
    settle_record(
        build,
        "desktop-test-host",
        settled=settled,
        configuration=str(host["configuration"]),
        package=host_record.parent.resolve().relative_to(root).as_posix(),
        artifacts={executable.relative_to(host_record.parent.resolve()).as_posix(): host["sha256"]},
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=require_enrolled_build, required=True)
    parser.add_argument("--component", action="append", default=[], help="a component whose identity to publish")
    parser.add_argument("--settle-test-host", type=Path, help="the host.json the packaged test host build wrote")
    args = parser.parse_args()
    if args.settle_test_host is not None:
        settle_test_host(args.build, args.settle_test_host)
    for name, resolved_identity in resolve(args.build, args.component).items():
        BuildLog("build-stamp").status(
            f"{name}: build {resolved_identity.stamp.build_id}, sequence {resolved_identity.stamp.build_sequence}"
        )
