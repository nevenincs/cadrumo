"""Exact-profile registered M303 attestation from the CLI."""

from __future__ import annotations

from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ...application.modelo.m303_attestation_operation import (
    MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
    ModeloWorkM303AttestationPublicResultV2,
    ModeloWorkM303AttestationRequest,
)
from ...application.user_profile.access_contracts import AccessDenialCode
from ...core.operations import OperationEffect


def run_modelo_m303_attestation(
    client: FrontendClient,
    request: ModeloWorkM303AttestationRequest,
    *,
    timeout: float = 120,
) -> RegisteredOperationCompletion[ModeloWorkM303AttestationPublicResultV2]:
    """Submit one explicit period and bind the receipt to its exact coordinate."""
    if request.profile_id != client.profile_id:
        raise FrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
    if request.period is None:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
        subject_ref=request.subject_ref,
        result_type=ModeloWorkM303AttestationPublicResultV2,
        request_version=2,
        result_version=2,
        timeout=timeout,
    )
    receipt = completed.projection
    if (
        not isinstance(receipt, ModeloWorkM303AttestationPublicResultV2)
        or receipt.profile_id != request.profile_id
        or receipt.work_unit_id is not None
        or receipt.period != request.period
        or receipt.filing_year != request.period.filing_year
        or completed.effect is not OperationEffect.UPDATED
    ):
        raise invalid_completion_error(completed)
    return completed


__all__ = ["run_modelo_m303_attestation"]
