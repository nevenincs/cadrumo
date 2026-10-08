"""Finite native Windows trees with exact incarnation and inheritance records."""

import asyncio
import os
import site
import subprocess
import sys
import time
from pathlib import Path
from threading import Event, Timer

import pydantic
from pydantic import BaseModel

from cadrumo.core.async_cleanup import close_async_resources
from cadrumo.core.models import STRICT_FROZEN_CONFIG

from ..windows import WindowsRuntimeEndpoint
from ..windows_process import WindowsProcessScope
from .process_support import fixture_arguments, fixture_environment, native_python

_MODULE = "cadrumo.adapters.local_runtime.tests.windows_inheritance_fixture"


class WindowsProcessIncarnation(BaseModel):
    """An observation identity, never a process termination capability."""

    model_config = STRICT_FROZEN_CONFIG

    pid: int
    created: str


class WindowsHandleProbe(BaseModel):
    """Native handle lookup and attempted event signaling by a controlled child."""

    model_config = STRICT_FROZEN_CONFIG

    process: WindowsProcessIncarnation
    handle_flags: int | None
    lookup_error: int
    signal_error: int


class WindowsTreeMember(BaseModel):
    """A fixed fixture role and the native object that executed it."""

    model_config = STRICT_FROZEN_CONFIG

    process: WindowsProcessIncarnation
    parent: int
    in_job_at_start: bool


class WindowsJobSnapshot(BaseModel):
    """Exact test-owned Job membership verified while every member is held live."""

    model_config = STRICT_FROZEN_CONFIG

    owner: WindowsProcessIncarnation
    members: tuple[WindowsTreeMember, ...]
    root_exited: bool
    job_inheritable: bool
    owner_inheritable: bool
    process_inheritable: bool
    thread_inheritable: bool


def _incarnation() -> WindowsProcessIncarnation:
    import win32api
    import win32process

    return WindowsProcessIncarnation(
        pid=os.getpid(),
        created=win32process.GetProcessTimes(win32api.GetCurrentProcess())["CreationTime"].isoformat(),
    )


def _publish(path: Path, record: BaseModel) -> None:
    pending = path.with_suffix(".pending")
    pending.write_text(record.model_dump_json(), encoding="utf-8")
    pending.replace(path)


def _probe(path: Path, sentinel: int) -> None:
    import pywintypes
    import win32api
    import win32event

    flags, lookup_error, signal_error = None, 0, 0
    try:
        flags = win32api.GetHandleInformation(sentinel)
    except pywintypes.error as error:
        lookup_error = error.winerror
    try:
        win32event.SetEvent(sentinel)
    except pywintypes.error as error:
        signal_error = error.winerror
    _publish(
        path,
        WindowsHandleProbe(
            process=_incarnation(), handle_flags=flags, lookup_error=lookup_error, signal_error=signal_error
        ),
    )


def _detached_creation_flags() -> int:
    if sys.platform == "win32":
        return subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    raise RuntimeError("requires native Windows")


def _wait_for_record(path: Path) -> WindowsTreeMember:
    deadline = time.monotonic() + 12
    while not path.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError("synthetic tree did not acknowledge its contained start")
        time.sleep(0.01)
    return WindowsTreeMember.model_validate_json(path.read_bytes())


async def _tree(directory: Path, role: str, *, exit_root: bool) -> None:
    if sys.platform != "win32":
        raise RuntimeError("Windows inheritance fixtures require Windows")
    import win32api
    import win32job

    _publish(
        directory / f"{role}.json",
        WindowsTreeMember(
            process=_incarnation(),
            parent=os.getppid(),
            in_job_at_start=win32job.IsProcessInJob(win32api.GetCurrentProcess(), 0),
        ),
    )
    child: asyncio.subprocess.Process | None = None
    try:
        if role != "leaf":
            next_role = "middle" if role == "root" else "leaf"
            child = await asyncio.create_subprocess_exec(
                str(native_python().with_name("pythonw.exe")),
                *fixture_arguments(_MODULE, "tree", str(directory), next_role, "stay"),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=fixture_environment(),
                close_fds=True,
                creationflags=_detached_creation_flags(),
            )
            await asyncio.to_thread(_wait_for_record, directory / "leaf.json")
            if exit_root and role == "root":
                os._exit(0)
        while not (directory / "release").exists():
            await asyncio.sleep(0.02)
    finally:
        if child is not None:
            if child.returncode is None:
                child.kill()
            await asyncio.wait_for(child.wait(), timeout=5)


