"""Exact-session censal transport exchange and request correlation."""

from __future__ import annotations

from uuid import UUID

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.operation_access import (
    OperationReply,
    OperationRequest,
)
from cadrumo_client.transport.frontend_client import (
    FrontendClient,
)


def _require_session(client: FrontendClient, session_id: UUID) -> None:
    if client.session_id != session_id:
        raise RefusalError(RefusalCode.CONNECTION_CLOSED)


def _exchange(
    client: FrontendClient,
    session_id: UUID,
    request: OperationRequest,
    *,
    deadline: float,
) -> OperationReply:
    _require_session(client, session_id)
    reply = client.operation(request, deadline=deadline)
    _require_session(client, session_id)
    if getattr(reply, "request_id", None) != getattr(request, "request_id", None):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return reply
