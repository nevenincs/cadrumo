"""Authenticated CLI bridge for the pension contribution certificate operations."""

from __future__ import annotations

from typing import Final, Never
from uuid import UUID

import typer
from pydantic import BaseModel

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error
from cadrumo_client.transport.frontend_client import FrontendClient

from ...application.prevision_social_contribution.contracts import (
    PREVISION_SOCIAL_LIST_OPERATION_DEFINITION_ID,
    PREVISION_SOCIAL_RECORD_OPERATION_DEFINITION_ID,
    PREVISION_SOCIAL_REMOVE_OPERATION_DEFINITION_ID,
)
from ...application.prevision_social_contribution.requests import (
    PrevisionSocialListRequest,
    PrevisionSocialRecordRequest,
    PrevisionSocialRemoveRequest,
)
from ...application.prevision_social_contribution.results import (
    PrevisionSocialListProjection,
    PrevisionSocialMutationProjection,
    PrevisionSocialRefusalProjection,
    PrevisionSocialRowProjection,
)
from ...core.errors.hierarchy import InternalInvariantError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .prevision_social_results import (
    PrevisionSocialListResult,
    PrevisionSocialRecordResult,
    PrevisionSocialRemoveResult,
    PrevisionSocialRowPayload,
)

_REFUSAL_EFFECTS = frozenset({OperationEffect.NONE, OperationEffect.PARTIAL})
"""A refusal leaves nothing, or only the certificate bytes custody kept before the record was refused."""

_REFUSAL_MESSAGE_LOCALE_KEYS: Final[dict[str, str]] = {
    "ejercicio_unsupported": "aggregation.prevision_social_contribution.errors.ejercicio_unsupported",
    "identity_mismatch": "aggregation.prevision_social_contribution.errors.identity_mismatch",
    "certificate_not_in_custody": "aggregation.prevision_social_contribution.errors.certificate_not_in_custody",
    "unplaced_clave": "aggregation.prevision_social_contribution.served.unplaced_clave",
    "indirect_match": "aggregation.prevision_social_contribution.served.indirect_match",
    "design_not_bundled": "aggregation.prevision_social_contribution.served.design_not_bundled",
    "same_plan_split_unstated": "aggregation.prevision_social_contribution.errors.same_plan_split_unstated",
    "beneficiary_out_of_scope": "aggregation.prevision_social_contribution.served.beneficiary_out_of_scope",
    "stale_revision": "aggregation.prevision_social_contribution.errors.stale_revision",
    "certificate_fingerprint_required": (
        "aggregation.prevision_social_contribution.errors.certificate_fingerprint_required"
    ),
    "certificate_file_unreadable": "aggregation.prevision_social_contribution.errors.certificate_file_unreadable",
    "certificate_fingerprint_mismatch": (
        "aggregation.prevision_social_contribution.errors.certificate_fingerprint_mismatch"
    ),
    "clave_pair_undefined": "aggregation.prevision_social_contribution.errors.clave_pair_undefined",
    "not_found": "aggregation.prevision_social_contribution.errors.not_found",
    "validation": "aggregation.prevision_social_contribution.errors.validation",
}


def _run[ProjectionT: BaseModel](
    ctx: typer.Context,
    request: BaseModel,
    *,
    definition_id: str,
    result_type: type[ProjectionT],
    allow_refusal_detail: bool,
) -> RegisteredOperationCompletion[ProjectionT]:
    profile_id = getattr(request, "profile_id", None)
    if not isinstance(profile_id, UUID):
        raise InternalInvariantError("pension contribution request has no typed profile identity")
    client: FrontendClient = require_profile_client(ctx, expected_profile_id=profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=result_type,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=allow_refusal_detail,
    )
    if getattr(completed.projection, "profile_id", None) != client.profile_id:
        raise invalid_completion_error(completed)
    return completed


def _raise_refusal(
    completed: RegisteredOperationCompletion[PrevisionSocialMutationProjection],
    refusal: PrevisionSocialRefusalProjection,
) -> Never:
    message = _REFUSAL_MESSAGE_LOCALE_KEYS.get(refusal.reason)
    if (
        message is None
        or completed.terminal_condition is not OperationTerminalCondition.REFUSED
        or completed.effect not in _REFUSAL_EFFECTS
        or completed.refusal_code != refusal.code
    ):
        raise invalid_completion_error(completed)
    raise CliRefusedBoundaryError(
        translated_message=message,
        context={
            "operation_id": str(completed.operation_id),
            "terminal_condition": completed.terminal_condition.value,
            "effect": completed.effect.value,
            "refusal_code": refusal.code,
            "reason": refusal.reason,
            "ejercicio": refusal.ejercicio,
        },
    )


