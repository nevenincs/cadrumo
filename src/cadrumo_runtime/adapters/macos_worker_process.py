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

import math
import os
import plistlib
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock, Thread
from uuid import UUID

from cadrumo.core.hashing import sha256_hex
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.posix_channel import PosixChannel

from .macos_job_print import parse_macos_job_print
from .macos_process import (
    MacosProcessIncarnation,
    MacosProcessObservation,
)
from .macos_worker_host import MacosExitWatch, MacosWorkerHost, NativeMacosWorkerHost
from .macos_worker_markers import (
    MACOS_SCOPE_KEY_PATTERN,
    MACOS_WORKER_LABEL_PATTERN,
    MACOS_WORKER_LABEL_PREFIX,
    MacosWorkerMarker,
    encode_macos_worker_marker,
    stale_macos_worker_markers,
)
from .worker_arguments import validated_worker_arguments
from .worker_environment import worker_path_environment_names

_CLEAN_ENVIRONMENT = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "PYDANTIC_DISABLE_PLUGINS": "__all__"}
_GUARDIAN_MODULE = "cadrumo_runtime.host.macos_worker_guardian"
# launchctl print exits with 113 when the domain has no service of that label.
_SERVICE_ABSENT = 113
_LAUNCHD_PID = 1
_REGISTRATION_SECONDS = 5.0
_REAP_SECONDS = 10.0
_GUARDIAN_LOSS_SECONDS = 5.0
_WATCH_INTERVAL_SECONDS = 0.25
_MAXIMUM_WATCH_SECONDS = 60.0

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
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE) from None
    return sha256_hex(os.fsencode(canonical))[:16]


