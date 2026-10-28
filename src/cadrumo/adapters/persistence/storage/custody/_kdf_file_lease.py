"""Kernel-signalled acquisition of the existing installation KDF file lock."""

from __future__ import annotations

import errno
import math
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

from .....application.user_profile.proof_cancellation import ProfileProofCancellation
from .....core.config import Settings, load_settings
from ._kdf_cancellation import kdf_cancellation_pipe
from ._kdf_codec import close_fd
from ._kdf_lease_worker import KDF_LEASE_ACQUIRED, KDF_LEASE_WAITING
from ._kdf_process import launch_lease_worker, terminate_process_tree
from ._kdf_refusals import resource_refusal, supervision_refusal

if sys.platform == "win32":
    import ctypes
    import msvcrt
    from ctypes import wintypes

    class _Overlapped(ctypes.Structure):
        _fields_ = [
            ("Internal", ctypes.c_size_t),
            ("InternalHigh", ctypes.c_size_t),
            ("Offset", wintypes.DWORD),
            ("OffsetHigh", wintypes.DWORD),
            ("hEvent", wintypes.HANDLE),
        ]

    def _kernel32() -> ctypes.CDLL:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.CreateEventW.restype = wintypes.HANDLE
        kernel.LockFileEx.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(_Overlapped),
        ]
        kernel.LockFileEx.restype = wintypes.BOOL
        kernel.UnlockFileEx.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(_Overlapped),
        ]
        kernel.UnlockFileEx.restype = wintypes.BOOL
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.WaitForMultipleObjects.argtypes = [
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        kernel.WaitForMultipleObjects.restype = wintypes.DWORD
        kernel.SetEvent.argtypes = [wintypes.HANDLE]
        kernel.SetEvent.restype = wintypes.BOOL
        kernel.CancelIoEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(_Overlapped)]
        kernel.CancelIoEx.restype = wintypes.BOOL
        kernel.GetOverlappedResult.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_Overlapped),
            ctypes.POINTER(wintypes.DWORD),
            wintypes.BOOL,
        ]
        kernel.GetOverlappedResult.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        return kernel

    def _open_windows_lease(path: Path) -> int:
        kernel = _kernel32()
        # Same byte-range lock domain as older msvcrt holders. Overlapped I/O
        # lets the kernel cue capacity and cancel a pending lock on timeout.
        handle = kernel.CreateFileW(str(path), 0xC0000000, 0x7, None, 4, 0x40000000, None)
        if handle in (None, ctypes.c_void_p(-1).value):
            raise supervision_refusal()
        try:
            return msvcrt.open_osfhandle(int(handle), os.O_RDWR | os.O_BINARY)
        except BaseException:
            kernel.CloseHandle(handle)
            raise

    def _unlock_windows_lease(descriptor: int) -> None:
        if not _kernel32().UnlockFileEx(msvcrt.get_osfhandle(descriptor), 0, 1, 0, ctypes.byref(_Overlapped())):
            raise supervision_refusal()

    @contextmanager
    def _windows_cancel_event(kernel: ctypes.CDLL, cancellation: ProfileProofCancellation) -> Generator[int]:
        event = kernel.CreateEventW(None, True, False, None)
        if not event:
            raise supervision_refusal()
        try:

            def wake() -> None:
                if not kernel.SetEvent(event):
                    raise supervision_refusal()

            with cancellation.watch(wake):
                yield int(event)
        finally:
            kernel.CloseHandle(event)

    def _wait_windows_completion(
        kernel: ctypes.CDLL, event: int, *, deadline: float, cancellation: ProfileProofCancellation | None
    ) -> int:
        remaining = deadline - time.monotonic()
        milliseconds = min(0xFFFFFFFE, max(0, math.ceil(remaining * 1000)))
        if cancellation is None:
            return int(kernel.WaitForSingleObject(event, milliseconds))
        with _windows_cancel_event(kernel, cancellation) as cancelled:
            cancellation.raise_if_cancelled()
            handles = (wintypes.HANDLE * 2)(event, cancelled)
            waited = int(kernel.WaitForMultipleObjects(2, handles, False, milliseconds))
            cancellation.raise_if_cancelled()
            return waited

    def _acquire_windows_lease(
        descriptor: int, *, deadline: float, cancellation: ProfileProofCancellation | None
    ) -> None:
        kernel = _kernel32()
        handle = msvcrt.get_osfhandle(descriptor)
        event = kernel.CreateEventW(None, True, False, None)
        if not event:
            raise supervision_refusal()
        overlapped = _Overlapped(hEvent=event)
        pending = False
        acquired = False
        try:
            if cancellation is not None:
                cancellation.raise_if_cancelled()
            if deadline <= time.monotonic():
                raise resource_refusal()
            acquired = bool(kernel.LockFileEx(handle, 2, 0, 1, 0, ctypes.byref(overlapped)))
            if not acquired:
                if ctypes.get_last_error() != 997:  # ERROR_IO_PENDING
                    raise supervision_refusal()
                pending = True
                waited = _wait_windows_completion(kernel, int(event), deadline=deadline, cancellation=cancellation)
                if waited != 0:
                    if waited == 258:  # WAIT_TIMEOUT
                        raise resource_refusal()
                    raise supervision_refusal()
                transferred = wintypes.DWORD()
                acquired = bool(
                    kernel.GetOverlappedResult(handle, ctypes.byref(overlapped), ctypes.byref(transferred), True)
                )
                pending = False
                if not acquired:
                    raise supervision_refusal()
            if time.monotonic() >= deadline:
                raise resource_refusal()
            if cancellation is not None:
                cancellation.raise_if_cancelled()
        except BaseException:
            if pending:
                # Cancellation is a request, so join its completion before the
                # OVERLAPPED/event storage goes away. Success can race timeout.
                kernel.CancelIoEx(handle, ctypes.byref(overlapped))
                transferred = wintypes.DWORD()
                acquired = bool(
                    kernel.GetOverlappedResult(handle, ctypes.byref(overlapped), ctypes.byref(transferred), True)
                )
                if not acquired and ctypes.get_last_error() != 995:  # ERROR_OPERATION_ABORTED
                    raise supervision_refusal() from None
            if acquired:
                _unlock_windows_lease(descriptor)
            raise
        finally:
            kernel.CloseHandle(event)


