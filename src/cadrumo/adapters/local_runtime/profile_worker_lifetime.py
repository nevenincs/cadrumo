"""ProfileWorkerNativeLifetime for runtime-owned profile worker custody."""

from __future__ import annotations

import time
from threading import Event, RLock
from uuid import UUID

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.profile_worker import (
    ProfileWorkerIdentity,
)
from .linux_worker_process import LinuxOwnedProcess, LinuxProcessScope
from .windows_process import WindowsOwnedProcess, WindowsProcessScope
from .worker_authorization import WorkerAuthorizationServer
from .worker_native_identity import verify_worker_native_pid
from .worker_resource_cleanup import WorkerResourceCleanup, release_worker_resources
from .worker_transport import WorkerChannel

_WORKER_NATIVE_HEALTH_WAIT_SECONDS = 2.0


class ProfileWorkerNativeLifetime:
    """Own the worker capability while retaining native custody and deadlines."""

    identity: ProfileWorkerIdentity
    _lock: RLock
    _operation_lock: RLock
    _human_lock: RLock
    _native_guard: RLock
    _scope: WindowsProcessScope | LinuxProcessScope
    _process: WindowsOwnedProcess | LinuxOwnedProcess
    _authorization: WorkerAuthorizationServer | None
    _stopping: Event
    _channel: WorkerChannel | None
    _operation_channel: WorkerChannel | None
    _human_candidate: UUID | None
    _human_deadline: float | None
    _listener_cleanup: tuple[WorkerResourceCleanup, ...]
    _pending_channel_cleanup: list[WorkerResourceCleanup]

    def _require_process_alive(self) -> None:
        with self._native_guard:
            if self._stopping.is_set():
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            try:
                self._process.wait(timeout=0)
            except RuntimeRefusalError as error:
                if error.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED:
                    return
                raise
        raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)

    def _verify_native_peer(self, channel: WorkerChannel) -> int:
        with self._native_guard:
            if self._stopping.is_set():
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            return verify_worker_native_pid(channel, self._scope, self.identity.binding.os_owner_id)

    def _owns_native_process(self, process_id: int) -> bool:
        with self._native_guard:
            return not self._stopping.is_set() and process_id in self._scope.active_process_ids()

    def _contain_native_process(self, *, timeout: float = 2.0) -> None:
        self._stopping.set()
        acquired = self._native_guard.acquire(blocking=False)
        if not acquired:
            deadline = time.monotonic() + timeout
            acquired = self._native_guard.acquire(timeout=max(0.0, timeout))
            timeout = max(0.0, deadline - time.monotonic())
        if not acquired:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        try:
            self._scope.terminate(timeout=timeout)
        finally:
            self._native_guard.release()

    @property
    def stopping(self) -> bool:
        """Whether containment or a dispatched control failure fenced this worker."""
        return self._stopping.is_set()

    def require_alive(self) -> None:
        """Bound native contention, then observe the retained worker's current health.

        Native membership checks do not await host callbacks or worker wire
        replies. Waiting briefly for their guard avoids refusing a healthy
        concurrent call; expiry never closes the other guard owner.
        """
        if self._stopping.is_set():
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        if not self._native_guard.acquire(timeout=_WORKER_NATIVE_HEALTH_WAIT_SECONDS):
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        try:
            if self._stopping.is_set() or self._channel is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            if self._authorization is not None:
                self._authorization.require_healthy()
            self._require_process_alive()
        finally:
            self._native_guard.release()

    def close(self, *, deadline: float | None = None) -> None:
        """Fence calls and terminate the complete owned process scope."""
        self._close_resources(deadline=deadline, retire_listeners=True)

    def _close_resources(self, *, deadline: float | None, retire_listeners: bool) -> None:
        self._stopping.set()
        failures: list[BaseException] = []
        if self._authorization is not None:
            try:
                self._authorization.close()
            except BaseException as error:
                failures.append(error)
        # Contain first: an operation may be waiting for the caller's profile
        # guard. Do not wait for its transport lock while it is still alive.
        try:
            self._contain_native_process(timeout=2.0 if deadline is None else max(0.0, deadline - time.monotonic()))
        except BaseException as error:
            failures.append(error)
        self._close_worker_channel(self._lock, False, deadline, failures)
        self._close_worker_channel(self._operation_lock, True, deadline, failures)
        if retire_listeners:
            try:
                release_worker_resources(*self._listener_cleanup, *self._pending_channel_cleanup)
            except BaseException as error:
                failures.append(error)
        if len(failures) == 1:
            raise failures[0]
        if failures:
            raise BaseExceptionGroup("Profile worker release failed", failures)

    def settle(self, *, deadline: float | None = None) -> None:
        """Join authorization callbacks after releasing the profile admission guard."""
        if self._authorization is not None:
            if deadline is None:
                self._authorization.settle()
            else:
                self._authorization.settle(timeout=max(0.0, deadline - time.monotonic()))

    def _close_worker_channel(
        self,
        lock: RLock,
        operation: bool,
        deadline: float | None,
        failures: list[BaseException],
    ) -> None:
        """Release one channel under its original lock and retain it when native close fails."""
        acquired = lock.acquire(timeout=2.0 if deadline is None else max(0.0, deadline - time.monotonic()))
        if acquired:
            try:
                channel = self._operation_channel if operation else self._channel
                if channel is not None:
                    try:
                        channel.close()
                    except BaseException as error:
                        failures.append(error)
                    else:
                        if operation:
                            self._operation_channel = None
                        else:
                            self._channel = None
            finally:
                lock.release()
        else:
            failures.append(RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED))
