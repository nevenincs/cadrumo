"""Controlled inheritance and owner-loss observations before fallback cleanup."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import pytest

from cadrumo.core.async_cleanup import close_async_resources

from ..windows_process import WindowsProcessScope
from .process_support import fixture_arguments, fixture_environment, launch_fixture, native_python
from .windows_inheritance_fixture import WindowsHandleProbe, WindowsJobSnapshot, WindowsProcessIncarnation

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows Job inheritance"),
]

_MODULE = "cadrumo.adapters.local_runtime.tests.windows_inheritance_fixture"


def test_inheritable_sentinel_is_detected_in_control_and_absent_in_job_child(tmp_path: Path) -> None:
    import pywintypes
    import win32api
    import win32event

    attributes = pywintypes.SECURITY_ATTRIBUTES()
    attributes.bInheritHandle = True
    sentinel = win32event.CreateEvent(attributes, True, False, None)
    scopes: list[WindowsProcessScope] = []
    try:
        assert win32api.GetHandleInformation(sentinel) & 1
        control_path = tmp_path / "control.json"
        startup = subprocess.STARTUPINFO()
        startup.lpAttributeList = {"handle_list": [int(sentinel)]}

        # The same live event proves that the detector can see and exercise
        # an inherited handle; a failed probe alone is insufficient evidence.
        async def inherited_control() -> None:
            control = await asyncio.create_subprocess_exec(
                str(native_python()),
                *fixture_arguments(_MODULE, "probe", str(control_path), str(int(sentinel))),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
                startupinfo=startup,
                env=fixture_environment(),
                close_fds=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            try:
                _, errors = await asyncio.wait_for(control.communicate(), timeout=10)
                assert control.returncode == 0, errors.decode(errors="replace")
            finally:
                if control.returncode is None:
                    control.kill()
                    await asyncio.wait_for(control.wait(), timeout=5)

        asyncio.run(inherited_control())
        detected = WindowsHandleProbe.model_validate_json(control_path.read_bytes())
        assert detected.handle_flags is not None and detected.handle_flags & 1
        assert detected.lookup_error == detected.signal_error == 0
        assert win32event.WaitForSingleObject(sentinel, 0) == win32event.WAIT_OBJECT_0
        win32event.ResetEvent(sentinel)

        scope = WindowsProcessScope()
        scopes.append(scope)
        child_path = tmp_path / "contained.json"
        child = scope.launch(
            executable=native_python(),
            arguments=fixture_arguments(_MODULE, "probe", str(child_path), str(int(sentinel))),
            directory=tmp_path,
            environment=fixture_environment(),
        )
        assert child.wait(timeout=10) == 0
        absent = WindowsHandleProbe.model_validate_json(child_path.read_bytes())
        assert absent.process.pid == child.pid
        # A child can reuse the parent's numeric handle slot for a different
        # object. The event operation and unchanged original event establish
        # absence of this sentinel even when that slot is valid in the child.
        assert absent.handle_flags is None or absent.handle_flags & 1 == 0
        assert absent.lookup_error in (0, 6)
        assert absent.signal_error == 6  # ERROR_INVALID_HANDLE
        assert win32event.WaitForSingleObject(sentinel, 0) == win32event.WAIT_TIMEOUT
        assert win32api.GetHandleInformation(sentinel) & 1
    finally:
        try:
            for scope in scopes:
                scope.terminate()
        finally:
            win32api.CloseHandle(sentinel)


class _ObservedNativeFixture:
    """Retain exact native objects until death is observed and cleanup releases them."""

    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self.process = process
        self.handles: dict[int, int] = {}
        self.stderr: bytes | None = None

    def retain(self, identity: WindowsProcessIncarnation, *, terminate: bool = False) -> int:
        import win32api
        import win32event
        import win32process

        assert identity.pid not in self.handles
        handle = win32api.OpenProcess(0x100000 | 0x1000 | (1 if terminate else 0), False, identity.pid)
        self.handles[identity.pid] = handle
        assert win32api.GetHandleInformation(handle) & 1 == 0
        assert win32process.GetProcessTimes(handle)["CreationTime"].isoformat() == identity.created
        assert win32event.WaitForSingleObject(handle, 0) == win32event.WAIT_TIMEOUT
        return handle

    async def close(self) -> None:
        import win32api
        import win32event

        if self.stderr is None:
            if self.process.returncode is None:
                retained = self.handles.get(self.process.pid)
                if retained is not None:
                    if win32event.WaitForSingleObject(retained, 0) == win32event.WAIT_TIMEOUT:
                        win32api.TerminateProcess(retained, 124)
                else:
                    self.process.kill()
            _, self.stderr = await asyncio.wait_for(self.process.communicate(), timeout=10)
        for pid, handle in tuple(self.handles.items()):
            win32api.CloseHandle(handle)
            del self.handles[pid]


async def _snapshot(owner: _ObservedNativeFixture) -> WindowsJobSnapshot:
    assert owner.process.stdin is not None and owner.process.stdout is not None
    owner.process.stdin.write(b"snapshot\n")
    await owner.process.stdin.drain()
    encoded = await asyncio.wait_for(owner.process.stdout.readline(), timeout=20)
    if not encoded:
        assert owner.process.stderr is not None
        errors = await asyncio.wait_for(owner.process.stderr.read(), timeout=5)
        pytest.fail(errors.decode(errors="replace"))
    assert 0 < len(encoded) <= 8192
    return WindowsJobSnapshot.model_validate_json(encoded)


@pytest.mark.asyncio
@pytest.mark.parametrize("root_exits", [False, True])
async def test_owner_loss_stops_exact_job_tree_and_preserves_unrelated_process(
    tmp_path: Path, root_exits: bool
) -> None:
    import win32api
    import win32event

    directory = tmp_path / "owned-tree"
    directory.mkdir()
    owner = _ObservedNativeFixture(
        await launch_fixture(_MODULE, "owner", str(directory), "exit" if root_exits else "stay")
    )
    owners = [owner]
    try:
        assert owner.process.stdout is not None
        owner_identity = WindowsProcessIncarnation.model_validate_json(
            await asyncio.wait_for(owner.process.stdout.readline(), timeout=15)
        )
        assert owner_identity.pid == owner.process.pid
        owner_handle = owner.retain(owner_identity, terminate=True)
        first = await _snapshot(owner)
        assert first.owner == owner_identity and first.root_exited is root_exits
        assert len(first.members) == (2 if root_exits else 3)
        assert not any(
            (first.job_inheritable, first.owner_inheritable, first.process_inheritable, first.thread_inheritable)
        )
        assert all(member.in_job_at_start for member in first.members)
        member_handles = [owner.retain(member.process) for member in first.members]

        unrelated = _ObservedNativeFixture(await launch_fixture(_MODULE, "unrelated"))
        owners.append(unrelated)
        assert unrelated.process.stdout is not None
        unrelated_identity = WindowsProcessIncarnation.model_validate_json(
            await asyncio.wait_for(unrelated.process.stdout.readline(), timeout=15)
        )
        assert unrelated_identity.pid == unrelated.process.pid
        unrelated_handle = unrelated.retain(unrelated_identity, terminate=True)
        assert unrelated_identity.pid not in {member.process.pid for member in first.members}
        assert await _snapshot(owner) == first
        assert all(win32event.WaitForSingleObject(handle, 0) == win32event.WAIT_TIMEOUT for handle in member_handles)

        # Terminate only the retained owner incarnation. No descendant kill,
        # native-owner drain, release marker or fixture cleanup has run.
        win32api.TerminateProcess(owner_handle, 23)
        assert win32event.WaitForSingleObject(owner_handle, 5000) == win32event.WAIT_OBJECT_0
        await asyncio.wait_for(owner.process.wait(), timeout=5)
        assert all(
            win32event.WaitForSingleObject(handle, 5000) == win32event.WAIT_OBJECT_0 for handle in member_handles
        )
        assert win32event.WaitForSingleObject(unrelated_handle, 0) == win32event.WAIT_TIMEOUT
        assert not (directory / "release").exists()
        assert owner.stderr is None and unrelated.stderr is None
    finally:
        await close_async_resources(
            *owners,
            task_name="windows-observed-fixtures-close",
            primary_error=sys.exception(),
        )
    assert owner.stderr == b""
    unrelated = owners[1]
    assert unrelated.stderr == b""
    assert not owner.handles and not unrelated.handles
