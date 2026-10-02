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
from .posix import PosixRuntimeChannel, posix_owner_uid

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

_INSTALLED_WORKER_ARGUMENTS = ("-I", "-m", "cadrumo.entrypoints.runtime.worker")


def validated_linux_worker_arguments(
    arguments: Sequence[str] | None = None, *, worker_script: Path | None = None
) -> tuple[str, ...]:
    """Build or verify argv for the host's explicitly selected isolated worker.

    Script selection belongs to the trusted Python constructor. It is never
    inferred from worker arguments, client documents or the environment.
    """
    prefix: tuple[str, ...] = _INSTALLED_WORKER_ARGUMENTS
    if worker_script is not None:
        if not worker_script.is_absolute():
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        try:
            selected = worker_script.resolve(strict=True)
            if not selected.is_file():
                raise ValueError
        except (OSError, ValueError):
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE) from None
        prefix = ("-I", str(selected))
    if arguments is None:
        return prefix
    command = tuple(arguments)
    if command[: len(prefix)] != prefix or any("\0" in argument for argument in command):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    return command


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
        selected = validated_linux_worker_arguments(worker_script=worker_script)
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
        if self._guardian is not None or not executable.is_absolute() or not directory.is_absolute():
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        arguments = validated_linux_worker_arguments(arguments, worker_script=self._worker_script)
        if environment != {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "PYDANTIC_DISABLE_PLUGINS": "__all__"}:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        # Keep the venv interpreter path: resolving its symlink changes Python's
        # pyvenv.cfg discovery and can launch without the installed package.
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        directory = directory.resolve(strict=True)
        parent_pid = os.getpid()
        start_identity = linux_process_start_identity(parent_pid)
        # `env -i` gives the guardian and worker an explicit noncredential
        # environment, independently of the user manager's inherited state.
        clean = ("PATH=/usr/bin:/bin", "LANG=C", "LC_ALL=C", "PYDANTIC_DISABLE_PLUGINS=__all__")
        script_selection = ("--worker-script", str(self._worker_script)) if self._worker_script is not None else ()
        # A lost manager acknowledgement may still have started this exact
        # unit. Retain the stop obligation before asking the manager.
        self._started = True
        result = run_manager_command_sync(
            NativeManagerCommand.SYSTEMD_RUN,
            (
                "--user",
                "--no-pager",
                "--no-ask-password",
                "--no-block",
                "--collect",
                "--expand-environment=no",
                "--service-type=exec",
                f"--unit={self._unit}",
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
            ),
        )
        if result.returncode != 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        deadline = time.monotonic() + 5
        while True:
            facts = _unit_properties(self._unit)
            if (
                facts["ActiveState"] == "active"
                and facts["Type"] == "exec"
                and facts["ExitType"] == "main"
                and facts["KillMode"] == "control-group"
                and facts["SendSIGKILL"] == "yes"
                and facts["TimeoutStopUSec"] == "1s"
                and facts["Restart"] == "no"
                and facts["StandardOutput"] == "null"
                and facts["StandardError"] == "null"
                and facts["MainPID"].isdecimal()
                and int(facts["MainPID"]) > 0
                and facts["ControlGroup"].startswith("/")
                and facts["ControlGroup"].endswith("/" + self._unit)
            ):
                pid = int(facts["MainPID"])
                pidfd = open_linux_pidfd(pid)
                try:
                    if _pidfd_alive(pidfd) and _cgroup_for(pid) == facts["ControlGroup"]:
                        self._cgroup = facts["ControlGroup"]
                        self._guardian = LinuxOwnedProcess(pid=pid, pidfd=pidfd)
                        return self._guardian
                finally:
                    if self._guardian is None:
                        os.close(pidfd)
            if time.monotonic() >= deadline:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
            time.sleep(0.05)

    def verify_worker(self, channel: PosixRuntimeChannel, *, owner_id: str) -> int:
        """Pin the socket peer and cgroup before worker identity or key release."""
        pid = channel.peer.process_id
        if self._guardian is None or not self._cgroup or not self._guardian.alive:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        if pid is None or channel.peer.os_owner_id != owner_id or owner_id != str(posix_owner_uid()):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        with channel.capture_peer_pidfd() as pidfd:
            if not _pidfd_alive(pidfd) or _cgroup_for(pid) != self._cgroup or pid == self._guardian.pid:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            held = os.dup(pidfd)
            with self._lock:
                if self._worker_pid and self._worker_pid != pid:
                    os.close(held)
                    raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
                if self._worker_pidfd >= 0:
                    os.close(self._worker_pidfd)
                self._worker_pid, self._worker_pidfd = pid, held
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
        if response.returncode != 0 and not (
            _unit_absent(self._unit)
            and (self._guardian is None or not self._guardian.alive)
            and (self._worker_pidfd < 0 or not _pidfd_alive(self._worker_pidfd))
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            guardian_dead = self._guardian is None or not self._guardian.alive
            worker_dead = self._worker_pidfd < 0 or not _pidfd_alive(self._worker_pidfd)
            if worker_dead and guardian_dead and (not self._cgroup or _cgroup_empty(self._cgroup)):
                if self._worker_pidfd >= 0:
                    os.close(self._worker_pidfd)
                    self._worker_pidfd = -1
                self._worker_pid = 0
                if self._guardian is not None:
                    self._guardian.close()
                    self._guardian = None
                self._started = False
                return
            time.sleep(0.01)
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
