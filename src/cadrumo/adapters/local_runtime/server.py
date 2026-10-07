"""Bounded concurrent transport hosting over native owner-verified endpoints."""

from __future__ import annotations

import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from threading import BoundedSemaphore, Event, RLock
from typing import Protocol
from uuid import UUID, uuid4

from ...application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
    RuntimeShutdownIncompleteError,
)
from ...application.runtime.profile_access import (
    RuntimeProfileDrainResult,
    RuntimeProfileHandler,
)
from ...core.async_cleanup import AsyncResourceCleanupError, attach_async_cleanup_error
from ...core.diagnostic_log import diagnostic_event
from ...core.logging import get_logger
from ...core.startup_phase_log import startup_phase
from .runtime_transport_cleanup import RuntimeTransportCleanup, close_runtime_transport_after_failure
from .server_connection_handling import RuntimeConnectionHandling

_LOGGER = get_logger(__name__)


class RuntimeListener(Protocol):
    """Exclusive native ownership with bounded acceptance and verified peers."""

    @property
    def storage_identity(self) -> str:
        """Return the canonical root identity selected by the native endpoint."""
        ...

    def listen(self) -> None:
        """Claim ownership, refusing any existing live owner."""
        ...

    def accept(self, *, timeout: float) -> RuntimeByteChannel:
        """Accept a kernel-verified peer within the supplied deadline."""
        ...

    def close(self) -> None:
        """Release native listener ownership after accepted channels settle."""
        ...