def open_kdf_file_lease(path: Path) -> int:
    """Open the canonical coordination file without changing its lock identity."""
    if sys.platform == "win32":
        return _open_windows_lease(path)
    return os.open(path, os.O_RDWR | os.O_CREAT, 0o600)


def acquire_kdf_file_lease(
    descriptor: int,
    *,
    deadline: float,
    settings: Settings | None = None,
    cancellation: ProfileProofCancellation | None = None,
) -> None:
    """Wait for kernel capacity, with an owned operation timeout."""
    if not math.isfinite(deadline):
        raise ValueError("profile KDF lease deadline must be finite")
    if cancellation is not None:
        cancellation.raise_if_cancelled()
    try:
        if sys.platform == "win32":
            _acquire_windows_lease(descriptor, deadline=deadline, cancellation=cancellation)
        else:
            _acquire_posix_lease(descriptor, deadline=deadline, settings=settings, cancellation=cancellation)
    except (OSError, subprocess.SubprocessError):
        raise supervision_refusal() from None


def release_kdf_file_lease(descriptor: int) -> None:
    """Release the same byte range/flock that old and current owners share."""
    try:
        if sys.platform == "win32":
            _unlock_windows_lease(descriptor)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_UN)
    except OSError:
        raise supervision_refusal() from None


def wait_for_kdf_process_exit(
    process: subprocess.Popen[bytes], *, deadline: float, cancellation: ProfileProofCancellation | None = None
) -> int:
    """Wait on process exit or the exact proof owner's cancellation signal."""
    if sys.platform == "win32":
        kernel = _kernel32()
        handle = int(cast(Any, process)._handle)
        waited = _wait_windows_completion(kernel, handle, deadline=deadline, cancellation=cancellation)
        if waited == 258:
            raise resource_refusal()
        if waited != 0:
            raise supervision_refusal()
        return process.wait()
    return _await_posix_helper_exit(process, deadline=deadline, cancellation=cancellation)


def _await_posix_helper_exit(
    process: subprocess.Popen[bytes], *, deadline: float, cancellation: ProfileProofCancellation | None = None
) -> int:
    with kdf_cancellation_pipe(cancellation) as cancelled:
        return _await_posix_exit_signal(process, deadline=deadline, cancellation=cancellation, cancelled=cancelled)


