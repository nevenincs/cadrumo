"""Correlate registered CLI exchanges with one fixed admitted frontend identity."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from cadrumo.application.operations.frontend_requests import (
    OperationResponseApplyRequestV1,
    OperationResponseRejectRequestV1,
)
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
)
from cadrumo.core.operations import OperationEffect
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationProgress
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.deadline_budget import remaining_budget
from cadrumo_client.contracts.operation_access import (
    OperationManage,
    OperationReply,
    OperationRequest,
)
from cadrumo_client.transport.frontend_client import FrontendClient


@dataclass(frozen=True, slots=True)
class RegisteredOperationExchange:
    """Correlate every bounded exchange to one fixed admitted frontend session."""

    client: FrontendClient
    profile_id: UUID
    session_id: UUID
    frontend: OperationFrontendProjection
    deadline: float
    call_deadline: Callable[[], float]
    progress: RegisteredOperationProgress

    def __call__(self, request: OperationRequest) -> OperationReply:
        """Preserve effect uncertainty and refuse identity drift before and after the exchange."""
        remaining_budget(self.deadline)
        require_registered_frontend_identity(
            self.client, self.profile_id, self.session_id, self.frontend, RefusalCode.CONNECTION_CLOSED
        )
        if isinstance(request, OperationManage) and isinstance(
            request.management, OperationResponseApplyRequestV1 | OperationResponseRejectRequestV1
        ):
            self.progress.effect = OperationEffect.UNKNOWN
        reply = self.client.operation(request, deadline=self.call_deadline())
        if reply.request_id != request.request_id:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        require_registered_frontend_identity(
            self.client, self.profile_id, self.session_id, self.frontend, RefusalCode.CONNECTION_CLOSED
        )
        remaining_budget(self.deadline)
        return reply


def require_registered_frontend_identity(
    client: FrontendClient,
    profile_id: UUID,
    session_id: UUID,
    frontend: OperationFrontendProjection,
    refusal: RefusalCode,
) -> None:
    """Require the same admitted identity at its original transport correlation boundary."""
    if client.profile_id != profile_id or client.session_id != session_id or client.frontend is not frontend:
        raise RefusalError(refusal)
