"""User-systemd-owned Linux profile worker and whole-cgroup death fence."""

from __future__ import annotations

import os
import select
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from threading import Lock
from uuid import UUID

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from .linux_pidfd import open_linux_pidfd
from .manager_commands import NativeManagerCommand, run_manager_command_sync
from .posix import posix_owner_uid
from .posix_channel import PosixRuntimeChannel
from .worker_arguments import validated_worker_arguments

_PROPERTIES = {
    "ActiveState",
    "ControlGroup",
    "ExitType",
    "KillMode",
    "MainPID",
    "Restart",
    "SendSIGKILL",
    "StandardError",
    "StandardOutput",
    "TimeoutStopUSec",
    "Type",
}


def linux_process_start_identity(pid: int) -> str:
    """Read the kernel start tick, avoiding PID reuse across a launch handoff."""
    if sys.platform != "linux" or pid <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    try:
        stat = (Path("/proc") / str(pid) / "stat").read_text(encoding="ascii")
        suffix = stat.rsplit(") ", 1)[1].split()
        # /proc/PID/stat field 22 is item 19 after field 2's command.
        start = suffix[19]
        if not start.isdecimal() or int(start) <= 0:
            raise ValueError
        return start
    except (OSError, UnicodeError, IndexError, ValueError):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE) from None


def _unit_properties(unit: str) -> dict[str, str]:
    result = run_manager_command_sync(
        NativeManagerCommand.SYSTEMCTL,
        ("--user", "--no-pager", "--no-ask-password", "show", unit, "--property=" + ",".join(sorted(_PROPERTIES))),
    )
    if result.returncode != 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    properties: dict[str, str] = {}
    for line in result.output.splitlines():
        name, equals, value = line.partition("=")
        if not equals or name not in _PROPERTIES or name in properties:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        properties[name] = value
    if set(properties) != _PROPERTIES:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    return properties


def _unit_absent(unit: str) -> bool:
    result = run_manager_command_sync(
        NativeManagerCommand.SYSTEMCTL,
        (
            "--user",
            "--no-pager",
            "--no-ask-password",
            "show",
            unit,
            "--property=LoadState,ActiveState,ControlGroup",
        ),
    )
    if result.returncode != 0:
        return False
    return set(result.output.splitlines()) == {"LoadState=not-found", "ActiveState=inactive", "ControlGroup="}


def _cgroup_for(pid: int) -> str:
    try:
        lines = (Path("/proc") / str(pid) / "cgroup").read_text(encoding="ascii").splitlines()
        if len(lines) != 1 or not lines[0].startswith("0::/"):
            raise ValueError
        return lines[0][3:]
    except (OSError, UnicodeError, ValueError):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE) from None


def _pidfd_alive(descriptor: int) -> bool:
    if sys.platform == "linux":
        poller = select.poll()
        poller.register(descriptor, select.POLLIN | select.POLLERR | select.POLLHUP)
        return not poller.poll(0)
    raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)


def _cgroup_empty(group: str) -> bool:
    """Use kernel populated state, including nested independent descendants."""
    if not group.startswith("/") or ".." in Path(group).parts:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    path = Path("/sys/fs/cgroup") / group.lstrip("/") / "cgroup.events"
    try:
        data = path.read_text(encoding="ascii")
    except FileNotFoundError:
        # A removed cgroup cannot still own tasks.
        return True
    except OSError:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE) from None
    rows = dict(line.split(" ", 1) for line in data.splitlines() if " " in line)
    if rows.get("populated") not in {"0", "1"}:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    return rows["populated"] == "0"


class LinuxOwnedProcess:
    """Retain the guardian's kernel PIDFD until the unit has been stopped."""

    def __init__(self, *, pid: int, pidfd: int) -> None:
        """Retain one noninherited kernel handle for the exact guardian."""
        self.pid = pid
        self._pidfd = pidfd

    def wait(self, *, timeout: float) -> int:
        """Wait for the exact guardian without reopening a reusable PID."""
        if sys.platform == "linux":
            if self._pidfd < 0 or timeout < 0:
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            poller = select.poll()
            poller.register(self._pidfd, select.POLLIN | select.POLLERR | select.POLLHUP)
            if not poller.poll(min(2_147_483_647, int(timeout * 1000))):
                raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
            return 0
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)

    def close(self) -> None:
        """Release the kernel handle after its service has settled."""
        if self._pidfd >= 0:
            os.close(self._pidfd)
            self._pidfd = -1

    @property
    def alive(self) -> bool:
        """Observe the held guardian without treating a PID as a capability."""
        return self._pidfd >= 0 and _pidfd_alive(self._pidfd)


