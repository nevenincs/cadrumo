"""Bounded connection to the native owner and authenticated runtime handshake."""

from __future__ import annotations

import asyncio
import time
from logging import ERROR, INFO, WARNING
from typing import Protocol

from ...application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeClientHello,
    RuntimeRefusalCode,
    RuntimeRefusalError,
)
from ...application.runtime.deadline_budget import deadline_after, remaining_budget
from ...core.async_cleanup import (
    async_cleanup_failures,
    attach_async_cleanup_error,
    await_cancellation_complete,
    close_async_resources,
)
from ...core.diagnostic_log import diagnostic_error_fields, diagnostic_event, diagnostic_scope
from ...core.logging import get_logger
from ...core.startup_phase_log import startup_phase
from .framing import VerifiedRuntimeConnection
from .runtime_transport_cleanup import RuntimeTransportCleanup

_LOGGER = get_logger(__name__)


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
    for failure in async_cleanup_failures(source):
        attach_async_cleanup_error(target, failure)


class RuntimeLaunchDoor:
    """Connect to an existing owner without provisioning or starting a process."""

    def __init__(
        self,
        endpoint: RuntimeEndpointConnector,
        *,
        expected: RuntimeClientHello,
    ) -> None:
        """Bind a native endpoint to the exact expected root and installed cohort."""
        if endpoint.storage_identity != expected.storage_identity:
            raise RuntimeRefusalError(RuntimeRefusalCode.ROOT_MISMATCH)
        self._endpoint = endpoint
        self._expected = expected

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
        with diagnostic_scope():
            started = time.monotonic()
            diagnostic_event(_LOGGER, "runtime_connect_started", fields={"timeout_seconds": timeout})
            opened: VerifiedRuntimeConnection | None = None
            try:
                opened = await self._open_connection(timeout=timeout)
                diagnostic_event(
                    _LOGGER,
                    "runtime_connect_finished",
                    fields={
                        "outcome": "connected",
                        "elapsed_seconds": time.monotonic() - started,
                        "runtime_boot_id": str(opened.hello.boot_id),
                        "runtime_version": opened.hello.product_version,
                    },
                )
            except BaseException as error:
                if opened is not None:
                    await close_async_resources(
                        RuntimeTransportCleanup(opened),
                        task_name="runtime-connect-result-diagnostic-close",
                        primary_error=error,
                    )
                refusal = isinstance(error, RuntimeRefusalError)
                cancelled = isinstance(error, asyncio.CancelledError)
                diagnostic_event(
                    _LOGGER,
                    "runtime_connect_finished",
                    fields={
                        **diagnostic_error_fields(error),
                        "outcome": "cancelled" if cancelled else "refused" if refusal else "failed",
                        "reason_code": (
                            error.reason.value
                            if isinstance(error, RuntimeRefusalError)
                            else "operation_cancelled"
                            if cancelled
                            else "unexpected_failure"
                        ),
                        "elapsed_seconds": time.monotonic() - started,
                        "cleanup_incomplete": bool(async_cleanup_failures(error)),
                    },
                    level=INFO if cancelled else WARNING if refusal else ERROR,
                    primary_error=error,
                )
                raise
            return opened

    async def _open_connection(self, *, timeout: float) -> VerifiedRuntimeConnection:
        deadline = deadline_after(timeout)
        opened: VerifiedRuntimeConnection | None = None
        try:
            async with asyncio.timeout(timeout):
                try:
                    with startup_phase(_LOGGER, "existing_connect"):
                        opened = await self._connect(deadline)
                        return opened
                except RuntimeRefusalError as error:
                    if error.reason is not RuntimeRefusalCode.ENDPOINT_NOT_READY:
                        raise
                    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from error
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
