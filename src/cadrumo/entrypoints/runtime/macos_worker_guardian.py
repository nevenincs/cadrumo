"""launchd job main watching one exact runtime parent and its contained worker."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from contextlib import suppress
from pathlib import Path
from typing import Protocol

from ...adapters.local_runtime.macos_coalition import read_macos_resource_coalition, terminate_macos_coalition
from ...adapters.local_runtime.macos_process import (
    MacosProcessIncarnation,
    MacosProcessWatch,
    read_macos_incarnation,
    read_macos_process,
)
from ...adapters.local_runtime.worker_arguments import validated_worker_arguments
from ...adapters.local_runtime.worker_environment import worker_path_environment_names
from ...application.runtime.contracts import RuntimeRefusalError

_CLEAN_ENVIRONMENT = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "PYDANTIC_DISABLE_PLUGINS": "__all__"}
_TERMINATION_SECONDS = 5.0
_POLL_SECONDS = 0.2


def _retire_coalition(coalition: int, own: MacosProcessIncarnation) -> bool:
    """Kill every other member of the guardian's coalition; False when emptiness is unproven."""
    try:
        terminate_macos_coalition(coalition, deadline=time.monotonic() + _TERMINATION_SECONDS, exclude=own)
    except RuntimeRefusalError:
        return False
    return True


class _Worker(Protocol):
    """Only the child's current exit code is consumed by the guardian watcher."""

    @property
    def returncode(self) -> int | None:
        """Return the child's code once its owning loop has reaped it."""
        ...


def _supervise(watch: MacosProcessWatch, worker: _Worker, coalition: int, own: MacosProcessIncarnation) -> int:
    """Wait for parent or worker exit, then empty the rest of the coalition."""
    while True:
        try:
            parent_lost = watch.wait(timeout=_POLL_SECONDS)
        except RuntimeRefusalError:
            parent_lost = True
        if parent_lost:
            _retire_coalition(coalition, own)
            return 2
        code = worker.returncode
        if code is not None:
            return code if _retire_coalition(coalition, own) else 2


async def _launch_and_supervise(
    watch: MacosProcessWatch,
    arguments: tuple[str, ...],
    environment: dict[str, str],
    coalition: int,
    own: MacosProcessIncarnation,
) -> int:
    """Keep the event loop reaping the worker while the native parent watch blocks elsewhere."""
    try:
        # Sharing the guardian's group keeps launchd's exit cleanup effective from creation.
        worker = await asyncio.create_subprocess_exec(
            sys.executable,
            *arguments,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            env=environment,
            close_fds=True,
        )
    except OSError:
        _retire_coalition(coalition, own)
        return 2
    try:
        return await asyncio.to_thread(_supervise, watch, worker, coalition, own)
    finally:
        if worker.returncode is None:
            await asyncio.to_thread(_retire_coalition, coalition, own)
        # The owning runtime retains the unproven coalition and its retirement marker.
        with suppress(TimeoutError):
            await asyncio.wait_for(worker.wait(), timeout=_TERMINATION_SECONDS)


def run(arguments: list[str] | None = None) -> int:
    """Kill the whole coalition on parent or worker loss, then exit.

    The worker shares this process group, so launchd's group kill on this
    exit also reaches it; regrouped descendants are reached through the
    coalition, which none of them can leave.
    """
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--parent-pid", type=int, required=True)
    parser.add_argument("--parent-version", type=int, required=True)
    parser.add_argument("--worker-script", type=Path)
    parser.add_argument("worker_arguments", nargs=argparse.REMAINDER)
    options = parser.parse_args(arguments)
    if sys.platform == "darwin":
        if not sys.flags.isolated:
            return 2
        worker_arguments = options.worker_arguments
        if worker_arguments[:1] == ["--"]:
            worker_arguments = worker_arguments[1:]
        try:
            worker_arguments = validated_worker_arguments(worker_arguments, worker_script=options.worker_script)
        except RuntimeRefusalError:
            return 2
        try:
            own = read_macos_incarnation(os.getpid())
            coalition = read_macos_resource_coalition(os.getpid())
            parent = read_macos_incarnation(options.parent_pid)
            parent_coalition = read_macos_resource_coalition(options.parent_pid)
            # launchd gave this job a fresh coalition; sharing the parent's
            # would make coalition termination reach the runtime itself.
            if (
                own is None
                or coalition is None
                or parent is None
                or parent_coalition is None
                or parent_coalition == coalition
                or parent.version != options.parent_version
            ):
                return 2
            watch = MacosProcessWatch(read_macos_process(options.parent_pid, expected_owner=str(os.getuid())))
        except RuntimeRefusalError:
            return 2
        try:
            # The PID may have been reused before the watch was registered.
            # Recheck the exact incarnation while holding the kernel exit filter.
            try:
                if watch.exited or read_macos_incarnation(options.parent_pid) != parent:
                    return 2
            except RuntimeRefusalError:
                return 2
            environment = dict(_CLEAN_ENVIRONMENT)
            allowed_paths = worker_path_environment_names()
            environment.update({name: value for name, value in os.environ.items() if name in allowed_paths})
            return asyncio.run(_launch_and_supervise(watch, tuple(worker_arguments), environment, coalition, own))
        finally:
            watch.close()
    return 2


if __name__ == "__main__":
    raise SystemExit(run())
