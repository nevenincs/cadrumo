"""CLI bridge for supervised AEAT NIF verification capture."""

from __future__ import annotations

from uuid import UUID

import typer

from ...application.live.verify import VerifySurface
from ...application.live.verify_capture_operation import (
    VERIFY_NIF_IVA_CAPTURE_DEFINITION_ID,
    VERIFY_TGVI_CAPTURE_DEFINITION_ID,
    VerifyCapturePublicResultV1,
    VerifyCaptureRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.identity.tax_id import tax_id_identity_token
from ...core.identity_check_verdict import IdentityCheckVerdictValue
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


def read_verify_capture_for_cli(
    ctx: typer.Context,
    *,
    surface: VerifySurface,
    nif: str,
    expected: IdentityCheckVerdictValue | None,
) -> VerifyCapturePublicResultV1:
    """Return only a settled exact-profile public projection for one live check."""
    client = bound_profile_client(ctx)
    profile_id = UUID(str(client.profile_id))
    request = VerifyCaptureRequest(profile_id=profile_id, nif=nif, expected=expected)
    definition_id = (
        VERIFY_NIF_IVA_CAPTURE_DEFINITION_ID if surface is VerifySurface.NIF_IVA else VERIFY_TGVI_CAPTURE_DEFINITION_ID
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=VerifyCapturePublicResultV1,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, VerifyCapturePublicResultV1):
            raise ValueError("verify capture projection has an invalid type")
        if (
            projection.bucket_id != str(profile_id)
            or projection.surface is not surface
            or tax_id_identity_token(projection.nif) != tax_id_identity_token(nif)
            or projection.expected != expected
            or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or completed.refusal_code is not None
            or completed.effect not in {OperationEffect.UPDATED, OperationEffect.NONE}
        ):
            raise ValueError("verify capture result disagrees with its submitted scope or receipt")
    except Exception:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None
    return projection


__all__ = ["read_verify_capture_for_cli"]
