"""Canonical google consent exchange stages for the human terminal."""

from __future__ import annotations

import time
from uuid import UUID

from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
)
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.operation_access import (
    OperationReply,
    OperationRequest,
)
from cadrumo_client.transport.frontend_client import FrontendClient


def google_consent_remaining(deadline: float) -> float:
    """Use the original consent deadline for every exchange and result read."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RefusalError(RefusalCode.DEADLINE_EXCEEDED)
    return remaining


def google_consent_exchange(
    client: FrontendClient,
    profile_id: UUID,
    session_id: UUID,
    request: OperationRequest,
    deadline: float,
) -> OperationReply:
    """Correlate each exchange before and after the exact-profile client call."""
    if (
        client.profile_id != profile_id
        or client.session_id != session_id
        or client.frontend is not OperationFrontendProjection.CLI
    ):
        raise RefusalError(RefusalCode.CONNECTION_CLOSED)
    google_consent_remaining(deadline)
    reply = client.operation(request, deadline=deadline)
    if (
        client.profile_id != profile_id
        or client.session_id != session_id
        or client.frontend is not OperationFrontendProjection.CLI
    ):
        raise RefusalError(RefusalCode.CONNECTION_CLOSED)
    if reply.request_id != request.request_id:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return reply
