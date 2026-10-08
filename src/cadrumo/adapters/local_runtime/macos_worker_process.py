"""launchd-owned macOS profile worker and whole-coalition death fence.

Each worker runs under a private launchd job bootstrapped into the user's Aqua
domain from an owner-only definition that is deleted at once. launchd gives the
job a fresh resource coalition that every descendant keeps, including setsid,
regrouped and orphaned ones. Termination kills that whole coalition, the
guardian kills it when the runtime dies, and the scope kills it when the
guardian dies. Crash-durable markers let a later runtime retire jobs whose
runtime and guardian were both lost abruptly.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import plistlib
import re
import stat
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Protocol, cast
from uuid import UUID

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.descriptor_write import write_all
from ...core.hashing import sha256_hex
from .containment_commands import ContainmentCommand, ContainmentCommandResult, run_containment_command_sync
from .macos_coalition import read_macos_resource_coalition, terminate_macos_coalition
from .macos_process import (
    MacosProcessIncarnation,
    MacosProcessObservation,
    MacosProcessWatch,
    read_macos_incarnation,
    read_macos_process,
)
from .posix import open_private_namespace, posix_owner_uid
from .posix_channel import PosixRuntimeChannel
from .worker_arguments import validated_worker_arguments
from .worker_environment import worker_path_environment_names

_CLEAN_ENVIRONMENT = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "PYDANTIC_DISABLE_PLUGINS": "__all__"}
_GUARDIAN_MODULE = "cadrumo.entrypoints.runtime.macos_worker_guardian"
_LABEL_PREFIX = "com.cadrumo.worker."
_LABEL_PATTERN = re.compile(r"com\.cadrumo\.worker\.[0-9a-f]{16}\.[0-9a-f]{32}")
_SCOPE_KEY_PATTERN = re.compile(r"[0-9a-f]{16}")
_MARKER_SUFFIX = ".json"
_PENDING_SUFFIX = ".pending"
_DEFINITION_SUFFIX = ".plist"
_MARKER_LIMIT = 4096
_PRINT_LIMIT = 64 * 1024
_MAXIMUM_PID = 2_147_483_647
# launchctl print exits with 113 when the domain has no service of that label.
_SERVICE_ABSENT = 113
_LAUNCHD_PID = 1
_REGISTRATION_SECONDS = 5.0
_REAP_SECONDS = 10.0
_GUARDIAN_LOSS_SECONDS = 5.0
_WATCH_INTERVAL_SECONDS = 0.25
_MAXIMUM_WATCH_SECONDS = 60.0
_COALITION_FIELDS: frozenset[str] = frozenset(("ID", "type", "state", "active count", "name"))

# Serializes stale-job reaping between scopes of this process. A live runtime's
# own markers are never stale, so publication and removal need no lock.
_REAPING = Lock()


def macos_worker_scope_key(storage_root: Path) -> str:
    """Derive the stable storage-scope component of worker labels and markers.

    Args:
        storage_root: Existing profile storage root; aliases resolve to one key.
    """
    try:
        canonical = storage_root.resolve(strict=True)
    except OSError:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE) from None
    return sha256_hex(os.fsencode(canonical))[:16]


def macos_worker_label(*, scope_key: str, worker_id: UUID) -> str:
    """Compose an unguessable job label confined to one storage scope.

    Args:
        scope_key: Storage-scope key from macos_worker_scope_key.
        worker_id: Random worker identity.
    """
    if not _SCOPE_KEY_PATTERN.fullmatch(scope_key):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    return f"{_LABEL_PREFIX}{scope_key}.{worker_id.hex}"


def macos_worker_job_definition(
    *,
    label: str,
    executable: Path,
    directory: Path,
    parent: MacosProcessIncarnation,
    worker_arguments: Sequence[str],
    worker_script: Path | None,
    environment: Mapping[str, str] | None = None,
) -> bytes:
    """Render the private job definition that launches the guardian in a fresh coalition.

    The guardian runs through ``env -i`` so neither launchd's nor the runtime's
    environment reaches it. launchd must not restart it, abandon its process
    group, or keep its output.

    Args:
        label: Unguessable storage-scoped job label.
        executable: Absolute interpreter that runs the guardian and worker.
        directory: Resolved working directory.
        parent: Exact runtime incarnation the guardian must watch.
        worker_arguments: Verified worker argv after the interpreter.
        worker_script: Host-selected worker script, when not the installed module.
        environment: Explicit authority, storage and scratch paths under the clean baseline.
    """
    if not _LABEL_PATTERN.fullmatch(label) or not executable.is_absolute() or not directory.is_absolute():
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    environment = _validated_environment(_CLEAN_ENVIRONMENT if environment is None else environment)
    script_selection = ("--worker-script", str(worker_script)) if worker_script is not None else ()
    program = (
        "/usr/bin/env",
        "-i",
        *(f"{name}={value}" for name, value in environment.items()),
        str(executable),
        "-I",
        "-m",
        _GUARDIAN_MODULE,
        "--parent-pid",
        str(parent.pid),
        "--parent-version",
        str(parent.version),
        *script_selection,
        "--",
        *worker_arguments,
    )
    if any("\0" in argument for argument in program):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    return plistlib.dumps(
        {
            "Label": label,
            "ProgramArguments": list(program),
            "EnvironmentVariables": dict(environment),
            "WorkingDirectory": str(directory),
            "StandardOutPath": "/dev/null",
            "StandardErrorPath": "/dev/null",
            "RunAtLoad": True,
            "KeepAlive": False,
            "AbandonProcessGroup": False,
            "LimitLoadToSessionType": "Aqua",
            "ExitTimeOut": 1,
            "Umask": 0o077,
        },
        fmt=plistlib.FMT_XML,
        sort_keys=True,
    )


def _validated_environment(environment: Mapping[str, str]) -> dict[str, str]:
    """Admit only fixed interpreter controls and explicitly configured data paths."""
    allowed_paths = worker_path_environment_names()
    extras = set(environment) - set(_CLEAN_ENVIRONMENT)
    if (
        any(environment.get(name) != value for name, value in _CLEAN_ENVIRONMENT.items())
        or not extras <= allowed_paths
        or any("\0" in name or "\0" in value for name, value in environment.items())
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    return dict(environment)


@dataclass(frozen=True, slots=True)
class MacosJobCoalition:
    """The resource coalition launchd reports for one job."""

    coalition_id: int
    state: str
    active_count: int


@dataclass(frozen=True, slots=True)
class MacosJobPrint:
    """Closed facts from launchd's effective view of one job."""

    state: str
    pid: int | None
    coalition: MacosJobCoalition | None


