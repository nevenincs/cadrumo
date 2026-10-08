"""Exact-session censal transport exchange and request correlation."""

from __future__ import annotations

from uuid import UUID

from ....adapters.local_runtime.frontend_client import (
    RuntimeFrontendClient,
)
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.runtime.operation_access import (
    RuntimeOperationReply,
    RuntimeOperationRequest,
)


def _require_session(client: RuntimeFrontendClient, session_id: UUID) -> None:
    if client.session_id != session_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)


def _exchange(
    client: RuntimeFrontendClient,
    session_id: UUID,
    request: RuntimeOperationRequest,
    *,
    deadline: float,
) -> RuntimeOperationReply:
    _require_session(client, session_id)
    reply = client.operation(request, deadline=deadline)
    _require_session(client, session_id)
    if getattr(reply, "request_id", None) != getattr(request, "request_id", None):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return reply
