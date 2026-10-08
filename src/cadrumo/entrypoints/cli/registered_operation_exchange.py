"""Correlate registered CLI exchanges with one fixed admitted frontend identity."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.operations.frontend_requests import (
    OperationResponseApplyRequestV1,
    OperationResponseRejectRequestV1,
)
from ...application.operations.registry import (
    OperationFrontendProjection,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.deadline_budget import remaining_budget
from ...application.runtime.operation_access import (
    RuntimeOperationManage,
    RuntimeOperationReply,
    RuntimeOperationRequest,
)
from ...core.operations import OperationEffect
from .registered_operation_contracts import RegisteredOperationProgress


@dataclass(frozen=True, slots=True)
class RegisteredOperationExchange:
    """Correlate every bounded exchange to one fixed admitted frontend session."""

    client: RuntimeFrontendClient
    profile_id: UUID
    session_id: UUID
    frontend: OperationFrontendProjection
    deadline: float
    call_deadline: Callable[[], float]
    progress: RegisteredOperationProgress

    def __call__(self, request: RuntimeOperationRequest) -> RuntimeOperationReply:
        """Preserve effect uncertainty and refuse identity drift before and after the exchange."""
        remaining_budget(self.deadline)
        require_registered_frontend_identity(
            self.client, self.profile_id, self.session_id, self.frontend, RuntimeRefusalCode.CONNECTION_CLOSED
        )
        if isinstance(request, RuntimeOperationManage) and isinstance(
            request.management, OperationResponseApplyRequestV1 | OperationResponseRejectRequestV1
        ):
            self.progress.effect = OperationEffect.UNKNOWN
        reply = self.client.operation(request, deadline=self.call_deadline())
        if reply.request_id != request.request_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        require_registered_frontend_identity(
            self.client, self.profile_id, self.session_id, self.frontend, RuntimeRefusalCode.CONNECTION_CLOSED
        )
        remaining_budget(self.deadline)
        return reply


def require_registered_frontend_identity(
    client: RuntimeFrontendClient,
    profile_id: UUID,
    session_id: UUID,
    frontend: OperationFrontendProjection,
    refusal: RuntimeRefusalCode,
) -> None:
    """Require the same admitted identity at its original transport correlation boundary."""
    if client.profile_id != profile_id or client.session_id != session_id or client.frontend is not frontend:
        raise RuntimeRefusalError(refusal)