def _row_payload(row: PrevisionSocialRowProjection) -> PrevisionSocialRowPayload:
    return PrevisionSocialRowPayload(
        ejercicio=row.ejercicio,
        issuer_ref=row.issuer_ref,
        issuer_name=row.issuer_legal_name,
        plan_ref=row.plan_ref,
        plan_name=row.plan_name,
        clave=row.clave.value,
        subclave=None if row.subclave is None else row.subclave.value,
        amount=row.amount.decimal,
        beneficiary=row.beneficiary.value,
        employer_same_plan=row.employer_contributed_to_same_plan,
        casilla_id=row.casilla_id,
        evidence_sha256=row.evidence_fingerprint,
        replaces_evidence_sha256=row.replaces_evidence_fingerprint,
        revision_id=row.revision_id,
    )


def _mutation(
    ctx: typer.Context,
    request: PrevisionSocialRecordRequest | PrevisionSocialRemoveRequest,
    *,
    definition_id: str,
    outcome: str,
) -> tuple[RegisteredOperationCompletion[PrevisionSocialMutationProjection], PrevisionSocialMutationProjection]:
    completed = _run(
        ctx,
        request,
        definition_id=definition_id,
        result_type=PrevisionSocialMutationProjection,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    if projection.outcome == "refused":
        if projection.refusal is None:
            raise invalid_completion_error(completed)
        _raise_refusal(completed, projection.refusal)
    if (
        projection.outcome != outcome
        or projection.count is None
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.UPDATED
        or completed.refusal_code is not None
    ):
        raise invalid_completion_error(completed)
    return completed, projection


def list_prevision_social(ctx: typer.Context, request: PrevisionSocialListRequest) -> PrevisionSocialListResult:
    """Read the stored contribution records of one ejercicio through the profile worker."""
    completed = _run(
        ctx,
        request,
        definition_id=PREVISION_SOCIAL_LIST_OPERATION_DEFINITION_ID,
        result_type=PrevisionSocialListProjection,
        allow_refusal_detail=False,
    )
    projection = completed.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or projection.ejercicio != request.ejercicio
    ):
        raise invalid_completion_error(completed)
    return PrevisionSocialListResult(
        bucket_id=str(request.profile_id),
        ejercicio=projection.ejercicio,
        rows=[_row_payload(row) for row in projection.rows],
        count=len(projection.rows),
    )


def record_prevision_social(ctx: typer.Context, request: PrevisionSocialRecordRequest) -> PrevisionSocialRecordResult:
    """Record or correct one contribution certificate through the profile worker."""
    completed, projection = _mutation(
        ctx,
        request,
        definition_id=PREVISION_SOCIAL_RECORD_OPERATION_DEFINITION_ID,
        outcome="recorded",
    )
    if projection.row is None or projection.count is None:
        raise invalid_completion_error(completed)
    return PrevisionSocialRecordResult(
        bucket_id=str(request.profile_id),
        row=_row_payload(projection.row),
        count=projection.count,
    )


def remove_prevision_social(ctx: typer.Context, request: PrevisionSocialRemoveRequest) -> PrevisionSocialRemoveResult:
    """Remove one contribution record through the profile worker."""
    completed, projection = _mutation(
        ctx,
        request,
        definition_id=PREVISION_SOCIAL_REMOVE_OPERATION_DEFINITION_ID,
        outcome="removed",
    )
    if projection.count is None or projection.row is not None:
        raise invalid_completion_error(completed)
    return PrevisionSocialRemoveResult(
        bucket_id=str(request.profile_id),
        ejercicio=request.ejercicio,
        issuer_ref=request.issuer_ref,
        plan_ref=request.plan_ref,
        clave=request.clave.value,
        subclave=None if request.subclave is None else request.subclave.value,
        count=projection.count,
    )


__all__ = ["list_prevision_social", "record_prevision_social", "remove_prevision_social"]