def _decimal(value: str, *, minimum: int) -> int:
    if not value.isascii() or not value.isdecimal() or len(value) > 20 or int(value) < minimum:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    return int(value)


def parse_macos_job_print(text: str, *, target: str, label: str) -> MacosJobPrint:
    """Parse launchd's bounded print view of one job; any unknown shape refuses.

    Blocks other than the resource coalition are kept opaque. The coalition
    block must carry exactly its five known fields and name the job's label.

    Args:
        text: Complete ``launchctl print`` output for the job.
        target: Exact ``gui/<uid>/<label>`` service target that was printed.
        label: Exact job label the coalition must be named after.
    """
    if len(text.encode("utf-8")) > _PRINT_LIMIT or any(ord(char) < 32 and char not in "\n\t" for char in text):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    lines = text.splitlines()
    if len(lines) < 2 or lines[0] != target + " = {" or lines[-1] != "}":
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    scalars: dict[str, str] = {}
    blocks: dict[str, tuple[str, ...]] = {}
    end = len(lines) - 1
    index = 1
    while index < end:
        line = lines[index]
        index += 1
        if not line:
            continue
        if not line.startswith("\t") or line.startswith("\t\t"):
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        key, separator, value = line[1:].partition(" = ")
        if not separator or not key or key in scalars or key in blocks:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        if value != "{":
            scalars[key] = value
            continue
        members: list[str] = []
        while True:
            if index >= end:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
            member = lines[index]
            index += 1
            if member == "\t}":
                break
            if not member.startswith("\t\t"):
                raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
            members.append(member[2:])
        blocks[key] = tuple(members)
    state = scalars.get("state")
    if not state:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    printed_pid = scalars.get("pid")
    pid = None if printed_pid is None else _decimal(printed_pid, minimum=1)
    if pid is not None and pid > _MAXIMUM_PID:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    coalition = None
    coalition_block = blocks.get("resource coalition")
    if coalition_block is not None:
        fields: dict[str, str] = {}
        for member in coalition_block:
            key, separator, value = member.partition(" = ")
            if not separator or key not in _COALITION_FIELDS or key in fields:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
            fields[key] = value
        if frozenset(fields) != _COALITION_FIELDS or fields["type"] != "resource" or fields["name"] != label:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        if not fields["state"]:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        coalition = MacosJobCoalition(
            coalition_id=_decimal(fields["ID"], minimum=1),
            state=fields["state"],
            active_count=_decimal(fields["active count"], minimum=0),
        )
    return MacosJobPrint(state=state, pid=pid, coalition=coalition)