class LinuxProcessScope:
    """A transient user service whose guardian exit kills the entire cgroup.

    The worker and ordinary fork/setsid descendants remain within the service
    cgroup. The guardian is MainPID and watches the runtime parent's PIDFD.
    Killing the guardian also triggers systemd's control-group termination.
    """

    _lock: Lock
    _unit: str
    _worker_script: Path | None

    def __init__(self, *, worker_id: UUID, worker_script: Path | None = None) -> None:
        """Reserve an unguessable unit identity without launching any child."""
        if sys.platform != "linux":
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        selected = validated_worker_arguments(worker_script=worker_script)
        self._worker_script = Path(selected[1]) if worker_script is not None else None
        self._unit = f"cadrumo-worker-{worker_id.hex}.service"
        self._lock = Lock()
        self._guardian: LinuxOwnedProcess | None = None
        self._started = False
        self._worker_pid = 0
        self._worker_pidfd = -1
        self._cgroup = ""

    def launch(
        self, *, executable: Path, arguments: Sequence[str], directory: Path, environment: Mapping[str, str]
    ) -> LinuxOwnedProcess:
        """Register systemd containment before its first child executes code."""
        arguments, directory = _validated_launch_inputs(self, executable, arguments, directory, environment)
        command = _guardian_launch_command(self, executable, arguments, directory, environment)
        # A lost manager acknowledgement may still have started this exact
        # unit. Retain the stop obligation before asking the manager.
        self._started = True
        result = run_manager_command_sync(NativeManagerCommand.SYSTEMD_RUN, command)
        if result.returncode != 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        return _wait_for_guardian(self)

    def verify_worker(self, channel: PosixRuntimeChannel, *, owner_id: str) -> int:
        """Pin the socket peer and cgroup before worker identity or key release."""
        pid = _validated_worker_peer(self, channel, owner_id)
        with channel.capture_peer_pidfd() as pidfd:
            if not _worker_pidfd_matches_cgroup(self, pidfd, pid):
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            _retain_worker_pidfd(self, pidfd, pid)
        return pid

    def owns_process(self, pid: int) -> bool:
        """Require the retained worker and guardian to remain live in this cgroup."""
        with self._lock:
            return (
                pid == self._worker_pid
                and self._worker_pidfd >= 0
                and _pidfd_alive(self._worker_pidfd)
                and self._guardian is not None
                and self._guardian.alive
                and _cgroup_for(pid) == self._cgroup
            )

    @property
    def worker_pid(self) -> int:
        """Return the verified worker PID for a fresh custody health check."""
        return self._worker_pid

    def active_process_ids(self) -> tuple[int, ...]:
        """Expose only the verified live worker to the authorization channel."""
        return (self._worker_pid,) if self.owns_process(self._worker_pid) else ()

    def terminate(self, *, timeout: float = 2.0) -> None:
        """Stop the verified unit and observe worker/guardian death, retaining failure."""
        if not self._started:
            return
        response = run_manager_command_sync(
            NativeManagerCommand.SYSTEMCTL,
            ("--user", "--no-pager", "--no-ask-password", "stop", self._unit),
        )
        if response.returncode != 0 and not _failed_stop_is_settled(self):
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        _wait_for_unit_settlement(self, timeout)


def _validated_launch_inputs(
    scope: LinuxProcessScope,
    executable: Path,
    arguments: Sequence[str],
    directory: Path,
    environment: Mapping[str, str],
) -> tuple[tuple[str, ...], Path]:
    if scope._guardian is not None or not executable.is_absolute() or not directory.is_absolute():
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    selected_arguments = validated_worker_arguments(arguments, worker_script=scope._worker_script)
    from ...core.config import Settings

    baseline = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "PYDANTIC_DISABLE_PLUGINS": "__all__"}
    allowed_storage = Settings.storage_env_var_names() | {"TEMP", "TMP", "TMPDIR"}
    extras = set(environment) - set(baseline)
    if any(environment.get(name) != value for name, value in baseline.items()) or not extras <= allowed_storage:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    # Keep the venv interpreter path: resolving its symlink changes Python's
    # pyvenv.cfg discovery and can launch without the installed package.
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    return selected_arguments, directory.resolve(strict=True)


def _guardian_launch_command(
    scope: LinuxProcessScope,
    executable: Path,
    arguments: tuple[str, ...],
    directory: Path,
    environment: Mapping[str, str],
) -> tuple[str, ...]:
    parent_pid = os.getpid()
    start_identity = linux_process_start_identity(parent_pid)
    # `env -i` gives the guardian and worker an explicit noncredential
    # environment, independently of the user manager's inherited state.
    clean = tuple(f"{name}={value}" for name, value in sorted(environment.items()))
    script_selection = ("--worker-script", str(scope._worker_script)) if scope._worker_script is not None else ()
    return (
        "--user",
        "--no-pager",
        "--no-ask-password",
        "--no-block",
        "--collect",
        "--expand-environment=no",
        "--service-type=exec",
        f"--unit={scope._unit}",
        f"--working-directory={directory}",
        "--property=KillMode=control-group",
        "--property=ExitType=main",
        "--property=SendSIGKILL=yes",
        "--property=TimeoutStopSec=1s",
        "--property=Restart=no",
        "--property=StandardOutput=null",
        "--property=StandardError=null",
        "/usr/bin/env",
        "-i",
        *clean,
        str(executable),
        "-I",
        "-m",
        "cadrumo.entrypoints.runtime.linux_worker_guardian",
        "--parent-pid",
        str(parent_pid),
        "--parent-start",
        start_identity,
        *script_selection,
        "--",
        *arguments,
    )


