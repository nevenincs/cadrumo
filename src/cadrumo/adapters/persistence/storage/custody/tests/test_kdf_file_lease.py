"""Same-domain KDF capacity signals, cancellation settlement and owner death."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest

from ......core.config import Settings
from .. import _kdf_file_lease as lease
from .._kdf_codec import close_fd
from .._kdf_lease_worker import KDF_LEASE_WAITING
from .._kdf_process import launch_lease_worker, terminate_process_tree
from ..errors import ProfileCustodyRefusal, ProfileCustodyRefusedError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BLOCKED_OWNER = """
import os
import sys
import threading
from pathlib import Path
from cadrumo.adapters.persistence.storage.custody._kdf_process import launch_lease_worker

root = Path(sys.argv[1])
lease = os.open(root / "profile-kdf.v1.lock", os.O_RDWR)
owner_read, owner_write = os.pipe()
result_read, result_write = os.pipe()
helper = launch_lease_worker(neutral_root=root, lease_fd=lease, owner_fd=owner_read, result_fd=result_write)
os.close(owner_read)
os.close(result_write)
assert os.read(result_read, 1) == b"W"
print(helper.pid, flush=True)
threading.Event().wait()
"""


def _old_lock(descriptor: int, *, acquire: bool) -> None:
    """An existing runtime uses precisely this unchanged OS lock domain."""
    if sys.platform == "win32":
        import msvcrt

        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_NBLCK if acquire else msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(descriptor, (fcntl.LOCK_EX | fcntl.LOCK_NB) if acquire else fcntl.LOCK_UN)


def test_kernel_wait_joins_the_same_lock_held_by_an_older_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "profile-kdf.v1.lock"
    old = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    os.write(old, b"\0")
    current = lease.open_kdf_file_lease(path)
    started = Event()
    if sys.platform == "win32":
        kernel = lease._kernel32()
        wait = kernel.WaitForSingleObject

        def waiting(handle: int, milliseconds: int) -> int:
            started.set()
            return wait(handle, milliseconds)

        kernel.WaitForSingleObject = waiting
        monkeypatch.setattr(lease, "_kernel32", lambda: kernel)
    else:
        launch = lease.launch_lease_worker

        def launching(*, neutral_root: Path, lease_fd: int, owner_fd: int, result_fd: int) -> subprocess.Popen[bytes]:
            process = launch(neutral_root=neutral_root, lease_fd=lease_fd, owner_fd=owner_fd, result_fd=result_fd)
            started.set()
            return process

        monkeypatch.setattr(lease, "launch_lease_worker", launching)
    _old_lock(old, acquire=True)
    try:

        def acquire() -> None:
            lease.acquire_kdf_file_lease(
                current, deadline=time.monotonic() + 10, settings=Settings(cadrumo_local_storage_root=tmp_path)
            )

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(acquire)
            assert started.wait(3)
            # A nonblocking probe still sees the legacy owner's lock, while
            # the current waiter remains pending until that owner releases.
            with pytest.raises(OSError):
                probe = os.open(path, os.O_RDWR)
                try:
                    _old_lock(probe, acquire=True)
                finally:
                    os.close(probe)
            assert not future.done()
            _old_lock(old, acquire=False)
            future.result(timeout=10)
        # The acquired lease outlives any helper used for the wait.
        probe = os.open(path, os.O_RDWR)
        try:
            with pytest.raises(OSError):
                _old_lock(probe, acquire=True)
        finally:
            os.close(probe)
        lease.release_kdf_file_lease(current)
        _old_lock(old, acquire=True)
        _old_lock(old, acquire=False)
    finally:
        os.close(current)
        os.close(old)


def test_timeout_settles_pending_kernel_lock_and_releases_no_late_lease(tmp_path: Path) -> None:
    path = tmp_path / "profile-kdf.v1.lock"
    old = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    os.write(old, b"\0")
    current = lease.open_kdf_file_lease(path)
    _old_lock(old, acquire=True)
    try:
        with pytest.raises(ProfileCustodyRefusedError) as captured:
            lease.acquire_kdf_file_lease(
                current, deadline=time.monotonic() + 0.1, settings=Settings(cadrumo_local_storage_root=tmp_path)
            )
        assert captured.value.refusal is ProfileCustodyRefusal.KDF_RESOURCE_LIMIT
        _old_lock(old, acquire=False)
        # A cancelled overlapped completion or helper must never acquire later
        # and hold capacity on behalf of the superseded login.
        probe = os.open(path, os.O_RDWR)
        try:
            _old_lock(probe, acquire=True)
            _old_lock(probe, acquire=False)
        finally:
            os.close(probe)
    finally:
        os.close(current)
        os.close(old)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows overlapped completion/cancellation race")
def test_windows_capacity_granted_as_timeout_wins_is_explicitly_unlocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if sys.platform != "win32":
        pytest.fail("Windows test selected on another OS")
    path = tmp_path / "profile-kdf.v1.lock"
    old = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    os.write(old, b"\0")
    current = lease.open_kdf_file_lease(path)
    _old_lock(old, acquire=True)
    kernel = lease._kernel32()
    wait = kernel.WaitForSingleObject

    def grant_at_timeout(handle: int, milliseconds: int) -> int:
        _old_lock(old, acquire=False)
        assert wait(handle, milliseconds) == 0
        # The real overlapped operation completed successfully, but its owner
        # has already chosen timeout. CancelIoEx cannot undo that successful lock.
        return 258

    kernel.WaitForSingleObject = grant_at_timeout
    monkeypatch.setattr(lease, "_kernel32", lambda: kernel)
    try:
        with pytest.raises(ProfileCustodyRefusedError) as captured:
            lease.acquire_kdf_file_lease(current, deadline=time.monotonic() + 5)
        assert captured.value.refusal is ProfileCustodyRefusal.KDF_RESOURCE_LIMIT
        _old_lock(old, acquire=True)
        _old_lock(old, acquire=False)
    finally:
        close_fd(current)
        close_fd(old)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX inherited-description flock helper")
def test_posix_helper_exits_when_its_only_owner_pipe_closes_while_capacity_is_held(tmp_path: Path) -> None:
    """Parent death wakes the helper even while its main thread blocks in flock."""
    if sys.platform == "win32":
        pytest.fail("POSIX test selected on Windows")
    import select

    path = tmp_path / "profile-kdf.v1.lock"
    old = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    current = lease.open_kdf_file_lease(path)
    owner_read, owner_write = os.pipe()
    result_read, result_write = os.pipe()
    helper: subprocess.Popen[bytes] | None = None
    _old_lock(old, acquire=True)
    try:
        helper = launch_lease_worker(
            neutral_root=tmp_path, lease_fd=current, owner_fd=owner_read, result_fd=result_write
        )
        close_fd(owner_read)
        owner_read = -1
        close_fd(result_write)
        result_write = -1
        assert select.select([result_read], [], [], 5)[0], "helper must install its owner-loss watcher"
        assert os.read(result_read, 1) == KDF_LEASE_WAITING
        assert helper.poll() is None
        close_fd(owner_write)
        owner_write = -1
        assert helper.wait(timeout=5) != 0
        assert os.read(result_read, 1) == b""
        _old_lock(old, acquire=False)
        # No orphan retained the shared description or acquired it after EOF.
        _old_lock(old, acquire=True)
        _old_lock(old, acquire=False)
    finally:
        if helper is not None and helper.poll() is None:
            terminate_process_tree(helper, None)
        for descriptor in (old, current, owner_read, owner_write, result_read, result_write):
            close_fd(descriptor)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux pidfd supplies exact descendant-exit evidence")
def test_killed_posix_owner_cannot_strand_a_blocked_helper_or_later_lease(tmp_path: Path) -> None:
    """A real owner's SIGKILL closes its sole writer and cues helper termination."""
    if sys.platform != "linux":
        pytest.fail("Linux test selected on another OS")
    import select

    path = tmp_path / "profile-kdf.v1.lock"
    old = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    _old_lock(old, acquire=True)

    async def kill_owner() -> None:
        owner = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            _BLOCKED_OWNER,
            str(tmp_path),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        helper_pidfd: int | None = None
        try:
            assert owner.stdout is not None
            helper_pid = int(await asyncio.wait_for(owner.stdout.readline(), timeout=30))
            helper_pidfd = os.pidfd_open(helper_pid)
            owner.kill()
            assert await asyncio.wait_for(owner.wait(), timeout=5) != 0
            assert select.select([helper_pidfd], [], [], 5)[0], "blocked helper survived its exact owner's death"
        finally:
            close_fd(helper_pidfd)
            if owner.returncode is None:
                owner.kill()
                await owner.wait()

    try:
        asyncio.run(kill_owner())
        _old_lock(old, acquire=False)
        _old_lock(old, acquire=True)
        _old_lock(old, acquire=False)
    finally:
        close_fd(old)