class RuntimeTransportServer(RuntimeConnectionHandling):
    """Host the application-owned profile admission door.

    Each unauthenticated connection has bounded I/O and its own identity. The
    fixed worker count bounds peer resource consumption. Operation execution
    belongs to the application supervisor, never to this transport pool.
    """

    DRAIN_SECONDS = 15.0

    def __init__(
        self,
        listener: RuntimeListener,
        *,
        product_version: str,
        stop: Event,
        profiles: RuntimeProfileHandler | None = None,
        boot_id: UUID | None = None,
        authority_generation: str | None = None,
    ) -> None:
        """Bind one endpoint and a fresh process boot, without claiming ownership yet."""
        self.listener = listener
        self._listener_owner = RuntimeTransportCleanup(listener)
        self.stop = stop
        self.profiles = profiles
        self.identity = RuntimeServerHello(
            product_version=product_version,
            storage_identity=listener.storage_identity,
            boot_id=boot_id or uuid4(),
            authority_generation=authority_generation,
        )
        self.ready = Event()
        self._failed = Event()
        self._slots = BoundedSemaphore(32)
        self._channels_guard = RLock()
        self._channels: dict[int, RuntimeTransportCleanup] = {}
        self._requests: set[Future[None]] = set()
        self._drain_guard = RLock()
        self._accept_tick: float | None = None

    def accept_tick_age(self) -> float | None:
        """Return seconds since the accept loop last turned, or ``None`` before it first ran.

        Each turn polls profile lifecycle and waits at most one bounded accept, so
        a growing age means the loop itself is blocked.
        """
        tick = self._accept_tick
        return None if tick is None else max(0.0, time.monotonic() - tick)

    def open_connection_count(self) -> int:
        """Return the number of accepted verified connections not yet closed."""
        # One atomic length read; a snapshot never waits on a serving thread.
        return len(self._channels)

    def serve(self) -> None:
        """Hold singleton ownership through all accepted connection cleanup."""
        incomplete = Event()
        primary_error: BaseException | None = None
        try:
            with startup_phase(_LOGGER, "listener_listen"):
                self.listener.listen()
            workers = ThreadPoolExecutor(max_workers=32, thread_name_prefix="cadrumo-ipc")
            try:
                self.ready.set()
                accept_error: BaseException | None = None
                try:
                    diagnostic_event(
                        _LOGGER,
                        "runtime_listener_ready",
                        fields={
                            "runtime_boot_id": str(self.identity.boot_id),
                            "runtime_version": self.identity.product_version,
                        },
                    )
                    self._accept_connections(workers)
                except BaseException as error:
                    accept_error = error
                    raise
                finally:
                    self.stop.set()
                    try:
                        diagnostic_event(
                            _LOGGER,
                            "runtime_listener_drain_started",
                            fields={"drain_timeout_seconds": self.DRAIN_SECONDS},
                            primary_error=accept_error,
                        )
                    finally:
                        deadline = time.monotonic() + self.DRAIN_SECONDS
                        try:
                            result = self._drain_owned_resources(deadline=deadline)
                        except BaseException:
                            incomplete.set()
                            raise
                        if result is not None and result.lacks_settlement_evidence:
                            self._failed.set()
            finally:
                workers.shutdown(wait=False, cancel_futures=True)
            if self._failed.is_set():
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        except BaseException as error:
            primary_error = error
            raise
        finally:
            self.ready.clear()
            if not incomplete.is_set():
                self._release_listener(primary_error)
            diagnostic_event(
                _LOGGER,
                "runtime_listener_stopped",
                fields={
                    "cleanup_incomplete": incomplete.is_set(),
                    "outcome": "incomplete" if incomplete.is_set() else "stopped",
                },
                primary_error=primary_error,
            )

    def _drain_owned_resources(self, *, deadline: float) -> RuntimeProfileDrainResult | None:
        if not self._drain_guard.acquire(timeout=max(0.0, deadline - time.monotonic())):
            raise RuntimeShutdownIncompleteError()
        try:
            result = None
            drain_error: BaseException | None = None
            incomplete = False
            try:
                if self.profiles is not None:
                    result = self.profiles.drain(deadline=deadline)
            except BaseException as error:
                drain_error = error
                incomplete = True
            with self._channels_guard:
                channels = tuple(self._channels.values())
                requests = tuple(self._requests)
            if self._close_registered_connections(channels, deadline):
                incomplete = True
            _, pending = wait(requests, timeout=max(0.0, deadline - time.monotonic()))
            with self._channels_guard:
                unsettled_transport = bool(self._channels or self._requests)
            if _drain_has_unsettled_custody(incomplete, pending, unsettled_transport, result):
                raise RuntimeShutdownIncompleteError() from drain_error
            return result
        finally:
            self._drain_guard.release()

    def _release_listener(self, primary_error: BaseException | None, *, deadline: float | None = None) -> None:
        try:
            self._listener_owner.close_now(deadline=deadline)
        except BaseException as release_error:
            cleanup_error = AsyncResourceCleanupError(
                (self._listener_owner,),
                (release_error,),
                retry_task_name="runtime-listener-cleanup",
                close_attempts=1,
            )
            if primary_error is None:
                raise cleanup_error from release_error
            attach_async_cleanup_error(
                primary_error,
                cleanup_error,
                note="Listener cleanup also failed; retry through the attached async_cleanup_error",
            )

    def _accept_connections(self, workers: ThreadPoolExecutor) -> None:
        while not self.stop.is_set():
            self._accept_tick = time.monotonic()
            if self.profiles is not None:
                self.profiles.poll()
            if self.stop.is_set():
                return
            try:
                channel = self.listener.accept(timeout=0.2)
            except RuntimeRefusalError as error:
                if self._accept_refusal_can_retry(error):
                    continue
                raise
            except BaseException as error:
                self._retain_channel_cleanup(error)
                raise
            channel_owner = self._channel_owner(channel)
            if self.stop.is_set() or not self._slots.acquire(blocking=False):
                self._close_owned_channel(channel_owner)
                continue
            future = self._submit_connection_worker(workers, channel)
            with self._channels_guard:
                self._requests.add(future)
            future.add_done_callback(self._forget_request)

    def _close_registered_connections(self, channels: tuple[RuntimeTransportCleanup, ...], deadline: float) -> bool:
        """Attempt all retained channel owners and report incomplete cleanup honestly."""
        incomplete = False
        for channel_owner in channels:
            try:
                self._close_owned_channel(channel_owner, deadline=deadline)
            except BaseException:
                incomplete = True
        return incomplete

    def _accept_refusal_can_retry(self, error: RuntimeRefusalError) -> bool:
        """Retry only ordinary peer refusals with no unreleased cleanup owner."""
        retained = self._retain_channel_cleanup(error)
        if retained is not None and not retained.released:
            self._failed.set()
            self.stop.set()
            return False
        return error.reason in {
            RuntimeRefusalCode.DEADLINE_EXCEEDED,
            RuntimeRefusalCode.PEER_UNTRUSTED,
            RuntimeRefusalCode.CONNECTION_CLOSED,
        }

    def _submit_connection_worker(self, workers: ThreadPoolExecutor, channel: RuntimeByteChannel) -> Future[None]:
        """Transfer a reserved slot to its worker or complete the original failure cleanup."""
        try:
            future = workers.submit(self._connection, channel)
        except BaseException as error:
            try:
                close_runtime_transport_after_failure(channel, error)
                self._retain_channel_cleanup(error, channel=channel)
            finally:
                self._slots.release()
            raise
        return future

    def _forget_request(self, request: Future[None]) -> None:
        with self._channels_guard:
            if request.cancelled():
                self._failed.set()
                self.stop.set()
            else:
                error = request.exception()
                if error is not None:
                    self._retain_channel_cleanup(error, require_registered=True)
                    self._failed.set()
                    self.stop.set()
            self._requests.discard(request)


def _drain_has_unsettled_custody(
    incomplete: bool,
    pending: set[Future[None]],
    unsettled_transport: bool,
    result: RuntimeProfileDrainResult | None,
) -> bool:
    """Require every transport, request, and profile custody receipt before release."""
    return bool(
        incomplete
        or pending
        or unsettled_transport
        or (result is not None and (result.uncontained or result.unsettled))
    )