def macos_worker_label(*, scope_key: str, worker_id: UUID) -> str:
    """Compose an unguessable job label confined to one storage scope.

    Args:
        scope_key: Storage-scope key from macos_worker_scope_key.
        worker_id: Random worker identity.
    """
    if not MACOS_SCOPE_KEY_PATTERN.fullmatch(scope_key):
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    return f"{MACOS_WORKER_LABEL_PREFIX}{scope_key}.{worker_id.hex}"


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
    if not MACOS_WORKER_LABEL_PATTERN.fullmatch(label) or not executable.is_absolute() or not directory.is_absolute():
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
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
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
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
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
    return dict(environment)


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
            raise RefusalError(RefusalCode.UNAVAILABLE)
        deadline = time.monotonic() + timeout
        while True:
            remaining = max(0.0, deadline - time.monotonic())
            if self._watch.wait(timeout=min(remaining, _MAXIMUM_WATCH_SECONDS)):
                return 0
            if remaining <= _MAXIMUM_WATCH_SECONDS:
                raise RefusalError(RefusalCode.TIMEOUT)

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
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
        selected = validated_worker_arguments(worker_script=worker_script)
        self._worker_script = Path(selected[-1]) if worker_script is not None else None
        self._host = host if host is not None else NativeMacosWorkerHost()
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

    def _launch_inputs(
        self, executable: Path, arguments: Sequence[str], directory: Path, environment: Mapping[str, str]
    ) -> tuple[tuple[str, ...], dict[str, str], Path]:
        if self._started or not executable.is_absolute() or not directory.is_absolute():
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
        arguments = validated_worker_arguments(arguments, worker_script=self._worker_script)
        environment = _validated_environment(environment)
        # Keep the venv interpreter path: resolving its symlink changes Python's
        # pyvenv.cfg discovery and can launch without the installed package.
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
        try:
            directory = directory.resolve(strict=True)
        except OSError:
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE) from None
        return arguments, environment, directory

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
        arguments, environment, directory = self._launch_inputs(executable, arguments, directory, environment)
        runtime = self._host.incarnation(os.getpid())
        runtime_coalition = self._host.coalition(os.getpid())
        if runtime is None or runtime_coalition is None:
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
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
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
        deadline = time.monotonic() + _REGISTRATION_SECONDS
        while True:
            guardian = self._admit_guardian(runtime_coalition)
            if guardian is not None:
                return guardian
            if time.monotonic() >= deadline:
                raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
            time.sleep(0.05)

    def _guardian_observation(self, pid: int) -> MacosProcessObservation | None:
        try:
            observation = self._host.observe(pid)
        except RefusalError as error:
            # launchd can publish a PID before its BSD identity is readable.
            if error.reason is RefusalCode.UNAVAILABLE:
                return None
            raise
        if observation.parent_pid != _LAUNCHD_PID:
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
        return observation

    def _watch_admitted_guardian(
        self, pid: int, observation: MacosProcessObservation, coalition_id: int
    ) -> MacosOwnedProcess:
        watches: list[MacosExitWatch] = []
        try:
            watches.append(self._host.watch(observation))
            watches.append(self._host.watch(observation))
            if watches[0].exited or self._host.coalition(pid) != coalition_id:
                raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
            runtime = self._runtime
            if runtime is None:
                raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
            self._host.publish_marker(
                self._label,
                encode_macos_worker_marker(MacosWorkerMarker(self._label, runtime, coalition_id)),
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
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
        observation = self._guardian_observation(pid)
        if observation is None:
            return None
        # From here any failure must retire this exact coalition.
        self._coalition = coalition.coalition_id
        return self._watch_admitted_guardian(pid, observation, coalition.coalition_id)

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

    def _verify_worker_identity(
        self, channel: PosixChannel, pid: int, guardian: MacosOwnedProcess, coalition: int
    ) -> tuple[MacosProcessObservation, MacosProcessIncarnation]:
        from .macos_login import macos_peer_audit_token

        with channel.pinned_peer_socket() as sock:
            token = macos_peer_audit_token(sock, expected_owner=channel.peer.os_owner_id)
        if token.process_id != pid or pid == guardian.pid or self._host.coalition(pid) != coalition:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        observation = self._host.observe(pid)
        incarnation = self._host.incarnation(pid)
        if (
            observation.parent_pid != guardian.pid
            or incarnation is None
            or incarnation.version != token.process_version
            or self._host.coalition(pid) != coalition
        ):
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        return observation, incarnation

    def _retain_worker(
        self, pid: int, observation: MacosProcessObservation, incarnation: MacosProcessIncarnation
    ) -> None:
        with self._lock:
            current = self._worker
        if current is not None:
            if current.incarnation != incarnation or current.watch.exited:
                raise RefusalError(RefusalCode.PEER_UNTRUSTED)
            return
        watch = self._host.watch(observation)
        try:
            if watch.exited or self._host.incarnation(pid) != incarnation:
                raise RefusalError(RefusalCode.PEER_UNTRUSTED)
            with self._lock:
                if self._worker is not None or self._fenced:
                    raise RefusalError(RefusalCode.PEER_UNTRUSTED)
                self._worker = _MacosWorker(incarnation=incarnation, watch=watch)
        except BaseException:
            watch.close()
            raise

    def verify_worker(self, channel: PosixChannel, *, owner_id: str) -> int:
        """Pin the socket peer's exact incarnation and coalition before worker identity or key release.

        Args:
            channel: Accepted worker connection with kernel-verified peer facts.
            owner_id: Native owner the worker must run as.
        """
        pid = channel.peer.process_id
        with self._lock:
            guardian, coalition, fenced = self._guardian, self._coalition, self._fenced
        if guardian is None or coalition is None or fenced or not guardian.alive:
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
        if pid is None or channel.peer.os_owner_id != owner_id or owner_id != str(self._host.owner_uid()):
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        observation, incarnation = self._verify_worker_identity(channel, pid, guardian, coalition)
        self._retain_worker(pid, observation, incarnation)
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

    def _terminate_job(self, deadline: float) -> None:
        coalition = self._coalition if self._coalition is not None else self._loaded_coalition(self._target)
        if coalition is not None:
            self._host.terminate_coalition(self._foreign_coalition(coalition), deadline=deadline)
        self._retire_job(self._target, deadline=deadline)
        for watch in (
            self._guardian,
            self._worker.watch if self._worker is not None else None,
        ):
            if watch is not None and not self._exited(watch, deadline=deadline):
                raise RefusalError(RefusalCode.TIMEOUT)
        if self._watcher is not None:
            self._watcher.join(timeout=max(0.0, deadline - time.monotonic()))
            if self._watcher.is_alive():
                raise RefusalError(RefusalCode.TIMEOUT)
            self._watcher = None

    def _release_watches(self) -> None:
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

    def terminate(self, *, timeout: float = 2.0) -> None:
        """Kill the whole coalition, retire the job and observe both exits, retaining failure.

        Args:
            timeout: Finite budget in seconds; a failed attempt can be retried.
        """
        if not math.isfinite(timeout) or timeout < 0:
            raise RefusalError(RefusalCode.UNAVAILABLE)
        if not self._started:
            return
        deadline = time.monotonic() + timeout
        with self._lock:
            self._fenced = True
        self._watcher_stop.set()
        try:
            self._terminate_job(deadline)
        except BaseException as error:
            if self._watcher_failure is not None:
                error.add_note("Guardian-loss containment also failed earlier: " + type(self._watcher_failure).__name__)
            raise
        self._release_watches()

    @staticmethod
    def _exited(watch: MacosOwnedProcess | MacosExitWatch, *, deadline: float) -> bool:
        if isinstance(watch, MacosOwnedProcess):
            if not watch.alive:
                return True
            try:
                watch.wait(timeout=max(0.0, deadline - time.monotonic()))
            except RefusalError as error:
                if error.reason is RefusalCode.TIMEOUT:
                    return False
                raise
            return True
        return watch.wait(timeout=min(_MAXIMUM_WATCH_SECONDS, max(0.0, deadline - time.monotonic())))

    def _foreign_coalition(self, coalition: int) -> int:
        # Killing the runtime's own coalition would kill the runtime itself.
        if coalition == self._host.coalition(os.getpid()):
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
        return coalition

    def _absent(self, target: str) -> bool:
        printed = self._host.launchctl(("print", target))
        if printed.returncode == _SERVICE_ABSENT:
            return True
        if printed.returncode == 0:
            return False
        raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)

    def _loaded_coalition(self, target: str, *, label: str | None = None) -> int | None:
        printed = self._host.launchctl(("print", target))
        if printed.returncode == _SERVICE_ABSENT:
            return None
        if printed.returncode != 0:
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
        job = parse_macos_job_print(printed.output, target=target, label=label or self._label)
        return job.coalition.coalition_id if job.coalition is not None else None

    def _retire_job(self, target: str, *, deadline: float) -> None:
        # Only an emptied coalition reaches bootout, so an absent job never
        # leaves members behind.
        if self._host.launchctl(("bootout", target)).returncode != 0 and not self._absent(target):
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
        while not self._absent(target):
            if time.monotonic() >= deadline:
                raise RefusalError(RefusalCode.TIMEOUT)
            time.sleep(0.01)

    def _reap_stale_jobs(self) -> None:
        """Retire this storage scope's jobs whose runtime incarnation died abruptly."""
        uid = self._host.owner_uid()
        stale = stale_macos_worker_markers(
            self._host.markers(f"{MACOS_WORKER_LABEL_PREFIX}{self._scope_key}."),
            scope_key=self._scope_key,
            live=lambda runtime: self._host.incarnation(runtime.pid) == runtime,
        )
        deadline = time.monotonic() + _REAP_SECONDS
        for marker in stale:
            target = f"gui/{uid}/{marker.label}"
            coalition = self._loaded_coalition(target, label=marker.label)
            if coalition is not None and marker.coalition is not None and coalition != marker.coalition:
                raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
            if coalition is None:
                # launchd can forget the job while regrouped descendants remain alive.
                # Keep the durable retirement obligation until its recorded coalition is empty.
                coalition = marker.coalition
            if coalition is not None:
                self._host.terminate_coalition(self._foreign_coalition(coalition), deadline=deadline)
            self._retire_job(target, deadline=deadline)
            self._host.remove_marker(marker.label)


__all__ = [
    "MacosOwnedProcess",
    "MacosProcessScope",
    "macos_worker_job_definition",
    "macos_worker_label",
    "macos_worker_scope_key",
]
