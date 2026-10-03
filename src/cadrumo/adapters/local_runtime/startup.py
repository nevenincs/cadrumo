"""One bounded launch door over native ownership, manager control and readiness."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Literal, Protocol

from ...application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeClientHello,
    RuntimeRefusalCode,
    RuntimeRefusalError,
)
from ...application.runtime.deadline_budget import deadline_after, remaining_budget
from ...application.runtime.management import RuntimeUserManager
from ...core.async_cleanup import (
    AsyncResourceCleanupError,
    attach_async_cleanup_error,
    await_cancellation_complete,
    close_async_resources,
)
from ...core.logging import LogExtra, get_logger
from .framing import RuntimeTransportCleanup, VerifiedRuntimeConnection

_LOGGER = get_logger(__name__)


def _log_startup_phase(
    phase: Literal["existing_connect", "manager_inspect", "manager_start", "readiness_wait"],
    transition: Literal["enter", "leave"],
    elapsed: float,
    *,
    primary_error: BaseException | None = None,
) -> None:
    """Keep diagnostic failures from replacing an existing product primary."""
    try:
        _LOGGER.info(
            "runtime_startup phase=%s transition=%s elapsed_seconds=%.6f",
            phase,
            transition,
            elapsed,
            extra=LogExtra(
                {"startup_phase": phase, "transition": transition, "elapsed_seconds": elapsed}
            ).for_logging(),
        )
    except Exception:
        return
    except BaseException:
        if primary_error is None:
            raise


@contextmanager
def _startup_phase(
    phase: Literal["existing_connect", "manager_inspect", "manager_start", "readiness_wait"],
) -> Generator[None]:
    """Emit only fixed phase names and elapsed native monotonic seconds."""
    started = time.monotonic()
    primary: list[BaseException] = []
    _log_startup_phase(phase, "enter", 0.0)
    try:
        yield
    except BaseException as error:
        primary.append(error)
        raise
    finally:
        elapsed = time.monotonic() - started
        _log_startup_phase(phase, "leave", elapsed, primary_error=primary[0] if primary else None)


class RuntimeEndpointConnector(Protocol):
    """Native owner verification before any wire handshake or profile secret."""

    @property
    def storage_identity(self) -> str:
        """Return the physical root identity used to select this endpoint."""
        ...

    def connect(self, *, timeout: float) -> RuntimeByteChannel:
        """Connect to a native verified peer, or return a typed refusal."""
        ...


def _carry_cleanup_owner(target: BaseException, source: BaseException) -> None:
    """Keep failed startup owners visible after cancellation or deadline mapping."""
    for name in ("async_cleanup_error", "cleanup_error"):
        failure = source.__dict__.get(name)
        if isinstance(failure, BaseException) and not isinstance(failure, AsyncResourceCleanupError):
            failure = failure.__dict__.get("async_cleanup_error")
        if isinstance(failure, AsyncResourceCleanupError):
            attach_async_cleanup_error(target, failure)


class RuntimeLaunchDoor:
    """Connect first, otherwise request existing provisioning once and await readiness.

    This is not admission, an operation supervisor or a direct-process launcher.
    A manager start may complete after cancellation/timeout; no rollback or
    service stop is implied. Another invocation always attempts connection first.
    Missing supported provisioning refuses rather than spawning an uncontained
    process or changing autostart, lingering or unattended authorization.
    """

    def __init__(
        self,
        endpoint: RuntimeEndpointConnector,
        *,
        expected: RuntimeClientHello,
        manager: RuntimeUserManager | None = None,
        manager_factory: Callable[[], RuntimeUserManager | None] | None = None,
    ) -> None:
        """Bind a native endpoint to the exact expected root and installed cohort."""
        if endpoint.storage_identity != expected.storage_identity:
            raise RuntimeRefusalError(RuntimeRefusalCode.ROOT_MISMATCH)
        if manager is not None and manager_factory is not None:
            raise ValueError("supply one runtime manager source")
        self._endpoint = endpoint
        self._expected = expected
        self._manager = manager
        self._manager_factory = manager_factory

    async def _connect(self, deadline: float) -> VerifiedRuntimeConnection:
        def connect() -> VerifiedRuntimeConnection:
            channel = self._endpoint.connect(timeout=min(0.5, remaining_budget(deadline)))
            return VerifiedRuntimeConnection(channel, expected=self._expected, deadline=deadline)

        task = asyncio.create_task(asyncio.to_thread(connect))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError as cancellation:
            # Finish native I/O before returning endpoint ownership to the
            # caller. A callback alone would allow its directory/handle to be
            # closed while the connection thread still uses it.
            async def discard() -> None:
                connection = await task
                await close_async_resources(
                    RuntimeTransportCleanup(connection), task_name="runtime-connect-close", primary_error=None
                )

            try:
                await await_cancellation_complete(
                    discard(), task_name="runtime-connect-cleanup", cancellation=cancellation
                )
            except asyncio.CancelledError as retained:
                _carry_cleanup_owner(retained, retained)
                raise
            raise

    async def open(self, *, timeout: float = 10) -> VerifiedRuntimeConnection:
        """Return a peer/cohort-verified connection without transmitting credentials."""
        deadline = deadline_after(timeout)
        opened: VerifiedRuntimeConnection | None = None
        try:
            async with asyncio.timeout(timeout):
                try:
                    with _startup_phase("existing_connect"):
                        opened = await self._connect(deadline)
                        return opened
                except RuntimeRefusalError as error:
                    if error.reason is not RuntimeRefusalCode.ENDPOINT_NOT_READY:
                        raise
                manager = self._manager if self._manager_factory is None else self._manager_factory()
                if manager is None:
                    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
                with _startup_phase("manager_inspect"):
                    current = await manager.inspect()
                if not current.available or not current.provisioned:
                    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
                if not current.binding_matches:
                    raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
                # login_autostart is deliberately not an admission condition.
                # Native manager adapters re-check the binding before control.
                remaining_budget(deadline)
                with _startup_phase("manager_start"):
                    await manager.start()
                with _startup_phase("readiness_wait"):
                    while True:
                        remaining_budget(deadline)
                        try:
                            opened = await self._connect(deadline)
                            return opened
                        except RuntimeRefusalError as error:
                            if error.reason is not RuntimeRefusalCode.ENDPOINT_NOT_READY:
                                raise
                        await asyncio.sleep(min(0.05, remaining_budget(deadline)))
        except TimeoutError as error:
            refusal = RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
            if isinstance(error.__cause__, asyncio.CancelledError):
                _carry_cleanup_owner(refusal, error.__cause__)
            raise refusal from error

        except BaseException as error:
            if opened is not None:
                await close_async_resources(
                    RuntimeTransportCleanup(opened), task_name="runtime-startup-diagnostic-close", primary_error=error
                )
            raise