def _wait_for_guardian(scope: LinuxProcessScope) -> LinuxOwnedProcess:
    deadline = time.monotonic() + 5
    while True:
        facts = _unit_properties(scope._unit)
        if _valid_guardian_service(facts) and _valid_guardian_identity(facts, scope._unit):
            guardian = _retain_guardian(scope, facts)
            if guardian is not None:
                return guardian
        if time.monotonic() >= deadline:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        time.sleep(0.05)


def _valid_guardian_service(facts: Mapping[str, str]) -> bool:
    return (
        facts["ActiveState"] == "active"
        and facts["Type"] == "exec"
        and facts["ExitType"] == "main"
        and facts["KillMode"] == "control-group"
        and facts["SendSIGKILL"] == "yes"
        and facts["TimeoutStopUSec"] == "1s"
        and facts["Restart"] == "no"
        and facts["StandardOutput"] == "null"
        and facts["StandardError"] == "null"
    )


def _valid_guardian_identity(facts: Mapping[str, str], unit: str) -> bool:
    return (
        facts["MainPID"].isdecimal()
        and int(facts["MainPID"]) > 0
        and facts["ControlGroup"].startswith("/")
        and facts["ControlGroup"].endswith("/" + unit)
    )


def _retain_guardian(scope: LinuxProcessScope, facts: Mapping[str, str]) -> LinuxOwnedProcess | None:
    pid = int(facts["MainPID"])
    pidfd = open_linux_pidfd(pid)
    try:
        if _pidfd_alive(pidfd) and _cgroup_for(pid) == facts["ControlGroup"]:
            scope._cgroup = facts["ControlGroup"]
            scope._guardian = LinuxOwnedProcess(pid=pid, pidfd=pidfd)
            return scope._guardian
    finally:
        if scope._guardian is None:
            os.close(pidfd)
    return None


def _validated_worker_peer(scope: LinuxProcessScope, channel: PosixRuntimeChannel, owner_id: str) -> int:
    pid = channel.peer.process_id
    if scope._guardian is None or not scope._cgroup or not scope._guardian.alive:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    if pid is None or channel.peer.os_owner_id != owner_id or owner_id != str(posix_owner_uid()):
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    return pid


def _worker_pidfd_matches_cgroup(scope: LinuxProcessScope, pidfd: int, pid: int) -> bool:
    guardian = scope._guardian
    return guardian is not None and _pidfd_alive(pidfd) and _cgroup_for(pid) == scope._cgroup and pid != guardian.pid


def _retain_worker_pidfd(scope: LinuxProcessScope, pidfd: int, pid: int) -> None:
    held = os.dup(pidfd)
    with scope._lock:
        if scope._worker_pid and scope._worker_pid != pid:
            os.close(held)
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        if scope._worker_pidfd >= 0:
            os.close(scope._worker_pidfd)
        scope._worker_pid, scope._worker_pidfd = pid, held


def _failed_stop_is_settled(scope: LinuxProcessScope) -> bool:
    return (
        _unit_absent(scope._unit)
        and (scope._guardian is None or not scope._guardian.alive)
        and (scope._worker_pidfd < 0 or not _pidfd_alive(scope._worker_pidfd))
    )


def _wait_for_unit_settlement(scope: LinuxProcessScope, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _unit_is_settled(scope):
            _release_worker_authority(scope)
            return
        time.sleep(0.01)
    raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)


def _unit_is_settled(scope: LinuxProcessScope) -> bool:
    guardian_dead = scope._guardian is None or not scope._guardian.alive
    worker_dead = scope._worker_pidfd < 0 or not _pidfd_alive(scope._worker_pidfd)
    return worker_dead and guardian_dead and (not scope._cgroup or _cgroup_empty(scope._cgroup))


def _release_worker_authority(scope: LinuxProcessScope) -> None:
    if scope._worker_pidfd >= 0:
        os.close(scope._worker_pidfd)
        scope._worker_pidfd = -1
    scope._worker_pid = 0
    if scope._guardian is not None:
        scope._guardian.close()
        scope._guardian = None
    scope._started = False