def _snapshot(
    scope: WindowsProcessScope, *, directory: Path, owner_handle: int, root_exited: bool
) -> WindowsJobSnapshot:
    import win32api
    import win32event
    import win32job
    import win32process

    records = tuple(_wait_for_record(directory / f"{role}.json") for role in ("root", "middle", "leaf"))
    root, middle, leaf = records
    assert root.parent == os.getpid()
    assert middle.parent == root.process.pid and leaf.parent == middle.process.pid
    assert all(member.in_job_at_start for member in records)
    members = records[1:] if root_exited else records
    expected = {member.process.pid for member in members}
    # Every role is known independently. An enumeration error or omission
    # cannot shrink the population for which this fixture claims containment.
    actual = set(scope.active_process_ids())
    assert actual == expected, f"exact synthetic members differ: actual={sorted(actual)}, expected={sorted(expected)}"
    job = scope._job
    assert job is not None
    for member in members:
        handle = win32api.OpenProcess(0x100000 | 0x1000, False, member.process.pid)
        try:
            assert win32event.WaitForSingleObject(handle, 0) == win32event.WAIT_TIMEOUT
            assert win32job.IsProcessInJob(handle, job)
            assert win32process.GetProcessTimes(handle)["CreationTime"].isoformat() == member.process.created
        finally:
            win32api.CloseHandle(handle)
    process = scope._children[0]
    assert process._handle is not None and process._thread_handle is not None
    return WindowsJobSnapshot(
        owner=_incarnation(),
        members=members,
        root_exited=root_exited,
        job_inheritable=bool(win32api.GetHandleInformation(job) & 1),
        owner_inheritable=bool(win32api.GetHandleInformation(owner_handle) & 1),
        process_inheritable=bool(win32api.GetHandleInformation(process._handle) & 1),
        thread_inheritable=bool(win32api.GetHandleInformation(process._thread_handle) & 1),
    )


def _owner(directory: Path, *, exit_root: bool) -> None:
    import win32api

    from .profile_worker_support import NativeRuntimeFixtureOwner

    endpoint = WindowsRuntimeEndpoint(storage_root=directory)
    cleanup = NativeRuntimeFixtureOwner(endpoint, Event(), timeout=10)
    owner_handles: list[int] = []
    try:
        endpoint.listen()
        scope = WindowsProcessScope()
        cleanup.after_drain = scope
        owner_handle = win32api.OpenProcess(0x100000 | 0x1000, False, os.getpid())
        owner_handles.append(owner_handle)
        print(_incarnation().model_dump_json(), flush=True)
        # Console interpreters introduce kernel-created console hosts. Use
        # the native windowless interpreter for this independently counted
        # tree, so an unknown helper cannot be dropped from its death proof.
        process = scope.launch(
            executable=native_python().with_name("pythonw.exe"),
            arguments=fixture_arguments(_MODULE, "tree", str(directory), "root", "exit" if exit_root else "stay"),
            directory=directory,
            environment=fixture_environment(),
        )
        _wait_for_record(directory / "leaf.json")
        if exit_root:
            assert process.wait(timeout=5) == 0
        for command in sys.stdin:
            if command == "snapshot\n":
                print(
                    _snapshot(
                        scope, directory=directory, owner_handle=int(owner_handle), root_exited=exit_root
                    ).model_dump_json(),
                    flush=True,
                )
            elif command == "stop\n":
                return
            else:
                raise ValueError("unknown synthetic owner command")
    finally:
        primary = sys.exception()
        try:
            asyncio.run(close_async_resources(cleanup, task_name="windows-tree-fixture-close", primary_error=primary))
        finally:
            for handle in owner_handles:
                win32api.CloseHandle(handle)


def main() -> None:
    """Make crash fixtures finite even if their observing test is interrupted."""
    if sys.platform != "win32":
        raise RuntimeError("requires native Windows")
    # Nested base-interpreter children retain the configured dependencies in
    # PYTHONPATH; their sysconfig points at the base installation. Re-run the
    # loaded environment's site hooks before importing native extension DLLs.
    site.addsitedir(str(Path(pydantic.__file__).resolve().parent.parent))
    lifetime = Timer(60, os._exit, args=(124,))
    lifetime.daemon = True
    lifetime.start()
    try:
        mode, *arguments = sys.argv[1:]
        if mode == "probe":
            path, sentinel = arguments
            _probe(Path(path), int(sentinel))
        elif mode == "owner":
            directory, behavior = arguments
            _owner(Path(directory), exit_root=behavior == "exit")
        elif mode == "tree":
            directory, role, behavior = arguments
            asyncio.run(_tree(Path(directory), role, exit_root=behavior == "exit"))
        elif mode == "unrelated":
            print(_incarnation().model_dump_json(), flush=True)
            sys.stdin.readline()
        else:
            raise ValueError("unknown synthetic fixture mode")
    finally:
        lifetime.cancel()


if __name__ == "__main__":
    main()