@dataclass(frozen=True, slots=True)
class MacosWorkerMarker:
    """Crash-durable ownership record naming one job and its runtime incarnation."""

    label: str
    runtime: MacosProcessIncarnation
    coalition: int | None


def encode_macos_worker_marker(marker: MacosWorkerMarker) -> bytes:
    """Render the one canonical marker encoding.

    Args:
        marker: Ownership record to persist.
    """
    if not _LABEL_PATTERN.fullmatch(marker.label) or (marker.coalition is not None and marker.coalition <= 0):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    return json.dumps(
        {
            "coalition": marker.coalition,
            "label": marker.label,
            "runtime_pid": marker.runtime.pid,
            "runtime_unique_id": marker.runtime.unique_id,
            "runtime_version": marker.runtime.version,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def decode_macos_worker_marker(payload: bytes, *, name: str) -> MacosWorkerMarker:
    """Accept only a canonical marker whose label matches its file name.

    Args:
        payload: Complete marker file contents.
        name: Marker file name within the private marker directory.
    """
    if len(payload) > _MARKER_LIMIT:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    try:
        document: object = json.loads(payload.decode("ascii"))
    except (UnicodeError, ValueError):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE) from None
    if not isinstance(document, dict):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    fields = cast(dict[object, object], document)
    label = fields.get("label")
    pid = fields.get("runtime_pid")
    version = fields.get("runtime_version")
    unique_id = fields.get("runtime_unique_id")
    coalition = fields.get("coalition")
    if (
        not isinstance(label, str)
        or name != label + _MARKER_SUFFIX
        or type(pid) is not int
        or type(version) is not int
        or type(unique_id) is not int
        or not (coalition is None or type(coalition) is int)
        or not 0 < pid <= _MAXIMUM_PID
        or not 0 < version <= _MAXIMUM_PID
        or unique_id <= 0
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    marker = MacosWorkerMarker(
        label=label,
        runtime=MacosProcessIncarnation(pid=pid, version=version, unique_id=unique_id),
        coalition=coalition,
    )
    if encode_macos_worker_marker(marker) != payload:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    return marker


def stale_macos_worker_markers(
    entries: Mapping[str, bytes], *, scope_key: str, live: Callable[[MacosProcessIncarnation], bool]
) -> tuple[MacosWorkerMarker, ...]:
    """Select this storage scope's markers whose runtime incarnation has died.

    Other scopes' entries are never decoded or returned. A corrupt marker of
    this scope refuses rather than being silently skipped.

    Args:
        entries: Marker file names and contents from the private directory.
        scope_key: Storage-scope key whose markers may be reaped.
        live: Whether an exact runtime incarnation is still alive.
    """
    prefix = f"{_LABEL_PREFIX}{scope_key}."
    stale: list[MacosWorkerMarker] = []
    for name in sorted(entries):
        if not name.startswith(prefix) or not name.endswith(_MARKER_SUFFIX):
            continue
        marker = decode_macos_worker_marker(entries[name], name=name)
        if not live(marker.runtime):
            stale.append(marker)
    return tuple(stale)


class MacosExitWatch(Protocol):
    """Latched exit observation for one exact process."""

    @property
    def exited(self) -> bool:
        """Whether the watched process has exited."""
        ...

    def wait(self, *, timeout: float) -> bool:
        """Wait a finite budget for exit.

        Args:
            timeout: Finite wait budget in seconds, at most sixty.
        """
        ...

    def close(self) -> None:
        """Release the native observation."""
        ...


class MacosWorkerHost(Protocol):
    """Native launchd, process and marker facts consumed by the worker scope."""

    def owner_uid(self) -> int:
        """Return the native owner UID."""
        ...

    def launchctl(self, arguments: tuple[str, ...]) -> ContainmentCommandResult:
        """Run one bounded launchctl request.

        Args:
            arguments: Exact launchctl action and target.
        """
        ...

    def bootstrap(self, label: str, definition: bytes) -> ContainmentCommandResult:
        """Bootstrap a private definition into the GUI domain, deleting it on every path.

        Args:
            label: Exact job label.
            definition: Complete job property list.
        """
        ...

    def incarnation(self, pid: int) -> MacosProcessIncarnation | None:
        """Read a live PID's exact incarnation; None when no live process holds it.

        Args:
            pid: Kernel PID.
        """
        ...

    def coalition(self, pid: int) -> int | None:
        """Read a live PID's resource coalition; None when no live process holds it.

        Args:
            pid: Kernel PID.
        """
        ...

    def observe(self, pid: int) -> MacosProcessObservation:
        """Read the owner's live process identity.

        Args:
            pid: Kernel PID.
        """
        ...

    def watch(self, observation: MacosProcessObservation) -> MacosExitWatch:
        """Retain an exit watch for one verified identity.

        Args:
            observation: Exact identity to watch.
        """
        ...

    def terminate_coalition(self, coalition: int, *, deadline: float) -> None:
        """Kill every coalition member until it is proven empty.

        Args:
            coalition: Resource coalition ID.
            deadline: Monotonic deadline.
        """
        ...

    def markers(self, prefix: str) -> dict[str, bytes]:
        """Read marker files whose names start with a storage-scope prefix.

        Args:
            prefix: Storage-scoped label prefix.
        """
        ...

    def publish_marker(self, label: str, payload: bytes) -> None:
        """Durably replace one job's marker.

        Args:
            label: Exact job label.
            payload: Canonical marker encoding.
        """
        ...

    def remove_marker(self, label: str) -> None:
        """Durably remove one job's marker, after any definition its abrupt loss left behind.

        An absent marker or definition is already removed.

        Args:
            label: Exact job label.
        """
        ...


def _private_open_flags(*, nonblocking: bool = False) -> int:
    """Darwin open flags refusing symlinks and keeping descriptors out of children."""
    if sys.platform == "darwin":
        return os.O_NOFOLLOW | os.O_CLOEXEC | (os.O_NONBLOCK if nonblocking else 0)
    raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)


class _NativeMacosWorkerHost:
    """Darwin launchd, libproc and owner-only marker directory."""

    def _directory(self, *, create: bool) -> tuple[Path, int]:
        if sys.platform == "darwin":
            try:
                return open_private_namespace(
                    Path("/").joinpath("tmp", f"cdr-{posix_owner_uid()}-launchd-workers"), create=create
                )
            except RuntimeRefusalError:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE) from None
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)

    def owner_uid(self) -> int:
        return posix_owner_uid()

    def launchctl(self, arguments: tuple[str, ...]) -> ContainmentCommandResult:
        return run_containment_command_sync(ContainmentCommand.LAUNCHCTL, arguments)

    def bootstrap(self, label: str, definition: bytes) -> ContainmentCommandResult:
        directory, descriptor = self._directory(create=True)
        name = label + _DEFINITION_SUFFIX
        try:
            file = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _private_open_flags(), 0o600, dir_fd=descriptor)
            try:
                try:
                    write_all(file, definition)
                finally:
                    os.close(file)
                # launchd keeps the loaded job after its definition file is gone.
                return run_containment_command_sync(
                    ContainmentCommand.LAUNCHCTL, ("bootstrap", f"gui/{posix_owner_uid()}", str(directory / name))
                )
            finally:
                os.unlink(name, dir_fd=descriptor)
        except OSError:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE) from None
        finally:
            os.close(descriptor)

    def incarnation(self, pid: int) -> MacosProcessIncarnation | None:
        return read_macos_incarnation(pid)

    def coalition(self, pid: int) -> int | None:
        return read_macos_resource_coalition(pid)

    def observe(self, pid: int) -> MacosProcessObservation:
        return read_macos_process(pid, expected_owner=str(posix_owner_uid()))

    def watch(self, observation: MacosProcessObservation) -> MacosExitWatch:
        return MacosProcessWatch(observation)

    def terminate_coalition(self, coalition: int, *, deadline: float) -> None:
        terminate_macos_coalition(coalition, deadline=deadline)

    def markers(self, prefix: str) -> dict[str, bytes]:
        _directory, descriptor = self._directory(create=False)
        if descriptor < 0:
            return {}
        try:
            entries: dict[str, bytes] = {}
            for name in os.listdir(descriptor):
                if not name.startswith(prefix) or not name.endswith(_MARKER_SUFFIX):
                    continue
                file = os.open(name, os.O_RDONLY | _private_open_flags(nonblocking=True), dir_fd=descriptor)
                try:
                    metadata = os.fstat(file)
                    if (
                        not stat.S_ISREG(metadata.st_mode)
                        or metadata.st_uid != posix_owner_uid()
                        or metadata.st_mode & 0o077
                        or metadata.st_nlink != 1
                        or metadata.st_size > _MARKER_LIMIT
                    ):
                        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
                    entries[name] = os.read(file, _MARKER_LIMIT + 1)
                finally:
                    os.close(file)
            return entries
        except OSError:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE) from None
        finally:
            os.close(descriptor)

    def publish_marker(self, label: str, payload: bytes) -> None:
        _directory, descriptor = self._directory(create=True)
        pending = label + _PENDING_SUFFIX
        try:
            file = os.open(
                pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | _private_open_flags(), 0o600, dir_fd=descriptor
            )
            try:
                metadata = os.fstat(file)
                if (
                    not stat.S_ISREG(metadata.st_mode)
                    or metadata.st_uid != posix_owner_uid()
                    or metadata.st_mode & 0o077
                    or metadata.st_nlink != 1
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
                write_all(file, payload)
                os.fsync(file)
            finally:
                os.close(file)
            os.replace(pending, label + _MARKER_SUFFIX, src_dir_fd=descriptor, dst_dir_fd=descriptor)
            os.fsync(descriptor)
        except OSError:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE) from None
        finally:
            os.close(descriptor)

    def remove_marker(self, label: str) -> None:
        _directory, descriptor = self._directory(create=False)
        if descriptor < 0:
            return
        try:
            # A runtime lost inside launchctl bootstrap never deletes its
            # definition. The marker goes last: it is the reaping obligation.
            for name in (label + _DEFINITION_SUFFIX, label + _PENDING_SUFFIX, label + _MARKER_SUFFIX):
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(name, dir_fd=descriptor)
            os.fsync(descriptor)
        except OSError:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE) from None
        finally:
            os.close(descriptor)


