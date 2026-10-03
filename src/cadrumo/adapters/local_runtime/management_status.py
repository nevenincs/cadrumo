"""Passive, bounded native listener probe for runtime management status."""

from __future__ import annotations

import time
from uuid import uuid4

from ...application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.deadline_budget import require_finite_budget
from ...application.runtime.management_status import RuntimeListenerState
from ...application.runtime.transport import RuntimeStatusRequest
from .framing import VerifiedRuntimeConnection
from .startup import RuntimeEndpointConnector


def probe_runtime_listener(
    endpoint: RuntimeEndpointConnector, *, expected: RuntimeClientHello, timeout: float = 3
) -> RuntimeListenerState:
    """Inspect an existing owner only; never call a launch or manager control door."""
    require_finite_budget(timeout)
    if endpoint.storage_identity != expected.storage_identity:
        return RuntimeListenerState.REFUSED
    deadline = time.monotonic() + timeout
    channel = None
    connection = None
    try:
        channel = endpoint.connect(timeout=timeout)
        connection = VerifiedRuntimeConnection(channel, expected=expected, deadline=deadline)
        status = connection.status(RuntimeStatusRequest(request_id=uuid4()), deadline=deadline)
        return RuntimeListenerState.READY if status.accepting_connections else RuntimeListenerState.DRAINING
    except RuntimeRefusalError as error:
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
    except OSError:
        return RuntimeListenerState.UNKNOWN
    finally:
        if connection is not None:
            connection.close()
        elif channel is not None:
            channel.close()


__all__ = ["probe_runtime_listener"]
