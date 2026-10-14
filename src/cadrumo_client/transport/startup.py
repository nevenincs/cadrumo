"""Bounded connection to the native owner and authenticated runtime handshake."""

from __future__ import annotations

import asyncio
import time
from logging import DEBUG, ERROR, WARNING
from typing import Protocol

from cadrumo.core.async_cleanup import (
    async_cleanup_failures,
    attach_async_cleanup_error,
    await_cancellation_complete,
    close_async_resources,
)
from cadrumo.core.diagnostic_log import diagnostic_error_fields, diagnostic_event, diagnostic_scope
from cadrumo.core.logging import get_logger
from cadrumo.core.startup_phase_log import startup_phase

from ..contracts.contracts import ByteChannel, ClientHello, RefusalCode, RefusalError
from ..contracts.deadline_budget import deadline_after, remaining_budget
from .framing import VerifiedConnection
from .transport_cleanup import TransportCleanup

_LOGGER = get_logger(__name__)


class EndpointConnector(Protocol):
    """Native owner verification before any wire handshake or profile secret."""

    @property
    def storage_identity(self) -> str:
        """Return the physical root identity used to select this endpoint."""
        ...

    def connect(self, *, timeout: float) -> ByteChannel:
        """Connect to a native verified peer, or return a typed refusal."""
        ...


def _carry_cleanup_owner(target: BaseException, source: BaseException) -> None:
    """Keep failed startup owners visible after cancellation or deadline mapping."""
    for failure in async_cleanup_failures(source):
        attach_async_cleanup_error(target, failure)


class LaunchDoor:
    """Connect to an existing owner without provisioning or starting a process."""

    def __init__(
        self,
        endpoint: EndpointConnector,
        *,
        expected: ClientHello,
    ) -> None:
        """Bind a native endpoint to the exact expected root and installed cohort."""
        if endpoint.storage_identity != expected.storage_identity:
            raise RefusalError(RefusalCode.ROOT_MISMATCH)
        self._endpoint = endpoint
        self._expected = expected

    async def _connect(self, deadline: float) -> VerifiedConnection:
        def connect() -> VerifiedConnection:
            channel = self._endpoint.connect(timeout=min(0.5, remaining_budget(deadline)))
            return VerifiedConnection(channel, expected=self._expected, deadline=deadline)

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
                    TransportCleanup(connection), task_name="runtime-connect-close", primary_error=None
                )

            try:
                await await_cancellation_complete(
                    discard(), task_name="runtime-connect-cleanup", cancellation=cancellation
                )
            except asyncio.CancelledError as retained:
                _carry_cleanup_owner(retained, retained)
                raise
            raise

    async def open(self, *, timeout: float = 10) -> VerifiedConnection:
        """Return a peer/cohort-verified connection without transmitting credentials."""
        with diagnostic_scope():
            started = time.monotonic()
            diagnostic_event(_LOGGER, "runtime_connect_started", fields={"timeout_seconds": timeout})
            opened: VerifiedConnection | None = None
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
                        TransportCleanup(opened),
                        task_name="runtime-connect-result-diagnostic-close",
                        primary_error=error,
                    )
                refusal = isinstance(error, RefusalError)
                cancelled = isinstance(error, asyncio.CancelledError)
                diagnostic_event(
                    _LOGGER,
                    "runtime_connect_finished",
                    fields={
                        **diagnostic_error_fields(error),
                        "outcome": "cancelled" if cancelled else "refused" if refusal else "failed",
                        "reason_code": (
                            error.reason.value
                            if isinstance(error, RefusalError)
                            else "operation_cancelled"
                            if cancelled
                            else "unexpected_failure"
                        ),
                        "elapsed_seconds": time.monotonic() - started,
                        "cleanup_incomplete": bool(async_cleanup_failures(error)),
                    },
                    level=DEBUG if cancelled else WARNING if refusal else ERROR,
                    primary_error=error,
                )
                raise
            return opened

    async def _open_connection(self, *, timeout: float) -> VerifiedConnection:
        deadline = deadline_after(timeout)
        opened: VerifiedConnection | None = None
        try:
            async with asyncio.timeout(timeout):
                try:
                    with startup_phase(_LOGGER, "existing_connect"):
                        opened = await self._connect(deadline)
                        return opened
                except RefusalError as error:
                    if error.reason is not RefusalCode.ENDPOINT_NOT_READY:
                        raise
                    raise RefusalError(RefusalCode.UNAVAILABLE) from error
        except TimeoutError as error:
            refusal = RefusalError(RefusalCode.DEADLINE_EXCEEDED)
            if isinstance(error.__cause__, asyncio.CancelledError):
                _carry_cleanup_owner(refusal, error.__cause__)
            raise refusal from error

        except BaseException as error:
            if opened is not None:
                await close_async_resources(
                    TransportCleanup(opened), task_name="runtime-startup-diagnostic-close", primary_error=error
                )
            raise