class MacosOwnedProcess:
    """Retain the guardian's exact exit watch until its job has been retired."""

    def __init__(self, *, pid: int, watch: MacosExitWatch) -> None:
        """Retain one verified guardian incarnation's exit observation.

        Args:
            pid: Guardian PID reported by launchd and corroborated natively.
            watch: Exit watch registered on the exact guardian.
        """
        self.pid = pid
        self._watch: MacosExitWatch | None = watch

    def wait(self, *, timeout: float) -> int:
        """Wait for the exact guardian without reopening a reusable PID.

        Args:
            timeout: Finite wait budget in seconds.
        """
        if self._watch is None or not math.isfinite(timeout) or timeout < 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        deadline = time.monotonic() + timeout
        while True:
            remaining = max(0.0, deadline - time.monotonic())
            if self._watch.wait(timeout=min(remaining, _MAXIMUM_WATCH_SECONDS)):
                return 0
            if remaining <= _MAXIMUM_WATCH_SECONDS:
                raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)

    def close(self) -> None:
        """Release the native watch after its job has settled."""
        if self._watch is not None:
            watch, self._watch = self._watch, None
            watch.close()

    @property
    def alive(self) -> bool:
        """Observe the held guardian without treating a PID as a capability."""
        return self._watch is not None and not self._watch.exited


