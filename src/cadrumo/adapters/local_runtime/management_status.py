"""Passive, bounded native listener probe for runtime management status."""

from __future__ import annotations

import asyncio
import math
import time
from uuid import uuid4

from ...application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.management_status import RuntimeListenerState
from ...application.runtime.transport import RuntimeStatusRequest
from ...core.async_cleanup import AsyncResourceCleanupError, async_cleanup_failures, has_async_cleanup_failure
from .framing import RuntimeTransportCleanup, VerifiedRuntimeConnection, close_runtime_transport_after_failure
from .startup import RuntimeEndpointConnector


def probe_runtime_listener(
    endpoint: RuntimeEndpointConnector, *, expected: RuntimeClientHello, timeout: float = 3
) -> RuntimeListenerState:
    """Inspect an existing owner only; never call a launch or manager control door."""
    if not math.isfinite(timeout) or timeout <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    if endpoint.storage_identity != expected.storage_identity:
        return RuntimeListenerState.REFUSED
    deadline = time.monotonic() + timeout
    connection: VerifiedRuntimeConnection | None = None
    try:
        channel = endpoint.connect(timeout=timeout)
        connection = VerifiedRuntimeConnection(channel, expected=expected, deadline=deadline)
        status = connection.status(RuntimeStatusRequest(request_id=uuid4()), deadline=deadline)
    except BaseException as error:
        # Framing already retires failed handshakes/exchanges and retains their
        # original owner. A pre-dispatch deadline also needs one release attempt.
        if connection is not None:
            close_runtime_transport_after_failure(connection, error)
        if has_async_cleanup_failure(error):
            raise
        if not isinstance(error, (RuntimeRefusalError, OSError)):
            raise
        if isinstance(error, OSError):
            return RuntimeListenerState.UNKNOWN
        if error.reason is RuntimeRefusalCode.ENDPOINT_NOT_READY:
            return RuntimeListenerState.UNAVAILABLE
        if error.reason in {
            RuntimeRefusalCode.VERSION_MISMATCH,
            RuntimeRefusalCode.ROOT_MISMATCH,
            RuntimeRefusalCode.ENDPOINT_UNTRUSTED,
            RuntimeRefusalCode.PEER_UNTRUSTED,
            RuntimeRefusalCode.INVALID_FRAME,
        }:
            return RuntimeListenerState.REFUSED
        return RuntimeListenerState.UNKNOWN
    owner = RuntimeTransportCleanup(connection)
    try:
        owner.close_now()
    except BaseException as error:
        cleanup = AsyncResourceCleanupError(
            (owner,), (error,), retry_task_name="runtime-status-probe-release", close_attempts=1
        )
        for previous in async_cleanup_failures(error):
            cleanup = previous.merged_with(cleanup)
        if isinstance(error, asyncio.CancelledError):
            error.__dict__["async_cleanup_error"] = cleanup
            if isinstance(error.__dict__.get("cleanup_error"), AsyncResourceCleanupError):
                error.__dict__["cleanup_error"] = cleanup
            raise
        raise cleanup from error
    return RuntimeListenerState.READY if status.accepting_connections else RuntimeListenerState.DRAINING


__all__ = ["probe_runtime_listener"]
