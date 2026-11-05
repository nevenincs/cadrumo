"""Authenticated CLI bridge for the credit-resolution operations of one persisted calculation revision."""

from __future__ import annotations

from typing import Never

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error
from cadrumo_client.transport.frontend_client import FrontendClient

from ...application.modelo.credit_resolution_contracts import (
    MODELO_CREDIT_RESOLUTION_ACCEPT_OPERATION_DEFINITION_ID,
    MODELO_CREDIT_RESOLUTION_LIST_OPERATION_DEFINITION_ID,
    MODELO_CREDIT_RESOLUTION_REVOKE_OPERATION_DEFINITION_ID,
    CreditResolutionAcceptRequest,
    CreditResolutionListProjection,
    CreditResolutionListRequest,
    CreditResolutionMutationProjection,
    CreditResolutionRefusalProjection,
    CreditResolutionRequest,
    CreditResolutionRevokeRequest,
    CreditResolutionRowProjection,
)
from ...application.modelo.credit_resolution_repository import CREDIT_RESOLUTION_MESSAGE_LOCALE_KEYS
from ...core.operations import OperationEffect, OperationTerminalCondition
from .modelo_work_disagreement_payloads import DisagreementResolutionPayload, DisagreementSourcePayload

__all__ = [
    "accept_credit_resolution",
    "list_credit_resolutions",
    "resolution_payload",
    "revoke_credit_resolution_for_cli",
]

_SETTLEMENT_SECONDS = 120.0


def resolution_payload(row: CreditResolutionRowProjection) -> DisagreementResolutionPayload:
    """Restate one projected resolution as the command's typed JSON payload."""
    return DisagreementResolutionPayload(
        finding_id=row.finding_id,
        key=row.key,
        reached_casillas=[str(casilla) for casilla in row.reached_casillas],
        sources=[
            DisagreementSourcePayload(role=source.role.value, source_family=source.source_family, value=source.value)
            for source in row.sources
        ],
        accepted_role=row.accepted_role.value,
        reason=row.reason,
        state=row.state.value,
        resolved_at=row.resolved_at.isoformat(),
        resolved_by_session=row.resolved_by_session,
        revoked_at=None if row.revoked_at is None else row.revoked_at.isoformat(),
        revoked_by_session=row.revoked_by_session,
        revision_id=row.revision_id,
        applies=row.applies,
    )


def _raise_refusal(
    completed: RegisteredOperationCompletion[CreditResolutionMutationProjection],
    refusal: CreditResolutionRefusalProjection,
) -> Never:
    if (
        completed.terminal_condition is not OperationTerminalCondition.REFUSED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code != refusal.code
    ):
        raise invalid_completion_error(completed)
    raise CliRefusedBoundaryError(
        translated_message=CREDIT_RESOLUTION_MESSAGE_LOCALE_KEYS[refusal.reason],
        context={
            "operation_id": str(completed.operation_id),
            "terminal_condition": completed.terminal_condition.value,
            "effect": completed.effect.value,
            "refusal_code": refusal.code,
            "reason": refusal.reason,
            "finding_id": refusal.finding_id,
        },
    )


def _mutation(
    client: FrontendClient,
    request: CreditResolutionRequest,
    *,
    work_unit_id: str,
    definition_id: str,
    outcome: str,
) -> CreditResolutionRowProjection:
    completed = run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=work_unit_id,
        result_type=CreditResolutionMutationProjection,
        request_version=1,
        result_version=1,
        timeout=_SETTLEMENT_SECONDS,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    if (
        projection.profile_id != client.profile_id
        or projection.calculation_revision_id != request.calculation_revision_id
    ):
        raise invalid_completion_error(completed)
    if projection.outcome == "refused":
        if projection.refusal is None:
            raise invalid_completion_error(completed)
        _raise_refusal(completed, projection.refusal)
    resolution = projection.resolution
    if (
        projection.outcome != outcome
        or resolution is None
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.UPDATED
        or completed.refusal_code is not None
    ):
        raise invalid_completion_error(completed)
    return resolution


def accept_credit_resolution(
    client: FrontendClient, *, work_unit_id: str, request: CreditResolutionAcceptRequest
) -> CreditResolutionRowProjection:
    """Accept one disagreement of a persisted calculation through the profile worker."""
    return _mutation(
        client,
        request,
        work_unit_id=work_unit_id,
        definition_id=MODELO_CREDIT_RESOLUTION_ACCEPT_OPERATION_DEFINITION_ID,
        outcome="accepted",
    )


def revoke_credit_resolution_for_cli(
    client: FrontendClient, *, work_unit_id: str, request: CreditResolutionRevokeRequest
) -> CreditResolutionRowProjection:
    """Take back one accepted disagreement through the profile worker."""
    return _mutation(
        client,
        request,
        work_unit_id=work_unit_id,
        definition_id=MODELO_CREDIT_RESOLUTION_REVOKE_OPERATION_DEFINITION_ID,
        outcome="revoked",
    )


def list_credit_resolutions(
    client: FrontendClient, *, work_unit_id: str, request: CreditResolutionListRequest
) -> tuple[CreditResolutionRowProjection, ...]:
    """Read every resolution one declaration holds through the profile worker."""
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_CREDIT_RESOLUTION_LIST_OPERATION_DEFINITION_ID,
        subject_ref=work_unit_id,
        result_type=CreditResolutionListProjection,
        request_version=1,
        result_version=1,
        timeout=_SETTLEMENT_SECONDS,
        allow_refusal_detail=False,
    )
    projection = completed.projection
    if (
        projection.profile_id != client.profile_id
        or projection.calculation_revision_id != request.calculation_revision_id
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
    ):
        raise invalid_completion_error(completed)
    return projection.resolutions