def _await_posix_exit_signal(
    process: subprocess.Popen[bytes],
    *,
    deadline: float,
    cancellation: ProfileProofCancellation | None,
    cancelled: int | None,
) -> int:
    """Observe process exit in the kernel before performing the owned waitpid reap."""
    import select

    if cancellation is not None:
        cancellation.raise_if_cancelled()
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise resource_refusal()
    if sys.platform == "linux":
        try:
            process_fd = os.pidfd_open(process.pid)
        except ProcessLookupError:
            result = process.poll()
            if result is None:
                raise supervision_refusal() from None
            return result
        try:
            watched = [process_fd] if cancelled is None else [process_fd, cancelled]
            ready = select.select(watched, [], [], remaining)[0]
            if cancellation is not None:
                cancellation.raise_if_cancelled()
            if process_fd not in ready:
                raise resource_refusal()
        finally:
            close_fd(process_fd)
    elif sys.platform == "darwin":
        events = select.kqueue()
        try:
            exited = select.kevent(
                process.pid,
                filter=select.KQ_FILTER_PROC,
                flags=select.KQ_EV_ADD | select.KQ_EV_ONESHOT,
                fflags=select.KQ_NOTE_EXIT,
            )
            try:
                subscriptions = [exited]
                if cancelled is not None:
                    subscriptions.append(select.kevent(cancelled, filter=select.KQ_FILTER_READ, flags=select.KQ_EV_ADD))
                ready = events.control(subscriptions, 1, remaining)
                if cancellation is not None:
                    cancellation.raise_if_cancelled()
                if not ready:
                    raise resource_refusal()
                notification = ready[0]
                if notification.flags & select.KQ_EV_ERROR:
                    if notification.data == errno.ESRCH:
                        raise ProcessLookupError(errno.ESRCH, "profile KDF lease helper already exited")
                    raise supervision_refusal()
                if (
                    notification.ident != process.pid
                    or notification.filter != select.KQ_FILTER_PROC
                    or not notification.fflags & select.KQ_NOTE_EXIT
                ):
                    raise supervision_refusal()
            except ProcessLookupError:
                result = process.poll()
                if result is None:
                    raise supervision_refusal() from None
                return result
        finally:
            events.close()
    else:
        raise supervision_refusal()
    # pidfd/NOTE_EXIT proves the child has ended, so this reap cannot turn
    # into an unbounded wait or Popen's timeout-based waitpid retry loop.
    return process.wait()


def _acquire_posix_lease(
    descriptor: int,
    *,
    deadline: float,
    settings: Settings | None,
    cancellation: ProfileProofCancellation | None,
) -> None:
    """A reaped, secret-free helper blocks in flock on this inherited description.

    On success its exit leaves the lease held by the parent's shared open
    description. While blocked, owner-pipe EOF terminates it even if its
    parent is killed; the parent otherwise contains and reaps it on timeout.
    """
    import select

    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise resource_refusal()
    # Avoid launching an interpreter for uncontended capacity. This is one
    # immediate probe, followed by a blocking kernel waiter, never polling.
    import fcntl

    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return
    except BlockingIOError:
        pass
    temporary_root = (settings or load_settings()).cadrumo_temp_dir
    temporary_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (
        tempfile.TemporaryDirectory(prefix="cadrumo-kdf-lease-", dir=temporary_root) as directory,
        kdf_cancellation_pipe(cancellation) as cancelled,
    ):
        owner_read, owner_write = os.pipe()
        try:
            result_read, result_write = os.pipe()
        except BaseException:
            close_fd(owner_read)
            close_fd(owner_write)
            raise
        process: subprocess.Popen[bytes] | None = None
        try:
            neutral_root = Path(directory)
            process = launch_lease_worker(
                neutral_root=neutral_root, lease_fd=descriptor, owner_fd=owner_read, result_fd=result_write
            )
            close_fd(owner_read)
            owner_read = -1
            close_fd(result_write)
            result_write = -1
            for cue in (KDF_LEASE_WAITING, KDF_LEASE_ACQUIRED):
                if cancellation is not None:
                    cancellation.raise_if_cancelled()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise resource_refusal()
                watched = [result_read] if cancelled is None else [result_read, cancelled]
                ready = select.select(watched, [], [], remaining)[0]
                if cancellation is not None:
                    cancellation.raise_if_cancelled()
                if result_read not in ready:
                    raise resource_refusal()
                if os.read(result_read, 1) != cue:
                    raise supervision_refusal()
            if (
                _await_posix_helper_exit(process, deadline=deadline, cancellation=cancellation) != 0
                or os.read(result_read, 1) != b""
            ):
                raise supervision_refusal()
            if time.monotonic() >= deadline:
                raise resource_refusal()
            if cancellation is not None:
                cancellation.raise_if_cancelled()
        except BaseException:
            close_fd(owner_write)
            owner_write = -1
            if process is not None:
                terminate_process_tree(process, None)
                if process.returncode is None:
                    raise supervision_refusal() from None
            # The helper may have acquired just as timeout won. The parent's
            # shared description must not retain a lease after failed handoff.
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            raise
        finally:
            for pipe in (owner_read, owner_write, result_read, result_write):
                close_fd(pipe)


__all__ = ["acquire_kdf_file_lease", "open_kdf_file_lease", "release_kdf_file_lease", "wait_for_kdf_process_exit"]