@dataclass(frozen=True, slots=True)
class _MacosWorker:
    incarnation: MacosProcessIncarnation
    watch: MacosExitWatch


class MacosProcessScope:
    """A private launchd job whose resource coalition contains the worker and its descendants.

    The guardian is the job's main process and watches the exact runtime
    incarnation. The worker shares the guardian's process group, and every
    descendant keeps the job's coalition however it regroups. Termination kills
    that whole coalition by exact incarnation before launchd retires the job.
    """

    _lock: Lock
    _host: MacosWorkerHost
    _worker_script: Path | None
    _scope_key: str
    _label: str
    _target: str
    _started: bool
    _fenced: bool
    _runtime: MacosProcessIncarnation | None
    _coalition: int | None
    _guardian: MacosOwnedProcess | None
    _worker: _MacosWorker | None
    _watcher: Thread | None
    _watcher_stop: Event
    _watcher_failure: BaseException | None

    def __init__(
        self,
        *,
        worker_id: UUID,
        storage_root: Path,
        worker_script: Path | None = None,
        host: MacosWorkerHost | None = None,
    ) -> None:
        """Reserve an unguessable storage-scoped job identity without launching any child.

        Args:
            worker_id: Random worker identity.
            storage_root: Existing profile storage root that scopes stale-job recovery.
            worker_script: Host-selected worker script, when not the installed module.
            host: Native facts; defaults to the Darwin kernel, launchd and marker directory.
        """
        if sys.platform != "darwin":
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        selected = validated_worker_arguments(worker_script=worker_script)
        self._worker_script = Path(selected[-1]) if worker_script is not None else None
        self._host = host if host is not None else _NativeMacosWorkerHost()
        self._scope_key = macos_worker_scope_key(storage_root)
        self._label = macos_worker_label(scope_key=self._scope_key, worker_id=worker_id)
        self._target = f"gui/{self._host.owner_uid()}/{self._label}"
        self._lock = Lock()
        self._started = False
        self._fenced = False
        self._runtime = None
        self._coalition = None
        self._guardian = None
        self._worker = None
        self._watcher = None
        self._watcher_stop = Event()
        self._watcher_failure = None

    def launch(
        self, *, executable: Path, arguments: Sequence[str], directory: Path, environment: Mapping[str, str]
    ) -> MacosOwnedProcess:
        """Register launchd containment before its first child executes code.

        Args:
            executable: Absolute interpreter for the guardian and worker.
            arguments: Worker argv after the interpreter.
            directory: Absolute working directory.
            environment: Exact clean worker environment.
        """
        if self._started or not executable.is_absolute() or not directory.is_absolute():
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        arguments = validated_worker_arguments(arguments, worker_script=self._worker_script)
        environment = _validated_environment(environment)
        # Keep the venv interpreter path: resolving its symlink changes Python's
        # pyvenv.cfg discovery and can launch without the installed package.
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        try:
            directory = directory.resolve(strict=True)
        except OSError:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE) from None
        runtime = self._host.incarnation(os.getpid())
        runtime_coalition = self._host.coalition(os.getpid())
        if runtime is None or runtime_coalition is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        definition = macos_worker_job_definition(
            label=self._label,
            executable=executable,
            directory=directory,
            parent=runtime,
            worker_arguments=arguments,
            worker_script=self._worker_script,
            environment=environment,
        )
        with _REAPING:
            self._reap_stale_jobs()
        # The marker precedes registration: if this runtime is lost abruptly,
        # a later runtime can still find and retire the job.
        self._host.publish_marker(
            self._label, encode_macos_worker_marker(MacosWorkerMarker(self._label, runtime, None))
        )
        self._runtime = runtime
        # A lost launchd acknowledgement may still have loaded this exact
        # job. Retain the stop obligation before asking launchd.
        self._started = True
        if self._host.bootstrap(self._label, definition).returncode != 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        deadline = time.monotonic() + _REGISTRATION_SECONDS
        while True:
            guardian = self._admit_guardian(runtime_coalition)
            if guardian is not None:
                return guardian
            if time.monotonic() >= deadline:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
            time.sleep(0.05)

    def _admit_guardian(self, runtime_coalition: int) -> MacosOwnedProcess | None:
        printed = self._host.launchctl(("print", self._target))
        if printed.returncode != 0:
            return None
        job = parse_macos_job_print(printed.output, target=self._target, label=self._label)
        coalition = job.coalition
        if job.state != "running" or job.pid is None or coalition is None or coalition.state != "active":
            return None
        pid = job.pid
        # launchd must have given the job its own coalition, distinct from the
        # runtime's, and the printed main process must actually belong to it.
        if coalition.coalition_id == runtime_coalition or self._host.coalition(pid) != coalition.coalition_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        try:
            observation = self._host.observe(pid)
        except RuntimeRefusalError as error:
            # launchd can publish a PID before its BSD identity is readable.
            if error.reason is RuntimeRefusalCode.UNAVAILABLE:
                return None
            raise
        if observation.parent_pid != _LAUNCHD_PID:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        # From here any failure must retire this exact coalition.
        self._coalition = coalition.coalition_id
        watches: list[MacosExitWatch] = []
        try:
            watches.append(self._host.watch(observation))
            watches.append(self._host.watch(observation))
            if watches[0].exited or self._host.coalition(pid) != coalition.coalition_id:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
            runtime = self._runtime
            if runtime is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
            self._host.publish_marker(
                self._label,
                encode_macos_worker_marker(MacosWorkerMarker(self._label, runtime, coalition.coalition_id)),
            )
            watcher = Thread(
                target=self._watch_guardian, args=(watches[1],), name="macos-worker-guardian-watch", daemon=True
            )
            watcher.start()
        except BaseException as error:
            for watch in watches:
                try:
                    watch.close()
                except BaseException as cleanup:
                    error.add_note(f"Guardian watch close also failed: {type(cleanup).__name__}")
            raise
        self._watcher = watcher
        self._guardian = MacosOwnedProcess(pid=pid, watch=watches[0])
        return self._guardian

    def _watch_guardian(self, sentinel: MacosExitWatch) -> None:
        """Contain the coalition at once if the guardian dies while the runtime lives."""
        failure: BaseException | None = None
        try:
            exited = False
            while not exited and not self._watcher_stop.is_set():
                exited = sentinel.wait(timeout=_WATCH_INTERVAL_SECONDS)
            if exited:
                with self._lock:
                    self._fenced = True
                    coalition = self._coalition
                if coalition is not None and not self._watcher_stop.is_set():
                    self._host.terminate_coalition(coalition, deadline=time.monotonic() + _GUARDIAN_LOSS_SECONDS)
        except BaseException as error:
            failure = error
        finally:
            try:
                sentinel.close()
            except BaseException as error:
                failure = failure or error
            if failure is not None:
                with self._lock:
                    # Without a guardian observation the scope can no longer
                    # vouch for its worker; terminate reports the retained failure.
                    self._fenced = True
                    self._watcher_failure = failure

    def verify_worker(self, channel: PosixRuntimeChannel, *, owner_id: str) -> int:
        """Pin the socket peer's exact incarnation and coalition before worker identity or key release.

        Args:
            channel: Accepted worker connection with kernel-verified peer facts.
            owner_id: Native owner the worker must run as.
        """
        pid = channel.peer.process_id
        with self._lock:
            guardian, coalition, fenced = self._guardian, self._coalition, self._fenced
        if guardian is None or coalition is None or fenced or not guardian.alive:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        if pid is None or channel.peer.os_owner_id != owner_id or owner_id != str(self._host.owner_uid()):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        token = channel.capture_peer_audit_token()
        if token.process_id != pid or pid == guardian.pid or self._host.coalition(pid) != coalition:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        observation = self._host.observe(pid)
        incarnation = self._host.incarnation(pid)
        if (
            observation.parent_pid != guardian.pid
            or incarnation is None
            or incarnation.version != token.process_version
            or self._host.coalition(pid) != coalition
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        with self._lock:
            current = self._worker
        if current is not None:
            if current.incarnation != incarnation or current.watch.exited:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            return pid
        watch = self._host.watch(observation)
        try:
            if watch.exited or self._host.incarnation(pid) != incarnation:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            with self._lock:
                if self._worker is not None or self._fenced:
                    raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
                self._worker = _MacosWorker(incarnation=incarnation, watch=watch)
        except BaseException:
            watch.close()
            raise
        return pid

    def owns_process(self, pid: int) -> bool:
        """Require the retained worker and guardian to remain live in this coalition.

        Args:
            pid: Worker PID to check.
        """
        with self._lock:
            worker, guardian, coalition, fenced = self._worker, self._guardian, self._coalition, self._fenced
        if fenced or worker is None or guardian is None or coalition is None or pid != worker.incarnation.pid:
            return False
        return (
            self._host.coalition(pid) == coalition
            and self._host.incarnation(pid) == worker.incarnation
            and not worker.watch.exited
            and guardian.alive
        )

    @property
    def worker_pid(self) -> int:
        """Return the verified worker PID for a fresh custody health check."""
        worker = self._worker
        return worker.incarnation.pid if worker is not None else 0

    def active_process_ids(self) -> tuple[int, ...]:
        """Expose only the verified live worker to the authorization channel."""
        pid = self.worker_pid
        return (pid,) if self.owns_process(pid) else ()

    def terminate(self, *, timeout: float = 2.0) -> None:
        """Kill the whole coalition, retire the job and observe both exits, retaining failure.

        Args:
            timeout: Finite budget in seconds; a failed attempt can be retried.
        """
        if not math.isfinite(timeout) or timeout < 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        if not self._started:
            return
        deadline = time.monotonic() + timeout
        with self._lock:
            self._fenced = True
        self._watcher_stop.set()
        try:
            coalition = self._coalition if self._coalition is not None else self._loaded_coalition(self._target)
            if coalition is not None:
                self._host.terminate_coalition(self._foreign_coalition(coalition), deadline=deadline)
            self._retire_job(self._target, deadline=deadline)
            for watch in (
                self._guardian,
                self._worker.watch if self._worker is not None else None,
            ):
                if watch is not None and not self._exited(watch, deadline=deadline):
                    raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
            if self._watcher is not None:
                self._watcher.join(timeout=max(0.0, deadline - time.monotonic()))
                if self._watcher.is_alive():
                    raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
                self._watcher = None
        except BaseException as error:
            if self._watcher_failure is not None:
                error.add_note("Guardian-loss containment also failed earlier: " + type(self._watcher_failure).__name__)
            raise
        guardian, self._guardian = self._guardian, None
        worker, self._worker = self._worker, None
        failures: list[BaseException] = []
        for owner in (guardian, worker.watch if worker is not None else None):
            if owner is not None:
                try:
                    owner.close()
                except BaseException as error:
                    failures.append(error)
        self._host.remove_marker(self._label)
        self._coalition = None
        self._watcher_failure = None
        self._started = False
        if failures:
            raise failures[0]

    @staticmethod
    def _exited(watch: MacosOwnedProcess | MacosExitWatch, *, deadline: float) -> bool:
        if isinstance(watch, MacosOwnedProcess):
            if not watch.alive:
                return True
            try:
                watch.wait(timeout=max(0.0, deadline - time.monotonic()))
            except RuntimeRefusalError as error:
                if error.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED:
                    return False
                raise
            return True
        return watch.wait(timeout=min(_MAXIMUM_WATCH_SECONDS, max(0.0, deadline - time.monotonic())))

    def _foreign_coalition(self, coalition: int) -> int:
        # Killing the runtime's own coalition would kill the runtime itself.
        if coalition == self._host.coalition(os.getpid()):
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        return coalition

    def _absent(self, target: str) -> bool:
        printed = self._host.launchctl(("print", target))
        if printed.returncode == _SERVICE_ABSENT:
            return True
        if printed.returncode == 0:
            return False
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)

    def _loaded_coalition(self, target: str, *, label: str | None = None) -> int | None:
        printed = self._host.launchctl(("print", target))
        if printed.returncode == _SERVICE_ABSENT:
            return None
        if printed.returncode != 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        job = parse_macos_job_print(printed.output, target=target, label=label or self._label)
        return job.coalition.coalition_id if job.coalition is not None else None

    def _retire_job(self, target: str, *, deadline: float) -> None:
        # Only an emptied coalition reaches bootout, so an absent job never
        # leaves members behind.
        if self._host.launchctl(("bootout", target)).returncode != 0 and not self._absent(target):
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        while not self._absent(target):
            if time.monotonic() >= deadline:
                raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
            time.sleep(0.01)

    def _reap_stale_jobs(self) -> None:
        """Retire this storage scope's jobs whose runtime incarnation died abruptly."""
        uid = self._host.owner_uid()
        stale = stale_macos_worker_markers(
            self._host.markers(f"{_LABEL_PREFIX}{self._scope_key}."),
            scope_key=self._scope_key,
            live=lambda runtime: self._host.incarnation(runtime.pid) == runtime,
        )
        deadline = time.monotonic() + _REAP_SECONDS
        for marker in stale:
            target = f"gui/{uid}/{marker.label}"
            coalition = self._loaded_coalition(target, label=marker.label)
            if coalition is not None and marker.coalition is not None and coalition != marker.coalition:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
            if coalition is None:
                # launchd can forget the job while regrouped descendants remain alive.
                # Keep the durable retirement obligation until its recorded coalition is empty.
                coalition = marker.coalition
            if coalition is not None:
                self._host.terminate_coalition(self._foreign_coalition(coalition), deadline=deadline)
            self._retire_job(target, deadline=deadline)
            self._host.remove_marker(marker.label)


__all__ = [
    "MacosExitWatch",
    "MacosJobCoalition",
    "MacosJobPrint",
    "MacosOwnedProcess",
    "MacosProcessScope",
    "MacosWorkerHost",
    "MacosWorkerMarker",
    "decode_macos_worker_marker",
    "encode_macos_worker_marker",
    "macos_worker_job_definition",
    "macos_worker_label",
    "macos_worker_scope_key",
    "parse_macos_job_print",
    "stale_macos_worker_markers",
]
