"""Systemd MainPID watching one exact runtime parent and contained worker."""

from __future__ import annotations

import argparse
import os
import select
import subprocess
import sys
from pathlib import Path
from typing import Protocol

from ...adapters.local_runtime.linux_pidfd import open_linux_pidfd
from ...adapters.local_runtime.linux_worker_process import linux_process_start_identity
from ...adapters.local_runtime.worker_arguments import validated_worker_arguments
from ...application.runtime.contracts import RuntimeRefusalError


class _ParentPoll(Protocol):
    """Kernel exit events consumed by the Linux guardian."""

    def poll(self, timeout: int, /) -> list[tuple[int, int]]:
        """Read pending parent exit events within the bounded wait."""
        ...


def _parse_arguments(arguments: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--parent-pid", type=int, required=True)
    parser.add_argument("--parent-start", required=True)
    parser.add_argument("--worker-script", type=Path)
    parser.add_argument("worker_arguments", nargs=argparse.REMAINDER)
    return parser.parse_args(arguments)


def _validated_arguments(options: argparse.Namespace) -> tuple[str, ...] | None:
    worker_arguments = options.worker_arguments
    if worker_arguments[:1] == ["--"]:
        worker_arguments = worker_arguments[1:]
    try:
        return validated_worker_arguments(worker_arguments, worker_script=options.worker_script)
    except RuntimeRefusalError:
        return None


def _open_parent(options: argparse.Namespace) -> tuple[Path, int] | None:
    if sys.platform != "linux":
        return None
    parent = Path("/proc") / str(options.parent_pid)
    try:
        if (
            parent.stat().st_uid != os.getuid()
            or linux_process_start_identity(options.parent_pid) != options.parent_start
        ):
            return None
        return parent, open_linux_pidfd(options.parent_pid)
    except (OSError, RuntimeRefusalError):
        return None


def _is_same_parent(options: argparse.Namespace, parent: Path, watcher: _ParentPoll) -> bool:
    if sys.platform != "linux":
        return False
    try:
        return (
            not watcher.poll(0)
            and parent.stat().st_uid == os.getuid()
            and linux_process_start_identity(options.parent_pid) == options.parent_start
            and not watcher.poll(0)
        )
    except (OSError, RuntimeRefusalError):
        return False


def _launch_worker(worker_arguments: tuple[str, ...]) -> subprocess.Popen[bytes] | None:
    from ...adapters.local_runtime.worker_environment import worker_path_environment_names

    environment = {
        "PATH": "/usr/bin:/bin",
        "LANG": "C",
        "LC_ALL": "C",
        "PYDANTIC_DISABLE_PLUGINS": "__all__",
    }
    path_names = worker_path_environment_names()
    environment.update({name: value for name, value in os.environ.items() if name in path_names})
    environment.update({name: os.environ[name] for name in ("TEMP", "TMP", "TMPDIR") if name in os.environ})
    try:
        return subprocess.Popen(  # noqa: S603 - fixed interpreter and verified worker arguments
            (sys.executable, *worker_arguments),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=environment,
            close_fds=True,
            start_new_session=True,
        )
    except OSError:
        return None


def _watch_worker(watcher: _ParentPoll, worker: subprocess.Popen[bytes]) -> int:
    while True:
        if watcher.poll(200):
            return 2
        code = worker.poll()
        if code is not None:
            return code


def _run_linux_guardian(options: argparse.Namespace) -> int:
    if sys.platform != "linux":
        return 2
    worker_arguments = _validated_arguments(options)
    if worker_arguments is None:
        return 2
    opened = _open_parent(options)
    if opened is None:
        return 2
    parent, descriptor = opened
    try:
        watcher = select.poll()
        watcher.register(descriptor, select.POLLIN | select.POLLERR | select.POLLHUP)
        # Recheck identity while holding the exact kernel process handle.
        if not _is_same_parent(options, parent, watcher):
            return 2
        worker = _launch_worker(worker_arguments)
        return 2 if worker is None else _watch_worker(watcher, worker)
    finally:
        os.close(descriptor)


def run(arguments: list[str] | None = None) -> int:
    """Exit on parent or worker loss; systemd then kills the whole service cgroup."""
    options = _parse_arguments(arguments)
    if sys.platform != "linux" or not sys.flags.isolated:
        return 2
    return _run_linux_guardian(options)


if __name__ == "__main__":
    raise SystemExit(run())
