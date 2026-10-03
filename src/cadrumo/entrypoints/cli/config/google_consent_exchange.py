"""Canonical google consent exchange stages for the human terminal."""

from __future__ import annotations

import time
from uuid import UUID

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.operations.registry import (
    OperationFrontendProjection,
)
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.runtime.operation_access import (
    RuntimeOperationReply,
    RuntimeOperationRequest,
)


def google_consent_remaining(deadline: float) -> float:
    """Use the original consent deadline for every exchange and result read."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    return remaining


def google_consent_exchange(
    client: RuntimeFrontendClient,
    profile_id: UUID,
    session_id: UUID,
    request: RuntimeOperationRequest,
    deadline: float,
) -> RuntimeOperationReply:
    """Correlate each exchange before and after the exact-profile client call."""
    if (
        client.profile_id != profile_id
        or client.session_id != session_id
        or client.frontend is not OperationFrontendProjection.CLI
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
    google_consent_remaining(deadline)
    reply = client.operation(request, deadline=deadline)
    if (
        client.profile_id != profile_id
        or client.session_id != session_id
        or client.frontend is not OperationFrontendProjection.CLI
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
    if reply.request_id != request.request_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return reply
